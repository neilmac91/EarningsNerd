"""Reviewed authority for retrospective legacy source-review custody.

This validates retained bytes. It does not assert provider-global completeness,
pre-dispatch journal chronology, financial correctness, or programme admission.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_AUTHORITY_KEYS = frozenset({
    "schema_version", "kind", "approved_manifest_sha256", "accession_number", "scope",
    "origin_contexts", "attempts", "limitations", "admission_authority",
    "semantic_resolution_authority",
})
_ORIGIN_KEYS = frozenset({
    "context_id", "role", "status", "history_prefix", "artifact_sha256", "artifact",
})
_ATTEMPT_KEYS = frozenset({
    "context_id", "role", "status", "reservation", "dispatch", "settlement",
    "settlement_artifacts", "successor_reservation",
})
_LIMITATIONS = [
    "Retrospective declaration of the operator-retained legacy custody set at migration; "
    "not provider-global completeness.",
    "No assertion of pre-dispatch journal chronology, private model attention, or unretained "
    "attempts.",
    "Custody verification does not establish financial correctness, semantic resolution, or "
    "programme admission.",
]

# The digest is reviewed code authority. The prerequisite supplies only a location.
APPROVED_LEGACY_HISTORY_AUTHORITIES: dict[str, dict[str, str]] = {
    "68242a2c1c57da8d445bc4e1aca104017cffaffe8bbebf131228cde8ea94ba66": {
        "0001104659-25-086034":
            "836403b0b85d0a6169d6ab49aedfe99442ceccb159f9084aaa5d6b29219678c6",
    },
}


def _reference(root: Path, record: Any) -> tuple[dict[str, Any], dict[str, Any] | None]:
    from evals.acceptance_readiness import _evidence, _sha256

    if (not isinstance(record, dict) or set(record) != {"path", "sha256"} or
            not isinstance(record.get("sha256"), str) or
            _SHA256.fullmatch(record["sha256"]) is None):
        raise ValueError("legacy authority artifact reference invalid")
    path, value = _evidence(root, record)
    return {
        "record": record,
        "resolved_path": str(path.resolve(strict=True)),
        "bytes_sha256": _sha256(path),
    }, value


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                       allow_nan=False).encode("ascii") + b"\n")


def _identity(
    accession: str, attempt: dict[str, Any], children: list[dict[str, Any]],
) -> tuple[Any, ...]:
    return (
        accession, attempt["context_id"], attempt["role"], attempt["status"],
        attempt["reservation"]["sha256"], attempt["dispatch"]["sha256"],
        attempt["settlement"]["sha256"],
        tuple((child["basename"], child["sha256"]) for child in children),
    )


def resolve_legacy_history_authorities(
    root: Path, approved_manifest_sha256: Any, ai: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Resolve the reviewed legacy registry before any optional wrapper branch."""
    from evals.acceptance_readiness import _json, _safe_file, _sha256
    from evals.acceptance_source_review_graph import validate_source_context_id

    registry = APPROVED_LEGACY_HISTORY_AUTHORITIES.get(approved_manifest_sha256)
    known_accessions = {
        accession
        for manifest_registry in APPROVED_LEGACY_HISTORY_AUTHORITIES.values()
        for accession in manifest_registry
    }
    observed_accessions = {
        row.get("accession_number")
        for key in ("source_briefs", "reconciled_references", "reconciliation_history")
        for row in ai.get(key, [])
        if isinstance(row, dict)
    }
    locations_present = "legacy_history_authorities" in ai
    history_present = "reconciliation_history" in ai
    registered_accession_present = bool(observed_accessions & known_accessions)
    if registry is None:
        if locations_present or history_present or registered_accession_present:
            raise ValueError("legacy history manifest is not registered")
        return {}

    locations = ai.get("legacy_history_authorities")
    if not isinstance(locations, list) or not locations:
        raise ValueError("registered legacy history authority location missing")
    if any(not isinstance(row, dict) or set(row) != {"accession_number", "path"}
           for row in locations):
        raise ValueError("legacy history authority location invalid")
    declared = [row["accession_number"] for row in locations]
    if (len(declared) != len(set(declared)) or set(declared) != set(registry) or
            any(not isinstance(row["path"], str) or not row["path"] for row in locations)):
        raise ValueError("legacy history authority accession set differs")

    resolved: dict[str, dict[str, Any]] = {}
    all_contexts: set[str] = set()
    all_context_owners: dict[str, str] = {}
    for location in locations:
        accession = location["accession_number"]
        path = _safe_file(root, location["path"])
        expected_sha256 = registry[accession]
        if _sha256(path) != expected_sha256:
            raise ValueError("legacy history authority digest differs from reviewed code")
        authority = _json(path)
        if path.read_bytes() != _canonical_bytes(authority):
            raise ValueError("legacy history authority is not canonical JSON")
        if (set(authority) != _AUTHORITY_KEYS or
                type(authority.get("schema_version")) is not int or
                authority["schema_version"] != 1 or
                authority.get("kind") != "legacy_custody_migration" or
                authority.get("approved_manifest_sha256") != approved_manifest_sha256 or
                authority.get("accession_number") != accession or
                authority.get("scope") != "retrospective_retained_custody" or
                authority.get("limitations") != _LIMITATIONS or
                authority.get("admission_authority") is not False or
                authority.get("semantic_resolution_authority") is not False or
                not isinstance(authority.get("origin_contexts"), list) or
                not authority["origin_contexts"] or
                not isinstance(authority.get("attempts"), list) or
                not authority["attempts"]):
            raise ValueError("legacy history authority shape or scope invalid")

        identities: set[tuple[Any, ...]] = set()
        contexts: set[str] = set()
        origin_identities: set[tuple[Any, ...]] = set()
        origin_inventory: list[dict[str, Any]] = []
        for origin in authority["origin_contexts"]:
            if (not isinstance(origin, dict) or set(origin) != _ORIGIN_KEYS or
                    origin.get("role") not in {
                        "source_reference_a", "source_reference_b", "source_reconciliation"} or
                    origin.get("status") != "retired_partial_history" or
                    not isinstance(origin.get("history_prefix"), str) or
                    not origin["history_prefix"] or
                    not isinstance(origin.get("artifact_sha256"), str) or
                    _SHA256.fullmatch(origin["artifact_sha256"]) is None or
                    not isinstance(origin.get("artifact"), dict) or
                    origin["artifact"].get("sha256") != origin["artifact_sha256"]):
                raise ValueError("legacy history origin shape invalid")
            context_id = validate_source_context_id(
                origin.get("context_id"), "legacy origin context_id")
            identity = (
                accession, context_id, origin["role"], origin["status"],
                origin["history_prefix"], origin["artifact_sha256"],
            )
            if (identity in origin_identities or context_id in contexts or
                    context_id in all_contexts or
                    all_context_owners.get(context_id, accession) != accession):
                raise ValueError("legacy history origin identity invalid or reused")
            reference, value = _reference(root, origin["artifact"])
            if value is None:
                raise ValueError("legacy history origin artifact must be JSON")
            origin_identities.add(identity)
            contexts.add(context_id)
            all_contexts.add(context_id)
            all_context_owners[context_id] = accession
            origin_inventory.append({"context_id": context_id, "artifact": reference})

        attempt_inventory: list[dict[str, Any]] = []
        successor_contexts: set[str] = set()
        for attempt in authority["attempts"]:
            if not isinstance(attempt, dict) or set(attempt) != _ATTEMPT_KEYS:
                raise ValueError("legacy history attempt shape invalid")
            context_id = validate_source_context_id(
                attempt.get("context_id"), "legacy history context_id")
            if (context_id in contexts or context_id in all_contexts or
                    all_context_owners.get(context_id, accession) != accession or
                    attempt.get("role") not in {"source_reference_a", "source_reference_b"} or
                    attempt.get("status") != "partial_ineligible"):
                raise ValueError("legacy history attempt identity invalid or reused")
            children = attempt.get("settlement_artifacts")
            if (not isinstance(children, list) or
                    [child.get("basename") for child in children if isinstance(child, dict)] !=
                    ["brief.md", "draft.json", "read-log.json"] or
                    any(not isinstance(child, dict) or
                        set(child) != {"basename", "path", "sha256"} or
                        Path(child["path"]).name != child["basename"]
                        for child in children)):
                raise ValueError("legacy history settlement artifacts invalid")

            control_inventory: dict[str, dict[str, Any]] = {}
            control_values: dict[str, dict[str, Any]] = {}
            for label in ("reservation", "dispatch", "settlement", "successor_reservation"):
                reference, value = _reference(root, attempt.get(label))
                if value is None:
                    raise ValueError("legacy history control artifact must be JSON")
                control_inventory[label] = reference
                control_values[label] = value
            if (len({attempt[label]["sha256"] for label in
                     ("reservation", "dispatch", "settlement", "successor_reservation")}) != 4 or
                    len({reference["resolved_path"] for reference in
                         control_inventory.values()}) != 4):
                raise ValueError("legacy history control artifacts are not distinct")
            reservation = control_values["reservation"]
            dispatch = control_values["dispatch"]
            settlement = control_values["settlement"]
            successor = control_values["successor_reservation"]
            child_hashes = {child["basename"]: child["sha256"] for child in children}
            if (reservation.get("context_id") != context_id or
                    reservation.get("role") != attempt["role"] or
                    reservation.get("accession_number") != accession or
                    reservation.get("candidate_outputs_seen") is not False or
                    reservation.get("admission_approved") is not False or
                    not isinstance(reservation.get("actual_prompt_sha256"), str) or
                    _SHA256.fullmatch(reservation["actual_prompt_sha256"]) is None or
                    dispatch.get("returned_context") != context_id or
                    dispatch.get("prompt_sha256") != reservation["actual_prompt_sha256"] or
                    dispatch.get("reservation_sha256") != attempt["reservation"]["sha256"] or
                    dispatch.get("admission_approved") is not False or
                    settlement.get("context_id") != context_id or
                    settlement.get("status") != "partial_ineligible" or
                    type(settlement.get("issue_count")) is not int or
                    settlement["issue_count"] != 0 or
                    settlement.get("admission_approved") is not False or
                    settlement.get("artifacts") != child_hashes or
                    successor.get("accession_number") != accession or
                    successor.get("role") != attempt["role"] or
                    successor.get("retained_previous_attempt") != child_hashes):
                raise ValueError("legacy history control chain differs")
            successor_context = validate_source_context_id(
                successor.get("context_id"), "legacy successor context_id")
            if successor_context == context_id or successor_context in successor_contexts:
                raise ValueError("legacy history successor context invalid or reused")
            if all_context_owners.get(successor_context, accession) != accession:
                raise ValueError("legacy history successor context is owned by another accession")
            successor_contexts.add(successor_context)
            contexts.add(successor_context)
            all_context_owners.setdefault(successor_context, accession)

            child_inventory: list[dict[str, Any]] = []
            for child in children:
                reference, child_value = _reference(
                    root, {"path": child["path"], "sha256": child["sha256"]})
                if (child["basename"] == "draft.json" and
                        (child_value is None or child_value.get("material_issues") != [])):
                    raise ValueError("legacy history draft contains retained issues")
                child_inventory.append({"basename": child["basename"], **reference})
            identity = _identity(accession, attempt, children)
            if identity in identities:
                raise ValueError("legacy history attempt identity duplicated")
            identities.add(identity)
            contexts.add(context_id)
            all_contexts.add(context_id)
            all_context_owners[context_id] = accession
            attempt_inventory.append({
                "context_id": context_id,
                "role": attempt["role"],
                "status": attempt["status"],
                **control_inventory,
                "settlement_artifacts": child_inventory,
                "typed_identity_sha256": hashlib.sha256(
                    json.dumps(identity, separators=(",", ":"), ensure_ascii=True).encode("ascii")
                ).hexdigest(),
            })

        resolved[accession] = {
            "identities": identities,
            "origin_identities": origin_identities,
            "contexts": contexts,
            "inventory": {
                "accession_number": accession,
                "authority": {
                    "record": location,
                    "resolved_path": str(path.resolve(strict=True)),
                    "expected_sha256": expected_sha256,
                    "bytes_sha256": _sha256(path),
                },
                "attempts": sorted(attempt_inventory, key=lambda row: row["context_id"]),
                "origins": sorted(origin_inventory, key=lambda row: row["context_id"]),
                "scope": authority["scope"],
                "limitations": authority["limitations"],
            },
        }
    return resolved


def authority_inventory(authorities: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the serializable projection frozen in the review-evidence binding."""
    return [authorities[accession]["inventory"] for accession in sorted(authorities)]
