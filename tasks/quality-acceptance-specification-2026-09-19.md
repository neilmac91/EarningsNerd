# E7 — approved quality acceptance specification and fixed candidate manifest

Prepared 2026-09-19; completed source preparation and offline assessment against checkout `44fd9c4425c7139dbaef1b8707327d3561bab0ce`.

**Founder decision, 2026-09-19:** approved this specification, its exact 30-accession candidate manifest and the USD 10 incremental generator-spend ceiling; reviewer details will follow. The criterion and accession selection are fixed. Independent reference briefs, reviewer/adjudicator commitments and external/untracked exposure attestation remain pending; this is not acceptance of generated quality. The accepted manifest bytes remain unchanged (SHA256 `68242a2c1c57da8d445bc4e1aca104017cffaffe8bbebf131228cde8ea94ba66`). Do not authorize generation until the accession manifest, exclusion audit, human review capacity, current tariffs and enforceable budget control are complete. This is read-only preparation, not quality clearance. No model call, test-suite execution, real app credential retrieval, deployment, production operation or paid run occurred in this preparation. Official SEC identity records were inspected through the read-only web tool, then full public source packets were captured through the existing repository SEC client and limiter. Existing form helpers were assessed offline using those retained sources.

**Freeze status:** rubric, approved ceiling and **30 exact candidate accession identities** were accepted by the founder in [fixed candidate manifest](review-evidence/acceptance-2026-09-19/candidate-manifest.json). The proposed 90 generation identities have no accession match in the audited reachable Git history. This is a concrete candidate manifest, **not yet a frozen unseen acceptance corpus**: all 30 source packets and their hashes are now retained, with offline helper observations below. Independent human material-issue reference briefs, reviewer commitments, untracked-evaluation exposure attestation and execution controls remain prerequisites. Helper coverage gaps are observations for acceptance, not automatic exclusions or proof that the full pipeline fails.

## 1. Scope and prerequisites

The acceptance unit is one selected SEC filing accession through the sole production summary orchestrator, with its own text and XBRL comparatives. Review raw canonical output, every retained preview, final rendered summary, citations and the supported export projection. A correct final value does not erase a materially wrong preview. Copilot and multi-period Analysis require their own acceptance and are not silently included.

Pin a stable source commit, content stamp, provider/model identity, actual response identity when available, all effective AI flags, fallback settings, temperature/thinking settings, extraction/stream settings, dependency versions, token limits and retry settings before generation. Keep the production provider and model. Holdout runs must match the proposed released configuration; no flag is armed by this specification. If E2–E6 change that configuration, record the final candidate before the holdout rather than using these cases for tuning.

Prerequisites are: accepted specification; all source packets and reference briefs frozen; documented exclusion audit; two named human reviewers with relevant filing/accounting competence; a named human adjudicator; offline extraction/citation checks and the separately authorized development smoke/readout completed; audited measurement-only execution path with no live email; enforceable call/token/dollar limits; fresh provider balance and prices; available Fable subscription quota. Missing source coverage is a product defect or an invalid measurement, never evidence that the filing had no disclosure.

This proposal adds no implemented CI gate and changes no golden set, scorer, pinned baseline, production flag or rollout condition. The existing regression gate remains a separate prerequisite. The later out-of-time sample, controlled beta, universe-wide pregeneration and historical replay need their existing separate decisions.

## 2. Severity and acceptance rule

Materiality is qualitative: a defect is material if it could reasonably change a reader's interpretation of results, liquidity, risk, guidance, accounting basis or an asserted financial relationship. A small amount can be material when it reverses a sign or creates a false driver. No percentage threshold excuses that error.

| Severity | Definition and examples | Consequence |
| --- | --- | --- |
| S0 — critical integrity | Wrong selected filing/company or cross-filing contamination presented as filing-only evidence; fabricated source/quotation that materially changes the conclusion; pervasive corruption preventing reliable interpretation. | Stop promotion and further holdout generation pending triage; preserve every attempted output. Affected capability fails. |
| S1 — material defect | Invented amount; wrong sign, period, currency, unit, accounting/consolidation basis; unsupported material cause; misleading source citation; issuer-adjusted FCF represented as conventional FCF; omitted material liquidity, covenant, legal or guidance issue. | Zero allowed. Affected capability fails even if aggregate scores improve. A serious S1 stops the run; stop criterion is impact, not how many other outputs passed. |
| S2 — substantive weakness | Incomplete explanation/coverage that does not reach materiality, a secondary unsupported interpretation, or ambiguity that forces a reader to reconstruct an important part of the filing. | Depresses completeness/usefulness to at most 3 where applicable. Two or more draws for one filing with either score below 4 fail repeatability. |
| S3 — minor defect | Nonmaterial omission, redundant paragraph, small formatting/navigation friction, or wording that preserves the correct financial meaning. | Record and fix through ordinary work; compatible with a score of 4. |
| M — invalid measurement | Missing/duplicate/unrequested identity; generation/judge error; truncated required grounding; missing source hashes; missing retained output or preview association needed for a claimed check. | Not scored as zero and not dropped from the denominator. Acceptance remains incomplete. |

Fabricated quotations and misleading citations are independently unacceptable even if a reviewer labels their immediate effect nonmaterial. Every challenged claim must have an explicit supported/unsupported/unresolved adjudication, with unresolved material claims blocking acceptance.

**All conditions must hold:**

1. Exactly 90 candidate outputs exist: 30 frozen filings × draws 1, 2 and 3. There are no invalid identities, silent exclusions, missing outputs or incomplete adjudications.
2. Zero adjudicated S0 or S1 defects across every in-scope visible surface, and zero fabricated quotations or misleading citations. No aggregate score overrides this veto.
3. At least **86/90 outputs** score **at least 4/5 on both completeness and usefulness on the same output** (ceil(0.95 × 90)). Report the two dimensions separately as well as their joint count.
4. No accession has two or three draws below 4 on either dimension. Report all 30 filing-level triples and each form/sector stratum; do not present the 90 repeated outputs as 90 independent filings.
5. Every source-backed quotation and citation is checked against its actual destination and surrounding context, and every material numeric/causal/financial-basis claim is checked against the selected filing. Missing exposure of a claim to an AI judge does not count as human verification.
6. Existing deterministic regression checks pass independently. Every requested Fable verdict is complete under one frozen contract/model; AI disagreements are adjudicated by humans, not decided by majority vote. Missing judge input or quota exhaustion leaves this acceptance run incomplete until the same retained artifact can be judged.
7. The founder records an acceptance or rejection for the explicitly offered filing classes after reviewing the dossier. A failed class cannot be removed post hoc to manufacture a global pass; a narrowed product scope requires an explicit new decision and the original failed result remains visible.

This sample is an acceptance exercise, not proof of a population-wide defect rate or market superiority. The 30 filings are the independent sampling units; three draws measure within-filing stability.

## 3. Human scoring anchors

Before seeing candidate outputs, both reviewers receive the full selected source packet and independently identify its material issues. Adjudicate and freeze a short reference brief containing each issue, its source location, expected numbers/bases, importance and any honest limits on disclosure. Do not build the reference from model output or a different filing.

| Score | Material completeness | Analytical usefulness |
| --- | --- | --- |
| 5 | Covers every frozen material issue accurately, including important qualifiers and uncertainty. | Prioritizes the issues, explains supported relationships clearly and distinguishes facts, permitted arithmetic and unknowns. |
| 4 | Covers every material issue; only minor omissions or limited nonmaterial context missing. | Accurate, filing-supported explanation a target reader can use, with only minor clarity or prioritization weakness. |
| 3 | Noticeable nonmaterial omissions or missing context; material defects separately trigger S1 regardless of score. | Mainly descriptive or insufficiently prioritized; substantial reader reconstruction needed. |
| 2 | Multiple substantial omissions or misleading coverage. | Little reliable help interpreting the filing; important ambiguity or unsupported reasoning. |
| 1 | Omits or misrepresents the core story. | Unusable or materially misleading. |

Assign scores independently before reviewers see each other's results or AI verdicts. Blind candidate labels and randomize display order; preserve the randomization seed/mapping outside their packets. Human reviewers may know the company because source verification requires it. Agent agreement is not independent human acceptance.

Reference-brief reading, output reviews and adjudication need an explicit time commitment. Planning allowance: two reviewers × (30 source/reference reviews at 45 minutes + 90 candidate reviews at 15 minutes + 30 comparator reviews at 10 minutes) = approximately 100 reviewer-hours total, plus approximately 10 adjudicator-hours. These are scope estimates, not bookings or approved fees. The founder may revise them before freeze; do not silently reduce review coverage to fit availability.

## 4. Proposed exact 30-filing candidate manifest

The machine-readable proposal is [fixed candidate manifest](review-evidence/acceptance-2026-09-19/candidate-manifest.json): 30 distinct issuers, exact SEC accession/form/filing date, selected document and source index links, reporting period, three draw identities, source-status fields and the exclusion audit. This is purposive stratified selection, not a random sample or necessarily each company's latest filing. No candidate outputs were generated or inspected during selection. The fixed eligibility cutoff is 2026-09-19; the selected 2025 foreign filings deliberately remain eligible historical cases rather than being called out-of-time evidence.

| Slot | Issuer | Form | Filed | Financial period end | Exact accession / official SEC index |
| --- | --- | --- | --- | --- | --- |
| H01 | CAT — Caterpillar Inc. | 10-K | 2026-02-13 | 2025-12-31 | [0000018230-26-000008](https://www.sec.gov/Archives/edgar/data/18230/000001823026000008/0000018230-26-000008-index.htm) |
| H02 | DUK — Duke Energy Corporation | 10-K | 2026-02-26 | 2025-12-31 | [0001326160-26-000014](https://www.sec.gov/Archives/edgar/data/1326160/000132616026000014/0001326160-26-000014-index.htm) |
| H03 | O — Realty Income Corporation | 10-K | 2026-02-25 | 2025-12-31 | [0000726728-26-000011](https://www.sec.gov/Archives/edgar/data/726728/000072672826000011/0000726728-26-000011-index.htm) |
| H04 | CB — Chubb Limited | 10-K | 2026-02-27 | 2025-12-31 | [0000896159-26-000005](https://www.sec.gov/Archives/edgar/data/896159/000089615926000005/0000896159-26-000005-index.htm) |
| H05 | GS — The Goldman Sachs Group Inc. | 10-K | 2026-02-25 | 2025-12-31 | [0000886982-26-000091](https://www.sec.gov/Archives/edgar/data/886982/000088698226000091/0000886982-26-000091-index.htm) |
| H06 | CVX — Chevron Corporation | 10-K | 2026-02-24 | 2025-12-31 | [0000093410-26-000078](https://www.sec.gov/Archives/edgar/data/93410/000009341026000078/0000093410-26-000078-index.htm) |
| H07 | TGT — Target Corporation | 10-K | 2026-03-11 | 2026-01-31 | [0000027419-26-000016](https://www.sec.gov/Archives/edgar/data/27419/000002741926000016/0000027419-26-000016-index.htm) |
| H08 | ADBE — Adobe Inc. | 10-K | 2026-01-15 | 2025-11-28 | [0000796343-26-000003](https://www.sec.gov/Archives/edgar/data/796343/000079634326000003/0000796343-26-000003-index.htm) |
| H09 | NTLA — Intellia Therapeutics Inc. | 10-K | 2026-02-26 | 2025-12-31 | [0001193125-26-076550](https://www.sec.gov/Archives/edgar/data/1652130/000119312526076550/0001193125-26-076550-index.htm) |
| H10 | OUST — Ouster Inc. | 10-K | 2026-03-02 | 2025-12-31 | [0001628280-26-013313](https://www.sec.gov/Archives/edgar/data/1816581/000162828026013313/0001628280-26-013313-index.htm) |
| H11 | ABCL — AbCellera Biologics Inc. | 10-K | 2026-02-24 | 2025-12-31 | [0001703057-26-000012](https://www.sec.gov/Archives/edgar/data/1703057/000170305726000012/0001703057-26-000012-index.htm) |
| H12 | WM — Waste Management Inc. | 10-K | 2026-02-09 | 2025-12-31 | [0001104659-26-012049](https://www.sec.gov/Archives/edgar/data/823768/000110465926012049/0001104659-26-012049-index.htm) |
| H13 | CRM — Salesforce Inc. | 10-Q | 2026-05-28 | 2026-04-30 | [0001108524-26-000127](https://www.sec.gov/Archives/edgar/data/1108524/000110852426000127/0001108524-26-000127-index.htm) |
| H14 | AMD — Advanced Micro Devices Inc. | 10-Q | 2026-08-05 | 2026-06-27 | [0000002488-26-000123](https://www.sec.gov/Archives/edgar/data/2488/000000248826000123/0000002488-26-000123-index.htm) |
| H15 | BIRD — Allbirds Inc. | 10-Q | 2026-05-15 | 2026-03-31 | [0001628280-26-035302](https://www.sec.gov/Archives/edgar/data/1653909/000162828026035302/0001628280-26-035302-index.htm) |
| H16 | CDXS — Codexis Inc. | 10-Q | 2026-08-11 | 2026-06-30 | [0001200375-26-000019](https://www.sec.gov/Archives/edgar/data/1200375/000120037526000019/0001200375-26-000019-index.htm) |
| H17 | PG — The Procter & Gamble Company | 10-Q | 2026-04-24 | 2026-03-31 | [0000080424-26-000060](https://www.sec.gov/Archives/edgar/data/80424/000008042426000060/0000080424-26-000060-index.htm) |
| H18 | USB — U.S. Bancorp | 10-Q | 2026-08-06 | 2026-06-30 | [0000036104-26-000044](https://www.sec.gov/Archives/edgar/data/36104/000003610426000044/0000036104-26-000044-index.htm) |
| H19 | AEP — American Electric Power Company Inc. | 10-Q | 2026-07-30 | 2026-06-30 | [0000004904-26-000059](https://www.sec.gov/Archives/edgar/data/1702494/000000490426000059/0000004904-26-000059-index.htm) |
| H20 | BRT — BRT Apartments Corp. | 10-Q | 2026-08-10 | 2026-06-30 | [0000014846-26-000037](https://www.sec.gov/Archives/edgar/data/14846/000001484626000037/0000014846-26-000037-index.htm) |
| H21 | QS — QuantumScape Corporation | 10-Q | 2026-07-24 | 2026-06-30 | [0001193125-26-316073](https://www.sec.gov/Archives/edgar/data/1811414/000119312526316073/0001193125-26-316073-index.htm) |
| H22 | CRWV — CoreWeave Inc. | 10-Q | 2026-05-08 | 2026-03-31 | [0001769628-26-000222](https://www.sec.gov/Archives/edgar/data/1769628/000176962826000222/0001769628-26-000222-index.htm) |
| H23 | SAP — SAP SE | 20-F | 2026-02-26 | 2025-12-31 | [0001104659-26-020058](https://www.sec.gov/Archives/edgar/data/1000184/000110465926020058/0001104659-26-020058-index.htm) |
| H24 | TM — Toyota Motor Corporation | 20-F | 2025-06-18 | 2025-03-31 | [0001193125-25-142326](https://www.sec.gov/Archives/edgar/data/1094517/000119312525142326/0001193125-25-142326-index.htm) |
| H25 | HSBC — HSBC Holdings plc | 20-F | 2026-02-26 | 2025-12-31 | [0001089113-26-000010](https://www.sec.gov/Archives/edgar/data/1089113/000108911326000010/0001089113-26-000010-index.htm) |
| H26 | BIDU — Baidu Inc. | 20-F | 2026-03-17 | 2025-12-31 | [0001193125-26-109289](https://www.sec.gov/Archives/edgar/data/1329099/000119312526109289/0001193125-26-109289-index.htm) |
| H27 | GLOB — Globant S.A. | 20-F | 2026-02-27 | 2025-12-31 | [0001628280-26-012910](https://www.sec.gov/Archives/edgar/data/1557860/000162828026012910/0001628280-26-012910-index.htm) |
| H28 | NOK — Nokia Corporation | 6-K | 2025-07-24 | 2025-06-30 | [0001104659-25-070159](https://www.sec.gov/Archives/edgar/data/924613/000110465925070159/0001104659-25-070159-index.htm) |
| H29 | XPEV — XPeng Inc. | 6-K | 2025-08-19 | 2025-06-30 | [0001193125-25-183155](https://www.sec.gov/Archives/edgar/data/1810997/000119312525183155/0001193125-25-183155-index.htm) |
| H30 | NIO — NIO Inc. | 6-K | 2025-09-02 | 2025-06-30 | [0001104659-25-086034](https://www.sec.gov/Archives/edgar/data/1736541/000110465925086034/0001104659-25-086034-index.htm) |

Allocation is **12 10-K, 10 10-Q, five 20-F and three earnings 6-K**, each generated three times. Industries span industrials, utilities, real estate, insurance, banking, energy, retail, software, biotechnology, consumer staples, semiconductors, automotive and telecom equipment. The JSON records each case's targeted stressor; a targeted stressor is not a completed independent material-issue review.

Six source-backed smaller-issuer **proxies**, rather than current market-cap estimates, are retained: OUST, BIRD, CDXS and BRT each check “smaller reporting company” on the selected filing's cover. NTLA and ABCL report nonaffiliate public float below USD 1 billion as of June 30, 2025 ($869.49 million and $789.23 million respectively); their cover filer classification is large accelerated, which is retained rather than rewritten. Public float excludes affiliates and is not total market capitalization. The remaining rows have no asserted current size bucket.

TGT/ADBE annual periods and CRM/AMD/PG/TM periods add non-calendar coverage. Nokia's EUR and the Chinese earnings releases' RMB with USD convenience translations add foreign-currency basis checks. Loss/precommercial/sparse cases include the smaller-reporting-company cohort, NTLA and QS, subject to source-reference review. HSBC reports in USD and is not claimed to be a non-USD bank case. CoreWeave is a recent-IPO case with comparatives; it does not satisfy a no-prior-period case. A separate no-prior-period case and amendment coverage remain explicit scope gaps for the founder's acceptance decision, rather than inventing those features or extending offered forms.

All three 6-K identities are earnings releases: Nokia includes the Q2/half-year report in its primary 6-K; XPeng and NIO have the verified earnings exhibit linked in the JSON. SEC's 6-K “Period of Report” is the filing/event date and is retained separately from the financial quarter end. Offline classification using the actual helper-output or primary-fallback branch labels all three `earnings`; this is not a full orchestrator run. Nokia has numerous image assets and needs particularly careful human review of coverage. Governance/general press-release 6-K, amendments, Copilot and multi-period Analysis remain outside this proposal.

DUK and AEP are combined multi-registrant filings and must retain the selected parent issuer's financial scope. AEP's accessible SEC index lives under co-registrant CIK 1702494 and explicitly names parent CIK 4904; this is recorded, not mistaken for a different accession. The parent's direct index could not be fetched by the web tool; the retained complete submission at the verified co-registrant path parses to parent CIK 4904 and includes all co-registrants. WM's primary exceeded the web tool's fetch limit but was subsequently captured in full through the repository SEC client, and its three canonical sections were extracted offline.

For comparative usefulness, preselect H01, H03, H05, H07, H09, H14, H18, H23, H26 and H29. Generate all three draws of a frozen current-product comparator on those ten filings (30 comparator outputs); retain all draws. Compare candidate, comparator and independent reference blind. Report paired better/tied/worse counts and reasons, overall and by filing. Absolute safety/usefulness remain the acceptance gate; no market-superiority claim is implied.

## 5. Source and exclusion evidence

All 30 identities were checked against official SEC filing indexes or submission headers using the read-only web tool. Exact source links are in the manifest and above. Search-result syndications were discovery aids only; official SEC records supply the accepted identities. No raw SEC HTTP bypass, provider call or paid financial service was used.

### Completed source capture and offline assessment

All **30** candidate packets are retained under `work/e7-sources/`: primary document, SEC index and complete submission for every accession, plus separately downloaded XPeng and NIO earnings exhibits. The complete submissions retain associated XBRL and embedded filing documents/assets. Capture used `SECEdgarServiceCompat.get_filing_document_with_source` and its existing `sec_rate_limiter.execute`, sequential requests and one attempt per document. An initial sandbox DNS failure is retained separately; the network-enabled attempt then completed **92 successful requests** with no SEC denial. Total retained source payload is **1,161,213,075 bytes**. Do not embed the 1.16 GB packet directory in the small founder dossier; keep it as the evidence archive with its manifest.

Hashes label the exact representation honestly: **complete HTTP-decoded response text re-encoded as UTF-8**, the repository client's existing provenance contract, not raw HTTP wire bytes. Every retained payload hash was independently recomputed and matched the client's SHA. Per-source URLs, final URLs, content types, character counts, payload sizes and hashes are in the JSON. `e7-sources/capture-log.json` has SHA256 `645b2a2af8fdc05c6ade21e5164d86edf1570dfc4f96981c390eb236670d96b7`; the directory `SHA256SUMS` also inventories source and assessment artifacts. Final candidate-manifest SHA256 is `68242a2c1c57da8d445bc4e1aca104017cffaffe8bbebf131228cde8ea94ba66`.

The offline assessment used pinned edgartools **5.58.0**, locally loaded complete SGML and the existing repository `_extract_sections_sync` / `_extract_sixk_text_sync` helpers. Only accession resolution and primary-document reads were bound to the retained local source; socket networking was blocked, inherited environment cleared, settings isolated with an in-memory database URL, and no database operations or provider calls were made. Binding the captured primary bypasses an SDK XML-declaration branch that otherwise tries to redownload the same primary. This is a deliberate offline harness boundary, not a production fix. All **30 parsed accession/form/date/issuer/SEC-report-period identities match** the manifest, including the DUK/AEP parent issuers.

For the 27 annual/quarterly filings, **18** produced all three canonical sections, **six** produced two, and **three** produced none:

| Filings | Helper observation |
| --- | --- |
| CB, NTLA, USB, AEP | Financials section absent |
| PG, BRT | Risk section absent |
| SAP, TM, HSBC | No canonical sections returned |

These are **helper-level source-coverage observations only**. Existing primary/legacy fallbacks may still make these supported filings eligible. No full orchestrator, legacy narrative fallback or XBRL metric extraction ran, and none of the 30 identities was replaced because of extraction quality. Do not require a clean generated summary before freezing the sample or tune the candidate against these cases.

For 6-Ks, XPeng yielded 47,306 grounding characters and NIO 67,810; each classifies as `earnings`. Nokia's exhibit helper returned no body, so the existing branch uses the retained primary HTML (271,002 characters); the existing classifier on that exact fallback also returns `earnings` (37 earnings cues, 20 monetary tokens in its first 60,000 characters). The empty helper's standalone `press_release` result is retained separately and is **not** the final branch classification. Nokia's image-table coverage remains a human source-review issue. Nothing here establishes full summary quality or complete downstream grounding.

Before paid execution, retain exact generator excerpts/structured channels under the frozen configuration, and freeze independent human reference briefs before showing outputs to humans. Do not truncate a difficult source into eligibility or silently substitute an easier case.

### Completed exclusion audit

- Full reachable history is now available: `shallow=false`; 2,441 commits at audit HEAD `44fd9c4425c7139dbaef1b8707327d3561bab0ce`. This supersedes the initial shallow-clone limitation.
- Scanned 7,809 unique historical textual blobs (242,069,225 bytes), across all locally reachable refs, for every candidate accession in dashed and dashless forms: **zero matches for the final 30**. Extensions and exact scope are retained in JSON.
- Nineteen historical summary/Copilot/weekly cohort blobs contain 38 distinct accessions and 32 issuer tickers. No proposed issuer or accession overlaps those cohorts. Current retained 26-filing Fable manifest is a development subset and stays excluded.
- Additionally scanned eval, review-evidence, golden, prompt and tasks/archive paths for structured ticker/CIK fields (including `ticker=` records): no final candidate issuer match. This does not claim exhaustive adjudication of every prose-only company mention.
- The scan caught initially proposed REGN `0000872589-26-000008` and PEP `0000077476-26-000035` in `tasks/archive/w39-review-2026-09-08.md`, a retained production facts review. Both were conservatively excluded and replaced by ABCL and PG. The JSON preserves these rejected identities/reasons; the replacement audit also has zero final matches.
- The existing summary/Copilot golden hashes from the initial inventory remain `e1ca0cfcb7d0f9f51eff911586437c503a1945a64763284f48c9cd5524498b6b` and `15f8e7f92f934a5b040d905e8f684896cb11b2309d41737bbb58d59d0127b3c0`. The retained Fable source-manifest hash is `f9d258293ed2bbf234c66829fd39a04eba93d0c0e918b199791e2ea803ae870c`.

**Meaning of this audit:** none of the final 30 exact accessions was found in the audited reachable Git evidence. That is stronger than absence from current goldens, but it is not an absolute unseen guarantee. Local/untracked reviews, external/cloud artifacts, expired Actions results with no retained manifest, reviewer memory and private experiments remain outside this scan. A founder/custodian attestation plus inventory of available external artifacts is required before marking `unseen=true`. No attestation is inferred from silence. An inaccessible exposure segment remains a limitation; an exposed case is replaced before freeze rather than relabeled.

A source custodian should record access to the source packets. Source-only identity/material-issue review is permitted; using the cases to tune candidate behavior consumes their holdout status. After a failed holdout, preserve the original result and move exposed cases into regression data, then select fresh cases for renewed acceptance.

**Remaining pre-execution evidence:** independent material-issue reference briefs and source-coverage assessment; exact final generator/structured grounding channels; external/untracked exposure attestation; stable candidate identity; two human reviewer commitments and adjudicator; current tariffs/balance; a proven request-level monetary reservation mechanism. The 30 concrete accession proposal, rubric and spending ceiling can be reviewed now without waiting for paid generation.

## 6. Proposed bounded execution and spending ceiling

**Founder-approved ceiling: USD 10 incremental DeepSeek charges total for this acceptance programme.** Judge API-credit spend: USD 0 (use the existing Fable subscription only). Reviewer fees and additional subscription/credit purchases: USD 0 authorized by this proposal; any paid reviewer engagement requires its own explicit amount and commitment. This ceiling is a proposed maximum, not a price quote or evidence that all worst-case retries fit it. No spend was incurred in preparing this document.

Programme scope: one representative smoke on an existing development filing; 90 candidate outputs; 30 comparator outputs. Maximum **121 logical generation slots**. No rerun to improve a score. Use the existing runner's at-most-one timeout retry per slot, preserving original failure/usage, giving at most **242 generation invocations**. Application-level primary/recovery retries count separately and must never be hidden by the slot count.

At this inspected code state, the shared primary summary budget is three provider attempts, up to eight missing sections each have two recovery attempts, and optional attribution verification has two attempts. For conservative programme planning reserve up to **21 provider calls per generation invocation**, hence **5,082 generator requests maximum**. The current verifier is off; reserving for it does not authorize activation. Re-audit any earlier classifier or provider path before dispatch: the ceiling wrapper must count *every* actual provider request, including any path not captured by this structural estimate, and fail closed at the total cap.

Proposed per-request maximum input envelope: 100,000 tokens for a primary call, 20,000 for recovery/verifier, with the already configured output maxima preserved (primary <=12,000; section recovery <=500; verifier <=700 at this inspected state). A request exceeding a budget envelope is refused and the programme becomes incomplete; **do not truncate evidence or alter production prompt limits to fit a budget**. Verify counts with the provider's actual tokenizer or a conservative documented upper bound before admission. Freeze exact effective request limits with the candidate; new model/path behavior requires a revised budget calculation.

Judge envelope: 121 substantive verdicts (smoke plus candidate and comparator outputs) and one quota probe, plus at most one error-only retry of each substantive verdict on its exact retained input: **243 CLI invocations maximum**. Never retry a negative judgment. A quota error pauses judging without changing model, input or generation. The existing judge's character caps are preflight requirements, not token-budget substitutes: excerpt 400,000 characters, canonical payload 100,000 and XBRL 40,000, with separate statement evidence included as required by code. Any overflow stays explicit; no cap increase is authorized here. Freeze the CLI's effective output/input limits and contract version before execution.

**Enforcement prerequisite:** the existing best-effort cost telemetry is not a spending cap. Before dispatch, a reviewed measurement-only adapter or equivalent provider-enforced budget must reserve the conservative maximum charge **before each provider request**, including all internal retries/recovery and concurrent requests. Price every input as an uncached input at the highest applicable tariff; include output maximum and any overhead/rounding. Atomically reject admission if incurred conservative charges plus in-flight reservations plus the new reservation exceed USD 10. Reconcile a reservation only when reliable full billed usage is available; retain the full reservation for unknown/partial usage. Stop on unrecognized pricing/model, absent price evidence, accounting error or ceiling exhaustion. Preserve the ledger even on cancellation. A post-run balance check or operator watching spend is insufficient to guarantee this ceiling.

Current prices must be verified from the provider's official pricing before the paid programme. Repository tariff constants and the September 19 historical observation of roughly USD 0.30 per 70-output development run are not current-price verification and do not bound retries/recovery. The USD 10 cap may terminate the programme before 121 slots complete; that result is **incomplete**, never a smaller passing sample. If the preflight worst-case full-run estimate exceeds the ceiling, either accept controlled incomplete-stop risk explicitly or propose a revised ceiling before spending; do not automatically raise it.

Run one filing at a time in the acceptance harness initially, with the production's own internal behavior intact. Do not overlap a new generation batch with unrelated paid eval work when reconciling provider balance. No live scheduled-report email, cron generation, production cache population or universe job is part of this programme. Routine CI/regression programmes and the later out-of-time sample are not secretly charged to this new ceiling.

## 7. Stop conditions, defects and final dossier

Freeze the selection/rubric/configuration before seeing outputs. Stop promotion immediately on a material safety defect, and stop generation on S0 or serious S1, wrong source identity, source truncation, unknown budget state or ceiling exhaustion. Retain the attempted denominator and every output/error. Nonmaterial scores do not trigger redraws. Operationally incomplete attempts are never imputed as passes or erased.

The defect register records: immutable ID, accession/draw/surface, exact claim, source passage/table/context, severity, completeness/usefulness effect, both initial reviewer decisions, each refutation attempt, adjudicated decision/reason, affected class, fix reference and unresolved status. Preserve dissent and rejected candidates. Tuning after a failed holdout converts those cases into development regressions; repeat acceptance on fresh unseen cases as well as checking the old failures.

The founder dossier contains the full frozen manifest and hashes, exposure audit/limitations, effective configuration and source SHA, planned/completed/scored/judged/adjudicated counts, all 30 score triples, stratum counts, complete defect register, strongest and weakest outputs with source links, blinded comparison results, actual incurred/unknown usage, price/budget ledger, timing and an explicit accept/reject/incomplete recommendation. Separate quality acceptance from release of universe-wide spend in the decision record. Silence is neither decision.

After acceptance, propose a later out-of-time filing sample with a fresh manifest and a separate bounded budget before wider release. No new automation or ongoing programme is created by this draft.

## Governing local references

- `CLAUDE.md`: filing-only rule, single orchestrator, SEC transport owners and verification discipline.
- `AGENTS.md`: founder-held acceptance/spend boundary, docs-only verification and authority precedence.
- `tasks/handover-astra-2026-09-19.md`: E7; current flags/model; founder-held review and spending decisions.
- `tasks/ceo-implementation-plan-2026-09-08.md`: proposed 30×3 human acceptance, source-grounded references and spend preflight.
- `backend/evals/RUNBOOK.md`: repeat/completeness semantics, current strong judge and caps, 6-K scope, incurred usage and re-pin boundaries.
- `lessons/evals-accept-a-prompt-change-on-two-runs-not-one.md`, `lessons/test-audit-every-judge-channel-for-truncation.md`, `lessons/ops-the-subscription-judge-has-a-usage-limit.md`.

The founder approved these acceptance procedures; they are not assertions of existing code enforcement. No holdout generation or paid acceptance evaluation has run. Required execution controls must be implemented and reviewed before the approved programme starts. Fable quota was reported exhausted by the parent task; no probe or model substitution was attempted.
