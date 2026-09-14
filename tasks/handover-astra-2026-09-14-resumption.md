# Handover — September 14, 2026, resumption review and blocked backend acceptance

Read this alongside the [September 14 wave handover](handover-astra-2026-09-14.md), [September 13 checkpoint](handover-astra-2026-09-13.md), AGENTS, CLAUDE and relevant lessons. Earlier boundaries and historical evidence remain binding. This checkpoint does not claim the master plan or world-class analysis quality is complete.

## 0. Handover points

Took over at verified main `324589269edde0c524b103e0f071375378934417` (#856). Implementation tip at writing is `401c9eb709041c79f4e6bc522cb5b1af30271a31` (#862); the docs PR containing this file follows it. Read GitHub main before resuming. The primary local checkout was fast-forwarded cleanly to that implementation tip.

No backend merge or deploy occurred in this resumption. The prior verified backend remains `earningsnerd-backend-00344-kj9`; its verification was not repeated. #861 is draft and not deployed.

## 1. Standing mandate and boundaries

Continue engineering autonomously with committed-state gates, three review lenses, exact-head merges and serial backend verification. Bounded necessary DeepSeek spend is authorized within the founder's budget; the latest balance readout was USD 85.56 before the failed assessment, not a current remaining balance. Unsuccessful calls have unknown cost.

Universe-wide pregeneration awaits explicit world-class confidence. Historical repair/replay is separately held. #805 remains held. Flags/capacity/pricing/trial/promo/registration, provider changes, destructive operations, legal decisions, new locked-anchor exceptions and live job/email/account actions as tests remain founder-held. New dependency majors need a new scoped approval. Notable's review runs through September 15; do not force the decision before that day ends.

## 2. Completed work

| PR | Result |
| --- | --- |
| [#858](https://github.com/neilmac91/EarningsNerd/pull/858) | Resumption review and dated corrections, merge `e245afc9762a0d3603073d7f4ec276f2622d95a8`; main CI 34883074560 passed. |
| [#859](https://github.com/neilmac91/EarningsNerd/pull/859) | Node range `>=22.22.2 <23`, dependency-aware ordinary gate, mutation proof and full frontend gate; merge `d992afffe6bdd650e6d05b78b74ada1909b0c30f`; main CI 34884994797 passed. |
| [#860](https://github.com/neilmac91/EarningsNerd/pull/860) | Five frontend minor updates, 640 tests/build and lockfile review; merge `2b8d8342f92f1b37416736bcba73c65c111e3cbc`; main CI 34887247833 and Vercel production deployment 6444804090 passed. Existing Apple filing smoke passed. #854 closed as superseded. |
| [#862](https://github.com/neilmac91/EarningsNerd/pull/862) | Manual two-request diagnostic, no automatic model calls or backend deploy. Merge `401c9eb709041c79f4e6bc522cb5b1af30271a31`; PR CI 34890801873 and main CI 34891555210 passed. Actual dispatch evidence below. |

The two initial doubts are resolved: the handled `vi.fn` error workaround remains necessary on Vitest 5, proved with failing handled-mock cases and passing plain-function controls; a real stored Apple summary exported as a five-page WeasyPrint 70 PDF, all pages inspected. See the [resumption review](resumption-review-2026-09-14.md). This covers portrait summary rendering, not every Analysis export or semantic quality. The cached Apple cash-flow sentence still contradicts its own numbers on both web and PDF; historical regeneration was not performed.

Six high npm audit package entries remain development-only, zero production entries. No complete supported remedy was established; do not claim a Lighthouse major necessarily fixes them or run force-update.

## 2a. What to doubt first

**The live assessment path is currently unusable.** #861 passed 3,263 local tests, all four PostgreSQL 15 lanes/performance and ordinary CI, but its single paid Copilot assessment returned 18 timeouts at 75 seconds, zero scored answers. Its retained inputs/source hashes match prior accepted #845. [Assessment review](review-evidence/resumption-2026-09-14/backend-assessment.md) records the two refutations and limitations.

The single bounded diagnostic [34891591680](https://github.com/neilmac91/EarningsNerd/actions/runs/34891591680) then timed out on both main OpenAI 3.8 and candidate 3.13, without first tokens or usage. A green diagnostic job is not successful inference. This weakens an upgrade-specific cause but does not prove provider-only failure. Isolate a shared transport/runner/account layer before paying for another full corpus. Do not quietly lengthen production deadlines, switch providers or mark #861 accepted.

**A verified citation can still carry the wrong source namespace.** Retained NVO IFRS revenue was relabelled `us-gaap:Revenue` under both EdgarTools versions. The [finding](review-evidence/resumption-2026-09-14/ifrs-revenue-finding.md) survives actual extraction and citation-path refutations. A local forward-only fix is ready below; old stored rows are not repaired by it.

**Nine-source extraction parity is not a full EdgarTools upgrade gate.** 5.56 and 5.57 returned identical product metrics on AAPL, TSLA, MSFT, ASML, two BABA annual filings, JPM, WMT and NVO, with network denied during parsing. JPM bank selection and NVO IFRS/DKK are covered. Quarterly/YTD, narrative section handling, attachment routing and the RUNBOOK's generated re-pin evidence are not. #855 remains open; #861 deliberately retains 5.56.

## 3. Local candidates and recoverable evidence

Workspace root: `/Users/neilmacaogain/Documents/Codex/2026-09-08/goal-you-are-the-chief-engineering`.

- `work/backend-minor-refresh`, branch `codex/wave3-backend-minor-refresh`, #861 head `6e1334e8106acbfda412554732317663aa830155`. Six package updates, full gates and offline actual SDK transport checks passed. Paid run 34887285696 failed; draft, no deployment. Do not trigger another ready transition or rerun without a reasoned diagnosis and recorded cost decision.
- `work/ifrs-revenue-provenance`, branch `codex/wave3-ifrs-revenue-provenance`, head `a77bab7d78f0f2fe95420cde1be41392365b290b`. Three-file source-namespace fix, 3,265 tests / 29 warnings / no skips, PostgreSQL 15 and all four lanes, eleven unchanged locks, one negative/restored mutation proof. Actual retained NVO SGML → extraction → normalized fact → citation now reports `ifrs-full:Revenue`; DKK 309,064,000,000 and 2025-01-01..2025-12-31 unchanged. Only revenue namespace projections differ. Unpublished; paid assessment/publication held while the shared failure remains unresolved. No DB write or historical replay.
- Evidence directories: `outputs/pr861-copilot`, `outputs/deepseek-transport-34891591680`, `outputs/ifrs-revenue-provenance`, `outputs/edgartools-parity`, `outputs/resumption-2026-09-14`. These are local artifacts, not files a cloud clone automatically receives. Provide them explicitly to a remote successor before it claims to have reviewed them.

Use `git -c core.fsmonitor=false` and shell `login:false` here. Node 22.23.2 is under `work/node-toolchain/node_modules/node/bin`. Existing main-compatible Python environment is `work/weasyprint70-venv`; #861 has `work/backend-minor-sept14-venv`. PostgreSQL 15 is on port 55433. Use fresh bytecode-cache prefixes and isolated gate databases; stale caches caused local import stalls. Preserve failed logs, never claim partial gates passed.

One local procedure mistake was disclosed: a delegate overlapped frontend/backend workflow tests in one worktree. Those results were discarded. The final committed #862 gate ran sequentially (124 backend tests, then three Node tests) and passed. No production/model action resulted from the overlap.

## 4. Remaining master plan

| Item | Next step / blocker |
| --- | --- |
| Quality and dependency release | Diagnose the shared inference failure; then accept actual #861 outputs and deploy serially. Independently publish/assess the ready IFRS fix when the path works. EdgarTools needs its separate extraction/re-pin evidence. Existing cached quality defects and unseen acceptance remain. |
| W3-10 Notable | Founder retain/kill decision after the review week through September 15; then owned flag PR. |
| W3-10 Analysis | Effective Vercel flag was already true. Actual companyfacts warm-up cohort/count/error evidence and Pro frontend acceptance remain. The latest backfill job is a historical liability readout, not warm-up clearance. |
| W3-7 | September 14 scheduled artifact 34880067441 is unavailable, 0/24. Read-only repository metadata shows generator key present, judge `ANTHROPIC_API_KEY` absent. Requires authorized judge credential and usable readout; no secret change or dispatch was done. |
| W3-8a then 8b | Existing breadth/classifier/scorer preparation remains; missing coverage and actual re-pin acceptance remain. Never two re-pin PRs. Preserve the more-than-one-week readout-slip exception without inventing its timing. |
| E09 | [Read-only job observations](review-evidence/resumption-2026-09-14/cloud-run-observations.md) add filing-scan and example-pregeneration limits/outcomes. Remaining job templates, scheduler retry/state, DB peaks and egress ownership still needed; proposal-only, no fleet build. |
| E06 | Natural delivery/signature/application attribution remains; no test payment or historical replay. |
| Dependencies / D8 | #854 superseded; #855 partly prepared; #270 held; development-only advisories unresolved. Exact stale branch deletions still need approval. |

The original plan's other named console/security prerequisites remain in the previous handovers with their dated corrections. Do not ask again for the already observed Analysis flag or GitHub create/approve-PR setting. No new founder answer is needed to investigate the current engineering blocker.

## 5. Next practical action

Read live #861/main state first. Preserve the failed full assessment and both failed tiny probes. Investigate their common path before another paid cohort; do not claim this is a flake. Keep the local IFRS candidate and actual acceptance evidence intact. Continue read-only operational evidence where useful, with no live job invocation or secret/configuration changes. Report the release blocker clearly rather than presenting successful local tests as production acceptance.
