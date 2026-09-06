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
| E05 | Protect checkout identity and subscription event ordering | Preserve locked Stripe contract | E05a #724, E05b #725 and E05c #727 released and independently verified; helper-only fixture approval preserved. Cross-ID policy remains separate |
| E06 | Record actual nonzero invoices and revenue cohorts | Integrated E05c source | #728 released as `cab71f9`; production migration, revision and independent health verified. Event-selection coverage remains unverified |
| E07 | Reserve usage atomically across processes | E03; founder reviews any existing duplicate repair | E07a #729 released as `90fdc69`; production migration/revision and independent health verified. Reservations remain separate |
| E08 | Align pricing copy, annual totals and server-derived limits | Coordinate E06/E07 response changes | E08a #731 released as `752f3a2`; CI, Vercel production and canonical pricing response verified. Pricing and activation decisions remain held |
| E09 | Bound fleet/provider/SEC admission and generation ownership | E02, E03, E07; no second generator | Queued |
| E10 | Bound hot reads and add filing-first facts index | E03; coordinate W3-9 | Index #726 released; production migration/revision/health verified. Other hot reads queued |
| E11 | Bound delivery and measure alert-to-return loop | E08 limits; calendar activation held | Queued |
| E12 | Expose saturation and bound startup/probe failure | E03; connect E09 counters | E12a reviewed and integrated with `53348d6`; combined full backend gate passed. Publication/release pending; startup deadlines remain separate |
| E13 | Atomic login failure counts and bounded local limiter state | Locked auth unchanged | E13b #732 merged as `53348d6`; production verification pending. E13a remains on publication hold |
| E14 | Reuse grounded example on waitlist and share canonical filings | E01; preserve citation/quality state | E14a local gate passed; preview/release pending. E14b queued |
| E15 | Partition sitemap and align eligible content | Independent | Queued |

W3-7 readout review, W3-8a breadth, W3-8b 6-K classification, W3-9 flag-repair preparation
and W3-10 activation retain the prerequisites in [the wave-3 handover](handover-wave3-2026-09.md).
The public-source membership change is merged; do not reopen its removed FMP prerequisite.

## Release checkpoint — 2026-09-06

Root recorded E07a #729 production verification: run `34036955028`, deploy job
`101497074770`, `apply_migrations: applied=0 skipped=36`, revision
`earningsnerd-backend-00283-6ck` at 100% traffic, and independent DB health 9.7 ms.
E08a #731 released as `752f3a2`: CI `34037077654` passed, Vercel production deployment
`6293801657` succeeded, and canonical pricing returned 200. Main CI `34037770022` correctly
skipped backend deployment for that frontend change.

E13b #732 is merged as `53348d6`; root is verifying production run `34039409016`, still
active at this checkpoint. This does not clear E13a's independent publication hold.
E12a is prepared on integrated source `ec045eb` with unchanged reviewed source `80abcf0`:
Ruff/Bandit passed; **2558 passed, 2 deselected, 23 warnings in 51.64s** with both PostgreSQL
lanes enabled. One original mutation proof is retained. The authorized branch push follows this
evidence commit; PR acceptance and serialized deployment remain root-owned. Earlier checkpoint
prose below retains its historical meaning.

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


## E08a — Trial presentation follows resolved entitlements

Source `48f51f3`, based on `cab71f9`, requires server-resolved Pro access before showing a current
trial on pricing and settings. Expired-trial Free responses regain the existing upgrade action;
customer-ID portal routing and all backend/checkout behavior remain unchanged. Existing test
homes cover both surfaces. One coordinated original-predicate mutation produced three intended
failures; exact restoration passed lint, typecheck, 504 tests in 97 files and the production build.
Root independently cleared correctness, rules/brief and tests/gates. Exact evidence is in todo.
Both-theme preview, remote CI and release remain root-owned; no live expired-trial fixture was
used. Price amounts/mapping, trial activation, promo, loading labels and FAQ timing are outside
this slice.

E07a source `60f28a0`: SQL monthly increments preserve existing helper calls and history; only
first-bucket creation locks/re-reads the User. Transaction-local lock timeout defaults to 3000 ms,
validated as whole milliseconds from 1 through 10000. Focused real PostgreSQL + workflow gate:
37 passed. Ten distinct mutation proofs failed their intended assertions; exact source restored.
Full backend with both PostgreSQL suites enabled: Ruff clean, Bandit 0 medium/high,
`2458 passed, 2 deselected, 23 warnings in 50.55s`, exit 0. Workflow-focused checks: 103 passed;
Node pin: 3 passed. Locked contracts and eval baseline are untouched. Old service/job writers
must drain before the first-use protocol holds; this stage does not reserve admission, repair
old duplicates or change existing best-effort meter policy. Independent review cleared `60f28a0`;
main `cab71f9` is integrated with E06 corrections intact. The final combined gate passed on `5c5f8b3`: Ruff clean, Bandit 0 medium/high;
2545 passed, 2 deselected, 23 warnings in 57.06s with Stripe and usage PostgreSQL cases enabled.
Workflow readers: 103 passed; Node pin: 3 passed. Integration correctness/rules/tests review is
clear; locked contracts match `cab71f9`, all E06 corrections are retained and E07a source is
unchanged. Authorized branch push follows; root owns PR publication and serial release. Prior
mutation proofs are retained without repetition.


### E06 verified release

PR #728 merged `cab71f9`; production run 34035873326 / deploy 101494113117 succeeded with
`applied=1 skipped=35`. Image `sha256:b6f32b0a0ca5d06b2675a892f4a2a3d8639c9f2723604c6a50a05c413a3ffea1`;
revision `earningsnerd-backend-00282-6rf` serves 100%. Independent health at
`1788701639.2790875`: healthy, DB 10.3 ms, Redis disabled, SEC closed. The watch client
lost its TLS connection; the completed run and actual deploy log were independently retrieved.
Final CI 34035195505 and Copilot 34035195535 passed; artifacts 9990022068 / 9989975114
verified 52 summary and 18 Copilot cases, unchanged harness/goldens/flags and all source hashes.
This verifies deployment, not Stripe endpoint event selection, API version or complete payment history.

### E14a local implementation checkpoint

Source `3153078`, main `cb2c1f8` integrated as `43d554c`: waitlist preview now resolves the
existing public cached example in its own Suspense child. No static fallback for unavailable
or placeholder data; same filing identity/source/quality and a direct canonical preview CTA.
Sparse examples retain a SEC filing link. Existing top CTA, signup/referral behavior and
homepage CTA defaults remain unchanged; no flags, access, generation or backend changes.
Four one-time proofs failed and restored; full frontend lint/typecheck, 98 files / 513 tests
and production build passed. Exact logs, boundaries and proof tails are in tasks/todo.md.
Independent source review cleared; root owns mobile/both-theme preview, PR and release.
E14b canonical-link copying remains separate and unimplemented.
