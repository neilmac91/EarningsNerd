# PR 970 hosted final audit — UNMERGED REVIEW HOLD

PR [#970](https://github.com/neilmac91/EarningsNerd/pull/970) remains **open and draft** at exact head `68e8ff1f29a3ec844d595cfce93b72225d46dba3`. It must not be merged. The final exact-head review completed with a substantive P2 finding: [`technical_attempts` completeness is self-authenticating](https://github.com/neilmac91/EarningsNerd/pull/970#discussion_r4114089923) (review `5328823266`, comment `4114089923`). Removing one known attempt and recomputing `source_context_closure_sha256` validates successfully; the omitted source-exposed context then disappears from `source_context_ids()` and can be reused by a downstream blind role.

Two refutations failed. The closure digest cannot establish completeness because it is calculated from the same mutable declaration. Transitive artifact validation does not help because the omitted reservation and settlement are reachable only through the removed attempt entry. Closing this requires an independent attempt/context authority. The next design pass should first examine reuse of PR #964's external history authority or journal for the already-retained attempts, without fabricating past dispatches or introducing a generic framework.

## Exact identity

- Base: `e39b475e13a0599d037303aacc75a82d51b053b8`
- Head: `68e8ff1f29a3ec844d595cfce93b72225d46dba3`
- Head tree: `aff6a974ba58158f3bc6f9157b8bbb56293f5725`
- Hosted synthetic merge: `755ca1ce21711097d2a73ac6dd5a8d5302547937`
- Synthetic tree: `aff6a974ba58158f3bc6f9157b8bbb56293f5725`

The hosted synthetic tree is byte-equivalent to the head tree. Green checks and physical evals below do not clear the independent completeness hold.

## Final physical artifacts

CI run [`36294511807`](https://github.com/neilmac91/EarningsNerd/actions/runs/36294511807) completed successfully. The physical baseline eval produced 70/70 scored outputs with zero errors, retries, hard-gate failures, or judges. It made 70 successful `summary_primary` calls using `deepseek-flash`, fingerprint `aeb56401ca74e127821c4f9126dcb669`; telemetry recorded 2,755,570 prompt and 283,167 completion tokens (3,038,737 total), estimated cost `$0.180235`, while billed cost remains unknown. The raw artifact is `ci-36294511807/artifact-10923871389.zip`, 3,674,594 bytes, SHA-256 `448876aa0d422b8b8aaeef13b25b41800aff90731f6f1ece888d38f6bffd8e5d`.

Copilot run [`36294511938`](https://github.com/neilmac91/EarningsNerd/actions/runs/36294511938) completed successfully. It produced 18/18 outputs with zero errors, failures, hard-gate failures, or judges. It made 36 successful `copilot_chat` calls using the same model and fingerprint; telemetry recorded 1,128,374 prompt and 5,586 completion tokens (1,133,960 total), estimated cost `$0.007779`, while billed cost remains unknown. The raw artifact is `copilot-36294511938/artifact-10923945246.zip`, 78,695,557 bytes, SHA-256 `4458011c791866b12aff5321578e6630ef2dd36fd99517e66ab67a20a527f0da`.

The final exact-head review gate run `36294511812` itself completed successfully at 04:35:03 UTC. That status means the review ran; review `5328823266` contains the unresolved finding above.

## Soft limits and negative evidence

The 70-output eval used deterministic scorers and no judge. It had 15 citation violations across 13 outputs, 164 untraceable dollar figures, 32 expected persisted-XBRL fallback observations, two incoherent segment-table drops, and one regression warning; all hard gates passed. Component minima included financial depth `0`, specificity `0.9459`, redundancy `0.7059`, delta consistency `0.75`, currency consistency `0.9859`, and citation fidelity `0.7143`. Previews ranged from 18,792 to 113,010 characters with no truncation.

The 18-output Copilot eval had 47 figures and 37 citations. Six figures were uncited across five outputs; there were no unverified excerpts, invalid provenance, contradictory currencies, misplaced fact citations, or hard-gate failures. Source preparation completed for six sources and 24 artifacts with zero mismatches or errors; it retained two documented incoherent segment drops, and ASML `sections.json` was literal `null`.

Costs above are application telemetry estimates, not invoices. No run performed a judge call. Earlier head generations, one skipped draft-snapshot run, and cancelled duplicate/ready-event runs remain preserved in `inventory.json`; they are not described as final-head execution.

## Files

- `metadata/final-ci-audit.json`: detailed final 70-output audit.
- `metadata/final-copilot-audit.json`: detailed final 18-output audit.
- `metadata/final-reviews.json` and `metadata/final-comments.json`: exact-head review evidence.
- `inventory.json`: workflow identity, artifact, status, and retained-file inventory across preserved generations.
- `files.sha256`: SHA-256 inventory of every retained file other than the checksum file itself.

## Evidence locations

This repository contains this compact audit, the [workflow inventory](pr970-hosted-inventory.json), [final CI audit](pr970-final-ci-audit.json) and [final Copilot audit](pr970-final-copilot-audit.json). Raw artifacts, metadata, prior-head runs and `files.sha256` remain in the operator workspace under `outputs/takeover-2026-09-26/pr970-hosted-final/`. Relative filenames above resolve there; they are not claims that those raw files are committed here. Public compact copies normalize host-specific workspace paths; the original external bytes and inventory hashes remain unchanged.
