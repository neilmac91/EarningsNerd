"""Resolve the fixed revised E7 source snapshot over the immutable selection manifest.

The approved 30 filing identities remain bound to their historical manifest bytes.  This
module validates a separate, fixed source snapshot and returns effective source packets plus
the supplemental structured inputs needed by the runtime archive adapter.  It performs no
network I/O and never treats a manifest assertion as proof without hashing the referenced file.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


APPROVED_SELECTION_SHA256 = "68242a2c1c57da8d445bc4e1aca104017cffaffe8bbebf131228cde8ea94ba66"
REVISED_SOURCE_MANIFEST_SHA256 = "f65b783c0d73f98eb49f4d91acc79fbada546be7133decb3f2094679b2aaa708"
SUPPLEMENT_MANIFEST_SHA256 = "f6365709fa83983538a55f7ad4745cf79ccdd955ac9c91bdde2d2118ac21f12a"
EMBEDDING_MANIFEST_SHA256 = "043a595866d51c74e807d533c2f980e1dcbcf0033af19d20ed4cd6c9485b5639"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_HOLDOUTS = {f"H{i:02d}" for i in range(1, 31)}


@dataclass(frozen=True)
class SourceContract:
    effective_filings: tuple[dict[str, Any], ...]
    bindings_by_holdout: dict[str, dict[str, Any]]
    inventory: dict[str, Any]

    def filing(self, holdout_id: str) -> dict[str, Any]:
        matches = [row for row in self.effective_filings if row["holdout_id"] == holdout_id]
        if len(matches) != 1:
            raise ValueError(f"unknown effective holdout: {holdout_id}")
        return matches[0]


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: expected JSON object")
    return value


def _file(root: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError("source contract path missing")
    part = PurePosixPath(relative)
    if part.is_absolute() or any(piece in {"", ".", ".."} for piece in part.parts):
        raise ValueError("unsafe source contract path")
    root = root.resolve(strict=True)
    path = root.joinpath(*part.parts)
    cursor = root
    for piece in part.parts:
        cursor /= piece
        if cursor.is_symlink():
            raise ValueError("symlink in source contract path")
    if not path.is_file() or not path.resolve(strict=True).is_relative_to(root):
        raise ValueError("source contract file missing or outside root")
    return path


def _ref(root: Path, relative: str, expected_sha: str | None = None,
         expected_bytes: int | None = None) -> dict[str, Any]:
    path = _file(root, relative)
    digest = _sha(path)
    if expected_sha is not None and digest != expected_sha:
        raise ValueError(f"source contract SHA256 mismatch: {relative}")
    if expected_bytes is not None and path.stat().st_size != expected_bytes:
        raise ValueError(f"source contract byte count mismatch: {relative}")
    return {"path": relative, "sha256": digest, "bytes": path.stat().st_size}


def _identity(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("holdout_id")), str(row.get("accession_number"))


def resolve_source_contract(
    selection_manifest_path: Path,
    source_root: Path,
    *,
    expected_selection_sha: str = APPROVED_SELECTION_SHA256,
) -> SourceContract:
    """Validate and resolve the one approved revised-source overlay, offline and fail closed."""
    selection_path = Path(selection_manifest_path).resolve(strict=True)
    unresolved_root = Path(source_root)
    if unresolved_root.is_symlink():
        raise ValueError("source contract root must be a real directory")
    root = unresolved_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("source contract root must be a real directory")
    if _sha(selection_path) != expected_selection_sha or expected_selection_sha != APPROVED_SELECTION_SHA256:
        raise ValueError("approved selection manifest bytes changed")
    selection = _object(selection_path)
    selected = selection.get("filings")
    if (not isinstance(selected, list) or len(selected) != 30 or
            {_identity(row)[0] for row in selected if isinstance(row, dict)} != _HOLDOUTS or
            len({_identity(row)[1] for row in selected if isinstance(row, dict)}) != 30):
        raise ValueError("approved selection identities incomplete")
    selected_by_holdout = {row["holdout_id"]: row for row in selected}

    manifests = {
        "source_manifest": ("source-manifest.json", REVISED_SOURCE_MANIFEST_SHA256),
        "supplement_manifest": ("supplements/supplement-manifest.json", SUPPLEMENT_MANIFEST_SHA256),
        "embedding_manifest": ("embedding-contracts/embedding-manifest.json", EMBEDDING_MANIFEST_SHA256),
    }
    manifest_refs = {name: _ref(root, relative, digest)
                     for name, (relative, digest) in manifests.items()}
    source = _object(_file(root, manifests["source_manifest"][0]))
    supplements = _object(_file(root, manifests["supplement_manifest"][0]))
    embeddings = _object(_file(root, manifests["embedding_manifest"][0]))
    if (source.get("schema_version") != 1 or source.get("kind") != "e7_revised_source_snapshot" or
            source.get("approved_selection_manifest_sha256") != APPROVED_SELECTION_SHA256 or
            source.get("complete") is not True or source.get("source_count") != 92 or
            source.get("captured_count") != 92 or not isinstance(source.get("source_packets"), list) or
            len(source["source_packets"]) != 92):
        raise ValueError("revised source manifest incomplete or incompatible")
    if (supplements.get("schema_version") != 1 or
            supplements.get("kind") != "e7_public_sec_json_supplements_current_capture" or
            supplements.get("approved_selection_manifest_sha256") != APPROVED_SELECTION_SHA256 or
            supplements.get("revised_snapshot_manifest_sha256") != REVISED_SOURCE_MANIFEST_SHA256 or
            supplements.get("complete") is not True or supplements.get("planned_count") != 60 or
            supplements.get("captured_count") != 60 or supplements.get("unavailable_count") != 0 or
            not isinstance(supplements.get("records"), list) or len(supplements["records"]) != 60):
        raise ValueError("supplement manifest incomplete or incompatible")
    if (embeddings.get("schema_version") != 1 or
            embeddings.get("kind") != "e7_dual_representation_embedding_contracts" or
            embeddings.get("selection_manifest_sha256") != APPROVED_SELECTION_SHA256 or
            embeddings.get("source_manifest_sha256") != REVISED_SOURCE_MANIFEST_SHA256 or
            embeddings.get("supplement_manifest_sha256") != SUPPLEMENT_MANIFEST_SHA256 or
            embeddings.get("filing_count") != 30 or not isinstance(embeddings.get("records"), list) or
            len(embeddings["records"]) != 30):
        raise ValueError("embedding manifest incomplete or incompatible")

    packets_by_holdout: dict[str, list[dict[str, Any]]] = {key: [] for key in _HOLDOUTS}
    packet_refs: list[dict[str, Any]] = []
    for record in source["source_packets"]:
        if not isinstance(record, dict):
            raise ValueError("revised source packet record invalid")
        holdout, accession = _identity(record)
        selected_row = selected_by_holdout.get(holdout)
        original = next((packet for packet in (selected_row or {}).get("source_packets", [])
                         if packet.get("role") == record.get("original_role")), None)
        provenance = record.get("new_provenance")
        if (selected_row is None or accession != selected_row.get("accession_number") or original is None or
                record.get("original_path") != original.get("path") or
                record.get("original_sha256") != original.get("sha256") or
                record.get("original_bytes") != original.get("bytes") or
                record.get("new_role") != record.get("original_role") or
                not isinstance(provenance, dict) or
                provenance.get("sha256") != record.get("new_sha256") or
                provenance.get("requested_url") != (original.get("provenance") or {}).get("requested_url")):
            raise ValueError(f"revised source identity differs: {holdout}")
        reference = _ref(root, record["new_path"], record["new_sha256"], record["new_bytes"])
        packet = {"role": record["new_role"], **reference, "provenance": provenance}
        if any(existing["role"] == packet["role"] for existing in packets_by_holdout[holdout]):
            raise ValueError(f"duplicate revised source role: {holdout}:{packet['role']}")
        packets_by_holdout[holdout].append(packet)
        packet_refs.append({"holdout_id": holdout, "accession_number": accession, **reference})

    supplements_by_holdout: dict[str, dict[str, dict[str, Any]]] = {key: {} for key in _HOLDOUTS}
    supplement_refs: list[dict[str, Any]] = []
    for record in supplements["records"]:
        if not isinstance(record, dict):
            raise ValueError("supplement record invalid")
        holdout, accession = _identity(record)
        selected_row = selected_by_holdout.get(holdout)
        kind, source_record = record.get("kind"), record.get("source_record")
        if (selected_row is None or accession != selected_row.get("accession_number") or
                str(record.get("cik")) != str(selected_row.get("cik")) or
                kind not in {"submissions", "companyfacts"} or record.get("status") != "captured" or
                kind in supplements_by_holdout[holdout] or not isinstance(source_record, dict)):
            raise ValueError(f"supplement identity differs: {holdout}")
        reference = _ref(root, source_record["path"], source_record["sha256"], source_record["bytes"])
        if record.get("provenance", {}).get("sha256") != reference["sha256"]:
            raise ValueError(f"supplement provenance differs: {holdout}:{kind}")
        supplements_by_holdout[holdout][kind] = record
        supplement_refs.append({"holdout_id": holdout, "accession_number": accession,
                                "kind": kind, **reference})

    embeddings_by_holdout: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    embedding_refs: list[dict[str, Any]] = []
    for record in embeddings["records"]:
        if not isinstance(record, dict):
            raise ValueError("embedding record invalid")
        holdout, accession = _identity(record)
        selected_row = selected_by_holdout.get(holdout)
        embedding_record = record.get("embedding_record")
        if (selected_row is None or accession != selected_row.get("accession_number") or
                holdout in embeddings_by_holdout or not isinstance(embedding_record, dict)):
            raise ValueError(f"embedding identity differs: {holdout}")
        reference = _ref(root, embedding_record["path"], embedding_record["sha256"],
                         embedding_record["bytes"])
        contract = _object(_file(root, reference["path"]))
        revised_packets = {packet["role"]: packet for packet in packets_by_holdout[holdout]}
        if (contract.get("schema_version") != 1 or contract.get("holdout_id") != holdout or
                contract.get("accession_number") != accession or
                str(contract.get("cik")) != str(selected_row.get("cik")) or
                contract.get("filing_type") != selected_row.get("filing_type") or
                contract.get("complete_submission_sha256") !=
                revised_packets.get("complete_submission", {}).get("sha256") or
                not isinstance(contract.get("attachments"), dict) or
                any(role not in revised_packets or item.get("packet_sha256") != revised_packets[role]["sha256"]
                    for role, item in contract["attachments"].items())):
            raise ValueError(f"embedding contract differs: {holdout}")
        embeddings_by_holdout[holdout] = (record, contract)
        embedding_refs.append({"holdout_id": holdout, "accession_number": accession, **reference})

    if (set(embeddings_by_holdout) != _HOLDOUTS or
            any(set(supplements_by_holdout[key]) != {"submissions", "companyfacts"} for key in _HOLDOUTS) or
            any({p["role"] for p in packets_by_holdout[key]} !=
                {p.get("role") for p in selected_by_holdout[key].get("source_packets", [])}
                for key in _HOLDOUTS)):
        raise ValueError("source contract does not cover all selected filings")

    effective: list[dict[str, Any]] = []
    bindings: dict[str, dict[str, Any]] = {}
    for selected_row in selected:
        holdout = selected_row["holdout_id"]
        packets = sorted(packets_by_holdout[holdout], key=lambda item: item["role"])
        filing = {**selected_row, "source_packets": packets,
                  "source_sha256": next(item["sha256"] for item in packets if item["role"] == "primary")}
        effective.append(filing)
        embedding_record, _contract = embeddings_by_holdout[holdout]
        bindings[holdout] = {
            "submissions": dict(supplements_by_holdout[holdout]["submissions"]["source_record"]),
            "companyfacts": dict(supplements_by_holdout[holdout]["companyfacts"]["source_record"]),
            "embedding": dict(embedding_record["embedding_record"]),
            "contract": {
                "schema_version": 1,
                "kind": "e7_revised_source_binding",
                "holdout_id": holdout,
                "accession_number": selected_row["accession_number"],
                "selection_manifest_sha256": APPROVED_SELECTION_SHA256,
                "source_manifest_sha256": REVISED_SOURCE_MANIFEST_SHA256,
                "supplement_manifest_sha256": SUPPLEMENT_MANIFEST_SHA256,
                "embedding_manifest_sha256": EMBEDDING_MANIFEST_SHA256,
            },
        }

    inventory = {
        "schema_version": 1,
        "kind": "e7_revised_source_contract",
        "selection_manifest": {"resolved_path": str(selection_path), "sha256": _sha(selection_path)},
        "source_root": str(root),
        "manifests": manifest_refs,
        "source_packets": sorted(packet_refs, key=lambda row: (row["holdout_id"], row["path"])),
        "supplements": sorted(supplement_refs, key=lambda row: (row["holdout_id"], row["kind"])),
        "embedding_contracts": sorted(embedding_refs, key=lambda row: row["holdout_id"]),
    }
    return SourceContract(tuple(effective), bindings, inventory)


def verify_source_contract_inventory(inventory: dict[str, Any]) -> SourceContract:
    """Re-resolve a previously frozen inventory and require exact equality."""
    if not isinstance(inventory, dict):
        raise ValueError("source contract inventory missing")
    selection = inventory.get("selection_manifest", {})
    contract = resolve_source_contract(Path(selection.get("resolved_path", "")),
                                       Path(inventory.get("source_root", "")))
    if contract.inventory != inventory:
        raise ValueError("source contract differs from frozen inventory")
    return contract
