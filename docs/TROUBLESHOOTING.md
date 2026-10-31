# Troubleshooting Guide

This document provides solutions to common development issues encountered while working on EarningsNerd.

## Frontend Issues

### "Something went wrong!" Error Page

**Symptoms:**
- Application displays a generic error page
- Browser console shows 500 errors for static assets (`/_next/static/chunks/*.js`)
- Error message: `Cannot find module './[number].js'`

**Root Cause:**
Next.js webpack build cache corruption. This typically occurs when:
- The dev server is force-quit or crashes during a build
- Switching git branches while the dev server is running
- Running multiple dev servers simultaneously
- File system conflicts or disk issues

**Solution:**
```bash
# Stop the dev server (Ctrl+C or kill the process)
# Unix/macOS:
pkill -f "next dev"
# Windows:
# taskkill /F /IM node.exe

# Clear the build cache
cd frontend
npm run clean

# Restart the dev server
npm run dev
```

**Prevention:**
- Always gracefully stop the dev server before switching git branches
- Use `npm run dev:clean` if you suspect cache issues
- Avoid running multiple dev servers on the same codebase

---

### Module Resolution Errors

**Symptoms:**
- Import errors for installed packages
- `Cannot find module` errors in the console

**Solution:**
```bash
# Clear all caches and reinstall dependencies
cd frontend
npm run clean:all
# Remove node_modules (cross-platform with rimraf if installed globally, or use npx)
npx rimraf node_modules
npm install
```

---

### Port Already in Use

**Symptoms:**
- Error: `Port 3000 is already in use`

**Solution:**
```bash
# Find and kill the process using port 3000

# Unix/macOS:
lsof -ti:3000 | xargs kill -9

# Windows (Command Prompt):
# netstat -ano | findstr :3000
# taskkill /PID <PID> /F

# Or use a different port
PORT=3001 npm run dev
# Windows (PowerShell):
# $env:PORT=3001; npm run dev
```

---

## Backend Issues

### Database Connection Errors

**Symptoms:**
- `sqlalchemy.exc.OperationalError: unable to open database file`

**Solution:**
```bash
# Ensure the database file exists
cd backend
python -c "from app.database import engine, Base; Base.metadata.create_all(bind=engine)"
```

---

### API Not Responding

**Symptoms:**
- Frontend shows network errors
- Backend is not accessible at `http://localhost:8000`

**Solution:**
```bash
# Check if the backend is running
# Unix/macOS:
lsof -i :8000
# Windows:
# netstat -ano | findstr :8000

# If not running, start it
cd backend
uvicorn main:app --reload
```

---

## General Development Tips

### Clean Slate Restart

If you're experiencing persistent issues, try a complete clean restart:

```bash
# Stop all services
# Unix/macOS:
pkill -f "next dev"
pkill -f "uvicorn"
# Windows:
# taskkill /F /IM node.exe
# taskkill /F /IM python.exe

# Frontend cleanup
cd frontend
npm run clean:all
npx rimraf node_modules
npm install

# Backend cleanup (if needed)
cd ../backend
npx rimraf __pycache__
npx rimraf .pytest_cache

# Restart services
# Terminal 1: Backend
cd backend
uvicorn main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

### Checking Service Status

```bash
# Check what's running on common ports
# Unix/macOS:
lsof -i :3000  # Frontend
lsof -i :8000  # Backend
# Windows:
# netstat -ano | findstr :3000
# netstat -ano | findstr :8000

# Check running Node processes
# Unix/macOS:
ps aux | grep node
# Windows:
# tasklist /FI "IMAGENAME eq node.exe"

# Check running Python processes
# Unix/macOS:
ps aux | grep python
# Windows:
# tasklist /FI "IMAGENAME eq python.exe"
```

---

## Getting Help

If you encounter an issue not covered here:

1. Check the browser console for detailed error messages
2. Check the terminal output for both frontend and backend
3. Review recent git commits for breaking changes
4. Check the GitHub Issues for similar problems
5. Create a new issue with:
   - Error message and stack trace
   - Steps to reproduce
   - Environment details (OS, Node version, Python version)

## Production / backend runtime issues

Moved from CLAUDE.md (July 2026, Wave 3). Operational context (caches, breaker, metrics)
is in docs/OPERATIONS.md.

### Common backend issues

| Symptom | Likely Cause | Resolution |
|---------|--------------|------------|
| Tests hang for 30+ minutes | Stale Redis connections from previous event loop | Fixed by `_reset_on_loop_change()` - update to latest code |
| `RuntimeError: Lock bound to different event loop` | asyncio.Lock created in wrong loop | Use lazy lock initialization pattern |
| High memory usage | L1 cache unbounded | Check `_cache_max_size` is set (default 1000) |
| Slow health checks | Sync DB check blocking event loop | Use `run_in_executor()` for DB operations |
| The Change Report's wording block stays `pending`, the wording review answers `unavailable`, no alert carries the "Risk factor wording" line | `ENABLE_SECTION_CHANGES` is missing from one of the processes that read it (the `earningsnerd-backend` service serves the block, the review and the dashboard counts; the `earningsnerd-filing-scan` job stores the text and writes the real-time line; the `earningsnerd-filing-digest` job writes the digest line; the task worker runs both on the durable path), or the filing or its prior has no Item 1A row yet and the hourly batch will extract it (`pending`), a row that is not `ok` (`unavailable`, `current_<status>` / `prior_<status>`), or no row and no batch that selects it (`unavailable`: `current_outside_window` / `prior_outside_window` for a filing older than the three-year window, `current_outside_cohort` / `prior_outside_cohort` for a company nobody watches and no filing of which has a summary) | Set the flag in all three deploy maps (`docs/CONFIGURATION.md`; the gate `test_section_changes_flag_placement.py` says which map is missing); read the two filings' `filing_section_text` rows (`status`, `diff_prior_filing_id`); `python scripts/extract_sections.py --tickers X` warms a cohort by hand, with `--window-days N` for a filing older than the window |
| 10-K/10-Q/20-F summaries are built on regex excerpts while `USE_EDGARTOOLS_SECTIONS=true`: prompts about 44% larger, citation fidelity down, `Excerpt provenance` logs `source: regex_fallback` | The section parse returned nothing: the document is over the 16,000,000-character cap (`Section parse skipped`), the parse failed (`Section parse found nothing for <accession>`, from `app.services.edgar`), the parse ran past its 30 s bound, 40 s for a 20-F (`Section parse timed out for <accession>`, from `app.services.edgar`; parses run one at a time, so a burst of large filings can queue past it, and the regex excerpt it leaves is stored for good), or an edgartools change moved the section headings (E28 was the October 2026 instance). An excerpt the join itself dropped logs `Excerpt not built by the enrichment join` | Count `edgartools` against `regex_fallback` provenance by day; the eval report's native-section share (`evals/regression_gate.py`) and `tests/unit/test_summary_sections_parity.py` show whether the parser itself changed. Stored excerpts are reused, so a fixed parser reaches only excerpts built afterwards |
| A real-time filing alert has no wording line while the next digest carries it | By design: the scan job's real-time pass runs before its extraction batch, so the comparison is rarely cached when the alert is selected; the digest and a rebuilt delivery are selected later | Nothing to fix. Whether the real-time pass should wait for the extraction batch is an open item under `tasks/todo.md` E27 |
| Durable tasks stop completing: `earningsnerd-task-worker` answers every delivery 503 and logs `Task identity unavailable: the worker is not configured` or `Task identity unavailable: Google's signing keys could not be read` at ERROR | The worker cannot check a task's identity: `DURABLE_TASKS_ENABLED` is off, or a `TASKS_*` setting is missing or malformed, on the worker (`_queue_path` in `app/services/durable_tasks.py`); or the hourly read of Google's signing keys failed. With `SENTRY_DSN` bound on the worker, each line also reaches Sentry by its exception's type and stack alone (F50) | Set `DURABLE_TASKS_ENABLED=true` and the complete `TASKS_*` settings on the worker (`docs/DEPLOYMENT.md`). A key-read failure clears when Google answers again; Cloud Tasks delivers each task again, up to the queue's five attempts (about 7.5 minutes at its 30 s doubling backoff); a task whose attempts all fell inside the outage is dropped, and its work runs again only when something enqueues it again (a stable key's name stays taken for 24 hours). A 401 (`Invalid task identity`) logs nothing: it is usually a token the check refused (audience, invoker, signature or expiry), but a key list Google sent as something other than JSON, or a `TASKS_WORKER_URL` that does not parse, answers 401 too |

### Fixing corrupt filing data (NULL sec_url)

If filings with NULL `sec_url` exist (causes `PendingRollbackError`), run:

```bash
# Dry run - see what would be fixed
python scripts/fix_null_sec_urls.py

# Apply fixes
python scripts/fix_null_sec_urls.py --execute

# Fix specific ticker
python scripts/fix_null_sec_urls.py --ticker BMRN --execute
```

