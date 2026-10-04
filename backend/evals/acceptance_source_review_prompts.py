"""Deterministically render text-only E7 source-review node prompts.

This module is a non-admitting custody primitive.  It reuses the source-unit owner for leaf
identity validation, binds exact UTF-8 source or child bytes into one stable byte format, and
does not dispatch a model or attest that a provider received the bytes.  Binary and multimodal
inputs are deliberately unsupported by format version 1.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from evals.acceptance_h20_joint_inputs import H20_TEXT_STRUCTURAL_KINDS, ValidatedH20JointInputs
from evals.acceptance_source_review_graph import children_sha256
from evals.acceptance_source_units import validate_unit_manifest


SCHEMA_VERSION = 1
RENDER_KIND = "e7_source_review_prompt_render"
INPUT_MANIFEST_KIND = "e7_source_review_prompt_input"
TEXT_STRUCTURAL_KINDS = frozenset({"markup", "table_fragment", "text"})
PARENT_NODE_KINDS = frozenset({"reducer", "role_synthesis"})

_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}")
_LABEL = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,127}")
_RESERVATION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CHILD_KEYS = frozenset({"node_id", "artifact_sha256"})
_START = b"\n\n<<<E7_SOURCE_REVIEW_INPUT_V1>>>\n"
_END = b"<<<E7_SOURCE_REVIEW_INPUT_END_V1>>>\n"
_VALIDATED_SOURCE_TOKEN = object()


@dataclass(frozen=True, slots=True)
class _Span:
    start: int
    end: int
    sha256: str


@dataclass(frozen=True, slots=True)
class _Packet:
    packet_id: str
    role: str
    sha256: str
    byte_length: int
    raw: bytes


@dataclass(frozen=True, slots=True)
class _Unit:
    unit_id: str
    packet_id: str
    unit_sha256: str
    structural_kind: str
    registrant_scope: str
    coverage_spans: tuple[_Span, ...]
    context_spans: tuple[_Span, ...]


@dataclass(frozen=True, slots=True, init=False)
class ValidatedPromptSource:
    """Immutable output of the one external source-manifest validation boundary."""

    accession_number: str
    manifest_sha256: str
    packets: tuple[_Packet, ...]
    units: tuple[_Unit, ...]

    def __init__(
        self,
        token: object,
        *,
        accession_number: str,
        manifest_sha256: str,
        packets: tuple[_Packet, ...],
        units: tuple[_Unit, ...],
    ) -> None:
        if token is not _VALIDATED_SOURCE_TOKEN:
            raise TypeError("ValidatedPromptSource must come from validate_prompt_source")
        object.__setattr__(self, "accession_number", accession_number)
        object.__setattr__(self, "manifest_sha256", manifest_sha256)
        object.__setattr__(self, "packets", packets)
        object.__setattr__(self, "units", units)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _token(value: Any, pattern: re.Pattern[str], name: str) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ValueError(f"invalid {name}")
    return value


def _exact_object(value: Any, keys: frozenset[str], name: str) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value) or set(value) != keys:
        raise ValueError(f"{name} must be an object with exactly: {', '.join(sorted(keys))}")
    return value


def _utf8(data: Any, name: str) -> bytes:
    if type(data) is not bytes:
        raise ValueError(f"{name} must be immutable bytes")
    try:
        data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{name} is not model-ready strict UTF-8") from exc
    return data


def _identity(
    *, accession_number: Any, role: Any, node_id: Any, role_contract_sha256: Any,
    reservation_id: Any,
) -> dict[str, str]:
    return {
        "accession_number": _token(accession_number, _ACCESSION, "accession_number"),
        "role": _token(role, _LABEL, "role"),
        "node_id": _token(node_id, _LABEL, "node_id"),
        "role_contract_sha256": _token(role_contract_sha256, _SHA256, "role_contract_sha256"),
        "reservation_id": _token(reservation_id, _RESERVATION, "reservation_id"),
    }


def _render(template: bytes, manifest: dict[str, Any], parts: list[bytes]) -> dict[str, Any]:
    template = _utf8(template, "prompt template")
    checked_parts = [_utf8(part, f"prompt part {index}") for index, part in enumerate(parts)]
    manifest_bytes = _canonical(manifest)
    manifest_sha256 = _sha(manifest_bytes)
    version = manifest["schema_version"]
    start = _START if version == 1 else b"\n\n<<<E7_SOURCE_REVIEW_INPUT_V2>>>\n"
    end = _END if version == 1 else b"<<<E7_SOURCE_REVIEW_INPUT_END_V2>>>\n"
    frames = [template, start,
              f"manifest {len(manifest_bytes):020d} {manifest_sha256}\n".encode("ascii"),
              manifest_bytes, b"\n"]
    for index, part in enumerate(checked_parts):
        frames.extend((f"part {index:08d} {len(part):020d} {_sha(part)}\n".encode("ascii"),
                       part, b"\n"))
    prompt = b"".join((*frames, end))
    # Defence in depth: every component was checked separately, and the final provider-facing
    # payload must still be one strict UTF-8 byte string.
    _utf8(prompt, "rendered prompt")
    return {
        "schema_version": version,
        "kind": RENDER_KIND,
        "prompt_bytes": prompt,
        "prompt_sha256": _sha(prompt),
        "input_manifest_bytes": manifest_bytes,
        "input_manifest_sha256": manifest_sha256,
        "input_sha256": manifest["input_sha256"],
    }


def validate_prompt_source(
    *,
    accession_number: str,
    unit_manifest: dict[str, Any],
    expected_packets: list[dict[str, Any]],
    packet_bytes: dict[str, bytes],
) -> ValidatedPromptSource:
    """Validate the complete external manifest once and return an immutable rendering owner."""
    validation = validate_unit_manifest(
        unit_manifest,
        accession_number=accession_number,
        expected_packets=expected_packets,
        packet_bytes=packet_bytes,
    )
    packets = tuple(
        _Packet(
            packet_id=packet["packet_id"],
            role=packet["role"],
            sha256=packet["sha256"],
            byte_length=packet["byte_length"],
            raw=packet_bytes[packet["role"]],
        )
        for packet in unit_manifest["declared_packets"]
    )
    units = tuple(
        _Unit(
            unit_id=unit["unit_id"],
            packet_id=unit["packet_id"],
            unit_sha256=unit["unit_sha256"],
            structural_kind=unit["structural_kind"],
            registrant_scope=unit["registrant_scope"],
            coverage_spans=tuple(_Span(span["start"], span["end"], span["sha256"])
                                 for span in unit["coverage_spans"]),
            context_spans=tuple(_Span(span["start"], span["end"], span["sha256"])
                                for span in unit["context_spans"]),
        )
        for unit in unit_manifest["units"]
    )
    return ValidatedPromptSource(
        _VALIDATED_SOURCE_TOKEN,
        accession_number=validation["accession_number"],
        manifest_sha256=validation["manifest_sha256"],
        packets=packets,
        units=units,
    )


def render_leaf_prompt(
    template: bytes,
    *,
    accession_number: str,
    role: str,
    node_id: str,
    role_contract_sha256: str,
    source: ValidatedPromptSource,
    unit_id: str,
    reservation_id: str,
    joint_inputs: ValidatedH20JointInputs | None = None,
) -> dict[str, Any]:
    """Render one leaf from an immutable validated owner and its exact covered/context bytes."""
    identity = _identity(accession_number=accession_number, role=role, node_id=node_id,
                         role_contract_sha256=role_contract_sha256, reservation_id=reservation_id)
    if type(source) is not ValidatedPromptSource:
        raise ValueError("source must come from validate_prompt_source")
    if source.accession_number != identity["accession_number"]:
        raise ValueError("validated prompt source belongs to a different accession")
    requested_unit = _token(unit_id, _SHA256, "unit_id")
    units = [unit for unit in source.units if unit.unit_id == requested_unit]
    if len(units) != 1:
        raise ValueError("unit_id must identify exactly one unit in the validated manifest")
    unit = units[0]
    if joint_inputs is not None:
        if type(joint_inputs) is not ValidatedH20JointInputs:
            raise ValueError("joint inputs require a validated original-to-review mapping")
        if unit.structural_kind not in H20_TEXT_STRUCTURAL_KINDS:
            raise ValueError("unsupported H20 structural kind cannot be rendered as text")
        joint_inputs.require_review(source.manifest_sha256,
                                    [{"role": p.role, "sha256": p.sha256, "byte_length": p.byte_length} for p in source.packets],
                                    {p.role: p.sha256 for p in source.packets})
        joint_unit = joint_inputs.unit(unit.unit_id)
        record = json.loads(joint_unit.record_bytes)
        manifest = {
            "schema_version": 2, "kind": INPUT_MANIFEST_KIND, "node_kind": "leaf", **identity,
            "joint_contract_sha256": joint_inputs.contract_sha256,
            "unmapped_original_roles_not_credited": list(joint_inputs.unmapped_original_roles),
            "template": {"byte_length": len(template), "sha256": _sha(template)},
            "input_sha256": joint_unit.input_sha256,
            "leaf": {"manifest_sha256": source.manifest_sha256, **record["unit"]},
            "parts": record["parts"],
        }
        return _render(template, manifest, list(joint_unit.parts))
    structural_kind = unit.structural_kind
    if structural_kind not in TEXT_STRUCTURAL_KINDS:
        raise ValueError(f"unsupported structural_kind {structural_kind!r} is not model-ready in prompt format 1")
    packets = [packet for packet in source.packets if packet.packet_id == unit.packet_id]
    if len(packets) != 1:  # The source owner guarantees this; keep selection fail-closed.
        raise ValueError("unit packet_id must identify exactly one declared packet")
    packet = packets[0]
    raw = packet.raw

    part_records: list[dict[str, Any]] = []
    parts: list[bytes] = []
    for part_kind, spans in (("coverage", unit.coverage_spans),
                             ("context", unit.context_spans)):
        for span in spans:
            part = raw[span.start:span.end]
            _utf8(part, f"leaf {part_kind} span")
            part_records.append({
                "part_index": len(parts),
                "part_kind": part_kind,
                "packet_role": packet.role,
                "packet_id": packet.packet_id,
                "unit_id": unit.unit_id,
                "start": span.start,
                "end": span.end,
                "byte_length": len(part),
                "sha256": span.sha256,
            })
            parts.append(part)

    template = _utf8(template, "prompt template")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": INPUT_MANIFEST_KIND,
        "node_kind": "leaf",
        **identity,
        "template": {"byte_length": len(template), "sha256": _sha(template)},
        "input_sha256": unit.unit_id,
        "leaf": {
            "manifest_sha256": source.manifest_sha256,
            "packet_id": packet.packet_id,
            "packet_role": packet.role,
            "packet_sha256": packet.sha256,
            "packet_byte_length": packet.byte_length,
            "unit_id": unit.unit_id,
            "unit_sha256": unit.unit_sha256,
            "structural_kind": structural_kind,
            "registrant_scope": unit.registrant_scope,
        },
        "parts": part_records,
    }
    return _render(template, manifest, parts)


def render_parent_prompt(
    template: bytes,
    *,
    accession_number: str,
    role: str,
    node_id: str,
    node_kind: Literal["reducer", "role_synthesis"],
    role_contract_sha256: str,
    children: list[dict[str, str]],
    child_artifacts: Mapping[str, bytes],
    reservation_id: str,
    joint_contract_sha256: str | None = None,
) -> dict[str, Any]:
    """Render a reducer or role synthesis from its ordered exact child artifacts."""
    identity = _identity(accession_number=accession_number, role=role, node_id=node_id,
                         role_contract_sha256=role_contract_sha256, reservation_id=reservation_id)
    if type(node_kind) is not str or node_kind not in PARENT_NODE_KINDS:
        raise ValueError("parent node_kind must be reducer or role_synthesis")
    if type(children) is not list or not children:
        raise ValueError("parent children must be a non-empty ordered list")
    if type(child_artifacts) is not dict or any(type(key) is not str or type(value) is not bytes
                                                for key, value in child_artifacts.items()):
        raise ValueError("child_artifacts must map artifact SHA-256 strings to immutable bytes")

    checked_children: list[dict[str, str]] = []
    seen_nodes: set[str] = set()
    seen_hashes: set[str] = set()
    parts: list[bytes] = []
    part_records: list[dict[str, Any]] = []
    for index, value in enumerate(children):
        child = _exact_object(value, _CHILD_KEYS, "parent child")
        child_id = _token(child["node_id"], _LABEL, "child node_id")
        digest = _token(child["artifact_sha256"], _SHA256, "child artifact_sha256")
        if child_id in seen_nodes or digest in seen_hashes:
            raise ValueError("parent children must have unique node IDs and artifact SHA-256 values")
        if digest not in child_artifacts:
            raise ValueError(f"child artifact bytes missing for {child_id}")
        artifact = child_artifacts[digest]
        if _sha(artifact) != digest:
            raise ValueError(f"child artifact bytes do not match SHA-256 for {child_id}")
        _utf8(artifact, f"child artifact {child_id}")
        seen_nodes.add(child_id)
        seen_hashes.add(digest)
        checked = {"node_id": child_id, "artifact_sha256": digest}
        checked_children.append(checked)
        part_records.append({"part_index": index, "part_kind": "child_artifact",
                             "node_id": child_id, "artifact_sha256": digest,
                             "byte_length": len(artifact)})
        parts.append(artifact)
    if set(child_artifacts) != seen_hashes:
        raise ValueError("child_artifacts must contain exactly the ordered children's artifacts")

    template = _utf8(template, "prompt template")
    input_sha256 = children_sha256(checked_children)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": INPUT_MANIFEST_KIND,
        "node_kind": node_kind,
        **identity,
        "template": {"byte_length": len(template), "sha256": _sha(template)},
        "input_sha256": input_sha256,
        "children": checked_children,
        "parts": part_records,
    }
    if joint_contract_sha256 is not None:
        manifest["schema_version"] = 2
        manifest["joint_contract_sha256"] = _token(joint_contract_sha256, _SHA256, "joint contract sha256")
    return _render(template, manifest, parts)
