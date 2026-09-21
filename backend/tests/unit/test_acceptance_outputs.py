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


def _fixture(tmp_path: Path, *, sixk: bool = False, primary_fallback: bool = False) -> tuple[Path, Path, Path]:
    root = tmp_path / "programme"
    root.mkdir()
    slot_id = "H01-candidate-1"
    slot = root / slot_id
    invocation = slot / "attempt-1"
    invocation.mkdir(parents=True)
    config_sha = "a" * 64
    primary_text = "Verified 6-K primary text"
    source_sha = hashlib.sha256(primary_text.encode()).hexdigest() if sixk else "b" * 64
    submission_sha = "c" * 64
    filing = {
        "holdout_id": "H01", "accession_number": "0000018230-26-000008",
        "ticker": "CAT", "cik": "18230", "filing_type": "6-K" if sixk else "10-K",
        "source_sha256": source_sha,
    }
    if sixk:
        filing.update(filing_date="2026-02-13",
                      document_url="https://www.sec.gov/Archives/edgar/data/18230/filing.htm")
        filing["source_packets"] = [
            {"role": "primary", "path": "e7-sources/H01/filing.htm", "sha256": source_sha,
             "bytes": len(primary_text.encode()),
             "provenance": {"requested_url": filing["document_url"]}},
            {"role": "complete_submission", "path": "e7-sources/H01/complete.txt",
             "sha256": submission_sha, "bytes": 1000,
             "provenance": {"requested_url": "https://www.sec.gov/Archives/edgar/data/18230/complete.txt"}},
        ]
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
        "eligible_for_measurement": True, "errors": [],
        "source_identity": "archived_sgml_verified" if sixk else "primary_verified",
        "source_packets": {"primary": {"sha256": source_sha}}, "artifacts": artifacts,
    }
    if sixk:
        receipt["source_packets"] = {
            packet["role"]: {"path": str(root / packet["path"]), "sha256": packet["sha256"],
                             "bytes": packet["bytes"],
                             "requested_url": packet["provenance"]["requested_url"]}
            for packet in filing["source_packets"]
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
    if sixk:
        extracted = "" if primary_fallback else "Verified 6-K extracted text"
        extracted_sha = hashlib.sha256(extracted.encode()).hexdigest()
        final_text = primary_text if primary_fallback else extracted
        calls = [
            {"owner": "edgartools.Filing.from_sgml_text", "accession": filing["accession_number"],
             "cik": filing["cik"], "form": "6-K", "filing_date": filing["filing_date"],
             "complete_submission_sha256": submission_sha, "embedded_primary_sha256": source_sha,
             "selected_attachments": []},
            {"owner": "get_sixk_text", "accession": filing["accession_number"],
             "cik": filing["cik"], "bytes": len(extracted.encode()), "sha256": extracted_sha,
             "source_packet_match": "verified_complete_submission"},
        ]
        if primary_fallback:
            calls.append({"owner": "sec_edgar_service.get_filing_document",
                          "url": filing["document_url"], "bytes": len(primary_text.encode()),
                          "sha256": source_sha})
        calls.append({"owner": "get_or_cache_excerpt", "accession": filing["accession_number"],
                      "filing_text_sha256": hashlib.sha256(final_text.encode()).hexdigest()})
        _write(invocation / "grounding.json", {"source_calls": calls,
                                                 "summarizer_calls": [{"args": [final_text]}]})
        _write(invocation / "source_evidence.json", receipt["source_packets"])
    else:
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


def test_collects_sixk_only_with_embedded_sgml_proof(tmp_path: Path) -> None:
    root, output, invocation = _fixture(tmp_path, sixk=True)
    result = collect_outputs(root, output)
    assert result["completed"] == 1, result["incomplete_slots"]
    assert result["records"][0]["accession_number"] == "0000018230-26-000008"
    assert result["records"][0]["raw_previews_sha256"] == _sha(invocation / "raw_previews.jsonl")


def test_collects_sixk_verified_primary_fallback(tmp_path: Path) -> None:
    root, output, _ = _fixture(tmp_path, sixk=True, primary_fallback=True)
    result = collect_outputs(root, output)
    assert result["completed"] == 1, result["incomplete_slots"]


def test_rejects_sixk_hash_or_evidence_drift(tmp_path: Path) -> None:
    root, output, invocation = _fixture(tmp_path, sixk=True)
    grounding_path = invocation / "grounding.json"
    grounding = json.loads(grounding_path.read_text())
    grounding["source_calls"][0]["embedded_primary_sha256"] = "f" * 64
    _write(grounding_path, grounding)
    first = collect_outputs(root, output)
    assert first["completed"] == 0
    assert "embedded primary or complete submission proof differs" in first["incomplete_slots"][0]["error"]
    grounding["source_calls"][0]["embedded_primary_sha256"] = json.loads(
        (invocation / "receipt.json").read_text())["source_packets"]["primary"]["sha256"]
    _write(grounding_path, grounding)
    evidence_path = invocation / "source_evidence.json"
    evidence = json.loads(evidence_path.read_text())
    evidence["complete_submission"]["sha256"] = "f" * 64
    _write(evidence_path, evidence)
    second = collect_outputs(root, output)
    assert second["completed"] == 0
    assert "retained source evidence differs" in second["incomplete_slots"][0]["error"]


def test_rejects_sixk_missing_extractor_proof_and_non_sixk_status_flip(tmp_path: Path) -> None:
    root, output, invocation = _fixture(tmp_path, sixk=True)
    grounding_path = invocation / "grounding.json"
    grounding = json.loads(grounding_path.read_text())
    grounding["source_calls"][1]["source_packet_match"] = "unverified"
    _write(grounding_path, grounding)
    result = collect_outputs(root, output)
    assert result["completed"] == 0
    assert "lacks verified SGML association" in result["incomplete_slots"][0]["error"]
    other = tmp_path / "other"
    other.mkdir()
    root2, output2, invocation2 = _fixture(other)
    receipt = json.loads((invocation2 / "receipt.json").read_text())
    receipt["source_identity"] = "archived_sgml_verified"
    _write(invocation2 / "receipt.json", receipt)
    _write(invocation2 / "result.json", receipt)
    non_sixk = collect_outputs(root2, output2)
    assert non_sixk["completed"] == 0
    assert "non-6-K" in non_sixk["incomplete_slots"][0]["error"]


def test_rejects_sixk_complete_submission_hash_and_missing_primary_fallback(tmp_path: Path) -> None:
    root, output, invocation = _fixture(tmp_path, sixk=True, primary_fallback=True)
    grounding_path = invocation / "grounding.json"
    grounding = json.loads(grounding_path.read_text())
    grounding["source_calls"][0]["complete_submission_sha256"] = "e" * 64
    _write(grounding_path, grounding)
    first = collect_outputs(root, output)
    assert first["completed"] == 0
    assert "embedded primary or complete submission proof differs" in first["incomplete_slots"][0]["error"]
    grounding["source_calls"][0]["complete_submission_sha256"] = json.loads(
        (invocation / "receipt.json").read_text())["source_packets"]["complete_submission"]["sha256"]
    grounding["source_calls"] = [call for call in grounding["source_calls"]
                                 if call["owner"] != "sec_edgar_service.get_filing_document"]
    _write(grounding_path, grounding)
    second = collect_outputs(root, output)
    assert second["completed"] == 0
    assert "lacks verified primary fallback" in second["incomplete_slots"][0]["error"]
