# Critique environment (2026-10-04)

Reproducible test environment used for the Impeccable critique of `frontend/app/filing/[id]/page.tsx`
(see `tasks/critique-handoff-2026-10-04.md`, `tasks/critique-run-notes-2026-10-04.md` and the archive under
`.impeccable/critique/`). It is critique tooling, not application code: nothing here ships, runs in CI or touches
production state. The mock backend proxies read-only public GETs to `https://api.earningsnerd.io` (cached under
`cache/`, gitignored) and simulates every authenticated, Pro, error and streaming state locally.

## Run

```bash
cd tasks/critique-env-2026-10-04
python3 build_fixture.py                       # fetches the production summary for filing 3 once, writes fixtures/
python3 mock_api.py > mock_api.stdout 2>&1 &   # mock backend on http://localhost:8010
source env.sh                                  # production-matching flags, API base http://localhost:8010
(cd ../../frontend && npm ci && npm run build) # build against the mock (it must be running: the homepage ISR fetches it)
./start_next.sh                                # production server on http://localhost:3000
CHROMIUM_PATH=/opt/pw-browsers/chromium node capture.mjs --jobs jobs-baseline.json   # 65 captures → evidence/
node capture.mjs --out demo --route /filing/3 --scenario pro,content --theme dark --viewport 390x844 \
  --coach-seen --steps 'click=role:button:Ask this Filing;wait=700;shot=sheet'    # one targeted capture
./stop_env.sh                                  # stops next + mock (+ an Impeccable live-server if one runs)
```

`CHROMIUM_PATH` is optional; without it Playwright uses its own browser (run `npx playwright install chromium`
in `frontend/` if it is missing). `capture.mjs --help`-style usage and the step DSL are documented at the top of the file.

## Scenarios (cookie `en_scenario` on `localhost`, or header `X-EN-Scenario`; comma-joined)

`anon` (default) | `free` | `pro` — identity/plan · `content` — serve `fixtures/filing-3-content.md` for
`/api/filings/3/content` · `nosummary` — summary 404 until a mocked generate-stream completes · `summaryerror` — summary
GET 500 · `partial` — quality.tier=partial · `genfail` — generation stream ends in an error · `askfail` — ask-stream 500 ·
`exhausted` — free user with no Copilot taste left · `saved` · `watch` · `slow` — +2.5 s on summary/content reads ·
`offline` — every proxied read 503.

## Caveats

- `fixtures/filing-3-content.md` is a SYNTHETIC, labelled abridged 10-K built from the real summary's cited excerpts so the
  in-app highlight path can be exercised; production serves no in-app filing text (`has_content=false` for every filing
  sampled on 2026-10-04). Findings that depend on it are marked fixture-dependent in the report.
- Copilot and analysis answers are canned (`mock_api.py`: `ask_completion`, the repo's `demo-analysis.json`).
- `verify_probe.mjs` / `verify_trace.mjs` are the orchestrator's verification probes (reflow culprits, keyboard popover
  reach, the Trace-to-Source click under five conditions); `jobs-verify.json` / `jobs-extra.json` are the targeted runs.
- `briefs/` are the two isolated assessment briefs as issued; their absolute scratchpad paths are historical.
- `detect_targets.txt` is the Impeccable detector scope (paths relative to `frontend/`; pass them with `frontend/` prefixed).
