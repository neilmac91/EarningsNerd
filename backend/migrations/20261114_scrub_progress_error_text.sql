-- Progress rows written before 2026-11-14 can hold an exception's text. Until that day's release the generic
-- failure handler stored str(exception) in summary_generation_progress.error, and
-- GET /api/summaries/filing/{id}/progress serves that column without authentication. The handler now stores the
-- fixed code summary_generation_failed (app/services/summary_stages/failure.py), but a row keeps what it holds
-- until its filing is generated again, and nothing purges it.
--
-- Replace the text with that code in every row last written before the cutoff whose error is not one of the
-- fixed values the application writes: its two failure codes, the two source-failure codes, the timeout and
-- stall sentences, and the model layer's one sentence. Those rows are left as they are, so what they say
-- about an old failure is kept. An empty error is replaced too: it is an exception that carried no message.
--
-- The cutoff is 16:00 UTC on 2026-11-14. The service and the workers switched to the fixed code at about
-- 10:36 UTC. A request there runs for at most 10 minutes, and a job execution keeps its image through at
-- most four one-hour tasks, so no process could store raw text after 14:36. The cutoff also bounds a later
-- run of this file (a ledger reset): whatever fixed values the application writes by then, a row written
-- after it is never touched.
--
-- Data only: one UPDATE of the matching rows, under the row locks it takes. It sets error and nothing else,
-- so stage, updated_at and the stored coverage stay. The ledger applies it once per sha256. Re-running is
-- safe: a replaced row holds the fixed code and no longer matches.
SET lock_timeout = '5s';
SET statement_timeout = '30s';
UPDATE summary_generation_progress
SET error = 'summary_generation_failed'
WHERE error IS NOT NULL
  AND updated_at < '2026-11-14 16:00:00+00'
  AND error NOT IN (
    'summary_generation_failed',
    'filing_source_unavailable',
    'sec_rate_limited',
    'Pipeline timeout',
    'Generation stalled and was abandoned. Please retry.',
    'We could not generate this summary. Try again shortly.'
  );
RESET statement_timeout;
RESET lock_timeout;
