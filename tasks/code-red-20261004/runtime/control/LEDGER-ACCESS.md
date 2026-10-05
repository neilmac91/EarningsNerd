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

A chief defect, written by the chief as sole writer under the hash-chain rule (`previous_sha256` `f4dd36fb…`): a chief defect — one paid
`copilot-eval` run (37350658792) triggered without a reservation by marking PR #1098 ready, cancel requested but the run
completed — recorded as use against the shared authority (29 calls, telemetry USD 0.005575; known use 0.547516 → 0.553091,
calls 297 → 326), holds unchanged (1.881713), one reservation of USD 0.010000 for the single required re-trigger;
conditional unreserved 25.000000 − 0.553091 − 1.881713 − 0.010000 = **22.555196**. Current document: 29,012 bytes, SHA-256
`6c2dc45f76b5405730c6079d2a08dee2507125a64b0afa1f759c533ac71449c5`; republished as artifact version 4. Event 4 will record the re-trigger's actual cost and release the unused reservation.
