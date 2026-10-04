"""Offline byte binding for the source owner's H20 note/U001 implementation contracts.

This partial preflight neither renders prompts nor produces a source-unit/graph manifest.
Expected hashes are independently frozen approval inputs, never derived here from the supplied
contracts. The caller retains that approval evidence. No source payload is returned or logged.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from evals.acceptance_source_units import MAX_TOTAL_CONTEXT_BYTES, MAX_UNIT_CONTEXT_BYTES


H20_ACCESSION = "0000014846-26-000037"
_ROLES = ("complete_submission", "primary")
_DEPENDENCIES = ["U001-distributed-notes", "IX-native-context-unit-continuation", "TABLE-caption-header-footnote"]
_HASH = re.compile(r"[0-9a-f]{64}")
_ROLE = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,127}")
_NOTE_KEYS = frozenset({
    "unit_label", "packet_role", "packet_sha256", "structural_kind", "coverage_spans", "context_spans",
    "coverage_bytes", "context_bytes", "note_ordinal", "source_owned_boundary_disposition", "capacity_proved",
    "dependency_ids", "whole_table_count", "fact_element_count", "continuation_count",
})
_NOTE_CONTRACT_KEYS = frozenset({
    "kind", "scope", "status", "semantic_financial_review_attested", "runtime_delivery_or_capacity_attested",
    "no_other_artifact_coverage_implied", "boundary_check", "units",
})
_CLOSURE_KEYS = frozenset({
    "kind", "status", "dependency_id", "origin", "governing_unit_sets", "other_retained_representation_obligations",
    "leaf_obligation", "join_obligation", "unresolved_conflict_route", "omission_rule", "outside_reference_rule",
})
_FALSE_FLAGS = (
    "semantic_financial_review_attested", "global_partition_validated", "original_to_review_packet_mapping_validated",
    "graph_binding_validated", "runtime_delivery_attested", "capacity_proved", "dependency_closure_attested",
    "admission_approved",
)


def _sha(raw: bytes | memoryview) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def _object(value: Any, keys: frozenset[str], name: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise ValueError(f"{name} must have exactly the supported fields")
    return value


def _text(value: Any, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _digest(value: Any, name: str) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError(f"invalid {name}")
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("nonfinite JSON value")


def _contract(raw: bytes, expected: str, name: str) -> dict[str, Any]:
    _digest(expected, f"expected {name} SHA-256")
    if type(raw) is not bytes or _sha(raw) != expected:
        raise ValueError(f"{name} differs from its externally approved SHA-256")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise ValueError(f"{name} is not unambiguous UTF-8 JSON") from exc
    if type(value) is not dict:
        raise ValueError(f"{name} must be a JSON object")
    return value


def _original_packets(contract: dict[str, Any], supplied: dict[str, bytes]) -> dict[str, dict[str, Any]]:
    _object(contract, frozenset({"accession_number", "packets"}), "original contract")
    if contract["accession_number"] != H20_ACCESSION:
        raise ValueError("only the frozen H20 accession is supported")
    packets = contract["packets"]
    if type(packets) is not list or not packets:
        raise ValueError("original packets must be a nonempty list")
    by_role: dict[str, dict[str, Any]] = {}
    for packet in packets:
        _object(packet, frozenset({"role", "sha256", "byte_length"}), "original packet")
        role = packet["role"]
        if type(role) is not str or _ROLE.fullmatch(role) is None or (by_role and role <= next(reversed(by_role))):
            raise ValueError("original packet roles must be unique and ascending")
        _digest(packet["sha256"], "original packet SHA-256")
        _integer(packet["byte_length"], "original packet byte_length", 1)
        by_role[role] = packet
    if not set(_ROLES) <= by_role.keys():
        raise ValueError("both original H20 representations are required")
    if (type(supplied) is not dict or any(type(key) is not str for key in supplied)
            or set(supplied) != set(by_role)):
        raise ValueError("bytes must match the complete independent original packet set")
    for role, packet in by_role.items():
        raw = supplied[role]
        if type(raw) is not bytes or len(raw) != packet["byte_length"] or _sha(raw) != packet["sha256"]:
            raise ValueError("original packet bytes differ from their frozen identity")
    return by_role


def _part(span: Any, packet: dict[str, Any], raw: bytes, kind: str) -> dict[str, Any]:
    _object(span, frozenset({"start", "end", "sha256"}), "span")
    start = _integer(span["start"], "span start")
    end = _integer(span["end"], "span end", 1)
    if not start < end <= len(raw):
        raise ValueError("span is outside its original packet")
    if _sha(memoryview(raw)[start:end]) != _digest(span["sha256"], "span SHA-256"):
        raise ValueError("span SHA-256 differs from the original native bytes")
    return {"part_kind": kind, "packet_role": packet["role"], "packet_sha256": packet["sha256"],
            **span, "byte_length": end - start}


def _parts(spans: Any, packet: dict[str, Any], raw: bytes, kind: str) -> list[dict[str, Any]]:
    if type(spans) is not list:
        raise ValueError("spans must be a list")
    result = [_part(span, packet, raw, kind) for span in spans]
    if any(left["end"] > right["start"] for left, right in zip(result, result[1:])):
        raise ValueError("spans must be ordered and nonoverlapping")
    return result


def _closure_origin(closure: dict[str, Any], packets: dict[str, Any], raw: dict[str, bytes]) -> dict[str, Any]:
    _object(closure, _CLOSURE_KEYS, "closure contract")
    if (closure["kind"] != "h20_source_owned_u001_closure_v1"
            or closure["status"] != "approved_distributed_source_obligation_for_implementation_not_review_result"
            or closure["dependency_id"] != _DEPENDENCIES[0]):
        raise ValueError("unsupported H20 closure contract")
    for field in ("leaf_obligation", "join_obligation", "unresolved_conflict_route", "omission_rule", "outside_reference_rule"):
        _text(closure[field], field)
    origin = _object(closure["origin"], frozenset({
        "packet_role", "member_ordinal", "local_span", "absolute_span", "sha256",
    }), "origin")
    if origin["packet_role"] != "complete_submission" or type(origin["member_ordinal"]) is not int or origin["member_ordinal"] != 34:
        raise ValueError("unsupported U001 origin owner")
    for field in ("local_span", "absolute_span"):
        if type(origin[field]) is not list or len(origin[field]) != 2:
            raise ValueError("origin requires exact local and absolute bounds")
        start, end = origin[field]
        if _integer(end, field) - _integer(start, field) != 251:
            raise ValueError("U001 origin must retain all 251 bytes")
    obligations = closure["other_retained_representation_obligations"]
    if type(obligations) is not list or len(obligations) != 2:
        raise ValueError("both other retained representation obligations are required")
    for record, ordinal, scope in zip(obligations, (34, 75), (
            "whole_member", "whole_member_with_contexts_units_and_matching_fact_dependency")):
        _object(record, frozenset({"member_ordinal", "scope", "absolute_span"}), "retained obligation")
        if type(record["member_ordinal"]) is not int or record["member_ordinal"] != ordinal or record["scope"] != scope:
            raise ValueError("retained representation obligation changed")
        bounds = record["absolute_span"]
        if (type(bounds) is not list or len(bounds) != 2
                or not _integer(bounds[0], "retained start") < _integer(bounds[1], "retained end") <= len(raw["complete_submission"])):
            raise ValueError("retained obligation bounds are outside the original submission")
    member_start, member_end = obligations[0]["absolute_span"]
    if (origin["absolute_span"] != [member_start + offset for offset in origin["local_span"]]
            or origin["absolute_span"][1] > member_end):
        raise ValueError("origin local and absolute bounds disagree with member34")
    return _part({"start": origin["absolute_span"][0], "end": origin["absolute_span"][1], "sha256": origin["sha256"]},
                 packets["complete_submission"], raw["complete_submission"], "dependency_context")


def preflight_h20_note_inputs(
    *, original_contract_bytes: bytes, expected_original_contract_sha256: str,
    note_contract_bytes: bytes, expected_note_contract_sha256: str,
    closure_contract_bytes: bytes, expected_closure_contract_sha256: str,
    packet_bytes: dict[str, bytes],
) -> dict[str, Any]:
    """Return hash-bound partial note inputs; all review/delivery/admission claims remain false.

    ``original_contract_bytes`` is independently frozen JSON with ``accession_number`` and
    ascending ``packets`` ({role, sha256, byte_length}). Supply bytes for that entire packet set.
    The other JSON files are the approved source-owner note/U001 projections. None of the three
    expected hashes may be learned from the corresponding untrusted input in the calling path.
    This function has no I/O and does not validate financial meaning, full-member coverage,
    original-to-review extraction mapping, model capacity, or completion of a dependency.
    """
    original = _contract(original_contract_bytes, expected_original_contract_sha256, "original contract")
    notes = _contract(note_contract_bytes, expected_note_contract_sha256, "note contract")
    closure = _contract(closure_contract_bytes, expected_closure_contract_sha256, "closure contract")
    packets = _original_packets(original, packet_bytes)
    origin = _closure_origin(closure, packets, packet_bytes)
    _object(notes, _NOTE_CONTRACT_KEYS, "note contract")
    if (notes["kind"] != "h20_source_owned_exact_note_units_v1" or notes["scope"] != "H20_only"
            or notes["status"] != "source_owned_boundary_and_dependency_disposition_for_implementation"
            or notes["semantic_financial_review_attested"] is not False
            or notes["runtime_delivery_or_capacity_attested"] is not False
            or notes["no_other_artifact_coverage_implied"] is not True):
        raise ValueError("unsupported note scope or review/capacity claim")
    _text(notes["boundary_check"], "boundary_check")
    units = notes["units"]
    expected_labels = [f"{role}-N{number:02}" for role in _ROLES for number in range(1, 16)]
    if type(units) is not list or len(units) != 30:
        raise ValueError("exactly both ordered 15-note sets are required")
    expected_sets = {role: [label for label in expected_labels if label.startswith(role + "-")] for role in _ROLES}
    if closure["governing_unit_sets"] != expected_sets:
        raise ValueError("closure must name both complete ordered note sets")
    bindings: list[dict[str, Any]] = []
    last_coverage_end: dict[str, int] = {}
    total_context = 0
    for index, (unit, label) in enumerate(zip(units, expected_labels)):
        _object(unit, _NOTE_KEYS, "note unit")
        role, ordinal = _ROLES[index // 15], index % 15 + 1
        if (unit["unit_label"] != label or unit["packet_role"] != role
                or type(unit["note_ordinal"]) is not int or unit["note_ordinal"] != ordinal
                or unit["packet_sha256"] != packets[role]["sha256"]
                or unit["structural_kind"] != "complete_numbered_note_group"
                or unit["source_owned_boundary_disposition"] != "approved_for_implementation"
                or unit["capacity_proved"] is not False or unit["dependency_ids"] != _DEPENDENCIES):
            raise ValueError("note identity, order, boundary approval or dependency differs")
        for field in ("whole_table_count", "fact_element_count", "continuation_count"):
            _integer(unit[field], field)  # Retain owner metadata; do not attest its semantic truth.
        coverage = _parts(unit["coverage_spans"], packets[role], packet_bytes[role], "coverage")
        context = _parts(unit["context_spans"], packets[role], packet_bytes[role], "native_context")
        if len(coverage) != 1 or coverage[0]["start"] < last_coverage_end.get(role, 0):
            raise ValueError("whole note coverage must be one ordered nonoverlapping span")
        last_coverage_end[role] = coverage[0]["end"]
        for field, parts in (("coverage_bytes", coverage), ("context_bytes", context)):
            if _integer(unit[field], field) != sum(part["byte_length"] for part in parts):
                raise ValueError("declared note byte count differs from its exact spans")
        repeated = [*context, origin]
        if any(part["packet_role"] == role and part["start"] < coverage[0]["end"]
               and coverage[0]["start"] < part["end"] for part in repeated):
            raise ValueError("repeated context cannot be counted as own coverage")
        context_count = sum(part["byte_length"] for part in repeated)
        total_context += context_count
        if context_count > MAX_UNIT_CONTEXT_BYTES or total_context > MAX_TOTAL_CONTEXT_BYTES:
            raise ValueError("declared repeated context exceeds existing custody limits")
        record = {
            "original_contract_sha256": expected_original_contract_sha256,
            "note_contract_sha256": expected_note_contract_sha256,
            "closure_contract_sha256": expected_closure_contract_sha256,
            "unit": unit,
            "ordered_parts": [*coverage, *context, dict(origin)],
            "repeated_context_bytes_not_counted_as_coverage": context_count,
        }
        bindings.append({**record, "note_binding_sha256": _sha(b"h20-note-input-v1\x00" + _canonical(record))})
    result = {
        "schema_version": 1, "kind": "h20_offline_partial_note_input_bindings",
        "accession_number": H20_ACCESSION,
        "original_contract_sha256": expected_original_contract_sha256,
        "note_contract_sha256": expected_note_contract_sha256,
        "closure_contract_sha256": expected_closure_contract_sha256,
        "original_packets": original["packets"],
        "source_owned_note_metadata": {key: value for key, value in notes.items() if key != "units"},
        "closure_obligations": closure,
        "note_bindings": bindings,
        **{flag: False for flag in _FALSE_FLAGS},
        "limitations": [
            "Partial note byte custody only; the remaining original bytes have no coverage claim here.",
            "Repeated native context is not original coverage or an extracted review packet.",
            "Other retained member obligations and all child-output dispositions remain unfulfilled here.",
            "No graph manifest, prompt, reservation, runtime delivery, capacity proof or source acceptance is produced.",
        ],
    }
    return {**result, "binding_sha256": _sha(b"h20-note-preflight-v1\x00" + _canonical(result))}
