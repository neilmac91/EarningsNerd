"""Version 3 role protocol with version 2 AI source evidence (offline validation only).

These records are model evidence, never human review or proof that a model read every
byte. All source-only and coverage claims are explicit, hash-bound assertions.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROLE_NAMES = frozenset({
    "source_reference_a", "source_reference_b", "source_reconciliation",
    "blind_quality", "source_challenge",
})
_BRIEF_KEYS = frozenset({
    "schema_version", "review_protocol", "accession_number", "context_id",
    "frozen_at", "source_only", "candidate_outputs_seen", "source_packets",
    "coverage_status", "context_window_truncated", "coverage_limits", "material_issues",
    "context_evidence",
})
_ISSUE_KEYS = frozenset({
    "issue_id", "issue", "source_role", "source_sha256", "source_locator", "amounts_and_bases",
    "qualifiers", "importance", "disclosure_limits",
})
_HISTORY_KEYS = frozenset({
    "accession_number", "schema_version", "kind", "current_reconciliation_context_id",
    "current_reconciliation", "reconciliation_draft", "history_manifest", "history_ledger",
    "origin_contexts", "technical_attempts", "source_context_closure_sha256",
})
_HISTORY_ROW_KEYS = frozenset({
    "history_id", "source_context_id", "original_artifact_sha256", "status", "source_role",
    "source_sha256", "source_locator", "reason", "reconciled_issue_id",
})
_HISTORY_ROLES = frozenset({
    "source_reference_a", "source_reference_b", "source_reconciliation",
})
_SHA256 = re.compile(r"[0-9a-f]{64}")
_HISTORY_PREFIX = re.compile(r"[a-z0-9][a-z0-9-]*")


def _helpers() -> tuple[Any, Any, Any, Any]:
    # Readiness imports this module lazily to keep one owner for file safety/hash rules.
    from evals.acceptance_readiness import _evidence, _sha256, _utc, _issue

    return _evidence, _sha256, _utc, _issue


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _canonical_set_sha256(values: list[str] | set[str]) -> str:
    payload = json.dumps(sorted(values), sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def _history_file_reference(value: Any) -> dict[str, str]:
    if (not isinstance(value, dict) or set(value) != {"path", "sha256"} or
            not isinstance(value.get("path"), str) or not value["path"] or
            not isinstance(value.get("sha256"), str) or
            _SHA256.fullmatch(value["sha256"]) is None):
        raise ValueError("history file reference invalid")
    return value


def _source_packets(value: Any, expected: dict[str, str]) -> bool:
    if not isinstance(value, list) or len(value) != len(expected):
        return False
    if any(not isinstance(item, dict) or set(item) != {"role", "sha256"} for item in value):
        return False
    pairs = [(item["role"], item["sha256"]) for item in value]
    return len(set(role for role, _ in pairs)) == len(pairs) and dict(pairs) == expected


def _material_issues(value: Any, source_hashes: dict[str, str]) -> bool:
    if not isinstance(value, list) or not value:
        return False
    ids: set[str] = set()
    for issue in value:
        if not isinstance(issue, dict) or set(issue) != _ISSUE_KEYS:
            return False
        role = issue.get("source_role")
        if role not in source_hashes or issue.get("source_sha256") != source_hashes[role]:
            return False
        if any(not _nonempty(issue.get(key)) for key in
               ("issue_id", "issue", "source_locator", "amounts_and_bases", "qualifiers",
                "importance", "disclosure_limits")):
            return False
        if issue["issue_id"] in ids:
            return False
        ids.add(issue["issue_id"])
    return True


def _record_ids(rows: Any, fields: tuple[str, ...]) -> set[tuple[str, ...]] | None:
    if not isinstance(rows, list):
        return None
    result: set[tuple[str, ...]] = set()
    for row in rows:
        if not isinstance(row, dict):
            return None
        values = tuple(row.get(field) for field in fields)
        if any(not _nonempty(value) for value in values):
            return None
        result.add(values)
    return result


def _artifact(base: Path, record: Any) -> tuple[dict[str, Any], dict[str, Any] | None]:
    evidence, sha256, _, _ = _helpers()
    path, value = evidence(base, record)
    return {"record": record, "resolved_path": str(path.resolve(strict=True)),
            "bytes_sha256": sha256(path)}, value


def _reference(base: Path, record: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    reference, value = _artifact(base, record)
    if value is None:
        raise ValueError("AI protocol evidence must be JSON")
    return reference, value


def _child_reference(
    base: Path, owner_reference: dict[str, Any], record: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve a child beside its owner, preserving unambiguous legacy base paths."""
    relative = Path(record.get("path", "")) if isinstance(record, dict) else Path()
    if relative.is_absolute():
        raise ValueError("child evidence path must be relative")
    roots = [base.resolve(), Path(owner_reference["resolved_path"]).parent.resolve()]
    candidates: list[Path] = []
    for root in roots:
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(root):
            raise ValueError("child evidence escapes its owner")
        if candidate not in candidates and candidate.exists():
            candidates.append(candidate)
    if not candidates:
        raise ValueError("child evidence is missing")
    if len(candidates) > 1 and len({candidate.read_bytes() for candidate in candidates}) > 1:
        raise ValueError("child evidence path is ambiguous")
    base_candidate = (base.resolve() / relative).resolve()
    root = base if candidates[0] == base_candidate else Path(owner_reference["resolved_path"]).parent
    return _reference(root, record)


def _child_artifact(
    base: Path, owner_reference: dict[str, Any], record: Any,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Resolve a JSON or text child beside its owner or from the evidence root."""
    relative = Path(record.get("path", "")) if isinstance(record, dict) else Path()
    if relative.is_absolute():
        raise ValueError("child evidence path must be relative")
    roots = [base.resolve(), Path(owner_reference["resolved_path"]).parent.resolve()]
    candidates: list[Path] = []
    for root in roots:
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(root):
            raise ValueError("child evidence escapes its owner")
        if candidate not in candidates and candidate.exists():
            candidates.append(candidate)
    if not candidates:
        raise ValueError("child evidence is missing")
    if len(candidates) > 1 and len({candidate.read_bytes() for candidate in candidates}) > 1:
        raise ValueError("child evidence path is ambiguous")
    base_candidate = (base.resolve() / relative).resolve()
    root = base if candidates[0] == base_candidate else Path(owner_reference["resolved_path"]).parent
    return _artifact(root, record)


def _reconciliation_history_inventory(
    base: Path, ai: dict[str, Any],
) -> tuple[list[dict[str, Any]], set[str], int]:
    """Validate optional cross-role history and return its sealed typed projection."""
    records = ai.get("reconciliation_history")
    if not isinstance(records, list) or not records:
        raise ValueError("reconciliation history must be a non-empty list")

    from evals.acceptance_source_review_graph import validate_source_context_id

    briefs_by_accession: dict[str, list[dict[str, Any]]] = {}
    current_context_owners: dict[str, str] = {}

    def bind_current_context(context: Any, accession: Any, label: str) -> str:
        context_id = validate_source_context_id(context, label)
        owner = current_context_owners.setdefault(context_id, accession)
        if owner != accession:
            raise ValueError("current source context is owned by another accession")
        return context_id

    for row in ai.get("source_briefs", []):
        if not isinstance(row, dict):
            raise ValueError("source brief record is malformed")
        _, brief = _reference(base, row)
        accession = row.get("accession_number")
        if (brief.get("accession_number") != accession or
                brief.get("context_id") != row.get("context_id")):
            raise ValueError("history source brief context differs")
        bind_current_context(row.get("context_id"), accession, "current source context_id")
        briefs_by_accession.setdefault(accession, []).append(row)

    reconciliations: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for row in ai.get("reconciled_references", []):
        if not isinstance(row, dict):
            raise ValueError("reconciliation record is malformed")
        _, reference = _reference(base, row)
        accession = row.get("accession_number")
        if reference.get("accession_number") != accession or accession in reconciliations:
            raise ValueError("history reconciliation identity differs or is duplicated")
        bind_current_context(
            reference.get("context_id"), accession, "current reconciliation context_id")
        reconciliations[accession] = (row, reference)

    if "adverse_source_evidence" in ai:
        from evals.acceptance_ai_adverse import _ROW_KEYS, inventory_rows

        adverse_rows = ai["adverse_source_evidence"]
        if not isinstance(adverse_rows, list) or not adverse_rows:
            raise ValueError("adverse source evidence must be a non-empty list")
        inventory_rows(base, adverse_rows, _artifact)
        for row in adverse_rows:
            accession = row.get("accession_number") if isinstance(row, dict) else None
            reconciliation = reconciliations.get(accession, ({}, {}))[1]
            if (not isinstance(row, dict) or set(row) != _ROW_KEYS or
                    row.get("role") != "source_reference_b" or
                    row.get("terminal_status") != "compacted_ineligible" or
                    row.get("reconciliation_context_id") != reconciliation.get("context_id")):
                raise ValueError("history adverse source identity differs")
            bind_current_context(
                row.get("context_id"), accession, "adverse source context_id")

    inventory: list[dict[str, Any]] = []
    all_history_contexts: set[str] = set()
    runtime_holds = 0
    seen_accessions: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != _HISTORY_KEYS:
            raise ValueError("reconciliation history record shape invalid")
        accession = record.get("accession_number")
        if (not _nonempty(accession) or accession in seen_accessions or
                type(record.get("schema_version")) is not int or
                record["schema_version"] != 1 or
                record.get("kind") != "source_reconciliation_history"):
            raise ValueError("reconciliation history identity invalid")
        seen_accessions.add(accession)
        reconciliation_row, reconciliation = reconciliations[accession]
        expected_reconciliation = {
            "path": reconciliation_row.get("path"), "sha256": reconciliation_row.get("sha256"),
        }
        if (record.get("current_reconciliation") != expected_reconciliation or
                record.get("current_reconciliation_context_id") != reconciliation.get("context_id")):
            raise ValueError("reconciliation history current reference differs")

        current_contexts = {
            validate_source_context_id(row.get("context_id"), "current source context_id")
            for row in briefs_by_accession.get(accession, [])
        }
        current_contexts.add(validate_source_context_id(
            reconciliation.get("context_id"), "current reconciliation context_id"))

        origins = record.get("origin_contexts")
        if not isinstance(origins, list) or not origins:
            raise ValueError("reconciliation history origins missing")
        origin_by_context: dict[str, dict[str, Any]] = {}
        origin_inventory: dict[str, dict[str, Any]] = {}
        origin_values: dict[str, dict[str, Any]] = {}
        history_prefixes: set[str] = set()
        for origin in origins:
            if (not isinstance(origin, dict) or set(origin) != {
                    "context_id", "role", "status", "history_prefix", "artifact_sha256",
                    "artifact"}):
                raise ValueError("reconciliation history origin shape invalid")
            context_id = validate_source_context_id(origin.get("context_id"), "history context_id")
            if current_context_owners.get(context_id, accession) != accession:
                raise ValueError("history context is owned by another accession")
            if (context_id in origin_by_context or context_id in all_history_contexts or
                    origin.get("role") not in _HISTORY_ROLES or
                    origin.get("status") != "retired_partial_history" or
                    not isinstance(origin.get("history_prefix"), str) or
                    _HISTORY_PREFIX.fullmatch(origin["history_prefix"]) is None or
                    origin["history_prefix"] in history_prefixes or
                    not isinstance(origin.get("artifact_sha256"), str) or
                    _SHA256.fullmatch(origin["artifact_sha256"]) is None or
                    not isinstance(origin.get("artifact"), dict) or
                    origin["artifact"].get("sha256") != origin["artifact_sha256"]):
                raise ValueError("reconciliation history origin invalid or reused")
            _history_file_reference(origin["artifact"])
            artifact_reference, artifact_value = _artifact(base, origin["artifact"])
            if artifact_value is None:
                raise ValueError("reconciliation history origin artifact must be JSON")
            origin_inventory[context_id] = artifact_reference
            origin_values[context_id] = artifact_value
            origin_by_context[context_id] = origin
            history_prefixes.add(origin["history_prefix"])
            all_history_contexts.add(context_id)

        manifest_record = _history_file_reference(record.get("history_manifest"))
        manifest_reference, manifest = _reference(base, manifest_record)
        manifest_contexts = manifest.get("source_exposed_contexts")
        retained_artifacts = manifest.get("retained_artifacts")
        counts = manifest.get("counts")
        limitations = manifest.get("limitations")
        if (type(manifest.get("schema_version")) is not int or
                manifest["schema_version"] != 1 or
                manifest.get("accession_number") != accession or
                not _nonempty(manifest.get("kind")) or
                manifest.get("coverage_status") != "partial" or
                manifest.get("eligible_source_evidence") is not False or
                manifest.get("formal_source_evidence_sealed") is not False or
                manifest.get("fresh_role_input") is not False or
                not isinstance(counts, dict) or not counts or
                any(not _nonempty(key) or type(value) is not int or value < 0
                    for key, value in counts.items()) or
                not isinstance(limitations, list) or not limitations or
                any(not _nonempty(item) for item in limitations) or
                not isinstance(manifest_contexts, list) or
                not isinstance(retained_artifacts, list)):
            raise ValueError("reconciliation history manifest invalid")
        exposed_contexts: set[str] = set()
        for exposed in manifest_contexts:
            if (not isinstance(exposed, dict) or set(exposed) != {
                    "context_id", "retained_status", "role"}):
                raise ValueError("history manifest context shape invalid")
            context_id = validate_source_context_id(exposed.get("context_id"),
                                                    "manifest history context_id")
            origin = origin_by_context.get(context_id)
            if (origin is None or context_id in exposed_contexts or
                    exposed.get("retained_status") != origin["status"] or
                    exposed.get("role") != origin["role"]):
                raise ValueError("history manifest context differs from origin map")
            exposed_contexts.add(context_id)
        retained_hashes: set[str] = set()
        retained_paths: set[str] = set()
        retained_inventory: list[dict[str, Any]] = []
        for artifact in retained_artifacts:
            if (not isinstance(artifact, dict) or set(artifact) != {"bytes", "path", "sha256"} or
                    type(artifact.get("bytes")) is not int or artifact["bytes"] < 1 or
                    not _nonempty(artifact.get("path")) or
                    not isinstance(artifact.get("sha256"), str) or
                    _SHA256.fullmatch(artifact["sha256"]) is None or
                    artifact["path"] in retained_paths or artifact["sha256"] in retained_hashes):
                raise ValueError("history manifest artifact invalid or duplicated")
            retained_paths.add(artifact["path"])
            retained_hashes.add(artifact["sha256"])
            resolved_artifact, _ = _child_artifact(base, manifest_reference, artifact)
            if Path(resolved_artifact["resolved_path"]).stat().st_size != artifact["bytes"]:
                raise ValueError("history manifest artifact byte count differs")
            retained_inventory.append(resolved_artifact)
        for context_id, origin in origin_by_context.items():
            if context_id not in exposed_contexts and context_id not in current_contexts:
                raise ValueError("history origin is neither manifest-exposed nor a current context")
            if context_id in exposed_contexts and origin["artifact_sha256"] not in retained_hashes:
                raise ValueError("history manifest omits an origin artifact hash")

        expected_history_origins: dict[str, tuple[str, str]] = {}
        expected_runtime_ids: set[str] = set()
        exposed_counts = {"source_issues": 0, "reconciled_issues": 0, "disagreements": 0}
        if not set(exposed_counts).issubset(counts):
            raise ValueError("history manifest canonical counts missing")
        for context_id, origin in origin_by_context.items():
            value = origin_values[context_id]
            if (("accession_number" in value and value["accession_number"] != accession) or
                    ("context_id" in value and value["context_id"] != context_id)):
                raise ValueError("history origin embedded identity differs")
            issues = value.get("material_issues", [])
            disagreements = value.get("disagreements", [])
            if (not isinstance(issues, list) or not isinstance(disagreements, list) or
                    not issues and not disagreements):
                raise ValueError("history origin has no derivable issues or disagreements")
            issue_ids: set[str] = set()
            for source_issue in issues:
                issue_id = source_issue.get("issue_id") if isinstance(source_issue, dict) else None
                if not _nonempty(issue_id) or issue_id in issue_ids:
                    raise ValueError("history origin issue identity invalid or duplicated")
                issue_ids.add(issue_id)
                derived_id = f"{origin['history_prefix']}:issue:{issue_id}"
                expected_history_origins[derived_id] = (context_id, origin["artifact_sha256"])
            for index, disagreement in enumerate(disagreements):
                if (not isinstance(disagreement, dict) or
                        disagreement.get("status") not in {"supported", "unresolved"}):
                    raise ValueError("history origin disagreement malformed")
                derived_id = f"{origin['history_prefix']}:disagreement:{index}"
                expected_history_origins[derived_id] = (context_id, origin["artifact_sha256"])
                if disagreement["status"] == "unresolved":
                    expected_runtime_ids.add(derived_id)
            if context_id in exposed_contexts:
                if origin["role"] in {"source_reference_a", "source_reference_b"}:
                    exposed_counts["source_issues"] += len(issues)
                elif origin["role"] == "source_reconciliation":
                    exposed_counts["reconciled_issues"] += len(issues)
                    exposed_counts["disagreements"] += len(disagreements)
        for count_name, derived_count in exposed_counts.items():
            if count_name in counts and counts[count_name] != derived_count:
                raise ValueError("history manifest count differs from retained artifacts")

        technical_attempts = record.get("technical_attempts")
        if not isinstance(technical_attempts, list) or not technical_attempts:
            raise ValueError("reconciliation history technical attempts missing")
        technical_contexts: set[str] = set()
        technical_inventory: list[dict[str, Any]] = []
        for attempt in technical_attempts:
            if not isinstance(attempt, dict) or set(attempt) != {
                    "context_id", "role", "status", "reservation", "dispatch", "settlement"}:
                raise ValueError("reconciliation history technical attempt shape invalid")
            context_id = validate_source_context_id(
                attempt.get("context_id"), "technical history context_id")
            if current_context_owners.get(context_id, accession) != accession:
                raise ValueError("technical history context is owned by another accession")
            if (context_id in technical_contexts or context_id in all_history_contexts or
                    attempt.get("role") not in {"source_reference_a", "source_reference_b"} or
                    attempt.get("status") != "partial_ineligible"):
                raise ValueError("reconciliation history technical attempt invalid or reused")
            reservation_record = _history_file_reference(attempt["reservation"])
            dispatch_record = _history_file_reference(attempt["dispatch"])
            settlement_record = _history_file_reference(attempt["settlement"])
            reservation_reference, reservation = _reference(base, reservation_record)
            dispatch_reference, dispatch = _reference(base, dispatch_record)
            settlement_reference, settlement = _reference(base, settlement_record)
            if (type(reservation.get("schema_version")) is not int or
                    reservation["schema_version"] != 1 or
                    reservation.get("context_id") != context_id or
                    reservation.get("role") != attempt["role"] or
                    reservation.get("accession_number") != accession or
                    reservation.get("candidate_outputs_seen") is not False or
                    reservation.get("admission_approved") is not False or
                    not isinstance(reservation.get("actual_prompt_sha256"), str) or
                    _SHA256.fullmatch(reservation["actual_prompt_sha256"]) is None or
                    dispatch.get("returned_context") != context_id or
                    dispatch.get("prompt_sha256") != reservation["actual_prompt_sha256"] or
                    dispatch.get("reservation_sha256") != reservation_record["sha256"] or
                    dispatch.get("admission_approved") is not False or
                    settlement.get("context_id") != context_id or
                    settlement.get("status") != attempt["status"] or
                    settlement.get("admission_approved") is not False or
                    type(settlement.get("issue_count")) is not int or
                    settlement["issue_count"] != 0 or
                    not _nonempty(settlement.get("reason")) or
                    not isinstance(settlement.get("artifacts"), dict) or
                    not settlement["artifacts"]):
                raise ValueError("reconciliation history technical custody differs")
            child_inventory: list[dict[str, Any]] = []
            settlement_artifacts = settlement["artifacts"]
            if (any(not _nonempty(path) or not isinstance(sha256, str) or
                    _SHA256.fullmatch(sha256) is None
                    for path, sha256 in settlement_artifacts.items()) or
                    sorted(Path(path).name for path in settlement_artifacts) !=
                    ["brief.md", "draft.json", "read-log.json"]):
                raise ValueError("technical settlement child declaration incomplete")
            for path, sha256 in settlement["artifacts"].items():
                child, child_value = _child_artifact(
                    base, settlement_reference, {"path": path, "sha256": sha256})
                if Path(path).name == "draft.json":
                    if child_value is None or child_value.get("material_issues") != []:
                        raise ValueError("technical settlement draft contains retained issues")
                child_inventory.append(child)
            technical_contexts.add(context_id)
            all_history_contexts.add(context_id)
            technical_inventory.append({
                "context_id": context_id,
                "role": attempt["role"],
                "status": attempt["status"],
                "reservation": reservation_reference,
                "dispatch": dispatch_reference,
                "settlement": settlement_reference,
                "settlement_artifacts": sorted(
                    child_inventory, key=lambda item: item["record"]["path"]),
            })

        expected_closure = current_contexts | set(origin_by_context) | technical_contexts
        if record.get("source_context_closure_sha256") != _canonical_set_sha256(expected_closure):
            raise ValueError("reconciliation history source-context closure differs")

        ledger_record = record.get("history_ledger")
        if (not isinstance(ledger_record, dict) or set(ledger_record) != {
                "path", "sha256", "row_count", "identity_set_sha256", "runtime_holds"} or
                type(ledger_record.get("row_count")) is not int or ledger_record["row_count"] < 1 or
                not isinstance(ledger_record.get("path"), str) or
                not isinstance(ledger_record.get("sha256"), str) or
                _SHA256.fullmatch(ledger_record["sha256"]) is None or
                not isinstance(ledger_record.get("identity_set_sha256"), str) or
                _SHA256.fullmatch(ledger_record["identity_set_sha256"]) is None or
                not isinstance(ledger_record.get("runtime_holds"), list)):
            raise ValueError("reconciliation history ledger declaration invalid")
        ledger_reference, ledger = _reference(base, ledger_record)
        rows = ledger.get("history_dispositions")
        if (set(ledger) != {"accession_number", "history_dispositions"} or
                ledger.get("accession_number") != accession or not isinstance(rows, list) or
                len(rows) != ledger_record["row_count"]):
            raise ValueError("reconciliation history ledger shape or count differs")
        holds: dict[str, str] = {}
        for hold in ledger_record["runtime_holds"]:
            if (not isinstance(hold, dict) or set(hold) != {"history_id", "hold"} or
                    not _nonempty(hold.get("history_id")) or
                    hold.get("hold") != "custodian_classification" or
                    hold["history_id"] in holds):
                raise ValueError("reconciliation history runtime hold invalid")
            holds[hold["history_id"]] = hold["hold"]
        if set(holds) != expected_runtime_ids:
            raise ValueError("runtime holds differ from unresolved origin disagreements")
        history_ids: set[str] = set()
        used_origins: set[str] = set()
        typed_rows: list[dict[str, Any]] = []
        source_hashes = {
            packet.get("role"): packet.get("sha256")
            for packet in reconciliation.get("source_packets", []) if isinstance(packet, dict)
        }
        targets = {
            issue.get("issue_id") for issue in reconciliation.get("material_issues", [])
            if isinstance(issue, dict)
        }
        for row in rows:
            if not isinstance(row, dict) or set(row) != _HISTORY_ROW_KEYS:
                raise ValueError("reconciliation history row shape invalid")
            history_id = row.get("history_id")
            context_id = row.get("source_context_id")
            origin = origin_by_context.get(context_id)
            if (not _nonempty(history_id) or history_id in history_ids or origin is None or
                    expected_history_origins.get(history_id) != (
                        context_id, origin["artifact_sha256"]) or
                    row.get("original_artifact_sha256") != origin["artifact_sha256"] or
                    row.get("source_role") not in source_hashes or
                    row.get("source_sha256") != source_hashes.get(row.get("source_role")) or
                    not _nonempty(row.get("source_locator")) or not _nonempty(row.get("reason"))):
                raise ValueError("reconciliation history row identity, origin or source invalid")
            history_ids.add(history_id)
            used_origins.add(context_id)
            hold = holds.get(history_id)
            if hold is None:
                if row.get("status") != "supported" or row.get("reconciled_issue_id") not in targets:
                    raise ValueError("financial history row lacks a current reconciled target")
                evidence_class = "filing_source"
                filing_source_locator = row["source_locator"]
            else:
                if row.get("status") != "unresolved" or row.get("reconciled_issue_id") is not None:
                    raise ValueError("operator-runtime history row cleared its custody hold")
                evidence_class = "operator_runtime"
                filing_source_locator = None
                runtime_holds += 1
            typed_rows.append({
                "history_id": history_id,
                "evidence_class": evidence_class,
                "origin_context_id": context_id,
                "original_artifact_sha256": row["original_artifact_sha256"],
                "status": row["status"],
                "source_role": row["source_role"],
                "source_sha256": row["source_sha256"],
                "filing_source_locator": filing_source_locator,
                "reconciled_issue_id": row["reconciled_issue_id"],
                "hold": hold,
            })
        if (set(holds) - history_ids or used_origins != set(origin_by_context) or
                history_ids != set(expected_history_origins)):
            raise ValueError("reconciliation history holds or origins are incomplete")
        if ledger_record["identity_set_sha256"] != _canonical_set_sha256(history_ids):
            raise ValueError("reconciliation history identity set differs")

        current_reference = _reference(base, expected_reconciliation)[0]
        reconciliation_draft = _artifact(
            base, _history_file_reference(record.get("reconciliation_draft")))[0]
        inventory.append({
            "record": record,
            "accession_number": accession,
            "current_reconciliation": current_reference,
            "reconciliation_draft": reconciliation_draft,
            "history_manifest": manifest_reference,
            "origin_artifacts": [
                {"context_id": context_id, "artifact": origin_inventory[context_id]}
                for context_id in sorted(origin_inventory)
            ],
            "retained_artifacts": sorted(
                retained_inventory, key=lambda item: item["record"]["path"]),
            "history_ledger": ledger_reference,
            "technical_attempts": sorted(
                technical_inventory, key=lambda item: item["context_id"]),
            "typed_rows": sorted(typed_rows, key=lambda row: row["history_id"]),
        })
    return sorted(inventory, key=lambda row: row["accession_number"]), all_history_contexts, runtime_holds


def _context_receipt(base: Path, owner_reference: dict[str, Any], owner: dict[str, Any],
                     accession: str, context: str,
                     role: str, sources: dict[str, str], frozen: datetime,
                     input_briefs: dict[str, str] | None = None) -> dict[str, Any]:
    _, _, utc, _ = _helpers()
    reference, receipt = _child_reference(base, owner_reference, owner["context_evidence"])
    if (set(receipt) != {"schema_version", "review_protocol", "accession_number", "context_id",
                         "role", "observed_at", "input_source_packets", "candidate_output_artifacts",
                         "source_only", "context_window_truncated", "input_brief_sha256"} or
            receipt["schema_version"] != 2 or receipt["review_protocol"] != "ai_assisted" or
            receipt["accession_number"] != accession or receipt["context_id"] != context or
            receipt["role"] != role or utc(receipt["observed_at"]) is None or
            utc(receipt["observed_at"]) > frozen or
            not _source_packets(receipt["input_source_packets"], sources) or
            receipt["input_brief_sha256"] != (input_briefs or {}) or
            receipt["candidate_output_artifacts"] != [] or
            receipt["source_only"] is not True or receipt["context_window_truncated"] is not False):
        raise ValueError("source-only context receipt incomplete")
    return reference


def ai_review_evidence_inventory(prerequisites_path: Path, prereq: dict[str, Any]) -> dict[str, Any]:
    """Freeze every AI role, prompt, source brief, reconciliation and exposure byte."""
    base = Path(prerequisites_path).resolve(strict=True).parent
    ai = prereq["ai_assisted"]
    protocol_ref, protocol = _reference(base, ai["protocol"])
    roles = protocol["roles"]

    def source_record(row: dict[str, Any], *, include_role: bool) -> dict[str, Any]:
        owner_reference, value = _reference(base, row)
        if include_role:
            return {"accession_number": row["accession_number"], "role": row["role"],
                    "context_id": row["context_id"], **owner_reference,
                    "context_evidence": _child_reference(
                        base, owner_reference, value["context_evidence"])[0]}
        return {"accession_number": row["accession_number"], **owner_reference,
                "context_evidence": _child_reference(
                    base, owner_reference, value["context_evidence"])[0]}

    inventory = {
        "prerequisites_path": str(Path(prerequisites_path).resolve(strict=True)),
        "schema_version": 2, "review_protocol": "ai_assisted",
        "protocol": protocol_ref,
        "role_artifacts": sorted(({
            "role": role["role"], "prompt": _artifact(base, role["prompt"])[0],
            "contract": _artifact(base, role["contract"])[0],
        } for role in roles), key=lambda row: row["role"]),
        "source_briefs": sorted((source_record(row, include_role=True)
                                  for row in ai["source_briefs"]),
            key=lambda row: (row["accession_number"], row["context_id"])),
        "reconciled_references": sorted((source_record(row, include_role=False)
                                          for row in ai["reconciled_references"]),
            key=lambda row: row["accession_number"]),
        "exposure_review": _reference(base, ai["exposure_review"])[0],
    }
    if "adverse_source_evidence" in ai:
        from evals.acceptance_ai_adverse import inventory_rows

        inventory["adverse_source_evidence"] = inventory_rows(
            base, ai["adverse_source_evidence"], _artifact)
    if "reconciliation_history" in ai:
        inventory["reconciliation_history"] = _reconciliation_history_inventory(base, ai)[0]
    return inventory


def source_context_ids(prereq: dict[str, Any], base: Path) -> set[str]:
    """Return the declared schema-2 source-review context closure."""
    ai = prereq["ai_assisted"]
    contexts = {row.get("context_id") for row in ai["source_briefs"]}
    reconciliations: dict[str, str] = {}
    for record in ai["reconciled_references"]:
        _, reference = _reference(base, record)
        reconciliations[record["accession_number"]] = reference.get("context_id")
        contexts.add(reference.get("context_id"))
    for row in ai.get("adverse_source_evidence", []):
        if (not isinstance(row, dict) or
                row.get("reconciliation_context_id") != reconciliations.get(row.get("accession_number"))):
            raise ValueError("adverse source reconciliation context differs")
        contexts.add(row.get("context_id"))
    if any(not _nonempty(context) for context in contexts):
        raise ValueError("source review context identity missing")
    expected_count = len(ai["source_briefs"]) + len(ai["reconciled_references"]) + len(
        ai.get("adverse_source_evidence", []))
    if len(contexts) != expected_count:
        raise ValueError("source review context identity reused")
    if "reconciliation_history" in ai:
        _, origin_contexts, _ = _reconciliation_history_inventory(base, ai)
        contexts.update(origin_contexts)
    return contexts


def validate_ai_prerequisites(
    prereq: dict[str, Any], base: Path, accessions: list[str],
    source_packets_by_accession: dict[str, dict[str, str]], now: datetime,
) -> tuple[list[dict[str, str]], dict[str, datetime], str, list[str]]:
    """Validate v2 without satisfying or borrowing any human v1 assertion."""
    _, _, utc, issue = _helpers()
    issues: list[dict[str, str]] = []
    freezes: dict[str, datetime] = {}
    exposure_status = "unverified"
    limitations = ["AI source coverage and independence are retained claims, not human verification"]
    ai = prereq.get("ai_assisted")
    required_ai_keys = {"protocol", "source_briefs", "reconciled_references", "exposure_review"}
    if (not isinstance(ai, dict) or not required_ai_keys.issubset(ai) or
            set(ai) - required_ai_keys - {"adverse_source_evidence", "reconciliation_history"}):
        issue(issues, "ai_protocol_invalid", "AI protocol inventory missing or malformed")
        return issues, freezes, exposure_status, limitations
    try:
        _, protocol = _reference(base, ai["protocol"])
        if (set(protocol) != {"schema_version", "review_protocol", "frozen_at",
                              "approved_manifest_sha256", "roles"} or
                protocol["schema_version"] != 3 or protocol["review_protocol"] != "ai_assisted" or
                protocol["approved_manifest_sha256"] != prereq["approved_manifest_sha256"] or
                utc(protocol["frozen_at"]) is None or utc(protocol["frozen_at"]) > now):
            raise ValueError("protocol version, manifest or freeze invalid")
        roles = protocol["roles"]
        if not isinstance(roles, list) or len(roles) != len(ROLE_NAMES):
            raise ValueError("AI role inventory incomplete")
        names = [role.get("role") for role in roles if isinstance(role, dict)]
        if set(names) != ROLE_NAMES:
            raise ValueError("AI roles duplicated")
        for role in roles:
            if (set(role) != {"role", "provider", "model", "model_version",
                              "prompt", "contract"} or
                    any(not _nonempty(role.get(k)) for k in
                        ("provider", "model", "model_version"))):
                raise ValueError("AI role identity incomplete")
            _artifact(base, role["prompt"])
            _artifact(base, role["contract"])
        protocol_frozen = utc(protocol["frozen_at"])
        reconciliation_prompt_sha256 = next(
            role["prompt"]["sha256"] for role in roles
            if role["role"] == "source_reconciliation")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        issue(issues, "ai_protocol_invalid", type(exc).__name__)
        return issues, freezes, exposure_status, limitations

    briefs = ai["source_briefs"]
    expected_pairs = {(acc, role) for acc in accessions
                      for role in ("source_reference_a", "source_reference_b")}
    if (not isinstance(briefs, list) or len(briefs) != 2 * len(accessions) or
            _record_ids(briefs, ("accession_number", "role")) != expected_pairs or
            _record_ids(briefs, ("context_id",)) is None or
            len(_record_ids(briefs, ("context_id",))) != len(briefs)):
        issue(issues, "ai_brief_coverage", "two independent source-only briefs per accession required")
        briefs = []
    source_contexts = {row["context_id"] for row in briefs}
    context_by_unit = {(row["accession_number"], row["role"]): row["context_id"] for row in briefs}
    brief_hashes: dict[tuple[str, str], str] = {}
    brief_freezes: dict[tuple[str, str], datetime] = {}
    brief_issue_ids: dict[tuple[str, str], set[str]] = {}
    for row in briefs:
        accession, context = row["accession_number"], row["context_id"]
        try:
            if set(row) != {"accession_number", "role", "context_id", "path", "sha256"}:
                raise ValueError("brief record shape invalid")
            brief_reference, brief = _reference(base, row)
            expected_sources = source_packets_by_accession[accession]
            frozen = utc(brief.get("frozen_at"))
            if (set(brief) != _BRIEF_KEYS or brief["schema_version"] != 2 or
                    brief["review_protocol"] != "ai_assisted" or
                    brief["accession_number"] != accession or brief["context_id"] != context or
                    frozen is None or frozen > protocol_frozen or frozen > now or
                    brief["source_only"] is not True or brief["candidate_outputs_seen"] is not False or
                    brief["coverage_status"] != "complete" or
                    brief["context_window_truncated"] is not False or
                    not isinstance(brief["coverage_limits"], str) or
                    not _source_packets(brief["source_packets"], expected_sources) or
                    not _material_issues(brief["material_issues"], expected_sources)):
                raise ValueError("source-only brief, full coverage or source binding invalid")
            brief_hashes[(accession, context)] = row["sha256"]
            brief_freezes[(accession, context)] = frozen
            brief_issue_ids[(accession, context)] = {item["issue_id"] for item in brief["material_issues"]}
            role = row["role"]
            _context_receipt(base, brief_reference, brief, accession, context, role,
                             expected_sources, frozen)
        except (OSError, KeyError, TypeError, ValueError) as exc:
            issue(issues, "ai_brief_invalid", f"{accession}: {type(exc).__name__}")

    references = ai["reconciled_references"]
    if (not isinstance(references, list) or len(references) != len(accessions) or
            _record_ids(references, ("accession_number",)) != {(acc,) for acc in accessions}):
        issue(issues, "ai_reference_coverage", "one reconciled source reference per accession required")
        references = []
    reconciliation_contexts: dict[str, str] = {}
    reconciled_issue_ids: dict[str, set[str]] = {}
    for row in references:
        accession = row["accession_number"]
        try:
            if set(row) != {"accession_number", "path", "sha256"}:
                raise ValueError("reference record shape invalid")
            reference_record, ref = _reference(base, row)
            context = ref.get("context_id")
            if not _nonempty(context) or context in source_contexts:
                raise ValueError("source reconciliation context reused or missing")
            source_contexts.add(context)
            expected_sources = source_packets_by_accession[accession]
            frozen = utc(ref.get("frozen_at"))
            expected_hashes = {role: brief_hashes[(accession, context_by_unit[(accession, role)])]
                               for role in ("source_reference_a", "source_reference_b")}
            if (set(ref) != {"schema_version", "review_protocol", "accession_number", "context_id",
                             "frozen_at", "source_only", "candidate_outputs_seen", "source_packets",
                             "coverage_status", "context_window_truncated", "coverage_limits",
                             "source_brief_sha256", "disagreements", "material_issues",
                             "issue_dispositions",
                             "context_evidence"} or
                    ref["schema_version"] != 2 or ref["review_protocol"] != "ai_assisted" or
                    ref["accession_number"] != accession or
                    frozen is None or frozen > protocol_frozen or frozen > now or
                    any(frozen < brief_freezes[(accession, context_by_unit[(accession, role)])]
                        for role in ("source_reference_a", "source_reference_b")) or
                    ref["source_only"] is not True or ref["candidate_outputs_seen"] is not False or
                    ref["coverage_status"] != "complete" or ref["context_window_truncated"] is not False or
                    not isinstance(ref["coverage_limits"], str) or
                    not _source_packets(ref["source_packets"], expected_sources) or
                    ref["source_brief_sha256"] != expected_hashes or
                    not isinstance(ref["disagreements"], list) or
                    not isinstance(ref["issue_dispositions"], list) or
                    not _material_issues(ref["material_issues"], expected_sources)):
                raise ValueError("reconciliation source, coverage or brief binding invalid")
            expected_issues = {(context_by_unit[(accession, role)], issue_id)
                               for role in ("source_reference_a", "source_reference_b")
                               for issue_id in brief_issue_ids[(accession, context_by_unit[(accession, role)])]}
            dispositions = ref["issue_dispositions"]
            if (len(dispositions) != len(expected_issues) or
                    any(not isinstance(item, dict) or set(item) != {
                        "source_context_id", "source_issue_id", "status", "reason",
                        "source_role", "source_sha256", "source_locator", "reconciled_issue_id",
                    } for item in dispositions)):
                raise ValueError("source brief issue dispositions incomplete")
            seen_issues = {(item["source_context_id"], item["source_issue_id"])
                           for item in dispositions}
            reconciled_ids = {item["issue_id"] for item in ref["material_issues"]}
            reconciliation_contexts[accession] = context
            reconciled_issue_ids[accession] = reconciled_ids
            if seen_issues != expected_issues or any(
                item["status"] not in {"supported", "rejected", "unresolved"} or
                not _nonempty(item["reason"]) or not _nonempty(item["source_locator"]) or
                item["source_role"] not in expected_sources or
                item["source_sha256"] != expected_sources.get(item["source_role"]) or
                (item["status"] == "supported" and item["reconciled_issue_id"] not in reconciled_ids) or
                (item["status"] != "supported" and item["reconciled_issue_id"] is not None)
                for item in dispositions
            ):
                raise ValueError("source brief issue disposition lacks source or reconciled link")
            if any(item["status"] == "unresolved" for item in dispositions):
                issue(issues, "ai_source_issue_unresolved", f"{accession}: source brief issue unresolved")
            if any(not isinstance(item, dict) or set(item) != {"claim", "status", "resolution", "source_role",
                                                               "source_sha256", "source_locator"} or
                   item.get("status") not in {"supported", "rejected", "unresolved"} or
                   any(not _nonempty(item.get(k)) for k in ("claim", "resolution", "source_locator")) or
                   item.get("source_role") not in expected_sources or
                   item.get("source_sha256") != expected_sources.get(item.get("source_role"))
                   for item in ref["disagreements"]):
                raise ValueError("disagreement lacks source resolution")
            if any(item["status"] == "unresolved" for item in ref["disagreements"]):
                issue(issues, "ai_source_disagreement_unresolved",
                      f"{accession}: unresolved source-reference disagreement")
            _context_receipt(base, reference_record, ref, accession, context,
                             "source_reconciliation", expected_sources, frozen, expected_hashes)
            freezes[accession] = frozen
        except (OSError, KeyError, TypeError, ValueError) as exc:
            issue(issues, "ai_reference_invalid", f"{accession}: {type(exc).__name__}")

    if "adverse_source_evidence" in ai:
        try:
            from evals.acceptance_ai_adverse import validate_rows

            adverse_contexts, unresolved, reattributed = validate_rows(
                base, ai["adverse_source_evidence"], accessions,
                source_packets_by_accession, source_contexts, reconciliation_contexts,
                reconciled_issue_ids, {
                    accession: {role: brief_hashes[
                        (accession, context_by_unit[(accession, role)])]
                        for role in ("source_reference_a", "source_reference_b")}
                    for accession in accessions
                }, reconciliation_prompt_sha256, _artifact, _reference, _ISSUE_KEYS)
            source_contexts.update(adverse_contexts)
            for accession in sorted(unresolved):
                issue(issues, "ai_adverse_source_issue_unresolved",
                      f"{accession}: retired source issue unresolved")
            if reattributed:
                limitations.append(
                    "adverse dispositions reattribute some retired issues within the frozen source packets")
        except (OSError, KeyError, TypeError, ValueError) as exc:
            issue(issues, "ai_adverse_source_invalid", type(exc).__name__)

    if "reconciliation_history" in ai:
        try:
            _, _, runtime_holds = _reconciliation_history_inventory(base, ai)
            if runtime_holds:
                limitations.append(
                    f"{runtime_holds} historical unresolved disagreement(s) remain under "
                    "declared custodian classification; structural validation does not prove "
                    "financial-versus-runtime semantics, and their source-exposed contexts "
                    "remain excluded from downstream review"
                )
        except (OSError, KeyError, TypeError, ValueError) as exc:
            issue(issues, "ai_reconciliation_history_invalid", type(exc).__name__)

    try:
        _, exposure = _reference(base, ai["exposure_review"])
        if (set(exposure) != {"schema_version", "review_protocol", "checked_accessions",
                              "known_candidate_output_exposed_accessions",
                              "known_tuning_exposed_accessions", "unknown_external_exposure",
                              "external_artifact_inventory", "scope", "observed_at"} or
                exposure["schema_version"] != 2 or exposure["review_protocol"] != "ai_assisted" or
                sorted(exposure["checked_accessions"]) != sorted(accessions) or
                len(exposure["checked_accessions"]) != len(accessions) or
                not isinstance(exposure["known_candidate_output_exposed_accessions"], list) or
                not isinstance(exposure["known_tuning_exposed_accessions"], list) or
                not isinstance(exposure["unknown_external_exposure"], bool) or
                not _nonempty(exposure["external_artifact_inventory"]) or
                not _nonempty(exposure["scope"]) or
                utc(exposure["observed_at"]) is None or utc(exposure["observed_at"]) > protocol_frozen):
            raise ValueError("AI exposure review incomplete")
        if (exposure["known_candidate_output_exposed_accessions"] or
                exposure["known_tuning_exposed_accessions"]):
            issue(issues, "ai_holdout_exposed", "known candidate-output or tuning exposure")
        if exposure["unknown_external_exposure"]:
            exposure_status = "no_known_candidate_exposure_external_unknown"
            limitations.append("external holdout exposure history is unknown")
        else:
            exposure_status = "no_known_exposure_in_declared_scope"
            limitations.append("exposure status is limited to the declared inventory and scope")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        issue(issues, "ai_exposure_invalid", type(exc).__name__)
    return issues, freezes, exposure_status, limitations
