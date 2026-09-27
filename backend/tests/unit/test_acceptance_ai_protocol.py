"""AI-assisted E7 evidence is source-bound, sealed and never a human attestation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from evals import acceptance_legacy_history
from evals.acceptance_ai_protocol import (ROLE_NAMES, _canonical_set_sha256,
                                          ai_review_evidence_inventory, source_context_ids,
                                          validate_ai_prerequisites)
from evals.acceptance_readiness import verify_review_evidence_binding


def _write(path: Path, value: object) -> dict[str, str]:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _write_canonical(path: Path, value: object) -> dict[str, str]:
    path.write_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n")
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _fixture(tmp_path: Path, *, accession: str = "0000000001-26-000001", prefix: str = "") -> tuple[dict, Path, str, dict[str, dict[str, str]], datetime]:
    def write(path: Path, value: object) -> dict[str, str]:
        return _write(path.with_name(prefix + path.name), value)

    now = datetime.now(timezone.utc)
    frozen = (now - timedelta(hours=2)).isoformat()
    sources = {accession: {"primary": "a" * 64, "index": "b" * 64}}
    packets = [{"role": role, "sha256": sha} for role, sha in sources[accession].items()]
    issue = {"issue_id": "revenue", "issue": "Revenue changed", "source_role": "primary", "source_sha256": "a" * 64,
             "source_locator": "Item 7, paragraph 3", "amounts_and_bases": "USD million, FY2026",
             "qualifiers": "continuing operations", "importance": "material trend",
             "disclosure_limits": "reported only"}
    roles = []
    for name in sorted(ROLE_NAMES):
        roles.append({"role": name, "provider": "Codex", "model": "gpt-6-astra",
                      "model_version": "2026-09-22",
                      "prompt": write(tmp_path / f"{name}-prompt.json", {"task": name}),
                      "contract": write(tmp_path / f"{name}-contract.json", {"version": 2})})
    protocol = write(tmp_path / "protocol.json", {
        "schema_version": 3, "review_protocol": "ai_assisted", "frozen_at": frozen,
        "approved_manifest_sha256": "c" * 64, "roles": roles})
    briefs = []
    hashes = {}
    def context_receipt(role: str, input_briefs: dict[str, str] | None = None) -> dict[str, str]:
        return write(tmp_path / f"{role}-context.json", {
            "schema_version": 2, "review_protocol": "ai_assisted",
            "accession_number": accession, "context_id": f"ctx-{prefix}{role}", "role": role,
            "observed_at": frozen, "input_source_packets": packets,
            "input_brief_sha256": input_briefs or {},
            "candidate_output_artifacts": [], "source_only": True,
            "context_window_truncated": False})

    for role in ("source_reference_a", "source_reference_b"):
        context = f"ctx-{prefix}{role}"
        brief = {"schema_version": 2, "review_protocol": "ai_assisted",
                 "accession_number": accession, "context_id": context, "frozen_at": frozen,
                 "source_only": True, "candidate_outputs_seen": False, "source_packets": packets,
                 "coverage_status": "complete", "context_window_truncated": False,
                 "coverage_limits": "All declared packets checked", "material_issues": [issue],
                 "context_evidence": context_receipt(role)}
        record = write(tmp_path / f"{role}.json", brief)
        briefs.append({"accession_number": accession, "role": role, "context_id": context, **record})
        hashes[role] = record["sha256"]
    reference = write(tmp_path / "reference.json", {
        "schema_version": 2, "review_protocol": "ai_assisted",
        "accession_number": accession, "context_id": f"ctx-{prefix}source_reconciliation",
        "frozen_at": frozen, "source_only": True, "candidate_outputs_seen": False,
        "source_packets": packets, "coverage_status": "complete", "context_window_truncated": False,
        "coverage_limits": "All declared packets checked", "source_brief_sha256": hashes,
        "disagreements": [], "material_issues": [issue],
        "issue_dispositions": [{"source_context_id": f"ctx-{prefix}{role}", "source_issue_id": "revenue",
                                "status": "supported", "reason": "Matches source",
                                "source_role": "primary", "source_sha256": "a" * 64,
                                "source_locator": "Item 7, paragraph 3",
                                "reconciled_issue_id": "revenue"}
                               for role in ("source_reference_a", "source_reference_b")],
        "context_evidence": context_receipt("source_reconciliation", hashes)})
    exposure = write(tmp_path / "exposure.json", {
        "schema_version": 2, "review_protocol": "ai_assisted", "checked_accessions": [accession],
        "known_candidate_output_exposed_accessions": [], "known_tuning_exposed_accessions": [],
        "unknown_external_exposure": True, "external_artifact_inventory": "Local checked set",
        "scope": "Local workspace only", "observed_at": frozen})
    prereq = {"schema_version": 2, "review_protocol": "ai_assisted",
              "approved_manifest_sha256": "c" * 64,
              "ai_assisted": {"protocol": protocol, "source_briefs": briefs,
                              "reconciled_references": [{"accession_number": accession, **reference}],
                              "exposure_review": exposure}}
    prereq_path = tmp_path / (prefix + "prerequisites.json")
    prereq_path.write_text(json.dumps(prereq), encoding="utf-8")
    return prereq, prereq_path, accession, sources, now


def _validate(prereq: dict, path: Path, accession: str,
              sources: dict[str, dict[str, str]], now: datetime):
    return validate_ai_prerequisites(prereq, path.parent, [accession], sources, now)


def _add_reconciliation_history(
    tmp_path: Path, prereq: dict, accession: str, sources: dict[str, dict[str, str]],
) -> tuple[dict, Path, str]:
    ai = prereq["ai_assisted"]
    current_reference = next(
        row for row in ai["reconciled_references"] if row["accession_number"] == accession)
    reference = json.loads((tmp_path / current_reference["path"]).read_text())
    current_briefs = [
        row for row in ai["source_briefs"] if row["accession_number"] == accession]
    origin_specs = [
        ("ctx-old-a", "source_reference_a", "old-a"),
        ("ctx-old-b", "source_reference_b", "old-b"),
        ("ctx-old-reconciliation", "source_reconciliation", "old-reconciliation"),
        (current_briefs[0]["context_id"], "source_reference_a", "same-context-a-partial"),
    ]
    origins = []
    for index, (context_id, role, prefix) in enumerate(origin_specs, start=1):
        artifact = _write(tmp_path / f"retired-{index}.json", {
            "material_issues": [{"issue_id": f"ISSUE-{index}"}],
            "disagreements": ([{
                "claim": "runtime history", "status": "unresolved",
                "source_locator": "not a filing fact",
            }]
                              if role == "source_reconciliation" else []),
        })
        origins.append({
            "context_id": context_id, "role": role,
            "status": "retired_partial_history", "history_prefix": prefix,
            "artifact_sha256": artifact["sha256"],
            "artifact": artifact,
        })
    manifest = _write(tmp_path / "reconciliation-history-manifest.json", {
        "schema_version": 1, "kind": "synthetic_cross_role_history",
        "accession_number": accession,
        "counts": {"source_issues": 2, "reconciled_issues": 1, "disagreements": 1},
        "coverage_status": "partial", "eligible_source_evidence": False,
        "formal_source_evidence_sealed": False, "fresh_role_input": False,
        "limitations": ["Synthetic retired history only"],
        "retained_artifacts": [{
            **origin["artifact"], "bytes": (tmp_path / origin["artifact"]["path"]).stat().st_size,
        } for origin in origins[:3]],
        "source_exposed_contexts": [
            {"context_id": origin["context_id"], "retained_status": origin["status"],
             "role": origin["role"]} for origin in origins[:3]
        ],
    })
    source_role, source_sha = next(iter(sources[accession].items()))
    rows = []
    for index, origin in enumerate(origins):
        rows.append({
            "history_id": f"{origin['history_prefix']}:issue:ISSUE-{index + 1}",
            "source_context_id": origin["context_id"],
            "original_artifact_sha256": origin["artifact_sha256"], "status": "supported",
            "source_role": source_role, "source_sha256": source_sha,
            "source_locator": f"Item 7, paragraph {index + 1}",
            "reason": "Synthetic source support", "reconciled_issue_id": "revenue",
        })
    rows.append({
        "history_id": "old-reconciliation:disagreement:0",
        "source_context_id": origins[2]["context_id"],
        "original_artifact_sha256": origins[2]["artifact_sha256"], "status": "unresolved",
        "source_role": source_role, "source_sha256": source_sha,
        "source_locator": "No filing locator: synthetic runtime custody claim.",
        "reason": "Runtime retention is not a financial source fact", "reconciled_issue_id": None,
    })
    ledger_path = tmp_path / "reconciliation-history-ledger.json"
    ledger = _write(ledger_path, {
        "accession_number": accession, "history_dispositions": rows})
    draft = _write(tmp_path / "reconciliation-history-draft.json", {
        "retained": "raw custody draft; no semantic derivation asserted"})
    technical_attempts = []
    successor_reservations = []
    for suffix, role in (("a", "source_reference_a"), ("b", "source_reference_b")):
        context_id = f"ctx-technical-{suffix}"
        attempt_dir = tmp_path / f"technical-{suffix}"
        attempt_dir.mkdir()
        reservation = _write(attempt_dir / "reservation.json", {
            "schema_version": 1, "context_id": context_id, "role": role,
            "accession_number": accession, "actual_prompt_sha256": suffix * 64,
            "candidate_outputs_seen": False, "admission_approved": False,
        })
        reservation["path"] = str((attempt_dir / "reservation.json").relative_to(tmp_path))
        dispatch = _write(attempt_dir / "dispatch.json", {
            "returned_context": context_id, "prompt_sha256": suffix * 64,
            "reservation_sha256": reservation["sha256"], "admission_approved": False,
        })
        dispatch["path"] = str((attempt_dir / "dispatch.json").relative_to(tmp_path))
        children = {}
        for path in ("draft.json", "brief.md", "read-log.json"):
            child_path = attempt_dir / path
            if path == "draft.json":
                child_path.write_text(json.dumps({"material_issues": []}), encoding="utf-8")
            elif path.endswith(".json"):
                child_path.write_text(
                    json.dumps({"attempt": suffix, "artifact": path}), encoding="utf-8")
            else:
                child_path.write_text(f"{suffix}:{path}", encoding="utf-8")
            children[path] = hashlib.sha256(child_path.read_bytes()).hexdigest()
        settlement = _write(attempt_dir / "settlement.json", {
            "context_id": context_id, "status": "partial_ineligible",
            "reason": "Synthetic incomplete technical attempt", "artifacts": children,
            "issue_count": 0, "admission_approved": False,
        })
        settlement["path"] = str((attempt_dir / "settlement.json").relative_to(tmp_path))
        successor_context = next(
            row["context_id"] for row in current_briefs if row["role"] == role)
        successor = _write(attempt_dir / "successor-reservation.json", {
            "schema_version": 1, "context_id": successor_context, "role": role,
            "accession_number": accession, "retained_previous_attempt": children,
        })
        successor["path"] = str(
            (attempt_dir / "successor-reservation.json").relative_to(tmp_path))
        successor_reservations.append(successor)
        technical_attempts.append({
            "context_id": context_id, "role": role, "status": "partial_ineligible",
            "reservation": reservation, "dispatch": dispatch, "settlement": settlement,
        })
    closure = {
        *(row["context_id"] for row in current_briefs), reference["context_id"],
        *(origin["context_id"] for origin in origins),
        *(attempt["context_id"] for attempt in technical_attempts),
    }
    record = {
        "accession_number": accession, "schema_version": 1,
        "kind": "source_reconciliation_history",
        "current_reconciliation_context_id": reference["context_id"],
        "current_reconciliation": {key: current_reference[key] for key in ("path", "sha256")},
        "reconciliation_draft": draft,
        "history_manifest": manifest,
        "history_ledger": {
            **ledger, "row_count": len(rows),
            "identity_set_sha256": _canonical_set_sha256({row["history_id"] for row in rows}),
            "runtime_holds": [{"history_id": "old-reconciliation:disagreement:0",
                               "hold": "custodian_classification"}],
        },
        "origin_contexts": origins,
        "technical_attempts": technical_attempts,
        "source_context_closure_sha256": _canonical_set_sha256(closure),
    }
    ai["reconciliation_history"] = [record]
    authority_attempts = []
    for attempt, successor in zip(technical_attempts, successor_reservations, strict=True):
        settlement_value = json.loads((tmp_path / attempt["settlement"]["path"]).read_text())
        children = [{
            "basename": Path(child_path).name,
            "path": str((tmp_path / attempt["settlement"]["path"]).parent.joinpath(
                child_path).relative_to(tmp_path)),
            "sha256": child_sha,
        } for child_path, child_sha in sorted(settlement_value["artifacts"].items())]
        authority_attempts.append({
            **attempt, "settlement_artifacts": children, "successor_reservation": successor,
        })
    authority = {
        "schema_version": 1, "kind": "legacy_custody_migration",
        "approved_manifest_sha256": prereq["approved_manifest_sha256"],
        "accession_number": accession, "scope": "retrospective_retained_custody",
        "origin_contexts": origins, "attempts": authority_attempts,
        "limitations": [
            "Retrospective declaration of the operator-retained legacy custody set at migration; "
            "not provider-global completeness.",
            "No assertion of pre-dispatch journal chronology, private model attention, or "
            "unretained attempts.",
            "Custody verification does not establish financial correctness, semantic resolution, "
            "or programme admission.",
        ],
        "admission_authority": False, "semantic_resolution_authority": False,
    }
    authority_record = _write_canonical(tmp_path / "legacy-source-review-history.json", authority)
    ai["legacy_history_authorities"] = [{
        "accession_number": accession, "path": authority_record["path"],
    }]
    return record, ledger_path, authority_record["sha256"]


def _add_adverse_evidence(
    tmp_path: Path, prereq: dict, accession: str, sources: dict[str, dict[str, str]],
    *, reconciliation_context: str = "ctx-source_reconciliation",
    reconciled_issue_id: str = "revenue",
) -> dict:
    packets = [{"role": role, "sha256": sha} for role, sha in sources[accession].items()]
    issues = [{
        "issue_id": f"retired-{index}", "issue": f"Retired issue {index}",
        "source_role": "primary", "source_sha256": sources[accession]["primary"],
        "source_locator": f"Item 7, paragraph {index}",
        "amounts_and_bases": "USD million, FY2026", "qualifiers": "reported basis",
        "importance": "material trend", "disclosure_limits": "reported only",
    } for index in range(15)]
    retired_prompt_path = tmp_path / "retired-prompt.md"
    retired_prompt_path.write_text("Retired source review prompt", encoding="utf-8")
    retired_prompt = {"path": retired_prompt_path.name,
                      "sha256": hashlib.sha256(retired_prompt_path.read_bytes()).hexdigest()}
    narrative_path = tmp_path / "retired.md"
    narrative_path.write_text("Retired source review narrative", encoding="utf-8")
    narrative = {"path": narrative_path.name,
                 "sha256": hashlib.sha256(narrative_path.read_bytes()).hexdigest()}
    draft = _write(tmp_path / "retired.json", {
        "accession_number": accession, "source_packets": packets, "coverage_status": "complete",
        "context_window_truncated": True, "coverage_limits": "compacted", "material_issues": issues})
    read_log = _write(tmp_path / "retired-read-log.json", {
        "accession_number": accession, "reviewer_role": "source_reference_b",
        "coverage_status": "complete", "observed_context_window_truncated": True,
        "context_compaction_observed": True, "source_packets": packets})
    addendum = _write(tmp_path / "retired-addendum.json", {
        "accession_number": accession, "reviewer_role": "source_reference_b",
        "observed_compaction": {"occurred": True},
        "original_artifacts": [draft, narrative, read_log],
        "custodian_disposition": {"coverage_status": "partial", "eligibility": "ineligible"}})
    decision = _write(tmp_path / "retired-decision.json", {
        "accession_number": accession, "reference_b": {
            "context_id": "ctx-retired-source-b", "draft_sha256": draft["sha256"],
            "read_log_sha256": read_log["sha256"], "material_issue_count": len(issues),
            "context_compaction_observed": True,
            "custodian_coverage_disposition": "partial_ineligible",
            "individual_evidence_frozen": False}})
    prompt_path = tmp_path / "reconciliation-prompt.md"
    prompt_path.write_text(
        f"Bind {draft['sha256']} and {addendum['sha256']}; write a separate "
        f"adverse-dispositions.json with exactly {len(issues)} rows.", encoding="utf-8")
    reconciliation_prompt = {
        "path": prompt_path.name, "sha256": hashlib.sha256(prompt_path.read_bytes()).hexdigest()}
    current_hashes = {row["role"]: row["sha256"] for row in prereq["ai_assisted"]["source_briefs"]
                      if row["accession_number"] == accession}
    protocol = json.loads((tmp_path / prereq["ai_assisted"]["protocol"]["path"]).read_text())
    protocol_prompt_sha256 = next(
        role["prompt"]["sha256"] for role in protocol["roles"]
        if role["role"] == "source_reconciliation")
    reservation = _write(tmp_path / "reconciliation-reservation.json", {
        "requested_context_name": reconciliation_context,
        "prompt_sha256": reconciliation_prompt["sha256"],
        "protocol_prompt_sha256": protocol_prompt_sha256,
        "a_sha256": current_hashes["source_reference_a"],
        "b_sha256": current_hashes["source_reference_b"], "candidate_inputs": [],
        "admission_approved": False})
    dispositions = [{
        "source_context_id": "ctx-retired-source-b", "source_issue_id": item["issue_id"],
        "status": "supported", "reason": "Checked against source",
        "source_role": item["source_role"], "source_sha256": item["source_sha256"],
        "source_locator": item["source_locator"], "reconciled_issue_id": reconciled_issue_id,
    } for item in issues]
    ledger = _write(tmp_path / "adverse-dispositions.json", {
        "accession_number": accession, "source_context_id": "ctx-retired-source-b",
        "eligibility": "ineligible_due_to_observed_context_compaction",
        "original_draft_sha256": draft["sha256"],
        "status_addendum_sha256": addendum["sha256"], "adverse_dispositions": dispositions})
    row = {
        "accession_number": accession, "role": "source_reference_b",
        "context_id": "ctx-retired-source-b",
        "reconciliation_context_id": reconciliation_context,
        "terminal_status": "compacted_ineligible", "retired_prompt": retired_prompt,
        "draft": draft, "narrative": narrative, "read_log": read_log,
        "status_addendum": addendum, "custody_decision": decision,
        "reconciliation_prompt": reconciliation_prompt, "operator_reservation": reservation,
        "adverse_dispositions": ledger,
    }
    prereq["ai_assisted"]["adverse_source_evidence"] = [row]
    return row


def test_ai_source_evidence_keeps_unknown_exposure_visible_and_is_sealed(tmp_path: Path) -> None:
    prereq, path, accession, sources, now = _fixture(tmp_path)
    nested_record = prereq["ai_assisted"]["source_briefs"][0]
    original_brief_path = tmp_path / nested_record["path"]
    nested_brief = json.loads(original_brief_path.read_text())
    original_receipt_path = tmp_path / nested_brief["context_evidence"]["path"]
    nested_dir = tmp_path / "nested-a"
    nested_dir.mkdir()
    nested_brief_path = nested_dir / original_brief_path.name
    nested_receipt_path = nested_dir / original_receipt_path.name
    nested_brief_path.write_bytes(original_brief_path.read_bytes())
    nested_receipt_path.write_bytes(original_receipt_path.read_bytes())
    original_brief_path.unlink()
    original_receipt_path.unlink()
    nested_record["path"] = str(nested_brief_path.relative_to(tmp_path))
    issues, freezes, status, limitations = _validate(prereq, path, accession, sources, now)
    assert issues == []
    assert accession in freezes
    assert status == "no_known_candidate_exposure_external_unknown"
    assert any("unknown" in text for text in limitations)
    original_receipt_path.write_text("{}", encoding="utf-8")
    assert "ai_brief_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    original_receipt_path.unlink()
    receipt_bytes = nested_receipt_path.read_bytes()
    original_receipt_path.write_bytes(receipt_bytes)
    nested_receipt_path.write_text("{}", encoding="utf-8")
    assert "ai_brief_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    nested_receipt_path.write_bytes(receipt_bytes)
    original_receipt_path.unlink()
    inventory = ai_review_evidence_inventory(path, prereq)
    assert inventory["source_briefs"][0]["context_evidence"]["resolved_path"] == str(
        nested_receipt_path.resolve())
    assert len(inventory["source_briefs"]) == 2
    assert "adverse_source_evidence" not in inventory
    ordinary_inventory = inventory

    adverse = _add_adverse_evidence(tmp_path, prereq, accession, sources)
    path.write_text(json.dumps(prereq), encoding="utf-8")
    assert _validate(prereq, path, accession, sources, now)[0] == []
    addendum_path = tmp_path / adverse["status_addendum"]["path"]
    prompt_path = tmp_path / adverse["reconciliation_prompt"]["path"]
    reservation_path = tmp_path / adverse["operator_reservation"]["path"]
    ledger_path = tmp_path / adverse["adverse_dispositions"]["path"]
    original_addendum = json.loads(addendum_path.read_text())
    original_prompt = prompt_path.read_text()
    original_reservation = json.loads(reservation_path.read_text())
    original_ledger = json.loads(ledger_path.read_text())
    old_addendum_sha = adverse["status_addendum"]["sha256"]
    addendum = json.loads(json.dumps(original_addendum))
    addendum["original_artifacts"].append({"path": "undeclared-fourth.txt", "sha256": "d" * 64})
    adverse["status_addendum"].update(_write(addendum_path, addendum))
    prompt_path.write_text(
        original_prompt.replace(old_addendum_sha, adverse["status_addendum"]["sha256"]),
        encoding="utf-8")
    adverse["reconciliation_prompt"]["sha256"] = hashlib.sha256(prompt_path.read_bytes()).hexdigest()
    reservation = {**original_reservation,
                   "prompt_sha256": adverse["reconciliation_prompt"]["sha256"]}
    adverse["operator_reservation"].update(_write(reservation_path, reservation))
    ledger = {**original_ledger,
              "status_addendum_sha256": adverse["status_addendum"]["sha256"]}
    adverse["adverse_dispositions"].update(_write(ledger_path, ledger))
    assert "ai_adverse_source_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    adverse["status_addendum"].update(_write(addendum_path, original_addendum))
    prompt_path.write_text(original_prompt, encoding="utf-8")
    adverse["reconciliation_prompt"]["sha256"] = hashlib.sha256(prompt_path.read_bytes()).hexdigest()
    adverse["operator_reservation"].update(_write(reservation_path, original_reservation))
    adverse["adverse_dispositions"].update(_write(ledger_path, original_ledger))
    addendum = json.loads(json.dumps(original_addendum))
    addendum["original_artifacts"][0]["path"], addendum["original_artifacts"][1]["path"] = (
        addendum["original_artifacts"][1]["path"], addendum["original_artifacts"][0]["path"])
    adverse["status_addendum"].update(_write(addendum_path, addendum))
    prompt_path.write_text(
        original_prompt.replace(old_addendum_sha, adverse["status_addendum"]["sha256"]),
        encoding="utf-8")
    adverse["reconciliation_prompt"]["sha256"] = hashlib.sha256(prompt_path.read_bytes()).hexdigest()
    reservation = {**original_reservation,
                   "prompt_sha256": adverse["reconciliation_prompt"]["sha256"]}
    adverse["operator_reservation"].update(_write(reservation_path, reservation))
    ledger = {**original_ledger,
              "status_addendum_sha256": adverse["status_addendum"]["sha256"]}
    adverse["adverse_dispositions"].update(_write(ledger_path, ledger))
    assert "ai_adverse_source_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    adverse["status_addendum"].update(_write(addendum_path, original_addendum))
    prompt_path.write_text(original_prompt, encoding="utf-8")
    adverse["reconciliation_prompt"]["sha256"] = hashlib.sha256(prompt_path.read_bytes()).hexdigest()
    adverse["operator_reservation"].update(_write(reservation_path, original_reservation))
    adverse["adverse_dispositions"].update(_write(ledger_path, original_ledger))
    alternate_ledger = json.loads(json.dumps(original_ledger))
    alternate_ledger["adverse_dispositions"][0].update(
        source_role="index", source_sha256="b" * 64,
        source_locator="Index source independently confirms the retained issue")
    adverse["adverse_dispositions"].update(_write(ledger_path, alternate_ledger))
    issues, _, _, adverse_limitations = _validate(prereq, path, accession, sources, now)
    assert "ai_adverse_source_invalid" not in {item["code"] for item in issues}
    assert any("reattribute" in text for text in adverse_limitations)
    adverse["adverse_dispositions"].update(_write(ledger_path, original_ledger))
    adverse_inventory = ai_review_evidence_inventory(path, prereq)
    assert len(adverse_inventory["adverse_source_evidence"][0]["artifacts"]) == 9
    assert len(adverse_inventory["source_briefs"]) == 2
    del prereq["ai_assisted"]["adverse_source_evidence"]
    assert ai_review_evidence_inventory(path, prereq) == ordinary_inventory
    prereq["ai_assisted"]["adverse_source_evidence"] = [adverse]
    inventory = adverse_inventory
    with sqlite3.connect(tmp_path / "budget.sqlite3") as db:
        db.execute("CREATE TABLE binding (id INTEGER PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO binding VALUES (1, ?)", (json.dumps({"review_evidence": inventory}),))
    verify_review_evidence_binding(tmp_path, path)

    # A coherent rewrite and updated inline hash still differs from the original seal.
    retired_prompt_path = tmp_path / adverse["retired_prompt"]["path"]
    retired_prompt_path.write_text("Changed retired prompt", encoding="utf-8")
    adverse["retired_prompt"]["sha256"] = hashlib.sha256(retired_prompt_path.read_bytes()).hexdigest()
    path.write_text(json.dumps(prereq), encoding="utf-8")
    assert _validate(prereq, path, accession, sources, now)[0] == []
    with pytest.raises(ValueError, match="review evidence differs"):
        verify_review_evidence_binding(tmp_path, path)

    for mutation, expected in (("omitted", "ai_adverse_source_invalid"),
                               ("unresolved", "ai_adverse_source_issue_unresolved"),
                               ("invalid_status", "ai_adverse_source_invalid"),
                               ("wrong_source", "ai_adverse_source_invalid"),
                               ("wrong_target", "ai_adverse_source_invalid")):
        ledger = json.loads(json.dumps(original_ledger))
        if mutation == "omitted":
            ledger["adverse_dispositions"].pop()
        elif mutation == "unresolved":
            ledger["adverse_dispositions"][0].update(status="unresolved", reconciled_issue_id=None)
        elif mutation == "invalid_status":
            ledger["adverse_dispositions"][0]["status"] = "omitted"
        elif mutation == "wrong_source":
            ledger["adverse_dispositions"][0]["source_sha256"] = "f" * 64
        else:
            ledger["adverse_dispositions"][0]["reconciled_issue_id"] = "missing"
        adverse["adverse_dispositions"].update(_write(ledger_path, ledger))
        codes = {item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
        assert expected in codes
    adverse["adverse_dispositions"].update(_write(ledger_path, original_ledger))

    for field, value in (("prompt_sha256", "f" * 64),
                         ("protocol_prompt_sha256", "f" * 64),
                         ("admission_approved", True)):
        reservation = {**original_reservation, field: value}
        adverse["operator_reservation"].update(_write(reservation_path, reservation))
        codes = {item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
        assert "ai_adverse_source_invalid" in codes


def test_cross_role_history_binds_typed_rows_and_excludes_every_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    prereq, path, accession, sources, now = _fixture(tmp_path)
    ordinary_inventory = ai_review_evidence_inventory(path, prereq)
    assert "legacy_history_authorities" not in ordinary_inventory
    assert "reconciliation_history" not in ordinary_inventory
    record, ledger_path, authority_sha256 = _add_reconciliation_history(
        tmp_path, prereq, accession, sources)
    monkeypatch.setitem(
        acceptance_legacy_history.APPROVED_LEGACY_HISTORY_AUTHORITIES,
        prereq["approved_manifest_sha256"], {accession: authority_sha256})
    path.write_text(json.dumps(prereq), encoding="utf-8")

    issues, _, _, limitations = _validate(prereq, path, accession, sources, now)
    assert issues == []
    assert any("declared custodian classification" in text for text in limitations)
    inventory = ai_review_evidence_inventory(path, prereq)
    history = inventory["reconciliation_history"][0]
    assert len(history["typed_rows"]) == 5
    assert sum(row["evidence_class"] == "filing_source" for row in history["typed_rows"]) == 4
    runtime = next(row for row in history["typed_rows"] if row["evidence_class"] == "operator_runtime")
    assert runtime["filing_source_locator"] is None
    assert runtime["reconciled_issue_id"] is None
    assert runtime["hold"] == "custodian_classification"
    history_contexts = ({origin["context_id"] for origin in record["origin_contexts"]} |
                        {attempt["context_id"] for attempt in record["technical_attempts"]})
    assert history_contexts <= source_context_ids(prereq, tmp_path)
    assert len(history["origin_artifacts"]) == 4
    assert len(history["retained_artifacts"]) == 3
    assert len(history["technical_attempts"]) == 2
    assert inventory["legacy_history_authorities"][0]["authority"][
        "expected_sha256"] == authority_sha256
    assert all(len(attempt["settlement_artifacts"]) == 3
               for attempt in history["technical_attempts"])
    assert history["reconciliation_draft"]["bytes_sha256"] == record["reconciliation_draft"][
        "sha256"]

    original_wrapper = prereq["ai_assisted"]["reconciliation_history"]
    original_locations = prereq["ai_assisted"]["legacy_history_authorities"]
    original_manifest_sha256 = prereq["approved_manifest_sha256"]
    for omit_wrapper, omit_location, alter_manifest in (
        (True, False, False), (False, True, False), (True, True, False), (True, True, True),
    ):
        if omit_wrapper:
            del prereq["ai_assisted"]["reconciliation_history"]
        if omit_location:
            del prereq["ai_assisted"]["legacy_history_authorities"]
        if alter_manifest:
            prereq["approved_manifest_sha256"] = "d" * 64
        assert "ai_reconciliation_history_invalid" in {
            item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
        with pytest.raises(ValueError, match="legacy history|reconciliation history"):
            ai_review_evidence_inventory(path, prereq)
        with pytest.raises(ValueError, match="legacy history|reconciliation history"):
            source_context_ids(prereq, tmp_path)
        prereq["ai_assisted"]["reconciliation_history"] = original_wrapper
        prereq["ai_assisted"]["legacy_history_authorities"] = original_locations
        prereq["approved_manifest_sha256"] = original_manifest_sha256

    authority_path = tmp_path / original_locations[0]["path"]
    original_authority_bytes = authority_path.read_bytes()
    incomplete_authority = json.loads(original_authority_bytes)
    incomplete_authority["attempts"].pop()
    _write_canonical(authority_path, incomplete_authority)
    with pytest.raises(ValueError, match="digest differs"):
        ai_review_evidence_inventory(path, prereq)
    authority_path.write_bytes(original_authority_bytes)

    other_accession = "0000000002-26-000002"
    other, _, _, _, _ = _fixture(
        tmp_path, accession=other_accession, prefix="successor-other-")
    prereq["ai_assisted"]["source_briefs"].extend(other["ai_assisted"]["source_briefs"])
    prereq["ai_assisted"]["reconciled_references"].extend(
        other["ai_assisted"]["reconciled_references"])
    wrong_successor_authority = json.loads(original_authority_bytes)
    wrong_successor_authority["attempts"][0]["successor_reservation"] = _write(
        tmp_path / "wrong-successor.json", {
            "schema_version": 1,
            "context_id": other["ai_assisted"]["source_briefs"][0]["context_id"],
            "role": "source_reference_a", "accession_number": accession,
            "retained_previous_attempt": {
                child["basename"]: child["sha256"]
                for child in wrong_successor_authority["attempts"][0]["settlement_artifacts"]
            },
        })
    wrong_successor = _write_canonical(authority_path, wrong_successor_authority)
    monkeypatch.setitem(
        acceptance_legacy_history.APPROVED_LEGACY_HISTORY_AUTHORITIES[
            prereq["approved_manifest_sha256"]], accession, wrong_successor["sha256"])
    with pytest.raises(ValueError, match="owned by another accession"):
        ai_review_evidence_inventory(path, prereq)
    authority_path.write_bytes(original_authority_bytes)
    monkeypatch.setitem(
        acceptance_legacy_history.APPROVED_LEGACY_HISTORY_AUTHORITIES[
            prereq["approved_manifest_sha256"]], accession, authority_sha256)
    del prereq["ai_assisted"]["source_briefs"][-2:]
    del prereq["ai_assisted"]["reconciled_references"][-1:]
    original_ledger = json.loads(ledger_path.read_text())

    def invalid(mutator) -> None:
        ledger = json.loads(json.dumps(original_ledger))
        declaration = json.loads(json.dumps(record["history_ledger"]))
        mutator(ledger, declaration)
        declaration.update(_write(ledger_path, ledger))
        record["history_ledger"] = declaration
        assert "ai_reconciliation_history_invalid" in {
            item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
        record["history_ledger"] = json.loads(json.dumps(original_declaration))
        ledger_path.write_text(original_ledger_bytes, encoding="utf-8")

    original_declaration = json.loads(json.dumps(record["history_ledger"]))
    original_ledger_bytes = ledger_path.read_text()

    def drop_and_reseal(ledger, declaration) -> None:
        ledger["history_dispositions"].pop(2)
        declaration["row_count"] = len(ledger["history_dispositions"])
        declaration["identity_set_sha256"] = _canonical_set_sha256({
            row["history_id"] for row in ledger["history_dispositions"]})

    def swap_origin_provenance(ledger, declaration) -> None:
        del declaration
        first = ledger["history_dispositions"][0]
        second = ledger["history_dispositions"][1]
        first["source_context_id"], second["source_context_id"] = (
            second["source_context_id"], first["source_context_id"])
        first["original_artifact_sha256"], second["original_artifact_sha256"] = (
            second["original_artifact_sha256"], first["original_artifact_sha256"])

    def swap_runtime_hold(ledger, declaration) -> None:
        runtime = next(row for row in ledger["history_dispositions"]
                       if row["history_id"] == "old-reconciliation:disagreement:0")
        financial = ledger["history_dispositions"][0]
        runtime.update(status="supported", reconciled_issue_id="revenue")
        financial.update(status="unresolved", reconciled_issue_id=None)
        declaration["runtime_holds"] = [{
            "history_id": financial["history_id"], "hold": "custodian_classification"}]

    invalid(drop_and_reseal)
    invalid(lambda ledger, declaration: ledger["history_dispositions"][1].update(
        history_id=ledger["history_dispositions"][0]["history_id"]))
    invalid(lambda ledger, declaration: ledger["history_dispositions"][0].update(
        history_id="unknown:changed"))
    invalid(lambda ledger, declaration: ledger["history_dispositions"][0].update(
        source_context_id="ctx-unknown-origin"))
    invalid(lambda ledger, declaration: ledger["history_dispositions"][0].update(
        original_artifact_sha256="f" * 64))
    invalid(swap_origin_provenance)
    invalid(lambda ledger, declaration: ledger["history_dispositions"][0].update(
        reconciled_issue_id="unknown-target"))
    invalid(lambda ledger, declaration: ledger["history_dispositions"][0].update(
        source_locator=""))
    invalid(lambda ledger, declaration: ledger["history_dispositions"][-1].update(
        status="supported"))
    invalid(lambda ledger, declaration: ledger["history_dispositions"][-1].update(
        reconciled_issue_id="revenue"))
    invalid(lambda ledger, declaration: declaration.update(runtime_holds=[]))
    invalid(swap_runtime_hold)

    record["history_ledger"] = original_declaration
    ledger_path.write_text(original_ledger_bytes, encoding="utf-8")

    record["schema_version"] = True
    assert "ai_reconciliation_history_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    record["schema_version"] = 1

    manifest_path = tmp_path / record["history_manifest"]["path"]
    original_manifest = json.loads(manifest_path.read_text())
    boolean_manifest = json.loads(json.dumps(original_manifest))
    boolean_manifest["schema_version"] = True
    record["history_manifest"].update(_write(manifest_path, boolean_manifest))
    assert "ai_reconciliation_history_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    record["history_manifest"].update(_write(manifest_path, original_manifest))

    missing_count_manifest = json.loads(json.dumps(original_manifest))
    del missing_count_manifest["counts"]["source_issues"]
    record["history_manifest"].update(_write(manifest_path, missing_count_manifest))
    assert "ai_reconciliation_history_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    record["history_manifest"].update(_write(manifest_path, original_manifest))

    draft_sha = record["reconciliation_draft"]["sha256"]
    record["reconciliation_draft"]["sha256"] = int("1" * 64)
    assert "ai_reconciliation_history_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    record["reconciliation_draft"]["sha256"] = draft_sha

    original_attempts = json.loads(json.dumps(record["technical_attempts"]))
    original_closure = record["source_context_closure_sha256"]
    record["technical_attempts"] = record["technical_attempts"][:-1]
    current_contexts = {
        row["context_id"] for row in prereq["ai_assisted"]["source_briefs"]
        if row["accession_number"] == accession
    }
    current_contexts.add(json.loads((tmp_path / prereq["ai_assisted"][
        "reconciled_references"][0]["path"]).read_text())["context_id"])
    record["source_context_closure_sha256"] = _canonical_set_sha256(
        current_contexts |
        {row["context_id"] for row in record["origin_contexts"]} |
        {row["context_id"] for row in record["technical_attempts"]})
    assert "ai_reconciliation_history_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    record["technical_attempts"] = json.loads(json.dumps(original_attempts))
    record["source_context_closure_sha256"] = original_closure
    record["technical_attempts"][0]["settlement"], record["technical_attempts"][1][
        "settlement"] = (record["technical_attempts"][1]["settlement"],
                          record["technical_attempts"][0]["settlement"])
    assert "ai_reconciliation_history_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    record["technical_attempts"] = original_attempts

    # Removing the unmanifested same-context origin and coherently resealing its ledger used to
    # leave a self-consistent wrapper. The reviewed authority independently fixes the origin set.
    original_origins = json.loads(json.dumps(record["origin_contexts"]))
    omitted_origin = record["origin_contexts"].pop()
    omitted_prefix = f"{omitted_origin['history_prefix']}:"
    omitted_ledger = json.loads(original_ledger_bytes)
    omitted_ledger["history_dispositions"] = [
        row for row in omitted_ledger["history_dispositions"]
        if not row["history_id"].startswith(omitted_prefix)
    ]
    omitted_declaration = json.loads(json.dumps(original_declaration))
    omitted_declaration["row_count"] = len(omitted_ledger["history_dispositions"])
    omitted_declaration["identity_set_sha256"] = _canonical_set_sha256({
        row["history_id"] for row in omitted_ledger["history_dispositions"]})
    omitted_declaration.update(_write(ledger_path, omitted_ledger))
    record["history_ledger"] = omitted_declaration
    assert "ai_reconciliation_history_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    record["origin_contexts"] = original_origins
    record["history_ledger"] = json.loads(json.dumps(original_declaration))
    ledger_path.write_text(original_ledger_bytes, encoding="utf-8")

    technical = record["technical_attempts"][0]
    reservation_path = tmp_path / technical["reservation"]["path"]
    dispatch_path = tmp_path / technical["dispatch"]["path"]
    original_reservation = json.loads(reservation_path.read_text())
    original_dispatch = json.loads(dispatch_path.read_text())
    invalid_prompt_reservation = {
        **original_reservation, "actual_prompt_sha256": "not-a-digest",
    }
    technical["reservation"].update(_write(reservation_path, invalid_prompt_reservation))
    technical["reservation"]["path"] = str(reservation_path.relative_to(tmp_path))
    invalid_prompt_dispatch = {
        **original_dispatch,
        "prompt_sha256": invalid_prompt_reservation["actual_prompt_sha256"],
        "reservation_sha256": technical["reservation"]["sha256"],
    }
    technical["dispatch"].update(_write(dispatch_path, invalid_prompt_dispatch))
    technical["dispatch"]["path"] = str(dispatch_path.relative_to(tmp_path))
    assert "ai_reconciliation_history_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    technical["reservation"].update(_write(reservation_path, original_reservation))
    technical["reservation"]["path"] = str(reservation_path.relative_to(tmp_path))
    technical["dispatch"].update(_write(dispatch_path, original_dispatch))
    technical["dispatch"]["path"] = str(dispatch_path.relative_to(tmp_path))

    settlement_path = tmp_path / technical["settlement"]["path"]
    original_settlement = json.loads(settlement_path.read_text())
    original_dispatch_declaration = json.loads(json.dumps(technical["dispatch"]))
    original_settlement_declaration = json.loads(json.dumps(technical["settlement"]))
    union_path = settlement_path.parent / "dispatch-settlement-union.json"
    union_reference = _write(union_path, {**original_dispatch, **original_settlement})
    union_reference["path"] = str(union_path.relative_to(tmp_path))
    technical["dispatch"] = json.loads(json.dumps(union_reference))
    technical["settlement"] = json.loads(json.dumps(union_reference))
    assert "ai_reconciliation_history_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    technical["dispatch"] = original_dispatch_declaration
    technical["settlement"] = original_settlement_declaration

    technical_alias = record["technical_attempts"][1]
    current_brief = next(
        row for row in prereq["ai_assisted"]["source_briefs"]
        if row["role"] == "source_reference_b")
    current_brief_bytes = (tmp_path / current_brief["path"]).read_bytes()
    alias_settlement_path = tmp_path / technical_alias["settlement"]["path"]
    alias_child_path = alias_settlement_path.parent / "brief.md"
    original_alias_child_bytes = alias_child_path.read_bytes()
    original_alias_settlement = json.loads(alias_settlement_path.read_text())
    original_alias_settlement_declaration = json.loads(json.dumps(technical_alias["settlement"]))
    alias_child_path.write_bytes(current_brief_bytes)
    alias_settlement = json.loads(json.dumps(original_alias_settlement))
    alias_settlement["artifacts"]["brief.md"] = current_brief["sha256"]
    technical_alias["settlement"].update(_write(alias_settlement_path, alias_settlement))
    technical_alias["settlement"]["path"] = str(alias_settlement_path.relative_to(tmp_path))
    assert "ai_reconciliation_history_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    alias_child_path.write_bytes(original_alias_child_bytes)
    _write(alias_settlement_path, original_alias_settlement)
    technical_alias["settlement"] = original_alias_settlement_declaration

    positive_settlement = json.loads(json.dumps(original_settlement))
    positive_settlement["issue_count"] = 1
    technical["settlement"].update(_write(settlement_path, positive_settlement))
    technical["settlement"]["path"] = str(settlement_path.relative_to(tmp_path))
    assert "ai_reconciliation_history_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    technical["settlement"].update(_write(settlement_path, original_settlement))
    technical["settlement"]["path"] = str(settlement_path.relative_to(tmp_path))

    for omitted_artifact in ("brief.md", "read-log.json"):
        incomplete_settlement = json.loads(json.dumps(original_settlement))
        del incomplete_settlement["artifacts"][omitted_artifact]
        technical["settlement"].update(_write(settlement_path, incomplete_settlement))
        technical["settlement"]["path"] = str(settlement_path.relative_to(tmp_path))
        assert "ai_reconciliation_history_invalid" in {
            item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
        technical["settlement"].update(_write(settlement_path, original_settlement))
        technical["settlement"]["path"] = str(settlement_path.relative_to(tmp_path))

    draft_path = settlement_path.parent / "draft.json"
    original_draft = json.loads(draft_path.read_text())
    draft_path.write_text(json.dumps({"material_issues": [{"issue_id": "omitted"}]}),
                          encoding="utf-8")
    changed_settlement = json.loads(json.dumps(original_settlement))
    changed_settlement["artifacts"]["draft.json"] = hashlib.sha256(
        draft_path.read_bytes()).hexdigest()
    technical["settlement"].update(_write(settlement_path, changed_settlement))
    technical["settlement"]["path"] = str(settlement_path.relative_to(tmp_path))
    assert "ai_reconciliation_history_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    draft_path.write_text(json.dumps(original_draft), encoding="utf-8")
    technical["settlement"].update(_write(settlement_path, original_settlement))
    technical["settlement"]["path"] = str(settlement_path.relative_to(tmp_path))

    retained_path = tmp_path / record["history_manifest"]["path"]
    retained_manifest = json.loads(retained_path.read_text())
    first_retained = tmp_path / retained_manifest["retained_artifacts"][0]["path"]
    original_retained_bytes = first_retained.read_bytes()
    first_retained.write_bytes(original_retained_bytes + b"changed")
    assert "ai_reconciliation_history_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    first_retained.write_bytes(original_retained_bytes)

    same_context_origin = next(
        row for row in record["origin_contexts"]
        if row["history_prefix"] == "same-context-a-partial")
    original_same_context_origin = json.loads(json.dumps(same_context_origin))
    current_brief = next(
        row for row in prereq["ai_assisted"]["source_briefs"]
        if row["context_id"] == same_context_origin["context_id"])
    same_context_origin.update({
        "artifact_sha256": current_brief["sha256"],
        "artifact": {key: current_brief[key] for key in ("path", "sha256")},
    })
    aliased_ledger = json.loads(original_ledger_bytes)
    aliased_row = next(
        row for row in aliased_ledger["history_dispositions"]
        if row["history_id"].startswith("same-context-a-partial:"))
    aliased_row.update({
        "history_id": "same-context-a-partial:issue:revenue",
        "original_artifact_sha256": current_brief["sha256"],
    })
    aliased_declaration = json.loads(json.dumps(original_declaration))
    aliased_declaration["identity_set_sha256"] = _canonical_set_sha256({
        row["history_id"] for row in aliased_ledger["history_dispositions"]})
    aliased_declaration.update(_write(ledger_path, aliased_ledger))
    record["history_ledger"] = aliased_declaration
    assert "ai_reconciliation_history_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    same_context_origin.clear()
    same_context_origin.update(original_same_context_origin)
    record["history_ledger"] = json.loads(json.dumps(original_declaration))
    ledger_path.write_text(original_ledger_bytes, encoding="utf-8")

    first_origin = record["origin_contexts"][0]
    duplicate_origin = record["origin_contexts"][1]
    original_duplicate_origin = json.loads(json.dumps(duplicate_origin))
    duplicate_origin.update({
        "artifact_sha256": first_origin["artifact_sha256"],
        "artifact": json.loads(json.dumps(first_origin["artifact"])),
    })
    duplicate_manifest = json.loads(json.dumps(original_manifest))
    duplicate_manifest["retained_artifacts"] = [
        artifact for artifact in duplicate_manifest["retained_artifacts"]
        if artifact["sha256"] != original_duplicate_origin["artifact_sha256"]
    ]
    record["history_manifest"].update(_write(manifest_path, duplicate_manifest))
    duplicate_ledger = json.loads(original_ledger_bytes)
    duplicate_row = next(
        row for row in duplicate_ledger["history_dispositions"]
        if row["history_id"].startswith("old-b:"))
    duplicate_row.update({
        "history_id": "old-b:issue:ISSUE-1",
        "original_artifact_sha256": first_origin["artifact_sha256"],
    })
    duplicate_declaration = json.loads(json.dumps(original_declaration))
    duplicate_declaration["identity_set_sha256"] = _canonical_set_sha256({
        row["history_id"] for row in duplicate_ledger["history_dispositions"]})
    duplicate_declaration.update(_write(ledger_path, duplicate_ledger))
    record["history_ledger"] = duplicate_declaration
    assert "ai_reconciliation_history_invalid" in {
        item["code"] for item in _validate(prereq, path, accession, sources, now)[0]}
    duplicate_origin.clear()
    duplicate_origin.update(original_duplicate_origin)
    record["history_manifest"].update(_write(manifest_path, original_manifest))
    record["history_ledger"] = json.loads(json.dumps(original_declaration))
    ledger_path.write_text(original_ledger_bytes, encoding="utf-8")

    other_accession = "0000000002-26-000002"
    other, _, _, other_sources, _ = _fixture(
        tmp_path, accession=other_accession, prefix="other-")
    prereq["ai_assisted"]["source_briefs"].extend(
        other["ai_assisted"]["source_briefs"])
    prereq["ai_assisted"]["reconciled_references"].extend(
        other["ai_assisted"]["reconciled_references"])
    cross_accession_context = other["ai_assisted"]["source_briefs"][0]["context_id"]
    origin = record["origin_contexts"][0]
    original_origin_context = origin["context_id"]
    origin["context_id"] = cross_accession_context
    original_manifest_context = original_manifest["source_exposed_contexts"][0]["context_id"]
    original_manifest["source_exposed_contexts"][0]["context_id"] = cross_accession_context
    record["history_manifest"].update(_write(manifest_path, original_manifest))
    ledger = json.loads(ledger_path.read_text())
    ledger["history_dispositions"][0]["source_context_id"] = cross_accession_context
    record["history_ledger"].update(_write(ledger_path, ledger))
    current_contexts = {
        row["context_id"] for row in prereq["ai_assisted"]["source_briefs"]
        if row["accession_number"] == accession
    }
    current_reference = next(
        row for row in prereq["ai_assisted"]["reconciled_references"]
        if row["accession_number"] == accession)
    current_contexts.add(json.loads(
        (tmp_path / current_reference["path"]).read_text())["context_id"])
    record["source_context_closure_sha256"] = _canonical_set_sha256(
        current_contexts |
        {row["context_id"] for row in record["origin_contexts"]} |
        {row["context_id"] for row in record["technical_attempts"]})
    with pytest.raises(ValueError, match="owned by another accession"):
        ai_review_evidence_inventory(path, prereq)
    origin["context_id"] = original_origin_context
    original_manifest["source_exposed_contexts"][0]["context_id"] = original_manifest_context
    record["history_manifest"].update(_write(manifest_path, original_manifest))
    ledger["history_dispositions"][0]["source_context_id"] = original_origin_context
    record["history_ledger"].update(_write(ledger_path, ledger))

    other_reconciliation_context = json.loads((tmp_path / other["ai_assisted"][
        "reconciled_references"][0]["path"]).read_text())["context_id"]
    _add_adverse_evidence(
        tmp_path, other, other_accession, other_sources,
        reconciliation_context=other_reconciliation_context)
    prereq["ai_assisted"]["adverse_source_evidence"] = other["ai_assisted"][
        "adverse_source_evidence"]
    cross_accession_context = prereq["ai_assisted"]["adverse_source_evidence"][0]["context_id"]
    origin["context_id"] = cross_accession_context
    original_manifest["source_exposed_contexts"][0]["context_id"] = cross_accession_context
    record["history_manifest"].update(_write(manifest_path, original_manifest))
    ledger["history_dispositions"][0]["source_context_id"] = cross_accession_context
    record["history_ledger"].update(_write(ledger_path, ledger))
    record["source_context_closure_sha256"] = _canonical_set_sha256(
        current_contexts |
        {row["context_id"] for row in record["origin_contexts"]} |
        {row["context_id"] for row in record["technical_attempts"]})
    with pytest.raises(ValueError, match="owned by another accession"):
        ai_review_evidence_inventory(path, prereq)
    origin["context_id"] = original_origin_context
    original_manifest["source_exposed_contexts"][0]["context_id"] = original_manifest_context
    record["history_manifest"].update(_write(manifest_path, original_manifest))
    ledger["history_dispositions"][0]["source_context_id"] = original_origin_context
    record["history_ledger"].update(_write(ledger_path, ledger))
    del prereq["ai_assisted"]["adverse_source_evidence"]
    del prereq["ai_assisted"]["source_briefs"][-2:]
    del prereq["ai_assisted"]["reconciled_references"][-1:]
    record["source_context_closure_sha256"] = _canonical_set_sha256(
        current_contexts |
        {row["context_id"] for row in record["origin_contexts"]} |
        {row["context_id"] for row in record["technical_attempts"]})

    assert _validate(prereq, path, accession, sources, now)[0] == []


@pytest.mark.parametrize("mutation,code", [
    ("source_hash", "ai_brief_invalid"),
    ("candidate_seen", "ai_brief_invalid"),
    ("truncated", "ai_brief_invalid"),
    ("generated_output_key", "ai_brief_invalid"),
    ("candidate_context_input", "ai_brief_invalid"),
    ("reference_hash", "ai_reference_invalid"),
    ("dropped_brief_issue", "ai_reference_invalid"),
    ("unresolved_disagreement", "ai_source_disagreement_unresolved"),
    ("role_context", "ai_brief_coverage"),
    ("reconciliation_context", "ai_reference_invalid"),
    ("known_tuning_exposure", "ai_holdout_exposed"),
])
def test_ai_protocol_fails_closed_on_false_independence_or_source_claims(
    tmp_path: Path, mutation: str, code: str,
) -> None:
    prereq, path, accession, sources, now = _fixture(tmp_path)
    ai = prereq["ai_assisted"]
    if mutation == "role_context":
        ai["source_briefs"][1]["context_id"] = ai["source_briefs"][0]["context_id"]
        assert code in {issue["code"] for issue in _validate(prereq, path, accession, sources, now)[0]}
        return
    elif mutation == "known_tuning_exposure":
        record = ai["exposure_review"]
        value = json.loads((tmp_path / record["path"]).read_text())
        value["known_tuning_exposed_accessions"] = [accession]
    elif mutation == "candidate_context_input":
        record = ai["source_briefs"][0]
        brief_path = tmp_path / record["path"]
        brief = json.loads(brief_path.read_text())
        context_record = brief["context_evidence"]
        context_path = tmp_path / context_record["path"]
        context = json.loads(context_path.read_text())
        context["candidate_output_artifacts"] = [{"path": "candidate.json", "sha256": "f" * 64}]
        context_record.update(_write(context_path, context))
        record.update(_write(brief_path, brief))
        path.write_text(json.dumps(prereq), encoding="utf-8")
        issues, _, _, _ = _validate(prereq, path, accession, sources, now)
        assert code in {issue["code"] for issue in issues}
        return
    else:
        record = (ai["reconciled_references"][0] if mutation in
                  {"reference_hash", "unresolved_disagreement", "dropped_brief_issue", "reconciliation_context"}
                  else ai["source_briefs"][0])
        value = json.loads((tmp_path / record["path"]).read_text())
        if mutation == "source_hash":
            value["source_packets"][0]["sha256"] = "f" * 64
        elif mutation == "candidate_seen":
            value["candidate_outputs_seen"] = True
        elif mutation == "truncated":
            value["context_window_truncated"] = True
        elif mutation == "generated_output_key":
            value["candidate_output"] = "leaked summary"
        elif mutation == "reference_hash":
            value["source_brief_sha256"]["source_reference_a"] = "f" * 64
        elif mutation == "dropped_brief_issue":
            value["issue_dispositions"].pop()
        elif mutation == "reconciliation_context":
            value["context_id"] = ai["source_briefs"][0]["context_id"]
            context_record = value["context_evidence"]
            context_path = tmp_path / context_record["path"]
            context = json.loads(context_path.read_text())
            context["context_id"] = value["context_id"]
            context_record.update(_write(context_path, context))
        else:
            value["disagreements"] = [{
                "claim": "Revenue basis differs", "status": "unresolved",
                "resolution": "Both values retained pending source resolution",
                "source_role": "primary", "source_sha256": "a" * 64,
                "source_locator": "Item 7, paragraph 3"}]
    record.update(_write(tmp_path / record["path"], value))
    path.write_text(json.dumps(prereq), encoding="utf-8")
    issues, _, _, _ = _validate(prereq, path, accession, sources, now)
    assert code in {issue["code"] for issue in issues}


def test_source_contexts_are_fresh_per_filing_and_never_reused(tmp_path: Path) -> None:
    first, path, accession, sources, now = _fixture(tmp_path)
    second, _, other_accession, other_sources, later = _fixture(
        tmp_path, accession="0000000002-26-000002", prefix="second-")
    ai = first["ai_assisted"]
    ai["source_briefs"] += second["ai_assisted"]["source_briefs"]
    ai["reconciled_references"] += second["ai_assisted"]["reconciled_references"]
    protocol = json.loads((tmp_path / ai["protocol"]["path"]).read_text())
    protocol["frozen_at"] = later.isoformat()
    ai["protocol"].update(_write(tmp_path / "protocol.json", protocol))
    exposure = json.loads((tmp_path / ai["exposure_review"]["path"]).read_text())
    exposure["checked_accessions"] = [accession, other_accession]
    ai["exposure_review"].update(_write(tmp_path / "exposure.json", exposure))
    path.write_text(json.dumps(first), encoding="utf-8")
    combined_sources = {**sources, **other_sources}
    issues, freezes, _, _ = validate_ai_prerequisites(
        first, tmp_path, [accession, other_accession], combined_sources, later)
    assert issues == []
    assert set(freezes) == {accession, other_accession}
    assert len({row["context_id"] for row in ai["source_briefs"]}) == 4

    # Coherently rehash every dependent record; only context uniqueness rejects this.
    record = ai["source_briefs"][2]
    old_context = record["context_id"]
    record["context_id"] = ai["source_briefs"][0]["context_id"]
    brief_path = tmp_path / record["path"]
    brief = json.loads(brief_path.read_text())
    brief["context_id"] = record["context_id"]
    context_record = brief["context_evidence"]
    context_path = tmp_path / context_record["path"]
    context = json.loads(context_path.read_text())
    context["context_id"] = record["context_id"]
    context_record.update(_write(context_path, context))
    record.update(_write(brief_path, brief))
    reference_record = ai["reconciled_references"][1]
    reference_path = tmp_path / reference_record["path"]
    reference = json.loads(reference_path.read_text())
    reference["source_brief_sha256"]["source_reference_a"] = record["sha256"]
    for disposition in reference["issue_dispositions"]:
        if disposition["source_context_id"] == old_context:
            disposition["source_context_id"] = record["context_id"]
    context_record = reference["context_evidence"]
    context_path = tmp_path / context_record["path"]
    context = json.loads(context_path.read_text())
    context["input_brief_sha256"] = reference["source_brief_sha256"]
    context_record.update(_write(context_path, context))
    reference_record.update(_write(reference_path, reference))
    issues, _, _, _ = validate_ai_prerequisites(
        first, tmp_path, [accession, other_accession], combined_sources, later)
    assert "ai_brief_coverage" in {issue["code"] for issue in issues}
