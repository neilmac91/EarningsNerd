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
| E07 | Reserve usage atomically across processes | E03; founder reviews any existing duplicate repair | E07a #729 released as `90fdc69`; production migration/revision and independent health verified. E07b summary admission reservations #746 released as `c09a4d2`: main CI 34064160001, migration 1/36, revision 00293-fqs at 100%, independent health verified by the handing-over agent; Copilot/Analysis are slice 2; duplicate repair stays founder-held |
| E08 | Align pricing copy, annual totals and server-derived limits | Coordinate E06/E07 response changes | E08a #731 released as `752f3a2`; account-cache isolation #742 released as `555c9ba` (PR CI 34056429179, main CI 34057059586, backend deploy skipped, production Vercel serving verified). Billing-state honesty #743 released as `3f44152` (PR CI 34058400627, main CI 34058656680, backend deploy skipped, production Vercel serving verified). Calendar pending-identity follow-up #744 released as `0b4b7f3` (main CI 34059268610, production serving verified). E08b free-tier cap mirror + lockstep gate #745 released as `e873ac8` (main CI 34060013570, Vercel production 6297983771); price/trial/feature copy without a server field stays founder-held |
| E09 | Bound fleet/provider/SEC admission and generation ownership | E02, E03, E07; no second generator | E09a #735 released as `96d7658`; CI/evals, production migration/revision and independent health verified. Fleet admission/quotas remain separate |
| E10 | Bound hot reads and add filing-first facts index | E03; coordinate W3-9 | Index #726 and saved-status lookup #730 (`e2e94956`) released; production verification recorded by root. Other hot reads remain separate |
| E11 | Bound delivery and measure alert-to-return loop | E08 limits; calendar activation held | E11a #740 released (`c4ae631`), production 34050523535 verified. E11b-0 #741 released (`d7b0177`), production 34055451277 verified. E11b-1 durable delivery is draft #747, original full gate 2620 passed and eight mutation proofs restored; five independent review corrections and final local acceptance in progress. Necessary paid CI subsequently approved in live chat; return measurement remains separate |
| E12 | Expose saturation and bound startup/probe failure | E03; connect E09 counters | E12a #733 released (`cb2c1f8`): production 34040098807, revision 00285-clp at 100%, DB 9.3 ms. Startup deadlines remain separate |
| E13 | Atomic login failure counts and bounded local limiter state | Locked auth unchanged | E13b #732 and E13a #736 (`414ea91`) released; production verification recorded by root |
| E14 | Reuse grounded example on waitlist and share canonical filings | E01; preserve citation/quality state | E14a #734 (`ee3ac988`) and E14b #738 (`d048e215`) released. E14b main CI 34046538868 passed with backend deployment skipped; Vercel 6295470419 succeeded. Clipboard denial remains automated-test evidence only |
| E15 | Partition sitemap and align eligible content | Independent | E15a #737 released (`93e30b0`): production 34045534643, revision 00289-jnn at 100%, DB 9.16 ms. E15b partitioning and eligible DB count remain unresolved |

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


## E15a — Sitemap eligibility parity, local checkpoint

Current integration `0e547de` includes main `96d7658` with original sitemap source/tests/lesson
unchanged (`b922d32`) and incoming E10b/E09/login/frontend/all three PostgreSQL CI lanes
identical to main. Four additive task-record conflicts preserve both histories. Full pinned
Ruff/Bandit/backend gate with all three local PostgreSQL URLs: **2576 passed, 2 deselected,
23 warnings in 54.79s**, exit 0, no skips; Ruff clean, Bandit zero medium/high. Three-lens
review and source/locked-byte checks passed; no repeated mutation or frontend gate.
Exact approval covers normal branch update; current remote acceptance/release remain pending.
Prior head `f84567f` CI `34043458241` failed with BA/BABA 75-second timeouts, 50/52 scores,
two execution errors and two missing scores (artifact `9992485051`). That failure and older
accepted source evidence remain separately retained; no baseline/AI/timeout/flag change was made.

Source `348ef73` reuses the curated unsupported-company predicate and excludes the exact
case-sensitive legacy `Generating summary` substring before the filing cap. Real partial
summaries remain eligible. Existing static entries, dates, single-flight and hourly cache
ownership are preserved; frontend and locked contracts are untouched. Root's independent
three-lens review is clear. Two single mutation proofs failed at their intended exclusions,
then exact restoration passed the full backend gate: Ruff clean, Bandit zero medium/high,
`2482 passed, 8 skipped, 2 deselected, 23 warnings in 49.00s` (exit 0). Skips are existing
PostgreSQL billing cases outside this slice. Exact local logs are recorded in `tasks/todo.md`.
Publication, latest-main integration and deployment remain root-owned and pending.

E15b is unresolved: company URLs are unbounded and 45,000 caps only filing rows, so the
whole document is not bounded by that constant. Partitioning and the actual current production
URL count need separate work. The 1,884 URLs reported on July 16 are historical evidence,
not a current count. No SEO console change, pregeneration spend or flag activation is included.


E15 public-output observation: root fetched the redirected canonical sitemap at
`2026-09-06T13:06:14.210278Z`; retained XML contains **567 URLs (6 static, 522 company,
39 filing)**, independently recounted locally. This is the cached served document, not a fresh
DB census or E15a deployment verification. The observed document has URL headroom; E15b's
whole-document cap/partition work and the current eligible DB count remain separate.
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

E09a integration `6136389` preserves reviewed `fe6916c` source and all E06 corrections from
released main `cab71f9`. Full combined gate with actual Stripe PostgreSQL cases: Ruff clean,
Bandit 0 medium/high, **2531 passed, 2 deselected, 23 warnings in 50.70s**, exit 0. Integration
review across correctness/rules/tests is clear; locked anchors match main. All three original
mutation proofs are retained without repetition. Authorized branch push follows; root owns
PR creation, actual CI/evals and serial release. No fleet admission or reservation implementation.

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

E13a source `24a4d1c`: native PostgreSQL/SQLite failed-login upserts preserve reset/threshold
and timestamp semantics, while successful-login clearing remains in the caller transaction.
Focused real PostgreSQL, behavioral, unchanged auth and workflow checks: 66 passed. One original
implementation mutation proved the concurrent-count and success-clear invariants (5 intended
failures, 1 pass); one missing-CI-URL mutation failed its structural assertion. Exact source
restored before the full backend gate: Ruff clean, Bandit 0 medium/high;
`2446 passed, 2 deselected, 23 warnings in 47.75s`, exit 0 with login and Stripe PostgreSQL
cases enabled. Workflow checks: 103 passed; Node pin: 3 passed. Root source review found no
actionable issue. No schema, configuration, retention deletion, admission reservation or locked
contract change. Root-owned integration/publication/remote CI/release remain pending.

E13a integration `c1ec2bb` includes main `90fdc69` and preserves reviewed `24a4d1c` runtime/tests.
All Stripe, usage and login PostgreSQL CI paths and structural entries are retained. Final combined
Ruff/Bandit gate passed: **2552 passed, 2 deselected, 23 warnings in 45.98s**, exit 0, all three
PostgreSQL URLs configured; workflow readers 104 passed and Node pin 3 passed. Integration review
is clear across correctness/rules/tests, and locked anchors match main. Prior mutation proofs
were not repeated. Authorized branch push follows; root owns PR and serial release.

### E06 verified release

PR #728 merged `cab71f9`; production run 34035873326 / deploy 101494113117 succeeded with
`applied=1 skipped=35`. Image `sha256:b6f32b0a0ca5d06b2675a892f4a2a3d8639c9f2723604c6a50a05c413a3ffea1`;
revision `earningsnerd-backend-00282-6rf` serves 100%. Independent health at
`1788701639.2790875`: healthy, DB 10.3 ms, Redis disabled, SEC closed. The watch client
lost its TLS connection; the completed run and actual deploy log were independently retrieved.
Final CI 34035195505 and Copilot 34035195535 passed; artifacts 9990022068 / 9989975114
verified 52 summary and 18 Copilot cases, unchanged harness/goldens/flags and all source hashes.
This verifies deployment, not Stripe endpoint event selection, API version or complete payment history.

E15a integration `4f65b8d` includes main `cab71f9` with source/test bytes unchanged from
`b922d32`. Three documentation overlaps retained both histories. Independent integration review
is clear; Ruff/Bandit passed and PostgreSQL-enabled backend gate reports **2530 passed,
2 deselected, 23 warnings in 51.22s** (exit 0, no skips). The two original proofs were retained
without repetition. The cached 567-URL snapshot above remains dated evidence, not release
verification. Root owns PR and serialized deployment acceptance after branch publication.

E15a latest integration `52c54bd` retains E07a runtime/CI and E08a frontend from main `752f3a2`.
Sitemap source/tests/lesson remain reviewed `b922d32`; all locked anchors match main. Full combined
gate with Stripe and usage PostgreSQL: Ruff clean, Bandit 0 medium/high; **2549 passed,
2 deselected, 23 warnings in 44.99s**, exit 0. Integration review is clear across all three lenses;
no mutation was repeated. Only existing-branch update is authorized here; root owns PR and release.
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

### E12a / E13b root release evidence at E14a checkpoint

E13b #732 production run `34039409016`, deploy `101503717032`, succeeded with
`applied=0 skipped=36`; revision `00284-n57` serves 100% and independent DB health was
7.26 ms. E12a #733 merged as `cb2c1f8d8e5b5ad9c066110c363a7759907ef0e0`; production
run `34040098807` was pending at this checkpoint. Root owns the remaining verification.
E14a root and independent source review are clear; preview acceptance remains pending.

### E14a measured mobile correction

PR #734 preview at original head `1d42e71` hid the company name at 320 px (width/clientWidth
0, scrollWidth 68). Two independent refutations upheld it. Correction `dd877c0` gives the
issuer a wrapping full-width mobile row with badges/date separate, retaining the desktop
arrangement. Full corrected frontend gate passed: 98 files / 513 tests, lint/typecheck and
build (27/27 pages). Existing four data-invariant proofs remain valid; no repeat or CSS test.
Root must verify the corrected 320/390 px and both-theme preview before release.

E14a second preview correction: the issuer became visible, but root's actual 320 px
screenshot still clipped the right edge/metrics/source/CTA. DOM reads timed out; no numeric
width is recorded. Two fresh refutations upheld it. Source `de432af` constrains mobile grid
and intrinsic card/titlebar sizing, uses two metric columns below sm, wraps labels and keeps
numeric units together. Final full frontend gate passed 98 files / 513 tests in 31.41s,
lint/typecheck and build 27/27. Root must verify corrected 320/390 px and desktop/both-theme
preview before release; the original four data proofs are unchanged and were not repeated.

### E14b local canonical-link action

Source `2ee65a7` from `ee3ac988` adds a Copy filing link action using actual filing.id and
the existing canonical origin. Awaited clipboard completion, pending activation ownership,
inline status/failure/manual link and success-only `filing_link_copied` with filing_id preserve
existing save/export/access/quality behavior. One new real-parent regression home: seven
cases; one coordinated original mutation failed six with one control passing, then restored.
Full pinned frontend gate passed lint/typecheck, 99 files / 520 tests and build 27/27 pages.
No backend, dependencies, locked tests, account URL/query copying, share endpoint or referral
policy changed. Existing SDK enrichment/pageviews are outside this slice; no global telemetry
redaction or actual sharing metric is claimed. Root owns review, released-E10b integration,
responsive/both-theme/denial preview and publication. Exact local logs/proof are in tasks/todo.md.
### E15a approved update checkpoint

The founder's 2026-09-06 “approved” response to all five exact requested actions explicitly
clears the earlier sitemap branch-update hold and covers approved main integration and hermetic
local gates. Merge `8f52c8d` includes main `ee3ac988`; source/tests/lesson match reviewed
`b922d32`, both original proofs remain intact, and integration correctness/rules/tests review is
clear. Full backend with Stripe and usage PostgreSQL URLs: Ruff clean, Bandit zero medium/high;
**2562 passed, 2 deselected, 23 warnings in 49.89s**, exit 0, no skips. The old cached 567-URL
observation remains dated evidence; no new DB census or SEO/deployment claim follows. Root owns
PR creation, CI/eval acceptance and serialized release after this approved branch update.


### E09a latest-main approval checkpoint

The founder's 2026-09-06 “approved” response to the exact five-action request explicitly clears
the earlier summary-handoff publication hold, including main integration and local disposable
PostgreSQL gates. Merge `58afe24` includes main `ee3ac988`; runtime and ownership tests remain
byte-identical to corrected `fe6916c`, with the scoped lesson retained from `5ade3df`. Three-lens
integration review is clear, both delayed-read force modes and all three original proofs remain
intact, and locked contracts match main. Full Stripe/usage PostgreSQL-enabled backend gate:
Ruff clean, Bandit zero medium/high, **2563 passed, 2 deselected, 23 warnings in 57.69s**, exit 0,
no skips. Branch publication is authorized; root owns PR/CI/eval and serialized release. No
fleet lease, durable queue, quota reservation, prompt/model/flag or production policy change.
E13a explicitly approved publication checkpoint: main `ee3ac988` is integrated as `4db2190`.
Reviewed login runtime/tests remain byte-identical to `24a4d1c`; all main limiter, metrics,
billing, usage and frontend changes are preserved. The full pinned gate passed with all three
PostgreSQL URLs: Ruff clean, Bandit 0 medium/high, 2565 passed / 2 deselected / 23 warnings
in 61.96s, exit 0. Workflow readers: 104 passed; Node pin: 3 passed. Three-lens review is clear;
locked anchors unchanged; original mutations retained. Normal branch push is explicitly approved;
root owns PR, remote CI and serial release. Exact evidence is recorded in `tasks/todo.md`.

E14b integration `9974f4d` incorporates exact E10b main `e2e94956` and its login/CI history.
Only task-document conflicts required resolution; E14b source remains byte-identical to
reviewed `2ee65a7`, backend/CI equal main and E10b's six runtime/test files are preserved.
Root source review and three-lens integration review are clear. Original mutation retained,
no repeat. Combined frontend lint/typecheck/build passed; **100 files / 525 tests** passed
in **56.11s**, build static pages **27/27**. Exact logs in tasks/todo.md. Actual responsive,
both-theme and clipboard-denial preview plus publication remain root-owned and pending.

E14b root local-browser acceptance: existing Next build on 4197, guest cached Apple filing 3,
copy wrote exactly `https://www.earningsnerd.io/filing/3`. Action/success verified at 320×844,
390×844 and 1280×900 in both themes; measured DOM width equaled scrollWidth at 390/1280.
Transient incomplete post-resize paint resolved in stable captures without source changes.
Loopback proxy 4198 sent `Permissions-Policy: clipboard-write=()` but copying still succeeded;
actual browser denial is unverified, with automated tests the denial evidence. Theme, empty
clipboard and viewport restored; temporary tab closed and both servers stopped. No live
authenticated/Pro fixture, signup, generation or policy operation. Source unchanged; no gate
repeat. Root retains publication until E09/E15 release sequencing permits it.
### E15a latest released-main integration

Merge `7474eb6` includes exact main `414ea913` with sitemap source/test/lesson identical to
`b922d32`; locked contracts, incoming login/summary runtime, all three PostgreSQL CI lanes
and frontend are unchanged from main. The exact five-action approval covers integration,
full hermetic gates and normal branch update. All three review lenses are clear; original
two mutation proofs and dated public-output observation are preserved without repetition.
Ruff clean, Bandit zero medium/high; all-three-PostgreSQL full backend gate **2569 passed,
2 deselected, 23 warnings in 64.58s**, exit 0, no skips. Prior PR #737 acceptance at head
`6f5e95e` / base `ee3ac988` remains separately retained (CI `34042764106`, ready Copilot
`34042776146`, summary 52 and Copilot 18 accepted with zero errors). New-head remote gates
and serial release remain root-owned and pending; the prior report does not cover this merge.

### E09a integration after E13 release

Prior PR #735 CI `34042620267` is failed AI acceptance: actual regression job failed despite
workflow success, with BA 10-K and BABA 20-F run-0 timeouts at 75.001 seconds (52 attempted,
50 scored, 2 errors; retained artifact `9992244620`). Prior Copilot run `34042670065` accepted
18/18 with 24 source hashes and scratch DB verified; it is historical for the new source.
No old run was retriggered and no timeout, provider, model, flags or baseline were changed.

Main `414ea913` is integrated as `c3b2db2`. Reviewed pipeline/tests still match `fe6916c`;
E13 login source and all three PostgreSQL CI steps are retained. Full pinned local gate:
Ruff clean; Bandit zero medium/high; 2570 passed / 2 deselected / 23 warnings in 72.09s, exit 0,
all three PostgreSQL URLs enabled, no skips. Three-lens integration review is clear; original
mutations retained and locked contracts/frontend match main. Authorized normal branch update
follows the evidence commit. Root owns fresh actual CI/eval acceptance and serial release.

### E14b final publication preparation

Merge `523e15e` integrates exact sitemap main `93e30b0` and preserves both task histories.
The whole frontend tree equals full-tested `9974f4d`; backend/CI equal main, and four E14b
runtime/test files equal reviewed `2ee65a7`. No new source, locked-test or dependency change.
Retain lint/typecheck, 100 files / 525 tests and 27/27 build, plus the original six-failure
mutation and root's local both-theme/mobile success evidence without repetition. Actual
browser denial remains test-only evidence. All three integration-review lenses are clear;
root owns publication and remote acceptance. Exact logs and limitations are in tasks/todo.md.

Current release rows supersede historical pending checkpoints: root reports #730, #734,
#735 and #736 released; #737 merged as `93e30b0`, production verification pending. #735
production run `34044729118` / deploy `101518082921` succeeded, `applied=0 skipped=36`,
revision `earningsnerd-backend-00288-kgv` at 100% traffic; independent DB health 7.31 ms.


## E08 prerequisite — Subscription and usage account-cache isolation

Local source `25b360ff` scopes all seven subscription and five usage consumers by resolved
identity. Synchronous transition cleanup cancels identity first; late data/refresh/identity
responses and login/logout UI continuations obey request ownership. A reason watermark lets
passive expiry cancel old reads without vetoing valid new credentials, while a newer explicit
transition wins. Profile mutation completion uses canonical identity invalidation instead of
publishing its prior account's returned user. Backend entitlements/API, price/trial policy and
analytics schema remain unchanged.

Full pinned frontend lint/typecheck/Vitest/build passed; 101 files, 553 tests, 35.20s. Six original
invariant proofs failed and restored exactly; details, source lineage, corrected review findings
and the resolved ordinary AuthRefresh fixture classification are in the account-cache
sections of `tasks/todo.md`. Named locked anchors remain unchanged. Released 2026-09-06 as
[#742](https://github.com/neilmac91/EarningsNerd/pull/742) → main `555c9ba4e0fb4107b1447c9dfa443f6df4ff81cc`:
PR CI 34056429179 and main CI 34057059586 passed, backend deployment correctly skipped, no paid
evaluation ran, and production Vercel served the new session-transition code by 20:10:54 UTC
(verified from the served `/pricing` chunk). Browser Set-Cookie ordering, cross-tab transitions
and other account caches are outside this bounded claim. Pricing's unknown subscription state
and same-account cached Billing retention are the next separate slice (billing-state honesty).
