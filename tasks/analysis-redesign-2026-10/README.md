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
  table and column widths, sticky-column occlusion at every scroll rest position, label counts, in the
  same ten configurations as the prototype harness (six widths, 200% zoom, 200% text at 1480, 390 and
  320), both themes. Output: `measurements/current.json`.
  The recorded run measured `main` at `97293e7`, before #1199–#1203 replaced the labels, the cards, the
  table, the dialog, the narrative and the picker; it was retaken with the widened probes (text-node
  rectangles, both sides of each cell's content box, every scroll rest position) and the phone
  200%-text profiles on that same build. The
  script selects Quarterly, mocks the API's field names, stores the app's consent key, waits for fonts,
  finds the shipped markup by data attribute (`[data-analysis-kpi]`, `[data-kpi-value]`,
  `[data-analysis-data-notes]`) with a fallback to the `97293e7` markup, and fails the run when a probe
  does not find what it expects (4 cards, 13 header cells, the metric rows).
- `harness/measure-proto.mjs` — the same probes on the prototype, in every state and both views, at
  1480 / 1054 / 1024 / 768 / 390 / 320 CSS px, light and dark, 200% browser zoom (CSS viewport halved at
  2x) and 200% text size at 1480, 390 and 320. Output: `measurements/prototype.json`. Since the
  comprehensive review of 2026-10-10 the probes read the rendered text (text-node rectangles and
  `scrollWidth` against `clientWidth` of every block, `.sr-only` excluded), test cell text against the
  cell's content box on both sides (a right-aligned overflow runs to the inline start, which `scrollWidth`
  never counts), visit every scroll rest position for a header straddling the sticky edge, and record the
  Chromium, platform and commit of the run. `EN_PROTO.state.noPad = true` removes the whole-column pad for
  the occlusion mutation proof (at 1024 the probe then reports the Q4 ’23 column straddling the edge).
- `harness/build_states.py`, `harness/prune_states.py` — reproduce `prototype/data/` from a saved
  companyfacts payload.
- `measurements/` — the two recorded runs the proposal cites.
- `astra-prompt.md` — the hand-over prompt for the implementing agent (GPT-6 Astra / Codex), with the
  founder's §9 decisions recorded.
- `review-2026-10-10.md` — the comprehensive review's findings, ranked, with what each changed in this
  folder and in the proposal and what remains open for the implementation.

Screenshots are not committed (binary bloat; the critique environment kept its evidence out of the
repository too). Both harnesses take `--shots <dir>` to regenerate them. Both compare the document
with the configured viewport width, never with `window.innerWidth`: mobile Chromium widens the layout
viewport to overflowing content, which hid a phone overflow in the first prototype build (proposal
§11). "200% zoom" in the configuration list is 2x device-scale emulation at half the CSS width.

## How the data was produced

1. Fetch `https://data.sec.gov/api/xbrl/companyfacts/CIK0001326801.json` (one request, descriptive
   User-Agent) to a scratch directory.
2. From the repository root, with `backend/`'s requirements installed (the script puts `backend/` on
   `sys.path` itself, so it runs from any directory):
   `python tasks/analysis-redesign-2026-10/harness/build_states.py <dir>/CIK0001326801.json <out>`
   runs `normalize_companyfacts` → `upsert_facts_bulk` → `build_dataset(quarterly, 2023Q3..2026Q2)` →
   `build_observation_catalogue` → `render_observation_selection` → `resolve_narrative_citations` →
   `scan_numeric_fidelity` inside a private SQLite database (the hermetic test environment's
   variables). It writes three states:
   - `clean`: the engine's own output on a fresh ingest (every calculation carries its lineage). This is
     not the state the production data repair produces: `frontend/tests/unit/fixtures/meta-data-notes.json`
     on `main` is the captured production dataset and keeps its own `not_in_dataset` and
     `legacy_calculation_not_supported` gaps. The gate #1206 landed (`tests/e2e/analysis-layout.spec.ts`)
     uses this folder's three states as hash-pinned visual fixtures instead; the capture-based cases of
     proposal §7 item 10 remain a follow-up.
   - `legacy`: ten computed rows have their stored provenance removed, as rows written before #1191 are
     (the `legacy_calculation` path of `fact_provenance.provenance_for_fact`), modelled on the cells the
     production screenshots show warned. The four capex / free-cash-flow gaps for Q3–Q4 2023 and the six
     EPS gaps on calculated fourth quarters are the engine's real output, not an injection.
   - `discrepancy`: the latest reported revenue carries `source_conflict`; the two margins calculated from
     it carry the same reason on that operand. This is a simulation of the state the engine produces when
     sources disagree; it does not claim Meta's filings disagree.
3. `python tasks/analysis-redesign-2026-10/harness/prune_states.py <out> tasks/analysis-redesign-2026-10/prototype/data`
   (a re-run from the repository root on 2026-10-10 reproduced the committed files exactly, apart from
   the `data_as_of` / `synced_at` run timestamps) keeps every displayed figure, comparison,
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
