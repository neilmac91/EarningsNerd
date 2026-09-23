"""Assign every complete-submission member one explicit, hash-bound disposition.

This is an internal, non-admitting engineering format built on the existing document map. It
proves only that the mapped member spans match the supplied submission bytes, that every member
received exactly one declared disposition, that exact duplicates are hash-proven, that encoded
members decode deterministically, and that members assigned to review units name a unit manifest
packet with the member's exact bytes. It never attests review, modality completeness, E7
coverage status or admission; unresolved members stay visible and hold completion.
"""

from __future__ import annotations

import binascii
import hashlib
import json
import re
from typing import Any


SCHEMA_VERSION = 1
LEDGER_KIND = "e7_offline_source_member_ledger"
VALIDATION_KIND = "e7_offline_source_member_validation"
DISPOSITIONS = ("assigned_to_review_units", "exact_duplicate", "declared_non_content_packaging", "unresolved")
REPRESENTATIONS = ("payload", "trimmed_payload", "content", "decoded")
# Any change to these strings, the flags, the dispositions or any key set requires a new schema_version.
LIMITATIONS = (
    "Member enumeration follows the existing document map's SGML parse; only the mapped byte spans are re-verified here.",
    "A member assigned to review units names a unit-manifest packet with its exact bytes; review of that packet is not attested.",
    "Declared non-content packaging and every label are unverified declarations; only exact duplicates are hash-proven.",
    "Tables, inline-XBRL facts (including hidden facts) and images inside members are not inventoried or dispositioned.",
    "No source review, E7 coverage_status or E7 admission is attested; unresolved members hold completion.",
)
ATTESTATION_FLAGS = (
    "semantic_review_attested",
    "semantic_labels_verified",
    "modality_completeness_attested",
    "admission_approved",
)

_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}")
_LABEL = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_MEMBER_ID_TAG = b"e7-source-member-id-v1\x00"
_UU_HEADER = re.compile(rb"begin [0-7]{3,4} [^\r\n]+")

_LEDGER_KEYS = frozenset({
    "schema_version", "kind", "accession_number", "submission", "members", "limitations", *ATTESTATION_FLAGS,
})
_SUBMISSION_KEYS = frozenset({"sha256", "byte_length", "member_count"})
_MEMBER_KEYS = frozenset({
    "member_id", "ordinal", "declared_type", "declared_filename", "declared_sequence",
    "payload", "trimmed_payload", "content", "encoding", "decoded", "disposition",
})
_SPAN_KEYS = frozenset({"start", "end", "sha256"})
_DECODED_KEYS = frozenset({"sha256", "byte_length"})
_DISPOSITION_KEYS = {
    "assigned_to_review_units": frozenset({"kind", "unit_manifest_sha256", "packet_role", "representation"}),
    "exact_duplicate": frozenset({"kind", "duplicate_of_ordinal"}),
    "declared_non_content_packaging": frozenset({"kind", "basis"}),
    "unresolved": frozenset({"kind", "reason"}),
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _same(value: Any, expected: Any) -> bool:
    try:
        return _canonical(value) == _canonical(expected)
    except (TypeError, ValueError, RecursionError):
        return False


def _sha(data: bytes | memoryview) -> str:
    return hashlib.sha256(data).hexdigest()


def _object(value: Any, keys: frozenset[str], name: str) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value) or set(value) != keys:
        raise ValueError(f"{name} must be an object with exactly: {', '.join(sorted(keys))}")
    return value


def _token(value: Any, pattern: re.Pattern[str], name: str) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ValueError(f"invalid {name}")
    return value


def _positive(value: Any, name: str) -> int:
    if type(value) is not int or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _declared_text(value: Any, name: str) -> str:
    # SGML header values are declarations; require exact, printable, bounded text without repair.
    if type(value) is not str or not value or len(value) > 256 or value != value.strip() or not value.isprintable():
        raise ValueError(f"invalid {name}")
    return value


def _span(raw: memoryview, start: Any, end: Any, name: str) -> dict[str, Any]:
    if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(raw):
        raise ValueError(f"invalid {name} span")
    return {"start": start, "end": end, "sha256": _sha(raw[start:end])}


def _uudecode(content: bytes) -> bytes | None:
    """Strictly decode one uuencoded member; return None when the content is not uuencoded."""
    if not content.startswith(b"begin "):
        return None
    lines = content.replace(b"\r\n", b"\n").split(b"\n")
    if _UU_HEADER.fullmatch(lines[0]) is None:
        raise ValueError("unsupported uuencode header")
    try:
        end = lines.index(b"end")
    except ValueError as exc:
        raise ValueError("uuencoded member has no end line") from exc
    if any(line for line in lines[end + 1:]):
        raise ValueError("bytes follow the uuencode end line")
    body = lines[1:end]
    if not body or body[-1] not in (b"`", b" "):
        raise ValueError("uuencoded member has no terminating zero-length line")
    decoded = bytearray()
    for line in body[:-1]:
        if not line or line[0] in (0x60, 0x20):
            raise ValueError("uuencoded member has an early terminating line")
        try:
            decoded.extend(binascii.a2b_uu(line))
        except binascii.Error as exc:
            raise ValueError("invalid uuencoded line") from exc
    return bytes(decoded)


def _member_record(accession: str, submission_sha256: str, raw: memoryview, document: Any) -> dict[str, Any]:
    """Re-derive one member's identity and spans from the submission bytes and its map entry."""
    if type(document) is not dict:
        raise ValueError("document map entry must be an object")
    ordinal = _positive(document.get("ordinal"), "member ordinal")
    declared_type = _declared_text(document.get("type"), "declared member type")
    declared_filename = _declared_text(document.get("filename"), "declared member filename")
    declared_sequence = _declared_text(document.get("sequence"), "declared member sequence")
    spans = {}
    for name in ("payload", "trimmed_payload", "content"):
        mapped = document.get(name)
        if type(mapped) is not dict:
            raise ValueError(f"document map {name} span missing")
        spans[name] = _span(raw, mapped.get("start"), mapped.get("end"), name)
        if mapped.get("sha256") != spans[name]["sha256"]:
            raise ValueError(f"member {ordinal} {name} bytes do not match the document map")
    content = raw[spans["content"]["start"]:spans["content"]["end"]].tobytes()
    decoded_bytes = _uudecode(content)
    decoded = None if decoded_bytes is None else {"sha256": _sha(decoded_bytes), "byte_length": len(decoded_bytes)}
    identity = {
        "accession_number": accession,
        "submission_sha256": submission_sha256,
        "ordinal": ordinal,
        "declared_type": declared_type,
        "declared_filename": declared_filename,
        "declared_sequence": declared_sequence,
        "payload": spans["payload"],
    }
    return {
        "member_id": _sha(_MEMBER_ID_TAG + _canonical(identity)),
        "ordinal": ordinal,
        "declared_type": declared_type,
        "declared_filename": declared_filename,
        "declared_sequence": declared_sequence,
        **spans,
        "encoding": "none" if decoded is None else "uuencode",
        "decoded": decoded,
    }


def _members(accession: str, submission: bytes, document_map: Any) -> list[dict[str, Any]]:
    if type(document_map) is not dict or type(document_map.get("documents")) is not list:
        raise ValueError("document map must contain a documents list")
    submission_sha256 = _sha(submission)
    if document_map.get("source_sha256") != submission_sha256 or document_map.get("source_bytes") != len(submission):
        raise ValueError("document map does not describe the supplied submission bytes")
    raw = memoryview(submission)
    members = [_member_record(accession, submission_sha256, raw, document) for document in document_map["documents"]]
    if not members or [member["ordinal"] for member in members] != list(range(1, len(members) + 1)):
        raise ValueError("document map members must be the contiguous ordinals 1..n")
    if len({member["declared_filename"] for member in members}) != len(members):
        raise ValueError("document map member filenames must be unique")
    return members


def _representation_sha(member: dict[str, Any], representation: str) -> str | None:
    if representation == "decoded":
        return None if member["decoded"] is None else member["decoded"]["sha256"]
    return member[representation]["sha256"]


def _check_dispositions(
    accession: str,
    members: list[dict[str, Any]],
    dispositions: list[dict[str, Any]],
    unit_manifests: Any,
) -> None:
    """Enforce one well-formed disposition per member and every hash-provable linkage."""
    if type(unit_manifests) is not list:
        raise ValueError("unit manifests must be a list")
    manifest_packets: dict[str, dict[str, str]] = {}
    for manifest in unit_manifests:
        if type(manifest) is not dict or manifest.get("accession_number") != accession:
            raise ValueError("unit manifests must be objects for the same accession")
        packets = manifest.get("declared_packets")
        if type(packets) is not list:
            raise ValueError("unit manifest has no declared_packets list")
        try:
            manifest_sha256 = _sha(_canonical(manifest))
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("unit manifest is not canonical JSON data") from exc
        manifest_packets[manifest_sha256] = {
            packet.get("role"): packet.get("sha256") for packet in packets if type(packet) is dict
        }
    by_ordinal = {member["ordinal"]: (member, disposition) for member, disposition in zip(members, dispositions)}
    claimed_packets: set[tuple[str, str]] = set()
    for member, disposition in zip(members, dispositions):
        kind = disposition["kind"]
        if kind == "assigned_to_review_units":
            _token(disposition["unit_manifest_sha256"], _SHA256, "unit_manifest_sha256")
            role = _token(disposition["packet_role"], _LABEL, "packet_role")
            representation = disposition["representation"]
            if representation not in REPRESENTATIONS:
                raise ValueError("invalid member representation")
            expected = _representation_sha(member, representation)
            packets = manifest_packets.get(disposition["unit_manifest_sha256"])
            if expected is None or packets is None or packets.get(role) != expected:
                raise ValueError(f"member {member['ordinal']} is not the named unit-manifest packet's exact bytes")
            if (disposition["unit_manifest_sha256"], role) in claimed_packets:
                raise ValueError("two members cannot claim the same unit-manifest packet")
            claimed_packets.add((disposition["unit_manifest_sha256"], role))
        elif kind == "exact_duplicate":
            target = disposition["duplicate_of_ordinal"]
            if type(target) is not int or target == member["ordinal"] or target not in by_ordinal:
                raise ValueError("exact_duplicate must name another member ordinal")
            original, original_disposition = by_ordinal[target]
            if (original["payload"]["sha256"] != member["payload"]["sha256"]
                    or original["payload"]["end"] - original["payload"]["start"]
                    != member["payload"]["end"] - member["payload"]["start"]):
                raise ValueError(f"member {member['ordinal']} is not a byte-identical duplicate")
            if original_disposition["kind"] != "assigned_to_review_units":
                raise ValueError("exact_duplicate must point at a member assigned to review units")
        elif kind == "declared_non_content_packaging":
            _token(disposition["basis"], _LABEL, "packaging basis")
        else:
            _token(disposition["reason"], _LABEL, "unresolved reason")


def _disposition(value: Any) -> dict[str, Any]:
    if type(value) is not dict or value.get("kind") not in DISPOSITIONS:
        raise ValueError(f"member disposition kind must be one of: {', '.join(DISPOSITIONS)}")
    return _object(value, _DISPOSITION_KEYS[value["kind"]], f"{value['kind']} disposition")


def validate_member_ledger(
    ledger: Any,
    *,
    accession_number: Any,
    submission: Any,
    document_map: Any,
    unit_manifests: Any,
) -> dict[str, Any]:
    """Recompute every member from the submission bytes and document map; never repair or reorder.

    The caller supplies the accession it expects, the complete submission bytes, the document map
    it trusts for that submission, and the unit manifests it has already validated with their own
    packet bytes (``acceptance_source_units.validate_unit_manifest``).
    """
    expected_accession = _token(accession_number, _ACCESSION, "expected accession_number")
    if type(submission) is not bytes or not submission:
        raise ValueError("submission must be non-empty immutable bytes")
    _object(ledger, _LEDGER_KEYS, "source member ledger")
    version, kind = ledger["schema_version"], ledger["kind"]
    if type(version) is not int or version != SCHEMA_VERSION or type(kind) is not str or kind != LEDGER_KIND:
        raise ValueError("unsupported source member ledger version or kind")
    if any(ledger[flag] is not False for flag in ATTESTATION_FLAGS):
        raise ValueError("a source member ledger cannot attest review, completeness or admission")
    limitations = ledger["limitations"]
    if type(limitations) is not list or any(type(item) is not str for item in limitations) or limitations != list(LIMITATIONS):
        raise ValueError("source member ledger limitations differ from this format")
    accession = _token(ledger["accession_number"], _ACCESSION, "accession_number")
    if accession != expected_accession:
        raise ValueError("source member ledger declares a different accession")
    members = _members(accession, submission, document_map)
    expected_submission = {"sha256": _sha(submission), "byte_length": len(submission), "member_count": len(members)}
    if not _same(_object(ledger["submission"], _SUBMISSION_KEYS, "submission"), expected_submission):
        raise ValueError("ledger submission identity does not match the supplied bytes and document map")
    recorded = ledger["members"]
    if type(recorded) is not list or len(recorded) != len(members):
        raise ValueError("ledger must record exactly one entry per mapped member, in ordinal order")
    dispositions = []
    for member, entry in zip(members, recorded):
        _object(entry, _MEMBER_KEYS, "ledger member")
        disposition = _disposition(entry["disposition"])
        for field in _MEMBER_KEYS - {"disposition"}:
            if not _same(entry[field], member[field]):
                raise ValueError(f"member {member['ordinal']} {field} does not match the submission bytes")
        dispositions.append(disposition)
    _check_dispositions(accession, members, dispositions, unit_manifests)
    counts = {kind: sum(1 for disposition in dispositions if disposition["kind"] == kind) for kind in DISPOSITIONS}
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": VALIDATION_KIND,
        "ledger_sha256": _sha(_canonical(ledger)),
        "accession_number": accession,
        "submission_sha256": expected_submission["sha256"],
        "member_count": len(members),
        "disposition_counts": counts,
        "encoded_member_count": sum(1 for member in members if member["encoding"] != "none"),
        "unresolved_member_ids": [entry["member_id"] for entry, disposition in zip(recorded, dispositions)
                                  if disposition["kind"] == "unresolved"],
        "every_member_dispositioned": True,
        **{flag: False for flag in ATTESTATION_FLAGS},
        "limitations": list(LIMITATIONS),
    }


def build_member_ledger(
    *,
    accession_number: Any,
    submission: Any,
    document_map: Any,
    dispositions: Any,
    unit_manifests: Any,
) -> dict[str, Any]:
    """Build the ledger in member ordinal order from one disposition per member, then validate it."""
    accession = _token(accession_number, _ACCESSION, "accession_number")
    if type(submission) is not bytes or not submission:
        raise ValueError("submission must be non-empty immutable bytes")
    members = _members(accession, submission, document_map)
    if type(dispositions) is not list or len(dispositions) != len(members):
        raise ValueError("supply exactly one disposition per mapped member, in ordinal order")
    entries = [{**member, "disposition": dict(_disposition(disposition))}
               for member, disposition in zip(members, dispositions)]
    ledger = {
        "schema_version": SCHEMA_VERSION,
        "kind": LEDGER_KIND,
        "accession_number": accession,
        "submission": {"sha256": _sha(submission), "byte_length": len(submission), "member_count": len(members)},
        "members": entries,
        **{flag: False for flag in ATTESTATION_FLAGS},
        "limitations": list(LIMITATIONS),
    }
    validate_member_ledger(ledger, accession_number=accession, submission=submission,
                           document_map=document_map, unit_manifests=unit_manifests)
    return ledger
