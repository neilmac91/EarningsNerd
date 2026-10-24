-- Detection: how often the Multi-Period Analysis notation fires, over every company and fiscal year
-- (docs/mpa-improvements/coherence.md §1). It names no company and changes nothing.
-- Retire: the records PR that closes the notation-frequency item in tasks/todo.md deletes this file,
-- after the detection-sql run that sizes the lineage backfill and the run that confirms it.
--
-- Population: one cell per (company, concept, fiscal year), the current FY row an annual analysis
-- reads (trend_analysis/dataset.py `_index_facts`: is_latest, fiscal_period FY, newest period_end per
-- fiscal year), for the 26 concepts of `DATASET_CONCEPT_ORDER`. Each cell is classified as
-- `fact_provenance.provenance_for_fact` classifies it: a stored version-1 record wins; otherwise a
-- legacy row is "calculated" when its source is derived or it is a formula concept with no XBRL tag of
-- its own, and a legacy calculation needs review ("legacy_calculation"); a legacy reported row passes
-- only when reconciled ("source_check_needed" otherwise); a derived EPS row is withheld.
-- Notation: needs_review is the review letter ("a" on REGN), unavailable is withheld and joins the
-- unavailable letter ("b" on REGN, with cells that have no row at all, which this file does not count),
-- method calculated is the dagger. YoY: a cell with a cell for the year before; the comparison carries
-- the review note when either side needs review (data_notes inherits operand validation).
--
-- Read-only: one REPEATABLE READ READ ONLY transaction, so both sets share one snapshot. Each
-- statement gets 120 s and waits at most 10 s for a lock. Cost: each set scans the current FY rows of
-- financial_fact once (materialized) and companies once. JSON: a provenance value holding a NUL or a
-- lone-surrogate escape is rewritten to the escape of U+FFFD before it is parsed, as #1532 did.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '120s';
SET LOCAL lock_timeout = '10s';

\echo '0. Session: this transaction is read-only and bounded.'
SELECT current_setting('transaction_read_only') AS read_only,
       current_setting('transaction_isolation') AS isolation,
       current_setting('statement_timeout') AS statement_timeout,
       current_setting('lock_timeout') AS lock_timeout;

\echo '1. Notation frequency by dimension (all, concept, fiscal_year, sic_division, owner, reason).'
\echo '   review_pct: share of cells carrying the review letter; calc_pct: share carrying the dagger;'
\echo '   legacy_pct: share with no stored lineage record; yoy_review_pct: share of YoY comparisons'
\echo '   that inherit the review letter. owner: filing (a per-filing XBRL row) or companyfacts.'
WITH params AS (
    SELECT '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), cells AS MATERIALIZED (
    SELECT DISTINCT ON (ff.company_id, ff.concept, ff.fiscal_year)
           ff.company_id, ff.concept, ff.fiscal_year, ff.source, ff.raw_tag, ff.reconciled,
           CASE WHEN ff.filing_id IS NOT NULL THEN 'filing' ELSE 'companyfacts' END AS owner,
           CASE WHEN ff.provenance IS NULL OR ff.provenance::text = 'null' THEN NULL
                WHEN ff.provenance::text ~ p.json_hazard
                THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::jsonb
                ELSE ff.provenance::jsonb END AS pv
    FROM financial_fact ff
    CROSS JOIN params p
    WHERE ff.is_latest AND ff.fiscal_period = 'FY' AND ff.fiscal_year IS NOT NULL
      AND ff.concept IN (
          'revenue', 'net_interest_income', 'noninterest_income', 'premiums_earned', 'net_investment_income',
          'gross_profit', 'gross_margin', 'operating_income', 'operating_margin', 'net_income', 'net_margin',
          'earnings_per_share', 'eps_diluted', 'operating_cash_flow', 'capital_expenditures', 'free_cash_flow',
          'investing_cash_flow', 'financing_cash_flow', 'total_assets', 'cash_and_equivalents',
          'current_assets', 'current_liabilities', 'working_capital', 'current_ratio', 'long_term_debt',
          'shareholders_equity')
    ORDER BY ff.company_id, ff.concept, ff.fiscal_year, ff.period_end DESC
), lineage AS (
    SELECT c.*,
           COALESCE(jsonb_typeof(c.pv) = 'object' AND c.pv ->> 'version' = '1', false) AS stored,
           c.source = 'derived' OR (
               c.concept IN ('net_margin', 'operating_margin', 'gross_margin', 'free_cash_flow',
                             'working_capital', 'current_ratio')
               AND (c.raw_tag IS NULL OR c.raw_tag = c.concept)) AS legacy_calculated
    FROM cells c
), classified AS (
    SELECT l.company_id, l.concept, l.fiscal_year, l.owner, l.stored,
           CASE WHEN l.stored THEN COALESCE(l.pv ->> 'method', 'unknown')
                WHEN l.legacy_calculated THEN 'calculated' ELSE 'reported' END AS method,
           CASE WHEN l.concept IN ('earnings_per_share', 'eps_diluted', 'eps_basic') AND l.source = 'derived'
                THEN 'unavailable'
                WHEN l.stored THEN COALESCE(l.pv ->> 'validation', 'unknown')
                WHEN l.legacy_calculated OR l.reconciled IS NOT TRUE THEN 'needs_review'
                ELSE 'passed' END AS validation,
           CASE WHEN l.concept IN ('earnings_per_share', 'eps_diluted', 'eps_basic') AND l.source = 'derived'
                THEN 'unsupported_eps_calculation'
                WHEN l.stored THEN COALESCE((
                    SELECT string_agg(r, '+' ORDER BY r)
                    FROM jsonb_array_elements_text(
                        CASE WHEN jsonb_typeof(l.pv -> 'reasons') = 'array' THEN l.pv -> 'reasons'
                             ELSE '[]'::jsonb END) AS r), 'none')
                WHEN l.legacy_calculated THEN 'legacy_calculation'
                WHEN l.reconciled IS NOT TRUE THEN 'source_check_needed'
                ELSE 'none' END AS reason
    FROM lineage l
), compared AS (
    SELECT k.*,
           lag(k.fiscal_year) OVER w = k.fiscal_year - 1 AS has_yoy,
           lag(k.validation) OVER w AS prior_validation
    FROM classified k
    WINDOW w AS (PARTITION BY k.company_id, k.concept ORDER BY k.fiscal_year)
), sectored AS (
    SELECT m.*, COALESCE(left(co.sic, 2), 'null') AS sic_division
    FROM compared m
    JOIN companies co ON co.id = m.company_id
)
SELECT CASE WHEN GROUPING(concept) = 0 THEN 'concept'
            WHEN GROUPING(fiscal_year) = 0 THEN 'fiscal_year'
            WHEN GROUPING(sic_division) = 0 THEN 'sic_division'
            WHEN GROUPING(owner) = 0 THEN 'owner'
            WHEN GROUPING(reason) = 0 THEN 'reason'
            ELSE 'all' END AS dimension,
       COALESCE(concept, fiscal_year::text, sic_division, owner, reason, 'all') AS key,
       count(DISTINCT company_id) AS companies,
       count(*) AS cells,
       round(100.0 * count(*) FILTER (WHERE validation = 'needs_review') / count(*), 1) AS review_pct,
       count(*) FILTER (WHERE validation = 'needs_review') AS review,
       count(*) FILTER (WHERE validation = 'unavailable') AS withheld,
       round(100.0 * count(*) FILTER (WHERE method = 'calculated') / count(*), 1) AS calc_pct,
       count(*) FILTER (WHERE method = 'calculated' AND validation = 'needs_review') AS calc_review,
       round(100.0 * count(*) FILTER (WHERE NOT stored) / count(*), 1) AS legacy_pct,
       count(*) FILTER (WHERE has_yoy) AS yoy,
       round(100.0 * count(*) FILTER (WHERE has_yoy AND 'needs_review' IN (validation, prior_validation))
             / NULLIF(count(*) FILTER (WHERE has_yoy), 0), 1) AS yoy_review_pct
FROM sectored
GROUP BY GROUPING SETS ((), (concept), (fiscal_year), (sic_division), (owner), (reason))
ORDER BY dimension, key;

\echo '2. Exposure per company in its newest ten fiscal years (the picker''s "Last 10"): how many'
\echo '   companies show 0, 1-5, 6-10, 11-20 or more than 20 cells with the review letter, and the'
\echo '   median review share of a company''s cells.'
WITH params AS (
    SELECT '\\u(0000|[dD][89a-fA-F][0-9a-fA-F]{2})'::text AS json_hazard
), cells AS MATERIALIZED (
    SELECT DISTINCT ON (ff.company_id, ff.concept, ff.fiscal_year)
           ff.company_id, ff.concept, ff.fiscal_year, ff.source, ff.raw_tag, ff.reconciled,
           CASE WHEN ff.provenance IS NULL OR ff.provenance::text = 'null' THEN NULL
                WHEN ff.provenance::text ~ p.json_hazard
                THEN regexp_replace(ff.provenance::text, p.json_hazard, '\\ufffd', 'g')::jsonb
                ELSE ff.provenance::jsonb END AS pv
    FROM financial_fact ff
    CROSS JOIN params p
    WHERE ff.is_latest AND ff.fiscal_period = 'FY' AND ff.fiscal_year IS NOT NULL
      AND ff.concept IN (
          'revenue', 'net_interest_income', 'noninterest_income', 'premiums_earned', 'net_investment_income',
          'gross_profit', 'gross_margin', 'operating_income', 'operating_margin', 'net_income', 'net_margin',
          'earnings_per_share', 'eps_diluted', 'operating_cash_flow', 'capital_expenditures', 'free_cash_flow',
          'investing_cash_flow', 'financing_cash_flow', 'total_assets', 'cash_and_equivalents',
          'current_assets', 'current_liabilities', 'working_capital', 'current_ratio', 'long_term_debt',
          'shareholders_equity')
    ORDER BY ff.company_id, ff.concept, ff.fiscal_year, ff.period_end DESC
), classified AS (
    SELECT c.company_id, c.fiscal_year,
           CASE WHEN c.concept IN ('earnings_per_share', 'eps_diluted', 'eps_basic') AND c.source = 'derived'
                THEN false
                WHEN COALESCE(jsonb_typeof(c.pv) = 'object' AND c.pv ->> 'version' = '1', false)
                THEN c.pv ->> 'validation' = 'needs_review'
                ELSE c.source = 'derived' OR c.reconciled IS NOT TRUE OR (
                    c.concept IN ('net_margin', 'operating_margin', 'gross_margin', 'free_cash_flow',
                                  'working_capital', 'current_ratio')
                    AND (c.raw_tag IS NULL OR c.raw_tag = c.concept)) END AS review
    FROM cells c
), windowed AS (
    SELECT k.*, dense_rank() OVER (PARTITION BY k.company_id ORDER BY k.fiscal_year DESC) AS recency
    FROM classified k
), per_company AS (
    SELECT company_id, count(*) AS cells, count(*) FILTER (WHERE review) AS review
    FROM windowed
    WHERE recency <= 10
    GROUP BY company_id
)
SELECT CASE WHEN review = 0 THEN '0' WHEN review <= 5 THEN '1-5' WHEN review <= 10 THEN '6-10'
            WHEN review <= 20 THEN '11-20' ELSE '>20' END AS review_cells,
       count(*) AS companies,
       round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct_of_companies,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY 100.0 * review / cells) AS median_review_pct
FROM per_company
GROUP BY 1
ORDER BY min(review);

COMMIT;
