"""The quarterly repair's proxy step (E211, ``app/services/proxy_fact_repair.py``).

Each shape is planted through the real writers as they ran before #1622: the companyfacts sync
(``_persist_companyfacts_payload``) and the per-filing writer (``process_filing_facts``) with the
authority ``extract_authoritative_values`` read then, under ``_before_the_fix``. Each test asserts its
planted precondition before the repair runs, so a change to a planting path fails loudly instead of
planting the fixed state. A shape no writer produces is planted as a row, and says so.
"""
import copy
import json
import re
from collections import Counter
from contextlib import contextmanager
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
from app.services.facts import currency
from app.services.facts.concepts import HEADLINE_GAAP_TAGS
from scripts import repair_quarterly_facts as cli
from tests.unit.test_companyfacts_ingest import (
    REV_TAG, _FDX_INCOME, _MRK_INCOME, _MRK_PROXY, _MRK_REVENUE, _cny_payload, _fdx_payload, _item,
    _mrk_payload, _payload, _ten_ks,
)

NEVER = re.compile(r"(?!)")  # matches nothing


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(**{**SessionLocal.kw, "bind": engine})()  # autoflush off, as in production
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@contextmanager
def _before_the_fix(monkeypatch):
    """No form is a proxy's, as before #1622. ``is_proxy_form`` reads ``_PROXY_FORM`` when it is called
    (facts/currency.py), so every importer, by module or by name, sees the old rule."""
    with monkeypatch.context() as patch:
        patch.setattr(currency, "_PROXY_FORM", NEVER)
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


def _filing(db, company, accession, period_end, filed):
    filing = Filing(company_id=company.id, accession_number=_accn(company, accession), filing_type="10-K",
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
    svc._persist_companyfacts_payload(db, company, _for(company, _mrk_payload(proxy=False)))
    _old_sync(db, monkeypatch, company, payload)
    svc._persist_companyfacts_payload(db, company, payload)
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
    svc._persist_companyfacts_payload(db, company, payload)
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
    payload = _for(company, _payload({
        REV_TAG: {"units": {"USD": _ten_ks({2021: 900e6, 2022: 1_000e6, 2023: 1_100e6})}},
        "NetIncomeLoss": {"units": {"USD": _ten_ks({2023: 130e6}) + [
            _item(value, f"{year}-12-31", start=f"{year}-01-01", accn="P24", fy=2023, form="DEF 14A",
                  filed="2024-04-20") for year, value in ((2021, 90e6), (2022, 100e6), (2023, 130e6))
        ]}},
        "ProfitLoss": {"units": {"USD": _ten_ks({2022: 110e6})}},
    }))
    _old_sync(db, monkeypatch, company, payload)
    return company, payload


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
    svc._persist_companyfacts_payload(db, company, _without_proxy_items(payload))
    filing = _filing(db, company, "K25", "2025-05-31", "2025-07-20")
    _file(db, monkeypatch, filing, {"net_income": ("2024-06-01", 4_092e6)}, authority_from=payload)
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
    svc._persist_companyfacts_payload(db, company, _without_proxy_items(then))
    filing = _filing(db, company, "K25", "2025-12-31", "2026-02-25")
    _file(db, monkeypatch, filing, {"net_income": ("2025-01-01", 17_000e6)}, authority_from=then)
    _filing_row(db, filing).provenance = None
    db.commit()
    now = copy.deepcopy(then)
    _items(now).append(_item(18_800e6, "2025-12-31", start="2025-01-01", accn=_accn(company, "KA26"), fy=2026,
                             form="10-K/A", filed="2027-06-15"))
    return company, now, filing


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


def test_a_stored_then_demoted_10k_row_is_promoted(db, monkeypatch):
    company, payload = _demoted(db, monkeypatch)
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
    plan = _preview(db, company, payload)
    assert _counts(plan["proxy"]) == {"retired": 5, "inserted": 5, "dependents_recomputed": 4,
                                      "filing_rows_restored": 1, "filing_calculations_reannotated": 1}
    _apply(db, company, payload)
    row = _filing_row(db, filing)
    check = _check(row)
    assert (float(row.value), row.source, row.reconciled, row.is_latest) == (4_092e6, "edgar_xbrl", True, was_latest)
    assert (check["outcome"], check["authoritative_value"], check["original_value"]) == ("confirmed", 4_092e6, 4_092e6)
    assert check["resolved_reasons"] == local["reasons"] and row.provenance["checks"]["local_reconciliation"] == local
    shown = svc.get_filing_fundamentals(db, filing.id)
    assert [p["value"] for c in shown["concepts"] if c["concept"] == "net_income" for p in c["points"]] == [4_092e6]
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
            svc._persist_companyfacts_payload(db, company, payload)
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
    assert stale.source == "derived"
    stale.value += 1  # an unrelated pending correction the same approval applies
    db.commit()
    plan = _preview(db, company, payload)
    assert (plan["proxy"]["other_planned_updates"], plan["proxy"]["other_planned_inserts"]) == (1, 0)
    assert plan["proxy"]["other_updates_by_kind"] == {**dict.fromkeys(proxy.OTHER_KINDS, 0), "value": 1}
    run = "tagged"
    _apply(db, company, payload, run_id=run)
    journal = {r.fact_id: r.calculation_version for r in db.query(FinancialFactRevision).filter_by(run_id=run)}
    assert journal.pop(stale.id) == "quarterly-v2"
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
    from app.services.facts.currency import is_proxy_form

    listed = {2: set(), 3: set(), 4: set(), 5: set()}
    for company in db.query(Company):
        rows = _rows(db, company)
        proxies = [r for r in rows if is_proxy_form(r.form)]
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
                    and any(f'"{r.accession}"' in json.dumps(row.provenance) for r in proxies)):
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


def test_after_the_apply_no_current_row_comes_from_or_is_built_on_a_proxy(db, monkeypatch):
    shapes = {
        "AAA": _unhealed(db, monkeypatch), "BBB": _demoted(db, monkeypatch),
        "CCC": _filed_behind(db, monkeypatch)[:2], "III": _filed_behind(db, monkeypatch, "III", start=None)[:2],
        "EEE": _only_a_proxy_tags_2021(db, monkeypatch), "DDD": _replaced(db, monkeypatch)[:2],
        "MMM": _payload_witness(db, monkeypatch)[:2], "NNN": _scaled_up(db, monkeypatch)[:2],
        "SSS": _scaled_up_where_only_a_proxy_tags(db, monkeypatch)[:2],
        "KKK": _holds_the_10k_figure(db, monkeypatch)[:2], "QQQ": _confirmed(db, monkeypatch)[:2],
    }
    company, payload, filing = _holds_the_10k_figure(db, monkeypatch, "OOO")
    _with_null_provenance(db, filing)
    shapes["OOO"] = (company, payload)
    payloads = {ticker: payload for ticker, (_company, payload) in shapes.items()}
    before = {number: dict(Counter(ticker for ticker, _ in entries))
              for number, entries in _detection(db, payloads).items()}
    assert before == {  # not vacuous: every set lists the planted rows
        2: {"AAA": 6, "BBB": 6, "CCC": 1, "III": 1, "EEE": 3, "DDD": 5, "NNN": 5, "SSS": 3, "KKK": 5, "OOO": 5,
            "QQQ": 5},
        3: {"AAA": 5, "CCC": 5, "III": 5, "EEE": 3, "DDD": 4, "NNN": 5, "SSS": 3, "KKK": 5, "OOO": 5, "QQQ": 5},
        4: {"DDD": 1, "MMM": 1, "KKK": 1, "OOO": 1},
        5: {"QQQ": 1},
    }
    for company, payload in shapes.values():
        _apply(db, company, payload)
    assert _detection(db, payloads) == {2: [], 3: [], 4: [], 5: []}


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
                                      "other_inserts_by_concept": {}}
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
        return _payload(usgaap)

    authority = svc.extract_authoritative_values(payload("10-K"))
    found = proxy.proxy_items(payload("DEF 14A"))
    assert authority and set(found) == {(concept, end.isoformat()) for concept, end in authority}
    assert all(value in found[(concept, end.isoformat())] for (concept, end), value in authority.items())
    assert proxy.proxy_items(payload("10-K")) == {} and svc.extract_authoritative_values(payload("DEF 14A")) == {}



def test_a_proxy_item_without_an_accession_names_no_dependent(db, monkeypatch):
    company = _company(db, "FBK")
    payload = _for(company, _mrk_payload())
    for item in _items(payload):
        if item["form"] == "DEF 14A":
            del item["accn"]  # facts/quarterly.py names such an item's row "companyfacts"
    filing = _filing(db, company, "K25", "2025-12-31", "2026-02-25")
    svc.process_filing_facts(db, filing, authoritative=svc.extract_authoritative_values(payload),
                             standardized={"net_income": {"series": [
                                 {"period": "2025-12-31", "period_start": "2025-01-01", "value": 18_254e6,
                                  "fiscal_period": "FY"}]}})
    _old_sync(db, monkeypatch, company, payload)
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
    _old_sync(db, monkeypatch, company, payload)
    assert {r.unit for r in _rows(db, company, concept="revenue")} == {"USD"}
    [row] = _current_proxy_rows(db, company)
    assert (row.period_end, row.unit) == (date(2023, 3, 31), "USD")
    _refuses(db, company, payload, rf"\(fact {row.id}\): the payload's winner for this period is in CNY; "
                                   "sync the company first")


def test_no_winner_but_a_stored_report_row_refuses(db, monkeypatch):
    company, payload = _only_a_proxy_tags_2021(db, monkeypatch, "RPT")
    filing = _filing(db, company, "K21", "2021-12-31", "2022-02-25")
    _file(db, monkeypatch, filing, {"net_income": ("2021-01-01", 90e6)})
    report = _filing_row(db, filing)
    assert (report.source, report.is_latest) == ("edgar_xbrl", False)
    [row] = [r for r in _current_proxy_rows(db, company) if r.period_end.year == 2021]
    _refuses(db, company, payload, rf"\(fact {row.id}\): a stored report row \(fact {report.id}\) has no fresh "
                                   "winner to agree with")


@pytest.mark.parametrize(("clause", "parsed", "start", "fiscal_year"), [
    ("value", 17_000e6, "2025-01-01", None), ("start", 18_254e6, "2025-02-01", None),
    ("fiscal year", 18_254e6, "2025-01-01", 2024),
])
def test_a_disagreeing_filing_row_refuses(db, monkeypatch, clause, parsed, start, fiscal_year):
    company, payload, filing = _filed_behind(db, monkeypatch, "CCD", parsed=parsed, start=start)
    report = _filing_row(db, filing)
    if fiscal_year is not None:
        report.fiscal_year = fiscal_year  # planted as a label edit
        db.commit()
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
