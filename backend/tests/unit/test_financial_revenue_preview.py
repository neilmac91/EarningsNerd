"""E264 step (2): scripts/financial_revenue_preview.py, the read-only preview of financial companies' revenue rows.

The script reads SEC's current companyfacts once per financial company, computes the deployed rule with the deployed
pure functions and sorts the stored revenue and margin rows of both fact writers into its sets. These cases pin:
- the sets on the 10 committed fixtures (tests/fixtures/companyfacts_fi), the old state written by the real writers (a
  blank-SIC sync, Filing rows for every 10-K and 10-Q, each 10-K's own year through the per-filing writer under the
  old generic authority), then the deployed resync: every set equals a brute-force oracle written here, row by row,
  and the per-company table is pinned (FIXTURE_SETS says where it differs from the design's table, and why);
- synthetic stored states: an empty choice, each per-filing verdict, per-filing rows holding feed identities, legacy
  quarter twins, the deploy-instant boundaries and every company outcome;
- read-only: every statement a SELECT with no lock clause when compiled for PostgreSQL (SQLite drops the clause), no
  write at the cursor, no flush, no lock helper, every table unchanged;
- the guards with genuine accept cases, one SEC read per previewed company, the stops, caps, time budget and window,
  planted credentials that never reach the output, the constants and the output's shape.
"""
import ast
import io
import json
import logging
import re
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Query, Session, sessionmaker
from sqlalchemy.sql.selectable import Select

from app import database
from app.config import settings
from app.models import Base, Company, Filing, FinancialFact
from app.services import facts_service
from app.services.facts import fi_revenue, transport, upsert
from app.services.facts.companyfacts import _collect_companyfacts_concepts, normalize_companyfacts
from app.services.facts.concepts import HEADLINE_GAAP_TAGS
from app.services.facts.currency import admitted_items
from app.services.facts.fiscal_naming import is_proxy_form, own_period_ends
from app.services.facts.reconcile import extract_authoritative_values
from app.services.facts.upsert import process_filing_facts
from app.services.sec_rate_limiter import sec_rate_limiter
from app.utils.sec_urls import build_sec_archive_url
from scripts import financial_revenue_preview as preview

pytestmark = pytest.mark.unit

BACKEND = Path(__file__).resolve().parents[2]
FIXTURES = BACKEND / "tests" / "fixtures" / "companyfacts_fi"
SCRIPT = BACKEND / "scripts" / "financial_revenue_preview.py"
CENSUS = BACKEND.parent / "ops" / "detection" / "financial_revenue_state.sql"
UTC = timezone.utc
OLD = datetime(2026, 10, 31, 12, tzinfo=UTC)  # the generic tuple's writes, while the SIC was blank
NEW = datetime(2026, 11, 2, 12, tzinfo=UTC)  # the deployed resync
TUESDAY = datetime(2026, 11, 3, 12, tzinfo=UTC)
COMMIT = "a" * 40
SECRET = "postgresql://ops:secret@127.0.0.1:5432/earningsnerd"  # gitleaks:allow planted, not a credential
SEC_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json"
RNOIE, FEE = fi_revenue.TOTAL_TAGS[0], fi_revenue.FEE_TAG
SIC = {"AMT": "6798", "AXP": "6199", "BLK": "6211", "IBKR": "6211", "ICE": "6200", "KKR": "6282",
       "MET": "6311", "PNC": "6021", "TROW": "6282", "WFC": "6021"}
# The design's table came from a pure prototype that stored no per-filing rows and never split D and E by tag. Here
# each 10-K's own year also goes through the per-filing writer, which adds F, F_gap and unjudged and changes no feed
# count; and ICE's FY2017 fee history is D_review, not D: ICE's choice keeps the fee tag (Revenues, then the fee),
# and the design sends a difference whose tag the choice keeps to review.
FIXTURE_SETS = {
    "AMT": {"A": 28, "C1": 3, "D": 2, "E": 5, "F_gap": 4},
    "AXP": {"A": 31, "C1": 4, "E": 9, "K": 3, "F_gap": 7},
    "BLK": {},
    "IBKR": {"A": 46, "B": 12, "C1": 68, "C2": 14, "D": 2, "F_gap": 10, "unjudged": 1},
    "ICE": {"A": 1, "D_review": 1, "F": 1},
    "KKR": {"A": 6, "B": 1, "D": 1, "E": 8, "F_gap": 2},
    "MET": {"A": 23, "C1": 2, "C2": 1, "E": 3, "F_gap": 5},
    "PNC": {"K_review": 2, "F": 1},
    "TROW": {"C2_review": 1},
    "WFC": {"C2_review": 2},
}
START_KEYS = {"started", "run_id", "workflow_commit", "dry_run", "execution", "production_image_used",
              "payload_source", "rule", "cohort_size", "blank_sic_companies", "cohort"}
COMPANY_KEYS = {"ticker", "company_id", "sic", "outcome", "choice", "payload_sha256", "payload_newest_filed",
                "counts", "fiscal_years"}
SUMMARY_KEYS = {"summary", "run_id", "outcomes", "totals", "companies_per_set", "sec", "stopped", "refused",
                "refused_tickers", "failed"}
ROW_KEYS = {"fact_id", *preview.REPORT_FIELDS, "rule", "stored_value", "deployed", "gap", "why"}


@pytest.fixture
def factory(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'preview.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", sessions)  # the CLI opens its sessions from here
    yield sessions
    engine.dispose()


@pytest.fixture
def db(factory):
    with factory() as session:
        yield session


@pytest.fixture(autouse=True)
def sec(monkeypatch):
    """SEC's companyfacts, faked by CIK (None is the transport's failed read), the Ops step's pins and a Tuesday."""
    payloads, reads = {}, []

    def read(cik):
        reads.append(cik)
        return payloads.get(cik)

    monkeypatch.setattr(facts_service, "_fetch_companyfacts_sync", read)
    monkeypatch.setattr(sec_rate_limiter, "requests_per_second", 1)
    monkeypatch.setattr(settings, "SEC_DISTRIBUTED_LIMIT_ENABLED", False)
    monkeypatch.setattr(preview, "utcnow", lambda: TUESDAY)
    return SimpleNamespace(payloads=payloads, reads=reads)


def _main(tmp_path, capsys, *argv):
    """Run the CLI: its exit code, its stdout lines and its report."""
    output = tmp_path / "out" / "report.json"
    output.unlink(missing_ok=True)
    code = preview.main(["--output", str(output), "--workflow-commit", COMMIT, *argv])
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    return code, lines, json.loads(output.read_text())


def _company(db, ticker, cik, *, sic="6211", synced=NEW):
    company = Company(cik=f"{cik:010d}", ticker=ticker, name=ticker, sic=sic, facts_synced_at=synced)
    db.add(company)
    db.flush()
    return company


def _filing(db, company, accession, filed, form="10-K"):
    url = build_sec_archive_url(company.cik, accession)
    filing = Filing(company_id=company.id, accession_number=accession, filing_type=form, filing_date=filed,
                    sec_url=url, document_url=f"{url}doc.htm")
    db.add(filing)
    db.flush()
    return filing


def _row(db, company, **fields):
    values = {"concept": "revenue", "unit": "USD", "fiscal_period": "FY", "source": "companyfacts",
              "reconciled": True, "is_latest": True, "created_at": OLD, **fields}
    values["value"] = Decimal(str(values["value"]))
    row = FinancialFact(company_id=company.id, **values)
    db.add(row)
    db.flush()
    return row


def _item(val, end, start, accn, form="10-K", fp="FY", filed=None):
    return {"val": val, "end": end, "start": start, "accn": accn, "form": form, "fp": fp, "fy": int(end[:4]),
            "filed": filed or f"{int(end[:4]) + 1}-02-15"}


def _payload(cik, **tags):
    return {"cik": cik, "facts": {"us-gaap": {tag: {"units": {"USD": items}} for tag, items in tags.items()}}}


def _accn(cik, year, serial=10):
    return f"{cik:010d}-{year % 100:02d}-{serial:06d}"


def _set(report, ticker, name):
    company = next(c for c in report["companies"] if c["ticker"] == ticker)
    return {row["fact_id"]: row for row in company["rows"].get(name, [])}


# --- the committed fixtures, through the real writers ---------------------------------------------------------------

def _own_years(payload):
    """Each 10-K's own year as the per-filing parse read it before E264: the generic tags in order, the fee first."""
    usgaap, found = payload["facts"]["us-gaap"], {}
    for tag in HEADLINE_GAAP_TAGS["revenue"]:
        listed = ((usgaap.get(tag) or {}).get("units") or {}).get("USD") or []
        for (end, klass), start, value, item in admitted_items(listed, instant=False):
            if klass == "FY" and item.get("form") == "10-K":
                found.setdefault(item["accn"], []).append((end, tag, start, value))
    out = {}
    for accn, points in found.items():
        last = max(end for end, *_ in points)
        tag, start, value = next((t, s, v) for tag_ in HEADLINE_GAAP_TAGS["revenue"]
                                 for end, t, s, v in reversed(points) if end == last and t == tag_)
        out[accn] = (last.isoformat(), start.isoformat(), float(value), tag)
    return out


def _seed(db, ticker, payload, sic):
    """The state before step (2): the generic tuple's sync while the SIC was blank, Filing rows for every 10-K and
    10-Q, each 10-K's own year through the per-filing writer under the old generic authority (dated OLD); then the
    deployed resync (its rows dated NEW)."""
    company = Company(cik=f"{int(payload['cik']):010d}", ticker=ticker, name=ticker, sic=None)
    db.add(company)
    db.flush()
    facts_service._persist_companyfacts_payload(db, company, payload)
    filed, forms = {}, {}
    for node in payload["facts"]["us-gaap"].values():
        for item in node["units"]["USD"]:
            if item["form"] in ("10-K", "10-Q", "10-K/A", "10-Q/A"):
                filed[item["accn"]], forms[item["accn"]] = max(filed.get(item["accn"], ""), item["filed"]), item["form"]
    filings = {accn: _filing(db, company, accn, datetime.fromisoformat(day).replace(tzinfo=UTC), forms[accn])
               for accn, day in filed.items()}
    old_authority = extract_authoritative_values(payload, financial=False)  # every backfill's before the deploy
    for accn, (end, start, value, tag) in _own_years(payload).items():
        process_filing_facts(db, filings[accn], authoritative=old_authority, standardized={"revenue": {"series": [
            {"period": end, "period_start": start, "value": value, "raw_tag": f"us-gaap:{tag}", "form": "10-K"}]}})
    db.query(FinancialFact).filter_by(company_id=company.id).update({"created_at": OLD})
    old = {row_id for (row_id,) in db.query(FinancialFact.id).filter_by(company_id=company.id)}
    company.sic = sic
    db.commit()
    facts_service._persist_companyfacts_payload(db, company, payload)
    db.query(FinancialFact).filter(FinancialFact.company_id == company.id, FinancialFact.id.notin_(old)).update(
        {"created_at": NEW}, synchronize_session=False)
    company.facts_synced_at = NEW
    db.commit()
    return company


def _oracle(rows, payload):
    """Every set as {fact id: deployed value} ("missing": identities), by brute force over the stored rows and the
    raw payload. It shares the deployed rule (normalize, the choice, own period ends, the authority) and nothing of
    the script's sorting."""
    facts, meta = normalize_companyfacts(0, payload, financial_sic=True)
    batch = [f for f in facts if f["concept"] in preview.CONCEPTS]
    usgaap = payload["facts"]["us-gaap"]
    choice = fi_revenue.financial_revenue_tags(usgaap, "USD")
    chosen = {f"us-gaap:{tag}" for tag in choice}
    own_ends = own_period_ends(_collect_companyfacts_concepts(usgaap, True)[0])
    authority = extract_authoritative_values(payload, financial=True)
    out = {name: {} for name in preview.SETS}

    def ident(x):
        return x["concept"], x["period_end"], x["fiscal_period"], x["unit"], x["accession"]

    def far(a, b):
        return abs(a - b) > 0.005 * max(abs(a), abs(b))

    def walk(node):
        found = set()
        for op in (node.get("inputs") or []) if isinstance(node, dict) else []:
            if isinstance(op, dict):
                found |= ({op["raw_tag"]} if op.get("concept") == "revenue" and op.get("raw_tag") else set())
                found |= walk(op.get("provenance"))
        return found

    def own(row):
        for tag in choice:
            hit = None
            for item in usgaap.get(tag, {}).get("units", {}).get("USD", []):
                if (item["accn"], item["end"], item.get("start")) == (
                        row["accession"], row["period_end"].isoformat(), row["period_start"].isoformat()) \
                        and not is_proxy_form(item.get("form")):
                    hit = (f"us-gaap:{tag}", float(item["val"]))
            if hit:
                return hit
        return None

    for row in rows:
        feed = row["filing_id"] is None
        calc = row["source"] == "derived" or row["concept"] != "revenue"
        reported = feed and not calc and row["source"] == "companyfacts"
        tags = walk(row["provenance"]) if calc else {row["raw_tag"]} - {None}
        review = bool(tags) and tags <= chosen
        same = [f for f in batch if ident(f) == ident(row)] if feed else []
        if same:
            if (calc or reported) and far(row["value"], same[0]["value"]):
                out["A" if reported else "C1_review" if review else "C1"][row["id"]] = same[0]["value"]
            elif reported and row["raw_tag"] not in chosen:
                out["A_tag_only"][row["id"]] = same[0]["value"]
        elif row["is_latest"]:
            at = [f for f in batch if (f["concept"], f["period_end"], f["unit"]) == (
                row["concept"], row["period_end"], row["unit"]) and (f["fiscal_period"] == row["fiscal_period"] if
                                                                     row["fiscal_period"] else
                                                                     f["fiscal_period"] in ("Q1", "Q2", "Q3", "Q4"))]
            if not at and feed and calc:
                out["C2_review" if review else "C2"][row["id"]] = None
            elif not at and reported:
                out["B_review" if row["raw_tag"] in chosen else "B"][row["id"]] = None
            elif at and ident(at[0]) != ident(row) and far(row["value"], at[0]["value"]):
                out["K_review" if review else "K"][row["id"]] = at[0]["value"]
        elif reported:
            hit = own(row)
            name = "D" if row["fiscal_period"] == "FY" and own_ends.get(row["accession"]) == row["period_end"] else "E"
            if hit is None and row["raw_tag"] not in chosen:
                out[name][row["id"]] = None
            elif hit is not None and far(row["value"], hit[1]):
                out[name if row["raw_tag"] not in chosen else f"{name}_review"][row["id"]] = hit[1]
        if not feed and row["concept"] == "revenue":
            auth = authority.get(("revenue", row["period_end"]))
            if auth is None:
                out["unjudged"][row["id"]] = None
            elif abs(row["value"] - auth) > 0.01 * (abs(auth) or 1.0):
                out["F" if row["source"] == "companyfacts" else "F_gap"][row["id"]] = auth
    held = {ident(row) for row in rows}
    out["missing"] = {ident(f) for f in [*batch, *meta["history"]] if f["concept"] in preview.CONCEPTS} - held
    return out


def test_the_sets_on_the_committed_fixtures_equal_a_brute_force_oracle_row_by_row(db, factory, tmp_path, capsys, sec):
    offline = tmp_path / "companyfacts"
    offline.mkdir()
    payloads = {}
    for path in sorted(FIXTURES.glob("*.json")):
        payloads[path.stem] = json.loads(path.read_text())
        _seed(db, path.stem, payloads[path.stem], SIC[path.stem])
        shutil.copy(path, offline / f"CIK{int(payloads[path.stem]['cik']):010d}.json")

    code, lines, report = _main(tmp_path, capsys, "--companyfacts-dir", str(offline))

    assert code == 0 and sec.reads == []  # offline: no SEC read at all
    db.expire_all()
    assert [(line["ticker"], line["outcome"]) for line in lines[1:-1]] == [(t, "previewed") for t in sorted(SIC)]
    for company in report["companies"]:
        ticker = company["ticker"]
        rows = [{name: getattr(r, name) for name in preview.ROW_FIELDS} | {"value": float(r.value)}
                for r in db.query(FinancialFact).filter(FinancialFact.company_id == company["company_id"],
                                                        FinancialFact.concept.in_(preview.CONCEPTS))]
        expected = _oracle(rows, payloads[ticker])
        for name in preview.SETS:
            got = company["rows"].get(name, [])
            if name == "missing":
                assert {(r["concept"], date.fromisoformat(r["period_end"]), r["fiscal_period"], r["unit"],
                         r["accession"]) for r in got} == expected[name], (ticker, name)
            else:
                assert {r["fact_id"]: (r["deployed"] or {}).get("value") for r in got} == expected[name], (ticker, name)
        assert {k: v for k, v in company["counts"].items() if v} == FIXTURE_SETS[ticker], ticker
        # The deployed resync's own rows agree with the batch: every listed row was stored before the deploy.
        assert {r["rule"] for listed in company["rows"].values() for r in listed} <= {"old"}, ticker
    ice = _set(report, "ICE", "D_review")
    assert [(r["fiscal_year"], r["stored_value"], r["deployed"]["tag"], r["deployed"]["value"]) for r in ice.values()] \
        == [(2017, 4_629_000_000.0, "us-gaap:Revenues", 5_834_000_000.0)]
    assert {r["fiscal_year"] for r in _set(report, "PNC", "K_review").values()} == {2019}
    assert all("newer_filing" in r["why"] for r in _set(report, "AXP", "K").values())
    assert report["summary"]["totals"] == {name: sum(FIXTURE_SETS[t].get(name, 0) for t in SIC) for name in preview.SETS}


# --- synthetic stored states ------------------------------------------------------------------------------------------

def test_an_empty_choice_leaves_every_current_feed_revenue_row_in_b_and_its_margins_in_c2(db, tmp_path, capsys, sec):
    """SYF's shape: no total, and a fee tag with interest income beside it, so the deployed rule reads no revenue."""
    accns = {year: _accn(7, year + 1) for year in (2023, 2024)}
    payload = _payload(7, **{
        FEE: [_item(50e6 + year, f"{year}-12-31", f"{year}-01-01", accn) for year, accn in accns.items()],
        "InterestAndDividendIncomeOperating": [_item(400e6, f"{y}-12-31", f"{y}-01-01", a) for y, a in accns.items()],
        "NetIncomeLoss": [_item(30e6, f"{y}-12-31", f"{y}-01-01", a) for y, a in accns.items()],
    })
    company = _company(db, "SYF", 7, sic=None, synced=None)
    facts_service._persist_companyfacts_payload(db, company, payload)  # the generic tuple reads the fee line
    company.sic, company.facts_synced_at = "6141", NEW
    db.commit()
    facts_service._persist_companyfacts_payload(db, company, payload)  # the deployed rule writes no revenue
    company.facts_synced_at = NEW
    db.commit()
    sec.payloads[company.cik] = payload

    code, lines, report = _main(tmp_path, capsys, "--tickers", "SYF")

    assert code == 0 and lines[1]["choice"] == []
    assert {r["fiscal_year"]: r["raw_tag"] for r in _set(report, "SYF", "B").values()} == {
        2023: f"us-gaap:{FEE}", 2024: f"us-gaap:{FEE}"}
    assert sorted((r["concept"], r["why"]) for r in _set(report, "SYF", "C2").values()) == [
        ("net_margin", ["filing_unreachable", "lineage_outside_choice"])] * 2
    assert {k: v for k, v in lines[1]["counts"].items() if v} == {"B": 2, "C2": 2}


def _total_and_fee(cik):
    """A total beside a smaller fee line, one 10-K a year for FY2021-24: the choice is the total alone."""
    years = {2021: (100, 60), 2022: (110, 65), 2023: (120, 70), 2024: (130, 75)}
    return _payload(cik, **{
        RNOIE: [_item(t * 1e6, f"{y}-12-31", f"{y}-01-01", _accn(cik, y + 1)) for y, (t, _f) in years.items()],
        FEE: [_item(f * 1e6, f"{y}-12-31", f"{y}-01-01", _accn(cik, y + 1)) for y, (_t, f) in years.items()],
    })


def test_each_per_filing_verdict_and_the_feed_identities_per_filing_rows_hold(db, tmp_path, capsys, sec):
    """F whatever the provenance (NULL before 2026-10-10), F_gap for a row the old authority confirmed or enrichment
    wrote unchecked, unjudged with no annual authority (a 10-Q), and nothing within 1%. Per-filing rows at the
    batch's identities hold them: neither A (a feed set) nor missing, and the rule splits at the deploy instant."""
    company = _company(db, "TOT", 11)
    sec.payloads[company.cik] = _total_and_fee(11)
    filings = {y: _filing(db, company, _accn(11, y + 1), datetime(y + 1, 2, 15, tzinfo=UTC)) for y in range(2021, 2025)}
    quarterly = _filing(db, company, _accn(11, 24, 20), datetime(2024, 5, 1, tzinfo=UTC), "10-Q")
    amended = _filing(db, company, _accn(11, 24, 30), datetime(2024, 6, 1, tzinfo=UTC), "10-K/A")

    def per_filing(year, value, filing, **fields):
        return _row(db, company, filing_id=filing.id, accession=filing.accession_number, fiscal_year=year,
                    period_start=date(year, 1, 1), period_end=date(year, 12, 31), value=value, **fields)

    confirmed = {"checks": {"authoritative": {"outcome": "confirmed", "original_value": 65e6}}}
    rows = {
        "F_null": per_filing(2021, 60e6, filings[2021], provenance=None, raw_tag="us-gaap:Revenues"),
        "F_gap_confirmed": per_filing(2022, 65e6, filings[2022], source="edgar_xbrl", provenance=confirmed),
        "F_gap_unchecked": per_filing(2023, 70e6, filings[2023], source="edgar_xbrl", provenance={"method": "reported"}),
        "F_new": per_filing(2024, 75e6, filings[2024], created_at=NEW),
        "within": per_filing(2023, 120.3e6, amended, source="edgar_xbrl"),
        "quarter": _row(db, company, filing_id=quarterly.id, accession=quarterly.accession_number, fiscal_year=2024,
                        fiscal_period=None, period_end=date(2024, 3, 31), value=30e6, source="edgar_xbrl",
                        raw_tag="us-gaap:Revenues", is_latest=False),
    }
    db.commit()

    code, _lines, report = _main(tmp_path, capsys, "--tickers", "TOT")

    assert code == 0
    ids = {name: row.id for name, row in rows.items()}
    assert {i: (r["deployed"]["value"], r["rule"]) for i, r in _set(report, "TOT", "F").items()} == {
        ids["F_null"]: (100e6, "old"), ids["F_new"]: (130e6, "new")}
    assert set(_set(report, "TOT", "F_gap")) == {ids["F_gap_confirmed"], ids["F_gap_unchecked"]}
    assert set(_set(report, "TOT", "unjudged")) == {ids["quarter"]}
    listed = {i for name in preview.SETS for i in _set(report, "TOT", name)}
    assert ids["within"] not in listed and not _set(report, "TOT", "A") and not _set(report, "TOT", "missing")
    whys = {i: r["why"] for name in ("F", "F_gap", "unjudged") for i, r in _set(report, "TOT", name).items()}
    assert all("holds_feed_identity" in whys[ids[name]] and "probe_replaced" in whys[ids[name]]
               for name in ("F_null", "F_gap_confirmed", "F_gap_unchecked", "F_new"))
    assert whys[ids["quarter"]] == ["filing_reachable", "lineage_outside_choice", "probe_no_authority"]


def _quarterly(cik):
    """A total for FY2023 (its 10-K) and Q1 2024 (its 10-Q): the choice is that total alone."""
    return _payload(cik, **{RNOIE: [_item(400e6, "2023-12-31", "2023-01-01", _accn(cik, 24)),
                                    _item(100e6, "2024-03-31", "2024-01-01", _accn(cik, 24, 5), "10-Q", "Q1",
                                          "2024-05-01")]})


def test_a_same_value_row_outside_the_choice_a_gap_past_half_a_percent_and_a_calculation_with_no_lineage(
        db, tmp_path, capsys, sec):
    """The sync skips a row stored at the batch's own identity: the same value under a tag the choice leaves out is
    A_tag_only (reported, never for cleanup), and a 0.7% gap is A (the feed's tolerance is 0.5%, not the
    cross-check's 1%). A calculation stored before 2026-10-10 records no lineage and stays C2, never C2_review."""
    company = _company(db, "QTA", 17)
    tag_only = _row(db, company, fiscal_year=2023, period_start=date(2023, 1, 1), period_end=date(2023, 12, 31),
                    value=400e6, accession=_accn(17, 24), raw_tag=f"us-gaap:{FEE}")
    near = _row(db, company, fiscal_year=2024, fiscal_period="Q1", period_start=date(2024, 1, 1),
                period_end=date(2024, 3, 31), value=100.7e6, accession=_accn(17, 24, 5), raw_tag=f"us-gaap:{RNOIE}")
    facts_service._persist_companyfacts_payload(db, company, _quarterly(17))  # both identities are skipped
    company.facts_synced_at = NEW
    legacy = _row(db, company, source="derived", raw_tag=None, provenance=None, fiscal_year=2023, fiscal_period="Q4",
                  period_start=date(2023, 10, 1), period_end=date(2023, 12, 31), value=110e6, accession=_accn(17, 24))
    db.commit()
    sec.payloads[company.cik] = _quarterly(17)

    code, _lines, report = _main(tmp_path, capsys, "--tickers", "QTA")

    assert code == 0
    assert {i: r["deployed"]["value"] for i, r in _set(report, "QTA", "A_tag_only").items()} == {tag_only.id: 400e6}
    assert {i: r["gap"] for i, r in _set(report, "QTA", "A").items()} == {near.id: round(0.7e6 / 100.7e6, 6)}
    assert {i: r["why"] for i, r in _set(report, "QTA", "C2").items()} == {
        legacy.id: ["filing_unreachable", "lineage_legacy"]}
    assert not _set(report, "QTA", "C2_review") and not _set(report, "QTA", "missing")


def test_a_stale_current_row_at_a_key_the_batch_fills_is_k_from_either_writer_and_as_a_legacy_quarter_twin(
        db, tmp_path, capsys, sec):
    """The writer demotes only when it inserts: where the batch's identity was already stored, a current row of
    either writer at the key stays current, and so does a quarter twin stored with no fiscal period (the D1 rule)."""
    q1, payload = _accn(13, 24, 5), _quarterly(13)
    company = _company(db, "QTR", 13)
    facts_service._persist_companyfacts_payload(db, company, payload)
    company.facts_synced_at = NEW
    sec.payloads[company.cik] = payload
    other = _filing(db, company, _accn(13, 24, 9), datetime(2024, 5, 2, tzinfo=UTC), "10-Q")

    def quarter(value, **fields):
        return _row(db, company, fiscal_year=2024, period_start=date(2024, 1, 1), period_end=date(2024, 3, 31),
                    value=value, **fields)

    twin = quarter(130e6, fiscal_period=None, accession=_accn(13, 24, 7), raw_tag=f"us-gaap:{FEE}")
    near_twin = quarter(100.2e6, fiscal_period=None, accession=_accn(13, 24, 8), raw_tag=f"us-gaap:{RNOIE}")
    per_filing = quarter(80e6, fiscal_period="Q1", filing_id=other.id, accession=other.accession_number,
                         source="edgar_xbrl", raw_tag=f"us-gaap:{RNOIE}")
    db.commit()

    code, _lines, report = _main(tmp_path, capsys, "--tickers", "QTR")

    assert code == 0
    assert {i: (r["deployed"]["accession"], r["why"]) for i, r in _set(report, "QTR", "K").items()} == {
        twin.id: (q1, ["filing_unreachable", "lineage_outside_choice"])}
    assert {i: r["deployed"]["value"] for i, r in _set(report, "QTR", "K_review").items()} == {per_filing.id: 100e6}
    assert near_twin.id not in {i for name in preview.SETS for i in _set(report, "QTR", name)}


def test_the_deploy_instant_splits_synced_companies_and_the_rule_of_a_row(db, tmp_path, capsys, sec):
    at, before = preview.E264_DEPLOYED_AT, preview.E264_DEPLOYED_AT - timedelta(seconds=1)
    for ticker, cik, synced in (("ATI", 21, at), ("BEF", 22, before)):
        company = _company(db, ticker, cik, synced=synced)
        sec.payloads[company.cik] = _total_and_fee(cik)
    db.commit()

    code, lines, _report = _main(tmp_path, capsys)

    assert code == 0 and [(line["ticker"], line["outcome"]) for line in lines[1:-1]] == [
        ("ATI", "previewed"), ("BEF", "pending_resync")]
    assert sec.reads == ["0000000021"]
    entry = {"id": 1, **{name: None for name in preview.REPORT_FIELDS}, "value": 1.0}
    assert [preview._entry({**entry, "created_at": created}, None, set())["rule"]
            for created in (at, before, None, at.replace(tzinfo=None))] == ["new", "old", "old", "new"]


# --- read-only, every outcome and public safety ----------------------------------------------------------------------

def _tables(engine):
    with engine.connect() as connection:
        return {table.name: sorted(map(tuple, connection.execute(select(table)).all()), key=repr)
                for table in Base.metadata.sorted_tables}


def test_a_run_reaching_every_outcome_reads_only_and_prints_closed_classes(db, factory, tmp_path, capsys, sec,
                                                                          monkeypatch, caplog):
    blk = json.loads((FIXTURES / "BLK.json").read_text())
    previewed = _seed(db, "AAA", blk, "6211")
    sec.payloads[previewed.cik] = blk
    _company(db, "BBB", 2, synced=OLD)
    _company(db, "CCC", 3, sic="7372")
    named = {ticker: _company(db, ticker, cik) for cik, ticker in enumerate(
        ("DDD", "EEE", "FFF", "GGG", "HHH", "III", "JJJ", "KKK", "LLL"), start=4)}
    item = _item(1e6, "2024-12-31", "2024-01-01", _accn(4, 25))
    sec.payloads.update({
        named["DDD"].cik: _payload(99, Revenues=[item]),  # another company's payload
        named["EEE"].cik: {"cik": 5, "facts": {"ifrs-full": {"Revenue": {"units": {"EUR": [item]}}}}},
        named["FFF"].cik: {"cik": 6, "facts": {"us-gaap": {"Revenues": {"units": {"EUR": [item]}}}}},
        named["GGG"].cik: _payload(7, Revenues=[item]),
        named["HHH"].cik: _payload(8, Revenues=[item]),
    })
    db.commit()
    read_company, deployed_rule = preview.read_company, preview.deployed_rule

    def failing_read(session, company_id, accessions):
        if company_id == named["GGG"].id:
            raise OperationalError(SECRET, {}, Exception(SEC_URL))
        return read_company(session, company_id, accessions)

    def failing_rule(member, *args):
        if member.ticker == "HHH":
            raise RuntimeError(f"{SECRET} {SEC_URL}")
        return deployed_rule(member, *args)

    monkeypatch.setattr(preview, "read_company", failing_read)
    monkeypatch.setattr(preview, "deployed_rule", failing_rule)
    locks = []
    for owner in (facts_service, upsert):
        monkeypatch.setattr(owner, "_lock_fact_companies", lambda *a, **k: locks.append(a))
    for owner in (Query, Select):
        monkeypatch.setattr(owner, "with_for_update", lambda *a, **k: locks.append(a))
    engine = factory.kw["bind"]
    before = _tables(engine)
    orm, cursor, flushes = [], [], []

    def on_orm(state):
        orm.append(str(state.statement.compile(dialect=postgresql.dialect())))

    def on_cursor(_conn, _cur, statement, *_args):
        cursor.append(statement)

    def on_flush(*args):
        flushes.append(args)

    event.listen(Session, "do_orm_execute", on_orm)
    event.listen(engine, "before_cursor_execute", on_cursor)
    event.listen(Session, "before_flush", on_flush)
    try:
        with caplog.at_level(logging.DEBUG):
            code, lines, report = _main(tmp_path, capsys, "--tickers", ",".join(["aaa", "BBB", "CCC", *named]))
    finally:
        event.remove(Session, "do_orm_execute", on_orm)
        event.remove(engine, "before_cursor_execute", on_cursor)
        event.remove(Session, "before_flush", on_flush)
    err = capsys.readouterr().err

    assert code == 1
    assert [(line["ticker"], line["outcome"]) for line in lines[1:-1]] == [
        ("AAA", "previewed"), ("BBB", "pending_resync"), ("CCC", "not_financial"), ("DDD", "payload_rejected"),
        ("EEE", "unsupported_ifrs"), ("FFF", "another_currency"), ("GGG", "database_error"),
        ("HHH", "internal_error"), ("III", "fetch_failed"), ("JJJ", "fetch_failed"), ("KKK", "fetch_failed"),
        ("LLL", "not_run")]
    assert set(report["summary"]["outcomes"]) == set(preview.OUTCOMES) and all(report["summary"]["outcomes"].values())
    assert (report["summary"]["stopped"], report["summary"]["failed"]) == ("failed_fetches", 6)
    assert sec.reads == [previewed.cik, *(named[t].cik for t in ("DDD", "EEE", "FFF", "GGG", "HHH", "III", "JJJ", "KKK"))]
    # Read-only: SELECTs alone, no lock clause where PostgreSQL would render one, nothing written, flushed or locked.
    assert orm and all(statement.lstrip().upper().startswith("SELECT") for statement in orm)
    assert not [s for s in orm if re.search(r"\bFOR\s+(UPDATE|SHARE|NO\s+KEY\s+UPDATE|KEY\s+SHARE)\b", s, re.I)]
    assert not [s for s in cursor if re.match(r"\s*(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE)\b", s, re.I)]
    assert (flushes, locks) == ([], []) and _tables(engine) == before
    # The cohort is chosen in Python (_is_financial_sic): its one read of companies filters nothing.
    assert [s for s in orm if "FROM companies" in s and "WHERE" in s] == []
    # Public: closed classes only, and app log records are withheld while the run lasts.
    text = (tmp_path / "out" / "report.json").read_text() + json.dumps(lines) + err + caplog.text
    assert SECRET not in text and "secret" not in text and SEC_URL not in text


def test_a_failed_reads_transport_warning_never_reaches_a_log_record(db, tmp_path, capsys, sec, monkeypatch, caplog):
    """The transport logs a failed read's exception text; the script withholds app log records while it runs."""
    company = _company(db, "LOG", 31)
    db.commit()

    def read(cik):
        transport.logger.warning("companyfacts sync fetch failed for CIK %s: %s", cik, SECRET)
        return None

    monkeypatch.setattr(facts_service, "_fetch_companyfacts_sync", read)
    with caplog.at_level(logging.DEBUG):
        code, lines, _report = _main(tmp_path, capsys, "--tickers", company.ticker)

    assert code == 1 and lines[1]["outcome"] == "fetch_failed"
    assert caplog.records == [] and logging.root.manager.disable == logging.NOTSET  # restored after the run


# --- guards -------------------------------------------------------------------------------------------------------------

class _PostgresSession:
    """A session reporting PostgreSQL's dialect and a transaction_read_only setting; it serves no other read."""

    def __init__(self, setting):
        self.setting, self.statements = setting, []

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def execute(self, statement):
        compiled = statement.compile(dialect=postgresql.dialect())
        self.statements.append((str(compiled), dict(compiled.params)))
        return SimpleNamespace(scalar=lambda: self.setting)

    def query(self, *_entities):
        raise AssertionError("read before the session's guard passed")

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def test_the_session_guard_accepts_a_read_only_postgresql_session_and_refuses_any_other(db):
    accepting = _PostgresSession("on")
    preview.check_read_only(accepting)  # the genuine accept case: PGOPTIONS' default_transaction_read_only=on
    assert [list(params.values()) for _sql, params in accepting.statements] == [["transaction_read_only"]]
    assert accepting.statements[0][0].startswith("SELECT current_setting(")
    for setting in ("off", None):
        with pytest.raises(preview.Refused) as refused:
            preview.check_read_only(_PostgresSession(setting))
        assert refused.value.reason == "session_not_read_only"
    preview.check_read_only(db)  # SQLite has no such setting: nothing to read


def test_the_sec_guards_accept_the_ops_pins_and_refuse_the_distributed_gate_or_another_rate(monkeypatch):
    preview.check_sec_guards()  # the Ops step's pins: limiter at 1, no distributed gate
    monkeypatch.setattr(sec_rate_limiter, "requests_per_second", 10)
    with pytest.raises(preview.Refused, match="limiter_not_one_per_second"):
        preview.check_sec_guards()
    monkeypatch.setattr(sec_rate_limiter, "requests_per_second", 1)
    monkeypatch.setattr(settings, "SEC_DISTRIBUTED_LIMIT_ENABLED", True)
    with pytest.raises(preview.Refused, match="distributed_limit_on"):
        preview.check_sec_guards()


@pytest.mark.parametrize("setting,rate,distributed,refused", [
    ("off", 1, False, "session_not_read_only"), ("on", 10, False, "limiter_not_one_per_second"),
    ("on", 1, True, "distributed_limit_on"),
])
def test_a_run_refuses_before_any_read_unless_every_guard_holds(tmp_path, monkeypatch, sec, setting, rate,
                                                                distributed, refused):
    monkeypatch.setattr(sec_rate_limiter, "requests_per_second", rate)
    monkeypatch.setattr(settings, "SEC_DISTRIBUTED_LIMIT_ENABLED", distributed)
    lines = []
    args = SimpleNamespace(tickers="", workflow_commit=COMMIT, companyfacts_dir=None)
    report = preview.run(args, lines.append, session_factory=lambda: _PostgresSession(setting))
    assert (lines, report["summary"]["refused"], sec.reads) == ([], refused, [])


def test_a_company_session_that_is_not_read_only_stops_the_run(db, factory, sec):
    for ticker, cik in (("ONE", 41), ("TWO", 42)):
        sec.payloads[_company(db, ticker, cik).cik] = _total_and_fee(cik)
    db.commit()
    opened = []

    def sessions():
        opened.append(1)
        return factory() if len(opened) == 1 else _PostgresSession("off")

    lines = []
    args = SimpleNamespace(tickers="", workflow_commit=COMMIT, companyfacts_dir=None)
    report = preview.run(args, lines.append, session_factory=sessions)
    assert [line.get("outcome") for line in lines[1:]] == ["not_run", "not_run"]
    assert report["summary"]["stopped"] == "session_not_read_only" and sec.reads == ["0000000041"]


# --- SEC reads: count, stops, caps, the time budget and the window -----------------------------------------------------

def test_the_script_holds_no_http_client_no_writer_and_no_apply_mode():
    tree = ast.parse(SCRIPT.read_text())
    imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                for alias in node.names} | {node.module.split(".")[0] for node in ast.walk(tree)
                                             if isinstance(node, ast.ImportFrom) and node.module}
    assert not imported & {"httpx", "requests", "urllib", "urllib3", "aiohttp", "http", "socket"}
    names = {getattr(node, "id", getattr(node, "attr", None)) for node in ast.walk(tree)} | {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names}
    assert not names & {"upsert_facts", "upsert_facts_bulk", "process_filing_facts", "_persist_companyfacts_payload",
                        "protected_rows", "demote_convenience_rows", "insert_history_rows", "_lock_fact_companies",
                        "with_for_update", "track_job", "backfill_facts", "commit", "flush", "merge",
                        "bulk_save_objects", "bulk_insert_mappings"}
    assert "--apply" not in SCRIPT.read_text()


def _companies(db, sec, count, *, synced=NEW, start=100):
    out = []
    for cik in range(start, start + count):
        company = _company(db, f"C{cik}", cik, synced=synced)
        sec.payloads[company.cik] = _total_and_fee(cik)
        out.append(company)
    db.commit()
    return out


def test_three_failed_reads_in_a_row_stop_the_run(db, tmp_path, capsys, sec):
    companies = _companies(db, sec, 4)
    sec.payloads.clear()

    code, lines, report = _main(tmp_path, capsys)

    assert code == 1 and [line["outcome"] for line in lines[1:-1]] == ["fetch_failed"] * 3 + ["not_run"]
    assert report["summary"]["stopped"] == "failed_fetches" and sec.reads == [c.cik for c in companies[:3]]


def test_three_rate_limit_hits_stop_the_run_and_the_summary_counts_them(db, tmp_path, capsys, sec, monkeypatch):
    companies = _companies(db, sec, 5)
    read = facts_service._fetch_companyfacts_sync

    def throttled(cik):
        sec_rate_limiter._rate_limit_hits += 1
        sec_rate_limiter._total_requests += 2
        return read(cik)

    monkeypatch.setattr(sec_rate_limiter, "_rate_limit_hits", sec_rate_limiter._rate_limit_hits)
    monkeypatch.setattr(sec_rate_limiter, "_total_requests", sec_rate_limiter._total_requests)
    monkeypatch.setattr(facts_service, "_fetch_companyfacts_sync", throttled)

    code, lines, report = _main(tmp_path, capsys)

    assert code == 1 and [line["outcome"] for line in lines[1:-1]] == ["previewed"] * 3 + ["not_run"] * 2
    assert report["summary"]["stopped"] == "rate_limit" and len(sec.reads) == 3 < len(companies)
    assert report["summary"]["sec"] == {"requests": 6, "rate_limit_hits": 3}


def test_the_time_budget_stops_before_the_next_read_and_the_run_still_ends_with_its_summary(db, tmp_path, capsys,
                                                                                            sec, monkeypatch):
    _companies(db, sec, 4)
    times = iter(TUESDAY + timedelta(seconds=s) for s in (0, 100, preview.TIME_BUDGET_SECONDS - 1,
                                                          preview.TIME_BUDGET_SECONDS, 99_999))
    monkeypatch.setattr(preview, "utcnow", lambda: next(times))

    code, lines, report = _main(tmp_path, capsys)

    assert code == 1 and [line["outcome"] for line in lines[1:-1]] == ["previewed"] * 2 + ["not_run"] * 2
    assert lines[-1] == report["summary"] and report["summary"]["stopped"] == "time_budget" and len(sec.reads) == 2
    assert preview.TIME_BUDGET_SECONDS == 3000  # inside the Ops step's 60 minutes, with room for the last company


@pytest.mark.parametrize("tickers,refused,named", [
    (",".join(f"T{i}" for i in range(51)), "too_many_tickers", []), ("A,,B", "invalid_tickers", []),
    ("A;B", "invalid_tickers", []), ("C100,NOPE", "unknown_tickers", ["NOPE"]),
])
def test_a_ticker_list_is_refused_before_any_sec_read(db, tmp_path, capsys, sec, tickers, refused, named):
    _companies(db, sec, 1)

    code, lines, report = _main(tmp_path, capsys, "--tickers", tickers)

    assert code == 1 and (report["summary"]["refused"], report["summary"]["refused_tickers"]) == (refused, named)
    assert sec.reads == [] and report["companies"] == [] and lines == [report["summary"]]


def test_more_companies_to_read_than_the_cap_are_refused_with_their_list_and_pending_ones_cost_nothing(
        db, tmp_path, capsys, sec, monkeypatch):
    to_read = _companies(db, sec, 3)
    _companies(db, sec, 2, synced=OLD, start=200)
    monkeypatch.setattr(preview, "MAX_PREVIEWED", 2)

    code, lines, report = _main(tmp_path, capsys)

    assert code == 1 and sec.reads == [] and lines[0]["cohort_size"] == 5
    assert report["summary"]["refused"] == "cohort_over_cap"
    assert report["summary"]["refused_tickers"] == [c.ticker for c in to_read]
    monkeypatch.setattr(preview, "MAX_PREVIEWED", 3)
    code, lines, report = _main(tmp_path, capsys)
    assert code == 0 and len(sec.reads) == 3 and report["summary"]["outcomes"]["pending_resync"] == 2
    assert (preview.MAX_TICKERS, preview.STOP_AFTER_FAILED_FETCHES, preview.STOP_AFTER_RATE_LIMIT_HITS) == (50, 3, 3)


@pytest.mark.parametrize("now,refused", [
    (datetime(2026, 11, 9, 6, 0, tzinfo=UTC), True), (datetime(2026, 11, 9, 8, 29, 59, tzinfo=UTC), True),
    (datetime(2026, 11, 9, 5, 59, 59, tzinfo=UTC), False), (datetime(2026, 11, 9, 8, 30, tzinfo=UTC), False),
    (datetime(2026, 11, 10, 7, 0, tzinfo=UTC), False),
])
def test_sec_reads_are_refused_in_mondays_scheduled_peak(db, tmp_path, capsys, sec, monkeypatch, now, refused):
    assert now.weekday() == (0 if now.day == 9 else 1)
    _companies(db, sec, 1)
    monkeypatch.setattr(preview, "utcnow", lambda: now)

    code, _lines, report = _main(tmp_path, capsys)

    assert (report["summary"]["refused"], code, len(sec.reads)) == (("sec_window", 1, 0) if refused else (None, 0, 1))


def test_an_offline_run_reads_no_sec_even_in_the_peak_and_reads_each_payload_from_its_file(db, tmp_path, capsys, sec,
                                                                                          monkeypatch):
    companies = _companies(db, sec, 3)
    offline = tmp_path / "offline"
    offline.mkdir()
    (offline / f"CIK{int(companies[0].cik):010d}.json").write_text(json.dumps(_total_and_fee(100)))
    (offline / f"CIK{int(companies[1].cik):010d}.json").write_text("{not json")
    monkeypatch.setattr(preview, "utcnow", lambda: datetime(2026, 11, 9, 7, tzinfo=UTC))

    code, lines, report = _main(tmp_path, capsys, "--companyfacts-dir", str(offline))

    assert code == 1 and sec.reads == [] and lines[0]["payload_source"] == "offline_directory"
    assert [line["outcome"] for line in lines[1:-1]] == ["previewed", "payload_rejected", "fetch_failed"]


# --- constants and the output's shape ----------------------------------------------------------------------------------

def test_the_deploy_instant_is_the_census_literal_and_the_script_names_no_tag_or_sic():
    literal = re.search(r"'([^']+)'::timestamptz AS e264_deployed", CENSUS.read_text()).group(1)
    assert preview.E264_DEPLOYED_AT == datetime.fromisoformat(literal + ":00")
    assert (preview.FEED_TOLERANCE, preview.CONCEPTS) == (0.005, ("revenue", "net_margin", "operating_margin",
                                                                  "gross_margin"))
    tree = ast.parse(SCRIPT.read_text())
    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and node.body
                  and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)}
    constants = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and id(node) not in docstrings]
    tags = {*fi_revenue.TOTAL_TAGS, fi_revenue.FEE_TAG, *fi_revenue.NON_606_TAGS, *HEADLINE_GAAP_TAGS["revenue"]}
    assert [c for c in constants if isinstance(c, str) and any(tag in c for tag in tags)] == []
    assert [c for c in constants if str(c) in ("6000", "6799")] == []
    header = ast.get_docstring(tree)
    assert "tests/unit/test_financial_revenue_preview.py" in header and "Retire: the records PR that closes E264" in header


def test_the_start_line_is_flushed_before_the_first_read_and_each_line_has_its_exact_keys(db, tmp_path, sec,
                                                                                          monkeypatch):
    class Stdout(io.StringIO):
        flushed = ""

        def flush(self):
            self.flushed = self.getvalue()

    out = Stdout()
    monkeypatch.setattr(sys, "stdout", out)
    _companies(db, sec, 1)
    _companies(db, sec, 1, synced=None, start=300)
    seen = []
    read = facts_service._fetch_companyfacts_sync
    monkeypatch.setattr(facts_service, "_fetch_companyfacts_sync", lambda cik: seen.append(out.flushed) or read(cik))
    output = tmp_path / "report.json"

    code = preview.main(["--output", str(output), "--workflow-commit", COMMIT])

    start, *companies, summary = [json.loads(line) for line in out.getvalue().splitlines()]
    assert code == 0 and json.loads(seen[0].splitlines()[0]) == start  # printed and flushed before the read
    assert set(start) == START_KEYS and start["dry_run"] and not start["production_image_used"]
    assert start["rule"] == {"e264_deployed_at": "2026-11-01T14:07:03Z", "feed_tolerance": 0.005,
                             "per_filing": "cross_check_facts (1%)"}
    assert (start["workflow_commit"], start["execution"]) == (COMMIT, "github_actions_runner")
    assert all(set(line) == COMPANY_KEYS for line in companies) and set(summary) == SUMMARY_KEYS
    assert [line["outcome"] for line in companies] == ["previewed", "pending_resync"]
    report = json.loads(output.read_text())
    assert set(report) == {"start", "companies", "summary"} and report["summary"] == summary
    assert all(set(entry) == COMPANY_KEYS | {"rows"} for entry in report["companies"])
    rows = [row for entry in report["companies"] for listed in entry["rows"].values() for row in listed]
    assert rows and all(set(row) == ROW_KEYS and set(row["why"]) <= set(preview.WHY) for row in rows)
    with pytest.raises(SystemExit):
        preview.main(["--output", str(output), "--workflow-commit", "A" * 40])
