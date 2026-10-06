# Decision record 13 — the founder's two decisions of 2026-10-06 (evening): the manifest control proceeds on the chief's recommendation (custodian question first; no predicate change), and readout contract revision 3 is ACCEPTED with the record-11 text; PR #1105 review record closed; closure 163 (chief, 2026-10-06)

Recorded 2026-10-06T23:04:39Z by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`, runtime-reported model
`claude-fable-5-1`). Context: record 12 merged to main as `adf983310b255e844acf371fd1fb50a9e48b2c44` (PR #1105, squash of
`17dbb5c5` + `2903ca9f`, merged 19:30Z); this branch was restarted from that main. Records only: no code, workflow, migration,
cloud, IAM or production change; no provider call; no reservation; no source material opened. The founder's message arrived after
the record-12 report and is recorded here in its intent, decision by decision.

## The founder's two decisions — recorded and translated into bounded actions

| # | Founder's decision (intent as received) | What it authorises | What it does not authorise | Owner |
|---|---|---|---|---|
| 1 | **Manifest control: "go with your recommendation."** Record 12's recommendation was: put the free factual question to the custodian first, and only then decide between keeping record 05's gate and superseding its predicate by an explicit recorded decision | One bounded metadata-only question to the custodian (brief below), relayed by the founder; the chief records the answer in the next record | Any change to record 05's gate; any substitution of an archive, allowlist or reconstructed hash; any comparison run; any input release or planner dispatch. The (a) / (b) decision is **not** made by this record and is not inferred from the answer | Custodian (answer); founder (relay, then the decision); chief (record) |
| 2 | **Readout contract revision 3: accept with the record-11 text** | The acceptance entry below, recorded by the founder with the CEO, dated by this entry, bound to the accepted document's identity; G3 set to the record-11 reading | Any export, PostHog request, operator run, capacity admission, invitation or roster change; nothing in G4 or G5 is settled | Founder with the CEO (acceptance); COO (owner of the document and of G1–G5 closure) |

## Readout contract revision 3 — acceptance entry

**Accepted document.** `handbacks/coo/QUERY-ROUTE-READOUT-CONTRACT-DRAFT-01.md`, revision 3, SHA-256
`ad599074e6f27149b6bfb736fccdb45014d1bdc411a2b087165a23d09e9b16dd`, 47,321 bytes (merged in PR #1100; identity recomputed by the
chief at main `adf98331` on 2026-10-06 and equal). Acceptance is of the content at that identity; the document's own status line
("DRAFT, revision 3, for acceptance by the founder with the CEO") is the COO's text and is not edited by the chief — the COO may
note the acceptance in a later revision on a manifest, and this entry, not a status line, is the record of acceptance. Recorded
separately from the G1 access decision (record 09) and its closure (record 10), as the contract's §5.2 (9) requires.

**Acceptance text (the record-11 recommended text, adopted by the founder on 2026-10-06 without amendment):**

> Readout contract revision 3 (`ad599074…`, 47,321 bytes) is accepted, on the date of this entry, as the binding readout contract for the
> file-download route. G3's consumer-as-is check (review 01, checklist item 14) failed and is bridged by the Option A adapter
> `file_export_to_v1.py` (independently reviewed; released consumer byte-unchanged). Acceptance settles the route, the export
> lifecycle, the completeness rule, retention and the G4/G5 binding rules; it settles nothing in G4 (roster, exclusions, control
> packet) or G5 (0 / 2), admits no capacity and invites no participant. The first customer part receives its own independent
> file-input review before it reaches the consumer.

**Recorded by:** the founder (decision, 2026-10-06, relayed to the chief in writing: "Accept contract revision 3 with the record-11
text") with the CEO (this entry). **Date of this entry:** 2026-10-06.

**Reporting groups after acceptance (COO owns closure; nothing here runs anything):**

| Group | State | What acceptance settled | Still required |
|---|---|---|---|
| G1 | **CLOSED** (record 10) | — (access decision recorded separately, record 09; production-host confirmation, record 10) | — |
| G2 | **Evidenced** | The receipt fields and the run-level completeness rule for the capability part | Nothing for the capability part; each customer part carries its own receipt |
| G3 | **Reviewed with a stated gap; bridged; first customer part review pending** (record 11's reading, now set) | The checklist, the exact statement of the consumer gap (item 14) and the Option A bridge | The first customer part's own independent file-input review recording `accept`; `source_availability_recorded` alignment (record 09 carry) |
| G4 | **INCOMPLETE** | The binding rule (§2.4) only | Frozen roster, exclusions, control packet — none settled by acceptance |
| G5 | **0 / 2** | The three-run cadence and what the route can and cannot carry (§2.5) | Two actual weekly readouts; R4 entry |

The operator's first customer run stays gated by G4 and R4 entry (COO `next_assignment`). No export, PostHog request or
operator run is authorised by this record; capacity stays unadmitted; no participant is invited.

## The manifest control — custodian question (decision 1; relayed by the founder)

One question, metadata-only answer, no cost, no substitution, no comparison, no predicate change:

**Do the three retained original component manifests — source snapshot `f65b783c…` (112,536 bytes), supplements
`f6365709…` (72,423 bytes), embedding contracts `043a5958…` (9,148 bytes), bound by the custody receipt of
2026-10-04T08:09:23.024269Z — jointly enumerate the 69 retained H20 inputs (21 bootstrap + 48 predecessor) with a per-file SHA-256
and byte length for each?**

Return fields (metadata only; no file names, no paths, no content, no mapping tables):

1. `enumerates_69`: `yes` / `no` / `partial`.
2. `enumerated_count`: how many of the 69 are enumerated with both a SHA-256 and a byte length (0–69), split 21-side / 48-side.
3. `per_file_hash_and_length`: `yes` / `no` (whether every enumerated entry carries both).
4. `components_used`: which of the three component manifests contribute entries (by the category names above).
5. `provenance`: one line — what retained the enumeration and when (no path).
6. `minutes_used`: minutes spent, and whether the founder consolidates them as preparation minutes under record 05; the chief
   charges against the 138 remaining only what the founder consolidates. The chief's proposed reading, subject to that
   consolidation, is that a custody look-up is not planner refinement.

Rules: do not build a new manifest to answer; do not hash or compare the 69 files against anything; do not supply any input to
any planner; report what the retained component manifests contain, as they are.

**What follows the answer (not decided here):**

- `yes` → the founder decides, in writing, (a) keep record 05's gate as written (R1 stays NOT_RELEASED until a complete original
  manifest identity is retrieved) or (b) supersede the predicate by an explicit recorded decision binding the frozen H20 input
  identity to the ordered triple of the three component originals; the chief records (b) in its own record and only then briefs
  Astra's comparison (matched / mismatched / partial over the 69).
- `no` or `partial` → the exact missing control stands as stated in record 12; the comparison cannot be run from the components;
  the founder decides whether R1's release predicate is redefined (founder-only; recorded separately) or R1 remains held.

The repository fact recorded in record 12 stands: the same triple is the committed E7 frozen source contract
(`backend/evals/acceptance_source_contract.py`, PR #1028), which governs the E7 route and does not by itself answer the question.

## R1 — state after this record

| Item | State | Evidence / rule |
|---|---|---|
| Registered planner | Resumable at the acknowledgment level (record 12); undispatched; source-only | Record 12 field 1 |
| Fallback | Not exercised; closure 146's label conditional and unresolved | Record 12 field 2 |
| Local availability | VERIFIED at 2026-10-06T18:36Z (as relayed; tool hash verified); pinning not established — the release flow re-runs the tool immediately before release | Record 12 field 3 |
| Complete original input-manifest comparison | **BLOCKED — custodian question outstanding** (this record); no predicate change; nothing substituted | Decision 1; record 12 field 4; record 05 gate |
| Allowance | 180 / 10 / 20 / 12 / **42** / **138** — unchanged by this record | Record 12 |
| Release | **NOT_RELEASED**; `R1-STATUS.md` unchanged; the receipt template stays `template_only=true` | Record 05 gate |

## PR #1105 review record closed (decision record 12)

- Head `17dbb5c5` reviewed by the single pre-registered reviewer (closure 162; records-only rule; launched 19:10Z): **BLOCKER** —
  the first draft's claim that the three component hashes appeared nowhere in the repository was contradicted by `git grep`
  (they are the committed E7 frozen-source-contract constants); 3 nits. All corrected in `2903ca9f`; the defect recorded in
  `APPOINTMENTS.json` (`chief_defects`, with the rule: absence claims only from `git grep` over every tracked file).
- Delta `17dbb5c5..2903ca9f` by the same reviewer: **NO BLOCKER bound to `2903ca9fa7043bc066af59209f1a586909f177aa`**; 0
  remaining. Codex quota exhausted (connector comment 6023816220, 19:24:25Z); override bound to the final head.
- Merged `adf98331` at 19:30Z. Main CI run 37519540764 green; its `deploy-backend` job 112463951112 ran only the change
  detector and **skipped all nine deploy steps** — the fourth live proof of the PR #1101 correction.

## Registration (closure 163)

`control/source-context-exclusion-163.json`: resolves closure 162's provisional label `record-12-reviewer-01` to
`launched-2026-10-06T1910Z`; pre-registers this record's single PR reviewer (`record-13-reviewer-01`). The custodian question
creates no new context (the custodian is the founder's existing custody process; Astra, if it relays, is the registered adviser).
The "existing registered control reviewer" Astra cited in record 12 is still not named by an identity string; no entry is added
or annotated for it (follow-up carried). No context gains source A/B, reconciliation or blind financial judging eligibility.

## Spend

0 DeepSeek calls; USD 0; 0 reservations; 0 ledger events; conditional unreserved 22.527800 unchanged; paid dispatch HELD.

## Founder actions this record needs

1. **Custodian question:** relay the question above and return the six fields; then state (a) or (b) in writing.
2. **D3 numbers:** unchanged, held (record 08 patch `21322a05…`).
3. Optional, not blocking: the control reviewer's identity string (record 12 follow-up).

Nothing in this record releases input, dispatches the planner, runs an export or operator leg, admits capacity, invites anyone,
changes a flag, adds load, implements E09 or redefines record 05's gate. The reporting contract is accepted; nothing else is.
