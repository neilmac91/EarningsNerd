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
