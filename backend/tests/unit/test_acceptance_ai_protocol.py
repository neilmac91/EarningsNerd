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


def test_ai_source_evidence_keeps_unknown_exposure_visible_and_is_sealed(tmp_path: Path) -> None:
    prereq, path, accession, sources, now = _fixture(tmp_path)
    issues, freezes, status, limitations = _validate(prereq, path, accession, sources, now)
    assert issues == []
    assert accession in freezes
    assert status == "no_known_candidate_exposure_external_unknown"
    assert any("unknown" in text for text in limitations)
    inventory = ai_review_evidence_inventory(path, prereq)
    assert len(inventory["source_briefs"]) == 2
    with sqlite3.connect(tmp_path / "budget.sqlite3") as db:
        db.execute("CREATE TABLE binding (id INTEGER PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO binding VALUES (1, ?)", (json.dumps({"review_evidence": inventory}),))
    verify_review_evidence_binding(tmp_path, path)

    # A coherent rewrite and updated inline hash still differs from the original seal.
    record = prereq["ai_assisted"]["reconciled_references"][0]
    reference_path = tmp_path / record["path"]
    reference = json.loads(reference_path.read_text())
    reference["material_issues"][0]["importance"] = "Changed after output"
    record.update(_write(reference_path, reference))
    path.write_text(json.dumps(prereq), encoding="utf-8")
    assert _validate(prereq, path, accession, sources, now)[0] == []
    with pytest.raises(ValueError, match="review evidence differs"):
        verify_review_evidence_binding(tmp_path, path)


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
