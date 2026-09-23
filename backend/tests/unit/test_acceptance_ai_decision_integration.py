"""Synthetic full E7 evidence graph exercises the offline decision wrapper."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest

from evals import acceptance_worker
from evals.acceptance_ai_decision import build_decision, _judge_input_sha
from evals.acceptance_ai_judge_evidence import _ARGV, MODEL
from evals.acceptance_outputs import inspect_outputs
from evals.acceptance_readiness import build_blinded_packets, review_evidence_inventory
from evals.judge import build_judge_messages
from evals.runner import _baseline_to_canonical
from tests.unit.test_acceptance_readiness import _fixture as human_fixture


def _write(path: Path, value: object) -> dict[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return {"path": str(path.relative_to(path.parent)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _v2_evidence(fixture: dict) -> dict:
    path = fixture["preflight"]
    base = path.parent
    original = json.loads(path.read_text())
    manifest = json.loads(fixture["manifest"].read_text())
    frozen = (fixture["now"] - timedelta(hours=2)).isoformat()
    prior = (fixture["now"] - timedelta(hours=3)).isoformat()
    roles = []
    for role in ("source_reference_a", "source_reference_b", "source_reconciliation",
                 "blind_quality", "source_challenge"):
        roles.append({"role": role, "provider": "synthetic-codex", "model": "gpt-6-astra",
                      "model_version": "synthetic-2026-09",
                      "prompt": _write(base / f"{role}-prompt.json", {"task": role}),
                      "contract": _write(base / f"{role}-contract.json", {"version": 2})})
    protocol = _write(base / "ai-protocol.json", {
        "schema_version": 3, "review_protocol": "ai_assisted", "frozen_at": frozen,
        "approved_manifest_sha256": fixture["manifest_sha"], "roles": roles})
    briefs = []
    references = []
    for filing in manifest["filings"]:
        accession = filing["accession_number"]
        name = filing["holdout_id"]
        packets = [{"role": p["role"], "sha256": p["sha256"]} for p in filing["source_packets"]]
        source_sha = next(p["sha256"] for p in packets if p["role"] == "primary")
        issue = {"issue_id": "i1", "issue": "Synthetic revenue issue", "source_role": "primary",
                 "source_sha256": source_sha, "source_locator": "line 1",
                 "amounts_and_bases": "USD, current filing", "qualifiers": "synthetic",
                 "importance": "material", "disclosure_limits": "only the supplied text"}
        brief_hashes = {}
        brief_contexts = {}
        for role in ("source_reference_a", "source_reference_b"):
            context = f"ctx-{name}-{role}"
            brief_contexts[role] = context
            receipt = _write(base / f"{name}-{role}-context.json", {
                "schema_version": 2, "review_protocol": "ai_assisted", "accession_number": accession,
                "context_id": context, "role": role, "observed_at": prior,
                "input_source_packets": packets, "input_brief_sha256": {},
                "candidate_output_artifacts": [], "source_only": True,
                "context_window_truncated": False})
            brief = _write(base / f"{name}-{role}-brief.json", {
                "schema_version": 2, "review_protocol": "ai_assisted", "accession_number": accession,
                "context_id": context, "frozen_at": prior, "source_only": True,
                "candidate_outputs_seen": False, "source_packets": packets,
                "coverage_status": "complete", "context_window_truncated": False,
                "coverage_limits": "synthetic complete packet set", "material_issues": [issue],
                "context_evidence": receipt})
            brief_hashes[role] = brief["sha256"]
            briefs.append({"accession_number": accession, "role": role,
                           "context_id": context, **brief})
        reconciliation_context = f"ctx-{name}-source_reconciliation"
        recon_receipt = _write(base / f"{name}-recon-context.json", {
            "schema_version": 2, "review_protocol": "ai_assisted", "accession_number": accession,
            "context_id": reconciliation_context, "role": "source_reconciliation",
            "observed_at": prior, "input_source_packets": packets,
            "input_brief_sha256": brief_hashes, "candidate_output_artifacts": [],
            "source_only": True, "context_window_truncated": False})
        ref = _write(base / f"{name}-reference.json", {
            "schema_version": 2, "review_protocol": "ai_assisted", "accession_number": accession,
            "context_id": reconciliation_context, "frozen_at": prior,
            "source_only": True, "candidate_outputs_seen": False,
            "source_packets": packets, "coverage_status": "complete",
            "context_window_truncated": False, "coverage_limits": "synthetic complete packet set",
            "source_brief_sha256": brief_hashes, "context_evidence": recon_receipt,
            "material_issues": [issue], "disagreements": [],
            "issue_dispositions": [{"source_context_id": brief_contexts[role],
                                    "source_issue_id": "i1", "status": "supported",
                                    "reason": "synthetic source match", "source_role": "primary",
                                    "source_sha256": source_sha, "source_locator": "line 1",
                                    "reconciled_issue_id": "i1"}
                                   for role in ("source_reference_a", "source_reference_b")]})
        references.append({"accession_number": accession, **ref})
    exposure = _write(base / "ai-exposure.json", {
        "schema_version": 2, "review_protocol": "ai_assisted",
        "checked_accessions": [f["accession_number"] for f in manifest["filings"]],
        "known_candidate_output_exposed_accessions": [], "known_tuning_exposed_accessions": [],
        "unknown_external_exposure": True, "external_artifact_inventory": "synthetic local set",
        "scope": "synthetic fixture", "observed_at": prior})
    original.update(schema_version=2, review_protocol="ai_assisted",
                    ai_assisted={"protocol": protocol, "source_briefs": briefs,
                                 "reconciled_references": references, "exposure_review": exposure})
    for old in ("reviewers", "adjudicator", "reference_briefs", "exposure_attestation"):
        original.pop(old)
    path.write_text(json.dumps(original), encoding="utf-8")
    return original


def _upgrade_collector(fixture: dict, prereq: dict) -> None:
    """Rebuild the synthetic fixture's durable seals as if v2 preceded dispatch."""
    root = fixture["outputs"].parent
    outputs = json.loads(fixture["outputs"].read_text())
    with sqlite3.connect(root / "budget.sqlite3") as db:
        db.execute("UPDATE binding SET value=? WHERE id=1", (json.dumps({
            "manifest": fixture["manifest_sha"],
            "configs": {arm: prereq[f"{arm}_config"]["sha256"]
                        for arm in ("candidate", "comparator")},
            "review_evidence": review_evidence_inventory(fixture["preflight"], prereq),
        }),))
        db.execute("ALTER TABLE reservations ADD COLUMN reserved_usd TEXT DEFAULT '0.01'")
        db.execute("ALTER TABLE reservations ADD COLUMN known_usage_upper_usd TEXT DEFAULT '0.01'")
        db.execute("CREATE TABLE programme (id INTEGER PRIMARY KEY, stop_reason TEXT)")
        db.execute("INSERT INTO programme VALUES (1, NULL)")
        for row in outputs["records"]:
            slot = row["slot_id"]
            invocation = root / slot / "attempt-1"
            grounding_path = invocation / "grounding.json"
            grounding = json.loads(grounding_path.read_text())
            source_text = (grounding.get("summarizer_calls") or [{}])[0].get("args", ["Synthetic excerpt"])[0]
            grounding["summarizer_calls"] = [{"args": [source_text, "Synthetic Co", "10-K"],
                                              "kwargs": {"filing_excerpt": "Synthetic excerpt",
                                                         "xbrl_metrics": None}}]
            _write(grounding_path, grounding)
            receipt_path = invocation / "receipt.json"
            receipt = json.loads(receipt_path.read_text())
            receipt["artifact_sha256"]["grounding"] = _bytes(grounding_path)
            _write(receipt_path, receipt)
            result = _write(invocation / "result.json", receipt)
            db.execute("UPDATE slots SET result_sha=? WHERE id=?", (result["sha256"], slot))
        smoke = root / "development-smoke" / "attempt-1"
        smoke.mkdir(parents=True)
        canonical = root / outputs["records"][0]["canonical_path"]
        (smoke / "canonical.json").write_bytes(canonical.read_bytes())
        _write(smoke / "grounding.json", {"summarizer_calls": [{
            "args": ["Synthetic excerpt", "Synthetic Co", "10-K"],
            "kwargs": {"filing_excerpt": "Synthetic excerpt", "xbrl_metrics": None}}]})
        smoke_receipt = {"artifacts": {"canonical_summary": "canonical.json", "grounding": "grounding.json"},
                         "artifact_sha256": {"canonical_summary": _bytes(smoke / "canonical.json"),
                                             "grounding": _bytes(smoke / "grounding.json")}}
        smoke_result = _write(smoke / "result.json", smoke_receipt)
        db.execute("UPDATE slots SET result_sha=? WHERE id='development-smoke'", (smoke_result["sha256"],))
    fixture["outputs"].write_text(json.dumps(inspect_outputs(
        root, root, expected_manifest_sha=fixture["manifest_sha"])), encoding="utf-8")


def _stdin_for(canonical: dict) -> str:
    _, user = build_judge_messages(_baseline_to_canonical(canonical),
                                   "Synthetic Co", "10-K", "Synthetic excerpt", "")
    return user


def _review_evidence(fixture: dict, prereq: dict, mapping_path: Path) -> Path:
    root = fixture["outputs"].parent
    base = fixture["preflight"].parent
    mapping = json.loads(mapping_path.read_text())
    outputs = json.loads(fixture["outputs"].read_text())
    manifest = json.loads(fixture["manifest"].read_text())
    filings = {f["accession_number"]: f for f in manifest["filings"]}
    by_identity = {(r["accession_number"], r["arm"], r["draw"]): r for r in outputs["records"]}
    challenges = {(p["accession_number"], p["arm"], p["draw"]): p
                  for p in mapping["packet_sets"]["ai-packet-2"]}
    protocol = json.loads((base / prereq["ai_assisted"]["protocol"]["path"]).read_text())
    roles = {r["role"]: r for r in protocol["roles"]}
    references = {r["accession_number"]: r for r in prereq["ai_assisted"]["reconciled_references"]}
    now = fixture["now"].isoformat()
    raw_verdict = json.dumps({"gate_failures": [], "dimensions": {
        "faithfulness": 5, "insight": 5, "clarity": 5, "specificity": 5},
        "verdict": "PASS", "notes": "synthetic source match"})
    stdout_payload = {"is_error": False, "subtype": "success", "result": raw_verdict}
    judge_entries = []
    assessments = []

    def judge_entry(slot: str, stdin: str, index: int) -> None:
        stdin_path = base / f"judge-{index}-stdin.txt"
        stdin_path.write_text(stdin, encoding="utf-8")
        input_ref = {"path": stdin_path.name, "sha256": _bytes(stdin_path)}
        stdout = _write(base / f"judge-{index}-stdout.json", stdout_payload)
        stderr_path = base / f"judge-{index}-stderr.txt"
        stderr_path.write_bytes(b"")
        stderr = {"path": stderr_path.name, "sha256": _bytes(stderr_path)}
        receipt = _write(base / f"judge-{index}-receipt.json", {
            "schema_version": 1, "programme_id": "E7", "slot_id": slot,
            "attempt": 1, "kind": "substantive", "invocation_id": f"synthetic-{index}",
            "model": MODEL, "contract_version": "2", "cli_version": "2.1.278",
            "auth_mode": "subscription_oauth_no_api_key", "argv": _ARGV,
            "exit_code": 0, "started_at": now, "finished_at": now,
            "input_sha256": input_ref["sha256"], "stdout_sha256": stdout["sha256"],
            "stderr_sha256": stderr["sha256"]})
        judge_entries.append({"slot_id": slot, "attempt": 1, "kind": "substantive",
                              "input": input_ref, "stdout": stdout, "stderr": stderr,
                              "receipt": receipt})

    for index, packet in enumerate(mapping["packet_sets"]["ai-packet-1"]):
        key = (packet["accession_number"], packet["arm"], packet["draw"])
        row = by_identity[key]
        slot = row["slot_id"]
        filing = filings[packet["accession_number"]]
        challenge = challenges[key]
        canonical = json.loads((root / row["canonical_path"]).read_text())
        stdin = _stdin_for(canonical)
        assert hashlib.sha256(stdin.encode()).hexdigest() == _judge_input_sha(
            canonical, json.loads((root / row["collector_evidence"]["grounding"]["path"]).read_text()))
        judge_entry(slot, stdin, index)
        reference_sha = references[packet["accession_number"]]["sha256"]
        grounding_sha = row["collector_evidence"]["grounding"]["sha256"]
        machine = {"schema_version": 1,
                   "selected": {"accession_number": packet["accession_number"],
                                "cik": str(filing["cik"])},
                   "sources": {p["role"]: {"sha256": p["sha256"],
                                           "accession_number": packet["accession_number"],
                                           "cik": str(filing["cik"]),
                                           "official_url": p["provenance"]["final_url"]}
                               for p in filing["source_packets"]},
                   "surfaces": {name: {"sha256": artifact["sha256"], "claims": []}
                                for name, artifact in packet["reviewer_artifacts"].items()}}
        machine_ref = _write(base / f"machine-{index}.json", machine)
        common = {"schema_version": 1, "review_protocol": "ai_assisted",
                  "reference_sha256": reference_sha, "grounding_sha256": grounding_sha,
                  "machine_inventory_sha256": machine_ref["sha256"],
                  "claim_inventory_coverage": "all_detected_claims_inventoried"}
        quality_context = "ctx-blind-quality-shared"
        challenge_context = "ctx-source-challenge-shared"
        quality = {**common, "role_identity": roles["blind_quality"],
                   "context_id": quality_context,
                   "packet_id": packet["packet_id"],
                   "reviewer_artifacts": packet["reviewer_artifacts"],
                   "completeness": 5, "usefulness": 5,
                   "completeness_reason": "synthetic complete", "usefulness_reason": "synthetic clear",
                   "allegations": []}
        source = {**common, "role_identity": roles["source_challenge"],
                  "context_id": challenge_context,
                  "packet_id": challenge["packet_id"],
                  "reviewer_artifacts": challenge["reviewer_artifacts"],
                  "checks": {k: "checked" for k in
                             ("numeric_claims", "causal_claims", "financial_basis", "quotations", "citations")},
                  "findings": []}
        semantic = {"schema_version": 1, "packet_id": packet["packet_id"],
                    "grounding_sha256": grounding_sha,
                    "reviewer_artifacts": packet["reviewer_artifacts"],
                    "model": MODEL, "contract_version": "2", "error": None,
                    "grounding_truncated": False, "raw": raw_verdict}
        assessment = {"schema_version": 1, "review_protocol": "ai_assisted",
                      "packet_id": packet["packet_id"],
                      "quality_context_id": quality_context,
                      "challenge_context_id": challenge_context,
                      "reviewer_artifacts": packet["reviewer_artifacts"],
                      "surfaces_checked": sorted(packet["reviewer_artifacts"]),
                      "grounding_sha256": grounding_sha, "reference_sha256": reference_sha,
                      "machine_inventory": machine_ref,
                      "quality_response": _write(base / f"quality-{index}.json", quality),
                      "challenge_response": _write(base / f"challenge-{index}.json", source),
                      "semantic_response": _write(base / f"semantic-{index}.json", semantic),
                      "completeness": 5, "usefulness": 5,
                      "completeness_reason": "synthetic complete",
                      "usefulness_reason": "synthetic clear",
                      "semantic": {"model": MODEL, "contract_version": "2", "status": "complete",
                                   "grounding_truncated": False, "verdict": "pass"},
                      "checks": source["checks"], "findings": []}
        assessments.append(_write(base / f"assessment-{index}.json", assessment))
    smoke = root / "development-smoke" / "attempt-1"
    judge_entry("development-smoke", _stdin_for(json.loads((smoke / "canonical.json").read_text())), 120)
    judge_ledger = _write(base / "judge-ledger.json", {
        "schema_version": 1, "programme_id": "E7", "kind": "e7_fable_cli_ledger",
        "model": MODEL, "contract_version": "2", "cli_version": "2.1.278",
        "entries": judge_entries})
    evidence_path = base / "ai-assessments.json"
    _write(evidence_path, {"schema_version": 1, "review_protocol": "ai_assisted",
                           "mapping_sha256": _bytes(mapping_path),
                           "protocol_sha256": prereq["ai_assisted"]["protocol"]["sha256"],
                           "judge_ledger": judge_ledger, "assessments": assessments})
    return evidence_path


def _full_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(acceptance_worker, "archive_binding_hold", lambda: None)
    fixture = human_fixture(tmp_path)
    prereq = _v2_evidence(fixture)
    _upgrade_collector(fixture, prereq)
    packets_root, custodian = tmp_path / "ai-packets", tmp_path / "ai-custodian"
    build_blinded_packets(fixture["manifest"], fixture["archive"], fixture["preflight"],
                          fixture["outputs"], packets_root, custodian,
                          expected_manifest_sha=fixture["manifest_sha"])
    mapping_path = custodian / "mapping.json"
    evidence_path = _review_evidence(fixture, prereq, mapping_path)
    return {**fixture, "mapping": mapping_path, "packets": packets_root,
            "evidence": evidence_path}


def _decide(fixture: dict) -> dict:
    return build_decision(fixture["manifest"], fixture["archive"], fixture["preflight"],
                          fixture["outputs"], fixture["mapping"], fixture["evidence"],
                          fixture["packets"], expected_manifest_sha=fixture["manifest_sha"])


def test_full_ai_decision_uses_retained_packet_and_judge_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _full_fixture(tmp_path, monkeypatch)
    report = _decide(fixture)
    assert report["status"] == "pass"
    assert report["joint_at_least_4"] == 90
    assert report["human_acceptance"] is False
    assert report["exposure_status"] == "no_known_candidate_exposure_external_unknown"

    index_path = fixture["packets"] / "ai-packet-1" / "index.json"
    original_index = index_path.read_bytes()
    index = json.loads(original_index)
    index["packets"][0]["packet_dir"] = index["packets"][1]["packet_dir"]
    index_path.write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(ValueError, match="index points to a different packet"):
        _decide(fixture)
    index_path.write_bytes(original_index)

    mapping = json.loads(fixture["mapping"].read_text())
    copied = fixture["packets"] / "ai-packet-1" / next(iter(
        mapping["packet_sets"]["ai-packet-1"][0]["reviewer_artifacts"].values()))["path"]
    original = copied.read_bytes()
    copied.write_bytes(original + b"\nchanged after packet construction")
    with pytest.raises(ValueError, match="evidence SHA256 mismatch"):
        _decide(fixture)
    copied.write_bytes(original)

    evidence = json.loads(fixture["evidence"].read_text())
    ledger_path = fixture["evidence"].parent / evidence["judge_ledger"]["path"]
    judge_ledger = json.loads(ledger_path.read_text())
    removed = judge_ledger["entries"].pop()
    evidence["judge_ledger"].update(_write(ledger_path, judge_ledger))
    fixture["evidence"].write_text(json.dumps(evidence), encoding="utf-8")
    incomplete = _decide(fixture)
    assert incomplete["status"] == "incomplete"
    assert any("judging:" in reason for reason in incomplete["incomplete_reasons"])
    judge_ledger["entries"].append(removed)
    evidence["judge_ledger"].update(_write(ledger_path, judge_ledger))
    fixture["evidence"].write_text(json.dumps(evidence), encoding="utf-8")

    # Packet order is deliberately randomized. The absolute fabricated-quote veto
    # belongs to the candidate arm; comparator defects remain descriptive.
    candidate_ids = {p["packet_id"] for p in mapping["packet_sets"]["ai-packet-1"]
                     if p["arm"] == "candidate"}
    assessment_ref = next(ref for ref in evidence["assessments"]
                          if json.loads((fixture["evidence"].parent / ref["path"]).read_text())["packet_id"]
                          in candidate_ids)
    assessment_path = fixture["evidence"].parent / assessment_ref["path"]
    assessment = json.loads(assessment_path.read_text())
    original_quality_context = assessment["quality_context_id"]
    quality_context_path = fixture["evidence"].parent / assessment["quality_response"]["path"]
    quality_context_response = json.loads(quality_context_path.read_text())
    source_context = json.loads(fixture["preflight"].read_text())["ai_assisted"]["source_briefs"][0]["context_id"]
    assessment["quality_context_id"] = source_context
    quality_context_response["context_id"] = source_context
    assessment["quality_response"].update(_write(quality_context_path, quality_context_response))
    assessment_ref.update(_write(assessment_path, assessment))
    fixture["evidence"].write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(ValueError, match="reused across review roles"):
        _decide(fixture)

    assessment["quality_context_id"] = assessment["challenge_context_id"]
    quality_context_response["context_id"] = assessment["challenge_context_id"]
    assessment["quality_response"].update(_write(quality_context_path, quality_context_response))
    assessment_ref.update(_write(assessment_path, assessment))
    fixture["evidence"].write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(ValueError, match="reused across review roles"):
        _decide(fixture)

    assessment["quality_context_id"] = "ctx-unbound-quality-response"
    assessment_ref.update(_write(assessment_path, assessment))
    fixture["evidence"].write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(ValueError, match="raw review response identity"):
        _decide(fixture)
    assessment["quality_context_id"] = original_quality_context
    quality_context_response["context_id"] = original_quality_context
    assessment["quality_response"].update(_write(quality_context_path, quality_context_response))
    assessment_ref.update(_write(assessment_path, assessment))
    fixture["evidence"].write_text(json.dumps(evidence), encoding="utf-8")

    packet = next(p for p in mapping["packet_sets"]["ai-packet-1"]
                  if p["packet_id"] == assessment["packet_id"])
    manifest = json.loads(fixture["manifest"].read_text())
    filing = next(f for f in manifest["filings"]
                  if f["accession_number"] == packet["accession_number"])
    primary = next(p for p in filing["source_packets"] if p["role"] == "primary")
    machine_path = fixture["evidence"].parent / assessment["machine_inventory"]["path"]
    machine = json.loads(machine_path.read_text())
    machine["surfaces"]["rendered"]["claims"] = [{
        "id": "Q1", "kind": "quote", "source_role": "primary",
        "source_sha256": primary["sha256"],
        "source_accession_number": packet["accession_number"],
        "source_range": [0, 7], "output_range": [0, 7],
    }]
    assessment["machine_inventory"].update(_write(machine_path, machine))
    quality_path = fixture["evidence"].parent / assessment["quality_response"]["path"]
    challenge_path = fixture["evidence"].parent / assessment["challenge_response"]["path"]
    quality = json.loads(quality_path.read_text())
    challenge = json.loads(challenge_path.read_text())
    quality["machine_inventory_sha256"] = assessment["machine_inventory"]["sha256"]
    challenge["machine_inventory_sha256"] = assessment["machine_inventory"]["sha256"]
    source_text = (fixture["archive"] / primary["path"]).read_text(encoding="utf-8")
    finding = {"id": "F-Q1", "claim": "Synthetic quote differs from source",
               "source_locator": "line 1", "source_context": source_text,
               "source_role": "primary", "source_sha256": primary["sha256"],
               "source_range": [0, len(source_text)],
               "reason": "Source challenge records the mismatch", "severity": "S2",
               "disposition": "rejected", "category": "claim",
               "refutations": ["Checked the byte span", "Checked the filing identity"],
               "machine_check_id": "Q1", "original_allegation": "machine:Q1:quote_mismatch",
               "surface": "canonical"}
    challenge["findings"] = [finding]
    assessment["findings"] = [finding]
    assessment["quality_response"].update(_write(quality_path, quality))
    assessment["challenge_response"].update(_write(challenge_path, challenge))
    assessment_ref.update(_write(assessment_path, assessment))
    fixture["evidence"].write_text(json.dumps(evidence), encoding="utf-8")
    wrong_surface = _decide(fixture)
    assert wrong_surface["status"] == "incomplete"
    assert any("lacks its own confirmed source challenge" in reason
               for reason in wrong_surface["incomplete_reasons"])

    finding["surface"] = "rendered"
    challenge["findings"] = [finding]
    assessment["findings"] = [finding]
    assessment["challenge_response"].update(_write(challenge_path, challenge))
    assessment_ref.update(_write(assessment_path, assessment))
    fixture["evidence"].write_text(json.dumps(evidence), encoding="utf-8")
    rejected_machine_finding = _decide(fixture)
    assert rejected_machine_finding["status"] == "incomplete"
    assert any("lacks its own confirmed source challenge" in reason
               for reason in rejected_machine_finding["incomplete_reasons"])

    finding["disposition"] = "confirmed"
    finding["category"] = "fabricated_quote"
    challenge["findings"] = [finding]
    assessment["findings"] = [finding]
    assessment["challenge_response"].update(_write(challenge_path, challenge))
    assessment_ref.update(_write(assessment_path, assessment))
    fixture["evidence"].write_text(json.dumps(evidence), encoding="utf-8")
    confirmed_machine_finding = _decide(fixture)
    assert confirmed_machine_finding["status"] == "fail"
    assert any("confirmed S2 fabricated_quote" in reason
               for reason in confirmed_machine_finding["failures"])

    # Rehash a coherently edited challenge: hashes alone must not bless an
    # invented passage used to dismiss a real machine allegation.
    finding["source_context"] = "Invented passage from a different filing"
    assessment["challenge_response"].update(_write(challenge_path, challenge))
    assessment_ref.update(_write(assessment_path, assessment))
    fixture["evidence"].write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(ValueError, match="passage differs from the frozen source"):
        _decide(fixture)
    finding["source_context"] = source_text
    assessment["challenge_response"].update(_write(challenge_path, challenge))
    assessment_ref.update(_write(assessment_path, assessment))
    fixture["evidence"].write_text(json.dumps(evidence), encoding="utf-8")

    original_assessment = json.loads(assessment_path.read_text())
    assessment["completeness"] = 1
    assessment_ref.update(_write(assessment_path, assessment))
    fixture["evidence"].write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(ValueError, match="normalized score differs"):
        _decide(fixture)
    assessment = original_assessment
    assessment.pop("machine_inventory")
    assessment_ref.update(_write(assessment_path, assessment))
    fixture["evidence"].write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises((ValueError, KeyError), match="evidence record|machine_inventory"):
        _decide(fixture)
