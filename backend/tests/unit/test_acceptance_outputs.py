"""Offline E7 output collection from synthetic durable slot evidence."""

import hashlib
import json
import sqlite3
from pathlib import Path

from evals.acceptance_outputs import collect_outputs
from evals.acceptance_readiness import APPROVED_MANIFEST_SHA256


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "programme"
    root.mkdir()
    slot_id = "H01-candidate-1"
    slot = root / slot_id
    invocation = slot / "attempt-1"
    invocation.mkdir(parents=True)
    config_sha = "a" * 64
    source_sha = "b" * 64
    filing = {
        "holdout_id": "H01", "accession_number": "0000018230-26-000008",
        "ticker": "CAT", "cik": "18230", "filing_type": "10-K",
        "source_sha256": source_sha,
    }
    selection = {"slot_id": slot_id, "arm": "candidate", "draw": 1,
                 "filing": filing, "config_sha256": config_sha,
                 "manifest_sha256": APPROVED_MANIFEST_SHA256}
    _write(slot / "selection.json", selection)
    request = {"slot_id": slot_id, "filing": filing, "config_sha256": config_sha,
               "invocation_dir": str(invocation)}
    _write(slot / "request.json", request)
    artifacts = {
        "canonical_summary": "canonical_summary.json", "rendered_summary": "rendered_summary.md",
        "export_html": "export.html", "raw_previews": "raw_previews.jsonl",
        "provider_accounting": "provider_accounting.json", "events": "events.jsonl",
        "grounding": "grounding.json", "rendered_sections": "rendered_sections.json",
    }
    receipt = {
        "identity": {key: filing[key] for key in ("holdout_id", "accession_number", "ticker", "cik", "filing_type")},
        "started_at": "2026-09-21T10:00:00+00:00", "status": "complete",
        "eligible_for_measurement": True, "errors": [], "source_identity": "primary_verified",
        "source_packets": {"primary": {"sha256": source_sha}}, "artifacts": artifacts,
    }
    _write(invocation / "receipt.json", receipt)
    _write(invocation / "result.json", receipt)
    _write(invocation / "canonical_summary.json", {"business_overview": "Synthetic result"})
    (invocation / "rendered_summary.md").write_text("Synthetic result", encoding="utf-8")
    (invocation / "export.html").write_text("<p>Synthetic result</p>", encoding="utf-8")
    frames = [
        {"generation_ordinal": 0, "provider_attempt": 9, "markdown": "First preview\nfull text"},
        {"generation_ordinal": 0, "provider_attempt": 9, "markdown": "Second preview Ω"},
    ]
    (invocation / "raw_previews.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in frames), encoding="utf-8"
    )
    _write(invocation / "provider_accounting.json", {
        "slot_id": slot_id,
        "records": [{"reservation_id": 9, "status": "settled", "request": {"model": "synthetic"}}],
    })
    (invocation / "events.jsonl").write_text('{"type":"complete"}\n', encoding="utf-8")
    _write(invocation / "grounding.json", {"excerpt": "Synthetic"})
    _write(invocation / "rendered_sections.json", [])
    with sqlite3.connect(root / "budget.sqlite3") as db:
        db.execute("CREATE TABLE slots (id TEXT PRIMARY KEY, config_sha TEXT, status TEXT, request_sha TEXT)")
        db.execute("CREATE TABLE reservations (id INTEGER PRIMARY KEY, slot_id TEXT, status TEXT, request_hash TEXT)")
        db.execute("INSERT INTO slots VALUES (?, ?, 'completed', ?)", (slot_id, config_sha, _sha(slot / "request.json")))
        db.execute("INSERT INTO reservations VALUES (9, ?, 'settled', ?)",
                   (slot_id, hashlib.sha256(json.dumps({"model": "synthetic"}, sort_keys=True,
                                                      separators=(",", ":")).encode()).hexdigest()))
        db.execute("INSERT INTO slots VALUES ('development-smoke', ?, 'completed', ?)",
                   (config_sha, "c" * 64))
    return root, root / "outputs.json", invocation


def test_collects_actual_raw_frames_and_is_idempotent(tmp_path: Path) -> None:
    root, output, invocation = _fixture(tmp_path)
    originals = {name: _sha(invocation / name) for name in
                 ("raw_previews.jsonl", "canonical_summary.json", "rendered_summary.md", "export.html")}
    first = collect_outputs(root, output)
    assert first["completed"] == 1 and first["expected"] == 120 and first["complete"] is False
    assert len(first["missing_slot_ids"]) == 119
    assert first["development_smoke"] == [{"slot_id": "development-smoke", "ledger_status": "completed",
                                            "reservation_count": 0}]
    row = first["records"][0]
    assert row["status"] == "completed" and row["error"] is None
    assert row["preview_count"] == 2 and row["previews_truncated"] is False
    assert row["retry_preview_attempts_omitted"] == 0
    assert [(root / relative).read_text() for relative in row["preview_paths"]] == [
        "First preview\nfull text", "Second preview Ω",
    ]
    assert row["raw_previews_sha256"] == originals["raw_previews.jsonl"]
    assert row["artifact_sha256"]["preview_0"] == _sha(root / row["preview_paths"][0])
    assert first == collect_outputs(root, output)
    assert originals == {name: _sha(invocation / name) for name in originals}
    assert json.loads(output.read_text()) == first


def test_rejects_unknown_preview_attempt_without_imputing_completion(tmp_path: Path) -> None:
    root, output, invocation = _fixture(tmp_path)
    raw = invocation / "raw_previews.jsonl"
    frames = [json.loads(line) for line in raw.read_text().splitlines()]
    frames[1]["provider_attempt"] = 42
    raw.write_text("".join(json.dumps(item) + "\n" for item in frames))
    result = collect_outputs(root, output)
    assert result["records"] == [] and result["completed"] == 0 and result["complete"] is False
    assert result["incomplete_slots"][0]["slot_id"] == "H01-candidate-1"
    assert "provider attempt" in result["incomplete_slots"][0]["error"]
    assert not (invocation / "preview-files").exists()


def test_rejects_source_mismatch_and_preserves_failed_slot(tmp_path: Path) -> None:
    root, output, invocation = _fixture(tmp_path)
    receipt = json.loads((invocation / "receipt.json").read_text())
    receipt["source_identity"] = "incomplete"
    _write(invocation / "receipt.json", receipt)
    _write(invocation / "result.json", receipt)
    with sqlite3.connect(root / "budget.sqlite3") as db:
        db.execute("INSERT INTO slots VALUES ('H02-candidate-1', ?, 'incomplete', ?)", ("a" * 64, "c" * 64))
    result = collect_outputs(root, output)
    assert result["records"] == []
    assert {item["slot_id"] for item in result["incomplete_slots"]} == {
        "H01-candidate-1", "H02-candidate-1",
    }
    assert "H02-candidate-1" not in result["missing_slot_ids"]


def test_rejects_artifact_symlink_without_reading_outside(tmp_path: Path) -> None:
    root, output, invocation = _fixture(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("do not expose", encoding="utf-8")
    (invocation / "rendered_summary.md").unlink()
    (invocation / "rendered_summary.md").symlink_to(outside)
    result = collect_outputs(root, output)
    assert result["records"] == [] and result["complete"] is False
    assert "artifact symlink" in result["incomplete_slots"][0]["error"]
    assert not (invocation / "preview-files").exists()


def test_rejects_accounting_request_drift_and_does_not_create_previews(tmp_path: Path) -> None:
    root, output, invocation = _fixture(tmp_path)
    accounting = json.loads((invocation / "provider_accounting.json").read_text())
    accounting["records"][0]["request"]["model"] = "different"
    _write(invocation / "provider_accounting.json", accounting)
    result = collect_outputs(root, output)
    assert result["completed"] == 0
    assert "differs from durable reservation" in result["incomplete_slots"][0]["error"]
    assert not (invocation / "preview-files").exists()


def test_rejects_truncated_jsonl_and_existing_preview_drift(tmp_path: Path) -> None:
    root, output, invocation = _fixture(tmp_path)
    raw = invocation / "raw_previews.jsonl"
    complete_raw = raw.read_bytes()
    raw.write_bytes(complete_raw.rstrip(b"\n"))
    result = collect_outputs(root, output)
    assert result["completed"] == 0
    assert "without a complete newline" in result["incomplete_slots"][0]["error"]
    raw.write_bytes(complete_raw)
    first = collect_outputs(root, output)
    assert first["completed"] == 1
    (invocation / "preview-files" / "0002.md").write_text("edited preview", encoding="utf-8")
    second = collect_outputs(root, output)
    assert second["completed"] == 0 and second["complete"] is False
    assert "existing preview differs" in second["incomplete_slots"][0]["error"]
    assert raw.read_bytes() == complete_raw


def test_rejects_missing_emitted_terminal_event(tmp_path: Path) -> None:
    root, output, invocation = _fixture(tmp_path)
    (invocation / "events.jsonl").write_text('{"type":"error","message":"failed"}\n', encoding="utf-8")
    result = collect_outputs(root, output)
    assert result["completed"] == 0 and result["complete"] is False
    assert "one clean completion" in result["incomplete_slots"][0]["error"]
    assert not (invocation / "preview-files").exists()


def test_reports_orphan_provider_reservation(tmp_path: Path) -> None:
    root, output, _ = _fixture(tmp_path)
    with sqlite3.connect(root / "budget.sqlite3") as db:
        db.execute("INSERT INTO reservations VALUES (10, 'unknown-slot', 'settled', ?)", ("d" * 64,))
    result = collect_outputs(root, output)
    assert result["completed"] == 1 and result["complete"] is False
    assert result["orphan_reservation_slot_ids"] == ["unknown-slot"]
