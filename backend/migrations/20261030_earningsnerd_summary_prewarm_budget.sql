-- Counts admitted jobs, including failed jobs, across the whole fleet per UTC day.
-- Enforced only when both preparation caps and durable generation are enabled.
CREATE TABLE IF NOT EXISTS earningsnerd_summary_prewarm_budget (
    day VARCHAR(10) PRIMARY KEY,
    admissions INTEGER NOT NULL DEFAULT 0
);
