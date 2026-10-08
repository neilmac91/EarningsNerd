# Make an absence claim only from `git grep` over every tracked file

**Date:** 2026-10-07 · **Area:** verification / review / durable records

## Context

CODE RED decision record 12 (PR #1105) first stated, on the blocked head `17dbb5c5` (named with its correction
in the commit message of `adf98331` on main), that "none of the three component hashes … appears anywhere in
the repository". The search behind the sentence had been a `grep -r` filtered to Markdown,
JSON and shell files; the hashes are Python constants in `backend/evals/acceptance_source_contract.py`,
added in PR #1028. The record's independent reviewer found them with a `git grep` over all tracked files
and blocked the head. The sentence was corrected before merge (commit `2903ca9f` on the PR #1105 branch,
squash-merged to main as `adf98331`) and the defect recorded in
`tasks/code-red-20261004/runtime/control/APPOINTMENTS.json` (`chief_defects`).

## Rule

A statement that something is absent from the repository is made only after `git grep -F` (or `-E`) over
**all tracked files**, with no `--include`, extension or directory filter. Glob-filtered greps are for
locating, never for asserting absence. State the command's scope with the claim. The same applies to a
test that asserts absence: it scans every file in its tree, never an allow-list of suffixes.

## Evidence

- `tasks/code-red-20261004/runtime/control/DECISIONS-12.md` — "Chief defect caught by this record's reviewer"
  and the corrected field 4.
- `tasks/code-red-20261004/runtime/control/APPOINTMENTS.json` — `chief_defects[3]`.
- `backend/tests/unit/test_code_red_runtime_records.py` — the rule-12 gate for the CODE RED runtime
  records (CLAUDE.md rule 12; `lessons/arch-structural-gates-over-prose-rules.md`), landed with this
  lesson because reviewers had re-derived the same invariants at every record PR. Its forbidden-string
  test applies this rule: every file in the tree is scanned, whatever its suffix. Each test fails on the
  defect it guards (byte tamper, untabled file, early stamp, numbering gap, chain break, private URL,
  broken JSON).
