"""Journaled lineage backfill for filing-owned legacy calculations (Multi-Period Analysis WP0).

A filing-owned margin, free cash flow, working capital or current ratio stored before #1191 has no
versioned provenance, so every reader projects it as ``legacy_calculation`` (``fact_provenance.
provenance_for_fact``). Neither writer ever gives it lineage: ingestion skips an identity already
stored (``facts/upsert.py``), and the quarterly repair leaves filing-owned rows alone
(``quarterly_fact_repair.repair_company``), except its proxy step's narrow writes
(``proxy_fact_repair``): it re-annotates only a calculation that has a version-1 record, and the one
write that can reach a row with none is a promotion, which sets ``is_latest`` alone. This backfill
recomputes each such row from the operands
its own accession stores, through the per-filing writer's calculator
(``facts/lineage.annotate_filing_calculations``), and records the result.

It writes ``provenance`` and ``reconciled`` only, never a value, label or ``is_latest``, and only
a pass or a concern that rests on positive evidence: a recomputed value that disagrees with the
figure, or a review state inherited from an operand. It holds, unchanged and counted, a row the
old local gate flagged (its reason cannot be recovered), a row whose record would withhold a shown
figure, a row whose operands it cannot find (often a flow operand stored before #831 with no
start date) and a row with a legacy calculation among its operands. Every write is journaled in
``financial_fact_revision`` (version ``lineage-backfill-v1``), so ``quarterly_fact_repair.
rollback_company`` reverts a company's run. The caller owns the transaction; nothing here commits,
opens a session or reads the network.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Company, FinancialFact
from app.models.financial_fact_revision import FinancialFactRevision
from app.services import facts_service, quarterly_fact_repair
from app.services.fact_provenance import METRIC_FORMULAS, METRIC_INPUTS, PROVENANCE_VERSION
from app.services.facts.lineage import _scope, annotate_filing_calculations
from app.services.quarterly_fact_repair import snapshot

BACKFILL_VERSION = "lineage-backfill-v1"  # financial_fact_revision.calculation_version
HOLD_REASONS = ("inputs_not_found", "legacy_flagged", "operand_legacy_calculation", "operand_withheld")
# Why the calculator found no operands, for the report only, first match in this order.
DIAGNOSTICS = (
    "no_operand_row", "ambiguous_operand", "unit_mismatch", "duration_unknown", "duration_mismatch", "other",
)
# The formulas over two instants, which need no start date (``facts/lineage._operands``).
_INSTANT_FORMULAS = frozenset({"working_capital", "current_ratio"})


def is_target(row: Any) -> bool:
    """The filing-owned rows the reader projects as ``legacy_calculation``: a formula concept with no
    tag of its own (none, empty or the concept itself) and no version-1 record."""
    stored = row.provenance
    return (row.filing_id is not None
            and row.concept in METRIC_FORMULAS
            and (not row.raw_tag or row.raw_tag == row.concept)
            and not (isinstance(stored, dict) and stored.get("version") == PROVENANCE_VERSION))


def _fact(row: Any, *, target: bool) -> dict[str, Any]:
    """A stored row as the calculator reads a fact. ``value`` is a float: the column reads back as a
    Decimal, which the calculator would count as a mismatch. A target's old record is replaced, so
    the calculator never reads it; an operand keeps its own."""
    return {
        "company_id": row.company_id, "filing_id": row.filing_id, "concept": row.concept,
        "raw_tag": row.raw_tag, "unit": row.unit, "period_start": row.period_start,
        "period_end": row.period_end, "fiscal_year": row.fiscal_year, "fiscal_period": row.fiscal_period,
        "value": float(row.value), "form": row.form, "accession": row.accession, "source": row.source,
        "reconciled": row.reconciled is True,  # present, so the calculator sets a target's flag
        "provenance": None if target else row.provenance,
    }


def _diagnose(fact: dict[str, Any], facts: list[dict[str, Any]]) -> dict[str, Any]:
    """Why the calculator found no operands for ``fact``: its checks, in its order, for the report."""
    found = {concept: [item for item in facts if item["concept"] == concept and _scope(item) == _scope(fact)]
             for concept in METRIC_INPUTS[fact["concept"]]}
    inputs = [{"concept": concept, "rows": len(rows), "units": sorted({str(row["unit"]) for row in rows}),
               "null_start": sum(row["period_start"] is None for row in rows)} for concept, rows in found.items()]
    counts = [len(rows) for rows in found.values()]
    if 0 in counts:
        label = "no_operand_row"
    elif any(count > 1 for count in counts):
        label = "ambiguous_operand"
    else:
        left, right = (rows[0] for rows in found.values())
        if not left["unit"] or left["unit"] != right["unit"]:
            label = "unit_mismatch"
        elif fact["concept"] not in _INSTANT_FORMULAS and None in (left["period_start"], right["period_start"]):
            label = "duration_unknown"
        elif left["period_start"] != right["period_start"] or (
                fact["period_start"] is not None and fact["period_start"] != left["period_start"]):
            label = "duration_mismatch"
        else:
            label = "other"
    return {"label": label, "inputs": inputs}


def plan_company(
    targets: list[FinancialFact], scope: list[FinancialFact], newest_fy: int | None = None,
) -> dict[str, Any]:
    """Decide each target from the calculator's verdict on its accession's rows; reads attributes only.

    ``scope`` is every row of the company in the targets' accessions, whatever its owner: the first
    writer to store an identity owns it, so an operand can be a companyfacts row. The calculator
    matches operands by its own scope rule. Formula rows that are not targets are left out: they
    are never operands. Holds come first, in this order, then passes and concerns. ``latest_fy``
    counts the current annual targets of ``newest_fy``, the company's newest fiscal year, the year
    whose review notes the Multi-Period Analysis baseline counts.
    """
    target_ids = {row.id for row in targets}
    by_accession: dict[str, list[FinancialFact]] = defaultdict(list)
    for row in sorted({row.id: row for row in [*targets, *scope]}.values(), key=lambda row: row.id):
        if row.id in target_ids or row.concept not in METRIC_FORMULAS:
            by_accession[row.accession].append(row)
    outcomes = Counter({"passed": 0, "needs_review": 0})
    held = Counter(dict.fromkeys(HOLD_REASONS, 0))
    diagnostics = Counter(dict.fromkeys(DIAGNOSTICS, 0))
    reasons: Counter[str] = Counter()
    latest_fy = Counter({"cleared": 0, "marked": 0, "held": 0})
    writes: list[tuple[FinancialFact, dict[str, Any], bool]] = []
    entries: list[dict[str, Any]] = []
    for rows in by_accession.values():
        facts = [_fact(row, target=row.id in target_ids) for row in rows]
        annotated = annotate_filing_calculations(facts)
        for row, fact, result in zip(rows, facts, annotated):
            if row.id not in target_ids:
                continue
            provenance = result["provenance"]
            validation, found = provenance["validation"], provenance["reasons"]
            diagnostic = None
            if row.reconciled is not True:
                outcome = "legacy_flagged"  # the old local gate's reason is lost; never flip it to true
            elif validation == "unavailable":
                outcome = "operand_withheld"  # the record would withhold a figure readers see today
            elif "missing_calculation_inputs" in found:
                outcome = "inputs_not_found"  # absent operands are no evidence against the figure
                diagnostic = _diagnose(fact, facts)
                diagnostics[diagnostic["label"]] += 1
            elif "legacy_calculation" in found:
                outcome = "operand_legacy_calculation"  # a version-1 record never carries a legacy reason
            else:
                outcome = "passed" if validation == "passed" else "needs_review"
                writes.append((row, provenance, result["reconciled"]))
                outcomes[outcome] += 1
                reasons.update(found)
            if outcome in HOLD_REASONS:
                held[outcome] += 1
            if row.is_latest and row.fiscal_period == "FY" and row.fiscal_year == newest_fy:
                latest_fy[{"passed": "cleared", "needs_review": "marked"}.get(outcome, "held")] += 1
            entry = {
                "fact_id": row.id, "concept": row.concept, "fiscal_year": row.fiscal_year,
                "fiscal_period": row.fiscal_period, "period_end": row.period_end.isoformat(),
                "accession": row.accession, "is_latest": row.is_latest, "value": fact["value"],
                "outcome": outcome, "validation": validation, "reasons": found,
                "inputs": [[item["concept"], item["value"]] for item in provenance["inputs"]],
            }
            if diagnostic is not None:
                entry["diagnostic"] = diagnostic
            entries.append(entry)
    return {
        "scanned": len(targets), "writes": writes, "outcomes": dict(outcomes),
        "reasons": dict(sorted(reasons.items())), "held": dict(held), "diagnostics": dict(diagnostics),
        "latest_fy": dict(latest_fy), "rows": sorted(entries, key=lambda entry: entry["fact_id"]),
    }


def backfill_company(db: Session, company_id: int, *, apply: bool, run_id: str) -> dict[str, Any]:
    """Plan one company's backfill; with ``apply`` also write and journal it. The caller commits.

    A dry run takes no lock and no row lock: Postgres refuses ``FOR UPDATE`` in the read-only
    transactions the Ops dry run opens. The apply takes the company lock both fact writers take,
    then locks the rows it reads. A company above the quarterly repair's fact bound is refused,
    since that repair's rollback, the audited undo of this one, refuses it too.
    """
    if db.new or db.dirty or db.deleted:
        raise ValueError("Backfill requires a clean caller-owned transaction")
    if apply:
        facts_service._lock_fact_companies(db, [{"company_id": company_id}])
    bound = quarterly_fact_repair.MAX_COMPANY_FACTS
    stored = db.query(func.count(FinancialFact.id)).filter(FinancialFact.company_id == company_id).scalar()
    if stored > bound:
        raise ValueError(f"Company exceeds the {bound}-fact repair bound")
    formulas = db.query(FinancialFact).filter(
        FinancialFact.company_id == company_id, FinancialFact.concept.in_(sorted(METRIC_FORMULAS)),
    ).order_by(FinancialFact.id).populate_existing()
    targets = [row for row in (formulas.with_for_update() if apply else formulas).all() if is_target(row)]
    scope: list[FinancialFact] = []
    if targets:
        query = db.query(FinancialFact).filter(
            FinancialFact.company_id == company_id,
            FinancialFact.accession.in_(sorted({row.accession for row in targets})),
        ).order_by(FinancialFact.id).populate_existing()
        scope = (query.with_for_update() if apply else query).all()
    newest_fy = db.query(func.max(FinancialFact.fiscal_year)).filter(
        FinancialFact.company_id == company_id, FinancialFact.is_latest.is_(True),
        FinancialFact.fiscal_period == "FY",
    ).scalar()
    plan = plan_company(targets, scope, newest_fy)
    revisions = 0
    if apply and plan["writes"]:
        if db.query(FinancialFactRevision.id).filter(
            FinancialFactRevision.run_id == run_id, FinancialFactRevision.company_id == company_id,
        ).first():
            raise ValueError("Run ID already used for this company; use a new ID")
        digest = hashlib.sha256(json.dumps(
            [[row.id, provenance, reconciled] for row, provenance, reconciled in plan["writes"]],
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        for row, provenance, reconciled in plan["writes"]:
            before = snapshot(row)
            row.provenance = provenance  # a new dict, so the change is detected
            row.reconciled = reconciled
            db.add(FinancialFactRevision(
                run_id=run_id, company_id=company_id, fact_id=row.id, action="apply",
                calculation_version=BACKFILL_VERSION, payload_sha256=digest,
                before_state=before, after_state=snapshot(row),
            ))
            revisions += 1
        db.flush()
    company = db.get(Company, company_id)
    return {
        "company_id": company_id, "ticker": company.ticker if company else None, "run_id": run_id,
        "dry_run": not apply, "scanned": plan["scanned"], "writes": len(plan["writes"]),
        "outcomes": plan["outcomes"], "reasons": plan["reasons"], "held": plan["held"],
        "diagnostics": plan["diagnostics"], "latest_fy": plan["latest_fy"], "revisions": revisions,
        "rows": plan["rows"],
    }
