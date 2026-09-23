# Return-ratio content stamp correction — 23 September 2026

[PR #942](https://github.com/neilmac91/EarningsNerd/pull/942)'s exact-head review identified [the missing content stamp](https://github.com/neilmac91/EarningsNerd/pull/942#discussion_r4079438509). The original label change affects both persisted deterministic text and generator grounding. Commit `464b7107` advances `SUMMARY_PROMPT_VERSION` to `summary-2026-09-q`, with schema 2 unchanged. Verified main `ebdc4c44` is integrated at `c08c95a49724b12bc172094be3867eac18051d60`. No drain or historical replay was scheduled.

Two fresh refutations confirmed the finding: the changed labels are generated and persisted, rather than substituted at read time; GET/provenance rendering passes through stored `returns_on_capital` text instead of recomputing the generation fallback. Root independently reviewed those paths and the current-versus-old stamp tests. The existing gates cover stamp freshness; no test that merely asserts the new literal was added.

Focused coverage passed `120 passed, 17 warnings in 7.40s`. The final full gate passed **3500 passed, 29 warnings in 120.26s (0:02:00)**, zero failures/errors/skips, all four PostgreSQL lanes and both performance cases, plus Ruff, Bandit and package consistency. [Parsed gate receipt](full-gate-receipt.json). The known interpreter-shutdown logging warning follows successful pytest completion.

This closes the stamp implementation gap. The original grounding change still requires justified baseline re-pinning with actual before/after evidence and two independent generated runs per configuration under the same Fable contract-2 judging. Ordinary CI generation is regression evidence, not that comparison. The founder's ready-for-review UI state is preserved; the PR remains unmerged. Existing E7 arms and E8 n/o corpora retain their frozen identities; no artifact is relabeled q.

The subsequent [generator-instruction correction](instruction-fix/README.md) aligns the remaining model-facing phrase and extends the existing retained-JPM gate. Its exact-final 3,500-test gate supersedes the implementation validation above; all release holds remain.
