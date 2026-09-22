"""Version 2, AI-assisted E7 source-reference protocol (offline validation only).

These records are model evidence, never human review or proof that a model read every
byte. All source-only and coverage claims are explicit, hash-bound assertions.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
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


def _helpers() -> tuple[Any, Any, Any, Any]:
    # Readiness imports this module lazily to keep one owner for file safety/hash rules.
    from evals.acceptance_readiness import _evidence, _sha256, _utc, _issue

    return _evidence, _sha256, _utc, _issue


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


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


def _context_receipt(base: Path, owner: dict[str, Any], accession: str, context: str,
                     role: str, sources: dict[str, str], frozen: datetime,
                     input_briefs: dict[str, str] | None = None) -> dict[str, Any]:
    _, _, utc, _ = _helpers()
    reference, receipt = _reference(base, owner["context_evidence"])
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
    return {
        "prerequisites_path": str(Path(prerequisites_path).resolve(strict=True)),
        "schema_version": 2, "review_protocol": "ai_assisted",
        "protocol": protocol_ref,
        "role_artifacts": sorted(({
            "role": role["role"], "prompt": _artifact(base, role["prompt"])[0],
            "contract": _artifact(base, role["contract"])[0],
        } for role in roles), key=lambda row: row["role"]),
        "source_briefs": sorted(({
            "accession_number": row["accession_number"], "context_id": row["context_id"],
            **_reference(base, row)[0],
            "context_evidence": _reference(base, _reference(base, row)[1]["context_evidence"])[0],
        } for row in ai["source_briefs"]), key=lambda row: (row["accession_number"], row["context_id"])),
        "reconciled_references": sorted(({
            "accession_number": row["accession_number"], **_reference(base, row)[0],
            "context_evidence": _reference(base, _reference(base, row)[1]["context_evidence"])[0],
        } for row in ai["reconciled_references"]), key=lambda row: row["accession_number"]),
        "exposure_review": _reference(base, ai["exposure_review"])[0],
    }


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
    if not isinstance(ai, dict) or set(ai) != {
        "protocol", "source_briefs", "reconciled_references", "exposure_review",
    }:
        issue(issues, "ai_protocol_invalid", "AI protocol inventory missing or malformed")
        return issues, freezes, exposure_status, limitations
    try:
        _, protocol = _reference(base, ai["protocol"])
        if (set(protocol) != {"schema_version", "review_protocol", "frozen_at",
                              "approved_manifest_sha256", "roles"} or
                protocol["schema_version"] != 2 or protocol["review_protocol"] != "ai_assisted" or
                protocol["approved_manifest_sha256"] != prereq["approved_manifest_sha256"] or
                utc(protocol["frozen_at"]) is None or utc(protocol["frozen_at"]) > now):
            raise ValueError("protocol version, manifest or freeze invalid")
        roles = protocol["roles"]
        if not isinstance(roles, list) or len(roles) != len(ROLE_NAMES):
            raise ValueError("AI role inventory incomplete")
        names = [role.get("role") for role in roles if isinstance(role, dict)]
        contexts = [role.get("context_id") for role in roles if isinstance(role, dict)]
        if set(names) != ROLE_NAMES or len(set(contexts)) != len(ROLE_NAMES):
            raise ValueError("AI roles or contexts duplicated")
        for role in roles:
            if (set(role) != {"role", "provider", "model", "model_version", "context_id",
                              "prompt", "contract"} or
                    any(not _nonempty(role.get(k)) for k in
                        ("provider", "model", "model_version", "context_id"))):
                raise ValueError("AI role identity incomplete")
            _artifact(base, role["prompt"])
            _artifact(base, role["contract"])
        context_by_role = {role["role"]: role["context_id"] for role in roles}
        protocol_frozen = utc(protocol["frozen_at"])
    except (OSError, KeyError, TypeError, ValueError) as exc:
        issue(issues, "ai_protocol_invalid", type(exc).__name__)
        return issues, freezes, exposure_status, limitations

    briefs = ai["source_briefs"]
    expected_pairs = {(acc, context_by_role[role]) for acc in accessions
                      for role in ("source_reference_a", "source_reference_b")}
    if (not isinstance(briefs, list) or len(briefs) != 2 * len(accessions) or
            _record_ids(briefs, ("accession_number", "context_id")) != expected_pairs):
        issue(issues, "ai_brief_coverage", "two independent source-only briefs per accession required")
        briefs = []
    brief_hashes: dict[tuple[str, str], str] = {}
    brief_freezes: dict[tuple[str, str], datetime] = {}
    brief_issue_ids: dict[tuple[str, str], set[str]] = {}
    for row in briefs:
        accession, context = row["accession_number"], row["context_id"]
        try:
            if set(row) != {"accession_number", "context_id", "path", "sha256"}:
                raise ValueError("brief record shape invalid")
            _, brief = _reference(base, row)
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
            role = ("source_reference_a" if context == context_by_role["source_reference_a"]
                    else "source_reference_b")
            _context_receipt(base, brief, accession, context, role, expected_sources, frozen)
        except (OSError, KeyError, TypeError, ValueError) as exc:
            issue(issues, "ai_brief_invalid", f"{accession}: {type(exc).__name__}")

    references = ai["reconciled_references"]
    if (not isinstance(references, list) or len(references) != len(accessions) or
            _record_ids(references, ("accession_number",)) != {(acc,) for acc in accessions}):
        issue(issues, "ai_reference_coverage", "one reconciled source reference per accession required")
        references = []
    for row in references:
        accession = row["accession_number"]
        try:
            if set(row) != {"accession_number", "path", "sha256"}:
                raise ValueError("reference record shape invalid")
            _, ref = _reference(base, row)
            expected_sources = source_packets_by_accession[accession]
            frozen = utc(ref.get("frozen_at"))
            expected_hashes = {role: brief_hashes[(accession, context_by_role[role])]
                               for role in ("source_reference_a", "source_reference_b")}
            if (set(ref) != {"schema_version", "review_protocol", "accession_number", "context_id",
                             "frozen_at", "source_only", "candidate_outputs_seen", "source_packets",
                             "coverage_status", "context_window_truncated", "coverage_limits",
                             "source_brief_sha256", "disagreements", "material_issues",
                             "issue_dispositions",
                             "context_evidence"} or
                    ref["schema_version"] != 2 or ref["review_protocol"] != "ai_assisted" or
                    ref["accession_number"] != accession or
                    ref["context_id"] != context_by_role["source_reconciliation"] or
                    frozen is None or frozen > protocol_frozen or frozen > now or
                    any(frozen < brief_freezes[(accession, context_by_role[role])]
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
            expected_issues = {(context_by_role[role], issue_id)
                               for role in ("source_reference_a", "source_reference_b")
                               for issue_id in brief_issue_ids[(accession, context_by_role[role])]}
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
            _context_receipt(base, ref, accession, context_by_role["source_reconciliation"],
                             "source_reconciliation", expected_sources, frozen, expected_hashes)
            freezes[accession] = frozen
        except (OSError, KeyError, TypeError, ValueError) as exc:
            issue(issues, "ai_reference_invalid", f"{accession}: {type(exc).__name__}")

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
