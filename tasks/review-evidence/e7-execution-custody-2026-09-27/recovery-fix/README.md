# Pending reservation recovery correction

Code `daf9a32a9e2b4325fa42ae7997a732a1ac710193`. Hosted review identified commit-before-return loss: a pending reservation survived
but the public caller could not recover its identity. Two refutations failed: direct SQLite edits
are not a supported API, and the known context ID cannot satisfy settlement's lost reservation ID.
The public read-only recovery API now returns exact retained identity/prompt bytes with uncertain
delivery and redispatch prohibited. A precommit settlement intent is exposed and validated; it
cannot be reinterpreted as a new status. Ordinary and sealed journals with no pending row return null.

Independent delta review found a child-symlink escape under an otherwise safe parent directory.
A safe parent does not constrain a child symlink, and matching canonical hashes do not establish
root custody. All three complete intent/artifact/receipt paths now use the existing safe resolver.
Matching external and dangling intent symlinks fail closed. The final [review](recovery-api-review.md)
clears the exact code/test/doc hashes.

Each new boundary had one committed-state failing proof: selecting eligible rows instead of the
pending reservation, and resolving only the intent's parent directory. Original bytes were restored;
final focused tail: **25 passed, 2 warnings in 0.97s**. Full Ruff/Bandit/pytest, performance and four
PostgreSQL lanes: **3729 passed, 40 warnings in 157.93s (0:02:37)**, exit 0. All eleven locked files unchanged. Raw proof/gate files retain
the inherited logging teardown diagnostic. No provider calls or earlier denied proof was run.
