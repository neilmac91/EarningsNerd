# Leave the working tree untouched while a background full-suite run reads it

**Date:** 2026-10-02  
**Area:** Testing & verification / local gates

**Context:** A full backend run was started in the background and a cherry-pick was begun in the
same checkout while it ran. The cherry-pick left conflict markers in `app/routers/auth.py` for a
few minutes; an AST gate that parses every router file from disk read the file in that window and
failed with a `SyntaxError`, so the run reported one failure that the committed code never had.

**Rule:** Source-reading gates (AST walks, allow-list scans, `git ls-files` selectors) parse the
working tree, not the commit. While a background suite runs in a checkout, make no edits, merges,
cherry-picks or checkouts there; do that work in another worktree or after the run. When a
background run fails only in such a gate, check whether the tree changed under it before
treating the failure as real, and re-run on the quiescent tree.

**Evidence:** PR #1069: the run on `29e47ac7` reported `1 failed, 5651 passed` with the single
failure in `test_user_keyed_rate_limits_allowlist.py` quoting `<<<<<<< HEAD`; the clean run on the
final head is recorded in the PR body.
