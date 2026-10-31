"""Synthetic guards for the partial H20 binding; no filing payload or provider call."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import evals.acceptance_h20_note_inputs as h20


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _span(raw: bytes, start: int, end: int) -> dict[str, Any]:
    return {"start": start, "end": end, "sha256": _sha(raw[start:end])}


def _fixture(context_size: int = 32) -> dict[str, Any]:
    """Two original representations with equal note bytes and distinct complete packet bytes."""
    context = b"x" * context_size
    note_parts = [f"<note>{ordinal:02} synthetic only</note>".encode() for ordinal in range(1, 16)]
    primary = context + b"".join(note_parts) + b"primary tail"
    prefix = b"submission prefix"
    member_start = len(prefix + primary + b"scaffold")
    origin_start = member_start + 7
    origin = bytes(range(251))  # Opaque custody; this is deliberately not a model-ready text probe.
    member34 = b"member:" + origin + b":end"
    member75_start = member_start + len(member34)
    submission = prefix + primary + b"scaffold" + member34 + b"synthetic member75" + b"tail"
    raw = {"complete_submission": submission, "index": b"synthetic index", "primary": primary}
    original = {"accession_number": "0000014846-26-000037", "packets": [
        {"role": role, "sha256": _sha(data), "byte_length": len(data)} for role, data in raw.items()
    ]}
    units = []
    for role, offset in (("complete_submission", len(prefix)), ("primary", 0)):
        start = offset + len(context)
        for ordinal, part in enumerate(note_parts, 1):
            end = start + len(part)
            units.append({
                "unit_label": f"{role}-N{ordinal:02}", "packet_role": role, "packet_sha256": _sha(raw[role]),
                "structural_kind": "complete_numbered_note_group", "coverage_spans": [_span(raw[role], start, end)],
                "context_spans": [_span(raw[role], offset, offset + len(context))],
                "coverage_bytes": len(part), "context_bytes": len(context), "note_ordinal": ordinal,
                "source_owned_boundary_disposition": "approved_for_implementation", "capacity_proved": False,
                "dependency_ids": ["U001-distributed-notes", "IX-native-context-unit-continuation", "TABLE-caption-header-footnote"],
                "whole_table_count": 0, "fact_element_count": 0, "continuation_count": 0,
            })
            start = end
    notes = {
        "kind": "h20_source_owned_exact_note_units_v1", "scope": "H20_only",
        "status": "source_owned_boundary_and_dependency_disposition_for_implementation",
        "semantic_financial_review_attested": False, "runtime_delivery_or_capacity_attested": False,
        "no_other_artifact_coverage_implied": True, "boundary_check": "Synthetic owner boundary declaration.",
        "units": units,
    }
    closure = {
        "kind": "h20_source_owned_u001_closure_v1",
        "status": "approved_distributed_source_obligation_for_implementation_not_review_result",
        "dependency_id": "U001-distributed-notes",
        "origin": {"packet_role": "complete_submission", "member_ordinal": 34,
                   "local_span": [7, 258], "absolute_span": [origin_start, origin_start + 251], "sha256": _sha(origin)},
        "governing_unit_sets": {role: [f"{role}-N{n:02}" for n in range(1, 16)] for role in ("complete_submission", "primary")},
        "other_retained_representation_obligations": [
            {"member_ordinal": 34, "scope": "whole_member", "absolute_span": [member_start, member75_start]},
            {"member_ordinal": 75, "scope": "whole_member_with_contexts_units_and_matching_fact_dependency",
             "absolute_span": [member75_start, len(submission) - 4]},
        ],
        "leaf_obligation": "Each assigned unit gives a local disposition only.",
        "join_obligation": "Both complete sets, other members, all whole child artifacts and every disposition.",
        "unresolved_conflict_route": "Retain both claims; fresh source-only reread needs capacity and binding.",
        "omission_rule": "Missing, open, conflicting, truncated or compacted evidence prevents closure.",
        "outside_reference_rule": "Retain scoped external limitations; no other filing acquisition.",
    }
    return {"original": original, "notes": notes, "closure": closure, "raw": raw}


def _arguments(fixture: dict[str, Any]) -> dict[str, Any]:
    arguments = {"packet_bytes": fixture["raw"]}
    for name, field in (("original", "original"), ("note", "notes"), ("closure", "closure")):
        raw = _json(fixture[field])
        arguments[f"{name}_contract_bytes"] = raw
        arguments[f"expected_{name}_contract_sha256"] = _sha(raw)
    return arguments


def _set(value: dict[str, Any], path: tuple[Any, ...], replacement: Any) -> dict[str, Any]:
    value = copy.deepcopy(value)
    owner: Any = value
    for key in path[:-1]:
        owner = owner[key]
    owner[path[-1]] = replacement
    return value


def test_h20_uses_external_approval_and_complete_supported_contracts() -> None:
    """One authority gate: pins, scope and the complete ordered obligations cannot be weakened."""
    fixture = _fixture()
    arguments = _arguments(fixture)
    successor = _set(fixture, ("notes", "status"),
                     "source_owned_boundary_and_complete_native_context_union_approved_for_implementation")
    assert h20.preflight_h20_note_inputs(**_arguments(successor))["admission_approved"] is False
    for name in ("original", "note", "closure"):
        changed = {**arguments, f"{name}_contract_bytes": arguments[f"{name}_contract_bytes"] + b"\n"}
        with pytest.raises(ValueError, match="externally approved SHA-256"):
            h20.preflight_h20_note_inputs(**changed)
    # Independently pinned but unsupported input still cannot extend this H20-only format.
    cases = [
        (("original", "accession_number"), "0000014846-26-000038"),
        (("notes", "scope"), "all_filings"),
        (("notes", "status"), "unknown_approval"),
        (("notes", "units"), fixture["notes"]["units"][:-1]),
        (("notes", "units"), list(reversed(fixture["notes"]["units"]))),
        (("notes", "units", 0, "unit_label"), "primary-N01"),
        (("notes", "units", 0, "packet_role"), "primary"),
        (("notes", "units", 0, "note_ordinal"), True),
        (("notes", "units", 0, "structural_kind"), "markup"),
        (("notes", "units", 0, "dependency_ids"), []),
        (("notes", "units", 0, "source_owned_boundary_disposition"), "provisional"),
        (("notes", "units", 0, "capacity_proved"), True),
        (("notes", "semantic_financial_review_attested"), True),
        (("notes", "runtime_delivery_or_capacity_attested"), True),
        (("notes", "no_other_artifact_coverage_implied"), False),
        (("notes", "boundary_check"), ""),
        (("closure", "governing_unit_sets", "primary"), ["primary-N01"]),
        (("closure", "origin", "packet_role"), "primary"),
        (("closure", "origin", "member_ordinal"), 75),
        (("closure", "other_retained_representation_obligations"), []),
        (("closure", "other_retained_representation_obligations", 1, "scope"), "omit"),
        (("closure", "join_obligation"), ""),
        (("closure", "omission_rule"), ""),
    ]
    for path, replacement in cases:
        with pytest.raises(ValueError):
            h20.preflight_h20_note_inputs(**_arguments(_set(fixture, path, replacement)))
    for duplicate in (b'{"kind":1,"kind":2}', b'{"kind":NaN}', b'[]', b'\xff'):
        with pytest.raises(ValueError):
            h20.preflight_h20_note_inputs(**{**arguments, "note_contract_bytes": duplicate,
                                            "expected_note_contract_sha256": _sha(duplicate)})
    # Dropping an unrelated original from both supplied lists cannot retain the external contract pin.
    original = copy.deepcopy(fixture["original"])
    original["packets"].pop(1)
    with pytest.raises(ValueError, match="externally approved SHA-256"):
        h20.preflight_h20_note_inputs(**{**arguments, "original_contract_bytes": _json(original),
                                        "packet_bytes": {k: v for k, v in fixture["raw"].items() if k != "index"}})


def test_h20_binds_exact_native_parts_and_keeps_representations_distinct() -> None:
    """One byte-custody gate covers whole packets, note spans and the cross-packet origin."""
    fixture = _fixture()
    before = copy.deepcopy(fixture)
    arguments = _arguments(fixture)
    result = h20.preflight_h20_note_inputs(**arguments)
    assert fixture == before
    assert result["original_packets"] == fixture["original"]["packets"]
    assert result["closure_obligations"] == fixture["closure"]
    assert len(result["note_bindings"]) == 30
    assert len({record["note_binding_sha256"] for record in result["note_bindings"]}) == 30
    for unit, binding in zip(fixture["notes"]["units"], result["note_bindings"]):
        assert binding["unit"] == unit
        origin = fixture["closure"]["origin"]
        expected_parts = []
        for kind, role, spans in (
            ("coverage", unit["packet_role"], unit["coverage_spans"]),
            ("native_context", unit["packet_role"], unit["context_spans"]),
            ("dependency_context", "complete_submission", [{"start": origin["absolute_span"][0],
                                                             "end": origin["absolute_span"][1], "sha256": origin["sha256"]}]),
        ):
            expected_parts.extend({"part_kind": kind, "packet_role": role, "packet_sha256": _sha(fixture["raw"][role]),
                                   **span, "byte_length": span["end"] - span["start"]} for span in spans)
        assert binding["ordered_parts"] == expected_parts
        assert binding["repeated_context_bytes_not_counted_as_coverage"] == unit["context_bytes"] + 251
        payload = {key: value for key, value in binding.items() if key != "note_binding_sha256"}
        assert binding["note_binding_sha256"] == _sha(b"h20-note-input-v1\x00" + _json(payload))
    assert result["note_bindings"][0]["unit"]["coverage_spans"][0]["sha256"] == result["note_bindings"][15]["unit"]["coverage_spans"][0]["sha256"]

    for role, data in fixture["raw"].items():
        for replacement in (data + b"extra", bytes([data[0] ^ 1]) + data[1:], bytearray(data)):
            with pytest.raises(ValueError, match="original packet bytes"):
                h20.preflight_h20_note_inputs(**{**arguments, "packet_bytes": {**fixture["raw"], role: replacement}})
    for raw in ({}, {**fixture["raw"], "foreign": b"x"},
                {**fixture["raw"], "primary": fixture["raw"]["complete_submission"]}):
        with pytest.raises(ValueError):
            h20.preflight_h20_note_inputs(**{**arguments, "packet_bytes": raw})
    cases = [
        (("notes", "units", 0, "packet_sha256"), fixture["notes"]["units"][15]["packet_sha256"]),
        (("notes", "units", 0, "coverage_spans", 0, "sha256"), "0" * 64),
        (("notes", "units", 0, "context_spans", 0, "sha256"), "0" * 64),
        (("notes", "units", 0, "coverage_spans", 0, "start"), True),
        (("notes", "units", 0, "coverage_spans", 0, "end"), len(fixture["raw"]["complete_submission"]) + 1),
        (("notes", "units", 0, "coverage_bytes"), 0),
        (("notes", "units", 0, "context_bytes"), True),
        (("notes", "units", 0, "coverage_spans"), []),
        (("notes", "units", 1, "coverage_spans"), fixture["notes"]["units"][0]["coverage_spans"]),
        (("notes", "units", 0, "context_spans"), fixture["notes"]["units"][0]["coverage_spans"]),
        (("closure", "origin", "sha256"), "0" * 64),
        (("closure", "origin", "local_span"), [8, 259]),
        (("closure", "origin", "absolute_span"), [0, 250]),
    ]
    for path, replacement in cases:
        with pytest.raises(ValueError):
            h20.preflight_h20_note_inputs(**_arguments(_set(fixture, path, replacement)))
    overlap = copy.deepcopy(fixture)
    unit = overlap["notes"]["units"][0]
    unit["context_spans"] = copy.deepcopy(unit["coverage_spans"])
    unit["context_bytes"] = unit["coverage_bytes"]
    with pytest.raises(ValueError, match="own coverage"):
        h20.preflight_h20_note_inputs(**_arguments(overlap))
    with pytest.raises(ValueError, match="custody limits"):
        h20.preflight_h20_note_inputs(**_arguments(_fixture(context_size=65536)))


def test_h20_preflight_cannot_admit_or_call_runtime() -> None:
    """One non-admission gate: complete metadata is still not a graph or an execution route."""
    result = h20.preflight_h20_note_inputs(**_arguments(_fixture()))
    assert result["kind"] == "h20_offline_partial_note_input_bindings"
    for flag in ("semantic_financial_review_attested", "global_partition_validated",
                 "original_to_review_packet_mapping_validated", "graph_binding_validated", "runtime_delivery_attested",
                 "capacity_proved", "dependency_closure_attested", "admission_approved"):
        assert result[flag] is False
    assert not {"coverage_status", "unit_manifest", "graph", "prompt_bytes", "reservation_id"} & result.keys()
    body = {key: value for key, value in result.items() if key != "binding_sha256"}
    assert result["binding_sha256"] == _sha(b"h20-note-preflight-v1\x00" + _json(body))
    assert all(isinstance(part["sha256"], str) for binding in result["note_bindings"] for part in binding["ordered_parts"])
    # Exact import boundary: adding a runtime/transport import or dynamic I/O entry point fails.
    tree = ast.parse(Path(h20.__file__).read_text())
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    assert imports == {"__future__", "hashlib", "json", "re", "typing", "evals.acceptance_source_units"}
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in {"__import__", "open", "eval", "exec", "compile"}]
