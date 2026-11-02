# Split stored rows by rule where the last writer on the old image stops, never at the last job move

Date: 2026-11-02 · Area: ops / deploy, facts

**Context.** E264's preview (`backend/scripts/financial_revenue_preview.py`) and detection set 8 (`ops/detection/financial_revenue_state.sql`) label each stored revenue row old or new rule by its `created_at`. E264's split (2026-11-01 14:07:03) and E278's (21:04:12) both sat where `deploy-backend` moved the last job image. Two writers outlive that moment:
- **A service's old revision** can finish a request it holds for the services' 600-second request timeout (`ci.yml`, `--timeout=600`) after its switch. At E286's deploy (job 125162249807) that was 08:07:13 + 600 s for the backend.
- **A Cloud Run job execution** keeps the image it started on, through every retry. `backfill-facts`' Monday run started at 07:30 on the old image. No documented create command sets `--max-retries`, so Cloud Run's default three retries apply, each with the 3,600-second task timeout (`docs/OPERATIONS.md`). It could write on the old image until about 11:34.

E286's follow-up (#1946) first set the split to 08:31, the end of that run's first attempt. Its review found two gaps. The bound assumed no retry, which nobody had observed. And deleting E264's hold left nothing to make the next change to the rule (E290, E291) move the split again.

**Rule.**
1. **The row split is the latest of three moments:**
   - the last job image move;
   - each service's switch to its new revision, plus its request timeout;
   - the latest end of every job execution started on the old image, through its retries: one task timeout per attempt, plus a minute for each attempt to start.
   Use observed execution times when you can read them (`gcloud run jobs executions describe`). Otherwise use the documented settings, and say so.
2. **A split over what only the services write takes the services' bound alone.** A company's companyfacts sync (`facts_synced_at`) is one: no job runs `ingest_companyfacts`. So E286's synced test splits at 08:17:14, and its rows at 11:35:00.
3. **When unsure, err late.** A row the new rule wrote before a late split reads as old, and is listed only where it differs from the deployed rule. A row the old image wrote after an early split reads as new: it looks as if the new rule had written something wrong.
4. **The next change to the rule's code moves the split too.** After its deploy it moves the split by rule 1, and holds the reads until then. Or its PR shows that it moves no row the split judges. E264's owner names the rule's files as their next writer, so the review gate makes such a PR name E264.

**Evidence.**
- #1946 and its review: the correctness and rules-and-brief lenses.
- `deploy-backend` job 125162249807's log: the worker switched at 08:06:38, the backend at 08:07:13, and the last job moved at 08:07:43.
- `docs/OPERATIONS.md`: the default retries.
- `docs/DEPLOYMENT.md`: `backfill-facts`' `--task-timeout=3600`.
- `backend/app/services/facts/ingest.py`: the only writer of `facts_synced_at`.
