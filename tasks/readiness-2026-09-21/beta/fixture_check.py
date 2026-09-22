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

import psycopg2

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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="isolated local tranche_beta DSN")
    parser.add_argument("--inventory-only", action="store_true", help="check browser event names without PostgreSQL")
    args = parser.parse_args()
    inventory = check_event_inventory()
    identity_schematic = check_identity_schematic()
    if args.inventory_only:
        print(json.dumps({**inventory, "identity_schematic": identity_schematic}, sort_keys=True))
        return
    if not args.dsn:
        parser.error("--dsn is required unless --inventory-only is used")
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
