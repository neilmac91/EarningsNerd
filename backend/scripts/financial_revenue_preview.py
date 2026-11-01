#!/usr/bin/env python3
"""E264 step (2): a read-only preview of each financial company's stored revenue rows against the deployed rule.

Since E264's deploy (#1913) a financial filer's companyfacts revenue is its reported total, never its ASC 606 fee
line. Rows stored before then keep the old reading, since both fact writers skip a stored identity. For each
financial company synced since the deploy, this reads SEC's current companyfacts once and computes what the
deployed rule writes with the deployed pure functions, never a copy: ``normalize_companyfacts`` (the batch and its
own-report history), ``financial_revenue_tags`` (the company's tag choice), ``extract_authoritative_values`` with
``cross_check_facts`` (the per-filing writer's verdict), ``admitted_items`` with ``own_period_ends`` (what an
accession reported itself), ``quarterly_fact_repair._validate_payload`` (the payload names the company) and the
sync's own currency test. It reads the company's revenue and margin rows from both writers, with their filings, and
sorts each row into at most one feed set and, for a per-filing revenue row, one per-filing verdict.

An identity is a row's concept, period end, fiscal period, unit and accession; its key is the same without the
accession. A gap is |a - b| / max(|a|, |b|). A feed row has no filing owner. The choice is the tags the deployed
collector reads, in order. A row's lineage is its revenue tag, or for a calculation the revenue tags of its recorded
operands: outside the choice, inside it, or legacy (none recorded: rows stored before 2026-10-10).
- A: a feed revenue row, current or not, at an identity the batch holds, more than 0.5% from it. A_tag_only: within
  0.5%, its tag outside the choice (reported, never for cleanup).
- B: a current feed revenue row at a key the batch no longer fills, its tag outside the choice; B_review inside it.
- C1: a feed calculation (a revenue quarter or a margin) at an identity the batch holds, more than 0.5% from it. C2:
  a current one at a key the batch no longer fills. Each is C1_review or C2_review when its lineage is inside.
- D and E: a non-current feed revenue row, judged against what its own accession reported for its span under the
  first chosen tag it reports there: flagged when more than 0.5% from that, or when the accession reports no chosen
  tag and the row's tag is outside the choice. D is an annual row at its accession's own year end (history), E any
  other. A difference with the row's tag inside the choice is D_review or E_review.
- K: a current row of either writer at a key the batch fills under another identity, more than 0.5% from it (a
  quarter stored with no fiscal period is read at the batch's quarter there); K_review when its lineage is inside.
- F: a per-filing revenue row the old cross-check replaced (source companyfacts), whatever its provenance, that
  cross_check_facts would replace under the deployed authority. F_gap: such a row of another source (confirmed by
  the old authority, or written unchecked). unjudged: no authority at its period end (10-Q quarters, E278's).
- missing (informational): batch identities no stored row holds.
Each listed row carries its stored and deployed figures, the gap, its rule (old when created before the deploy
instant, as census set 8 splits them) and a closed ``why`` (WHY).

Outcomes per company (OUTCOMES): previewed; pending_resync (synced before the deploy, no SEC read: step (1)'s rest
of the cohort); not_financial; fetch_failed; payload_rejected; unsupported_ifrs; another_currency (the sync's
currency step would run, which this does not model); database_error; internal_error; not_run (left by a stop).
Output: a flushed start line before any SEC read, one line per company, then the summary line; the report at
--output holds all of them and every listed row. Failures print a closed class only, and app log records are
withheld while it runs, since they can carry an exception's text: the Ops log and its artifact are public.

Read-only and bounded. The Ops step (financial-revenue-preview) fixes PGOPTIONS to read-only and checks them with
psql first. Here, before the cohort read and in each company's session, a PostgreSQL session must report
transaction_read_only on; SEC_DISTRIBUTED_LIMIT_ENABLED (its gate stores a row per request) is refused, and so is a
limiter not at 1 request a second. There is no apply mode, no heartbeat and no writer. Each previewed company costs
one companyfacts read through facts_service._fetch_companyfacts_sync (the shared limiter), before its session
opens. It refuses more than 50 tickers or an unknown one, Monday 06:00-08:30 UTC for SEC reads (the scheduled jobs
already sum to SEC's cap then), and more than 500 companies to read (it lists them, to batch by --tickers). It stops
after 3 failed reads in a row, 3 rate-limit hits or 3000 s, inside the step's 60 minutes: the companies left to read
are not_run. Exit 1 on any failure, refusal or stop.

  python scripts/financial_revenue_preview.py --output report.json --workflow-commit SHA [--tickers A,B]
  python scripts/financial_revenue_preview.py ... --companyfacts-dir DIR   # offline CIK##########.json, no SEC

Gate: tests/unit/test_financial_revenue_preview.py. Retire: the records PR that closes E264 deletes this script,
its test, the Ops operation and its gate lines, with ops/detection/financial_revenue_state.sql and its test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime, time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, NamedTuple
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import database  # noqa: E402
from app.config import settings  # noqa: E402
from app.models import Company, Filing, FinancialFact  # noqa: E402
from app.services import facts_service  # noqa: E402
from app.services.facts.companyfacts import _collect_companyfacts_concepts, normalize_companyfacts  # noqa: E402
from app.services.facts.concepts import CROSS_CHECK_TOLERANCE, _is_financial_sic, _unit_for  # noqa: E402
from app.services.facts.currency import (  # noqa: E402
    _another_currency, admitted_items, companyfacts_currencies, payload_view,
)
from app.services.facts.fi_revenue import financial_revenue_tags  # noqa: E402
from app.services.facts.fiscal_naming import own_period_ends  # noqa: E402
from app.services.facts.reconcile import cross_check_facts, extract_authoritative_values  # noqa: E402
from app.services.quarterly_fact_repair import _validate_payload  # noqa: E402
from app.services.sec_rate_limiter import sec_rate_limiter  # noqa: E402
from app.utils.datetimes import ensure_utc, iso_z, utc_from_iso, utcnow  # noqa: E402

E264_DEPLOYED_AT = utc_from_iso("2026-11-01T14:07:03+00:00")  # census SQL's e264_deployed
FEED_TOLERANCE = 0.005
CONCEPTS = ("revenue", "net_margin", "operating_margin", "gross_margin")
MARGINS = frozenset(CONCEPTS[1:])
QUARTERS = frozenset({"Q1", "Q2", "Q3", "Q4"})
MAX_TICKERS = 50
MAX_PREVIEWED = 500
TIME_BUDGET_SECONDS = 3000
STOP_AFTER_FAILED_FETCHES = 3
STOP_AFTER_RATE_LIMIT_HITS = 3
MAX_INPUT_BYTES = 32 * 1024 * 1024
TICKER = re.compile(r"[A-Z0-9][A-Z0-9.-]{0,11}")
SETS = ("A", "A_tag_only", "B", "B_review", "C1", "C1_review", "C2", "C2_review", "D", "D_review", "E", "E_review",
        "K", "K_review", "F", "F_gap", "unjudged", "missing")
OUTCOMES = ("previewed", "pending_resync", "not_financial", "fetch_failed", "payload_rejected", "unsupported_ifrs",
            "another_currency", "database_error", "internal_error", "not_run")
FAILURES = ("fetch_failed", "payload_rejected", "database_error", "internal_error")
WHY = ("lineage_outside_choice", "lineage_in_choice", "lineage_legacy", "newer_filing", "holds_feed_identity",
       "filing_reachable", "filing_unreachable", "probe_confirmed", "probe_replaced", "probe_no_authority")
ROW_FIELDS = ("id", "company_id", "filing_id", "concept", "raw_tag", "unit", "period_start", "period_end",
              "fiscal_year", "fiscal_period", "value", "accession", "source", "provenance", "is_latest", "created_at")
REPORT_FIELDS = ("concept", "fiscal_year", "fiscal_period", "period_start", "period_end", "unit", "accession",
                 "filing_id", "source", "raw_tag", "is_latest")


class Refused(Exception):
    """The run refuses, or stops, for a closed reason; ``tickers`` lists the companies that explain it."""

    def __init__(self, reason: str, tickers: list[str] | None = None) -> None:
        super().__init__(reason)
        self.reason, self.tickers = reason, tickers or []


class Member(NamedTuple):
    id: int
    ticker: str
    cik: str
    sic: str | None
    synced: bool  # facts_synced_at at or after the deploy instant


class Deployed(NamedTuple):
    choice: tuple[str, ...]
    facts: list[dict[str, Any]]  # the batch's rows of CONCEPTS
    history: list[dict[str, Any]]  # its own-report history rows of CONCEPTS
    own_ends: dict[Any, Any]  # each annual report's own period end, by accession
    own: dict[tuple, tuple[str, float]]  # (accession, end, start or klass) -> the first chosen tag's item there
    authority: dict[tuple, float]


def check_sec_guards() -> None:
    """Refuse the distributed SEC gate (it stores a row per request) and a limiter not at 1 request a second."""
    if settings.SEC_DISTRIBUTED_LIMIT_ENABLED:
        raise Refused("distributed_limit_on")
    if sec_rate_limiter.requests_per_second != 1:
        raise Refused("limiter_not_one_per_second")


def check_read_only(db: Session) -> None:
    """On PostgreSQL the session must report transaction_read_only on, as the Ops step's PGOPTIONS make it."""
    if db.get_bind().dialect.name == "postgresql" and db.execute(
            select(func.current_setting("transaction_read_only"))).scalar() != "on":
        raise Refused("session_not_read_only")


def in_sec_window(now: datetime) -> bool:
    """Monday 06:00-08:30 UTC, when docs/OPERATIONS.md's scheduled SEC rates already sum to SEC's cap."""
    return now.weekday() == 0 and time(6, 0) <= now.time() < time(8, 30)


def stop_reason(failed_reads: int, rate_limit_hits: int, elapsed_seconds: float) -> str | None:
    """Why the run stops before its next SEC read, or None: SEC's health first, then the time budget."""
    if failed_reads >= STOP_AFTER_FAILED_FETCHES:
        return "failed_fetches"
    if rate_limit_hits >= STOP_AFTER_RATE_LIMIT_HITS:
        return "rate_limit"
    return "time_budget" if elapsed_seconds >= TIME_BUDGET_SECONDS else None


def parse_tickers(raw: str | None) -> list[str]:
    if not (raw or "").strip():
        return []
    tickers = [part.strip().upper() for part in (raw or "").split(",")]
    if not all(TICKER.fullmatch(ticker) for ticker in tickers):
        raise Refused("invalid_tickers")
    tickers = list(dict.fromkeys(tickers))
    if len(tickers) > MAX_TICKERS:
        raise Refused("too_many_tickers")
    return tickers


def read_cohort(db: Session, tickers: list[str]) -> tuple[list[Member], int]:
    """The named companies, or every financial one (``_is_financial_sic``, in Python); and the blank-SIC count."""
    rows = db.query(Company.id, Company.ticker, Company.cik, Company.sic, Company.facts_synced_at).order_by(
        Company.ticker, Company.id).all()
    members = [Member(id_, ticker, cik, sic, synced is not None and ensure_utc(synced) >= E264_DEPLOYED_AT)
               for id_, ticker, cik, sic, synced in rows
               if (ticker in tickers if tickers else _is_financial_sic(sic))]
    unknown = sorted(set(tickers) - {member.ticker for member in members})
    if unknown:
        raise Refused("unknown_tickers", unknown)
    return members, sum(1 for row in rows if not row.sic)


def read_payload(member: Member, directory: Path | None, fetch: Callable[[str], Any]) -> tuple[str | None, Any]:
    """(failure outcome or None, payload): one SEC read through the shared limiter, or the offline file."""
    if directory is None:
        try:
            payload = fetch(member.cik)
        except Exception:  # the transport answers None on a failed read; a raise is one too
            payload = None
        return ("fetch_failed", None) if payload is None else (None, payload)
    try:
        path = directory / f"CIK{int(member.cik):010d}.json"
        if path.stat().st_size > MAX_INPUT_BYTES:
            return "payload_rejected", None
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return "fetch_failed", None
    try:
        return None, json.loads(text)
    except ValueError:
        return "payload_rejected", None


def deployed_rule(member: Member, payload: dict, facts: list[dict], meta: dict) -> Deployed:
    """What the deployed sync and cross-check read from this payload, beside the batch normalize gave."""
    usgaap = payload["facts"]["us-gaap"]
    currency, foreign = companyfacts_currencies(usgaap)  # the collector's own pick
    unit = _unit_for("revenue", currency)
    choice = financial_revenue_tags(usgaap, unit, foreign)
    duration_values, _instants = _collect_companyfacts_concepts(usgaap, _is_financial_sic(member.sic))
    own: dict[tuple, tuple[str, float]] = {}
    for tag in reversed(choice):  # the first chosen tag an accession reports wins, so it is written last
        node = usgaap.get(tag)
        units = node.get("units") if isinstance(node, dict) else None
        listed = units.get(unit) if isinstance(units, dict) else None
        for (end, klass), start, value, item in admitted_items(listed if isinstance(listed, list) else [], instant=False):
            if item.get("accn") not in foreign:  # a later item at the same span wins, as in the collector
                own[(item.get("accn"), end, start)] = own[(item.get("accn"), end, klass)] = (
                    f"us-gaap:{tag}", float(value))
    return Deployed(choice, [f for f in facts if f["concept"] in CONCEPTS],
                    [f for f in meta["history"] if f["concept"] in CONCEPTS], own_period_ends(duration_values), own,
                    extract_authoritative_values(payload, financial=_is_financial_sic(member.sic)))


def read_company(db: Session, company_id: int, accessions: set[str]) -> tuple[list[dict], dict]:
    """One read of the company's rows of CONCEPTS from both writers, and one of the filings they and the batch name."""
    rows = [{name: getattr(row, name) for name in ROW_FIELDS} for row in db.query(FinancialFact).filter(
        FinancialFact.company_id == company_id, FinancialFact.concept.in_(CONCEPTS)).order_by(FinancialFact.id)]
    for row in rows:
        row["value"] = float(row["value"])
    names = accessions | {row["accession"] for row in rows}
    filings = {accession: (ensure_utc(filed), owner) for accession, filed, owner in db.query(
        Filing.accession_number, Filing.filing_date, Filing.company_id).filter(Filing.accession_number.in_(names))}
    return rows, filings


def gap(a: float, b: float) -> float:
    scale = max(abs(a), abs(b))
    return abs(a - b) / scale if scale else 0.0


def _identity(row: dict) -> tuple:
    return row["concept"], row["period_end"], row["fiscal_period"], row["unit"], row["accession"]


def _calculated(row: dict) -> bool:
    return row["source"] == "derived" or row["concept"] in MARGINS


def lineage(row: dict, chosen: set[str]) -> str:
    """outside_choice, in_choice or legacy: a row's revenue tag, or the revenue tags in a calculation's operands."""
    calculated = _calculated(row)
    tags: set[str] = {row["raw_tag"]} if not calculated and row["raw_tag"] else set()
    stack = [row["provenance"]] if calculated else []
    while stack:
        node = stack.pop()
        for operand in (node.get("inputs") or []) if isinstance(node, dict) else []:
            if isinstance(operand, dict):
                if operand.get("concept") == "revenue" and operand.get("raw_tag"):
                    tags.add(operand["raw_tag"])
                stack.append(operand.get("provenance"))
    return "legacy" if not tags else "outside_choice" if tags - chosen else "in_choice"


def _figure(kind: str, value: float, tag: str | None, accession: str | None) -> dict[str, Any]:
    return {"kind": kind, "value": value, "tag": tag, "accession": accession}


def feed_set(row: dict, kind: str, chosen: set[str], deployed: Deployed, winners: dict, at_key: dict,
             at_quarter: dict, filings: dict) -> tuple[str, dict | None, tuple[str, ...]] | None:
    """The row's one feed-side set, the deployed figure it was judged against, and any extra why."""
    feed, calculated, review = row["filing_id"] is None, _calculated(row), kind == "in_choice"
    reported = feed and not calculated and row["concept"] == "revenue" and row["source"] == "companyfacts"
    winner = winners.get(_identity(row)) if feed else None
    if winner is not None:
        figure = _figure("batch_winner", winner["value"], winner["raw_tag"], winner["accession"])
        far = gap(row["value"], winner["value"]) > FEED_TOLERANCE
        if far and (calculated or reported):
            return ("A" if reported else "C1_review" if review else "C1"), figure, ()
        return ("A_tag_only", figure, ()) if reported and row["raw_tag"] not in chosen else None
    if row["is_latest"]:
        target = (at_quarter.get((row["concept"], row["period_end"], row["unit"])) if row["fiscal_period"] is None
                  else at_key.get(_identity(row)[:4]))
        if target is None:
            if feed and calculated:
                return ("C2_review" if review else "C2"), None, ()
            return (("B_review" if row["raw_tag"] in chosen else "B"), None, ()) if reported else None
        if _identity(target) == _identity(row) or gap(row["value"], target["value"]) <= FEED_TOLERANCE:
            return None
        mine, theirs = filings.get(row["accession"]), filings.get(target["accession"])  # upsert_facts_bulk's rule
        newer = mine is not None and (theirs is None or (mine[0], row["accession"]) > (theirs[0], target["accession"]))
        figure = _figure("batch_winner", target["value"], target["raw_tag"], target["accession"])
        return ("K_review" if review else "K"), figure, ("newer_filing",) if newer else ()
    if not reported:
        return None
    span = row["period_start"] or ("FY" if row["fiscal_period"] == "FY" else "Q")
    own = deployed.own.get((row["accession"], row["period_end"], span))
    name = "D" if row["fiscal_period"] == "FY" and deployed.own_ends.get(row["accession"]) == row["period_end"] else "E"
    if own is None:
        return (name, None, ()) if row["raw_tag"] not in chosen else None
    if gap(row["value"], own[1]) <= FEED_TOLERANCE:
        return None
    return (name if row["raw_tag"] not in chosen else f"{name}_review"), _figure(
        "own_report", own[1], own[0], row["accession"]), ()


def per_filing_verdict(row: dict, authority: dict) -> tuple[str, tuple[str, dict | None] | None]:
    """The deployed cross-check's probe on a per-filing revenue row's stored value, and the set it puts it in."""
    fact = {"concept": row["concept"], "period_end": row["period_end"], "unit": row["unit"], "value": row["value"]}
    provenance = cross_check_facts([fact], authority)[0].get("provenance") or {}
    check = (provenance.get("checks") or {}).get("authoritative")
    if not check:
        return "no_authority", ("unjudged", None)
    if check["outcome"] != "replaced":
        return "confirmed", None
    figure = _figure("authority", check["authoritative_value"], None, None)
    return "replaced", ("F" if row["source"] == "companyfacts" else "F_gap", figure)


def _plain(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


def _entry(row: dict, figure: dict | None, why: set[str]) -> dict[str, Any]:
    created = row["created_at"]
    return {"fact_id": row["id"], **{name: _plain(row[name]) for name in REPORT_FIELDS},
            "rule": "old" if created is None or ensure_utc(created) < E264_DEPLOYED_AT else "new",
            "stored_value": row["value"], "deployed": figure,
            "gap": None if figure is None else round(gap(row["value"], figure["value"]), 6), "why": sorted(why)}


def classify(rows: list[dict], filings: dict, deployed: Deployed) -> dict[str, list[dict]]:
    """Each stored row in at most one feed set and, if a per-filing revenue row, one per-filing verdict (pure)."""
    chosen = {f"us-gaap:{tag}" for tag in deployed.choice}
    winners = {_identity(fact): fact for fact in deployed.facts}
    batch_ids = winners.keys() | {_identity(fact) for fact in deployed.history}
    at_key: dict[tuple, dict] = {}
    at_quarter: dict[tuple, dict] = {}
    for fact in deployed.facts:
        at_key.setdefault(_identity(fact)[:4], fact)
        if fact["fiscal_period"] in QUARTERS:
            at_quarter.setdefault((fact["concept"], fact["period_end"], fact["unit"]), fact)
    sets: dict[str, list[dict]] = {name: [] for name in SETS}
    for row in rows:
        kind = lineage(row, chosen)
        owner = filings.get(row["accession"], (None, None))[1]
        why = {f"lineage_{kind}", "filing_reachable" if owner == row["company_id"] else "filing_unreachable"}
        placed = []
        if (feed := feed_set(row, kind, chosen, deployed, winners, at_key, at_quarter, filings)) is not None:
            placed.append(feed[:2])
            why.update(feed[2])
        if row["filing_id"] is not None:
            if _identity(row) in batch_ids:
                why.add("holds_feed_identity")
            if row["concept"] == "revenue":
                probe, verdict = per_filing_verdict(row, deployed.authority)
                why.add(f"probe_{probe}")
                placed += [verdict] if verdict else []
        for name, figure in placed:
            sets[name].append(_entry(row, figure, why))
    held = {_identity(row) for row in rows}
    for kind, facts in (("batch_winner", deployed.facts), ("history", deployed.history)):
        sets["missing"] += [{"fact_id": None, **{name: _plain(fact.get(name)) for name in REPORT_FIELDS},
                             "rule": None, "stored_value": None, "gap": None, "why": [],
                             "deployed": _figure(kind, fact["value"], fact["raw_tag"], fact["accession"])}
                            for fact in facts if _identity(fact) not in held]
    return sets


def preview_company(member: Member, payload: Any, sessions: Callable[[], Session]) -> tuple[str, Any, Any]:
    """(outcome, sets, choice) for one fetched payload; sessions open only after the read and close before sorting."""
    if not isinstance(payload, dict):
        return "payload_rejected", None, None
    facts, meta = normalize_companyfacts(member.id, payload, financial_sic=_is_financial_sic(member.sic))
    named = {"cik": payload.get("cik"), "facts": {"us-gaap": {}}} if meta["unsupported_ifrs"] else payload
    try:  # the quarterly repair's check: the payload names this company (and, unless IFRS-only, holds US GAAP)
        _validate_payload(SimpleNamespace(cik=member.cik), named)
    except ValueError:
        return "payload_rejected", None, None
    if meta["unsupported_ifrs"]:
        return "unsupported_ifrs", None, None
    deployed = deployed_rule(member, payload, facts, meta)
    with sessions() as db:
        check_read_only(db)
        if facts and _another_currency(db, facts, payload_view(payload)):
            return "another_currency", None, None
        rows, filings = read_company(db, member.id, {f["accession"] for f in [*deployed.facts, *deployed.history]})
    return "previewed", classify(rows, filings, deployed), deployed.choice


def company_line(member: Member, outcome: str, payload: Any = None, sets: Any = None, choice: Any = None) -> dict:
    line = {"ticker": member.ticker, "company_id": member.id, "sic": member.sic, "outcome": outcome,
            "choice": None if choice is None else list(choice), "payload_sha256": None, "payload_newest_filed": None,
            "counts": None, "fiscal_years": None}
    if payload is not None:
        line["payload_sha256"] = hashlib.sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        line["payload_newest_filed"] = payload_view(payload).newest_filed
    if sets is not None:
        line["counts"] = {name: len(listed) for name, listed in sets.items()}
        years = {name: [r["fiscal_year"] for r in listed if r["fiscal_year"] is not None] for name, listed in sets.items()}
        line["fiscal_years"] = {name: [min(found), max(found)] for name, found in years.items() if found}
    return line


def summarize(run_id: str, lines: list[dict], before: dict, stopped: str | None, refused: str | None,
              explained: list[str]) -> dict[str, Any]:
    after = sec_rate_limiter.get_stats()
    outcomes = dict.fromkeys(OUTCOMES, 0)
    totals, companies = dict.fromkeys(SETS, 0), dict.fromkeys(SETS, 0)
    for line in lines:
        outcomes[line["outcome"]] += 1
        for name, count in (line["counts"] or {}).items():
            totals[name] += count
            companies[name] += bool(count)
    return {"summary": True, "run_id": run_id, "outcomes": outcomes, "totals": totals, "companies_per_set": companies,
            "sec": {"requests": after["total_requests"] - before["total_requests"],
                    "rate_limit_hits": after["rate_limit_hits"] - before["rate_limit_hits"]},
            "stopped": stopped, "refused": refused, "refused_tickers": explained,
            "failed": sum(outcomes[name] for name in FAILURES)}


def run(args: argparse.Namespace, emit: Callable[[dict], None], *, fetch: Callable[[str], Any] | None = None,
        session_factory: Callable[[], Session] | None = None, clock: Callable[[], datetime] | None = None) -> dict:
    """The whole run: refusals and failures become closed classes, so it always returns its report."""
    clock = clock or utcnow
    run_id, before = str(uuid4()), sec_rate_limiter.get_stats()
    report: dict[str, Any] = {"start": None, "companies": []}
    stopped = refused = None
    explained: list[str] = []
    try:
        tickers = parse_tickers(args.tickers)
        check_sec_guards()
        started = ensure_utc(clock())
        if args.companyfacts_dir is None and in_sec_window(started):
            raise Refused("sec_window")
        sessions = session_factory or database.SessionLocal
        with sessions() as db:
            check_read_only(db)
            members, blank = read_cohort(db, tickers)
        to_read = [member for member in members if _is_financial_sic(member.sic) and member.synced]
        report["start"] = {
            "started": True, "run_id": run_id, "workflow_commit": args.workflow_commit, "dry_run": True,
            "execution": "github_actions_runner", "production_image_used": False,
            "payload_source": "sec" if args.companyfacts_dir is None else "offline_directory",
            "rule": {"e264_deployed_at": iso_z(E264_DEPLOYED_AT), "feed_tolerance": FEED_TOLERANCE,
                     "per_filing": f"cross_check_facts ({CROSS_CHECK_TOLERANCE:.0%})"},
            "cohort_size": len(members), "blank_sic_companies": blank,
            "cohort": [{"ticker": m.ticker, "sic": m.sic, "synced_since_deploy": m.synced} for m in members],
        }
        emit(report["start"])
        if len(to_read) > MAX_PREVIEWED:
            raise Refused("cohort_over_cap", [member.ticker for member in to_read])
        read = fetch or (lambda cik: facts_service._fetch_companyfacts_sync(cik))
        failed_reads = 0
        for member in members:
            payload = sets = choice = None
            if not _is_financial_sic(member.sic):
                outcome = "not_financial"
            elif not member.synced:
                outcome = "pending_resync"
            else:
                if not stopped:
                    hits = sec_rate_limiter.get_stats()["rate_limit_hits"] - before["rate_limit_hits"]
                    stopped = stop_reason(failed_reads, hits, (ensure_utc(clock()) - started).total_seconds())
                outcome, fetched = ("not_run", None) if stopped else read_payload(member, args.companyfacts_dir, read)
                failed_reads = failed_reads + 1 if outcome == "fetch_failed" else 0
                if outcome is None:
                    try:
                        outcome, sets, choice = preview_company(member, fetched, sessions)
                        payload = fetched if outcome != "payload_rejected" else None
                    except Refused as exc:  # a company session that is not read-only stops the run
                        outcome, stopped = "not_run", exc.reason
                    except SQLAlchemyError:
                        outcome = "database_error"
                    except Exception:  # closed class only: an exception's text never reaches the output
                        outcome = "internal_error"
            line = company_line(member, outcome, payload, sets, choice)
            emit(line)
            report["companies"].append({**line, "rows": {k: v for k, v in (sets or {}).items() if v}})
    except Refused as exc:
        refused, explained = exc.reason, exc.tickers
    except SQLAlchemyError:
        refused = "database_error"
    except Exception:
        refused = "internal_error"
    report["summary"] = summarize(run_id, report["companies"], before, stopped, refused, explained)
    return report


def _commit(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise argparse.ArgumentTypeError("expected 40 lowercase hex characters")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only preview of E264's deployed revenue rule (docstring).")
    parser.add_argument("--tickers", help="Comma-separated, at most 50 (default: every financial company).")
    parser.add_argument("--output", type=Path, required=True, help="Where the full report is written.")
    parser.add_argument("--workflow-commit", type=_commit, required=True, help="The commit this run executes.")
    parser.add_argument("--companyfacts-dir", type=Path, help="Offline CIK##########.json payloads; no SEC read.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    def emit(line: dict) -> None:
        print(json.dumps(line, sort_keys=True), flush=True)

    withheld = logging.root.manager.disable
    logging.disable(logging.CRITICAL)  # app log records can carry an exception's text; the Ops log is public
    try:
        report = run(args, emit)
    finally:
        logging.disable(withheld)
    summary = report["summary"]
    code = 1 if summary["refused"] or summary["stopped"] or summary["failed"] else 0
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    except OSError:
        emit({"report_written": False})
        code = 1
    emit(summary)
    return code


if __name__ == "__main__":
    os.environ.setdefault("SKIP_REDIS_INIT", "true")
    raise SystemExit(main())
