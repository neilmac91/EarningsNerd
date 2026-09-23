"""Synthetic E7 preflight and blinding contract; no source network or provider calls."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models import Summary
from evals import acceptance_executor, acceptance_readiness, acceptance_worker
from evals.acceptance_outputs import collect_outputs, inspect_outputs
from evals.acceptance_readiness import (_reviewer_artifact, build_blinded_packets,
                                        inspect_readiness, review_evidence_inventory,
                                        verify_review_evidence_binding)


_ACCEPTED = Path(__file__).resolve().parents[3] / "tasks/review-evidence/acceptance-2026-09-19/candidate-manifest.json"
_REAL_ARCHIVE_BINDING_HOLD = acceptance_worker.archive_binding_hold
_COMPARATOR = {"H01", "H03", "H05", "H07", "H09", "H14", "H18", "H23", "H26", "H29"}


@pytest.fixture(autouse=True)
def synthetic_archive_binding(monkeypatch):
    # Keep testing the downstream independent gates with synthetic bound channels;
    # the first readiness gate below reinstates and tests the real execution hold.
    monkeypatch.setattr(acceptance_worker, "archive_binding_hold", lambda: None)


def _write(path: Path, value: object) -> dict[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _retain_collector_evidence(root: Path, manifest: dict, manifest_sha: str,
                               rows: list[dict], prerequisites_path: Path) -> dict:
    """Synthetic worker/ledger files only; no budget admission or provider execution."""
    filings = {f["accession_number"]: f for f in manifest["filings"]}
    def digest(value):
        return hashlib.sha256(value).hexdigest()
    provider_request = {"model": "synthetic"}
    request_hash = digest(json.dumps(provider_request, sort_keys=True, separators=(",", ":")).encode())
    with sqlite3.connect(root / "budget.sqlite3") as db:
        prereq = json.loads(prerequisites_path.read_text())
        db.execute("CREATE TABLE binding (id INTEGER PRIMARY KEY, value TEXT)")
        db.execute("INSERT INTO binding VALUES (1, ?)", (json.dumps({
            "manifest": manifest_sha, "configs": {
                arm: prereq[f"{arm}_config"]["sha256"] for arm in ("candidate", "comparator")},
            "review_evidence": review_evidence_inventory(prerequisites_path, prereq),
        }, sort_keys=True),))
        db.execute("CREATE TABLE slots (id TEXT PRIMARY KEY, config_sha TEXT, status TEXT, request_sha TEXT, result_sha TEXT)")
        db.execute("CREATE TABLE reservations (id INTEGER PRIMARY KEY, slot_id TEXT, status TEXT, request_hash TEXT)")
        db.execute("INSERT INTO slots VALUES ('development-smoke', ?, 'completed', ?, NULL)", ("a" * 64, "b" * 64))
        db.execute("INSERT INTO reservations VALUES (1, 'development-smoke', 'settled', ?)", (request_hash,))
        for number, row in enumerate(rows, start=2):
            filing = filings[row["accession_number"]]
            slot_id = f"{filing['holdout_id']}-{row['arm']}-{row['draw']}"
            slot, invocation = root / slot_id, root / slot_id / "attempt-1"
            artifacts = {"canonical_summary": "canonical.json", "rendered_summary": "rendered.md",
                         "export_html": "export.html", "raw_previews": "raw_previews.jsonl",
                         "provider_accounting": "provider_accounting.json", "events": "events.jsonl",
                         "grounding": "grounding.json", "rendered_sections": "rendered_sections.json"}
            _write(slot / "selection.json", {"slot_id": slot_id, "arm": row["arm"], "draw": row["draw"],
                                            "filing": filing, "config_sha256": row["config_sha256"],
                                            "manifest_sha256": manifest_sha})
            request = _write(slot / "request.json", {"slot_id": slot_id, "filing": filing,
                             "config_sha256": row["config_sha256"], "invocation_dir": str(invocation)})
            db.execute("INSERT INTO slots VALUES (?, ?, 'completed', ?, NULL)",
                       (slot_id, row["config_sha256"], request["sha256"]))
            db.execute("INSERT INTO reservations VALUES (?, ?, 'settled', ?)",
                       (number, slot_id, request_hash))
            evidence = {p["role"]: {"path": str(root / p["path"]), "sha256": p["sha256"],
                                   "bytes": p["bytes"], "requested_url": p["provenance"]["requested_url"]}
                        for p in filing["source_packets"]}
            receipt = {"identity": {key: filing[key] for key in
                       ("holdout_id", "accession_number", "ticker", "cik", "filing_type")},
                       "started_at": row["created_at"], "status": "complete", "eligible_for_measurement": True,
                       "errors": [], "source_identity": "archived_sgml_verified" if filing["filing_type"] == "6-K" else "primary_verified",
                       "source_packets": evidence, "artifacts": artifacts}
            _write(invocation / "receipt.json", receipt)
            _write(invocation / "result.json", receipt)
            _write(invocation / "provider_accounting.json", {"slot_id": slot_id, "records": [
                {"reservation_id": number, "status": "settled", "request": provider_request}]})
            (invocation / "events.jsonl").write_text('{"type":"complete"}\n')
            frames = ["Incorrect early preview: revenue was $999B.", "Revenue rose on the filing basis."]
            (invocation / "raw_previews.jsonl").write_text("".join(json.dumps({
                "generation_ordinal": 0, "provider_attempt": number, "markdown": text}) + "\n" for text in frames))
            grounding = {}
            if filing["filing_type"] == "6-K":
                text = "Synthetic verified extraction"
                grounding = {"source_calls": [
                    {"owner": "edgartools.Filing.from_sgml_text", "accession": filing["accession_number"],
                     "cik": filing["cik"], "form": "6-K", "filing_date": filing["filing_date"],
                     "complete_submission_sha256": evidence["complete_submission"]["sha256"],
                     "embedded_primary_sha256": evidence["primary"]["sha256"],
                     "selected_attachments": [Path(evidence["earnings_exhibit"]["path"]).name]
                     if "earnings_exhibit" in evidence else []},
                    {"owner": "get_sixk_text", "accession": filing["accession_number"], "cik": filing["cik"],
                     "bytes": len(text.encode()), "sha256": digest(text.encode()),
                     "source_packet_match": "verified_complete_submission"},
                    {"owner": "get_or_cache_excerpt", "accession": filing["accession_number"],
                     "filing_text_sha256": digest(text.encode())}], "summarizer_calls": [{"args": [text]}]}
                _write(invocation / "source_evidence.json", evidence)
            _write(invocation / "grounding.json", grounding)
            _write(invocation / "rendered_sections.json", [])
            receipt["artifact_sha256"] = {key: digest((invocation / relative).read_bytes())
                                          for key, relative in artifacts.items()}
            _write(invocation / "receipt.json", receipt)
            result = _write(invocation / "result.json", receipt)
            db.execute("UPDATE slots SET result_sha=? WHERE id=?", (result["sha256"], slot_id))
    return inspect_outputs(root, root, expected_manifest_sha=manifest_sha, materialize_previews=True)


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
        filing["source_sha256"] = next(p["sha256"] for p in filing["source_packets"] if p["role"] == "primary")
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
    balance = _write(evidence / "balance.json", {
        "schema_version": 1, "kind": "balance", "observed_at": observed,
        "provider": "deepseek", "currency": "USD", "available_usd": 10})
    fable = _write(evidence / "fable.json", {
        "schema_version": 1, "kind": "fable", "observed_at": observed,
        "contract_version": "2", "model": "cli:claude-fable-5-1", "quota_available": True})
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
        "balance": {**balance, "observed_at": observed, "available_usd": 10},
        "fable": {**fable, "observed_at": observed, "contract_version": "2",
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
                    path = outputs_root / slot / "attempt-1" / f"{key}.{extension}"
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
    outputs_path.write_text(json.dumps(_retain_collector_evidence(
        outputs_root, manifest, manifest_sha, output_records, preflight_path)), encoding="utf-8")
    return {"manifest": manifest_path, "archive": archive, "preflight": preflight_path,
            "outputs": outputs_path, "manifest_sha": manifest_sha, "now": now}


def test_preflight_fails_closed_on_missing_independent_brief(tmp_path: Path, monkeypatch) -> None:
    fixture = _fixture(tmp_path)
    ready = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                              expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
    assert ready["ready_for_paid_execution"] is True
    assert ready["source_packets_verified"] == 92
    with monkeypatch.context() as actual:
        actual.setattr(acceptance_worker, "archive_binding_hold", _REAL_ARCHIVE_BINDING_HOLD)
        held = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                 expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
        assert held["ready_for_paid_execution"] is False and held["ready_for_packets"] is False
        assert [issue["code"] for issue in held["issues"]] == ["structured_source_binding_unavailable"]
        def forbidden(*_args, **_kwargs):
            raise AssertionError("dispatch or database reached before archive binding")
        actual.setattr(acceptance_executor.subprocess, "run", forbidden)
        actual.setattr(acceptance_worker, "_check_configuration", forbidden)
        # Use the real preflight with this synthetic manifest's expected hash.
        actual.setattr(acceptance_executor, "inspect_readiness", lambda *args: inspect_readiness(
            *args, expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"]))
        programme = tmp_path / "unstarted-programme"
        for command in ("run-smoke", "run-slot"):
            args = SimpleNamespace(command=command, manifest=fixture["manifest"],
                                   archive=fixture["archive"], prerequisites=fixture["preflight"],
                                   programme=programme, slot="H01-candidate-1")
            with pytest.raises(ValueError, match="structured_source_binding_unavailable"):
                acceptance_executor.run_slot(args)
            assert not programme.exists()
        actual.setattr(acceptance_executor, "claim_worker", forbidden)
        request = tmp_path / "blocked-worker-request.json"
        request.write_text(json.dumps({"manifest": str(fixture["manifest"]),
                                       "archive": str(fixture["archive"]),
                                       "prerequisites": str(fixture["preflight"]), "smoke_mode": True}))
        with pytest.raises(ValueError, match="child readiness"):
            asyncio.run(acceptance_executor.worker(SimpleNamespace(request=request)))
        # Direct worker use cannot sneak a 6-K subset around the programme gate.
        for form in ("10-K", "10-Q", "20-F", "6-K"):
            invocation = tmp_path / ("unstarted-" + form)
            with pytest.raises(acceptance_worker.InvalidMeasurement, match="requires a verified frozen archive"):
                asyncio.run(acceptance_worker.run_invocation({"filing_type": form}, invocation, {}, None))
            assert not invocation.exists()
        reviewers, custodian = tmp_path / "held-reviewers", tmp_path / "held-custodian"
        with pytest.raises(ValueError, match="structured_source_binding_unavailable"):
            build_blinded_packets(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                  fixture["outputs"], reviewers, custodian,
                                  expected_manifest_sha=fixture["manifest_sha"])
        assert not reviewers.exists() and not custodian.exists()
    preflight = json.loads(fixture["preflight"].read_text())
    removed_brief = preflight["reference_briefs"].pop()
    fixture["preflight"].write_text(json.dumps(preflight))
    missing = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
    assert missing["ready_for_paid_execution"] is False
    assert "reference_brief_coverage" in {item["code"] for item in missing["issues"]}
    preflight["reference_briefs"].append(removed_brief)
    future = (fixture["now"] + timedelta(days=1)).isoformat()
    for person in (preflight["reviewers"][0], preflight["adjudicator"]):
        person["commitment_date"] = future
        fixture["preflight"].write_text(json.dumps(preflight))
        not_committed = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                          expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
        assert not_committed["ready_for_paid_execution"] is False
        assert "human_commitment" in {item["code"] for item in not_committed["issues"]}
        person["commitment_date"] = (fixture["now"] - timedelta(hours=2)).isoformat()


@pytest.mark.parametrize("field", [
    "issue", "source_locator", "expected_numbers_basis", "importance", "disclosure_limits",
])
def test_human_brief_rejects_null_material_issue_field(tmp_path: Path, field: str) -> None:
    fixture = _fixture(tmp_path)
    prereq = json.loads(fixture["preflight"].read_text())
    record = prereq["reference_briefs"][0]
    path = fixture["preflight"].parent / record["path"]
    brief = json.loads(path.read_text())
    brief["material_issues"][0][field] = None
    record.update(_write(path, brief))
    fixture["preflight"].write_text(json.dumps(prereq))

    result = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                               expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
    assert "reference_brief_invalid" in {issue["code"] for issue in result["issues"]}
    assert result["ready_for_paid_execution"] is False


def test_rehashed_review_evidence_after_output_cannot_reach_collection_or_packets(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    prerequisites_path = fixture["preflight"]
    original_prerequisites = prerequisites_path.read_bytes()
    programme = fixture["outputs"].parent
    for kind in ("reviewer", "adjudicator", "brief", "exposure"):
        prereq = json.loads(original_prerequisites)
        changed_path = None
        original_evidence = None
        if kind == "reviewer":
            prereq["reviewers"][0]["committed_hours"] += 1
        elif kind == "adjudicator":
            prereq["adjudicator"]["committed_hours"] += 1
        else:
            record = (prereq["reference_briefs"][0] if kind == "brief"
                      else prereq["exposure_attestation"])
            changed_path = prerequisites_path.parent / record["path"]
            original_evidence = changed_path.read_bytes()
            payload = json.loads(original_evidence)
            if kind == "brief":
                payload["material_issues"][0]["importance"] = "Changed after output"
            else:
                payload["external_artifact_inventory"] = "Changed after output"
            record["sha256"] = _write(changed_path, payload)["sha256"]
        prerequisites_path.write_text(json.dumps(prereq), encoding="utf-8")
        ready = inspect_readiness(fixture["manifest"], fixture["archive"], prerequisites_path,
                                  expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
        assert ready["ready_for_packets"] is True, kind
        with pytest.raises(ValueError, match="review evidence"):
            collect_outputs(programme, tmp_path / "collected.json")
        reviewer_root, custodian_root = tmp_path / "reviewers", tmp_path / "custodian"
        with pytest.raises(ValueError, match="review evidence"):
            build_blinded_packets(fixture["manifest"], fixture["archive"], prerequisites_path,
                                  fixture["outputs"], reviewer_root, custodian_root,
                                  expected_manifest_sha=fixture["manifest_sha"])
        assert not reviewer_root.exists() and not custodian_root.exists()
        prerequisites_path.write_bytes(original_prerequisites)
        if changed_path is not None:
            changed_path.write_bytes(original_evidence)
    # A fresh, internally consistent balance observation is renewable.
    prereq = json.loads(original_prerequisites)
    balance_path = prerequisites_path.parent / prereq["balance"]["path"]
    balance = json.loads(balance_path.read_text())
    balance["available_usd"] = prereq["balance"]["available_usd"] = 9
    prereq["balance"]["sha256"] = _write(balance_path, balance)["sha256"]
    prerequisites_path.write_text(json.dumps(prereq), encoding="utf-8")
    ready = inspect_readiness(fixture["manifest"], fixture["archive"], prerequisites_path,
                              expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
    assert ready["ready_for_paid_execution"] is True
    verify_review_evidence_binding(programme, prerequisites_path)


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
    price["base_url"] += "/"
    preflight["pricing"].update(_write(price_path, price))
    fixture["preflight"].write_text(json.dumps(preflight))
    slash_mismatch = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                       expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
    assert slash_mismatch["ready_for_paid_execution"] is False
    assert "pricing_invalid" in {item["code"] for item in slash_mismatch["issues"]}
    price["base_url"] = price["base_url"].rstrip("/")
    preflight["pricing"].update(_write(price_path, price))
    config_path = evidence / preflight["candidate_config"]["path"]
    candidate_config = json.loads(config_path.read_text())
    candidate_config["base_url"] += "/"
    preflight["candidate_config"].update(_write(config_path, candidate_config))
    fixture["preflight"].write_text(json.dumps(preflight))
    config_slash_mismatch = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                              expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
    assert config_slash_mismatch["ready_for_paid_execution"] is False
    assert "pricing_invalid" in {item["code"] for item in config_slash_mismatch["issues"]}
    candidate_config["base_url"] = candidate_config["base_url"].rstrip("/")
    preflight["candidate_config"].update(_write(config_path, candidate_config))
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
    for kind in ("balance", "fable"):
        path = fixture["preflight"].parent / preflight[kind]["path"]
        original = json.loads(path.read_text())
        changes = ([{"available_usd": 0}, {"available_usd": True}, {"available_usd": float("inf")},
                    {"available_usd": float("nan")}, {"available_usd": 9}, {"currency": "CNY"},
                    {"provider": "other"}] if kind == "balance" else
                   [{"quota_available": False}, {"quota_available": "true"},
                    {"contract_version": "1"}, {"model": "other-judge"}])
        invalid = [{"synthetic": True}, {**original, "schema_version": True},
                   {**original, "kind": "unrelated"},
                   {**original, "observed_at": (fixture["now"] - timedelta(days=3)).isoformat()},
                   {**original, "observed_at": (fixture["now"] + timedelta(days=1)).isoformat()},
                   *({**original, **change} for change in changes)]
        for payload in invalid:
            # Rehash the bad receipt: this exercises its contents, not a SHA mismatch.
            preflight[kind].update(_write(path, payload))
            fixture["preflight"].write_text(json.dumps(preflight))
            held = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                     expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
            assert f"{kind}_invalid" in {issue["code"] for issue in held["issues"]}, payload
            assert held["ready_for_paid_execution"] is False and held["ready_for_packets"] is False
        stale = {**original, "observed_at": (fixture["now"] - timedelta(days=3)).isoformat()}
        preflight[kind].update(_write(path, stale), observed_at=stale["observed_at"])
        fixture["preflight"].write_text(json.dumps(preflight))
        held = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                 expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
        assert f"stale_{kind}" in {issue["code"] for issue in held["issues"]}
        assert held["ready_for_paid_execution"] is False and held["ready_for_packets"] is True
        preflight[kind].update(_write(path, original), observed_at=original["observed_at"])
    fixture["preflight"].write_text(json.dumps(preflight))
    ready = inspect_readiness(fixture["manifest"], fixture["archive"], fixture["preflight"],
                              expected_manifest_sha=fixture["manifest_sha"], now=fixture["now"])
    assert ready["ready_for_paid_execution"] is True
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
    assert mapping["collector_index"]["sha256"] == hashlib.sha256(fixture["outputs"].read_bytes()).hexdigest()
    assert mapping["programme_ledger"]["sha256"] == hashlib.sha256(
        (fixture["outputs"].parent / "budget.sqlite3").read_bytes()).hexdigest()
    assert {row["arm"] for row in mapping["reviewers"]["reviewer-1"]} == {"candidate", "comparator"}
    original = Path(mapping["reviewers"]["reviewer-1"][0]["raw_artifacts"]["canonical"]["path"])
    raw = json.loads(original.read_text())
    assert set(raw) == {column.name for column in Summary.__table__.columns}
    assert raw["prompt_version"].startswith("synthetic-")
    for private in mapping["reviewers"]["reviewer-1"]:
        assert {"receipt", "events", "raw_previews", "provider_accounting"} <= private["collector_evidence"].keys()
        for artifact in private["reviewer_artifacts"].values():
            path = reviewer_root / "reviewer-1" / artifact["path"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
        early = private["reviewer_artifacts"]["preview_0"]["path"]
        assert "Incorrect early preview" in (reviewer_root / "reviewer-1" / early).read_text()
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
    original_index = fixture["outputs"].read_bytes()

    def refused(message):
        before = fixture["outputs"].read_bytes()
        with pytest.raises(ValueError, match=message):
            build_blinded_packets(fixture["manifest"], fixture["archive"], fixture["preflight"],
                                  fixture["outputs"], tmp_path / "no-reviewers", tmp_path / "no-custodian",
                                  expected_manifest_sha=fixture["manifest_sha"])
        assert fixture["outputs"].read_bytes() == before
        assert not (tmp_path / "no-reviewers").exists()
        assert not (tmp_path / "no-custodian").exists()

    # Coherent, self-authored omissions used to pass the row/hash-only packet gate.
    for omitted in (1, 2):
        outputs = json.loads(original_index)
        row = outputs["records"][0]
        row["preview_paths"] = row["preview_paths"][omitted:]
        row["preview_count"] = len(row["preview_paths"])
        row["artifact_sha256"].pop("preview_0")
        last_hash = row["artifact_sha256"].pop("preview_1")
        if row["preview_paths"]:
            row["artifact_sha256"]["preview_0"] = last_hash
        fixture["outputs"].write_text(json.dumps(outputs))
        refused("differs from durable collector evidence")
    outputs = json.loads(original_index)
    outputs["complete"] = False
    fixture["outputs"].write_text(json.dumps(outputs))
    refused("collector evidence is incomplete")
    fixture["outputs"].write_bytes(original_index)
    row = outputs["records"][0]
    root = fixture["outputs"].parent
    # Revalidation must consult each retained channel, not trust the saved collector flag.
    for key in ("receipt", "events", "raw_previews", "provider_accounting"):
        evidence = root / row["collector_evidence"][key]["path"]
        original = evidence.read_bytes()
        evidence.write_text('{}\n')
        refused("collector evidence is incomplete")
        evidence.write_bytes(original)
    preview = root / row["preview_paths"][0]
    original_preview = preview.read_bytes()
    preview.unlink()
    refused("collector evidence is incomplete")
    assert not preview.exists()  # Packet inspection must not reconstruct missing evidence.
    preview.write_bytes(original_preview)
    with sqlite3.connect(root / "budget.sqlite3") as db:
        db.execute("UPDATE reservations SET status='pending' WHERE slot_id=?", (row["slot_id"],))
    refused("collector evidence is incomplete")
    # A self-authored index without any durable programme association also fails closed.
    fixture["outputs"].write_text(json.dumps({"records": outputs["records"]}))
    refused("missing relative file path")
    fixture["outputs"].write_bytes(original_index)
    outside = tmp_path / "outside.sqlite3"
    outside.write_bytes(b"not a programme")
    outputs["programme_ledger_path"] = "../outside.sqlite3"
    fixture["outputs"].write_text(json.dumps(outputs))
    refused("unsafe relative file path")


def test_blinding_rejects_corrupted_source_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = _fixture(tmp_path)
    original_copy = acceptance_readiness.shutil.copyfile

    def corrupt_source_copy(source: Path, destination: Path) -> None:
        original_copy(source, destination)
        if "sources" in Path(destination).parts:
            Path(destination).write_bytes(Path(destination).read_bytes() + b"corrupt")

    monkeypatch.setattr(acceptance_readiness.shutil, "copyfile", corrupt_source_copy)
    reviewers, custodian = tmp_path / "reviewers", tmp_path / "custodian"
    with pytest.raises(ValueError, match="copy differs from frozen source packet"):
        build_blinded_packets(fixture["manifest"], fixture["archive"], fixture["preflight"],
                              fixture["outputs"], reviewers, custodian,
                              expected_manifest_sha=fixture["manifest_sha"])
    assert not reviewers.exists() and not custodian.exists()


def test_blinding_rejects_raw_rendered_identity_marker(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    outputs = json.loads(fixture["outputs"].read_text())
    row = outputs["records"][0]
    rendered = fixture["outputs"].parent / row["rendered_path"]
    rendered.write_text(f"Revenue rose. {row['config_sha256']}", encoding="utf-8")
    # This fixture represents an identity leak present at generation, not a later edit.
    receipt_path = rendered.parent / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["artifact_sha256"]["rendered_summary"] = hashlib.sha256(rendered.read_bytes()).hexdigest()
    _write(receipt_path, receipt)
    result = _write(rendered.parent / "result.json", receipt)
    with sqlite3.connect(fixture["outputs"].parent / "budget.sqlite3") as db:
        db.execute("UPDATE slots SET result_sha=? WHERE id=?", (result["sha256"], row["slot_id"]))
    fixture["outputs"].write_text(json.dumps(inspect_outputs(
        fixture["outputs"].parent, fixture["outputs"].parent,
        expected_manifest_sha=fixture["manifest_sha"])))
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
