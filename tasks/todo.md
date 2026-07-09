# Tier 5.3 — Value drivers fed deterministically (dividends/buybacks/capex + ROE/ROA trend)

**Goal (roadmap T5.3 / plan §4):** §4's figures come from code — shareholder returns (dividends paid, share
repurchases, capex) and the returns read (ROE/ROA level + trend) — while the model keeps the value VERDICT
(`capital_allocation` prose + `highlights`). Kills the standing fabrication invitation: the prompt asks for
ROIC, which is never a filing line item and absent from the grounding; the honest, already-standardized read
is ROE/ROA (ROIC founders on short-term debt being a multi-concept sum — verified: AAPL splits it across
LongTermDebtCurrent + CommercialPaper; single-tag extraction would OVERSTATE ROIC).

## Load-bearing facts (two understand maps, live-verified on 6 filers)

1. **Concepts verified live** (AAPL/MSFT/TSLA/ASML/TSM/NVO): dividends need 4 candidates
   `[PaymentsOfDividends, PaymentsOfDividendsCommonStock, PaymentsOfOrdinaryDividends,
   DividendsPaidClassifiedAsFinancingActivities]` (each filer tags exactly one); buybacks
   `[PaymentsForRepurchaseOfCommonStock, PaymentsForRepurchaseOfEquity,
   PaymentsToAcquireOrRedeemEntitysShares]`. **Trap tags excluded** (wrong-by-construction:
   `DividendsCommonStockCash` = DECLARED not paid, MSFT 24,678≠24,082; ifrs `DividendsPaid` =
   equity-statement, TSM 531,618≠466,779; `StockRepurchasedAndRetiredDuringPeriodValue` =
   equity-statement, AAPL 89,300≠90,711). All Payments* facts tag POSITIVE → store as-tagged
   (capex precedent), NOT in NON_NEGATIVE_CONCEPTS.
2. **Insertion points:** DURATION_CONCEPTS (instance_extractor.py:45-88, unconditional — RICHER flag
   graduated); pass-through tuple (xbrl_service.py:1154-1165, inert-until-populated); _CONCEPT_UNITS
   (facts_service.py:42-73, "USD"); `_XBRL_CACHE_VERSION` v3→v4 (extraction semantics changed). The
   companyfacts fallback + get_financials last resort deliberately NOT extended (P1.1 precedent);
   golden-set EXTENDED_METRIC_CONCEPTS untouched (non-gating; avoids the mirror drift-guard).
3. **ROE/ROA already standardized WITH trend** (xbrl_service.py:1229-1244; current+prior+change+series)
   and explicitly the FI-appropriate read → the returns line authors for banks too (NO fi gate).
4. **Render:** `_v2_value_drivers` iterates an explicit key tuple (summary_sections.py:624) — the new
   field needs a builder tuple entry; frontend is fully generic (paragraph blocks; zero FE changes).
5. **T4 precedent:** adding a sub-model field ≠ schema-version bump ("taxonomy shape unchanged, still
   v2"); prompt bump is what marks rows stale. figure_trace is an allowlist → an unlisted machine field
   is unpoliced by construction; `capital_allocation`/`highlights` stay policed.
6. **Eval:** depth's capex term becomes a guaranteed hit (can only rise); redundancy risk = model
   restating buyback/dividend $ elsewhere — mitigated by mechanism A + ONE-HOME rewording (both prior
   slices moved redundancy UP). HARD gates structurally untouched (golden facts don't include these).

## Plan

**STATUS: implemented; reviewed (2 adversarial agents, all findings actioned incl. the WFC
component-summing fix + negative-equity ROE guard); gates green (1668); live-verified on 10 filers;
final eval in flight.**

- [x] **Extraction:** DURATION_CONCEPTS += `dividends_paid`, `share_repurchases` (verified lists, trap
      tags documented in a comment + a rule-12 pin that the traps are absent); pass-through tuple += both;
      _CONCEPT_UNITS += both; cache version v3→v4.
- [x] **Grounding:** `_XBRL_NARRATIVE_SPEC` += ("Dividends Paid", usd), ("Share Repurchases (payments)",
      usd) — model sees the facts; figure_trace grounds any restatement via xbrl_values.
- [x] **markdown_render filler** (after cash_conversion block, before segments):
      (a) `shareholder_returns` — mechanism A, filler sole author, pop-first:
      "Capital returned — dividends paid $X (prior $Y), share repurchases $Z (prior $W); capital
      expenditures $C (prior $P)." Currency-aware; only computable clauses; zero-valued current omitted;
      capex-only fallback sentence when no returns; author nothing when nothing computable.
      ONE-HOME: never FCF (§3) nor financing/investing totals (§8).
      (b) `returns_on_capital` — T5.1 code-owns, pop-first: "Return on equity was X.X% (prior Y.Y%);
      return on assets A.A% (prior B.B%)." No FI gate; author nothing when neither ratio computable.
- [x] **Schema:** ValueDrivers += `shareholder_returns: str = ""` (machine-authored annotation + v1-name
      history note); annotate `returns_on_capital` machine-authored.
- [x] **Prompt:** schema_template — REMOVE `returns_on_capital` (mechanism A); `capital_allocation`
      description → qualitative value read ("do not restate the deterministic figures");
      `highlights` example → authorization-style (a NEW program from the filing text, not cash paid);
      ONE-HOME value_drivers clause reworded (T5.1 style). Re-ask snippet: drop returns_on_capital.
      `SUMMARY_PROMPT_VERSION → summary-2026-07-h`.
- [x] **figure_trace:** `_PROSE_STRING_FIELDS["value_drivers"]` → `("capital_allocation",)`; docstring
      lists both machine fields; exclusion + still-policed tests.
- [x] **Render:** `_v2_value_drivers` tuple → (shareholder_returns, capital_allocation,
      returns_on_capital) — deterministic facts lead, model verdict follows.
- [x] **Tests (rule 12):** extraction happy-path both namespaces + dimensioned/out-of-window skips +
      absent→no keys + trap-tag pins + standardized entries; filler full/partial/none + currency + zero
      omission + pop-first ownership ×2 + bank-not-suppressed + ONE-HOME (no FCF); figure_trace policed/
      unpoliced split; render order + no-field-name-leak.
- [x] **Live verify:** AAPL (div+buyback+capex), TSLA (capex-only), TSM (IFRS TWD; buyback current=0 →
      omitted), NVO (DKK). Full gates. Eval `--runs 3` (prompt change) → HARD gates → no re-pin unless moved.
- [x] Two adversarial reviewers → fix → commit → push → draft PR.

## Not in scope (documented deferrals)
- M&A payments (`PaymentsToAcquireBusinessesNetOfCashAcquired`) — NOT live-verified; next slice.
- Effective tax rate (income_tax_expense + pretax_income — verified clean 6/6) — separate follow-up.
- ROIC proper (short-term debt = multi-concept sum; new summation mechanism + analyst-policy judgments).
- Companyfacts/get_financials fallback parity; trend/excel/provenance registries (absent keys degrade
  gracefully); T5.4 forward-quote gate; T4 follow-up.
