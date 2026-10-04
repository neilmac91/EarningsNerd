"""H20-only exact whole-packet mapping and joint native input custody, without execution.

Only identity mappings are supported: extraction, concatenation, decoding and derived-view
claims require their own validator. Unmapped originals remain retained, not credited as reviewed.
All expected contract hashes come from independent frozen authority, not caller attestations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from evals.acceptance_h20_note_inputs import H20_ACCESSION, _canonical, _contract, _digest, _object, _original_packets, _sha
from evals.acceptance_source_units import MAX_TOTAL_CONTEXT_BYTES, MAX_UNIT_CONTEXT_BYTES, validate_unit_manifest


_TOKEN = object()
_KEYS = frozenset({"schema_version", "kind", "accession_number", "original_contract_sha256",
                   "review_contract_sha256", "unit_manifest_sha256", "source_controls", "packet_mapping", "units"})
H20_TEXT_STRUCTURAL_KINDS = frozenset({
    "markup", "table_fragment", "text", "exact_json_scaffold", "complete_concept_all_units_and_observations",
    "exact_submission_scaffold", "complete_pre_note_material_with_structural_header", "complete_numbered_note_group",
    "complete_post_note_material", "complete_native_member", "complete_artifact_pending_capacity",
    "complete_native_bound_prepared_reader", "complete_decoded_child", "derived_projection_record_group",
})


@dataclass(frozen=True, slots=True)
class JointUnit:
    unit_id: str
    record_bytes: bytes
    parts: tuple[bytes, ...]
    input_sha256: str


@dataclass(frozen=True, slots=True, init=False)
class ValidatedH20JointInputs:
    """Immutable mechanically validated mapping/source owner; never a semantic attestation."""

    contract_bytes: bytes
    original_contract_bytes: bytes
    review_contract_bytes: bytes
    original_packets: tuple[tuple[str, bytes], ...]
    contract_sha256: str
    manifest_sha256: str
    review_identity: bytes
    units: tuple[JointUnit, ...]
    unmapped_original_roles: tuple[str, ...]

    def __init__(self, token: object, **values: Any) -> None:
        if token is not _TOKEN:
            raise TypeError("joint inputs must come from validate_h20_joint_inputs")
        for name, value in values.items():
            object.__setattr__(self, name, value)

    def require_review(self, manifest_sha256: str, expected_packets: Any, packet_hashes: dict[str, str]) -> None:
        if self.manifest_sha256 != manifest_sha256 or self.review_identity != _canonical({
            "expected_packets": expected_packets, "packet_hashes": packet_hashes,
        }):
            raise ValueError("joint inputs belong to different review source inputs")

    def unit(self, unit_id: str) -> JointUnit:
        matches = [unit for unit in self.units if unit.unit_id == unit_id]
        if len(matches) != 1:
            raise ValueError("joint input must identify exactly one complete review unit")
        return matches[0]


def _part(role: str, packet: dict[str, Any], raw: bytes, span: dict[str, Any], kind: str) -> tuple[dict[str, Any], bytes]:
    _object(span, frozenset({"start", "end", "sha256"}), "joint span")
    start, end = span["start"], span["end"]
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(raw):
        raise ValueError("joint span lies outside its original packet")
    data = raw[start:end]
    if _sha(data) != _digest(span["sha256"], "joint span sha256"):
        raise ValueError("joint context bytes differ from their approved hash")
    return ({"part_kind": kind, "original_packet_role": role, "packet_sha256": packet["sha256"],
             **span, "byte_length": len(data)}, data)


def validate_h20_joint_inputs(
    *, original_contract_bytes: bytes, expected_original_contract_sha256: str,
    review_contract_bytes: bytes, expected_review_contract_sha256: str,
    joint_contract_bytes: bytes, expected_joint_contract_sha256: str,
    original_packet_bytes: dict[str, bytes], unit_manifest: dict[str, Any],
    expected_packets: list[dict[str, Any]], packet_bytes: dict[str, bytes],
) -> ValidatedH20JointInputs:
    """Validate both pinned packet sets, a whole review manifest and exact identity mappings.

    Original/review contracts each use {accession_number, packets}, with role-ordered packet
    identities. The joint contract binds their external hashes and the full manifest hash. One
    ordered mapping per review packet names {review_role, original_role}; its complete bytes must
    equal that original. One ordered record per review unit retains its structural_kind and names
    dependency_context entries {packet_role, start, end, sha256, dependency_id}. These are exact
    additional original spans, never extra coverage. This proves neither global mapping
    completeness nor semantic suitability, modality delivery, capacity or admission.
    """
    original = _contract(original_contract_bytes, expected_original_contract_sha256, "original contract")
    review = _contract(review_contract_bytes, expected_review_contract_sha256, "review contract")
    joint = _contract(joint_contract_bytes, expected_joint_contract_sha256, "joint contract")
    originals = _original_packets(original, original_packet_bytes)
    reviews = _original_packets(review, packet_bytes)
    if _canonical(expected_packets) != _canonical(review["packets"]):
        raise ValueError("review expected set differs from the independently pinned review contract")
    validation = validate_unit_manifest(unit_manifest, accession_number=H20_ACCESSION,
                                       expected_packets=expected_packets, packet_bytes=packet_bytes)
    _object(joint, _KEYS, "joint contract")
    if (type(joint["schema_version"]) is not int or joint["schema_version"] != 1
            or joint["kind"] != "h20_joint_native_inputs" or joint["accession_number"] != H20_ACCESSION
            or joint["original_contract_sha256"] != expected_original_contract_sha256
            or joint["review_contract_sha256"] != expected_review_contract_sha256
            or joint["unit_manifest_sha256"] != validation["manifest_sha256"]):
        raise ValueError("joint contract differs from the frozen H20 inputs")
    controls = _object(joint["source_controls"], frozenset({"handback_sha256", "note_contract_sha256", "u001_contract_sha256"}),
                       "source controls")
    for name, digest in controls.items():
        _digest(digest, name)  # Provenance identity only; source semantics remain the independent owner's work.
    mappings = joint["packet_mapping"]
    if type(mappings) is not list or len(mappings) != len(reviews):
        raise ValueError("every review packet requires a whole-packet identity mapping")
    origin_by_review = {}
    for mapping, role in zip(mappings, reviews):
        _object(mapping, frozenset({"review_role", "original_role"}), "identity mapping")
        original_role = mapping["original_role"]
        if mapping["review_role"] != role or type(original_role) is not str or original_role not in originals:
            raise ValueError("identity mapping order or original owner differs")
        if packet_bytes[role] != original_packet_bytes[original_role]:
            raise ValueError("only exact whole-packet identity mappings are supported")
        origin_by_review[role] = original_role
    declarations = joint["units"]
    if type(declarations) is not list or len(declarations) != len(unit_manifest["units"]):
        raise ValueError("joint contract must bind every whole review unit")
    packet_roles = {packet["packet_id"]: packet["role"] for packet in unit_manifest["declared_packets"]}
    result = []
    total_context = 0
    for declaration, unit in zip(declarations, unit_manifest["units"]):
        _object(declaration, frozenset({"unit_id", "structural_kind", "dependency_context"}), "joint unit")
        if declaration["unit_id"] != unit["unit_id"] or declaration["structural_kind"] != unit["structural_kind"]:
            raise ValueError("joint unit order, identity or structural label differs")
        role = packet_roles[unit["packet_id"]]
        origin_role = origin_by_review[role]
        records, parts = [], []
        context_bounds: dict[str, list[tuple[int, int]]] = {}
        for kind, spans in (("coverage", unit["coverage_spans"]), ("native_context", unit["context_spans"])):
            for span in spans:
                record, data = _part(origin_role, originals[origin_role], original_packet_bytes[origin_role], span, kind)
                record["review_packet_role"] = role
                records.append(record)
                parts.append(data)
                if kind == "native_context":
                    context_bounds.setdefault(origin_role, []).append((span["start"], span["end"]))
        extra = declaration["dependency_context"]
        if type(extra) is not list:
            raise ValueError("dependency_context must be an ordered list")
        prior = None
        for value in extra:
            _object(value, frozenset({"packet_role", "start", "end", "sha256", "dependency_id"}), "dependency context")
            foreign = value["packet_role"]
            if type(foreign) is not str or foreign not in originals:
                raise ValueError("dependency context names an unknown original packet")
            if type(value["dependency_id"]) is not str or not value["dependency_id"].strip():
                raise ValueError("dependency context requires its frozen dependency identity")
            span = {key: value[key] for key in ("start", "end", "sha256")}
            record, data = _part(foreign, originals[foreign], original_packet_bytes[foreign], span, "dependency_context")
            order = (foreign, span["start"])
            if prior is not None and order <= prior:
                raise ValueError("dependency context must retain canonical packet/span order")
            prior = order
            bounds = context_bounds.setdefault(foreign, [])
            if any(span["start"] < end and start < span["end"] for start, end in bounds):
                raise ValueError("dependency context overlaps already retained context")
            if foreign == origin_role and any(span["start"] < s["end"] and s["start"] < span["end"] for s in unit["coverage_spans"]):
                raise ValueError("dependency context overlaps the unit's own coverage")
            bounds.append((span["start"], span["end"]))
            record["dependency_id"] = value["dependency_id"]
            records.append(record)
            parts.append(data)
        context_bytes = sum(record["byte_length"] for record in records if record["part_kind"] != "coverage")
        total_context += context_bytes
        if context_bytes > MAX_UNIT_CONTEXT_BYTES or total_context > MAX_TOTAL_CONTEXT_BYTES:
            raise ValueError("joint context exceeds existing source-unit custody ceilings")
        record = {"joint_contract_sha256": expected_joint_contract_sha256, "unit": unit, "parts": records}
        encoded = _canonical(record)
        result.append(JointUnit(unit["unit_id"], encoded, tuple(parts), _sha(b"h20-joint-input-v1\x00" + encoded)))
    return ValidatedH20JointInputs(
        _TOKEN, contract_bytes=joint_contract_bytes, original_contract_bytes=original_contract_bytes,
        review_contract_bytes=review_contract_bytes, original_packets=tuple(original_packet_bytes.items()),
        contract_sha256=expected_joint_contract_sha256, manifest_sha256=validation["manifest_sha256"],
        review_identity=_canonical({"expected_packets": expected_packets,
                                    "packet_hashes": {role: _sha(raw) for role, raw in packet_bytes.items()}}),
        units=tuple(result),
        unmapped_original_roles=tuple(role for role in originals if role not in origin_by_review.values()),
    )
