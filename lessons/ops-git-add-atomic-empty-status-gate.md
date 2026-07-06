# Require an empty git status after every completing commit; never chain add-path recovery

Date: 2026-07-03   Area: ops

**Context**: The summary-layout commit shipped docs without its actual CSS because a bad root-relative path poisoned the whole multi-path add — git add is atomic across pathspecs. Caught by the stop hook, not by me.

**Rule**: After every commit intended to complete a change, run `git status --short` and require EMPTY before pushing or opening/updating a PR. Never chain `git add bad-path || true`-style recovery — fix the path. Remember: a multi-path `git add a b c` stages NOTHING if any single pathspec is invalid.

**Evidence**: Multi-path `git add a b c` stages NOTHING on one invalid pathspec; summary-layout commit shipped docs without its CSS; caught by the stop hook.
