# Handover — September 9, 2026, quality remediation and master-plan continuation

Read root AGENTS.md, CLAUDE.md, applicable lessons, the original [September 8 handover](handover-astra-2026-09-08.md), [wave-3 plan](handover-wave3-2026-09.md), [CEO implementation plan](ceo-implementation-plan-2026-09-08.md), then this checkpoint and [todo](todo.md). Earlier ledger entries are historical; dated corrections supersede them without rewriting them.

## Subsequent incident correction — read first

The [documentation-evaluation incident](incident-docs-eval-scope-2026-09-09.md) supersedes the earlier “no subsequent paid measurement” statement below. A stale-base workflow comparison counted upstream main changes as part of docs #783 and launched seven unintended evaluations: 196 successful summary generations, 147 HTTP 402 errors, 8,378,456 provider-reported tokens. Exact billing and canceled in-flight usage remain unknown. One launch occurred after the explicit funding hold; the agent stopped unsafe pushes and reported the deviation. Original records remain intact.

#783 merged as `395027a6a6c2f8a7c6edad8d3ee1bae1f602353e`; backend remains #788 / revision00318-q79. A separate local scope safeguard is prepared at `979f0890487d7ec7e05eaf16cea38f576cd3f381`, with full gate passed: 2,756 tests, Ruff/Bandit, YAML/consumer gates and 3 Node-lockstep tests. It validates the checked PR merge and compares its first parent, failing without authorizing generation if provenance/history/diff is unavailable. After funding restoration, release this safeguard first, then resume the held source/error/identity/prompt sequence. Do not repeat paid Copilot merely to rerun a failed summary job.

## 0. Handover point and checkpoint

The original takeover was main `3336d513` (#770), auditing the prior session's `d7b01779..3336d513` span. The initial audit and dependency follow-up were completed through #781; #782 records the founder's quality-first direction. This continuation leaves the backend at main `3e0c256cf1cb38f9a28f9c3c333d12a359fcace1` (#788). The handover/research publication is docs-only #783; resolve its final squash SHA from GitHub when resuming rather than treating the backend SHA as the later documentation commit.

Production is `earningsnerd-backend-00318-q79` at 100% traffic. Main CI 34293928853 and deploy job 102286975731 passed; `apply_migrations: applied=0 skipped=39`. CI detailed health timestamp 1788913070.8209805 and independent curl 1788913197.024444 were healthy. These endpoints do not exercise the paid AI provider.

DeepSeek returned HTTP 402 “Insufficient Balance” during #792's evaluation. No subsequent paid measurement was launched, no top-up was made, and no provider was substituted. The founder was asked once to replenish the API balance. #792 remains open and unmerged; its green overall workflow is not regression acceptance.

Local workspace is under Documents/Codex/2026-09-08/goal-you-are-the-chief-engineering. Shared repo is work/EarningsNerd, with one external worktree per codex/wave3-* branch. Its local main branch can be stale; use freshly read origin/main and preserve prepared worktrees. Current runtime/dev/eval pins require work/minor-sdk-venv. PostgreSQL 15.15 is on 127.0.0.1:55432 with dedicated databases per worktree and all four CI-named lane variables. Do not repeat completed mutation proofs.

## 1. Mandate this session worked under

The founder requested proceeding with confirmed quality findings while Fable is usage-limited, a deep EdgarTools capability investigation, and continued master-plan delivery. Routine direct account observations and justified reversible edits are authorized by #782. Specific locked-contract, product, legal, destructive, vendor/spend, provider and replay boundaries remain. DeepSeek stays; Fable is a judge only, High effort or below when its allowance returns.

Universe-wide pregeneration and broad stale-summary replay remain held until explicit founder quality acceptance and spend release. Existing saved analyses were not refreshed. Routine full gates, draft-first publication, one paid Copilot evaluation at ready and a second confirmed-finding fix round remain authorized. No third Copilot run is needed merely to retry an external failed summary job.

## 2. What was done

The initial audit merged as #773; delivery must-fix #772 was released, the founder approved retaining #759's additions as a documented locked-file exception, and authorized dependency work shipped through #779. Audit S1 was subsequently completed as #786. The initial handover #781 and CEO plan #782 remain the preceding checkpoints.

This continuation independently reviewed 52 retained analyses from 26 filings, froze the findings, then compared available Fable reports. Those outputs are a development corpus, not every production analysis or unseen acceptance evidence. Fable's available snapshot contains 17 complete JSON reports, four incomplete, two Markdown-only and three absent; declared coverage and individual findings were checked. No full consensus or strong-judge 24/24 acceptance is claimed.

| PR | Delivered slice | Production evidence |
| --- | --- | --- |
| #784 | Actual prior balance dates in working-capital comparisons | CI 34286869418; revision 00312-7jp |
| #785 | Selected-accession fallback identity | CI 34288013954; revision 00313-pqs |
| #786 | Chat admission retained through transport cleanup | CI 34289364726; revision 00314-jsf |
| #789 | Exact excerpt provenance and honest unknown legacy coverage | CI 34291185532; revision 00315-qlb |
| #787 | Remove segment shares with unverified overlapping denominators | CI 34291811124; revision 00316-tfj |
| #791 | Compatible minor PostHog/Anthropic SDK maintenance; #780 closed | CI 34292889980; revision 00317-88l |
| #788 | Explicit return-ratio basis in grounding/rendering | CI 34293928853; revision 00318-q79 |
| #790 | Honest “Report year” filing-list label | CI 34290442746 and Vercel production success |

Every backend row has migration 0/39, 100% traffic, healthy CI and independent detailed health recorded in the [execution ledger](beta-to-scale-execution.md). Required committed local gates, mutation proofs and review evidence are in the PR bodies. The dependency-only #791 summary step explicitly skipped; no 52-output artifact is claimed for it.

The [EdgarTools investigation](edgartools-quality-plan-2026-09-09.md) and [selection experiments](evidence-selection-experiments-2026-09-09.md) are complete research deliverables. Keep pinned 5.56.0; no new vendor or blind upgrade was adopted. Structured statements, dimensions, calculation relationships, complete sections/tables and attachments are useful existing capabilities. Source identity and evidence selection are the main product gaps. Production TOC sections refuted the standalone long-cell truncation hypothesis. Whole-section expansion recovers facts at material input growth; the tested selectors did not justify production adoption. Legal section names, amount equality and SDK confidence values do not certify accounting identity. NVO's incorporated report needs bounded acquisition through the existing transport owner before generation changes.

### 2a. Things worth your scepticism

1. **Green CI can conceal a failed advisory regression.** #792 CI 34293573625, artifact 10082475808 / eval_20260909T001448Z.json, contains 26 failure placeholders. The actual regression job 102285187391 failed coverage/recall, exit 1; local replay also exits 1. All 52 decoded source hashes still match retained documents. Copilot 34293573627 accepted 18/18 before balance depletion. Do not merge from the badge.
2. **Application failures were counted as scored.** The runner lost status:error and reported error:null for returned fallback dictionaries. A separately gated local correction retains generic non-transient failure evidence. It does not repair the provider balance or change product fallback/retry behavior.
3. **The baseline eval bypasses production enrichment.** Broad prior backfill could attach net income to pretax/operating rows. The prepared metric-c correction uses explicit supported identities and own diluted EPS/ADS data; basic/unknown/loss rows conservatively keep missing priors. This does not certify complete period/currency provenance.
4. **Local prompt tests are not quality evidence.** Prepared d replaces the fixed P&L menu with a shared source-reported label policy and retains exact bounded previews. No funded output evaluation has run for d. It must demonstrate PFE improvement without redistributing failures across all 52 analyses and actual normalized/exported representations.
5. **New version stamps do not repair stored analyses.** a/b/c/d identify old content for explicit refresh; no background drain or broad replay was run. Historical persisted fallback provenance remains unmeasured.
6. **The comparison preparer is a reviewer aid.** It now preserves full normalized facts, enforces the expected cohort, marks missing output/zero previews honestly, checks preview character totals and requires fresh output directories. Its self-check and negative controls do not constitute model-quality acceptance.
7. **Research corrections matter.** Full production sections preserve the long KO cell; NBSP normalization refuted a raw substring absence claim. KO's $450M tax increment is for three months ended April 3, not an annual increase. The complete-section alternatives consume more input or omit target facts under a small cap. Retain these corrections when summarizing the study.

Process deviation: one agent inadvertently repeated an excerpt-provenance mutation proof after an unrelated ORM correction. Original evidence was retained, the duplicate was stopped/reported, and no paid evaluation or production action resulted. Do not repeat it again or count it as a separate invariant.

## 3. Resume brief and prepared candidates

Read each handoff and exact local head before edits. No prepared candidate below has a PR number except #792. A normal integration after prerequisite squash merges may change the committed tree; repeat the full gate on that new committed state, but preserve completed mutation proofs. Do not invent test counts, SHAs, run IDs or revisions.

| Candidate | Prepared head | Gate / dependency |
| --- | --- | --- |
| #792, work/source-provenance | 396b01b5a43261e787678d4dc322386a82e9ef7e | 2,760 tests; second Copilot passed; actual summary regression held on balance |
| work/metric-prior-identity | 2f094ec13afe0113d13ddefc83895db08cfadaa4 | 2,784 tests; exact #788 main integrated; source-reported d requires this correction |
| work/eval-error-outcome | c9f2e30800b8cf798b45d638d192d220fbbad1db | 2,769 tests; local #792 plus main integration; preserve d preview fields later |
| work/reported-metric-labels | 7fd71bdcfc451fc280a3d2960cb4676a7b02b869 | 2,801 tests; locally includes c and #792, not their production release |
| work/measurement-only-dispatch | b37099bdd19151c750b50c8c7cc934236154ff63 | 2,755 tests, YAML/consumer gates and 3 Node-lockstep tests; no dispatch |

All listed full gates include Ruff, Bandit, performance, four PostgreSQL lanes and locked-anchor identity. Independent reviews found no remaining local code blockers; actual hosted acceptance and serial production verification remain incomplete. Handoffs and exact proof tails are work/source-provenance-verification.md, metric-prior-identity-review.md, eval-error-outcome-review.md reported-metric-labels-review.md and measurement-only-verification.md. Draft bodies are retained under work/. Do not replace original failed artifacts with synthetic re-scoring.

After balance is restored, rerun only #792's failed summary job to recover required evidence (`gh run rerun 34293573625 --repo neilmac91/EarningsNerd --job 102285187391`), after re-reading current remote head/state and checking whether it already ran. This should not rerun the separate paid Copilot workflow. Inspect the actual artifact and gate, then exact-head merge and production verification. Release error-outcome and metric identity in separate slices before final d acceptance; normally integrate their merged main into d and gate it again.

For d, use work/reported-label-comparison-plan.md and work/compare-reported-labels.py with a fresh output directory, current minor SDK environment and closest source-identical pre-d report. Check both PFE repeats, all accounting/qualified/EPS rows, source periods/currency, normalized numeric facts, exact previews and projected web/export content. These are offline content projections, not a live account test or PDF/browser layout certificate. Preserve all failures and no-output cases. Fable's independent completion remains separate.

Measurement-only dispatch is locally ready: explicit manual `measurement_only=true` skips the entire report job, including Google authentication and Cloud Run execution. Default false preserves existing manual and scheduled reporting. This is engineering preparation, not permission to run paid weekly judging or live email as a test; actual no-email dispatch evidence remains unavailable. Because the candidate edits a backend test, current CI would deploy the backend after merge, requiring normal serial verification.

## 4. Remaining master plan, in order

Notable waits for the retain decision after the review week through September 15. Analysis's effective Vercel value was observed true; companyfacts/data and behavior acceptance remain incomplete. W3-7 waits on its real strong-judge readout and arm decision; the manual development corpus is not that artifact. W3-8a then W3-8b retain their sequence and more-than-one-week exception. E09 remains a proposal pending actual fleet/egress/provider/database evidence. E06 waits for Stripe endpoint/API-version observation. Major dependency #749/#750/#751 require the founder's explicit merge decision; D8 and #270 retain their separate holds. #780 is closed after #791.

Authenticated controllable access remains blocked for remaining account observations. The in-app browser lacks Google/Stripe sessions; existing Chrome PostHog project 117863 is readable, but Chrome automation is unavailable in this task. Do not extract cookies/credentials or claim account updates. Routine account authority remains valid when access is available; the user was not repeatedly asked while sleeping.

Source completeness, typed accounting evidence and bounded incorporated-report acquisition are staged future implementation work. The measured trade-offs and prerequisites are in the EdgarTools plan. They do not justify silently expanding prompt budgets, introducing a vendor, or starting universe-wide generation. Complete Fable reconciliation and unseen human acceptance before the founder's quality/spend release.

## 5. Operating procedure to preserve

Use the full eleven-anchor inventory, not only the six introductory CLAUDE paths. Keep DeepSeek and locked contracts unchanged. Gate only committed clean state, one test process per worktree and one mutation proof per invariant. Run three lenses with two refutations for surviving findings. Read exact PR head before any merge; inspect remote state before retrying an irreversible operation. Never merge a backend PR before the preceding deployment is verified. Record deployment evidence in the next docs PR.

Avoid another paid run when only a retained artifact, local code trace or existing evidence can answer the question. An advisory badge and an all-ones heuristic score are not world-class acceptance. No live email/job/account action should be used as a test. No automatic overnight monitor or future background-work promise was created.

## 6. Next session configuration

Resume in the existing workspace and prepared worktrees. Retain source/output artifacts and mutation logs. Use the current minor SDK environment; the older edgar-maintenance-venv does not match #791's updated pins. Ask only about named unresolved founder prerequisites, once, with concrete evidence. Start by checking DeepSeek funding and the actual #792 regression outcome, then continue the serial queue. The founder will supply Fable's remaining review when available.

## Dated addition — 10 September 2026: DeepSeek model cutover (read before any paid assessment)

DeepSeek retires `deepseek-v4-pro` at 04:00 UTC on Monday 14 September; requests are then routed to V4.1 Flash (`deepseek-flash`) at Flash pricing. Consequences for this stream, decided by the founder on 10 Sept (`tasks/deepseek-v41-flash-migration-2026-09-10.md`, `tasks/todo.md`):

1. Any summary or Copilot assessment run against `deepseek-v4-pro` this week measures a model that stops serving production on Monday. Measure the `d`/`e` prompt candidates (#805 and `work/reported-metric-labels`) on `deepseek-flash` after the cutover PR re-pins `baseline_scores.json`, once each; do not re-pin from another PR.
2. `backend/evals/runner.py` now records `provider_usage` per baseline attempt through an `ai_metrics` observer (additive; the result row gains one key, the summary gains token stats). Rebase the local `work/eval-error-outcome` candidate onto it; keep its error-outcome correction.
3. `backend/evals/baselines/` holds the 5 Sept pinned report (V4 Pro reference, 3 × 26). `python -m evals.compare_reports <a> <b>` pairs two reports filing-by-filing.
4. The cutover PR will change one line in `.github/workflows/data-quality-weekly.yml` (`AI_DEFAULT_MODEL`); `work/measurement-only-dispatch` should expect that textual conflict.
5. Check the DeepSeek balance before any paid run; the 9 Sept HTTP 402 cohort was scored from fallback output.
