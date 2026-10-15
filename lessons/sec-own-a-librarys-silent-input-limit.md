# Apply a library's input limit in our own code; a major bump can turn its silent truncation into an error

Date: 2026-10-15   Area: sec

**Context**: The password policy accepts up to 128 characters, which is up to 512 UTF-8 bytes,
and bcrypt reads only the first 72 bytes. `password_utils.py` passed the whole encoding to
`bcrypt.hashpw` and `bcrypt.checkpw`, and a comment said the excess was "silently truncated by the
algorithm". That was true of bcrypt 4. bcrypt 5.0.0, pinned in `backend/requirements.txt`, raises
`ValueError: password cannot be longer than 72 bytes` instead. Nothing above the hash caught it, so
register, reset-password and change-password answered 500 for a long passphrase or for about 37
non-ASCII characters. Login answered 401 for such a password even against the hash bcrypt 4 had
stored for it, and each attempt counted toward the account lockout. No test sent a password over
72 bytes, so the bump passed CI.

**Rule**: When a library caps or reshapes its input (bcrypt's 72 bytes, a column width, a payload
size), apply the cap explicitly at our call site, in every path that feeds it (hash and verify
alike), and test an input past the cap. Pick the cut that reproduces what is already stored (here
`encode('utf-8')[:72]`, bcrypt 4's own truncation), so that old records keep working without a
migration or a second format. A comment that describes a library's implicit behaviour cannot fail
when the library changes; the test can.

**Evidence**: `backend/app/services/password_utils.py` (`_bcrypt_input`); gate
`backend/tests/unit/test_password_byte_limit.py` (a 128-character password of 4-byte characters,
the exact 72-byte boundary, a character straddling byte 72, and a bcrypt-4-shaped hash of a long
password through login). Hashes made with bcrypt 4.3.0 from 84- to 512-byte passwords verify
under bcrypt 5.0.0 with the fix.
