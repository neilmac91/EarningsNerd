# Beta reporting route proposal — query-based readout contract over the PostHog MCP `execute-sql` route (COO worker `coo-report-route-proposal-01`)

**Status: proposal and decision table for the CEO/founder — nothing adopted, approved, dispatched or queried.**
Record 07 shows that a HogQL query runs and returns rows through the official PostHog MCP `execute-sql` route on
project 117863 — the same project the blocked batch-export ticket 76581 concerns. That is a supported,
non-batch-export route for the beta readout. Its completeness guarantees differ from the file contract G2 and G3
were written for: no run id, no file parts, no completeness metadata in the response, a 100-row default cap, a
500-row maximum, LIMIT/OFFSET pagination, and an interactive connector rather than a server-side export run. This
file puts the two contracts side by side (§2), writes the query-route contract in the G2/G3 shape (§3), states
what it does and does not settle for G1–G5 (§4), lists the risks and open questions with owners (§5) and ends in
a three-option decision table (§6). MASTERPLAN-REVIEW §3B governs: no substitute reporting contract is silently
approved, so this is a proposal, not an adoption. No participant count, threshold, budget or policy number is
supplied; no customer query was made and none is authorised here.

## 1. Identity, inputs, observation date, authority and limits

| Item | Value |
|---|---|
| Worker role label | `coo-report-route-proposal-01` (COO-owned wave R3, reporting groups G1–G3; lane: beta operations) |
| Dispatch | `tasks/code-red-20261004/runtime/dispatch/COO-REPORT-ROUTE-03.json`, recorded 2026-10-05T17:12:34.712066+00:00 by the chief (session `01GWYV7WXWstgVGQG43YcSM8`); requested model inherited `claude-fable-5-1`; one active writer for this output: true |
| Runtime limitation | This worker **cannot observe its own served model or its runtime/session id**; the chief resolves the label and registers the identity in the next exclusion closure. Not read here. |
| Observation date | Inputs verified 2026-10-05T17:12:42Z; written 2026-10-05T17:13Z–17:19Z (UTC). |
| Repository state relied on | Branch `claude/vigilant-goodall-633yx3` at `52eaa6d3` (manifest entry condition; confirmed by the passive reads `git rev-parse --short HEAD` and `git branch --show-current`). No other repository file was opened. |
| Authority | **COO owns closure of G1–G5** (COO FIRST-DELIVERABLE, five-group table: "COO owns closure" for G1, "receipt acceptance" for G2, "reporting readiness" for G3). **The CEO/founder decide any substitute reporting contract** — MASTERPLAN-REVIEW §3B: "determine a concrete supported export/readout route and its evidence first. No substitute reporting contract is silently approved here." Record 07 handed the query-route evidence "to the COO for the G1–G3 route decision"; this file is the COO's proposal under that hand-over, not a decision. |
| Available authority of this worker | Administrative/management only. Excluded from source A/B authorship, reconciliation, semantic financial review and blind judging. Read-only except this one file. No git write, network, PostHog or other connector call, customer query, test, cloud or production read. Zero provider calls; zero reservation. |
| Not read, by rule | Source packets, candidate outputs, judge material, customer or participant data, credentials, anything under `tasks/readiness-2026-09-21/acceptance/`, any file outside the manifest's inputs (including the readout receipt note, CTO handback revisions, records 03–06, closures and the two PostHog `project-get` client tokens record 07 mentions — never recorded anywhere). |

### 1.1 Inputs read and verified (SHA-256 and byte length; all 7 match the manifest on `sha256sum` before any input was relied on)

| Label | Path | SHA-256 | Bytes |
|---|---|---|---:|
| COO first deliverable (G1–G5 definitions, C1) | `…/scratchpad/handover/officers/coo/references/FIRST-DELIVERABLE.md` | `c82773953be1e85daa87525003d1ade26db4e8f8e9df428f97fff80d10ee3f7f` | 15184 |
| COO operating-envelope disposition revision 1 (§5 G1–G5 carried) | `tasks/code-red-20261004/runtime/handbacks/coo/CURRENT-BETA-OPERATING-ENVELOPE-DISPOSITION.md` | `d30bdd50125ae304ad5c4fd1c6559326d3767c0f17c1ca7ec41d895ab6fc13be` | 40291 |
| COO disposition update 01 (§5 G1–G5; §6 return contract) | `tasks/code-red-20261004/runtime/handbacks/coo/CURRENT-BETA-OPERATING-ENVELOPE-DISPOSITION-UPDATE-01.md` | `07ebaaf3f1433460a6b78738314152ba00b7caeba0bbbcf447e0374cf959fdeb` | 37570 |
| Decision record 07 (PostHog query-route evidence; B62) | `tasks/code-red-20261004/runtime/control/DECISIONS-07.md` | `d4468a18e04f9f9ff6c4939cef526e33ea40f78e0feca5786346531ad7147bd0` | 6247 |
| Masterplan review (§3B beta reporting paragraph; §4 R3 row) | `…/scratchpad/handover/reference/MASTERPLAN-REVIEW.md` | `0c946f93c801bbb98836aab9c11b789d7748d88bf8894f3fbf57d0370399c710` | 21877 |
| Decision record 02 (D5 records privacy; D2 identity-registration precedent) | `tasks/code-red-20261004/runtime/control/DECISIONS-02.md` | `4d93171f68c7491afd70fcd54b19a355093c5f2a14b437d02c4fd13d3f4f508b` | 21885 |
| PostHog probe response (invented literals; as returned) | `…/scratchpad/posthog-probe/execute-sql-response-20261005.json` | `c9c1961ec63b04f26842b9878fe18c77e7e36b397e420a26dc35c5df0cff9b0b` | 193 |

The `…/scratchpad` prefix is `/tmp/claude-0/-home-user-EarningsNerd/27aa9761-b14a-5cab-9ee6-5f8ec27f49f3/scratchpad`.
Path references inside these documents (ticket 76581's own text, `control/source-context-exclusion-*.json`, the
readout receipt note, records 03–06, CTO handbacks, the successor ledger artifact) were treated as metadata and not
opened.

### 1.2 What the 193-byte probe response itself shows (read directly; no interpretation beyond its bytes)

```
{"query":{"kind":"HogQLQuery","query":"SELECT 1 AS probe_a, 'alpha' AS probe_b, toDateTime('2026-10-05 00:00:00') AS probe_c"},"results":"probe_a|probe_b|probe_c\n1|alpha|2026-10-05T00:00:00Z"}
```

Four facts the contract in §3 relies on: (a) the response **echoes the query text** under `query.query`, so a
receipt's retained query text can be checked against the response rather than against the operator's notes;
(b) `results` is a **pipe-delimited text block** (header line, then rows), not a JSON array of typed values;
(c) a `toDateTime('YYYY-MM-DD HH:MM:SS')` literal came back rendered `…T00:00:00Z`, consistent with the project
timezone UTC reported by `project-get` (record 07), so UTC window literals are unambiguous on this route;
(d) the response carries **no row count, no `limit`/`offset`, no `hasMore` and no run identifier** — completeness
metadata is absent, which is why §3.2 proves completeness with a separate count query and a last-page rule rather
than reading it from the response.

## 2. Side-by-side: the blocked batch-export contract versus a query-based readout contract

| Dimension | Batch-export contract (G1–G3 as written) | Query-based readout contract (official PostHog MCP `execute-sql`) | Evidence |
|---|---|---|---|
| Route | PostHog HogQL batch export producing a server-side run with file parts | Official PostHog MCP connector attached to a session; `execute-sql` (HogQL) against the active project | FIRST-DELIVERABLE G1–G3; record 07 §"G1/G2" row "Route" |
| Project | 117863 | 117863 — `project-get` returned "Default project", timezone UTC; the same project ticket 76581 concerns | FIRST-DELIVERABLE G1; record 07 "Project identity" |
| Access state (G1) | **BLOCKED**: 2026-09-30 literal export failed HTTP 403 `HogQL batch exports are not enabled for this team`, with tools/scopes available; ticket 76581 acknowledged, no access decision; exit requires an explicit supported feature/access decision with dated provenance and actual enablement | **Enablement evidenced, decision absent**: the route functioned on 2026-10-05T17:07Z with invented literals; record 07 states "G1's exit still requires an explicit access decision for whichever route the COO adopts" | FIRST-DELIVERABLE G1; disposition rev 1 §5; update 01 §5; record 07 "What it does not show" |
| Format probe (G2) | Required: one tiny invented-literal-only export with exact requested query, actual run id/status, reported completed row count, all file parts and hashes — **no successful run credited** | **Done for the query route**: one invented-literal query, one row returned, response retained as returned (193 bytes, SHA-256 `c9c1961e…`); record 07 names it "the tiny invented-literal format probe the COO's G2 definition names, on a query route rather than a file-export route". Pagination and the count mechanism were **not** exercised by it (one row, no LIMIT/OFFSET). | FIRST-DELIVERABLE G2; record 07 "Probe", "Result", "What it shows" |
| Unit of result / server artefact | A run (id, status, completed row count) and file parts with hashes, produced server-side | One response per query call, retained client-side; no run id, no file parts | record 07 "What it does not show"; §1.2(d) |
| Completeness metadata | Expected from the run (count, part inventory) — the earlier three-row, 21-column query projection "omitted pagination completeness" | **None in the response**; must be constructed: explicit LIMIT/OFFSET pages plus a separate count query (§3.2) | FIRST-DELIVERABLE G2; §1.2(d) |
| Row bounds | Export-sized | **100-row default cap; 500-row maximum via LIMIT** | record 07 "What it does not show" |
| Pagination | Not applicable (file parts) | **LIMIT/OFFSET**, explicit on every call | record 07 |
| Output format | File run, JSONLines — "a different contract" from the released consumer's bounded query-response JSON | Query response JSON whose `results` field is pipe-delimited text (§1.2(b)); compatibility with the released consumer's bounded query-response JSON is **not established** by the probe | FIRST-DELIVERABLE G3; §1.2 |
| Review target (G3) | Actual retained files: format, fields/types, all-part inventory, run/count completeness, bounds, duplicate/conflict rules, provenance, denominator/unknown semantics | **Query receipts**: query text, parameters, window, page inventory, count reconciliation, hashes, denominator semantics, provenance (§3.5) | FIRST-DELIVERABLE G3; this proposal |
| Operator mode | Separately named export operator; CEO controls dispatch; executive contexts never read customer rows | Same rule (§3.4). **Observed so far:** the probe was run by the chief context itself (record 07 §Registration) — permissible only because no collected data was touched; the connector is attached to an interactive session | FIRST-DELIVERABLE G2; record 07 §Registration; record 02 D2 |
| Scheduled / unattended operation | Server-side run once enabled | **Interactive connector**; availability in a Routine-fired or worker session is not evidenced in the inputs | record 07 "Route"; §5 |
| Cost coverage | Unknown — a plan purchase is explicitly insufficient and not to be made | "The PostHog MCP calls are covered by the existing PostHog plan" (dated 2026-10-05); query-volume plan limits not in the inputs; **no plan purchase proposed** | FIRST-DELIVERABLE G1; MASTERPLAN-REVIEW §3B; record 07 §Spend |
| Privacy | Files with customer rows would live in a private store; repository keeps hashes | Same (record 02 D5): rows and raw responses private; repository keeps sanitized receipt and SHA-256 | record 02 D5 |
| What the evidence does not show | — | No customer or participant data was read; nothing about the route's behaviour on collected tables, on multi-page results, under load or over time; nothing about PostHog's support terms for using the MCP as a reporting route | record 07 "What it does not show" |

## 3. The proposed query-route contract (same shape as G2/G3)

Groups are named **Q-G2** and **Q-G3** to keep them distinct from the file-route G2/G3 until the CEO/founder decide
(§6). Every placeholder in angle brackets is bound to a literal in the retained receipt; nothing is substituted
from an unretained source.

### 3.1 Q-G2 — complete literal query receipt (exit evidence)

**Exit requires** one receipt for the invented-literal format probe (**exists**: record 07, §1.2) and, before the
first customer-data query is authorised, the receipt template below filled for that probe; every later readout
query produces one receipt of the same shape. Part inventory, count and completion must agree; uncertainty stays
`incomplete`.

| Receipt field | Content | Retention class (record 02 D5) |
|---|---|---|
| Route and project | `posthog-mcp/execute-sql`; project id as returned by `project-get` in the same run (expected 117863), name and timezone — tokens redacted (record 07) | public |
| Query text, retained verbatim | The exact text sent, per page (differs between pages only in the OFFSET literal); checked against the response echo `query.query` | public if it contains no customer identifier; otherwise private, with its SHA-256 public |
| Parameters | `window_start_utc`, `window_end_utc` (UTC half-open, §3.2 rule 1); `L` (explicit page size ≤ 500); `K` (last page index); ORDER BY key; roster/exclusion reference (hash of the frozen G4 packet) | window, `L`, `K`, key: public; roster reference: hash only |
| Call log | UTC timestamp of every call (count-before, pages 0…K, count-after); connector result (`ok` / error class) per call | public |
| Page inventory | Per page: rows returned, byte length, SHA-256 of the response as returned | public |
| Count reconciliation | `n_before`, `n_after`, Σ page rows; the §3.2 verdict and, if `incomplete`, the failing rule number | public |
| Raw responses | Every response as returned, bytes unmodified | **private**; never in the repository |
| Denominator and exclusions | `N` (frozen roster size by reference), exclusions by count, both by hash; unobserved members kept in `N` | counts and hashes public; membership private |
| Operator and reviewer identity | Role labels; context ids registered in the exclusion closure before the run | labels public; ids private (D5) |
| Status | `complete` / `incomplete` / `source-unavailable` per window | public |

**Exact retained query text — format probe (done, record 07):**

```
SELECT 1 AS probe_a, 'alpha' AS probe_b, toDateTime('2026-10-05 00:00:00') AS probe_c
```

**Exact retained query shape — readout page `k` and its count query (template; no literal bound here):**

```
-- Q-R(k): rows, one page
SELECT <named projected columns>
FROM <table>
WHERE <event-time column> >= toDateTime('<window_start_utc>')
  AND <event-time column> <  toDateTime('<window_end_utc>')
  AND <roster predicate over the frozen G4 identifier set>
ORDER BY <total order on a key Q-G3 confirms unique for <table>>
LIMIT <L> OFFSET <k × L>

-- Q-C: count, identical predicate, run before page 0 and after page K
SELECT count() AS n
FROM <table>
WHERE <identical WHERE clause to Q-R>
```

The window literals use the form the probe proved (`toDateTime('YYYY-MM-DD HH:MM:SS')`, rendered UTC, §1.2(c)).
`<window_end_utc>` must be earlier than the first call's timestamp: readouts observe elapsed windows only
(FIRST-DELIVERABLE G5).

### 3.2 Pagination-completeness rule

1. **Window.** UTC half-open `[window_start_utc, window_end_utc)`: `>=` start, `<` end; both literals UTC; the end
   lies in the past at the first call.
2. **Explicit page size.** `L` is stated on every page and never exceeds the route's 500-row maximum (record 07);
   the 100-row default cap is never relied on implicitly.
3. **Contiguous pages.** Pages `k = 0 … K` with `OFFSET = k × L`; no page skipped or repeated; query text identical
   across pages except the OFFSET literal.
4. **Stable order.** `ORDER BY` a total order on a key whose uniqueness for `<table>` is confirmed in Q-G3 from the
   schema, not assumed — LIMIT/OFFSET slices are meaningful only under a stable total order.
5. **Count bracket.** Q-C runs immediately before page 0 (`n_before`) and immediately after page K (`n_after`); both
   responses are retained.
6. **Terminal page.** Paging stops at the first page returning fewer than `L` rows; a page returning exactly `L`
   rows is followed by another page; an empty page is a valid terminal page.
7. **Complete** only when **all** hold: `n_before = n_after = Σ rows`; the terminal page has `< L` rows; every
   non-terminal page has exactly `L` rows; no non-terminal page returned exactly 100 rows while `L ≠ 100`
   (a cap hit the query did not request); the keys across all pages are `Σ rows` distinct values.
8. **Otherwise incomplete.** Recorded as `incomplete` with the failing rule number; never estimated, extrapolated,
   truncated-and-reported or re-paged partially; no `hasMore=false` is fabricated and no concatenation workaround
   is applied (G3's standing rule); the window stays `incomplete` until a full re-run under a new receipt.
9. **Source unavailable.** A connector error, denial or timeout on any call makes the window `source-unavailable`
   for that run: an unknown, not a zero and not a partial result.
10. **Aggregates.** Where a readout needs per-member aggregates rather than rows, the aggregate query obeys rules
    1–9 over the roster key; a roster member absent from the result is recorded "not observed in window" and is
    interpreted only with the source-availability record — never silently as zero use or as success.

### 3.3 Result retention

- Every response is retained **as returned** (bytes, SHA-256, length, UTC timestamp) in a private store (record 02
  D5: private stores are the ledger artifact and its successors, or a CEO-designated equivalent); the repository
  keeps the sanitized receipt of §3.1 — query text or its hash, non-customer parameters, page inventory, counts,
  hashes, status, role labels. **Nothing containing a customer row enters the public repository.**
- Denominators and exclusions are preserved: `N` is the frozen G4 roster carried by reference and hash; exclusions
  are carried by count and hash; unobserved members remain in `N`; no member is dropped to make a ratio.
- Unknowns stay unknown: `source-unavailable` and `incomplete` windows are reported as such; absence of events is
  not zero without source availability; nothing is coerced.
- Credentials: any token in any response (record 07: `project-get` carries two public client tokens) is redacted
  before retention and never recorded.
- The `project-get` identity confirmation (id, name, timezone, minus tokens) is retained per run.

### 3.4 Operator identity rule

- **An executive context never runs a customer query.** Chief/CEO, COO, CTO, CFO, CPO sessions and every management
  worker (this one included) are excluded. Record 07's probe by the chief is the ceiling for an executive context:
  invented literals only, no collected data.
- **The readout operator** is a separately named, non-executive, bounded worker context dispatched by the CEO under a
  hash-bound manifest — the role FIRST-DELIVERABLE already names ("one separately named export operator" for G2;
  "named operator/reviewer executes after entry" for G5) — excluded from source A/B authorship, reconciliation,
  semantic financial review and blind judging.
- **Its identity is registered in the exclusion closure (`control/source-context-exclusion-<n>.json`) before it
  runs**, following the record 02 D2 precedent ("the planner's context identity is reported before any executive
  context reads its output and is registered in the next exclusion closure"): role label public, full context id
  private (D5).
- **Executive contexts receive only the engineering-safe return** — counts, hashes, status, verdict — never rows.
- **Open:** record 07 shows the connector attached to the chief's interactive session; whether a non-executive worker
  context can hold it, without the executive context seeing responses, is not established (§5, R2).

### 3.5 Q-G3 — independent review of query receipts (replaces the file-contract review)

**Exit requires** a named independent read-only reviewer recording `accept` / `reject` / `incomplete` on the actual
retained receipts and private responses, checking:

| Check | What is verified |
|---|---|
| Query text | Retained text byte-identical to the response echo `query.query` on every page; identical across pages except OFFSET; no identifier or predicate outside the authorised roster/window |
| Parameters | `L ≤ 500`, explicit; `K` consistent with Σ rows; ORDER BY key uniqueness confirmed from schema |
| Window | UTC half-open literals; end before first call; matches the authorised readout window |
| Page inventory | Pages 0…K all present; OFFSET sequence contiguous; per-page rows, bytes and SHA-256 match the private responses |
| Count reconciliation | §3.2 rules 5–7 re-derived by the reviewer from the retained responses, not from the operator's verdict |
| Hashes | Each private response re-hashed; each matches the public receipt |
| Format | `results` pipe-delimited text (§1.2(b)): header matches projected columns; delimiter and newline escaping in values checked; type fidelity (text rendering of numbers, times, nulls) checked against the released consumer's bounded query-response JSON contract before any consumer change is proposed |
| Duplicate/conflict rules | Keys distinct across pages; any conflict between `n_before` and `n_after` recorded, not resolved by choice |
| Denominator semantics | `N`, exclusions and unobserved members preserved; unknowns not coerced; no `hasMore=false` fabricated; no concatenation |
| Provenance | Project identity per run; operator identity in the closure before the run; UTC timestamps; route named; tokens absent |

The released consumer stays unchanged until this review justifies a bounded change; the CTO supplies a minimal
implementation writer only if a reviewed real contract demonstrates the need (FIRST-DELIVERABLE G3, carried).

### 3.6 Privacy (record 02 D5)

The repository is public. Rows, raw responses, roster membership, full context identities and operator-only detail
live in private stores; the repository keeps sanitized receipts, decisions and SHA-256 hashes. No history rewrite.
Where the private store for readout responses is to be — the ledger artifact's family or another CEO-designated
store — is an open question (§5, R8) that must be settled **before** the first customer-data query, not after.

## 4. What the query route settles and does not settle for G1–G5

| Group | State today (update 01 §5) | Settled by the query route | Not settled — still required |
|---|---|---|---|
| G1 — supported access | BLOCKED (file route) | Enablement of a supported non-batch-export route is evidenced with dated provenance (record 07, 2026-10-05T17:07Z, project 117863) | **An explicit access/route decision for whichever route is adopted** (record 07: "G1's exit still requires an explicit access decision for whichever route the COO adopts"; MASTERPLAN-REVIEW §3B). For the query route that decision is the CEO/founder's in §6, recorded with date; whether PostHog's terms support the MCP as a reporting route is part of it. Ticket 76581 remains retained; no resend, poll loop, retry or plan purchase. |
| G2 — complete literal receipt | BLOCKED behind G1 (file route) | **The invented-literal format probe is done for the query route only** (record 07; §1.2); the receipt template exists (§3.1) | The §3.1 receipt filled for the done probe; the pagination/count mechanism (§3.2) has not been exercised by any probe (one row, no LIMIT/OFFSET). **The first customer-data query stays unauthorised until the entry gates** — G4 packet, R2 quality decision, R3 operating readiness (C1 HOLD stands, update 01), the founder's separately controlled invitation/consent/start authority — and the CEO's dispatch of a named operator (§3.4). |
| G3 — independent contract review | BLOCKED behind G2 (file route) | **Review target changes from file parts to query receipts** (§3.5) | A named independent read-only reviewer; real receipts to review; the format-compatibility finding before any consumer change. Still no hypothetical adapter, coerced response or customer readout. |
| G4 — control packet | INCOMPLETE | Nothing | Unchanged; owners as before (founder, CPO, CTO, CFO; CEO integrates). The query route adds one dependency on G4: the frozen roster/exclusion packet must exist, by hash, before any roster predicate is written. |
| G5 — cohort observation | QUEUED; 0/2 actual weekly readouts | Nothing | Unchanged; two elapsed windows cannot be parallelised away; each readout would carry one Q-G2 receipt per query under this contract. |

## 5. Risks and open questions with owners

| # | Risk / open question | Why it matters | Owner | Permitted next step (none dispatched here) |
|---|---|---|---|---|
| R1 | **Row caps and query cost.** 500 rows per call maximum (record 07); row-level readouts over a window take ⌈n/L⌉ + 2 calls per query; the cost model of MCP calls under the existing plan is not in the inputs | Many pages raise call count, latency and the chance of a mid-paging change (rule 7 then fails honestly) | COO (contract: prefer bounded aggregates over the roster key; rows only where a readout field needs them); CEO/founder (plan-limit read) | Record the plan's query/call limits with source and date — a documentation read, no purchase |
| R2 | **MCP availability in scheduled or unattended runs and in a non-executive context.** The connector is attached to the chief's interactive session (record 07); nothing shows it in a Routine-fired or worker session | §3.4 requires a non-executive operator; a route only an executive context can hold cannot carry a customer query | CEO (session/connector configuration); CTO (if an alternative supported client is needed — none proposed) | One dated statement of which session kinds can hold the connector, from configuration, before any operator dispatch |
| R3 | **Auditability versus a batch export.** A batch export yields a server-side run id and file parts; the query route yields only client-retained responses with no run record | Independent review must rely on retained bytes, hashes, the response's query echo and the count bracket (§3.2, §3.5) — all client-side | Independent reviewer (Q-G3); COO (contract) | Accept or reject the §3.5 checks as sufficient for the beta report path in the §6 decision |
| R4 | **Whether ticket 76581 stays open in parallel.** | Options A/B/C differ exactly here; closing it forfeits the file route; keeping it costs nothing and must not become a resend/poll loop | CEO/founder (account/contact relationship, FIRST-DELIVERABLE G1) | Decide in §6; no resend, poll or plan purchase under any option |
| R5 | **PostHog plan limits.** Record 07 states the probe calls are covered by the existing plan (dated 2026-10-05); readout-scale limits unknown; a plan purchase is insufficient for G1 and is not proposed (FIRST-DELIVERABLE G1; MASTERPLAN-REVIEW §3B) | A route that needs a purchase to run at readout scale is a different decision | CEO/founder | Same read as R1; **no spend proposed** |
| R6 | **Response format.** `results` is pipe-delimited text (§1.2(b)); escaping of `\|` and newlines in values, null rendering and numeric typing are unverified; the released consumer accepts bounded query-response JSON (FIRST-DELIVERABLE G3) | A silent mis-parse would corrupt denominators; a consumer change needs the review first | Q-G3 reviewer; CTO only if the review demonstrates need | Review on real literal receipts; no adapter before that |
| R7 | **Pagination exercise.** The probe returned one row; LIMIT/OFFSET and the count bracket are untested on this route; whether a multi-row invented-literal set can be produced without touching collected data is not established | Rule 7 would be first proven on the first authorised customer query otherwise | COO (contract); CEO (authorise a second invented-literal probe or accept first-use proof) | Decide whether a second literal-only probe is required before the first customer query |
| R8 | **Private store for responses.** D5 requires it; the designated private store so far is the ledger artifact (record 02 D1); update 01 §1.2 records a classifier denial when copying readout files to a private store, not pursued | Without a settled store, the first customer query would have nowhere compliant to land | CEO | Designate the store (and its custody/hash rule) before any operator dispatch |
| R9 | **Changing data under paging.** Late-arriving events inside an elapsed window can move counts between `n_before` and `n_after` | Rule 7 fails honestly; readouts may need a defined settle delay after `window_end_utc` — a policy choice not made here | COO (contract) with CEO | Record the settle rule when the first readout window is authorised; no number here |
| R10 | **Token exposure.** `project-get` returns two public client tokens (record 07) | Must never reach a receipt or the repository | Operator; Q-G3 reviewer (provenance check) | §3.3 redaction rule applied on every run |

## 6. Decision table for the CEO/founder

The COO makes **no recommendation** here (MASTERPLAN-REVIEW §3B; approval is not this worker's authority). No option
proposes spend, a plan purchase, a customer query, an invitation or a production change.

| Option | Concrete next step | What it unblocks | Risk |
|---|---|---|---|
| **A — Adopt the query route** | CEO/founder record the **G1 access/route decision** for `posthog-mcp/execute-sql` on project 117863 with date and provenance (record 07), including the terms question (R5). Then, in order: CEO settles R2 and R8 (connector-holding session kind; private store); COO prepares the Q-G2 receipt template and fills it for the done probe (§3.1); CEO decides R7 (second literal-only probe or first-use proof); CEO names the readout operator and the independent reviewer and registers both in the exclusion closure. | G1 closes in the query shape once the decision is recorded; G2 and G3 proceed on the §3 contract; R3's "usable report path" becomes a defined, reviewable contract instead of an indefinite wait | Client-side-only auditability (R3); format and pagination unproven on real data (R6, R7); connector availability in a non-executive or unattended context unknown (R2); plan limits at readout scale unknown (R1, R5) |
| **B — Keep waiting for the batch export** | None executable: retain ticket 76581; no resend, status poll, unchanged retry, customer query, alternate unsupported route or plan purchase (FIRST-DELIVERABLE G1) | Nothing until PostHog supplies a decision; preserves the original file contract with server-side run ids and parts if ever enabled | G1–G3 stay BLOCKED with no date; R3 exit ("usable report path", MASTERPLAN-REVIEW §4) has no path; enablement may turn out to need a plan change, which is not proposed |
| **C — Run both** | As A for the query route, with ticket 76581 retained open and not resent; one completeness definition (§3.2) governs regardless of route; if batch export is later enabled, Q-G3 compares the two routes on the same invented-literal probe before either carries a customer query | Everything A unblocks, plus a server-side fallback if it is ever enabled | Two contracts to maintain and review; the first customer query must run on one route only (no duplicate customer queries across routes); reviewer burden (R3) |

## 7. Return contract and closing record

- **Counts unchanged:** 3/30 dossiers; 0/2 actual weekly readouts; 5 reporting groups + 1 capacity decision (C1);
  candidate HOLD; E7 90+30 not admitted (update 01 §6). These counters overlap and are not summed.
- **Status:** `pass` for the administrative deliverable (all seven required-content items present; every claim
  cited to a record/section or to the probe bytes; no number, admission, approval or authority supplied; one file
  written). **G1–G3 remain BLOCKED; nothing is adopted by this file.**
- **Input hashes:** the 7 inputs and the dispatch manifest are listed with full SHA-256 and byte length in §1.1;
  all matched on `sha256sum` before any input was relied on. **Output hash:** this file cannot contain its own
  digest; its SHA-256 and byte length are computed after the exclusive-create write and reported in the worker's
  return message to the chief.
- **Next named accountable owner and action:** **CEO/founder** — record one of the §6 options as the G1 access/route
  decision (dated; with the R2/R8 settlements if A or C). **COO** — prepares the Q-G2 query-route receipt template
  **only after that decision**, then names the Q-G3 review scope. No operator dispatch, probe, customer query or
  consumer change before the decision and the entry gates. Stop condition for any successor: hash mismatch,
  missing field, concurrent writer, any connector or network call from a management context, any customer or
  participant data, any invented number.
- **Actual new calls / spend / reservations / external changes by this worker:** provider calls **0**; DeepSeek
  spend **USD 0.000000**; reservations **0**; ledger writes **0**; external mutations **0**; PostHog or other
  connector calls **0**; network calls **0**; customer queries **0** (no git write, GitHub, cloud, gcloud/gh/curl,
  test, server, code, config, flag, pricing, registration, invitation, subscription, probe or measurement action).
  Files written: exactly one (this file). Agents spawned: 0. Passive reads beyond the inputs: `git rev-parse`,
  `git branch --show-current`, existence check of this output path. These zeros are observed for this worker's own
  actions; ordinary session/platform overhead is unmeasured and not claimed as zero.
- **No further writes; no background work is claimed after this handback.**
