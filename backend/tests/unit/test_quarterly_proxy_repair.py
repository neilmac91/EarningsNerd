"""The quarterly repair's proxy step (E211, ``app/services/proxy_fact_repair.py``).

Each shape is planted through the real writers as they ran before #1622: the companyfacts sync
(``_persist_companyfacts_payload``) and the per-filing writer (``process_filing_facts``) with the
authority ``extract_authoritative_values`` read then, under ``_before_the_fix``. Every planting sync, the
fixed ones (``_sync``) too, also runs as it did before #1682 (deployed 2026-10-28 23:13Z), which keeps each
restated year's own-report value as a non-current history row (``facts/own_reports.py``): production holds
none from before then, and none computed against a proxy winner. ``_resync`` is a sync since then, the state
of a company synced after the deploy. Each test asserts its planted precondition before the repair runs, so
a change to a planting path fails loudly instead of planting the fixed state. A shape no writer produces is
planted as a row, and says so.
"""
import copy
import json
import re
import sys
from collections import Counter
from contextlib import ExitStack, contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, SessionLocal
from app.models import Company, Filing, FinancialFact
from app.models.financial_fact_revision import FinancialFactRevision
from app.services import facts_service as svc
from app.services import proxy_fact_repair as proxy
from app.services import quarterly_fact_repair as repair
from app.services.facts import companyfacts, currency, fiscal_naming
from app.services.facts.concepts import HEADLINE_GAAP_TAGS
from scripts import repair_quarterly_facts as cli
from tests.unit.test_companyfacts_ingest import (
    REV_TAG, _FDX_INCOME, _FDX_REVENUE, _MRK_INCOME, _MRK_PROXY, _MRK_REVENUE, _cny_payload, _fdx_payload,
    _item, _mrk_payload, _payload, _ten_ks,
)

NEVER = re.compile(r"(?!)")  # matches nothing


@contextmanager
def _database():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(**{**SessionLocal.kw, "bind": engine})()  # autoflush off, as in production
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def db():
    with _database() as session:
        yield session


@contextmanager
def _before_1682(monkeypatch):
    """No own-report history, as before #1682: the normalizer returned none (``companyfacts.own_report_history``),
    so a sync stored none."""
    with monkeypatch.context() as patch:
        patch.setattr(companyfacts, "own_report_history", lambda *_args: [])
        yield


@contextmanager
def _before_the_fix(monkeypatch):
    """No form is a proxy's, as before #1622, and no own-report history, which #1682 added after it. ``is_proxy_form``
    reads ``_PROXY_FORM`` when it is called (facts/fiscal_naming.py), so every importer, by module or by name, sees
    the old rule. #1682's history under the old rule would take a proxy item as a year's winner and store the 10-K's
    own figure beside it, at the 10-K's identity, before the per-filing writer ran: a state no writer ever stored."""
    with monkeypatch.context() as patch, _before_1682(monkeypatch):
        patch.setattr(fiscal_naming, "_PROXY_FORM", NEVER)
        yield


def _company(db, ticker):
    company = Company(ticker=ticker, cik=str(9_000_000 + db.query(Company).count()), name=ticker)
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def _accn(company, accession):
    return f"{accession}-{company.ticker}"


def _for(company, payload):
    """``payload`` as this company's: its CIK, and every accession suffixed with its ticker (an accession
    is unique across companies, and the bulk upsert reads filing dates by accession alone)."""
    out = copy.deepcopy(payload)
    out["cik"] = int(company.cik)
    for node in out["facts"]["us-gaap"].values():
        for items in node["units"].values():
            for item in items:
                if "accn" in item:
                    item["accn"] = _accn(company, item["accn"])
    return out


def _items(payload, tag="NetIncomeLoss", unit="USD"):
    return payload["facts"]["us-gaap"][tag]["units"][unit]


def _old_sync(db, monkeypatch, company, payload):
    with _before_the_fix(monkeypatch):
        svc._persist_companyfacts_payload(db, company, payload)


def _sync(db, monkeypatch, company, payload):
    """A sync with #1622's fix, as it ran before #1682 was deployed."""
    with _before_1682(monkeypatch):
        svc._persist_companyfacts_payload(db, company, payload)


def _resync(db, company, payload):
    """A sync since #1682 was deployed: ``_sync``'s winners, and each restated year's own-report value as a
    non-current history row where no stored row holds its identity."""
    return svc._persist_companyfacts_payload(db, company, payload)


def _filing(db, company, accession, period_end, filed, form="10-K"):
    filing = Filing(company_id=company.id, accession_number=_accn(company, accession), filing_type=form,
                    filing_date=datetime.fromisoformat(filed).replace(tzinfo=timezone.utc),
                    period_end_date=datetime.fromisoformat(period_end).replace(tzinfo=timezone.utc),
                    document_url="https://example.com/d", sec_url="https://example.com/s")
    db.add(filing)
    db.commit()
    return filing


def _file(db, monkeypatch, filing, series, *, authority_from=None):
    """The per-filing writer stores ``series`` (concept -> (start or None, value)) at the filing's period
    end; with ``authority_from`` the backfill cross-checks it against that payload's authority, read
    before #1622."""
    end = filing.period_end_date.date().isoformat()
    standardized = {concept: {"series": [{"period": end, "value": value, "fiscal_period": "FY",
                                          **({"period_start": start} if start else {})}]}
                    for concept, (start, value) in series.items()}
    with _before_the_fix(monkeypatch):
        authority = None if authority_from is None else svc.extract_authoritative_values(authority_from)
        svc.process_filing_facts(db, filing, standardized=standardized, authoritative=authority)


def _rows(db, company, **filters):
    return db.query(FinancialFact).filter_by(company_id=company.id, **filters).order_by(FinancialFact.id).all()


def _snapshots(db, company=None):
    query = db.query(FinancialFact) if company is None else db.query(FinancialFact).filter_by(company_id=company.id)
    return {row.id: repair.snapshot(row) for row in query}


def _current_proxy_rows(db, company):
    return [r for r in _rows(db, company, is_latest=True) if r.form == "DEF 14A"]


def _filing_row(db, filing, concept="net_income"):
    return db.query(FinancialFact).filter_by(filing_id=filing.id, concept=concept).one()


def _check(row):
    return (row.provenance or {}).get("checks", {}).get("authoritative")


def _preview(db, company, payload):
    return repair.repair_company(db, company.id, payload, dry_run=True)


def _apply(db, company, payload, run_id="apply-1"):
    result = repair.repair_company(db, company.id, payload, dry_run=False, run_id=run_id)
    db.commit()
    return result


# --- The shapes, each planted as the writers stored it before #1622 ------------------------------------

def _unhealed(db, monkeypatch, ticker="AAA", payload=None):
    """One sync before the fix: each proxy figure won its period, and nothing stored the 10-K's
    (production's 53 rows with no report row behind them)."""
    company = _company(db, ticker)
    payload = _for(company, payload or _mrk_payload())
    _old_sync(db, monkeypatch, company, payload)
    return company, payload


def _demoted(db, monkeypatch, ticker="BBB"):
    """A sync stored the 10-K's rows, a sync before the fix demoted them behind the proxy's, and the
    fixed sync skips their stored identities (#1622, "report-stored-then-demoted"). The stored 10-K-named
    Q4 carries the NULL provenance of a sync before operand lineage, so it differs from its candidate."""
    company = _company(db, ticker)
    payload = _for(company, _mrk_payload())
    _sync(db, monkeypatch, company, _for(company, _mrk_payload(proxy=False)))
    _old_sync(db, monkeypatch, company, payload)
    _sync(db, monkeypatch, company, payload)
    q4 = _rows(db, company, concept="net_income", fiscal_period="Q4", accession=_accn(company, "K25"))[0]
    q4.provenance = None
    db.commit()
    return company, payload


def _filed_behind(db, monkeypatch, ticker="CCC", parsed=18_254e6, start="2025-01-01"):
    """A sync before the fix made the proxy's rows current; the FY2025 10-K was listed after it, and the
    per-filing writer stored its row behind the proxy's (a current row with no local filing counts as
    newer); the fixed sync then healed every other year (#1622, "stays current over a 10-K listed after")."""
    company = _company(db, ticker)
    payload = _for(company, _mrk_payload())
    _old_sync(db, monkeypatch, company, payload)
    filing = _filing(db, company, "K25", "2025-12-31", "2026-02-25")
    _file(db, monkeypatch, filing, {"net_income": (start, parsed)})
    _sync(db, monkeypatch, company, payload)
    return company, payload, filing


def _replaced(db, monkeypatch, ticker="DDD"):
    """FedEx's shape: the proxy tags its years in dollars. The backfill cross-checked the FY2025 10-K's
    parse against the proxy's figure, replaced it and recorded the original (since #1191); the filing's
    margin was annotated against the replaced figure."""
    company = _company(db, ticker)
    payload = _for(company, _fdx_payload())
    _old_sync(db, monkeypatch, company, payload)
    filing = _filing(db, company, "K25", "2025-05-31", "2025-07-20")
    _file(db, monkeypatch, filing, {
        "net_income": ("2024-06-01", 4_092e6), "revenue": ("2024-06-01", 87_926e6),
        "net_margin": ("2024-06-01", 4_092e6 / 87_926e6 * 100),
    }, authority_from=payload)
    return company, payload, filing


def _only_a_proxy_tags_2021(db, monkeypatch, ticker="EEE"):
    """FY2021 has the 10-K's revenue and no reported net income under any tag; FY2022's 10-K tags it
    ProfitLoss only; the proxy tags both years NetIncomeLoss, the first tag (#1622's payload)."""
    company = _company(db, ticker)
    payload = _for(company, _only_a_proxy_tags_payload())
    _old_sync(db, monkeypatch, company, payload)
    return company, payload


def _only_a_proxy_tags_payload(fy2021=90e6):
    """``fy2021``: the proxy's FY2021 net income."""
    return _payload({
        REV_TAG: {"units": {"USD": _ten_ks({2021: 900e6, 2022: 1_000e6, 2023: 1_100e6})}},
        "NetIncomeLoss": {"units": {"USD": _ten_ks({2023: 130e6}) + [
            _item(value, f"{year}-12-31", start=f"{year}-01-01", accn="P24", fy=2023, form="DEF 14A",
                  filed="2024-04-20") for year, value in ((2021, fy2021), (2022, 100e6), (2023, 130e6))
        ]}},
        "ProfitLoss": {"units": {"USD": _ten_ks({2022: 110e6})}},
    })


def _without_proxy_items(payload):
    out = copy.deepcopy(payload)
    for node in out["facts"]["us-gaap"].values():
        for unit, items in node["units"].items():
            node["units"][unit] = [item for item in items if item.get("form") != "DEF 14A"]
    return out


def _payload_witness(db, monkeypatch, ticker="MMM"):
    """No stored proxy row (the sync ran before the proxy was filed), but the backfill read the proxy's
    figure in dollars from companyfacts as the FY2025 authority and replaced the 10-K's parse with it."""
    company = _company(db, ticker)
    payload = _for(company, _fdx_payload())
    _sync(db, monkeypatch, company, _without_proxy_items(payload))
    filing = _filing(db, company, "K25", "2025-05-31", "2025-07-20")
    _file(db, monkeypatch, filing, {"net_income": ("2024-06-01", 4_092e6)}, authority_from=payload)
    return company, payload, filing


def _confirmed_by_the_10ks_figure(db, monkeypatch, ticker="XQT"):
    """The proxy quotes FY2025 exactly (CRM, META, NVDA and REGN's shape). After a sync before the fix,
    the FY2025 10-K was listed and its parse confirmed against the proxy's figure, which is the 10-K's.
    The filing row holds the winner's identity, so nothing else stores that figure."""
    company = _company(db, ticker)
    payload = _for(company, _mrk_payload())
    _old_sync(db, monkeypatch, company, payload)
    filing = _filing(db, company, "K25", "2025-12-31", "2026-02-25")
    _file(db, monkeypatch, filing, {"net_income": ("2025-01-01", 18_254e6)}, authority_from=payload)
    return company, payload, filing


def _without_accessions(db, monkeypatch, ticker="FBK"):
    """The FY2025 10-K stored and cross-checked first; then a sync before the fix stored proxy items that
    carry no accession, which facts/quarterly.py names "companyfacts", the name every cross-checked filing
    row's check quotes as its method."""
    company = _company(db, ticker)
    payload = _for(company, _mrk_payload())
    for item in _items(payload):
        if item["form"] == "DEF 14A":
            del item["accn"]
    filing = _filing(db, company, "K25", "2025-12-31", "2026-02-25")
    svc.process_filing_facts(db, filing, authoritative=svc.extract_authoritative_values(payload),
                             standardized={"net_income": {"series": [
                                 {"period": "2025-12-31", "period_start": "2025-01-01", "value": 18_254e6,
                                  "fiscal_period": "FY"}]}})
    _old_sync(db, monkeypatch, company, payload)
    return company, payload, filing


def _confirmed(db, monkeypatch, ticker="QQQ"):
    """BIIB's shape: the proxy rounds FY2025 (18,250 for the 10-K's 18,254 million); the FY2025 10-K's
    parse agrees with the 10-K, and the backfill confirmed it against the proxy's rounded figure."""
    company = _company(db, ticker)
    payload = _for(company, _mrk_payload())
    for item in _items(payload):
        if item["form"] == "DEF 14A" and item["end"] == "2025-12-31":
            item["val"] = 18_250e6
    _old_sync(db, monkeypatch, company, payload)
    filing = _filing(db, company, "K25", "2025-12-31", "2026-02-25")
    _file(db, monkeypatch, filing, {"net_income": ("2025-01-01", 18_254e6)}, authority_from=payload)
    return company, payload, filing


def _fdx_with_proxy(values_by_year):
    """FedEx's payload with the proxy's figure for each year set: the 10-K's (``None``) or another."""
    payload = _fdx_payload()
    for item in _items(payload):
        if item["form"] == "DEF 14A":
            override = values_by_year.get(int(item["end"][:4]))
            item["val"] = override if override is not None else _FDX_INCOME[int(item["end"][:4])]
    return payload


def _cross_checked(db, monkeypatch, ticker, payload, parsed, *, period=("2025-05-31", "2024-06-01", "2025-07-20")):
    """A sync before the fix, then the filing's net income cross-checked against the authority read then."""
    company = _company(db, ticker)
    payload = _for(company, payload)
    _old_sync(db, monkeypatch, company, payload)
    end, start, filed = period
    filing = _filing(db, company, f"K{end[2:4]}", end, filed)
    _file(db, monkeypatch, filing, {"net_income": (start, parsed)}, authority_from=payload)
    return company, payload, filing


def _scaled_up(db, monkeypatch, ticker="NNN"):
    """A parse in units (4,092 for 4,092 million) that the authority, here a proxy agreeing with the
    10-K, multiplied up to the 10-K's figure: the replacement the cross-check exists for."""
    return _cross_checked(db, monkeypatch, ticker, _fdx_with_proxy({}), 4_092.0)


def _scaled_up_where_only_a_proxy_tags(db, monkeypatch, ticker="SSS"):
    """The same where only the proxy tags the year, so today's authority has no figure there."""
    company, payload = _only_a_proxy_tags_2021(db, monkeypatch, ticker)
    filing = _filing(db, company, "K21", "2021-12-31", "2022-02-25")
    _file(db, monkeypatch, filing, {"net_income": ("2021-01-01", 90.0)}, authority_from=payload)
    return company, payload, filing


def _replaced_by_an_amendment(db, monkeypatch, ticker="AMD"):
    """A 10-K/A restates FY2025. Listed after the proxy, it was the old authority, which replaced the
    10-K's parse with its figure; filed before the proxy, it won no sync, so no stored row holds that
    figure. No proxy figure is behind the row."""
    payload = _fdx_payload()
    _items(payload).append(_item(4_100e6, "2025-05-31", start="2024-06-01", accn="KA25", fy=2025,
                                 form="10-K/A", filed="2025-09-01"))
    return _cross_checked(db, monkeypatch, ticker, payload, 4_000e6)


def _holds_the_10k_figure(db, monkeypatch, ticker="KKK"):
    """The proxy quotes the 10-K exactly; the parse was off by a non-scale amount (3,500 for 4,092
    million), and the authority, the proxy's figure, replaced it with the 10-K's own figure."""
    return _cross_checked(db, monkeypatch, ticker, _fdx_with_proxy({}), 3_500e6)


def _restated_after_the_proxy(db, monkeypatch, ticker="RST"):
    """The proxy quotes the FY2025 figure of a 10-K a 10-K/A later restated by more than 1%. A sync
    stored the report's figure under the FY2026 10-K's comparative, and a replacement from before
    #1191 (no record) put the proxy's figure, the old one, on the FY2025 10-K's row."""
    company = _company(db, ticker)
    then = _for(company, _mrk_payload())
    k26 = _item(18_254e6, "2025-12-31", start="2025-01-01", accn="K26", fy=2026, filed="2027-02-25")
    _items(then).insert(0, {**k26, "accn": _accn(company, "K26")})  # listed first: the proxy wins the old tie
    _sync(db, monkeypatch, company, _without_proxy_items(then))
    filing = _filing(db, company, "K25", "2025-12-31", "2026-02-25")
    _file(db, monkeypatch, filing, {"net_income": ("2025-01-01", 17_000e6)}, authority_from=then)
    _filing_row(db, filing).provenance = None
    db.commit()
    now = copy.deepcopy(then)
    _items(now).append(_item(18_800e6, "2025-12-31", start="2025-01-01", accn=_accn(company, "KA26"), fy=2026,
                             form="10-K/A", filed="2027-06-15"))
    return company, now, filing


def _only_a_proxy_tags_2021_and_the_10k_was_replaced(db, monkeypatch, ticker="ZAA", *, proxy_rows=False,
                                                     parsed=85e6, quoted=90e6):
    """FY2021's net income only a proxy tags (``quoted``, 90 million), so today's payload has no 10-K figure there.
    The FY2021 10-K's parse was cross-checked against the proxy's figure before the fix: replaced when
    it differed, confirmed when it agreed. ``proxy_rows``: a sync before the fix also stored the proxy's
    rows; otherwise the sync ran before the proxy was filed and only the payload holds its figure."""
    company = _company(db, ticker)
    payload = _for(company, _only_a_proxy_tags_payload(quoted))
    if proxy_rows:
        _old_sync(db, monkeypatch, company, payload)
    else:
        _sync(db, monkeypatch, company, _without_proxy_items(payload))
    filing = _filing(db, company, "K21", "2021-12-31", "2022-02-25")
    _file(db, monkeypatch, filing, {"net_income": ("2021-01-01", parsed)}, authority_from=payload)
    return company, payload, filing


def _replaced_with_operating_rows(db, monkeypatch, ticker="DDO"):
    """DDD's shape, the filing also carrying operating income and its margin, whose record cannot rest
    on net income."""
    company = _company(db, ticker)
    payload = _for(company, _fdx_payload())
    _old_sync(db, monkeypatch, company, payload)
    filing = _filing(db, company, "K25", "2025-05-31", "2025-07-20")
    start = "2024-06-01"
    _file(db, monkeypatch, filing, {
        "net_income": (start, 4_092e6), "revenue": (start, 87_926e6),
        "net_margin": (start, 4_092e6 / 87_926e6 * 100), "operating_income": (start, 5_200e6),
        "operating_margin": (start, 5_200e6 / 87_926e6 * 100),
    }, authority_from=payload)
    return company, payload, filing


def _replaced_where_the_10k_names_the_margin(db, monkeypatch, ticker="SCP"):
    """Merck's shape with a proxy 1.4% under the 10-K's FY2025 figure: the FY2025 10-K's parse, the 10-K's
    own figure, was replaced with the proxy's. The FY2025 10-K is revenue's winner too, so the
    companyfacts margin shares the filing row's scope (company, accession, period, fiscal year)."""
    payload = _mrk_payload()
    for item in _items(payload):
        if item["form"] == "DEF 14A" and item["end"] == "2025-12-31":
            item["val"] = 18_000e6
    return _cross_checked(db, monkeypatch, ticker, payload, 18_254e6,
                          period=("2025-12-31", "2025-01-01", "2026-02-25"))


def _with_proxy_revenue(fdx_revenue):
    """FedEx's payload whose proxy also tags revenue, ``fdx_revenue`` (year -> value)."""
    payload = _fdx_payload()
    payload["facts"]["us-gaap"][REV_TAG]["units"]["USD"] += [
        _item(value, f"{year}-05-31", start=f"{year - 1}-06-01", accn="P26", fy=2026, form="DEF 14A",
              filed="2026-08-17") for year, value in fdx_revenue.items()]
    return payload


def _replaced_and_confirmed_in_one_filing(db, monkeypatch, ticker="MIX", *, revenue_in_dollars=False):
    """DDD's shape where the proxy also tags FY2025 revenue. Rounded (87,900 for 87,926 million), it
    confirmed the filing's revenue; in dollars, it replaced it too."""
    revenue = ({year: value / 1e6 for year, value in _FDX_REVENUE.items()} if revenue_in_dollars
               else {2025: 87_900e6})
    company = _company(db, ticker)
    payload = _for(company, _with_proxy_revenue(revenue))
    _old_sync(db, monkeypatch, company, payload)
    filing = _filing(db, company, "K25", "2025-05-31", "2025-07-20")
    _file(db, monkeypatch, filing, {
        "net_income": ("2024-06-01", 4_092e6), "revenue": ("2024-06-01", 87_926e6),
        "net_margin": ("2024-06-01", 4_092e6 / 87_926e6 * 100),
    }, authority_from=payload)
    return company, payload, filing


def _reconfirmed_with_its_margin(db, monkeypatch, ticker="LRC"):
    """QQQ's shape in a filing that also carries revenue and the margin over both, annotated against the
    proxy's rounded figure. The proxy tags no revenue, so set 5 alone rewrites a row in the margin's scope."""
    company = _company(db, ticker)
    payload = _for(company, _mrk_payload())
    for item in _items(payload):
        if item["form"] == "DEF 14A" and item["end"] == "2025-12-31":
            item["val"] = 18_250e6
    _old_sync(db, monkeypatch, company, payload)
    filing = _filing(db, company, "K25X", "2025-12-31", "2026-02-25")
    start = "2025-01-01"
    _file(db, monkeypatch, filing, {"net_income": (start, 18_254e6), "revenue": (start, 64_900e6),
                                    "net_margin": (start, 18_254e6 / 64_900e6 * 100)}, authority_from=payload)
    return company, payload, filing


def _replaced_with_its_margin(db, monkeypatch, ticker="RPM"):
    """Merck's shape with a proxy 1.4% under the 10-K's FY2025 figure, which replaced the parse of a filing
    that also carries revenue and the margin over both: the margin, annotated against the proxy's figure,
    reads calculation_mismatch. The proxy tags no revenue."""
    company = _company(db, ticker)
    payload = _for(company, _mrk_payload())
    for item in _items(payload):
        if item["form"] == "DEF 14A" and item["end"] == "2025-12-31":
            item["val"] = 18_000e6
    _old_sync(db, monkeypatch, company, payload)
    filing = _filing(db, company, "K25X", "2025-12-31", "2026-02-25")
    start = "2025-01-01"
    _file(db, monkeypatch, filing, {"net_income": (start, 18_254e6), "revenue": (start, 64_900e6),
                                    "net_margin": (start, 18_254e6 / 64_900e6 * 100)}, authority_from=payload)
    return company, payload, filing


def _later_proxy_quotes_the_10k(db, monkeypatch, company, payload):
    """``payload`` plus a later proxy that quotes FY2025 exactly, stored by a sync before the fix."""
    later = copy.deepcopy(payload)
    _items(later).append(_item(18_254e6, "2025-12-31", start="2025-01-01", accn=_accn(company, "P27"), fy=2026,
                               form="DEF 14A", filed="2027-04-08"))
    _old_sync(db, monkeypatch, company, later)
    return later


def _reconfirmed_where_a_later_proxy_quotes_the_10k(db, monkeypatch, ticker="RCL"):
    """QQQ's shape, then a later proxy that quotes FY2025 exactly: the reconfirmed row's new figure, the
    10-K's, is also a stored proxy row's, so set 5 still lists it."""
    company, payload, filing = _confirmed(db, monkeypatch, ticker)
    return company, _later_proxy_quotes_the_10k(db, monkeypatch, company, payload), filing


def _restored_where_a_later_proxy_quotes_the_10k(db, monkeypatch, ticker="RSW"):
    """A proxy 6.9% under the 10-K's FY2025 figure replaced the 10-K's parse on its own row (the winner's
    identity), then a later proxy quoted the 10-K exactly: the restored row's new figure, the 10-K's, is
    also a stored proxy row's, so set 5 lists it after the apply."""
    payload = _mrk_payload()
    for item in _items(payload):
        if item["form"] == "DEF 14A" and item["end"] == "2025-12-31":
            item["val"] = 17_000e6
    company, payload, filing = _cross_checked(db, monkeypatch, ticker, payload, 18_254e6,
                                              period=("2025-12-31", "2025-01-01", "2026-02-25"))
    return company, _later_proxy_quotes_the_10k(db, monkeypatch, company, payload), filing


def _scaled_parse_with_no_proxy(db, monkeypatch, ticker="NPF"):
    """A parse 1,000 times too large that the 10-K's figure replaced, at a company no proxy tags: the filing
    was read before any sync, so its row holds the 10-K's identity and no report row holds the figure.
    Detection's set 4 lists it ("scale"); the step leaves it (no proxy figure is behind it)."""
    company = _company(db, ticker)
    payload = _for(company, _mrk_payload(proxy=False))
    filing = _filing(db, company, "K25", "2025-12-31", "2026-02-25")
    _file(db, monkeypatch, filing, {"net_income": ("2025-01-01", 18_254e9)}, authority_from=payload)
    _sync(db, monkeypatch, company, payload)
    return company, payload, filing


def _with_revenue_quarters(payload):
    """``payload`` plus 2025's revenue 10-Qs, so Q4 revenue derives and a Q4 margin with it."""
    out = copy.deepcopy(payload)
    _items(out, REV_TAG).extend(
        _item(value, end, start=start, accn=f"{fp}-25", fy=2025, fp=fp, form="10-Q", filed=filed)
        for value, start, end, fp, filed in (
            (16_000e6, "2025-01-01", "2025-03-31", "Q1", "2025-05-01"),
            (16_000e6, "2025-04-01", "2025-06-30", "Q2", "2025-07-30"),
            (17_000e6, "2025-07-01", "2025-09-30", "Q3", "2025-10-30"),
            (49_000e6, "2025-01-01", "2025-09-30", "Q3", "2025-10-30")))
    return out


def _twin_row(db, company, filing, concept="net_income", value="2957000000"):
    """A legacy current row with no fiscal period at Q4 2025's period end, filed locally (planted as a
    row: no writer stores one today)."""
    twin = FinancialFact(company_id=company.id, filing_id=filing.id, concept=concept,
                         raw_tag="us-gaap:NetIncomeLoss", unit="USD", period_start=date(2025, 10, 1),
                         period_end=date(2025, 12, 31), fiscal_year=2025, fiscal_period=None,
                         value=Decimal(value), form="10-K", accession=filing.accession_number,
                         source="edgar_xbrl", reconciled=True, is_latest=True)
    db.add(twin)
    db.commit()
    return twin


def _assert_planted_proxy_rows(db, company, expected):
    """The precondition: the shape's proxy rows are current, as the writers stored them before #1622."""
    assert {(r.fiscal_period, r.period_end.year) for r in _current_proxy_rows(db, company)} == expected


_MRK_PROXY_ROWS = {("FY", year) for year in _MRK_PROXY} | {("Q4", 2025)}
_STEP_ZERO = dict.fromkeys(proxy.COUNTERS, 0)


def _counts(block):
    return {name: block[name] for name in proxy.COUNTERS if block[name]}


# --- Behaviours -------------------------------------------------------------------------------------

def test_a_proxy_winner_no_sync_healed_is_retired_and_the_10k_winner_inserted(db, monkeypatch):
    company, payload = _unhealed(db, monkeypatch)
    _assert_planted_proxy_rows(db, company, _MRK_PROXY_ROWS)
    planted = _snapshots(db, company)
    statements = []
    spy = lambda conn, cursor, statement, *args: statements.append(statement)  # noqa: E731
    event.listen(db.bind, "before_cursor_execute", spy)
    plan = _preview(db, company, payload)
    event.remove(db.bind, "before_cursor_execute", spy)
    assert not any(s.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for s in statements)
    assert _snapshots(db, company) == planted
    assert _counts(plan["proxy"]) == {"retired": 6, "inserted": 6, "dependents_recomputed": 5}
    assert plan["planned_inserts"] == 6  # the step's Q4 and the derived-quarter path's are one insert
    assert {row["winner_form"] for row in plan["proxy"]["rows"]} == {"10-K"}
    fy2021 = next(row for row in plan["proxy"]["rows"] if (row["fiscal_period"], row["fiscal_year"]) == ("FY", 2021))
    assert fy2021["gap"] == pytest.approx(704 / 13_049, abs=1e-6)

    _apply(db, company, payload)
    proxies = [r for r in _rows(db, company) if r.form == "DEF 14A"]
    assert len(proxies) == 6
    for row in proxies:
        assert not row.is_latest and row.reconciled is False
        assert (row.provenance["validation"], row.provenance["reasons"]) == ("unavailable", ["proxy_statement_value"])
        assert row.provenance["replacement"]["accession"].startswith("K") and row.provenance["replacement"]["form"] == "10-K"
    latest_10k = {2021: "K23", 2022: "K24", 2023: "K25", 2024: "K25", 2025: "K25"}
    assert {r.period_end.year: (float(r.value), r.accession) for r in _rows(db, company, concept="net_income",
                                                                            fiscal_period="FY", is_latest=True)} == {
        year: (value, _accn(company, latest_10k[year])) for year, value in _MRK_INCOME.items()}
    [q4] = _rows(db, company, concept="net_income", fiscal_period="Q4", is_latest=True)
    assert (q4.accession, q4.form, q4.source, float(q4.value)) == (_accn(company, "K25"), "10-K", "derived", 2_957e6)
    accession = _accn(company, "P26")
    for margin in _rows(db, company, concept="net_margin", fiscal_period="FY", is_latest=True):
        year = margin.period_end.year
        assert float(margin.value) == pytest.approx(_MRK_INCOME[year] / _MRK_REVENUE[year] * 100)
        assert f'"{accession}"' not in json.dumps(margin.provenance)

    again = _apply(db, company, payload, run_id="apply-2")
    assert again["revisions"] == 0 and _counts(again["proxy"]) == {}


@pytest.mark.parametrize("synced", [False, True], ids=["as-planted", "after-a-sync-involving-eur"])
def test_a_stored_then_demoted_10k_row_is_promoted(db, monkeypatch, synced):
    # A sync that involves another currency (a stored EUR row) leaves the stored 10-K rows behind P26's, as a sync in
    # USD alone does, so the step plans the same repair.
    company, payload = _demoted(db, monkeypatch)
    if synced:
        _a_stored_eur_row(db, company)
        _resync(db, company, payload)
    _assert_planted_proxy_rows(db, company, _MRK_PROXY_ROWS)
    plan = _preview(db, company, payload)
    assert _counts(plan["proxy"]) == {"retired": 6, "promoted": 5, "corrected": 1}
    assert plan["planned_inserts"] == 0
    _apply(db, company, payload)
    assert {r.period_end.year: (float(r.value), r.accession) for r in _rows(
        db, company, concept="net_income", fiscal_period="FY", is_latest=True)}[2021] == (13_049e6, _accn(company, "K23"))
    # The loop corrects this row too; it composes on the step's promotion rather than undoing it.
    [q4] = _rows(db, company, concept="net_income", fiscal_period="Q4", is_latest=True)
    assert (q4.accession, q4.source, q4.provenance["formula"]) == (_accn(company, "K25"), "derived", "FY - YTD9")


@pytest.mark.parametrize("synced", [False, True], ids=["as-planted", "after-a-sync-involving-eur"])
def test_a_stored_then_demoted_10k_row_with_another_value_is_corrected(db, monkeypatch, synced):
    # The K25 FY2025 row stored behind P26's holds another figure than today's winner (an older normalizer read another
    # tag of the same 10-K; the tag is outside the identity). The step corrects it as it promotes it. A sync that
    # involves another currency never makes it current in its place: the upsert skips the stored identity and the
    # newer-filing rule leaves the key as found behind P26's row, so the step still corrects it.
    company, payload = _demoted(db, monkeypatch)
    [k25] = [r for r in _rows(db, company, concept="net_income", fiscal_period="FY", accession=_accn(company, "K25"))
             if r.period_end.year == 2025]
    k25.value = Decimal("17000000000")
    db.commit()
    if synced:
        _a_stored_eur_row(db, company)
        _resync(db, company, payload)
        assert not db.get(FinancialFact, k25.id).is_latest
    assert _counts(_preview(db, company, payload)["proxy"]) == {"retired": 6, "promoted": 4, "corrected": 2}
    _apply(db, company, payload)
    k25 = db.get(FinancialFact, k25.id)
    assert (k25.is_latest, float(k25.value)) == (True, 18_254e6)


@pytest.mark.parametrize(("parsed", "start"), [
    (18_254e6, "2025-01-01"), (18_200e6, "2025-01-01"), (18_254e6, None),
], ids=["equal", "within-1pct", "start-missing"])
def test_a_filing_row_behind_the_proxy_is_promoted_when_it_agrees(db, monkeypatch, parsed, start):
    # A filing row stored before #831 has no start; with the value within 1% and the same fiscal year it
    # agrees (founder, 2026-10-26), since its identity already names the filing and the period.
    company, payload, filing = _filed_behind(db, monkeypatch, parsed=parsed, start=start)
    _assert_planted_proxy_rows(db, company, {("FY", 2025)})
    row = _filing_row(db, filing)
    assert not row.is_latest and (row.period_start is None) == (start is None)
    stored = repair.snapshot(row)
    plan = _preview(db, company, payload)
    assert _counts(plan["proxy"]) == {"retired": 1, "promoted": 1, "dependents_recomputed": 5}
    _apply(db, company, payload)
    row = _filing_row(db, filing)
    assert row.is_latest and repair.snapshot(row) == {**stored, "is_latest": True}
    assert [r.is_latest for r in _rows(db, company) if r.form == "DEF 14A" and r.fiscal_period == "FY"
            and r.period_end.year == 2025] == [False]


@pytest.mark.parametrize("beside", [None, "stale_margin", "quarantined_report"])
def test_a_period_only_a_proxy_tags_is_retired_and_its_margin_with_it(db, monkeypatch, beside):
    company, payload = _only_a_proxy_tags_2021(db, monkeypatch)
    _assert_planted_proxy_rows(db, company, {("FY", 2021), ("FY", 2022), ("FY", 2023)})
    fy2021 = date(2021, 12, 31)
    if beside == "stale_margin":  # a calculation at the key is no report row to agree with
        db.add(FinancialFact(company_id=company.id, concept="net_margin", raw_tag=None, unit="pure",
                             period_start=date(2021, 1, 1), period_end=fy2021, fiscal_year=2021,
                             fiscal_period="FY", value=Decimal("9.5"), form="10-K", accession=_accn(company, "K21"),
                             source="companyfacts", reconciled=True, is_latest=False))
    elif beside == "quarantined_report":  # neither is a reported row a repair already withheld
        db.add(FinancialFact(company_id=company.id, concept="net_income", raw_tag="us-gaap:NetIncomeLoss",
                             unit="USD", period_start=date(2021, 1, 1), period_end=fy2021, fiscal_year=2021,
                             fiscal_period="FY", value=Decimal("90000000"), form="10-K", accession=_accn(company, "X21"),
                             source="companyfacts", reconciled=False, is_latest=False, provenance={
                                 "version": 1, "method": "reported", "validation": "unavailable",
                                 "reasons": ["legacy_period_label_mismatch"]}))
    db.commit()
    plan = _preview(db, company, payload)
    assert _counts(plan["proxy"]) == {"retired": 3, "inserted": 2, "retired_without_winner": 1,
                                      "dependents_recomputed": 2, "dependents_retired": 1}
    _apply(db, company, payload)
    assert not _rows(db, company, concept="net_income", period_end=fy2021, is_latest=True)
    [margin] = _rows(db, company, concept="net_margin", period_end=fy2021, accession=_accn(company, "K23"))
    assert not margin.is_latest and margin.provenance["reasons"] == ["proxy_statement_operand"]
    assert margin.provenance["replacement"] is None
    [fy2022] = _rows(db, company, concept="net_income", period_end=date(2022, 12, 31), is_latest=True)
    assert (float(fy2022.value), fy2022.raw_tag) == (110e6, "us-gaap:ProfitLoss")


def test_a_filing_row_the_cross_check_replaced_with_a_proxy_figure_is_restored(db, monkeypatch):
    company, payload, filing = _replaced(db, monkeypatch)
    row = _filing_row(db, filing)
    check = _check(row)
    assert (float(row.value), row.source, check["outcome"], check["original_value"]) == (4_092.0, "companyfacts", "replaced", 4_092e6)
    assert "calculation_mismatch" in _filing_row(db, filing, "net_margin").provenance["reasons"]
    local, was_latest = row.provenance["checks"]["local_reconciliation"], row.is_latest

    def chart():
        return {p["period_end"]: p["value"] for c in svc.get_filing_fundamentals(db, filing.id)["concepts"]
                if c["concept"] == "net_income" for p in c["points"]}

    assert chart() == {"2025-05-31": 4_092.0}  # readers see the proxy's dollars as the filing's own year
    plan = _preview(db, company, payload)
    assert _counts(plan["proxy"]) == {"retired": 5, "inserted": 5, "dependents_recomputed": 4,
                                      "filing_rows_restored": 1, "filing_calculations_reannotated": 1}
    _apply(db, company, payload)
    row = _filing_row(db, filing)
    check = _check(row)
    assert (float(row.value), row.source, row.reconciled, row.is_latest) == (4_092e6, "edgar_xbrl", True, was_latest)
    assert (check["outcome"], check["authoritative_value"], check["original_value"]) == ("confirmed", 4_092e6, 4_092e6)
    assert check["resolved_reasons"] == local["reasons"] and row.provenance["checks"]["local_reconciliation"] == local
    # The chart reads the filing's rows at its accession (#1658): its own year is the restored figure. The FY2023 10-K
    # winner the repair stored under this 10-K's accession (the last 10-K to report it) does not chart beside it: FY2024,
    # which the repair stored under the FY2026 10-K's accession, is missing between them, so the line shows its years
    # from FY2025 on (#1682's sixth condition, facts/filing_scope.py), as it does over a fixed sync's rows. No proxy
    # figure charts.
    assert chart() == {"2025-05-31": 4_092e6}
    [fy2023] = _rows(db, company, concept="net_income", period_end=date(2023, 5, 31), accession=filing.accession_number)
    assert (fy2023.filing_id, fy2023.is_latest, float(fy2023.value), fy2023.form) == (None, True, 3_972e6, "10-K")
    margin = _filing_row(db, filing, "net_margin")
    assert float(margin.value) == pytest.approx(4_092e6 / 87_926e6 * 100)
    assert {i["concept"]: i["value"] for i in margin.provenance["inputs"]}["net_income"] == 4_092e6
    assert "calculation_mismatch" not in margin.provenance["reasons"]


def test_a_replacement_only_the_payload_witnesses_is_restored(db, monkeypatch):
    company, payload, filing = _payload_witness(db, monkeypatch)
    assert not [r for r in _rows(db, company) if r.form == "DEF 14A"]  # no stored proxy row
    assert (float(_filing_row(db, filing).value), _filing_row(db, filing).source) == (4_092.0, "companyfacts")
    plan = _preview(db, company, payload)
    assert _counts(plan["proxy"]) == {"filing_rows_restored": 1}
    _apply(db, company, payload)
    assert (float(_filing_row(db, filing).value), _filing_row(db, filing).source) == (4_092e6, "edgar_xbrl")


def _with_null_provenance(db, filing):
    _filing_row(db, filing).provenance = None
    db.commit()


@pytest.mark.parametrize(("shape", "kept"), [
    ("scale_up", False), ("scale_up_no_authority", False), ("amendment", False),
    ("holds_10k", True), ("holds_10k_no_record", True), ("holds_10k_report_backed", False),
    ("report_backed_restated", False),
])
def test_legitimate_replacements_are_left_alone(db, monkeypatch, shape, kept):
    if shape == "scale_up":
        company, payload, filing = _scaled_up(db, monkeypatch)
    elif shape == "scale_up_no_authority":
        company, payload, filing = _scaled_up_where_only_a_proxy_tags(db, monkeypatch)
    elif shape == "amendment":
        company, payload, filing = _replaced_by_an_amendment(db, monkeypatch)
    elif shape == "report_backed_restated":
        company, payload, filing = _restated_after_the_proxy(db, monkeypatch)
    else:
        company, payload, filing = _holds_the_10k_figure(db, monkeypatch)
        if shape == "holds_10k_no_record":  # a replacement before #1191 records nothing
            _with_null_provenance(db, filing)
        elif shape == "holds_10k_report_backed":  # a fixed sync has since stored the 10-K's row
            _sync(db, monkeypatch, company, payload)
    row = _filing_row(db, filing)
    assert row.source == "companyfacts"  # the precondition: the old cross-check replaced the parse
    stored = repair.snapshot(row)
    plan = _preview(db, company, payload)
    entries = [entry for entry in plan["proxy"]["rows"] if entry["fact_id"] == row.id]
    filing_counts = {name: plan["proxy"][name] for name in ("filing_rows_restored", "filing_rows_kept",
                                                             "filing_rows_reconfirmed")}
    if kept:
        assert filing_counts == {"filing_rows_restored": 0, "filing_rows_kept": 1, "filing_rows_reconfirmed": 0}
        assert [entry["action"] for entry in entries] == ["kept_agrees_with_authority"]
    else:
        assert set(filing_counts.values()) == {0} and entries == []
    # A row a report row backs is left, and the preview lists it with the rows that back it; no other is listed.
    report_backed = shape in ("holds_10k_report_backed", "report_backed_restated")
    assert [(entry["fact_id"], entry["set"], entry["action"]) for entry in plan["proxy"]["left_report_backed"]] == (
        [(row.id, 4, "left_report_backed")] if report_backed else [])
    # A scale-up with no 10-K figure to read its scale from is left, and listed: the step cannot tell SSS's parse
    # read in units from a right parse a proxy tagged at the wrong scale replaced (review 5718798403, item 2). One the
    # 10-K's figure confirms within 1% (NNN's) is not listed.
    assert [(entry["fact_id"], entry["original"], entry["reason"]) for entry in plan["proxy"]["scale_up_retained"]] == (
        [(row.id, 90.0, "no_10k_figure")] if shape == "scale_up_no_authority" else [])
    _apply(db, company, payload)
    assert repair.snapshot(_filing_row(db, filing)) == stored
    if kept:  # the 10-K winner the apply stored now backs the row, so the next run passes it silently
        assert _preview(db, company, payload)["proxy"]["filing_rows_kept"] == 0


def _with_operating_cash_flow(payload):
    """MRK's payload plus a 10-K's and 10-Qs' operating cash flow, whose derived quarters no proxy touches."""
    out = copy.deepcopy(payload)
    ytd = [("2025-03-31", 4_000e6, "Q1", "2025-05-01"), ("2025-06-30", 9_000e6, "Q2", "2025-07-30"),
           ("2025-09-30", 15_000e6, "Q3", "2025-10-30")]
    out["facts"]["us-gaap"]["NetCashProvidedByUsedInOperatingActivities"] = {"units": {"USD": [
        _item(21_000e6, "2025-12-31", start="2025-01-01", accn="K25", fy=2025, filed="2026-02-25"),
        *[_item(value, end, start="2025-01-01", accn=f"{fp}-25", fy=2025, fp=fp, form="10-Q", filed=filed)
          for end, value, fp, filed in ytd],
    ]}}
    return out


def test_the_journal_tags_the_proxy_repair_apart_from_other_corrections(db, monkeypatch):
    company, payload = _unhealed(db, monkeypatch, payload=_with_operating_cash_flow(_mrk_payload()))
    _assert_planted_proxy_rows(db, company, _MRK_PROXY_ROWS)
    [stale] = _rows(db, company, concept="operating_cash_flow", fiscal_period="Q2", is_latest=True)
    [missing] = _rows(db, company, concept="operating_cash_flow", fiscal_period="Q3", is_latest=True)
    assert stale.source == missing.source == "derived"
    stale.value += 1  # unrelated pending corrections the same approval applies: a stale quarter,
    db.delete(missing)  # and a calculated quarter no sync stored
    db.commit()
    plan = _preview(db, company, payload)
    assert (plan["proxy"]["other_planned_updates"], plan["proxy"]["other_planned_inserts"]) == (1, 1)
    assert plan["proxy"]["other_updates_by_kind"] == {**dict.fromkeys(proxy.OTHER_KINDS, 0), "value": 1}
    assert plan["proxy"]["other_inserts_by_concept"] == {"operating_cash_flow Q3": 1}
    run = "tagged"
    _apply(db, company, payload, run_id=run)
    journal = {r.fact_id: r.calculation_version for r in db.query(FinancialFactRevision).filter_by(run_id=run)}
    assert journal.pop(stale.id) == "quarterly-v2"
    [inserted] = _rows(db, company, concept="operating_cash_flow", fiscal_period="Q3", is_latest=True)
    assert journal.pop(inserted.id) == "quarterly-v2"
    assert set(journal.values()) == {"proxy-repair-v1"}
    rows = {r.id: r for r in _rows(db, company)}
    assert {(rows[i].form, rows[i].concept) for i in journal} == {
        ("DEF 14A", "net_income"), ("10-K", "net_income"), ("10-K", "net_margin")}


def test_rollback_restores_every_write_and_keeps_inserts_as_history(db, monkeypatch):
    shapes = {"AAA": _unhealed(db, monkeypatch)[:2], "BBB": _demoted(db, monkeypatch)[:2],
              "CCC": _filed_behind(db, monkeypatch)[:2], "DDD": _replaced(db, monkeypatch)[:2]}
    planted = {ticker: _snapshots(db, company) for ticker, (company, _unused) in shapes.items()}
    previews = {ticker: _preview(db, company, payload)["changes"] for ticker, (company, payload) in shapes.items()}
    for ticker, (company, payload) in shapes.items():
        assert _apply(db, company, payload, run_id="proxy-run")["proxy"]["retired"]
    for ticker, (company, _unused) in shapes.items():
        repair.rollback_company(db, company.id, "proxy-run", dry_run=False, run_id=f"rollback-{ticker}")
        db.commit()
        after = _snapshots(db, company)
        assert {row_id: after[row_id] for row_id in planted[ticker]} == planted[ticker]
        inserted = [after[row_id] for row_id in after if row_id not in planted[ticker]]
        assert all(not s["is_latest"] and s["provenance"]["reasons"] == ["repair_rolled_back"] for s in inserted)
        assert bool(inserted) == (ticker in ("AAA", "DDD"))
    company, payload = shapes["AAA"]  # its rolled-back Q4 is a candidate: the repair's own check refuses
    with pytest.raises(ValueError, match="Candidate identity was rolled back"):
        _preview(db, company, payload)
    company, payload = shapes["DDD"]  # no quarter: only the step sees its rolled-back annual winners
    with pytest.raises(proxy.ProxyRepairRefused, match=r"the winner's row \(fact \d+\) was rolled back"):
        _preview(db, company, payload)
    for ticker in ("BBB", "CCC"):  # nothing was inserted, so the same writes plan again
        company, payload = shapes[ticker]
        assert _preview(db, company, payload)["changes"] == previews[ticker]


def _same(a, b):
    return abs(a - b) <= 1e-6 * max(abs(a), abs(b))


def _detection(db, payloads):
    """Sets 2 to 5 of ``ops/detection/proxy_form_winners.sql`` as invariants over the stored rows. The
    file needs PostgreSQL, which this suite has not; the PR records the file's own run over these
    shapes. A payload proxy item also witnesses set 4, which the file cannot read."""
    from app.services.facts.fiscal_naming import is_proxy_form

    listed = {2: set(), 3: set(), 4: set(), 5: set()}
    for company in db.query(Company):
        rows = _rows(db, company)
        proxies = [r for r in rows if is_proxy_form(r.form)]
        accessions = {r.accession for r in proxies} - {"", "companyfacts"}  # set 3 skips the fallback name
        items = proxy.proxy_items(payloads[company.ticker])

        def witnessed(row, value, payload_too=True):
            stored = [float(r.value) for r in proxies if (r.concept, r.period_end) == (row.concept, row.period_end)]
            extra = items.get((row.concept, row.period_end.isoformat()), []) if payload_too else []
            return any(_same(value, w) for w in stored + extra)

        def report_backed(row, value):
            return any(r.id != row.id and (r.concept, r.period_end) == (row.concept, row.period_end)
                       and not (r.filing_id is not None and r.source == "companyfacts")
                       and (r.form or "").strip() and not is_proxy_form(r.form) and _same(float(r.value), value)
                       for r in rows)

        for row in rows:
            check = _check(row) or {}
            if row.is_latest and is_proxy_form(row.form):
                listed[2].add((company.ticker, row.id))
            if (row.is_latest and not is_proxy_form(row.form) and row.provenance is not None
                    and any(f'"{accession}"' in json.dumps(row.provenance) for accession in accessions)):
                listed[3].add((company.ticker, row.id))
            if row.filing_id is not None and row.source == "companyfacts" and not report_backed(row, float(row.value)):
                value, original = float(row.value), check.get("original_value")
                ratio = value / original if isinstance(original, (int, float)) and original and value * original > 0 else None
                scaled = ratio is not None and min(abs(ratio / 1e3 - 1), abs(ratio / 1e6 - 1)) <= 0.01
                shrunk = ratio is not None and min(abs(ratio * 1e3 - 1), abs(ratio * 1e6 - 1)) <= 0.01
                if (witnessed(row, value) and not scaled) or (not witnessed(row, value, payload_too=False) and shrunk):
                    listed[4].add((company.ticker, row.id))  # why = proxy row, or why = scale
            witness = check.get("authoritative_value")
            if (row.filing_id is not None and row.source != "companyfacts" and check.get("outcome") == "confirmed"
                    and isinstance(witness, (int, float)) and witnessed(row, witness, payload_too=False)
                    and not report_backed(row, witness)):
                listed[5].add((company.ticker, row.id))
    return {number: sorted(entries) for number, entries in listed.items()}


def _holds_the_10k_figure_with_no_record(db, monkeypatch, ticker="OOO"):
    company, payload, filing = _holds_the_10k_figure(db, monkeypatch, ticker)
    _with_null_provenance(db, filing)
    return company, payload, filing


_CENSUS = {  # ticker -> the shape's builder, (db, monkeypatch) -> (company, payload, *filing)
    "AAA": _unhealed, "BBB": _demoted, "CCC": _filed_behind,
    "III": lambda db, monkeypatch: _filed_behind(db, monkeypatch, "III", start=None),
    "EEE": _only_a_proxy_tags_2021, "DDD": _replaced, "MMM": _payload_witness, "NNN": _scaled_up,
    "SSS": _scaled_up_where_only_a_proxy_tags, "KKK": _holds_the_10k_figure, "QQQ": _confirmed,
    "OOO": _holds_the_10k_figure_with_no_record, "XQT": _confirmed_by_the_10ks_figure, "FBK": _without_accessions,
    "KEP": lambda db, monkeypatch: _cross_checked(  # 1,000 times too large, replaced by the 10-K's
        db, monkeypatch, "KEP", _mrk_payload(), 18_254e9, period=("2025-12-31", "2025-01-01", "2026-02-25")),
    "NPF": _scaled_parse_with_no_proxy, "RCL": _reconfirmed_where_a_later_proxy_quotes_the_10k,
    "RSW": _restored_where_a_later_proxy_quotes_the_10k,
}


def test_after_the_apply_no_current_row_comes_from_or_is_built_on_a_proxy(db, monkeypatch):
    shapes = {ticker: build(db, monkeypatch)[:2] for ticker, build in _CENSUS.items()}
    payloads = {ticker: payload for ticker, (_company, payload) in shapes.items()}
    before = {number: dict(Counter(ticker for ticker, _ in entries))
              for number, entries in _detection(db, payloads).items()}
    assert before == {  # not vacuous: every set lists the planted rows
        2: {"AAA": 6, "BBB": 6, "CCC": 1, "III": 1, "EEE": 3, "DDD": 5, "NNN": 5, "SSS": 3, "KKK": 5, "OOO": 5,
            "QQQ": 5, "XQT": 6, "FBK": 5, "KEP": 6, "RCL": 5, "RSW": 5},
        3: {"AAA": 5, "CCC": 5, "III": 5, "EEE": 3, "DDD": 4, "NNN": 5, "SSS": 3, "KKK": 5, "OOO": 5, "QQQ": 5,
            "XQT": 5, "KEP": 5, "RCL": 5, "RSW": 5},
        4: {"DDD": 1, "MMM": 1, "KKK": 1, "OOO": 1, "KEP": 1, "NPF": 1, "RSW": 1},
        5: {"QQQ": 1, "XQT": 1, "FBK": 1, "RCL": 1},
    }
    named, verdicts = set(), {}
    for ticker, (company, payload) in shapes.items():
        # The preview lists over the rows as the plan leaves them, inserts included, as the apply then does.
        planned = _preview(db, company, payload)["proxy"]["detection_listed"]
        listed = _apply(db, company, payload)["proxy"]["detection_listed"]
        assert listed == planned and all(entry["verdict"] != "unclassified" for entry in listed)
        named |= {(ticker, entry["fact_id"], entry["set"]) for entry in listed}
        verdicts.update({(ticker, entry["set"]): entry["verdict"] for entry in listed})
    after = _detection(db, payloads)
    assert (after[2], after[3]) == ([], [])
    # Sets 4 and 5 read exactly the rows the apply reports name, each with the step's verdict.
    assert {(ticker, fact_id, number) for number in (4, 5) for ticker, fact_id in after[number]} == named
    assert verdicts == {("XQT", 5): "kept_confirmed_by_10k", ("FBK", 5): "kept_confirmed_by_10k",
                        ("KEP", 4): "kept_agrees_with_authority", ("NPF", 4): "no_proxy_figure",
                        ("RCL", 5): "reconfirmed", ("RSW", 5): "restored"}
    for ticker, (company, payload) in shapes.items():  # a second apply journals nothing
        again = _apply(db, company, payload, run_id="apply-2")
        kept = {entry["fact_id"] for entry in again["proxy"]["detection_listed"] if entry["verdict"].startswith("kept_")}
        assert again["revisions"] == 0 and _counts(again["proxy"]) == ({"filing_rows_kept": len(kept)} if kept else {})


def test_the_cli_preview_reports_proxy_totals(db, monkeypatch, tmp_path):
    from app import database

    company, payload = _unhealed(db, monkeypatch)
    planted = _snapshots(db, company)
    monkeypatch.setattr(database, "SessionLocal", lambda: Session(db.bind))
    (tmp_path / f"CIK{int(company.cik):010d}.json").write_text(json.dumps(payload))
    report = cli.run(cli.build_parser().parse_args(["--tickers", "AAA", "--companyfacts-dir", str(tmp_path)]))
    assert report["failed"] == 0 and report["dry_run"]
    [result] = report["companies"]
    assert _counts(result["proxy"]) == {"retired": 6, "inserted": 6, "dependents_recomputed": 5}
    assert report["proxy_totals"] == {**_STEP_ZERO, "retired": 6, "inserted": 6, "dependents_recomputed": 5,
                                      "other_planned_updates": 0, "other_planned_inserts": 0,
                                      "other_updates_by_kind": dict.fromkeys(proxy.OTHER_KINDS, 0),
                                      "other_inserts_by_concept": {}, "left_report_backed": 0,
                                      "scale_up_retained": 0}
    db.expire_all()
    assert _snapshots(db, company) == planted and db.query(FinancialFactRevision).count() == 0


def test_a_filing_row_confirmed_against_a_rounded_proxy_figure_is_reconfirmed(db, monkeypatch):
    company, payload, filing = _confirmed(db, monkeypatch)
    row = _filing_row(db, filing)
    check = _check(row)
    assert (row.source, row.is_latest, check["outcome"], check["authoritative_value"]) == (
        "edgar_xbrl", False, "confirmed", 18_250e6)
    stored = repair.snapshot(row)
    plan = _preview(db, company, payload)
    assert _counts(plan["proxy"]) == {"retired": 5, "inserted": 4, "promoted": 1, "dependents_recomputed": 5,
                                      "filing_rows_reconfirmed": 1}
    _apply(db, company, payload)
    row = _filing_row(db, filing)
    check = _check(row)
    assert row.is_latest and (row.value, row.source) == (Decimal(stored["value"]), stored["source"])
    assert (check["outcome"], check["authoritative_value"], check["original_value"]) == ("confirmed", 18_254e6, 18_254e6)


def test_the_apply_fails_when_an_insert_lands_behind_a_newer_twin(db, monkeypatch):
    company, payload = _unhealed(db, monkeypatch)
    # A legacy row with no fiscal period, current at the proxy Q4's period end, from a filing listed
    # locally with a date later than any the step's insert carries (planted as a row: no writer today).
    filing = _filing(db, company, "TWIN", "2025-12-31", "2026-03-01")
    twin = FinancialFact(company_id=company.id, filing_id=filing.id, concept="net_income",
                         raw_tag="us-gaap:NetIncomeLoss", unit="USD", period_start=date(2025, 10, 1),
                         period_end=date(2025, 12, 31), fiscal_year=2025, fiscal_period=None,
                         value=Decimal("2957000000"), form="10-K", accession=filing.accession_number,
                         source="edgar_xbrl", reconciled=True, is_latest=True)
    db.add(twin)
    db.commit()
    planted = _snapshots(db, company)
    plan = _preview(db, company, payload)
    [q4] = [row for row in plan["proxy"]["rows"] if row["fiscal_period"] == "Q4"]
    assert q4["twin_fact_id"] == twin.id and plan["proxy"]["projected_residual"]["keys_not_settled"] == []
    with pytest.raises(ValueError, match=r"Proxy repair left rows for detection") as raised:
        repair.repair_company(db, company.id, payload, dry_run=False, run_id="twin")
    assert "['net_income', '2025-12-31', 'Q4', 'USD', 0, 1, 1]" in str(raised.value)
    db.rollback()
    assert db.query(FinancialFactRevision).count() == 0 and _snapshots(db, company) == planted


def test_proxy_items_reads_items_as_the_authority_does():
    # Rule 12: proxy_items keeps exactly the items extract_authoritative_values keeps, but a proxy's.
    def items(form):
        return [
            _item(100.0, "2024-12-31", start="2024-01-01", form=form),  # annual
            _item(101.0, "2024-12-27", start="2023-12-30", form=form),  # a 52-week year
            _item(75.0, "2024-09-30", start="2024-01-01", form=form),  # nine months
            _item(25.0, "2024-06-30", start="2024-04-01", form=form),  # a quarter
            _item(102.0, "2019-12-31", start="2019-01-30", form=form),  # 335 days: the band's lower edge
            _item(103.0, "2018-12-31", start="2018-01-31", form=form),  # 334 days: just outside it
            _item(104.0, "2017-12-31", start="2016-12-01", form=form),  # 395 days: the upper edge
            _item(105.0, "2016-12-31", start="2015-11-30", form=form),  # 397 days: just outside it
            _item(99.0, "2023-12-31", form=form),  # no start
            _item("98", "2022-12-31", start="2022-01-01", form=form),  # a string
            _item(True, "2021-12-31", start="2021-01-01", form=form),  # a bool
            _item(97.0, "not a date", start="2021-01-01", form=form),
            "not an item",
        ]

    def payload(form):
        usgaap = {tag: {"units": {"USD": items(form), "EUR": items(form)}}
                  for tags in HEADLINE_GAAP_TAGS.values() for tag in tags}
        usgaap["Assets"]["units"]["USD"].append(_item(500.0, "2020-12-31", form=form))  # an instant
        for tags in HEADLINE_GAAP_TAGS.values():  # a year only a concept's later tag has
            usgaap[tags[-1]]["units"]["USD"].append(_item(106.0, "2015-12-31", start="2015-01-01", form=form))
        return _payload(usgaap)

    authority = svc.extract_authoritative_values(payload("10-K"))
    found = proxy.proxy_items(payload("DEF 14A"))
    assert authority and set(found) == {(concept, end.isoformat()) for concept, end in authority}
    assert all(value in found[(concept, end.isoformat())] for (concept, end), value in authority.items())
    assert proxy.proxy_items(payload("10-K")) == {} and svc.extract_authoritative_values(payload("DEF 14A")) == {}



def test_a_proxy_item_without_an_accession_names_no_dependent(db, monkeypatch):
    company, payload, filing = _without_accessions(db, monkeypatch)
    row = _filing_row(db, filing)
    assert row.is_latest and '"method": "companyfacts"' in json.dumps(row.provenance)
    assert {r.accession for r in _current_proxy_rows(db, company)} == {"companyfacts"}
    stored = repair.snapshot(row)
    plan = _preview(db, company, payload)
    assert (plan["proxy"]["retired"], plan["proxy"]["inserted"]) == (5, 5)
    _apply(db, company, payload)
    assert repair.snapshot(_filing_row(db, filing)) == stored


# --- Refusals: a case the step cannot settle refuses the company before any write ----------------------

def _refuses(db, company, payload, match):
    planted = _snapshots(db, company)
    with pytest.raises(proxy.ProxyRepairRefused, match=match):
        _preview(db, company, payload)
    with pytest.raises(proxy.ProxyRepairRefused, match=match):
        repair.repair_company(db, company.id, payload, dry_run=False, run_id="refused")
    db.rollback()  # as the CLI's per-company transaction ends
    assert db.query(FinancialFactRevision).count() == 0 and _snapshots(db, company) == planted


def _refusal(db, *reasons):
    """The step's whole refusal message for ``reasons``, ``(fact id, why)`` in the step's order, as a pattern that
    matches it alone, so a second reason fails it."""
    parts = []
    for fact_id, why in reasons:
        row = db.get(FinancialFact, fact_id)
        parts.append(f"{row.concept} {row.fiscal_period} {row.period_end.isoformat()} (fact {fact_id}): {why}")
    return "^" + re.escape(f"Proxy repair refused for this company ({len(parts)}): " + "; ".join(parts)) + "$"


def _current_figure(value, authority):
    """The refusal of a left row that is the company's current figure and more than 1% off the 10-K's figure."""
    return (f"a report row holds the proxy figure behind the filing row, which is the company's current figure, {value}, "
            f"more than 1% off the 10-K's, {authority}")


def test_a_proxy_replacement_with_no_recorded_original_refuses(db, monkeypatch):
    company, payload, filing = _replaced(db, monkeypatch, "FFF")
    _with_null_provenance(db, filing)  # a replacement before #1191; the row holds the proxy's dollars
    row = _filing_row(db, filing)
    assert (float(row.value), row.source, row.provenance) == (4_092.0, "companyfacts", None)
    _refuses(db, company, payload, rf"\(fact {row.id}\): a filing row holds a proxy's figure, not the 10-K's, "
                                   "and records no original value")


def test_a_parse_the_10k_contradicts_refuses_when_the_row_holds_a_proxy_figure(db, monkeypatch):
    company, payload, filing = _cross_checked(db, monkeypatch, "LLL", _fdx_with_proxy({2025: 4_000e6}), 3_500e6)
    row = _filing_row(db, filing)
    assert (float(row.value), _check(row)["original_value"]) == (4_000e6, 3_500e6)
    _refuses(db, company, payload, rf"\(fact {row.id}\): the 10-K's figure disagrees with the recorded original "
                                   "value by more than 1%, and the filing row holds neither")


def test_a_filing_owned_proxy_row_refuses(db, monkeypatch):
    company, payload = _unhealed(db, monkeypatch, "OWN")
    filing = _filing(db, company, "K24", "2024-12-31", "2025-02-25")
    [row] = [r for r in _current_proxy_rows(db, company) if (r.fiscal_period, r.period_end.year) == ("FY", 2024)]
    row.filing_id = filing.id  # planted as a row: no writer stores one (FilingType has no 14A or 14C form)
    db.commit()
    _refuses(db, company, payload, rf"\(fact {row.id}\): a row with a filing owner carries a proxy form")


def test_a_second_current_row_at_a_proxy_key_refuses(db, monkeypatch):
    company, payload = _unhealed(db, monkeypatch, "TWO")
    [row] = [r for r in _current_proxy_rows(db, company) if (r.fiscal_period, r.period_end.year) == ("FY", 2021)]
    other = FinancialFact(company_id=company.id, concept="net_income", raw_tag="us-gaap:NetIncomeLoss", unit="USD",
                          period_start=date(2021, 1, 1), period_end=date(2021, 12, 31), fiscal_year=2021,
                          fiscal_period="FY", value=Decimal("13049000000"), form="10-K",
                          accession=_accn(company, "X21"), source="companyfacts", reconciled=True, is_latest=True)
    db.add(other)  # planted as a row: two current rows at one key is an anomaly no writer leaves
    db.commit()
    _refuses(db, company, payload, rf"\(fact {row.id}\): another row is current at this key \(fact {other.id}\)")


def _state(**overrides):
    fact = {"company_id": 1, "filing_id": None, "concept": "net_income", "raw_tag": "us-gaap:NetIncomeLoss",
            "unit": "USD", "period_start": date(2021, 1, 1), "period_end": date(2021, 12, 31), "fiscal_year": 2021,
            "fiscal_period": "FY", "value": 13_049e6, "form": "10-K", "accession": "K21", "source": "companyfacts",
            "reconciled": True, "provenance": None, **overrides}
    return fact, repair._candidate_state(fact)


def test_an_ambiguous_winner_refuses():
    # A pure test of the planner: the normalizer keeps one fact per identity, and so far one per key.
    _fact, stored = _state(value=12_345e6, form="DEF 14A", accession="P26")
    winners = [_state()[0], _state(accession="K22")[0]]
    with pytest.raises(proxy.ProxyRepairRefused, match=r"\(fact 7\): the payload holds more than one winner at this key"):
        proxy.plan({7: stored}, {}, winners, {}, _payload({}))


def test_a_winner_in_another_currency_refuses_until_a_sync(db, monkeypatch):
    company = _company(db, "CNY")
    payload = _cny_payload()
    _items(payload, REV_TAG).extend([  # a proxy's USD figures: one at a year the CNY list lacks made the old
        # sync read the whole series in USD (series_unit), and one at a year it has won that year
        _item(100e9, "2021-03-31", start="2020-04-01", accn="P24", fy=2024, form="DEF 14A", filed="2024-08-01"),
        _item(120e9, "2023-03-31", start="2022-04-01", accn="P24", fy=2024, form="DEF 14A", filed="2024-08-01"),
    ])
    payload = _for(company, payload)
    with monkeypatch.context() as patch:
        # The old sync read each concept's list in one currency (``series_unit``, before #1583): revenue
        # in USD, every other concept in CNY. Today's pick reads each filing in its own currency and never
        # a foreign filing's items, so the shape is planted with the old units, on a sync in USD alone
        # (the pick both the collector and ``payload_view`` read says USD and no foreign filing), which
        # is main's upsert: main 163ce89c's own run of this test stored these 21 rows, every one current.
        collect = companyfacts._collect_companyfacts_values

        def old_units(usgaap, tags, unit_key, *, instant, foreign=frozenset()):
            unit = unit_key.replace("CNY", "USD") if REV_TAG in tags else unit_key.replace("USD", "CNY")
            return collect(usgaap, tags, unit, instant=instant, foreign=foreign)

        patch.setattr(companyfacts, "_collect_companyfacts_values", old_units)
        patch.setattr(currency, "_filing_pick", lambda *args: ("USD", frozenset(), {}, None))
        _old_sync(db, monkeypatch, company, payload)
    planted = _rows(db, company)
    assert len(planted) == 21 and all(r.is_latest for r in planted)
    assert {(r.concept == "revenue", r.unit) for r in planted} == {(True, "USD"), (False, "CNY"), (False, "CNY/shares")}
    [row] = _current_proxy_rows(db, company)
    assert (row.period_end, row.unit) == (date(2023, 3, 31), "USD")
    _refuses(db, company, payload, rf"\(fact {row.id}\): the payload's winner for this period is in CNY; "
                                   "sync the company first")
    svc._persist_companyfacts_payload(db, company, payload)  # the sync the refusal asks for
    db.commit()
    assert _current_proxy_rows(db, company) == []
    assert {r.unit for r in _rows(db, company, concept="revenue", is_latest=True)} == {"CNY"}
    assert _preview(db, company, payload)["proxy"]["retired"] == 0


def test_no_winner_but_a_stored_report_row_refuses(db, monkeypatch):
    company, payload = _only_a_proxy_tags_2021(db, monkeypatch, "RPT")
    filing = _filing(db, company, "K21", "2021-12-31", "2022-02-25")
    _file(db, monkeypatch, filing, {"net_income": ("2021-01-01", 90e6)})
    report = _filing_row(db, filing)
    assert (report.source, report.is_latest) == ("edgar_xbrl", False)
    [row] = [r for r in _current_proxy_rows(db, company) if r.period_end.year == 2021]
    _refuses(db, company, payload, rf"\(fact {row.id}\): a stored report row \(fact {report.id}\) has no fresh "
                                   "winner to agree with")


def _a_stored_eur_row(db, company):
    """A stored, non-current EUR net income row (a stray the per-filing pick once read): every sync of the company's net
    income then involves another currency than USD (``currency._another_currency``), so the currency step runs."""
    db.add(FinancialFact(company_id=company.id, concept="net_income", unit="EUR", value=1.0,
                         period_end=date(2019, 5, 31), period_start=date(2018, 6, 1), fiscal_year=2019,
                         fiscal_period="FY", accession=_accn(company, "X19"), form="10-K", source="edgar_xbrl",
                         is_latest=False))
    db.commit()


@pytest.mark.parametrize(("clause", "parsed", "start", "fiscal_year"), [
    ("value", 17_000e6, "2025-01-01", None), ("start", 18_254e6, "2025-02-01", None),
    ("fiscal year", 18_254e6, "2025-01-01", 2024),
])
@pytest.mark.parametrize("synced", [False, True], ids=["as-planted", "after-a-sync-involving-eur"])
def test_a_disagreeing_filing_row_refuses(db, monkeypatch, clause, parsed, start, fiscal_year, synced):
    # A sync that involves another currency leaves the key as main does: the 10-K's identity is stored behind P26's
    # current row, so the upsert skips it and the newer-filing rule leaves the key as found (#1583 never protects a
    # proxy's row, but leaves a stored identity behind it), and the step refuses as before the sync.
    company, payload, filing = _filed_behind(db, monkeypatch, "CCD", parsed=parsed, start=start)
    report = _filing_row(db, filing)
    if fiscal_year is not None:
        report.fiscal_year = fiscal_year  # planted as a label edit
        db.commit()
    if synced:
        _a_stored_eur_row(db, company)
        _resync(db, company, payload)
        assert not _filing_row(db, filing).is_latest
    [row] = _current_proxy_rows(db, company)
    _refuses(db, company, payload, rf"\(fact {row.id}\): the filing row holding the 10-K's identity "
                                   rf"\(fact {report.id}\) disagrees with the 10-K on: {clause}$")


def test_a_filing_calculation_built_on_a_proxy_refuses(db, monkeypatch):
    company, payload = _unhealed(db, monkeypatch, "CAL")
    filing = _filing(db, company, "F25", "2025-12-31", "2026-02-25")
    margin = FinancialFact(company_id=company.id, filing_id=filing.id, concept="net_margin", raw_tag=None,
                           unit="pure", period_start=date(2025, 1, 1), period_end=date(2025, 12, 31),
                           fiscal_year=2025, fiscal_period="FY", value=Decimal("28.1"), form="10-K",
                           accession=filing.accession_number, source="edgar_xbrl", reconciled=True, is_latest=True,
                           provenance={"version": 1, "method": "calculated", "validation": "passed", "reasons": [],
                                       "inputs": [{"concept": "net_income", "accession": _accn(company, "P26")}]})
    db.add(margin)  # planted as a row: a filing's calculation names its own accession's operands
    db.commit()
    _refuses(db, company, payload, rf"\(fact {margin.id}\): a row outside the repair's scope is built on a proxy figure")


def test_the_apply_refuses_when_a_proxy_row_would_stay_current(db, monkeypatch):
    company, payload = _unhealed(db, monkeypatch, "NOP")
    planted = _snapshots(db, company)

    def no_step(before, updates, facts, normalized, payload):
        return proxy.ProxyPlan(inserts=[], tagged=set(), accessions=proxy.proxy_accessions(before.values()),
                               keys={}, counts=dict(_STEP_ZERO), rows=[])

    monkeypatch.setattr(proxy, "plan", no_step)
    for dry_run in (True, False):
        with pytest.raises(ValueError, match=r"Proxy repair would leave rows for detection: \{'current_proxy_rows': 6"):
            repair.repair_company(db, company.id, payload, dry_run=dry_run, run_id="nop")
        db.rollback()
    assert db.query(FinancialFactRevision).count() == 0 and _snapshots(db, company) == planted


def test_a_proxy_confirmed_parse_the_10k_contradicts_refuses(db, monkeypatch):
    company, payload, filing = _cross_checked(db, monkeypatch, "RRR", _fdx_payload(), 4_092.0)
    row = _filing_row(db, filing)
    check = _check(row)
    assert (row.source, float(row.value), check["outcome"], check["authoritative_value"]) == (
        "edgar_xbrl", 4_092.0, "confirmed", 4_092.0)  # FedEx's proxy in dollars certified a parse in units
    _refuses(db, company, payload, rf"\(fact {row.id}\): the old cross-check confirmed this filing row against a "
                                   "proxy's figure, and the 10-K's figure disagrees with it by more than 1%")


# --- Round 2: rows detection keeps listing, the authority-absent branches, re-annotation, the postcondition -----

def test_a_filing_row_confirmed_against_the_10ks_own_figure_is_kept_and_named(db, monkeypatch):
    # The proxy quotes the 10-K exactly, so the figure the old check confirmed the row against is the 10-K's:
    # the row is right and stays as it is. Set 5 still lists it after the apply (it is the 10-K's winner, so
    # no other stored report row holds the figure), and the report names it by fact id with its verdict.
    company, payload, filing = _confirmed_by_the_10ks_figure(db, monkeypatch)
    row = _filing_row(db, filing)
    check = _check(row)
    assert (row.source, row.is_latest, check["outcome"], check["authoritative_value"]) == (
        "edgar_xbrl", False, "confirmed", 18_254e6)
    stored = repair.snapshot(row)
    listed = [{"fact_id": row.id, "set": 5, "verdict": "kept_confirmed_by_10k"}]
    plan = _preview(db, company, payload)
    assert plan["proxy"]["filing_rows_kept"] == 1 and plan["proxy"]["filing_rows_reconfirmed"] == 0
    assert [e["action"] for e in plan["proxy"]["rows"] if e["fact_id"] == row.id] == ["kept_confirmed_by_10k"]
    assert plan["proxy"]["detection_listed"] == listed
    applied = _apply(db, company, payload)
    assert repair.snapshot(_filing_row(db, filing)) == {**stored, "is_latest": True}  # promoted, nothing else
    assert applied["proxy"]["detection_listed"] == listed
    assert _detection(db, {company.ticker: payload})[5] == [(company.ticker, row.id)]


@pytest.mark.parametrize("proxy_rows", [False, True], ids=["payload-witness", "stored-proxy-rows"])
def test_a_replacement_where_the_payload_has_no_10k_figure_is_restored_to_the_parse(db, monkeypatch, proxy_rows):
    # Only a proxy tags FY2021's net income, so today's backfill would keep the filing's parse: the restore
    # writes the recorded original with the local verdict and no authoritative check. Where a sync also
    # stored the proxy's rows, the restored row is then a report row at a key with no fresh winner.
    company, payload, filing = _only_a_proxy_tags_2021_and_the_10k_was_replaced(db, monkeypatch, proxy_rows=proxy_rows)
    row = _filing_row(db, filing)
    assert (float(row.value), row.source, _check(row)["original_value"]) == (90e6, "companyfacts", 85e6)
    if proxy_rows:
        [retired] = [r for r in _current_proxy_rows(db, company) if r.period_end.year == 2021]
        _refuses(db, company, payload, rf"\(fact {retired.id}\): a stored report row \(fact {row.id}\) has no "
                                       "fresh winner to agree with")
        return
    plan = _preview(db, company, payload)
    assert _counts(plan["proxy"]) == {"filing_rows_restored": 1}
    _apply(db, company, payload)
    row = _filing_row(db, filing)
    assert (float(row.value), row.source, row.reconciled) == (85e6, "edgar_xbrl", True)
    assert row.provenance["checks"] == {"local_reconciliation": {"reasons": []}}
    assert row.provenance["validation"] == "passed"


def test_a_proxy_confirmed_row_with_no_10k_figure_keeps_its_value_and_the_local_verdict(db, monkeypatch):
    # The old check confirmed the parse against the proxy's figure; today's backfill, with no authority for
    # the year, keeps the local verdict and records no authoritative check.
    company, payload, filing = _only_a_proxy_tags_2021_and_the_10k_was_replaced(db, monkeypatch, parsed=90e6)
    row = _filing_row(db, filing)
    assert (row.source, _check(row)["outcome"], _check(row)["authoritative_value"]) == ("edgar_xbrl", "confirmed", 90e6)
    stored = repair.snapshot(row)
    plan = _preview(db, company, payload)
    assert _counts(plan["proxy"]) == {"filing_rows_reconfirmed": 1}
    _apply(db, company, payload)
    row = _filing_row(db, filing)
    assert (row.value, row.source, row.is_latest) == (Decimal(stored["value"]), "edgar_xbrl", stored["is_latest"])
    assert row.reconciled and row.provenance["checks"] == {"local_reconciliation": {"reasons": []}}


def test_a_proxy_confirmed_row_a_report_also_backs_is_left_alone(db, monkeypatch):
    # The proxy's rounded figure is also an earnings release's, stored as a report row: the confirmation
    # may have come from that report, so set 5 leaves the row, as set 4 leaves a report-backed one.
    company, payload, filing = _confirmed(db, monkeypatch, "RBK")
    release = FinancialFact(company_id=company.id, concept="net_income", raw_tag="us-gaap:NetIncomeLoss", unit="USD",
                            period_start=date(2025, 1, 1), period_end=date(2025, 12, 31), fiscal_year=2025,
                            fiscal_period="FY", value=Decimal("18250000000"), form="8-K",
                            accession=_accn(company, "E26"), source="companyfacts", reconciled=True, is_latest=False)
    db.add(release)  # planted as a row: a sync that read the release before the 10-K stored it
    db.commit()
    stored = repair.snapshot(_filing_row(db, filing))
    plan = _preview(db, company, payload)
    assert plan["proxy"]["filing_rows_reconfirmed"] == 0 and plan["proxy"]["filing_rows_kept"] == 0
    [left] = plan["proxy"]["left_report_backed"]
    assert (left["fact_id"], left["set"], left["figure"], left["authority"]) == (
        _filing_row(db, filing).id, 5, "18250000000", 18_254e6)
    assert left["backed_by"] == [{"fact_id": release.id, "accession": release.accession, "form": "8-K",
                                  "is_latest": False, "filing_id": None, "source": "companyfacts"}]
    _apply(db, company, payload)
    assert repair.snapshot(_filing_row(db, filing)) == {**stored, "is_latest": True}  # promoted only


@pytest.mark.parametrize("shape", ["legacy_margin", "other_calculation", "companyfacts_calculation",
                                   "operands_not_found"])
def test_the_restore_reannotates_only_filing_calculations_of_a_rewritten_concept(db, monkeypatch, shape):
    # Re-annotation writes provenance and reconciled only on a filing-owned calculation with a version-1
    # record over a concept sets 4 and 5 rewrote, whose operands the calculator finds: a calculation with no
    # record is the lineage backfill's (filing_lineage_repair.is_target), and any other record stays as it is.
    if shape == "companyfacts_calculation":  # the companyfacts margin shares the restored row's scope
        company, payload, filing = _replaced_where_the_10k_names_the_margin(db, monkeypatch)
        [untouched] = [r for r in _rows(db, company, concept="net_margin", fiscal_period="FY",
                                        period_end=date(2025, 12, 31))
                       if r.accession == filing.accession_number and r.filing_id is None]
        expected = 0
    elif shape == "operands_not_found":  # revenue has left the margin's scope: the calculator finds no
        company, payload, filing = _replaced(db, monkeypatch, "DNF")  # operands, so the record would be empty
        _filing_row(db, filing, "revenue").fiscal_year = 2024  # planted as a label edit
        db.commit()
        untouched = _filing_row(db, filing, "net_margin")
        assert {i["concept"] for i in untouched.provenance["inputs"]} == {"net_income", "revenue"}
        expected = 0
    else:
        company, payload, filing = _replaced_with_operating_rows(db, monkeypatch)
        untouched = _filing_row(db, filing, "net_margin" if shape == "legacy_margin" else "operating_margin")
        if shape == "legacy_margin":  # a calculation stored before #1191, with no record
            untouched.provenance = None
        else:  # a record a recompute over these operands would rewrite, on a calculation of other inputs
            untouched.provenance = {**untouched.provenance, "reasons": ["recorded_before_this_repair"]}
        db.commit()
        expected = 0 if shape == "legacy_margin" else 1
    assert _filing_row(db, filing).source == "companyfacts"  # the replacement the step restores
    before = repair.snapshot(untouched)
    plan = _preview(db, company, payload)
    assert (plan["proxy"]["filing_rows_restored"], plan["proxy"]["filing_calculations_reannotated"]) == (1, expected)
    assert untouched.id not in [e["fact_id"] for e in plan["proxy"]["rows"] if e["action"] == "reannotated"]
    assert all(change["after"]["provenance"] == before["provenance"] for change in plan["changes"]
               if change["fact_id"] == untouched.id and shape != "companyfacts_calculation")
    _apply(db, company, payload)
    if shape != "companyfacts_calculation":  # the loop recomputes the companyfacts margin on its own terms
        assert repair.snapshot(db.get(FinancialFact, untouched.id)) == before


@pytest.mark.parametrize("revenue_in_dollars", [False, True], ids=["restored-and-reconfirmed", "both-restored"])
def test_a_filing_calculation_is_reannotated_once_after_both_passes(db, monkeypatch, revenue_in_dollars):
    # Net income restored (set 4) and revenue re-recorded (set 5) or also restored, in one filing: the
    # margin is re-annotated once, after both, so each operand's record in it is the operand's own now.
    company, payload, filing = _replaced_and_confirmed_in_one_filing(db, monkeypatch,
                                                                    revenue_in_dollars=revenue_in_dollars)
    revenue = _filing_row(db, filing, "revenue")
    assert (revenue.source, _check(revenue)["outcome"]) == (
        ("companyfacts", "replaced") if revenue_in_dollars else ("edgar_xbrl", "confirmed"))
    margin = _filing_row(db, filing, "net_margin")
    plan = _preview(db, company, payload)
    assert plan["proxy"]["filing_calculations_reannotated"] == 1
    assert [e["fact_id"] for e in plan["proxy"]["rows"] if e["action"] == "reannotated"] == [margin.id]
    _apply(db, company, payload)
    operands = {i["concept"]: i for i in _filing_row(db, filing, "net_margin").provenance["inputs"]}
    for concept, value in (("net_income", 4_092e6), ("revenue", 87_926e6)):
        own = _filing_row(db, filing, concept).provenance
        assert operands[concept]["value"] == value
        assert operands[concept]["provenance"]["checks"]["authoritative"] == own["checks"]["authoritative"]
        assert own["checks"]["authoritative"]["authoritative_value"] == value


def _margin_operand_check(margin, concept="net_income"):
    return {i["concept"]: i for i in margin.provenance["inputs"]}[concept]["provenance"]["checks"]["authoritative"]


def test_a_reconfirm_alone_reannotates_its_filings_calculations(db, monkeypatch):
    # Set 5 alone rewrites net income's check in the margin's scope (no set-4 restore schedules it): the margin
    # is re-annotated, so the operand record it carries names the 10-K's figure, not the proxy's.
    company, payload, filing = _reconfirmed_with_its_margin(db, monkeypatch)
    margin = _filing_row(db, filing, "net_margin")
    assert (margin.provenance["version"], margin.provenance["validation"]) == (1, "passed")
    assert _margin_operand_check(margin)["authoritative_value"] == 18_250e6
    plan = _preview(db, company, payload)
    assert {name: plan["proxy"][name] for name in ("filing_rows_restored", "filing_rows_reconfirmed",
                                                   "filing_calculations_reannotated", "filing_calculations_held")} == {
        "filing_rows_restored": 0, "filing_rows_reconfirmed": 1, "filing_calculations_reannotated": 1,
        "filing_calculations_held": 0}
    assert [e["fact_id"] for e in plan["proxy"]["rows"] if e["action"] == "reannotated"] == [margin.id]
    _apply(db, company, payload)
    margin = _filing_row(db, filing, "net_margin")
    own = _check(_filing_row(db, filing))
    assert own["authoritative_value"] == 18_254e6 and _margin_operand_check(margin) == own
    assert (margin.provenance["validation"], margin.reconciled) == ("passed", True)


def _with_revenue_withheld(db, filing):
    """The filing's revenue made a companyfacts row a correction retired with the filing's labels, so it
    stays in the margin's scope and its record reads unavailable (planted as a row)."""
    revenue = _filing_row(db, filing, "revenue")
    retired = repair._quarantine(repair.snapshot(revenue), "legacy_period_label_mismatch")
    revenue.filing_id, revenue.source, revenue.is_latest = None, "companyfacts", False
    revenue.reconciled, revenue.provenance = False, retired["provenance"]
    db.commit()


def test_a_restore_that_clears_a_margins_mismatch_reannotates_it(db, monkeypatch):
    # Re-annotation's usual result: the margin, annotated against the proxy's net income, read
    # calculation_mismatch; with the 10-K's figure restored it passes. A change of validation is no hold:
    # the hold is for a record that would withhold a figure readers see today, nothing else.
    company, payload, filing = _replaced_with_its_margin(db, monkeypatch)
    assert (_filing_row(db, filing).source, float(_filing_row(db, filing).value)) == ("companyfacts", 18_000e6)
    margin = _filing_row(db, filing, "net_margin")
    assert (margin.provenance["validation"], margin.provenance["reasons"]) == ("needs_review", ["calculation_mismatch"])
    plan = _preview(db, company, payload)
    assert {name: plan["proxy"][name] for name in ("filing_rows_restored", "filing_calculations_reannotated",
                                                   "filing_calculations_held")} == {
        "filing_rows_restored": 1, "filing_calculations_reannotated": 1, "filing_calculations_held": 0}
    _apply(db, company, payload)
    margin = _filing_row(db, filing, "net_margin")
    assert (margin.provenance["validation"], margin.provenance["reasons"], margin.reconciled) == ("passed", [], True)
    assert {i["concept"]: i["value"] for i in margin.provenance["inputs"]} == {
        "net_income": 18_254e6, "revenue": 64_900e6}


def test_a_calculation_already_withheld_is_reannotated_not_held(db, monkeypatch):
    # The hold keeps a figure readers see today. A margin whose record already reads unavailable shows no
    # figure, so it is re-annotated like any other: its operand record names the 10-K's figure, and it stays
    # withheld.
    company, payload, filing = _reconfirmed_with_its_margin(db, monkeypatch, "LRU")
    _with_revenue_withheld(db, filing)
    margin = _filing_row(db, filing, "net_margin")
    margin.provenance = {**margin.provenance, "validation": "unavailable", "reasons": ["legacy_period_label_mismatch"]}
    margin.reconciled = False  # planted as a row: annotated once revenue was withheld
    db.commit()
    plan = _preview(db, company, payload)
    assert {name: plan["proxy"][name] for name in ("filing_rows_reconfirmed", "filing_calculations_reannotated",
                                                   "filing_calculations_held")} == {
        "filing_rows_reconfirmed": 1, "filing_calculations_reannotated": 1, "filing_calculations_held": 0}
    _apply(db, company, payload)
    margin = _filing_row(db, filing, "net_margin")
    assert (margin.provenance["validation"], margin.reconciled) == ("unavailable", False)
    assert _margin_operand_check(margin)["authoritative_value"] == 18_254e6


def test_a_reannotation_that_would_withhold_a_shown_figure_is_held(db, monkeypatch):
    # The lineage backfill's operand_withheld hold: revenue, in the margin's scope, is a companyfacts row a
    # correction retired with the filing's labels, so a recomputed margin would read unavailable and leave
    # the public pages. The margin keeps its record, and the preview names it.
    company, payload, filing = _reconfirmed_with_its_margin(db, monkeypatch, "LRW")
    _with_revenue_withheld(db, filing)
    margin = _filing_row(db, filing, "net_margin")
    stored = repair.snapshot(margin)
    assert stored["provenance"]["validation"] == "passed"
    plan = _preview(db, company, payload)
    assert {name: plan["proxy"][name] for name in ("filing_rows_reconfirmed", "filing_calculations_reannotated",
                                                   "filing_calculations_held")} == {
        "filing_rows_reconfirmed": 1, "filing_calculations_reannotated": 0, "filing_calculations_held": 1}
    [held] = [e for e in plan["proxy"]["rows"] if e["fact_id"] == margin.id]
    assert (held["action"], held["hold"], held["winner_value"]) == ("reannotation_held", "operand_withheld", None)
    assert held["reasons"] == ["legacy_period_label_mismatch"]
    assert margin.id not in [change["fact_id"] for change in plan["changes"]]
    _apply(db, company, payload)
    assert repair.snapshot(db.get(FinancialFact, margin.id)) == stored
    # Nothing names it again: the next run leaves its operand as the apply wrote it, and so leaves it too.
    again = _apply(db, company, payload, run_id="apply-2")
    assert (again["revisions"], again["proxy"]["filing_calculations_held"]) == (0, 0)
    assert repair.snapshot(db.get(FinancialFact, margin.id)) == stored


def test_a_twin_at_a_dependents_quarter_key_refuses_at_the_preview(db, monkeypatch):
    # A Q4 margin built on the proxy's FY2025 is left to the computed-metric correction, which recomputes it in
    # place: no upsert demotes a current row with no fiscal period at its period, so the plan refuses.
    company, payload = _unhealed(db, monkeypatch, "TDQ", payload=_with_revenue_quarters(_mrk_payload()))
    [dependent] = _rows(db, company, concept="net_margin", fiscal_period="Q4", is_latest=True)
    assert f'"{_accn(company, "P26")}"' in json.dumps(dependent.provenance)
    filing = _filing(db, company, "TWIN", "2025-12-31", "2026-03-01")
    db.add(FinancialFact(company_id=company.id, filing_id=filing.id, concept="net_margin", raw_tag=None, unit="pure",
                         period_start=date(2025, 10, 1), period_end=date(2025, 12, 31), fiscal_year=2025,
                         fiscal_period=None, value=Decimal("18.6"), form="10-K", accession=filing.accession_number,
                         source="edgar_xbrl", reconciled=True, is_latest=True))  # planted as a row
    db.commit()
    planted = _snapshots(db, company)
    with pytest.raises(ValueError, match=r"would leave rows for detection") as raised:
        _preview(db, company, payload)
    assert "'keys_not_settled': [['net_margin', '2025-12-31', 'Q4', 'pure', 1, 1, 1]]}" in str(raised.value)
    assert _snapshots(db, company) == planted


def test_a_sync_after_the_apply_is_read_against_a_fresh_dry_run(db, monkeypatch):
    # The done criterion compares the file with the apply's listing right after the apply. A sync in between
    # stores a later 10-K's comparative, which backs the kept row and takes it off set 5; a fresh dry run
    # reads the rows as they stand, so its listing is the file's again.
    company, payload, filing = _confirmed_by_the_10ks_figure(db, monkeypatch, "SYN")
    row = _filing_row(db, filing)
    applied = _apply(db, company, payload)["proxy"]["detection_listed"]
    assert applied == [{"fact_id": row.id, "set": 5, "verdict": "kept_confirmed_by_10k"}]
    later = copy.deepcopy(payload)
    _items(later).append(_item(18_254e6, "2025-12-31", start="2025-01-01", accn=_accn(company, "K26"), fy=2026,
                               filed="2027-02-25"))
    _resync(db, company, later)
    assert _detection(db, {company.ticker: later})[5] == []
    fresh = _preview(db, company, later)["proxy"]
    assert fresh["detection_listed"] == [] and _counts(fresh) == {}


def test_a_promotion_beside_a_current_row_with_no_fiscal_period_refuses_at_the_preview(db, monkeypatch):
    # A promoted (or corrected) row is made current in place: no upsert demotes a current row with no fiscal
    # period at its quarter's period, so the plan sees the two current rows and refuses before any write.
    company, payload = _demoted(db, monkeypatch)
    _twin_row(db, company, _filing(db, company, "TWIN", "2025-12-31", "2026-03-01"))
    planted = _snapshots(db, company)
    with pytest.raises(ValueError, match=r"would leave rows for detection") as raised:
        _preview(db, company, payload)
    # Only the quarter key counts it: the FY2025 key the step also promotes shares the period end, but a
    # row with no fiscal period is never a twin at an annual key.
    assert "'keys_not_settled': [['net_income', '2025-12-31', 'Q4', 'USD', 1, 1, 1]]}" in str(raised.value)
    assert _snapshots(db, company) == planted


def test_a_second_current_row_at_a_dependents_key_refuses(db, monkeypatch):
    # A calculation left to the loop keeps its key, which must then hold it alone.
    company, payload = _unhealed(db, monkeypatch, "DUP")
    db.add(FinancialFact(company_id=company.id, concept="net_margin", raw_tag=None, unit="pure",
                         period_start=date(2021, 1, 1), period_end=date(2021, 12, 31), fiscal_year=2021,
                         fiscal_period="FY", value=Decimal("26.8"), form="10-K", accession=_accn(company, "X21"),
                         source="companyfacts", reconciled=True, is_latest=True))  # planted: an anomaly
    db.commit()
    with pytest.raises(ValueError, match=r"would leave rows for detection") as raised:
        _preview(db, company, payload)
    assert "['net_margin', '2021-12-31', 'FY', 'pure', 2, 0, 1]" in str(raised.value)


def test_two_proxy_rows_at_one_key_retire_together_and_admit_one_winner(db, monkeypatch):
    company, payload = _unhealed(db, monkeypatch, "TWP")
    [first] = [r for r in _current_proxy_rows(db, company) if (r.fiscal_period, r.period_end.year) == ("FY", 2021)]
    second = FinancialFact(company_id=company.id, concept="net_income", raw_tag="us-gaap:NetIncomeLoss", unit="USD",
                           period_start=date(2021, 1, 1), period_end=date(2021, 12, 31), fiscal_year=2021,
                           fiscal_period="FY", value=Decimal("12345000000"), form="DEFA14A",
                           accession=_accn(company, "PA26"), source="companyfacts", reconciled=True, is_latest=True)
    db.add(second)  # planted as a row: an additional proxy's item, current beside the first
    db.commit()
    plan = _preview(db, company, payload)
    assert _counts(plan["proxy"]) == {"retired": 7, "inserted": 6, "dependents_recomputed": 5}
    _apply(db, company, payload)
    for row_id in (first.id, second.id):
        row = db.get(FinancialFact, row_id)
        assert not row.is_latest and row.provenance["replacement"]["accession"] == _accn(company, "K23")
    [winner] = _rows(db, company, concept="net_income", fiscal_period="FY", period_end=date(2021, 12, 31),
                     is_latest=True)
    assert winner.accession == _accn(company, "K23")


def _listed_state(**overrides):
    _fact, state = _state(**{"filing_id": 3, "accession": "K25", "form": "10-K", "source": "edgar_xbrl",
                             **overrides})
    return state


def test_detection_listed_reads_sets_4_and_5_as_the_file_does():
    # The report's detection_listed transcribes the file's sets 4 and 5 (only a stored proxy row
    # witnesses); the PR records the file's own run over the shapes above. Each branch, once.
    proxy_row = _listed_state(filing_id=None, form="DEF 14A", accession="P26", value=12_345e6)
    replaced = {"checks": {"authoritative": {"original_value": 11_000e6, "outcome": "replaced"}}}
    rows = [
        (1, proxy_row),
        (2, _listed_state(source="companyfacts", value=12_345e6, provenance=replaced)),  # why = proxy row
        (3, _listed_state(source="companyfacts", value=12_345e6, concept="revenue",  # why = scale: no proxy
                          provenance={"checks": {"authoritative": {"original_value": 12_345e9}}})),  # row, 1/1,000
        (4, _listed_state(source="companyfacts", value=12_345e9, period_end=date(2022, 12, 31),
                          provenance={"checks": {"authoritative": {"original_value": 12_345e6}}})),  # neither
        (5, _listed_state(value=13_049e6, provenance={"checks": {"authoritative": {  # set 5
            "outcome": "confirmed", "authoritative_value": 12_345e6}}})),
        (6, _listed_state(value=13_049e6, provenance={"checks": {"authoritative": {  # replaced, not confirmed
            "outcome": "replaced", "authoritative_value": 12_345e6}}})),
        (7, _listed_state(value=13_049e6, concept="revenue", provenance={"checks": {"authoritative": {
            "outcome": "confirmed", "authoritative_value": 12_345e6}}})),  # no proxy row at revenue
        (9, _listed_state(source="companyfacts", value=4_092.0, period_end=date(2023, 12, 31),  # why = scale,
                          provenance={"checks": {"authoritative": {"original_value": 4_092e6}}})),  # 1/1,000,000
        (10, _listed_state(value=13_049e6, period_end=date(2024, 12, 31), provenance={"checks": {"authoritative": {
            "outcome": "confirmed", "authoritative_value": 500.0}}})),
        (11, _listed_state(filing_id=None, source="companyfacts", form=None, accession="X24",  # no form: no
                           value=500.0, period_end=date(2024, 12, 31))),  # proxy's witness, so 10 is not listed
        (12, _listed_state(filing_id=None, form="DEF 14A", accession="P26", value=700.0,  # a proxy row, so 13 is
                           period_end=date(2020, 12, 31))),  # listed: 14, of no form, is no report row to back it
        (13, _listed_state(value=13_049e6, period_end=date(2020, 12, 31), provenance={"checks": {"authoritative": {
            "outcome": "confirmed", "authoritative_value": 700.0}}})),
        (14, _listed_state(filing_id=None, source="companyfacts", form=None, accession="X20", value=700.0,
                           period_end=date(2020, 12, 31))),
        (15, _listed_state(filing_id=None, form="DEF 14A", accession="P26", value=800.0,  # as 12-14, with a
                           period_end=date(2019, 12, 31))),  # blank form: 17 is no report row, so 16 is listed
        (16, _listed_state(value=13_049e6, period_end=date(2019, 12, 31), provenance={"checks": {"authoritative": {
            "outcome": "confirmed", "authoritative_value": 800.0}}})),
        (17, _listed_state(filing_id=None, source="companyfacts", form="  ", accession="X19", value=800.0,
                           period_end=date(2019, 12, 31))),
    ]
    verdicts = {2: "kept_agrees_with_authority", 5: "kept_confirmed_by_10k", 9: "no_proxy_figure", 13: "reconfirmed",
                16: "reconfirmed"}
    assert proxy.detection_listed(rows, verdicts) == [
        {"fact_id": 2, "set": 4, "verdict": "kept_agrees_with_authority"},
        {"fact_id": 3, "set": 4, "verdict": "unclassified"},
        {"fact_id": 5, "set": 5, "verdict": "kept_confirmed_by_10k"},
        {"fact_id": 9, "set": 4, "verdict": "no_proxy_figure"},
        {"fact_id": 13, "set": 5, "verdict": "reconfirmed"},
        {"fact_id": 16, "set": 5, "verdict": "reconfirmed"},
    ]
    scaled_up = {"checks": {"authoritative": {"original_value": 12_345.0}}}  # the authority scaled a units parse
    assert proxy.detection_listed([(1, proxy_row), (2, _listed_state(source="companyfacts", value=12_345e6,
                                                                     provenance=scaled_up))], {}) == []
    # A report row holding the figure takes a row off either set.
    report = _listed_state(filing_id=None, source="companyfacts", value=12_345e6, accession="K26")
    assert proxy.detection_listed([*rows[:3], *rows[4:6], (8, report)], verdicts) == [
        {"fact_id": 3, "set": 4, "verdict": "unclassified"}]


def _edge_rows():
    """Rows on each of the file's edges and just past it, one period end per case: ``(rows, listed ids)``.
    The file compares in numeric, exactly; in floats 101 / 100,000 * 1,000 is 1.0100000000000002, and
    1e-6 * 1,110,000 falls short of 1.11."""
    def scale(value, original):  # a replacement whose original is recorded, no proxy row beside it
        return [_listed_state(source="companyfacts", value=Decimal(value),
                              provenance={"checks": {"authoritative": {"original_value": original}}})]

    def witnessed(value, original=None, witness=None):  # a replacement a proxy row holds
        record = None if original is None else {"checks": {"authoritative": {"original_value": original}}}
        return [_listed_state(filing_id=None, form="DEF 14A", accession="P26", value=Decimal(witness or value)),
                _listed_state(source="companyfacts", value=Decimal(value), provenance=record)]

    def confirmed(figure, report=None):  # a confirmation against a figure a proxy row holds
        return [_listed_state(filing_id=None, form="DEF 14A", accession="P26", value=Decimal("1110000")),
                _listed_state(value=Decimal("13049000000"), provenance={"checks": {"authoritative": {
                    "outcome": "confirmed", "authoritative_value": figure}}}),
                *([] if report is None else [_listed_state(filing_id=None, source="companyfacts", accession="K26",
                                                           value=Decimal(report))])]

    cases = [  # (rows, listed): the filing row is the case's second row when a proxy row leads
        (scale("101", 100_000.0), True), (scale("101.0000001", 100_000.0), False),  # 1/1,000, upper edge
        (scale("99", 100_000.0), True), (scale("98.9999999", 100_000.0), False),  # 1/1,000, lower edge
        (scale("1.01", 1_000_000.0), True), (scale("1.0100001", 1_000_000.0), False),  # 1/1,000,000
        (witnessed("101000", 100.0), False), (witnessed("101000.01", 100.0), True),  # 1,000 times: scaled up
        (witnessed("101000000", 100.0), False), (witnessed("101000000.01", 100.0), True),  # 1,000,000 times
        (witnessed("1109998.89", witness="1110000"), True),  # a witness 1e-6 away
        (witnessed("1109998.8899", witness="1110000"), False),
        (confirmed(1_109_998.89), True), (confirmed(1_109_998.8899), False),  # set 5's witness
        (confirmed(1_110_000.0, report="1109998.89"), False),  # a report row 1e-6 away backs it
        (confirmed(1_110_000.0, report="1109998.8899"), True),
    ]
    rows, listed, fact_id = [], [], 0
    for year, (states, shown) in enumerate(cases, start=2001):
        for state in states:
            fact_id += 1
            rows.append((fact_id, {**state, "period_end": date(year, 12, 31).isoformat()}))
            if shown and state["filing_id"] is not None:
                listed.append(fact_id)
    return rows, listed


def test_detection_listed_compares_exactly_at_each_edge():
    # The scale bands' edges (1/1,000, 1/1,000,000, 1,000 and 1,000,000 times, within 1%) and the 1e-6
    # witness and report-row edges, each on the edge and just past it, as the file's numeric reads them.
    rows, listed = _edge_rows()
    assert [entry["fact_id"] for entry in proxy.detection_listed(rows, {})] == listed


# --- A sync since #1682 (deployed 2026-10-28 23:13Z): each restated year's own-report value, as a history row --------
#
# Production holds the shapes above as the writers stored them before #1682. A company synced since also holds a history
# row (facts/own_reports.py) for each year a later report restated, at the year's own report's accession: non-current,
# with no filing owner, source companyfacts and a report form, so the step reads it as it reads a demoted winner, a
# report row. The history writer reads admitted items only and maps own reports by annual form, so a history row is
# never a proxy's figure, and it stores a row only where no row holds the identity, so it never takes a filing row's.

def _restating(build_payload):
    """``build_payload``'s payload in which each 10-K gives the oldest year it tags, two before its own, 0.5% above that
    year's own 10-K and the next: a later report restating a year, whose own report a sync since #1682 keeps beside the
    winner as a history row. No shape's filing row sits at a restated year. The harness's extra sync settles most
    shapes' set-2 rows before the step runs (only BBB keeps current proxy rows in a restated year), so the census
    differential holds history rows elsewhere in a company against what the step still plans; the tests after it put
    a history row in the periods the step plans on."""
    def built(*args, **kwargs):
        payload = build_payload(*args, **kwargs)
        for node in payload["facts"]["us-gaap"].values():
            for items in node["units"].values():
                for item in items:
                    if item["form"] == "10-K" and int(item["end"][:4]) == item["fy"] - 2:
                        item["val"] = float(round(item["val"] * 1.005))
        return payload
    return built


def _with_payloads(monkeypatch, restate):
    """Every shape's payload as ``restate`` gives it: the builders read these names when they run."""
    module = sys.modules[__name__]
    for name in ("_mrk_payload", "_fdx_payload", "_only_a_proxy_tags_payload"):
        monkeypatch.setattr(module, name, restate(getattr(module, name)))


@contextmanager
def _synced_before_and_since_1682(monkeypatch, build):
    """``build``'s shape planted alike in two databases, each then synced once more with the shape's payload: in the
    first by a sync as it ran before #1682, in the second by one since. Yields ``{since: (db, company, payload, *rest)}``;
    the two hold the same rows under the same ids, and the second the history rows too."""
    with ExitStack() as stack:
        states = {}
        for since in (False, True):
            db = stack.enter_context(_database())
            built = build(db, monkeypatch)
            company, payload = built[:2]
            if since:
                _resync(db, company, payload)
            else:
                _sync(db, monkeypatch, company, payload)
            states[since] = (db, *built)
        yield states


def _by_identity(db, company):
    return {repair._identity(state): state for state in _snapshots(db, company).values()}


def _journal(db):
    return {(repair._identity(r.after_state), r.action): (r.calculation_version, r.before_state, r.after_state)
            for r in db.query(FinancialFactRevision)}


def _the_step_reads_history_rows_as_nothing(states):
    """The step plans, writes, journals, lists and rolls back the same in both databases, and never touches a history
    row; each history row is a restated year's own 10-K figure. Returns the history rows by identity and the apply's
    result (None where both refuse alike)."""
    (old, company, payload), (new, company_since, _payload) = states[False][:3], states[True][:3]
    assert company_since.id == company.id
    held, stored = _by_identity(old, company), _snapshots(old, company)
    history = {identity: state for identity, state in _by_identity(new, company).items() if identity not in held}
    assert {row_id: state for row_id, state in _snapshots(new, company).items() if row_id in stored} == stored
    own = {(item["accn"], item["end"], float(item["val"])) for node in payload["facts"]["us-gaap"].values()
           for items in node["units"].values() for item in items
           if item["form"] == "10-K" and int(item["end"][:4]) == item["fy"]}
    assert history and all(not s["is_latest"] and s["filing_id"] is None and (s["form"], s["source"], s["fiscal_period"])
                           == ("10-K", "companyfacts", "FY") for s in history.values())
    assert {(s["accession"], s["period_end"], float(s["value"])) for s in history.values()} <= own

    def each(run):
        return [run(*state[:3]) for state in (states[False], states[True])]

    def preview(db, company, payload):
        try:
            return {name: value for name, value in _preview(db, company, payload).items() if name != "run_id"}
        except proxy.ProxyRepairRefused as refused:
            return str(refused)

    plan, plan_since = each(preview)
    assert plan_since == plan
    if isinstance(plan, str):  # refused alike: nothing to apply
        return history, None
    applied, applied_since = each(lambda db, company, payload: _apply(db, company, payload, run_id="since"))
    assert applied_since == applied and _journal(new) == _journal(old)
    after, after_since = each(lambda db, company, _payload: _by_identity(db, company))
    assert {identity: after_since[identity] for identity in history} == history
    assert {identity: state for identity, state in after_since.items() if identity not in history} == after
    found, found_since = each(lambda db, company, payload: _detection(db, {company.ticker: payload}))
    assert found_since == found and found[2] == found[3] == []
    assert {(ticker, row_id, number) for number in (4, 5) for ticker, row_id in found[number]} == {
        (company.ticker, entry["fact_id"], entry["set"]) for entry in applied["proxy"]["detection_listed"]}
    if not applied["revisions"]:  # the step and the other corrections leave the shape as it is
        assert _journal(old) == {} and after == held
        return history, applied
    for db, company, _payload in (states[False][:3], states[True][:3]):
        repair.rollback_company(db, company.id, "since", dry_run=False, run_id="rollback")
        db.commit()
    rolled, rolled_since = each(lambda db, company, _payload: _by_identity(db, company))
    assert {identity: rolled[identity] for identity in held} == held  # every row the apply wrote is as the sync left it
    assert {identity: rolled_since[identity] for identity in history} == history
    assert {identity: state for identity, state in rolled_since.items() if identity not in history} == rolled
    return history, applied


@pytest.mark.parametrize("ticker", list(_CENSUS))
def test_a_sync_since_1682_adds_history_rows_and_the_step_does_the_same(monkeypatch, ticker):
    # Each shape synced once more with a payload in which later 10-Ks restated years: a sync since #1682 adds the
    # restated years' own-report rows and changes no stored row, and the step's preview, apply, journal, detection
    # listing and rollback are those of the same shape synced as before #1682.
    _with_payloads(monkeypatch, _restating)
    with _synced_before_and_since_1682(monkeypatch, _CENSUS[ticker]) as states:
        _history, applied = _the_step_reads_history_rows_as_nothing(states)
        assert applied is not None  # no shape refuses over a restated year it holds no filing row at


def _restating_fy2025(build_payload):
    """FedEx's payload in which the FY2026 10-K gives FY2025 0.5% above the FY2025 10-K's own figure."""
    def built(*args, **kwargs):
        payload = build_payload(*args, **kwargs)
        for item in _items(payload):
            if item["form"] == "10-K" and (item["end"], item["fy"]) == ("2025-05-31", 2026):
                item["val"] = float(round(item["val"] * 1.005))
        return payload
    return built


def test_a_sync_since_1682_stores_no_history_row_at_the_identity_a_filing_row_holds(monkeypatch):
    # The FY2026 10-K restated FY2025, so a sync since #1682 keeps the FY2025 10-K's own figure as a history row at that
    # 10-K's accession unless a row holds the identity. The filing row set 4 restores holds it: the sync stores nothing
    # there and the row stays as it was, and the step restores it as in a company not synced since.
    _with_payloads(monkeypatch, lambda build: _restating_fy2025(_restating(build)))
    with _synced_before_and_since_1682(monkeypatch, _replaced) as states:
        new, company, payload, filing = states[True]
        identity = ("net_income", date(2025, 5, 31), "FY", "USD", filing.accession_number)
        _facts, meta = svc.normalize_companyfacts(company.id, payload)
        assert [h["value"] for h in meta["history"] if (h["concept"], h["period_end"], h["fiscal_period"], h["unit"],
                                                       h["accession"]) == identity] == [4_092e6]
        row = _filing_row(new, filing)
        assert (row.source, float(row.value)) == ("companyfacts", 4_092.0)  # the replacement, its identity held
        stored = repair.snapshot(row)
        assert [r.id for r in _rows(new, company, concept="net_income", period_end=date(2025, 5, 31),
                                    accession=filing.accession_number)] == [row.id]
        history, applied = _the_step_reads_history_rows_as_nothing(states)
        assert sorted((concept, end, accession) for concept, end, _period, _unit, accession in history
                      if concept == "net_income") == [
            ("net_income", f"{year}-05-31", _accn(company, f"K{year % 100}")) for year in (2022, 2023, 2024)]
        [restored] = [change["after"] for change in applied["changes"] if change["fact_id"] == row.id]
        check = restored["provenance"]["checks"]["authoritative"]
        assert (restored["value"], restored["source"], check["outcome"], check["authoritative_value"]) == (
            "4092000000", "edgar_xbrl", "confirmed", float(round(4_092e6 * 1.005)))
        assert repair.snapshot(_filing_row(new, filing)) == stored  # and rolled back with the rest


def _comparative_checked_against_a_later_proxy(db, monkeypatch, ticker="LTR", *, parsed):
    """Merck's FY2026 10-K gives FY2025 as ``parsed``, restating the FY2025 10-K's 18,254 million, and a proxy filed
    after it (P27) quotes FY2025 as first reported. A sync before the fix stored the proxies' rows, then the backfill
    cross-checked the FY2026 10-K's FY2025 comparative against the authority read then, P27's figure. No row holds the
    FY2025 10-K's own figure: the per-filing writer never read that 10-K, and no sync ran while it was the newest."""
    company = _company(db, ticker)
    payload = _for(company, _mrk_payload())
    _items(payload).extend([
        _item(parsed, "2025-12-31", start="2025-01-01", accn=_accn(company, "K26"), fy=2026, filed="2027-02-25"),
        _item(19_000e6, "2026-12-31", start="2026-01-01", accn=_accn(company, "K26"), fy=2026, filed="2027-02-25"),
        _item(18_254e6, "2025-12-31", start="2025-01-01", accn=_accn(company, "P27"), fy=2026, form="DEF 14A",
              filed="2027-04-08"),
    ])
    _old_sync(db, monkeypatch, company, payload)
    filing = _filing(db, company, "K26", "2026-12-31", "2027-02-25")
    with _before_the_fix(monkeypatch):
        svc.process_filing_facts(db, filing, authoritative=svc.extract_authoritative_values(payload), standardized={
            "net_income": {"series": [{"period": "2025-12-31", "period_start": "2025-01-01", "value": parsed,
                                       "fiscal_period": "FY", "fiscal_year": 2025}]}})
    return company, payload, filing


@pytest.mark.parametrize(("parsed", "number"), [(18_345_270_000.0, 5), (18_600e6, 4)], ids=["confirmed", "replaced"])
def test_a_history_row_holding_a_proxy_figure_backs_a_filing_row_as_any_report_row_does(monkeypatch, parsed, number):
    # One of the ways a sync since #1682 changes the step's plan (the docs' "A company synced since #1682" lists them:
    # this one, a refusal that disappears or changes its reason, and the adoption). The FY2025 10-K's own figure, which
    # the FY2026 10-K restated and P27 quotes, becomes a history row: a report row holding the figure the old cross-check took from P27, so set 5 leaves the
    # FY2026 10-K's confirmed comparative and the preview lists it (detection's rule and the step's, as for a demoted
    # winner a sync stored while the FY2025 10-K was the newest); without that row the step re-records the check. Set 4's
    # replaced comparative is backed alike, but today's 10-K figure confirms its recorded original, so set 4 restores
    # it as without the history row, and set 2, retiring P27's row current at the key, promotes it (review of #1840,
    # SF-B; detection leaves the backed row unlisted before the apply, and the restored row leaves set 4).
    with _synced_before_and_since_1682(
            monkeypatch, lambda db, monkeypatch: _comparative_checked_against_a_later_proxy(db, monkeypatch,
                                                                                           parsed=parsed)) as states:
        (old, company, payload, filing), (new, *_rest) = states[False], states[True]
        row = _filing_row(old, filing)
        check = _check(row)
        assert (check["outcome"], check["authoritative_value"], row.period_end) == (
            "confirmed" if number == 5 else "replaced", 18_254e6, date(2025, 12, 31))
        held = _by_identity(old, company)
        [history] = [state for identity, state in _by_identity(new, company).items() if identity not in held]
        assert (history["accession"], history["period_end"], float(history["value"])) == (
            _accn(company, "K25"), "2025-12-31", 18_254e6)
        assert _detection(old, {company.ticker: payload})[number] == [(company.ticker, row.id)]
        assert _detection(new, {company.ticker: payload})[number] == []
        stored = repair.snapshot(row)
        plan = _preview(old, company, payload)["proxy"]
        rewritten = "filing_rows_reconfirmed" if number == 5 else "filing_rows_restored"
        assert (plan[rewritten], plan["promoted"], plan["detection_listed"]) == (1, 1, [])
        if number == 4:
            since = _preview(new, company, payload)["proxy"]
            assert (since[rewritten], since["promoted"], since["detection_listed"], since["left_report_backed"]) == (
                1, 1, [], [])
            applied = _apply(new, company, payload)["proxy"]
            restored = _filing_row(new, filing)
            assert (applied["detection_listed"], restored.is_latest, restored.source, float(restored.value)) == (
                [], True, "edgar_xbrl", parsed)
            return
        since = _preview(new, company, payload)["proxy"]
        assert (since[rewritten], since["promoted"], since["detection_listed"]) == (0, 1, [])
        assert plan["left_report_backed"] == []
        [left] = since["left_report_backed"]
        assert (left["fact_id"], left["set"], left["figure"], [b["accession"] for b in left["backed_by"]]) == (
            row.id, 5, "18254000000", [_accn(company, "K25")])
        _apply(new, company, payload)
        assert repair.snapshot(_filing_row(new, filing)) == {**stored, "is_latest": True}  # promoted, its check as it was


CONTRADICTED = 17_000e6  # a parse of FY2025 the 10-K's 18,600 contradicts (8.6% off): SF-B restores nothing
SET4_OWN = "the 10-K's figure disagrees with the recorded original value by more than 1%, and the filing row holds neither"


def _replaced_behind_the_proxy_row(db, monkeypatch, ticker="LRC", parsed=CONTRADICTED):
    """A sync before the fix stored the proxies' rows, P27's current at FY2025; the backfill before the fix replaced the
    FY2026 10-K's parse of FY2025 (``parsed``) with P27's figure, and the filing row, at the year's 10-K winner's
    identity, sits behind P27's row."""
    company = _company(db, ticker)
    payload, filing = _restated_and_quoted_as_first_reported(db, monkeypatch, company, old_sync=True, parsed=parsed)
    return company, payload, filing


def test_a_backed_row_behind_a_current_proxy_row_whose_original_the_10k_contradicts_is_refused_by_set_2(monkeypatch):
    # The FY2026 10-K's comparative, parsed 17,000 (the 10-K's own figure is 18,600) and replaced with P27's 18,254,
    # holds the year's 10-K winner's identity behind P27's current row. Since #1682 the FY2025 10-K's history row backs
    # 18,254, so set 4 leaves the row (its original is contradicted too); set 2, retiring P27's row, would promote it at
    # the winner's identity, and its agreement test refuses the company on value, naming the row: promoted, the
    # proxy's figure would be the company's current figure (principal review 5718798403, item 1). Synced as before,
    # set 4's own test refuses the original first, and set 2 refuses the same row. (Review of #1840, round 8: the
    # restore of LTR's replaced row removed the only test of set 2's agreement test on a row the old check replaced.)
    with _synced_before_and_since_1682(monkeypatch, _replaced_behind_the_proxy_row) as states:
        (old, company, payload, _filing), (new, *_rest) = states[False], states[True]
        [row] = [r for r in _rows(new, company, concept="net_income", period_end=date(2025, 12, 31)) if r.filing_id]
        [p27] = [r for r in _rows(new, company, is_latest=True) if r.accession == _accn(company, "P27")]
        assert (row.is_latest, row.source, float(row.value), _check(row)["original_value"], p27.form) == (
            False, "companyfacts", 18_254e6, CONTRADICTED, "DEF 14A")
        disagrees = f"the filing row holding the 10-K's identity (fact {row.id}) disagrees with the 10-K on: value"
        _refuses(new, company, payload, _refusal(new, (p27.id, disagrees)))
        _refuses(old, company, payload, _refusal(old, (row.id, SET4_OWN), (p27.id, disagrees)))


def _fetched_after_the_sync(states, payload):
    """``states`` with the repair's payload fetched after their last sync: ``payload(company, synced)``."""
    return {since: (db, company, payload(company, synced), *rest) for since, (db, company, synced, *rest) in states.items()}


def _with_an_amendment(company, payload):
    """A 10-K/A filed after the sync restates FY2023 (380 million): the year's winner, at an identity no row holds."""
    amended = copy.deepcopy(payload)
    _items(amended).append(_item(380e6, "2023-12-31", start="2023-01-01", accn=_accn(company, "KA23"), fy=2023,
                                 form="10-K/A", filed="2026-06-01"))
    return amended


def test_a_winner_filed_after_a_sync_since_1682_is_inserted_beside_the_history_rows(monkeypatch):
    # BBB's proxy rows stay current over its demoted 10-K rows through any sync. Synced since #1682, it also holds the
    # restated years' own-report rows; a 10-K/A filed after that sync gives FY2023 a winner at an identity no row
    # holds. The step inserts it, and plans, writes, journals and rolls back as with no history rows.
    _with_payloads(monkeypatch, _restating)
    with _synced_before_and_since_1682(monkeypatch, _demoted) as states:
        states = _fetched_after_the_sync(states, _with_an_amendment)
        _history, applied = _the_step_reads_history_rows_as_nothing(states)
        company = states[True][1]
        [fy2023] = [row for row in applied["proxy"]["rows"] if (row["fiscal_period"], row["period_end"]) == (
            "FY", "2023-12-31")]
        assert (fy2023["action"], fy2023["winner_accession"], fy2023["winner_value"]) == (
            "inserted", _accn(company, "KA23"), "380000000")


def _with_fy2023_withdrawn_from_later_reports(company, payload):
    """FY2023's items from the later 10-Ks gone from companyfacts, so the year's winner is its own 10-K's item, at the
    identity of the history row a sync since #1682 stored for it."""
    withdrawn = copy.deepcopy(payload)
    _items(withdrawn)[:] = [item for item in _items(withdrawn) if not (
        item["form"] == "10-K" and item["end"] == "2023-12-31" and item["fy"] > 2023)]
    return withdrawn


def test_a_winner_at_a_history_rows_identity_is_adopted_journaled_and_rolled_back_exactly(monkeypatch):
    # The one way a fresh winner lands on a history row's identity: the later reports' items for its year are gone
    # from the payload. Synced as before #1682, no row holds that identity and the step inserts the winner; synced
    # since, the history row holds it, and the step promotes it in place, as it promotes a demoted winner. Both end
    # with the same current row; the journal holds the history row's prior state, and the rollback restores it.
    _with_payloads(monkeypatch, _restating)
    with _synced_before_and_since_1682(monkeypatch, _demoted) as states:
        states = _fetched_after_the_sync(states, _with_fy2023_withdrawn_from_later_reports)
        (old, company, payload), (new, _company, _payload) = states[False][:3], states[True][:3]
        identity = ("net_income", "2023-12-31", "FY", "USD", _accn(company, "K23"))
        [history_id] = [row.id for row in _rows(new, company) if repair._identity(repair.snapshot(row)) == identity]
        history = repair.snapshot(new.get(FinancialFact, history_id))
        assert not history["is_latest"] and identity not in _by_identity(old, company)

        def fy2023(plan):
            return [(row["action"], row["winner_accession"]) for row in plan["proxy"]["rows"]
                    if (row["fiscal_period"], row["period_end"]) == ("FY", "2023-12-31")]

        assert fy2023(_preview(old, company, payload)) == [("inserted", identity[4])]
        assert fy2023(_preview(new, company, payload)) == [("promoted", identity[4])]
        _apply(old, company, payload, run_id="since")
        _apply(new, company, payload, run_id="since")
        assert _by_identity(new, company)[identity] == _by_identity(old, company)[identity] == {
            **history, "is_latest": True}
        assert _journal(new)[(identity, "apply")] == ("proxy-repair-v1", history, {**history, "is_latest": True})
        for db in (old, new):
            repair.rollback_company(db, company.id, "since", dry_run=False, run_id="rollback")
            db.commit()
        assert repair.snapshot(new.get(FinancialFact, history_id)) == history
        rolled = _by_identity(old, company)[identity]
        assert not rolled["is_latest"] and rolled["provenance"]["reasons"] == ["repair_rolled_back"]



def _restated_and_quoted_as_first_reported(db, monkeypatch, company, *, old_sync, own_fy2025=18_254e6,
                                           quoted=18_254e6, parsed=18_600e6, start="2025-01-01", fiscal_year=2025):
    """Merck's payload, the FY2026 10-K restating FY2025 (18,600 million against the FY2025 10-K's own 18,254) and
    P27, a proxy filed after it, quoting FY2025 as first reported. The backfill before #1622 read P27's figure as the
    authority and replaced the FY2026 10-K's parse of its FY2025 comparative with it. ``old_sync``: a sync before the
    fix also stored the proxies' rows, P27's current at FY2025; otherwise no sync before the fix read the proxies, and
    P27's figure is a payload witness alone (MMM's shape). ``own_fy2025``: the FY2025 10-K's own figure; ``quoted``:
    P27's; ``parsed``, ``start`` and ``fiscal_year``: the per-filing writer's read of the FY2026 10-K's FY2025."""
    payload = _for(company, _mrk_payload())
    for item in _items(payload):
        if item["form"] == "10-K" and (item["end"], item["fy"]) == ("2025-12-31", 2025):
            item["val"] = own_fy2025
    _items(payload).extend([
        _item(18_600e6, "2025-12-31", start="2025-01-01", accn=_accn(company, "K26"), fy=2026, filed="2027-02-25"),
        _item(19_000e6, "2026-12-31", start="2026-01-01", accn=_accn(company, "K26"), fy=2026, filed="2027-02-25"),
        _item(quoted, "2025-12-31", start="2025-01-01", accn=_accn(company, "P27"), fy=2026, form="DEF 14A",
              filed="2027-04-08"),
    ])
    if old_sync:
        _old_sync(db, monkeypatch, company, payload)
    filing = _filing(db, company, "K26", "2026-12-31", "2027-02-25")
    with _before_the_fix(monkeypatch):
        svc.process_filing_facts(db, filing, authoritative=svc.extract_authoritative_values(payload), standardized={
            "net_income": {"series": [
                {"period": "2025-12-31", "period_start": start, "value": parsed, "fiscal_period": "FY",
                 "fiscal_year": fiscal_year},
                {"period": "2026-12-31", "period_start": "2026-01-01", "value": 19_000e6, "fiscal_period": "FY",
                 "fiscal_year": 2026}]}})
    return payload, filing


def _replaced_at_the_winners_identity(db, monkeypatch, ticker="NSB", parsed=18_600e6):
    """No sync before the fix: the FY2026 10-K's replaced FY2025 comparative is the only row at FY2025 and current,
    at the identity of the year's 10-K winner (the FY2026 10-K's), which a fixed sync then skipped. ``parsed``: the
    per-filing writer's read of that comparative, the recorded original (the 10-K's own 18,600 unless given)."""
    company = _company(db, ticker)
    payload, filing = _restated_and_quoted_as_first_reported(db, monkeypatch, company, old_sync=False, parsed=parsed)
    _sync(db, monkeypatch, company, payload)
    return company, payload, filing



def _replaced_below_a_later_winner(db, monkeypatch, ticker="LTX", fy2025=18_600e6):
    """A sync before the fix stored the proxies' rows, and a later 10-K (K27) gives FY2025 as ``fy2025`` (as the FY2026
    10-K did, unless given): the year's winner is K27's, which the harness's sync makes current, so the FY2026 10-K's
    replaced comparative is neither current nor at the winner's identity."""
    company = _company(db, ticker)
    payload, filing = _restated_and_quoted_as_first_reported(db, monkeypatch, company, old_sync=True)
    _items(payload).extend(_item(value, f"{year}-12-31", start=f"{year}-01-01", accn=_accn(company, "K27"), fy=2027,
                                 filed="2028-02-25")
                           for year, value in ((2025, fy2025), (2026, 19_000e6), (2027, 20_000e6)))
    return company, payload, filing


def test_a_current_row_a_history_row_backs_is_restored_where_the_10k_confirms_its_original(monkeypatch):
    # The FY2025 10-K's own figure, as first reported, becomes a history row that holds the figure the old cross-check
    # took from P27, on FY2025's current row, at the 10-K winner's identity, 1.9% off the winner. The history row says
    # nothing of the FY2026 10-K's own parse, which today's 10-K figure confirms: set 4 restores the row to its recorded
    # original through today's cross-check, as it does synced as before #1682, with no history row (review of #1840,
    # SF-B). Where the 10-K contradicts the original too, the company is refused (LXC, below).
    with _synced_before_and_since_1682(monkeypatch, _replaced_at_the_winners_identity) as states:
        for db, company, payload, _filing in states.values():
            [row] = [r for r in _rows(db, company, concept="net_income", period_end=date(2025, 12, 31)) if r.filing_id]
            assert (row.is_latest, row.source, float(row.value), _check(row)["original_value"]) == (
                True, "companyfacts", 18_254e6, 18_600e6)
            assert not [r for r in _rows(db, company) if r.form == "DEF 14A"]  # P27's figure is a payload witness alone
            plan = _preview(db, company, payload)["proxy"]
            assert (plan["filing_rows_restored"], plan["left_report_backed"]) == (1, [])
            _apply(db, company, payload)
            restored = db.get(FinancialFact, row.id)
            assert (restored.is_latest, restored.source, float(restored.value)) == (True, "edgar_xbrl", 18_600e6)
        assert [float(r.value) for r in _rows(states[True][0], states[True][1], concept="net_income",
                                              period_end=date(2025, 12, 31), filing_id=None)] == [18_254e6]


def test_a_current_backed_row_at_the_winners_identity_whose_original_the_10k_contradicts_is_refused(monkeypatch):
    # NSB's shape with the recorded original contradicted too (parse 17,000 against the 10-K's 18,600): the row is
    # FY2025's current row at the year's 10-K winner's identity. Synced as before #1682 set 4's own test refuses the
    # original; since, the FY2025 10-K's history row backs the proxy's 18,254, so set 4 leaves the row, and left, the
    # company's figure would stay the proxy's, 1.9% off the 10-K, at the winner's identity: the current-figure refusal.
    # (Review of #1840, round 8: NSB's restore removed the only test of the refusal at the winner's identity.)
    with _synced_before_and_since_1682(monkeypatch, lambda db, monkeypatch: _replaced_at_the_winners_identity(
            db, monkeypatch, "NSC", parsed=CONTRADICTED)) as states:
        (old, company, payload, _filing), (new, *_rest) = states[False], states[True]
        [row] = [r for r in _rows(new, company, concept="net_income", period_end=date(2025, 12, 31)) if r.filing_id]
        assert (row.is_latest, row.accession, float(row.value), _check(row)["original_value"]) == (
            True, _accn(company, "K26"), 18_254e6, CONTRADICTED)
        assert [(r.accession, float(r.value)) for r in _rows(new, company, concept="net_income",
                                                             period_end=date(2025, 12, 31), filing_id=None)] == [
            (_accn(company, "K25"), 18_254e6)]
        _refuses(new, company, payload, _refusal(new, (row.id, _current_figure("18254000000", "18600000000"))))
        _refuses(old, company, payload, _refusal(old, (row.id, SET4_OWN)))


def _replaced_at_the_winners_identity_with_no_record(db, monkeypatch, ticker="NSN"):
    """NSB's shape, its FY2025 comparative replaced before #1191, which recorded no check: no original to read."""
    company, payload, filing = _replaced_at_the_winners_identity(db, monkeypatch, ticker)
    [row] = [r for r in _rows(db, company, concept="net_income", period_end=date(2025, 12, 31)) if r.filing_id]
    row.provenance = None
    db.commit()
    return company, payload, filing


def test_a_current_backed_row_at_the_winners_identity_with_no_recorded_original_is_refused(monkeypatch):
    # NSB's shape with no recorded original (a replacement before #1191). Synced as before #1682, set 4 refuses a row
    # holding a proxy's figure with no original. Since, the FY2025 10-K's history row backs the proxy's 18,254, SF-B has
    # no original to read, so set 4 leaves the row, and left, the company's current figure would stay the proxy's, 1.9%
    # off the 10-K: the current-figure refusal (the refusal table's "or the row records none"; review of #1840, round 8).
    with _synced_before_and_since_1682(monkeypatch, _replaced_at_the_winners_identity_with_no_record) as states:
        (old, company, payload, _filing), (new, *_rest) = states[False], states[True]
        [row] = [r for r in _rows(new, company, concept="net_income", period_end=date(2025, 12, 31)) if r.filing_id]
        assert (row.is_latest, row.source, float(row.value), row.provenance) == (True, "companyfacts", 18_254e6, None)
        _refuses(new, company, payload, _refusal(new, (row.id, _current_figure("18254000000", "18600000000"))))
        _refuses(old, company, payload, _refusal(old, (row.id, "a filing row holds a proxy's figure, not the 10-K's, "
                                                               "and records no original value")))


def test_a_row_below_a_later_winner_a_history_row_backs_is_restored_where_the_10k_confirms_its_original(monkeypatch):
    # The FY2026 10-K's comparative holds a figure a report row holds (since #1682, the FY2025 10-K's own figure as first
    # reported) and is not the company's current figure (K27's winner is). Today's 10-K figure, K27's 18,600, confirms
    # its recorded original, so set 4 restores it, as with no history row, and its filing's chart shows the filing's
    # own figure, not the proxy's (review of #1840, SF-B). A row the 10-K contradicts in its original too stays left and
    # listed (principal review 5718798403, item 3, below).
    with _synced_before_and_since_1682(monkeypatch, _replaced_below_a_later_winner) as states:
        for db, company, payload, filing in states.values():
            [row] = [r for r in _rows(db, company, concept="net_income", period_end=date(2025, 12, 31)) if r.filing_id]
            assert (row.source, float(row.value), _check(row)["original_value"]) == ("companyfacts", 18_254e6, 18_600e6)
            plan = _preview(db, company, payload)["proxy"]
            assert (plan["filing_rows_restored"], plan["left_report_backed"]) == (1, [])
            applied = _apply(db, company, payload)["proxy"]
            assert applied["detection_listed"] == []
            restored = db.get(FinancialFact, row.id)
            assert (restored.is_latest, restored.source, float(restored.value)) == (False, "edgar_xbrl", 18_600e6)
            chart = {p["period_end"]: p["value"] for c in svc.get_filing_fundamentals(db, filing.id)["concepts"]
                     if c["concept"] == "net_income" for p in c["points"]}
            assert chart["2025-12-31"] == 18_600e6
        [history] = [r for r in _rows(states[True][0], states[True][1], concept="net_income",
                                      period_end=date(2025, 12, 31)) if r.accession == _accn(states[True][1], "K25")]
        assert (history.is_latest, history.filing_id, float(history.value)) == (False, None, 18_254e6)


def test_a_row_below_a_later_winner_whose_original_the_10k_contradicts_is_listed_and_detection_leaves_it(monkeypatch):
    # LTX's shape with K27 restating FY2025 again (18,900), so today's 10-K figure contradicts the recorded original
    # (18,600) too and SF-B restores nothing. A sync before the fix stored the proxies' rows, so P27's stored row
    # witnesses the filing row's 18,254 for detection's set 4. Since #1682 the FY2025 10-K's history row holds that
    # figure: set 4 leaves the row (not the company's current figure: K27's is) and lists it with that backer, and
    # detection, by the same report-row rule, leaves it unlisted, before the apply and after; here the backer alone
    # decides it. Synced as before #1682, no report row backs it, and set 4's own test refuses the original. (Review of
    # #1840, rounds 8 and 9: the pin LTX's listing test held, where a stored proxy row makes the backer decide.)
    with _synced_before_and_since_1682(monkeypatch, lambda db, monkeypatch: _replaced_below_a_later_winner(
            db, monkeypatch, "LTC", fy2025=RESTATED_AGAIN)) as states:
        (old, company, payload, _filing), (new, *_rest) = states[False], states[True]
        [row] = [r for r in _rows(new, company, concept="net_income", period_end=date(2025, 12, 31)) if r.filing_id]
        assert (row.is_latest, row.source, float(row.value), _check(row)["original_value"]) == (
            False, "companyfacts", 18_254e6, 18_600e6)
        [p27] = [r for r in _rows(new, company, concept="net_income", period_end=date(2025, 12, 31))
                 if r.accession == _accn(company, "P27")]
        [history] = [r for r in _rows(new, company, concept="net_income", period_end=date(2025, 12, 31))
                     if r.accession == _accn(company, "K25")]
        assert (p27.form, history.is_latest, history.filing_id, float(history.value)) == ("DEF 14A", False, None, 18_254e6)
        stored = repair.snapshot(row)
        since = _preview(new, company, payload)["proxy"]
        assert [(e["fact_id"], e["set"], e["authority"], [b["fact_id"] for b in e["backed_by"]])
                for e in since["left_report_backed"]] == [(row.id, 4, RESTATED_AGAIN, [history.id])]
        applied = _apply(new, company, payload)["proxy"]
        assert (since["detection_listed"], applied["detection_listed"]) == ([], [])  # the backer decides it
        found = _detection(new, {company.ticker: payload})
        assert (found[4], found[5]) == ([], [])
        assert repair.snapshot(new.get(FinancialFact, row.id)) == stored
        assert row.id not in {r.fact_id for r in new.query(FinancialFactRevision)}
        _refuses(old, company, payload, _refusal(old, (row.id, SET4_OWN)))


def _replaced_where_the_own_report_gave_another_figure(db, monkeypatch, ticker="UNB"):
    """The restated-and-quoted shape with the FY2025 10-K's own figure 18,100 million: its history row holds another
    figure than the proxies' 18,254."""
    company = _company(db, ticker)
    payload, filing = _restated_and_quoted_as_first_reported(db, monkeypatch, company, old_sync=True,
                                                             own_fy2025=18_100e6)
    return company, payload, filing


RESTATED_FY2023 = 366_825_000.0  # the FY2025 10-K's FY2023, 0.5% above the FY2023 10-K's own 365 million


def _kept_at_a_restated_year(db, monkeypatch, ticker="UNL"):
    """The FY2025 10-K restates FY2023 and P26 quotes the restated figure. Its FY2023 comparative, parsed 1,000 times
    too large, the old cross-check replaced with P26's figure, today's authority too: set 4 lists it, and the step
    keeps it. The FY2023 10-K's own 365 million becomes a history row holding another figure."""
    company = _company(db, ticker)
    payload = _for(company, _mrk_payload())
    for item in _items(payload):
        if item["end"] == "2023-12-31" and item["accn"] in (_accn(company, "K25"), _accn(company, "P26")):
            item["val"] = RESTATED_FY2023
    _old_sync(db, monkeypatch, company, payload)
    filing = _filing(db, company, "K25", "2025-12-31", "2026-02-25")
    with _before_the_fix(monkeypatch):
        svc.process_filing_facts(db, filing, authoritative=svc.extract_authoritative_values(payload), standardized={
            "net_income": {"series": [{"period": "2023-12-31", "period_start": "2023-01-01", "value": RESTATED_FY2023 * 1e3,
                                       "fiscal_period": "FY", "fiscal_year": 2023}]}})
    return company, payload, filing


@pytest.mark.parametrize("shape", ["restored", "kept_and_listed"])
def test_a_history_row_holding_another_figure_backs_nothing(monkeypatch, shape):
    # A history row backs a filing row only where it holds that row's figure (sets 4 and 5's report-row rule, value
    # within 1e-6). At a restated year it holds the year's figure as first reported, so where the proxy quotes another
    # figure, the step restores the row, or keeps and names it, as it does with no history row.
    build = _replaced_where_the_own_report_gave_another_figure if shape == "restored" else _kept_at_a_restated_year
    with _synced_before_and_since_1682(monkeypatch, build) as states:
        old, company, new = states[False][0], states[False][1], states[True][0]
        end = date(2025, 12, 31) if shape == "restored" else date(2023, 12, 31)
        [row] = [r for r in _rows(old, company, concept="net_income", period_end=end) if r.filing_id]
        assert (row.source, float(row.value)) == ("companyfacts", 18_254e6 if shape == "restored" else RESTATED_FY2023)
        held = _by_identity(old, company)
        assert [(s["accession"], float(s["value"])) for i, s in _by_identity(new, company).items() if i not in held
                and (s["concept"], s["period_end"]) == ("net_income", end.isoformat())] == [
            (_accn(company, "K25" if shape == "restored" else "K23"), 18_100e6 if shape == "restored" else 365e6)]
        _history, applied = _the_step_reads_history_rows_as_nothing(states)
        assert applied["proxy"]["left_report_backed"] == []
        if shape == "restored":
            assert applied["proxy"]["filing_rows_restored"] == 1
        else:
            assert applied["proxy"]["detection_listed"] == [
                {"fact_id": row.id, "set": 4, "verdict": "kept_agrees_with_authority"}]


def _with_k27(company, payload, fy2025=18_600e6):
    """``payload`` plus the FY2027 10-K (K27), which gives FY2025 as ``fy2025`` (the FY2026 10-K's figure unless given)
    and FY2026 as the FY2026 10-K did: FY2025's winner."""
    later = copy.deepcopy(payload)
    _items(later).extend(_item(value, f"{year}-12-31", start=f"{year}-01-01", accn=_accn(company, "K27"), fy=2027,
                               filed="2028-02-25")
                         for year, value in ((2025, fy2025), (2026, 19_000e6), (2027, 20_000e6)))
    return later


RESTATED_AGAIN = 18_900e6  # K27's FY2025 where it restates the year again: 1.6% off the FY2026 10-K's 18,600


def _current_over_a_later_winner(db, monkeypatch, ticker="LXC"):
    """NSB's shape, then K27, restating FY2025 again (``RESTATED_AGAIN``): a fixed sync stores K27's FY2025 winner behind
    the FY2026 10-K's row, current at its own identity, since the upsert keeps a row with a local Filing over one
    without (K27 has none here)."""
    company = _company(db, ticker)
    payload, filing = _restated_and_quoted_as_first_reported(db, monkeypatch, company, old_sync=False)
    payload = _with_k27(company, payload, RESTATED_AGAIN)
    _sync(db, monkeypatch, company, payload)
    return company, payload, filing


@pytest.mark.parametrize("winner", ["stored_behind", "fetched_after_the_sync"])
def test_a_current_row_left_at_a_proxy_figure_below_a_later_winner_refuses_the_company(monkeypatch, winner):
    # The refusal reads the company's current figure, not the winner's identity: the FY2026 10-K's replaced comparative
    # is FY2025's current row at its own identity, while K27 gives the year's winner, stored non-current behind it or
    # only in a payload fetched after the last sync. K27 restates FY2025 again, 18,900 million, so today's 10-K figure
    # contradicts the recorded original (18,600) too. Synced as before #1682, set 4's own test refuses the original;
    # since, the FY2025 10-K's history row backs the proxy's figure, and left, the company's figure would stay the
    # proxy's, 3.4% off the 10-K: the current-figure refusal.
    build = _current_over_a_later_winner if winner == "stored_behind" else _replaced_at_the_winners_identity
    with _synced_before_and_since_1682(monkeypatch, build) as states:
        if winner == "fetched_after_the_sync":
            states = _fetched_after_the_sync(states, lambda company, payload: _with_k27(company, payload, RESTATED_AGAIN))
        (old, company, payload), new = states[False][:3], states[True][0]
        [row] = [r for r in _rows(new, company, concept="net_income", period_end=date(2025, 12, 31)) if r.filing_id]
        assert (row.is_latest, row.accession, float(row.value)) == (True, _accn(company, "K26"), 18_254e6)
        assert [(r.accession, r.is_latest) for r in _rows(new, company, concept="net_income",
                                                          period_end=date(2025, 12, 31), filing_id=None)] == (
            [(_accn(company, "K27"), False), (_accn(company, "K25"), False)] if winner == "stored_behind"
            else [(_accn(company, "K25"), False)])
        _refuses(old, company, payload, _refusal(old, (row.id, "the 10-K's figure disagrees with the recorded original "
                                                               "value by more than 1%, and the filing row holds neither")))
        _refuses(new, company, payload, _refusal(new, (row.id, _current_figure("18254000000", "18900000000"))))


def _set5_current(db, monkeypatch, ticker="S5R"):
    """NSB's shape in set 5: the FY2026 10-K's parse of FY2025, 18,300 million, was confirmed against P27's 18,254
    (within 1%), and is FY2025's current row, 1.6% off the 10-K's 18,600."""
    company = _company(db, ticker)
    payload, filing = _restated_and_quoted_as_first_reported(db, monkeypatch, company, old_sync=False,
                                                             parsed=18_300e6)
    _sync(db, monkeypatch, company, payload)
    return company, payload, filing


def test_a_set5_row_left_as_the_companys_current_figure_refuses_the_company(monkeypatch):
    # Set 5 alike: synced as before #1682, set 5's own check refuses the row the 10-K contradicts; since, the history
    # row backs the figure it was confirmed against, and the refusal of a row left so refuses it instead. The company
    # stays refused, its reason changed.
    with _synced_before_and_since_1682(monkeypatch, _set5_current) as states:
        (old, company, payload), new = states[False][:3], states[True][0]
        [row] = [r for r in _rows(new, company, concept="net_income", period_end=date(2025, 12, 31)) if r.filing_id]
        assert (row.is_latest, row.source, _check(row)["outcome"], _check(row)["authoritative_value"]) == (
            True, "edgar_xbrl", "confirmed", 18_254e6)
        _refuses(old, company, payload, _refusal(old, (row.id, "the old cross-check confirmed this filing row against "
                                                               "a proxy's figure, and the 10-K's figure disagrees with it "
                                                               "by more than 1%")))
        _refuses(new, company, payload, _refusal(new, (row.id, _current_figure("18300000000", "18600000000"))))


def _behind_a_stale_own_report(db, monkeypatch, ticker="DWB", parsed=18_600e6):
    """A fixed sync while the FY2025 10-K was the newest stored its FY2025 row (18,254), current. The FY2026 10-K
    restates FY2025 (18,600) and P27 quotes 18,254. The backfill before the fix replaced the FY2026 10-K's FY2025
    comparative with P27's figure (a payload witness), and stored it behind the FY2025 10-K's current row (no local
    Filing for it); a fixed sync then skips the winner's identity, which the filing row holds. ``parsed``: the per-filing
    writer's read of that comparative (the 10-K's own 18,600 unless given)."""
    company = _company(db, ticker)
    payload = _for(company, _mrk_payload())
    _items(payload).extend([
        _item(18_600e6, "2025-12-31", start="2025-01-01", accn=_accn(company, "K26"), fy=2026, filed="2027-02-25"),
        _item(19_000e6, "2026-12-31", start="2026-01-01", accn=_accn(company, "K26"), fy=2026, filed="2027-02-25"),
        _item(18_254e6, "2025-12-31", start="2025-01-01", accn=_accn(company, "P27"), fy=2026, form="DEF 14A",
              filed="2027-04-08"),
    ])
    early = copy.deepcopy(payload)
    _items(early)[:] = [item for item in _items(early) if item["accn"] not in (_accn(company, "K26"),
                                                                                _accn(company, "P27"))]
    _sync(db, monkeypatch, company, early)
    filing = _filing(db, company, "K26", "2026-12-31", "2027-02-25")
    with _before_the_fix(monkeypatch):
        svc.process_filing_facts(db, filing, authoritative=svc.extract_authoritative_values(payload), standardized={
            "net_income": {"series": [{"period": "2025-12-31", "period_start": "2025-01-01", "value": parsed,
                                       "fiscal_period": "FY", "fiscal_year": 2025}]}})
    _sync(db, monkeypatch, company, payload)
    return company, payload, filing


def test_a_backed_row_not_current_whose_original_the_10k_confirms_is_restored_beside_a_stale_row(monkeypatch):
    # Here the FY2026 10-K's replaced comparative holds the 10-K winner's identity but is not current: the FY2025 10-K's
    # stale row, which a fixed sync stored while it was the newest and which backs the proxy's figure, is. Today's 10-K
    # figure confirms the comparative's recorded original, so set 4 restores it in both states (review of #1840, SF-B);
    # the stale row is no proxy's and stays as it is, and nothing is refused or listed.
    with _synced_before_and_since_1682(monkeypatch, _behind_a_stale_own_report) as states:
        for db, company, payload, filing in states.values():
            row = _filing_row(db, filing)
            assert (row.is_latest, row.source, float(row.value)) == (False, "companyfacts", 18_254e6)
            [backer] = [r for r in _rows(db, company, concept="net_income", period_end=date(2025, 12, 31),
                                         fiscal_period="FY", filing_id=None) if r.accession == _accn(company, "K25")]
            assert backer.is_latest and float(backer.value) == 18_254e6
            stale = repair.snapshot(backer)
            applied = _apply(db, company, payload)["proxy"]
            assert (applied["filing_rows_restored"], applied["left_report_backed"]) == (1, [])
            restored = _filing_row(db, filing)
            assert (restored.is_latest, restored.source, float(restored.value)) == (False, "edgar_xbrl", 18_600e6)
            assert repair.snapshot(db.get(FinancialFact, backer.id)) == stale


def test_a_backed_row_not_current_at_the_winners_identity_whose_original_the_10k_contradicts_is_listed(monkeypatch):
    # DWB's shape with the recorded original contradicted too (parse 17,000 against the 10-K's 18,600): the FY2026
    # 10-K's comparative holds the year's 10-K winner's identity, but the FY2025 10-K's stale row, which backs its
    # figure, is current. The current-figure refusal reads the company's current figure only, not the winner's
    # identity, so in both states set 4 leaves the row and lists it, and refuses nothing. (Review of #1840, round 8:
    # DWB's restore removed the only test of a non-current left row at the winner's identity.)
    with _synced_before_and_since_1682(monkeypatch, lambda db, monkeypatch: _behind_a_stale_own_report(
            db, monkeypatch, "DWC", parsed=CONTRADICTED)) as states:
        for db, company, payload, filing in states.values():
            row = _filing_row(db, filing)
            assert (row.is_latest, row.accession, float(row.value), _check(row)["original_value"]) == (
                False, _accn(company, "K26"), 18_254e6, CONTRADICTED)
            [backer] = [r for r in _rows(db, company, concept="net_income", period_end=date(2025, 12, 31),
                                         fiscal_period="FY", filing_id=None) if r.accession == _accn(company, "K25")]
            assert backer.is_latest
            stored = repair.snapshot(row)
            applied = _apply(db, company, payload)["proxy"]
            assert (applied["filing_rows_restored"], applied["detection_listed"]) == (0, [])
            assert [(e["fact_id"], e["set"], e["authority"], [b["fact_id"] for b in e["backed_by"]])
                    for e in applied["left_report_backed"]] == [(row.id, 4, 18_600e6, [backer.id])]
            assert repair.snapshot(_filing_row(db, filing)) == stored


@pytest.mark.parametrize(("start", "fiscal_year", "parsed"), [
    ("2025-01-01", 2025, 17_000e6), ("2025-01-02", 2025, 17_000e6), ("2025-01-01", 2024, 17_000e6),
    ("2025-01-01", 2025, 18_770e6),
], ids=["labels-agree", "start-differs", "fiscal-year-differs", "original-agrees"])
def test_a_current_left_row_within_1pct_of_the_10k_is_left_whatever_its_labels(monkeypatch, start, fiscal_year, parsed):
    # P27 quotes FY2025 as the FY2025 10-K first reported it, 18,560 million, 0.2% under the 10-K's 18,600: the FY2026
    # 10-K's comparative, parsed 17,000 and replaced with P27's figure, is FY2025's current row. Since #1682 the history
    # row backs it. The current-figure refusal reads the value alone, which the old cross-check changed, never a start
    # or fiscal year, so the row is left and listed whatever its labels. Where the parse was 18,770, 0.9% off the 10-K's
    # figure (and 1.1% off P27's, which replaced it), the row is left and listed too: set 4 restores a backed row whose original the 10-K confirms only where its value is
    # more than 1% off the 10-K's figure (review of #1840, SF-B), and this one is within 1%, a figure the cross-check
    # would itself confirm. Synced as before #1682, no report row backs it, and set 4 restores it.
    def build(db, monkeypatch):
        company = _company(db, "AGR")
        payload, filing = _restated_and_quoted_as_first_reported(
            db, monkeypatch, company, old_sync=False, own_fy2025=18_560e6, quoted=18_560e6, parsed=parsed,
            start=start, fiscal_year=fiscal_year)
        _sync(db, monkeypatch, company, payload)
        return company, payload, filing

    with _synced_before_and_since_1682(monkeypatch, build) as states:
        (old, company, payload), new = states[False][:3], states[True][0]
        [row] = [r for r in _rows(new, company, concept="net_income", period_end=date(2025, 12, 31)) if r.filing_id]
        assert (row.is_latest, float(row.value), row.period_start.isoformat(), row.fiscal_year) == (
            True, 18_560e6, start, fiscal_year)
        assert _check(row)["original_value"] == parsed
        if parsed == 17_000e6:
            # Before #1682 set 4's own check refuses it: its recorded original, 17,000, is 8.6% off the 10-K's figure.
            # Since, the history row backs it, and the refusal disappears (docs, "A refusal can disappear").
            _refuses(old, company, payload, _refusal(old, (row.id, "the 10-K's figure disagrees with the recorded "
                                                                   "original value by more than 1%, and the filing row "
                                                                   "holds neither")))
        else:
            assert _preview(old, company, payload)["proxy"]["filing_rows_restored"] == 1
        plan = _preview(new, company, payload)["proxy"]
        assert plan["filing_rows_restored"] == 0
        assert [(e["fact_id"], e["set"], e["authority"]) for e in plan["left_report_backed"]] == [
            (row.id, 4, 18_600e6)]


def _labelled_apart(db, monkeypatch, ticker, *, backed, start, fiscal_year):
    """The FY2026 10-K repeats FY2025 unchanged (18,254 million), P27 quotes it exactly, and the backfill before the fix
    confirmed the FY2026 10-K's parse of its FY2025 comparative against P27's figure (set 5), the per-filing writer
    naming its start and fiscal year ``start`` and ``fiscal_year``. K27 repeats FY2025 unchanged; ``backed``: a fixed
    sync stored K27's row (behind the filing row, K27 having no local Filing), a report row holding the figure."""
    company = _company(db, ticker)
    payload = _for(company, _mrk_payload())
    _items(payload).extend([
        _item(18_254e6, "2025-12-31", start="2025-01-01", accn=_accn(company, "K26"), fy=2026, filed="2027-02-25"),
        _item(19_000e6, "2026-12-31", start="2026-01-01", accn=_accn(company, "K26"), fy=2026, filed="2027-02-25"),
        _item(18_254e6, "2025-12-31", start="2025-01-01", accn=_accn(company, "P27"), fy=2026, form="DEF 14A",
              filed="2027-04-08"),
    ])
    filing = _filing(db, company, "K26", "2026-12-31", "2027-02-25")
    with _before_the_fix(monkeypatch):
        svc.process_filing_facts(db, filing, authoritative=svc.extract_authoritative_values(payload), standardized={
            "net_income": {"series": [{"period": "2025-12-31", "period_start": start, "value": 18_254e6,
                                       "fiscal_period": "FY", "fiscal_year": fiscal_year}]}})
    _items(payload).extend(_item(value, f"{year}-12-31", start=f"{year}-01-01", accn=_accn(company, "K27"), fy=2027,
                                 filed="2028-02-25") for year, value in ((2025, 18_254e6), (2026, 19_000e6),
                                                                         (2027, 20_000e6)))
    synced = copy.deepcopy(payload)
    if not backed:
        _items(synced)[:] = [item for item in _items(synced) if item["accn"] != _accn(company, "K27")]
    _sync(db, monkeypatch, company, synced)
    return company, payload, filing


@pytest.mark.parametrize(("start", "fiscal_year"), [("2025-01-02", 2025), ("2025-01-01", 2024)],
                         ids=["start-differs", "fiscal-year-differs"])
def test_a_row_holding_the_10ks_figure_is_never_refused_for_its_labels(monkeypatch, start, fiscal_year):
    # The FY2026 10-K's FY2025 comparative holds the 10-K's own figure, 18,254 million, the year's current row, but the
    # per-filing writer named its start or fiscal year apart from companyfacts (a gap between the writers that can stay
    # open, docs/fiscal-year-label-repair.md). Unbacked, set 5 keeps it, confirmed by the 10-K. Backed by K27's
    # unchanged comparative, it is left and listed: the same verdict against the same figure, never a refusal over a
    # label the proxy did not write and the step cannot fix.
    for backed in (False, True):
        with _database() as db:
            company, payload, filing = _labelled_apart(db, monkeypatch, f"LB{int(backed)}", backed=backed,
                                                       start=start, fiscal_year=fiscal_year)
            row = _filing_row(db, filing)
            assert (row.is_latest, row.source, float(row.value), row.period_start.isoformat(), row.fiscal_year,
                    _check(row)["outcome"]) == (True, "edgar_xbrl", 18_254e6, start, fiscal_year, "confirmed")
            plan = _preview(db, company, payload)["proxy"]
            assert (plan["filing_rows_kept"], [e["fact_id"] for e in plan["left_report_backed"]]) == (
                (0, [row.id]) if backed else (1, []))


def test_a_current_left_row_with_no_10k_figure_is_left_and_listed(db, monkeypatch):
    # Only a proxy tags FY2021's net income, so the payload gives no 10-K figure: the replaced row, FY2021's current
    # row, is restored to its parse when nothing backs it (the payload-witness test above). An earnings release holding
    # the proxy's figure backs it here, so it is left and listed, and with no 10-K figure to contradict it, never refused.
    company, payload, filing = _only_a_proxy_tags_2021_and_the_10k_was_replaced(db, monkeypatch, "NAU")
    row = _filing_row(db, filing)
    assert (row.is_latest, row.source, float(row.value)) == (True, "companyfacts", 90e6)
    release = FinancialFact(company_id=company.id, concept="net_income", raw_tag="us-gaap:NetIncomeLoss", unit="USD",
                            period_start=date(2021, 1, 1), period_end=date(2021, 12, 31), fiscal_year=2021,
                            fiscal_period="FY", value=Decimal("90000000"), form="8-K", accession=_accn(company, "E22"),
                            source="companyfacts", reconciled=True, is_latest=False)
    db.add(release)  # planted as a row: a sync that read the release
    db.commit()
    plan = _preview(db, company, payload)["proxy"]
    assert plan["filing_rows_restored"] == 0
    assert [(e["fact_id"], e["set"], e["authority"], [b["fact_id"] for b in e["backed_by"]])
            for e in plan["left_report_backed"]] == [(row.id, 4, None, [release.id])]


def test_the_current_figure_refusal_reads_todays_10k_figure_where_no_winner_is_kept(monkeypatch):
    # A pure test of the planner. A bank's revenue: normalize_companyfacts keeps no revenue winner for a financial SIC,
    # while extract_authoritative_values, which sets 4 and 5 read for every verdict, keeps the 10-K's figure. The
    # current-figure refusal reads that figure too, so a backed row and its unbacked twin are judged against the same
    # number: the current row, 18,300 million, is 1.6% off the 10-K's 18,600, and the company is refused.
    row = {**_state(concept="revenue", raw_tag="us-gaap:Revenues", period_start=date(2025, 1, 1),
                    period_end=date(2025, 12, 31), fiscal_year=2025, value=18_300e6, accession="K26",
                    source="edgar_xbrl", filing_id=3)[1],
           "provenance": {"version": 1, "checks": {"authoritative": {"outcome": "confirmed",
                                                                     "authoritative_value": 18_254e6}}}}
    backer = {**row, "filing_id": None, "accession": "K25", "source": "companyfacts", "is_latest": False,
              "value": "18254000000", "provenance": None}
    proxy_row = {**backer, "form": "DEF 14A", "accession": "P27"}
    payload = _payload({"Revenues": {"units": {"USD": [
        _item(18_600e6, "2025-12-31", start="2025-01-01", accn="K26", fy=2026, filed="2027-02-25")]}}})
    assert row["is_latest"] and proxy.facts_service.extract_authoritative_values(payload)[
        ("revenue", date(2025, 12, 31))] == 18_600e6
    with pytest.raises(proxy.ProxyRepairRefused, match=r"^" + re.escape(
            "Proxy repair refused for this company (1): revenue FY 2025-12-31 (fact 1): "
            + _current_figure("18300000000", "18600000000")) + "$"):
        proxy.plan({1: row, 2: backer, 3: proxy_row}, {}, [], {}, payload)


def _own_figure_scaled_up(db, monkeypatch, ticker, *, backed):
    """The FY2026 10-K's own FY2026, 19,000 million, parsed as 19,000 thousand; P27 quotes the figure, and the backfill
    before the fix scaled the parse up to it (the cross-check's own unit fix). K27 repeats FY2026 unchanged (``backed``:
    a fixed sync stored it). K28 restates FY2026 as 19,500 million: the repair's payload carries it, and the harness's
    sync stores its row behind the filing row (no local Filing)."""
    company = _company(db, ticker)
    payload = _for(company, _mrk_payload())
    _items(payload).extend([
        _item(18_254e6, "2025-12-31", start="2025-01-01", accn=_accn(company, "K26"), fy=2026, filed="2027-02-25"),
        _item(19_000e6, "2026-12-31", start="2026-01-01", accn=_accn(company, "K26"), fy=2026, filed="2027-02-25"),
        _item(19_000e6, "2026-12-31", start="2026-01-01", accn=_accn(company, "P27"), fy=2026, form="DEF 14A",
              filed="2027-04-08"),
    ])
    filing = _filing(db, company, "K26", "2026-12-31", "2027-02-25")
    with _before_the_fix(monkeypatch):
        svc.process_filing_facts(db, filing, authoritative=svc.extract_authoritative_values(payload), standardized={
            "net_income": {"series": [{"period": "2026-12-31", "period_start": "2026-01-01", "value": 19_000e3,
                                       "fiscal_period": "FY", "fiscal_year": 2026}]}})
    _items(payload).extend(_item(value, f"{year}-12-31", start=f"{year}-01-01", accn=_accn(company, "K27"), fy=2027,
                                 filed="2028-02-25") for year, value in ((2026, 19_000e6), (2027, 20_000e6)))
    synced = copy.deepcopy(payload)
    if not backed:
        _items(synced)[:] = [item for item in _items(synced) if item["accn"] != _accn(company, "K27")]
    _sync(db, monkeypatch, company, synced)
    _items(payload).extend(_item(value, f"{year}-12-31", start=f"{year}-01-01", accn=_accn(company, "K28"), fy=2028,
                                 filed="2029-02-25") for year, value in ((2026, 19_500e6), (2027, 20_000e6),
                                                                         (2028, 21_000e6)))
    return company, payload, filing


@pytest.mark.parametrize("backed", [False, True], ids=["unbacked", "backed"])
def test_a_scaled_up_replacement_is_left_alone_backed_or_not(monkeypatch, backed):
    # The cross-check scaling up a parse read in units is its own job, which detection never lists: set 4 leaves such
    # a row before it asks whether a report row backs it, so a backing row neither lists nor refuses it. K28's
    # restatement puts today's 10-K figure 2.6% off the value, on its scale step: the row stays, neither replaced nor
    # refused (a unit fix and a later restatement may justify the value as filed), and the preview lists it in
    # ``scale_up_retained`` with reason ``off_10k_figure`` and the ratio of the value to the 10-K's figure (review
    # 5718798403, item 2; the CTO's review 5719610791). Alike before and since #1682.
    with _synced_before_and_since_1682(monkeypatch, lambda db, monkeypatch: _own_figure_scaled_up(
            db, monkeypatch, "SUP", backed=backed)) as states:
        for db, company, payload, filing in states.values():
            row = _filing_row(db, filing)
            assert (row.is_latest, row.source, float(row.value), _check(row)["original_value"]) == (
                True, "companyfacts", 19_000e6, 19_000e3)
            assert bool([r for r in _rows(db, company, concept="net_income", period_end=date(2026, 12, 31),
                                          filing_id=None) if r.accession == _accn(company, "K27")]) == backed
            stored = repair.snapshot(row)
            plan = _preview(db, company, payload)["proxy"]
            assert (plan["filing_rows_restored"], plan["left_report_backed"], plan["detection_listed"]) == (0, [], [])
            assert row.id not in {entry["fact_id"] for entry in plan["rows"]}
            assert [{name: e[name] for name in ("fact_id", "is_latest", "value", "original", "authority", "gap",
                                                "reason")} for e in plan["scale_up_retained"]] == [{
                "fact_id": row.id, "is_latest": True, "value": "19000000000", "original": 19_000e3,
                "authority": 19_500e6, "gap": 0.974359, "reason": "off_10k_figure"}]
            _apply(db, company, payload)
            assert repair.snapshot(_filing_row(db, filing)) == stored
            assert row.id not in {r.fact_id for r in db.query(FinancialFactRevision)}


def test_the_cli_totals_count_the_rows_each_listing_holds(db, monkeypatch, tmp_path):
    # proxy_totals tallies both read-only listings over the companies that succeeded: KKB's and RST's rows a report row
    # backs, and the scale-ups SSS (no 10-K figure) and SUP (K28's figure 2.6% off) retain (review of #1840, round 8).
    from app import database

    payloads = {}
    for ticker, build in (("KKB", _holds_the_10k_figure), ("RST", _restated_after_the_proxy),
                          ("SSS", _scaled_up_where_only_a_proxy_tags),
                          ("SUP", lambda db, monkeypatch, ticker: _own_figure_scaled_up(db, monkeypatch, ticker,
                                                                                         backed=False))):
        company, payloads[ticker], _filing_ = build(db, monkeypatch, ticker)
        if ticker == "KKB":  # a fixed sync has since stored the 10-K's row, which backs the filing row
            _sync(db, monkeypatch, company, payloads[ticker])
        (tmp_path / f"CIK{int(company.cik):010d}.json").write_text(json.dumps(payloads[ticker]))
    monkeypatch.setattr(database, "SessionLocal", lambda: Session(db.bind))
    report = cli.run(cli.build_parser().parse_args(["--tickers", "KKB,RST,SSS,SUP", "--companyfacts-dir",
                                                    str(tmp_path)]))
    assert report["failed"] == 0
    assert [(c["ticker"], len(c["proxy"]["left_report_backed"]), [e["reason"] for e in c["proxy"]["scale_up_retained"]])
            for c in report["companies"]] == [("KKB", 1, []), ("RST", 1, []), ("SSS", 0, ["no_10k_figure"]),
                                              ("SUP", 0, ["off_10k_figure"])]
    assert (report["proxy_totals"]["left_report_backed"], report["proxy_totals"]["scale_up_retained"]) == (2, 2)


def _listing_block(left, retained):
    """A company's ``proxy`` block with every counter at zero, ``left`` rows in ``left_report_backed`` and ``retained``
    in ``scale_up_retained``."""
    return {**dict.fromkeys(proxy.COUNTERS, 0), "other_planned_updates": 0, "other_planned_inserts": 0,
            "other_updates_by_kind": dict.fromkeys(proxy.OTHER_KINDS, 0), "other_inserts_by_concept": {},
            "left_report_backed": [{"fact_id": n} for n in range(left)],
            "scale_up_retained": [{"fact_id": n} for n in range(retained)]}


@pytest.mark.parametrize(("blocks", "expected"), [
    ([(2, 0), (0, 1), (1, 0)], (3, 1)), ([(0, 2)], (0, 2)), ([(0, 0), (1, 3)], (1, 3)),
], ids=["two_rows_in_one_listing", "retained_rows_alone", "both_listings_in_one_company"])
def test_proxy_totals_count_each_listings_rows_apart(blocks, expected):
    # A pure test of ``totals`` (review of #1840, round 9): each listing's total is the number of rows the companies'
    # blocks list there, its own listing's alone, rows and not companies. The CLI test's batch is symmetric (two
    # companies with one row in each listing), so these batches are not: a company listing two rows in one listing, a
    # batch whose only rows are retained, and a company in both listings.
    out = proxy.totals([_listing_block(left, retained) for left, retained in blocks])
    assert (out["left_report_backed"], out["scale_up_retained"]) == expected


@pytest.mark.parametrize("exit_", ["filing-stored-first", "per-filing-write", "synced-first"])
def test_a_sync_clears_the_current_figure_refusal_only_after_the_later_10ks_filing(monkeypatch, exit_):
    # NSB's company, synced since #1682, with K27 filed after its last sync, restating FY2025 again (18,900 million), so
    # today's 10-K figure contradicts the recorded original too: refused (the current-figure refusal). (Where K27
    # confirms the original, set 4 restores the row, current or not, and nothing is refused.) Once K27's Filing is stored, a sync, or K27's own per-filing write with no sync, lands K27's FY2025 row current over
    # the filing row (the later local Filing), which stops being the company's current figure, and the step leaves and
    # lists it. Synced first, K27's row is stored behind the filing row (no local Filing), and no later sync or
    # per-filing write, Filing or not, moves it: the refusal stays (docs, "A company synced since #1682").
    with _database() as db:
        company, payload, filing = _replaced_at_the_winners_identity(db, monkeypatch)
        _resync(db, company, payload)
        later = _with_k27(company, payload, RESTATED_AGAIN)
        [row] = [r for r in _rows(db, company, concept="net_income", period_end=date(2025, 12, 31)) if r.filing_id]
        refused = _refusal(db, (row.id, _current_figure("18254000000", "18900000000")))
        _refuses(db, company, later, refused)
        if exit_ == "synced-first":
            _resync(db, company, later)
        k27_filing = _filing(db, company, "K27", "2027-12-31", "2028-02-25")
        if exit_ == "per-filing-write":
            svc.process_filing_facts(db, k27_filing, standardized={"net_income": {"series": [
                {"period": "2025-12-31", "period_start": "2025-01-01", "value": RESTATED_AGAIN, "fiscal_period": "FY",
                 "fiscal_year": 2025}]}})
        else:
            _resync(db, company, later)
            if exit_ == "synced-first":
                svc.process_filing_facts(db, k27_filing, standardized={"net_income": {"series": [
                    {"period": "2025-12-31", "period_start": "2025-01-01", "value": RESTATED_AGAIN,
                     "fiscal_period": "FY", "fiscal_year": 2025}]}})
        [k27] = [r for r in _rows(db, company, concept="net_income", period_end=date(2025, 12, 31), fiscal_period="FY")
                 if r.accession == _accn(company, "K27")]
        cleared = exit_ != "synced-first"
        assert (db.get(FinancialFact, row.id).is_latest, k27.is_latest) == (not cleared, cleared)
        if cleared:
            assert [e["fact_id"] for e in _preview(db, company, later)["proxy"]["left_report_backed"]] == [row.id]
        else:
            _refuses(db, company, later, refused)


def test_a_sync_involving_another_currency_clears_the_current_figure_refusal_without_the_later_10ks_filing(monkeypatch):
    # docs/quarterly-data-repair.md, "A company synced since #1682": a sync in USD alone stores K27's row behind the
    # filing row until K27's Filing is stored; a sync that involves another currency dates K27's row by its `filed` in
    # the payload (``currency._filed``) and makes it current over the filing row (``_promote_batch_rows``), so the
    # current-figure refusal clears with no Filing, and the step leaves and lists the row.
    with _database() as db:
        company, payload, filing = _replaced_at_the_winners_identity(db, monkeypatch)
        _resync(db, company, payload)
        later = _with_k27(company, payload, RESTATED_AGAIN)
        [row] = [r for r in _rows(db, company, concept="net_income", period_end=date(2025, 12, 31)) if r.filing_id]
        _refuses(db, company, later, _refusal(db, (row.id, _current_figure("18254000000", "18900000000"))))
        _a_stored_eur_row(db, company)
        _resync(db, company, later)
        [k27] = [r for r in _rows(db, company, concept="net_income", period_end=date(2025, 12, 31), fiscal_period="FY")
                 if r.accession == _accn(company, "K27")]
        assert (db.get(FinancialFact, row.id).is_latest, k27.is_latest) == (False, True)
        assert [e["fact_id"] for e in _preview(db, company, later)["proxy"]["left_report_backed"]] == [row.id]


@pytest.mark.parametrize(("parsed", "quoted", "refused"), [(18_420e6, 18_254e6, False), (18_380e6, 18_560e6, True)],
                         ids=["row-within-1pct-witness-off", "row-off-witness-within-1pct"])
def test_set5s_current_figure_refusal_reads_the_rows_own_value_not_its_witness(monkeypatch, parsed, quoted, refused):
    # NSB's shape in set 5: the FY2026 10-K's parse of FY2025 was confirmed against P27's figure, which the FY2025 10-K's
    # own figure, the history row, holds; today's 10-K figure is 18,600. The refusal reads the company's current figure,
    # the row's own value, not the figure its check was confirmed against: 18,420 (0.97% off) is left and listed though
    # its witness is 1.86% off; 18,380 (1.18% off) is refused though its witness is 0.2% off.
    def build(db, monkeypatch):
        company = _company(db, "S5V")
        payload, filing = _restated_and_quoted_as_first_reported(db, monkeypatch, company, old_sync=False,
                                                                 own_fy2025=quoted, quoted=quoted, parsed=parsed)
        _sync(db, monkeypatch, company, payload)
        return company, payload, filing

    with _synced_before_and_since_1682(monkeypatch, build) as states:
        new, company, payload, _filing_ = states[True]
        [row] = [r for r in _rows(new, company, concept="net_income", period_end=date(2025, 12, 31)) if r.filing_id]
        assert (row.is_latest, row.source, float(row.value), _check(row)["outcome"], _check(row)["authoritative_value"]) == (
            True, "edgar_xbrl", parsed, "confirmed", quoted)
        if refused:
            _refuses(new, company, payload, _refusal(new, (row.id, _current_figure("18380000000", "18600000000"))))
        else:
            plan = _preview(new, company, payload)["proxy"]
            assert [(e["fact_id"], e["set"], e["figure"], e["authority"]) for e in plan["left_report_backed"]] == [
                (row.id, 5, "18254000000", 18_600e6)]


@pytest.mark.parametrize("shape", ["mirror_1000", "mirror_1000000", "true_scale_up"])
def test_a_proxy_tagged_at_the_wrong_scale_over_a_right_parse_is_restored(monkeypatch, shape):
    # FedEx's real error mirrored: P26 tags FY2025 1,000 or 1,000,000 times the 10-K's figure, and the old cross-check
    # replaced the FY2025 10-K's right parse (4,092 million) with it. The value is a scale-up of the recorded original,
    # but today's 10-K sides with the original, so set 4 restores the row, and its filing's chart shows the 10-K's
    # figure again. Detection's set 4 never listed it (it cannot read the payload's 10-K figure) and lists nothing
    # after. A true scale-up, a parse read in units that the 10-K's figure, scaled, corrected, stays the old check's
    # own job: left, unlisted. Alike before and since #1682.
    scale = {"mirror_1000": 1_000, "mirror_1000000": 1_000_000}.get(shape)
    parsed, stored = (4_092.0, 4_092e6) if scale is None else (4_092e6, 4_092e6 * scale)

    def build(db, monkeypatch):
        if scale is None:
            return _scaled_up(db, monkeypatch, "TSU")
        return _cross_checked(db, monkeypatch, "MSE", _fdx_with_proxy({2025: 4_092e6 * scale}), 4_092e6)

    with _synced_before_and_since_1682(monkeypatch, build) as states:
        for db, company, payload, filing in states.values():

            def chart():
                return {p["period_end"]: p["value"] for c in svc.get_filing_fundamentals(db, filing.id)["concepts"]
                        if c["concept"] == "net_income" for p in c["points"]}

            row = _filing_row(db, filing)
            assert (row.source, float(row.value), _check(row)["original_value"]) == ("companyfacts", stored, parsed)
            assert chart()["2025-05-31"] == stored
            plan = _preview(db, company, payload)["proxy"]
            assert (plan["left_report_backed"], plan["detection_listed"]) == ([], [])
            if shape == "true_scale_up":
                assert plan["filing_rows_restored"] == 0 and row.id not in {e["fact_id"] for e in plan["rows"]}
                continue
            assert plan["filing_rows_restored"] == 1
            _apply(db, company, payload)
            row = _filing_row(db, filing)
            assert (row.source, float(row.value), _check(row)["outcome"]) == ("edgar_xbrl", 4_092e6, "confirmed")
            assert chart()["2025-05-31"] == 4_092e6
            found = _detection(db, {company.ticker: payload})
            assert (found[4], found[5]) == ([], [])


def test_the_current_figure_refusal_reads_todays_10k_figure_where_a_winner_differs(monkeypatch):
    # A pure test of the planner. Where the payload gives both, the refusal reads today's 10-K figure, the authority
    # every set-4/5 verdict reads, not set 2's fresh winner at the key (the two can differ by tag precedence, or by the
    # authority's annual band and tie-break): the current row, 18,300 million, is 0.3% off a fresh winner of 18,350 but
    # 1.6% off the 10-K's 18,600, and the company is refused.
    row = {**_state(period_start=date(2025, 1, 1), period_end=date(2025, 12, 31), fiscal_year=2025, value=18_300e6,
                    accession="K26", source="edgar_xbrl", filing_id=3)[1],
           "provenance": {"version": 1, "checks": {"authoritative": {"outcome": "confirmed",
                                                                     "authoritative_value": 18_254e6}}}}
    backer = {**row, "filing_id": None, "accession": "K25", "source": "companyfacts", "is_latest": False,
              "value": "18254000000", "provenance": None}
    proxy_row = {**backer, "form": "DEF 14A", "accession": "P27"}
    fresh = _state(period_start=date(2025, 1, 1), period_end=date(2025, 12, 31), fiscal_year=2025, value=18_350e6,
                   accession="K27")[0]
    payload = _payload({"NetIncomeLoss": {"units": {"USD": [
        _item(18_600e6, "2025-12-31", start="2025-01-01", accn="K26", fy=2026, filed="2027-02-25")]}}})
    assert proxy.facts_service.extract_authoritative_values(payload)[("net_income", date(2025, 12, 31))] == 18_600e6
    with pytest.raises(proxy.ProxyRepairRefused, match=r"^" + re.escape(
            "Proxy repair refused for this company (1): net_income FY 2025-12-31 (fact 1): "
            + _current_figure("18300000000", "18600000000")) + "$"):
        proxy.plan({1: row, 2: backer, 3: proxy_row}, {}, [fresh], {}, payload)


def _set5_below_a_later_winner(db, monkeypatch, ticker="S5L"):
    """S5R's row below a later winner: a sync before the fix stored the proxies' rows, the backfill confirmed the FY2026
    10-K's parse of FY2025, 18,300 million, against P27's 18,254, and K27, which the harness's sync stores current over
    P27's row, gives FY2025 as 18,600."""
    company = _company(db, ticker)
    payload, filing = _restated_and_quoted_as_first_reported(db, monkeypatch, company, old_sync=True, parsed=18_300e6)
    return company, _with_k27(company, payload), filing


def test_a_set5_row_below_a_later_current_winner_is_refused_before_1682_and_left_since(monkeypatch):
    # "A refusal can disappear" (docs): set 5's own check refuses the row the 10-K contradicts by 1.6% before #1682;
    # since, the FY2025 10-K's history row backs the figure it was confirmed against, and the row, not the company's
    # current figure (K27's is), is left and listed.
    with _synced_before_and_since_1682(monkeypatch, _set5_below_a_later_winner) as states:
        (old, company, payload), new = states[False][:3], states[True][0]
        [row] = [r for r in _rows(new, company, concept="net_income", period_end=date(2025, 12, 31)) if r.filing_id]
        assert (row.is_latest, float(row.value), _check(row)["authoritative_value"]) == (False, 18_300e6, 18_254e6)
        _refuses(old, company, payload, _refusal(old, (row.id, "the old cross-check confirmed this filing row against "
                                                               "a proxy's figure, and the 10-K's figure disagrees with it "
                                                               "by more than 1%")))
        plan = _preview(new, company, payload)["proxy"]
        assert [(e["fact_id"], e["set"]) for e in plan["left_report_backed"]] == [(row.id, 5)]



def _mirrored(db, monkeypatch, ticker, *, parsed, scale, current):
    """FedEx's payload with P26 tagging FY2025 at ``scale`` times the FY2025 10-K's right parse ``parsed``, which the
    backfill before the fix replaced with P26's figure (the recorded original, ``parsed``); today's 10-K figure is FedEx's
    4,092 million. ``current``: no sync before the fix stored P26's rows, so the filing row is FY2025's current row (a
    fixed sync stores the FY2026 10-K's winner behind it, with no local Filing); otherwise P26's row is current over it."""
    company = _company(db, ticker)
    payload = _for(company, _fdx_with_proxy({2025: parsed * scale}))
    if not current:
        _old_sync(db, monkeypatch, company, payload)
    filing = _filing(db, company, "K25", "2025-05-31", "2025-07-20")
    _file(db, monkeypatch, filing, {"net_income": ("2024-06-01", parsed)}, authority_from=payload)
    if current:
        _sync(db, monkeypatch, company, payload)
    return company, payload, filing


@pytest.mark.parametrize(("scale", "gap", "current"), [
    (1_000, 0.005, False), (1_000, 0.015, False), (1_000, 0.005, True), (1_000, 0.015, True),
    (1_000_000, 0.005, True), (1_000_000, 0.015, False),
], ids=["x1000-0.5pct", "x1000-1.5pct", "x1000-0.5pct-current", "x1000-1.5pct-current", "x1000000-0.5pct-current",
        "x1000000-1.5pct"])
def test_a_mirrored_scale_error_takes_set_4s_ordinary_path(monkeypatch, scale, gap, current):
    # A proxy tagged 1,000 or 1,000,000 times a right parse that today's 10-K figure, 4,092 million, puts on the
    # original's scale: the scale-up exemption does not apply, and set 4's own test of the recorded original decides.
    # Within 1% (the 10-K 0.5% off the parse) the row is restored to its parse; beyond (1.5% off, the year restated) it
    # is refused, whether or not the row is the company's current figure. Alike before and since #1682.
    parsed = float(round(4_092e6 * (1 + gap)))
    with _synced_before_and_since_1682(monkeypatch, lambda db, monkeypatch: _mirrored(
            db, monkeypatch, "MIR", parsed=parsed, scale=scale, current=current)) as states:
        for db, company, payload, filing in states.values():
            row = _filing_row(db, filing)
            assert (row.is_latest, row.source, float(row.value), _check(row)["original_value"]) == (
                current, "companyfacts", parsed * scale, parsed)
            if gap > 0.01:
                _refuses(db, company, payload, _refusal(db, (row.id, "the 10-K's figure disagrees with the recorded "
                                                                     "original value by more than 1%, and the filing "
                                                                     "row holds neither")))
                continue
            plan = _preview(db, company, payload)["proxy"]
            assert (plan["filing_rows_restored"], plan["left_report_backed"], plan["detection_listed"]) == (1, [], [])
            _apply(db, company, payload)
            row = _filing_row(db, filing)
            assert (row.is_latest, row.source, float(row.value), _check(row)["outcome"]) == (
                current, "edgar_xbrl", parsed, "confirmed")


@pytest.mark.parametrize(("value", "original", "authority", "outcome"), [
    (-4_092e9, -4_092e6, -4_112_460_000.0, "restored"),
    (-4_092e9, -4_092e6, -4_153_380_000.0, "refused"),
    (-4_092e12, -4_092e6, -4_092e6, "restored"),
    (19_000e6, 19_000e3, 19_500e6, "exempt"),
    (-19_000e6, -19_000e3, -19_500e6, "exempt"),
    (4_092e6, 4_092.0, 4_092e6 * 1.3, "exempt"),
    (4_092e9, 4_092e3, 4_092e6, "refused"),
    (4_092e6, 4_092e3, 4_092e9, "refused"),
    (4_092e9, 4_092e6, -4_092e6, "refused"),
    (4_092e9, 4_092e6, -4_092e9, "refused"),
    (-4_092e9, -4_092e6, 4_092e9, "refused"),
    (4_092e9, 4_092e6, 0.0, "refused"),
    (1e9, 1e6, 1e9 / 31, "exempt"),
    (1e9, 1e6, 1e9 / 32, "refused"),
    (1e9, 1e6, 1e9 * 31, "exempt"),
    (1e9, 1e6, 1e9 * 32, "refused"),
    (1e9, 1e6, 31_622_776_600.0, "exempt"),
    (1e9, 1e6, 31_622_776_700.0, "refused"),
    (31_622_776_600.0, 31_622_776.6, 1e9, "exempt"),
    (31_622_776_700.0, 31_622_776.7, 1e9, "refused"),
    (1e9, 1e6, 31_622_776.601683795, "exempt"),
    (1e9, 1e6, 31_622_776.60168379, "refused"),
    (4_092e9, 4_092e6, 4_092e9 / 40, "refused"),
    (4_092e9, 4_092e6, 4_092e9 / 10, "exempt"),
], ids=["negative-x1000-0.5pct", "negative-x1000-1.5pct", "negative-x1000000", "k28-restated-true-scale-up",
        "a-loss-restated-on-its-scale-step",
        "true-scale-up-restated-30pct", "x1000000-10k-a-step-between", "x1000-10k-a-step-above-the-value",
        "opposite-sign-on-the-originals-scale", "opposite-sign-on-the-values-scale",
        "negative-value-a-profit-on-its-scale", "zero-10k-figure", "31x-under-the-value-within-half-a-step",
        "32x-under-the-value-past-half-a-step", "31x-over-the-value-within-half-a-step",
        "32x-over-the-value-past-half-a-step", "31.6227766x-over-the-value-within", "31.6227767x-over-the-value-past",
        "31.6227766x-under-the-value-within", "31.6227767x-under-the-value-past",
        "a-float-just-inside-the-bound-within", "a-float-just-outside-the-bound-past",
        "40x-under-the-value-past-half-a-step", "10x-under-the-value"])
def test_the_scale_up_exemption_reads_the_10k_figures_sign_and_scale(value, original, authority, outcome):
    # A pure test of the planner. A scale-up stays the old check's own unit fix only where today's 10-K figure is of the
    # value's sign and on its scale step, strictly within half a step (about 31.6 times) of it on a log scale, or where
    # there is none. Otherwise set 4's ordinary path decides, the original against the 10-K's figure. So a loss's
    # mirrored scale error is restored or refused as a profit's; K28's restatement and a true scale-up restated 30% stay
    # exempt; a figure a step between the value and the original (a parse and a proxy each 1,000 times off) or a step
    # beyond the value is refused, never exempt; a figure of the other sign, on either scale, and a zero figure, which
    # the rest of the step reads as a figure, are on no scale of the value's, and refused (review 5718798403, item 2);
    # 31 times either side of the value is within half a step and 32 times past it, as is 40 times (a plain difference
    # would call that near); 10 times under is within it. The bound, a factor of sqrt(1,000), is read exactly, from the
    # stored decimal and the JSON number: 31.6227766 times either side of the value is within it and 31.6227767 times
    # past it, and a JSON float of 31,622,776.601683795 against a value of 1,000 million is within it by about 1e-19 of
    # 1/1,000 in the squared ratio, where a float logarithm put it exactly on the bound and refused it.
    row = {**_state(period_start=date(2025, 1, 1), period_end=date(2025, 12, 31), fiscal_year=2025, value=value,
                    accession="K25", filing_id=3)[1],
           "provenance": {"version": 1, "checks": {"authoritative": {"outcome": "replaced", "original_value": original,
                                                                     "authoritative_value": value}}}}
    proxy_row = {**row, "filing_id": None, "form": "DEF 14A", "accession": "P26", "is_latest": False,
                 "provenance": None}
    payload = _payload({"NetIncomeLoss": {"units": {"USD": [
        _item(authority, "2025-12-31", start="2025-01-01", accn="K26", fy=2026, filed="2027-02-25")]}}})
    assert proxy.facts_service.extract_authoritative_values(payload)[("net_income", date(2025, 12, 31))] == authority
    if outcome == "refused":
        with pytest.raises(proxy.ProxyRepairRefused, match=r"^" + re.escape(
                "Proxy repair refused for this company (1): net_income FY 2025-12-31 (fact 1): the 10-K's figure "
                "disagrees with the recorded original value by more than 1%, and the filing row holds neither") + "$"):
            proxy.plan({1: row, 2: proxy_row}, {}, [], {}, payload)
        return
    updates = {}
    plan = proxy.plan({1: row, 2: proxy_row}, updates, [], {}, payload)
    assert plan.counts["filing_rows_restored"] == (1 if outcome == "restored" else 0)
    assert (updates[1]["value"], updates[1]["source"]) == (repair._json_value(Decimal(str(original))), "edgar_xbrl") \
        if outcome == "restored" else 1 not in updates



@pytest.mark.parametrize(("noise", "current"), [(1.0, False), (1.0, True), (1.002, False), (0.997, True)],
                         ids=["exact", "exact-current", "plus-0.2pct", "minus-0.3pct-current"])
def test_a_parse_and_a_proxy_each_a_step_off_are_refused(monkeypatch, noise, current):
    # The parse read thousands as units (4,092 thousand) and P26 tagged FY2025 a step too large the other way (about
    # 4,092 billion), so the value is a x1,000,000 scale-up of the original while today's 10-K figure, 4,092 million,
    # sits on the step between them. It is on neither the value's scale nor the original's: set 4's ordinary path
    # refuses the row, the original 1,000 times off the 10-K's figure, whatever the proxy's sub-1% noise, whether or not
    # the row is current, before and since #1682.
    with _synced_before_and_since_1682(monkeypatch, lambda db, monkeypatch: _mirrored(
            db, monkeypatch, "MID", parsed=4_092e3, scale=1e6 * noise, current=current)) as states:
        for db, company, payload, filing in states.values():
            row = _filing_row(db, filing)
            assert (row.is_latest, row.source, float(row.value), _check(row)["original_value"]) == (
                current, "companyfacts", 4_092e3 * 1e6 * noise, 4_092e3)
            _refuses(db, company, payload, _refusal(db, (row.id, "the 10-K's figure disagrees with the recorded "
                                                                 "original value by more than 1%, and the filing row "
                                                                 "holds neither")))


# --- Principal review 5718798403 (#1667): its reproductions, through the real writers, before and since #1682 ----------
#
# The review reproduced three defects against 50fa41894, which merged to main as 1f56928db, and asked for regression
# coverage through the actual writers: the legacy per-filing writer (``process_filing_facts`` under ``_before_the_fix``)
# and today's companyfacts persistence, each shape synced as before #1682 and since. The tests carry the review's item
# numbers. Item 1: a report row (since #1682, the year's own report as first reported) backs the proxy figure on a
# filing row while today's 10-K figure contradicts it, after an amendment and after a later comparative restated the
# year. Item 2: the scale-up exemption, where a proxy was tagged at the wrong scale over a right parse, or no 10-K
# figure can read the scale. Item 3: what the preview shows of a row it leaves. Each fails on 1f56928db's
# proxy_fact_repair.py and passes after.

REVIEW_FIRST, REVIEW_AMENDED, REVIEW_RESTATED = 100e6, 120e6, 80e6


def _review_payload(company, later, *, first=REVIEW_FIRST, figure=None, then=None):
    """FY2025's 10-K (K25) reports ``first``, 100 million. ``later`` gives the year ``figure``: ``amendment``, a 10-K/A
    (KA25, 120 million), or ``restatement``, the FY2026 10-K's comparative (K26, 80 million). A proxy filed after it
    quotes FY2025 as first reported and is listed last: before #1622 it was the authority, the latest filed. ``then``: a
    later 10-K (K26 after the amendment, K27 after the restatement) gives FY2025 as ``then``. Returns the payload and
    that 10-K's (accession, fiscal year, filing date)."""
    figure = figure if figure is not None else REVIEW_AMENDED if later == "amendment" else REVIEW_RESTATED
    fy2025 = {"start": "2025-01-01"}
    items = [_item(first, "2025-12-31", accn="K25", fy=2025, filed="2026-02-25", **fy2025)]
    if later == "amendment":
        items.append(_item(figure, "2025-12-31", accn="KA25", fy=2025, form="10-K/A", filed="2026-03-20", **fy2025))
        repeat = ("K26", 2026, "2027-02-25")
    else:
        items += [_item(figure, "2025-12-31", accn="K26", fy=2026, filed="2027-02-25", **fy2025),
                  _item(110e6, "2026-12-31", start="2026-01-01", accn="K26", fy=2026, filed="2027-02-25")]
        repeat = ("K27", 2027, "2028-02-25")
    if then is not None:
        accn, fy, filed = repeat
        items.append(_item(then, "2025-12-31", accn=accn, fy=fy, filed=filed, **fy2025))
    proxy_filed = ("P26", 2025, "2026-04-08") if later == "amendment" else ("P27", 2026, "2027-04-08")
    items.append(_item(first, "2025-12-31", accn=proxy_filed[0], fy=proxy_filed[1], form="DEF 14A",
                       filed=proxy_filed[2], **fy2025))
    return _for(company, _payload({"NetIncomeLoss": {"units": {"USD": items}}})), repeat


def _reported_then_overwritten(db, monkeypatch, ticker, later, *, first=REVIEW_FIRST, figure=None, parsed=None,
                               then=None, then_filed=False, proxy_rows=False):
    """``_review_payload``'s company. The per-filing writer read the later filing's FY2025 (the amendment's, or the FY2026
    10-K's comparative) as ``parsed`` (``figure`` unless given), and the backfill before #1622 replaced it with the
    proxy's figure. With no sync before the fix the filing row is FY2025's current row; a fixed sync then skipped its
    identity, the year's winner's (NSB's shape). ``proxy_rows``: a sync before the fix stored the proxy's row first,
    current at FY2025, so the filing row is behind it. ``then_filed``: the later 10-K's Filing is stored first, so the
    sync lands its FY2025 row current over the filing row; without it, the sync stores that row behind the filing row."""
    company = _company(db, ticker)
    payload, (accn, fy, filed) = _review_payload(company, later, first=first, figure=figure, then=then)
    figure = figure if figure is not None else REVIEW_AMENDED if later == "amendment" else REVIEW_RESTATED
    if proxy_rows:
        _old_sync(db, monkeypatch, company, payload)
    series = [{"period": "2025-12-31", "period_start": "2025-01-01", "value": figure if parsed is None else parsed,
               "fiscal_period": "FY", "fiscal_year": 2025}]
    if later == "amendment":
        filing = _filing(db, company, "KA25", "2025-12-31", "2026-03-20", form="10-K/A")
    else:
        filing = _filing(db, company, "K26", "2026-12-31", "2027-02-25")
        series.append({"period": "2026-12-31", "period_start": "2026-01-01", "value": 110e6, "fiscal_period": "FY",
                       "fiscal_year": 2026})
    with _before_the_fix(monkeypatch):
        svc.process_filing_facts(db, filing, authoritative=svc.extract_authoritative_values(payload),
                                 standardized={"net_income": {"series": series}})
    if then_filed:
        _filing(db, company, accn, f"{fy}-12-31", filed)
    _sync(db, monkeypatch, company, payload)
    return company, payload, filing


def _overwritten_row(db, company, filing, parsed, first=REVIEW_FIRST):
    """The filing row the backfill overwrote, asserted as planted: FY2025, the proxy's figure, its parse recorded."""
    [row] = [r for r in _rows(db, company, concept="net_income", period_end=date(2025, 12, 31)) if r.filing_id]
    check = _check(row)
    assert (row.filing_id, row.source, float(row.value), check["outcome"], check["original_value"],
            check["authoritative_value"]) == (filing.id, "companyfacts", first, "replaced", parsed, first)
    return row


def _history_rows(db, company):
    return [(r.accession, r.is_latest, r.filing_id, r.source, r.form, float(r.value))
            for r in _rows(db, company, concept="net_income", period_end=date(2025, 12, 31), filing_id=None)
            if r.accession == _accn(company, "K25")]


@pytest.mark.parametrize(("later", "parsed", "proxy_rows"), [
    ("amendment", REVIEW_AMENDED, False), ("restatement", REVIEW_RESTATED, False),
    ("amendment", REVIEW_AMENDED, True), ("restatement", REVIEW_RESTATED, True), ("amendment", 119.5e6, False),
], ids=["item_1_amendment", "item_1_restatement", "item_1_amendment_behind_the_proxy_row",
        "item_1_restatement_behind_the_proxy_row", "item_1_amendment_parse_within_1pct"])
def test_principal_review_5718798403_item_1_a_report_backed_row_whose_original_the_10k_confirms_is_restored(
        monkeypatch, later, parsed, proxy_rows):
    # Principal review 5718798403, item 1: an amendment (100 to 120 million) and a later comparative (100 to 80
    # million); the backfill before #1622 overwrote the later filing's parse with the proxy's 100 million, the year as
    # first reported. Synced since #1682, the year's own 10-K figure, 100 million, is a history row at K25, a report row
    # holding the proxy's figure. It says nothing of the later filing's parse, which today's 10-K figure confirms within
    # 1%, so set 4 restores the row to its own recorded original through today's cross-check, exactly as with no history
    # row: the parse, not the 10-K's figure, is written (pinned where they differ, 119.5 against 120 million). Behind
    # P2x's stored row, set 2 then retires that row and promotes the restored one, at the winner's identity. Main
    # (1f56928db) leaves the row at 100 million, silently. Nothing is listed, and detection lists nothing after.
    figure = REVIEW_AMENDED if later == "amendment" else REVIEW_RESTATED
    with _synced_before_and_since_1682(monkeypatch, lambda db, monkeypatch: _reported_then_overwritten(
            db, monkeypatch, "PR" + later[0].upper(), later, parsed=parsed, proxy_rows=proxy_rows)) as states:
        assert (_history_rows(states[False][0], states[False][1]), _history_rows(states[True][0], states[True][1])) == (
            [], [(_accn(states[True][1], "K25"), False, None, "companyfacts", "10-K", REVIEW_FIRST)])
        for db, company, payload, filing in (states[True], states[False]):  # since #1682 first: main fails it
            row = _overwritten_row(db, company, filing, parsed)
            assert row.is_latest == (not proxy_rows)
            assert svc.extract_authoritative_values(payload)[("net_income", date(2025, 12, 31))] == figure
            plan = _preview(db, company, payload)["proxy"]
            assert [e["action"] for e in plan["rows"] if e["fact_id"] == row.id] == ["restored"]
            assert (plan["filing_rows_restored"], plan["filing_rows_kept"], plan["promoted"], plan["left_report_backed"],
                    plan["detection_listed"]) == (1, 0, 1 if proxy_rows else 0, [], [])
            assert [(e["form"], e["winner_accession"]) for e in plan["rows"] if e["action"] == "promoted"] == (
                [("DEF 14A", filing.accession_number)] if proxy_rows else [])
            _apply(db, company, payload)
            restored = db.get(FinancialFact, row.id)
            check = _check(restored)
            assert (restored.is_latest, restored.source, restored.value, check["outcome"], check["original_value"],
                    check["authoritative_value"]) == (True, "edgar_xbrl", Decimal(str(parsed)), "confirmed", parsed,
                                                      figure)
            found = _detection(db, {company.ticker: payload})
            assert (found[2], found[4], found[5]) == ([], [], [])


def _restated_again(later):
    """A later 10-K's FY2025, 4% off the later filing's figure: the recorded original is contradicted too."""
    return round((REVIEW_AMENDED if later == "amendment" else REVIEW_RESTATED) * 1.04)


@pytest.mark.parametrize("later", ["amendment", "restatement"], ids=["item_1_amendment", "item_1_restatement"])
def test_principal_review_5718798403_item_1_a_report_backed_current_row_whose_original_the_10k_contradicts_refuses(
        monkeypatch, later):
    # Principal review 5718798403, item 1, where the 10-K contradicts the recorded original too: a later 10-K, with no
    # local Filing, restated FY2025 again, 4% off the parse, and a fixed sync stored its row behind the filing row, which
    # stays the company's current figure. Synced since #1682, the K25 history row backs the proxy's 100 million, so set
    # 4 leaves the row, and left, the company's figure would stay the proxy's where the 10-K contradicts it and its
    # original both: the current-figure refusal. Synced as before, no report row backs it, and set 4's own test refuses
    # the original. Nothing is written either way.
    then = _restated_again(later)
    with _synced_before_and_since_1682(monkeypatch, lambda db, monkeypatch: _reported_then_overwritten(
            db, monkeypatch, "PC" + later[0].upper(), later, then=then)) as states:
        (old, company, payload, filing), (new, *_rest) = states[False], states[True]
        figure = REVIEW_AMENDED if later == "amendment" else REVIEW_RESTATED
        row = _overwritten_row(new, company, filing, figure)
        assert row.is_latest and _overwritten_row(old, company, filing, figure).is_latest
        assert svc.extract_authoritative_values(payload)[("net_income", date(2025, 12, 31))] == then
        _refuses(new, company, payload, _refusal(new, (row.id, _current_figure("100000000", f"{then:.0f}"))))
        _refuses(old, company, payload, _refusal(old, (row.id, "the 10-K's figure disagrees with the recorded original "
                                                               "value by more than 1%, and the filing row holds neither")))


@pytest.mark.parametrize("current", [True, False], ids=["current", "behind_the_proxy_row"])
@pytest.mark.parametrize("scale", [1_000, 1_000_000], ids=["thousandfold", "millionfold"])
def test_principal_review_5718798403_item_2_a_proxy_scaled_over_a_right_parse_is_restored_not_kept(
        monkeypatch, scale, current):
    # Principal review 5718798403, item 2. FedEx's FY2025 10-K parse, 4,092 million, is right, and today's 10-K figure
    # is the same; P26 tags FY2025 at 4,092 billion (or, millionfold, 4,092 trillion), and the backfill before #1622
    # replaced the parse with it, a value that looks like the cross-check scaling up a parse read in units. Today's
    # 10-K figure sits on the original's scale, not the value's, so the scale-up exemption does not hold: set 4
    # restores the row to 4,092 million, keeps nothing and lists nothing, and the filing's chart shows the 10-K's figure
    # again. FedEx restates no year, so no history row is stored since #1682; the report-backed case is the next test.
    with _synced_before_and_since_1682(monkeypatch, lambda db, monkeypatch: _mirrored(
            db, monkeypatch, "PRS", parsed=4_092e6, scale=scale, current=current)) as states:
        for db, company, payload, filing in states.values():
            row = _filing_row(db, filing)
            assert (row.is_latest, row.source, float(row.value), _check(row)["original_value"]) == (
                current, "companyfacts", 4_092e6 * scale, 4_092e6)
            assert svc.extract_authoritative_values(payload)[("net_income", date(2025, 5, 31))] == 4_092e6
            plan = _preview(db, company, payload)["proxy"]
            assert [e["action"] for e in plan["rows"] if e["fact_id"] == row.id] == ["restored"]
            assert (plan["filing_rows_restored"], plan["filing_rows_kept"], plan["detection_listed"]) == (1, 0, [])
            assert (plan["left_report_backed"], plan["scale_up_retained"]) == ([], [])
            _apply(db, company, payload)
            row = _filing_row(db, filing)
            assert (row.is_latest, row.source, float(row.value), _check(row)["outcome"]) == (
                current, "edgar_xbrl", 4_092e6, "confirmed")
            assert {p["period_end"]: p["value"] for c in svc.get_filing_fundamentals(db, filing.id)["concepts"]
                    if c["concept"] == "net_income" for p in c["points"]}["2025-05-31"] == 4_092e6


@pytest.mark.parametrize(("then", "then_filed"), [(None, False), (103e6, False), (103e6, True)],
                         ids=["corrected", "restated_current", "restated_not_current"])
def test_principal_review_5718798403_item_2_a_report_backed_scale_error_takes_the_ordinary_path(
        monkeypatch, then, then_filed):
    # Principal review 5718798403, items 1 and 2 together (the M17 shape of the review of #1840). FY2025's 10-K tagged
    # its net income 1,000 times too large, 100 billion; a 10-K/A corrected it to 100 million, and P26 quotes the first
    # report's 100 billion. The backfill before #1622 replaced the 10-K/A's right parse, 100 million, with P26's figure.
    # Since #1682 the FY2025 10-K's own figure, 100 billion, is a history row: a report row backing the value. The value
    # is a scale-up of the original, but today's 10-K figure is on the original's scale, so the exemption does not
    # stand, backed or not, and set 4's ordinary path decides. ``corrected``: the 10-K/A's figure confirms the original,
    # which is restored, before #1682 and since. ``restated``: a later 10-K restated FY2025 to 103 million, 3% off the
    # original. Before #1682 set 4's own test refuses; since, the history row backs the value, and the row is refused
    # where it is the company's current figure and listed where it is not (the later 10-K's Filing stored first).
    with _synced_before_and_since_1682(monkeypatch, lambda db, monkeypatch: _reported_then_overwritten(
            db, monkeypatch, "PBS", "amendment", first=100e9, figure=100e6, then=then,
            then_filed=then_filed)) as states:
        (old, company, payload, filing), (new, *_rest) = states[False], states[True]
        row = _overwritten_row(new, company, filing, 100e6, first=100e9)
        assert row.is_latest == (not then_filed)
        assert svc.extract_authoritative_values(payload)[("net_income", date(2025, 12, 31))] == (then or 100e6)
        assert (_history_rows(old, company), _history_rows(new, company)) == (
            [], [(_accn(company, "K25"), False, None, "companyfacts", "10-K", 100e9)])
        [history] = [r for r in _rows(new, company, concept="net_income", filing_id=None)
                     if r.accession == _accn(company, "K25")]
        if then is None:
            for db in (new, old):
                plan = _preview(db, company, payload)["proxy"]
                assert [e["action"] for e in plan["rows"] if e["fact_id"] == row.id] == ["restored"]
                assert (plan["filing_rows_restored"], plan["left_report_backed"], plan["scale_up_retained"]) == (
                    1, [], [])
                _apply(db, company, payload)
                restored = db.get(FinancialFact, row.id)
                assert (restored.is_latest, restored.source, float(restored.value), _check(restored)["outcome"]) == (
                    True, "edgar_xbrl", 100e6, "confirmed")
            return
        _refuses(old, company, payload, _refusal(old, (row.id, "the 10-K's figure disagrees with the recorded original "
                                                               "value by more than 1%, and the filing row holds neither")))
        if not then_filed:
            _refuses(new, company, payload, _refusal(new, (row.id, _current_figure("100000000000", "103000000"))))
            return
        stored = repair.snapshot(row)
        plan = _preview(new, company, payload)["proxy"]
        assert (plan["filing_rows_restored"], plan["scale_up_retained"]) == (0, [])
        assert [(e["fact_id"], e["set"], e["figure"], e["authority"], [b["fact_id"] for b in e["backed_by"]])
                for e in plan["left_report_backed"]] == [(row.id, 4, "100000000000", 103e6, [history.id])]
        _apply(new, company, payload)
        assert repair.snapshot(new.get(FinancialFact, row.id)) == stored
        assert row.id not in {r.fact_id for r in new.query(FinancialFactRevision)}


@pytest.mark.parametrize("later", ["amendment", "restatement"], ids=["item_1_amendment", "item_1_restatement"])
def test_principal_review_5718798403_item_3_a_left_row_is_listed_with_its_backers_and_never_written(monkeypatch, later):
    # Principal review 5718798403, item 3: item 1's shapes, where the 10-K contradicts the original too (a later 10-K
    # restated FY2025 again, 4% off the parse) and that 10-K's Filing is stored first, so the sync lands its row current
    # and the overwritten row is not the company's current figure. Synced since #1682, set 4 leaves the row (the K25
    # history row holds its 100 million) and the preview lists it in ``left_report_backed`` with that backer and today's
    # 10-K figure; the apply lists it alike and writes, journals and checks nothing. Synced as before, no report row
    # backs it, and set 4's own test refuses the original (the control).
    then = _restated_again(later)
    with _synced_before_and_since_1682(monkeypatch, lambda db, monkeypatch: _reported_then_overwritten(
            db, monkeypatch, "PV" + later[0].upper(), later, then=then, then_filed=True)) as states:
        (old, company, payload, filing), (new, *_rest) = states[False], states[True]
        figure = REVIEW_AMENDED if later == "amendment" else REVIEW_RESTATED
        row = _overwritten_row(new, company, filing, figure)
        repeat = _accn(company, "K26" if later == "amendment" else "K27")
        [winner] = [r for r in _rows(new, company, concept="net_income", period_end=date(2025, 12, 31))
                    if r.accession == repeat]
        assert (row.is_latest, winner.is_latest, float(winner.value)) == (False, True, then)
        [history] = [r for r in _rows(new, company, concept="net_income", period_end=date(2025, 12, 31),
                                      filing_id=None) if r.accession == _accn(company, "K25")]
        assert (history.is_latest, history.source, history.form, float(history.value)) == (
            False, "companyfacts", "10-K", REVIEW_FIRST)
        stored, planted = repair.snapshot(row), _snapshots(new, company)
        since = _preview(new, company, payload)["proxy"]
        assert (since["filing_rows_restored"], since["filing_rows_kept"]) == (0, 0)
        assert row.id not in {e["fact_id"] for e in since["rows"]}
        assert since["left_report_backed"] == [{
            "fact_id": row.id, "action": "left_report_backed", "concept": "net_income", "fiscal_year": 2025,
            "fiscal_period": "FY", "period_end": "2025-12-31", "accession": filing.accession_number,
            "form": filing.filing_type, "value": "100000000", "winner_accession": None, "winner_value": None,
            "gap": None, "set": 4, "figure": "100000000", "authority": then, "backed_by": [{
                "fact_id": history.id, "accession": history.accession, "form": "10-K", "is_latest": False,
                "filing_id": None, "source": "companyfacts"}]}]
        applied = _apply(new, company, payload)["proxy"]
        assert applied["left_report_backed"] == since["left_report_backed"]
        # No stored proxy row witnesses the row here (the proxy's figure is a payload item alone), so detection cannot
        # list it, backed or not; LTX's contradicted test above pins the case where the backer decides.
        assert (since["detection_listed"], applied["detection_listed"]) == ([], [])
        found = _detection(new, {company.ticker: payload})
        assert (found[4], found[5]) == ([], [])
        assert repair.snapshot(new.get(FinancialFact, row.id)) == stored and _snapshots(new, company) == planted
        assert new.query(FinancialFactRevision).count() == 0
        _refuses(old, company, payload, _refusal(old, (row.id, "the 10-K's figure disagrees with the recorded original "
                                                               "value by more than 1%, and the filing row holds neither")))


def test_principal_review_5718798403_item_3_left_report_backed_names_every_backer():
    # A pure test of the planner (principal review 5718798403, item 3): the listing names every stored report row that
    # holds the left row's figure, in the planner's order, not the first alone. Here a non-current filing row holds a
    # proxy's 100 million, behind the year's own 10-K row at K25 and a later 10-K's comparative at K26, each holding
    # 100 million, and today's 10-K figure contradicts its original too (104 against 120 million).
    row = {**_state(period_start=date(2025, 1, 1), period_end=date(2025, 12, 31), fiscal_year=2025, value=100e6,
                    accession="KA25", form="10-K/A", filing_id=3, is_latest=False)[1],
           "provenance": {"version": 1, "checks": {"authoritative": {"outcome": "replaced", "original_value": 120e6,
                                                                     "authoritative_value": 100e6}}}}
    backers = {2: {**row, "filing_id": None, "accession": "K25", "form": "10-K", "provenance": None},
               3: {**row, "filing_id": None, "accession": "K26", "form": "10-K", "provenance": None}}
    proxy_row = {**row, "filing_id": None, "form": "DEF 14A", "accession": "P26", "provenance": None}
    payload = _payload({"NetIncomeLoss": {"units": {"USD": [
        _item(104e6, "2025-12-31", start="2025-01-01", accn="K27", fy=2027, filed="2028-02-25")]}}})
    plan = proxy.plan({1: row, **backers, 4: proxy_row}, {}, [], {}, payload)
    [left] = plan.left
    assert (left["fact_id"], left["authority"]) == (1, 104e6)
    assert left["backed_by"] == [{"fact_id": fact_id, "accession": state["accession"], "form": "10-K", "is_latest": False,
                                  "filing_id": None, "source": "companyfacts"} for fact_id, state in backers.items()]


@pytest.mark.parametrize("proxy_rows", [False, True], ids=["current", "behind_the_proxy_row"])
def test_principal_review_5718798403_item_2_a_scale_up_with_no_10k_figure_is_listed_retained_and_never_written(
        monkeypatch, proxy_rows):
    # Principal review 5718798403, item 2, where the payload gives no 10-K figure. FY2021's parse, 90 million, was right;
    # P24, the only filing that tags FY2021's net income, tags it at 90 billion, and the backfill before #1622 replaced
    # the parse with it. The value is a scale-up of the recorded original, and with no 10-K figure the step cannot tell
    # this row from SSS's parse read in units: it leaves it, and the preview lists it in ``scale_up_retained`` (reason
    # ``no_10k_figure``, no gap) with its original and current flag, to be read against the filing. The listing writes, journals and checks nothing; detection never lists a
    # scale-up. Alike with the row FY2021's current figure (only the payload holds P24's) and behind P24's stored row,
    # which set 2 retires with no winner, before and since #1682.
    with _synced_before_and_since_1682(monkeypatch, lambda db, monkeypatch: (
            _only_a_proxy_tags_2021_and_the_10k_was_replaced(db, monkeypatch, "PNF", proxy_rows=proxy_rows,
                                                             parsed=90e6, quoted=90e9))) as states:
        for db, company, payload, filing in states.values():
            row = _filing_row(db, filing)
            check = _check(row)
            assert (row.is_latest, row.source, float(row.value), check["outcome"], check["original_value"]) == (
                not proxy_rows, "companyfacts", 90e9, "replaced", 90e6)
            assert ("net_income", date(2021, 12, 31)) not in svc.extract_authoritative_values(payload)
            stored = repair.snapshot(row)
            plan = _preview(db, company, payload)["proxy"]
            assert row.id not in {e["fact_id"] for e in plan["rows"]}
            assert plan["scale_up_retained"] == [{
                "fact_id": row.id, "action": "scale_up_retained", "concept": "net_income", "fiscal_year": 2021,
                "fiscal_period": "FY", "period_end": "2021-12-31", "accession": filing.accession_number,
                "form": "10-K", "value": "90000000000", "winner_accession": None, "winner_value": None, "gap": None,
                "set": 4, "is_latest": not proxy_rows, "original": 90e6, "authority": None,
                "reason": "no_10k_figure"}]
            assert (plan["filing_rows_restored"], plan["filing_rows_kept"], plan["left_report_backed"],
                    plan["detection_listed"]) == (0, 0, [], [])
            applied = _apply(db, company, payload)["proxy"]
            assert applied["scale_up_retained"] == plan["scale_up_retained"]
            assert applied["retired_without_winner"] == (1 if proxy_rows else 0)
            assert repair.snapshot(_filing_row(db, filing)) == stored
            assert row.id not in {r.fact_id for r in db.query(FinancialFactRevision)}
            found = _detection(db, {company.ticker: payload})
            assert (found[4], found[5]) == ([], [])


def _scaled_up_then_amended(db, monkeypatch, ticker, amended, *, current=False):
    """NNN's true scale-up (a parse in units, 4,092, that P26's figure, the 10-K's own, multiplied up), then a 10-K/A,
    filed after the backfill and listed last, tags FY2025 at ``amended``: today's 10-K figure. ``current``: no sync
    before the fix stored P26's rows, so the filing row is FY2025's current row (a fixed sync stores the later
    reports' FY2025 rows behind it, with no local Filing); otherwise P26's row is current over it."""
    if current:
        company, payload, filing = _mirrored(db, monkeypatch, ticker, parsed=4_092.0, scale=1_000_000, current=True)
    else:
        company, payload, filing = _scaled_up(db, monkeypatch, ticker)
    now = copy.deepcopy(payload)
    _items(now).append(_item(amended, "2025-05-31", start="2024-06-01", accn=_accn(company, "KA25"), fy=2025,
                             form="10-K/A", filed="2026-09-01"))
    return company, now, filing


@pytest.mark.parametrize("amended", [-4_092e6, 0.0], ids=["other_sign_on_the_values_scale", "zero"])
def test_principal_review_5718798403_item_2_a_10k_figure_of_the_other_sign_or_zero_takes_the_ordinary_path(
        monkeypatch, amended):
    # Principal review 5718798403, item 2's guard: a 10-K figure of the other sign at the value's magnitude, or of zero,
    # is on no scale step of the value's, so the scale-up exemption does not stand and set 4's ordinary path decides. A
    # zero figure is read as a figure, as the rest of the step reads it (``_agrees``, ``cross_check_facts``). The
    # recorded original, 4,092, is more than 1% off either, so the company is refused, before #1682 and since.
    with _synced_before_and_since_1682(monkeypatch, lambda db, monkeypatch: _scaled_up_then_amended(
            db, monkeypatch, "PSG", amended)) as states:
        for db, company, payload, filing in states.values():
            row = _filing_row(db, filing)
            assert (row.source, float(row.value), _check(row)["original_value"]) == ("companyfacts", 4_092e6, 4_092.0)
            assert svc.extract_authoritative_values(payload)[("net_income", date(2025, 5, 31))] == amended
            _refuses(db, company, payload, _refusal(db, (row.id, "the 10-K's figure disagrees with the recorded "
                                                                 "original value by more than 1%, and the filing row "
                                                                 "holds neither")))


@pytest.mark.parametrize(("amended", "current", "gap"), [
    (4_092e6 * 1.3, False, 0.769231), (409.2e6, True, 10.0), (4_092e6 * 1.005, True, None),
    (4_092e6 * 0.995, False, None),
], ids=["restated_30pct_not_current", "the_ctos_10x_current", "within_1pct_current", "within_1pct_not_current"])
def test_principal_review_5718798403_item_2_a_retained_scale_up_off_the_10k_figure_is_listed_and_never_written(
        monkeypatch, amended, current, gap):
    # Principal review 5718798403, item 2, as the CTO's review 5719610791 settles it: a true scale-up (NNN's parse in
    # units, 4,092, multiplied up to 4,092 million by P26's figure, the 10-K's own) that a 10-K/A later restated stays as
    # filed: today's 10-K figure is on the value's scale step, so the exemption stands, and set 4 writes nothing. More
    # than 1% off the value, it is listed in ``scale_up_retained`` (reason ``off_10k_figure``, ``gap`` the ratio value /
    # 10-K figure): restated 30%, behind P26's stored row; and the CTO's own example, the current row ten times today's
    # 10-K figure (gap 10). Within 1% of the value, though not equal to it (0.5% either way), the 10-K confirms it and
    # it is not listed. Nothing is written.
    with _synced_before_and_since_1682(monkeypatch, lambda db, monkeypatch: _scaled_up_then_amended(
            db, monkeypatch, "PRT", amended, current=current)) as states:
        for db, company, payload, filing in states.values():
            row = _filing_row(db, filing)
            assert (row.is_latest, row.source, float(row.value), _check(row)["original_value"]) == (
                current, "companyfacts", 4_092e6, 4_092.0)
            assert svc.extract_authoritative_values(payload)[("net_income", date(2025, 5, 31))] == amended
            stored = repair.snapshot(row)
            plan = _preview(db, company, payload)["proxy"]
            assert row.id not in {e["fact_id"] for e in plan["rows"]}
            assert (plan["filing_rows_restored"], plan["filing_rows_kept"]) == (0, 0)
            assert plan["scale_up_retained"] == ([] if gap is None else [{
                "fact_id": row.id, "action": "scale_up_retained", "concept": "net_income", "fiscal_year": 2025,
                "fiscal_period": "FY", "period_end": "2025-05-31", "accession": filing.accession_number,
                "form": "10-K", "value": "4092000000", "winner_accession": None, "winner_value": None,
                "gap": gap, "set": 4, "is_latest": current, "original": 4_092.0, "authority": amended,
                "reason": "off_10k_figure"}])
            assert plan["left_report_backed"] == []
            applied = _apply(db, company, payload)["proxy"]
            assert applied["scale_up_retained"] == plan["scale_up_retained"]
            assert repair.snapshot(_filing_row(db, filing)) == stored
            assert row.id not in {r.fact_id for r in db.query(FinancialFactRevision)}


THIRD_TAG = "NetIncomeLossAvailableToCommonStockholdersBasic"  # a net-income tag the normalizer reads, the authority not


def _retained_at_the_winners_identity(db, monkeypatch, ticker, fy2026, *, tag="NetIncomeLoss"):
    """FedEx's FY2026 10-K, read in units (4,433 for 4,433 million), which the backfill before the fix scaled up to P26's
    figure, 4,433 million; a sync before the fix left P26's row current at FY2026. The FY2026 10-K, the year's only one,
    tags FY2026 at ``fy2026``, on the value's scale step: the year's winner, at the identity the filing row holds.
    ``tag``: the tag every 10-K uses for net income (P26's items stay under NetIncomeLoss); under ``THIRD_TAG``, which
    the normalizer reads and today's authority (``extract_authoritative_values``) does not, the authority gives no
    figure for any year, while the normalizer's winner is still the 10-K's."""
    payload = _fdx_with_proxy({})
    for item in _items(payload):
        if item["form"] == "10-K" and item["end"] == "2026-05-31":
            item["val"] = fy2026
    if tag != "NetIncomeLoss":
        usgaap = payload["facts"]["us-gaap"]
        usgaap[tag] = {"units": {"USD": [item for item in _items(payload) if item["form"] == "10-K"]}}
        usgaap["NetIncomeLoss"]["units"]["USD"] = [item for item in _items(payload) if item["form"] != "10-K"]
    return _cross_checked(db, monkeypatch, ticker, payload, 4_433.0, period=("2026-05-31", "2025-06-01", "2026-07-20"))


@pytest.mark.parametrize(("fy2026", "tag", "listed"), [
    (4_500e6, "NetIncomeLoss", "off_10k_figure"), (44_330e6, "NetIncomeLoss", "off_10k_figure"),
    (4_433e6, "NetIncomeLoss", None), (4_433e6 * 1.005, "NetIncomeLoss", None), (4_433e6, THIRD_TAG, "no_10k_figure"),
], ids=["10k_1.5pct_off", "10k_10x_the_value", "10k_equals_the_value", "10k_0.5pct_off",
        "10k_under_a_tag_the_authority_does_not_read"])
def test_principal_review_5718798403_item_2_set_2_judges_a_retained_scale_up_at_the_winners_identity(
        monkeypatch, fy2026, tag, listed):
    # Principal review 5718798403, item 2, and the review of #1840, rounds 8 and 9: a scale-up set 4 leaves is not out of
    # the step's reach. The FY2026 10-K's row holds the year's 10-K winner's identity behind P26's current row, so set 2,
    # retiring P26's row, would promote it, and its agreement test judges it against the 10-K winner, as any filing row
    # there. More than 1% off the winner (1.5%, or the 10-K at ten times the value), the company is refused on value,
    # naming the row; set 4 had listed it off_10k_figure, and that listing never reaches a preview. Where the winner
    # confirms it (equal, or 0.5% off), set 2 promotes it, nothing is listed, and the apply leaves it current. Where the
    # 10-Ks tag net income only under a tag the authority does not read, the authority gives no figure: set 4 lists the
    # row no_10k_figure, and set 2 promotes it, since it agrees with the normalizer's winner; the listing reaches the
    # preview beside the promotion. Alike before #1682 and since.
    with _synced_before_and_since_1682(monkeypatch, lambda db, monkeypatch: _retained_at_the_winners_identity(
            db, monkeypatch, "PRW", fy2026, tag=tag)) as states:
        for db, company, payload, filing in states.values():
            row = _filing_row(db, filing)
            [p26] = _rows(db, company, concept="net_income", period_end=date(2026, 5, 31), is_latest=True)
            assert (row.is_latest, row.accession, row.source, float(row.value), _check(row)["original_value"],
                    p26.form) == (False, _accn(company, "K26"), "companyfacts", 4_433e6, 4_433.0, "DEF 14A")
            assert svc.extract_authoritative_values(payload).get(("net_income", date(2026, 5, 31))) == (
                fy2026 if tag == "NetIncomeLoss" else None)
            if listed == "off_10k_figure":
                seen = []
                refuse = proxy._Planner.refuse

                def spy(self, row_id, why):
                    seen.append([(e["fact_id"], e["reason"], e["gap"]) for e in self.retained])
                    return refuse(self, row_id, why)

                with monkeypatch.context() as patch:
                    patch.setattr(proxy._Planner, "refuse", spy)
                    _refuses(db, company, payload, _refusal(db, (p26.id, f"the filing row holding the 10-K's identity "
                                                                         f"(fact {row.id}) disagrees with the 10-K on: "
                                                                         "value")))
                assert seen[0] == [(row.id, "off_10k_figure", round(4_433e6 / fy2026, 6))]
                continue
            plan = _preview(db, company, payload)["proxy"]
            assert [(e["fact_id"], e["reason"]) for e in plan["scale_up_retained"]] == (
                [] if listed is None else [(row.id, listed)])
            assert (plan["promoted"], plan["filing_rows_restored"], plan["left_report_backed"]) == (1, 0, [])
            assert [(e["fact_id"], e["winner_accession"], e["winner_value"]) for e in plan["rows"]
                    if e["action"] == "promoted"] == [(p26.id, row.accession, "4433000000")]
            applied = _apply(db, company, payload)["proxy"]
            assert applied["scale_up_retained"] == plan["scale_up_retained"]
            promoted = _filing_row(db, filing)
            assert (promoted.is_latest, promoted.source, float(promoted.value)) == (True, "companyfacts", 4_433e6)
            found = _detection(db, {company.ticker: payload})
            assert (found[2], found[4], found[5]) == ([], [], [])


@pytest.mark.parametrize(("fy2026", "agrees"), [(4_500e6, False), (44_330e6, False), (4_433e6 * 1.005, True)],
                         ids=["10k_1.5pct_off", "10k_10x_the_value", "10k_0.5pct_off"])
def test_a_sync_involving_another_currency_leaves_a_retained_scale_up_behind_the_proxys_row_for_the_step(
        db, monkeypatch, fy2026, agrees):
    # The FY2026 10-K's row holds the year's winner's identity behind P26's current row. A sync that involves
    # another currency (a stored EUR row) leaves it there, as a sync in USD alone does: the upsert skips the
    # stored identity and the newer-filing rule leaves the key as found behind P26's row. So the step judges the
    # row as it would after a sync in USD alone: more than 1% off the winner, it refuses the company on value;
    # 0.5% off, set 2 promotes it.
    company, payload, filing = _retained_at_the_winners_identity(db, monkeypatch, "PRE", fy2026)
    _a_stored_eur_row(db, company)
    _resync(db, company, payload)
    row = _filing_row(db, filing)
    [p26] = _rows(db, company, concept="net_income", period_end=date(2026, 5, 31), is_latest=True)
    assert (p26.form, row.is_latest) == ("DEF 14A", False)
    if agrees:
        plan = _preview(db, company, payload)["proxy"]
        assert [(e["fact_id"], e["winner_accession"]) for e in plan["rows"] if e["action"] == "promoted"] == [
            (p26.id, row.accession)]
        return
    _refuses(db, company, payload, _refusal(db, (p26.id, f"the filing row holding the 10-K's identity (fact {row.id}) "
                                                         "disagrees with the 10-K on: value")))


@pytest.mark.parametrize("witnessed", [True, False], ids=["a_proxy_figure_holds_it", "no_proxy_figure_holds_it"])
def test_a_scale_up_with_no_10k_figure_is_listed_only_where_a_proxy_figure_holds_it(witnessed):
    # A pure test of the planner (review of #1840, round 8): set 4 lists a retained scale-up with no 10-K figure in
    # ``scale_up_retained`` only where a proxy figure holds its value, set 4's own scope. A scale-up no proxy figure holds
    # (here, no proxy row and no proxy item) is outside E211: left as it is, unlisted, and nothing is written.
    row = {**_state(period_start=date(2025, 1, 1), period_end=date(2025, 12, 31), fiscal_year=2025, value=4_092e6,
                    accession="K25", filing_id=3)[1],
           "provenance": {"version": 1, "checks": {"authoritative": {"outcome": "replaced", "original_value": 4_092.0,
                                                                     "authoritative_value": 4_092e6}}}}
    proxy_row = {**row, "filing_id": None, "form": "DEF 14A", "accession": "P26", "is_latest": False,
                 "provenance": None}
    stored = {1: row, **({2: proxy_row} if witnessed else {})}
    updates = {}
    plan = proxy.plan(stored, updates, [], {}, _payload({}))
    assert ("net_income", date(2025, 12, 31)) not in proxy.facts_service.extract_authoritative_values(_payload({}))
    assert [(e["fact_id"], e["reason"], e["gap"]) for e in plan.retained] == (
        [(1, "no_10k_figure", None)] if witnessed else [])
    assert (updates, plan.counts["filing_rows_restored"], plan.left) == ({}, 0, [])
