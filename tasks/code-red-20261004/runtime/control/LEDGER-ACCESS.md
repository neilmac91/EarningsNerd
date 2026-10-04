# Live spending ledger — access statement (chief, 2026-10-04)

**Authoritative live ledger named by the package:**
`outputs/next-stage-20261003/spend-and-reservation.json` under
`/Users/neilmacaogain/Documents/Codex/2026-10-03/github-plugin-github-openai-curated-remote-3` (the
founder's local Codex task root). **Status from this cloud session: not reachable.** The repository
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
