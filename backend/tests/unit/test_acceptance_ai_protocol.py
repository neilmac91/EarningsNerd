"""AI-assisted E7 evidence is source-bound, sealed and never a human attestation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from evals.acceptance_ai_protocol import (ROLE_NAMES, ai_review_evidence_inventory,
                                          validate_ai_prerequisites)
from evals.acceptance_readiness import verify_review_evidence_binding


def _write(path: Path, value: object) -> dict[str, str]:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
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
