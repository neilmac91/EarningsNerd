# EarningsNerd takeover and completion path — 26 September 2026

EarningsNerd remains at **quality acceptance before controlled beta**. The engineering
foundation is strong. The next evidence needed is that complete filing summaries are correct
and useful, that the database can be recovered, and that real users return for another analysis.
Shipping more evaluation infrastructure does not establish those outcomes.

This checkpoint supersedes the current-state/queue descriptions in the
[September 23 continuation](continuation-plan-2026-09-23.md), through main
`b53455bb3b13817d44cf089f3280ced143998583` (#961). Historical results, approvals, budgets and
specific holds remain in force. The founder confirmed that external Agents A, B and C are
still working; their unpublished checkpoints and current ownership are pending. Codex owns
integration and this completion plan, but has not taken over their active branches.

## What the agents delivered

| Work | Verified position | What it does not establish |
| --- | --- | --- |
| SDK refresh #953, replacing #950 | Merged and deployed; real exact-head 70/70 summary regression and accepted 18/18 Copilot measurement. | E7 quality acceptance or a new model's quality. |
| E7 preparation #940, including #951/#954 | Merged and deployed; frozen-source preparation, document mapping, source views, capacity preflight and source-unit custody exist. | Complete semantic coverage of the filing corpus. |
| Member dispositions #956, contract/context bounds #957, modality inventory #959 | Merged and deployed; offline validators bind declared source bytes and make unresolved evidence visible. | Table/graphic interpretation, complete role reviews or source reconciliation. |
| Test isolation #958 | Merged and deployed; isolates the process-wide AI-call ContextVar between tests. | A product-quality improvement. |
| Review graph #961 | Merged during this audit at 21:29:29 UTC. Tree, current-node receipt and declared-context validation exist. | Complete attempt history, deterministic prompt construction, issue preservation or admission. Three independently reproduced gaps remain below. |
| Documentation #955/#960 | Release record and lesson organization merged. | Additional production behavior. |

The [takeover evidence](review-evidence/takeover-2026-09-26/README.md) records release runs,
migrations, revisions, health, actual measurement denominators and their limits. One serial-merge
rule breach is established: #959 merged before #958's deployment was verified. The actual deploy
jobs were serialized and subsequently healthy. Several historical independent health observations
were not retained; a current health response cannot reconstruct them.

## Immediate E7 corrections

The [custody review](review-evidence/takeover-2026-09-26/e7-custody-review.md) independently
reproduces three defects in #961. They affect an offline, non-admitting validator; no current
production generation call site or serving failure was found.

1. An arbitrary prompt can be substituted while preserving the declared template and input
   hashes. Validate the actual prompt construction against the frozen template and complete
   declared inputs before trusting the receipt.
2. A compacted/failed attempt can be deleted and the successful attempt renumbered. The
   resulting source-context list is incomplete. Admission needs a separately retained authority
   for the complete attempt history; a self-declared list or a self-recomputed hash chain alone
   cannot prove that history was preserved.
3. A leaf output can alias the template of an allowed but unused reducer kind. Check outputs
   against all templates declared by the frozen contract, including unused kinds.

The latter two were also raised by the completed exact-head Codex review before the merge.
The PR body's review-quota explanation is not evidence that no review occurred. Founder merge
authority reported in the PR is separate from whether findings were resolved.

Finish these corrections in the existing owner's next bounded slice after reconciling their
checkpoint. Agent B should review the exact corrected commit and supply the original independent
fixture pack. Do not repeat completed full audits just to produce another report. Retain required
gates and focused failing/restored proofs; do not retry the two previously denied E7 proofs.

## Ordered completion path and ownership

The assignments below are the proposed post-checkpoint division of work. Stage 1 must reconcile
actual ownership and running work first; this document does not transfer an active branch or
claim an external agent has stopped. Codex's independent audit and documentation work can continue
meanwhile. Existing approvals and release gates, rather than the priority ordering, govern execution.

| Stage | Owner and next deliverable | Observable exit condition |
| --- | --- | --- |
| 1. Reconcile active work | Codex; each external agent supplies its checkpoint, current SHA, unpublished artifacts and running work. | One owner per active slice; no duplicated generation/judging or concurrent merge decisions. SDK work is closed after its handback. |
| 2. Close the candidate configuration | Codex owns #942's actual-output/release decision. Prefer completing the formula-label fix before E7; keep it outside other agents' custody work. | Current-main integration, documented actual baseline plus two independent same-contract draws and review, serial verified release; then freeze candidate stamp `q`. Until that evidence exists, production remains `p`; no assumed promotion or paid holdout start. |
| 3. Complete one source-review path | Existing E7 implementer owns the custody corrections and minimum missing semantic/integration path; Agent B independently verifies it; Codex accepts the result. | Real H29 A/B briefs and reconciliation pass the same readiness/inventory/decision boundaries needed by E7. Preserve eligible A; retire compacted B; use fresh bounded B contexts. |
| 4. Prove corpus capacity and finish references | Codex coordinates bounded source-only contexts after Stage 3. | H01/H02/H25 all-member/modality and actual input/context capacity demonstrated; unchanged 30 filings have 60 independent source briefs and 30 reconciliations, with no unresolved material coverage/issue holds. |
| 5. Execute E7 | Codex owns the frozen run and evidence dossier under existing approvals. | Preflight and metered non-holdout smoke; exactly 90 candidate + 30 comparator identities, source-based blind reviews, retained Fable judgments, and pass/fail/incomplete report within ceilings. |
| 6. Prove recoverability | Codex prepares/operates; founder supplies the still-missing clone cost and scoped cleanup authority. | One isolated PITR restore, read-only integrity check and confirmed clone cleanup, with timings, costs and limitations. This can run alongside quality work once authorized. |
| 7. Controlled beta | Founder supplies recruitment/commitments and product-scope decision; Codex operates acceptance/support readouts. | 5–10 consenting target users, two dated weekly readouts of useful analysis, different-filing return, misleading outputs, support burden and observed cost; explicit expand/hold/narrow decision. |

Stage 3 is the stopping point for speculative infrastructure. Implement only the issue/evidence
propagation, source-bound reconciliation, modality composition and downstream binding needed for
the actual H29 path and named full-corpus constraints. Follow the existing
[integration requirements](readiness-2026-09-21/acceptance/source-review-hierarchy-integration.md):
preserve schema-2 inventory bytes, the final nine-field issue shape, all source-context exclusions
and blinded coverage-limit projection. A source-free reducer cannot resolve a dispute that needs
fresh source inspection. Every added capability should identify the concrete execution blocker it
removes. After the real path works, freeze the interfaces and execute the evidence programme.

E7 retains the approved 30 accessions, USD 10 generator ceiling, 243 Fable-invocation ceiling,
zero confirmed critical/material defects and 86/90 joint completeness/usefulness scores of at
least 4/5. Preserve the [AI-assisted protocol](readiness-2026-09-21/acceptance/ai-assisted-plan.md)
and its weaker assurance. Do not ask for the unavailable human panel again. Do not silently change
the judge/CLI contract, redraw negative verdicts, or treat a partial result as a pass.

The retained H29 record has one individually frozen eligible A brief, an ineligible compacted B,
and no complete pair/reconciliation. No E7 acceptance outputs or decision dossier were found.
No new E7/E8/provider call was made by this takeover audit. Active agents' unreturned evidence
could update that position; it must be reconciled before any execution.

## Open PRs and deferred work

- **#942 — formula labels:** remains open at `aab234fb0d041eadea378a1b374d29b71b9c7b0a`.
  This changes generator grounding as well as rendering. Ordinary CI does not replace its
  required actual-output evidence. Resolve it before the E7 candidate freeze, or explicitly
  document a decision to defer it and the accepted scope of `p`; do not invalidate a completed
  E7 run by silently switching to `q` afterward.
- **#952 — E8 launch/recovery:** remains draft at
  `1d48eb336a8a22427d466966b1814fce2e94c3f2`. Recommend parking it while E7 progresses, after
  reconciling any work already running. E8 remains 140 reused
  controls / zero new judgments / 160 missing slots in retained evidence, with prior charge 287
  of 601. The current external-session history is pending. No permission-route redesign or judge
  continuation is needed for E7: retain prompt `o` while E8 is inconclusive.
- **#710 — index publication:** next natural monthly refresh is scheduled for October 1 at
  08:00 UTC; the latest run remains the successful September 6 no-change run. Keep the issue
  open for genuine changed-list draft-PR publication. Do not manufacture a change.
- **Dependency alerts #270/#283:** two high-severity `extract-zip` advisories in the development
  Lighthouse chain remain open, with no patched version reported by GitHub. The #270 hold and
  direct-major holds stand; no forced downgrade or unrelated upgrade belongs in this tranche.
- **E8, attribution activation, fleet expansion, optional features and dependency majors:**
  remain outside the quality/recovery/beta critical path. Keep production attribution flags off.

## Founder inputs that actually remain

The only present coordination request is the active agents' checkpoints. They should include
chat-only instructions, unfinished work, original review fixtures, evaluation calls/retries and
any release receipts missing from GitHub. This prevents duplicate work and false completion claims.

Before live recovery, cloud credentials need renewal and the existing
[restore procedure](readiness-2026-09-21/operations/restore-rehearsal.md) needs a verified current
price estimate, numeric all-in ceiling and deletion authority scoped to the drill clone. The
September 26 read-only `gcloud` attempt failed reauthentication; backup/export observations remain
dated. Daily backup and PITR approval is already settled. Monthly export needs verification or an
explicit de-scope decision; a restore does not silently satisfy that requirement.

Before product acceptance/cohort execution, obtain a named Pro test account and bounded Analysis
warm-up, Notable retain/kill, and cohort recruitment/commitments. Do not repeat completed provisioning,
invent a test payment, send invitations, or activate a production flag from this checkpoint.

## Master-plan position

The product's core engineering is largely complete, approximately 90% as a planning estimate.
The full beta-to-scale outcome remains around **55–60% complete**, with substantial uncertainty;
this is a milestone-weighted judgment, not a count of merged PRs. Since the prior checkpoint,
source-review prerequisites improved, but no new quality verdict, recovery proof, cohort, retention
or economic outcome was established. Those missing outcomes limit the estimate.

The shortest route is therefore: correct and finish one E7 path, freeze the candidate, execute
the quality programme, prove recovery, and observe a small controlled cohort. Two weekly cohort
readouts impose elapsed observation time that faster implementation cannot remove. Fleet scaling
follows demonstrated demand and its separate capacity/design decision.
