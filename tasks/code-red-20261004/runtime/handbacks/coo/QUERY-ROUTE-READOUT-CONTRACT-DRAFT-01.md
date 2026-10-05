# Query-route readout contract — DRAFT 01 (COO worker `coo-query-route-contract-draft-01`)

**Status: DRAFT for acceptance by the founder with the CEO. Nothing in this file is adopted, authorised, dispatched,
queried or run.** The founder adopted **option C** on 2026-10-05 (decision record 08, §"Founder instructions", row 3):
keep PostHog ticket 76581 open and prepare the query route without spending or accessing customer data beyond existing
authorization. This file is that preparation: the contract of `REPORT-ROUTE-PROPOSAL-01` §3 made executable for G1–G5
(§2), the operator-identity rule as a decision for the founder with the CEO, not assumed (§3), a dry-run plan that
costs nothing and reads no customer data (§4), what is and is not settled (§5), risks with owners (§6) and the return
contract (§7). MASTERPLAN-REVIEW §3B governs: no substitute reporting contract is silently approved. No participant
count, threshold, budget, cost or policy number is supplied; no connector, network or production call was made; no
customer or participant data was read. G1–G3 remain BLOCKED until this contract is accepted and the access decision for
the chosen route is explicit (record 08, row 3).

## 1. Identity, inputs, observation date, authority and limits

| Item | Value |
|---|---|
| Worker role label | `coo-query-route-contract-draft-01` (COO-owned wave R3, reporting groups G1–G3; lane: beta operations; label pre-registered in closure 151 per record 08) |
| Dispatch | `tasks/code-red-20261004/runtime/dispatch/COO-QUERY-ROUTE-04.json`, SHA-256 `49cb15b715c89da6ababd538a0a7bff9477be4405d40f4614d5bab1e32fb744c`, 5,482 bytes (both verified before reading); recorded 2026-10-05T18:36:02.037958+00:00 by the chief (session `01GWYV7WXWstgVGQG43YcSM8`); requested model inherited `claude-fable-5-1`; one active writer for this output: true |
| Runtime limitation | This worker **cannot observe its own served model or its runtime/session id**; the chief resolves the provisional label and registers the identity in the next exclusion closure. Not read here. |
| Observation date | Manifest and all eight inputs verified 2026-10-05T18:38Z; file written 2026-10-05T18:39Z–18:46Z and trimmed for length once before handback (UTC). |
| Repository state | Branch `claude/vigilant-goodall-633yx3` at `1b5e0a47` (passive reads: `git rev-parse`, `git branch --show-current`, `git status --porcelain` clean). The manifest names `e1b00514`; `git merge-base --is-ancestor` confirms it is an ancestor of HEAD and the only later commit is the manifest's own (`1b5e0a47`). A wording deviation, not a content one: every input hash matched at HEAD. No other repository file was opened. |
| Authority | **COO drafts; the founder with the CEO accepts.** COO owns closure of G1–G5 (FIRST-DELIVERABLE five-group table). MASTERPLAN-REVIEW §3B: "determine a concrete supported export/readout route and its evidence first. No substitute reporting contract is silently approved here." **Option C adopted by the founder 2026-10-05** (record 08, founder instructions row 3). Record 07 handed the query-route evidence to the COO; `REPORT-ROUTE-PROPOSAL-01` §6 set the three options; this draft is the preparation option C permits and nothing more. |
| Available authority of this worker | Administrative/management only; excluded from source A/B authorship, reconciliation, semantic financial review and blind judging. Read-only except this one file. No git write, network, connector call, customer query, test, cloud or production read. Zero provider calls, reservations and spend. |
| Not read, by rule | Source packets, candidate outputs, judge material, customer or participant data, credentials, anything under `tasks/readiness-2026-09-21/acceptance/` or `/root/.claude/uploads/`, and any file outside the manifest's inputs (the probe response bytes are relied on as quoted in the proposal §1.2). |

### 1.1 Inputs verified (sha256sum and byte length compared to the manifest BEFORE any input was relied on)

| Label | Path | SHA-256 | Bytes | Match |
|---|---|---|---:|---|
| COO report-route proposal 01 (three options; option C adopted) | `tasks/code-red-20261004/runtime/handbacks/coo/REPORT-ROUTE-PROPOSAL-01.md` | `0916b5f27190cb7805b561d82498552697375071f14121b5a91901ce24017810` | 33854 | match |
| Decision record 08 (option C decision; operator-identity question; no spend, no customer data) | `tasks/code-red-20261004/runtime/control/DECISIONS-08.md` | `9a19701dab44f1ef1f8827a3c7355b6a10d72404892c75dcb965c52adfe2be91` | 13211 | match |
| Decision record 07 (query-route evidence; caps labelled connector-stated) | `tasks/code-red-20261004/runtime/control/DECISIONS-07.md` | `0f511f5a9f6eeb97cd59886b732cb96adc6828d16373d1fae57198b980897bf0` | 18305 | match |
| COO disposition revision 1 (§5 G1–G5, R4) | `tasks/code-red-20261004/runtime/handbacks/coo/CURRENT-BETA-OPERATING-ENVELOPE-DISPOSITION.md` | `d30bdd50125ae304ad5c4fd1c6559326d3767c0f17c1ca7ec41d895ab6fc13be` | 40291 | match |
| COO disposition update 01 (§5 G1–G5, R4; §1.2 private-store denial) | `tasks/code-red-20261004/runtime/handbacks/coo/CURRENT-BETA-OPERATING-ENVELOPE-DISPOSITION-UPDATE-01.md` | `07ebaaf3f1433460a6b78738314152ba00b7caeba0bbbcf447e0374cf959fdeb` | 37570 | match |
| Decision record 02 (D5 privacy; D2 identity registration; D9 refuter record) | `tasks/code-red-20261004/runtime/control/DECISIONS-02.md` | `4d93171f68c7491afd70fcd54b19a355093c5f2a14b437d02c4fd13d3f4f508b` | 21885 | match |
| COO first deliverable (G1–G5 definitions, C1) | `…/scratchpad/handover/officers/coo/references/FIRST-DELIVERABLE.md` | `c82773953be1e85daa87525003d1ade26db4e8f8e9df428f97fff80d10ee3f7f` | 15184 | match |
| Masterplan review (§3B; §4 R3/R4 rows) | `…/scratchpad/handover/officers/cto/evidence/MASTERPLAN-REVIEW.md` | `0c946f93c801bbb98836aab9c11b789d7748d88bf8894f3fbf57d0370399c710` | 21877 | match |

The `…/scratchpad` prefix is `/tmp/claude-0/-home-user-EarningsNerd/27aa9761-b14a-5cab-9ee6-5f8ec27f49f3/scratchpad`.
**8/8 matched.** Path references inside these documents were treated as metadata and not opened.

### 1.2 Facts this contract relies on, each with its source

| # | Fact | Source |
|---|---|---|
| F1 | The official PostHog MCP `execute-sql` (HogQL) route ran one invented-literal query on project **117863** (timezone UTC) at 2026-10-05T17:07Z and returned one row; response 193 bytes, SHA-256 `c9c1961ec63b04f26842b9878fe18c77e7e36b397e420a26dc35c5df0cff9b0b` | record 07 §"G1/G2"; proposal §1.2 |
| F2 | The response echoes the query text under `query.query`; `results` is pipe-delimited text (header, then rows); a `toDateTime('YYYY-MM-DD HH:MM:SS')` literal rendered `…T00:00:00Z`; no row count, limit, offset, `hasMore` or run id in the response | proposal §1.2 (a)–(d) |
| F3 | A 100-row default cap and a 500-row maximum are **stated by the connector's `execute-sql` command description as read in the chief's session on 2026-10-05, not independently verified and not stated by the tool schema** | record 07 "What it does not show"; binding note |
| F4 | The connector was attached to the chief's interactive session; the chief context ran the probe itself, permissible only because no collected data was touched | record 07 §Registration; proposal §3.4 |
| F5 | `project-get` returns two public client tokens; they are recorded nowhere | record 07; proposal §3.3 |
| F6 | The repository is public; rows, raw responses, roster membership and full context identities live in private stores; the repository keeps sanitized receipts and SHA-256 hashes | record 02 D5 |
| F7 | A context's identity is reported before any executive context reads its output and is registered in the next exclusion closure | record 02 D2 |
| F8 | Ticket 76581 is retained and not resent; G1–G3 stay BLOCKED until the contract is accepted and the access decision for the chosen route is explicit | record 08 row 3 |
| F9 | The 2026-10-05 readout receipt's files were **not** copied to a private store (classifier denial, not pursued); the retained store is a GitHub Actions artifact that expires | update 01 §1.2 last row |
| F10 | G5's readout must carry the frozen roster/denominator and exclusions, UTC half-open window, source availability, exact query/parameters/consumer identity, hashes, completeness, observed outcomes, session-linked usefulness, citation/problem/support evidence and honest cost coverage, plus one fixed-roster combined-window receipt for later-ISO-week different-filing return | FIRST-DELIVERABLE G5 |

## 2. The query-route readout contract — executable shape for G1–G5

### 2.0 Conventions that apply to every query below

- **Placeholders.** `{{…}}` marks a value bound to a literal in the retained receipt **before** the text is sent. The
  text sent contains no braces; HogQL's own `{variable}` mechanism is not used, so the response echo `query.query`
  (F2) shows the bound literal and the reviewer can compare it byte for byte. Window placeholders are always
  `{{window_start}}` and `{{window_end}}` in the form `YYYY-MM-DD HH:MM:SS`, UTC (the form F2 proved); the window is
  **half-open**: `>= toDateTime('{{window_start}}')` and `< toDateTime('{{window_end}}')`. `{{window_end}}` precedes the
  first call's timestamp (elapsed windows only, F10).
- **No literal customer identifier appears in this file.** `{{member_key}}` is the column that identifies a roster
  member (bound at G3's schema confirmation, §2.3); `{{roster_predicate}}` is the predicate over the frozen eligible
  roster (bound from the G4 packet, §2.4). Any bound text containing roster literals is **private**; its SHA-256 is
  public (F6).
- **Event vocabulary.** `{{event_*}}`, `{{prop_*}}` and `{{table}}` are placeholders for event names, property names
  and the collected table as the project schema names them. They are **bound by the Q-G3 schema confirmation, not
  invented here**; no event name in this file is a claim about what the product emits.
- **Count bracket (Q-C).** Every result set is bracketed by a count query with the **identical** `FROM … WHERE` clause:
  `n_before` immediately before page 0 and `n_after` immediately after the terminal page; for a `GROUP BY` result the
  count is `count(DISTINCT <group key>)` (the number of result rows), and a second `count()` records the number of
  underlying events the aggregate summarises. Both responses are retained.
- **Pagination rule (every row-level or grouped result).** Explicit `LIMIT {{L}} OFFSET {{k}} × {{L}}` on every page,
  `k = 0 … K`, contiguous, text identical across pages except the OFFSET literal, `ORDER BY` a total order on a key
  whose uniqueness Q-G3 confirmed from the schema. `{{L}}` never exceeds the route's maximum; the default cap is never
  relied on implicitly. The **100-row default and 500-row maximum are reported by the connector's `execute-sql`
  description on 2026-10-05, not independently verified; confirm on first use and record** the confirmed values (F3).
  Terminal page = first page with fewer than `L` rows (an empty page is valid). `complete` only when
  `n_before = n_after = Σ rows`, every non-terminal page has exactly `L` rows, no non-terminal page returned exactly
  100 rows while `L ≠ 100`, and keys are `Σ rows` distinct values; otherwise `incomplete` with the failing rule;
  connector error, denial or timeout = `source-unavailable` (an unknown, not zero). No `hasMore=false` fabricated, no
  concatenation workaround, no partial re-paging (proposal §3.2 rules 1–10, carried unchanged).
- **Retention rule.** Private store (CEO-designated; §6 K2): query text as sent (every page and both counts), the
  window, every response as returned (bytes unmodified), each response's SHA-256 and length, row count per page, UTC
  timestamp per call, operator context id. **Repository:** SHA-256 of each query text and of each response, row counts,
  window, `L`, `K`, `n_before`, `n_after`, verdict, status, role labels — hashes and counts only; never a row, a roster
  literal or a token (F5, F6). Templates and invented-literal probe texts contain no customer identifier and may appear
  in the repository as this file does.
- **Denominators.** `N` is the frozen eligible roster size, carried by reference and hash from the G4 packet;
  exclusions by count and hash; a roster member absent from a result is recorded "not observed in window" and read
  only with the source-availability record — never as zero use, never as success; `N` is never reduced to make a ratio.
- **Operator.** No query in §2.4–§2.5 runs before the §3 decision is recorded, the operator's identity is registered
  in the exclusion closure and the entry gates hold. §2.1–§2.2 contain only invented literals.

### 2.1 G1 — supported access (query route)

| Field | Content |
|---|---|
| Purpose | Dated evidence that a supported, non-batch-export route exists on project 117863, and the **explicit access decision** that G1's exit requires for whichever route is adopted (record 07; §5.2 below says what it must contain). |
| Query text(s) | **Q-G1-a** (connector command, not HogQL): `project-get` — retained per run as id, name, timezone with the two public client tokens redacted (F5). **Q-G1-b** (done, record 07): `SELECT 1 AS probe_a, 'alpha' AS probe_b, toDateTime('2026-10-05 00:00:00') AS probe_c` — invented literals, no `FROM`, no window (there is no collected table to window). |
| Denominators | Not applicable (no roster, no customer data). |
| Count bracket | Not applicable to a one-row literal `SELECT`; the retained row count is 1. |
| Pagination | Not applicable; no `LIMIT` was sent, so the probe neither confirms nor refutes the caps (F3). |
| Retention | Q-G1-b's response is already retained (193 bytes, SHA-256 `c9c1961e…`, F1); it contains no customer data and its hash is public. Q-G1-a's redacted identity confirmation is retained per run (proposal §3.3). |
| Q-G3 checklist items that apply | Provenance (project identity per run; route named; tokens absent); query text byte-identical to the echo. |
| State | Evidence exists; **decision absent**. BLOCKED (record 08 row 3). |

### 2.2 G2 — complete literal query receipt

| Field | Content |
|---|---|
| Purpose | Prove the receipt mechanism end to end on invented literals — format, half-open window, LIMIT/OFFSET paging, count bracket, hashing — so the first customer query, when authorised, is not the first exercise of any rule. The format probe (Q-G1-b) is done; it exercised neither paging nor counting (proposal §4 G2). |
| Query text(s) | The six dry-run probes **P1–P6 of §4**, each a `SELECT` over a literal subquery (no collected table in any `FROM`), plus the page/count **template** below, whose placeholders are bound only at G5. |
| Template — page `k` | `SELECT {{projected_columns}} FROM {{table}} WHERE {{event_time}} >= toDateTime('{{window_start}}') AND {{event_time}} < toDateTime('{{window_end}}') AND {{roster_predicate}} ORDER BY {{order_key}} LIMIT {{L}} OFFSET {{k_times_L}}` |
| Template — count | `SELECT count() AS n FROM {{table}} WHERE {{event_time}} >= toDateTime('{{window_start}}') AND {{event_time}} < toDateTime('{{window_end}}') AND {{roster_predicate}}` |
| Denominators | Not applicable to literal probes; the template carries `{{roster_predicate}}` so that `N` enters only by reference. |
| Count bracket | P2 brackets P1 (expected count equals the literal set size, stated in §4); the template count runs before page 0 and after page K. |
| Pagination | P1 exercises three contiguous pages and the terminal rule on a literal set; P5 exercises the connector-stated caps (F3) — the observed default and maximum are **recorded** as "confirmed on <date>" in every later receipt. |
| Retention | Probe responses contain no customer data: bytes, SHA-256, length and row counts may be public; stored under the proposal §3.1 receipt template so the template is itself exercised. |
| Q-G3 checklist items that apply | Query text (echo identity across pages except OFFSET); parameters (`L` explicit, `K` consistent); page inventory; count reconciliation re-derived from responses; hashes re-computed; format (delimiter, newline, null, numeric rendering — P6). |
| State | BLOCKED behind G1's decision; the dry-run itself needs the CEO's R7 decision (§4). |

### 2.3 G3 — independent review of query receipts (Q-G3)

| Field | Content |
|---|---|
| Purpose | A named independent read-only reviewer records `accept` / `reject` / `incomplete` on the actual retained receipts and private responses, re-deriving completeness from bytes rather than from the operator's verdict (proposal §3.5). |
| Query text(s) | **None against collected data.** The reviewer re-hashes every private response, re-derives `n_before = n_after = Σ rows` and key distinctness from retained bytes, and compares each retained query text to the response echo. **One schema confirmation** precedes any G5 binding: `{{order_key}}` unique per row of `{{table}}`; `{{member_key}}`, `{{event_time}}` and each `{{event_*}}`/`{{prop_*}}` present with the expected types. Source, in order of preference: PostHog's published schema documentation (no project access); or the connector's schema command — its command list as presented to this session on 2026-10-05 includes a `read-data-schema` name beside `execute-sql` (seen in the tool description only; **not invoked, capability not verified**). Whether a schema read of project 117863 is within "existing authorization" is **open question Q2 for the founder** (§7): it reads no rows but reveals collected event and property names. |
| Denominators | The reviewer checks that `N`, exclusions and unobserved members are preserved and that unknowns are not coerced. |
| Count bracket | Re-derived, not re-run: the reviewer never issues a fresh customer query to "fix" a mismatch; a conflict between `n_before` and `n_after` is recorded, not resolved by choice. |
| Pagination | The reviewer checks the OFFSET sequence, the terminal-page rule, the cap-hit rule and that the recorded cap confirmation (P5) exists. |
| Retention | The review record is public (verdict, failing rule numbers, hashes compared); the reviewer's context id is private (F6); its label is registered in the closure before it reads any response (F7). |
| Checklist (the ten proposal §3.5 checks) | Query text · Parameters · Window · Page inventory · Count reconciliation · Hashes · Format · Duplicate/conflict rules · Denominator semantics · Provenance. Each records pass / fail / not-applicable with the receipt field read. |
| Consumer rule | The released consumer stays unchanged until this review justifies a bounded change; the CTO supplies a minimal implementation writer only if a reviewed real contract demonstrates the need (FIRST-DELIVERABLE G3). The format finding (pipe-delimited `results` versus the consumer's bounded JSON) is a review output, not a pre-decided adapter. |
| State | BLOCKED behind G2; needs the named reviewer and real receipts. |

### 2.4 G4 — private cohort, offered-scope and support control packet (what the query route adds)

| Field | Content |
|---|---|
| Purpose | The route adds exactly one dependency to G4: the **frozen eligible roster and exclusions must exist, by hash, before any `{{roster_predicate}}` is written** (proposal §4 G4). G4's other contents are unchanged and outside this contract. |
| Query text(s) | **None run.** The packet yields the bound predicate shape: `{{roster_predicate}}` := `{{member_key}} IN ({{roster_member_literals}})`, where `{{roster_member_literals}}` is the eligible roster after exclusions, bound from the packet. Exclusions are **not** queried: they are applied by absence from the literal set and carried by count and hash. The bound predicate text is private; its SHA-256 and the packet hash it was bound from are public. |
| Denominators | `N` = size of the eligible roster in the frozen packet (by reference and hash). Observed members per window ≤ `N` by construction. |
| Count bracket | For every G5 query: `SELECT count(DISTINCT {{member_key}}) AS n_members FROM {{table}} WHERE {{event_time}} >= toDateTime('{{window_start}}') AND {{event_time}} < toDateTime('{{window_end}}') AND {{roster_predicate}}` — the number of roster members observed in the window, compared to `N`; the difference is the "not observed in window" count. |
| Pagination | Not applicable to the packet; whether a single `IN (…)` literal list of size `N` is accepted by the route is confirmed by P4 on an invented set of comparable shape (§4) — no number is set here. |
| Retention | The packet is private (FIRST-DELIVERABLE G4: no names in any shared bundle); the repository holds the packet hash, `N`, the exclusion count and the predicate hash. |
| Q-G3 checklist items that apply | Query text (no identifier or predicate outside the authorised roster/window); denominator semantics (roster hash in the receipt equals the packet hash; `N` unchanged across both weekly windows and the combined window). |
| State | INCOMPLETE; owners unchanged (founder, CPO, CTO, CFO; CEO integrates). No invitation, data collection, inferred consent, start date, flag, registration or pricing change. |

### 2.5 G5 — actual cohort observation (the two weekly readouts and the combined-window receipt)

| Field | Content |
|---|---|
| Purpose | Two dated weekly readouts and one fixed-roster combined-window receipt (F10), one receipt per query under §2.0. Fields the route can carry: observed request/view outcomes, first useful summary, citation use, repeat use, failures. Fields it **cannot** carry: support burden (support mailbox), cost per successful analysis (provider telemetry, spend ledger), reviewed session-linked usefulness (session review) — joined to the readout by roster key and window from their own evidence routes, never by querying PostHog for them. |
| Q-G5-1 per-member activity | `SELECT {{member_key}} AS member, count() AS events_in_window, min({{event_time}}) AS first_event_utc, max({{event_time}}) AS last_event_utc, count(DISTINCT toDate({{event_time}})) AS active_days FROM {{table}} WHERE {{event_time}} >= toDateTime('{{window_start}}') AND {{event_time}} < toDateTime('{{window_end}}') AND {{roster_predicate}} GROUP BY member ORDER BY member LIMIT {{L}} OFFSET {{k_times_L}}` |
| Q-G5-2 first useful summary and citation use | `SELECT {{member_key}} AS member, countIf(event = '{{event_summary_useful}}') AS useful_summaries, minIf({{event_time}}, event = '{{event_summary_useful}}') AS first_useful_utc, countIf(event = '{{event_citation_used}}') AS citation_uses FROM {{table}} WHERE {{event_time}} >= toDateTime('{{window_start}}') AND {{event_time}} < toDateTime('{{window_end}}') AND {{roster_predicate}} AND event IN ('{{event_summary_useful}}', '{{event_citation_used}}') GROUP BY member ORDER BY member LIMIT {{L}} OFFSET {{k_times_L}}` — what counts as "useful" is the CPO's offered-scope definition bound to an event name at G3; not decided here. |
| Q-G5-3 failures | `SELECT {{member_key}} AS member, count() AS failures, count(DISTINCT {{prop_filing_id}}) AS filings_affected FROM {{table}} WHERE {{event_time}} >= toDateTime('{{window_start}}') AND {{event_time}} < toDateTime('{{window_end}}') AND {{roster_predicate}} AND event IN ({{event_failure_list}}) GROUP BY member ORDER BY member LIMIT {{L}} OFFSET {{k_times_L}}` |
| Q-G5-4 combined-window different-filing return | Window = the union of the two weekly windows as one half-open interval. `SELECT {{member_key}} AS member, toISOWeek({{event_time}}) AS iso_week, count(DISTINCT {{prop_filing_id}}) AS distinct_filings FROM {{table}} WHERE {{event_time}} >= toDateTime('{{window_start}}') AND {{event_time}} < toDateTime('{{window_end}}') AND {{roster_predicate}} AND event = '{{event_filing_viewed}}' GROUP BY member, iso_week ORDER BY member, iso_week LIMIT {{L}} OFFSET {{k_times_L}}` — "later-ISO-week different-filing return" is derived client-side per member from the retained rows (a filing identifier present in a later week and absent from the earlier), the derivation recorded in the receipt; the query asserts nothing. `toISOWeek` acceptance is proved by P4 (§4). |
| Row-level fallback | Only where a readout field needs rows, the §2.2 page template with `{{projected_columns}}` limited to the fields the readout names; aggregates are preferred (proposal R1). |
| Denominators | `N` from the G4 packet; each Q-G5 result lists observed members only; `N − n_members` are "not observed in window"; `source-unavailable` on any call makes the whole window unknown (not zero) for that readout. |
| Count bracket | For each Q-G5 query, two counts with the identical `FROM … WHERE` (including the `event` filter): `count(DISTINCT {{member_key}})` (result rows, run before page 0 and after page K) and `count()` (underlying events). Agreement rule as §2.0. |
| Pagination | As §2.0. A grouped result has at most `N` rows (Q-G5-4: `N` × ISO weeks in the window); if that is ≤ `L`, page 0 is terminal **and must still return fewer than `L` rows**, otherwise a second page is fetched. No participant count is assumed. |
| Settle rule | Late-arriving events can move `n_before`/`n_after` (proposal R9). The delay between `{{window_end}}` and the first call is a policy the COO with the CEO record when the first window is authorised; none is set here. |
| Retention | As §2.0; the readout record also names, per field, the evidence route that supplied it (query, support, ledger, session review) so no PostHog-derived figure is presented as covering a field it cannot. |
| Q-G3 checklist items that apply | All ten; denominator semantics and provenance are decisive. |
| State | QUEUED; **0/2 actual weekly readouts**; nothing here changes that count. Two elapsed windows cannot be parallelised away. |

## 3. Operator-identity rule — a decision for the founder with the CEO (not decided here)

**Standing rule (proposal §3.4, carried):** an executive context never runs a customer query. Chief/CEO, COO, CTO, CFO,
CPO sessions and every management worker — this one included — are excluded; record 07's chief-run probe (invented
literals only) is the ceiling for an executive context. The readout operator is a separately named, non-executive,
bounded context, excluded from source authorship, reconciliation, semantic financial review and blind judging, whose
identity is registered in `control/source-context-exclusion-<n>.json` **before** it runs (label public, context id
private — F6, F7); executive contexts receive only counts, hashes, status and verdict.

**Fact the decision must start from (F4):** the PostHog connector is today attached only to the chief's interactive
session — an executive context that must never run a customer query. **One further observation, stated carefully:** the
tool roster presented to this worker on 2026-10-05 lists a PostHog `exec` tool among the deferred tools (schema not
loaded; **never called**). A child context spawned inside the chief's session is therefore *presented* with the
connector; that does not show a call would succeed, and it does **not** make such a worker an eligible operator: its
transcript is readable from the parent session through session tooling, so "without the executive context seeing
responses" is not established. It narrows proposal R2 (presentation evidenced; function and isolation not).

| Option | Which non-executive context runs a customer query | How its identity is registered before any run | What it requires from the founder | What it does not settle |
|---|---|---|---|---|
| **O1 — Dedicated non-executive remote session** | A separate Claude Code Remote session for the readout lane only: no executive role, no access to source packets or judging material, the PostHog connector attached in **that** session's configuration; dispatched by the CEO under a hash-bound manifest | The CEO pre-registers the role label in the next closure; the session id is recorded privately on creation and resolved in the closure **before** the first customer query; the closure entry names the window and query set authorised | The founder attaches the connector to that session or its environment (an account action only the founder can take), confirms the authorization is the existing one (no new scope, no plan change), and states in the G1 decision that this session kind may read project 117863 for the beta readout | Whether the connector can be attached to a non-interactive or scheduled session; whether its transcript is isolated from the chief's session (a statement from configuration — proposal R2); the private store (K2) |
| **O2 — Founder-operated run with a hashing script** | The founder, as account owner with existing authorization, runs the bound queries in PostHog's own SQL interface or a local founder-side session; a read-only script computes per-response SHA-256, length and row count and emits the sanitized receipt; no AI executive context sees rows | A named human operator role, recorded by label in the closure; no AI context id is created; the receipt names "founder-operated" as the consumer identity | The founder's time for every page and count call of every readout; a founder-side script in the style of the custody-check tool (record 07) that never prints row contents; the founder's statement that this is within existing authorization | Operator/reviewer independence holds only if the Q-G3 reviewer is a different, non-executive context; the echo check (F2) must be done by the script, not by eye; no scheduled runs |
| **O3 — Child worker of the executive session** | A bounded subagent launched from the chief's session (the connector is presented to such a worker, per the observation above) | As O1 | The founder's explicit acceptance that a context whose transcript is readable from an executive session may run a customer query, with the chief bound not to read it — a rule, not an isolation | **Weakest isolation**: non-reading is a discipline, not a control; the standing rule would need an explicit, recorded exception. Listed for completeness, not favoured by the standing rule |
| **O4 — No operator until G4 exists** | None | None | Nothing now; decided when the frozen roster exists, since no customer query has anything to bind to before then | Leaves G2's paging proof to the dry-run (§4), which needs no operator; delays the operator decision only, not the contract |

The COO draws no conclusion among O1–O4. The founder with the CEO records one option, dated, in the G1 access decision
(§5.2); until then, no context — executive or otherwise — runs a customer query on this route.

## 4. Dry-run plan — costs nothing, reads no customer data, **not executed by this worker**

Purpose: exercise every query *shape* of §2 with invented literals so that syntax acceptance, result shape, pagination
mechanics and the hashing procedure are proved before any customer query. Every probe is a `SELECT` whose only `FROM`
is a subquery over literal arrays; **no collected table is named in any `FROM`**. No probe reads customer data, so under
record 07's ceiling an executive context could run them; **whether and by whom is the CEO's decision (proposal R7)**;
this worker runs none. Record 07 states such calls are covered by the existing PostHog plan (dated 2026-10-05); no
DeepSeek call; no spend. If the route rejects a construct, the rejection is a recorded finding and the shape is
re-expressed with an accepted construct — the expected counts are properties of the literal sets, not of the route.

| Probe | Shape exercised | Query text (invented literals) | Proves | Cannot prove |
|---|---|---|---|---|
| **P1** | Row pages, LIMIT/OFFSET, terminal rule | `SELECT k AS probe_key, concat('row_', toString(k)) AS probe_label FROM (SELECT arrayJoin([1,2,3,4,5,6,7,8,9,10,11,12]) AS k) ORDER BY probe_key LIMIT 5 OFFSET 0` then `… OFFSET 5`, `… OFFSET 10` — expected 5, 5, 2 rows; the third page is terminal (`2 < 5`) | OFFSET arithmetic, contiguity, stable order on a literal key, the terminal-page rule, per-page hashing | Completeness on a changing real table; key uniqueness on `{{table}}`; behaviour at `N` rows |
| **P2** | Count bracket | `SELECT count() AS n FROM (SELECT arrayJoin([1,2,3,4,5,6,7,8,9,10,11,12]) AS k)` — expected `12`, run before P1 page 0 and after P1 page 2 | `n_before = n_after = Σ rows` mechanics; the `results` text rendering of a count | That counts are stable on real data between bracket calls |
| **P3** | Half-open UTC window | `SELECT t FROM (SELECT arrayJoin([toDateTime('2026-01-01 00:00:00'), toDateTime('2026-01-01 12:00:00'), toDateTime('2026-01-02 00:00:00'), toDateTime('2026-01-02 00:00:01')]) AS t) WHERE t >= toDateTime('2026-01-01 00:00:00') AND t < toDateTime('2026-01-02 00:00:00') ORDER BY t` — expected 2 rows: the start boundary included, the end boundary excluded | Boundary semantics of `>=`/`<` with `toDateTime` literals; UTC rendering (F2 c) | Timezone of real `{{event_time}}` values; late-arrival effects |
| **P4** | Grouped aggregate, `IN (…)` literal set, `toISOWeek`, `count(DISTINCT)` bracket | `SELECT m AS member, count() AS n_events, count(DISTINCT f) AS distinct_filings, toISOWeek(t) AS iso_week FROM (SELECT arrayJoin([('m1','f1',toDateTime('2026-01-05 10:00:00')),('m1','f2',toDateTime('2026-01-13 10:00:00')),('m2','f1',toDateTime('2026-01-06 10:00:00')),('m3','f3',toDateTime('2026-01-14 10:00:00'))]) AS r, r.1 AS m, r.2 AS f, r.3 AS t) WHERE m IN ('m1','m2','m3','m4') GROUP BY member, iso_week ORDER BY member, iso_week LIMIT 100 OFFSET 0` — expected 4 rows; bracket `SELECT count(DISTINCT m) …` with the identical subquery and `WHERE` — expected `3`, so "not observed" = 4 − 3 = 1 (`m4`) | GROUP BY, tuple literals, `IN` over a literal set with an unmatched member, `toISOWeek`, the two-count bracket and the client-side "not observed" derivation | That `{{member_key}}`/`{{prop_filing_id}}` exist with these types; the real roster literal list's acceptance at size `N` |
| **P5** | Caps (F3) | **P5-a**: a `SELECT` over a literal set larger than 100 rows with **no** `LIMIT` — observe whether 100 return (the stated default). **P5-b**: `LIMIT 500` over a set larger than 500 — observe whether 500 return. **P5-c**: `LIMIT 501` — observe acceptance, truncation or error. Sets of that size need a range-generating function (`range(…)` with `arrayJoin`); if rejected, the cap confirmation falls to first use and the receipt keeps "connector-reported, unconfirmed" | The default and maximum as **confirmed on <date>**, replacing F3's "connector-reported" in every later receipt; the cap-hit rule of §2.0 | Plan-level call or query limits (proposal R1, R5); behaviour under load |
| **P6** | Format fidelity of `results` (proposal R6) | `SELECT 'a\|b' AS has_pipe, 'line1\nline2' AS has_newline, NULL AS is_null, 1.5 AS a_float, toDateTime('2026-01-01 00:00:00') AS a_time, '' AS empty_text` (one row) | How a pipe, a newline, a null, a float, a datetime and an empty string are rendered in the pipe-delimited text — the parse rules Q-G3 and any later consumer change depend on | That real property values contain only these cases |

Hashing procedure exercised by every probe: retain the response bytes as returned; compute SHA-256 and length; count
rows by parsing `results` under the P6-confirmed rules; compare the retained query text to the echo `query.query`;
write the sanitized receipt (proposal §3.1 template), probe texts public. **Execution: none by this worker; none
authorised by this file.**

## 5. What the contract settles and does not settle for G1–G5

### 5.1 Per group

| Group | State (update 01 §5; record 08 row 3) | Settled by this draft (once accepted) | Not settled — still required |
|---|---|---|---|
| G1 | BLOCKED | The shape of the access decision (§5.2); the route's dated enablement evidence (F1) | **The explicit access decision itself** (founder with the CEO); the terms question (whether PostHog's terms support the MCP as a reporting route — a documentation read); the operator option (§3); the private store (K2). **Ticket 76581 stays open and is not resent** (F8). |
| G2 | BLOCKED behind G1 | The executable receipt mechanism (§2.0, §2.2) and a dry-run that proves it on literals (§4) | The CEO's R7 decision to run the dry-run; the caps confirmation (P5); the receipt filled for the done probe and each dry-run probe; no customer query before the entry gates and the §3 operator |
| G3 | BLOCKED behind G2 | The review target and the ten-check list (§2.3) | The named independent reviewer; real receipts; the schema-confirmation source (Q2 for the founder); the format finding before any consumer change |
| G4 | INCOMPLETE | The single dependency the route adds (frozen roster by hash before any predicate) and the predicate shape (§2.4) | Everything else in G4, owners unchanged |
| G5 | QUEUED, 0/2 | The query set per readout field, which fields the route can and cannot carry, the combined-window query and its client-side derivation (§2.5) | The settle rule (R9); the event vocabulary binding (G3); the entry gates (R2 quality decision, R3 operating readiness including the C1 HOLD, G1–G4, invitation/consent/start authority); two elapsed windows |

### 5.2 What G1's explicit access decision must say for this route

Recorded by the founder with the CEO, dated, with provenance, before any customer query: (1) the route — official
PostHog MCP `execute-sql` (HogQL) on project **117863**, with record 07's probe as enablement evidence; (2) the
authorizing person and the authorization relied on — the founder's existing account authorization, stating that **no
new scope, plan purchase or plan change** is involved (FIRST-DELIVERABLE G1; MASTERPLAN-REVIEW §3B); (3) the data
scope — the roster-limited, window-limited queries of §2.5 for the beta readout only, not general analytics; (4) the
operator option from §3 and the rule that executive contexts never run a customer query; (5) whether a schema read
(§2.3) is within the same authorization (Q2); (6) the private store for responses and its custody rule (K2), noting
F9; (7) the caps as confirmed or still connector-reported (F3); (8) that the file route is **not** closed — ticket 76581
remains open, not resent, not polled, and if batch export is later enabled Q-G3 compares the two routes on the same
invented-literal probe before either carries a customer query (proposal §6 option C); (9) that the first customer query
runs on one route only; (10) that acceptance of this contract is recorded separately from the access decision, so
neither is inferred from the other (MASTERPLAN-REVIEW §3B).

## 6. Risks with owners

| # | Risk | Why it matters | Owner | Permitted next step (none dispatched here) |
|---|---|---|---|---|
| K1 | Operator isolation (proposal R2, narrowed): the connector is presented to child workers of the executive session; function and transcript isolation are not established | Without a settled non-executive operator, no customer query may run on this route | **Founder with the CEO** (§3); CEO (one dated statement from configuration of which session kinds can hold the connector) | Record the §3 option in the G1 decision |
| K2 | Private store for responses (proposal R8) — F9: the last copy of a receipt to a private store was classifier-denied, not pursued | The first customer query would have nowhere compliant to land | **CEO** designates; founder confirms custody | Designate before any operator dispatch; test the custody path with a dry-run receipt (no customer data) |
| K3 | Caps unconfirmed (F3) | A silent 100-row cap is caught by the cap-hit rule only if `L ≠ 100` | **CEO** (authorise P5); operator records | P5 in the dry-run |
| K4 | Function acceptance on the route (`arrayJoin`, tuple literals, `toISOWeek`, `range`, `countIf`/`minIf`) unverified | A query could fail on syntax, not data; a failure is a finding, not a workaround trigger | **COO** (contract); operator records the rejection | Re-express with an accepted construct; expected counts unchanged |
| K5 | Format fidelity of `results` (proposal R6) | A mis-parsed pipe or newline corrupts counts and denominators | **Q-G3 reviewer**; CTO only if the review shows need | P6 before any parse rule is relied on |
| K6 | Event vocabulary and key uniqueness are bound at G3, not known here | A wrong `{{order_key}}` makes LIMIT/OFFSET slices meaningless; a wrong event name empties a readout field silently | **COO** (binding step); founder (Q2) | Bind from documentation or the schema command only after Q2 is answered |
| K7 | Changing data under paging (proposal R9) | `n_before ≠ n_after` fails honestly and forces a re-run | **COO with the CEO** | Record the settle rule when the first window is authorised; no number here |
| K8 | Plan limits at readout scale (proposal R1, R5) | A route needing a purchase to run is a different decision; a purchase is insufficient for G1 and not proposed | **CEO/founder** | Documentation read of plan query/call limits, with source and date |
| K9 | Fields the route cannot carry (support burden, cost per analysis, session-linked usefulness) presented as covered | Over-claiming the readout | **COO** (evidence route named per field) | §2.5 retention rule |
| K10 | Token exposure (`project-get` tokens, F5) | Must never reach a receipt or the repository | Operator; Q-G3 reviewer (provenance) | Redaction on every run |
| K11 | Two contracts under option C | Reviewer burden; a duplicate customer query across routes | **COO**; Q-G3 reviewer | One completeness definition (§2.0) for both; first customer query on one route only |

## 7. Return contract and closing record

- **Counts unchanged:** 3/30 dossiers; 0/2 actual weekly readouts; 5 reporting groups + 1 capacity decision (C1);
  candidate HOLD; E7 90+30 not admitted (update 01 §6); counters overlap and are not summed. **G1–G3 remain BLOCKED;
  G4 INCOMPLETE; G5 QUEUED. Nothing is adopted, authorised or run by this file.**
- **Status:** `pass` for the administrative deliverable — the manifest's six `required_content` items map to §1, §2,
  §3, §4, §5 and §6–§7. Every claim is cited to a record, a proposal section or a manifest field; no participant count,
  threshold, budget, cost or policy number is supplied.
- **Files written:** exactly one — `tasks/code-red-20261004/runtime/handbacks/coo/QUERY-ROUTE-READOUT-CONTRACT-DRAFT-01.md`
  (this file; exclusive create). Its SHA-256 and byte length cannot be contained in itself and are reported in the
  worker's return message to the chief.
- **Input hashes:** 8/8 matched on `sha256sum` and byte length against the manifest before any input was relied on
  (§1.1); the manifest's own hash and length matched the dispatch message.
- **Actual new calls / spend / changes by this worker:** PostHog or other connector calls **0** (the connector's tool
  name was seen in this worker's tool roster and never loaded or called); network calls **0**; customer or participant
  data read **0**; production reads **0**; provider calls **0**; DeepSeek spend **USD 0.000000**; reservations **0**;
  ledger writes **0**; git mutations **0** (passive reads only: `rev-parse`, `branch --show-current`, `status
  --porcelain`, `merge-base --is-ancestor`, `log` of the one-commit range); agents spawned **0**; invitations, flags,
  pricing, registration, load, probes, measurements **0**. Observed for this worker's own actions; session/platform
  overhead is unmeasured and not claimed as zero.
- **Deviations:** (1) the manifest's `repository_read_scope` commit is `e1b00514`; this worker ran at `1b5e0a47`, whose
  only additional commit is the manifest's own — all input hashes matched. (2) The file exceeded the ~45,000-byte
  guidance on first write and was trimmed once before handback (same single file; no content item removed). No stop
  condition was met.
- **Open questions for the founder (with the CEO):** Q1 — which §3 operator option (O1–O4), recorded in the G1 access
  decision (§5.2). Q2 — whether a schema read of project 117863 (no rows) is within existing authorization, so that
  `{{order_key}}`, `{{member_key}}` and the event vocabulary can be bound at G3. Q3 — the private store for readout
  responses and its custody rule (K2), given F9. Q4 — whether the §4 dry-run (invented literals, no customer data, no
  spend) is authorised and by which context (proposal R7; a CEO decision under option C).
- **Next named accountable owner and action:** **founder with the CEO** — accept, amend or reject this draft and record
  the G1 access decision with the §5.2 contents; **CEO** — decide Q4 and, if authorised, name and register the dry-run
  context; **COO** — on acceptance, fill the §2.2 receipt template for record 07's done probe and each dry-run probe,
  then name the Q-G3 review scope. No operator dispatch, customer query or consumer change before the decision and the
  entry gates.
- **Served model:** this worker cannot observe its own served model; the requested model is recorded in the manifest
  as inherited `claude-fable-5-1`, and the chief resolves the label.
- **No further writes; no background work is claimed after this handback.**
