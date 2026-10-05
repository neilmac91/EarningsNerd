# Decision record 06 — overnight masterplan execution: ledger event 2 (shared ceiling 25), wave table, C1 closures, Monday readout plan (chief, 2026-10-05)

Recorded 2026-10-05T00:15:41Z by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`, runtime-reported
model `claude-fable-5-1`). Inputs: the founder's overnight directive and updated spending authorization
(received 2026-10-05T00:02:09Z), the merged records 02–05, the handover package's `WAVE-REGISTER`,
`CEO-DIRECTIVE` and `MASTERPLAN-REVIEW`, the COO disposition's eight C1 items and the CTO handback revision 3.
Nothing below releases inputs, dispatches the planner, admits capacity, releases a hold, invites a user, changes a
production flag, adds load, extends a timebox or spends. The assessment is not restarted; counts are carried
from the retained records.

## PR #1092 finished

All six required checks succeeded on head `d86f8f04` (backend-tests, frontend-tests, e2e-tests,
migrations-postgres, lighthouse, review-gate; secret-scan and eval-baseline also success; deploy-backend skipped
for a `tasks/`-only change). Squash-merged to main as `0b8d39ebad065a8ab5f3ab4b6213892f2e7544a2`; PR
subscription removed. Record 05 is durable on main.

## Ledger event 2 — shared DeepSeek ceiling raised USD 15 → USD 25 (CEO; CFO reconciliation rule reused)

- Written 2026-10-05T00:10:56Z under the hash-chain rule: `previous_sha256`
  `beef4ca0b2973db9f00503e0bbbf3ae2ad816def51c0f53820c41e51431be3fa`; new document SHA-256
  **`f4dd36fb0bba8528ae31faebf93b49fe1c493e5795becc8314c56c10b23f9f4f`**, 25,307 bytes. Republished to the private
  "CODE RED Spend Ledger" artifact (version 3) and read back from the published store: the served bytes hash
  `f4dd36fb…` (match). The URL stays out of this public record (record 02, D5).
- Reconciliation (arithmetic on recorded counters; the CFO worker stays unlaunched because no paid action is
  pending): ceiling 25.000000 − known future cost 0.547516 (297 calls) − retained holds 1.881713 (other owner
  1.000000, uncertainty 0.600000, cancelled-run unknown 0.281713) = **22.570771 conditional unreserved** (was
  12.570771). Cumulative recorded usage unchanged at 2,356 calls / USD 4.331765. Active reservations 0. Paid
  dispatch stays HELD until a reservation is written before each paid trigger.
- Scope as the founder stated it and as recorded in the event: one shared ceiling across the chief, officers and
  workers; not per agent; not additive to any unused earlier allowance; existing charges, reservations, holds and
  unknown costs remain; the authorization releases no held work, extends no timebox, permits no new load and
  relaxes no source-role, quality, review or deployment gate. The founder's exact wording is stored in the event
  (private store), not reproduced here.
- Event classification: `authorization_changed: true`; balances, reservations and holds unchanged; spend 0. This
  is an administrative write permitted under the narrowed rule of record 03 (no reservation needed for a
  non-balance-affecting write).

## Wave table (state at this record; counts, not percentages)

| Wave | Accountable | Completed outcomes retained | Remaining counts | Blocker (recorded once) | Next concrete deliverable and acceptance |
|---|---|---|---|---|---|
| R1 — Finish acceptance inputs | CTO | 3/30 dossiers (H28/H29/H30); H20 24 attempts / 19 complete / 5 partial; offline custody released (PR1084); fresh source-only planner registered (closure 140); controls package hash-verified (`ceed7244…`); release-receipt gate adopted (record 05) | 27 dossiers = 54 briefs + 27 reconciliations; custody 18/21 bootstrap and 14/48 predecessor files cloud-only, 11 of 39 local files verified by hash and length, 0 mismatches; candidate freeze HOLD; 30 of 180 minutes charged, 150 remain | Founder-local custody materialisation and two-part verification; planner runtime availability unverified; release receipt NOT_RELEASED | Founder + Astra: bounded availability-discrepancy investigation, then materialise and verify every selected original and governing control; complete the receipt and send the chief its SHA-256 and metadata. Acceptance: six attestations true, manifest identity named, totals with 0 mismatches and 0 partials, planner context registered (fresh identity if not resumable). Then the refinement returns the six-field JSON and the chief sets `R1-STATUS.md`. |
| R2 — Decide summary quality | CPO | A1–A9 administrative admission status and process handback complete (two verifier passes) | 0/90 candidate and 0/30 comparator outputs admitted; no final E7 acceptance; E8 separate | R1 exit (complete inputs, frozen candidate/comparator) and the retained judging-resumption authority | None executable tonight. Next: bind the role/evidence admission matrix when R1 exit evidence exists. Acceptance: matrix names every role, exclusion closure and input hash; no executive context in a source or judging role. |
| R3 — Close beta operations | COO | CTO envelope handback rev 3 (58 bounds) and COO disposition (HOLD, 8 items); records 02 D4/D6/D7/D8/D9; two read-only Ops describes; per-process SEC budget patch prepared and gated (founder holds it, record 02 D3) | G1 BLOCKED (PostHog ticket 76581, no access decision), G2/G3 behind G1, G4 INCOMPLETE, G5 0/2; C1: 5 of 8 items open after tonight's closures (below) | External: PostHog's access decision; founder: Slice B policy numbers (patch); readout evidence arrives 08:10Z | Monday 06:00–08:00 UTC `capacity-readout` receipt (item 1 / B32) → CTO handback revision 4 (B07/B08/B36/B41/B52 updates, B32 observation, C5 re-determination) → COO disposition update. Acceptance: receipt with run id, conclusion and retained artifact name; rev 4 with `CORRECTION-03.md` hash chain; disposition update stating each item's state. Capacity is not admitted by any of these. |
| R4 — Run controlled cohort | COO | Worksheets, runbook, consumer and synthetic receipts prepared (count as zero readouts) | 0/2 actual weekly readouts; 10–20 intended participants not enrolled | R2 decision, R3 operating readiness (C1 HOLD, G1–G4), and the founder's separately controlled invitation/consent/start authority | None executable tonight; two elapsed observation windows cannot be parallelised away. |
| R5 — Expand safely | CTO | Design prepared; the only earlier-safety subset identified (per-process SEC budgets) is configuration, not E09 code | Fleet coordination, out-of-time quality evidence, canary and bounded rollout not admitted | R4 evidence; the SEC budget patch waits on the founder's decision (commit was classifier-denied, record 02 D3) | None executable tonight beyond D3's founder step. |
| Shared spend | CFO (recommends) / CEO (writes) | Successor ledger designated (record 02 D1); events 1 and 2 written | Headroom 22.570771 conditional unreserved under the 25 ceiling; holds 1.881713; reservations 0 | None; no paid action is pending | Reserve before the first paid action (next candidates: ~USD 0.01 `copilot-eval` when a PR carrying the D3 patch is marked ready; paid CI for any backend change). |

## C1 items — closures recorded by their named owner (COO disposition §4)

| # | Item | Named owner | Disposition tonight |
|---|---|---|---|
| 1 | B32 DB operating reserve under concurrent generation | COO/CEO decision; CTO executes | Authorised (record 02 D4); the Routine dispatches the readout at 08:10Z; open until the receipt exists |
| 2 | B39 realised fleet SEC rate; B37 egress identity | CTO via CEO-approved observation | B37 closed for compliance by record 02 D8 (SEC's cap is per user regardless of IP); B39 stays open — the readout does not carry `rate_limit_hits` |
| 3 | Founder's Slice B policy numbers | Founder | Open; the prepared patch (SHA-256 `21322a05…`) is the concrete bounded choice |
| 4 | B46 provider account limits | CTO/CEO | **Closed** by record 02 D7 (published figures recorded with source identity and date) |
| 5 | Evidenced stop thresholds | CTO baselines → COO/CEO policy | Open; provisional conditions (record 02 D6) stand until items 1 and 2 supply baselines |
| 6 | B58 provider operating-spend field | CEO | **Dependency closed**: the successor ledger is designated and reachable (record 02 D1; event 2 raises the ceiling). The field's value is not set tonight: it attaches to a C1 admission decision, which does not exist, and the ceiling alone is not capacity (handback B58 note retained) |
| 7 | C5 specific determination | CTO after items 1–4 | Open; re-determination belongs to handback revision 4 after the readout |
| 8 | Independent refutation of derived rows | CEO decision | **Closed** on the refutation record (record 02 Appendices A and B: no arithmetic error; six qualifications; one external input verified; one assumption resolved by observation). The CEO exercises the closure as the item's named owner; the COO carries the six qualifications into the disposition update |

Open after tonight: items 1, 2 (B39 part), 3, 5, 7 — five of eight. Nothing here admits capacity or sets a
threshold, budget or participant count.

## Executability assessment (why effort does not move to R1, R2, R4 or R5 tonight)

- R1's next step is founder-local (custody bytes and Astra's opaque checks); no executive context may touch
  the inputs, and the planner's runtime is unverified. Recording more would be administrative repetition.
- R2 waits for R1's exit; the CPO's administrative readiness is complete.
- R4 waits for R2, R3 and the founder's invitation/consent authority; prepared machinery counts as zero.
- R5 waits for R4; its only earlier-safety item is the founder-held D3 patch.
- R3 is therefore the one wave with an executable deliverable overnight, and its evidence arrives with the
  08:10Z readout; the CTO revision-4 and COO update workers are pre-registered as provisional labels so they
  can run as soon as the receipt exists without a further record.

## Monday readout (record 02 D4, confirmed)

Routine `trig_01QEr6wQnjqtMG4FdqLce2qT` (verified armed, `run_once_at` 2026-10-05T08:10:00Z, bound to this
session) dispatches one read-only `ops.yml` `capacity-readout` over 06:00–08:00 UTC after confirming that no
`deploy-backend` run is in flight on main. The receipt (run id, conclusion, retained artifact name; the SQL
snapshot is taken at dispatch time; `rate_limit_hits` is not in it) is recorded as a dated note under
`handbacks/coo/` and folded into this record's PR rather than a separate one. The scheduled Monday pregenerate run
may itself spend provider budget inside that window; the readout does not measure it and the ledger does not
estimate it — it stays unknown until telemetry is read.

## Record-05 nit carried in (as directed: cosmetic fixes ride the next necessary update)

Record 05's header now lists all three amendment times (the third, 2026-10-04T23:54:42Z, changed one owners-table
row). No other change to record 05.

## Registration (closure 145)

`control/source-context-exclusion-145.json` (197 known contexts; prior 193 preserved) resolves the record-05
independent reviewer's identity (launched 2026-10-04T23:46:16Z; the same context ran the two later delta checks)
and pre-registers three provisional labels: the record-06 PR reviewer, the CTO handback revision-4 author and the
COO disposition-update worker. The registered H20 planner is unchanged; no substitute context is registered.

## Owners and next actions

| Item | Owner | Next action | State |
|---|---|---|---|
| Ledger event 2 | CEO | Done; `LEDGER-ACCESS.md` and `APPOINTMENTS.json` carry the new hash | done |
| Monday readout receipt | Routine → chief → COO | 08:10Z dispatch; receipt note; fold into this PR | armed |
| CTO handback rev 4 | CTO worker (provisional label registered) | After the receipt: B07/B08/B36/B41/B52 updates, B32 observation, C5 re-determination; `CORRECTION-03.md` | queued on receipt |
| COO disposition update | COO worker (provisional label registered) | After rev 4: per-item state for the eight C1 items | queued on rev 4 |
| Custody / planner runtime / receipt | Founder + Astra | Unchanged from record 05 | open |
| Patch (D3) | Founder | Unchanged; chief reserves ~USD 0.01 before any PR carrying it is marked ready | open |
| PostHog access decision (G1) | External (PostHog) via the founder's account relationship | Wait for the real decision; no resend, poll, retry or plan purchase | blocked |

## Spend

0 DeepSeek calls; USD 0.000000; 0 reservations; 1 ledger event (event 2: authorization raised to USD 25; no
balance change).
