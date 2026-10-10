"""Bounded quarterly corrections with read-only previews and transactional audit history.

The caller owns commit/rollback. Fetch inputs BEFORE opening the repair transaction. Normal
companyfacts ingestion remains insert-only; this explicit maintenance path journals corrections
of already occupied identities without deleting facts or rewriting filing-owned records.
"""
from collections import Counter
from datetime import date
from decimal import Decimal
import hashlib
import json
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import Company, FinancialFact
from app.models.financial_fact_revision import FinancialFactRevision
from app.services import facts_service
from app.services.fact_provenance import CALCULATION_VERSION, EPS_CONCEPTS, METRIC_INPUTS

REPAIR_VERSION = CALCULATION_VERSION
MAX_COMPANY_FACTS = 10000
QUARTERS = frozenset({"Q1", "Q2", "Q3", "Q4"})
_STATE_FIELDS = (
    "company_id", "filing_id", "concept", "raw_tag", "unit", "period_start", "period_end",
    "fiscal_year", "fiscal_period", "value", "form", "accession", "source", "reconciled",
    "is_latest", "provenance",
)
_MUTABLE_FIELDS = (
    "value", "period_start", "fiscal_year", "raw_tag", "reconciled", "provenance", "source", "form",
)


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, date):
        return value.isoformat()
    return value


def snapshot(row: FinancialFact) -> dict[str, Any]:
    return {key: _json_value(Decimal(str(row.value))) if key == "value"
            else _json_value(getattr(row, key)) for key in _STATE_FIELDS}


def _identity(row: dict[str, Any]) -> tuple:
    return tuple(row[key] for key in (
        "concept", "period_end", "fiscal_period", "unit", "accession",
    ))


def _candidate_state(fact: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _json_value(Decimal(str(fact[key]))) if key == "value"
        else _json_value(fact.get(key, True if key == "is_latest" else None))
        for key in _STATE_FIELDS
    }


def _restore(row: FinancialFact, state: dict[str, Any]) -> None:
    for key, value in state.items():
        if key in {"period_start", "period_end"} and value is not None:
            value = date.fromisoformat(value)
        elif key == "value":
            value = Decimal(value)
        setattr(row, key, value)


def _quarantine(state: dict[str, Any], reason: str) -> dict[str, Any]:
    provenance = {"formula": None, "inputs": [], "filed_at": None, **(state.get("provenance") or {})}
    provenance.update({
        "version": 1, "method": provenance.get("method", "calculated" if state["source"] == "derived" else "reported"), "validation": "unavailable",
        "reasons": [reason], "calculation_version": REPAIR_VERSION,
    })
    return {**state, "reconciled": False, "provenance": provenance}


def coverage(states: list[dict[str, Any]]) -> dict[str, Any]:
    current = [s for s in states if s["is_latest"] and s["fiscal_period"] in QUARTERS]
    annual = [s for s in states if s["is_latest"] and s["fiscal_period"] == "FY"
              and s["concept"] in METRIC_INPUTS]
    return {
        "annual_computed_current_rows": len(annual),
        "annual_computed_by_status": dict(sorted(Counter(
            (s.get("provenance") or {}).get("validation", "legacy") for s in annual
        ).items())),
        "quarterly_current_rows": len(current),
        "quarterly_periods": len({s["period_end"] for s in current}),
        "by_concept": dict(sorted(Counter(s["concept"] for s in current).items())),
        "by_status": dict(sorted(Counter(
            (s.get("provenance") or {}).get("validation", "legacy") for s in current
        ).items())),
        "quarantined_rows": sum(
            (s.get("provenance") or {}).get("validation") == "unavailable" for s in states
        ),
    }


def _rows(db: Session, company_id: int, *, for_update: bool = False) -> list[FinancialFact]:
    query = db.query(FinancialFact).filter(FinancialFact.company_id == company_id).order_by(
        FinancialFact.id
    ).populate_existing().limit(MAX_COMPANY_FACTS + 1)
    if for_update:
        query = query.with_for_update()
    rows = query.all()
    if len(rows) > MAX_COMPANY_FACTS:
        raise ValueError(f"Company exceeds the {MAX_COMPANY_FACTS}-fact repair bound")
    return rows


def _validate_payload(company: Company, payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Companyfacts payload must be an object identifying a CIK")
    try:
        same_cik = int(str(payload["cik"])) == int(company.cik)
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("Companyfacts payload must identify the selected company's CIK") from exc
    if not same_cik:
        raise ValueError("Companyfacts CIK does not match the selected company")
    root = payload.get("facts")
    if not isinstance(root, dict) or not isinstance(root.get("us-gaap"), dict):
        raise ValueError("Repair requires a US GAAP companyfacts payload")


def _source_identity(state: dict[str, Any]) -> tuple:
    """Source-owned duration/entity identity, independent of the application's fiscal labels."""
    return tuple(_json_value(state.get(key)) for key in (
        "concept", "raw_tag", "period_start", "period_end", "accession", "unit",
    ))


def _calendar_relabels(
    before: dict[int, dict[str, Any]], facts: list[dict[str, Any]], meta: dict[str, Any],
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    """Correct only source-proven fiscal labels; absence never proves a rolling annual error."""
    canonical: dict[tuple, list[dict[str, Any]]] = {}
    for fact in facts:
        if fact["source"] == "companyfacts" and fact["raw_tag"] is not None:
            canonical.setdefault(_source_identity(fact), []).append(fact)
    rolling = {
        _source_identity(item): item for item in meta.get("calendar_exclusions", [])
        if item.get("reason") == "rolling_duration_not_fiscal_year"
    }
    identities = {_identity(state): row_id for row_id, state in before.items()}
    updates, inserts = {}, {}
    for row_id, state in before.items():
        if state["source"] != "companyfacts" or state["filing_id"] is not None or not state["is_latest"]:
            continue
        candidates = canonical.get(_source_identity(state), [])
        same_period = [f for f in candidates if f["fiscal_period"] == state["fiscal_period"]]
        possible = same_period or candidates
        # Year-end balance-sheet facts legitimately have both FY and Q4 labels.
        if len(possible) == 1:
            fact = possible[0]
            target = _candidate_state(fact)
            if (state["fiscal_period"], state["fiscal_year"]) == (target["fiscal_period"], target["fiscal_year"]):
                continue
            if state["fiscal_period"] == target["fiscal_period"]:
                updates[row_id] = {**state, **{key: target[key] for key in _MUTABLE_FIELDS}}
                continue
            _admit_canonical_replacement(before, identities, updates, inserts, fact)
            replacement = {**_quarantine(state, "legacy_period_label_mismatch"), "is_latest": False}
            replacement["provenance"]["replacement_period"] = {
                "fiscal_period": target["fiscal_period"], "fiscal_year": target["fiscal_year"],
            }
            updates[row_id] = replacement
        elif state["fiscal_period"] == "FY" and _source_identity(state) in rolling:
            replacement = {**_quarantine(state, "rolling_duration_not_fiscal_year"), "is_latest": False}
            replacement["provenance"]["exclusion_evidence"] = [rolling[_source_identity(state)]]
            updates[row_id] = replacement
    _retire_calendar_dependents(before, facts, updates)
    return updates, list(inserts.values())


def _retire_calendar_dependents(
    before: dict[int, dict[str, Any]], facts: list[dict[str, Any]],
    updates: dict[int, dict[str, Any]],
) -> None:
    """Positive parent-scope corrections invalidate legacy formulas in that exact old scope."""
    canonical = {_identity(_candidate_state(f)) for f in facts if f["source"] == "derived"}
    parents = [(row_id, before[row_id], after) for row_id, after in updates.items()
               if before[row_id]["source"] == "companyfacts" and before[row_id]["raw_tag"] is not None
               and before[row_id]["is_latest"] and (
                   before[row_id]["fiscal_year"] != after["fiscal_year"] or
                   {"legacy_period_label_mismatch", "rolling_duration_not_fiscal_year"}.intersection(
                       (after.get("provenance") or {}).get("reasons", []),
                   )
               )]
    for row_id, state in before.items():
        if (state["source"] not in {"derived", "companyfacts"} or state["raw_tag"] is not None
                or state["filing_id"] is not None or not state["is_latest"]
                or state["concept"] not in METRIC_INPUTS or _identity(state) in canonical):
            continue
        evidence = []
        for parent_id, parent, corrected in parents:
            if parent["concept"] not in METRIC_INPUTS[state["concept"]] or any(
                state[key] != parent[key] for key in
                ("fiscal_year", "fiscal_period", "period_start", "period_end")
            ):
                continue
            evidence.append({
                "source_fact_id": parent_id, "concept": parent["concept"],
                "accession": parent["accession"], "raw_tag": parent["raw_tag"],
                "period_start": parent["period_start"], "period_end": parent["period_end"],
                "before_period": [parent["fiscal_year"], parent["fiscal_period"]],
                "after_period": [corrected["fiscal_year"], corrected["fiscal_period"]],
                "after_is_latest": corrected["is_latest"],
                "reason": (corrected.get("provenance") or {}).get("reasons", []),
            })
        if evidence:
            retired = {**_quarantine(state, "calculation_parent_period_corrected"), "is_latest": False}
            retired["provenance"]["exclusion_evidence"] = evidence
            updates[row_id] = retired


def _admit_canonical_replacement(
    before: dict[int, dict[str, Any]], identities: dict[tuple, int],
    updates: dict[int, dict[str, Any]], inserts: dict[tuple, dict[str, Any]], fact: dict[str, Any],
) -> None:
    target = _candidate_state(fact)
    target_id = identities.get(_identity(target))
    if target_id is None:
        inserts[_identity(target)] = fact
        return
    existing = before[target_id]
    if "repair_rolled_back" in (existing.get("provenance") or {}).get("reasons", []):
        raise ValueError("Canonical identity was rolled back; reviewed reapplication is required")
    if existing["source"] != "companyfacts" or existing["filing_id"] is not None:
        if any(existing[key] != target[key] for key in ("value", "period_start", "fiscal_year")):
            raise ValueError("Canonical period conflicts with a filing-owned/reported identity")
        if not existing["is_latest"]:
            raise ValueError("Canonical replacement is not current; refusing to alter a filing-owned identity")
        return
    corrected = {**existing, **{key: target[key] for key in _MUTABLE_FIELDS}}
    other_current = any(
        row_id != target_id and state["is_latest"] and all(state[key] == target[key] for key in
            ("concept", "period_end", "fiscal_period", "unit"))
        for row_id, state in before.items()
    )
    if not other_current:
        corrected["is_latest"] = True
    if corrected != existing:
        updates[target_id] = corrected


def repair_company(
    db: Session, company_id: int, payload: dict[str, Any], *, dry_run: bool = True,
    run_id: str | None = None, reported_eps: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Plan or apply one company's repair; never commits or calls external services.

    ``reported_eps`` contains trusted rows from the explicit filing-source manifest adapter.
    Same-identity edits cover calculated quarters and known annual computed metrics without a
    filing owner. Source-proven calendar errors can relabel companyfacts-owned reported rows;
    filing-owned records stay untouched. Standard upsert chooses latest winners for new identities;
    explicit reported EPS has narrow precedence.
    """
    if db.new or db.dirty or db.deleted:
        raise ValueError("Repair requires a clean caller-owned transaction")
    if not dry_run:
        facts_service._lock_fact_companies(db, [{"company_id": company_id}])
    company = db.get(Company, company_id)
    if company is None:
        raise ValueError("Unknown company")
    _validate_payload(company, payload)
    facts, meta = facts_service.normalize_companyfacts(
        company_id, payload, financial_sic=facts_service._is_financial_sic(company.sic),
    )
    if meta.get("unsupported_ifrs") or not facts:
        raise ValueError("No supported normalized facts; refusing to quarantine from an empty result")
    candidates = [f for f in facts if f["fiscal_period"] in QUARTERS or (
        f["fiscal_period"] == "FY" and f["concept"] in METRIC_INPUTS and f["source"] == "derived"
    )]
    existing = _rows(db, company_id, for_update=not dry_run)
    before = {row.id: snapshot(row) for row in existing}
    identities = {_identity(s): row_id for row_id, s in before.items()}
    normalized = {_identity(_candidate_state(f)): f for f in candidates}
    for state in before.values():
        if ("repair_rolled_back" in (state.get("provenance") or {}).get("reasons", [])
                and _identity(state) in normalized):
            raise ValueError("Candidate identity was rolled back; explicit reviewed reapplication is required")
    exclusions = {
        (e["concept"], e["fiscal_year"], e["fiscal_period"]): e
        for e in meta.get("quarterly_exclusions", [])
        if e.get("reason") in {"incompatible_vintages", "negative_calculated_value"}
    }
    dependent_concepts = {
        "operating_margin": {"operating_income", "revenue"},
        "net_margin": {"net_income", "revenue"},
        "free_cash_flow": {"operating_cash_flow", "capital_expenditures"},
    }
    updates, calendar_inserts = _calendar_relabels(before, facts, meta)
    for row_id, state in before.items():
        quarter_calculated = state["source"] == "derived" and state["fiscal_period"] in QUARTERS
        annual_computed = (
            state["fiscal_period"] == "FY" and state["concept"] in METRIC_INPUTS
            and state["source"] in {"derived", "companyfacts"} and state["raw_tag"] is None
        )
        if state["filing_id"] is not None or not (quarter_calculated or annual_computed):
            continue
        if row_id in updates and not updates[row_id]["is_latest"]:
            # A proven obsolete calendar scope must not be restored by a second exclusion path.
            continue
        candidate = normalized.get(_identity(state))
        if candidate is None:
            # Missing data is not evidence of an error. Only explicit incompatible source
            # operands/invalid calculations can quarantine an absent monetary candidate.
            reasons = [exclusions[(concept, state["fiscal_year"], state["fiscal_period"])]
                       for concept in {state["concept"]} | dependent_concepts.get(state["concept"], set())
                       if (concept, state["fiscal_year"], state["fiscal_period"]) in exclusions]
            if state["is_latest"] and (state["concept"] in EPS_CONCEPTS or reasons):
                quarantined = _quarantine(state, "legacy_calculation_not_supported")
                if reasons:
                    quarantined["provenance"]["exclusion_evidence"] = reasons
                if quarantined != state:
                    updates[row_id] = quarantined
            continue
        target = _candidate_state(candidate)
        # Preserve source/entity/accession identity and the existing latest selection.
        corrected = {**state, **{key: target[key] for key in _MUTABLE_FIELDS}}
        if corrected != state:
            updates[row_id] = corrected

    # Only calculated missing quarters enter from companyfacts; explicit reported EPS comes from
    # the narrow source adapter, never from a URL or user-supplied free-form numeric value.
    inserts = calendar_inserts + [f for f in candidates
               if f["source"] == "derived" and f["fiscal_period"] in QUARTERS
               and _identity(_candidate_state(f)) not in identities]
    quarterly_labels = {
        (_json_value(f["period_end"]), f["fiscal_period"], f["fiscal_year"])
        for f in candidates if f["fiscal_period"] in QUARTERS
    }
    for fact in reported_eps or []:
        if (fact.get("company_id") != company_id or fact.get("source") != "reported_eps"
                or fact.get("concept") not in {"earnings_per_share", "eps_diluted"}
                or fact.get("fiscal_period") not in QUARTERS):
            raise ValueError("Reported EPS adapter returned an out-of-scope fact")
        if (_json_value(fact["period_end"]), fact["fiscal_period"], fact["fiscal_year"]) not in quarterly_labels:
            raise ValueError("Reported EPS fiscal label does not match the normalized company period")
        identity = _identity(_candidate_state(fact))
        prior_id = identities.get(identity)
        if (prior_id is not None and "repair_rolled_back" in
                (before[prior_id].get("provenance") or {}).get("reasons", [])):
            raise ValueError("Reported EPS identity was rolled back; explicit reviewed reapplication is required")
        if prior_id is None:
            inserts.append(fact)
        elif before[prior_id]["source"] == "derived":
            target = _candidate_state(fact)
            updates[prior_id] = {**before[prior_id], **{k: target[k] for k in _MUTABLE_FIELDS}}
        else:
            prior = before[prior_id]
            expected = _candidate_state(fact)
            if any(prior[key] != expected[key] for key in ("value", "period_start")):
                raise ValueError("Reported EPS conflicts with an existing reported identity")
            other_reported = any(
                row_id != prior_id and state["is_latest"] and state["source"] != "derived"
                and all(state[key] == expected[key] for key in
                        ("concept", "period_end", "fiscal_period", "unit"))
                for row_id, state in before.items()
            )
            if not prior["is_latest"] and not other_reported:
                updates[prior_id] = {**prior, "is_latest": True}

        # A directly reported exact quarter outranks an unsupported annual-derived EPS even
        # when the 10-K accession is filed later. Preserve both original facts in the journal.
        for row_id, state in before.items():
            if (row_id != prior_id and state["source"] == "derived" and state["is_latest"]
                    and state["concept"] == fact["concept"]
                    and state["period_end"] == _json_value(fact["period_end"])
                    and state["fiscal_period"] == fact["fiscal_period"]
                    and state["unit"] == fact["unit"]):
                updates[row_id] = {**updates.get(row_id, state), "is_latest": False}

    digest = hashlib.sha256(json.dumps(
        {"companyfacts": payload, "reported_eps": reported_eps or []}, sort_keys=True,
        separators=(",", ":"), default=_json_value,
    ).encode()).hexdigest()
    run_id = run_id or str(uuid4())
    if len(run_id) > 64:
        raise ValueError("run_id must fit 64 characters")
    projected = [updates.get(row_id, state) for row_id, state in before.items()]
    # The dry-run preview reports additions before latest-filed precedence is applied by upsert.
    result = {
        "run_id": run_id, "version": REPAIR_VERSION, "company_id": company_id,
        "ticker": company.ticker, "dry_run": dry_run, "payload_sha256": digest,
        "before": coverage(list(before.values())), "planned_updates": len(updates),
        "planned_inserts": len(inserts), "changes": [
            {"fact_id": row_id, "before": before[row_id], "after": state}
            for row_id, state in updates.items()
        ], "inserts": [_candidate_state(fact) for fact in inserts],
    }
    if dry_run:
        result["projected_after"] = coverage(projected + result["inserts"])
        result["projection_note"] = "Insert latest-filed precedence is resolved during apply."
        return result
    if db.query(FinancialFactRevision.id).filter(
        FinancialFactRevision.run_id == run_id,
        FinancialFactRevision.company_id == company_id,
    ).first():
        raise ValueError("Run ID already used for this company; use a new ID")
    for row in existing:
        if row.id in updates:
            _restore(row, updates[row.id])
    facts_service.upsert_facts_bulk(db, inserts, commit=False)
    db.flush()
    after_rows = _rows(db, company_id)
    revisions = 0
    for row in after_rows:
        after = snapshot(row)
        if before.get(row.id) != after:
            db.add(FinancialFactRevision(
                run_id=run_id, company_id=company_id, fact_id=row.id, action="apply",
                calculation_version=REPAIR_VERSION, payload_sha256=digest,
                before_state=before.get(row.id), after_state=after,
            ))
            revisions += 1
    db.flush()
    result.update({"after": coverage([snapshot(row) for row in after_rows]), "revisions": revisions})
    return result


def rollback_company(
    db: Session, company_id: int, target_run_id: str, *, dry_run: bool = True,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Revert a complete company repair only if every affected row still matches its audit.

    Inserted rows are retained as unavailable, non-current audit history. A compare mismatch
    refuses the entire company, so later ingestion or another repair cannot be overwritten.
    """
    if db.new or db.dirty or db.deleted:
        raise ValueError("Rollback requires a clean caller-owned transaction")
    if not dry_run:
        facts_service._lock_fact_companies(db, [{"company_id": company_id}])
    revisions = db.query(FinancialFactRevision).filter(
        FinancialFactRevision.company_id == company_id,
        FinancialFactRevision.run_id == target_run_id,
        FinancialFactRevision.action == "apply",
    ).order_by(FinancialFactRevision.id).limit(MAX_COMPANY_FACTS + 1).all()
    if not revisions or len(revisions) > MAX_COMPANY_FACTS:
        raise ValueError("No bounded apply journal for this company/run")
    if db.query(FinancialFactRevision.id).filter(
        FinancialFactRevision.reverts_revision_id.in_([r.id for r in revisions]),
    ).first():
        raise ValueError("This company repair has already been rolled back")
    rows = {row.id: row for row in _rows(db, company_id, for_update=not dry_run)}
    for revision in revisions:
        row = rows.get(revision.fact_id)
        if row is None or snapshot(row) != revision.after_state:
            raise ValueError(f"Rollback conflict on fact {revision.fact_id}; no changes applied")
    changes = [{
        "fact_id": revision.fact_id, "before": revision.after_state,
        "after": revision.before_state or {
            **_quarantine(revision.after_state, "repair_rolled_back"), "is_latest": False,
        },
    } for revision in revisions]
    run_id = run_id or str(uuid4())
    if len(run_id) > 64:
        raise ValueError("run_id must fit 64 characters")
    result = {
        "run_id": run_id, "target_run_id": target_run_id,
        "company_id": company_id, "dry_run": dry_run, "changes": changes,
        "before": coverage([snapshot(row) for row in rows.values()]),
    }
    if not dry_run:
        for revision, change in zip(revisions, changes):
            _restore(rows[revision.fact_id], change["after"])
            db.add(FinancialFactRevision(
                run_id=result["run_id"], company_id=company_id, fact_id=revision.fact_id,
                action="rollback", calculation_version=REPAIR_VERSION,
                payload_sha256=revision.payload_sha256,
                before_state=change["before"], after_state=change["after"],
                reverts_revision_id=revision.id,
            ))
        db.flush()
    restored = {c["fact_id"]: c["after"] for c in changes}
    result["projected_after" if dry_run else "after"] = coverage([
        restored.get(row_id, snapshot(row)) for row_id, row in rows.items()
    ])
    return result
