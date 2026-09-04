# Grep-verify every "no X exists" claim from a workstream report before it enters a synthesis

**Date:** 2026-09-04 · **Area:** ops / audit method

## Context

The September 2026 audit synthesised six agent reports. The founder's review of PR #653 caught
three absence claims that had been carried into the synthesis and plan unverified: "6-Ks have no
summary path" (the path exists behind `ENABLE_FPI_FILINGS`: `backend/prompts/6k-*.md`,
`summary_pipeline.py:358-489`), "`signup_completed` is defined but never fired" (it is emitted
server-side in `posthog_client.py:46`), and "`ops.yml` fires from a stale branch that exists on
origin" (the branch was already gone). Positive claims with file:line evidence held up; the
negatives did not, because a negative is only as good as the search that produced it and the lead
had spot-checked only the highest-impact positives.

## Rule

- Before a synthesised report or plan asserts that something does not exist, is never called, or
  is still present, the lead runs the grep (or `git ls-remote`) personally and records the command
  in the verification section. If there is no time, label the claim a hypothesis.
- When two workstreams disagree on an absence (one appendix says the feature is shipped, another
  says no path exists), the disagreement is itself a finding to resolve before publishing, not a
  detail to average.
- Plan items derived from an absence claim inherit its status: an unverified negative may not
  become a checkbox.

## Evidence

- PR #653 review (2026-09-04), "Audit-content corrections" section; fixes landed in the same PR
  (`docs/ENGINEERING_AUDIT_2026-09.md`, `tasks/todo.md`, lead-correction notes in appendices 01, 03, 04, 05).
