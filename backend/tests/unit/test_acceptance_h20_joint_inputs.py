"""Three synthetic guards for H20 identity mapping, exact joint rendering and v2 custody."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from evals import acceptance_source_review_execution as execution
from evals import acceptance_source_review_graph as graph_api
from evals.acceptance_h20_joint_inputs import ValidatedH20JointInputs, validate_h20_joint_inputs
from evals.acceptance_source_review_delivery import deliver_reserved_attempt
from evals.acceptance_source_review_prompts import render_leaf_prompt, validate_prompt_source
from evals.acceptance_source_units import build_unit_manifest


ACCESSION = "0000014846-26-000037"
ORIGIN = b"<origin>synthetic dependency context</origin>"
TEMPLATES = {"leaf": b"Read exact source inputs.", "role_synthesis": b"Retain complete child outputs."}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _fixture(origin: bytes = ORIGIN, primary_kind: str = "complete_numbered_note_group") -> dict[str, Any]:
    raw = {"complete_submission": origin + b"<note>submission note</note>", "primary": b"<note>distinct native primary</note>"}
    packets = [{"role": role, "sha256": _sha(data), "byte_length": len(data)} for role, data in raw.items()]
    declarations = [
        {"packet_role": "complete_submission", "structural_kind": "complete_pre_note_material_with_structural_header",
         "registrant_scope": "synthetic", "coverage_spans": [{"start": 0, "end": len(origin)}], "context_spans": []},
        {"packet_role": "complete_submission", "structural_kind": "complete_numbered_note_group",
         "registrant_scope": "synthetic", "coverage_spans": [{"start": len(origin), "end": len(raw["complete_submission"])}], "context_spans": []},
        {"packet_role": "primary", "structural_kind": primary_kind,
         "registrant_scope": "synthetic", "coverage_spans": [{"start": 0, "end": len(raw["primary"])}], "context_spans": []},
    ]
    manifest = build_unit_manifest(accession_number=ACCESSION, packets=packets, packet_bytes=raw, units=declarations)
    originals = {"complete_submission": raw["complete_submission"], "index": b"unmapped original retained only", "primary": raw["primary"]}
    original_contract = {"accession_number": ACCESSION, "packets": [
        {"role": role, "sha256": _sha(data), "byte_length": len(data)} for role, data in originals.items()]}
    review_contract = {"accession_number": ACCESSION, "packets": packets}
    foreign = {"packet_role": "complete_submission", "start": 0, "end": len(origin), "sha256": _sha(origin), "dependency_id": "synthetic-u001"}
    joint = {
        "schema_version": 1, "kind": "h20_joint_native_inputs", "accession_number": ACCESSION,
        "original_contract_sha256": _sha(_canonical(original_contract)),
        "review_contract_sha256": _sha(_canonical(review_contract)), "unit_manifest_sha256": _sha(_canonical(manifest)),
        "source_controls": {name: _sha(name.encode()) for name in ("handback_sha256", "note_contract_sha256", "u001_contract_sha256")},
        "packet_mapping": [{"review_role": role, "original_role": role} for role in raw],
        "units": [{"unit_id": unit["unit_id"], "structural_kind": unit["structural_kind"],
                   "dependency_context": [] if index == 0 else [dict(foreign)]} for index, unit in enumerate(manifest["units"])],
    }
    return {"original": original_contract, "review": review_contract, "joint": joint, "original_bytes": originals,
            "manifest": manifest, "packets": packets, "raw": raw}


def _args(fixture: dict[str, Any]) -> dict[str, Any]:
    args = {"original_packet_bytes": fixture["original_bytes"], "unit_manifest": fixture["manifest"],
            "expected_packets": fixture["packets"], "packet_bytes": fixture["raw"]}
    for name in ("original", "review", "joint"):
        raw = _canonical(fixture[name])
        args[f"{name}_contract_bytes"] = raw
        args[f"expected_{name}_contract_sha256"] = _sha(raw)
    return args


def _render(fixture: dict[str, Any], owner: ValidatedH20JointInputs, index: int = 2) -> dict[str, Any]:
    source = validate_prompt_source(accession_number=ACCESSION, unit_manifest=fixture["manifest"],
                                    expected_packets=fixture["packets"], packet_bytes=fixture["raw"])
    return render_leaf_prompt(TEMPLATES["leaf"], accession_number=ACCESSION, role="role-a", node_id="leaf",
                              role_contract_sha256="a" * 64, source=source,
                              unit_id=fixture["manifest"]["units"][index]["unit_id"], reservation_id="synthetic", joint_inputs=owner)


def test_joint_mapping_requires_independent_contracts_and_whole_manifest() -> None:
    fixture = _fixture()
    args = _args(fixture)
    owner = validate_h20_joint_inputs(**args)
    assert owner.unmapped_original_roles == ("index",)
    for name in ("original", "review", "joint"):
        with pytest.raises(ValueError, match="externally approved"):
            validate_h20_joint_inputs(**{**args, f"{name}_contract_bytes": args[f"{name}_contract_bytes"] + b"\n"})
    with pytest.raises(TypeError):
        ValidatedH20JointInputs(object(), contract_sha256="a" * 64)
    with pytest.raises(ValueError, match="independently pinned"):
        validate_h20_joint_inputs(**{**args, "expected_packets": fixture["packets"][:-1]})
    partial = copy.deepcopy(fixture)
    partial["manifest"]["units"].pop(0)
    partial["joint"]["units"].pop(0)
    partial["joint"]["unit_manifest_sha256"] = _sha(_canonical(partial["manifest"]))
    with pytest.raises(ValueError, match="coverage gap"):
        validate_h20_joint_inputs(**_args(partial))
    swapped = copy.deepcopy(fixture)
    # A prefix extraction has valid span hashes but is not a whole-packet identity mapping.
    impostor = swapped["raw"]["primary"] + b"<unreviewed-tail/>"
    swapped["original_bytes"]["index"] = impostor
    swapped["original"]["packets"][1].update(sha256=_sha(impostor), byte_length=len(impostor))
    swapped["joint"]["original_contract_sha256"] = _sha(_canonical(swapped["original"]))
    swapped["joint"]["packet_mapping"][1]["original_role"] = "index"
    with pytest.raises(ValueError, match="whole-packet identity"):
        validate_h20_joint_inputs(**_args(swapped))
    for change in ("mapping", "control", "scope", "structural", "units", "transform"):
        bad = copy.deepcopy(fixture)
        if change == "mapping":
            bad["joint"]["packet_mapping"].pop()
        elif change == "control":
            del bad["joint"]["source_controls"]["handback_sha256"]
        elif change == "scope":
            bad["original"]["accession_number"] = "0000014846-26-000038"
        elif change == "structural":
            bad["joint"]["units"][0]["structural_kind"] = "text"
        elif change == "units":
            bad["joint"]["units"].reverse()
        else:
            bad["joint"]["packet_mapping"][0]["transform"] = "decode"
        with pytest.raises(ValueError):
            validate_h20_joint_inputs(**_args(bad))
    with pytest.raises(ValueError, match="original packet bytes"):
        validate_h20_joint_inputs(**{**args, "original_packet_bytes": {**fixture["original_bytes"], "index": b"changed"}})


def test_joint_render_preserves_same_and_foreign_native_context_without_limit_bypass() -> None:
    fixture = _fixture()
    owner = validate_h20_joint_inputs(**_args(fixture))
    for index in (1, 2):
        rendered = _render(fixture, owner, index)
        assert rendered["schema_version"] == 2
        manifest = json.loads(rendered["input_manifest_bytes"])
        assert manifest["leaf"]["structural_kind"] == "complete_numbered_note_group"
        assert manifest["unmapped_original_roles_not_credited"] == ["index"]
        assert manifest["parts"][-1]["original_packet_role"] == "complete_submission"
        assert rendered["prompt_bytes"].count(ORIGIN) == 1
        part = manifest["parts"][-1]
        expected_frame = f"part 00000001 {len(ORIGIN):020d} {_sha(ORIGIN)}\n".encode() + ORIGIN + b"\n"
        assert expected_frame in rendered["prompt_bytes"]
        assert part["part_kind"] == "dependency_context"
        assert rendered["input_sha256"] != fixture["manifest"]["units"][index]["unit_id"]
    for defect in ("hash", "duplicate", "own_coverage", "unknown_owner", "overlap"):
        bad = copy.deepcopy(fixture)
        extra = bad["joint"]["units"][2]["dependency_context"]
        if defect == "hash":
            extra[0]["sha256"] = "0" * 64
        elif defect == "duplicate":
            extra.append(dict(extra[0]))
        elif defect == "own_coverage":
            bad["joint"]["units"][0]["dependency_context"] = extra
        elif defect == "unknown_owner":
            extra[0]["packet_role"] = "other_filing"
        else:
            second = {**extra[0], "start": 1, "sha256": _sha(ORIGIN[1:])}
            extra.append(second)
        with pytest.raises(ValueError):
            validate_h20_joint_inputs(**_args(bad))
    with pytest.raises(ValueError, match="custody ceilings"):
        validate_h20_joint_inputs(**_args(_fixture(origin=b"x" * 65537)))
    binary = _fixture(primary_kind="binary_image")  # ASCII bytes alone must not relabel a binary modality.
    with pytest.raises(ValueError, match="unsupported H20 structural kind"):
        _render(binary, validate_h20_joint_inputs(**_args(binary)))
    altered = copy.deepcopy(fixture)
    altered["joint"]["source_controls"]["note_contract_sha256"] = "b" * 64
    assert _render(altered, validate_h20_joint_inputs(**_args(altered)))["input_sha256"] != _render(fixture, owner)["input_sha256"]


def _complete(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    fixture = _fixture()
    owner = validate_h20_joint_inputs(**_args(fixture))
    contract = {"schema_version": 1, "kind": graph_api.CONTRACT_KIND, "role": "role-a", "provider": "synthetic",
                "model": "synthetic-model", "provider_version": "synthetic-1", "exposure_limit": None,
                "node_kinds": {kind: {"template_sha256": _sha(raw)} for kind, raw in TEMPLATES.items()}}
    execution.initialize_journal(root, programme_id="h20-joint-synthetic", accession_number=ACCESSION,
                                  role_contract=contract, unit_manifest_sha256=_sha(_canonical(fixture["manifest"])),
                                  unit_manifest=fixture["manifest"], expected_packets=fixture["packets"],
                                  packet_bytes=fixture["raw"], joint_inputs=owner)
    artifacts = {_sha(raw): raw for raw in TEMPLATES.values()}
    nodes, registry, children = [], [], []
    for index in range(4):
        kind = "leaf" if index < 3 else "role_synthesis"
        unit_id = fixture["manifest"]["units"][index]["unit_id"] if kind == "leaf" else None
        node_id, context_id = f"n{index}", f"ctx{index}"
        inputs = {"template": TEMPLATES[kind], "unit_id": unit_id} if kind == "leaf" else {
            "template": TEMPLATES[kind], "children": children,
            "child_artifacts": {child["artifact_sha256"]: artifacts[child["artifact_sha256"]] for child in children}}
        reserved = execution.reserve_attempt(root, node_id=node_id, node_kind=kind, context_id=context_id, render_inputs=inputs)
        assert execution.recover_pending_attempt(root)["prompt_bytes"] == reserved["prompt_bytes"]
        receipt = {"role_contract_sha256": _sha(_canonical(contract)), "template_sha256": _sha(TEMPLATES[kind]),
                   "rendered_prompt_sha256": reserved["prompt_sha256"], "input_sha256": reserved["input_sha256"],
                   "provider": contract["provider"], "model": contract["model"], "provider_version": contract["provider_version"],
                   "source_only": True, "truncated": False, "compaction_observed": False, "candidate_inputs": []}
        output = f"complete synthetic child artifact {index}".encode()
        execution.settle_attempt(root, reservation_id=reserved["reservation_id"], status="eligible", artifact_bytes=output, receipt=receipt)
        artifacts[_sha(output)] = output
        artifacts[reserved["prompt_sha256"]] = reserved["prompt_bytes"]
        nodes.append({"node_id": node_id, "kind": kind, "unit_id": unit_id, "children": [] if kind == "leaf" else list(children),
                      "context_id": context_id, "receipt": receipt, "artifact_sha256": _sha(output)})
        registry.append({"context_id": context_id, "node_id": node_id, "attempt": 1, "status": "eligible"})
        if kind == "leaf":
            children.append({"node_id": node_id, "artifact_sha256": _sha(output)})
        else:
            assert all(artifacts[c["artifact_sha256"]] in reserved["prompt_bytes"] for c in children)
    graph = {"schema_version": 2, "kind": graph_api.GRAPH_KIND, "accession_number": ACCESSION, "role": "role-a",
             "unit_manifest_sha256": _sha(_canonical(fixture["manifest"])), "role_contract_sha256": _sha(_canonical(contract)),
             "joint_contract_sha256": owner.contract_sha256, "nodes": nodes, "context_registry": registry,
             "limitations": list(graph_api.LIMITATIONS), **{flag: False for flag in graph_api.ATTESTATION_FLAGS}}
    inputs = {"accession_number": ACCESSION, "unit_manifest": fixture["manifest"], "expected_packets": fixture["packets"],
              "packet_bytes": fixture["raw"], "role_contract": contract, "artifacts": artifacts,
              "foreign_context_ids": [], "joint_inputs": owner}
    return execution.seal_history(root), graph, inputs


def test_joint_journal_graph_replay_rejects_downgrade_tamper_and_unversioned_delivery(tmp_path: Path) -> None:
    root = tmp_path / "journal"
    seal, graph, inputs = _complete(root)
    execution._SOURCE_CACHE = None
    execution._JOINT_CACHE = None
    validation = execution.validate_execution_binding(Path(seal["history_path"]), expected_history_sha256=seal["history_sha256"],
                                                       graph=graph, graph_validation_inputs=inputs)
    assert validation["schema_version"] == 2
    assert validation["exact_prompt_construction_verified"] is True
    assert all(validation[flag] is False for flag in graph_api.ATTESTATION_FLAGS)
    delivery_root = tmp_path / "delivery"
    delivery_root.mkdir()
    def forbidden_runner(_invocation: Any) -> Any:
        pytest.fail("v2 journal reached the v1 delivery subprocess boundary")
    with pytest.raises(ValueError, match="separately versioned delivery"):
        deliver_reserved_attempt(root, delivery_root, reservation_id="a" * 32, prompt_bytes=b"synthetic",
                                 cli_path="unused", environment={},
                                 limits={"max_stdin_bytes": 65536, "timeout_seconds": 30, "max_budget_usd": None},
                                 runner=forbidden_runner)
    assert list(delivery_root.iterdir()) == []
    for defect in ("input", "contract", "downgrade", "missing_joint"):
        bad = copy.deepcopy(graph)
        if defect == "input":
            bad["nodes"][2]["receipt"]["input_sha256"] = bad["nodes"][2]["unit_id"]
        elif defect == "contract":
            bad["joint_contract_sha256"] = "0" * 64
        elif defect == "downgrade":
            bad["schema_version"] = 1
        else:
            del bad["joint_contract_sha256"]
        with pytest.raises(ValueError):
            graph_api.validate_review_graph(bad, **inputs)
    legacy = copy.deepcopy(graph)
    legacy["schema_version"] = 1
    del legacy["joint_contract_sha256"]
    with pytest.raises(ValueError):
        graph_api.validate_review_graph(legacy, **{k: v for k, v in inputs.items() if k != "joint_inputs"})
    changed = _fixture()
    changed["joint"]["source_controls"]["handback_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="different frozen joint"):
        execution.validate_execution_binding(Path(seal["history_path"]), expected_history_sha256=seal["history_sha256"], graph=graph,
                                             graph_validation_inputs={**inputs, "joint_inputs": validate_h20_joint_inputs(**_args(changed))})
    path = root / "source" / "joint" / "contract.json"
    saved = path.read_bytes()
    path.write_bytes(saved + b"\n")
    try:
        with pytest.raises(ValueError, match="frozen joint contract changed"):
            execution.validate_execution_binding(Path(seal["history_path"]), expected_history_sha256=seal["history_sha256"],
                                                 graph=graph, graph_validation_inputs=inputs)
    finally:
        path.write_bytes(saved)
