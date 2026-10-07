# Make an absence claim only from `git grep` over every tracked file

**Date:** 2026-10-07 · **Area:** verification / review / durable records

## Context

CODE RED decision record 12 (PR #1105) first stated that three manifest hashes "appear nowhere in the
repository". The search behind the sentence had been a `grep -r` filtered to Markdown, JSON and shell
files; the hashes are Python constants in `backend/evals/acceptance_source_contract.py`, added in PR #1028.
The record's independent reviewer found them with one `git grep -F` over all tracked files and blocked the
head. The sentence was corrected before merge (commit `2903ca9f`) and the defect recorded in
`tasks/code-red-20261004/runtime/control/APPOINTMENTS.json` (`chief_defects`). The same reviews had been
re-deriving the records' other invariants by hand at every PR — hash rows, closure chain, stamp ordering,
decision numbering, forbidden strings — so the gate for those landed with this lesson.

## Rule

1. A statement that something is absent from the repository is made only after `git grep -F` (or `-E`)
   over **all tracked files**, with no `--include`, extension or directory filter. Glob-filtered greps
   are for locating, never for asserting absence. State the command's scope with the claim.
2. When a reviewer has re-derived the same record invariant twice, write the machine check and land it
   in the same PR as the next record (CLAUDE.md rule 12). For the CODE RED runtime records that gate is
   `backend/tests/unit/test_code_red_runtime_records.py`: every `CHECKPOINT.md` hash row equals its
   file and every runtime file has a row; the exclusion closures chain append-only; the checkpoint and
   `APPOINTMENTS.json` are stamped no earlier than the newest closure; decisions are numbered
   contiguously; every JSON parses; no private artifact URL, local home path or upload-area path is
   written.

## Evidence

- `tasks/code-red-20261004/runtime/control/DECISIONS-12.md` — "Chief defect caught by this record's reviewer"
  and the corrected field 4.
- `tasks/code-red-20261004/runtime/control/APPOINTMENTS.json` — `chief_defects[3]`.
- `backend/tests/unit/test_code_red_runtime_records.py` — the gate; each test fails on the defect it
  guards (byte tamper, untabled file, early stamp, numbering gap, chain break, private URL, broken JSON).
