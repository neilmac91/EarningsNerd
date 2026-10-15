# Key the refresh-token theft sweep on a rotated-away token, never on any revoked one

Date: 2026-10-15 · Area: arch / authentication

**Context.** `refresh_token_service.rotate_refresh_token` treated every token with `revoked_at`
set as a replayed copy of a rotated token and revoked all of the user's live tokens. Rotation is
only one of five writers of `revoked_at`: logout, logout-all, a password change and a password
reset revoke tokens too, without rotating them. A device signed out that way keeps its cookie and
presents it on its next silent refresh, so the sweep revoked the session the user had just been
given (the acting device after a password change, the new login after logout-all or a reset).
After a reset, whoever still held an evicted token could sign the owner out on every request until
the retention purge deleted the row.

**Rule.** Take the theft path (revoke every live token, `RefreshTokenReuseError`) only when the
presented token was rotated away: `replaced_by_id IS NOT NULL`, which only rotation writes. Refuse
any other revoked token with a plain `RefreshTokenError`, which writes nothing. A new revocation
path must leave `replaced_by_id` NULL. More generally, before code reads a column's state as
evidence that event X happened, list every writer of that column; if any writer is not X, key the
check on a field only X writes.

**Evidence.** `backend/app/services/refresh_token_service.py::rotate_refresh_token`;
`backend/tests/unit/test_refresh_token_revocation_kinds.py` drives change-password, logout-all,
reset and logout with two clients (separate cookie jars): the stale device gets a 401 that revokes
nothing and the other device's new session still refreshes, and replaying a rotated-away token
still revokes the live chain. Restoring the unconditional sweep fails the four revocation cases.
