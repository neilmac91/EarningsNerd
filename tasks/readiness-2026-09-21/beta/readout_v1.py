"""Offline, bounded consumer of posthog-v1-export.hogql JSON query responses.

No network/database access. Caller freezes the private eligible roster, exclusions,
UTC window and executed query. Events remain best-effort observations, never consent,
usefulness, provider-cost or whole-cohort success attestations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

MAX_ROWS = 10_000
MAX_BYTES = 16 * 1024 * 1024
FIELDS = (
    "evidence_version", "auth_state_at_event", "account_id_at_event",
    "analytics_consent_at_event", "filing_id", "summary_id", "request_id",
    "logical_request_id", "client_attempt", "transport_attempt", "identity_evidence",
    "consent_evidence", "outcome", "delivery_path", "summary_service_invoked",
    "duration_ms", "reason", "entry_point",
)
COLUMNS = ["uuid", "event", "timestamp_s", *[f"{key}_json" for key in FIELDS]]
REQUEST_EVENTS = {"summary_request_started", "summary_request_finished"}
OUTCOMES = {"complete", "partial", "error", "timed_out", "rejected", "cancelled", "incomplete"}
PATHS = {"route", "pipeline", "router_cache", "pipeline_cache", "coalesced", "generation"}


def _integer(value: object, minimum: int = 1) -> bool:
    return type(value) is int and value >= minimum


def _account(value: object) -> bool:
    return isinstance(value, str) and len(value) <= 19 and re.fullmatch(r"[1-9][0-9]*", value) is not None


def _uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _utc(value: str) -> int:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset().total_seconds() != 0 or parsed.microsecond:
        raise ValueError("window must use whole-second UTC timestamps")
    return int(parsed.timestamp())


def _base_error(row: dict) -> str | None:
    if type(row["evidence_version"]) is not int or row["evidence_version"] != 1:
        return "legacy_or_invalid_version"
    if row["analytics_consent_at_event"] is not True:
        return "no_affirmative_consent_snapshot"
    if row["auth_state_at_event"] != "authenticated":
        return "anonymous_or_unknown_auth_snapshot"
    if not _account(row["account_id_at_event"]) or not _integer(row["filing_id"]):
        return "malformed_account_or_filing"
    return None


def _request_error(row: dict) -> str | None:
    reason = _base_error(row)
    if reason:
        return reason
    if row["identity_evidence"] != "server_authenticated" or row["consent_evidence"] != "client_declaration":
        return "missing_server_identity_or_consent_evidence"
    if row["logical_request_id"] is not None and not _uuid(row["logical_request_id"]):
        return "malformed_client_hint"
    if any(row[key] is not None and (type(row[key]) is not int or row[key] not in (1, 2))
           for key in ("client_attempt", "transport_attempt")):
        return "malformed_client_hint"
    if row["event"] == "summary_request_finished":
        if (not isinstance(row["outcome"], str) or row["outcome"] not in OUTCOMES or
                not isinstance(row["delivery_path"], str) or row["delivery_path"] not in PATHS or
                type(row["summary_service_invoked"]) is not bool or not _integer(row["duration_ms"], 0) or
                (row["summary_id"] is None and row["outcome"] in ("complete", "partial")) or
                (row["summary_id"] is not None and not _integer(row["summary_id"]))):
            return "malformed_terminal"
    return None


def _pair_request(request_id: str, rows: list[dict]) -> dict:
    """One owner for pairing; malformed/conflicting evidence poisons the whole ID."""
    errors = {reason for row in rows if (reason := _request_error(row))}
    # Distinct UUIDs with identical selected event bytes are duplicate deliveries.
    variants = {_canonical({k: v for k, v in row.items() if k != "uuid"}): row for row in rows}
    unique = list(variants.values())
    starts = [row for row in unique if row["event"] == "summary_request_started"]
    finishes = [row for row in unique if row["event"] == "summary_request_finished"]
    immutable = ("account_id_at_event", "filing_id", "logical_request_id", "client_attempt",
                 "transport_attempt", "entry_point")
    if len({_canonical([row[k] for k in immutable]) for row in rows}) != 1:
        errors.add("conflicting_request_identity_or_hints")
    if len(starts) > 1 or len(finishes) > 1:
        errors.add("conflicting_start_or_finish")
    if starts and finishes and finishes[0]["timestamp_s"] < starts[0]["timestamp_s"]:
        errors.add("finish_precedes_start")
    status = ("ambiguous" if errors else "missing_start" if not starts else
              "missing_finish" if not finishes else "paired")
    identity = rows[0]
    terminal = finishes[0] if len(finishes) == 1 and not errors else None
    return {
        "request_id": request_id, "status": status, "errors": sorted(errors),
        "account_id": identity["account_id_at_event"] if not errors else None,
        "filing_id": identity["filing_id"] if not errors else None,
        "logical_request_id": identity["logical_request_id"] if not errors else None,
        "client_attempt": identity["client_attempt"] if not errors else None,
        "transport_attempt": identity["transport_attempt"] if not errors else None,
        "event_uuids": sorted({row["uuid"] for row in rows}),
        "duplicate_deliveries": len(rows) - len(unique),
        "observed_terminal": ({key: terminal[key] for key in
                               ("outcome", "reason", "delivery_path", "summary_id", "summary_service_invoked")}
                              if terminal else None),
        "paired_duration_ms": terminal["duration_ms"] if status == "paired" else None,
    }


def build_readout(response: dict, parameters: dict) -> dict:
    """Consume selected raw JSON properties, preserving malformed/unknown evidence."""
    start, end = _utc(parameters["window_start"]), _utc(parameters["window_end"])
    if start >= end:
        raise ValueError("window must be nonempty")
    eligible, excluded = parameters["eligible_account_ids"], parameters["excluded_account_ids"]
    if (not isinstance(eligible, list) or not isinstance(excluded, list) or
            any(not _account(x) for x in eligible + excluded) or
            len(set(eligible)) != len(eligible) or len(set(excluded)) != len(excluded)):
        raise ValueError("frozen roster/exclusions must be distinct positive account-ID strings")
    accounts = set(eligible) - set(excluded)
    rows = response.get("results")
    if response.get("columns") != COLUMNS or not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("unexpected export columns/rows or row bound exceeded")
    if response.get("error") or response.get("exception"):
        raise ValueError("query response contains an error")
    diagnostics: list[dict] = []
    decoded: list[dict] = []
    poisoned_requests: dict[str, set[str]] = defaultdict(set)
    for index, values in enumerate(rows):
        if not isinstance(values, list) or len(values) != len(COLUMNS):
            raise ValueError("export row shape mismatch")
        row = dict(zip(COLUMNS[:3], values[:3]))
        try:
            row.update({key: None if value == "" else json.loads(value)
                        for key, value in zip(FIELDS, values[3:])})
        except (TypeError, ValueError):
            raise ValueError("property export must contain raw JSON strings") from None
        if _integer(row["timestamp_s"], 0) and not start <= row["timestamp_s"] < end:
            diagnostics.append({"row": index, "uuid": row["uuid"], "reason": "outside_window"})
            continue
        if not _uuid(row["uuid"]) or not _integer(row["timestamp_s"], 0):
            diagnostics.append({"row": index, "uuid": row["uuid"], "reason": "malformed_event_identity"})
            if row["event"] in tuple(REQUEST_EVENTS) and _uuid(row["request_id"]):
                poisoned_requests[row["request_id"]].add("malformed_event_identity")
            continue
        decoded.append(row)
    uuid_variants: dict[str, set[str]] = defaultdict(set)
    for row in decoded:
        uuid_variants[row["uuid"]].add(_canonical(row))
    conflicted = {key for key, values in uuid_variants.items() if len(values) > 1}
    seen: set[str] = set()
    requests: dict[str, list[dict]] = defaultdict(list)
    views: dict[str, list[dict]] = defaultdict(list)
    duplicate_uuid_deliveries = 0
    for row in decoded:
        uid, account = row["uuid"], row["account_id_at_event"]
        if uid in conflicted:
            diagnostics.append({"uuid": uid, "reason": "conflicting_event_uuid"})
            if row["event"] in tuple(REQUEST_EVENTS) and _uuid(row["request_id"]):
                poisoned_requests[row["request_id"]].add("conflicting_event_uuid")
            continue
        if uid in seen:
            duplicate_uuid_deliveries += 1
            continue
        seen.add(uid)
        if not _account(account) or account not in accounts:
            reason = "excluded_account" if account in excluded else "outside_roster_or_unattributable"
            if row["event"] in tuple(REQUEST_EVENTS) and _uuid(row["request_id"]):
                poisoned_requests[row["request_id"]].add(reason)
        elif row["event"] in tuple(REQUEST_EVENTS):
            if _uuid(row["request_id"]):
                requests[row["request_id"]].append(row)
                continue
            reason = "malformed_request_id"
        elif row["event"] == "summary_viewed":
            reason = _base_error(row)
            if reason is None and not _integer(row["summary_id"]):
                reason = "malformed_summary_id"
            if reason is None:
                views[account].append(row)
                continue
        else:
            reason = "unexpected_event_name"
        diagnostics.append({"uuid": uid, "reason": reason})
    paired = [_pair_request(key, values) for key, values in sorted(requests.items())]
    for request in paired:
        if request["request_id"] in poisoned_requests:
            request.update(status="ambiguous", errors=sorted(set(request["errors"]) |
                                                             poisoned_requests[request["request_id"]]),
                           account_id=None, filing_id=None, logical_request_id=None,
                           client_attempt=None, transport_attempt=None,
                           observed_terminal=None, paired_duration_ms=None)
    users = []
    for account in sorted(accounts, key=int):
        observed = sorted(views[account], key=lambda row: (row["timestamp_s"], row["uuid"]))
        weeks = [(datetime.fromtimestamp(row["timestamp_s"], timezone.utc).isocalendar()[:2], row["filing_id"])
                 for row in observed]
        first_week = weeks[0][0] if weeks else None
        first_filings = {filing for week, filing in weeks if week == first_week}
        returned = any(week > first_week and (len(first_filings) > 1 or filing not in first_filings)
                       for week, filing in weeks)
        users.append({"account_id": account, "observed_summary_views": len(observed),
                      "summary_view_state": "observed" if observed else "unknown",
                      "first_observed_view_timestamp_s": observed[0]["timestamp_s"] if observed else None,
                      "view_event_uuids": [row["uuid"] for row in observed],
                      "observed_later_week_new_filing_return": True if returned else None})
    return {
        "readout_version": 1, "window_start": parameters["window_start"], "window_end": parameters["window_end"],
        "eligible_denominator": len(accounts), "users": users,
        "observed_view_accounts": sum(user["summary_view_state"] == "observed" for user in users),
        "unobserved_view_accounts_unknown": sum(user["summary_view_state"] == "unknown" for user in users),
        "requests": paired, "request_status_counts": dict(Counter(r["status"] for r in paired)),
        "paired_outcome_counts": dict(Counter(r["observed_terminal"]["outcome"] for r in paired if r["status"] == "paired")),
        "diagnostics": diagnostics, "duplicate_uuid_deliveries": duplicate_uuid_deliveries,
        "conflicting_event_uuids": sorted(conflicted), "poisoned_request_ids": sorted(poisoned_requests),
        "poisoned_request_reasons": {key: sorted(poisoned_requests[key]) for key in sorted(poisoned_requests)},
        "export_complete_observed": (response.get("hasMore") is False and len(rows) < MAX_ROWS
                                     and not response.get("warnings")
                                     and ("offset" not in response or
                                          type(response["offset"]) is int and response["offset"] == 0)),
        "export_row_count": len(rows), "project_unattributable_event_count": None,
        "limits": ["All eligible accounts remain in the denominator; absent observations are unknown.",
                   "View identity is client-observed; server request identity is authenticated but consent is a client declaration.",
                   "Pairing covers this export/window only; missing sides, capture loss and unexported identities remain unknown.",
                   "Event time has one-second resolution; paired duration uses the server-emitted duration_ms.",
                   "No usefulness, browser terminal receipt, provider cost, exact cached-view count or whole-cohort success rate is inferred."],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--parameters", type=Path, required=True)
    parser.add_argument("--query", type=Path, required=True, help="exact executed and retained HogQL")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = {}
    for name in ("events", "parameters", "query"):
        path = getattr(args, name)
        with path.open("rb") as handle:
            inputs[name] = handle.read(MAX_BYTES + 1)
        if len(inputs[name]) > MAX_BYTES:
            raise ValueError("input byte bound exceeded")
    result = build_readout(json.loads(inputs["events"]), json.loads(inputs["parameters"]))
    result["input_sha256"] = {key: hashlib.sha256(value).hexdigest() for key, value in inputs.items()}
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
