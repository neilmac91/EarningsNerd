"""SEC companyfacts fallback transport and parsing behind the XBRL service facade.

The existing user-facing fallback uses one limiter token wait and no circuit breaker.
Local XBRL instance parsing lives in xbrl_instance under the service's plain timeouts: parse cost is not SEC health.
"""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.services.sec_rate_limiter import sec_rate_limiter
from app.utils.sec_urls import companyfacts_url
from .config import EDGAR_IDENTITY
from .xbrl_cache import logger

# Cash concept candidates for the single-filing statement path, in priority order. The
# ASU 2016-18 restricted-cash total sits LAST (lowest priority): it only resolves when no
# unrestricted-cash tag is present — the JPM-class bank case whose only cash line is the
# migrated tag (data-quality plan P0-3). test_cash_registry_consistency.py pins this ordering
# across all three cash registries.
CASH_TAG_CANDIDATES: List[str] = [
    "CashAndCashEquivalentsAtCarryingValue",
    "Cash",
    "CashAndCashEquivalents",
    "CashCashEquivalentsAndShortTermInvestments",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
]


async def fallback_to_company_facts(
    service: Any,
    cik: str,
    accession_number: str,
) -> Optional[Dict[str, Any]]:
    """
    Fallback to SEC company facts API if EdgarTools financials not available.

    This replicates the logic from the legacy xbrl_service.py for cases
    where EdgarTools doesn't have the data.
    """
    # Keep the receiver: resolve its parser after the response, so class/instance patches intercept.
    import httpx

    logger.info(f"Falling back to SEC company facts API for CIK {cik}")

    try:
        facts_url = companyfacts_url(cik)

        # Route through the SEC rate limiter with a SINGLE token wait (execute, NOT
        # execute_with_backoff): this fallback runs inside user-facing summary generation, so it
        # fail-fasts rather than sleeping through the full backoff ladder (S4 review #3).
        # raise_for_status turns a non-200 into an exception, preserving "non-200 -> None" via the
        # outer except.
        async with httpx.AsyncClient() as client:
            async def _do_request() -> httpx.Response:
                resp = await client.get(
                    facts_url,
                    headers={"User-Agent": EDGAR_IDENTITY},
                    timeout=30.0,
                )
                resp.raise_for_status()
                return resp

            response = await sec_rate_limiter.execute(_do_request)
            data = response.json()
            return service._parse_company_facts(data, accession_number)

    except Exception as e:
        logger.error(f"Error in company facts fallback: {e}")
        return None


def _is_target(item: Dict, normalized_accession: Optional[str]) -> bool:
    return bool(
        normalized_accession
        and isinstance(item.get("accn"), str)
        and item["accn"].replace("-", "") == normalized_accession
    )


def _duration_penalty(item: Dict) -> int:
    """Distance from the standard duration for the item's form.

    Companyfacts reports several durations sharing one period end
    (Q4 + FY both end on the fiscal year end; Q3 + 9-month YTD both
    end on the quarter end). The standard statement value is the
    12-month figure for a 10-K and the 3-month figure for a 10-Q.
    Instant facts (no start) have a single duration; penalty 0.
    """
    start, end = item.get("start"), item.get("end")
    if not start:
        return 0
    try:
        days = (date.fromisoformat(end) - date.fromisoformat(start)).days
    except (ValueError, TypeError):
        return 0
    target_days = 365 if (item.get("form") or "").startswith("10-K") else 91
    return abs(days - target_days)


def filter_and_sort(data_list: list, max_items: int = 5) -> list:
    if not isinstance(data_list, list):
        return []

    valid_items = [
        item for item in data_list
        if isinstance(item, dict) and item.get("end")
    ]

    # Dedupe by period end: prefer the standard duration for the form,
    # then the most recently filed restatement.
    best_by_end: Dict[str, Dict] = {}
    for item in valid_items:
        incumbent = best_by_end.get(item["end"])
        if incumbent is None:
            best_by_end[item["end"]] = item
            continue
        key = (_duration_penalty(item), item.get("filed") or "")
        incumbent_key = (_duration_penalty(incumbent), incumbent.get("filed") or "")
        # Lower penalty wins; on a tie, later filed date wins.
        if key[0] < incumbent_key[0] or (key[0] == incumbent_key[0] and key[1] > incumbent_key[1]):
            best_by_end[item["end"]] = item

    sorted_items = sorted(
        best_by_end.values(),
        key=lambda x: x.get("end", ""),
        reverse=True
    )
    return sorted_items[:max_items]


def select_fact_data_with_concept(
    us_gaap: Dict, normalized_accession: Optional[str], fields: List[str], unit_keys: Tuple[str, ...] = ("USD",),
) -> Tuple[list, Optional[str]]:
    """Pick the candidate concept actually used by recent filings.

    Taking the first concept present is wrong: issuers retire tags over
    time (e.g. AAPL last reported `Revenues` in FY2018 and has used
    `RevenueFromContractWithCustomerExcludingAssessedTax` since), so a
    stale concept would shadow the live one and surface years-old
    values as "current". Prefer a concept with facts from the target
    filing; concepts absent from that accession are unavailable.
    """
    best_end: Optional[str] = None
    best_data: list = []
    best_tag: Optional[str] = None
    for field in fields:
        fact = us_gaap.get(field)
        if not (isinstance(fact, dict) and isinstance(fact.get("units"), dict)):
            continue
        for unit_key in unit_keys:
            data = fact["units"].get(unit_key) or []
            # No match means unavailable, not permission to use another filing.
            valid = [i for i in data if isinstance(i, dict) and i.get("end") and _is_target(i, normalized_accession)]
            if not valid:
                continue
            latest_end = max(i["end"] for i in valid)
            if best_end is None or latest_end > best_end:
                best_end, best_data = latest_end, valid
                best_tag = f"us-gaap:{field}"
            break  # first unit key with data for this concept
    return best_data, best_tag


def select_fact_data(
    us_gaap: Dict, normalized_accession: Optional[str],
    fields: List[str], unit_keys: Tuple[str, ...] = ("USD",),
) -> list:
    data, _raw_tag = select_fact_data_with_concept(us_gaap, normalized_accession, fields, unit_keys)
    return data


def append_items(
    result: Dict[str, List[Dict]], normalized_accession: Optional[str],
    metric: str, data: list, raw_tag: Optional[str] = None,
) -> None:
    from .fiscal_periods import fiscal_label
    from app.services.facts.concepts import _classify_duration

    target = [item for item in data if _is_target(item, normalized_accession)]
    anchor = max(target, key=lambda item: item.get("end", "")) if target else {}
    for item in filter_and_sort(data):
        label = {}
        # Classify the actual duration before treating the filing focus as a quarter.
        # Instant facts share the selected filing's report-period anchor.
        try:
            discrete = not item.get("start") or _classify_duration(
                date.fromisoformat(item["start"]), date.fromisoformat(item["end"])
            ) == "Q"
        except (ValueError, TypeError):
            discrete = False
        if discrete and (item.get("form") or "").removesuffix("/A") == "10-Q" and _is_target(item, normalized_accession):
            label = fiscal_label(item["end"], anchor.get("end"), anchor.get("fy"), anchor.get("fp"))
        result[metric].append({
            **label,
            "period": item.get("end"),
            "value": item.get("val"),
            "form": item.get("form"),
            "accn": item.get("accn"),
            # Preserve the selected source's duration; instant facts have no start.
            **({"period_start": item["start"]} if item.get("start") else {}),
            **({"raw_tag": raw_tag} if raw_tag is not None else {}),
        })


def parse_company_facts(
    facts_data: Dict,
    target_accession: str,
) -> Dict[str, List[Dict]]:
    """Parse SEC company facts API response."""
    result = {
        "revenue": [],
        "net_income": [],
        "total_assets": [],
        "total_liabilities": [],
        "cash_and_equivalents": [],
        "earnings_per_share": [],
    }

    normalized_accession = target_accession.replace("-", "") if target_accession else None

    try:
        facts = facts_data.get("facts", {})
        us_gaap = facts.get("us-gaap", {})

        if not isinstance(us_gaap, dict):
            return result

        append_items(result, normalized_accession, "revenue", select_fact_data(
            us_gaap, normalized_accession, ["Revenues", "Revenue", "RevenueFromContractWithCustomerExcludingAssessedTax",
             "SalesRevenueNet", "NetSales", "TotalRevenue"]))
        append_items(result, normalized_accession, "net_income", select_fact_data(
            us_gaap, normalized_accession, ["NetIncomeLoss", "ProfitLoss", "NetIncomeLossAvailableToCommonStockholdersBasic"]))
        append_items(result, normalized_accession, "total_assets", select_fact_data(us_gaap, normalized_accession, ["Assets"]))
        append_items(result, normalized_accession, "total_liabilities", select_fact_data(us_gaap, normalized_accession, ["Liabilities"]))
        cash_data, cash_tag = select_fact_data_with_concept(us_gaap, normalized_accession, CASH_TAG_CANDIDATES)
        append_items(result, normalized_accession, "cash_and_equivalents", cash_data, cash_tag)
        append_items(result, normalized_accession, "earnings_per_share", select_fact_data(
            us_gaap, normalized_accession, ["EarningsPerShareBasic", "EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"],
            unit_keys=("USD/shares", "USD", "pure")))

    except Exception as e:
        logger.warning(f"Error parsing company facts: {e}")

    return result
