# Stamp-`t` snapshot census (item C, 2026-10-01)

This is a read-only count of persisted `Filing.xbrl_data` snapshots. It must run before #1039 (stamp `t`) is released and before any later drain. It follows the delegated decision in comment 5925688598 on PR #1029:
- count and report the affected snapshots, with the total population as denominator;
- distinguish legacy, fallback, unknown and malformed cases;
- do not clear, overwrite or re-extract anything.

**Status: blocked on access.** The Claude session cannot reach the production Cloud SQL database (its GCP access token is invalid), so the founder or an agent with production read access must run the query.

## Run (read-only)

`census.sql` runs inside `BEGIN TRANSACTION READ ONLY; … ROLLBACK;`. PostgreSQL rejects any write inside that transaction; this was checked with `cannot execute INSERT in a read-only transaction`.

Run it through the Cloud SQL proxy, as `deploy-backend` does:

```bash
./cloud-sql-proxy --port 5432 earnings-nerd:us-west1:earningsnerd-db &
psql "host=127.0.0.1 port=5432 dbname=<db> user=<read-capable user>" -f census.sql
```

Paste the output table into PR #1029 or #1039.

### Cloud SQL Studio (single statement)

Some consoles, Cloud SQL Studio included, may not accept explicit `BEGIN`/`ROLLBACK` statements. For those, paste `census_select_only.sql` instead.
- It is the same query as `census.sql`, byte for byte, but as one `SELECT` with no transaction statements. A lone `SELECT` writes nothing.
- SHA-256: `census.sql` is `2e9284b9…4823c`; `census_select_only.sql` is `f16e21b1…611b2`.
- It was re-checked on a local PostgreSQL 16 scratch database.

## Classes

The classes follow `app/services/edgar/xbrl_service.py` on main `0032bca8`. Classes 5–8 are the affected population.

| Class | Meaning | Affected by a `t` refresh? |
| --- | --- | --- |
| `0_no_snapshot` | `xbrl_data` is NULL | No. Extraction runs fresh. |
| `1_unusable_*` | Not an object, or none of the eight keys `_persisted_xbrl()` checks is a non-empty list | No. The snapshot is ignored and re-extracted. |
| `2_net_income_malformed` | `net_income` is not a list, or has a non-object element | Unknown. Report it. |
| `3_no_net_income` | `net_income` is absent, null or empty | No returns line can name a numerator. |
| `4_tagged_scope_renders` | Every net-income point has a non-blank `raw_tag`, i.e. the post-#925 instance path | No. Scope renders. |
| `5_mixed_partially_tagged` | Some net-income points are tagged and some are not | Partly. It depends on the selected point. |
| `6_untagged_legacy_instance` | No `raw_tag`, and every point carries `currency`. This is the pre-#925 instance-path shape. | **Yes.** Renders `(numerator scope unestablished)`. |
| `7_untagged_fallback_or_older` | No `raw_tag` and no `currency`. This is the companyfacts fallback, or an older shape. | **Yes**, by design for the fallback. |
| `8_untagged_unknown_shape` | Untagged, with mixed `currency` presence | Yes. Report it. |

The output also shows, for each class, the count with an existing summary and the split by form (10-K, 10-Q, foreign annual, other). The last row is the total, which is the denominator.

## Validation

The query was run on a local PostgreSQL 16 database with 12 synthetic rows, one or more per class. Every row landed in its expected class. A first draft classified untagged points as tagged, because `NOT (NULL = 'string' …)` evaluates to NULL; that was fixed with `coalesce(…, false)` and re-verified.

The `currency` heuristic only separates the instance path from the fallback path for snapshots this code wrote. Older formats fall into class 7 or 8 and are reported as such, not guessed.

## Not authorized here

The decision rules out the following. Any repair or drain needs its own preservation and migration proposal.
- clearing or re-extracting snapshots;
- regenerating summaries;
- a stamp-`t` drain.

## Result (2026-10-01T23:16Z, Codex in the founder's Cloud SQL Studio session as `appuser`; PR #1029 comment 5942525078)

| class | filings | with_summary | k10 | q10 | foreign_annual | other_forms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0_no_snapshot | 38392 | 2 | 8471 | 24855 | 223 | 4843 |
| 4_tagged_scope_renders | 1 | 1 | 0 | 1 | 0 | 0 |
| 6_untagged_legacy_instance | 52 | 46 | 30 | 20 | 2 | 0 |
| 7_untagged_fallback_or_older | 6 | 1 | 2 | 4 | 0 | 0 |
| total | 38451 | 50 | 8503 | 24880 | 225 | 4843 |

There are **58 untagged snapshots** (classes 6 and 7); 47 of them have a summary. Under stamp `t` these render as "numerator scope unestablished". This is truthful, and it is the behaviour to preserve. No malformed, mixed, unknown-shape or unusable class appeared.

**How it ran.**
- A first attempt as the IAM user failed with `pq: permission denied for table filings`; that failure is retained.
- The editor batch contained the original script twice. Both read-only copies ran, and their result tables are identical.
- The file's SHA-256 `2e9284b9…4823c` identifies the source file, not the duplicated batch.

**Not authorized by this result:** clearing, rewriting, re-extracting, refreshing or draining snapshots.
