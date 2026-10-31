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
retention purge deleted the row. The sweep was also user-wide, so a stolen copy rotated away before
a reset (by the attacker using it, or by the owner's own device refreshing after the theft) still
revoked, when replayed after the reset or a logout-all, the sessions the owner signed in to since.
E96 (Neil's 2026-10-25 decision: chain-scoped, no grace window) closed that: the sweep now revokes the
replayed token's own chain, so two tabs refreshing with one cookie, a lost refresh answer or a replay
on one device ends that device's chain and leaves the account's other sessions signed in.

**Rule.** Take the theft path (`RefreshTokenReuseError`) only when the presented token was rotated
away: `replaced_by_id IS NOT NULL`, which only rotation writes. It revokes that token's chain, the live
tokens its rotation links lead to, and follows a link only to the same user's newer token
(`refresh_token_service._live_descendants`), never every token of the account. Refuse
any other revoked token with a plain `RefreshTokenError`, which writes nothing. Only rotation may
write `replaced_by_id`; a new revocation path leaves it NULL. More generally, before code reads a
column's state as evidence that event X happened, list every writer of that column; if any writer
is not X, key the check on a field only X writes.

**Evidence.** `backend/app/services/refresh_token_service.py::rotate_refresh_token`. Since E127 (2026-10-19)
it and every revocation take the user's row lock first and read under it, so the second of two
refreshes with one cookie reads the first's rotation and takes this path, as it did while refresh ran
on the event loop. A logout reads the link too, for the same reason it is trusted here: a token with
`replaced_by_id` set was rotated, so a logout that finds its token rotated away follows the links to the
chain's live tip and revokes that, the session it was meant to end, and nothing else; it is no theft
signal (`lessons/ops-release-cached-filing-reads-before-yield.md`). The logout and the replay sweep walk
the same way (`_live_descendants`), so they agree on what a chain is.
`backend/tests/unit/test_refresh_token_revocation_kinds.py` drives change-password, logout-all,
reset and logout with two clients (separate cookie jars): the stale device gets a 401 that revokes
nothing and the other device's new session still refreshes. Restoring the unconditional sweep fails
all four. Its later tests pin the chain scope (E96): a replay on one device leaves the other device's
session refreshing, a copy the owner's own refresh rotated away, replayed after a reset, no longer ends
the new login, and a link no rotation writes (to another user, to an older token, to itself, to no row)
refuses the replay and revokes nothing past it.
`backend/tests/unit/test_replaced_by_id_writers_allowlist.py` holds every mention of
`replaced_by_id` in every Python, SQL, shell and workflow file that can reach the production
database (the whole repository but the browser app and the test homes: the backend and its
migrations, `ops/` detection SQL, the root `scripts/`, `tasks/` operator SQL, the workflows) to
rotation's own read and write, the chain walk the replay sweep and the logout share, the column definition and its
migration, counted per function, so a second write inside a listed function fails too. It counts
reads, so an aliased write cannot slip
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
reassigned, augmented or deleted, a token's `user` set or deleted, by name too, `del_attribute`
included) and every `merge` (a merged detached user deletes the tokens its copy lacks) counts as a
delete. They go by name, not type, so any object's `user` store and any `merge` in those files count
and need a reviewed entry saying they drop no token. Those checks know the
relationships by name, so a test holds the mappers to them: `User.refresh_tokens` is the only
relationship into the model and `user` its only one, and a second delete-orphan collection, a rename
or a relationship over the link (`t.replaced_by = None` writes it) fails it. Two deleters exist. The
retention purge deletes in ascending id order, so a chain's predecessor always goes before its
successor and keeps its link even if a run stops between batches
(`test_retention_purge.py::test_an_interrupted_purge_never_strips_a_remaining_tokens_rotation_link`).
An account's deletion cascades to all of its tokens in one transaction, so none is left to hold a link.
The gate scores its scan on planted forms and names its gaps: a generic helper elsewhere handed a
token or a model to delete or merge, or a token to cut from its user; the collection handed to any
helper that drops its members, one in the same module too, or reached through a binding other than
`x.refresh_tokens`, `getattr(x, "refresh_tokens")` or a plain `name = x.refresh_tokens` (a walrus,
a `getattr`-bound name, unpacking, an attribute holding it); a name from code the folder does not
run, a whole-row copy or load (`INSERT ... SELECT *`, a positional `INSERT ... VALUES`, `COPY`), a
write through an ORM synonym, a psql variable standing in for the column, dynamic SQL that builds
both names, and a same-kind swap inside one function.
Replaying a rotated-away token still revokes its live chain (`test_refresh_replay.py`,
`test_auth_token_flows.py`).
