"""Offline validation of the revised E7 source overlay contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evals import acceptance_source_contract as source_contract


def _write(path: Path, value: object) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return {"path": path.as_posix(), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _relative(root: Path, reference: dict[str, object]) -> dict[str, object]:
    return {**reference, "path": Path(str(reference["path"])).relative_to(root).as_posix()}


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    root = tmp_path / "source"
    root.mkdir()
    filings = []
    revised = []
    supplement_rows = []
    embedding_rows = []
    for number in range(1, 31):
        holdout = f"H{number:02d}"
        accession = f"0000000001-26-{number:06d}"
        cik = str(1000 + number)
        packets = []
        roles = ["primary", "index", "complete_submission"]
        if number <= 2:
            roles.append("earnings_exhibit")
        for role in roles:
            original_path = f"old/{holdout}/{role}.txt"
            original_sha = hashlib.sha256(original_path.encode()).hexdigest()
            url = f"https://www.sec.gov/{accession}/{role}"
            packets.append({"role": role, "path": original_path, "bytes": len(original_path),
                            "sha256": original_sha, "provenance": {"requested_url": url}})
            payload = f"{holdout}:{role}:revised".encode()
            path = root / "packets" / holdout / f"{role}.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            revised.append({
                "holdout_id": holdout, "accession_number": accession,
                "original_role": role, "original_path": original_path,
                "original_bytes": len(original_path), "original_sha256": original_sha,
                "new_role": role, "new_path": path.relative_to(root).as_posix(),
                "new_bytes": len(payload), "new_sha256": hashlib.sha256(payload).hexdigest(),
                "new_provenance": {"requested_url": url,
                                   "sha256": hashlib.sha256(payload).hexdigest()},
            })
        filings.append({
            "holdout_id": holdout, "accession_number": accession, "ticker": f"T{number}",
            "cik": cik, "filing_type": "10-K", "document_url": packets[0]["provenance"]["requested_url"],
            "source_sha256": packets[0]["sha256"], "source_packets": packets,
        })
        for kind in ("submissions", "companyfacts"):
            data = {"cik": cik, "facts": {}} if kind == "companyfacts" else {"cik": cik}
            reference = _relative(root, _write(root / "supplements" / holdout / f"{kind}.json", data))
            supplement_rows.append({"holdout_id": holdout, "accession_number": accession,
                                    "cik": cik, "kind": kind, "status": "captured",
                                    "source_record": reference,
                                    "provenance": {"sha256": reference["sha256"]}})
        complete = next(row for row in revised
                        if row["holdout_id"] == holdout and row["new_role"] == "complete_submission")
        primary = next(row for row in revised
                       if row["holdout_id"] == holdout and row["new_role"] == "primary")
        contract_ref = _relative(root, _write(root / "embedding-contracts" / f"{holdout}.json", {
            "schema_version": 1, "holdout_id": holdout, "accession_number": accession,
            "cik": cik, "filing_type": "10-K",
            "complete_submission_sha256": complete["new_sha256"],
            "attachments": {"primary": {"packet_sha256": primary["new_sha256"]}},
        }))
        embedding_rows.append({"holdout_id": holdout, "accession_number": accession,
                               "embedding_record": contract_ref})

    selection = tmp_path / "selection.json"
    _write(selection, {"filings": filings})
    selection_sha = hashlib.sha256(selection.read_bytes()).hexdigest()
    source_ref = _write(root / "source-manifest.json", {
        "schema_version": 1, "kind": "e7_revised_source_snapshot",
        "approved_selection_manifest_sha256": selection_sha, "complete": True,
        "source_count": 92, "captured_count": 92, "source_packets": revised,
    })
    source_sha = str(source_ref["sha256"])
    supplement_ref = _write(root / "supplements" / "supplement-manifest.json", {
        "schema_version": 1, "kind": "e7_public_sec_json_supplements_current_capture",
        "approved_selection_manifest_sha256": selection_sha,
        "revised_snapshot_manifest_sha256": source_sha, "complete": True,
        "planned_count": 60, "captured_count": 60, "unavailable_count": 0,
        "records": supplement_rows,
    })
    supplement_sha = str(supplement_ref["sha256"])
    embedding_ref = _write(root / "embedding-contracts" / "embedding-manifest.json", {
        "schema_version": 1, "kind": "e7_dual_representation_embedding_contracts",
        "selection_manifest_sha256": selection_sha, "source_manifest_sha256": source_sha,
        "supplement_manifest_sha256": supplement_sha, "filing_count": 30,
        "records": embedding_rows,
    })
    monkeypatch.setattr(source_contract, "APPROVED_SELECTION_SHA256", selection_sha)
    monkeypatch.setattr(source_contract, "REVISED_SOURCE_MANIFEST_SHA256", source_sha)
    monkeypatch.setattr(source_contract, "SUPPLEMENT_MANIFEST_SHA256", supplement_sha)
    monkeypatch.setattr(source_contract, "EMBEDDING_MANIFEST_SHA256", embedding_ref["sha256"])
    return selection, root


def test_resolves_direct_runtime_bindings_and_rejects_changed_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection, root = _fixture(tmp_path, monkeypatch)
    expected_sha = hashlib.sha256(selection.read_bytes()).hexdigest()
    contract = source_contract.resolve_source_contract(
        selection, root, expected_selection_sha=expected_sha,
    )
    assert (len(contract.effective_filings), len(contract.bindings_by_holdout)) == (30, 30)
    assert len(contract.inventory["source_packets"]) == 92
    assert len(contract.inventory["supplements"]) == 60
    assert set(contract.bindings_by_holdout["H01"]) == {
        "submissions", "companyfacts", "embedding", "contract",
    }
    assert set(contract.bindings_by_holdout["H01"]["submissions"]) == {"path", "bytes", "sha256"}
    assert {packet["role"] for packet in contract.filing("H01")["source_packets"]} == {
        "primary", "index", "complete_submission", "earnings_exhibit",
    }

    changed = root / contract.filing("H01")["source_packets"][0]["path"]
    original = changed.read_bytes()
    changed.write_bytes(bytes([original[0] ^ 1]) + original[1:])
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        source_contract.resolve_source_contract(selection, root, expected_selection_sha=expected_sha)
