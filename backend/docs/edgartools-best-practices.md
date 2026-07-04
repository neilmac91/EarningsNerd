# EdgarTools best practices (financial-data extraction)

Captured from an investigation of the EdgarTools docs (v5.40.x) during the financial-institution
revenue fix (filing 528 / MCB). Read this before touching XBRL extraction in
`app/services/edgar/`.

## The core lesson

**Do not hand-pick a single revenue tag from a flat priority list.** Concept names vary by company,
and the "first tag that resolves" wins the wrong value for whole industries. EdgarTools' own
standardization shares this blind spot: it maps *"139 revenue variations"* to one generic `Revenue`
concept with **no industry-specific handling**. For a bank, `RevenueFromContractWithCustomer…`
(ASC-606 fee income) and even `standard_concept == "Revenue"` point at a **subset** (~fee income),
not total revenue.

The reliable source is the filing's **as-reported income statement**:

```python
xb = filing.xbrl()
df = xb.statements.income_statement().to_dataframe(view="standard")  # undimensioned face values
```

It renders the filer's *own* line items and labels (a bank shows interest income / net interest
income / non-interest income), plus columns we use to select by structure: `concept`, `label`,
`standard_concept`, `is_breakdown`, `dimension`, `abstract`, `parent_concept`, and one column per
period (`"2025-12-31 (FY)"`).

## Rules we follow (see `instance_extractor.py`)

1. **Gate financial institutions with `Company.is_financial_institution()`**, not SIC alone — some
   financial filers (e.g. ARCC) carry a **blank SIC**. Use the SIC band (6000–6799) only as a
   fallback, and sub-type (bank / insurer / BDC / catch-all) by **concept presence** in the
   statement.
2. **Select by specific us-gaap concept anchors**, not `standard_concept`. `standard_concept ==
   "Revenue"` is attached to a bank's fee-income row and to a BDC's *net* investment income — both
   wrong as "total revenue". Use `standard_concept` only to disambiguate the total row when one
   concept spans several presentation lines.
3. **Use undimensioned face values** (`view="standard"`; the successor to the deprecated
   `include_dimensions=False`) and drop `is_breakdown` / `dimension` rows — never sum a dimensional
   member as if it were the total.
4. **Record the winning tag** (`raw_tag`, persisted on `financial_fact`) so a concept that **flips
   between filings** can be detected — the source of apples-to-oranges period-over-period deltas.
5. **Period discipline** for multi-period comparisons: annual = duration > 300 days / the `(FY)`
   column marker; exclude amendments and require a strictly-earlier reporting *period* (not just
   filing date) so a restatement of the same period is never differenced against the original.
6. **Values are in actual dollars** from these APIs — never rescale by thousands/millions.
7. **Always keep a fallback.** The statement path is wrapped defensively and falls back to the
   generic fact-query extractor on any failure, so extraction never hard-fails.

## Per-industry revenue treatment (validated against MCB, MET, BLK, ARCC)

| Industry | Detect (concept present) | Emitted metric(s) | Anchor concept(s) |
|---|---|---|---|
| Bank / thrift | `InterestIncomeExpenseNet` / `NoninterestIncome` | `net_interest_income`, `noninterest_income` (**no** single revenue) | `InterestIncomeExpenseNet`; `NoninterestIncome` |
| Insurer | `PremiumsEarnedNet` | `revenue` (total) + `premiums_earned`, `net_investment_income` | `Revenues`; `PremiumsEarnedNet`; `NetInvestmentIncome` |
| BDC / closed-end fund | `GrossInvestmentIncomeOperating` | `revenue` = total investment income | `GrossInvestmentIncomeOperating` (gross, before expenses) |
| Investment mgr / broker-dealer | (catch-all financial) | `revenue` (reported total) | `Revenues` / `RevenueFromContractWithCustomer…` (the `is_total`/`standard_concept="Revenue"` row) |
| Non-financial | — | unchanged | generic fact-query path |

## APIs worth adopting later (not yet used)

- `XBRLS.from_filings(...)` — stitched multi-period statements with aligned periods/concepts, for
  trend/history instead of assembling series ourselves.
- `Company.get_facts()` — cached multi-year companyfacts (with the same industry caveats).
- Statement `standard_concept` column — fine as a cross-company **annotation** for unambiguous
  lines (assets, net income), never as the source of a financial institution's revenue.

Sources: EdgarTools docs — common-pitfalls, choosing-the-right-api, extract-statements,
getting-xbrl, xbrl/concepts/standardization, dimension-handling, multi-period-analysis,
company-classification.
