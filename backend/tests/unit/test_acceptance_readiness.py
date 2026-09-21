"""Synthetic E7 preflight and blinding contract; no source network or provider calls."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from evals.acceptance_readiness import build_blinded_packets, inspect_readiness


_ACCEPTED = Path(__file__).resolve().parents[3] / "tasks/review-evidence/acceptance-2026-09-19/candidate-manifest.json"
_COMPARATOR = {"H01", "H03", "H05", "H07", "H09", "H14", "H18", "H23", "H26", "H29"}


def _write(path: Path, value: object) -> dict[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _fixture(tmp_path: Path) -> dict[str, Path | str | datetime]:
    now = datetime.now(timezone.utc)
    frozen = (now - timedelta(hours=2)).isoformat()
    observed = (now - timedelta(hours=1)).isoformat()
    archive = tmp_path / "archive"
    archive.mkdir()
    manifest = json.loads(_ACCEPTED.read_text(encoding="utf-8"))
    for filing in manifest["filings"]:
        for packet in filing["source_packets"]:
            path = archive / "e7-sources" / filing["holdout_id"] / f"{packet['role']}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"synthetic {filing['accession_number']} {packet['role']}", encoding="utf-8")
            packet.update(path=str(path.relative_to(archive)), bytes=path.stat().st_size,
                          sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    reviewers = [
        {"id": f"reviewer-{i}", "name": f"Synthetic Reviewer {i}",
         "competence": "filing review", "committed_hours": 50, "commitment_date": frozen}
        for i in (1, 2)
    ]
    adjudicator = {"id": "adjudicator-1", "name": "Synthetic Adjudicator",
                   "competence": "accounting", "committed_hours": 10, "commitment_date": frozen}
    briefs = []
    for filing in manifest["filings"]:
        accession = filing["accession_number"]
        brief = {"accession_number": accession, "reviewer_ids": [r["id"] for r in reviewers],
                 "adjudicator_id": adjudicator["id"], "independent_source_review_attested": True,
                 "frozen_at": frozen, "material_issues": [{
                     "issue": "Synthetic issue", "source_role": "primary", "source_locator": "line 1",
                     "expected_numbers_basis": "synthetic basis", "importance": "synthetic importance",
                     "disclosure_limits": "synthetic limit"}]}
        ref = _write(evidence / f"brief-{filing['holdout_id']}.json", brief)
        briefs.append({"accession_number": accession, **ref})
    exposure = _write(evidence / "exposure.json", {
        "custodian_name": "Synthetic Custodian", "signed_at": frozen,
        "checked_accessions": [f["accession_number"] for f in manifest["filings"]],
        "external_artifact_inventory": "Synthetic inventory", "untracked_sources_checked": True,
        "unseen_confirmed": True, "exposed_accessions": []})
    configs = {}
    for arm in ("candidate", "comparator"):
        configs[arm] = _write(evidence / f"{arm}.json", {
            "source_commit": "a" * 40, "content_stamp": f"synthetic-{arm}",
            "provider": "DeepSeek", "model": "deepseek-flash", "effective_flags": {"AI_EVIDENCE_SNAP": True},
            "effective_settings": {"temperature": 0.2}, "dependency_lock_sha256": "b" * 64,
            "frozen_at": frozen})
    receipt = _write(evidence / "receipt.json", {"synthetic": True})
    preflight = {
        "schema_version": 1, "approved_manifest_sha256": manifest_sha,
        "reviewers": reviewers, "adjudicator": adjudicator,
        "reference_briefs": briefs, "exposure_attestation": exposure,
        "candidate_config": configs["candidate"], "comparator_config": configs["comparator"],
        "pricing": {**receipt, "observed_at": observed,
                    "official_url": "https://api-docs.deepseek.com/quick_start/pricing",
                    "model": "deepseek-flash", "uncached_input_usd_per_million": 0.1,
                    "output_usd_per_million": 0.2},
        "balance": {**receipt, "observed_at": observed, "available_usd": 10},
        "fable": {**receipt, "observed_at": observed, "contract_version": "2",
                  "model": "Fable 5.1", "quota_available": True},
        "development_smoke": {**receipt, "completed": True, "accession_number": "0000000001-26-000001"},
        "budget_control": {**receipt, "verified": True, "reviewed_commit": "c" * 40},
    }
    preflight_path = evidence / "prerequisites.json"
    preflight_path.write_text(json.dumps(preflight), encoding="utf-8")
    outputs_root = tmp_path / "outputs"
    outputs_root.mkdir()
    output_records = []
    for filing in manifest["filings"]:
        for arm in (("candidate", "comparator") if filing["holdout_id"] in _COMPARATOR else ("candidate",)):
            for draw in (1, 2, 3):
                slot = f"{filing['holdout_id']}-{arm}-{draw}"
                paths = {}
                hashes = {}
                for key, extension in (("canonical", "json"), ("rendered", "md"),
                                       ("export", "html"), ("preview_0", "md")):
                    path = outputs_root / slot / f"{key}.{extension}"
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(f"synthetic {slot} {key}", encoding="utf-8")
                    paths[key] = str(path.relative_to(outputs_root))
                    hashes[key] = hashlib.sha256(path.read_bytes()).hexdigest()
                output_records.append({
                    "accession_number": filing["accession_number"], "arm": arm, "draw": draw,
                    "status": "completed", "error": None, "created_at": observed,
                    "config_sha256": configs[arm]["sha256"],
                    "canonical_path": paths["canonical"], "rendered_path": paths["rendered"],
                    "export_path": paths["export"], "preview_paths": [paths["preview_0"]],
                    "preview_count": 1, "previews_truncated": False,
                    "retry_preview_attempts_omitted": 0, "artifact_sha256": hashes,
                })
    outputs_path = outputs_root / "outputs.json"
    outputs_path.write_text(json.dumps({"records": output_records}), encoding="utf-8")
    return {"manifest": manifest_path, "archive": archive, "preflight": preflight_path,
            "outputs": outputs_path, "manifest_sha": manifest_sha, "now": now}


def test_preflight_fails_closed_on_missing_independent_brief(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    ready = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                              expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
    assert ready["ready_for_paid_execution"] is True
    assert ready["source_packets_verified"] == 92
    preflight = json.loads(fixture["preflight"].read_text())
    preflight["reference_briefs"].pop()
    fixture["preflight"].write_text(json.dumps(preflight))
    missing = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
    assert missing["ready_for_paid_execution"] is False
    assert "reference_brief_coverage" in {item["code"] for item in missing["issues"]}


def test_blinding_keeps_arm_private_and_rejects_lost_preview(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    reviewer_root, custodian_root = tmp_path / "reviewers", tmp_path / "custodian"
    result = build_blinded_packets(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                   fixture["outputs"], reviewer_root, custodian_root,
                                   expected_manifest_sha=fixture["manifest_sha"])
    assert result["packets_per_reviewer"] == 120
    mapping = json.loads((custodian_root / "mapping.json").read_text())
    assert {row["arm"] for row in mapping["reviewers"]["reviewer-1"]} == {"candidate", "comparator"}
    for reviewer in ("reviewer-1", "reviewer-2"):
        root = reviewer_root / reviewer
        index = json.loads((root / "index.json").read_text())
        assert len(index["packets"]) == 120
        assert len(list((root / "sources").iterdir())) == 30
        for path in root.rglob("*"):
            if path.is_file():
                assert "candidate" not in str(path.relative_to(root))
                assert "comparator" not in str(path.relative_to(root))
                assert fixture["manifest_sha"] not in path.read_text(encoding="utf-8")
        assert '"arm"' not in (root / "index.json").read_text()
        assert '"config_sha256"' not in (root / "index.json").read_text()
    outputs = json.loads(fixture["outputs"].read_text())
    outputs["records"][0]["preview_paths"] = []
    fixture["outputs"].write_text(json.dumps(outputs))
    with pytest.raises(ValueError, match="preview evidence incomplete"):
        build_blinded_packets(fixture["manifest"], fixture["archive"], fixture["preflight"],
                              fixture["outputs"], tmp_path / "no-reviewers", tmp_path / "no-custodian",
                              expected_manifest_sha=fixture["manifest_sha"])
    assert not (tmp_path / "no-reviewers").exists()
