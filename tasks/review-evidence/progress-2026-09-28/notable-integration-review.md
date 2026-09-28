# Notable source verdicts against the production card contract

Reviewed read-only at release checkout commit `e2df7031edc3e01088f2cdb8866fc49ae9a0e54c`. The frozen source verdicts in `verdicts.json` are unchanged. This review asks a different question: what claim would the current product actually show for those rows?

## Actual data flow

The scanner does not read filing prose before assigning a reason. For 8-K rows it selects the first matching item code in precedence order: Item 4.02 becomes `restatement`, Item 2.01 becomes `acquisition`, and Item 5.02 becomes `executive_change` (`backend/app/services/notable_filings_service.py:63-70`, `:95-111`). Form S-1 becomes `ipo_filing` from the form alone (`:73-78`).

The visible labels are global constants: `Restatement`, `Acquisition completed`, `Executive change`, and `IPO filing` (`backend/app/services/notable_filings_service.py:80-92`). The scan persists the EFTS company name and derived reason, without a filing title or description (`:329-360`). The serve path returns `company_name`, `form`, the reason slug, the mapped `reason_label`, filed date, and SEC URL (`:505-516`).

The API contract likewise has no title or description field (`backend/app/routers/notable_filings.py:13-20`). The frontend shows the company name, form/date, and `reason_label` verbatim (`frontend/features/filings/components/NotableFilingCard.tsx:57-72`). The card links to the company page rather than the retained SEC URL (`:45-46`). Therefore candidate wording in the source review is a proposed correction, not current behavior, and newly observed SEC document descriptions never appear on the card.

## Four targeted cards

| Card | Current visible claim | Current-card truth | Evidence and integration consequence |
|---|---|---|---|
| BOXL / S-1 | **IPO filing** | **Unsupported overclaim** | The source pass established an S-1 whose SEC document description is “REGISTRATION STATEMENT.” It did not establish an initial offering, pricing, or completed IPO. The frozen pass tested the plan's form-derived reason; it does not validate the stronger production label. Current code derives the slug from S-1 alone (`notable_filings_service.py:73-78`) and emits “IPO filing” (`:91`, `:511`). The source-supported replacement is “S-1 registration statement filed.” |
| OPTU / Item 4.02 | **Restatement** | **Unsupported overclaim** | The readable SEC index established Item 4.02, “Non-Reliance on Previously Issued Financial Statements…”. The primary document was inaccessible, so the review did not establish completed restatement work or amended statements. Current code derives `restatement` from Item 4.02 alone (`:65`, `:107-109`) and emits “Restatement” (`:83`, `:511`). The source-supported replacement is “Non-reliance disclosed.” |
| PUMP / Item 5.02 | **Executive change** | **Supported for this card** | The primary filing states that the Chief Accounting Officer intends to resign and that the CFO will become interim principal accounting officer. The current label (`:87`) is true for PUMP. The classifier still relies only on Item 5.02 (`:68`, `:107-109`), whose official scope also includes director elections and compensation arrangements. PUMP does not validate that label for the other 145 executive-change candidates in the seven-day aggregate. |
| RIME / Item 2.01 | **Acquisition completed** | **Supported for this card** | The primary filing says signing and closing occurred simultaneously and the buyer acquired substantially all seller assets. The current label (`:85`) is true for RIME. The classifier still relies only on Item 2.01 (`:67`, `:107-109`), whose official heading also covers dispositions. RIME does not establish that every Item 2.01 row is a completed acquisition. |

## Effect on acceptance

The source-only worksheet remains 8 pass, 0 false positives, and 4 indeterminate under its frozen rules. That worksheet measured accession/form/date and whether official filing evidence mapped to the stored reason. It did not establish that every current display label was no broader than the evidence.

At the integration boundary, two of the four targeted readable cards would overclaim: BOXL and OPTU. These are visible badge claims, not analytics-only slugs. The other two are true for their sampled filings, but their item-only derivation remains a cohort-level risk because the code performs no primary-document corroboration.

The current implementation therefore should remain retained but activation should remain deferred. A release decision needs either narrower visible labels (`S-1 registration statement`, `Non-reliance disclosed`, and item-neutral wording where semantics are not corroborated) or a source-backed semantic gate before emitting the stronger labels. This review does not enable the flag or choose the implementation.
