"""Deterministic, text-only source-review prompt rendering."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

import pytest

import evals.acceptance_source_review_prompts as prompt_renderer
from evals.acceptance_source_review_graph import children_sha256
from evals.acceptance_source_review_prompts import (
    INPUT_MANIFEST_KIND,
    RENDER_KIND,
    SCHEMA_VERSION,
    render_leaf_prompt,
    render_parent_prompt,
    validate_prompt_source,
)
from evals.acceptance_source_units import build_unit_manifest


ACCESSION = "0000000000-26-000001"
ROLE = "source_reference_b"
CONTRACT_SHA = "a" * 64
HEADER = "<h1>Café results</h1>\n".encode()
BODY = "<p>Revenue was €100.</p>\n".encode()
PRIMARY = HEADER + BODY
PACKETS = [{"role": "primary", "sha256": hashlib.sha256(PRIMARY).hexdigest(),
            "byte_length": len(PRIMARY)}]
MANIFEST = build_unit_manifest(
    accession_number=ACCESSION,
    packets=PACKETS,
    packet_bytes={"primary": PRIMARY},
    units=[
        {"packet_role": "primary", "structural_kind": "markup", "registrant_scope": "registrant",
         "coverage_spans": [{"start": 0, "end": len(HEADER)}], "context_spans": []},
        {"packet_role": "primary", "structural_kind": "text", "registrant_scope": "registrant",
         "coverage_spans": [{"start": len(HEADER), "end": len(PRIMARY)}],
         "context_spans": [{"start": 0, "end": len(HEADER)}]},
    ],
)
UNIT = MANIFEST["units"][1]
SOURCE = validate_prompt_source(
    accession_number=ACCESSION, unit_manifest=MANIFEST, expected_packets=PACKETS,
    packet_bytes={"primary": PRIMARY},
)
TEMPLATE = b"Review the exact source parts below."
_START = b"\n\n<<<E7_SOURCE_REVIEW_INPUT_V1>>>\n"
_END = b"<<<E7_SOURCE_REVIEW_INPUT_END_V1>>>\n"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _oracle_prompt(template: bytes, manifest: dict[str, Any], parts: list[bytes]) -> bytes:
    manifest_bytes = _canonical(manifest)
    frames = [template, _START,
              f"manifest {len(manifest_bytes):020d} {_sha(manifest_bytes)}\n".encode(),
              manifest_bytes, b"\n"]
    for index, part in enumerate(parts):
        frames.extend((f"part {index:08d} {len(part):020d} {_sha(part)}\n".encode(), part, b"\n"))
    return b"".join((*frames, _END))


def _leaf(**overrides: Any) -> dict[str, Any]:
    arguments = {
        "accession_number": ACCESSION,
        "role": ROLE,
        "node_id": "leaf-2",
        "role_contract_sha256": CONTRACT_SHA,
        "source": SOURCE,
        "unit_id": UNIT["unit_id"],
        "reservation_id": "reserve-leaf-2-1",
    }
    arguments.update(overrides)
    return render_leaf_prompt(TEMPLATE, **arguments)


def test_leaf_prompt_binds_validated_unit_and_exact_utf8_parts(monkeypatch: pytest.MonkeyPatch) -> None:
    before = copy.deepcopy(MANIFEST)
    rendered = _leaf()
    assert MANIFEST == before
    assert set(rendered) == {"schema_version", "kind", "prompt_bytes", "prompt_sha256",
                             "input_manifest_bytes", "input_manifest_sha256", "input_sha256"}
    assert rendered["schema_version"] == SCHEMA_VERSION
    assert rendered["kind"] == RENDER_KIND
    assert rendered["input_sha256"] == UNIT["unit_id"]

    packet = MANIFEST["declared_packets"][0]
    parts = [BODY, HEADER]  # Declared coverage first, then separately labelled context.
    input_manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": INPUT_MANIFEST_KIND,
        "node_kind": "leaf",
        "accession_number": ACCESSION,
        "role": ROLE,
        "node_id": "leaf-2",
        "role_contract_sha256": CONTRACT_SHA,
        "reservation_id": "reserve-leaf-2-1",
        "template": {"byte_length": len(TEMPLATE), "sha256": _sha(TEMPLATE)},
        "input_sha256": UNIT["unit_id"],
        "leaf": {
            "manifest_sha256": _sha(_canonical(MANIFEST)),
            "packet_id": packet["packet_id"],
            "packet_role": "primary",
            "packet_sha256": _sha(PRIMARY),
            "packet_byte_length": len(PRIMARY),
            "unit_id": UNIT["unit_id"],
            "unit_sha256": UNIT["unit_sha256"],
            "structural_kind": "text",
            "registrant_scope": "registrant",
        },
        "parts": [
            {"part_index": 0, "part_kind": "coverage", "packet_role": "primary",
             "packet_id": packet["packet_id"], "unit_id": UNIT["unit_id"],
             "start": len(HEADER), "end": len(PRIMARY), "byte_length": len(BODY),
             "sha256": _sha(BODY)},
            {"part_index": 1, "part_kind": "context", "packet_role": "primary",
             "packet_id": packet["packet_id"], "unit_id": UNIT["unit_id"],
             "start": 0, "end": len(HEADER), "byte_length": len(HEADER),
             "sha256": _sha(HEADER)},
        ],
    }
    expected_manifest = _canonical(input_manifest)
    expected_prompt = _oracle_prompt(TEMPLATE, input_manifest, parts)
    assert rendered["input_manifest_bytes"] == expected_manifest
    assert rendered["input_manifest_sha256"] == _sha(expected_manifest)
    assert rendered["prompt_bytes"] == expected_prompt
    assert rendered["prompt_sha256"] == _sha(expected_prompt)
    assert expected_prompt.decode("utf-8").count("Café") == 1
    assert _leaf() == rendered

    changed = copy.deepcopy(MANIFEST)
    changed["units"][1]["coverage_spans"][0]["start"] += 1
    with pytest.raises(ValueError, match="unit coverage_spans does not match"):
        validate_prompt_source(accession_number=ACCESSION, unit_manifest=changed,
                               expected_packets=PACKETS, packet_bytes={"primary": PRIMARY})
    with pytest.raises(ValueError, match="packet primary bytes do not match"):
        validate_prompt_source(accession_number=ACCESSION, unit_manifest=MANIFEST,
                               expected_packets=PACKETS,
                               packet_bytes={"primary": PRIMARY.replace(b"100", b"101")})
    with pytest.raises(ValueError, match="unit_id must identify exactly one"):
        _leaf(unit_id="b" * 64)
    with pytest.raises(ValueError, match="source must come from validate_prompt_source"):
        _leaf(source={})
    with pytest.raises(ValueError, match="prompt template is not model-ready strict UTF-8"):
        render_leaf_prompt(b"bad\xff", **{
            "accession_number": ACCESSION, "role": ROLE, "node_id": "leaf-2",
            "role_contract_sha256": CONTRACT_SHA, "source": SOURCE,
            "unit_id": UNIT["unit_id"], "reservation_id": "reserve-leaf-2-1",
        })
    # The external source boundary is validated once; rendering an arbitrary leaf reuses the
    # immutable owner rather than hashing the complete filing again for every node.
    monkeypatch.setattr(prompt_renderer, "validate_unit_manifest",
                        lambda *args, **kwargs: pytest.fail("leaf renderer revalidated full manifest"))
    assert _leaf() == rendered


@pytest.mark.parametrize("structural_kind", ["binary_image", "image", "structured_binary"])
def test_leaf_rejects_non_text_modalities_even_when_the_bytes_are_utf8(structural_kind: str) -> None:
    raw = b"text-looking bytes are still not a delivered image"
    packets = [{"role": "graphic", "sha256": _sha(raw), "byte_length": len(raw)}]
    manifest = build_unit_manifest(
        accession_number=ACCESSION, packets=packets, packet_bytes={"graphic": raw},
        units=[{"packet_role": "graphic", "structural_kind": structural_kind,
                "registrant_scope": "registrant", "coverage_spans": [{"start": 0, "end": len(raw)}],
                "context_spans": []}],
    )
    source = validate_prompt_source(accession_number=ACCESSION, unit_manifest=manifest,
                                    expected_packets=packets, packet_bytes={"graphic": raw})
    with pytest.raises(ValueError, match="unsupported structural_kind .* is not model-ready"):
        render_leaf_prompt(
            TEMPLATE, accession_number=ACCESSION, role=ROLE, node_id="leaf-image",
            role_contract_sha256=CONTRACT_SHA, source=source,
            unit_id=manifest["units"][0]["unit_id"],
            reservation_id="reserve-image-1",
        )


def test_leaf_rejects_non_utf8_source_even_when_byte_custody_is_valid() -> None:
    raw = b"valid prefix\n\xffinvalid utf8"
    packets = [{"role": "primary", "sha256": _sha(raw), "byte_length": len(raw)}]
    manifest = build_unit_manifest(
        accession_number=ACCESSION, packets=packets, packet_bytes={"primary": raw},
        units=[{"packet_role": "primary", "structural_kind": "text", "registrant_scope": "registrant",
                "coverage_spans": [{"start": 0, "end": len(raw)}], "context_spans": []}],
    )
    source = validate_prompt_source(accession_number=ACCESSION, unit_manifest=manifest,
                                    expected_packets=packets, packet_bytes={"primary": raw})
    with pytest.raises(ValueError, match="leaf coverage span is not model-ready strict UTF-8"):
        render_leaf_prompt(
            TEMPLATE, accession_number=ACCESSION, role=ROLE, node_id="leaf-bad-utf8",
            role_contract_sha256=CONTRACT_SHA, source=source,
            unit_id=manifest["units"][0]["unit_id"],
            reservation_id="reserve-bad-utf8-1",
        )


def test_parent_prompt_binds_ordered_exact_utf8_child_artifacts() -> None:
    artifacts = ["Issue A — café".encode(), "Issue B — €100".encode()]
    children = [{"node_id": f"leaf-{index}", "artifact_sha256": _sha(artifact)}
                for index, artifact in enumerate(artifacts, start=1)]
    artifact_map = {_sha(artifact): artifact for artifact in artifacts}
    template = b"Reduce the exact child artifacts below."
    rendered = render_parent_prompt(
        template, accession_number=ACCESSION, role=ROLE, node_id="reduce-1", node_kind="reducer",
        role_contract_sha256=CONTRACT_SHA, children=children, child_artifacts=artifact_map,
        reservation_id="reserve-reduce-1",
    )
    input_manifest = json.loads(rendered["input_manifest_bytes"])
    assert input_manifest["children"] == children
    assert input_manifest["parts"] == [
        {"part_index": index, "part_kind": "child_artifact", "node_id": child["node_id"],
         "artifact_sha256": child["artifact_sha256"], "byte_length": len(artifacts[index])}
        for index, child in enumerate(children)
    ]
    assert rendered["input_sha256"] == children_sha256(children)
    assert rendered["prompt_bytes"] == _oracle_prompt(template, input_manifest, artifacts)

    reversed_result = render_parent_prompt(
        template, accession_number=ACCESSION, role=ROLE, node_id="reduce-1", node_kind="reducer",
        role_contract_sha256=CONTRACT_SHA, children=list(reversed(children)), child_artifacts=artifact_map,
        reservation_id="reserve-reduce-1",
    )
    assert reversed_result["input_sha256"] != rendered["input_sha256"]
    assert reversed_result["prompt_sha256"] != rendered["prompt_sha256"]

    changed = {**artifact_map, children[0]["artifact_sha256"]: b"changed child"}
    with pytest.raises(ValueError, match="bytes do not match SHA-256 for leaf-1"):
        render_parent_prompt(
            template, accession_number=ACCESSION, role=ROLE, node_id="reduce-1", node_kind="reducer",
            role_contract_sha256=CONTRACT_SHA, children=children, child_artifacts=changed,
            reservation_id="reserve-reduce-1",
        )
    with pytest.raises(ValueError, match="exactly the ordered children's artifacts"):
        render_parent_prompt(
            template, accession_number=ACCESSION, role=ROLE, node_id="reduce-1", node_kind="reducer",
            role_contract_sha256=CONTRACT_SHA, children=children,
            child_artifacts={**artifact_map, "f" * 64: b"extra"}, reservation_id="reserve-reduce-1",
        )
    bad_artifact = b"bad\xff"
    bad_children = [{"node_id": "leaf-bad", "artifact_sha256": _sha(bad_artifact)}]
    with pytest.raises(ValueError, match="child artifact leaf-bad is not model-ready strict UTF-8"):
        render_parent_prompt(
            template, accession_number=ACCESSION, role=ROLE, node_id="reduce-1", node_kind="reducer",
            role_contract_sha256=CONTRACT_SHA, children=bad_children,
            child_artifacts={_sha(bad_artifact): bad_artifact}, reservation_id="reserve-reduce-1",
        )
