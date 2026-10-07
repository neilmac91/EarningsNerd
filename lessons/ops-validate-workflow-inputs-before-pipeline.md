# Validate workflow inputs before `pipeline()`, and treat a missing agent result as no result

**Date:** 2026-10-07 · **Area:** ops / Claude Code workflows

## Context

The tiered `premerge-review.js` first threw on an unknown tier inside a `pipeline()` stage. The
workflow runtime drops a throwing item to `null` and `results.filter(Boolean)` then removed it, so
a PR passed with `tier: "High"` vanished from the output with no error, and a batch-level
`args.tier: 'records'` would have given every PR without its own tier zero agents and
`mergeable: true`. In the same script an `agent()` that returned `null` (a skipped or crashed
agent) became `[]` findings, and a refuter that returned `null` made a blocker "refuted". Both
turned missing review output into clearance, the opposite of AGENTS.md §5.

## Rule

- Validate every item and every batch-level option before the first `pipeline()` or
  `parallel()` call and throw there; a throw inside a stage is a silent drop.
- Default to the strictest branch when an input is missing (an unset tier reviews as high); accept
  the most permissive value only when it is set on the item itself.
- A `null` from `agent()` is an absent result: mark the run `incomplete` and leave the finding
  unverified. Never fold it into "no findings" or "refuted". `v.length > 0 && v.every(...)` is the
  bug shape; require `v.length === expected`.
- Simulate the script with stubbed `agent`/`pipeline`/`parallel` for every tier and for a null
  lens and a null refuter before committing it (`node -e` with `new Function`).

## Evidence

- #1118 review findings S2 and S3 (2026-10-07); fix in `ea054a55`
  (`.claude/workflows/premerge-review.js`: `tierOf`, the pre-pipeline validation loop,
  `missingLenses`, `complete`).
- Workflow authoring reference: "A stage that throws drops that item to `null` and skips its
  remaining stages"; "agent() returns null if the user skips the agent mid-run or the subagent
  dies on a terminal API error".
