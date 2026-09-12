# EdgarTools capability audit for EarningsNerd

## Implementation checkpoint — September 9

The selected-filing fallback defect documented below was fixed and production-verified in #785; dates, segment shares and return-basis corrections shipped in #784/#787/#788. Excerpt provenance shipped in #789. Source-response provenance #792 has local and paid Copilot clearance but its final summary regression is held on DeepSeek balance exhaustion, not accepted from its advisory green badge. The original findings below are evidence, not a claim those shipped defects remain unfixed.

The SDK investigation and offline experiments are complete. No experimental evidence selector, incorporated-report acquisition, typed accounting parser, new vendor or EdgarTools upgrade has shipped. The next implementation requires the measured coverage/identity controls below and actual funded output acceptance.


EarningsNerd should retain EdgarTools and use more of its existing structured-document capabilities before considering a replacement. The current pin, **5.56.0**, already supports the most useful building blocks: filing-specific facts, statement presentation, role-scoped dimensions, calculation relationships, structured tables, document sections/chunks/search and attachment access. The principal quality gap is the application’s selection and interpretation of evidence after extraction. A newer SDK cannot itself correct a wrongly named operating-income metric, a double-counted segment denominator, or an omitted cash-flow explanation.

This research examined repository checkout `c1bc866bfd61ba04b3f5f69ab629f5c8de8571b7`, its exact installed 5.56.0 distribution, public upstream documentation and retained filing evidence. It found one confirmed application boundary defect to fix first and a separate SDK rendering trap to account for when designing evidence packages; the latter was not reproduced in the retained production sections. No production query, new SEC download, model call, dependency installation or repository edit was performed.

## Version and evidence boundary

`backend/requirements.txt:52` pins `edgartools==5.56.0`; `requirements.in:40` specifies the floor. The installed distribution under `work/edgar-maintenance-venv/lib/python3.11/site-packages/` independently reports 5.56.0, MIT licensing and Python ≥3.10. Upstream’s tagged release exists and highlights changes to dimensional relationships, calculation arcs, footnotes and previously broken document chunks. These are available now, not proposed 6.0 features. [Tagged 5.56.0 release](https://github.com/dgunning/edgartools/releases/tag/v5.56.0).

The latest documentation also describes **6.0 in development**, including silent changes to section content, fact DataFrames and error semantics. Treat those pages as discovery aids, then check the installed source and fixtures. Do not upgrade solely because a method appears in a latest-doc example. [6.0 migration guide](https://edgartools.readthedocs.io/en/latest/upgrade/6.0/).

ADR 0003 had stale 5.40.1 and blanket breaker wording. This documentation PR corrects it to the verified 5.56.0 pin and CLAUDE rule 5 transport boundaries, preserving the accepted consolidation decision.

## What is used and what is available

| Capability verified in installed 5.56.0 | Actual EarningsNerd use | Quality opportunity and constraint |
|---|---|---|
| `Company.get_filings` with recent-window filtering | Used, with accession resolution, cached companies, cheap listing metadata and `trigger_full_load=False` on listing paths | Preserve this work. Do not call `obj`, `html`, `period_of_report`, search or attachments once per listing row: properties can trigger downloads. |
| `filing.xbrl().facts.query()`; concept, date, dimension, unit and text filters | Exact concept queries are used; application selects filing-period durations, currency and dimensioned segment facts | Keep accession/date/currency checks. Add source concept/label/statement role and start/end/basis to canonical metrics rather than flattening to a display number. |
| Filing-specific `xb.statements`, as-reported views, `to_dataframe(standard=False, include_unit=True, include_point_in_time=True)` | As-reported statement extraction mainly serves financial-institution revenue profiles; generic filers use ordered concept lists | Extend exact accounting-basis handling to operating/pretax/net income, attributable/consolidated income and cash-flow classifications. Do not blindly accept SDK standardized labels: existing bank code documents a fee-income-to-revenue mapping hazard. |
| `XBRL.axes_for_role`, `domains_for_role`, `calculation_linkbase` and relationship weights | No calls found in audited application extraction paths | Preserve role-scoped member hierarchies and elimination relationships. Useful for Intel parent/child segments, issuer extension concepts and debt components. A calculation graph is evidence, not a universal reconciliation guarantee. |
| `report.document.sections`; section metadata, tables and full document parsing | Used through `obj`, but application returns only financials/MD&A/risk strings | Include controls, legal proceedings, repurchases and subsequent-event context when relevant. Retain section provenance and coverage status; numbering varies by form. |
| `parse_html` on retained HTML; `Document.tables`, `chunks`, `search`, `to_markdown` | Native document parsing is indirect; no use of native chunks/search/table objects found in audited summary paths | Parse once from the owned HTML fetch, index locally, select whole passages and tables, and retain document/node/section locators. Avoid another network-bearing filing object call just to parse the same content. |
| `filing.attachments`, `exhibits`, `Attachment.text/markdown`, same-filing grep | 6-K extractor uses press releases, then SixK text; 10-K/10-Q/20-F section extraction does not inventory attachments | Resolve **same-accession** incorporated financial exhibits such as NVO’s annual-report exhibit. Explicitly distinguish an attachment from a reference to another accession; the latter remains outside filing-only summaries. |
| XBRL footnote relationships; text facts | Not used in audited extraction paths | Targeted supplemental evidence for tagged disclosures. XBRL footnotes are fact-linked annotations, not a promise that every accounting note is represented; use full document notes too. |
| Company facts, stitched multi-filing financials, AI context helpers/MCP | Separate companyfacts service exists for labeled multi-period analysis; generic latest-company financials remain a summary fallback | Company-wide APIs belong to labeled longitudinal surfaces. Convenience context helpers and hosted MCP do not enforce chosen-filing provenance or guaranteed completeness. |

SDK source locators: `_filings.py:1597,1859,2138,2166,2181`; `documents/__init__.py:47`; `documents/document.py:885,942,963,1029,1190,1277`; `xbrl/facts.py:232–765`; `xbrl/statements.py:1041`; `xbrl/xbrl.py:415,432,459,2714`. Application locators: `edgar/client.py:335`; `edgar/instance_extractor.py:218,599,764,922`; `edgar/xbrl_service.py:234,292,487`; `edgar/sixk_extractor.py:73`. Public descriptions: [filing attachments](https://edgartools.readthedocs.io/en/latest/guides/filing-attachments/), [calculation relationships](https://edgartools.readthedocs.io/en/latest/xbrl/guides/calculation-linkbase/), [XBRL footnotes](https://edgartools.readthedocs.io/en/latest/guides/xbrl-footnotes/).

## Confirmed defect: chosen-filing fallback is not exclusive

`edgar/xbrl_service.py:709–736` tries the selected filing instance, companyfacts, then `Company.get_financials()`. The last API reads the company’s latest annual financials, which need not be the selected filing. `_extract_from_dataframe` at lines 928–944 then writes the **requested accession** onto those unrelated statement values. Separately, companyfacts selection at lines 1038–1099 prefers matching accessions but retains other accessions when no matching fact exists. This violates the filing-only boundary during fallback even though the primary path is filing-aware.

Concrete failure: a user selects an older quarterly filing whose instance extraction fails. Companyfacts lacks the selected accession for a concept, so a newer annual value can be returned as current; if both earlier paths are empty, latest annual financials can be stamped with the quarterly accession. `summary_pipeline.py:479–489` extracts and persists the returned data without an accession rejection. `extract_standardized_metrics` receives no requested-accession argument and normalizes away that field, so downstream rendering cannot reliably recover the mismatch.

Two independent refutations failed. First, the fallback order reduces frequency but never checks equality at the last resort; the existing `test_fetch_uses_latest_financials_as_last_resort` explicitly accepts this branch. Second, an offline probe executing only the two unchanged pure source methods returned an `other-filing` companyfact for a `chosen-filing` request, and relabeled a synthetic latest-financials row `chosen-filing`. Evidence: `work/edgartools-fallback-smoke.json` and reproducible script beside it. No claim is made that any of the 52 retained summaries actually traversed this fallback; production incidence needs separately authorized observation.

**Recommended first fix:** require exact accession for every fallback fact; never substitute latest-company financials unless its source accession is independently identical. Preserve genuine missing data as missing and make extraction coverage explicit. Gate this at the boundary, before persistence and all model-facing surfaces. Review locked-test inventory before touching any existing test; the current fallback behavior being tested does not make it consistent with rule 2.

## Confirmed SDK trap: text can silently shorten a cell

Installed `TableStyle.simple()` sets `max_col_width=500` (`documents/renderers/fast_table.py:65–86`); the renderer shortens longer cell contents at line 640. `Document.text` exposes `table_max_col_width`, but its documentation says `None` means unlimited while the default path falls through to the bounded table renderer. The setting does not automatically make the entire document complete.

A network-disabled local smoke used a 919-character table cell ending `END_SENTINEL`. Default `text()` and explicit `table_max_col_width=None` both lost that marker. Explicit width 10,000 and `to_markdown()` preserved it. This demonstrates the exact default behavior in 5.56.0; it does not establish Markdown’s fidelity on every complex filing. Evidence: `work/edgartools-table-smoke.json` and script. The full review already needed recovery supplements for this class of loss, including Intel narrative cells and Walmart auditor evidence.

**Recommended evidence-package design:** distinguish canonical source storage from presentation rendering. Retain full table-cell content and headers; when producing text, size the rendering to actual cell contents or emit structured/Markdown tables with explicit completeness checks. Do not use a fixed 10,000-character value as a universal guarantee. Check original labels, signs, currency, period headings, colspan/rowspan and long narrative cells against the retained HTML. Keep source offsets/locators stable or version the transformation so citations do not point at a different text representation.

### Production-path refutation (September 9 follow-up)

The full-document renderer result above must not be generalized to every production section. The installed table-of-contents section callback traverses HTML text directly and ignores table-width kwargs; it does not use the bounded table renderer. A subsequent offline comparison of all 26 retained filings found identical text across 526 sections (499 TOC, 27 pattern) with default and source-length-derived widths. No production long-cell loss is established; no real heading-method section was present. A real 646-character KO cell survives the current TOC path. Fix only a demonstrated affected path; do not introduce a fragile parser workaround merely because the standalone renderer probe fails. The source/evidence package must still preserve full cells and explicitly verify its own transformation.

## Where evidence is lost today

`ai/extraction.py:414–433` budgets 10-K and 20-F financials/MD&A/risk at **70k/55k/45k characters** and 10-Q at **50k/45k/25k**. `assemble_excerpt_from_sections` takes each prefix at line 478 and caps the combined result at 320k. Dense-window recovery is conditional on financials being below 5k or MD&A below 3k; a long but incomplete prefix therefore does not receive later-note recovery. This is deterministic selection loss, not a model-context-limit mystery.

The offline retained KO Q1 2026 filing parsed with 5.56.0 in 0.45 seconds on this machine: financials 80,218 characters, MD&A 58,473, Part II legal proceedings 12,716, controls 999, 49 tables and 187 chunks. Network connections were blocked. The current selector necessarily shortens the first two and never selects legal proceedings or controls as separate sections. This is one local example, not a Cloud Run latency benchmark. Evidence: `work/edgartools-capability-smoke.json`.

Use a coverage inventory over the full selected filing: every section/table/attachment either retained, deliberately excluded with reason, or unavailable. Retrieve relevant complete passages across that inventory, including middle and end notes. A retrieval hit does not prove completeness; retain mandatory topics for debt, liquidity funding, contingencies, controls, subsequent events and non-GAAP reconciliation, with entity-specific applicability. Avoid forwarding an entire million-character report or blindly extending all three prefixes.

## Connections to reviewed defects

| Reviewed issue | Better use of EdgarTools | Additional EarningsNerd responsibility |
|---|---|---|
| KO conditional later-year tax exposure; XOM 2026 investment guidance; Intel 14A risk | Broader sections plus local retrieval spanning notes and later MD&A | Rank materiality, preserve conditional language, distinguish “not in excerpt” from “not disclosed”. |
| ASML €6.2B factoring; Sea $4.7B loan funding; Intel $1.327B financing capex; KO fairlife comparator | Whole cash-flow tables and linked note passages, classification labels and prior comparators | Define FCF; explain timing and recurring core funding. Do not mechanically subtract every factored receivable or replace company measures without reconciliation. |
| Intel duplicated Products/CCG/DCAI percentages; Sea empty segment-profit columns | Role-scoped dimensions, presentation hierarchy, note tables and issuer concepts | Prevent parent-child addition; label segment profit versus consolidated operating income and show elimination/unallocated reconciliation. Current 0.5–2.0 revenue-sum guard cannot detect all hierarchy errors. |
| XOM pretax labeled operating income; COIN EBITDA exclusion error | As-reported statement concepts and actual reconciliation table | Preserve metric meaning; validate arithmetic and included/excluded components. Neither problem is fixed by generic semantic search alone. |
| Sea debt absence; ASML commercial paper omission; Intel resolved Apollo risk | Debt-note tables, subsequent events and accession-bound retrieval | Combine debt components with maturity dates, distinguish net cash from no debt, and update historical risk with subsequent resolution. |
| NVO financials incorporated into Exhibit 15.1 | Same-accession attachment inventory and targeted document resolution | Verify incorporation, accession and accounting basis; never follow arbitrary external/other-filing references into the summary. |
| WMT/COIN rounding and date labels | Exact XBRL values, period start/end and statement headers retained in a canonical record | Render all representations from one calculation source, with declared quarterly/annual and denominator basis. |

These mappings identify plausible engineering causes and remedies, not promises that a particular API automatically fixes each output. The frozen Codex/Fable comparison contains the exact findings and severity adjudications. Existing evidence already present in G but ignored by the model—such as Sea segment profit—requires structured extraction and acceptance checks, not additional retrieval alone.

## Prioritized implementation sequence

**1. Provenance boundary and measured completeness.** Fix the cross-accession fallback: exact chosen-accession rejection, no mislabeled fallback values and deliberate missing-input status. Separately record source coverage/renderer version before introducing more data. The full-cell preservation invariant belongs to the canonical evidence-package transformation; no production parser patch is justified by the currently refuted long-cell generalization. Neither step requires a new vendor.

**2. Canonical filing evidence package.** Parse owned retained HTML once; preserve sections, full tables, headings and source identity; inventory same-accession attachments. Add explicit extraction statuses for unsupported, missing, timed out and complete. Acceptance must include KO, Intel, WMT and NVO exhibit evidence. The package should feed the existing summary orchestrator and judge consistently; it must not become a second generation pipeline.

**3. Statement and dimension semantics.** Build typed metric/segment records from the same filing instance and as-reported tables, carrying concept, label, currency, scale, duration, accounting basis, parent/member and role. Validate Intel hierarchy, XOM pretax, Sea segment profit, ADR EPS and foreign-currency comparatives. Use calculation arcs for cross-checks where supplied; preserve raw signs separately from presentation signs and allow missing calculation networks.

**4. Budgeted completeness retrieval.** Replace prefix-only selection with local structural chunks and topic retrieval, keeping adjacent definitions/table notes and deduplicating overlapping passages. Explicitly report topics absent from the retrieved view. Measure coverage improvement on all retained 26 filings without new generation first. Token estimation must be measured: `chunks` promises target token size, not an exact provider-token budget.

**5. Generation and evaluation acceptance.** Only after offline evidence/semantic checks pass, perform the authorized bounded live evaluations through the existing orchestrator. Use the corrected full-review rubric and exact retained source packages; distinguish extraction misses from reasoning errors and complete from partial judge coverage. Keep universe-wide pregeneration held until the founder’s world-class quality condition is met. An SDK upgrade or green legacy recall score alone is insufficient.

## Cost, deployment and upgrade risks

The open-source SDK introduces no per-filing licence charge; this is distinct from hosted EdgarTools services. Existing HTML and XBRL can support substantial offline work without new SEC traffic or model spend. Additional attachment downloads consume SEC request/egress budgets; additional parsed structures consume memory/CPU; better retrieval can increase or decrease LLM input depending on selection. Those costs must be measured rather than inferred from the small KO smoke.

Keep all network-bearing APIs inside the existing transport owners and shared admission policy. `filing.grep()` searches attachments by default and can initiate many reads; `Company.get_financials`, `filing.obj`, XBRL and attachment properties can hide downloads. Prefer local `parse_html`/document search when the owned bytes already exist. Timeouts around synchronous executor work do not reliably stop the underlying CPU task; avoid unbounded parser concurrency or fleet-wide jobs. SDK-local throttling is not proof of a shared fleet SEC budget.

SDK model/section confidence values are extraction heuristics, not confidence that a summary is correct. Role unions cannot replace role-specific axes. XBRL linked footnotes are incomplete coverage of prose notes; imported taxonomy typing remains a documented limitation. Section aliases, text renderers and DataFrame display signs are behavior, not merely interfaces: pin them with representative fixtures before any future dependency bump. The current pin already has the needed capabilities, so a 6.0 upgrade is not a prerequisite for this plan.

A production change remains subject to full local gates, locked-contract boundaries, exactly one mutation proof per new invariant, review lenses, applicable eval/re-pin rules and serial deployment verification. This research recommends no new provider, raw SEC bypass, blanket corpus replay, paid tool subscription or production flag change.

## Source inventory

1. EarningsNerd current pin and application source at checkout `c1bc866bfd61ba04b3f5f69ab629f5c8de8571b7`: `backend/requirements.txt`, `app/services/edgar/{client,compat,xbrl_service,instance_extractor,sixk_extractor,statement_parser}.py`, `app/services/ai/extraction.py`, `app/services/summary_pipeline.py`; local read access.
2. Installed EdgarTools 5.56.0 source and distribution metadata at `work/edgar-maintenance-venv/lib/python3.11/site-packages/`; exact method/file locators above. [Upstream repository](https://github.com/dgunning/edgartools), [release v5.56.0](https://github.com/dgunning/edgartools/releases/tag/v5.56.0).
3. Upstream documentation: [overview](https://edgartools.readthedocs.io/en/latest/), [attachments](https://edgartools.readthedocs.io/en/latest/guides/filing-attachments/), [calculation linkbase](https://edgartools.readthedocs.io/en/latest/xbrl/guides/calculation-linkbase/), [fact footnotes](https://edgartools.readthedocs.io/en/latest/guides/xbrl-footnotes/), [6.0 migration](https://edgartools.readthedocs.io/en/latest/upgrade/6.0/). Latest documentation was checked against installed source where recommendations rely on a method.
4. Retained filing evidence and frozen reviews under `outputs/fable-full-review/cases/`, `outputs/codex-full-review/`, and comparison `work/codex-fable-comparison/agent-c.json`. These are selected-filing evidence, not live production observations.
5. Reproducible offline probes: `work/edgartools-capability-smoke.py/.json`, `work/edgartools-table-smoke.py/.json`, `work/edgartools-fallback-smoke.py/.json`. The fallback probe executes source-identical pure methods only; it is not an integration test or production incident measurement.

## Alternatives: bounded validation tools, no new production dependency

Arelle is a possible **offline independent validator** for XBRL relationship/calculation checks when a concrete EdgarTools discrepancy survives. Its supported Python Session API shares global state and is not thread-safe; independent processes are required for parallel sessions. EarningsNerd previously removed Arelle from serving dependencies under ADR 0003, so this proposal does not restore it to the request path. Calculation consistency would not prove that an analysis interpreted a metric correctly. [Arelle Python API](https://arelle.readthedocs.io/en/latest/python_api/python_api.html), [XBRL validation concepts](https://www.xbrl.org/the-standard/what/key-concepts-in-xbrl/validation/).

Docling merits a retained-document experiment only for PDF or complex incorporated exhibits that the pinned parser cannot preserve. Its structured JSON/HTML serializations retain merged-cell information; Markdown loses some of that structure. Compare full cell text, period headers and row/column spans against original bytes before accepting its output. Measure memory and latency; installing an additional document stack is not necessary for the first quality fixes. [Docling serialization documentation](https://docling-project.github.io/docling/concepts/serialization/).

SEC-API could provide a commercial extraction comparison if a measured gap remains. Its advertised startup plan is for internal use; redistribution or a paywalled product requires the appropriate enterprise licence, so the low advertised plan is not an established EarningsNerd option. No purchase, contact or integration is proposed now. [SEC-API pricing and usage rights](https://sec-api.io/pricing).

The priority is to use the already-installed library more carefully, validate exact accounting semantics and preserve source completeness. Reconsider an alternative only against an explicit failing fixture and measured operating cost; none changes the selected-filing provenance requirement.

## Selection follow-up decision — September 9

The [general-selector experiments](evidence-selection-experiments-2026-09-09.md) did not justify production integration. They recovered some confirmed missing inputs while displacing other material passages or excluding unresolved source structure. The next safe stage is truthful observed excerpt provenance, followed by complete source assembly and explicit association/budget rules. Intel 14A was present in the actual retained generator context and remains a synthesis issue. These results narrow the earlier capability opportunities; they do not justify a larger prompt or an SDK replacement.

## Source identity follow-up

The current document owner already returns decoded HTTP response text, including inline XBRL for HTML filings. Offline PFE and XOM probes preserve that exact string with one mocked HTTP request, exposing namespace URI, original fact IDs, context/entity/dates, unit and scale directly from retained HTML. SDK fact tables alone lose namespace bindings and cannot prove expanded identity from a us-gaap prefix. Preserve optional source representation metadata through the existing owner; label its hash decoded-response-text UTF-8, never original wire bytes.

This supports a later conservative offline concept audit without another SEC request. It does not yet prove a complete parser or justify automatic operating-income relabeling: malformed namespaces, duplicate IDs, continuations, ambiguous context, currencies and independently valid calculations require unknown outcomes or source adjudication. Serving classification waits for positive identity evidence and shared-surface coverage.

## Incorporated reports and legal-section identity

NVO's primary 20-F directly links Exhibit 15.1 in the same accession directory. Its already-retained 10,592,851-byte annual-report HTML supplies adjusted -5% to -13% CER outlook with the nonadjusted basis, approximately DKK 8 billion restructuring and acquisition-affected cash-flow context absent from the primary. The embedded 6-K cover does not change the containing 20-F accession. The USD 4.2 billion 340B disclosure already exists in the primary and is not evidence of an attachment gap. No new source request was necessary for this investigation.

Pinned SDK attachment APIs can inventory that link, but its download shortcut would bypass the application's transport owner. Current buffered fetching has no streaming size ceiling or per-hop identity check; a bounded same-accession acquisition change needs its own reviewed transport limits before automatic attachment inclusion.

Legal section lookup also needs identity validation. On retained files, the correctly Part-qualified BYND legal key returned an inventory note, while Intel's span crossed multiple sections. Empty lazy TOC child lists cannot prove zero tables or paragraphs. An observed section key/hash/length is useful inventory; it is not a certificate of content identity or completeness. Generic legal selection must validate actual boundaries and preserve unknown cases. KO's tax exposure is also present after the current canonical prefixes, so a legal section is a compact alternative source, not the only one; the selection experiment records the whitespace-sensitive correction.

## Production-only metric backfill finding

The source-label review exposed a separate application defect: generic label inference maps income/profit labels to net income and arbitrary margin labels to net margin when filling missing prior values. This production pipeline step is outside the baseline generation evaluation path. A narrow identity-safe backfill fix therefore precedes further instruction changes or automatic pretax relabeling. Unknown labels should keep missing comparison values rather than inherit another accounting measure.

## September 12 — current-Flash evidence and implementation order

The [archived current-Flash reviews and scoped designs](review-evidence/current-flash-2026-09-12/README.md) supersede speculative claims about which old narrative errors recur. Some old BA/RIVN/JD/NVO defects do not recur; source ownership, units, financial meaning and comparative direction still need work. The original reports remain verbatim with a separate ASML carrying-amount correction.

First finish #808 metadata/citation acceptance and serial production verification; its first summary assessment proves unchanged data plus qualified cash/debt tags, not correct total-debt narratives. First Copilot17/18 failed on source-present excerpts below the verifier minimum. Corrected `0e6b076b3e1112c7e11fb3170b64c941d880a18f` passed2,878 tests/29 warnings in83.93s; second assessment is pending. The independently gated cash-basis candidate `e9dbe8b991cfd393033f88e277c434d9e3540cc5` passed2,885 tests/29 warnings in85.80s and remains unpublished. #819 and E06 reconciliation/configuration are complete, with future natural payment attribution still unverified.

Then prioritize source-unit preservation (COST's primary already received the millions header), a source-owned tax/continuing-income relationship and later explicit adjustment-table relations, restricted numeric comparisons, and guidance coverage. The unit design requires selected source passages with governing unit context, not a global dollar multiplier. The semantic registry must bind entity, period, measure, sign, units and accounting basis together; no amount collision, global cue, model-authored inclusion flag or calculation/presentation edge certifies business causation. Both designs distinguish useful metadata from visible corrections and unknown source scope. Retain good explanations and qualify missing evidence rather than deleting all interpretation.

No source-unit/semantic implementation, paid assessment, new public contract or quality clearance is claimed by these designs. Original founder prerequisites, locked anchors and financial-quality/pregeneration holds remain unchanged.

### September 12 — bounded Copilot acceptance update

[Second #808 Copilot assessment](review-evidence/current-flash-2026-09-12/pr808-second-copilot-acceptance.md) passed18/18 across three draws per six questions. Two ASML answers remain without citations; another answer's closing sales citation has narrower scope than the repeated sentence. Preserve these limitations. Separate summary CI34691090937, with two repeats per filing, remains pending, as do #808 merge and production verification. This updates the preceding assessment status without changing the broader quality priorities or holds.

### September 12, 11:39 UTC — metadata change merged; semantic limits remain

[Final summary acceptance](review-evidence/current-flash-2026-09-12/pr808-flash-summary-second-acceptance.md) clears data/metadata conservation and execution accounting. #808 merged as `f0a81fff216c318a40979b7dfcd55500c8b43a03`; main CI34691615781 and production verification remain pending. WMT and COIN still omit borrowing components in one summary each; both ASML summaries omit the current portion. These observations reinforce the distinction between source metadata and correct source-qualified aggregation. No financial-quality/pregeneration clearance follows from this bounded release.

### September 12, after deployment — provenance release complete

The [verified release record](review-evidence/current-flash-2026-09-12/README.md#september-12-1147-utc--808-production-verified) supersedes all pending #808 gates, assessments, merge and deployment instructions above. Main CI `34691615781` and deploy job `103548163219` succeeded: migrations 0/39, revision `earningsnerd-backend-00331-tfm` at 100%, healthy CI and independent detailed health. Do not repeat those completed actions.

Proceed with the separate cash-basis candidate, integrated at `37401e996c980fbdf01306fcb1472601b31c2eed` with 2,888 passing tests. Integrate later documentation and gate committed state before publication and actual-output assessment. Then continue source-unit and source-owned explanation work in the priority order above. Remaining financial findings and all specific founder prerequisites, including universe-wide pregeneration and historical replay, remain open. E06 configuration is complete; future natural delivery is unobserved.

### September 12 — comparative backfill prerequisite already completed

The earlier “Production-only metric backfill finding” is resolved by [#797](https://github.com/neilmac91/EarningsNerd/pull/797), merged as `4ba05087a04969e0391ac4e0efcfd1b5bef99eb3` on September 9. Current `backend/app/schemas/summary.py` uses `_PRIOR_METRIC_KEYS` whole-label lookup in `_infer_xbrl_metric`, consumed by `attach_normalized_facts`; percentage margins also require an explicitly percentage-valued current row. Do not rebuild that completed prerequisite. This correction leaves genuinely unimplemented source-unit and source-owned explanation work in the order above.


## September 12, after #823 merge — current continuation correction

This dated correction supersedes older instructions to publish or assess #808, cash basis or source-unit quote context; retain those records as history and do not repeat completed paid assessments. #821 is merged and production-verified: main CI `34699536585`, migration tail `applied=0 skipped=39`, revision `earningsnerd-backend-00332-p9k` at 100%, and healthy CI/independent detailed checks. The [cash-basis archive](review-evidence/cash-basis-2026-09-12/README.md) retains both assessment rounds and exact deployment evidence.

#823 merged as `d2c176f6019b3dbef431b44f55a7c635f8cf4a36` at 2026-09-12T14:54:28Z after the final 2,906-test gate and accepted bounded summary/Copilot assessments. [Source-unit evidence](review-evidence/source-unit-2026-09-12/README.md) preserves both original mutation proofs, 52 summary outcomes and 18 Copilot answers. Main CI `34700643792` is running; verify its migration tail, serving revision and both health checks before another backend merge. No #823 production result is claimed yet.

The next quality work is actual authored-guidance unit preservation, source-qualified debt scope and a finite capital-allocation relationship consumer that corrects false comparisons while preserving valid program/highlight text. Source metadata alone or a correct paragraph beside contradictory prose is not a closed finding. Instance duration/context feasibility is under review; do not reconstruct missing starts or broaden locked contracts. COST authored guidance, broader accounting/issuer cash-flow explanations, and previously sampled numerical failures remain open. #805 stays held; no wholesale revival is authorized. E06 awaits natural payment delivery only. Existing master-plan founder prerequisites and universe-wide pregeneration/historical replay holds remain unchanged.


## September 12, after #823 production verification — current continuation

This dated correction supersedes the preceding production-pending instruction. Main CI `34700643792` and deploy job `103572015821` succeeded. Migrations reported `applied=0 skipped=39` at 14:59:08.2960343Z; revision `earningsnerd-backend-00333-56s` serves 100% of traffic. CI detailed health was healthy at 15:00:48.5214041Z (database 6.52 ms); independent detailed health was healthy (database 6.27 ms, server timestamp `1789225367.402431`; Redis disabled, SEC circuit closed). The independent response is retained privately in `work/pr823-independent-health.json`. [Source-unit release evidence](review-evidence/source-unit-2026-09-12/README.md) retains bounded acceptance and original proofs. Both #821 and #823 are now merged and production-verified; do not repeat their assessments or releases.

Continue actual authored-guidance unit correction, source-qualified debt scope and the finite capital-allocation relationship consumer, preserving valid analytical and program text. No parallel correct paragraph beside contradictory prose counts as completion. Source-side descriptor feasibility is design evidence, not a shipped numerical fix. Previous findings, original master-plan prerequisites, #805 hold, natural E06 delivery observation and universe-wide pregeneration/historical replay holds remain unchanged.


## September 12 — #825 production verified; current continuation

This dated record supersedes earlier current HOLD, unpublished and release-pending instructions for the supported authored-guidance unit correction. #825 merged as `473558ec259e5c4860cd0373ee4209289bb17167` at 17:55:30Z. Main CI `34709660590` and deploy job `103596329864` succeeded. Migrations reported `apply_migrations: applied=0 skipped=39` at 18:00:25.9058631Z. Revision `earningsnerd-backend-00334-pqv` serves 100% of traffic, confirmed at 18:01:14.1872642Z and explicitly at 18:01:15.7139218Z. CI detailed health was healthy at 18:01:53.6718523Z (database 7.16 ms). Independent `curl -fsS` exited 0 and returned healthy (database 7.9 ms, server timestamp `1789236229.8216112`; Redis disabled, SEC circuit closed). [Release evidence](review-evidence/authored-guidance-release-2026-09-12/README.md) preserves the fourth scoped acceptance and links all three earlier failed rounds; no prior verdict or usage uncertainty was rewritten.

- [x] Complete #825 correction, actual fourth assessment and serial production verification.
- [ ] Continue source-qualified debt and financial relationship design that preserves valid explanation; metadata or parallel contradictory prose is not a completed fix.
- [ ] Retain unsupported guidance/recovery/source-coverage cases and broader numerical/accounting findings for bounded future work.

No further #825 assessment is required by this record. World-class quality and universe-wide pregeneration/historical replay remain held. Original master-plan prerequisites remain in effect; E06 natural delivery is unobserved and E09 remains proposal-only with incomplete fleet/egress/budget evidence.
