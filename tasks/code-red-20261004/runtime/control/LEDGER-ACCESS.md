# Live spending ledger — access statement (chief, 2026-10-04)

**Authoritative live ledger named by the package:**
`outputs/next-stage-20261003/spend-and-reservation.json` under the founder's local Codex task root (the
absolute path is held in the private handover materials; removed from this public record under the
records-privacy decision, `DECISIONS-04.md`). **Status from this cloud session: not reachable.** The repository
clone contains no `outputs/` directory and the founder's machine is not mounted or networked here.

**Packaged reference:** `control/spend-and-reservation.SNAPSHOT.json`, SHA-256
`99c7259ff3e5f0f2c40b60e6b557bbc711222be0e261b9277f3105e9bca8fc7b`, 18,351 bytes. It equals
`PACKAGE-INDEX.json.ledger_sha256` and the CFO packet copy. It is reference evidence: a ZIP copy is
never an independently spendable balance.

**Decisions applied (CHIEF-TRANSFER-POLICY.md, "One actual chief, one writer"):**

1. No successor ledger is designated. Designation requires reconciling the latest original and
   recording the original writer as retired; the original cannot be read from here, so this chief
   holds write authority without exercising it.
2. Paid dispatch, paid-CI triggers, reservations and ledger writes are HELD in this session until
   either (a) the founder supplies the current `spend-and-reservation.json` bytes and SHA-256 (then one
   successor ledger is designated here with the full event/hold history and hash chain preserved), or
   (b) the founder confirms the live file is byte-identical to the packaged snapshot hash above.
3. Eligible offline work continues. Every action in this session is USD 0 / 0 DeepSeek calls; none of
   the currently unblocked deliverables needs a paid trigger, so the hold blocks nothing today.
4. Officers cannot spend from the snapshot. The CFO's reconciliation (USD 12.570771 conditional
   unreserved under the shared USD 15 authority, USD 1.881713 retained holds including the
   cancelled-run unknown) is reused as dated evidence, not as a lock.

**Founder-dependent item (not blocking today):** supply the live ledger file or hash confirmation
before the first paid action is proposed. The chief will not manufacture a fresh budget from the
snapshot and will not re-ask for the USD 15 authority.

---

## Update 2026-10-04T17:39Z — successor ledger designated (supersedes decisions 1–2 above)

Astra (the retired original writer, read-only) confirmed on 2026-10-04 that the live
`outputs/next-stage-20261003/spend-and-reservation.json` is byte-identical to the packaged snapshot
(SHA-256 `99c7259ff3e5f0f2c40b60e6b557bbc711222be0e261b9277f3105e9bca8fc7b`, 18,351 bytes) and that
no reservation, hold or event was added after 2026-10-04T09:35:21Z. Condition (b) is met.

- **Successor ledger:** private claude.ai artifact "CODE RED Spend Ledger" in the founder's account;
  authoritative document `spend-and-reservation.json`, 20,272 bytes, SHA-256
  `53e8486800e193277c5be5c14a786cfeff90d3b4fa212be1c044c7343fea9f78` (snapshot + `successor_designation`
  block with the predecessor hash, hash-chain rule, state at designation and an empty `events` list).
  The URL is not recorded here (public repository; `DECISIONS-02.md` D5).
- **Writer:** the chief only. Every write appends an event carrying the previous document's SHA-256.
- **Predecessor:** the founder's local file is frozen reference; Astra stays read-only.
- **Paid dispatch:** still HELD — a reservation must be written in the successor before any paid trigger
  (including `copilot-eval` on a backend PR marked ready). Active reservations: 0.
- Decisions 3–4 above remain in force; the founder-dependent item is closed.

### Event 1 — written 2026-10-04T20:04:46Z (recorded here 20:07:50Z)

Wording correction appended under the hash-chain rule (`previous_sha256` `53e84868…`): the supported
reconciliation statement is "byte-identical to the packaged snapshot"; the snapshot already carried
entries stamped 09:35:21.075Z and 12:49:19.634Z. Current document: 21,295 bytes, SHA-256
`beef4ca0b2973db9f00503e0bbbf3ae2ad816def51c0f53820c41e51431be3fa`. Balances, holds and reservations
unchanged; spend 0. See `DECISIONS-03.md`. Rule as narrowed there: the reservation requirement applies to
balance-affecting writes (reservations, holds, spend); administrative wording or correction events are
permitted under the hash chain with `balances_changed: false`.

### Event 2 — written 2026-10-05T00:10:56Z (recorded here 2026-10-05T00:15:41Z)

Shared DeepSeek ceiling raised by the founder from USD 15.000000 to USD 25.000000 total (one shared ceiling across
the chief, officers and workers; not per agent; nothing resets). Appended under the hash-chain rule
(`previous_sha256` `beef4ca0…`). Reconciled headroom: 25.000000 − 0.547516 known future cost − 1.881713 retained
holds = **22.570771 conditional unreserved**. Current document: 25,307 bytes, SHA-256
`f4dd36fb0bba8528ae31faebf93b49fe1c493e5795becc8314c56c10b23f9f4f`; republished (artifact version 3) and read
back from the published store with the same hash. Balances, holds and reservations unchanged; spend 0; active
reservations 0; paid dispatch still HELD until a reservation is written before each paid trigger. The
authorization releases no held work, extends no timebox, permits no new load and relaxes no gate. See
`DECISIONS-06.md`.

### Event 3 — written 2026-10-05T17:54:35Z (recorded here 2026-10-05T17:56:53Z)

Written by the chief as sole writer under the hash-chain rule (`previous_sha256` `f4dd36fb…`): a chief defect — one paid
`copilot-eval` run (37350658792) triggered without a reservation by marking PR #1098 ready, cancel requested but the run
completed — recorded as use against the shared authority (29 calls, telemetry USD 0.005575; known use 0.547516 → 0.553091,
calls 297 → 326), holds unchanged (1.881713), one reservation of USD 0.010000 for the single required re-trigger;
conditional unreserved 25.000000 − 0.553091 − 1.881713 − 0.010000 = **22.555196**. Current document: 29,012 bytes, SHA-256
`6c2dc45f76b5405730c6079d2a08dee2507125a64b0afa1f759c533ac71449c5`; republished as artifact version 4 and read back with the same hash. From this event, decision 3 of the 2026-10-04 statement (every action USD 0 / 0 DeepSeek calls) no longer holds: 29 calls are recorded and active reservations are 1. Event 4 will record the re-trigger's actual cost and release the unused reservation.

### Event 4 — written 2026-10-05T18:21:22Z (recorded here 2026-10-05T18:35:26Z)

Written by the chief as sole writer under the hash-chain rule (`previous_sha256` `6c2dc45f…`): the event-3 reservation
(USD 0.010000, the one required `copilot-eval` re-trigger on PR #1098) settled at its actual telemetry cost of
USD 0.025568 (34 calls; run 37354664320); the excess USD 0.015568 is recorded as use without a reservation (chief defect:
reservation undersized). Known use 0.553091 → 0.578659 (calls 326 → 360); holds unchanged (1.881713); active
reservations 0; conditional unreserved 25.000000 − 0.578659 − 1.881713 = **22.539628**. Current document: 31,690 bytes,
SHA-256 `b4ce7016ed1996c345dfc40fc3565cfc1e964963bfc866af1df79f49660f9c36`; republished as artifact version 5 and read back with the same hash. See `DECISIONS-08.md`.

### Reservation rule refined — recorded 2026-10-05T22:06Z (record 09; no event written; stamp corrected from a forward-dated 22:08Z after the PR #1100 review)

Founder instruction 2026-10-05 ~20:17Z: keep the recorded overrun visible; future reservations carry justified headroom;
USD 0.03 is a measured minimum, not a guaranteed maximum. Rule from this record: a reservation is written before any paid
action at the dearest measured cost of a comparable run multiplied by a headroom factor stated and justified in the
ledger event. For `copilot-eval`, the two measured runs on identical code cost USD 0.005575 and USD 0.025568 (4.6×), so
the next reservation is **USD 0.060000** (0.025568 × 2, rounded up) unless a dearer run is measured first. The event-4
excess of USD 0.015568 recorded without a reservation stays visible in every ledger view, in record 08 and here. No
balance changes; no event is written by this rule; the document SHA-256 remains `b4ce7016…` (31,690 bytes). See
`DECISIONS-09.md`.

### Event 5 — written 2026-10-06T05:31:46Z (recorded here 2026-10-06T05:49:57Z)

Written by the chief as sole writer under the hash-chain rule (`previous_sha256` `b4ce7016…`): a reservation of
**USD 0.060000** for the one paid `copilot-eval` run that marking the deploy-scoping correction PR (#1101; Astra's patch
`6d6f14fa…`, head `e3eac7a7`, adds `backend/tests/unit/test_backend_deploy_scope.py` under `backend/**`) ready will trigger.
Sized by the refined rule: dearest measured comparable run USD 0.025568 (34 calls; event 4) × headroom factor 2, rounded up;
USD 0.03 is the measured minimum, not a ceiling; no optional rerun, retry or prompt iteration is covered. Written before
the PR was opened (draft at 05:38Z) and before it leaves draft. No spend; holds unchanged (1.881713); active reservations
0 → 1; conditional unreserved 25.000000 − 0.578659 − 1.881713 − 0.060000 = **22.479628**. Current document: 34,158 bytes,
SHA-256 `2ab676370c19ce1d73921ccb05e2958195eac5067111bfafdab2c506b6d834b1`. The first publish attempt was refused by the
artifact store because the published file had not been re-read in this session; the chief read it back (`b4ce7016…`,
31,690 bytes — equal to the event-4 hash), republished as artifact version 6 and read the new file back with the same hash
`2ab67637…`. Event 6 will settle this reservation at the run's actual telemetry cost and release the unused part. The
event-4 excess of USD 0.015568 stays visible. See `DECISIONS-10.md`.

### Event 6 — written 2026-10-06T06:26:18Z (recorded here 2026-10-06T06:28:30Z)

Written by the chief as sole writer under the hash-chain rule (`previous_sha256` `2ab67637…`): the event-5 reservation
(USD 0.060000, the one `copilot-eval` run that marking PR #1101 ready triggered) settled at its actual telemetry cost of
**USD 0.011828** (33 `ai_call` lines, all success, `deepseek-flash`; run 37423107415, job 112136659879, 06:19:41–06:22:03Z,
success, 18 / 18 passed); **USD 0.048172 released unused; no excess** — the refined reservation rule held on its first use.
Recorded use against the authority 0.578659 → 0.590487 (calls 360 → 393); cumulative recorded usage 2,452 calls / USD 4.374736;
holds unchanged (1.881713); active reservations 0; conditional unreserved 25.000000 − 0.590487 − 1.881713 = **22.527800**.
Current document: 35,946 bytes, SHA-256 `a0ef4057db45844bda67ebe2c80c850cdc06f9c58cd4ded928050d35112ca817`; republished as
artifact version 7 and read back from the published store with the same hash. Paid dispatch is HELD again until the next
reservation is written. The event-4 excess of USD 0.015568 stays visible. Three measured `copilot-eval` runs on comparable code
now read 0.005575 / 0.025568 / 0.011828; the next reservation stays at the dearest measured run × 2 (USD 0.060000) unless a
dearer run is measured. See `DECISIONS-10.md`.
