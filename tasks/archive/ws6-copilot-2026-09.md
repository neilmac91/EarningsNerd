# Filing-scoped Copilot — implementation archive

Archived 2026-09-05 after [PR #703](https://github.com/neilmac91/EarningsNerd/pull/703) merged and its deployment was verified.
Final local backend gate: `2319 passed, 2 deselected, 72 warnings in 48.82s`; Ruff and Bandit passed. 143 valid intended mutation failures. Final actual Copilot 18/18 accepted after the retained first 14/18 report; the original summary 51/52 timeout report also remains failed evidence. Five accepted answers were uncited, so coverage remains advisory. Unknown duration basis returns basis_unavailable; no invented period starts or production backfill.

See the [current evidence ledger](../wave2-ledger-2026-09.md) for merge SHAs, actual CI and deployment links,
and [active handover](../handover-wave2-2026-09.md) for unmet programme conditions.
The original plan below is historical: unchecked implementation boxes record its pre-execution
state, not a request to repeat completed work. Explicit readout, broader-coverage and founder
residuals remain open in the active todo. No wave-completion claim is made.

---

## WS-6 Copilot — observed first live failure and corrective plan

Run 33984283703 retained all 18 completed/scored attempts, zero execution errors, and four
hard vetoes (14 passed). GitHub incorrectly reported success because a shell pipeline hid
the runner failure. Three MSFT answers contained the correct $13.64 but the Copilot scorer
passed canonical `USD/shares` to a shared matcher expecting `_per_share`. AAPL draw 2 emitted
an invented ellipsis inside a text citation; that citation veto is valid and remains mandatory.
The original report, source database and source artifacts are retained unchanged.

- [ ] Make both logged workflow pipelines fail when their Python command fails; prove actual
  shell exit propagation for preparation and evaluation, retaining always-uploaded artifacts.
- [ ] Adapt canonical per-share units only at the Copilot numeric-scoring boundary, preserving
  native golden/source units and the shared summary matcher; prove exact mixed-unit MSFT
  answers, wrong basic EPS and missing EPS without changing tolerances or expected values.
- [ ] Clarify contiguous exact text excerpts and reuse of existing fact markers in the Copilot
  prompt; keep the actual AAPL stitched quotation as a hard-failing regression. No automatic
  deletion of invalid citations, coverage promotion, model change or baseline re-pin.
- [ ] Obtain intended mutation failures for these new tests, independent review, and a fresh
  full backend gate before root opts the draft PR back into a complete three-repeat live run.
- [ ] Inspect the new actual Copilot and summary reports; a workflow badge alone is insufficient.

## WS-6 Copilot — implementation plan after verified hygiene deployment

Owners: AI Engineer (plan_gates) owns service/snapshot/currency, eval schema/scorers/runner,
goldens/workflow and docs; plan_rules owns copilot_tools and tool tests.
plan_correctness owns source-only bootstrap, identity manifest and bootstrap tests; the other
three reviewers independently review that component before acceptance.
Base: #702 merged `efc81adcd5f4891836b2d6c5b4d28460d08b3fa9`; deployment 33981155212
applied 0/skipped 34, revision `00267-2kc` serves all traffic; detailed health is healthy.

- [ ] Bind trusted accession and native reporting currency from detached filing snapshot into
  every numeric tool branch; missing scope cannot fall back to company-wide latest facts.
- [ ] Preserve own-filing comparatives and historical rows; require compatible units and known
  duration basis for derived arithmetic. Missing period_start remains basis_unavailable; no
  invented dates, currency conversions, or expanded fact-writer scope.
- [ ] Retain direct/derived operand provenance in citations; verify all declared XBRL citations
  before numeric filtering and reject contradictory currency labels adjacent to their figures.
  Distinct derived expressions must not share a marker; absence of prose currency is not USD.
- [ ] Preserve the actual refusal terminal contract: default the absent strip count only for
  a valid not_disclosed completion, while rejecting missing answer counts and malformed values.
- [ ] Accept actual normalized source facts with nullable raw_tag, keeping absent tags explicit
  and requiring concept, accession, finite value, unit and period without fabricating tags.
- [ ] Close observed real-ORM snapshot gap: read actual period_end_date while the session is
  live, retain plain ISO period after expiry/close, and verify context with a persisted ORM row.
- [ ] Close observed same-value wrong-period scorer acceptance: declare expected period per QA
  metric and bind used matching-fact citations to it, preserving explicit comparative questions.
- [ ] Close observed Markdown-emphasis currency bypass: normalize supported inline delimiters
  only in the currency check, retaining rendered text and valid non-USD formatting.
- [ ] Verify six researched accessions/five issuers with stable question IDs, periods and units;
  retain old unverified QA explicitly pending. Preserve existing trust/refusal/numeric hard bars.
- [ ] Prepare only actual SEC-layer documents/XBRL/sections in fresh scratch file SQLite, then
  production excerpt/fact normalization. Source manifest is separate from golden answers;
  save source hashes and extraction evidence, and abort before provider calls on missing inputs.
- [ ] Require one valid terminal completion and exact planned accession/question/run identities;
  errors/skips/missing rows cannot disappear from denominators. Save actual inputs and outputs.
- [ ] Add same-repository PR workflow gated by !draft and ready_for_review: root opts in only after
  offline full gates and three reviews. Run the complete cohort at least three times with the
  existing Actions generator credential, upload evidence even on failure, never extract secrets.
- [ ] Prove every new/changed test by intended-assertion mutation, restore exactly, run the full
  pinned backend gate and separate summary regression against the sole unchanged baseline.
- [ ] Correct owning historical service/RUNBOOK provider comments; record actual Copilot evidence
  before root merge/deployment. First strong-judge readout and evidence-snap arming remain held.

No production DB/backfill/prewarm, new credentials, live email, model swap, threshold relaxation,
or baseline re-pin. This deterministic Copilot run is not the first weekly judged readout.
