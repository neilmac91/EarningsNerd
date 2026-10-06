# Decision record 12 — Astra's five-field R1 handback recorded (planner acknowledged inside the 60-second bound; no fallback; all 69 originals local and 69 of 69 equal; the complete original H20 input-manifest identity NOT established — exact missing control stated; 12 minutes charged, 138 remain); PR #1104 review record closed; closure 162 (chief, 2026-10-06)

Recorded 2026-10-06T19:07:54Z by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`, runtime-reported model
`claude-fable-5-1`). Context: record 11 merged to main as `88df1f7f2f84acbbe452f0ad8d6250032fe632c0` (PR #1104, squash of
`7537b2ec` + `6d3d205b`, merged 18:37Z); this branch was restarted from that main. Records only: no code, workflow, migration,
cloud, IAM or production change; no provider call; no reservation; no source material opened. The founder relayed Astra's two
handback files after the record-11 brief; their content is Astra's statement, recorded here as relayed, with the parts the chief
can verify from the repository marked as verified.

## What arrived

| File (relayed by the founder; retained outside the repository, bound by hash) | Bytes | SHA-256 |
|---|---:|---|
| `ASTRA-HANDBACK-FOR-CHIEF-20261006.md` (Astra's prose handback, metadata only) | 3,730 | `41d0945fbb6e6b5c259d69c6281196890215f77ddcf94a08ea5ac49a6ce63b8b` |
| `ASTRA-FIVE-FIELD-HANDBACK-20261006.json` (the five fields of the record-11 brief) | 3,339 | `a12d749249a2bf9c6e0b3d98a37c00a5889fafb08e3f728f0b14839c11c4d391` |

Both files are administrative: no source inputs, candidate outputs, judge material, custodian mappings, private references or
customer data. Astra states zero provider calls and spend, zero ledger, repository, production or held-PR writes, zero
source-input release or refinement dispatch. Raw custody details stay with the founder.

## The five fields — Astra's values and the chief's disposition

| Field | Astra's value (as relayed) | Chief's verification and disposition |
|---|---|---|
| 1. `ack_attempt` | **acknowledged**; 1 attempt; registered identity `codex-thread:01a102be-45bf-72f3-8b9a-a5ff7bb8adfe:/root/h20_refinement_planner_20261004`; attempt not before 18:30:40Z, acknowledgment observed by 18:31:03Z, elapsed upper bound 23 s (clock-bounded; the messaging tool exposes no precise send timestamp); `source_inputs_supplied=false`; `refinement_dispatched=false` | **Verified:** the identity string equals closure 140's registered label exactly (string equality against closure 161's list). The 23-second upper bound is inside decision 1's 60-second limit. **Disposition:** the registered planner is **resumable at the acknowledgment level**; it remains undispatched and source-only; no history, input or task was supplied. Closure 162 annotates the closure-140 entry; no new context |
| 2. `fallback_identity` | **none** — the registered planner responded; the conditional replacement was not bootstrapped | **Disposition:** closure 146's conditional label `source-only-planner:fresh-context:launched-after-this-record:h20-refinement-planner-fallback-01` was **not exercised**; it stays conditional and unresolved (annotated in closure 162; not retired, not substituted) |
| 3. `custody_totals_and_equality` | `TOTAL=22 LOCAL_BEFORE=22 MATERIALISED_BY_THIS_READ=0 STUBS=0 UNREADABLE=0` and `TOTAL=48 LOCAL_BEFORE=48 MATERIALISED_BY_THIS_READ=0 STUBS=0 UNREADABLE=0`; **69 of 69 equal** (21 bootstrap originals + 48 predecessor originals; 1 Finder metadata file excluded from equality); mismatches 0; partial reads 0; cloud-only after verification 0; custody check 18:35:21Z; archive comparison 18:36:27Z; custody script SHA-256 `31046549905004e53ff035be5141cdfc159c85de06fc68752e1ab2a483d23b8b`; recovery archive identities verified; restoration through the existing Apple download API; Keep Downloaded not offered in the inspected folder menu, so persistent pinning is **not claimed** | **Verified:** the custody script hash equals the committed `tools/h20-custody-check.sh` on main (`31046549…`) — Astra ran the registered tool, byte-identical. The two `TOTAL=` lines match the expected 22 and 48 (record 11) with every line already `LOCAL` when read (`LOCAL_BEFORE` = `TOTAL`, nothing materialised by the read, no stubs, nothing unreadable). Equality against the recovery archive and the archive identities are as relayed (record 08 holds the archive confirmation as relayed, not verified by the chief). **Disposition:** local availability **VERIFIED at 2026-10-06T18:36Z** (point-in-time). Because pinning is not established, a cloud eviction can recur; the release flow of record 05 must re-run the same tool immediately before any release and the chief records that run's two `TOTAL=` lines again |
| 4. `manifest_identity` | **`COMPONENT_ORIGINALS_VERIFIED_COMPLETE_H20_INPUT_MANIFEST_IDENTITY_NOT_ESTABLISHED`**; `complete_original_h20_input_manifest_sha256` null; bytes null; missing control: "Original input manifest identity was not found as a complete-H20-input designation in the checked retained custody controls and administrative handback records; the exact missing control is its SHA-256 and byte count." Three original component manifests recovered and re-hashed equal to the retained custody receipt of 2026-10-04T08:09:23.024269Z: source snapshot 112,536 B `f65b783c0d73f98eb49f4d91acc79fbada546be7133decb3f2094679b2aaa708`; supplements 72,423 B `f6365709fa83983538a55f7ad4745cf79ccdd955ac9c91bdde2d2118ac21f12a`; embedding contracts 9,148 B `043a595866d51c74e807d533c2f980e1dcbcf0033af19d20ed4cd6c9485b5639`. The source snapshot covers 92 captured source records and is one component; per-component complete flags do not designate a singular complete H20 input manifest; no archive, allowlist, projection or reconstructed manifest substituted. "The existing registered control reviewer independently confirmed this administrative distinction using metadata only" | **Checked:** none of the three component hashes and not the receipt timestamp appears anywhere in the repository (founder-side by design, as record 10 stated), so they are recorded as relayed. Astra's handling matches founder decision 3: the exact missing control is reported and nothing is substituted. **Disposition:** the record-05 predicate `clean_frozen_h20_input_manifest_sha256` cannot be filled from retained evidence; the complete-manifest comparison stays **BLOCKED**; R1 stays **NOT_RELEASED**. The "existing registered control reviewer" is not named by an identity string, so the chief cannot map it to a closure entry; recorded as relayed (follow-up below; not blocking) |
| 5. `minutes_used` | **12** focused preparation minutes: 10 Astra (rounded up, including the handback) + 2 for the reused registered control reviewer; "at most 138 remain, pending the chief's reconciliation"; no ledger entry; no reset | **Charged** against the allowance below: total charged 30 → **42**, remaining 150 → **138**. Astra's figure agrees. Minutes are not money: no ledger event |

## R1 allowance — reconciled, not reset

| Item | Minutes |
|---|---|
| Allowance (record 02 D2; three focused hours of source-only planner refinement) | 180 |
| Charged before record 03 | 10 |
| Charged after record 03 (inside `minutes_used`, record 05 return route) | 20 |
| Charged by this record (Astra's 2026-10-06 `minutes_used`: acknowledgment attempt, custody restore and verification, manifest retrieval attempt, handback; 10 + 2) | 12 |
| Total charged | 42 |
| Remaining | 138 |

Not charged: the chief's and reviewers' time (not part of the allowance). Nothing resets.

## R1 — state after this record

| Item | State | Evidence / rule |
|---|---|---|
| Registered planner | **Resumable at the acknowledgment level** (one attempt, ≤ 23 s, no input, no task); undispatched; source-only; closure 140 entry annotated in closure 162 | Field 1; founder decision 1 |
| Fallback | **Not exercised**; closure 146's label stays conditional and unresolved | Field 2 |
| Bootstrap count | 21 source inputs + 1 Finder metadata file (22 regular files) — resolved (record 11) and now observed by the tool (`TOTAL=22`) | Field 3; founder decision 2 |
| Predecessor count | 48 / 48 | Field 3 |
| Local availability | **VERIFIED at 2026-10-06T18:36Z**: 69 of 69 originals local and equal to the recovery archive's members (as relayed); pinning not established, so the release flow re-runs the tool immediately before release | Field 3; record 05 gate; record 07 tool semantics |
| Complete original input-manifest comparison | **BLOCKED — control not establishable from retained evidence**: the complete original H20 input manifest's SHA-256 and byte count were not found as a designation; three component manifests are identified and verified but are not that control; nothing substituted | Field 4; founder decision 3; record 05 |
| Allowance | 180 / 10 / 20 / 12 / **42** / **138** | Table above |
| Release | **NOT_RELEASED**; `R1-STATUS.md` unchanged (it changes only when every predicate holds); the receipt template stays `template_only=true` | Record 05 gate |

## The manifest control — what the founder decides (precise)

Record 05's standing gate requires `clean_frozen_h20_input_manifest_sha256` from the existing custody process and names the
original input-manifest identity among the items the chief receives before any release. Astra's retrieval found no retained
designation of a singular complete H20 input manifest. Under decision 3 the hold stands and nothing is substituted. The chief
does not redefine the gate. Two facts are missing, in this order:

1. **A factual answer from the custodian (no cost, no substitution):** do the three retained original component manifests
   (source snapshot `f65b783c…`, supplements `f6365709…`, embedding contracts `043a5958…`, bound by the custody receipt of
   2026-10-04T08:09:23.024269Z) jointly enumerate the 69 retained inputs with a per-file hash and length? Yes or no, with the
   count of inputs they enumerate. If no, the complete-manifest comparison cannot be run from them either.
2. **Only then, a founder decision (contract change, recorded in its own record, never inferred):** either (a) keep the gate as
   written, in which case R1 stays NOT_RELEASED until a complete original manifest identity is retrieved or the gate is
   superseded; or (b) supersede record 05's predicate by an explicit founder decision that binds the frozen H20 input identity
   to the ordered triple of those three custody-receipt-bound original component manifests (their SHA-256s and byte counts),
   after which Astra runs the comparison and reports matched / mismatched / partial counts. (b) is a documented change of the
   control's definition made by its owner, not a substitution of a reconstructed or archive hash; the chief records it only if
   the founder states it and only after the custodian's answer in 1 is yes.

Recommendation: ask the custodian question 1 first; it is free and decides whether (b) is even available.

**Follow-up (not blocking):** the identity string of "the existing registered control reviewer" that Astra reused for two
minutes, so the chief can map it to a closure entry. If it is a context already in the closures, the mapping is an annotation;
if not, it is pre-registered in the next closure before any further use.

## PR #1104 review record closed (decision record 11)

- Head `7537b2ec` reviewed by the single pre-registered reviewer (closure 161; records-only rule; launched 18:14Z): **NO
  BLOCKER**; 90 hash rows / 0 mismatched / 0 missing; closure chain 160 → 161 verified; every locally checkable anchor
  verified; 1 should-fix and 5 nits, all applied in `6d3d205b`.
- Delta `7537b2ec..6d3d205b` by the same reviewer: **NO BLOCKER bound to `6d3d205bab68fc64c0632c3277926121945e4638`**; 0
  remaining. Codex quota exhausted (connector comment 6022852442, 18:30:36Z); override bound to the final head.
- Merged `88df1f7f` at 18:37Z. Main CI run 37512718577 green; its `deploy-backend` job 112441254666 ran only the change
  detector and **skipped all nine deploy steps** — the third live proof of the PR #1101 correction.

## Registration (closure 162)

`control/source-context-exclusion-162.json`: resolves closure 161's provisional label `record-11-reviewer-01` to
`launched-2026-10-06T1814Z`; pre-registers this record's single PR reviewer (`record-12-reviewer-01`); annotates closure 140's
planner entry with the acknowledgment metadata of field 1 (no new context; no edit of closure 140) and closure 146's fallback
label as not exercised and still conditional. No context gains source A/B, reconciliation or blind financial judging
eligibility.

## Spend

0 DeepSeek calls; USD 0; 0 reservations; 0 ledger events; conditional unreserved 22.527800 unchanged; paid dispatch HELD.
Astra reports zero provider calls and spend for the handback.

## Founder decisions this record needs

1. **Manifest control:** relay the custodian's answer to question 1 above; then state (a) or (b).
2. **Contract revision 3:** still open — accept with record 11's recommended text, or amend.
3. **D3 numbers:** unchanged, held (record 08 patch `21322a05…`).
4. Optional, not blocking: the control reviewer's identity string (follow-up above).

Nothing in this record releases input, dispatches the planner, admits capacity, invites anyone, changes a flag, adds load,
implements E09 or accepts the reporting contract.
