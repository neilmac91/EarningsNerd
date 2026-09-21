"""Synthetic E7 preflight and blinding contract; no source network or provider calls."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models import Summary
from evals.acceptance_readiness import _reviewer_artifact, build_blinded_packets, inspect_readiness


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
            "provider": "DeepSeek", "model": "deepseek-flash", "base_url": "https://api.deepseek.com/v1",
            "effective_flags": {"AI_EVIDENCE_SNAP": True},
            "effective_settings": {"temperature": 0.2}, "dependency_lock_sha256": "b" * 64,
            "frozen_at": frozen})
    receipt = _write(evidence / "receipt.json", {"synthetic": True})
    pricing = _write(evidence / "pricing.json", {
        "model": "deepseek-flash", "base_url": "https://api.deepseek.com/v1",
        "official_source": "https://api-docs.deepseek.com/quick_start/pricing",
        "verified_at": observed, "valid_until": "2099-01-02T00:00:00Z",
        "uncached_input_per_million": "0.1", "max_output_per_million": "0.2"})
    preflight = {
        "schema_version": 1, "approved_manifest_sha256": manifest_sha,
        "reviewers": reviewers, "adjudicator": adjudicator,
        "reference_briefs": briefs, "exposure_attestation": exposure,
        "candidate_config": configs["candidate"], "comparator_config": configs["comparator"],
        "pricing": {**pricing, "observed_at": observed,
                    "official_url": "https://api-docs.deepseek.com/quick_start/pricing"},
        "balance": {**receipt, "observed_at": observed, "available_usd": 10},
        "fable": {**receipt, "observed_at": observed, "contract_version": "2",
                  "model": "cli:claude-fable-5-1", "quota_available": True},
        "development_smoke": {**receipt, "completed": True, "accession_number": "0000000001-26-000001"},
        "budget_control": {**receipt, "verified": True, "reviewed_commit": "c" * 40,
                           "full_run_worst_case_usd": 9.5,
                           "incomplete_stop_risk_accepted_by": "", "incomplete_stop_risk_accepted_at": None},
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
                    if key == "canonical":
                        path.write_text(json.dumps({
                            "id": 1, "filing_id": 1,
                            "business_overview": "Revenue rose on the filing basis.",
                            "financial_highlights": None, "risk_factors": [],
                            "management_discussion": "Operations improved.",
                            "key_changes": "Higher investment.",
                            "raw_summary": {"sections": {"business_overview": {
                                "model": "Subscription business model",
                                "provider": "Regional care provider",
                                "arm": "Clinical trial arm", "draw": "Credit facility draw",
                            }}, "status": "complete", "schema_version": 2},
                            "schema_version": 2, "prompt_version": f"synthetic-{arm}",
                            "created_at": observed, "updated_at": None,
                        }), encoding="utf-8")
                    else:
                        path.write_text("Revenue rose on the filing basis.", encoding="utf-8")
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


def test_pricing_identity_and_over_ceiling_decision_hold_paid_run(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    preflight = json.loads(fixture["preflight"].read_text())
    evidence = fixture["preflight"].parent
    price_path = evidence / preflight["pricing"]["path"]
    price = json.loads(price_path.read_text())
    price["model"] = "unrequested-model"
    preflight["pricing"].update(_write(price_path, price))
    fixture["preflight"].write_text(json.dumps(preflight))
    mismatch = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                 expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
    assert mismatch["ready_for_paid_execution"] is False
    assert "pricing_invalid" in {item["code"] for item in mismatch["issues"]}

    price["model"] = "deepseek-flash"
    preflight["pricing"].update(_write(price_path, price))
    preflight["budget_control"]["full_run_worst_case_usd"] = 12
    fixture["preflight"].write_text(json.dumps(preflight))
    over_ceiling = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                     expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
    assert over_ceiling["ready_for_paid_execution"] is False
    assert "budget_control_invalid" in {item["code"] for item in over_ceiling["issues"]}

    preflight["budget_control"].update(incomplete_stop_risk_accepted_by="Synthetic Sponsor",
                                        incomplete_stop_risk_accepted_at=fixture["now"].isoformat())
    fixture["preflight"].write_text(json.dumps(preflight))
    accepted = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                 expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
    assert accepted["ready_for_paid_execution"] is True


def test_stale_verified_price_and_wrong_fable_contract_hold_paid_run(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    preflight = json.loads(fixture["preflight"].read_text())
    price_path = fixture["preflight"].parent / preflight["pricing"]["path"]
    price = json.loads(price_path.read_text())
    price["verified_at"] = (fixture["now"] - timedelta(days=3)).isoformat()
    preflight["pricing"].update(_write(price_path, price))
    fixture["preflight"].write_text(json.dumps(preflight))
    stale = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                              expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
    assert stale["ready_for_paid_execution"] is False
    assert "stale_pricing_verification" in {item["code"] for item in stale["issues"]}
    price["verified_at"] = preflight["pricing"]["observed_at"]
    price["uncached_input_per_million"] = "NaN"
    preflight["pricing"].update(_write(price_path, price))
    fixture["preflight"].write_text(json.dumps(preflight))
    bad_rate = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                 expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
    assert "pricing_invalid" in {item["code"] for item in bad_rate["issues"]}
    price["uncached_input_per_million"] = "0.1"
    preflight["pricing"].update(_write(price_path, price))
    preflight["fable"]["model"] = "different-judge"
    fixture["preflight"].write_text(json.dumps(preflight))
    wrong_judge = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                    expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
    assert "fable_invalid" in {item["code"] for item in wrong_judge["issues"]}


def test_blinding_keeps_arm_private_and_rejects_lost_preview(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    reviewer_root, custodian_root = tmp_path / "reviewers", tmp_path / "custodian"
    result = build_blinded_packets(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                   fixture["outputs"], reviewer_root, custodian_root,
                                   expected_manifest_sha=fixture["manifest_sha"])
    assert result["packets_per_reviewer"] == 120
    mapping = json.loads((custodian_root / "mapping.json").read_text())
    assert {row["arm"] for row in mapping["reviewers"]["reviewer-1"]} == {"candidate", "comparator"}
    original = Path(mapping["reviewers"]["reviewer-1"][0]["raw_artifacts"]["canonical"]["path"])
    raw = json.loads(original.read_text())
    assert set(raw) == {column.name for column in Summary.__table__.columns}
    assert raw["prompt_version"].startswith("synthetic-")
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
        packet = root / index["packets"][0]["packet_dir"] / "canonical.json"
        product = json.loads(packet.read_text())
        assert set(product) == {"business_overview", "financial_highlights", "risk_factors",
                                "management_discussion", "key_changes", "raw_summary"}
        assert product["raw_summary"]["sections"]["business_overview"] == {
            "model": "Subscription business model", "provider": "Regional care provider",
            "arm": "Clinical trial arm", "draw": "Credit facility draw",
        }
    outputs = json.loads(fixture["outputs"].read_text())
    outputs["records"][0]["preview_paths"] = []
    fixture["outputs"].write_text(json.dumps(outputs))
    with pytest.raises(ValueError, match="preview evidence incomplete"):
        build_blinded_packets(fixture["manifest"], fixture["archive"], fixture["preflight"],
                              fixture["outputs"], tmp_path / "no-reviewers", tmp_path / "no-custodian",
                              expected_manifest_sha=fixture["manifest_sha"])
    assert not (tmp_path / "no-reviewers").exists()


def test_blinding_rejects_raw_rendered_identity_marker(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    outputs = json.loads(fixture["outputs"].read_text())
    row = outputs["records"][0]
    rendered = fixture["outputs"].parent / row["rendered_path"]
    rendered.write_text(f"Revenue rose. {row['config_sha256']}", encoding="utf-8")
    row["artifact_sha256"]["rendered"] = hashlib.sha256(rendered.read_bytes()).hexdigest()
    fixture["outputs"].write_text(json.dumps(outputs))
    with pytest.raises(ValueError, match="exposes execution identity"):
        build_blinded_packets(fixture["manifest"], fixture["archive"], fixture["preflight"],
                              fixture["outputs"], tmp_path / "reviewers", tmp_path / "custodian",
                              expected_manifest_sha=fixture["manifest_sha"])
    assert not (tmp_path / "reviewers").exists()
    assert not (tmp_path / "custodian").exists()
    export = tmp_path / "export.html"
    export.write_text("Filing Date: May 01, 2026 · Period End: March 31, 2026 · "
                      "Generated September 21, 2026<br>Source: SEC EDGAR<p>Revenue rose.</p>")
    preflight = json.loads(fixture["preflight"].read_text())
    config = json.loads((fixture["preflight"].parent / preflight["candidate_config"]["path"]).read_text())
    projected = _reviewer_artifact(export, "export", row, config, "H01").decode()
    assert "Generated September" not in projected and "Period End: March 31, 2026" in projected
    assert "Revenue rose." in projected and "Generated September" in export.read_text()


def test_blinding_refuses_unknown_nested_execution_marker_or_canonical_shape(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    row = json.loads(fixture["outputs"].read_text())["records"][0]
    canonical = fixture["outputs"].parent / row["canonical_path"]
    prereq = json.loads(fixture["preflight"].read_text())
    config = json.loads((fixture["preflight"].parent / prereq["candidate_config"]["path"]).read_text())
    value = json.loads(canonical.read_text())
    value["raw_summary"]["sections"]["business_overview"]["config_sha256"] = "unknown-nested-marker"
    canonical.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="exposes execution identity"):
        _reviewer_artifact(canonical, "canonical", row, config, "H01")
    del value["raw_summary"]["sections"]["business_overview"]["config_sha256"]
    value["unknown_execution_field"] = "unreviewed"
    canonical.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="reviewed production Summary shape"):
        _reviewer_artifact(canonical, "canonical", row, config, "H01")
