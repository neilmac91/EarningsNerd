# Critique environment (2026-10-04)

Reproducible test environment used for the Impeccable critique of `frontend/app/filing/[id]/page.tsx`
(see `tasks/critique-handoff-2026-10-04.md`, `tasks/critique-run-notes-2026-10-04.md` and the archive under
`.impeccable/critique/`). It is critique tooling, not application code: nothing here ships, runs in CI or touches
production state. The mock backend proxies read-only public GETs to `https://api.earningsnerd.io` (cached under
`cache/`, gitignored; provenance recorded in `fixtures/CACHE_MANIFEST.json`) and simulates every authenticated,
Pro, error and streaming state locally.

Supported environment for the lifecycle scripts (`start_mock.sh`, `start_next.sh`, `stop_env.sh`): **Linux only**. They
need `/proc` (process identity) and `setsid` (one session/process group per server). Elsewhere they exit 2 with a clear
message and change nothing; stop servers manually there. The capture and verification scripts themselves are plain Node.

## Run

```bash
cd tasks/critique-env-2026-10-04
python3 build_fixture.py                       # checks fixtures/filing-3-content.md against a fresh regeneration (--force rewrites it + PROVENANCE.json)
./start_mock.sh                                # mock backend on http://localhost:8010; identity recorded in mock.proc
source env.sh                                  # production-matching flags, API base http://localhost:8010
(cd ../../frontend && npm ci && npm run build) # build against the mock (it must be running: the homepage ISR fetches it)
./start_next.sh                                # production server on http://localhost:3000; identity recorded in next.proc
node capture.mjs --jobs jobs-baseline.json     # 65 captures → evidence/ (gitignored)
node capture.mjs --out demo --route /filing/3 --scenario pro,content --theme dark --viewport 390x844 \
  --coach-seen --steps 'click=role:button:Ask this Filing;wait=700;shot=sheet'    # one targeted capture
./run_detect.sh                                # one deterministic Impeccable scan → scans/detect-<sha>.json + .meta.json
python3 cache_manifest.py                      # record which production responses the run used → fixtures/CACHE_MANIFEST.json
./stop_env.sh                                  # stops exactly the servers whose records still verify (see Lifecycle)
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

### Lifecycle: process identity records (`lifecycle.sh`)

Each start script launches its server with `setsid` in a new session/process group, waits until it answers, then writes a
record (`mock.proc`, `next.proc`) with the server's identity: `pid`, `pgid`, `sid` (both equal to `pid`), `starttime`
(`/proc/<pid>/stat` field 22, clock ticks since boot), `boot_id`, the physical `cwd` and the stable `cmd` line (Next is
launched directly from `node_modules/next/dist/bin/next`, not through `npx`, and names itself `next-server (v…)`; the
record is taken only after the command line has stopped changing). A process is treated as this environment's server only
when EVERY field still matches the live process and the `cwd` is the directory this environment expects. Both the
already-running check in the start scripts and the shutdown in `stop_env.sh` use the same verification:

- verified → `start_*` reports "already running"; `stop_env.sh` sends SIGTERM to the recorded process group (SIGKILL after 10 s)
  and removes the record;
- record present but process gone, a zombie, or from another boot → stale: the record is removed, nothing is signalled;
- malformed record (syntax is validated field by field; digits are never scraped out of arbitrary text) or a live process
  that does not match (reused pid with a different start time, same command in another directory, different command line,
  not its own session/group leader) → REFUSED: nothing is signalled, the record is moved to `<name>.proc.rejected` with the
  reason printed, `stop_env.sh` exits 1, and `start_*` goes on to start a fresh server.

An unrelated process is therefore never signalled even when its command line contains `mock_api.py` or `next`. The proof
transcript (forged records against look-alike decoys, malformed records, a simulated non-Linux host, then the normal owned
shutdown) is in the run notes. An Impeccable live server is stopped through its own launcher only when this environment
recorded starting one (`touch live-server.started` after `impeccable live-server --background`).

## Scenarios (cookie `en_scenario` on `localhost`, or header `X-EN-Scenario`; comma-joined)

`anon` (default) | `free` | `pro` — identity/plan · `content` — serve `fixtures/filing-3-content.md` for
`/api/filings/3/content` only (other ids pass through to production) · `nosummary` — summary 404 until a mocked
generate-stream completes · `summaryerror` — summary GET 500 · `partial` — quality.tier=partial · `genfail` — generation
stream ends in an error · `askfail` — ask-stream 500 · `exhausted` — free user with no Copilot taste left · `saved` · `watch` ·
`slow` — +2.5 s on summary/content reads · `offline` — every proxied read 503.

## Files

- `mock_api.py` — the mock backend; `env.sh` — build/runtime flags; `lifecycle.sh` — process-identity helpers;
  `start_mock.sh` / `start_next.sh` / `stop_env.sh` — lifecycle (Linux only).
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
- `evidence/`, `cache/`, `*.log`, `*.pid`, `*.stdout`, `*.proc`, `*.proc.rejected`, `*.unverified`, `*.tmp` and
  `live-server.started` are gitignored run state.
