"""Run the kit's exact read-only SQL against temporary synthetic PostgreSQL tables.

Requires an explicit DSN for an isolated `tranche_beta` database. No application
tables, customer records, provider calls, or production configuration are used.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

import psycopg2


HERE = Path(__file__).resolve().parent
PARAMETERS = {
    "cohort": "fixture-beta",
    "window_start": "2026-09-21T00:00:00Z",
    "window_end": "2026-09-28T00:00:00Z",
    "excluded_user_ids": [3],
    "excluded_invite_ids": [106],
}


def query(name: str) -> str:
    source = (HERE / name).read_text()
    return re.sub(r":'([a-z_]+)'", r"%(\1)s", source)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True, help="isolated local tranche_beta DSN")
    args = parser.parse_args()
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
                  (9,'2026-09-29 09:00Z',true,true);
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
                  (111,9,'fixture-beta','2026-09-21 08:00Z','2026-09-29 09:00Z','2026-10-01',false);
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
            assert len(roster) == 10, len(roster)
            revoked = next(row for row in roster if row["invite_id"] == 105)
            assert revoked["roster_state"] == "no linked user"
            assert revoked["pending_reachable_at_window_end_current_state"] is False
            assert next(row for row in roster if row["invite_id"] == 110)["pending_reachable_at_window_end_current_state"] is True
            late = next(row for row in roster if row["invite_id"] == 111)
            assert late["roster_state"] == "joined after window"
            assert late["redeemed_by_window_end"] is False
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
