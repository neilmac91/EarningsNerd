"""A role's review graph binds every unit, context and receipt; nothing ineligible becomes eligible."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

import pytest

from evals.acceptance_source_review_graph import load_review_graph, validate_review_graph
from evals.acceptance_source_units import build_unit_manifest


ACCESSION = "0000000000-26-000001"
PRIMARY = b"<p>Revenue rose.</p><p>Margins fell.</p><p>Guidance held.</p>"
PACKETS = [{"role": "primary", "sha256": hashlib.sha256(PRIMARY).hexdigest(), "byte_length": len(PRIMARY)}]
CUTS = (0, PRIMARY.index(b"<p>Margins"), PRIMARY.index(b"<p>Guidance"), len(PRIMARY))
MANIFEST = build_unit_manifest(
    accession_number=ACCESSION, packets=PACKETS, packet_bytes={"primary": PRIMARY},
    units=[{"packet_role": "primary", "structural_kind": "text", "registrant_scope": "registrant",
            "coverage_spans": [{"start": start, "end": end}], "context_spans": []}
           for start, end in zip(CUTS, CUTS[1:])])
UNITS = MANIFEST["units"]
TEMPLATES = {kind: f"template:{kind}".encode() for kind in ("leaf", "reducer", "role_synthesis")}
FLAGS = ("semantic_review_attested", "issue_propagation_verified", "modality_completeness_attested",
         "admission_approved")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


# Independent reimplementation of the documented child-set hash; it imports no module helper.
def children_sha256(children: list[dict[str, str]]) -> str:
    return _sha(b"e7-source-review-children-v1\x00" + _canonical(children))


CONTRACT = {
    "schema_version": 1, "kind": "e7_offline_source_role_contract", "role": "role-b",
    "node_kinds": {kind: {"template_sha256": _sha(data)} for kind, data in TEMPLATES.items()},
    "provider": "example-provider", "model": "example-model-1", "provider_version": "2026-09-01",
    "exposure_limit": None,
}
# (node_id, kind, unit index or child node_ids). L1's first context was compacted and retried.
SHAPE = [("l1", "leaf", 0), ("l2", "leaf", 1), ("r1", "reducer", ["l1", "l2"]), ("l3", "leaf", 2),
         ("s", "role_synthesis", ["r1", "l3"])]
REGISTRY = [
    {"context_id": "prior-b-1", "node_id": "legacy-b", "attempt": 1, "status": "retired"},
    {"context_id": "ctx-l1-a", "node_id": "l1", "attempt": 1, "status": "compacted"},
    {"context_id": "ctx-l1-b", "node_id": "l1", "attempt": 2, "status": "eligible"},
    {"context_id": "ctx-l2", "node_id": "l2", "attempt": 1, "status": "eligible"},
    {"context_id": "ctx-r1", "node_id": "r1", "attempt": 1, "status": "eligible"},
    {"context_id": "ctx-l3", "node_id": "l3", "attempt": 1, "status": "eligible"},
    {"context_id": "ctx-s", "node_id": "s", "attempt": 1, "status": "eligible"},
]
CONTEXT = {"l1": "ctx-l1-b", "l2": "ctx-l2", "r1": "ctx-r1", "l3": "ctx-l3", "s": "ctx-s"}


def _graph(shape: list[tuple[str, str, Any]] = SHAPE, contexts: dict[str, str] | None = None,
           registry: list[dict[str, Any]] | None = None,
           contract: dict[str, Any] = CONTRACT) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Assemble a graph whose receipts, child references and artifacts are all consistent."""
    contexts = CONTEXT if contexts is None else contexts
    artifacts = {_sha(data): data for data in TEMPLATES.values()}
    nodes, hashes = [], {}
    for node_id, kind, target in shape:
        children = [] if kind == "leaf" else [{"node_id": child, "artifact_sha256": hashes[child]} for child in target]
        artifact, prompt = f"artifact:{node_id}".encode(), f"prompt:{node_id}".encode()
        artifacts.update({_sha(artifact): artifact, _sha(prompt): prompt})
        hashes[node_id] = _sha(artifact)
        nodes.append({
            "node_id": node_id, "kind": kind, "unit_id": UNITS[target]["unit_id"] if kind == "leaf" else None,
            "children": children, "context_id": contexts[node_id], "artifact_sha256": _sha(artifact),
            "receipt": {
                "role_contract_sha256": _sha(_canonical(contract)), "template_sha256": _sha(TEMPLATES[kind]),
                "rendered_prompt_sha256": _sha(prompt),
                "input_sha256": UNITS[target]["unit_id"] if kind == "leaf" else children_sha256(children),
                "provider": contract["provider"], "model": contract["model"],
                "provider_version": contract["provider_version"], "source_only": True, "truncated": False,
                "compaction_observed": False, "candidate_inputs": [],
            },
        })
    graph = {
        "schema_version": 1, "kind": "e7_offline_source_review_graph", "accession_number": ACCESSION,
        "role": "role-b", "unit_manifest_sha256": _sha(_canonical(MANIFEST)),
        "role_contract_sha256": _sha(_canonical(contract)),
        "context_registry": copy.deepcopy(REGISTRY if registry is None else registry), "nodes": nodes,
        **{flag: False for flag in FLAGS},
        "limitations": [
            "Receipts are recorded declarations; the validator checks them against the frozen role contract and the supplied bytes, not that a provider actually ran them.",
            "Context freshness is proved only against this graph's registry and the caller-supplied context IDs of other roles, never provider-globally.",
            "Leaves bind whole review units; table grouping, modality dispositions and member linkage are validated by their own formats, not here.",
            "Issues, evidence fragments, reducer dispositions and reconciliation are not validated.",
            "No source review, E7 coverage_status or E7 admission is attested.",
        ],
    }
    return graph, artifacts


def _validate(graph: Any, artifacts: Any, **overrides: Any) -> dict[str, Any]:
    arguments = {"accession_number": ACCESSION, "expected_packets": PACKETS, "packet_bytes": {"primary": PRIMARY},
                 "unit_manifest": MANIFEST, "role_contract": CONTRACT, "artifacts": artifacts,
                 "foreign_context_ids": ["ctx-a-1", "ctx-a-2"]}
    arguments.update(overrides)
    return validate_review_graph(graph, **arguments)


def _rejected(graph: Any, artifacts: Any, message: str, **overrides: Any) -> None:
    before = copy.deepcopy(graph)
    with pytest.raises(ValueError, match=message):
        _validate(graph, artifacts, **overrides)
    assert graph == before, "validation must not repair or reorder a rejected graph"


def _edited(graph: dict[str, Any], node_id: str, path: tuple[str, ...], value: Any) -> dict[str, Any]:
    changed = copy.deepcopy(graph)
    target = next(node for node in changed["nodes"] if node["node_id"] == node_id)
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return changed


def test_every_node_runs_in_its_own_latest_eligible_context() -> None:
    graph, artifacts = _graph()
    summary = _validate(load_review_graph(_canonical(graph)), artifacts)
    assert summary == {
        "schema_version": 1,
        "kind": "e7_offline_source_review_graph_validation",
        "graph_sha256": _sha(_canonical(graph)),
        "accession_number": ACCESSION,
        "role": "role-b",
        "unit_manifest_sha256": _sha(_canonical(MANIFEST)),
        "role_contract_sha256": _sha(_canonical(CONTRACT)),
        "node_counts": {"leaf": 3, "reducer": 1, "role_synthesis": 1},
        "root_artifact_sha256": _sha(b"artifact:s"),
        # Failed, compacted, truncated and retired contexts stay in the closure but are never eligible.
        "source_context_closure": [entry["context_id"] for entry in REGISTRY],
        "ineligible_context_ids": ["prior-b-1", "ctx-l1-a"],
        "frozen_artifact_sha256s": sorted(artifacts),
        "every_unit_bound_to_one_leaf": True,
        **{flag: False for flag in FLAGS},
        "limitations": graph["limitations"],
    }

    # The compacted first attempt cannot be used, and neither can any earlier attempt of a node.
    _rejected(_graph(contexts={**CONTEXT, "l1": "ctx-l1-a"})[0], artifacts, "ctx-l1-a is compacted and cannot be eligible")
    reordered = copy.deepcopy(REGISTRY)
    reordered[1]["status"], reordered[2]["status"] = "eligible", "failed"
    _rejected(_graph(contexts={**CONTEXT, "l1": "ctx-l1-a"}, registry=reordered)[0], artifacts,
              "l1 must use its latest registered attempt")
    for status in ("failed", "truncated", "retired"):
        registry = copy.deepcopy(REGISTRY)
        registry[4]["status"] = status
        _rejected(_graph(registry=registry)[0], artifacts, f"ctx-r1 is {status} and cannot be eligible")

    # A context is used once, by the node it is registered for, and never shared with another role.
    _rejected(_graph(contexts={**CONTEXT, "l2": "ctx-l3"})[0], artifacts, "ctx-l3 is not registered for this node")
    _rejected(graph, artifacts, "ctx-l2 is already used by another role", foreign_context_ids=["ctx-l2"])
    _rejected(graph, artifacts, "prior-b-1 is already used by another role", foreign_context_ids=["prior-b-1"])
    duplicate = [*REGISTRY, {**REGISTRY[3], "node_id": "l9", "attempt": 1}]
    _rejected(_graph(registry=duplicate)[0], artifacts, "ctx-l2 is registered more than once")
    skipped = copy.deepcopy(REGISTRY)
    skipped[2]["attempt"] = 3
    _rejected(_graph(registry=skipped)[0], artifacts, "l1 attempts must be consecutive from 1")
    unused = [*REGISTRY, {"context_id": "ctx-spare", "node_id": "l3", "attempt": 2, "status": "eligible"}]
    _rejected(_graph(registry=unused)[0], artifacts, "l3 must use its latest registered attempt")
    idle = [*REGISTRY, {"context_id": "ctx-idle", "node_id": "l8", "attempt": 1, "status": "eligible"}]
    _rejected(_graph(registry=idle)[0], artifacts, "eligible contexts are not used by any node: ctx-idle")

    # A receipt admitting truncation, compaction, candidate inputs or non-source input is rejected.
    for field, value in (("truncated", True), ("compaction_observed", True), ("source_only", False),
                         ("candidate_inputs", ["candidate-a"]), ("truncated", 0)):
        expected = "no candidate inputs" if field == "candidate_inputs" else "source_only with no truncation"
        _rejected(_edited(graph, "l2", ("receipt", field), value), artifacts, expected)


def test_graph_structure_and_receipts_are_bound_to_frozen_bytes() -> None:
    graph, artifacts = _graph()
    _validate(graph, artifacts)

    # Every unit is bound to exactly one leaf; the tree is complete, acyclic and single-rooted.
    _rejected(_graph(shape=[SHAPE[0], SHAPE[1], SHAPE[2], ("s", "role_synthesis", ["r1"])])[0], artifacts,
              "1 review units have no leaf")
    _rejected(_graph(shape=[SHAPE[0], ("l2", "leaf", 0), *SHAPE[2:]])[0], artifacts, "is bound to leaves l1 and l2")
    _rejected(_edited(graph, "r1", ("children",), [{"node_id": "l3", "artifact_sha256": _sha(b"artifact:l3")}]),
              artifacts, "r1 names a missing or later child")
    _rejected(_edited(graph, "r1", ("children",), []), artifacts, "reducer r1 needs at least one child")
    _rejected(_graph(shape=[*SHAPE[:4], ("s", "role_synthesis", ["r1", "l3", "l1"])])[0], artifacts,
              "l1 has two parents: r1 and s")
    _rejected(_graph(shape=[*SHAPE[:4], ("s", "role_synthesis", ["r1"])])[0], artifacts,
              "not reachable from the role synthesis: l3")
    _rejected(_graph(shape=[*SHAPE[:2], ("r1", "role_synthesis", ["l1", "l2"]), SHAPE[3],
                            ("s", "role_synthesis", ["r1", "l3"])])[0], artifacts, "exactly one role_synthesis")
    _rejected(_edited(graph, "l3", ("unit_id",), _sha(b"foreign-unit")), artifacts, "outside the unit manifest")

    # A parent binds its children's exact artifact hashes, and every artifact byte is supplied.
    _rejected(_edited(graph, "s", ("children", 1, "artifact_sha256"), _sha(b"artifact:l3-v2")), artifacts,
              "s child l3 artifact hash does not match the child")
    changed = dict(artifacts)
    changed[_sha(b"artifact:l2")] = b"artifact:l2-edited"
    _rejected(graph, changed, "bytes do not match their SHA-256")
    _rejected(graph, {k: v for k, v in artifacts.items() if k != _sha(b"prompt:l2")}, "artifacts missing")
    _rejected(graph, {**artifacts, _sha(b"extra"): b"extra"}, "bytes the graph does not reference")

    # Receipts must match the frozen role contract and the node's own inputs.
    for field, value in (("model", "example-model-2"), ("provider", "other-provider"),
                         ("provider_version", "2026-10-01"), ("provider_version", None),
                         ("template_sha256", _sha(b"template:alternate")),
                         ("role_contract_sha256", _sha(b"other-contract")),
                         ("input_sha256", UNITS[0]["unit_id"]), ("input_sha256", UNITS[1]["unit_sha256"])):
        _rejected(_edited(graph, "l2", ("receipt", field), value), artifacts, f"l2 receipt {field} does not match")
    _rejected(_edited(graph, "r1", ("receipt", "input_sha256"), children_sha256([])), artifacts,
              "r1 receipt input_sha256 does not match")
    no_reducers = {**CONTRACT, "node_kinds": {k: v for k, v in CONTRACT["node_kinds"].items() if k != "reducer"}}
    _rejected(_graph(contract=no_reducers)[0], artifacts, "r1 kind reducer is not allowed by the role contract",
              role_contract=no_reducers)

    # Node shapes are exact, and a node's output cannot alias another output, a template or a prompt.
    _rejected(_edited(graph, "l1", ("children",), [{"node_id": "l2", "artifact_sha256": _sha(b"artifact:l2")}]),
              artifacts, "leaf l1 cannot have children")
    _rejected(_edited(graph, "r1", ("unit_id",), UNITS[0]["unit_id"]), artifacts, "reducer r1 cannot bind a unit")
    _rejected({**graph, "nodes": [graph["nodes"][0], *graph["nodes"]]}, artifacts, "duplicate node_id l1")
    _rejected({**graph, "nodes": []}, artifacts, "at least one node")
    for value in (_sha(b"artifact:l1"), _sha(TEMPLATES["leaf"]), _sha(b"prompt:l2")):
        _rejected(_edited(graph, "l2", ("artifact_sha256",), value), artifacts, "l2 artifact must be distinct")
    for key, value, message in (
        ("accession_number", "0000000000-26-000002", "different accession"),
        ("role", "role-a", "role differs from the role contract"),
        ("unit_manifest_sha256", _sha(b"other"), "different unit manifest"),
        ("admission_approved", True, "cannot attest"),
        ("limitations", graph["limitations"][:-1], "limitations differ"),
        ("coverage_status", "complete", "must be an object with exactly"),
    ):
        _rejected({**graph, key: value}, artifacts, message)

    # An unavailable immutable build is an explicit exposure limit, never inferred.
    unversioned = {**CONTRACT, "provider_version": None, "exposure_limit": "provider_build_not_exposed"}
    limited, limited_artifacts = _graph(contract=unversioned)
    _validate(limited, limited_artifacts, role_contract=unversioned)
    _rejected(_edited(limited, "l1", ("receipt", "provider_version"), "2026-09-01"), limited_artifacts,
              "l1 receipt provider_version does not match", role_contract=unversioned)
    for contract, message in (({**unversioned, "exposure_limit": None}, "exposure_limit"),
                              ({**CONTRACT, "exposure_limit": "not_exposed"}, "exposure_limit must be null")):
        with pytest.raises(ValueError, match=message):
            _validate(graph, artifacts, role_contract=contract)
    for variant in (json.dumps(graph, indent=2).encode("ascii"), _canonical(graph) + b"\n", b"[]"):
        with pytest.raises(ValueError, match="not canonical JSON"):
            load_review_graph(variant)
    with pytest.raises(ValueError, match="must be bytes"):
        load_review_graph(_canonical(graph).decode("ascii"))


class _Text(str):
    pass


@pytest.mark.parametrize(("change", "message"), [
    ({"schema_version": True}, "unsupported role contract"),
    ({"kind": "e7_offline_source_role_contract_v2"}, "unsupported role contract"),
    ({"role": "Role B"}, "invalid contract role"),
    ({"model": _Text("example-model-1")}, "invalid contract model"),
    ({"node_kinds": {**CONTRACT["node_kinds"], "critic": {"template_sha256": "0" * 64}}}, "must map allowed kinds"),
    ({"node_kinds": {_Text("leaf"): CONTRACT["node_kinds"]["leaf"],
                     "role_synthesis": CONTRACT["node_kinds"]["role_synthesis"]}}, "must map allowed kinds"),
    ({"node_kinds": {"leaf": CONTRACT["node_kinds"]["leaf"]}}, "must allow role_synthesis"),
    ({"node_kinds": {"role_synthesis": CONTRACT["node_kinds"]["role_synthesis"]}}, "must allow leaf"),
    ({"node_kinds": {**CONTRACT["node_kinds"], "leaf": {"template_sha256": "A" * 64}}}, "invalid leaf template"),
    ({"node_kinds": {**CONTRACT["node_kinds"], "leaf": {"template_sha256": "0" * 64, "prompt": "x"}}},
     "leaf template declaration must be an object"),
    ({"provider_version": 20260901}, "invalid contract provider_version"),
])
def test_malformed_role_contracts_are_rejected(change: dict[str, Any], message: str) -> None:
    graph, artifacts = _graph()
    contract = {**CONTRACT, **change}
    with pytest.raises(ValueError, match=message):
        _validate(graph, artifacts, role_contract=contract)
