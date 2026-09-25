"""Validate the custody of one role's multi-context source review graph.

This is an internal, non-admitting engineering format. For one role, it proves only that every
review unit of a validated unit manifest is bound to exactly one leaf; that leaves, reducers and the
single role synthesis form a tree whose child references match the children's artifact hashes; that
every node ran in its own registered, eligible context; that every receipt matches the frozen role
contract (node kind, template, provider, model and version) and the exact supplied bytes of its
template, rendered prompt and artifact; and that no receipt admits truncation, compaction or
candidate inputs. Failed, compacted, truncated and retired contexts stay in the context closure and
can never become eligible. Issues, evidence fragments and reconciliation are not validated, and
no review, E7 coverage status or admission is attested.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from evals.acceptance_source_units import validate_unit_manifest


SCHEMA_VERSION = 1
GRAPH_KIND = "e7_offline_source_review_graph"
CONTRACT_KIND = "e7_offline_source_role_contract"
VALIDATION_KIND = "e7_offline_source_review_graph_validation"
NODE_KINDS = ("leaf", "reducer", "role_synthesis")
CONTEXT_STATUSES = ("eligible", "failed", "compacted", "truncated", "retired")
# Any change to these strings, the flags, the node kinds, the statuses or any key set requires a new
# schema_version.
LIMITATIONS = (
    "Receipts are recorded declarations; the validator checks them against the frozen role contract and the supplied bytes, not that a provider actually ran them.",
    "Context freshness is proved only against this graph's registry and the caller-supplied context IDs of other roles, never provider-globally.",
    "Leaves bind whole review units; table grouping, modality dispositions and member linkage are validated by their own formats, not here.",
    "Issues, evidence fragments, reducer dispositions and reconciliation are not validated.",
    "No source review, E7 coverage_status or E7 admission is attested.",
)
ATTESTATION_FLAGS = (
    "semantic_review_attested",
    "issue_propagation_verified",
    "modality_completeness_attested",
    "admission_approved",
)

_ACCESSION = re.compile(r"[0-9]{10}-[0-9]{2}-[0-9]{6}")
_LABEL = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,127}")
_CONTEXT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CHILD_SET_TAG = b"e7-source-review-children-v1\x00"

_CONTRACT_KEYS = frozenset({
    "schema_version", "kind", "role", "node_kinds", "provider", "model", "provider_version", "exposure_limit",
})
_GRAPH_KEYS = frozenset({
    "schema_version", "kind", "accession_number", "role", "unit_manifest_sha256", "role_contract_sha256",
    "context_registry", "nodes", "limitations", *ATTESTATION_FLAGS,
})
_REGISTRY_KEYS = frozenset({"context_id", "node_id", "attempt", "status"})
_NODE_KEYS = frozenset({"node_id", "kind", "unit_id", "children", "context_id", "receipt", "artifact_sha256"})
_CHILD_KEYS = frozenset({"node_id", "artifact_sha256"})
_RECEIPT_KEYS = frozenset({
    "role_contract_sha256", "template_sha256", "rendered_prompt_sha256", "input_sha256", "provider", "model",
    "provider_version", "source_only", "truncated", "compaction_observed", "candidate_inputs",
})


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _object(value: Any, keys: frozenset[str], name: str) -> dict[str, Any]:
    if type(value) is not dict or any(type(key) is not str for key in value) or set(value) != keys:
        raise ValueError(f"{name} must be an object with exactly: {', '.join(sorted(keys))}")
    return value


def _token(value: Any, pattern: re.Pattern[str], name: str) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ValueError(f"invalid {name}")
    return value


def _list(value: Any, name: str) -> list[Any]:
    if type(value) is not list:
        raise ValueError(f"{name} must be a list")
    return value


def children_sha256(children: list[dict[str, str]]) -> str:
    """The input hash of a reducer or synthesis: its ordered child (node_id, artifact_sha256) list."""
    return _sha(_CHILD_SET_TAG + _canonical(children))


def validate_role_contract(contract: Any) -> str:
    """Validate one frozen role contract and return its SHA-256 (of its canonical JSON)."""
    _object(contract, _CONTRACT_KEYS, "role contract")
    if type(contract["schema_version"]) is not int or contract["schema_version"] != SCHEMA_VERSION \
            or type(contract["kind"]) is not str or contract["kind"] != CONTRACT_KIND:
        raise ValueError("unsupported role contract version or kind")
    _token(contract["role"], _LABEL, "contract role")
    _token(contract["provider"], _LABEL, "contract provider")
    _token(contract["model"], _LABEL, "contract model")
    version, limit = contract["provider_version"], contract["exposure_limit"]
    if version is None:
        # An unavailable immutable build is recorded as an explicit exposure limit, never inferred.
        _token(limit, _LABEL, "exposure_limit (required when provider_version is null)")
    else:
        _token(version, _CONTEXT_ID, "contract provider_version")
        if limit is not None:
            raise ValueError("exposure_limit must be null when provider_version is declared")
    kinds = contract["node_kinds"]
    if type(kinds) is not dict or not kinds or any(type(kind) is not str or kind not in NODE_KINDS for kind in kinds):
        raise ValueError(f"contract node_kinds must map allowed kinds ({', '.join(NODE_KINDS)}) to templates")
    for kind in ("leaf", "role_synthesis"):
        if kind not in kinds:
            raise ValueError(f"contract must allow {kind} nodes")
    for kind, declaration in kinds.items():
        _object(declaration, frozenset({"template_sha256"}), f"{kind} template declaration")
        _token(declaration["template_sha256"], _SHA256, f"{kind} template_sha256")
    return _sha(_canonical(contract))


def _registry(value: Any, foreign: set[str]) -> dict[str, dict[str, Any]]:
    """Append-only attempt history: unique context IDs and consecutive attempts per node from 1."""
    entries: dict[str, dict[str, Any]] = {}
    attempts: dict[str, int] = {}
    for entry in _list(value, "context_registry"):
        _object(entry, _REGISTRY_KEYS, "context registry entry")
        context_id = _token(entry["context_id"], _CONTEXT_ID, "context_id")
        node_id = _token(entry["node_id"], _LABEL, "registry node_id")
        if type(entry["attempt"]) is not int or entry["attempt"] != attempts.get(node_id, 0) + 1:
            raise ValueError(f"node {node_id} attempts must be consecutive from 1 in registry order")
        if type(entry["status"]) is not str or entry["status"] not in CONTEXT_STATUSES:
            raise ValueError(f"context status must be one of: {', '.join(CONTEXT_STATUSES)}")
        if context_id in entries:
            raise ValueError(f"context {context_id} is registered more than once")
        if context_id in foreign:
            raise ValueError(f"context {context_id} is already used by another role")
        attempts[node_id] = entry["attempt"]
        entries[context_id] = entry
    return entries


def validate_review_graph(
    graph: Any,
    *,
    accession_number: Any,
    expected_packets: Any,
    packet_bytes: Any,
    unit_manifest: Any,
    role_contract: Any,
    artifacts: Any,
    foreign_context_ids: Any,
) -> dict[str, Any]:
    """Recompute every custody check for one role's review graph; never repair or reorder.

    ``expected_packets`` must come from the frozen source contract. ``artifacts`` maps SHA-256 to the
    exact bytes of every template, rendered prompt and node artifact the graph references, and nothing
    else. ``foreign_context_ids`` lists the context IDs registered by the other roles for this
    accession, so a context cannot be shared across roles.
    """
    manifest = validate_unit_manifest(unit_manifest, accession_number=accession_number,
                                      expected_packets=expected_packets, packet_bytes=packet_bytes)
    contract_sha256 = validate_role_contract(role_contract)
    if type(foreign_context_ids) is not list or any(type(item) is not str for item in foreign_context_ids):
        raise ValueError("foreign_context_ids must be a list of context IDs")
    if type(artifacts) is not dict or any(type(key) is not str or type(data) is not bytes
                                          for key, data in artifacts.items()):
        raise ValueError("artifacts must map SHA-256 strings to immutable bytes")
    for digest, data in artifacts.items():
        if _sha(data) != digest:
            raise ValueError(f"artifact {digest} bytes do not match their SHA-256")

    _object(graph, _GRAPH_KEYS, "source review graph")
    if type(graph["schema_version"]) is not int or graph["schema_version"] != SCHEMA_VERSION \
            or type(graph["kind"]) is not str or graph["kind"] != GRAPH_KIND:
        raise ValueError("unsupported source review graph version or kind")
    if any(graph[flag] is not False for flag in ATTESTATION_FLAGS):
        raise ValueError("a source review graph cannot attest review, completeness or admission")
    limitations = graph["limitations"]
    if type(limitations) is not list or any(type(item) is not str for item in limitations) or limitations != list(LIMITATIONS):
        raise ValueError("source review graph limitations differ from this format")
    if type(graph["accession_number"]) is not str or graph["accession_number"] != manifest["accession_number"]:
        raise ValueError("source review graph declares a different accession")
    if type(graph["role"]) is not str or graph["role"] != role_contract["role"]:
        raise ValueError("source review graph role differs from the role contract")
    if type(graph["unit_manifest_sha256"]) is not str or graph["unit_manifest_sha256"] != manifest["manifest_sha256"]:
        raise ValueError("source review graph is bound to a different unit manifest")
    if type(graph["role_contract_sha256"]) is not str or graph["role_contract_sha256"] != contract_sha256:
        raise ValueError("source review graph is bound to a different role contract")

    registry = _registry(graph["context_registry"], set(foreign_context_ids))
    final_attempt: dict[str, str] = {}
    for context_id, entry in registry.items():
        final_attempt[entry["node_id"]] = context_id
    units = {unit["unit_id"]: unit for unit in unit_manifest["units"]}

    nodes = _list(graph["nodes"], "nodes")
    if not nodes:
        raise ValueError("a review graph needs at least one node")
    seen: dict[str, dict[str, Any]] = {}
    parents: dict[str, str] = {}
    used_contexts: set[str] = set()
    leaf_units: dict[str, str] = {}
    referenced: set[str] = set()
    for position, node in enumerate(nodes):
        _object(node, _NODE_KEYS, "review node")
        node_id = _token(node["node_id"], _LABEL, "node_id")
        if node_id in seen:
            raise ValueError(f"duplicate node_id {node_id}")
        kind = node["kind"]
        if type(kind) is not str or kind not in NODE_KINDS:
            raise ValueError(f"node {node_id} kind must be one of: {', '.join(NODE_KINDS)}")
        if kind not in role_contract["node_kinds"]:
            raise ValueError(f"node {node_id} kind {kind} is not allowed by the role contract")
        if (kind == "role_synthesis") != (position == len(nodes) - 1):
            raise ValueError("exactly one role_synthesis node is required, and it must be last")
        artifact = _token(node["artifact_sha256"], _SHA256, f"node {node_id} artifact_sha256")

        children = _list(node["children"], f"node {node_id} children")
        if kind == "leaf":
            if children:
                raise ValueError(f"leaf {node_id} cannot have children")
            unit_id = _token(node["unit_id"], _SHA256, f"leaf {node_id} unit_id")
            if unit_id not in units:
                raise ValueError(f"leaf {node_id} names a unit outside the unit manifest")
            if unit_id in leaf_units:
                raise ValueError(f"unit {unit_id} is bound to leaves {leaf_units[unit_id]} and {node_id}")
            leaf_units[unit_id] = node_id
            expected_input = units[unit_id]["unit_sha256"]
        else:
            if node["unit_id"] is not None:
                raise ValueError(f"{kind} {node_id} cannot bind a unit directly")
            if not children:
                raise ValueError(f"{kind} {node_id} needs at least one child")
            for child in children:
                _object(child, _CHILD_KEYS, f"node {node_id} child")
                child_id = child["node_id"]
                # Children must precede their parent, which also excludes cycles.
                if type(child_id) is not str or child_id not in seen:
                    raise ValueError(f"node {node_id} names a missing or later child")
                if type(child["artifact_sha256"]) is not str or child["artifact_sha256"] != seen[child_id]["artifact_sha256"]:
                    raise ValueError(f"node {node_id} child {child_id} artifact hash does not match the child")
                if child_id in parents:
                    raise ValueError(f"node {child_id} has two parents: {parents[child_id]} and {node_id}")
                parents[child_id] = node_id
            expected_input = children_sha256(children)

        context_id = _token(node["context_id"], _CONTEXT_ID, f"node {node_id} context_id")
        entry = registry.get(context_id)
        if entry is None or entry["node_id"] != node_id:
            raise ValueError(f"node {node_id} context {context_id} is not registered for this node")
        if entry["status"] != "eligible":
            raise ValueError(f"node {node_id} context {context_id} is {entry['status']} and cannot be eligible")
        if final_attempt[node_id] != context_id:
            raise ValueError(f"node {node_id} must use its latest registered attempt")
        if context_id in used_contexts:
            raise ValueError(f"context {context_id} is reused")
        used_contexts.add(context_id)

        receipt = _object(node["receipt"], _RECEIPT_KEYS, f"node {node_id} receipt")
        declared = role_contract["node_kinds"][kind]["template_sha256"]
        for field, value in (("role_contract_sha256", contract_sha256), ("template_sha256", declared),
                             ("input_sha256", expected_input), ("provider", role_contract["provider"]),
                             ("model", role_contract["model"]),
                             ("provider_version", role_contract["provider_version"])):
            if type(receipt[field]) is not type(value) or receipt[field] != value:
                raise ValueError(f"node {node_id} receipt {field} does not match")
        _token(receipt["rendered_prompt_sha256"], _SHA256, f"node {node_id} rendered_prompt_sha256")
        if receipt["source_only"] is not True or receipt["truncated"] is not False \
                or receipt["compaction_observed"] is not False:
            raise ValueError(f"node {node_id} receipt must be source_only with no truncation or compaction")
        if type(receipt["candidate_inputs"]) is not list or receipt["candidate_inputs"]:
            raise ValueError(f"node {node_id} receipt must have no candidate inputs")
        referenced.update((declared, receipt["rendered_prompt_sha256"], artifact))
        seen[node_id] = node

    root = nodes[-1]["node_id"]
    orphans = [node_id for node_id in seen if node_id != root and node_id not in parents]
    if orphans:
        raise ValueError("nodes are not reachable from the role synthesis: " + ", ".join(orphans))
    missing_units = [unit_id for unit_id in units if unit_id not in leaf_units]
    if missing_units:
        raise ValueError(f"{len(missing_units)} review units have no leaf, starting with {missing_units[0]}")
    unused = [context_id for context_id, entry in registry.items()
              if entry["status"] == "eligible" and context_id not in used_contexts]
    if unused:
        raise ValueError("eligible contexts are not used by any node: " + ", ".join(unused))
    if set(artifacts) != referenced:
        missing = sorted(referenced - set(artifacts))
        raise ValueError(("artifacts missing: " + ", ".join(missing)) if missing
                         else "artifacts include bytes the graph does not reference")

    counts = {kind: sum(1 for node in nodes if node["kind"] == kind) for kind in NODE_KINDS}
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": VALIDATION_KIND,
        "graph_sha256": _sha(_canonical(graph)),
        "accession_number": manifest["accession_number"],
        "role": role_contract["role"],
        "unit_manifest_sha256": manifest["manifest_sha256"],
        "role_contract_sha256": contract_sha256,
        "node_counts": counts,
        "root_artifact_sha256": nodes[-1]["artifact_sha256"],
        # Every registered context, including failed, compacted, truncated and retired ones.
        "source_context_closure": list(registry),
        "ineligible_context_ids": [context_id for context_id, entry in registry.items() if entry["status"] != "eligible"],
        "frozen_artifact_sha256s": sorted(referenced),
        "every_unit_bound_to_one_leaf": True,
        **{flag: False for flag in ATTESTATION_FLAGS},
        "limitations": list(LIMITATIONS),
    }


def load_review_graph(raw: Any) -> dict[str, Any]:
    """Parse stored graph bytes, requiring exactly ``canonical_json(graph)``."""
    if type(raw) is not bytes:
        raise ValueError("stored source review graph must be bytes")
    try:
        graph = json.loads(raw.decode("ascii"))
        canonical = _canonical(graph)
    except (UnicodeDecodeError, ValueError, TypeError, RecursionError) as exc:
        raise ValueError("stored source review graph is not canonical JSON") from exc
    if canonical != raw or type(graph) is not dict:
        raise ValueError("stored source review graph is not canonical JSON")
    return graph
