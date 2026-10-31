"""Run the kit's exact read-only SQL against temporary synthetic PostgreSQL tables.

Requires an explicit DSN for an isolated `tranche_beta` database. No application
tables, customer records, provider calls, or production configuration are used.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SERVER_EVENTS_IN_QUERY_A = {
    "generation_started", "generation_succeeded", "generation_failed",
    "generation_timed_out", "analysis_inference_cost",
}
PARAMETERS = {
    "cohort": "fixture-beta",
    "window_start": "2026-09-21T00:00:00Z",
    "window_end": "2026-09-28T00:00:00Z",
    "excluded_user_ids": [3, 11],
    "excluded_invite_ids": [106],
}


def query(name: str) -> str:
    source = (HERE / name).read_text()
    return re.sub(r":'([a-z_]+)'", r"%(\1)s", source)


def check_event_inventory() -> dict:
    """Guard both client-coverage predicates against browser-emitter drift."""
    frontend_events: set[str] = set()
    frontend_sources: list[str] = []
    tracked = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "frontend/app", "frontend/components",
         "frontend/features", "frontend/hooks", "frontend/lib", "frontend/types"],
        cwd=REPO,
    )
    for relative in filter(None, tracked.decode().split("\0")):
        path = REPO / relative
        if (path.suffix not in {".ts", ".tsx"} or
                any(part in {"tests", "__tests__", "generated", "__generated__"} for part in path.parts) or
                ".spec." in path.name or ".test." in path.name):
            continue
        emitted = set(re.findall(r"(?:safeCapture|posthog\.capture)\('([^']+)'", path.read_text()))
        if emitted:
            frontend_events.update(emitted)
            frontend_sources.append(str(path.relative_to(REPO)))
    sql = (HERE / "posthog.hogql").read_text()
    a_match = re.search(r"countIf\(event IN\s*\(([^)]*)\)\) AS client_events", sql, re.DOTALL)
    filters = re.findall(r"AND event IN\s*\(([^)]*)\)", sql, re.DOTALL)
    assert a_match is not None and len(filters) == 2, "expected Query A and B coverage predicates"
    a_coverage = re.findall(r"'([^']+)'", a_match.group(1))
    a_filter, b_coverage = [re.findall(r"'([^']+)'", text) for text in filters]
    predicates = (a_coverage, a_filter, b_coverage)
    assert all(len(names) == len(set(names)) for names in predicates), "duplicate event in predicate"
    assert set(a_coverage) == set(b_coverage) == frontend_events, {
        "missing_a": sorted(frontend_events - set(a_coverage)),
        "missing_b": sorted(frontend_events - set(b_coverage)),
        "extra_a": sorted(set(a_coverage) - frontend_events),
        "extra_b": sorted(set(b_coverage) - frontend_events),
    }
    assert set(a_filter) == frontend_events | SERVER_EVENTS_IN_QUERY_A
    assert not frontend_events & SERVER_EVENTS_IN_QUERY_A
    return {"frontend_event_count": len(frontend_events), "frontend_sources": frontend_sources,
            "server_events_kept_out_of_coverage": sorted(SERVER_EVENTS_IN_QUERY_A)}


def check_identity_schematic() -> dict:
    """Exercise the identity join shape offline; this does not execute HogQL."""
    db = sqlite3.connect(":memory:")
    try:
        db.executescript("""
            CREATE TABLE eligible (user_id INTEGER PRIMARY KEY);
            CREATE TABLE person_distinct_ids (
              distinct_id TEXT PRIMARY KEY, person_id TEXT, is_numeric_account INTEGER
            );
            CREATE TABLE events (event_id TEXT PRIMARY KEY, distinct_id TEXT, person_id TEXT);
            INSERT INTO eligible VALUES (1), (2), (3), (4);
            INSERT INTO person_distinct_ids VALUES
              ('1','p1',1), ('anon-1','p1',0),
              ('2','p2',1), ('999','p2',1), ('anon-2','p2',0),
              ('3','p3',1), ('anon-3a','p3',0), ('anon-3b','p3',0);
            INSERT INTO events VALUES
              ('numeric','1','p1'), ('linked-uuid','anon-1','p1'),
              ('shared-person','anon-2','p2'),
              ('multi-uuid-a','anon-3a','p3'), ('multi-uuid-b','anon-3b','p3'),
              ('unlinked','orphan','p5');
        """)
        assert db.execute("SELECT count() FROM events WHERE distinct_id IN ('1','2','3','4')").fetchone()[0] == 1
        rows = db.execute("""
            WITH numeric_person_ids AS (
              SELECT person_id, count() AS numeric_id_count
              FROM person_distinct_ids WHERE is_numeric_account = 1 GROUP BY person_id
            ), linked AS (
              SELECT e.user_id, p.person_id, n.numeric_id_count FROM eligible e
              JOIN person_distinct_ids p ON p.distinct_id = CAST(e.user_id AS TEXT)
              JOIN numeric_person_ids n ON n.person_id = p.person_id
            ), resolved AS (
              SELECT user_id, person_id FROM linked WHERE numeric_id_count = 1
            ), event_counts AS (
              SELECT r.user_id, count() AS event_count FROM events ev
              JOIN resolved r ON ev.person_id = r.person_id GROUP BY r.user_id
            )
            SELECT e.user_id, coalesce(c.event_count, 0),
                   CASE WHEN r.user_id IS NOT NULL THEN 'resolved'
                        WHEN l.user_id IS NOT NULL THEN 'ambiguous'
                        ELSE 'unresolved' END
            FROM eligible e LEFT JOIN linked l ON l.user_id = e.user_id
            LEFT JOIN resolved r ON r.user_id = e.user_id
            LEFT JOIN event_counts c ON c.user_id = e.user_id ORDER BY e.user_id
        """).fetchall()
        assert rows == [(1, 2, "resolved"), (2, 0, "ambiguous"),
                        (3, 2, "resolved"), (4, 0, "unresolved")], rows
        return {"raw_numeric_event_count": 1, "linked_event_counts": [2, 0, 2, 0],
                "ambiguous_and_unresolved_remain_in_denominator": True}
    finally:
        db.close()


def check_v1_readout() -> dict:
    """Exercise the actual offline consumer; this does not execute live HogQL."""
    import sys
    import tempfile
    from copy import deepcopy
    from datetime import datetime, timezone

    from readout_v1 import COLUMNS, FIELDS, MAX_ROWS, build_readout

    parameters = {"window_start": "2026-09-28T00:00:00Z", "window_end": "2026-10-12T00:00:00Z",
                  "eligible_account_ids": ["1", "2", "3", "4", "5", "6"], "excluded_account_ids": ["6"]}
    begin = int(datetime(2026, 9, 28, tzinfo=timezone.utc).timestamp())
    rows = []

    def uuid(n: int) -> str:
        return f"00000000-0000-0000-0000-{n:012d}"

    def emit(event: str, *, account: str = "1", offset: int = 0, request: int | None = None,
             **changes: object) -> list:
        props = dict.fromkeys(FIELDS)
        props.update(evidence_version=1, auth_state_at_event="authenticated", account_id_at_event=account,
                     analytics_consent_at_event=True, filing_id=11, summary_id=21)
        if request is not None:
            props.update(request_id=uuid(1000 + request), summary_id=None,
                         identity_evidence="server_authenticated", consent_evidence="client_declaration",
                         logical_request_id=uuid(2000), client_attempt=1, transport_attempt=1,
                         entry_point="filing")
            if event == "summary_request_finished":
                props.update(outcome="complete", delivery_path="router_cache", summary_service_invoked=False,
                             duration_ms=12, summary_id=21)
        props.update(changes)
        row = [uuid(len(rows) + 1), event, begin + offset, *[json.dumps(props[key]) for key in FIELDS]]
        rows.append(row)
        return row

    def pair(request: int, **changes: object) -> None:
        terminal_only = {"outcome", "delivery_path", "summary_service_invoked", "duration_ms", "summary_id", "reason"}
        emit("summary_request_started", request=request,
             **{key: value for key, value in changes.items() if key not in terminal_only})
        emit("summary_request_finished", request=request, offset=1, **changes)

    # Client-observed views use only event-time identity, never a later person merge.
    first = emit("summary_viewed")
    rows.append(deepcopy(first))  # same UUID, byte-identical duplicate export/delivery
    emit("summary_viewed", offset=7 * 86400, filing_id=12)
    emit("summary_viewed", account="2")
    emit("summary_viewed", account="2", offset=7 * 86400)  # same filing is not a qualifying return
    emit("summary_viewed", account="3", auth_state_at_event="anonymous")
    emit("summary_viewed", account="3", evidence_version=True)
    emit("summary_viewed", account="3", analytics_consent_at_event="true")
    emit("summary_viewed", account="3", summary_id=True)
    emit("summary_viewed", account="6")
    emit("summary_viewed", account="99")
    emit("summary_viewed", offset=14 * 86400)  # end is excluded

    pair(1)
    duplicate = deepcopy(rows[-1])
    duplicate[0] = uuid(900)
    rows.append(duplicate)
    pair(2, outcome="error", delivery_path="generation", summary_service_invoked=True)
    pair(3, client_attempt=2)  # later success under same client label must not erase request2
    emit("summary_request_started", request=4)
    emit("summary_request_finished", request=5, outcome="error")
    pair(6)
    emit("summary_request_finished", request=6, offset=1, outcome="error")
    emit("summary_request_started", request=7)
    emit("summary_request_finished", request=7, account="2", offset=1)
    pair(8, duration_ms=True)
    pair(9)
    conflict = deepcopy(rows[-1])
    conflict[COLUMNS.index("outcome_json")] = '"error"'
    rows.append(conflict)
    pair(10)
    bad_uuid = emit("summary_request_finished", request=10, outcome="error")
    bad_uuid[0] = "not-a-uuid"
    pair(11)
    emit("summary_request_finished", request=11, account="6", outcome="error")
    pair(12, account="4")  # shared client label across accounts never combines requests
    pair(13, outcome=["complete"])
    pair(14, evidence_version="1")
    for n, outcome in enumerate(("partial", "timed_out", "rejected", "cancelled", "incomplete"), 20):
        pair(n, outcome=outcome, delivery_path="coalesced")
    emit("summary_request_started", request=30, offset=4)
    emit("summary_request_finished", request=30, offset=3)
    # Complete/partial frames identify persisted summaries; absent IDs cannot
    # become positive request outcomes. Other terminal kinds may legitimately
    # finish before a summary exists.
    missing_summary_requests = {}
    for n, outcome in enumerate(("complete", "partial"), 40):
        pair(n, outcome=outcome, summary_id=None)
        missing_summary_requests[f"{outcome}_null"] = uuid(1000 + n)
        pair(n + 2, outcome=outcome)
        rows[-1][COLUMNS.index("summary_id_json")] = ""  # absent JSON property
        missing_summary_requests[f"{outcome}_missing"] = uuid(1002 + n)
    pair(50, outcome="error", summary_id=None, delivery_path="route")
    pair(51, outcome="rejected", summary_id=None, delivery_path="route", reason="http_404")

    response = {"columns": COLUMNS, "results": rows, "hasMore": False}
    result = build_readout(response, parameters)
    users = {row["account_id"]: row for row in result["users"]}
    requests = {row["request_id"]: row for row in result["requests"]}
    assert result["eligible_denominator"] == 5
    assert result["observed_view_accounts"] == 2 and result["unobserved_view_accounts_unknown"] == 3
    assert users["1"]["observed_summary_views"] == 2
    assert users["1"]["observed_later_week_new_filing_return"] is True
    assert users["2"]["observed_later_week_new_filing_return"] is None
    assert all(users[x]["summary_view_state"] == "unknown" for x in ("3", "4", "5"))
    assert result["duplicate_uuid_deliveries"] == 1
    assert requests[uuid(1001)]["duplicate_deliveries"] == 1
    assert requests[uuid(1002)]["observed_terminal"]["outcome"] == "error"
    assert requests[uuid(1003)]["observed_terminal"]["outcome"] == "complete"
    assert requests[uuid(1004)]["status"] == "missing_finish"
    assert requests[uuid(1005)]["status"] == "missing_start"
    assert requests[uuid(1005)]["paired_duration_ms"] is None
    for n in (6, 7, 8, 9, 10, 11, 13, 14, 30):
        assert requests[uuid(1000+n)]["status"] == "ambiguous", (n, requests[uuid(1000+n)])
        assert requests[uuid(1000+n)]["observed_terminal"] is None
    expected_poison_reasons = {
        uuid(1009): ["conflicting_event_uuid"],
        uuid(1010): ["malformed_event_identity"],
        uuid(1011): ["excluded_account"],
    }
    actual_poison_reasons = {key: requests[key]["errors"] for key in expected_poison_reasons}
    assert actual_poison_reasons == expected_poison_reasons, actual_poison_reasons
    assert result["poisoned_request_ids"] == sorted(expected_poison_reasons)
    assert result["poisoned_request_reasons"] == expected_poison_reasons
    assert all(requests[key]["paired_duration_ms"] is None for key in expected_poison_reasons)
    # Reuse those same adverse rows under one ID: every cause must survive, not
    # whichever poison path happened to run last.
    request_column = COLUMNS.index("request_id_json")
    poison_ids_json = {json.dumps(key) for key in expected_poison_reasons}
    shared_poison_rows = deepcopy([row for row in rows if row[request_column] in poison_ids_json])
    for row in shared_poison_rows:
        row[request_column] = json.dumps(uuid(1009))
    shared_poison = build_readout({**response, "results": shared_poison_rows}, parameters)
    all_poison_reasons = sorted(reason for values in expected_poison_reasons.values() for reason in values)
    assert shared_poison["requests"][0]["errors"] == all_poison_reasons
    assert shared_poison["poisoned_request_reasons"] == {uuid(1009): all_poison_reasons}
    assert shared_poison["requests"][0]["status"] == "ambiguous"
    assert shared_poison["requests"][0]["observed_terminal"] is None
    assert shared_poison["requests"][0]["paired_duration_ms"] is None
    assert requests[uuid(1012)]["account_id"] == "4"
    missing_summary_statuses = {label: requests[request_id]["status"]
                                for label, request_id in missing_summary_requests.items()}
    assert set(missing_summary_statuses.values()) == {"ambiguous"}, missing_summary_statuses
    for request_id in missing_summary_requests.values():
        assert "malformed_terminal" in requests[request_id]["errors"]
        assert requests[request_id]["observed_terminal"] is None
        assert requests[request_id]["paired_duration_ms"] is None
    for n, outcome in ((50, "error"), (51, "rejected")):
        assert requests[uuid(1000 + n)]["status"] == "paired"
        assert requests[uuid(1000 + n)]["observed_terminal"]["outcome"] == outcome
        assert requests[uuid(1000 + n)]["observed_terminal"]["summary_id"] is None
        assert requests[uuid(1000 + n)]["paired_duration_ms"] == 12
    assert result["paired_outcome_counts"] == {
        "complete": 3, "error": 2, "partial": 1, "timed_out": 1,
        "rejected": 2, "cancelled": 1, "incomplete": 1,
    }
    assert result["export_complete_observed"] is True
    for changed in ({"hasMore": True}, {"warnings": ["partial access"]}, {"hasMore": None},
                    {"offset": 1}, {"offset": None}, {"offset": False}):
        assert build_readout({**response, **changed}, parameters)["export_complete_observed"] is False
    assert build_readout({**response, "offset": 0}, parameters)["export_complete_observed"] is True
    assert build_readout({**response, "results": [first] * MAX_ROWS}, parameters)["export_complete_observed"] is False
    empty = build_readout({**response, "results": []}, parameters)
    assert empty["eligible_denominator"] == 5 and empty["unobserved_view_accounts_unknown"] == 5
    assert empty["paired_outcome_counts"] == {}  # no fabricated zero-cost/success percentage
    props = re.findall(r"JSONExtractRaw\(properties, '([^']+)'\) AS ([a-z_]+)",
                       (HERE / "posthog-v1-export.hogql").read_text())
    assert props == [(key, f"{key}_json") for key in FIELDS]
    with tempfile.TemporaryDirectory(prefix="beta-v1-fixture-") as temp:
        root = Path(temp)
        (root / "events.json").write_text(json.dumps(response))
        (root / "parameters.json").write_text(json.dumps(parameters))
        command = [sys.executable, str(HERE / "readout_v1.py"), "--events", str(root / "events.json"),
                   "--parameters", str(root / "parameters.json"), "--query", str(HERE / "posthog-v1-export.hogql"),
                   "--output", str(root / "result.json")]
        subprocess.run(command, check=True, capture_output=True)
        assert (root / "result.json").stat().st_mode & 0o777 == 0o600
        actual = json.loads((root / "result.json").read_text())
        assert actual.pop("input_sha256").keys() == {"events", "parameters", "query"}
        assert actual == result
        assert subprocess.run(command, capture_output=True, check=False).returncode != 0  # no overwrite
    return {"v1_fixture_rows": len(rows), "eligible_denominator": 5,
            "paired_outcomes": result["paired_outcome_counts"], "request_statuses": result["request_status_counts"],
            "missing_success_summary_id_statuses": missing_summary_statuses,
            "poisoned_request_reasons": result["poisoned_request_reasons"],
            "actual_cli_roundtrip": "passed", "hogql_live_execution": "not performed"}

def check_file_export_adapter() -> dict:
    """Exercise the file-export adapter offline; no part is downloaded and no HogQL executes."""
    import hashlib
    import sys
    import tempfile
    from datetime import datetime, timezone

    from file_export_to_v1 import file_export_completeness, parse_record, v1_response_from_parts
    from readout_v1 import COLUMNS, FIELDS, build_readout

    parameters = {"window_start": "2026-09-28T00:00:00Z", "window_end": "2026-10-12T00:00:00Z",
                  "eligible_account_ids": ["1001", "1002"], "excluded_account_ids": []}
    begin = int(datetime(2026, 9, 28, tzinfo=timezone.utc).timestamp())
    run_id = "00000000-0000-4000-8000-0000000000aa"
    file_ids = ["00000000-0000-4000-8000-0000000000a1", "00000000-0000-4000-8000-0000000000a2"]

    def uuid(n: int) -> str:
        return f"00000000-0000-4000-8000-{n:012d}"

    def row(n: int, event: str, offset: int, **props: object) -> list:
        values = dict.fromkeys(FIELDS)
        values.update(evidence_version=1, auth_state_at_event="authenticated", account_id_at_event="1001",
                      analytics_consent_at_event=True, filing_id=11, entry_point="synthetic_validation")
        values.update(props)
        # JSONExtractRaw renders an absent property as "" (as the actual capability part does).
        return [uuid(n), event, begin + offset, *["" if values[key] is None else json.dumps(values[key]) for key in FIELDS]]

    def line(values: list, order: list[str]) -> bytes:
        obj = dict(zip(COLUMNS, values))
        return json.dumps({key: obj[key] for key in order}, separators=(",", ":")).encode()

    def rotated(k: int) -> list[str]:
        return COLUMNS[k:] + COLUMNS[:k]

    request = {"request_id": uuid(1), "identity_evidence": "server_authenticated", "consent_evidence": "client_declaration"}
    view = row(10, "summary_viewed", 0, summary_id=22)
    started = row(11, "summary_request_started", 1, **request)
    finished = row(12, "summary_request_finished", 2, summary_id=22, outcome="complete", delivery_path="generation",
                   summary_service_invoked=True, duration_ms=1000, reason="synthetic_fixture", **request)
    other_view = row(13, "summary_viewed", 7 * 86400, account_id_at_event="1002", filing_id=12, summary_id=23)
    # Part one: finish before start (file order is not event order); shuffled keys; trailing LF.
    part_one = line(view, rotated(5)) + b"\n" + line(finished, rotated(13)) + b"\n"
    # Part two: one row in projection key order with a CR before its LF; one reversed; no trailing LF.
    part_two = line(started, COLUMNS) + b"\r\n" + line(other_view, list(reversed(COLUMNS)))
    parts = [part_one, part_two]
    expected = {"columns": COLUMNS, "results": [view, finished, started, other_view]}
    response = v1_response_from_parts(parts)
    assert response == expected, response
    assert set(response) == {"columns", "results"}  # never hasMore, offset, warnings or error
    record = parse_record(parts)
    assert [fact["rows"] for fact in record["parts"]] == [2, 2]
    assert [fact["trailing_newline"] for fact in record["parts"]] == [True, False]
    assert [fact["cr_bytes"] for fact in record["parts"]] == [0, 1]  # recorded, not stripped
    assert [fact["key_order_matched_rows"] for fact in record["parts"]] == [0, 1]
    assert record["totals"] == {"parts": 2, "bytes": len(part_one) + len(part_two), "cr_bytes": 1,
                                "lines": 4, "rows": 4, "key_order_matched_rows": 1}, record["totals"]

    def rejects(bad_parts: list[bytes], *needles: str) -> str:
        try:
            v1_response_from_parts(bad_parts)
        except ValueError as exc:
            assert all(needle in str(exc) for needle in needles), str(exc)
            return str(exc)
        raise AssertionError("adapter accepted a part it must reject")

    rejections = {
        "bom": rejects([b"\xef\xbb\xbf" + part_one, part_two], "part 0", "byte-order mark"),
        "key_set_mismatch": rejects([part_one, part_two.replace(b'"uuid":', b'"id":', 1)],
                                    "part 1 line 1", "key set mismatch", "'uuid'", "'id'"),
        "second_trailing_empty_line": rejects([part_one + b"\n", part_two], "part 0 line 3"),
        "non_object_line": rejects([part_one, b"[1]\n"], "part 1 line 1", "not a JSON object"),
        "duplicate_key": rejects([line(view, COLUMNS)[:-1] + b',"uuid":"' + uuid(10).encode() + b'"}\n'],
                                 "part 0 line 1", "duplicate key", "'uuid'"),
    }
    # A string-typed timestamp_s passes through uncoerced; the consumer, not the adapter, diagnoses it.
    string_timestamp = part_one.replace(b'"timestamp_s":%d' % begin, b'"timestamp_s":"%d"' % begin, 1)
    assert string_timestamp != part_one
    adapted = v1_response_from_parts([string_timestamp, part_two])
    assert adapted["results"][0][COLUMNS.index("timestamp_s")] == str(begin)
    consumer_reasons = [entry["reason"] for entry in build_readout(adapted, parameters)["diagnostics"]
                        if entry.get("uuid") == uuid(10)]
    assert consumer_reasons == ["malformed_event_identity"], consumer_reasons  # observed, not assumed

    inventory = [{"id": file_id, "sha256": hashlib.sha256(part).hexdigest(), "bytes": len(part), "rows": fact["rows"]}
                 for file_id, part, fact in zip(file_ids, parts, record["parts"])]
    run_record = {"id": run_id, "status": "Completed", "files": list(file_ids), "records_completed": 4}
    complete = file_export_completeness(run_record, inventory, 4, 4)
    assert complete == {"status": "Completed", "error": None, "records_completed": 4, "n_before": 4, "n_after": 4,
                        "rows_parsed": 4, "files": inventory, "file_export_complete_observed": True,
                        "failing_rules": []}, complete
    passing_cases = {  # not signals: an error key that is null or empty; "plan" only inside another word
        "error_null": file_export_completeness({**run_record, "error": None}, inventory, 4, 4),
        "error_empty": file_export_completeness({**run_record, "error": ""}, inventory, 4, 4),
        "explanation_text": file_export_completeness({**run_record, "detail": "explanation of the run"}, inventory, 4, 4),
    }
    assert all(case["file_export_complete_observed"] is True and case["failing_rules"] == []
               for case in passing_cases.values()), passing_cases
    reordered, duplicated = [inventory[1], inventory[0]], [inventory[0], inventory[0], inventory[1]]
    false_cases = {
        "n_after_mismatch": file_export_completeness(run_record, inventory, 4, 5),
        "missing_file_id": file_export_completeness({**run_record, "files": [*file_ids, uuid(999)]}, inventory, 4, 4),
        "failed_billing": file_export_completeness({**run_record, "status": "FailedBilling"}, inventory, 4, 4),
        "n_after_none": file_export_completeness(run_record, inventory, 4, None),
        "error_text": file_export_completeness({**run_record, "error": "boom"}, inventory, 4, 4),
        "pricing_text": file_export_completeness({**run_record, "detail": "Upgrade your plan"}, inventory, 4, 4),
        "pricing_plural": file_export_completeness({**run_record, "detail": "see Plans"}, inventory, 4, 4),
        "part_from_another_run": file_export_completeness(run_record, [*inventory, {**inventory[0], "id": uuid(998)}], 4, 4),
        "duplicate_part_id": file_export_completeness(run_record, duplicated, 4, 4),
        "out_of_order_files": file_export_completeness(run_record, reordered, 4, 4),
        "bad_sha256": file_export_completeness(run_record, [{**inventory[0], "sha256": "abc"}, inventory[1]], 4, 4),
        "limit_cap": file_export_completeness({**run_record, "records_completed": 10_000},
                                              [{**inventory[0], "rows": 9_998}, inventory[1]], 10_000, 10_000),
    }
    assert all(case["file_export_complete_observed"] is False for case in false_cases.values())
    assert false_cases["n_after_none"]["failing_rules"] == ["n_after not observed"], false_cases["n_after_none"]
    assert any(rule.startswith("counts differ") for rule in false_cases["n_after_mismatch"]["failing_rules"])
    assert any(uuid(999) in rule for rule in false_cases["missing_file_id"]["failing_rules"])
    assert any("FailedBilling" in rule for rule in false_cases["failed_billing"]["failing_rules"])
    assert false_cases["error_text"]["failing_rules"] == ["error field present: 'boom'"]
    assert false_cases["pricing_text"]["failing_rules"] == ["pricing signal ['plan'] in run record text: 'Upgrade your plan'"]
    assert false_cases["pricing_plural"]["failing_rules"] == ["pricing signal ['plans'] in run record text: 'see Plans'"]
    assert any(uuid(998) in rule for rule in false_cases["part_from_another_run"]["failing_rules"])
    assert false_cases["duplicate_part_id"]["rows_parsed"] == 6  # counted over the parts as supplied
    assert f"part {file_ids[0]} supplied more than once" in false_cases["duplicate_part_id"]["failing_rules"]
    assert false_cases["out_of_order_files"]["failing_rules"] == [
        f"supplied part ids {[file_ids[1], file_ids[0]]} do not equal the run's files inventory {file_ids}"]
    assert any("sha256 is not 64 hex characters" in rule for rule in false_cases["bad_sha256"]["failing_rules"])
    assert false_cases["limit_cap"]["failing_rules"] == ["n_before 10000 is not below the LIMIT cap 10000"]
    empty_part = b""
    assert parse_record([empty_part])["totals"]["rows"] == 0
    empty_inventory = [{"id": file_ids[0], "sha256": hashlib.sha256(empty_part).hexdigest(), "bytes": 0, "rows": 0}]
    empty_run = {"id": run_id, "status": "Completed", "files": [file_ids[0]], "records_completed": 0}
    zero_without = file_export_completeness(empty_run, empty_inventory, 0, 0)
    zero_spliced = file_export_completeness({**empty_run, "source_availability_recorded": True}, empty_inventory, 0, 0)
    zero_with = file_export_completeness(empty_run, empty_inventory, 0, 0, source_availability_recorded=True)
    assert zero_without["failing_rules"] == ["zero rows without a source-availability record"]
    assert zero_without["file_export_complete_observed"] is False
    assert zero_spliced["failing_rules"] == zero_without["failing_rules"]  # a key in the run record is not the record
    assert zero_with["file_export_complete_observed"] is True and zero_with["failing_rules"] == []

    # End to end: the file-ordered adapter output and the query-ordered direct response read out identically.
    direct = {"columns": COLUMNS, "results": sorted(expected["results"], key=lambda values: (values[2], values[0]))}
    from_parts = build_readout(v1_response_from_parts(parts), parameters)
    from_direct = build_readout(direct, parameters)
    assert from_parts == from_direct
    assert from_parts["export_complete_observed"] is False and from_direct["export_complete_observed"] is False
    assert from_parts["request_status_counts"] == {"paired": 1}
    assert from_parts["paired_outcome_counts"] == {"complete": 1}
    assert from_parts["observed_view_accounts"] == 2 and from_parts["diagnostics"] == []
    with tempfile.TemporaryDirectory(prefix="beta-adapter-fixture-") as temp:
        root = Path(temp)
        paths = [root / f"posthog-hogql-{run_id}-{file_id}.jsonl" for file_id in file_ids]
        for path, part in zip(paths, parts):
            path.write_bytes(part)
        (root / "run-record.json").write_text(json.dumps(run_record))
        (root / "parameters.json").write_text(json.dumps(parameters))
        command = [sys.executable, str(HERE / "file_export_to_v1.py"), "--parts", *map(str, paths),
                   "--run-record", str(root / "run-record.json"), "--n-before", "4", "--n-after", "4",
                   "--output", str(root / "events.json"), "--completeness-output", str(root / "completeness.json")]
        subprocess.run(command, check=True, capture_output=True)
        for name in ("events.json", "completeness.json"):
            assert (root / name).stat().st_mode & 0o777 == 0o600
        assert json.loads((root / "events.json").read_text()) == expected
        assert json.loads((root / "completeness.json").read_text()) == complete
        refused = subprocess.run(command, capture_output=True, check=False)  # no overwrite: one-line refusal
        assert refused.returncode != 0 and b"refusing to overwrite" in refused.stderr, refused.stderr
        assert b"Traceback" not in refused.stderr
        duplicate = [sys.executable, str(HERE / "file_export_to_v1.py"), "--parts", str(paths[0]), str(paths[0]),
                     "--run-record", str(root / "run-record.json"), "--n-before", "4",
                     "--output", str(root / "dup-events.json"), "--completeness-output", str(root / "dup-completeness.json")]
        duplicate_result = subprocess.run(duplicate, capture_output=True, check=False)
        assert duplicate_result.returncode != 0 and b"refusing duplicate" in duplicate_result.stderr, duplicate_result.stderr
        assert b"Traceback" not in duplicate_result.stderr
        assert not (root / "dup-events.json").exists() and not (root / "dup-completeness.json").exists()
        consumer = [sys.executable, str(HERE / "readout_v1.py"), "--events", str(root / "events.json"),
                    "--parameters", str(root / "parameters.json"), "--query", str(HERE / "posthog-v1-export.hogql"),
                    "--output", str(root / "readout.json")]
        subprocess.run(consumer, check=True, capture_output=True)
        actual = json.loads((root / "readout.json").read_text())
        assert actual.pop("input_sha256").keys() == {"events", "parameters", "query"}
        assert actual == from_parts
    # D4 parity pin: the committed capability part (invented literals) reads out exactly as the retained
    # September 30 readout minus the input hashes; export_complete_observed stays false by construction.
    evidence = REPO / "tasks" / "review-evidence" / "beta-readout-2026-09-30"
    part_bytes = (REPO / "tasks" / "code-red-20261004" / "runtime" / "handbacks" / "coo" / "export-validation-01" / "parts"
                  / "posthog-hogql-01a10d89-1ee8-0000-3e2c-9000712c9502-01a10d89-3a26-0000-56f3-e1f6c4004610.jsonl").read_bytes()
    retained = json.loads((evidence / "readout.json").read_text())
    assert retained.pop("input_sha256").keys() == {"events", "parameters", "query"}
    d4 = build_readout(v1_response_from_parts([part_bytes]), json.loads((evidence / "parameters.json").read_text()))
    assert d4 == retained, d4
    assert d4["export_complete_observed"] is False and d4["export_row_count"] == 3
    return {"adapter_fixture_rows": len(expected["results"]), "adapter_fixture_parts": len(parts),
            "key_order_matched_rows": record["totals"]["key_order_matched_rows"], "rejections": rejections,
            "string_timestamp_s_consumer_reasons": consumer_reasons,
            "completeness_true_case": complete["file_export_complete_observed"],
            "completeness_passing_cases": sorted(passing_cases),
            "completeness_false_cases": {name: case["failing_rules"] for name, case in false_cases.items()},
            "zero_rows": {"without_source_availability_record": zero_without["failing_rules"],
                          "with_run_record_key_only": zero_spliced["file_export_complete_observed"],
                          "with_explicit_keyword_argument": zero_with["file_export_complete_observed"]},
            "end_to_end_readout_equal": from_parts == from_direct,
            "export_complete_observed": {"from_parts": from_parts["export_complete_observed"],
                                         "from_direct": from_direct["export_complete_observed"]},
            "d4_parity_with_retained_readout": "passed", "d4_part_sha256": hashlib.sha256(part_bytes).hexdigest(),
            "actual_cli_roundtrip": "passed", "download_or_hogql_live_execution": "not performed"}



def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="isolated local tranche_beta DSN")
    parser.add_argument("--inventory-only", action="store_true", help="check browser event names without PostgreSQL")
    parser.add_argument("--v1-only", action="store_true", help="exercise v1 export/readout with synthetic events only")
    parser.add_argument("--adapter-only", action="store_true", help="exercise the file-export adapter with synthetic parts only")
    args = parser.parse_args()
    if args.v1_only:
        print(json.dumps(check_v1_readout(), sort_keys=True))
        return
    if args.adapter_only:
        print(json.dumps(check_file_export_adapter(), sort_keys=True))
        return
    inventory = check_event_inventory()
    identity_schematic = check_identity_schematic()
    if args.inventory_only:
        print(json.dumps({**inventory, "identity_schematic": identity_schematic}, sort_keys=True))
        return
    if not args.dsn:
        parser.error("--dsn is required unless --inventory-only is used")
    import psycopg2

    with psycopg2.connect(args.dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            if cursor.fetchone()[0] != "tranche_beta":
                raise SystemExit("Refusing to create fixtures outside tranche_beta")
            cursor.execute("""
                CREATE TEMP TABLE users (
                  id bigint PRIMARY KEY, created_at timestamptz,
                  email_verified boolean, is_beta boolean
                );
                CREATE TEMP TABLE invite_codes (
                  id bigint PRIMARY KEY, user_id bigint, cohort text,
                  created_at timestamptz, used_at timestamptz,
                  expires_at timestamptz, is_revoked boolean
                );
                CREATE TEMP TABLE feedback (
                  id bigint PRIMARY KEY, user_id bigint, created_at timestamptz, status text
                );
                CREATE TEMP TABLE earningsnerd_delivery_batches (
                  id bigint PRIMARY KEY, user_id bigint, status text,
                  provider_email_id text, first_dispatch_at timestamptz,
                  first_click_at timestamptz
                );
                CREATE TEMP TABLE earningsnerd_billing_payments (
                  stripe_payment_id text PRIMARY KEY, user_id bigint, livemode boolean,
                  amount_minor bigint, payment_type text, subscription_invoice boolean,
                  attribution text, paid_at timestamptz
                );
                INSERT INTO users VALUES
                  (1,'2026-09-21 09:00Z',true,true),
                  (2,'2026-09-21 09:00Z',true,true),
                  (3,'2026-09-21 09:00Z',true,true),
                  (4,'2026-09-21 09:00Z',false,true),
                  (5,'2026-09-21 09:00Z',true,true),
                  (6,'2026-09-21 09:00Z',true,true),
                  (8,'2026-09-21 09:00Z',true,true),
                  (9,'2026-09-29 09:00Z',true,true),
                  (10,'2026-09-28 00:00Z',true,true),
                  (11,'2026-09-29 09:00Z',true,true);
                INSERT INTO invite_codes VALUES
                  (101,1,'fixture-beta','2026-09-21 08:00Z','2026-09-21 09:00Z','2026-10-01',false),
                  (102,2,'fixture-beta','2026-09-21 08:00Z','2026-09-21 09:00Z','2026-10-01',false),
                  (103,3,'fixture-beta','2026-09-21 08:00Z','2026-09-21 09:00Z','2026-10-01',false),
                  (104,4,'fixture-beta','2026-09-21 08:00Z','2026-09-21 09:00Z','2026-10-01',false),
                  (105,NULL,'fixture-beta','2026-09-21 08:00Z',NULL,'2026-09-22',true),
                  (106,5,'fixture-beta','2026-09-21 08:00Z','2026-09-21 09:00Z','2026-10-01',false),
                  (107,6,'fixture-beta','2026-09-21 08:00Z','2026-09-21 09:00Z','2026-10-01',false),
                  (108,6,'fixture-beta','2026-09-21 08:00Z','2026-09-21 10:00Z','2026-10-01',false),
                  (109,8,'other-cohort','2026-09-21 08:00Z','2026-09-21 09:00Z','2026-10-01',false),
                  (110,NULL,'fixture-beta','2026-09-21 08:00Z',NULL,'2026-10-01',false),
                  (111,9,'fixture-beta','2026-09-21 08:00Z','2026-09-29 09:00Z','2026-10-01',false),
                  (112,10,'fixture-beta','2026-09-21 08:00Z','2026-09-28 00:00Z','2026-10-01',false),
                  (113,NULL,'fixture-beta','2026-09-28 00:00Z',NULL,'2026-10-01',false),
                  (114,NULL,'fixture-beta','2026-09-21 08:00Z',NULL,'2026-09-28 00:00Z',false),
                  (115,11,'fixture-beta','2026-09-21 08:00Z','2026-09-29 09:00Z','2026-10-01',false);
                INSERT INTO feedback VALUES
                  (201,1,'2026-09-22 09:00Z','new'),
                  (202,2,'2026-09-22 09:00Z','resolved'),
                  (203,3,'2026-09-22 09:00Z','new'),
                  (204,5,'2026-09-22 09:00Z','new');
                INSERT INTO earningsnerd_delivery_batches VALUES
                  (301,1,'accepted','email-a','2026-09-22 10:00Z','2026-09-22 11:00Z'),
                  (302,2,'accepted','email-b','2026-09-22 10:00Z',NULL),
                  (303,3,'accepted','email-c','2026-09-22 10:00Z','2026-09-22 11:00Z'),
                  (304,6,'accepted','email-d','2026-09-22 10:00Z','2026-09-29 11:00Z'),
                  (305,6,'ambiguous',NULL,'2026-09-22 10:00Z',NULL);
                INSERT INTO earningsnerd_billing_payments VALUES
                  ('live-eligible',1,true,3900,'payment_intent',true,'attributed','2026-09-23 09:00Z'),
                  ('test-mode',2,false,3900,'payment_intent',true,'attributed','2026-09-23 09:00Z'),
                  ('internal',3,true,3900,'payment_intent',true,'attributed','2026-09-23 09:00Z'),
                  ('zero-beta',6,true,0,'payment_intent',true,'attributed','2026-09-23 09:00Z'),
                  ('unsupported',6,true,3900,'manual',true,'attributed','2026-09-23 09:00Z'),
                  ('unattributed',NULL,true,3900,'charge',true,'unknown_customer','2026-09-23 09:00Z'),
                  ('non-subscription',6,true,3900,'charge',false,'attributed','2026-09-23 09:00Z');
            """)

            cursor.execute(query("db_roster.sql"), PARAMETERS)
            cols = [item.name for item in cursor.description]
            roster = [dict(zip(cols, row)) for row in cursor.fetchall()]
            eligible = {row["user_id"] for row in roster if row["eligible_verified"]}
            assert eligible == {1, 2, 6}, eligible
            assert len(roster) == 13, len(roster)
            revoked = next(row for row in roster if row["invite_id"] == 105)
            assert revoked["roster_state"] == "no linked user"
            assert revoked["pending_reachable_at_window_end_current_state"] is False
            assert next(row for row in roster if row["invite_id"] == 110)["pending_reachable_at_window_end_current_state"] is True
            late = next(row for row in roster if row["invite_id"] == 111)
            assert late["roster_state"] == "joined after window"
            assert late["redeemed_by_window_end"] is False
            assert late["pending_reachable_at_window_end_current_state"] is True
            boundary = next(row for row in roster if row["invite_id"] == 112)
            assert boundary["redeemed_by_window_end"] is False
            assert boundary["roster_state"] == "joined after window"
            assert boundary["pending_reachable_at_window_end_current_state"] is True
            assert next(row for row in roster if row["invite_id"] == 101)["pending_reachable_at_window_end_current_state"] is False
            assert all(row["invite_id"] != 113 for row in roster), "invite created at window end is outside the window"
            assert next(row for row in roster if row["invite_id"] == 114)["pending_reachable_at_window_end_current_state"] is False
            excluded_late = next(row for row in roster if row["invite_id"] == 115)
            assert excluded_late["excluded_user"] is True
            assert excluded_late["redeemed_by_window_end"] is False
            assert excluded_late["pending_reachable_at_window_end_current_state"] is False
            assert next(row for row in roster if row["invite_id"] == 108)["roster_state"] == "duplicate invite for user"
            assert next(row for row in roster if row["invite_id"] == 103)["excluded_user"]
            assert next(row for row in roster if row["invite_id"] == 106)["excluded_invite"]
            assert next(row for row in roster if row["invite_id"] == 104)["roster_state"] == "unverified"

            cursor.execute(query("db_support_alerts.sql"), PARAMETERS)
            cols = [item.name for item in cursor.description]
            support = dict(zip(cols, cursor.fetchone()))
            expected = {
                "eligible_verified_users": 3,
                "feedback_submissions": 2,
                "feedback_reporters": 2,
                "open_new": 1,
                "open_triaged": 0,
                "resolved": 1,
                "accepted_batches": 3,
                "first_clicked_batches": 1,
                "alerted_users": 3,
                "alert_clicked_users": 1,
            }
            assert support == expected, {"actual": support, "expected": expected}

            cursor.execute(query("db_paid_cohort.sql"), PARAMETERS)
            cols = [item.name for item in cursor.description]
            paid = dict(zip(cols, cursor.fetchone()))
            assert paid == {
                "eligible_verified_users": 3,
                "observed_paying_users": 1,
                "qualifying_payment_allocations": 1,
            }, paid

            # Browser event fixture truth table for the PostHog query contract.
            # The actual HogQL cannot be executed without a PostHog project.
            client_observed = {1, 3, 5, 6}
            summary_viewed = {1, 3, 5, 6}  # user 1 cached; user 6 fresh
            known_nonconsenting = {2}
            assert len(eligible) == 3
            assert eligible & client_observed == {1, 6}
            assert eligible & summary_viewed == {1, 6}
            assert eligible & known_nonconsenting == {2}
            assert eligible - client_observed == {2}
            print(json.dumps({
                "database": "tranche_beta (temporary tables; transaction rolled back)",
                "source_inventory": inventory,
                "identity_schematic": identity_schematic,
                "eligible_verified_ids": sorted(eligible),
                "eligible_denominator": len(eligible),
                "client_observed_fixture": 2,
                "client_unobserved_unknown_fixture": 1,
                "cached_or_fresh_summary_viewers_fixture": 2,
                "support_alert_counts": support,
                "paid_cohort_counts": paid,
                "result": "PASS",
            }, sort_keys=True))
        connection.rollback()


if __name__ == "__main__":
    main()
