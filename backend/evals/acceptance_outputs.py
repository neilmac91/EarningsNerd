"""Build a packet index from durable E7 slot evidence, without running a model.

The index is deliberately partial until every approved slot has a valid, retained
production-worker result. Original invocation files remain the custodian record.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from evals.acceptance_readiness import (APPROVED_MANIFEST_SHA256, COMPARATOR_HOLDOUT_IDS,
                                        verify_review_evidence_binding)

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
_SLOT = re.compile(r"(H\d{2})-(candidate|comparator)-([123])\Z")
_EXPECTED = frozenset(
    f"H{number:02d}-{arm}-{draw}"
    for number in range(1, 31)
    for arm in (("candidate", "comparator") if f"H{number:02d}" in COMPARATOR_HOLDOUT_IDS else ("candidate",))
    for draw in (1, 2, 3)
)
_REQUIRED_WORKER_ARTIFACTS = {
    "canonical_summary", "rendered_summary", "export_html", "raw_previews",
    "provider_accounting", "events", "grounding", "rendered_sections",
}


class IncompleteSlot(ValueError):
    """A claimed slot cannot be represented as a completed review output."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise IncompleteSlot(f"{path.name} is not a JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _within(root: Path, relative: str) -> Path:
    """Return only a regular, unsymlinked file inside the invocation directory."""
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise IncompleteSlot("missing or absolute artifact path")
    parts = Path(relative).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise IncompleteSlot("artifact path traversal")
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise IncompleteSlot("artifact symlink")
    if not current.is_file() or not current.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
        raise IncompleteSlot("artifact missing or outside invocation")
    return current


def _output_relative(path: Path, output_parent: Path) -> str:
    try:
        return path.resolve(strict=True).relative_to(output_parent.resolve(strict=True)).as_posix()
    except ValueError as error:
        raise IncompleteSlot("output artifacts must sit below outputs.json parent") from error


def _validate_preview_frames(path: Path, reservation_ids: set[int]) -> list[bytes]:
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise IncompleteSlot("raw preview JSONL ends without a complete newline")
    frames: list[bytes] = []
    for ordinal, line in enumerate(raw.splitlines(), start=1):
        try:
            frame = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise IncompleteSlot(f"invalid raw preview JSONL line {ordinal}") from error
        if (not isinstance(frame, dict) or set(frame) != {"generation_ordinal", "provider_attempt", "markdown"}
                or frame["generation_ordinal"] != 0 or type(frame["provider_attempt"]) is not int
                or frame["provider_attempt"] <= 0 or frame["provider_attempt"] not in reservation_ids
                or not isinstance(frame["markdown"], str)):
            raise IncompleteSlot(f"raw preview line {ordinal} has no valid provider attempt/content")
        frames.append(frame["markdown"].encode("utf-8"))
    return frames


def _validate_events(path: Path) -> None:
    raw = path.read_bytes()
    if not raw or not raw.endswith(b"\n"):
        raise IncompleteSlot("emitted event JSONL is empty or unterminated")
    terminals = []
    last_type = None
    for ordinal, line in enumerate(raw.splitlines(), start=1):
        try:
            event = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise IncompleteSlot(f"invalid emitted event JSONL line {ordinal}") from error
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise IncompleteSlot(f"malformed emitted event JSONL line {ordinal}")
        last_type = event["type"]
        if event["type"] in {"complete", "partial", "error"}:
            terminals.append(event["type"])
    if terminals != ["complete"] or last_type != "complete":
        raise IncompleteSlot("emitted events do not end in one clean completion")


def _validate_sixk_source(filing: dict[str, Any], receipt: dict[str, Any], invocation: Path,
                          grounding_path: Path) -> None:
    if receipt.get("source_identity") != "archived_sgml_verified":
        raise IncompleteSlot("6-K lacks archived SGML identity proof")
    selected = filing.get("source_packets")
    evidence = receipt.get("source_packets")
    if not isinstance(selected, list) or not isinstance(evidence, dict):
        raise IncompleteSlot("6-K source packet inventory missing")
    packets: dict[str, dict[str, Any]] = {}
    for packet in selected:
        if not isinstance(packet, dict) or not isinstance(packet.get("role"), str):
            raise IncompleteSlot("6-K selected source packet malformed")
        role = packet["role"]
        if role in packets:
            raise IncompleteSlot("6-K selected source packet role duplicated")
        packets[role] = packet
    if not {"primary", "complete_submission"}.issubset(packets) or set(evidence) != set(packets):
        raise IncompleteSlot("6-K primary/complete source roles missing or changed")
    if _read_json(_within(invocation, "source_evidence.json")) != evidence:
        raise IncompleteSlot("6-K retained source evidence differs from receipt")
    for role, packet in packets.items():
        item = evidence.get(role)
        relative = packet.get("path")
        if (not isinstance(item, dict) or not isinstance(relative, str) or
                not _SHA256.fullmatch(str(packet.get("sha256", ""))) or
                type(packet.get("bytes")) is not int or packet["bytes"] <= 0 or
                item.get("sha256") != packet["sha256"] or item.get("bytes") != packet.get("bytes") or
                item.get("requested_url") != (packet.get("provenance") or {}).get("requested_url") or
                not isinstance(item.get("path"), str) or
                tuple(Path(item["path"]).parts[-len(Path(relative).parts):]) != Path(relative).parts):
            raise IncompleteSlot(f"6-K {role} evidence does not match selected source packet")
    primary, submission = evidence["primary"], evidence["complete_submission"]
    if primary["sha256"] != filing["source_sha256"]:
        raise IncompleteSlot("6-K verified primary hash differs from selected filing")
    grounding = _read_json(grounding_path)
    calls = grounding.get("source_calls")
    if not isinstance(calls, list) or any(not isinstance(call, dict) for call in calls):
        raise IncompleteSlot("6-K source grounding is malformed")
    source = [call for call in calls if call.get("owner") == "edgartools.Filing.from_sgml_text"]
    extractor = [call for call in calls if call.get("owner") == "get_sixk_text"]
    if len(source) != 1 or len(extractor) != 1:
        raise IncompleteSlot("6-K archived SGML/extractor proof is missing or duplicated")
    source, extractor = source[0], extractor[0]
    attachments = source.get("selected_attachments")
    if (source.get("accession") != filing["accession_number"] or
            str(source.get("cik")) != str(filing["cik"]) or source.get("form") != "6-K" or
            str(source.get("filing_date")) != str(filing.get("filing_date")) or
            source.get("complete_submission_sha256") != submission["sha256"] or
            source.get("embedded_primary_sha256") != primary["sha256"] or
            not isinstance(attachments, list) or
            any(not isinstance(name, str) or not name for name in attachments) or
            len(attachments) != len(set(attachments))):
        raise IncompleteSlot("6-K embedded primary or complete submission proof differs")
    if "earnings_exhibit" in packets and Path(packets["earnings_exhibit"]["path"]).name not in attachments:
        raise IncompleteSlot("6-K selected earnings exhibit absent from extraction proof")
    count, digest = extractor.get("bytes"), extractor.get("sha256")
    if (extractor.get("accession") != filing["accession_number"] or
            str(extractor.get("cik")) != str(filing["cik"]) or
            extractor.get("source_packet_match") != "verified_complete_submission" or
            type(count) is not int or count < 0 or not _SHA256.fullmatch(str(digest))):
        raise IncompleteSlot("6-K extractor result lacks verified SGML association")
    if count == 0:
        if digest != _EMPTY_SHA256:
            raise IncompleteSlot("6-K empty extractor hash is not the empty-content hash")
        fetched = [call for call in calls if call.get("owner") == "sec_edgar_service.get_filing_document"]
        if (len(fetched) != 1 or fetched[0].get("sha256") != primary["sha256"] or
                fetched[0].get("bytes") != primary["bytes"] or
                fetched[0].get("url") != filing.get("document_url")):
            raise IncompleteSlot("6-K empty extractor lacks verified primary fallback")
        expected_filing_hash = primary["sha256"]
    else:
        expected_filing_hash = digest
    excerpts = [call for call in calls if call.get("owner") == "get_or_cache_excerpt"]
    summaries = grounding.get("summarizer_calls")
    if (len(excerpts) != 1 or excerpts[0].get("accession") != filing["accession_number"] or
            excerpts[0].get("filing_text_sha256") != expected_filing_hash or
            not isinstance(summaries, list) or len(summaries) != 1 or
            not isinstance(summaries[0], dict) or not isinstance(summaries[0].get("args"), list) or
            not summaries[0]["args"] or not isinstance(summaries[0]["args"][0], str) or
            hashlib.sha256(summaries[0]["args"][0].encode("utf-8")).hexdigest() != expected_filing_hash or
            (count > 0 and len(summaries[0]["args"][0].encode("utf-8")) != count)):
        raise IncompleteSlot("6-K summarizer grounding differs from verified extractor/primary text")


def _write_preview_files(invocation: Path, frames: list[bytes], *, materialize: bool = True) -> list[Path]:
    directory = invocation / "preview-files"
    if directory.is_symlink():
        raise IncompleteSlot("preview directory is a symlink")
    if not frames and not directory.exists():
        return []
    if materialize:
        directory.mkdir(exist_ok=True)
    if not directory.is_dir():
        raise IncompleteSlot("preview directory is not a directory")
    expected_names = {f"{number:04d}.md" for number in range(1, len(frames) + 1)}
    existing_names = {path.name for path in directory.iterdir()}
    if existing_names - expected_names:
        raise IncompleteSlot("preview directory contains an unindexed callback file")
    paths: list[Path] = []
    for number, content in enumerate(frames, start=1):
        target = directory / f"{number:04d}.md"
        if target.exists() or target.is_symlink():
            if target.is_symlink() or not target.is_file() or target.read_bytes() != content:
                raise IncompleteSlot(f"existing preview differs from raw callback {number}")
        else:
            if not materialize:
                raise IncompleteSlot(f"retained preview missing for raw callback {number}")
            try:
                descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError as error:
                raise IncompleteSlot(f"preview write race at callback {number}") from error
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        paths.append(target)
    return paths


def _slot_record(
    programme_root: Path, output_parent: Path, slot_id: str, config_sha: str,
    request_sha: str, result_sha: str, ledger_reservations: list[tuple[int, str, str]],
    *, expected_manifest_sha: str = APPROVED_MANIFEST_SHA256,
    expected_filing: dict[str, Any] | None = None,
    expected_source_binding: dict[str, Any] | None = None,
    expected_source_root: Path | None = None,
    materialize_previews: bool = True,
) -> dict[str, Any]:
    match = _SLOT.fullmatch(slot_id)
    if match is None or slot_id not in _EXPECTED:
        raise IncompleteSlot("unapproved slot identity")
    holdout_id, arm, draw_text = match.groups()
    draw = int(draw_text)
    if not _SHA256.fullmatch(config_sha) or not _SHA256.fullmatch(request_sha or ""):
        raise IncompleteSlot("slot has no durable configuration/request hash")
    slot_dir = programme_root / slot_id
    if slot_dir.is_symlink() or not slot_dir.is_dir():
        raise IncompleteSlot("slot directory missing or symlinked")
    invocation = slot_dir / "attempt-1"
    if invocation.is_symlink() or not invocation.is_dir():
        raise IncompleteSlot("invocation directory missing or symlinked")
    selection_path = _within(slot_dir, "selection.json")
    request_path = _within(slot_dir, "request.json")
    receipt_path = _within(invocation, "receipt.json")
    result_path = _within(invocation, "result.json")
    selection, request = _read_json(selection_path), _read_json(request_path)
    receipt, result = _read_json(receipt_path), _read_json(result_path)
    if not _SHA256.fullmatch(result_sha or "") or _sha256(result_path) != result_sha:
        raise IncompleteSlot("durable completion hash differs from retained worker result")
    if _sha256(request_path) != request_sha:
        raise IncompleteSlot("durable request hash differs from retained request")
    filing = selection.get("filing")
    if (not isinstance(filing, dict) or
            any(not str(filing.get(key, "")).strip() for key in
                ("holdout_id", "ticker", "cik", "filing_type", "accession_number")) or
            not _SHA256.fullmatch(str(filing.get("source_sha256", "")))):
        raise IncompleteSlot("selected filing identity or source hash is missing")
    if (selection.get("slot_id") != slot_id or
            selection.get("arm") != arm or selection.get("draw") != draw or
            selection.get("config_sha256") != config_sha or
            selection.get("manifest_sha256") != expected_manifest_sha or
            filing.get("holdout_id") != holdout_id or
            request.get("slot_id") != slot_id or request.get("config_sha256") != config_sha or
            request.get("filing") != filing or Path(request.get("invocation_dir", "")).resolve() != invocation.resolve()):
        raise IncompleteSlot("selection, request, manifest or ledger identity mismatch")
    if expected_filing is not None and filing != expected_filing:
        raise IncompleteSlot("selected filing differs from frozen effective source contract")
    expected_identity = {key: str(filing.get(key)) for key in
                         ("holdout_id", "ticker", "cik", "filing_type", "accession_number")}
    if ({key: str((receipt.get("identity") or {}).get(key)) for key in expected_identity} != expected_identity or
            receipt != result or receipt.get("status") != "complete" or
            receipt.get("eligible_for_measurement") is not True or receipt.get("errors") != [] or
            (receipt.get("source_packets") or {}).get("primary", {}).get("sha256") != filing.get("source_sha256")):
        raise IncompleteSlot("worker result is incomplete or source/filing identity differs")
    if expected_source_binding is not None:
        if receipt.get("source_identity") != "frozen_archive_verified":
            raise IncompleteSlot("worker result lacks frozen archive source identity")
        if receipt.get("source_binding") != expected_source_binding:
            raise IncompleteSlot("worker supplemental source binding differs from frozen contract")
    elif filing["filing_type"] != "6-K" and receipt.get("source_identity") != "primary_verified":
        raise IncompleteSlot("non-6-K worker result lacks verified primary source")
    try:
        started = datetime.fromisoformat(receipt["started_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as error:
        raise IncompleteSlot("receipt has no valid started_at") from error
    if started.tzinfo is None:
        raise IncompleteSlot("receipt started_at lacks timezone")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, dict) or not _REQUIRED_WORKER_ARTIFACTS.issubset(artifacts):
        raise IncompleteSlot("worker artifact inventory is incomplete")
    if expected_source_binding is not None and not {"source_evidence", "frozen_settings"}.issubset(artifacts):
        raise IncompleteSlot("worker frozen source artifact inventory is incomplete")
    resolved = {key: _within(invocation, relative) for key, relative in artifacts.items()}
    if len(set(resolved.values())) != len(resolved):
        raise IncompleteSlot("worker artifact path reused")
    if expected_source_binding is not None:
        source_evidence = _read_json(resolved["source_evidence"])
        if source_evidence != receipt.get("source_packets"):
            raise IncompleteSlot("retained source evidence differs from worker receipt")
        packets = filing.get("source_packets")
        if not isinstance(packets, list):
            raise IncompleteSlot("effective filing source packets are missing")
        for packet in packets:
            if not isinstance(packet, dict) or not isinstance(packet.get("role"), str):
                raise IncompleteSlot("effective filing source packet is malformed")
            observed = source_evidence.get(packet["role"])
            relative = packet.get("path")
            if (not isinstance(observed, dict) or not isinstance(relative, str) or
                    any(observed.get(field) != packet.get(field) for field in ("sha256", "bytes")) or
                    observed.get("requested_url") != (packet.get("provenance") or {}).get("requested_url") or
                    not isinstance(observed.get("path"), str) or
                    tuple(Path(observed["path"]).parts[-len(Path(relative).parts):]) != Path(relative).parts):
                raise IncompleteSlot(f"{packet['role']} evidence differs from effective source packet")
        grounding = _read_json(resolved["grounding"])
        archive = grounding.get("archive_binding")
        if (not isinstance(archive, dict) or archive.get("source_evidence") != source_evidence or
                archive.get("source_violations") != [] or
                archive.get("grounding_complete") is not True or
                archive.get("source_binding") != "frozen_complete_submission_and_raw_sec_json"):
            raise IncompleteSlot("archive binding report is missing, changed or violated")
        trace = archive.get("source_calls")
        if not isinstance(trace, list) or not trace or any(not isinstance(row, dict) for row in trace):
            raise IncompleteSlot("archive source trace is missing or malformed")
        terminal = {
            "edgar.resolve_filing_by_accession": {"bound"},
            "edgar.Filing.sgml": {"bound"},
            "sec_edgar_service.get_filing_document": {"bound"},
            "edgar.companyfacts": {"bound"},
            "edgar.get_xbrl_data": {"returned"},
            "edgar.get_filing_sections": {"returned"},
            "edgar.get_sixk_text": {"bound", "returned_empty"},
            "statement_source": {"bound"},
            "filing_excerpt": {"returned"},
            "edgar.attachments.download_file": {"bound", "sgml_embedded_alias"},
            "edgar.FilingHomepage.load": {"bound"},
        }
        if not any(row.get("path") == "archive.grounding" and row.get("outcome") == "complete"
                   for row in trace):
            raise IncompleteSlot("archive grounding completion event is missing")
        for path in {row.get("path") for row in trace if row.get("outcome") == "attempted"}:
            attempted = sum(row.get("path") == path and row.get("outcome") == "attempted"
                            for row in trace)
            completed = sum(row.get("path") == path and row.get("outcome") in terminal.get(path, set())
                            for row in trace)
            if path not in terminal or completed < attempted:
                raise IncompleteSlot(f"archive source trace has no terminal binding for {path}")
        for key, evidence_key in (("submissions", "company_submissions"),
                                  ("companyfacts", "companyfacts"),
                                  ("embedding", "embedding_contract")):
            record = expected_source_binding[key]
            observed = source_evidence.get(evidence_key)
            if (not isinstance(observed, dict) or
                    any(observed.get(field) != record.get(field) for field in ("sha256", "bytes")) or
                    not isinstance(observed.get("path"), str) or
                    tuple(Path(observed["path"]).parts[-len(Path(record["path"]).parts):]) !=
                    Path(record["path"]).parts):
                raise IncompleteSlot(f"{key} evidence differs from frozen supplemental source")
        seeded = grounding.get("seeded_company_metadata")
        submissions_record = expected_source_binding["submissions"]
        if expected_source_root is None:
            raise IncompleteSlot("frozen source root is unavailable")
        submissions_path = expected_source_root.joinpath(*Path(submissions_record["path"]).parts)
        submissions = _read_json(submissions_path)
        expected_sic = submissions.get("sic")
        expected_sic = str(expected_sic) if expected_sic is not None else None
        if (not isinstance(seeded, dict) or seeded.get("sic") != expected_sic or
                seeded.get("source_sha256") != submissions_record["sha256"]):
            raise IncompleteSlot("seeded company metadata differs from frozen submissions source")
    elif filing["filing_type"] == "6-K":
        _validate_sixk_source(filing, receipt, invocation, resolved["grounding"])
    _validate_events(resolved["events"])
    accounting = _read_json(resolved["provider_accounting"])
    records = accounting.get("records")
    ledger_ids = {identity for identity, status, _ in ledger_reservations if status == "settled"}
    if (accounting.get("slot_id") != slot_id or not isinstance(records, list) or not ledger_ids or
            len(ledger_ids) != len(ledger_reservations) or len(records) != len(ledger_ids) or
            {row.get("reservation_id") for row in records if isinstance(row, dict)} != ledger_ids or
            any(not isinstance(row, dict) or type(row.get("reservation_id")) is not int or
                row.get("status") != "settled" for row in records)):
        raise IncompleteSlot("provider accounting does not match settled slot reservations")
    ledger_requests = {identity: request_hash for identity, _, request_hash in ledger_reservations}
    for record in records:
        request_body = record.get("request")
        if not isinstance(request_body, dict):
            raise IncompleteSlot("provider request body missing from accounting")
        request_digest = hashlib.sha256(json.dumps(
            request_body, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")).hexdigest()
        if ledger_requests[record["reservation_id"]] != request_digest:
            raise IncompleteSlot("provider request differs from durable reservation")
    frames = _validate_preview_frames(resolved["raw_previews"], ledger_ids)
    completion_hashes = receipt.get("artifact_sha256")
    if (not isinstance(completion_hashes, dict) or set(completion_hashes) != set(resolved) or
            any(not _SHA256.fullmatch(str(completion_hashes[key])) or
                _sha256(path) != completion_hashes[key] for key, path in resolved.items())):
        raise IncompleteSlot("worker artifact differs from its completion seal")
    preview_files = _write_preview_files(invocation, frames, materialize=materialize_previews)
    output_paths = {
        "canonical": resolved["canonical_summary"],
        "rendered": resolved["rendered_summary"],
        "export": resolved["export_html"],
    }
    output_paths.update({f"preview_{index}": path for index, path in enumerate(preview_files)})
    relative = {key: _output_relative(path, output_parent) for key, path in output_paths.items()}
    evidence = {"selection": selection_path, "request": request_path,
                "receipt": receipt_path, "result": result_path, **resolved}
    return {
        "accession_number": filing["accession_number"], "arm": arm, "draw": draw,
        "status": "completed", "error": None, "created_at": receipt["started_at"],
        "config_sha256": config_sha,
        "canonical_path": relative["canonical"], "rendered_path": relative["rendered"],
        "export_path": relative["export"],
        "preview_paths": [relative[f"preview_{index}"] for index in range(len(preview_files))],
        "preview_count": len(preview_files), "previews_truncated": False,
        "retry_preview_attempts_omitted": 0,
        "artifact_sha256": {key: _sha256(path) for key, path in output_paths.items()},
        "raw_previews_path": _output_relative(resolved["raw_previews"], output_parent),
        "raw_previews_sha256": _sha256(resolved["raw_previews"]),
        "provider_accounting_path": _output_relative(resolved["provider_accounting"], output_parent),
        "provider_accounting_sha256": _sha256(resolved["provider_accounting"]),
        "receipt_path": _output_relative(receipt_path, output_parent),
        "result_path": _output_relative(result_path, output_parent),
        "slot_id": slot_id,
        "collector_evidence": {
            key: {"path": _output_relative(path, output_parent), "sha256": _sha256(path)}
            for key, path in evidence.items()
        },
    }


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    encoded = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    temp = path.with_name(path.name + f".tmp-{os.getpid()}")
    with temp.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(path)


def _incomplete_entry(programme_root: Path, output_parent: Path, slot_id: str,
                      ledger_status: str, error: str) -> dict[str, Any]:
    entry: dict[str, Any] = {"slot_id": slot_id, "ledger_status": ledger_status, "error": error}
    slot_dir = programme_root / slot_id
    if slot_dir.is_symlink() or not slot_dir.is_dir():
        return entry
    references: dict[str, str] = {}
    for key, relative in (("selection", "selection.json"), ("request", "request.json"),
                          ("worker_log", "worker.log"), ("receipt", "attempt-1/receipt.json"),
                          ("result", "attempt-1/result.json")):
        try:
            references[key] = _output_relative(_within(slot_dir, relative), output_parent)
        except (IncompleteSlot, OSError, ValueError):
            continue
    if references:
        entry["evidence_paths"] = references
    if "receipt" in references:
        try:
            receipt = _read_json(slot_dir / "attempt-1/receipt.json")
            entry["worker_status"] = receipt.get("status")
            entry["worker_errors"] = receipt.get("errors")
        except (OSError, ValueError, json.JSONDecodeError):
            entry["worker_errors"] = ["receipt unreadable"]
    return entry


def inspect_outputs(
    programme_root: Path, output_parent: Path, *,
    expected_manifest_sha: str = APPROVED_MANIFEST_SHA256,
    materialize_previews: bool = False,
) -> dict[str, Any]:
    """Reconstruct the index from durable evidence; read-only unless collecting previews."""
    programme_root, output_parent = Path(programme_root).resolve(strict=True), Path(output_parent).resolve(strict=True)
    if not programme_root.is_dir():
        raise ValueError("programme root is invalid")
    if not programme_root.is_relative_to(output_parent):
        raise ValueError("outputs.json parent must contain the programme artifacts")
    ledger = _within(programme_root, "budget.sqlite3")
    with sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True) as db:
        if "result_sha" not in {column[1] for column in db.execute("PRAGMA table_info(slots)")}:
            raise ValueError("programme lacks durable completion seals; do not reconstruct or reset evidence")
        slots = db.execute("SELECT id, config_sha, status, request_sha, result_sha FROM slots ORDER BY id").fetchall()
        reservations = db.execute("SELECT slot_id, id, status, request_hash FROM reservations ORDER BY id").fetchall()
        binding_row = db.execute("SELECT value FROM binding WHERE id = 1").fetchone()
    source_contract = None
    effective_by_holdout: dict[str, dict[str, Any]] = {}
    source_bindings: dict[str, dict[str, Any]] = {}
    source_inventory = None
    source_root = None
    if binding_row is not None:
        try:
            binding = json.loads(binding_row[0])
            source_inventory = binding["review_evidence"].get("source_contract")
            if source_inventory is not None:
                from evals.acceptance_source_contract import verify_source_contract_inventory

                source_contract = verify_source_contract_inventory(source_inventory)
                effective_by_holdout = {row["holdout_id"]: row
                                        for row in source_contract.effective_filings}
                source_bindings = source_contract.bindings_by_holdout
                source_root = Path(source_contract.inventory["source_root"])
        except (OSError, KeyError, TypeError, ValueError, AttributeError, json.JSONDecodeError) as error:
            raise ValueError("programme source contract binding is unavailable or changed") from error
    by_slot: dict[str, list[tuple[int, str, str]]] = {}
    for slot_id, identity, status, request_hash in reservations:
        by_slot.setdefault(slot_id, []).append((identity, status, request_hash))
    records: list[dict[str, Any]] = []
    incomplete: list[dict[str, Any]] = []
    smoke: list[dict[str, Any]] = []
    seen: set[str] = set()
    for slot_id, config_sha, status, request_sha, result_sha in slots:
        if slot_id in seen:
            incomplete.append(_incomplete_entry(programme_root, output_parent, slot_id,
                                                status, "duplicate slot claim"))
            continue
        seen.add(slot_id)
        if slot_id == "development-smoke":
            smoke.append({"slot_id": slot_id, "ledger_status": status,
                          "reservation_count": len(by_slot.get(slot_id, []))})
            continue
        if status != "completed":
            incomplete.append(_incomplete_entry(programme_root, output_parent, slot_id,
                                                status, "durable slot claim is not completed"))
            continue
        try:
            holdout_id = slot_id.split("-", 1)[0]
            records.append(_slot_record(programme_root, output_parent, slot_id, config_sha,
                                        request_sha, result_sha, by_slot.get(slot_id, []),
                                        expected_manifest_sha=expected_manifest_sha,
                                        expected_filing=effective_by_holdout.get(holdout_id),
                                        expected_source_binding=source_bindings.get(holdout_id),
                                        expected_source_root=source_root,
                                        materialize_previews=materialize_previews))
        except (IncompleteSlot, OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
            incomplete.append(_incomplete_entry(programme_root, output_parent, slot_id,
                                                status, f"{type(error).__name__}: {error}"))
    missing = sorted(_EXPECTED - seen)
    unexpected = sorted(seen - _EXPECTED - {"development-smoke"})
    orphan_reservations = sorted(set(by_slot) - seen)
    smoke_valid = (len(smoke) == 1 and smoke[0]["ledger_status"] == "completed"
                   and smoke[0]["reservation_count"] > 0)
    result = {
        "schema_version": 1, "records": records, "completed": len(records), "expected": len(_EXPECTED),
        "complete": (len(records) == len(_EXPECTED) and not incomplete and not unexpected
                     and not missing and not orphan_reservations and smoke_valid),
        "incomplete_slots": incomplete, "missing_slot_ids": missing,
        "unexpected_slot_ids": unexpected, "orphan_reservation_slot_ids": orphan_reservations,
        "development_smoke": smoke,
        "programme_ledger_path": _output_relative(ledger, output_parent),
    }
    if source_contract is not None:
        result["source_contract"] = source_inventory
    return result


def collect_outputs(programme_root: Path, output_path: Path) -> dict[str, Any]:
    """Materialize every raw preview, then atomically retain the durable-evidence index."""
    programme_root = Path(programme_root).resolve(strict=True)
    verify_review_evidence_binding(programme_root)
    output_path = Path(output_path).absolute()
    if output_path.is_symlink():
        raise ValueError("programme root/output path is invalid")
    output_path = output_path.parent.resolve(strict=True) / output_path.name
    if output_path.is_relative_to(programme_root):
        raise ValueError("collector output must be outside the programme directory")
    if output_path.exists():
        previous = _read_json(output_path)
        ledger_path = previous.get("programme_ledger_path")
        if (previous.get("schema_version") != 1 or previous.get("expected") != len(_EXPECTED) or
                not isinstance(previous.get("records"), list) or
                not isinstance(ledger_path, str) or
                _within(output_path.parent, ledger_path) != programme_root / "budget.sqlite3"):
            raise ValueError("existing output is not a collector index for this programme")
    result = inspect_outputs(programme_root, output_path.parent, materialize_previews=True)
    _atomic_json(output_path, result)
    return result
