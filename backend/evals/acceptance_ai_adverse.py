"""Bounded custody for explicitly declared, retired source-review attempts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


_ROW_KEYS = frozenset({
    "accession_number", "role", "context_id", "reconciliation_context_id",
    "terminal_status", "retired_prompt", "draft", "narrative", "read_log",
    "status_addendum", "custody_decision", "reconciliation_prompt",
    "operator_reservation", "adverse_dispositions",
})
_DISPOSITION_KEYS = frozenset({
    "source_context_id", "source_issue_id", "status", "reason", "source_role",
    "source_sha256", "source_locator", "reconciled_issue_id",
})


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _packet_hashes(value: Any) -> dict[str, str] | None:
    if not isinstance(value, list):
        return None
    pairs = [(item.get("role"), item.get("sha256")) for item in value
             if isinstance(item, dict)]
    if (len(pairs) != len(value) or any(not _nonempty(role) or not _nonempty(sha)
                                       for role, sha in pairs) or
            len({role for role, _ in pairs}) != len(pairs)):
        return None
    return dict(pairs)


def inventory_rows(
    base: Path, rows: list[dict[str, Any]],
    artifact: Callable[[Path, Any], tuple[dict[str, Any], dict[str, Any] | None]],
) -> list[dict[str, Any]]:
    """Freeze the complete child-artifact closure for each declared retired attempt."""
    artifact_names = _ROW_KEYS - {
        "accession_number", "role", "context_id", "reconciliation_context_id",
        "terminal_status",
    }
    return sorted(({
        "accession_number": row["accession_number"], "role": row["role"],
        "context_id": row["context_id"],
        "reconciliation_context_id": row["reconciliation_context_id"],
        "terminal_status": row["terminal_status"],
        "artifacts": {name: artifact(base, row[name])[0] for name in sorted(artifact_names)},
    } for row in rows), key=lambda row: (row["accession_number"], row["context_id"]))


def validate_rows(
    base: Path, rows: Any, accessions: list[str],
    source_packets_by_accession: dict[str, dict[str, str]],
    current_contexts: set[str], reconciliation_contexts: dict[str, str],
    reconciled_issue_ids: dict[str, set[str]],
    eligible_brief_hashes: dict[str, dict[str, str]],
    protocol_prompt_sha256: str,
    artifact: Callable[[Path, Any], tuple[dict[str, Any], dict[str, Any] | None]],
    reference: Callable[[Path, Any], tuple[dict[str, Any], dict[str, Any]]],
    issue_keys: frozenset[str],
) -> tuple[set[str], set[str], set[str]]:
    """Validate retired custody and return its contexts and unresolved accessions."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("adverse source evidence must be a non-empty list")
    declared = {(row.get("accession_number"), row.get("context_id"))
                for row in rows if isinstance(row, dict)}
    if len(declared) != len(rows):
        raise ValueError("adverse source identities are missing or duplicated")
    adverse_contexts: set[str] = set()
    unresolved: set[str] = set()
    reattributed: set[str] = set()
    for row in rows:
        if (set(row) != _ROW_KEYS or row["accession_number"] not in accessions or
                row["role"] != "source_reference_b" or
                not _nonempty(row["context_id"]) or row["context_id"] in current_contexts or
                row["context_id"] in adverse_contexts or
                row["reconciliation_context_id"] !=
                reconciliation_contexts.get(row["accession_number"]) or
                row["terminal_status"] != "compacted_ineligible"):
            raise ValueError("adverse source identity or terminal status invalid")
        accession = row["accession_number"]
        expected_sources = source_packets_by_accession[accession]
        _, draft = reference(base, row["draft"])
        _, read_log = reference(base, row["read_log"])
        _, addendum = reference(base, row["status_addendum"])
        _, decision = reference(base, row["custody_decision"])
        prompt_ref, prompt = artifact(base, row["reconciliation_prompt"])
        _, reservation = reference(base, row["operator_reservation"])
        _, ledger = reference(base, row["adverse_dispositions"])
        # These may be prose, but resolving them here makes malformed references fail.
        artifact(base, row["retired_prompt"])
        artifact(base, row["narrative"])

        material_issues = draft.get("material_issues")
        packet_hashes = _packet_hashes(draft.get("source_packets"))
        if (draft.get("accession_number") != accession or
                draft.get("coverage_status") != "complete" or
                draft.get("context_window_truncated") is not True or
                packet_hashes != expected_sources or not isinstance(material_issues, list) or
                not material_issues):
            raise ValueError("retired source draft status or packets invalid")
        issue_by_id: dict[str, dict[str, Any]] = {}
        for retired_issue in material_issues:
            if (not isinstance(retired_issue, dict) or set(retired_issue) != issue_keys or
                    any(not _nonempty(retired_issue.get(key)) for key in issue_keys) or
                    retired_issue["source_role"] not in expected_sources or
                    retired_issue["source_sha256"] !=
                    expected_sources[retired_issue["source_role"]] or
                    retired_issue["issue_id"] in issue_by_id):
                raise ValueError("retired source issue invalid")
            issue_by_id[retired_issue["issue_id"]] = retired_issue

        originals = addendum.get("original_artifacts")
        expected_originals = {
            (Path(row[name]["path"]).name, row[name]["sha256"])
            for name in ("draft", "narrative", "read_log")
        }
        if (not isinstance(originals, list) or len(originals) != 3 or
                any(not isinstance(item, dict) or set(item) != {"path", "sha256"} or
                    not _nonempty(item.get("path")) or not _nonempty(item.get("sha256"))
                    for item in originals) or
                len({item["path"] for item in originals}) != 3 or
                len(expected_originals) != 3 or
                {(Path(item["path"]).name, item["sha256"]) for item in originals} !=
                expected_originals):
            raise ValueError("retired source original artifact set invalid")
        retired = decision.get("reference_b")
        if (read_log.get("accession_number") != accession or
                read_log.get("reviewer_role") != row["role"] or
                read_log.get("context_compaction_observed") is not True or
                read_log.get("observed_context_window_truncated") is not True or
                _packet_hashes(read_log.get("source_packets")) != expected_sources or
                addendum.get("accession_number") != accession or
                addendum.get("reviewer_role") != row["role"] or
                addendum.get("observed_compaction", {}).get("occurred") is not True or
                addendum.get("custodian_disposition", {}).get("coverage_status") != "partial" or
                addendum.get("custodian_disposition", {}).get("eligibility") != "ineligible" or
                decision.get("accession_number") != accession or not isinstance(retired, dict) or
                retired.get("context_id") != row["context_id"] or
                retired.get("draft_sha256") != row["draft"]["sha256"] or
                retired.get("read_log_sha256") != row["read_log"]["sha256"] or
                retired.get("material_issue_count") != len(issue_by_id) or
                retired.get("context_compaction_observed") is not True or
                retired.get("custodian_coverage_disposition") != "partial_ineligible" or
                retired.get("individual_evidence_frozen") is not False):
            raise ValueError("retired source custody chain invalid")

        prompt_text = Path(prompt_ref["resolved_path"]).read_text(encoding="utf-8")
        if (prompt is not None or reservation.get("prompt_sha256") != row["reconciliation_prompt"]["sha256"] or
                reservation.get("requested_context_name") != row["reconciliation_context_id"] or
                reservation.get("a_sha256") != eligible_brief_hashes[accession]["source_reference_a"] or
                reservation.get("b_sha256") != eligible_brief_hashes[accession]["source_reference_b"] or
                reservation.get("protocol_prompt_sha256") != protocol_prompt_sha256 or
                reservation.get("candidate_inputs") != [] or
                reservation.get("admission_approved") is not False or
                row["draft"]["sha256"] not in prompt_text or
                row["status_addendum"]["sha256"] not in prompt_text or
                str(len(issue_by_id)) not in prompt_text or "adverse-dispositions.json" not in prompt_text or
                "separate" not in prompt_text.lower()):
            raise ValueError("adverse reconciliation prompt reservation invalid")

        disposition_rows = ledger.get("adverse_dispositions")
        if (set(ledger) != {"accession_number", "source_context_id", "eligibility",
                            "original_draft_sha256", "status_addendum_sha256",
                            "adverse_dispositions"} or ledger["accession_number"] != accession or
                ledger["source_context_id"] != row["context_id"] or
                "ineligible" not in ledger["eligibility"] or
                ledger["original_draft_sha256"] != row["draft"]["sha256"] or
                ledger["status_addendum_sha256"] != row["status_addendum"]["sha256"] or
                not isinstance(disposition_rows, list) or len(disposition_rows) != len(issue_by_id)):
            raise ValueError("adverse disposition ledger identity invalid")
        seen: set[str] = set()
        for disposition in disposition_rows:
            source_issue_id = disposition.get("source_issue_id") if isinstance(disposition, dict) else None
            old_issue = issue_by_id.get(source_issue_id)
            status = disposition.get("status") if isinstance(disposition, dict) else None
            target = disposition.get("reconciled_issue_id") if isinstance(disposition, dict) else None
            if (not isinstance(disposition, dict) or set(disposition) != _DISPOSITION_KEYS or
                    disposition.get("source_context_id") != row["context_id"] or
                    old_issue is None or source_issue_id in seen or
                    status not in {"supported", "rejected", "unresolved"} or
                    not _nonempty(disposition.get("reason")) or
                    not _nonempty(disposition.get("source_locator")) or
                    disposition.get("source_role") not in expected_sources or
                    disposition.get("source_sha256") !=
                    expected_sources.get(disposition.get("source_role")) or
                    (status == "supported" and target not in reconciled_issue_ids[accession]) or
                    (status != "supported" and target is not None)):
                raise ValueError("adverse disposition source or target invalid")
            seen.add(source_issue_id)
            if (disposition["source_role"], disposition["source_sha256"]) != (
                    old_issue["source_role"], old_issue["source_sha256"]):
                reattributed.add(accession)
            if status == "unresolved":
                unresolved.add(accession)
        if seen != set(issue_by_id):
            raise ValueError("adverse dispositions do not cover the retired issue set")
        adverse_contexts.add(row["context_id"])
    return adverse_contexts, unresolved, reattributed
