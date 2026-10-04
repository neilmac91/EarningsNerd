# Critique environment (2026-10-04)

Reproducible test environment used for the Impeccable critique of `frontend/app/filing/[id]/page.tsx`
(see `tasks/critique-handoff-2026-10-04.md`, `tasks/critique-run-notes-2026-10-04.md` and the archive under
`.impeccable/critique/`). It is critique tooling, not application code: nothing here ships, runs in CI or touches
production state. The mock backend proxies read-only public GETs to `https://api.earningsnerd.io` (cached under
`cache/`, gitignored; provenance recorded in `fixtures/CACHE_MANIFEST.json`) and simulates every authenticated,
Pro, error and streaming state locally.

## Run

```bash
cd tasks/critique-env-2026-10-04
python3 build_fixture.py                       # checks fixtures/filing-3-content.md against a fresh regeneration (--force rewrites it + PROVENANCE.json)
./start_mock.sh                                # mock backend on http://localhost:8010 (own process group; PID in mock.pid)
source env.sh                                  # production-matching flags, API base http://localhost:8010
(cd ../../frontend && npm ci && npm run build) # build against the mock (it must be running: the homepage ISR fetches it)
./start_next.sh                                # production server on http://localhost:3000 (own process group; PID in next.pid)
node capture.mjs --jobs jobs-baseline.json     # 65 captures → evidence/ (gitignored)
node capture.mjs --out demo --route /filing/3 --scenario pro,content --theme dark --viewport 390x844 \
  --coach-seen --steps 'click=role:button:Ask this Filing;wait=700;shot=sheet'    # one targeted capture
./run_detect.sh                                # one deterministic Impeccable scan → scans/detect-<sha>.json + .meta.json
python3 cache_manifest.py                      # record which production responses the run used → fixtures/CACHE_MANIFEST.json
./stop_env.sh                                  # stops exactly what the start scripts started (see Shutdown)
```

### Browser resolution (`browser.mjs`, shared by `capture.mjs`, `verify_probe.mjs`, `verify_trace.mjs`)

1. `CHROMIUM_PATH`, when set, is used as given and must exist (an explicit caller value is never overridden; a wrong
   path fails with the message `CHROMIUM_PATH is set to "…" but no file exists there`).
2. Otherwise Playwright's own Chromium, when installed (`npx playwright install chromium` in `frontend/`).
3. Otherwise a Chromium under `PLAYWRIGHT_BROWSERS_PATH` or `/opt/pw-browsers` (the cloud image's preinstall, either the
   `chromium` symlink or `chromium-*/chrome-linux*/chrome`).
4. Otherwise a clear error naming both remedies.

`env.sh` only offers `/opt/pw-browsers/chromium` when `CHROMIUM_PATH` is unset and that file exists. Each script prints the
browser it launched (`[capture] chromium: …`). Module paths are derived with `fileURLToPath`/`pathToFileURL`, so a checkout
path containing spaces works.

### Shutdown (`stop_env.sh`)

Each server is stopped through the PID file its start script wrote: the PID must still exist, its `/proc/<pid>/cmdline` must
contain the expected command (`mock_api.py`, `next start`), and then its own process group (created with `setsid`) receives
SIGTERM, with SIGKILL after 10 s. A PID whose command line does not match is reported and left alone; stale PID files are
removed. There are no pattern kills, so unrelated processes whose arguments merely mention `mock_api.py` or `next start`
survive (proof transcript in the run notes). An Impeccable live server is stopped through its own launcher only when this
environment recorded starting one (`touch live-server.started` after `impeccable live-server --background`).

## Scenarios (cookie `en_scenario` on `localhost`, or header `X-EN-Scenario`; comma-joined)

`anon` (default) | `free` | `pro` — identity/plan · `content` — serve `fixtures/filing-3-content.md` for
`/api/filings/3/content` only (other ids pass through to production) · `nosummary` — summary 404 until a mocked
generate-stream completes · `summaryerror` — summary GET 500 · `partial` — quality.tier=partial · `genfail` — generation
stream ends in an error · `askfail` — ask-stream 500 · `exhausted` — free user with no Copilot taste left · `saved` · `watch` ·
`slow` — +2.5 s on summary/content reads · `offline` — every proxied read 503.

## Files

- `mock_api.py` — the mock backend; `env.sh` — build/runtime flags; `start_mock.sh` / `start_next.sh` / `stop_env.sh` — lifecycle.
- `capture.mjs` — Playwright capture harness (usage and step DSL at the top of the file); `browser.mjs` — browser resolution.
- `jobs-baseline.json` (65 jobs), `jobs-extra.json`, `jobs-verify.json` — the captured matrices; `verify_probe.mjs` /
  `verify_trace.mjs` — the orchestrator's verification probes (reflow culprits, keyboard popover reach, the Trace-to-Source
  click under five conditions).
- `detect_targets.txt` — detector scope (paths relative to `frontend/`; `#` comments and blank lines are ignored by
  `run_detect.sh`, which validates each path and passes them as an argument array); `scans/` — recorded scans with their
  source SHA and `frontend` tree hash.
- `fixtures/filing-3-content.md` — the committed, labelled fixture; `fixtures/PROVENANCE.json` — its source response, hashes
  and generation time; `fixtures/CACHE_MANIFEST.json` — the production responses the mock cached (the cache itself is gitignored).
- `briefs/` — the two isolated assessment briefs as issued; their absolute scratchpad paths are historical.

## Caveats

- `fixtures/filing-3-content.md` is a SYNTHETIC, labelled abridged 10-K built from the real summary's cited excerpts so the
  in-app highlight path can be exercised. `build_fixture.py` without flags reports whether a regeneration from the cached
  production summary still MATCHES the committed bytes (keep the committed fixture for repeatable runs; `--force` rewrites it
  and `PROVENANCE.json`). On 2026-10-04, `GET /api/filings/{id}/content` returned `has_content=false` for each of the 59 filing
  ids sampled (listed in the run notes); that is a dated observation about those ids, not a statement about every filing.
  Findings that depend on the fixture are marked fixture-dependent in the report.
- Copilot and analysis answers are canned (`mock_api.py`: `ask_completion`, the repo's `demo-analysis.json`).
- `evidence/`, `cache/`, `*.log`, `*.pid`, `*.stdout` and `live-server.started` are gitignored run state.
