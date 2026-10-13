/**
 * The password rule the auth pages state, mirrored from the server
 * (`backend/app/config.py`: PASSWORD_MIN_LENGTH, enforced by
 * `backend/app/services/password_utils.py::validate_password_strength`).
 *
 * The server stays the only judge: it rejects a short password and, while
 * PWNED_PASSWORD_CHECK_ENABLED holds its default (true), one found in the HaveIBeenPwned corpus
 * (`backend/app/services/pwned_passwords.py`). The field's `minLength`, the strength meter's
 * "Too short" and the sentence a page shows read these two constants, so the number is never typed
 * by hand. `tests/unit/passwordRulesLockstep.spec.ts` fails when the mirror drifts from the backend,
 * when the breach check's default turns off under the sentence, or when a file spells the length out.
 */
export const PASSWORD_MIN_LENGTH = 12

export const PASSWORD_RULE = `At least ${PASSWORD_MIN_LENGTH} characters. A longer passphrase is stronger. Breached passwords are rejected.`
