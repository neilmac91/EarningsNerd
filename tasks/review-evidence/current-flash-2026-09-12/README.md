# Current-Flash assessment archive — September 12, 2026

These snapshots preserve the original review text verbatim. Their `work/` paths identify local retained evidence and are not repository artifacts; original source payloads and private scratch files are not added here. Source checks were targeted, not exhaustive original-filing coverage. Reviews concern the #818 baseline unless explicitly identified as a first or second #808 assessment. They do not certify all production output.

- [Earnings review](flash-earnings-review-20260912.md)
- [Cash, debt and guidance review](flash-cash-guidance-review-20260912.md)
- [Remaining filings review](flash-remaining-review-20260912.md)
- [Priority plan snapshot](flash-quality-priority-plan-20260912.md)
- [Source-qualified explanation slice](flash-explanation-next-slice-20260912.md)
- [COST source-unit feasibility](cost-source-unit-feasibility-20260912.md)
- [First #808 summary acceptance](pr808-flash-summary-acceptance.md)
- [First #808 Copilot failure](pr808-copilot-failure-review.md)

## September 12 correction — ASML carrying amount

The original remaining-filings review and priority snapshot use €693.0M commercial-paper principal alongside €3,699.2M long-term-debt carrying amount. The [first #808 source check](pr808-flash-summary-acceptance.md#debt-scope-disposition) establishes ECP carrying amount **€691.7M**, giving comparable combined carrying debt **€4,390.9M**, not €4,392.2M. The source anchors are retained excerpt offsets159,209 (ECP) and154,673 (long-term debt). This corrects the illustrative basis; it does not refute the omitted-short-borrowing finding. Original snapshots remain unchanged.

## Current release boundary

The first #808 summary assessment accepts only metadata/data conservation:52 matched outcomes and362 permitted null-to-qualified cash/debt tags, with recurring debt narratives still incorrect. First Copilot assessment34688285251 passed17/18; ASML's two excerpts were present but shorter than the unchanged24-normalized-character minimum. Correction head `0e6b076b3e1112c7e11fb3170b64c941d880a18f` has a reported committed full gate of2,878 passes/29 warnings in83.93s; the second assessment is pending at this archive checkpoint. No #808 merge or production verification is claimed.

The cash-basis candidate `e9dbe8b991cfd393033f88e277c434d9e3540cc5` is locally gated with2,885 passes and remains unpublished at this checkpoint. #819 and E06 reconciliation/configuration are complete; naturally occurring payment-delivery attribution remains future observation. Root will append actual assessment/release evidence before publication when available. Financial-quality clearance, universe-wide pregeneration and original founder prerequisites remain held.

## September 12 — second Copilot assessment accepted with limitations

The [second Copilot assessment](pr808-second-copilot-acceptance.md) and [integrity checks](pr808-second-copilot-integrity.json) preserve run34691111620/job103546396873. All18 outcomes passed the existing bounded gate: **three draws for each of six pinned Copilot questions**, not two repeats per filing. ASML draws0 and2 gave correct figures but no citations/tool calls; draw1's redundant closing citation supports sales only. These limitations remain visible;18/18 is not universal citation adherence or world-class clearance.

The verified synthetic source `c0999c8df55751a8a7a5d3e2941e312ed7aa541d` has the same whole tree as correction `0e6b076b3e1112c7e11fb3170b64c941d880a18f`. The separate second summary assessment CI34691090937 remains pending at this checkpoint and uses **two summary repeats per filing**. Earlier second-Copilot-pending wording is superseded only for Copilot. #808 is not recorded as merged or production-verified; deployment evidence remains outstanding.

## September 12, 11:39 UTC — final summary accepted; merge awaiting deployment

The [final-head summary assessment](pr808-flash-summary-second-acceptance.md) accepts bounded provenance/data conservation and usage accounting. Retained evidence includes [metadata versus #818](pr808-flash-summary-second-metadata.json), [unchanged first/second XBRL](pr808-flash-summary-first-second-metadata.json), and [usage reconciliation](pr808-flash-summary-second-usage.json). All52 summary outcomes are present;53 primary calls include one unknown-usage call. Zero reported cost is not proof of a free run.

Material narrative limitations remain: WMT draw1 omits separate short borrowings from “total debt”; COIN draw1 omits short borrowings; both ASML summary attempts omit the €990.2M current portion when adding noncurrent debt and ECP. ASML comparable carrying debt is €4,390.9M. Metadata improved without certifying financial meaning. Two ASML Copilot draws remain uncited as recorded separately.

[#808](https://github.com/neilmac91/EarningsNerd/pull/808) merged as `f0a81fff216c318a40979b7dfcd55500c8b43a03` at2026-09-12T11:39:24Z. Main CI34691615781 is running; no migration/revision/health or completed deployment is claimed. Earlier pending-summary and pending-merge text is superseded; production verification remains a prerequisite before the next backend merge or archive publication.

## September 12, 11:47 UTC — #808 production verified

This dated record supersedes earlier pending-assessment, pending-merge and pending-deployment entries. [PR #808](https://github.com/neilmac91/EarningsNerd/pull/808) merged as `f0a81fff216c318a40979b7dfcd55500c8b43a03` at 11:39:24 UTC. [Main CI 34691615781](https://github.com/neilmac91/EarningsNerd/actions/runs/34691615781) and deploy job `103548163219` succeeded. The deploy log records:

```text
2026-09-12T11:45:06.9511863Z apply_migrations: applied=0 skipped=39
2026-09-12T11:46:04.9189989Z   100% LATEST (currently earningsnerd-backend-00331-tfm)
```

CI detailed health passed at 11:46:44 UTC (database 5.68 ms). Independent `curl -fsS https://api.earningsnerd.io/health/detailed` returned healthy with database 5.27 ms and server timestamp `1789213665.7251222`. The final committed gate passed 2,878 tests with 29 warnings in 83.93 seconds, including performance and all four PostgreSQL lanes; Ruff and Bandit passed. Both actual second assessments were accepted within their documented limits, with 52 summary outcomes and 18 Copilot answers. Original failed evidence and material debt-scope findings remain preserved. This is no general financial-quality or universal citation-compliance clearance.

- [x] Complete #808 merge and serial production verification; do not repeat either paid assessment or the merge.
- [x] Integrate the separate cash-basis candidate with #808 at `37401e996c980fbdf01306fcb1472601b31c2eed`: 2,888 tests passed, 29 warnings, 93.77 seconds; all eleven locked anchors match new main.
- [ ] Publish and assess that cash-basis slice after any subsequent documentation integration and committed gate. Its local gate is not actual-output or production acceptance.
- [ ] Continue source-unit ownership, compatible accounting/explanation relationships, typed numerical comparisons and scoped guidance coverage. Current reviews still contain material financial findings.

E06 event-selection configuration is complete under the exact approval; naturally occurring delivery and attribution remain unobserved. No test event or replay was sent. Notable retain review through September 15, Analysis warm-up/live acceptance, the exact W3-7 strong-judge readout/arm decision, serial W3-8 re-pins, E09 proposal decisions, major dependencies, D8/#270, CI-only DeepSeek key and other named founder prerequisites remain as recorded. Universe-wide pregeneration and historical replay remain held; Flash with thinking off is unchanged.

### Local archive merge correction

During integration of main, a local conflict cleanup briefly shortened one historical pytest separator line. The original line was restored before publication. The final integrated `tasks/todo.md` diff against main was checked as additions only; no earlier published ledger text is replaced. This was a local preparation error, not a released test result or a gate failure. The earlier cash-worktree incident remains separately recorded.

### September 12 — cash candidate made recoverable before handover

The fully gated cash candidate `37401e996c980fbdf01306fcb1472601b31c2eed` is now preserved on the remote [codex/wave3-standalone-cash-basis branch](https://github.com/neilmac91/EarningsNerd/tree/codex/wave3-standalone-cash-basis). A fresh checkout can fetch that branch; its implementation is no longer dependent on a local worktree. This supersedes earlier “unpublished” only for branch publication: no cash PR, hosted assessment or production release is claimed yet. Subsequent documentation integration and its committed gate precede the draft PR.
