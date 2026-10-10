# Founder decisions still necessary for the file-download readout route — with recommended answers (COO draft, 2026-10-05)

**For the founder, with the CEO.** Companion to `QUERY-ROUTE-READOUT-CONTRACT-DRAFT-01.md` revision 3 (the contract). Only
the decisions that are genuinely still open for the selected route are listed; each carries a recommended answer, the
reason and what it unblocks. **Not re-asked (decided):** the route (file-download batch export, selected 2026-10-05
~20:17Z); ticket 76581 (resolved); the HogQL file-download export flag (enabled and validated by the completed three-row
run `01a10d89-1ee8-0000-3e2c-9000712c9502`); the USD 25 authorisation (DeepSeek only, untouched); no PostHog charge.
**Not asked now (belongs to later gates):** start date, the two weekly windows, roster observation time, consent and
offered-scope facts (G4/R4 gates); the settle delay (COO/CEO policy when the first window is authorised); any number.
**Open founder confirmation (not a decision):** the PostHog cloud region and host production actually uses — section
after D5.
Recording a decision here settles nothing by itself: G1–G5 settle only after the access decision is recorded **and**
the G3 review of the actual downloaded part accepts the file-input contract. Nothing here marks cohort reporting, beta
admission or capacity complete or admitted. Prepared by a bounded COO worker with no connector or HTTP call, no customer
data and no spend.

| # | Decision | Recommended answer | Unblocks |
|---|---|---|---|
| D1 | Operator identity for customer exports (both legs) | **O2 — founder-operated**, with a founder-side verification script; G3 reviewer a separate non-executive context | Registration of the operator label; the first customer export after the gates |
| D2 | The explicit G1 access decision | Record the text in D2 as written, dated, after the capability part is verified | G1 closes in the file-route shape |
| D3 | Private store for parts, bound queries, parameters and outputs | Founder-side private directory outside any repository, under the existing custody-check convention; repository gets hashes and counts only | The first customer part has a compliant home; receipts can be written |
| D4 | A no-cost dry run before the first real readout | **No second export**; **yes** to one offline consumer dry run on the downloaded three-row part once D5 is authored | Proves the JSONLines → consumer path without a connector call or customer data |
| D5 | How parts reach the released consumer | **Option A — thin adapter**, authored only after G3 accepts the actual part; released consumer byte-unchanged | A readout can be produced from a completed export; `fixture_check` extended for the adapter only |

## D1 — Operator identity for customer-data exports

**Question.** Which non-executive context runs the two legs of a customer export: the connector leg (count-rows, create,
retrieve — returns no rows but sends the roster-bearing query) and the download leg (one authenticated GET per part with
a personal API key — returns rows)? The contract's revision 2 listed O1 (dedicated non-executive remote session), O2
(founder-operated with a hashing script), O3 (child worker of the executive session), O4 (defer).

**Recommended answer: O2 — founder-operated for both legs on the two weekly readouts and the combined-window run**, with a
founder-side read-only script that performs count-rows/create/poll/count via the founder's own PostHog-authenticated
context or app, downloads each part, computes SHA-256 and byte length, parses and verifies JSONLines, writes
`VERIFICATION.json` and the sanitized receipt, and **never prints a row, the key or the signed URL**. The G3 reviewer is a
different, non-executive context that reads only hashed artefacts and the run record. Executive contexts (chief, officers,
management workers) receive counts, hashes, status and verdicts only.

**Reason.** (1) The download leg already requires the founder's authenticated context — the only one that exists (receipt
01: the worker had none; the founder is downloading the capability part now); handing a personal API key to any AI
context widens credential exposure for no gain. (2) The roster literals are participant data the founder already holds as
G4 owner; with O2 they never cross into an AI context. (3) O3 is functionally proven for the connector leg (the capability
worker called the export tools) but its transcript is readable from the executive session — a discipline, not a control.
(4) O1 would need the connector attached to a new session plus a credential for the download leg — two configuration
changes before any evidence, with the isolation statement still to be produced. (5) The cost of O2 is founder time: three
runs per cohort cycle, each a few calls plus one GET per part — bounded by the contract's one-create-per-window rule.
Scheduled runs are impossible under O2; none are needed for two weekly readouts.

**What it requires from the founder.** The script (in the style of the custody-check tool), confirmation that the
connector and key are the existing authorisation (no new scope, no plan change), and the statement in D2. **What it
unblocks.** The operator label can be registered in the next exclusion closure and the first customer export can follow
the gates. **If declined:** O1 is the next choice, with the CEO producing a dated statement of connector attachment and
transcript isolation before any customer run; O3 is not recommended for customer data.

## D2 — The explicit G1 access decision (text to record)

**Question.** What exactly is recorded as G1's access decision for this route, so that G1's exit condition (an explicit,
dated, supported access decision with provenance) is met without inference?

**Recommended answer — record this, dated, once the capability part is verified and G3-reviewed:**

> **G1 access decision (file-download route), <date>.** The beta readout uses PostHog's supported HogQL file-download batch
> export (JSONLines) on project 117863 at the API host production actually uses — founder-stated **EU cloud**,
> `https://eu.posthog.com` (ingestion origin `https://eu.i.posthog.com`), confirmed against the production environment
> and the organisation's app URL. Enablement: ticket 76581 resolved by PostHog support; validated by the completed
> three-row literal run `01a10d89-1ee8-0000-3e2c-9000712c9502` (count 3 = records_completed 3; one part, verified
> <hash>). Authorisation relied on: the founder's existing account authorisation and the `batch_export:read`/`write`
> scopes connected on 2026-09-30; **no new scope, plan purchase, plan change or PostHog charge is authorised**; any
> billing or pricing signal stops the run. Data scope: the released v1 projection over the three named events, the
> frozen eligible roster after exclusions, and an elapsed UTC half-open window — for the beta readout only. Operator:
> <D1 option>, label registered in the exclusion closure before the first customer run; executive contexts receive
> counts, hashes, status and verdicts only. Private store: <D3>. The consumer input contract is fixed by <D5> after the
> G3 review; the released consumer is unchanged until then. The first customer export runs on this route only; the
> `execute-sql` query route is a fallback requiring its own decision. Acceptance of the readout contract (revision 3) is
> recorded separately from this decision. Nothing in this decision admits capacity, invites a participant, infers
> consent or marks cohort reporting or beta admission complete.

**Reason.** It names route, project, enablement evidence, authorisation, data scope, operator, store, consumer rule and
the single-route rule — the nine items the contract's §5.2 requires — and nothing more. **What it unblocks.** G1 closes
in the file-route shape; G2's receipt can be credited once verified; G3 can be dispatched against the actual part.

## D3 — Private store for readout files

**Question.** Where do the parts of customer exports, the bound query text (roster literals), the parameters file, the
connector responses, `VERIFICATION.json` and the consumer outputs live, given the repository is public and the last
attempt to copy readout files into a private artifact store was classifier-denied and not pursued (contract F11)?

**Recommended answer: a founder-side private directory outside any repository**, under the custody convention already in
use for the founder's private planning folders (per-file SHA-256 and byte length printed by a read-only script; a
`TOTAL=` line per folder), with the repository holding only hashes, counts, run ids, file ids, windows, `N`, exclusion
count, verdicts and labels. The CEO records the store's existence and custody rule by label, never its path.

**Reason.** It is the one private store the founder already operates and controls; it needs no new platform, no upload
to a session, and no connector; it keeps the operator (D1 = founder) and the store in the same hands; the artifact-store
route is blocked by a platform denial that must not be worked around. **What it unblocks.** The first customer part has a
compliant destination; receipts can cite hashes; G3 can be given hashed artefacts for review. **Trial first** on the
capability part (invented rows): it exercises the custody path at zero risk.

## D4 — A no-cost dry run before the first real readout

**Question.** Is any further dry run wanted before the first customer export?

**Recommended answer: no second export; yes to one offline consumer dry run.** The completed three-row run already
exercised the export mechanics (count-rows, create, poll to Completed, records_completed, part inventory), and its
download and verification are in flight. Repeating it would cost a create authorisation and add nothing. What is
unexercised and exercisable at zero cost is the path from JSONLines to the released consumer: once D5 is authored, run
it offline on the downloaded three-row part with the September 30 synthetic parameters and compare with the retained
September 30 consumer output (one view, one paired complete request, 1,000 ms) — no connector call, no customer data.

**Reason.** It proves the only untested link in the chain with the data already in hand, and it gives G3 a concrete
input-contract artefact to review. **What it unblocks.** Confidence that the first customer readout is not the first
exercise of the adapter; a fixture for `fixture_check`. **Not covered by any dry run:** the `events`-table predicate,
window literals and multi-part output — first exercised on the first authorised customer run, which is why the
`n_before = n_after = records_completed = rows_parsed` rule exists.

## D5 — How file-export parts reach the released consumer

**Question.** The released consumer expects query-response JSON (`columns`, `results`, `hasMore`); a file-download run
yields JSONLines parts with none of those fields (contract §2.3). Which single change is authorised, after G3 reviews
the actual part: **Option A** — a thin, separately reviewed adapter that converts parts to `{columns, results}` with no
`hasMore`, no coercion, plus a file-route completeness record; or **Option B** — a consumer change that accepts a
`file_export` object and computes `export_complete_observed` from the file-route rule?

**Recommended answer: Option A (adapter), authored by a CTO-named minimal implementation writer only after G3 records
`accept` on the actual part.** The released `readout_v1.py` stays byte-unchanged; the receipt carries
`file_export_complete_observed` from the adapter's completeness record and states that the consumer's own
`export_complete_observed` is a query-route field that remains `false` by construction.

**Reason.** (1) It honours the released rule to keep the consumer and its unknowns unchanged until a reviewed real
contract demonstrates the need (runbook; FIRST-DELIVERABLE G3), and the need is now demonstrable on a real part. (2) It
is smaller and independently testable; the consumer's released fixtures and hashes stay valid. (3) It cannot manufacture
`hasMore=false` or concatenate parts, because the completeness record is separate from the response object. (4) Option B
re-opens a released component and its contract tests for the same outcome. **Condition:** if G3 finds a rendering that the
consumer rejects (for example a string-typed `timestamp_s`), the remedy is a reviewed projection change, never adapter
coercion. **What it unblocks.** A readout can be produced from a completed, complete export; D4's offline dry run; the
first customer readout after the gates.

## Open founder confirmation (not a decision) — PostHog cloud region and host

**Founder-stated (addendum 2026-10-05):** the organisation uses **PostHog EU cloud** — private API host
`https://eu.posthog.com`, ingestion origin `https://eu.i.posthog.com`, personal API keys created at the EU settings
page. Revision 3 of the contract carries this as an explicit assumption (F5, §2.0 step 6, K4, §5.2).

**What stands beside it in the record:** export-capability receipt 01 and its run record state that the repository's
configured ingestion origin is `https://us.i.posthog.com` (`docs/CONFIGURATION.md` line 77; `backend/app/config.py`
line 107), and the chief's addendum states that `backend/app/config.py` `POSTHOG_HOST` and the frontend provider default
to that US origin unless overridden by env. This worker did not open those files and made no connector or HTTP call;
nothing here asserts a mismatch — only that the two statements are not yet reconciled in writing.

**What the founder confirms (once, in writing, before the first download):** (a) the production values of the backend
`POSTHOG_HOST` and the frontend provider host as actually deployed (the env overrides, not the code defaults); (b) that
project 117863 lives in the EU region (the organisation's app URL); (c) that the personal API key used for the download
leg is issued at the EU settings page. **Why it matters:** the download leg's host must be the one production actually
uses, or the GET returns a 404 or reads the wrong place; and if production ingested to one region while the export read
another, the export would be empty or wrong without any error — the confirmation closes that possibility rather than
assuming it away. **Where it lands:** the host named in the D2 decision text and in the contract's §5.2; no code change
is proposed here.

## Closing

Decisions recorded here are the founder's with the CEO; the COO recommends and does not decide. No participant count,
threshold, budget, date or cost is supplied. No connector or HTTP call, customer data, repository write or spend
occurred in preparing this file. **G1–G5 remain not settled; cohort reporting, beta admission and capacity are not
complete and not admitted.**
