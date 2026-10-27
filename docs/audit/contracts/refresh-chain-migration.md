# Refresh-token chain contract (E96)

Day-zero interface from Agent A (identity) for Agent E (models, migrations, registration) and for the
browser-session work that consumes it (E29, E157, E121). It fixes what a refresh-token *chain* is, what a
replay revokes, the lock order every writer keeps, the successor foreign key and index Agent E lands, and the
per-IP limit on `POST /api/auth/refresh`. Code is truth: where this document and the code disagree after
either lands, the code wins and this file is corrected in that pull request ([AGENTS.md §2](../../../AGENTS.md#2-precedence-when-documents-conflict)).

| | |
| --- | --- |
| Item | E96 (P1, high tier: auth, models, migrations) |
| Semantics owner | Agent A: `backend/app/services/refresh_token_service.py`, `backend/app/routers/auth.py`, their tests |
| Schema owner | Agent E: `backend/app/models/refresh_token.py`, one new file in `backend/migrations/` |
| Consumers | E29 and E157 (browser session transitions), E121 (refused-refresh response), F53 (founder-owned `/security` text) |
| Accepted policy | Neil, 2026-10-25: chain-scoped replay revocation, single-use tokens, **no grace period** |
| Base read | `main` at `086de72` |

## 1. What exists today

- Every rotation runs under the account's users row lock (`lock_user_tokens`, `FOR NO KEY UPDATE`), re-reads the
  presented token, mints a successor, revokes the presented token and writes `replaced_by_id` = successor, all in
  one transaction ([`refresh_token_service.py`](../../../backend/app/services/refresh_token_service.py)
  `rotate_refresh_token`). Rotation is the only writer of `replaced_by_id`
  (`backend/tests/unit/test_replaced_by_id_writers_allowlist.py`).
- A presented token that is revoked **and** has `replaced_by_id` set is a replay. Today it calls
  `revoke_all_for_user`: every session of the account, on every device, ends.
  [`lessons/arch-only-a-rotated-refresh-token-signals-theft.md`](../../../lessons/arch-only-a-rotated-refresh-token-signals-theft.md)
  keys the sweep on that link and must keep doing so.
- A token revoked any other way (logout, logout-all, password change or reset, the sweep) is refused and nothing is
  written.
- `revoke_refresh_token` (logout) already walks forward from the presented token along `replaced_by_id` to the
  chain's live tip and revokes that tip only.
- `replaced_by_id` references `refresh_tokens(id)` `ON DELETE SET NULL`, unindexed
  ([`20260613_create_refresh_tokens.sql`](../../../backend/migrations/20260613_create_refresh_tokens.sql)).
  The retention purge deletes dead tokens in ascending id order so a predecessor goes before its successor and
  keeps its link (`backend/app/services/retention_service.py` `_purge`).
- Of two tabs refreshing with one cookie, the second always waits for the first's commit and then meets the replay
  branch. So today a two-tab race signs the account out everywhere.

## 2. Definitions

**Chain.** The tokens one sign-in mints and its rotations supersede: a mint (password login, OAuth callback, the
token a password change issues) followed by each successor that rotation linked to through `replaced_by_id`.

**Well-formed link.** A link from token `t` to `replaced_by_id = s` is followed only when all three hold:

1. the row `s` exists;
2. `s.user_id == t.user_id`;
3. `s.id > t.id`. A successor is always minted after the token it replaces, so a link to an equal or lower id is
   malformed. This guard also makes a cycle impossible to follow.

A link that fails any of the three is not followed. The walk ends at `t`. The anomaly is logged with token ids and
the user id only: never a raw token, a token hash, an IP or an IP hash.

**Descendants of `t`.** Every token reached from `t` by following well-formed links, `t` excluded.

**Live.** `revoked_at IS NULL` and `expires_at` not passed. A replay revokes descendants whose `revoked_at` is null
whatever their expiry, so an expired tip cannot be revived by a later clock or setting change.

No chain-id column is added. The forward links already identify a chain for every rotation that has not been
purged, and a backfill could not recover links that `SET NULL` has already severed (§6).

## 3. Replay semantics (the behaviour change)

When the presented token `t`, re-read under the lock, has `revoked_at` set and `replaced_by_id` set:

1. Revoke every descendant of `t` whose `revoked_at` is null (`revoked_at = now`, naive UTC as today).
2. Do not revoke anything outside `t`'s descendants. Other chains of the same account stay live.
3. Commit the revocation, then refuse the request: `RefreshTokenReuseError`, answered as today with
   `401 {"detail": "Your session has ended. Log in again."}` and `WWW-Authenticate: Bearer`.
4. Log one warning with the user id and the number revoked, as today.

Unchanged: a token revoked without rotation is refused with no write; an unknown, expired or inactive-user token is
refused with no write; a live token rotates as before.

**Ancestors** of `t` were each revoked by the rotation that superseded them, so the sweep touches none. It reads
forward links only and neither revokes nor inspects an ancestor.

**Concurrent use of one cookie.** The first request rotates and mints successor `s1`. The second waits on the lock,
re-reads `t`, sees the link and revokes `s1`. At most one successor is ever minted from `t`; both requests' holders
then need to log in again. No grace window applies. The product does not claim that a dropped refresh answer
recovers: a tab whose answer was lost presents `t` again and that chain ends.

**Malformed references.** A cross-user, backward, cyclic or dangling link stops the walk, as §2 defines. It never
authorizes a token and never revokes a session outside the presented token's account. A dangling link cannot exist
under `ON DELETE SET NULL` (the delete nulls it), nor under `NO ACTION` (the delete is refused), so it is only
reachable through a manual write; it is still guarded.

**Query shape.** A single ORM statement over a recursive CTE (`select(...).cte(recursive=True)`), seeded with `t`,
whose recursive term joins `refresh_tokens.id = chain.replaced_by_id` with the user-id and increasing-id guards of
§2. The `UPDATE ... WHERE id IN (descendants) AND revoked_at IS NULL` then runs inside the same transaction, after
the lock. It must run on SQLite and PostgreSQL alike and needs no raw SQL (CLAUDE.md API conventions). The logout
walk (`revoke_refresh_token`) adopts the same three guards so the two walks cannot disagree about a chain.

## 4. Lock order (unchanged, restated so consumers can rely on it)

Every rotation and revocation takes the users row lock before reading the tokens it writes, and holds it to commit:

| Writer | Scope | Lock |
| --- | --- | --- |
| refresh (rotate) | the presented token; on replay, its descendants | users row, then token re-read |
| logout | the presented chain's live tip | users row, then token re-read |
| logout-all | every active token of the account | users row |
| password change | every active token of the account, plus the new hash | users row first (`stage_password_change`) |
| password reset | every active token of the account, plus the new hash | users row (`complete_password_reset`, through `revoke_all_for_user`) |
| password login mint | a new token, after re-checking the verified hash | users row (`record_password_login`) |
| account deletion | every token, through the ORM cascade (`db.delete(user)`, one DELETE per token) | users row, `FOR UPDATE` (`user_account_service.delete_user`) |

E157's expired-access logout-all fallback takes the same lock, after validating the presented refresh credential
belongs to the account it sweeps. The logout-all, reset, change and deletion scopes stay account-wide. Only the
replay sweep narrows.

## 5. Successor foreign key and index (Agent E)

Agent E lands one new idempotent file in `backend/migrations/` and the matching model metadata, schema-first: it
merges and deploys before Agent A's sweep change depends on it. The sweep in §3 does not need the schema to be
correct. The schema makes link loss fail loudly and keeps the purge's foreign-key work indexed.

1. **Index** `refresh_tokens(replaced_by_id)`. Name it as SQLAlchemy names a column's `index=True`
   (`ix_refresh_tokens_replaced_by_id`), so `create_all` on a fresh database and the migration converge on one
   index. Without it every deleted token makes PostgreSQL scan the table for rows that reference it, under either
   delete rule.
2. **Foreign key** `replaced_by_id REFERENCES refresh_tokens(id)` with **`ON DELETE NO ACTION`**, replacing
   `SET NULL`. Deleting a successor while a surviving row references it then fails. PostgreSQL checks a
   non-deferred NO ACTION constraint at the end of each statement, so a purge batch that deletes a predecessor and
   its successor in one statement passes. Account deletion does not delete the tokens in one statement:
   `user_account_service.delete_user` calls `db.delete(user)`, and the relationship's `cascade="all, delete-orphan"`
   makes the ORM issue one DELETE per token before the user's own. It passes under NO ACTION only while each
   predecessor is deleted no later than its successor. SQLAlchemy's unit of work orders a mapper's deletes by
   primary key, which a well-formed chain (§2, guard 3) satisfies. Test 5 in §8 proves this on PostgreSQL;
   this sentence alone does not.
3. **Model**: `replaced_by_id = Column(Integer, ForeignKey("refresh_tokens.id"), nullable=True, index=True)`
   (no `ondelete`, which PostgreSQL defaults to NO ACTION). Update the model's docstring sentence on the sweep
   to say "revokes that chain's descendants".
4. **Lock safety** ([CLAUDE.md rule 3](../../../CLAUDE.md#non-negotiable-rules),
   `backend/tests/unit/test_migration_lock_safety.py`): `refresh_tokens` exists, so the index is guarded by a
   `pg_indexes` check in a `DO $$` block (or built `CONCURRENTLY` outside a transaction). The foreign-key swap is
   guarded by a `pg_constraint` lookup on the column's constraint (`conrelid = 'refresh_tokens'::regclass`,
   `contype = 'f'`, the `replaced_by_id` attribute in `conkey`). While `confdeltype = 'n'` (SET NULL), one block
   drops that constraint by the name it finds and adds the NO ACTION one `NOT VALID` under the explicit name
   `refresh_tokens_replaced_by_id_fkey`. That is PostgreSQL's default name for the column's constraint, the one
   `create_all` gives a fresh database, so fresh and migrated databases converge. A second, separate block runs
   `VALIDATE CONSTRAINT` while that constraint's `convalidated = false`. `apply_migrations.sh` runs a file with
   `psql -f`, not in one transaction, so a validation cut off by its timeout is finished by the next run instead of
   being skipped as converged.
5. **Pre-flight, read-only and outside the migration**: Agent E's readback reports the count of links that §2
   calls malformed, `refresh_tokens t JOIN refresh_tokens s ON s.id = t.replaced_by_id WHERE s.user_id <> t.user_id
   OR s.id <= t.id`, and never fails a deploy on it. Such a link does not violate the foreign key, so `VALIDATE`
   cannot fail on it, and under `SET NULL` no dangling link exists for it to fail on either. Rotation never writes
   a malformed link, so a non-zero count is a finding to report, not a row to repair in the file.
6. **Evidence Agent E supplies**: the migrations-postgres fresh, repeat and reset-and-reapply passes, and a catalog
   readback (`pg_indexes`, `pg_constraint.confdeltype = 'a'`, `convalidated = true`) after each pass.

### Purge order under NO ACTION

With NO ACTION, `_purge` fails a batch that deletes a successor while its predecessor survives. For a chain rotation
wrote, that cannot happen. The predicate is `expires_at < cutoff OR revoked_at < cutoff`, and rotation sets the
predecessor's `revoked_at` to the moment it mints the successor, before the successor's own revocation or expiry.
So the predecessor qualifies no later than its successor whatever the token lifetime, and the ascending-id batches
delete it first or in the same statement. Only a manual row or a clock moved backwards could put a successor first.
As defence in depth, the refresh-token target's predicate gains a correlated guard: no row that does **not** itself
qualify references this token, i.e. `NOT EXISTS (SELECT 1 FROM refresh_tokens r WHERE r.replaced_by_id =
refresh_tokens.id AND NOT <the predicate on r>)`, served by the new index. A plain `NOT EXISTS` on any referencer
would be wrong. It would hold back every token that still has a predecessor. `_purge` ends at its first short
batch, so it would then delete one token per chain per run while active sessions add dozens a day. The guard lands
before or with the foreign-key change, never after it, with a test that purges a long qualifying chain in one run.
**Owner to confirm with the CTO**: `retention_service.py` is a job file outside both agents' named lists. Agent A
supplies the patch and the purge-order tests either way.

## 6. Limits stated, not hidden

- A link `ON DELETE SET NULL` has already nulled in production, by a manual delete or by a purge run from before
  the ascending-id order, cannot be rebuilt from code or data. Such a token reads as revoked-without-rotation and is
  refused without a sweep. Nothing here fabricates ancestry. Today's purge cannot sever a link (§5).
- A replay revokes one chain. If an attacker's stolen token and the user's session are in the same chain (the
  attacker rotated first), the user's tip is revoked with it, as today. Detecting which party holds the tip is out
  of scope.
- `ip_hash` stays audit context only. It is never used to scope a sweep.

## 7. Per-IP limit on `POST /api/auth/refresh`

- **Mechanism**: the existing in-memory `RateLimiter` and `enforce_rate_limit` in
  [`rate_limiter.py`](../../../backend/app/services/rate_limiter.py), keyed by `get_client_ip`. That reads
  `X-Forwarded-For` only through `settings.TRUSTED_PROXY_HOPS` from the right and otherwise the socket peer, so a
  forged header cannot reset the bucket. It is per process (the API scales to at most two instances), like every
  auth limiter. Once it tracks `RATE_LIMITER_MAX_KEYS` keys (10,000), it refuses every key it has not seen for the
  window, so a spray of source addresses would refuse new addresses' refreshes too. That is a fail-closed 429,
  which the consumer obligation below keeps from reading as session loss.
- **Placement**: before any database work. A limited request takes no pool connection and no row lock.
- **Answer**: `429` with `Retry-After` and a `detail` string, the existing convention. No cookie is set or deleted.
- **Threshold**: chosen from a fixture burst of N same-browser tabs waking at once (one refresh per tab, each tab
  single-flighting its own refreshes in `ensureRefreshed`) plus a shared-NAT allowance, and recorded with the burst
  numbers in the E96 pull request. The proposal to test against is 60 requests per 60 s per IP. A module constant in
  `routers/auth.py` beside the other auth limiters, with no new setting unless measurement shows one is needed. If
  one is needed, Agent E registers it.
- **Logs**: no raw token, token hash or IP is added to any log line. The limiter's key lives only in process memory.
- **Consumer obligation (E29)**: the browser must not read a `429` from `/refresh` as session loss.
  `frontend/lib/api/client.ts` already confirms session loss only on a refresh `401` (`sessionLossConfirmed`), and
  that must stay true.

## 8. Tests Agent A supplies (the E96 pull request)

From `backend/`, with `REFRESH_CONCURRENCY_TEST_DATABASE_URL` naming a disposable PostgreSQL database. A skip is
missing evidence, not a pass.

1. Two chains, one account: a replay of an ancestor in chain A revokes A's tip and is refused, and chain B's live
   token then rotates. Mutation proof: today's `revoke_all_for_user` call fails this case.
2. Concurrent use of one cookie on PostgreSQL: exactly one successor exists afterwards and it is revoked, and the
   second answer is the replay 401.
3. Malformed links (cross-user, backward, self-cycle, dangling): no token authorized, nothing outside the walk's
   well-formed prefix revoked, one anomaly log line carrying ids only.
4. Logout, logout-all, reset, change and deletion keep their scopes and their users-row-first lock (statement spy,
   `lessons/test-pin-a-row-lock-with-a-statement-spy.md`).
5. Purge and deletion on PostgreSQL under NO ACTION: chains purge in order; a successor whose predecessor survives
   is held, not failed; an account with a multi-token chain deletes through `delete_user`'s per-row ORM cascade, and
   does so without deadlock beside a concurrent refresh of the same account.
6. Limiter: a fixture burst of N tabs passes, a sustained loop is limited with `Retry-After`, and a forged
   `X-Forwarded-For` with `TRUSTED_PROXY_HOPS` at its deployed value does not escape the bucket.

7. `backend/tests/unit/test_replaced_by_id_writers_allowlist.py` counts every mention of the column in backend Python,
   SQL and shell. Each new mention gets its reviewed entry in `ALLOWED_MENTIONS` in the pull request that adds it:
   the walk in `refresh_token_service.py` (A), the purge guard in `retention_service.py` (its owner) and the new
   migration file (E).

The locked anchors keep passing unchanged: `test_auth_flow.py`'s replay case asserts only the 401, and T8,
`test_refresh_replay.py`, revokes the replayed token's own live successor, which is its descendant. The one
expectation that changes is the last case of `test_refresh_token_revocation_kinds.py`,
`test_a_copy_rotated_away_before_a_reset_still_takes_the_user_wide_sweep`. Its docstring says chain scoping "would
flip the last two assertions", and the E96 pull request flips them and names that as the accepted change.

## 9. What consumers may rely on

- The replay answer, its status, detail and headers are unchanged. E29 and E157 need no new client branch for E96.
- A refused refresh (any `RefreshTokenError`) sets no cookie today. The injected-`Response` deletions are discarded
  when the route raises (E121's row in `tasks/todo.md`). E96 does not change that. E121 decides it, after E29 and
  E157 show a deletion cannot erase a newer login's cookies.
- The `/security` page's sentence on reused tokens is founder-owned (F53). E96 makes "a reused token ends that
  session's chain" true; it changes no public copy.
