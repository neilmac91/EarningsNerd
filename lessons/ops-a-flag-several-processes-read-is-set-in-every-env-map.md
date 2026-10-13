# A flag several processes read is set in every env map it is deployed from, with its cadence, in one change

Date: 2026-10-13   Area: ops

**Context**: `ENABLE_SECTION_CHANGES` is read by four Cloud Run processes deployed from three
`--update-env-vars` maps in `.github/workflows/ci.yml`: the `earningsnerd-backend` service serves the
Change Report's `section_changes` block, the wording review and the dashboard counts; the
`earningsnerd-filing-scan` job extracts and stores the Item 1A text the block is built from and writes
the real-time alert's wording line; the `earningsnerd-filing-digest` job writes the digest's line (the
jobs share one map); and the `earningsnerd-task-worker` service runs the scan and the digest when
`DURABLE_TASKS_ENABLED` routes them there. Set on the service alone, every block stays `pending` for
want of text, every review answers `unavailable` and no alert carries the line; set on the jobs alone,
the scan fetches text from the SEC for a block nobody is served. PR A's docs said "set it on both
processes when it flips" and counted two readers; PR C's review counted four. The docs also said "add
`section-extraction` to `JOB_CADENCES` so `job_health` watches the batch", and
`tests/unit/test_prod_flag_visibility.py` already showed the shape of a test that reads the deploy maps.

**Rule**: before a flag flips, list every process that reads it (grep `settings.<FLAG>`, then follow
each reader to the entrypoints that run it: the service, each job image, the task worker on the
durable path) and the deploy map each is configured from; flip it in every one of those maps in the
same commit, with the job cadence `job_health` needs to watch the work the flag turns on. Write the
gate with the flag: it fails the flag on some maps and not the others, differing values, a job carrying
an on value with no cadence, and the flag spelled anywhere else in the workflows (a flip lands in the
maps or it is not a flip). The default stays off in `Settings` until the flip; the gate pins the
placement, not the default.

**Evidence**: gate `backend/tests/unit/test_section_changes_flag_placement.py` (reads the service, task
worker and jobs steps; self-tested on the bad shapes); `backend/app/services/internal_task_runner.py`
(the durable path runs `run_filing_scan` and `run_daily_digest` on the worker);
`backend/scripts/filing_scan.py` (the extraction batch under `section-extraction`);
`docs/CONFIGURATION.md` (the `ENABLE_SECTION_CHANGES` row); `backend/app/services/job_run_service.py::JOB_CADENCES`.
