/**
 * The password rule the auth pages state, mirrored from the server
 * (`backend/app/config.py`: PASSWORD_MIN_LENGTH, enforced by
 * `backend/app/services/password_utils.py::validate_password_strength`).
 *
 * The server stays the only judge: it rejects a short password and, while
 * PWNED_PASSWORD_CHECK_ENABLED holds its default (true), one found in the HaveIBeenPwned corpus
 * (`backend/app/services/pwned_passwords.py`). That lookup fails open (an outage or an error lets the
 * password through, so a third party never blocks a sign-up), which is why the sentence says the check
 * happens and never that a breached password is refused. The field's `minLength`, the strength meter's
 * "Too short" and the sentence a page shows read these two constants, so the number is never typed
 * by hand. `tests/unit/passwordRulesLockstep.spec.tsx` fails when the mirror drifts from the backend,
 * when the validator gains a rule beyond length, when the breach check's default turns off under the
 * sentence or the sentence promises a refusal, or when a password-handling file spells the length out
 * or drops the field's minimum.
 *
 * Not mirrored: the server's ceiling (password_utils.PASSWORD_MAX_LENGTH, 128 characters, far past
 * any passphrase a person types) and its unit (Python counts code points; the browser's `minLength`
 * and `.length` count UTF-16 units, so a password of astral characters such as emoji can clear the
 * field and still be refused). Either way the server refuses with a 422 whose `detail` is a list, and
 * how that reads on the form is the API client's (`lib/api/client.ts`), not this module's.
 */
export const PASSWORD_MIN_LENGTH = 12

export const PASSWORD_RULE = `At least ${PASSWORD_MIN_LENGTH} characters. A longer passphrase is stronger. We check new passwords against known data breaches.`
