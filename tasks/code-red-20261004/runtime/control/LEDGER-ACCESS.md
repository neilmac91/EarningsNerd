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

### Events 7–34 — the runtime-records gate PR's paid runs (recorded here 2026-10-08T03:51:14Z)

All written by the chief as sole writer under the hash-chain rule, each publish preceded by a readback of the published file and
followed by a readback with the new hash. Every reservation was USD 0.060000 (dearest measured comparable run 0.025568 × headroom
factor 2, rounded up; no optional rerun covered) and was written before the run it covers fired — before PR #1110 left draft (runs
1–9) or before a push while it was ready (runs 11–14) — except event 25, recorded after the founder's ready action had triggered
run 10 (2026-10-07T22:17:46Z, while the chief held the PR in draft); every settlement
recorded the run's actual telemetry cost and released the rest. Holds unchanged (1.881713) throughout. See `DECISIONS-15.md`.

| Event | Written | Kind | Figures | Document after |
|---|---|---|---|---|
| 7 | 2026-10-07T07:14:49Z | reservation (run 1; named head `e9911039`) | headroom 22.527800 → 22.467800 | `a86f29b6…`, 38,703 B (version 8) |
| 8 | 2026-10-07T08:14:03Z | settlement of 7 (run 37591507299 on `d74f2c44`, failure: eval not accepted on its citation check) | actual 0.012581, 34 calls; released 0.047419; use 0.590487 → 0.603068 (393 → 427 calls); headroom 22.515219 | `847de0aa…`, 40,893 B (version 9) |
| 9 | 2026-10-07T08:14:47Z | reservation (run 2; named head `8fb59df1`) | headroom 22.455219 | `135d299a…`, 43,670 B (version 10) |
| 10 | 2026-10-07T08:40:58Z | settlement of 9 (run 37594477790 on `abdaae24`, success: accepted 18 / 18) | actual 0.011949, 33 calls; released 0.048051; use → 0.615017 (460 calls); headroom 22.503270 | `f5197a98…`, 45,399 B (version 11) |
| 11 | 2026-10-07T08:40:58Z | reservation (run 3; named head `66d5521d`) — its active-reservation entry carried event number 9 in error (chief defect 5) | headroom 22.443270 | `16c59167…`, 48,284 B (version 12) |
| 12 | 2026-10-07T08:56:44Z | settlement of 11 (run 37596562861 on `351191d7`, failure: not accepted, one draw withheld) + correction of event 11's entry (balances unaffected) | actual 0.011918, 33 calls; released 0.048082; use → 0.626935 (493 calls); headroom 22.491352 | `6bb68191…`, 50,952 B (version 13) |
| 13 | 2026-10-07T09:01:12Z | reservation (run 4; head `817f68d9`) | headroom 22.431352 | `1ba62bd4…`, 53,894 B (version 14) |
| 14 | 2026-10-07T09:14:11Z | settlement of 13 (run 37598266061 on `817f68d9`, success: accepted 18 / 18) | actual 0.011884, 33 calls; released 0.048116; use → 0.638819 (526 calls); headroom 22.479468 | `38f59c3f…`, 55,536 B (version 15) |
| 15 | 2026-10-07T09:15:26Z | reservation (run 5; head `5060ab09`) | headroom 22.419468 | `78dd4ed8…`, 58,479 B (version 16) |
| 16 | 2026-10-07T09:31:33Z | settlement of 15 (run 37600263407 on `5060ab09`, success: accepted 18 / 18) | actual 0.011904, 33 calls; released 0.048096; use → 0.650723 (559 calls); headroom 22.467564 | `86d95709…`, 60,130 B (version 17) |
| 17 | 2026-10-07T09:39:08Z | reservation (run 6; head `6a7a3f27`) | headroom 22.407564 | `b90fc70e…`, 63,377 B (version 18) |
| 18 | 2026-10-07T09:44:46Z | settlement of 17 (run 37602360863 on `6a7a3f27`, failure: not accepted, two draws withheld) | actual 0.012428, 34 calls; released 0.047572; use → 0.663151 (593 calls); headroom 22.455136 | `7bf2469e…`, 65,213 B (version 19) |
| 19 | 2026-10-07T09:50:31Z | reservation (run 7; head `defe0281`) | headroom 22.395136 | `64c7eee0…`, 68,296 B (version 20) |
| 20 | 2026-10-07T10:00:00Z | settlement of 19 (run 37603580135 on `defe0281`, success: accepted 18 / 18) | actual 0.012222, 34 calls; released 0.047778; use → 0.675373 (627 calls); headroom 22.442914 | `9cfb22d3…`, 69,965 B (version 21) |
| 21 | 2026-10-07T10:05:36Z | reservation (run 8; head `e692da12`) | headroom 22.382914 | `d95785ef…`, 73,073 B (version 22) |
| 22 | 2026-10-07T10:14:51Z | settlement of 21 (run 37605751354 on `e692da12`, failure: not accepted, one draw withheld) | actual 0.005937, 33 calls; released 0.054063; use → 0.681310 (660 calls); headroom 22.436977 | `11cdc0c0…`, 74,883 B (version 23) |
| 23 | 2026-10-07T10:21:03Z | reservation (run 9; head `e0f00861`) | headroom 22.376977 | `952ba782…`, 77,835 B (version 24) |
| 24 | 2026-10-07T10:33:59Z | settlement of 23 (run 37607362138 on `e0f00861`, success: accepted 18 / 18) | actual 0.005913, 33 calls; released 0.054087; use → 0.687223 (693 calls); headroom 22.431064 | `a6bfb2b0…`, 79,530 B (version 25) |
| 25 | 2026-10-07T22:20:03Z | reservation recorded after the founder's trigger (run 10, fired 22:17:46Z by the founder's ready action; head `37327581`) | headroom 22.371064 | `e3b76caa…`, 83,132 B (version 26) |
| 26 | 2026-10-07T22:47:36Z | settlement of 25 (run 37695253262 on `37327581`, success: accepted 18 / 18) | actual 0.006290, 34 calls; released 0.053710; use → 0.693513 (727 calls); headroom 22.424774 | `5420bf04…`, 85,034 B (version 27) |
| 27 | 2026-10-08T02:27:31Z | reservation (run 11; head `37c3ce12`) | headroom 22.364774 | `c95d9cb0…`, 88,665 B (version 28) |
| 28 | 2026-10-08T02:31:05Z | settlement of 27 (run 37718004123 on `37c3ce12`, failure: not accepted, one draw withheld) | actual 0.014386, 38 calls; released 0.045614; use → 0.707899 (765 calls); headroom 22.410388 | `2b228330…`, 90,774 B (version 29) |
| 29 | 2026-10-08T02:53:01Z | reservation (run 12; head `839113b1`) | headroom 22.350388 | `601357d1…`, 93,857 B (version 30) |
| 30 | 2026-10-08T02:58:22Z | settlement of 29 (run 37720074791 on `839113b1`, success: accepted 18 / 18) | actual 0.012848, 34 calls; released 0.047152; use → 0.720747 (799 calls); headroom 22.397540 | `62cd70a5…`, 95,843 B (version 31) |
| 31 | 2026-10-08T03:10:25Z | reservation (run 13; head `03b5cefc`) | headroom 22.337540 | `ccd7e694…`, 98,938 B (version 32) |
| 32 | 2026-10-08T03:13:31Z | settlement of 31 (run 37721483659 on `03b5cefc`, failure: not accepted, one draw withheld) | actual 0.013696, 36 calls; released 0.046304; use → 0.734443 (835 calls); headroom 22.383844 | `0aa6cd15…`, 101,111 B (version 33) |
| 33 | 2026-10-08T03:25:54Z | reservation (run 14; head `471a253c`) | headroom 22.323844 | `73fc2c93…`, 104,273 B (version 34) |
| 34 | 2026-10-08T03:29:44Z | settlement of 33 (run 37722715889 on `471a253c`, success: accepted 18 / 18) | actual 0.014129, 37 calls; released 0.045871; use → 0.748572 (872 calls); headroom 22.369715 | `66471d09…`, 106,288 B (version 35) |

Cumulative recorded usage after the last event: 2,931 calls / USD 4.532821. Paid dispatch is HELD again until the
next reservation is written. The event-4 excess of USD 0.015568 stays visible. Measured `copilot-eval` runs on comparable code now
read 0.005575 / 0.025568 / 0.011828 / 0.012581 / 0.011949 / 0.011918 / 0.011884 / 0.011904 / 0.012428 / 0.012222 / 0.005937 / 0.005913 / 0.006290 / 0.014386 / 0.012848 / 0.013696 / 0.014129; the next reservation stays at the dearest measured
run × 2 unless a dearer run is measured.
