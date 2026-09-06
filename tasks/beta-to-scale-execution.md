# Beta-to-scale execution ledger

Approved by the founder on 2026-09-06 after the read-only audit of `32e10e8`.
Implementation starts from `7d06edc`; re-check code before each item. This ledger tracks
execution of the approved conversation document, not new authority for founder-held actions.

## Engineering queue

All items retain CLAUDE.md's twelve rules, locked contracts, ADRs, one regression home per
invariant and one mutation proof. Keep one unverified backend deployment and one baseline
re-pin in flight at most. New schema uses guarded, idempotent SQL through the migration ledger.

| ID | Objective | Dependency | State |
| --- | --- | --- | --- |
| E01 | Keep mobile example identity and figures from one source | None | #720 released; both-theme mobile preview and production deployment verified |
| E02 | Correct SEC refill elapsed-time accounting | None; isolated branch | #721 released; backend deployment and independent health verified |
| E03 | Release DB connections before generation waits; offload health probe | Before E09; coordinate W3-8b | #723 released; CI/evals, migration tail, revision/traffic and independent health verified |
| E04 | Bound SSE handshake and reject premature EOF | Independent frontend | #722 released; exact-head CI and production Vercel verified |
| E05 | Protect checkout identity and subscription event ordering | Preserve locked Stripe contract | E05a #724 and E05b #725 released; E05c #727 merged after CI/evals and review under helper-only fixture approval; production verification pending. Cross-ID policy remains separate |
| E06 | Record actual nonzero invoices and revenue cohorts | Integrated E05c source | #728 merged as `cab71f9`; root verified deployment. Account export and lifecycle fixture corrections retained |
| E07 | Reserve usage atomically across processes | E03; founder reviews any existing duplicate repair | Queued |
| E08 | Align pricing copy, annual totals and server-derived limits | Coordinate E06/E07 response changes | Queued |
| E09 | Bound fleet/provider/SEC admission and generation ownership | E02, E03, E07; no second generator | E09a local failed-leader handoff implemented; fleet admission and quotas remain separate |
| E10 | Bound hot reads and add filing-first facts index | E03; coordinate W3-9 | Index #726 released; production migration/revision/health verified. Other hot reads queued |
| E11 | Bound delivery and measure alert-to-return loop | E08 limits; calendar activation held | Queued |
| E12 | Expose saturation and bound startup/probe failure | E03; connect E09 counters | Queued |
| E13 | Atomic login failure counts and bounded local limiter state | Locked auth unchanged | Queued |
| E14 | Reuse grounded example on waitlist and share canonical filings | E01; preserve citation/quality state | Queued |
| E15 | Partition sitemap and align eligible content | Independent | Queued |

W3-7 readout review, W3-8a breadth, W3-8b 6-K classification, W3-9 flag-repair preparation
and W3-10 activation retain the prerequisites in [the wave-3 handover](handover-wave3-2026-09.md).
The public-source membership change is merged; do not reopen its removed FMP prerequisite.

## Founder track

- FND1: beta treatment, actual alternate-price mapping, native-trial timing and any locked billing contract change.
- FND2: complete strong-judge evidence, review and explicit guard arming decision; retain the prescribed re-pin sequence.
- FND3: verified production pool/egress/provider limits, spending budget, monitoring and rollback/restore evidence.
- FND4: exact dry-run review and authorization for historical flag, usage-history, seed or drain operations.
- FND5: Notable seed/week review, Analysis warm-up/flag evidence, calendar licensing, public registration and financial referral policy.

Engineering preparation continues while these decisions are held. No mass registration,
price/flag change, paid referral reward or destructive data operation follows from an unchecked row.

## Outcome measures

At $39 monthly / $390 annual and an assumed 50/50 mix, 2,332 nonzero paying subscribers
exceed $1M annualised recurring revenue. This is scenario arithmetic, not current revenue.
Measure actual first payments, renewals, cohort conversion and next-filing returns; allocate
Free/pregeneration/provider/infrastructure costs before claiming gross margin. Beta $0
activations do not count as paid conversion. No current user, conversion, churn or ARR figure
has been established by this implementation session.


## Release checkpoint — 2026-09-06

E01 [#720](https://github.com/neilmac91/EarningsNerd/pull/720) merged as
`7403076f55880e6de0f24d5e310b491e87fef35e` after exact-head
[CI 34019162195](https://github.com/neilmac91/EarningsNerd/actions/runs/34019162195)
and independent correctness/rules/tests review. The frontend-only eval skip was expected.
The branch preview at 390 × 844 showed the live Apple 10-K example with $416.2B revenue,
$112.0B net income and $7.46 EPS, readable in both themes without card clipping. No preview
data was modified; the non-AAPL sparse-data condition is proved by the unit regression,
not by that live preview. Production Vercel deployment `G1Rdtbtf64kNcUD3GAqnVH4Usp5u`
was pending at this checkpoint; merging does not claim production verification.

E02's source and tests are unchanged by the merge of E01 main. Local backend gates,
the single mutation proof and independent three-lens review passed. Prior
[CI 34019200809](https://github.com/neilmac91/EarningsNerd/actions/runs/34019200809)
retained artifact `9984995450`: 52 results, zero errors/vetoes and
`PASS — no hard regressions (1 warning(s)).`; mean untraceable figures 2.2692 is advisory.
Its tested merge source was `7160405614ea6217349aa69b06fa01a569bcf705`, with parents
`7d06edc` and `ec5419fb`; the golden hash was verified. Those are prior-candidate results.
Draft-only Copilot execution was skipped. The new merged head still requires actual CI,
Copilot and root's serialized backend release/deployment verification; no mutation is repeated.

After integrating E01 main, local merge `09758a7` passed the full backend gate:
Ruff/Bandit exit 0; `2390 passed, 2 deselected, 23 warnings in 46.41s`, exit 0.
No backend source/test bytes changed during integration; the existing mutation proof remains valid.

### Updated release evidence

Root verified E01 production Vercel `G1Rdtbtf64kNcUD3GAqnVH4Usp5u` succeeded and the canonical
homepage returned HTTP 200. E02 [#721](https://github.com/neilmac91/EarningsNerd/pull/721)
merged as `5298c77`; [production CI 34024814391](https://github.com/neilmac91/EarningsNerd/actions/runs/34024814391),
deploy `101464120936`, passed with `applied=0 skipped=34`. Revision `00276-qhd` serves 100%;
image `9bb76917797ccc8473eb6b0aa8722151056c724024e317084007b466d6bdcec9`. Independent detailed
health: healthy, DB 7.89 ms, Redis disabled, SEC closed. This supersedes the earlier pending checkpoint.

E04 [#722](https://github.com/neilmac91/EarningsNerd/pull/722) merged as `049cd4f` after
[CI 34025236804](https://github.com/neilmac91/EarningsNerd/actions/runs/34025236804) passed.
Root verified production Vercel `BYywW33Tav6FAoyHa4LZ43h2cCSE` succeeded; main CI `34025409826`
succeeded with backend deployment correctly skipped.

E03 is implemented locally and reviewed after correcting a discovered lazy-subscription lookup
on the route event loop. Frozen input snapshots now resolve missing subscription fields in an
owned worker session; the real-user query-thread regression catches the reviewed defect.
Integrated source `43eb5c8` includes current main `049cd4f`; full backend gate: Ruff clean,
Bandit 0 medium/high, `2412 passed, 2 deselected, 23 warnings in 50.01s` (exit 0). The initial
lifetime/health proofs and one additional exact-site lookup proof are retained. E03 still needs
publication, actual CI/eval inspection and serialized deployment; local evidence is not release evidence.


E05b [#725](https://github.com/neilmac91/EarningsNerd/pull/725) merged as
`f94501fd01d2c330688b7f031616626549793d83`. Root verified production
[CI 34029873954](https://github.com/neilmac91/EarningsNerd/actions/runs/34029873954),
deploy `101477674329`, succeeded with `applied=0 skipped=34`. Image digest
`sha256:627ea716c48753c306437ca72f8a34911370f5a321caac058287fbbba95dcc04`; revision
`earningsnerd-backend-00279-s9z` serves 100%. Independent health timestamp
`1788693905.0609558`: healthy, DB 8.24 ms, Redis disabled, SEC closed.

E05c reconciles only currently bound created/updated events after the existing account lock and
dedup. Initial/different-ID, checkout and exact-ID deletion behavior stay unchanged. The founder
approved only the locked `_post_event` provider stub; every contract assertion remains intact.
Source `aa36c95`: 93 focused billing checks and 13 real PostgreSQL transaction checks passed.
Seven distinct new-invariant mutations produced intended failures and restored exact committed
bytes; the final scope-admission proof restored `aa36c95` and all 45 focused tests passed.
Full backend gate with PostgreSQL enabled: Ruff clean, Bandit 0 medium/high,
`2486 passed, 2 deselected, 23 warnings in 55.96s`, exit 0. The initial `/bin/sh` invocation lost
the macOS native-library environment and failed two PDF tests; direct Python invocation passed
without a source change. Provider timeout settings limit connect/read inactivity, not total
duration. Independent review and release evidence remain pending at this checkpoint.


E06 source `a7e2ff4` integrates E05c and records canonical InvoicePayment allocations without
changing entitlements. Root/independent review found and corrected a report snapshot race;
window rows and first-payment timestamps now share one statement. Final local backend gate:
Ruff clean, Bandit 0 medium/high severity, 2524 passed / 2 deselected in 51.90s with PostgreSQL
cases enabled. Eight initial invariant mutation failures and one exact race proof were restored.
The migration ledger passed 35 apply / 35 skip / 35 replay in a dedicated local database.
Locked Stripe files remain byte-identical to E05c `aa36c95`. Root and independent review are clear; integrated main `6a648f7` in `bef2dc8` without E06
runtime/test changes. Publication and production event-selection verification remain separate; no present
revenue or full-history claim follows from [the report](../docs/observed-invoice-payments.md).

E06 combined source `bef2dc8` (main `6a648f7`) passed Ruff/Bandit and all 2524 backend tests
with PostgreSQL enabled (2 deselected, 23 warnings, 56.08s; exit 0). Earlier 35-file migration
replay remains scoped evidence; combined migration CI must include all 36 files after E10.
Root/independent review is clear, locked files match main, and no mutation was repeated.
Publication follows verified E05c deployment; event coverage is still unverified.

E09a local source `fe6916c` corrects competing failed-leader followers, expired-follower takeover
and delayed empty DB snapshots. A joined follower holds its replacement claim during a fresh
persisted read before admitting provider work. The sole generator, force-regenerate follower
behavior, 120-second backstop, six-slot default and quotas remain unchanged. This does not
establish fleet-safe admission. Three scoped invariant mutation proofs were restored; existing
locked contracts, model/prompt/flags and eval baseline remain unchanged. Final full gate on `fe6916c`: Ruff clean, Bandit 0 medium/high severity; 2483 passed,
8 PostgreSQL-only skips, 2 deselected in 45.82s (exit 0). Root corrected-source review is clear.
Independent acceptance, latest-main integration, actual CI/eval and production release remain separate.
