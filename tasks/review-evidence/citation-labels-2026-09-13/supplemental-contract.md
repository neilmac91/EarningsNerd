# Source-owned supplementary passage contract proposal

September 13, 2026. Unpaid design only. No repository, model, network or production changes.

## Decision

An optional supplementary-passage field is technically backwards compatible, but **cannot by itself remove ASML's unsupported confirmatory sentence from today's free-form answer**. The safe immediate sequence is finish truthful source-match attribution, retain the entailment finding, then specify the answer-generation contract before implementing a new field as a claimed fix. Do not build a field that merely duplicates the current Sources list and declare the defect resolved.

## Existing contract and lifecycle

There is no standalone Copilot Pydantic response schema in the inspected service path. `backend/app/routers/summaries.py:434` consumes `answer_filing_question`; that service emits dictionary SSE events. In `copilot_service.py:1170–1205`, ordinary answer text is yielded incrementally before the citations trailer is available. At :1299–1311, terminal `complete` contains authoritative `answer`, `citations`, `grounded`, `kind`, `followups` and telemetry. Text excerpts are validated by exact normalized source occurrence; fact markers have additional numeric/concept/currency adjacency guards. Neither establishes semantic entailment of arbitrary prose.

Frontend `features/filings/api/copilot-api.ts:36–43` declares `CopilotCompletion`; its :247–258 terminal parser copies only known fields, so an added server field is ignored by older clients. Token buffering is discarded at completion. `AskCopilotRail.tsx:266–282` appends tokens then replaces the message with terminal content/citations. `CopilotMessage.tsx:447–450` renders raw streamed text and later final Markdown with chips. Therefore a terminal-only cleanup could still expose the unsupported sentence during streaming. This is a product behavior constraint, not merely a JSON type change.

## Minimal optional field, if a source-owned channel is pursued

Proposed terminal-only `supplementary_passages?: [{citation_n: integer}]`, absent on legacy/not-disclosed paths. Each item refers to an existing final resolved text citation, whose excerpt, accession-derived URL and source match are already validated by the backend. No duplicate excerpt, untrusted caption, arbitrary model HTML, causal explanation or section-based claim of authority is needed. The application owner selects/deduplicates eligible entries after source verification and final marker numbering; the model cannot directly populate trusted final objects. Render with a fixed “Filing excerpt” attribution and the actual excerpt/source navigation. Do not increment grounded counts twice or silently redefine `verified`.

This minimal form is useful only for citations already present in the final answer. A truly separate channel whose passages have no inline marker needs its own stable source references, explicit occurrence/numbering behavior and Sources deduplication; `_resolve_citations` intentionally omits declared-but-unused candidates. Do not bypass that protection by indiscriminately surfacing every model-declared citation. For a first prototype, require passages to reference existing retained text sources, and acknowledge that this is representation only.

Frontend change would add optional parser validation (array, bounded positive integer IDs, existing matching citation), message storage, and a fixed attributed block. Absent field preserves today's rendering. Old clients still see the complete legacy answer and citations. New clients must not hide the original answer simply because the optional field exists. No database migration is established as necessary by this session-local interface; check persistence readers before claiming that universally.

## How to prevent the unsupported prose

There is no trustworthy current field identifying a “supplemental confirmation sentence.” A model-generated sentence can mix quantitative restatement with useful legal/operational context. Removing all text-cited sentences, regex-matching “confirms”, or stripping [3] alone is not a safe separation.

A generation contract could instead ask for primary `answer` plus a separate list of source passages, with the supplemental channel offering no prose field. The code would render only its generic attribution. This prevents extra assertions **inside that channel**, but the model can still put the same unsupported assertion inside free-form `answer`. A prompt prohibition does not prove otherwise—the current prompt already forbids redundant tool-value text citations and stitched quotations.

To guarantee elimination of the actual ASML class, one must either (a) own the complete response for a genuinely supported, strictly bounded structured numeric question, leaving all other questions on their existing route, or (b) introduce a broader structured claim/evidence answer contract with a conservative admission policy. Neither can be honestly derived from this one case as a tiny supplementary-field fix. Option (a) requires its own evidence that question intent, metric identity, accounting basis, dates and units are fully known; missing raw tags cannot establish US-GAAP-versus-IFRS semantics. Option (b) is a larger product change and risks dropping legitimate qualitative answers. No implementation is recommended until those boundaries and fallback behavior are concrete.

For either approach, avoid rendering unchecked supplemental content in token events. Buffer only a structurally separate new channel until validation; keep the existing qualitative answer streaming behavior unless an explicit broader contract requires changing it. A complete-answer buffer would be a latency/product tradeoff requiring review, not an invisible implementation detail.

## Locked anchors and prerequisites

The inventory in `lessons/test-contract-tests-are-locked.md` and `tasks/architecture-refactor-plan.md:668–677`, including later T3/T4 corrections, locks summary SSE, background generation, auth, subscription webhook, expired trial, scan, refresh replay, companyfacts and frontend summary-stream anchors. It does **not** name ordinary Copilot citation/parser tests as locked. T1/T10 cover the filing-summary stream, not this Copilot stream. T5 does exercise Copilot entitlement gating; leave authorization, taste accounting and its assertions unchanged. An optional Copilot completion field with absent-field compatibility therefore does not, by itself, establish a required founder locked-contract decision. If actual tests require modifying any named anchor, stop and present the exact contract change first; do not infer a lock solely from “stream” in a filename or assume API additions exempt existing anchors.

Root still owns publication, full backend/frontend gates, before/after paid evaluation and any flagged product boundary. This document grants no new spend or source access.

## Concrete prototype review criteria

Use the retained PR842 ASML run 0 and exact source as a regression, plus its two clean numeric-only runs and actual qualitative text-citation cases. Preserve both primary fact chips and their accession/amount/currency/duration identity, exact source excerpt and URL, followups, error/not-disclosed behavior, unmatched markers and legacy completion behavior. Demonstrate whether the confirmatory sentence is absent in **both tokens and final answer**, or explicitly state that it remains unresolved. Prove unique qualitative explanations survive. Add one meaningful mutation proof for the eventual source-owned channel invariant, not tests that merely mirror the optional field shape.

Recommended next slice is a reviewed design choosing the narrow numeric-answer owner versus broader answer contract, with real examples and explicit unsupported fallbacks. Until then the honest deliverable is the attribution improvement and this bounded unresolved finding, not a speculative parser.
