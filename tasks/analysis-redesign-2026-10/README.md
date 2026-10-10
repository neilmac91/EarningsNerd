# Multi-Period Analysis redesign — prototype, harnesses and measurements (2026-10-10)

Support material for the design proposal in
[`docs/design/analysis-data-notes-redesign-2026-10.md`](../../docs/design/analysis-data-notes-redesign-2026-10.md).
Nothing here ships, runs in CI or touches production: it is design tooling in the manner of
`tasks/critique-env-2026-10-04/`.

## What is here

- `prototype/` — a runnable, dependency-free page (`index.html`, `styles.css`, `app.js`) that renders the
  proposed treatment of the analysis results on the real META 12-quarter dataset in three states, with a
  reproduction of today's markup for side-by-side measurement. Open `prototype/index.html` in a browser
  (fonts load from Google Fonts; without network the system fallbacks render). The bar at the top is
  prototype chrome, not part of the design: state, view, table window, theme and 200% text size.
- `prototype/data/` — the dataset and narrative for each state, produced by the repository's own engine
  (see "How the data was produced"), pruned to what the page renders. Figures are the real SEC
  companyfacts values for Meta Platforms, Inc. as fetched on 2026-10-10; the narrative is the engine's
  observation catalogue rendered with a deterministic "first three per section" selection instead of the
  model's choice (the sentence text is identical to production's; only which optional sentences appear
  differs). No AI was called.
- `harness/measure-current.mjs` — measures the CURRENT components on the repository's own frontend build
  (`next build` + `next start` with `NEXT_PUBLIC_ENABLE_ANALYSIS=true`, every API answered in the browser
  with `page.route`, as `tests/e2e` does): page overflow, KPI card-child containment and value alignment,
  table and column widths, far-right sticky-column occlusion, label counts. Output: `measurements/current.json`.
- `harness/measure-proto.mjs` — the same probes on the prototype, in every state and both views, at
  1480 / 1054 / 1024 / 768 / 390 / 320 CSS px, light and dark, 200% browser zoom (CSS viewport halved at
  2x) and 200% text size. Output: `measurements/prototype.json`.
- `harness/build_states.py`, `harness/prune_states.py` — reproduce `prototype/data/` from a saved
  companyfacts payload.
- `measurements/` — the two recorded runs the proposal cites.
- `astra-prompt.md` — the hand-over prompt for the implementing agent (GPT-6 Astra / Codex), with the
  founder's §9 decisions recorded.

Screenshots are not committed (binary bloat; the critique environment kept its evidence out of the
repository too). Both harnesses take `--shots <dir>` to regenerate them. Both compare the document
with the configured viewport width, never with `window.innerWidth`: mobile Chromium widens the layout
viewport to overflowing content, which hid a phone overflow in the first prototype build (proposal
§11). "200% zoom" in the configuration list is 2x device-scale emulation at half the CSS width.

## How the data was produced

1. Fetch `https://data.sec.gov/api/xbrl/companyfacts/CIK0001326801.json` (one request, descriptive
   User-Agent) to a scratch directory.
2. From `backend/` with its requirements installed:
   `python harness/build_states.py <dir>/CIK0001326801.json <out>` runs `normalize_companyfacts` →
   `upsert_facts_bulk` → `build_dataset(quarterly, 2023Q3..2026Q2)` → `build_observation_catalogue` →
   `render_observation_selection` → `resolve_narrative_citations` → `scan_numeric_fidelity` inside a
   private SQLite database (the hermetic test environment's variables). It writes three states:
   - `clean`: the engine's own output on a fresh ingest (every calculation carries its lineage).
   - `legacy`: ten computed rows have their stored provenance removed, as rows written before #1191 are
     (the `legacy_calculation` path of `fact_provenance.provenance_for_fact`), modelled on the cells the
     production screenshots show warned. The four capex / free-cash-flow gaps for Q3–Q4 2023 and the six
     EPS gaps on calculated fourth quarters are the engine's real output, not an injection.
   - `discrepancy`: the latest reported revenue carries `source_conflict`; the two margins calculated from
     it carry the same reason on that operand. This is a simulation of the state the engine produces when
     sources disagree; it does not claim Meta's filings disagree.
3. `python harness/prune_states.py <out> prototype/data` keeps every displayed figure, comparison,
   validation state, reason, formula and first-level operand with its own lineage, and drops deeper
   nesting. The result is a visual reference, not the API schema: the provenance `version` is dropped
   and a comparison's operands are flattened to concept, value, period and validation.

## Running the harnesses

```bash
# current components: build and serve the frontend from frontend/ (the critique environment's flags; no backend)
(cd frontend && NEXT_PUBLIC_ENABLE_ANALYSIS=true NEXT_PUBLIC_API_BASE_URL=http://localhost:8010 npm run build)
(cd frontend && WAITLIST_MODE=false npx next start -p 3000 &)
# then, from the repository root, with Playwright resolvable (the frontend's install, or the cloud image's global one)
NODE_PATH="$PWD/frontend/node_modules" node tasks/analysis-redesign-2026-10/harness/measure-current.mjs --base http://localhost:3000 --shots /tmp/shots

# prototype (no server needed; --fonts answers Google Fonts from a local directory when offline)
NODE_PATH="$PWD/frontend/node_modules" node tasks/analysis-redesign-2026-10/harness/measure-proto.mjs --shots /tmp/shots
```

Both scripts resolve Playwright through `createRequire`, so the cloud image's global install
(`NODE_PATH=/opt/node-tools/node_modules`, `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`) or the frontend's
own `@playwright/test` works.
