# Agent handbacks reconciled — 26 September 2026

The founder supplied all three checkpoints after the initial takeover audit. Each reports idle
status, no uncommitted work, no reserved files, no running commands and no active automation.
Codex can take over from main `b53455bb` without transferring an unfinished external branch.
No clarification is required for that engineering handback.

## Custody of the supplied evidence

The original `agent-b-checkpoint-2026-09-26.zip` is preserved byte-for-byte in the private task
workspace, SHA-256 `a1bc0fe70207bd6c229bf3a0b50255e281216d9acc84d28fc955ebbb4936782c`.
Outer/nested ZIP integrity and safe paths were checked before extraction. All **80 entries** in
the outer and nested SHA256SUMS manifests match; no missing/mismatched file was found.
The separately attached CHECKPOINT.md is byte-identical to the bundled copy.

The independent pre-implementation fixture pack is now available, rather than merely cited:
`agent-b-source-units-review-pack-v1.zip`, SHA-256
`2f9273bbe1e76c6d9709af21114ebd79099a566f1cfdd0e00a38b724043dad88`.
Its receipt identifies base `523b26fe6a86e2c0f92f98e2f27bfde0f51a160d`, 64 cases, 13 relations
and 24 tamper operators. The returned #954/#957/#958/#959/#961 reviews, probes and adapters are
retained with it. These integrity checks establish receipt of the artifacts, not that every
reported probe was independently rerun by Codex.

## Ownership and completion

| Agent | Handback accepted | Outstanding useful work |
| --- | --- | --- |
| A | Source units, members, modality inventory and graph are on main. No next slice started. Later founder directions/overrides are reported explicitly. | No active ownership. Codex takes over the corrections and eventual H29 integration. |
| B | Advisory-only reviewer; no PRs, pushes, comments, merges or production changes. Original independent fixture pack and subsequent reviews delivered. | Available for a narrow independent delta review of the next corrective commit. |
| C | #953 SDK refresh, #958 test isolation and #960 index ordering are complete. No next slice or unique branch content. | None needed now. Optional test nits do not justify another backend deployment by themselves. |

## Corrections to the checkpoints

- A's final addendum retracts its earlier claim that the final #961 Codex review had not returned
  before merge. It acknowledges both exact-head findings were available and were not rechecked.
  This agrees with GitHub timestamps and the [takeover release evidence](README.md).
- B reviewed more than #954: the returned artifacts cover #957, #958, #959 and #961 too. A's
  statement that independent B review existed only for #954 describes what reached A, not the
  full review history. Findings were lost between sessions; they are consolidated below.
- B's claim that #962 did not exist and its pending #961 deployment observation are dated
  snapshots. #962 now exists; Codex verified #961's completed deploy, migration counts,
  revision and independent detailed health. No further agent inquiry is needed.
- C's claim that docs-only #960 left production on `00385-7bp` misses the intervening #959
  release. #959 deployed `00386-9bw`; #961 subsequently deployed `00387-55c`. The observed
  logs control the current-state record.
- C supplies dated independent-health observations for #953 (22:54:22 UTC, DB 6.68 ms) and
  #958 (21:44:12 UTC, DB 5.93 ms). These are now retained agent attestations; raw responses
  were not attached. Do not turn them into independently reconstructed historical observations.
- The 9–10-line `full-gate.log` files for #957/#959/#961 are result summaries, not full raw
  console captures. Hosted exact-head gates remain independently observed. Future receipts
  should label summaries accurately and retain the actual captured output when available.

## Consolidated engineering disposition

| Finding | Evidence / disposition |
| --- | --- |
| #961 arbitrary prompt accepted | Independently reproduced by B and Codex. Deterministic rendering remains required before admission; the current limitation must be explicit. |
| #961 omitted/renumbered adverse attempt | Independently reproduced by B and Codex. Use externally retained expected history at admission; a caller-recomputed hash chain alone is insufficient. No need for a founder design decision. |
| #961 unused-template/output alias | Independently reproduced by B and Codex. Fix all-contract template coverage in the small correction. |
| #957 repeated full-packet hashing on invalid overlapping units | B supplied executed refutations. Independently verify, then reject excessive cumulative coverage before hashing; preserve the later exact-partition check. |
| #957 context-before-hash test is insensitive to moved guard | B supplied a mutation showing the test passes despite late validation. Strengthen the existing test with observed hash work. |
| #959 bare/default-namespace inline-XBRL silently omitted | B supplied executed probes. Independently verify and fail closed on unsupported bare fact/hidden elements while preserving ordinary HTML `header`. |
| #959 projection memory and self-closing constructs | Capacity risks, not measured 57 MB outcomes. Use a bounded real-source canary and hard resource limits before any largest-file projection. Do not call the extrapolated 15 GB an observed H25 measurement. |
| Wider link gate, lesson ordering, optional ContextVar assertions | Defer: no demonstrated execution blocker. Do not create a separate deployment for cosmetic or speculative improvements. |

## Calls, spend and authority

All three report zero E7/E8 generation, Fable/judge calls, quota probes, retries, live jobs and
guard changes. This resolves their session histories only, not a new sole-guard attestation.
Do not reset either programme's ledger or change its model/CLI contract.

Ordinary hosted DeepSeek regression/Copilot calls occurred. A/C report founder-observed balance
USD 65.69 on September 23 and explicit merge/review-override directions. C additionally reports
cancelled ordinary run `35928885930` after about 55 seconds of generation with an untallied call
count. Preserve that uncertainty; it is not E7/E8 evidence or zero provider spend. Fresh paid
measurement still requires the existing balance/cost prerequisites.

The cloud sessions' workflow-dispatch 403 and review-limit observations describe those sessions
at their observation times. They do not authorize permission workarounds or establish the current
Codex session's capability. No previously denied action is retried by this handback reconciliation.
