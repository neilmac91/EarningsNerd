-- Project-specific bookkeeping: never adopt a conventional job_runs table.
-- Fresh databases receive the same schema through the JobRun model/create_all.
CREATE TABLE IF NOT EXISTS earningsnerd_job_runs (
    id VARCHAR(36) PRIMARY KEY,
    job_name VARCHAR(80) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL,
    error_type VARCHAR(120),
    counters JSON
);
-- Catalog guard also makes ledger-reset replays avoid locking this now-live table.
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'ix_earningsnerd_job_runs_job_started') THEN
        CREATE INDEX ix_earningsnerd_job_runs_job_started ON earningsnerd_job_runs (job_name, started_at);
    END IF;
END $$;
