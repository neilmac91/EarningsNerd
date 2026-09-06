-- Filing-scoped FY reads filter filing_id/fiscal_period, then order concept/period_end.
-- No is_latest predicate: this filing's original figures survive later restatements.
-- Run only through scripts/apply_migrations.sh (ADR-0007), outside a transaction/DO block.
-- Production size is unmeasured: concurrent creation allows writes but consumes CPU/I/O
-- and may exceed the script's 10s lock / 120s statement budgets. A cancelled build can
-- leave an INVALID index; the script fails rather than silently accepting IF NOT EXISTS.
-- Follow its operator recovery output; never edit an applied migration or auto-drop data.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_financial_fact_filing_period_concept_end
    ON financial_fact (filing_id, fiscal_period, concept, period_end);
