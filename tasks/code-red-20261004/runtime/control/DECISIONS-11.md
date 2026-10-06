# Decision record 11 — the founder's bounded decisions of 2026-10-06 (one planner acknowledgment attempt with a 60-second wait and an administrative fallback; bootstrap count resolved as 21 source inputs plus Finder metadata; local availability to be restored; the original manifest identity a retained-evidence retrieval task); readout contract revision 3 presented for acceptance; record-10 merge verified; closure 161 (chief, 2026-10-06)

Recorded 2026-10-06T18:11:41Z by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`, runtime-reported model
`claude-fable-5-1`). Context: record 10 merged to main as `fbb79922dd7f0c19172dba122b8693bd3b4b3675` (PR #1103, merged 07:01Z); this branch
was restarted from that main. Records only: no code, workflow, migration, cloud, IAM or production change; no provider call; no
reservation. The founder's message arrived after the record-10 report and is recorded here in its intent, decision by decision.

## The founder's four decisions — recorded and translated into bounded actions

| # | Decision (founder, 2026-10-06) | What it authorises | What it does not authorise | Owner of the next action |
|---|---|---|---|---|
| 1 | Planner runtime: Astra makes **one** runtime-only acknowledgment attempt to the registered planner (closure 140; runtime subchat identity annotated in closure 159), **maximum 60-second wait**. If the runtime is unavailable or does not respond: **administrative bootstrap of one fresh source-only replacement**; register its actual identity and establish eligibility through the existing custody process before supplying inputs; **no executive history transferred**; all preparation within the reconciled remaining allowance; **no timebox reset** | The attempt; on failure, the bootstrap of the context closure 146 pre-registered as `source-only-planner:fresh-context:launched-after-this-record:h20-refinement-planner-fallback-01`, with the hash-verified controls package (`ceed7244…`, record 04) | Any source input, any refinement work, any release, any history transfer; a second attempt; a second replacement | Astra (execution; founder relays); chief (registration in the next closure; allowance accounting from Astra's report) |
| 2 | Bootstrap count: Astra confirmed **22 regular files = 21 source inputs + a root-level `.DS_Store` of 16,388 bytes**; Finder metadata is excluded from the source-input count. This resolves the count discrepancy, **not** the manifest comparison. Astra's latest metadata check found the 21 bootstrap originals and the 48 predecessor files **cloud-only again**: restore local availability through the established custody process and verify originals before claiming readiness | The count rule (metadata excluded) and the restore-and-verify step below | Any readiness, release or eligibility claim before the restore is verified | Astra / founder (restore, custody check); chief (records the two `TOTAL=` lines and the equality count) |
| 3 | Original manifest: the complete original input-manifest SHA-256 and byte count remain unverified; this is a **retained-evidence retrieval task for Astra**, not a value the founder can invent. **No substitute** (archive hash, allowlist hash, reconstructed manifest). If the original identity cannot be established, report the exact missing control and keep release held | The retrieval and its honest outcome | Any substitute identity; any release | Astra (retrieval); chief (records identity or the exact missing control) |
| 4 | Other lanes: reuse the completed IAM, export and deployment evidence; keep B32 unobserved where its required conditions were absent and do not repeatedly reassess unchanged windows; present reporting contract revision 3 with the precise acceptance decision and the unresolved G3 gap; D3 remains held; defer optional follow-ups unless they resolve a demonstrated blocker | The presentation below; evidence reuse | New readouts over unchanged windows; the three optional follow-ups (detector hardening, explicit PyYAML pin, EU-host code default) — deferred, none blocks anything | Chief (presentation); founder (acceptance decision); COO/CEO (B32 only when a qualifying retained window exists) |

## R1 — state after these decisions

| Item | State | Evidence / rule |
|---|---|---|
| Bootstrap count | **Resolved**: 21 source inputs; the 22nd regular file is Finder metadata (`.DS_Store`, 16,388 bytes) and is excluded from the source-input count by the founder's rule | Founder's statement 2026-10-06 (Astra's confirmation relayed); the retained custody report's first line `.DS_Store LOCAL` (record 07) |
| Predecessor count | 48 / 48 | Retained `TOTAL=48 LOCAL_BEFORE=48` (record 10) |
| Local availability | **Not currently established**: Astra's latest metadata check found all 21 + 48 files cloud-only again. Restore through the established custody process: Keep Downloaded / Download Now on both folders, then one run of `tools/h20-custody-check.sh` on both folders (expected `TOTAL=22` and `TOTAL=48`, every line `LOCAL` or `WAS_DATALESS` materialised by that read, `STUBS=0 UNREADABLE=0`), then per-file SHA-256 and byte-length equality of the 21 + 48 originals against the recovery archive's members (recovery equality was confirmed on 2026-10-05) as the availability proof. The founder relays the two `TOTAL=` lines and the equality count only — no file names, no contents | Record 07 (tool; materialisation semantics); record 08 (recovery and archive integrity confirmed) |
| Complete original input-manifest comparison | **BLOCKED** — the exact missing control is the identity (SHA-256 and byte count) of the complete original frozen H20 input manifest produced by the custody process at freeze time (record 05: `clean_frozen_h20_input_manifest_sha256` "comes from the existing custody process, not the ZIP or scope hash"). Retrieval is Astra's; no archive hash, allowlist hash or reconstructed manifest substitutes. If it cannot be established, that sentence is the report and release stays held | Founder decision 3; record 05; record 10 |
| Registered planner | Acknowledgment attempt **authorised** (one attempt, ≤ 60 s wait, no input, no task). Fallback **authorised** on failure: administrative bootstrap of one fresh source-only replacement under closure 146's conditional label; actual identity registered in the next closure; eligibility through the custody process before any input; no executive history | Founder decision 1; closures 140, 146, 159 |
| Allowance | 180 / 10 / 20 / 30 / **150** — unchanged by this record; the acknowledgment attempt and any bootstrap preparation are charged when Astra reports `minutes_used` (record 05 return route); nothing resets | Records 02, 03, 05, 09 |
| Release | **NOT_RELEASED**; the six attestations not newly established; `R1-STATUS.md` unchanged | — |

## Brief for Astra (the founder relays it; the chief has no channel to Astra and opens no source material)

1. **Planner acknowledgment (decision 1).** Send the registered planner (closure 140 identity; runtime subchat `01a1086f-f579-7153-b290-dffd51654248`) one runtime-only message asking it to acknowledge that it is resumable. Wait at most 60 seconds. Send no input, no task, no history. Report: the attempt's UTC time, `acknowledged` or `no response` (or `unavailable`), and nothing else from the exchange.
2. **Fallback only if step 1 fails.** Bootstrap one fresh source-only planner context with the hash-verified controls package (`ceed7244…`); report its actual identity string for registration (the chief resolves closure 146's conditional label in the next closure) and the eligibility evidence through the existing custody process; transfer no executive history; supply no input until the chief confirms registration and the founder authorises release. Report `minutes_used` for the preparation; it is charged against the remaining 150.
3. **Local availability (decision 2).** Restore the 21 + 48 originals (Keep Downloaded / Download Now), run `tools/h20-custody-check.sh` on both folders once, and compare each original's SHA-256 and byte length with the recovery archive's members. Report: the two `TOTAL=` lines, `STUBS` and `UNREADABLE`, and the equality count (`N of 69 equal`). No file names, no contents.
4. **Original manifest identity (decision 3).** Retrieve the retained complete original frozen H20 input manifest from where the custody process kept it and report its SHA-256 and byte count with a one-line provenance (what retained it and when; no path). Do not substitute an archive hash, an allowlist hash or a reconstructed manifest. If it cannot be found, report exactly: "original input manifest identity not retained at <place>; the exact missing control is its SHA-256 and byte count" — and nothing is released.
5. **Return format.** Five fields, metadata only: `ack_attempt`, `fallback_identity` (or `none`), `custody_totals_and_equality`, `manifest_identity` (or the missing-control sentence), `minutes_used`. The founder relays them to the chief, who records them in record 12 and the next closure.

## R3 reporting — contract revision 3 presented for acceptance (decision 4)

**What is being accepted.** `handbacks/coo/QUERY-ROUTE-READOUT-CONTRACT-DRAFT-01.md`, revision 3 (SHA-256
`ad599074e6f27149b6bfb736fccdb45014d1bdc411a2b087165a23d09e9b16dd`, 47,321 bytes; merged in PR #1100), as the executable readout
contract for the file-download route: §2.0 lifecycle and completeness rule, §2.1–2.5 per group, §3 operator legs (D1 O2), §2.3
Option A (now implemented: `file_export_to_v1.py`, reviewed and merged). Acceptance is recorded **separately** from the G1 access
decision (record 09) and its closure (record 10), as the contract's §5.2 (9) requires.

**The precise acceptance decision (recommended text for the founder):**

> Readout contract revision 3 (`ad599074…`, 47,321 bytes) is accepted on 2026-10-06 as the binding readout contract for the
> file-download route. G3's consumer-as-is check (review 01, checklist item 14) failed and is bridged by the Option A adapter
> `file_export_to_v1.py` (independently reviewed; released consumer byte-unchanged). Acceptance settles the route, the export
> lifecycle, the completeness rule, retention and the G4/G5 binding rules; it settles nothing in G4 (roster, exclusions, control
> packet) or G5 (0 / 2), admits no capacity and invites no participant. The first customer part receives its own independent
> file-input review before it reaches the consumer.

**The unresolved G3 gap, stated exactly.** G3 review 01 (`eb21a013…`): checklist **14 pass / 1 fail / 1 not-applicable**. The
one failure is item 14 — the released consumer's input is its retained raw query response (`columns`, `results`, `hasMore`); the
JSONLines part has none of those fields and the consumer exits 1 at `json.loads`. The bridge is the Option A adapter, reviewed in
PR #1100 (three lenses + delta) and verified by the D4 dry run (adapter → consumer on the actual three-row part reproduces the
September 30 readout except `input_sha256.events`). Residual, not bridged by acceptance: (a) the review covered a **synthetic
three-row part only** — the first customer part must pass the same named independent review before the consumer runs on it;
(b) `export_complete_observed` on this route comes from the adapter's run-level completeness rule, never from an in-file flag
(item 15 not-applicable); (c) the adapter's `source_availability_recorded` flag must be aligned with the operator's offline mode
(carried from record 09). G3 therefore reads **"reviewed with a stated gap; bridged; first customer part review pending"** and
closes only when that review records `accept`.

**Recommended answer:** accept revision 3 with the gap statement as written; no change to the draft is needed. On acceptance
the chief records the text above as the dated acceptance in record 12 and sets G3 to the reading above; on amendment the COO
revises once more on a manifest.

## Other lanes (decision 4) — evidence reused, nothing reassessed

IAM (PERMITTED, run 37418676235), the capability export (run `01a10d89…`, part `67bc4e91…`) and the deploy-scoping proof
(PR #1101's merge) are reused as recorded. B32 stays unobserved: no retained window with concurrent generation exists among those
the records describe (COO update 02), so no readout is dispatched and no unchanged window is reassessed. D3 stays held. The three
optional follow-ups are deferred: none resolves a demonstrated blocker.

## Record-10 merge verified

Main CI run 37427152965 on `fbb79922` (07:01:49–07:09:25Z): every test job success; `deploy-backend` job 112151662415 ran the
corrected detector and **skipped all nine deploy steps** (tasks-only merge) — the second live proof of PR #1101's correction.

## Carried from PR #1103's review

The record-10 review section's sentence "every hash, byte count and ledger figure in this record verified" overstated the reviewer's
result: the correct statement is **every locally checkable** hash, byte count and ledger figure verified; Astra's four handover
files, the custody report identity and the artifact zip digest were stated as reported and are not verifiable in the repository.
Recorded here; record 10 is not edited. The lens-label convention (`review:<lens>` in a workflow journal ↔
`<record>-review-lens-<lens>-01` in the closure, agent ids identical) is stated in closure 161. Session scratchpad path literals
in dispatch manifests remain the convention (a container path identified by hash, not a local-machine path).

## Registration (closure 161)

`control/source-context-exclusion-161.json`: resolves closure 160's provisional label `record-10-reviewer-01` to
`launched-2026-10-06T0641Z` (NO BLOCKER on `987a2bc9`; delta NO BLOCKER bound to `6629a8c6`); pre-registers this record's single
PR reviewer (`record-11-reviewer-01`); states the lens-label convention. The fallback planner label (closure 146) stays conditional
until Astra reports; the acknowledgment attempt creates no new context.

## Spend

0 DeepSeek calls; USD 0; 0 reservations; 0 ledger events; conditional unreserved 22.527800 unchanged; paid dispatch HELD.

## Founder decisions this record needs

1. **Contract revision 3:** accept with the recommended text (or amend).
2. **D3 numbers:** unchanged, held (record 08 patch `21322a05…`).

Everything else is now Astra's execution under decisions 1–3; the chief records the five return fields when the founder relays them.
