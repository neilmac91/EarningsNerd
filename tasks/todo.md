# Remediation plan — from the September 2026 engineering audit

## Wave 3 — GPT-6 Astra session (2026-09)

### W3-3 public-source replacement — 2026-09-06

The founder requested an FMP-independent constituent filter. Live public retrieval returned
503 S&P 500 rows and 102 Nasdaq-100 rows. The Nasdaq constituents table is on the dedicated
`List_of_NASDAQ-100_companies` page, not the general article used by the old script.
This supersedes the FMP-access prerequisite for this replacement; it does not assert that
FMP entitlement was repaired or change any later founder hold. The existing application
already filters against the committed union; only its maintenance path needs replacement.

- [ ] Make the automatic refresh use both public constituent lists without any FMP credential;
  preserve explicit FMP compatibility, normalization, per-index floors, prior-file protection,
  reviewed-commit delivery, and the unchanged 100-day age limit.
- [ ] Verify the fetched lists and changes, demonstrate the filter on the supplied 77-row CSV,
  and update owning workflow/docs plus the lesson about checking public alternatives.
- [ ] Run meaningful offline regression/mutation checks and the full backend gate; review
  correctness, rules and tests independently before readiness.
- [ ] Publish the draft PR, inspect required CI, merge and verify the backend deployment;
  dispatch the public refresh and retain its actual result. Any Actions-policy prerequisite
  remains founder-owned; never change settings or introduce a PAT workaround.

### Current checkpoint — 2026-09-06

W3-0, W3-1, W3-2, W3-4, W3-5 and W3-6 are complete with the recorded verification below.
W3-6 [#716](https://github.com/neilmac91/EarningsNerd/pull/716) merged
`a7bc78be791d188f4f36d399dd117ee4282a84bd`; its source gates and independent reviews are
verified. [Production run 34010252813](https://github.com/neilmac91/EarningsNerd/actions/runs/34010252813),
deploy job 101424963044, succeeded with `applied=0 skipped=34`; revision
`earningsnerd-backend-00274-fgq` serves 100% of traffic. Image digest
`b5ab6f9067f5047df5c4adb4b4071ca9a7315d5e97527d5a9911c291583b9f58` matches source `a7bc78be`.
Independent `/health/detailed` is healthy: DB 6.41 ms, SEC closed, Redis disabled/healthy.
The Notable job was not found and its update was skipped; provisioning/activation remains held.
This is not completion of wave 3.

- [x] Final [CI 34009654771](https://github.com/neilmac91/EarningsNerd/actions/runs/34009654771):
  backend 2386 passed, 2 deselected, 23 warnings (70.51s); performance 2 passed,
  18 warnings (15.03s); frontend 487 passed; browser 21 passed (17.1s), 3 existing skips.
  PostgreSQL migration passes: applied/skipped `34/0`, `0/34`, `34/0`.
- [x] Summary artifact `9982136005`: 52 complete results, zero errors/vetoes; typed guards
  and source hashes preserved. Mean untraceable figures 2.0769 remains advisory.
  [Copilot 34010025095](https://github.com/neilmac91/EarningsNerd/actions/runs/34010025095),
  artifact `9982206256`: 18 passing results, zero errors/vetoes; six source bundles and
  database hashes verified. Neither result is the held strong-judge readout.
- [x] W3-5's late DevOps dependency-pinning prose qualification is included in merged #716;
  application/lint-test requirements are locked, ancillary installers are not uniformly pinned.
- [x] #716 deployment, actual migration tail, serving revision/traffic and independent public
  health verified as recorded above.
- [ ] Separate frontend audit follow-up: the current GitHub open-alert readout retains
  [Dependabot #270](https://github.com/neilmac91/EarningsNerd/security/dependabot/270),
  high-severity `extract-zip` in `frontend/package-lock.json`, development
  scope. No backend alert is open and the runtime-lock pip-audit is clean; this does not
  establish repository-wide audit clearance or change the advisory policy. No dependency
  change for this unrelated finding is included in W3-6.

W3-3 remains held: supplied `Production` credentials reached
[run 34000192154](https://github.com/neilmac91/EarningsNerd/actions/runs/34000192154), which
failed at the first S&P 500 route `/stable/sp500-constituent` with HTTP 402 (exit 2).
[Issue #710](https://github.com/neilmac91/EarningsNerd/issues/710) remains open. No data or
auto-PR was produced; `/stable/nasdaq-constituent` was not reached. The founder must provide
account/key entitlement for both documented routes before retry. The response alone does not
establish a billing cause, and this is not a missing-secret finding. All later founder holds remain.

### W3-6 implementation history — PyJWT migration

The following checklists preserve pre-merge source and correction checkpoints, including their
then-current draft/release status. The current status is the checkpoint above.


Owner: plan_correctness. Root owns publication, independent reviews, CI, merge and deployment.
Entry satisfied: #715 merged `56d33f0435723030b072017ba47e2d3e32697132`; production
[34006685337](https://github.com/neilmac91/EarningsNerd/actions/runs/34006685337), deploy job
101415369329, succeeded with `applied=0 skipped=34`, revision `00273-r65` at 100%.
Image digest `d3c86ac5d708dd272e0a7619d3e3eff2deb83428f16705f2beadd662ef92548b`;
independent detailed health healthy (DB 15.29 ms, SEC closed). Notable job was not found and
its update was skipped; its founder provisioning/activation hold remains.

PR #716 remains draft for a further independently confirmed waitlist clock-skew correction.
The completed Google/probe correction below is retained as superseded release evidence.

- [x] Add configured leeway at the remaining waitlist decode; audit all five production
  decodes without changing algorithms, claim requirements, audiences, issuers or token type.
- [x] Add one offline test through the actual waitlist token issuer and verification route:
  +5-second issuer skew persists verification; +11 seconds returns HTTP 400 and leaves a
  distinct signup unverified in isolated SQLite.
- [x] Commit source, remove only waitlist leeway for one intended failure, restore exact bytes,
  then run the full coherent 102-pin Ruff/Bandit/pytest gate. Preserve lock and existing tests.

Final waitlist source `0626f0ab`: all five production JWT decodes use configured leeway;
fixed algorithms and existing audience/issuer/type/subject/required-claim checks are unchanged.
The real waitlist issuer runs five seconds ahead of a frozen verifier; the actual route persists
`email_verified=True` in isolated SQLite. An eleven-second token returns HTTP 400 and its
separate signup remains unverified. Focused: 1 passed, 16 warnings (3.57s). Removing only
waitlist leeway fails the intended positive route call (1 failed, 16 warnings in 3.47s);
exact restoration passes (1 passed, 16 warnings in 2.84s), router SHA256
`e2cbff30387f00e4f17b2c4c0dc3b5eed6b9bce71913477378ebefe170a235da`.
Full coherent gate: 102 exact pins, Ruff/Bandit exit 0;
2386 passed, 2 deselected, 23 warnings (51.09s), exit 0.
Lock, the two approved existing-test edits, Google regression and original AST gate remain
unchanged; their retained audit/mutation evidence is scoped to those unchanged files.
Four locked contracts, sole baseline, 59 archives and historical findings remain byte-identical;
18 local owning-document links resolve. No live OAuth or network operation was performed.
Root owns final review and release; the earlier correction evidence below is historical.

PR #716 is draft again for two independently confirmed review corrections; prior source
and gate evidence below remains historical and is superseded for release by this correction.

- [x] Replace the stale dynamic dependency probe tuple with `PyJWT` / `jwt`; verify only
  the extracted `check_dependencies` function offline, never the full deployment diagnostic.
- [x] Give Google token validation the configured clock-skew leeway. The current 10-second
  setting also applies to its `exp`/`nbf` checks; document that expanded tolerance explicitly.
- [x] Add one deterministic offline Google RSA/JWK test: near-future `iat` within leeway
  succeeds and beyond leeway fails. Keep the two prior approved existing-test edits unchanged.
- [x] Commit source; remove only Google's leeway to prove the intended regression assertion,
  restore exactly and run one full coherent 102-pin backend gate. Lock/audit evidence is unchanged.

Corrected source `c5d1f3d3`: the offline AST-extracted dependency probe passes with PyJWT;
no full diagnostic or live OAuth was run. Real local RSA/JWK with frozen validation time
passes the +5-second `iat` and rejects +11 seconds at configured leeway 10 seconds.
Focused test: 1 passed, 1 warning (0.45s). Removing only Google's configured leeway fails
that intended near-future acceptance call (1 failed, 1 warning in 0.21s); exact restoration
passes (1 passed, 1 warning in 0.16s), source SHA256
`a5a5feaa374305fa37b4cd3b57e2aa6ce0851617f207c43357d77bd8623d45e8`.
The corrected full coherent gate verifies 102 exact pins; Ruff/Bandit exit 0;
2385 passed, 2 deselected, 23 warnings (56.16s), exit 0. Existing post-summary shutdown
logging error remains recorded. Lock, the two approved existing-test edits and original AST
gate are byte-identical to the previous candidate, so unchanged audit and earlier AST proof
remain scoped evidence. All locked contracts, baseline, 59 current archives and historical
review finding bodies remain exact; 18 local owning-document links resolve.
Root owns final review, CI and publication; previous release evidence below is historical.

- [x] Migrate only the four JWT production modules, preserving fixed algorithms, audiences,
  issuers, nonce binding, string subjects and configured clock-skew leeway. Disclose that
  PyJWT enforces the existing required-claim lists and future `iat` validation.
- [x] Apply the two founder-preapproved non-locked test edits: library/leeway in
  `test_security_hardening_week7.py`, selected-JWK conversion in `test_apple_signin.py`.
  Keep all assertions and the four locked contracts unchanged; no live OAuth.
- [x] Resolve the observed compiler platform delta before accepting the lock: macOS ARM
  SQLAlchemy metadata omits greenlet, although existing Linux/CI lock includes 3.5.1. Preserve
  that existing runtime pin through an explicit input, without enabling async database behavior.
  Retain the first compiler output and re-check that only the four retired packages disappear.
- [x] Replace the dependency input with `PyJWT[crypto]>=2.10,<3`; compile using documented
  Python 3.11 command and pip-tools 7.6.1, preserving unrelated pins. Install a fresh coherent
  runtime outside Documents; prove retired jose/ecdsa/rsa/pyasn1 distributions absent.
- [x] Add the one planned AST/dependency gate; inject one actual jose import, demonstrate its
  intended assertion failure, restore exact committed bytes and retain both tails.
- [x] Run full Ruff/Bandit/pytest and actual pip-audit; preserve advisory posture and report
  remaining findings. Prove locked contracts, sole baseline and historical archives unchanged.
- [x] Include the separately confirmed late W3-5 prose correction: qualify the DevOps brief
  dependency-pinning claim; preserve its no-new-unpinned-installs directive and change no tools/workflows.
- [x] Synchronize active handover/todo checkpoints with observed evidence; retain dated
  historical findings and original definition of done. Commit final results, stop before push.

Local source `25548116`: Python 3.11.16 / PyJWT 2.13.0, 102 exact runtime/dev pins,
retired jose/ecdsa/rsa/pyasn1 distributions and modules absent. Documented pip-compile command
retained every unrelated version; explicit greenlet 3.5.1 input preserves the prior Linux pin.
The first platform-dropping output is retained and excluded. The supported compiler header
override records actual arguments after a Click default-rendering artifact; no resolver flag
or compiled version was hand-edited.

Focused existing auth/refresh/Apple/leeway and the new gate: 44 passed, 17 warnings (28.74s).
The sole new actual-jose-import mutant failed its intended AST assertion (1 failed in 0.58s),
then exact restoration passed (1 passed in 0.51s). Full Ruff/Bandit exit 0;
2384 passed, 2 deselected, 23 warnings (67.59s), exit 0. The existing post-summary shutdown
logging error is retained. Actual runtime-lock pip-audit reports 99 dependencies, no known
vulnerabilities, exit 0; audit policy stays advisory and other ecosystems are not covered.
All 59 current archives (including the original 52), original handover/ledger, dated review
finding text, four locked contracts and sole baseline are byte-identical; 18 local owning-doc
links resolve. The private initial archive-count assumption (52 total versus actual 59) was
corrected to compare complete inventories and retained as excluded checker evidence.

- [ ] Root: final independent review, draft publication, actual required CI, merge and verified
  deployment. Local source/evidence completion does not claim a shipped W3-6 change.

### W3-5 preparation history — verified #715

W3-5 is complete with the deployment evidence above. Final CI 34006454576 passed backend
2383 tests, performance 2, frontend 487 and browser 21 (3 existing skips), plus PostgreSQL
triple application. Copilot run 34006471949 artifact 9981128325 contains 18 passing results,
zero errors/vetoes and verified six-source/database hashes. The checkboxes and draft-status
statements below preserve their pre-merge source checkpoints; they are not current holds.


Latest review confirmed two bounded gaps after independent refutation: companyfacts transport
made the EFTS-only exception wording incomplete, and case-insensitive Render phrases matched
benign rendering text. Earlier CI and mutation evidence remains scoped history.

- [x] Correct active SEC guidance and literal-gate descriptions without changing runtime or
  executable SEC checks; distinguish limiter-only paths, local parsing and the manual diagnostic.
- [x] Bound the three Render platform phrases and assert benign rendering text in the same gate.
- [x] Removed-boundary mutant failed the intended `section rendering` assertion: `1 failed
  in 0.03s`; exact restoration passed (`1 passed in 0.04s`).
- [x] Source `37b3e04e`: coherent Python 3.11.16, 105 exact pins, Ruff/Bandit exit 0;
  `2383 passed, 2 deselected, 23 warnings in 54.17s`, exit 0. SEC-gate executable AST is
  unchanged after excluding its description/error messages; application runtime is unchanged.
  Final prose preserves existing transport ownership even for paced requests.
  All 80 brief source paths and 152 local links resolve (31 brief links); original archives,
  §7/ledger, locked contracts and sole baseline remain exact.
- [x] Independent correctness and tests/rules reviews cleared the final delta and actual
  proof/full-gate evidence; root verified the documentation-only result checkpoint.
- [ ] Root: inspect corrected actual CI, merge and verify deployment.

The final table audit corrected app-chrome placement to files directly under `frontend/components/`
and distinguished seven configured job targets from verified provisioning. Root and two reviewers
checked the entire stack table against source. Conflicting CLAUDE/deployment prose now preserves
the required pregenerate update and conditional updates for the other six jobs.

Final prose review qualified existing stateful discovery GETs in the API brief after two
independent refutation attempts confirmed the contradiction. Runtime and gated source are unchanged.
The optional `frontend/src` matcher suggestion is outside the specified token set; current engineering
briefs contain no such path, and the frozen legacy set is preserved.

A further review confirmed lowercase obsolete recipes bypassed the case-sensitive pattern.
Two independent attempts to disprove the finding confirmed the gap. The full
case-insensitive scan requires no frozen-allowlist expansion. PR #715 remains draft.

- [x] Add `re.IGNORECASE` to the existing obsolete-stack pattern only.
- [x] Actual lowercase `alembic upgrade head` insertion failed the intended engineering
  assertion (`1 failed in 0.06s`); exact restoration passed (`1 passed in 0.04s`).
- [x] Source `98d0fb4d`: coherent Python 3.11.16, 105 exact pins, Ruff/Bandit exit 0;
  `2383 passed, 2 deselected, 23 warnings in 54.83s`, exit 0. Prior proofs and CI remain
  scoped historical evidence. All 148 local links resolve; original archives/§7/ledger,
  locked contracts and sole baseline are preserved.
- [x] Independent correctness and tests/rules reviews cleared the case delta and actual
  mutation/full-gate evidence; root verified the final documentation-only result update.
- [ ] Root: inspect corrected actual CI before merge and deployment verification.

PR #715 is draft during a bounded review correction. Two independent refutations confirmed
that the original obsolete-stack gate did not require the seven named engineering files,
and that the SEC prose overstated circuit-breaker coverage. Earlier CI evidence is retained.

- [x] Add explicit required-file presence to the existing gate (a review-added invariant),
  keeping its obsolete-stack and frozen legacy checks unchanged.
- [x] Correct the backend brief and conflicting active CLAUDE/architecture prose: existing
  EFTS uses the shared limiter/backoff without the breaker; new bypasses remain prohibited.
- [x] Actual backend-brief deletion failed the intended required-file assertion: `1 failed in
  0.03s`; exact restoration passed (`1 passed in 0.03s`). The initial old-runtime attempt
  timed out before pytest output, restored in `finally`, and is excluded from mutation credit.
- [x] Corrected source `609c84f9`: isolated Python 3.11.16, 105 exact runtime/dev pins;
  Ruff/Bandit exit 0; `2383 passed, 2 deselected, 23 warnings in 55.03s`, exit 0.
  Documentation checks: 79 brief source paths, 31 brief links, 148 expanded local links
  with none broken. Locked contracts, sole baseline, original §7/ledger and 52 archives preserved.
  Original obsolete-stack mutation evidence still applies to its unchanged assertion branch.
- [x] Independent correctness and tests/rules reviews cleared the corrected source and actual
  mutation/full-gate evidence; root verified the final documentation-only result update.

W3-2 (#709) is deployed and its effective pins are verified. This branch is based on
[#713](https://github.com/neilmac91/EarningsNerd/pull/713) merge `99b506d7`. W3-4 deployment and
corrected green/red acceptance are verified below. Root controls publication and serialized deployment.
W3-3's observed FMP HTTP 402 / issue #710 is a founder entitlement prerequisite; it does not
block this independent engineering work. Other founder boundaries remain unchanged.

- [x] Refresh all seven engineering briefs and README status using actual source pointers.
- [x] Add one recursive obsolete-stack gate with a frozen, shrinking non-engineering allowlist.
- [x] Prove the gate with one intended Firebase assertion failure and exact restoration.
- [x] Three independent lenses cleared the W3-5 source; unchanged source bytes retain that evidence.
- [x] Prior #711 union gate at `3daf0c4c`: 105 exact runtime/dev pins, Ruff/Bandit exit 0;
  `2383 passed, 2 deselected, 72 warnings in 52.11s`.
- [x] Corrected timeout-safe #711 union at `d3986771`: 105 exact runtime/dev pins,
  Ruff/Bandit exit 0; `2383 passed, 2 deselected, 72 warnings in 48.26s`.
- [x] W3-4 verification is complete; root authorized W3-5 publication.
- [x] Root published draft #715; its prior CI evidence is retained.
- [ ] Root: inspect corrected actual CI, merge and verify W3-5 backend deployment.
  No corrected CI, merge or deployment is claimed at this source checkpoint.

Initial gate: `2355 passed, 2 deselected, 72 warnings in 52.52s`; the Firebase mutant failed its
intended assertion and restored with `1 passed in 0.03s`. Previous W3-2 union at `29f1dc61`:
105 exact pins, Ruff/Bandit clean; `2382 passed, 2 deselected, 72 warnings in 53.66s`.
These earlier gates are historical evidence. The review correction above adds required-file
presence and qualifies SEC prose; the original obsolete-stack assertion branch, all four locked
contracts and the sole baseline remain unchanged. Source checks resolve
79 paths and 31 Markdown links/anchors after the SEC source-pointer correction. The new base adds W3-4's scheduled workflow gate case.

The chief engineer reviewed #705 and the standalone writeup on 2026-09-05: sound, with eleven
discrepancies (none invalidating the handover). The ordered plan, founder prerequisites and the
per-item gates live in [`handover-wave3-2026-09.md`](handover-wave3-2026-09.md); non-Claude
operating directives live in the root `AGENTS.md`. Work items (engineering unless marked founder):

- [x] W3-0 Additional #705 tail verification: 13 task docs, 43 links valid, 52 earlier archives and original §7/ledger preserved. Final manual-reviewed `34350292` tree equals `eddcfbb7`; only the GitHub bot stopped at `c660e9a1`.
- [x] W3-0 documentation correction: #707 merged `a7ad8f85` after three reviews and link/preservation checks; #706 history, agent count, refresh cause, environment assumptions and dependency evidence corrected.
- [x] W3-1 `ops.yml` exposes revision and pregenerate flags; #708 merged `6414e5bd`, actual run 33996220468 verified revision 00270-4k6 at 100% and matched #704 image/config. Service calendar=true differs from its false default; founder approved preserving this override.
- [x] W3-2 Pin every prod guard flag explicitly in `ci.yml` (service + pregenerate job) with a bidirectional gate; pin `AI_FALLBACK_*` empty in all eval workflows with gates and pin-tool refusal; structural fail-loud gate for scheduled workflows
- [ ] W3-3 Universe refresh: supplied `Production` key reached [run 34000192154](https://github.com/neilmac91/EarningsNerd/actions/runs/34000192154), job 101397548811; FMP `/stable/sp500-constituent` returned HTTP 402 Payment Required and the script exited 2. [Issue #710](https://github.com/neilmac91/EarningsNerd/issues/710) remains open. No data changed or auto-PR step ran; Nasdaq entitlement is untested. Held for founder-provided endpoint entitlement/key before retry, without changing billing, keys or Actions settings — deadline remains 2026-10-01 cron / 2026-10-16 age gate.
- [x] W3-4 Daily production smoke: #711 deployed; #713 corrected launcher targeting; actual green 34002892976 and deliberate red 34003003306 verified with separate failure reporter and resolved issues (details below).
- [x] W3-5 Rewrite the seven engineering agent files to the real stack; gate and #715 deployment verified above
- [x] W3-6 PyJWT #716 merged with verified source/CI, unchanged locked auth contract and verified production deployment (current checkpoint above).
- [ ] W3-7 **(founder)** first strong-judge readout → engineering reports the wrong-snap rate, pauses for the arm decision → arm `AI_EVIDENCE_SNAP` + listed re-pin → **(founder)** drain
- [ ] W3-8 Golden breadth (REIT/utility/insurer/small-cap, BRK.B) with its own re-pin; then the 6-K pre-classifier + 6-K scorer + goldens
- [ ] W3-9 Historical reconciliation-flag audit/repair script (dry-run default) → **(founder)** executes
- [ ] W3-10 **(founder)** Notable job + seed + one full week → flag PR; **(founder)** Analysis Vercel value + warm-up → `vercel.json` PR
- [ ] D8 **(founder OK)** delete the two stale remote branches with no PR

## W3-2 implementation — production parity (verified #709)

Owner: AI engineer (plan_gates). Root owns GitHub publication, actual CI, merge and deployment.
Entry evidence: W3-1 run 33996220468/job 101387131600; source image #704/123f99e.
Founder correction: preserve service `CALENDAR_INDEX_FILTER_ENABLED=true` as an intentional
production override, pregenerate=false, Settings default=false. Both fallback fields must be
empty for new pins. Founder provided `FMP_API_KEY` in the GitHub `Production` environment;
bind the existing refresh job to that environment without reading or changing the secret.
Routine required CI evaluations are authorized; extra sweeps and strong-judge dispatch remain held.

- [x] Implement explicit service/job pins and three gate families: visibility/defaults/parity,
  measured fallback provenance and pin refusal, scheduled failure notification structure.
- [x] Preserve serving-revision/traffic and distinct job observation through executable offline
  ops renderer tests; extend existing eval tests without adding duplicate rules.
- [x] Wire refresh to `Production`; correct owning RUNBOOK/config/deployment/dark-surface/handover
  docs, including the founder-approved calendar exception and current entry evidence.
  Documentation source, local verification and production deployment are complete.
- [x] Commit source; run one intended mutation proof per rule, restore exactly, run focused
  workflow gates and exact-runtime full backend gate. Locked tests and sole baseline stay unchanged.
  Local gate at `6a0e7174`: 105 exact pins, Ruff/Bandit clean, 2381 passed, 2 deselected,
  72 warnings (52.19s); 11 intended mutation proofs restored. Initial cache-path collection
  failures are retained and excluded; their four corrected reruns fail the intended assertions.
- [x] Root: independent reviews, publish draft, inspect actual serialized CI evaluations, merge,
  verify deployment and effective pins. #709 merged `ff8fe0f5`; [production run 33999866705](https://github.com/neilmac91/EarningsNerd/actions/runs/33999866705),
  deploy job 101396935030, succeeded with `applied=0 skipped=34`, revision `00271-8nk` at 100%.
  Image digest `c1d3789aa8fd0186c31d56971510037ccc71b1863946bffdfba679989402a4d2`;
  public detailed health healthy (DB 6.09 ms, SEC circuit closed).
  [Ops run 34000144716](https://github.com/neilmac91/EarningsNerd/actions/runs/34000144716) verified all seven service/job pins,
  calendar service=true/job=false, both fallback fields absent with verified empty defaults,
  and matching pregenerate image `ff8fe0f`. Refresh execution belongs to W3-3; judged readout remains held.

## W3-4 implementation — production smoke (verified #711 / #713)

Owner: plan_correctness; root owns publication, merge, deployment and live dispatch coordination.
W3-2 merged `ff8fe0f5` and its deployment/effective settings are verified above; the publication
prerequisite is satisfied. The scheduled
workflow reads a cached public filing as an unauthenticated visitor and never clicks generation
or Copilot. The existing health policy accepts degraded serving status and rejects unhealthy.

- [x] Add the daily/manual smoke workflow with safely bound filing input, bounded browser install,
  retained API/browser artifacts and final create-or-comment failure issue.
- [x] Extend the existing Node lockstep gate across all workflows while preserving its original
  nonempty `ci.yml` assertion; add prod-smoke to the existing scheduled-failure tuple.
  Review found the first extension lost CI-specific presence: both independent refuters confirmed;
  correction and one missing-CI-pins proof supplement the retained wrong-new-workflow-pin proof.
- [x] Restore exact mutation bytes; run full backend and frontend gates on combined `b636780a`:
  105 exact runtime/dev pins; Ruff/Bandit exit 0; 2382 passed, 2 deselected, 72 warnings (80.15s).
  Frontend lint/TypeScript exit 0, 95 files/487 tests passed (49.74s), production build passed.
  The CI-presence mutant failed its intended assertion; exact restoration passed all three Node checks.
- [x] Three independent reviews cleared the pre-timeout-correction source; its ancestry/docs
  updates preserved the then-tested workflow and test bytes. Fresh timeout-delta correctness,
  rules and tests/gates reviews also cleared the corrected source.
- [x] Correct confirmed #711 timeout reporting: move issue creation/comment to a bounded
  dependent job with `always()` and a non-success worker result; extend the existing parametrized
  gate, prove the condition with one intended mutation, restore and run the full backend gate.
  Artifact upload in the 15-minute worker remains best effort after timeout.
  Source `481dc168`: 105 exact pins; Ruff/Bandit exit 0; full backend 2382 passed,
  2 deselected, 72 warnings (52.01s), exit 0. Focused checks 52 passed (3.74s); Node gate
  3 passed (830ms). Exactly one result-condition mutant failed the intended assertion
  (1 failed, 1 passed in 0.06s); exact restoration passed both parametrized cases (0.04s).
  Existing shutdown logging warning is retained. Frontend source/full-gate proof unchanged.
- [x] #711 merged `9ab159b7`; [production run 34001741244](https://github.com/neilmac91/EarningsNerd/actions/runs/34001741244)
  succeeded, migrations `applied=0 skipped=34`, revision `00272-klf` serving 100%.
  Independent detailed health was healthy (DB 6.87 ms, SEC circuit closed).
- [x] Corrected the existing smoke locator in [#713](https://github.com/neilmac91/EarningsNerd/pull/713),
  merged `99b506d7`, after [initial run 34002187563](https://github.com/neilmac91/EarningsNerd/actions/runs/34002187563)
  passed the summary check but matched both the callout CTA and dialog launcher. The correction
  targets the exact accessible name plus dialog semantics and preserves both visibility assertions
  and timeouts. [Issue #712](https://github.com/neilmac91/EarningsNerd/issues/712) records the genuine
  failure and was resolved with the correction and passing evidence. This semantic smoke does not
  establish deployed commit identity.
  [#713 main CI 34002890791](https://github.com/neilmac91/EarningsNerd/actions/runs/34002890791)
  passed; actual backend scope reported `No backend changes - skipping deploy.`
- [x] Corrected default [green run 34002892976](https://github.com/neilmac91/EarningsNerd/actions/runs/34002892976)
  on `/filing/3`: `1 passed (5.1s)`, artifact `9980026833`, API healthy (DB 6.18 ms).
- [x] Deliberate [red run 34003003306](https://github.com/neilmac91/EarningsNerd/actions/runs/34003003306)
  on `/filing/does-not-exist` failed summary visibility; artifact `9980065113` was retained.
  Separate reporter job `101405277325` created [issue #714](https://github.com/neilmac91/EarningsNerd/issues/714),
  which root closed after inspecting the actual issue and artifacts. Both acceptance outcomes and
  failure reporting are verified; the genuine initial failure remains part of the evidence.

## WS-10 verified engineering handover — final synchronization

Documentation-stage checkboxes below record the 2026-09-05 pre-merge source checkpoint
`177f9ff4`. [PR #705](https://github.com/neilmac91/EarningsNerd/pull/705) is authoritative for
subsequent review, CI and merge outcomes; unchecked items do not assert those later results failed.

Verified backend checkpoint: #704 (`123f99eac2b758f0dc7e2b9fcbc2a0a6bbf8146c`).
Its deployment is healthy. Original handover §7 is not complete: the first actual strong-judge
readout, dependent activation and founder production operations still need evidence.

- [x] Knowledge Curator (plan_rules): synchronize the active handover, ledger, briefs, todo,
  dark-surface and launch checklists with observed merges, gates and deployments. Attribute
  independently merged #673 separately; preserve accepted D1–D8 and every outstanding boundary.
- [x] Knowledge Curator: archive finished implementation plans and the exact earlier ledger;
  preserve existing archives and the original definition of done verbatim. Keep mixed-stage
  readout, broader coverage and founder residuals active rather than marking them completed.
- [x] Chief engineer: verify archive bytes, local links/anchors, exact commit references and
  documentation-only scope. Root, plan_correctness and plan_gates independently review the
  final documentation; serious findings require two refuters before correction. *Done in #705 (`eddcfbb7`).*
- [x] Chief engineer: inspect required CI, merge with the freshly read head, and publish a
  standalone engineering handover with the evidence and a single founder action list. Pause
  the hourly check-in when no authorized work remains in flight. *Done in #705 (`eddcfbb7`); the
  handover was reviewed 2026-09-05 and its findings are tracked in wave 3 above.*

This stage changes only task documentation. The owning evaluation RUNBOOK was corrected in
#704. No backend path, feature flag, threshold, baseline, job, secret or production data changes.

## Prospective reporting-date wiring — archived

- [x] #704 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws7-period-wiring-2026-09.md).

## Filing-scoped Copilot — archived

- [x] #703 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws6-copilot-2026-09.md).

## Filing-only input and recovery hygiene — archived

- [x] #702 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws6-hygiene-2026-09.md).

Source: `docs/ENGINEERING_AUDIT_2026-09.md` (synthesis) + `docs/audit-2026-09/` (six workstream
appendices with file:line evidence). Lens: invite-only beta, product quality wins ties.
Each phase is one or a few reviewed PRs. Engineering merges are authorized for the chief
engineer; items marked **(founder)** still require the founder.

## Wave 2 execution — 2026-09-05

Owner: chief engineer (Codex); founder has authorized engineering merges and deployments.
Accepted D1–D8 remain in force. Existing unchecked decision rows below are historical tracking,
not requests to revisit accepted decisions. Founder-only actions remain founder-only.

Verified backend/code checkpoint #704: `123f99eac2b758f0dc7e2b9fcbc2a0a6bbf8146c`.
Deployment 33988401306: applied=0 skipped=34, revision `00270-4k6` at 100%, healthy.
The [ledger](wave2-ledger-2026-09.md) records all accepted code/actual gates; last verified frontend
remains #697. #673 was externally merged and preserved, not authored or merged by this task.
#684 closed as integrated by #701; #685 merged; #686 split/closed by #694/#695.
No usable strong-judge credential or actual first readout was available, so D5 remains held.
The unavailable Claude Workflow runtime was replaced by three independent Codex review lenses
and two refuters per serious finding; absent verifier output never counted as clearance.

- [x] Chief engineer: execution plan merged #689 (`47d65a2c`), reviewed and CI green.
- [x] Backend Developer + Database Specialist: WS-7 steps 1–2 merged #690 (`99e91ba7`); graduate statement
  financials default, prepare SIC backfill instructions, implement distinctive job heartbeat
  storage with a new lock-safe migration, instrument every job, report coverage/stubs/age/last success.
- [x] Chief engineer: backend deployments through #704 serialized and independently verified; retain this prerequisite for every future backend merge.
- [ ] Founder: trigger SIC backfill; supply observed completion before declaring SIC data backfilled.
- [x] Backend Developer: WS-7 remaining code steps merged #697 (`c925cfa8`): 10-Q periods/unit assertions and
  reconciliation labels; amendments/supersession/Change Report; persisted XBRL first and missing
  balance-sheet facts; FPI + 10-Q pregeneration and universe Company seeding preparation.
- [x] AI Engineer: parity and sole honest pin merged #698 (`d696f408`), deployed with healthy detailed health.
  Statement env, JPM G5 components, production streaming and safe baseline provenance are verified.
- [x] AI Engineer: measurement code merged #700 (`80314db6`): WARN figure-trace dimension,
  persisted audit counters and bounded weekly strong-judge workflow/readout handoff; deployed healthy.
- [ ] AI Engineer / founder credential boundary: obtain the first actual weekly strong-judge readout.
  An unavailable artifact and routine judge-off regression runs do not satisfy this prerequisite.
- [x] AI Engineer: resilience #701 integrated #684, optional real fallback, bounded retries, actual usage/model telemetry and missing-grounding protection; full backend and complete actual eval gates passed.
- [x] AI Engineer: #702 filing-only AST/context hygiene; #703 scoped/native-currency Copilot with six verified accessions/five issuers and three actual draws each. Latest #704 18/18 accepted; uncited-answer coverage remains advisory.
- [ ] Chief engineer: arm AI_EVIDENCE_SNAP in ci.yml only after first judged readout; founder triggers drain.
- [x] Frontend Developer: sitemap freshness + /terms + SEO correction merged #693 (`157e6a39`).
- [x] Frontend Developer: locate boundary and regression/mutation proof merged #691 (`a2c7fa70`).
- [x] Frontend Developer: #686 split/closed through #694 (`6e169de8`) and #695 (`919aa862`);
  full lint/typecheck/vitest/build and Playwright with no backend for each candidate.
- [x] Security/Backend Developer: #685 compatibility/backend gate and verified deployment (`5cb23b8a`).
- [x] Backend + Frontend Developers: WS-9 preparation merged #692 (`60d8015e`); activation remains held;
  Analysis requires confirmed Vercel value + warmed companyfacts; Notable requires founder-created
  job, seed and a week of review before repository flag flip. Calendar and Insiders stay off.
- [x] Owning PRs corrected migration/provider/report/eval/config docs and script placement; FPI plans archived with residuals. Final active-task synchronization and its review/CI/merge are tracked at the top.
- [ ] Founder: pregeneration off-peak only after WS-7 prerequisites; console/secrets/licence actions
  remain as listed in handover §6, with exact instructions in the relevant PR.
- [ ] Chief engineer: finish final docs review/CI/merge and standalone handover, then pause the hourly quiet check-in when no authorized work remains in flight. Report original §7 as incomplete; do not wait for founder-held operations to claim engineering handover.

Every implementation PR is draft immediately, uses a worktree under `.claude/worktrees/`,
and includes exact gate tails and mutation proofs. Locked contracts, migration allow-lists,
and AI baseline protections remain unchanged unless explicitly permitted by the mandate.

## Resilience and complete-report gate — archived

- [x] #701 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws6-resilience-2026-09.md).

## Phase 0 — this PR: make releases safe, land the audit

- [x] Explicit ruff rule set (`select = ["E4","E7","E9","F"]`) + pinned `requirements-dev.txt`; CI and the local gate install from it
- [x] `timeout-minutes: 30` on `deploy-backend`
- [x] Migration step: `lock_timeout=10s` / `statement_timeout=120s`, 5 bounded retries, `pg_stat_activity` dump on final failure
- [x] Gate test `backend/tests/unit/test_migration_lock_safety.py` (workflow knobs, toolchain pin, explicit select, filename convention, frozen shrink-only allow-list of 17 legacy unguarded ALTERs)
- [x] Lessons: `ops-migrations-need-lock-timeout.md`, `ops-pin-ci-toolchain.md` (+ index)
- [x] Doc sync: `DEPLOYMENT.md` (7 jobs, `/health/detailed`, `pdx1`, migrations automatic, only backend pushes deploy), `CLAUDE.md` (7 jobs, rule-3 lock note, gate install line)
- [x] `frontend/package.json`: `"postcss": "$postcss"` override (unblocks Dependabot; lockfile-neutral, `npm ci` verified)
- [x] Archive finished SEO plan → `tasks/archive/seo-audit-quick-wins-todo.md`
- [x] **(founder)** Pre-flight: run the `pg_stat_activity` query in `ENGINEERING_AUDIT_2026-09.md` §2; terminate any idle-in-transaction session — *skipped by decision 2026-09-04 (no Cloud SQL access from the merging session; the new `lock_timeout` bounded the worst case to a failed, diagnosable job). The migration step applied all 32 files on the first attempt, so no blocker was present.*
- [x] **(founder)** Merge this PR → watch `deploy-backend` complete → verify API `robots.txt` is `Disallow: /`, `/health/detailed` healthy, 31-burst to `/api/companies/AAPL/insiders` → 429 — *done 2026-09-04 22:36–22:42Z: merge `df9c893`, CI run 1840 success; robots `Disallow: /` live after 319 s; `/health/detailed` healthy (db 7.8 ms, circuit closed); burst → 30×200 then 429 with `Retry-After: 36`.*
- [ ] **(founder)** Check Cloud Run 5xx/latency + Sentry for 2026-07-16 18:40Z → 07-17 00:38Z; if degraded, add a lesson

## Phase 1 — Priority 1: reliability floor (≈4 engineer-days + founder console time)

- [x] **(founder decision)** Migration design: DO-block guard only (status quo, gated) vs `schema_migrations` ledger (recommended; ADR supersedes rule-3 wording) — *decided 2026-09-04: ledger (PR #658, ADR-0007)*
- [x] Implement the chosen migration design — *PR #658 merged 2026-09-05 (`c6eaddf`); its first deploy failed because prod already had a foreign `schema_migrations` table, fixed by hotfix PR #678 (`f8e7728`, ledger renamed `migration_ledger`, CI decoy gate, ADR-0007 amendment, lesson `ops-deploy-owned-state-needs-a-distinctive-name.md`); seed deploy verified `applied=32 skipped=0`, health green*; Cloud SQL flag `idle_in_transaction_session_timeout` as DB-side backstop **(founder: flag)**; **(founder)** inspect and drop the legacy prod `schema_migrations` table
- [x] Extend the lock gate: plain `CREATE INDEX IF NOT EXISTS` on pre-existing tables (second frozen legacy list; `CONCURRENTLY` for new files) — *PR #656 merged 2026-09-05 (`f340bb0`), deploy green*
- [x] Ledger-skip the re-run `UPDATE` in `20260706_demote_null_fiscal_period_duplicates.sql` — *ledger live since #678; the file ran once at seed and is now skipped*
- [ ] Alerting minimum: uptime check on `/health/detailed`; Cloud Run job-failure alert; log-based alerts (SEC circuit open, generation failures); Actions failure notifications for `refresh-index-membership` / `data-quality-weekly` **(founder: GCP console)**
- [x] Scheduled workflow running `tests/e2e/prod-smoke.spec.ts` against production (`SMOKE_BASE_URL`), daily — #711 plus #713 locator correction; green 34002892976 and deliberate red 34003003306 accepted, failure reporting and issue closure verified (W3-4 evidence above).
- [x] Frontend observability: `GlobalErrorBoundary` imports the Sentry SDK; delete the dead frontend `signup_completed` helper; pre-consent PostHog proposal — *PR #660 merged 2026-09-05 (`ffb0b61`)*; Sentry source-map env in Vercel **(founder)**
- [x] Dependabot triage: merge #635 #636 #639 #640 #641 #642 — *all merged 2026-09-04, deploys green*
- [x] Dependabot closes: #629 and #570 closed 2026-09-04; `typescript` major-ignore landed in #674; #662–#670 closed as superseded by #674 and #672 closed as superseded by #679 + #680; #659 closed so Dependabot re-creates the remaining 15 minors against Next 16.3.4 / Node 22 — *2026-09-05*; the fresh #686 group appeared and was resolved by #694/#695
- [x] #684 OpenAI 3.7 integrated and closed through #701 resilience/native SDK/full actual eval gates. #685/#683 merged; #686 superseded by #694/#695.
- [x] Split #672: non-edgartools bumps (pandas 3.0.5, fastapi, stripe, posthog, …) — *PR #679 merged 2026-09-05 (`fbbccc5`)*; edgartools 5.40.1→5.55.0 alone through the eval gate — *PR #680 merged (`083247d`, regression gate PASS, 0 warnings)*; #672 closed
- [x] Next.js 16.3.4 (+ transitive security patches, `npm audit --omit=dev` 10 → 0) — *PR #674 merged 2026-09-05 (`2f2e48d`); Vercel production deployment completed; `::highlight` lives in a constructed stylesheet; `next build` typechecks `tsconfig.ci.json`*
- [x] Dependency-audit gates in CI (advisory): `pip-audit -r backend/requirements.txt`, `npm audit --omit=dev --audit-level=high` — *PR #674*; cryptography 50 shipped #685. Audit posture remains advisory. W3-6 local runtime-lock `pip-audit` reports no known vulnerabilities after removing the jose/ecdsa chain; this does not claim every dev-tool, image or frontend dependency is clean or authorize a blocking-policy transition.
- [ ] Backups: PITR + deletion protection on `earningsnerd-db`; monthly export to lifecycle-managed GCS; one-page rehearsed restore runbook **(founder: console)**
- [x] Universe refresh: FMP stable API first, loud partial-list abort, 100-day age gate — *PR #655 merged 2026-09-05 (`49dd399`), deploy green*; founder supplied `FMP_API_KEY` in GitHub `Production`; W3-2 binding/deployment verified. W3-3 run 34000192154 reached FMP but returned HTTP 402; issue #710 remains open for the founder entitlement/key prerequisite. Successful refresh and reviewed PR remain pending
- [x] Pricing page SSR (`useSearchParams` → Suspense-scoped child) + Product/Offer JSON-LD; contact meta-description entity; noindex auth pages — *PR #660 merged 2026-09-05*
- [x] Node 20 → 22.23.2 (`.nvmrc`, `engines`, CI ×3, lockstep gate `nodeVersionLockstep.spec.ts`) — *PR #674*; **(founder)** set the Vercel project Node.js Version to 22 so the dashboard matches the `engines.node` override that already governs the build
- [x] Quick wins: `ops.yml` push trigger removed + `cloud-sql-proxy` sha256 pinned (*#656*); `hot_filings.py` and the trending refresh route deleted outright (*#657*, so the admin-token compare and rate limit are moot)
- [x] Drop `"log"` from client Sentry console levels — *PR #660 merged 2026-09-05*
- [x] Rule-8 gate: env-access allow-list test — *PR #661 merged 2026-09-05 (`41abb26`), deploy green*

## Phase 2 — Priority 2: summary fidelity measurement, then arm the guards (≈7 engineer-days)

- [x] Add `mean_untraceable_dollar_figures` as a measured absolute WARN dimension — #700. The parity pin has no reference for it; no invented zero baseline or new hard floor.
- [x] #700 implemented the fixed 8 × 3 weekly strong-judge workflow and report receiver; judge remains off in routine PR CI.
- [ ] First actual strong-judge readout: founder credential/execution required; workflow also sends the report email.
- [x] Roll the five audit counters into the weekly data-quality report from persisted `raw_summary` audits — #700, with separate valid/missing/malformed denominators.
- [ ] Arm `AI_EVIDENCE_SNAP` only after the first judged readout (D5 accepted); figure-trace and forward-quote remain advisory. Strong-judge credential/readout currently unavailable
- [x] #701 retry/fallback: delete the dead Gemini chain in `openai_service.py`; bounded backoff on the primary; env-configured `AI_FALLBACK_BASE_URL`/`AI_FALLBACK_MODEL`; fix the retry unit test to use real names
- [x] #701 per-summary telemetry: log `usage` and `response.model`; surface on `/metrics`
- [x] Eval ↔ prod parity, restored JPM G5 components, actual production streaming, routine two-run gate and sole three-run baseline pin — #698.
- [x] #703 Copilot on verified live-source FPI filings: currency directive (never bare `$` for CNY/TWD/EUR); scope `_query_fact` to the filing being viewed (period from the filing, not `is_latest` company-wide); six verified accessions/five issuers, three actual draws each; older unverified entries remain pending
- [ ] Golden-set breadth: 6-K entries, one REIT/utility/insurer, small caps **(D4 spend approved; execution pending)**
- [x] Reading surface on the filing page: distinct risk headings, mobile section jump-nav, skip-to-content + live region, company-name casing — *PRs #671 + #676 merged 2026-09-05, casing verified live*
- [x] #702 section-recovery grounding: build context from labelled excerpt sections (~30k cap) instead of raw HTML with a 6,000-char cap
- [x] #702 deleted the latent `previous_filings` prompt path + AST pin (rule 2 hygiene)
- [ ] **D4 spend approved; founder execution pending:** drain cached v1 summaries → v2 via admin `refresh-stale` (~$0.05/filing), after D5's judged-readout and evidence-snap prerequisites
- [x] Owning #698–#704 PRs corrected RUNBOOK status, quality-plan headers, façade/provider and DATA_COMPLIANCE processor descriptions; historical quality-plan bodies preserved.

## Phase 3 — Priority 3: coverage and data integrity for the beta universe (≈8 engineer-days)

- [ ] **D4 spend approved; founder execution pending (~$25–50 one-time):** universe-wide pregeneration, latest 10-K + 10-Q for the 515-name universe in batches via `precompute`; weekly 10-Q and Company seed tooling merged #697; founder seed/SIC enrichment and off-peak generation still pending (237 missing rows was the audit snapshot)
- [x] Weekly coverage/stub/universe-age/job-heartbeat report implementation — #690. Live report/backfill evidence remains required.
- [ ] **(founder)** Execute SIC backfill and retain completion/report evidence. Code default True shipped #690; pregenerate FPI env shipped #697; neither proves data was backfilled.
- [x] Amendments: list/ingest 10-K/A and 10-Q/A; supersession and Change Report — #697; existing rows link on refresh/backfill.
- [x] Fiscal periods, unit/decimals assertions and reconciliation UI/exports — #697.
- [x] #704 wires actual ORM reporting date into prospective reconciliation; existing-identity skips/cross-check policy preserved.
- [ ] Engineering: design an explicit historical flag audit/repair capability before founder production repair. Ordinary backfill or freshness `--force` does not re-reconcile existing identities.
- [x] Rule-5 gate: `_fetch_companyfacts_sync` through the SEC limiter via the app-loop bridge (`app/services/event_loop.py`); `sec.gov` allow-list test — *PRs #661 + #675 merged 2026-09-05*
- [x] Rule-10 gate: `app/utils/sec_urls.py::build_sec_archive_url` + listener tests — *PR #661 merged 2026-09-05*
- [x] Sitemap: hourly ISR with uncached upstream fetch, regression tests, `/terms` and SEO doc — #693.
- [ ] 6-K classifier (earnings vs governance vs press release): the 6-K summary path exists behind `ENABLE_FPI_FILINGS` (`prompts/6k-*.md`, `summary_pipeline.py:358-489`) but every 6-K gets one prompt; add 6-K golden-set entries
- [x] Dead-integration teardown: trending, hot_filings, fmp, finnhub, stocktwits and their consumers removed — *PR #657 merged 2026-09-05 (`9ff8da6`), deploy green, old routes 404*
- [ ] Clear the four standing weekly-report anomalies: `backfill-filing-history` for C, MS, WFC, GS; grant deployer SA access to `INTERNAL_JOB_TOKEN`
- [x] Liabilities/cash fallback and persisted accession-specific XBRL first — #697.
- [ ] **D3 accepted; execution pending:** founder creates/seeds the Notable job and reviews one week of output before `NOTABLE_FILINGS_ENABLED` activation per `DEPLOYMENT.md`; homepage findings archive completed #692
- [x] FPI roadmap archive and status block — #692. Residual 6-K classifier and founder backfill remain open.

## Accepted policies — execution and verification pending

- [x] Migration design (guard-only vs ledger) — *ledger, 2026-09-04*
- [ ] **D5 accepted:** obtain the first judged readout, then arm `AI_EVIDENCE_SNAP`; figure-trace and forward-quote remain advisory. The strong-judge credential/readout prerequisite is outstanding.
- [ ] **Execution pending; D4 spend approved:** universe pregeneration, v1→v2 drain and golden-set runs; FMP secret remains founder-owned
- [ ] **D3 accepted:** confirm the Analysis production flag and warm companyfacts before activation; complete Notable job/seed/one-week review prerequisites. Calendar remains off pending the licence decision; Insiders remains off.

## Remaining founder decisions and console actions

- [ ] Alpha Vantage: licence or EDGAR-only
- [ ] Legal: Terms §7e counsel pass; processor DPAs; legal entity / governing law
- [ ] `WAITLIST_MODE` intent; LAUNCH_CHECKLIST founder-only actions (GSC, Bing, apex 307→308, Vercel plan, `NEXT_PUBLIC_EXAMPLE_FILING_ID`)
- [ ] Pro trial timing; delete retired reverse-trial code?
- [ ] `USE_STRUCTURED_OUTPUT`: bake-off or delete
- [ ] GCP console: PITR + deletion protection; uptime/alert policies; Turnstile keys; confirm effective `REGISTRATION_MODE` in the console (`ops.yml describe-service` withholds its value); inspect other permitted flags

## Deferred (tracked in appendix 06, not scheduled)

SEO phases 2–3; dashboard "later" tier (8-K rows, weekly brief, sparklines, 13F); competitive roadmap
A4/A7/A8; cold-path Phase C; MFA/TOTP; retention purge jobs (policy promise — schedule before public
launch); Turnstile fail-closed; T5 depth ledger; cheaper-model routing flags; waitlist/contact route tests;
`SUMMARY_SELF_VERIFY`; prompt-prefix caching; off-peak cron windows.

## Parity and the sole measured baseline — archived

- [x] #698 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws6-parity-2026-09.md).

## WS-7 implementation — archived

Steps 1–6 are merged (#690/#697). [Completed steps 3–6 and proof](archive/ws7-completeness-2026-09.md).
Founder execution and live data evidence remain unchecked above and in the ledger; #697 deployment is verified.

## WS-10 — configuration and script placement hygiene

- [x] Implementation and current-main local gates complete in PR #696; [archived proof](archive/ws10-hygiene-2026-09.md).
- [x] WS-7 default/docs integrated; 1910-test gate, independent review and CI passed; #696 merged (`0e0e7762`), deployment verified.

## Measurement implementation — archived

- [x] #700 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws6-measurement-implementation-2026-09.md).
