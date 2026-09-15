# Handover — September 15, 2026, inference stall resolved and two backend releases

Read this alongside the [September 14 resumption handover](handover-astra-2026-09-14-resumption.md), [September 14 wave handover](handover-astra-2026-09-14.md), AGENTS, CLAUDE and relevant lessons. Earlier boundaries and dated corrections remain binding. This checkpoint does not claim the master plan or world-class analysis quality is complete.

## 0. Handover points

Took over at verified main `60df4ef66c6e382416882c821dbdd5a198091f83` (#863). Implementation tip at writing is the #867 merge recorded in section 2; the docs PR containing this file follows it. Read GitHub main before resuming.

Production backend at the overnight checkpoint is `earningsnerd-backend-00349-hs8` (#873); earlier this session it moved through `00345-9t9` (#861), `00346-kz7` (#867), `00347-xwv` (#870) and `00348-hbq` (#872). Both were verified serially: main CI, `apply_migrations: applied=0 skipped=39`, revision at 100%, CI probe and independent detailed-health curl. No backend deploy is pending.

## 1. Standing mandate and boundaries

Unchanged. Bounded necessary DeepSeek spend stays authorized within the founder's budget; the latest readout is USD 84.47 at 00:43 UTC on September 15 (run 34914382524), down 1.09 from 85.56 across the night's four Copilot assessments and five eval measurements; the September 14 readouts of 85.56 were before those runs. Universe-wide pregeneration, historical repair/replay, #805, flags/capacity/prices/trial/promo/registration, provider changes, destructive operations, legal decisions, new locked-anchor exceptions, live jobs/email/accounts as tests, security/secret changes, future dependency majors, Dependabot #270 and D8 deletion remain founder-held. Notable's review runs through September 15; the retain/kill decision falls due once that day ends.

## 2. Completed work

| PR | Result |
| --- | --- |
| [#864](https://github.com/neilmac91/EarningsNerd/pull/864) | Layered diagnostic (unauthenticated POST, keyed free GET, exact application shape, plain call, bare default) with httpcore phase timestamps; merge `8d356f9a`. Run [34898642117](https://github.com/neilmac91/EarningsNerd/actions/runs/34898642117) placed the stall after 200 headers on the thinking-disabled shape only. |
| [#865](https://github.com/neilmac91/EarningsNerd/pull/865) | One-field-at-a-time matrix; merge `e3abfbe3`. Run [34899733464](https://github.com/neilmac91/EarningsNerd/actions/runs/34899733464) showed every shape completing twelve minutes later with nothing changed on our side. |
| [#861](https://github.com/neilmac91/EarningsNerd/pull/861) | Six backend dependency updates accepted on one recorded paid rerun [34899891399](https://github.com/neilmac91/EarningsNerd/actions/runs/34899891399): 18/18 scored and passed, XBRL citations identical to #845. Merge `295d915f`; main CI 34900287819; deploy job 104165390881; revision `00345-9t9`. |
| [#867](https://github.com/neilmac91/EarningsNerd/pull/867) | IFRS revenue provenance: `raw_tag` keeps the qualified source concept. Full gate 3,265 on the merged head under the deployed dependency set; eval-baseline [34901458363](https://github.com/neilmac91/EarningsNerd/actions/runs/34901458363) PASS (52/52 scored, one standing advisory); Copilot [34902202900](https://github.com/neilmac91/EarningsNerd/actions/runs/34902202900) 18/18 with XBRL citations identical to #861's run. Merge `2f526c6d`; main CI 34902536578; deploy job 104172613288; revision `00346-kz7` at 100%; both health probes healthy. |
| [#869](https://github.com/neilmac91/EarningsNerd/pull/869) | Diagnostic runs on the committed SDK pin with the two free layer probes first (Codex findings on the lesson draft). Workflow-only; see its PR for the merge. |
| [#870](https://github.com/neilmac91/EarningsNerd/pull/870) | posthog 7.53.0, PyJWT 2.14.0 from Dependabot #866 via a codex branch (Dependabot branches get no secrets). Full gate 3,265; Copilot 34908041303 18/18; merge `a68b0d2f`; revision `00347-xwv`. |
| [#872](https://github.com/neilmac91/EarningsNerd/pull/872) | EdgarTools 5.58.0 after thirteen-filing offline parity (nine annual, four newly acquired 10-Qs); recorded manual eval-baseline 34908921577 PASS 52/52; Copilot 34909529680 18/18; merge `10f7c132`; revision `00348-hbq`. #866 superseded and closed. |
| [#873](https://github.com/neilmac91/EarningsNerd/pull/873) | W3-8a golden breadth (PLD, NEE, PGR, FIGS, GPRO, BRK.B hand-filled) and re-pin from run 34913316907 (32 × 3, 96/96). PR eval 64/64 PASS, Copilot 34915010028 18/18; merge `5c6a2b7b`; revision `00349-hs8`. |

The diagnosis is recorded in [inference-stall.md](review-evidence/resumption-2026-09-14/inference-stall.md) with both retained diagnostic artifacts beside it. Two lessons were added: `ops-place-a-provider-stall-before-paying-again.md` and `test-fresh-bytecode-prefix-before-trusting-local-timing.md`.

## 2a. What to doubt first

**The stall's production impact is unconfirmed.** Every production path sends the affected request shape, so summaries, Copilot and Analysis were probably timing out between at least 19:30 and about 21:30 UTC on September 14, and nothing establishes when the window began. No `ai_call` log line was read: the Mac's gcloud credential has expired (`invalid_grant`) and the Cloud Console did not render through the browser extension. A fresh `gcloud auth login` is the prerequisite; reading the window's outcomes is then a read-only query. Users who hit the window received deadline failures, not wrong content.

**The provider changed behaviour without notice.** Its status page showed no incident and its documentation now says `temperature` in thinking mode is ignored rather than rejected, which differs from the September 10 reading. The layered diagnostic is the tool for the next such event; do not lengthen production deadlines or switch providers on the strength of one stall.

**The added golden profiles expose scorer/profile gaps, not wrong numbers.** On the pin run BRK.B scored financial depth 0.33 because `score_financial_depth` counts cash-flow, balance-sheet and margin figures and an insurance conglomerate's highlights surface premiums and float instead; its "flat" revenue (371,444M vs 371,433M) is what the filing reports. GPRO scored delta consistency 0.33 because loss-narrowing rows are rendered as "+38.3%" / "+78.4%" while the code-computed table delta on a negative base carries the opposite sign; the arithmetic is right, the convention differs. Treat both as prompt/scorer convention work for those profiles (a listed re-pin trigger when touched), not as measurement errors.

**IFRS correction is forward-only.** Stored facts written before #867 keep `us-gaap:`-prefixed tags for IFRS filers; upsert skips existing identities. Consumers comparing tags across periods withhold rather than mis-difference, so old rows produce missing comparisons, not wrong ones. Repair is historical handling under its own approval.

**Dependabot pull requests can never pass `copilot-eval`.** Their runs receive no repository secrets, so `OPENAI_API_KEY` is empty and the runner exits immediately (#855's 07:46 UTC failure). Dependency groups that need the paid gates go through a `codex/wave3-*` branch; #866's three updates were taken that way in #870 and #872 and Dependabot closed it.

## 3. Local candidates and evidence

Workspace root: `/Users/neilmacaogain/Documents/Codex/2026-09-08/goal-you-are-the-chief-engineering`. New evidence directories: `outputs/deepseek-transport-34898642117`, `outputs/deepseek-transport-34899733464`, `outputs/pr861-copilot-2`, `outputs/ifrs-revenue-provenance/{full-gate-merged.log,eval-report-34901458363,copilot-fidelity-34902202900}`. New worktrees: `work/deepseek-transport-diagnostic-v2`, `work/deepseek-parameter-matrix`, `work/sept14-inference-record`. The `work/backend-minor-sept14-venv` environment now matches main's pins. Use `git -c core.fsmonitor=false`, a fresh `PYTHONPYCACHEPREFIX` for every local Python run, isolated gate databases on PostgreSQL 15 port 55433, and one test process per worktree.

## 4. Remaining master plan

| Item | Next step / blocker |
| --- | --- |
| Quality | Cached analysis defects (Apple cash-flow sentence) and the ASML supplemental-scope sentence remain; historical regeneration held. |
| EdgarTools | 5.58.0 adopted in #872 with thirteen-filing parity and a passing generated-output measurement; nothing pending. |
| W3-10 Notable | Founder retain/kill decision after September 15 closes; then owned flag PR. |
| W3-10 Analysis | Warm-up cohort/count/error evidence and Pro frontend acceptance remain; both need console or log access. |
| W3-7 | Judge credential `ANTHROPIC_API_KEY` absent; weekly artifact unusable. Founder prerequisite unchanged. |
| W3-8a then 8b | W3-8a delivered in #873 under the readout-slip exception (timing basis in the ledger). W3-8b (6-K pre-classifier, three 6-K prompt variants, hand-filled 6-K ground truth, its own re-pin) is next and must wait for #873 to merge; one re-pin in flight at a time. |
| E09 | Read-only inventory blocked on console access this session; proposal-only. |
| E06 | Natural payment evidence still needed; no test payment or replay. |
| Dependencies | Six dev-only advisories have no supported forward fix (npm's only offer is a downgrade to `@lhci/cli` 0.12.0). #270 and D8 held. |

## 5. Next practical action

Read GitHub main first. The next engineering item in governing order is W3-8b (6-K pre-classifier, three 6-K prompt variants, hand-filled 6-K ground truth, its own re-pin); #857 is the only other open non-held PR and needs a merge from main plus a decision on its Codex thread. The founder's overnight re-authentication reached the Chrome console session, not the gcloud CLI (credential files still dated February 5; token refresh returns `invalid_grant`), and the browser extension cannot inject into the Cloud Console page, so the September 14 `ai_call` outcomes for the stall window remain unread. A `gcloud auth login` in a terminal is the remaining prerequisite. [#857](https://github.com/neilmac91/EarningsNerd/pull/857) (an earlier session's lesson and handover pointer fix) is open, conflicting on the lessons index after #868, with an unresolved Codex thread; it was not taken over overnight. Otherwise continue the named master-plan items above under the same serial discipline.
