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
`replaced_by_id` in `backend/app` (reads included, so an aliased or by-name write cannot slip past
it) to rotation's own read and write and the column definition, and scores its scan on planted forms. Replaying a rotated-away token still revokes the live chain
(`test_refresh_replay.py`, `test_auth_token_flows.py`).
