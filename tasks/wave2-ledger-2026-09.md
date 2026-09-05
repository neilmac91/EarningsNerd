# Wave 2 evidence ledger — interim checkpoint

Checkpoint: 2026-09-05, based on main `c925cfa83647f521583b6fa4dd257ac9027461db`.
The programme remains in progress. Engineering merges do not certify founder backfills,
production generation, a judged readout, or feature activation.

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

Evidence is the merge history, retained PR verification and the chief-engineer session's
observed deployment logs/health checks. Run IDs link through
`https://github.com/neilmac91/EarningsNerd/actions/runs/<run-id>`.
PR #697's [production run 33962267301](https://github.com/neilmac91/EarningsNerd/actions/runs/33962267301)
and job `101296414778` completed successfully: `apply_migrations: applied=1 skipped=33`, revision
`earningsnerd-backend-00263-kzt` serves 100% of traffic, and the pregenerate job's FPI environment
was updated. Detailed health was healthy (database 5.74 ms; CI probe 5.85 ms). The Notable job
remains absent in that deploy's log. The chief-engineer session also observed
[Vercel production success](https://vercel.com/neil-mac-aogains-projects/earnings-nerd/F8LoU8TyScho52C9ZRo8pYUK36yy)
for merge `c925cfa8`. These are production observations, separate from PR CI's migration replay.

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

Sentry production configuration uses its supported config entry. #686 is closed as superseded
by #694/#695. The #696 script proofs sent no email and performed no real Vercel deployment.
[WS-7 implementation archive](archive/ws7-completeness-2026-09.md) separates shipped code from
founder data operations. Exact raw gate tails remain in the respective PR bodies.

The initial #697 full run exposed three real fixture/shape mismatches. Repairs retain existing
revenue dictionary equality, omit unknown fiscal metadata, assert exact newly populated balance
facts, and distinguish original-only from amendment-inclusive freshness. Initial local browser
runs also used a missing browser cache and incorrect waitlist environment; corrected setup passed
without weakening product tests. Warnings, deselections and existing skips are retained above.

## WS-6 remains open

[PR #698](https://github.com/neilmac91/EarningsNerd/pull/698) remains draft. The first parity
measurement ([33960565273](https://github.com/neilmac91/EarningsNerd/actions/runs/33960565273),
26 filings × 2 runs) had zero execution errors but two hard G5 failures: both JPM outputs
omitted the verified $87.004B noninterest-income component. That failed run was not pinned.

The bounded correction preserves legitimate reported bank totals and deterministically replaces
component rows from aligned filing XBRL, including SEC revenue aliases. The subsequent
[33961883439 report](https://github.com/neilmac91/EarningsNerd/actions/runs/33961883439/artifacts/9968277066)
(`eval_20260905T110119Z.json`, source `df3422adc72928a33acdaf1d43995c24cf9e259e`)
contains **52 outputs, zero execution errors, zero gate failures**, and the unchanged regression
gate reports **PASS, 0 warnings**. Citation fidelity was 0.7248; judge was off. Eleven correction
mutations failed. This two-run result does not replace the required final three-run pin. The final 26 × 3 run
[33962580838](https://github.com/neilmac91/EarningsNerd/actions/runs/33962580838) was dispatched at
11:09:48 UTC on integrated source `f5b46ba96b3023f93554087e431937ed9daba3c4`; it is still running
at this checkpoint and the committed baseline is unchanged. Requested streaming/preview metadata alone is not proof that
transport never fell back.

Still open: final parity run/pin (the #697 union is integrated); WARN figure-trace dimension; persisted audit counters;
weekly judged workflow and first readout; resilience including held OpenAI #684; usage/model
telemetry; recovery/previous-filings hygiene; filing-scoped Copilot and verified examples;
then evidence-snap activation only after the first judged readout.

The current session's credential checks found no usable strong-judge credential. An unavailable
judge is not a readout: keep the first judged report and `AI_EVIDENCE_SNAP` held until an
existing authorized strong-judge credential is available. Do not silently substitute a cheaper
judge. No secret values or credentials are recorded here.

## Founder and production gates remain open

- [x] Chief engineer: #697 production run 33962267301, migration summary, revision and detailed
  health verified as recorded above. Coordinate subsequent merges with the active parity run.
- [ ] Founder: SIC backfill and observed report evidence; company identity seed (preview, apply,
  preview) and SIC enrichment for newly seeded issuers. Tooling being merged is not data coverage.
- [ ] Founder: off-peak universe pregeneration after the prerequisites; v1→v2 drain only after
  evidence-snap activation. D4 spend is approved; the execution boundaries remain.
- [ ] Founder: confirm Analysis Vercel flag and warm companyfacts; create Notable job/Scheduler,
  seed and review one week before activation. Calendar licence and Insiders remain held/off.
- [ ] Founder: outstanding console, backup, alerting, secret and legal actions in
  [handover §6](handover-wave2-2026-09.md#6-founder-only-items-outstanding-do-not-do-these-yourself-keep-them-visible).

PR #673 belongs to the founder's other session and remains untouched. The hourly quiet
check-in remains active while work is in flight. This ledger is not a wave-completion report.
