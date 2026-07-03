-- Earnings-calendar engine (tasks/earnings-calendar-strategy.md §3.3 / §3.7).
-- Applied manually in prod (no Alembic); Base.metadata.create_all() also creates these at startup.
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS earnings_events (
    id                 BIGSERIAL PRIMARY KEY,
    ticker             VARCHAR(16) NOT NULL,
    cik                VARCHAR(10),
    company_name       TEXT,
    fiscal_period_end  DATE NOT NULL,
    event_date         DATE NOT NULL,
    event_time         VARCHAR(3),               -- bmo | amc | dmh | NULL
    status             VARCHAR(10) NOT NULL DEFAULT 'estimated',  -- estimated | confirmed | reported
    confidence         VARCHAR(10) NOT NULL DEFAULT 'medium',     -- high | medium | low
    eps_estimate       NUMERIC,
    eps_actual         NUMERIC,
    anticipation_score NUMERIC NOT NULL DEFAULT 0,
    source             VARCHAR(20) NOT NULL DEFAULT 'pattern',    -- alpha_vantage | edgar_8k | pattern
    accession_number   VARCHAR(25),
    prior_event_date   DATE,
    date_changed_at    TIMESTAMPTZ,
    first_seen_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    reported_at        TIMESTAMPTZ,
    CONSTRAINT uq_earnings_events_ticker_period UNIQUE (ticker, fiscal_period_end)
);

CREATE INDEX IF NOT EXISTS ix_earnings_events_event_date ON earnings_events (event_date);
CREATE INDEX IF NOT EXISTS ix_earnings_events_ticker     ON earnings_events (ticker);
-- top-N-per-day for the anticipated-earnings surfaces
CREATE INDEX IF NOT EXISTS ix_earnings_events_day_rank   ON earnings_events (event_date, anticipation_score);

CREATE TABLE IF NOT EXISTS earnings_alert_log (
    id                BIGSERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    earnings_event_id INTEGER NOT NULL REFERENCES earnings_events(id) ON DELETE CASCADE,
    event_date        DATE NOT NULL,
    channel           VARCHAR(20) NOT NULL DEFAULT 'email',
    status            VARCHAR(20) NOT NULL DEFAULT 'sent',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_earnings_alert_log_user_event_date_channel
        UNIQUE (user_id, earnings_event_id, event_date, channel)
);

CREATE INDEX IF NOT EXISTS ix_earnings_alert_log_user  ON earnings_alert_log (user_id);
CREATE INDEX IF NOT EXISTS ix_earnings_alert_log_event ON earnings_alert_log (earnings_event_id);

-- Per-company earnings-day alert opt-in on the existing watchlist rows.
ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS earnings_alert BOOLEAN NOT NULL DEFAULT false;
