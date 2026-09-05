# Wave 2 evidence ledger — verified engineering handover

Checkpoint: 2026-09-05. Verified backend/code checkpoint #704 is
`123f99eac2b758f0dc7e2b9fcbc2a0a6bbf8146c`; its production deployment is healthy.
**The programme is not complete.** Engineering merges do not certify founder data operations,
the first strong-judge readout or dependent feature activation.

The [earlier ledger through #697](archive/wave2-ledger-through-697-2026-09.md) is an exact
byte copy from #699 (`4257de56823ec10a2a2fcc64b275967c712b028a`). Its relative links were
authored in `tasks/` and retain that original source context. All 52 pre-existing archives
and the original handover §7 remain unchanged.

## Merged engineering

| PR | Scope | Merge SHA | Observed evidence |
|---|---|---|---|
| [#689](https://github.com/neilmac91/EarningsNerd/pull/689) | Execution plan | `47d65a2c4f849ca700627a466d9a20dd0134219b` | Docs only; CI 33957293507 green |
| [#692](https://github.com/neilmac91/EarningsNerd/pull/692) | WS-9 preparation and roadmap archives | `60d8015e68336c61c7355210fcbc0623ca8dd84f` | Docs only; CI 33957917465 green |
| [#691](https://github.com/neilmac91/EarningsNerd/pull/691) | Locate text-node boundary | `a2c7fa70ff7282f823e1f0fca23aabd15c7a8cc1` | Vercel production deployment succeeded |
| [#685](https://github.com/neilmac91/EarningsNerd/pull/685) | Cryptography 50 compatibility | `5cb23b8a3c3b080b428a5fe2004cc608bb0041ea` | Run 33958635353; applied=0 skipped=32; revision 00260-xfw; healthy |
| [#693](https://github.com/neilmac91/EarningsNerd/pull/693) | Hourly ISR sitemap freshness | `157e6a39b5a427074cc04993a8efd902ea55d326` | Vercel production deployment succeeded |
| [#690](https://github.com/neilmac91/EarningsNerd/pull/690) | WS-7 steps 1–2: statement default and job/report integrity | `99e91ba7721190e3df887d159beb9eb041094b62` | Run 33959305523; applied=1 skipped=32; revision 00261-z7x; healthy |
| [#694](https://github.com/neilmac91/EarningsNerd/pull/694) | Non-Sentry frontend dependency split | `6e169de83cc55cbc55a881b69c2a581196d914e4` | CI 33959296135 green; supersedes #686 part 1 |
| [#696](https://github.com/neilmac91/EarningsNerd/pull/696) | Configuration inventory and script placement | `0e0e7762cadda0fddd40407377467911550a28e3` | Run 33959884494; applied=0 skipped=33; revision 00262-4lj; healthy |
| [#695](https://github.com/neilmac91/EarningsNerd/pull/695) | Sentry 10.73 with isolated Vitest compatibility | `919aa8629c6b53d2d29a98ad35b10dadfcbe6885` | Vercel production deployment succeeded; supersedes #686 part 2 |
| [#697](https://github.com/neilmac91/EarningsNerd/pull/697) | WS-7 steps 3–6: periods, amendments, quality and seed tooling | `c925cfa83647f521583b6fa4dd257ac9027461db` | CI 33961912275 green; run 33962267301 applied=1 skipped=33; revision 00263-kzt; healthy; Vercel success |
| [#699](https://github.com/neilmac91/EarningsNerd/pull/699) | Interim ledger (historical) | `4257de56823ec10a2a2fcc64b275967c712b028a` | Docs only; CI [33963048325](https://github.com/neilmac91/EarningsNerd/actions/runs/33963048325) |
| [#698](https://github.com/neilmac91/EarningsNerd/pull/698) | Parity, G5 correction and sole measured pin | `d696f4081ff8987d197fc4785581f3d00a0d41db` | 78/78 accepted; CI [33963437020](https://github.com/neilmac91/EarningsNerd/actions/runs/33963437020) |
| [#700](https://github.com/neilmac91/EarningsNerd/pull/700) | Persisted audit measurement and judged-readout implementation | `80314db6b978d38d49a2fe2f1b8719a13f08baff` | 52/52 accepted; CI [33965545733](https://github.com/neilmac91/EarningsNerd/actions/runs/33965545733) |
| [#701](https://github.com/neilmac91/EarningsNerd/pull/701) | Resilience, actual usage/model telemetry and strict completeness | `f4c6041f50648fa2e5a5e4347afc1a4cd5085818` | 52/52 accepted; CI [33977112696](https://github.com/neilmac91/EarningsNerd/actions/runs/33977112696); #684 closed as integrated |
| [#702](https://github.com/neilmac91/EarningsNerd/pull/702) | Filing-only inputs and labelled recovery context | `efc81adcd5f4891836b2d6c5b4d28460d08b3fa9` | 52/52 accepted; CI [33980331589](https://github.com/neilmac91/EarningsNerd/actions/runs/33980331589) |
| [#703](https://github.com/neilmac91/EarningsNerd/pull/703) | Accession/currency-scoped Copilot and actual source-backed evaluation | `d7a2a269a0d993d3a7c6d19ef2c602babbe39061` | Summary 52/52; Copilot 18/18; CI [33985211897](https://github.com/neilmac91/EarningsNerd/actions/runs/33985211897) |
| [#673](https://github.com/neilmac91/EarningsNerd/pull/673) | External logging/privacy work, preserved without edits by this task | `a1c108a38900886effe0b5eb9870893bb8f0f2fd` | Externally merged; deployment [33987415379](https://github.com/neilmac91/EarningsNerd/actions/runs/33987415379) verified |
| [#704](https://github.com/neilmac91/EarningsNerd/pull/704) | Actual ORM reporting date into prospective reconciliation | `123f99eac2b758f0dc7e2b9fcbc2a0a6bbf8146c` | Summary 52/52; Copilot 18/18; union CI [33987628737](https://github.com/neilmac91/EarningsNerd/actions/runs/33987628737) |

Evidence is the merge history, retained PR verification and the chief-engineer session's
observed deployment logs/health checks. Run IDs link through
`https://github.com/neilmac91/EarningsNerd/actions/runs/<run-id>`.
Latest backend [production run 33988401306](https://github.com/neilmac91/EarningsNerd/actions/runs/33988401306),
job `101366418068`, succeeded: `apply_migrations: applied=0 skipped=34`, revision
`earningsnerd-backend-00270-4k6` serves 100% of traffic; detailed health was healthy
(CI database 6.76 ms, independent probe 6.46 ms). The Notable job was still absent in the actual log.

Last verified frontend production checkpoint remains #697, with
[Vercel production success](https://vercel.com/neil-mac-aogains-projects/earnings-nerd/F8LoU8TyScho52C9ZRo8pYUK36yy).
Subsequent backend stages do not establish a newer frontend deployment. #697 also deployed
the pregenerate FPI environment; founder seed, SIC enrichment and actual generation remain separate.

| Backend stage | Verified production run | Migration summary | Revision (100% traffic; healthy) |
|---|---|---|---|
| #698 | [33964233483](https://github.com/neilmac91/EarningsNerd/actions/runs/33964233483) | applied=0 skipped=34 | 00264-ctx |
| #700 | [33966302078](https://github.com/neilmac91/EarningsNerd/actions/runs/33966302078) | applied=0 skipped=34 | 00265-9js |
| #701 | [33977786320](https://github.com/neilmac91/EarningsNerd/actions/runs/33977786320) | applied=0 skipped=34 | 00266-q6k |
| #702 | [33981155212](https://github.com/neilmac91/EarningsNerd/actions/runs/33981155212) | applied=0 skipped=34 | 00267-2kc |
| #703 | [33986181022](https://github.com/neilmac91/EarningsNerd/actions/runs/33986181022) | applied=0 skipped=34 | 00268-jn7 |
| External #673 | [33987415379](https://github.com/neilmac91/EarningsNerd/actions/runs/33987415379) | applied=0 skipped=34 | 00269-xgx |
| #704 | [33988401306](https://github.com/neilmac91/EarningsNerd/actions/runs/33988401306) | applied=0 skipped=34 | 00270-4k6 |

## Gate evidence and limits

| Candidate | Observed gate results | Relevant limits/proof |
|---|---|---|
| #691 | Full frontend gate; 470 unit tests; 20 Playwright passes | Exact range/scroll mutations failed |
| #693 | Full frontend gate; 474 unit tests; 21 Playwright passes | Three route/upstream/fallback mutations failed |
| #694 | Fresh final-lock `npm ci`; full frontend gate; 474 unit tests; 21 Playwright passes | All `@sentry/*` package entries unchanged; residual Sentry transitive churn restored before final gate |
| #695 | Union with #694: clean install 1077 packages; lint/typecheck; 475 unit tests; build; 21 Playwright passes | Real browser SDK emitted an in-memory envelope; removing Vitest-only alias failed at import |
| #696 | Full backend gate; 1910 passed; 2 existing performance deselections | Settings name/default mutations and moved-script file-relative/stubbed checks passed |
| #697 local, source `6076fe7f` | Ruff/bandit pass; 1935 backend passed, 2 deselected, 72 warnings; clean frontend install, lint/typecheck, 487 tests, build; no-backend Playwright 21 passed / 3 existing skips | 32 backend, 10 Analysis UI and 5 supersession UI mutations all failed and were restored |
| #697 [CI 33961912275](https://github.com/neilmac91/EarningsNerd/actions/runs/33961912275) | 1935 backend passes; 2 performance passes; 487 frontend tests; Playwright 21 passed / 3 existing skips | PostgreSQL seed/replay each applied 34; ledger rerun applied 0 / skipped 34 |
| #698 | Local backend 1961 passed; actual 26 × 3 pin: 78 accepted, 0 errors/vetoes, PASS/0 warnings | Sole authoritative pin; subsequent stages do not re-pin |
| #700 | Local backend 2026 passed / 2 deselected; actual 52/52 accepted, 0 errors/vetoes, one advisory | 52 valid mutations; judge-off regression is not the first readout |
| #701 | `2138 passed, 2 deselected, 72 warnings in 41.03s`; actual 52/52 accepted | Resilience plus strict complete-report gate; initial 51/52 remains failed evidence |
| #702 | `2167 passed, 2 deselected, 72 warnings in 40.28s`; actual 52/52 accepted | 54 valid mutations; invalid/equivalent attempts excluded |
| #703 | `2319 passed, 2 deselected, 72 warnings in 48.82s`; actual summary 52/52 and Copilot 18/18 accepted | 143 valid mutations; five uncited answers remain advisory |
| #704 exact union | `2354 passed, 2 deselected, 72 warnings in 52.71s`; Ruff/Bandit passed | Eight valid mutations; three independent integration reviews include external #673 |
| #704 [CI 33987628737](https://github.com/neilmac91/EarningsNerd/actions/runs/33987628737) | Backend `2354 passed, 2 deselected, 23 warnings in 170.48s`; performance 2 passed / 13.96s; frontend 487; Playwright 21 passed / 3 existing skips / 17.6s | PostgreSQL apply/skip replay: 34/0 → 0/34 → 34/0; actual summary 52/52 accepted |

Sentry production configuration uses its supported config entry. #686 is closed as superseded
by #694/#695. The #696 script proofs sent no email and performed no real Vercel deployment.
[WS-7 implementation archive](archive/ws7-completeness-2026-09.md) separates shipped code from
founder data operations. Exact raw gate tails remain in the respective PR bodies.

The initial #697 full run exposed three real fixture/shape mismatches. Repairs retain existing
revenue dictionary equality, omit unknown fiscal metadata, assert exact newly populated balance
facts, and distinguish original-only from amendment-inclusive freshness. Initial local browser
runs also used a missing browser cache and incorrect waitlist environment; corrected setup passed
without weakening product tests. Warnings, deselections and existing skips are retained above.

## Accepted AI evidence and retained failures

The sole parity pin is [run 33962580838](https://github.com/neilmac91/EarningsNerd/actions/runs/33962580838),
measured source `f5b46ba96b3023f93554087e431937ed9daba3c4`: 26 × 3 = 78 accepted,
zero errors/vetoes, PASS/0 warnings. The initial JPM G5 omissions in
[33960565273](https://github.com/neilmac91/EarningsNerd/actions/runs/33960565273) were legitimate
failures and were not pinned. Aligned XBRL bank-component replacement and truthful total handling
passed a subsequent two-run measurement before that sole final pin.

Measurement, resilience, hygiene and Copilot implementation subsequently shipped (#700–#703).
The first resilience [33975395335](https://github.com/neilmac91/EarningsNerd/actions/runs/33975395335)
report had 52 attempts but only 51 scores; the old gate's PASS was invalid. Strict declared
identities, counts, errors and score presence now veto incomplete reports without inventing zero
quality scores. Scored-only means and the original thresholds remain intact.

The first Copilot [33984283703](https://github.com/neilmac91/EarningsNerd/actions/runs/33984283703)
report completed 18 attempts but passed only 14. Explicit Bash pipeline failure propagation,
a Copilot-only per-share unit adapter and exact contiguous-quote instructions corrected the
confirmed causes; an invented stitched quote still hard-fails. The separate summary
[33984195172](https://github.com/neilmac91/EarningsNerd/actions/runs/33984195172) timeout report
remains failed 51/52 evidence; no deadline increase, threshold relaxation or re-pin followed.
Final #703 [Copilot 33985648605](https://github.com/neilmac91/EarningsNerd/actions/runs/33985648605)
accepted all 18 attempts (six accessions, five issuers, three draws each); five answers lacked
citations, which remains an advisory coverage limitation.

Final #704 [summary CI](https://github.com/neilmac91/EarningsNerd/actions/runs/33987628737)
accepted 52/52, zero errors/vetoes, with one absolute figure-trace advisory (citation fidelity
0.695). [Copilot 33988057484](https://github.com/neilmac91/EarningsNerd/actions/runs/33988057484)
accepted 18/18; six answers used no tools/citations, so citation coverage 0.6667 remains advisory.
Actual source facts matched the prior fresh preparation. This is source/eval evidence, not a
production backfill or historical flag repair. Direct filing facts remain available; unknown
period starts prevent derived arithmetic and return `basis_unavailable` rather than invented dates.

The workflow and report receiver for the fixed eight-filing × three-repeat strong-judge readout
exist, but no usable strong-judge credential or actual readout was available. Unavailable,
simulated, judge-off and deterministic Copilot results do not satisfy D5. Keep evidence-snap held;
figure-trace and forward-quote remain advisory. Completed plans are linked from the active todo.

## Founder and production gates remain open

- [x] #704 deployment, migration summary, traffic and detailed health verified above.
- [ ] First actual strong-judge readout, then D5 evidence-snap activation and D4 stale-summary drain.
- [ ] SIC and company seed, live report coverage, Analysis warm-up and off-peak universe generation.
- [ ] Notable job/Scheduler, seed and one full subsequent week of review before the accepted D3 action.
- [ ] Remaining console, licence, legal and launch actions in the single
  [founder list](handover-wave2-2026-09.md#6-founder-only-items-outstanding-do-not-do-these-yourself-keep-them-visible).

#673 was externally merged during #704 validation; this task preserved that work and did not
author or execute its merge. #704 was accepted on the union. As of the 2026-09-05 pre-merge source checkpoint
`177f9ff4`, documentation review/CI/merge remained pending in todo. [PR #705](https://github.com/neilmac91/EarningsNerd/pull/705)
is authoritative for its subsequent outcome. This is an engineering
handover, not completion of original §7.
