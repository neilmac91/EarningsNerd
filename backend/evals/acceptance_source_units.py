"""Build and validate byte-custody review units over explicitly declared source packets.

This is an internal, non-admitting engineering format. A valid manifest proves only that the
supplied bytes match each declared packet identity and that coverage spans partition every
declared packet exactly. Declared accessions, roles and unit labels are not verified facts, and
no review, source/member/modality completeness, E7 coverage status or admission is attested.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from typing import Any


SCHEMA_VERSION = 1
MANIFEST_KIND = "e7_offline_source_unit_manifest"
VALIDATION_KIND = "e7_offline_source_unit_validation"
# Any change to these strings, the flags or any key set requires a new schema_version.
LIMITATIONS = (
    "Byte custody only: the declared accession, packet roles, structural kinds and registrant scopes are unverified declarations.",
    "The declared packets are not every source in the filing; other exhibits, submission members, supplements and graphics remain separate obligations.",
    "A byte-valid span boundary is not a semantically safe text, table, footnote or UTF-8 character split.",
    "Tables, hidden inline-XBRL facts, images, encoded archives and decoded members are neither inventoried nor dispositioned.",
    "No source review, model-context custody, issue propagation, E7 coverage_status or E7 admission is attested.",
)
ATTESTATION_FLAGS = (
    "semantic_review_attested",
    "semantic_labels_verified",
    "source_set_completeness_attested",
    "member_modality_completeness_attested",
    "admission_approved",
)

_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}")
_LABEL = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_PACKET_ID_TAG = b"e7-source-unit-packet-id-v1\x00"
_UNIT_PAYLOAD_TAG = b"e7-source-unit-coverage-v1\x00"
_UNIT_ID_TAG = b"e7-source-unit-id-v1\x00"

_MANIFEST_KEYS = frozenset({
    "schema_version", "kind", "accession_number", "declared_packets", "units", "limitations",
    *ATTESTATION_FLAGS,
})
_PACKET_INPUT_KEYS = frozenset({"role", "sha256", "byte_length"})
_PACKET_KEYS = _PACKET_INPUT_KEYS | {"packet_id"}
_UNIT_LABEL_KEYS = frozenset({"structural_kind", "registrant_scope", "coverage_spans", "context_spans"})
_UNIT_INPUT_KEYS = _UNIT_LABEL_KEYS | {"packet_role"}
_UNIT_KEYS = _UNIT_LABEL_KEYS | {"unit_id", "packet_id", "unit_sha256"}
_SPAN_INPUT_KEYS = frozenset({"start", "end"})
_SPAN_KEYS = _SPAN_INPUT_KEYS | {"sha256"}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _sha(*parts: bytes | memoryview) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part)
    return digest.hexdigest()


def _object(value: Any, keys: frozenset[str], name: str) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value) or set(value) != keys:
        raise ValueError(f"{name} must be an object with exactly: {', '.join(sorted(keys))}")
    return value


def _token(value: Any, pattern: re.Pattern[str], name: str) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ValueError(f"invalid {name}")
    return value


def _packet_record(accession: str, role: Any, sha256: Any, byte_length: Any) -> dict[str, Any]:
    """Validate one declared packet identity and derive its packet ID."""
    _token(role, _LABEL, "packet role")
    _token(sha256, _SHA256, "packet sha256")
    if type(byte_length) is not int or byte_length < 1:
        raise ValueError("packet byte_length must be a positive integer; empty packets are not reviewable units")
    identity = {"accession_number": accession, "role": role, "sha256": sha256, "byte_length": byte_length}
    return {"packet_id": _sha(_PACKET_ID_TAG, _canonical(identity)), "role": role, "sha256": sha256,
            "byte_length": byte_length}


def _declared_packets(accession: str, value: Any, keys: frozenset[str]) -> list[dict[str, Any]]:
    """Validate unique, role-ordered packet declarations; a supplied packet_id must recompute."""
    if type(value) is not list or not value:
        raise ValueError("declared_packets must be a non-empty list")
    packets: list[dict[str, Any]] = []
    for packet in value:
        _object(packet, keys, "declared packet")
        record = _packet_record(accession, packet["role"], packet["sha256"], packet["byte_length"])
        if "packet_id" in keys and _token(packet["packet_id"], _SHA256, "packet_id") != record["packet_id"]:
            raise ValueError(f"packet_id does not match declared packet {record['role']}")
        if packets and record["role"] <= packets[-1]["role"]:
            raise ValueError("declared_packets must be unique and in ascending role order")
        packets.append(record)
    return packets


def _packet_bytes(packets: list[dict[str, Any]], supplied: Any) -> dict[str, bytes]:
    """Require exactly one immutable buffer per declared packet, matching its length and SHA-256."""
    if (type(supplied) is not dict or any(type(role) is not str for role in supplied)
            or set(supplied) != {packet["role"] for packet in packets}):
        raise ValueError("packet bytes must be supplied for exactly the declared packet roles")
    for packet in packets:
        data = supplied[packet["role"]]
        if type(data) is not bytes:
            raise ValueError("packet bytes must be immutable bytes")
        if len(data) != packet["byte_length"] or _sha(data) != packet["sha256"]:
            raise ValueError(f"packet {packet['role']} bytes do not match the declared length and SHA-256")
    return supplied


def _spans(value: Any, keys: frozenset[str], byte_length: int, name: str, gap: int) -> list[tuple[int, int]]:
    """Parse ordered half-open byte spans without converting, sorting or merging them.

    ``gap`` is the minimum distance between consecutive spans: 1 keeps coverage canonical (adjacent
    coverage is one span), 0 lets separately hashed context items such as a caption and header touch.
    """
    if type(value) is not list:
        raise ValueError(f"{name} must be a list")
    bounds: list[tuple[int, int]] = []
    for span in value:
        _object(span, keys, f"{name} entry")
        start, end = span["start"], span["end"]
        if type(start) is not int or type(end) is not int:
            raise ValueError(f"{name} offsets must be integers")
        if not 0 <= start < end <= byte_length:
            raise ValueError(f"{name} must satisfy 0 <= start < end <= packet byte_length")
        if bounds and start < bounds[-1][1] + gap:
            raise ValueError(f"{name} must be ascending and non-overlapping"
                             + (" with at least one byte between spans" if gap else ""))
        if "sha256" in keys:
            _token(span["sha256"], _SHA256, f"{name} sha256")
        bounds.append((start, end))
    return bounds


def _unit_bounds(unit: dict[str, Any], keys: frozenset[str], byte_length: int) -> tuple[list[tuple[int, int]], ...]:
    coverage = _spans(unit["coverage_spans"], keys, byte_length, "coverage_spans", gap=1)
    context = _spans(unit["context_spans"], keys, byte_length, "context_spans", gap=0)
    if not coverage:
        raise ValueError("a unit must cover at least one byte")
    context_index = coverage_index = 0
    while context_index < len(context) and coverage_index < len(coverage):
        (context_start, context_end), (start, end) = context[context_index], coverage[coverage_index]
        if context_end <= start:
            context_index += 1
        elif end <= context_start:
            coverage_index += 1
        else:
            raise ValueError("context_spans must not overlap the unit's own coverage_spans")
    return coverage, context


def _unit_payload_sha256(fragments: list[memoryview]) -> str:
    """Hash ordered coverage fragments with a count and per-fragment length frame."""
    digest = hashlib.sha256(_UNIT_PAYLOAD_TAG)
    digest.update(struct.pack(">Q", len(fragments)))
    for fragment in fragments:
        digest.update(struct.pack(">Q", fragment.nbytes))
        digest.update(fragment)
    return digest.hexdigest()


def _unit_record(
    accession: str,
    packet: dict[str, Any],
    data: bytes,
    unit: dict[str, Any],
    coverage: list[tuple[int, int]],
    context: list[tuple[int, int]],
) -> dict[str, Any]:
    """Derive one complete unit record from packet bytes and its declared labels and spans."""
    view = memoryview(data)
    structural_kind = _token(unit["structural_kind"], _LABEL, "structural_kind")
    registrant_scope = _token(unit["registrant_scope"], _LABEL, "registrant_scope")
    coverage_spans = [{"start": start, "end": end, "sha256": _sha(view[start:end])} for start, end in coverage]
    context_spans = [{"start": start, "end": end, "sha256": _sha(view[start:end])} for start, end in context]
    unit_sha256 = _unit_payload_sha256([view[start:end] for start, end in coverage])
    record = {
        "packet_id": packet["packet_id"],
        "structural_kind": structural_kind,
        "registrant_scope": registrant_scope,
        "coverage_spans": coverage_spans,
        "context_spans": context_spans,
        "unit_sha256": unit_sha256,
    }
    unit_id = _sha(_UNIT_ID_TAG, _canonical({"accession_number": accession, **record}))
    return {"unit_id": unit_id, **record}


def _require_exact_partition(role: str, byte_length: int, bounds: list[tuple[int, int]]) -> None:
    """Walk the union of one packet's coverage spans; equal total length is not sufficient."""
    if not bounds:
        raise ValueError(f"declared packet {role} has no coverage units")
    cursor = 0
    for start, end in sorted(bounds):
        if start < cursor:
            raise ValueError(f"coverage spans overlap in packet {role} at byte {start}")
        if start > cursor:
            raise ValueError(f"coverage gap in packet {role} at byte {cursor}")
        cursor = end
    if cursor != byte_length:
        raise ValueError(f"coverage gap in packet {role} at byte {cursor}")


def validate_unit_manifest(manifest: Any, *, accession_number: Any, packet_bytes: Any) -> dict[str, Any]:
    """Recompute every identity from the supplied bytes and require an exact declared-packet partition.

    The caller states the accession it expects, so a consistent manifest declared for another
    accession over identical bytes is rejected. Nothing is repaired, coerced or reordered; any
    difference raises ``ValueError``.
    """
    expected_accession = _token(accession_number, _ACCESSION, "expected accession_number")
    _object(manifest, _MANIFEST_KEYS, "source unit manifest")
    version, kind = manifest["schema_version"], manifest["kind"]
    if type(version) is not int or version != SCHEMA_VERSION or type(kind) is not str or kind != MANIFEST_KIND:
        raise ValueError("unsupported source unit manifest version or kind")
    if any(manifest[flag] is not False for flag in ATTESTATION_FLAGS):
        raise ValueError("a source unit manifest cannot attest review, completeness or admission")
    limitations = manifest["limitations"]
    if (type(limitations) is not list or any(type(item) is not str for item in limitations)
            or limitations != list(LIMITATIONS)):
        raise ValueError("source unit manifest limitations differ from this format")
    accession = _token(manifest["accession_number"], _ACCESSION, "accession_number")
    if accession != expected_accession:
        raise ValueError("source unit manifest declares a different accession")

    packets = _declared_packets(accession, manifest["declared_packets"], _PACKET_KEYS)
    data_by_role = _packet_bytes(packets, packet_bytes)
    packet_index = {packet["packet_id"]: index for index, packet in enumerate(packets)}

    units = manifest["units"]
    if type(units) is not list:
        raise ValueError("units must be a list")
    coverage_by_packet: dict[str, list[tuple[int, int]]] = {packet["packet_id"]: [] for packet in packets}
    order: list[tuple[int, int]] = []
    unit_ids: set[str] = set()
    context_span_count = context_bytes = 0
    for unit in units:
        _object(unit, _UNIT_KEYS, "unit")
        for field in ("unit_id", "packet_id", "unit_sha256"):
            _token(unit[field], _SHA256, f"unit {field}")
        if unit["packet_id"] not in packet_index:
            raise ValueError("unit references an undeclared packet")
        packet = packets[packet_index[unit["packet_id"]]]
        coverage, context = _unit_bounds(unit, _SPAN_KEYS, packet["byte_length"])
        expected = _unit_record(accession, packet, data_by_role[packet["role"]], unit, coverage, context)
        for field in ("coverage_spans", "context_spans", "unit_sha256", "unit_id"):
            if _canonical(unit[field]) != _canonical(expected[field]):
                raise ValueError(f"unit {field} does not match the declared packet bytes and labels")
        if unit["unit_id"] in unit_ids:
            raise ValueError("duplicate unit_id")
        unit_ids.add(unit["unit_id"])
        coverage_by_packet[packet["packet_id"]].extend(coverage)
        order.append((packet_index[packet["packet_id"]], coverage[0][0]))
        context_span_count += len(context)
        context_bytes += sum(end - start for start, end in context)

    for packet in packets:
        _require_exact_partition(packet["role"], packet["byte_length"], coverage_by_packet[packet["packet_id"]])
    if order != sorted(order):
        raise ValueError("units must be ordered by declared packet, then by first coverage start")

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": VALIDATION_KIND,
        "manifest_sha256": _sha(_canonical(manifest)),
        "accession_number": accession,
        "packet_count": len(packets),
        "unit_count": len(units),
        "declared_packet_bytes": sum(packet["byte_length"] for packet in packets),
        "coverage_bytes": sum(end - start for bounds in coverage_by_packet.values() for start, end in bounds),
        "context_span_count": context_span_count,
        "context_span_bytes_not_counted_as_coverage": context_bytes,
        "declared_packet_byte_partition": "exact",
        **{flag: False for flag in ATTESTATION_FLAGS},
        "limitations": list(LIMITATIONS),
    }


def load_unit_manifest(raw: Any) -> dict[str, Any]:
    """Parse stored manifest bytes, requiring exactly ``canonical_json(manifest)``.

    The round trip rejects duplicate JSON keys and indentation, key-order, exponent or ``-0``
    spellings, so the stored bytes, their file hash and ``manifest_sha256`` stay one identity.
    A decimal such as ``6.0`` survives the round trip and is left to the validator's exact-int rule.
    Call ``validate_unit_manifest`` on the result; loading proves nothing about the source bytes.
    """
    if type(raw) is not bytes:
        raise ValueError("stored source unit manifest must be bytes")
    try:
        manifest = json.loads(raw.decode("ascii"))
        canonical = _canonical(manifest)
    except (UnicodeDecodeError, ValueError, TypeError, RecursionError) as exc:
        raise ValueError("stored source unit manifest is not canonical JSON") from exc
    if canonical != raw or type(manifest) is not dict:
        raise ValueError("stored source unit manifest is not canonical JSON")
    return manifest


def build_unit_manifest(
    *,
    accession_number: Any,
    packets: Any,
    packet_bytes: Any,
    units: Any,
) -> dict[str, Any]:
    """Construct a manifest in declared order, then validate it exactly as a consumer must."""
    accession = _token(accession_number, _ACCESSION, "accession_number")
    declared = _declared_packets(accession, packets, _PACKET_INPUT_KEYS)
    by_role = {packet["role"]: packet for packet in declared}
    data_by_role = _packet_bytes(declared, packet_bytes)
    if type(units) is not list:
        raise ValueError("units must be a list")
    records = []
    for unit in units:
        _object(unit, _UNIT_INPUT_KEYS, "declared unit")
        packet = by_role.get(unit["packet_role"]) if type(unit["packet_role"]) is str else None
        if packet is None:
            raise ValueError("unit references an undeclared packet")
        coverage, context = _unit_bounds(unit, _SPAN_INPUT_KEYS, packet["byte_length"])
        records.append(_unit_record(accession, packet, data_by_role[packet["role"]], unit, coverage, context))
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": MANIFEST_KIND,
        "accession_number": accession,
        "declared_packets": declared,
        "units": records,
        **{flag: False for flag in ATTESTATION_FLAGS},
        "limitations": list(LIMITATIONS),
    }
    validate_unit_manifest(manifest, accession_number=accession, packet_bytes=packet_bytes)
    return manifest
