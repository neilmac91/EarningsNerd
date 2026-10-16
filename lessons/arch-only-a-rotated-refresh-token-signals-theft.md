# Key the refresh-token theft sweep on a rotated-away token, never on any revoked one

Date: 2026-10-15 · Area: arch / authentication

**Context.** `refresh_token_service.rotate_refresh_token` treated every token with `revoked_at`
set as a replayed copy of a rotated token and revoked all of the user's live tokens. Rotation is
only one of six writers of `revoked_at`: logout, logout-all, a password change, a password reset and
the theft sweep itself revoke tokens too, without rotating them. A device signed out that way keeps
its cookie and presents it on its next silent refresh, so the sweep revoked the session the user had
just been given (the acting device after a password change, the new login after logout-all or a
reset). After a reset, whoever still held a token the reset itself revoked (a forgotten device, or a
stolen copy nobody refreshed before the reset) could sign the owner out on every request until the
retention purge deleted the row. Still open: the sweep is user-wide, so a stolen copy that was
rotated away before the reset, by the attacker using it or by the owner's own device refreshing
after the theft, is a rotated-away token, and replaying it after a reset or logout-all still revokes
the sessions the owner signed in to since, until the purge deletes that row 30 days after its
rotation. Scoping the sweep to the replayed token's own chain (walk `replaced_by_id` forward to its
head; no migration) would close that, but it narrows the theft response, so it is a separate
decision.

**Rule.** Take the theft path (revoke every live token, `RefreshTokenReuseError`) only when the
presented token was rotated away: `replaced_by_id IS NOT NULL`, which only rotation writes. Refuse
any other revoked token with a plain `RefreshTokenError`, which writes nothing. Only rotation may
write `replaced_by_id`; a new revocation path leaves it NULL. More generally, before code reads a
column's state as evidence that event X happened, list every writer of that column; if any writer
is not X, key the check on a field only X writes.

**Evidence.** `backend/app/services/refresh_token_service.py::rotate_refresh_token`;
`backend/tests/unit/test_refresh_token_revocation_kinds.py` drives change-password, logout-all,
reset and logout with two clients (separate cookie jars): the stale device gets a 401 that revokes
nothing and the other device's new session still refreshes. Restoring the unconditional sweep fails
all four. Its last test pins the residual: a copy the owner's own refresh rotated away, replayed
after a reset, still ends the new login.
`backend/tests/unit/test_replaced_by_id_writers_allowlist.py` holds every mention of
`replaced_by_id` in every Python, SQL, shell and workflow file that can reach the production
database (the whole repository but the browser app and the test homes: the backend and its
migrations, `ops/` detection SQL, the root `scripts/`, `tasks/` operator SQL, the workflows) to
rotation's own read and write, the column definition and its migration, counted per function, so a
second write inside a listed function fails too. It counts reads, so an aliased write cannot slip
past it; it folds names built from literals (`"_".join(("replaced", "by", "id"))`) and matches SQL
in any case; and in every file that names the model, its table, `User.refresh_tokens` or the column,
or imports a refresh-token module, it counts each place a column could be picked at run time
(`setattr` with a computed name, row data that is not a literal mapping such as `.update(carried)`,
`{col.name: v}` or `set_=data`, `text(sql)`, SQL assembled at run time wherever it is built or from
pieces (`+=`, a list join, psycopg2 composition), `EXECUTE` in a migration), since such a name
cannot be read off the source. Because the column is `ON DELETE SET NULL`, a delete writes it too:
deleting a successor clears its predecessor's link, so every delete in those files (a `delete` or
`Delete` call, aliased or handed on, or `DELETE FROM refresh_tokens`, `TRUNCATE` or `MERGE ... THEN
DELETE` in a string or a migration) is counted. `User.refresh_tokens` is `delete-orphan`, so a token
dropped from it is deleted at flush and strips its predecessor's link the same way: every drop
(`user.refresh_tokens.remove(t)`, `pop`, `clear`, an item or slice stored or deleted, the collection
reassigned, augmented or deleted, a token's `user` set or deleted, by name too) and every `merge` (a
merged detached user deletes the tokens its copy lacks) counts as a delete. Those checks know the
relationships by name, so a test holds the mappers to them: `User.refresh_tokens` is the only
relationship into the model and `user` its only one, and a second delete-orphan collection, a rename
or a relationship over the link (`t.replaced_by = None` writes it) fails it. The one refresh-token
deleter that exists, the retention purge, deletes in ascending id order, so a chain's predecessor
always goes before its successor and keeps its link even if a run stops between batches
(`test_retention_purge.py::test_an_interrupted_purge_never_strips_a_remaining_tokens_rotation_link`).
The gate scores its scan on planted forms and names its gaps: a generic helper elsewhere handed a
token or a model to delete or merge, or the collection to drop members from, a name from code the
folder does not run, a whole-row copy or load (`INSERT ... SELECT *`, a positional
`INSERT ... VALUES`, `COPY`), a write through an ORM synonym, a psql variable standing in for the
column, dynamic SQL that builds both names, and a same-kind swap inside one function.
Replaying a rotated-away token still revokes the live chain (`test_refresh_replay.py`,
`test_auth_token_flows.py`).
