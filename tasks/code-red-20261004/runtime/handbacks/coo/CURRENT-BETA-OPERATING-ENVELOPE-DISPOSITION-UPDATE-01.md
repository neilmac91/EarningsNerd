# R3 current-beta operating-envelope disposition — update 01 (COO worker `coo-envelope-disposition-update-01`)

**Disposition after this update: HOLD stands — exact missing evidence/decision, re-stated per item.** The revision-1
disposition (`CURRENT-BETA-OPERATING-ENVELOPE-DISPOSITION.md`, SHA-256 `d30bdd50…`, never edited) reached HOLD on
eight C1 items. Since then the named owners have closed items 4 and 8 and the dependency of item 6 (record 06), the
2026-10-05 Monday capacity readout ran as authorised by record 02 D4 (receipt note), and the CTO delivered handback
revision 4 with the item-7 re-determination (`CORRECTION-03.md`). After this update: **2 items closed (4, 8), 1 item
dependency-closed (6), 5 items open (1, 2, 3, 5, 7), of which 2 carry the new sub-dependency B62 (1, 5).** The three
load-bearing quantities for a supported useful-work envelope — B32, B39 and B56 — remain `unknown` (null) by the CTO's
own classification in revision 4, the founder's D3 decision (item 3) is open, and the readout route itself now has an
unresolved prerequisite (B62). No supported envelope can be stated. This is an administrative record for the
accountable COO/CEO owners; it admits no capacity, sets no threshold, budget or participant count, and authorises no
invitation, flag, pricing, registration, job, probe, load or E09 code. A worker recommendation cannot authorise
production entry.

## 1. Identity, inputs, observation date, authority and limits

| Item | Value |
|---|---|
| Worker role label | `coo-envelope-disposition-update-01` (COO-owned wave R3, lane: beta operations; provisional label pre-registered in closure 145, listed in closure 146) |
| Runtime | Claude Code subagent dispatched by the chief/CEO (session `01GWYV7WXWstgVGQG43YcSM8`); requested model inherited `claude-fable-5-1`. **Limitation:** this worker cannot observe its served model or its own runtime/session id; the chief resolves the provisional label. |
| Dispatch manifest | `dispatch/COO-ENVELOPE-DISPOSITION-02.json`, SHA-256 `9c11bd60c4a65806bd9860a67825688436fdfee5c0175e98a9bf5b4484bacf09` (6,358 bytes); recorded 2026-10-05T08:43:37.775546+00:00; one active writer for this output: true |
| Observation date (this update) | inputs verified 2026-10-05T08:44:53Z; written 2026-10-05T08:47Z–08:50Z (UTC) |
| Repository state relied on | branch `claude/vigilant-goodall-633yx3` (manifest: main `0b8d39eb` plus the runtime records); the only passive repository reads beyond the inputs were `git branch --show-current`, `git status --short`, and a citation check of the revision-4 B32 anchors (`.github/workflows/ops.yml:477`–483, `ops/capacity/readout.py:38`, `:128`) — see §1.2 |
| Authority relied on | Record 02 **D4** (COO/CEO decision authorising the one read-only Monday readout; window widened) and **D9** (refuter results handed to the COO; closure exercised by the CEO in record 06). Record 06 **"C1 items — closures recorded by their named owner"** (items 4, 6-dependency and 8 closed; B37 closed by D8). This update re-opens no closure and closes no item its named owner did not close; COO qualifications are marked as such. |
| Available authority of this worker | Administrative/management only. Excluded from source A/B authorship, reconciliation, semantic financial review and blind judging. Zero provider calls; zero reservation; no git write, network, cloud, GitHub, gcloud/gh/curl, test, server, code, measurement, probe or production action. Write authority: this one file, exclusive create. |
| Not read, by rule | source packets, candidate outputs, judge material, customer/participant data, credentials, anything under `tasks/readiness-2026-09-21/acceptance/`, the readout's `cloud.json`/`database.jsonl` (outside this manifest; cited through the receipt note and revision 4), `control/LEDGER-ACCESS.md`, `control/PRODUCTION-CONFIG-OBSERVATION-20261004.md` (cited through revision 4 and record 02). |

### 1.1 Inputs read and verified (SHA-256 and byte length, all 13 match the manifest)

| Label | Path | SHA-256 | Bytes |
|---|---|---|---:|
| CTO handback revision 4 (Markdown) | `handbacks/cto/envelope/CURRENT-BETA-OPERATING-ENVELOPE-HANDBACK.md` | `94c155c7c517b36b73d751a1935fa78060747907dd810fcbf84685ac19ee3d41` | 72085 |
| CTO handback revision 4 (bounds JSON, 62 bounds) | `handbacks/cto/envelope/CURRENT-BETA-OPERATING-ENVELOPE-BOUNDS.json` | `d675516eea6b401780e6dbe29061388573b5c736f4447b979bb86536a2577505` | 68998 |
| Correction 03 (rev 3 → rev 4) | `handbacks/cto/envelope/CORRECTION-03.md` | `33ce976660442b467d15c020762e7c3ca2afc1aa2d58f5b5abe0cb2e1b2e9b78` | 16882 |
| COO disposition revision 1 (HOLD, 8 items) — never edited | `handbacks/coo/CURRENT-BETA-OPERATING-ENVELOPE-DISPOSITION.md` | `d30bdd50125ae304ad5c4fd1c6559326d3767c0f17c1ca7ec41d895ab6fc13be` | 40291 |
| Capacity-readout receipt note (chief → COO, 2026-10-05) | `handbacks/coo/CAPACITY-READOUT-RECEIPT-20261005.md` | `eea93bba6b1285354bd921e472ad18e8ffb83edaf60ce13cfbc757174ec9c297` | 7453 |
| Decision record 02 (D1–D9, Appendices A/B) | `control/DECISIONS-02.md` | `4d93171f68c7491afd70fcd54b19a355093c5f2a14b437d02c4fd13d3f4f508b` | 21885 |
| Decision record 03 | `control/DECISIONS-03.md` | `56bfb21b3ff5b7dccfafd53a7355cb70795a8962f1454aab951223c70efccd26` | 8578 |
| Decision record 04 | `control/DECISIONS-04.md` | `9d66fbd093b5ff9cd022c98058dca0fcdfd5a2dbb126e8f4c8c76bfa00b116cd` | 7812 |
| Decision record 05 | `control/DECISIONS-05.md` | `d3723842b2140cdc81976edfefecfe94a307d613ce5410bb17571c9862799d50` | 10357 |
| Decision record 06 (C1 closures; readout plan; founder update) | `control/DECISIONS-06.md` | `13f852f0b4bb8f69e37d4e5477e30e2b8d3363efb2ecc3e53d3a38213c56a8d3` | 14904 |
| CTO dispatch manifest 02 | `dispatch/CTO-ENVELOPE-HANDBACK-02.json` | `260a706a37cd448b075cedbb96246101a6f41895ba16c70195e0463ed4f30fd5` | 8584 |
| Exclusion closure 146 | `control/source-context-exclusion-146.json` | `804426be7030c64a52e3de04e82d489d526b81a96cb4cbbbbef6e3567463ebd3` | 18618 |
| COO first deliverable (G1–G5; C1 five components) | `…/scratchpad/handover/officers/coo/references/FIRST-DELIVERABLE.md` | `c82773953be1e85daa87525003d1ade26db4e8f8e9df428f97fff80d10ee3f7f` | 15184 |

Repository paths are relative to `tasks/code-red-20261004/runtime/`; the `…/scratchpad` prefix is
`/tmp/claude-0/-home-user-EarningsNerd/27aa9761-b14a-5cab-9ee6-5f8ec27f49f3/scratchpad`. The revision-4 JSON was
checked for agreement with the Markdown on the ids, classifications and null values of B32, B37, B39, B46, B51, B52,
B56, B58 and B62 and on the `determination` block; it agrees.

### 1.2 Evidence-quality notes carried from revision 1 §1.2 — state after revision 4

| Revision-1 finding | State now | Evidence |
|---|---|---|
| Unresolved generator placeholders in B27, B32, B40 (adverse provenance finding) | **Resolved for B32** — revision 4 cites `.github/workflows/ops.yml:477`–483 (the `capacity-readout` step, read-only `PGOPTIONS`), `ops/capacity/readout.py:38` (window cap) and `:128` (pool-timeout signature); checked passively at this checkout, each line is what the row says it is. Revision 4 states every retained anchor is unchanged and every new anchor was read at the checkout (rev 4 §0). | rev 4 §0, B32; Correction 03 intro |
| No isolated adversarial lens on the handback | **Partly changed** — the revision-3 derived rows were refuted by two isolated read-only refuters (record 02 D9, Appendices A/B; item 8 closed by the CEO, record 06). Revision 4 was authored in an isolated context, but **no adversarial lens ran on revision 4 itself** (rev 4 §0). Its new and changed content (B36 two-bucket model, B51, B52, B59–B62, the rewritten §5 and hazard ranking) is therefore author judgement, unrefuted: recorded here, not relied on for any admission, neither strengthened nor weakened. | rev 4 §0; record 02 D9; record 06 item 8 |
| Partial re-read of `docs/DEPLOYMENT.md` schedules (B23 weaker) | **Partly resolved** — backfill-facts confirmed and observed (record 02 D4; rev 4 B23); notable-filings remains reviewer-reported, not read by the chief (rev 4 B23). | rev 4 B23, §6 |
| Docs-vs-config inconsistency (B33) | **Unchanged** — the founder-held D3 patch would fix the documented threshold; not applied. Not a capacity item. | rev 4 B33; record 02 D3 execution note |
| New (receipt) | The receipt's two files were **not** copied to a private store (classifier denial, not pursued); the retained store is the GitHub Actions artifact, which expires 2026-10-19T08:13:07Z. The repository keeps the note and hashes (record 02 D5). The filing-scan execution listing is `partial`. Recorded as retention and completeness limits; no action is dispatched here. | receipt §Run identity, §What the receipt contains |

## 2. Per-item state of the eight C1 items (revision 1 §4)

States: **closed** · **dependency closed** · **open** · **open-with-new-sub-dependency**. "Moved by" names the evidence
identity that changed the item since revision 1 (record and section; bound id in handback revision 4; receipt note
section). Where the named owner recorded a closure, this update records it as the owner's act and adds only a COO
qualification. Nothing in this table is a capacity number, threshold, budget or participant count; nothing is
dispatched by it.

| # | Item (rev 1 §4) | State after this update | Moved by (evidence identity) | Smallest permitted next handback (if open) | Existing owner |
|---|---|---|---|---|---|
| 1 | **B32** — DB operating reserve and wait/cleanup allowance under concurrent generation | **open-with-new-sub-dependency (B62)** | Record 02 D4 (authorised; window widened); record 06 C1 table item 1 ("open until the receipt exists"); **receipt note** §Run identity (Ops run 37282199614, conclusion success, artifact `capacity-readout-37282199614`), §"What the receipt does NOT contain" (Monitoring `num_backends`/`request_count`/`request_latencies` and Logging all HTTP 403 → no in-window DB sample), §"Disposition inputs for the COO (item 1)"; **rev 4 B32** (`unknown`, value null), **B59** (channel availability), **B62** (new prerequisite), B60/B61 (job ledger; point-in-time snapshot outside the window) | **(a)** The B62 result: one dated read-only statement of whether the Ops Workload Identity Federation identity holds Monitoring/Logging read access and the cause of the new or intermittent 403 — or a CTO-named alternative retained-sample route. No grant is proposed here; any grant is the founder's decision. **(b)** Then, on a recorded COO/CEO decision, one dated read-only Ops `capacity-readout` receipt over a window that contains actual concurrent generation, with the Monitoring/Logging channels returning samples: backend counts by state, the job ledger, the pool-timeout log signature result and `/metrics.provider_admission` peaks (B56) for the same window. No new load, probe, job or flag. | **COO/CEO** decision (re-run); **CTO** executes; B62: **CTO/CEO** (read-only IAM check), **founder** (any grant) |
| 2 | **B39** — realised aggregate SEC rate / `rate_limit_hits` across every instance and running job; **B37** — egress identity | **open (B39 part); B37 part closed by record 02 D8** | Record 02 **D8** (SEC's cap is per user regardless of the number of machines; egress moot for compliance); record 06 C1 table item 2; **rev 4 B37** (`unknown` → `observed`: dynamic egress; compliance consequence none), **B35** (unit corrected to per user), **B39** (`unknown`, value null; counter semantics verified at the checkout per records 03/05: only recognised rate-limit errors on the two backoff paths move the counter; `execute()` paths and edgartools traffic never do; an SEC 403 is re-raised uncounted), **B38** (call-site enumeration); receipt note (`rate_limit_hits` never in the readout's scope) | One dated fleet SEC observation receipt: per-process `/metrics.sec_rate_limiter` (`total_requests`, `rate_limit_hits`) on every instance plus job logs in one window, read-only and CEO-approved, interpreted under the records 03/05 semantics (a flat counter closes nothing; a rise is a conservative stop signal); plus a Cloud Logging search for SEC 403/429 once B62 is resolved. No SEC call added. The egress-identity statement revision 1 asked for is no longer required (D8). | **CTO** via CEO-approved read-only observation |
| 3 | **Founder's retained E09 Slice B policy numbers** (aggregate SEC rate across service and jobs, burst/headroom, wait/error tolerance) | **open** | Record 02 **D3** and execution note (per-process SEC budget patch prepared and gated locally; `git commit` denied by the platform classifier; patch handed to the founder); record 03 §D3/D6 (revised patch SHA-256 `21322a05…` supersedes `e1c097f9…`); records 04, 05 and 06 owners tables ("Patch — Founder — open"); **rev 4 §5** "Exactly what remains missing" row 1 and JSON `determination.missing_decision` (the D3 decision *is* the Slice B allocation); **rev 4 B36** (two-bucket model; the patch recorded as NOT applied) | The founder's recorded decision on the prepared patch — apply as prepared, change the numbers, or drop it (a recorded deferral is also a decision for this item) — routed by the **CEO** as a concrete bounded choice with the revision-4 B36 model and the readout receipt attached. A reservation precedes marking any carrying PR ready (CEO's act, record 06 owners table). Not a code change by this update; not E09 implementation; this update proposes and evaluates no numbers. | **Founder** (retained decision); **CEO** routes |
| 4 | **B46** — provider (DeepSeek) account quota / rate limits | **closed** (by the named owner) | Record 02 **D7** (published figures recorded with source identity and read date); record 06 C1 table item 4 ("**Closed** by record 02 D7"); **rev 4 B46** (`unknown` → `observed`: published, dated), §5 gap (d) closed | None. | **CTO/CEO** |
| 5 | **Evidenced stop thresholds for the beta** (B57 signals exist; thresholds not evidenced) | **open-with-new-sub-dependency (B62)** | Record 02 **D6** (provisional conditions) as corrected by record 03 §D3/D6 (condition 1); record 06 C1 table item 5 ("Open; provisional conditions stand until items 1 and 2 supply baselines"); **receipt note** §"Disposition inputs for the COO" ("New sub-dependency for items 1 and 5"); **rev 4 B57** (`provisional_stop_conditions` recorded; log routes HTTP 403 for the Ops identity; readout lacks `rate_limit_hits`), §4 envelope item 4, hazard ranking entry "observation blindness" | Unchanged from revision 1: a dated threshold record with provenance for each named signal (`database.checked_out`, pool-timeout signature, `sec_rate_limiter.rate_limit_hits`, `provider_admission.rejected`, SEC breaker state, `/health/detailed` latency), after items 1 and 2 supply baselines — and now after B62 for the log-based signals. Not set here. | **CTO** supplies baselines from items 1 and 2; **COO/CEO** record threshold policy |
| 6 | **B58** — provider operating-spend field (HOLD in revision 1) | **dependency closed** (by the named owner); field value not set | Record 02 **D1** (successor ledger designated on Astra's byte-identity confirmation; chief sole writer); record 03 §D1 (event 1, wording correction); record 06 §"Ledger event 2" (shared ceiling raised by founder authorisation; balances, holds and reservations unchanged) and C1 table item 6 ("**Dependency closed** … The field's value is not set tonight: it attaches to a C1 admission decision, which does not exist"); **rev 4 B58** (`observed`: provenance on the successor ledger; paid dispatch HELD) | None for the dependency. The field's value attaches to a C1 admission decision, which does not exist and is not proposed. | **CEO** (sole ledger/reservation writer); CFO policy |
| 7 | **C5 specific determination** | **open** (re-determination delivered; closing condition unmet) | Record 06 C1 table item 7 ("re-determination belongs to handback revision 4"); **rev 4 §5** ("undetermined, with no E09 code subset demonstrated necessary … The verdict is unchanged; the evidence under it has changed"); JSON `determination` (`existing_controls_suffice` = `undetermined`; `necessary_e09_subset` = null; `missing_decision` = the founder's D3 decision; `missing_observations` = B32 via B62, B39, B56; `closed_since_revision_3`); Correction 03 (determination block changed for the first time since revision 1); rev 4 §7 | One dated CTO determination stating either "existing controls demonstrably suffice for the current beta" with the evidence ids, or the named necessary E09 subset with its retained implementation decision still pending — after item 3 (founder's D3 decision), item 1 (B62 then B32) and item 2 (B39). Item 4 no longer gates it (closed). The E09 implementation hold, including inactive lease/schema/runtime code, stays unchanged until then. | **CTO** (determination); **founder** retains Slice A/Slice B; **CEO** coordinates |
| 8 | **Independent read-only review of the handback's `assumed`/derived rows and §5 judgements** | **closed** (by the named owner) | Record 02 **D9** and closure ("no arithmetic error; six qualifications accepted; one external input verified; one assumption resolved by observation"), Appendices A and B (isolated read-only refuters, closure 139); record 06 C1 table item 8 ("**Closed** … The CEO exercises the closure as the item's named owner; the COO carries the six qualifications into the disposition update") | None. The six qualifications are carried in §2.1. | **CEO** |

### 2.0 COO qualifications per item (added where the evidence warrants; none re-opens a closure)

| # | COO qualification |
|---|---|
| 1 | Revision 1's smallest permitted handback ("one dated read-only readout receipt") **was delivered exactly as authorised** — one dispatch, no retry, no widening, pre-checks recorded (receipt header). Its DB-reserve content is empty because of the 403s, so B32 does not move; its job-ledger content is new C1 evidence (the first retained window in which job business phases overlap each other and the service, with near-empty work — receipt §"Concurrency observed"; rev 4 B22/B60): evidence that Monday overlap happens, not of load, and not convertible into a reserve or a participant count. The revision-1 §1.2 anchor-provenance finding on B32 is resolved by revision 4 (§1.2 above). The receipt also confirms what revision 1 anticipated: a job-overlap window evidences job-side concurrency, not cohort-shaped useful demand, which cannot exist before entry — the COO/CEO still have to decide what a future receipt is allowed to close. |
| 2 | D8 closes B37 **for compliance only**: how SEC attributes traffic stays external and unknown (rev 4 B35/B37), and resolving it relaxes nothing (record 02 Appendix B). Under revision 4's B39, the Cloud Logging search for SEC 403/429 inherits B62; the per-process `/metrics` half of the route does not. The receipt note's statement that `rate_limit_hits` was never in the readout's scope means the authorised readout could not have closed B39 even with Monitoring access. |
| 3 | The item has moved from "numbers needed" to "decision on a prepared artefact needed": the concrete bounded choice revision 1 asked the CEO to route now exists (record 02 D3; record 03). Revision 4's JSON `what_each_missing_item_resolves` records that "drop" leaves the configured ceiling as the recorded policy. This update does not evaluate the patch, propose numbers or prejudge the decision. |
| 4 | The closure's own scope is "published, dated; account-specific overrides not verified; re-read if the account, model or provider changes" (rev 4 B46 uncertainty; record 02 D7 "treat the figures as dated"). Carried as the closure's scope, not as a re-opening. |
| 5 | Record 02 D6 was headed "provisional until COO item 8 closes"; item 8 has closed (record 06), but the CEO's record 06 item 5 keeps D6 provisional **until items 1 and 2 supply baselines**, and revision 4 B57/§4 record it the same way — the later statement governs and this update applies it. The D6 conditions (as corrected by record 03) remain the only recorded stop rules; `/health/detailed` and the admin `/metrics` signals remain readable per process while the log-based signals are not readable by the Ops route (rev 4 B57, hazard ranking). No threshold is set here. |
| 6 | The raised shared ceiling is spend-authority provenance, not concurrency, capacity or runtime-budget admission (record 06 §"Ledger event 2" scope; rev 4 B58). Provider use by the Monday pregenerate run inside the readout window is **unknown, not zero** (no `generated` counter — receipt §"Disposition inputs"; rev 4 B60) and has no ledger estimate; carried as a cost unknown, not a budget. |
| 7 | The CTO delivered the named-owner action revision 1 required, and the verdict is honest: neither "demonstrably suffice" nor "named subset necessary" is concluded, so the C5 requirement stays unmet and the item stays open. The negative finding ("no E09 subset demonstrated necessary") is author judgement, unrefuted on revision 4 (rev 4 §0); the COO neither strengthens nor weakens it and does not rely on it for any admission. Revision 4 preserves the hold, preselects no fleet build, keeps Slice A independent of egress identity and does not treat dormant code as exempt — consistent with the COO's constraints. |
| 8 | The closure covers revision 3's derived rows (B08, B19, B36, B41, B54, §5). Revision 4's changed and new content has had no adversarial lens (rev 4 §0; §1.2 above). Whether a further read-only refutation is required before any admission decision relies on revision 4 is a **CEO decision**; it is not a re-opening of item 8 and is not dispatched here. |

### 2.1 Item 8 — the six qualifications carried (record 02 Appendices A/B; record 06 item 8)

| # | Row | Qualification (as accepted by the chief) | Where revision 4 carries it |
|---|---|---|---|
| 1 | B08 | Rollout-overlap extra remains unknown; the configured overlap case is up to two extra instances, not one, and the larger case is not excluded by any observation. One serving process per instance is observed (assumption resolved by the 2026-10-04 Ops read). | B07/B08 reclassified `observed` with `configured_overlap_case_max_extra_instances`; B15 uncertainty; B04 |
| 2 | B19 | The usable-connections figure is a ceiling on **everyone's** backends (platform agents, the monthly export, Ops proxy sessions), not an application-fillable figure; at the server limit new connects fail immediately (FATAL), not after the pool wait; PostgreSQL 15 has no `reserved_connections` GUC, so the null is "parameter absent" — still not zero. | B18, B19 uncertainty; B61 re-observation |
| 3 | B36 | "One bucket per process" was a floor: edgartools' internal limiter is a second, unwrapped bucket in every process (external input verified); the app bucket starts full, so the first second after an idle gap exceeds the sustained rate; the hourly filing-scan window and the daily EFTS jobs are SEC callers the row omitted; SEC's keying is external and unknown, so the shared-budget reading is the conservative branch either way. "Mostly the Monday window" withdrawn. | B36 retitled, two-bucket model; B23 SEC-calling set; B38 edgartools limiter and call sites; B35 unit |
| 4 | B41 | The pregenerate process is sequential with recovery after the primary stream, so its tight bound is smaller than the loose one; none of the other seven jobs reaches the provider; Copilot and summary multi-stream figures are call counts, not simultaneous streams. | B41 `plus_pregenerate_tight`; B48 uncertainty |
| 5 | B54 | A ceiling of metered, user-originated, admitted uses per calendar month — not provider requests: retries, section recovery, cross-instance duplicates and system-initiated generation sit outside it; "one account per participant" is an assumption; there is no guest generation path. | B54 uncertainty; B52 resolved from source |
| 6 | §5 | The "+4" overlap case was an assumption; the hazard-frequency claim is withdrawn (hourly window, daily EFTS jobs); the configuration-only mitigation was conditional on a bounded process count (now observed), a separately bounded library throttle (verified configurable), integer granularity (the patched scheduled-overlap sum has no headroom) and per-call Retry-After backoff (not a fleet control — "existing control" wording withdrawn). The negative determination survives; nothing establishes that configuration suffices. | §5 rewritten; hazard ranking corrected; JSON `determination` |

### 2.2 Count after this update

| State | Items | Count |
|---|---|---|
| closed | 4, 8 | 2 |
| dependency closed | 6 | 1 |
| open | 2 (B39 part), 3, 7 | 3 |
| open-with-new-sub-dependency (B62) | 1, 5 | 2 |

Five of eight remain open — the same five record 06 listed ("items 1, 2 (B39 part), 3, 5, 7"); this update adds the
B62 sub-dependency to items 1 and 5, as the receipt note and revision 4 §7 record, and changes no other state.

## 3. What the 2026-10-05 readout does and does not change for the five C1 components and the HOLD

Components C1–C5 are the five requirements of the COO first deliverable §"C1 — one capacity admission, still HOLD",
as used in revision 1 §2. "Readout" is the receipt note (run 37282199614); "revision 4" is the CTO handback beyond
the readout.

| C | Requirement | What the readout changes | What revision 4 changes beyond the readout | What does not change | Verdict after this update |
|---|---|---|---|---|---|
| C1 | Service/worker/engine/pool and simultaneous job-execution bounds, incl. rollout overlap and other clients, classified | Monday job business-phase overlap with each other and the service **observed for the first time**, with near-empty work (B22, B60); task configuration observed for the three jobs that executed (B21); a second point-in-time SQL snapshot, outside the window (B61); backfill-facts schedule observed (B23) | One serving process per instance **observed** (B07/B08; 2026-10-04 Ops read); live confirmation of B04, B05, B06, B10, B14, B49; configured overlap case up to two extra instances recorded (B08, B15) | Realised rollout overlap unknown (B08); same-job concurrency unknown (B22); Cloud SQL tier unknown (B16); parallelism of the five non-executing jobs unknown (B21); filing-scan listing `partial` (B59) | **Supplied, with named unknowns** (unchanged) |
| C2 | Evidenced DB operating reserve and wait/cleanup allowance for the proposed useful workload; no policy number from the four-slot arithmetic or the request controls | **Nothing on the reserve**: every Monitoring and Logging channel HTTP 403 (B59); the SQL snapshot is outside the window and point-in-time; **new prerequisite B62** on the readout route | B32 anchors resolved (§1.2); B18/B19 qualified; the four-slot nominal margin and the request controls remain recorded facts, deliberately not converted (rev 4 §2) | **B32 `unknown`, value null**; no DB sample inside any overlap | **Not supplied** (unchanged); the route now needs B62 |
| C3 | Effective aggregate SEC/provider policy and enforcement scope; process-local settings insufficient | Nothing: `rate_limit_hits` was never in the readout's scope | **B37 closed** (D8, observed dynamic; compliance moot); **B46 closed** (D7, published/dated); **B36 corrected** to the two-bucket model — revision 3's figure was a floor, and by configuration the fleet exceeds the external per-user cap in every state, not only the Monday window (D9, Appendix A); B39 counter semantics verified (records 03/05); B38 call sites enumerated; the founder-held D3 patch recorded as the configuration route, **not applied** | **B39 `unknown`, value null**; no fleet-wide admission exists; realised aggregate rate unmeasured; cross-instance duplicate generation by design (B45, Slice A retained) | **Not evidenced at the aggregate** (unchanged); the configured gap is sharper and its configuration-only route is prepared but unapplied (item 3) |
| C4 | Demand envelope and stop/rollback conditions supported by retained useful-work evidence and recorded policy, with spend-authority provenance | **No useful-work evidence**: pregenerate reported cached examples and no `generated` counter — provider use unknown, not zero (B56, B60); the log-based stop signals are unreadable by the Ops identity (B57, B59) | Per-account burst limiters and the absence of a guest generation path resolved from source (B51, B52); D6 provisional conditions recorded in B57; spend provenance moved to the successor ledger (B58; item 6 dependency closed); the envelope proposal restates existing configuration with nothing new (rev 4 §4) | **B56 `unknown`, value null**; thresholds not evidenced and not set; provider operating-spend field value not set; user-visible failure rate under overload unknown (B55) | **Not supported by useful-work evidence** (unchanged) |
| C5 | A specific determination: existing controls demonstrably suffice, or a named E09 subset is necessary | Indirectly: gap (b) becomes "a missing observation whose route lacks a prerequisite" (rev 4 §5) | **Re-determined: undetermined; no E09 subset demonstrated necessary**; gap (d) closed; the missing decision is named exactly (founder's D3 decision = Slice B allocation) and the missing observations exactly (B32 via B62, B39, B56); hold preserved, no fleet build preselected, Slice A independent of egress, dormant code not exempt | Neither "demonstrably suffice" nor "named subset necessary" is concluded; the E09 implementation hold incl. inactive code unchanged | **Requirement not met** (unchanged); the missing inputs are more precisely named |

**Does the HOLD stand?** Yes. The HOLD stands because the three quantities a supported useful-work envelope would rest
on are still `unknown` with null values in the CTO's revision 4 — the DB operating reserve under concurrent generation
(B32), the realised aggregate SEC rate (B39) and retained useful-work evidence under concurrency (B56) — and the first
readout aimed at B32 returned no in-window sample on any Monitoring or Logging channel (B59), so the route itself now
waits on B62; the founder's D3 decision (item 3), which is the retained Slice B policy allocation, is open; and the C5
determination remains "undetermined" (item 7). What has closed since revision 1 — provider limits (B46), egress
identity (B37), the spend-authority dependency (B58), the refutation of revision 3's derived rows (item 8), one
process per instance (B07/B08), the burst limiters and guest path (B51/B52) — removes uncertainty from the
*configured* picture and in one case (B36) makes the configured SEC hazard larger than revision 3 stated; none of it
supplies reserve or useful-work evidence. The readout's new facts (Monday overlap happens; the work was near-empty) are
evidence of concurrency, not of load, and are not converted into capacity. Nothing here weakens the COO's five
requirements, sets a threshold or budget, names an E09 subset as necessary, or re-asks the founder for cohort size,
response target or general engineering authority. Capacity remains unadmitted.

## 4. New sub-dependency B62 — recorded once

| Field | Record |
|---|---|
| Sub-dependency | **B62** — Monitoring/Logging read access for the Ops Workload Identity Federation identity (rev 4 B62, `unknown`, component 2) |
| What was observed | In the 2026-10-05 run (Ops run 37282199614) the Ops identity read Cloud Run executions and Cloud SQL but was refused by the Cloud Monitoring and Cloud Logging APIs with HTTP 403 on all four channels; the retained 2026-10-04 receipt (Ops run 37184184008, attempt 2) carried Monitoring samples, so the refusal is new or intermittent; the cause was not investigated (receipt §"What the receipt does NOT contain"; rev 4 B59) |
| Items it gates | Item 1 (B32) and item 5 (log-based stop signals: pool-timeout signature, SEC 403/429 in logs) per the receipt note and rev 4 §7; the Logging-search half of item 2 (B39) per rev 4 B39; B56 through B32 (rev 4 B56); also rev 4 §6 rows B08 (instance series) |
| Resolving step | A read-only IAM check of the Ops identity's Monitoring/Logging read roles and the cause of the 403 — a cloud read, not performed here — or a CTO-named alternative retained-sample route |
| Owner | **CTO/CEO** (read-only check); **founder** (any grant — a cloud-configuration change the founder decides; not made, not proposed here) |
| What this update does not do | It does not propose, request or make a grant; it does not dispatch the check; it does not re-run or widen the readout; it does not treat the 403 as evidence either way about the DB reserve |

## 5. R3 reporting G1–G5 and R4 entry dependencies — carried forward

Carried from revision 1 §5 unchanged; the only input touching them is record 06 (wave table rows R3/R4; owners table),
which confirms each state and changes none.

| Group | State | What the inputs show | Permitted next step / stop |
|---|---|---|---|
| G1 — supported export access | **BLOCKED** | PostHog ticket 76581 acknowledged; **still no actual access decision** (record 06 wave table R3 blocker; owners table "PostHog access decision (G1) — blocked") | Wait for the real decision; no resend, poll loop, unchanged retry, customer query, alternate unsupported route or plan purchase |
| G2 — complete literal file receipt | **BLOCKED behind G1** | No change in any input | The separately authorised tiny invented-literal export receipt stays preserved in order and is not dispatched here |
| G3 — independent actual-file contract review | **BLOCKED behind G2** | No change | Needs a named read-only reviewer once real files exist |
| G4 — private cohort, offered-scope and support control packet | **INCOMPLETE** | No change; owners as before (founder consent/recruitment and offered scope; CPO scope/product evidence; CTO contacts; CFO commercial readiness; CEO integrates) | Separate from this capacity disposition; no invitation, data collection, inferred consent, start date, flag, registration or pricing change |
| G5 — actual cohort observation | **QUEUED, 0/2 actual weekly readouts** | Prepared worksheets, consumer and synthetic receipts count as zero (record 06 wave table R4) | Two elapsed windows cannot be parallelised away |
| R4 — controlled cohort | **dependency-queued** | Behind the R2 quality decision, R3 operating readiness (this C1 HOLD; G1–G4) and the founder's separately controlled invitation/consent/start authority; the settled intended cohort (B53) is not enrolled (record 06 wave table R4) | None executable by this update |

## 6. Return contract and closing record

- **Counts unchanged:** 3/30 dossiers; 0/2 actual weekly readouts; 5 reporting groups + 1 capacity decision (C1);
  candidate HOLD; E7 90+30 not admitted. These counters overlap and are not summed.
- **Status:** `pass` for the administrative worker deliverable (all eight items dispositioned with evidence identities;
  HOLD statement derived from cited evidence; no number, admission or authority supplied; one file written).
  **Capacity: unadmitted; C1 remains HOLD.**
- **Input hashes:** the 13 inputs and the dispatch manifest are listed with full SHA-256 and byte length in §1/§1.1;
  all matched on `sha256sum` and Python before any input was relied on. **Output hash:** this file cannot contain its
  own digest; its SHA-256 and byte length are computed after the exclusive-create write and reported in the worker's
  return message to the chief.
- **Next named accountable owner and action:** **COO** remains accountable for the C1 disposition, with the **CEO** as
  coordinator. Next executable actions, in dependency order, none dispatched by this update: (1) the **CEO** routes the
  founder's **D3 decision** (item 3) as the concrete bounded choice, with the revision-4 B36 model and the readout
  receipt attached; (2) the **CTO/CEO** perform the read-only **B62** IAM check (any grant is the founder's decision);
  (3) only then do the COO/CEO decide whether to authorise one further bounded read-only `capacity-readout` over a
  window with actual concurrent generation (item 1), bundling item 2's per-process SEC observation into the same
  window; (4) the CTO's item-7 determination follows items 1–3. Stop condition for any successor: hash mismatch,
  missing field, concurrent writer, or any request for a production read beyond a recorded authorisation,
  measurement, load, invitation, flag, pricing, registration or E09 code.
- **Actual new calls / spend / reservations / external changes by this worker:** provider calls **0**; DeepSeek spend
  **USD 0.000000**; reservations **0**; ledger writes **0**; external mutations **0** (no git write, GitHub, cloud,
  gcloud/gh/curl, network, production, test, server, code, config, flag, pricing, registration, invitation,
  subscription, probe or measurement action). Files written: exactly one (this file). Agents spawned: 0. These zeros
  are observed for this worker's own actions; ordinary session/platform overhead is unmeasured and not claimed as
  zero.
- **Limits of cost knowledge carried:** provider use by the Monday pregenerate run inside the readout window is
  unknown, not zero (no counter; no ledger estimate); provider-side billing of cancelled streams is unknown (B43);
  cross-instance duplicate generation (B45) is an unmeasured exposure. None of these is a budget.
- **No further writes; no background work is claimed after this handback.**
