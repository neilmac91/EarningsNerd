# Apply a library's input limit in our own code; a major bump can turn its silent truncation into an error

Date: 2026-10-15   Area: arch

**Context**: The password policy accepts up to 128 characters, which is up to 512 UTF-8 bytes,
and bcrypt reads only the first 72 bytes. `password_utils.py` passed the whole encoding to
`bcrypt.hashpw` and `bcrypt.checkpw`, and a comment said the excess was "silently truncated by the
algorithm". That was true of bcrypt 4. bcrypt 5.0.0, pinned in `backend/requirements.txt`, raises
`ValueError: password cannot be longer than 72 bytes` instead. Nothing above the hash caught it, so
register, reset-password and change-password answered 500 for a long passphrase or for about 37
non-ASCII characters. Login answered 401 for such a password even against the hash bcrypt 4 had
stored for it, and each attempt counted toward the account lockout. No test sent a password over
72 bytes, so the bump passed CI.

**Rule**: When a library caps its input and stored records depend on what it did past the cap
(every stored bcrypt hash is the hash of the password's first 72 bytes), apply the cap explicitly
in our own code, in every path that feeds the library (hash and verify alike, through one helper),
and test an input past the cap. Reproduce the library's old handling exactly (here
`encode('utf-8')[:72]`, bcrypt 4's own truncation), so old records keep working without a
migration or a second format. Any other input limit, such as a column width or a payload size, is
not ours to cut to fit: validate and reject the input where it enters (CLAUDE.md rule 9). A comment
that describes a library's implicit behaviour cannot fail when the library changes; the test can.
Once the cut is ours, every check of that input must also see what the library keys on: a breach
screen of the whole password alone passed a breached 72-byte password with any tail appended, while
the hash, and so login, keyed on the breached part. Screen a text that shares the key exactly: when
byte 72 splits a character, its lead bytes are part of the key, so the screened text ends with the
whole split character. Dropping that character screened a text with a different key, and a breached
text ending in it passed while it opened the account.

**Evidence**: `backend/app/services/password_utils.py` (`_bcrypt_input`, `bcrypt_screen_texts`); gate
`backend/tests/unit/test_password_byte_limit.py` (a 128-character password of 4-byte characters,
the exact 72-byte boundary, a character straddling byte 72, a bcrypt-4-shaped hash of a long
password through login and change-password, and an AST walk that keeps every bcrypt call behind
`_bcrypt_input`, scored on planted forms with its gaps named; breach screening of the 72-byte
prefix through `pwned_passwords.is_password_pwned` and register, and a check that the first
screened text verifies against the password's own hash, a split 2- or 4-byte character included).
Hashes made with bcrypt 4.3.0 from 84- to 512-byte passwords verify under bcrypt 5.0.0 with the fix.
