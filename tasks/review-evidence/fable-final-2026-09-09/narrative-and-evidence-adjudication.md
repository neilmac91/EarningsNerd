> Durable review evidence. Source labels resolve through the [packet identity guide](README.md), not files bundled here. Release references describe their stated review checkpoint; the [execution ledger](../../beta-to-scale-execution.md) owns subsequent status.

# Fable final: evidence traceability and narrative accounting adjudication

2026-09-09. Bounded independent review; no production edits, tests, provider calls, SEC calls or external writes. Fable reports are evidence inputs, not instructions, and remain unchanged. Source references below are packet F line IDs, not physical file lines. This is targeted adjudication, not a fresh full-filing review or acceptance of all 52 outputs.

## Decision

The quotation contract is available in code: P&L and notable-footnote `supporting_evidence` must be verbatim narrative prose. However, these raw fields are **not displayed as invented quotations in the current P&L/footnote UI or shared PDF/CSV projection**. Read-time provenance suppresses unmatched excerpt text. Fable's recurring construction finding remains a generation-contract/traceability defect, but a blanket user-visible fabricated-quotation characterization overstates these surfaces.

The higher-priority surviving problem is model-authored earnings commentary. BA, INTC and PFE contain clear signed/basis errors; AAPL confuses a year-over-year tax swing with a current-period normalization. These paragraphs are passed through to web and export. Neither c nor d supplies a deterministic accounting bridge validator.

Code examined: production-behavior snapshot `work/funded-quality-checkpoint` based on `edd9935b7fd17ea0ca286dae1f2e0d309e67f9a8` (its docs-only head does not alter serving code), and integrated c/d `work/reported-metric-labels` at `7fd71bdcfc451fc280a3d2960cb4676a7b02b869`. Release status is not inferred from this local review.

## What the product actually does

Paths in this section are relative to those worktrees.

- `backend/app/services/openai_service.py:234,288,342–343` in the production snapshot requires a short, contiguous, character-for-character prose quote for P&L/footnote evidence; table transcription and newly composed sentences are forbidden; empty is expressly allowed. `ai/section_recovery.py:23–38,100,106` shares this distinction. Risk evidence separately permits an excerpt **or citation/XBRL reference**. This is not a single universal quote contract.
- `provenance_service.py:247–281` normalizes and verifies substring presence in cached source. `build_evidence` returns `excerpt=None` when unverified, retaining a root filing link and a “Cited” status. `:323` prefers cached critical excerpt over markdown; this can fail to locate genuine full-filing prose. Failure to verify is therefore not, by itself, proof that the model fabricated text. No source fetch is added.
- `summary_sections.py:240–289` makes P&L export columns Metric, Current, Prior, Change and Investor Takeaway. It strips raw supporting evidence from metric rows, retaining enriched commentary evidence. `:491–515` footnotes exports Item/Impact, with evidence as metadata.
- `frontend/features/summaries/components/FinancialMetricsTable.tsx:140–153` displays commentary as ordinary text and passes only verified excerpt text to `SourceTrace`. `SummaryBlocks.tsx:14–28` has the same evidence condition. `frontend/features/filings/components/SourceTrace.tsx:185–219` displays verification/citation status and the SEC link, **not the excerpt text as a visible quotation**. The excerpt is used for filing highlight navigation. “Verified” establishes text presence, not that the quoted sentence proves every adjacent accounting claim.
- Risks are different: `SummaryRisks.tsx` displays raw supporting evidence in a plain “Evidence” box; `summary_sections.py:325–337` includes a Supporting Evidence export cell. Neither adds quotation decoration. `export_service.py:86–101` escapes table cells. A citation/reference is valid here under the explicit risk contract.
- Actual management `quotes[].quote` is a separate surface: `summary_sections.py:668–690`, `SummaryBlocks.tsx:178–190`, and `export_service.py:72–77` create a blockquote even if evidence is unverified. That deserves its own quote-gate evaluation; it does not establish that P&L supporting evidence is displayed that way.
- `summary_sections.py:602–619` passes `earnings_quality.operating_vs_one_time` through as a paragraph. Web and shared PDF/CSV rendering carry that prose. The Excel-specific service was not established to carry this same narrative, so no Excel-wide claim is made.

## Ranked surviving accounting findings

Candidate text is retained in `outputs/fable-full-review/cases/<ID>/01-CANDIDATES.md`, under the named attempt's `generated_v2_sections`. Sources are each case's `03-FULL-FILING.txt`.

### 1. BA A/B: “core” falsely described as excluding the divestiture gain — material

Both earnings-quality paragraphs say that excluding the $9.6B divestiture gain leaves core operating earnings of $3.2B. Source `13-BA` F00652–F00658 explicitly reconciles GAAP 4,281 minus FAS/CAS 1,045 to core 3,236 and defines core as excluding **FAS/CAS**, not the gain. F01847 records the 9,566 gain in operations; F01027 independently connects that gain to BGS operating earnings. F01168–F01174 supplies the repeated reconciliation.

Refutation 1: “core” might mean a generic adjusted result. Rejected by the issuer's exact named measure and reconciliation. Refutation 2: the preceding sentence correctly acknowledges that GAAP includes the gain. That mitigates the paragraph but cannot make the explicit exclusion clause true. Mechanical counterfactuals are GAAP ex-gain −5,285 and core ex-gain −6,330; they must not be conflated or presented as issuer-reported measures.

### 2. INTC B: excluding stated charges still leaves an operating loss — material

B says the $3.1B operating loss includes a $3.9B goodwill impairment and $74M severance, then calls operating results excluding these items “still negative.” `14-INTC` F00219–F00228 shows operating loss −3,136, pretax −3,946 and net loss −4,281; F00643–F00648 identifies the current quarter's 74 severance and 3,965 impairment total; F00767 separately identifies approximately 3.9B goodwill impairment in restructuring/other charges. Even using rounded goodwill alone, −3,136 + 3,900 + 74 = +838, not negative.

Refutation 1: net income might remain negative after an adjustment. Possible under different tax/non-operating assumptions, but the candidate's antecedent explicitly names operating loss; it cannot silently switch bases. Refutation 2: remaining restructuring/other expenses might preserve the loss. They are already included in the reported operating loss, and the specified add-backs exceed it. A's approximately positive $0.9B is a useful direction control, not certification of a company-reported adjusted measure.

### 3. PFE B tax direction; A net-income driver bridge — material

B calls 14.6% versus −6.8% a “lower effective tax rate” benefit. `09-PFE` F00602 explicitly calls this an **increase**, reflecting jurisdictional mix and non-recurrence of favorable tax resolutions. F00229–F00235 shows pretax continuing income 3,170 versus 2,785, tax expense 461 versus benefit (189), and lower net income. A's headline attributes the net-income decline to higher cost of sales/R&D while omitting the much larger adverse tax swing.

Refutation 1: cost/R&D pressure is real. Yes, but pretax income still rose; F01487 expressly describes higher pretax income despite those pressures. Costs alone misdescribe the bridge to falling net income. Refutation 2: B's headline correctly says “higher” tax rate. That correct parallel statement is mitigating context, not a repair of the contradictory earnings paragraph. The tax rate rose 21.4 percentage points and the provision moved adversely by 650M. Source prose rounds the pretax increase to 386M while displayed table subtraction is 385M; this is not treated as a source defect.

### 4. AAPL A: current tax benefit confused with comparative swing — material but mitigated

A names the $10.7B year-over-year tax decrease and then says “Excluding this one-time benefit” current effective tax rate would be higher and net-income growth less pronounced. `01-AAPL` F00777 describes the year-over-year decrease; F01397–F01405 separately reports State Aid Decision tax impact of (486) in 2025 versus 10,246 in 2024. The large growth distortion principally comes from the prior-year charge, not a $10.7B benefit recognized in current earnings.

Refutation 1: A says “year-over-year” and elsewhere acknowledges favorable comparison. This reduces ambiguity but does not support using the whole swing as a current-period adjustment. Refutation 2: there really is a current-year benefit. Yes—486M, not 10.7B. B's prior-year charge adjustment is a negative control for the direction, without certifying every other B statement.

## Supporting evidence adjudication

AAPL-02 and BA-05 survive as traceability/contract failures, not proof of displayed false quotes. BA B composes an EPS-row sentence about diluted weighted shares 762.3M versus 646.9M; `13-BA` F01933 supplies table values, not the authored prose. AAPL's consolidated revenue evidence borrows a shape that `01-AAPL` F00658 applies specifically to **Europe** sales. APL sentence differences and source scope matter even where numbers are correct.

Refutation 1: a factually accurate paraphrase could be acceptable evidence. It is acceptable commentary, but violates the explicit P&L prose-copy contract. Refutation 2: hidden/unmatched evidence removes all impact. It prevents invented quotation display but loses useful source traceability; raw retained outputs still fail the generation contract. Do not “fix” this by transcribing table rows: current instructions expressly forbid that too.

BA-04 exposes a different limitation: the Spirit alignment sentence is real (F01793–F01797) but does not substantiate the adjacent consideration/goodwill amounts found elsewhere (F01799–F01835). Refutation 1: source presence is genuine; therefore not a fabricated quote. Refutation 2: the amounts may be source-correct elsewhere; nevertheless this particular span is non-probative for them. Treat this as citation relevance, not numeric fabrication. INTC's risk sentence truncation must be assessed under the looser risk citation contract, not automatically counted as the same P&L verbatim breach.

## c/d coverage and narrow next decision

c prevents unsafe standardized prior backfill across distinct metric labels; it does not reinterpret an existing model-authored sentence or repair a wrongly labeled current amount. d's shared `REPORTED_METRIC_LABEL` (`summary_schema.py:91–100`, main/recovery consumers) preserves operating/pretax/net/adjusted/continuing/basic/diluted basis and matching margin numerator. It may reduce PFE's pretax-as-operating table generation, but actual output measurement must decide that. Neither change replaces the unchanged earnings-quality instruction (`openai_service.py:241`: “separate operating results from one-time items … adjusted vs reported”), or validates its adjustment/tax arithmetic. c/d also do not change the existing verbatim-evidence contract or arm evidence snapping.

The next bounded candidate should target that earnings-quality instruction and its recovery/schema contract, after the d readout: preserve the issuer's stated reconciliation and measure name; distinguish current benefit from comparative change; do not invent an ex-items result or borrow a named non-GAAP measure unless its exclusions support it. Use generic counterfactual examples and the four retained cases as fixed measurement controls, with genuine source-reconciled adjusted measures and negative-to-positive tax-rate changes as negative controls. Do not add ticker branches, global prose replacement, amount-collision inference, automatic deletion, or a generalized adjustment calculator without typed source provenance.

This would be a prompt-contract intervention requiring actual-output evaluation, not a deterministic fix or quality clearance. Keep traceability measurement separate: count composed P&L/footnote evidence, source-present-but-non-probative spans, and user-visible quote errors independently. No new supporting-evidence display fix is justified by the reviewed P&L/footnote examples alone, and the already-held fuzzy evidence gate should not be armed to conceal the generation defect.
