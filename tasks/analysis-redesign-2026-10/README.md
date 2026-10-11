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
  table and column widths, sticky-column occlusion at the start, every column boundary and the far-right end
  (with the table's scroll-snap-type: the build at 97293e7 does not snap, so a scroll can rest anywhere between
  boundaries), label counts, in the
  same ten configurations as the prototype harness (six widths, 200% zoom, 200% text at 1480, 390 and
  320), both themes. Output: `measurements/current.json`. By default it serves the build itself (`next start`
  through Next's own CLI, in `build-hash.mjs`'s controlled environment with `WAITLIST_MODE=false`, on `--port`,
  default 3100), records how, and stops the server when the run ends; it checks the build's output and its install
  against the stamp before it serves and again after the server stops, and writes the recording only if both hold; `--base <url>` measures a server started
  elsewhere, whose environment it cannot see, and the baseline refuses that, as it refuses any browser but the one
  `browser-pin.mjs` pins.
  The recorded run measured `main` at `97293e7`, before #1199–#1203 replaced the labels, the cards, the
  table, the dialog, the narrative and the picker; it was retaken with the widened probes (text-node
  rectangles, both sides of each cell's content box, every column boundary) and the phone
  200%-text profiles on that same build. The
  script selects Quarterly, mocks the API's field names, stores the app's consent key, waits for fonts,
  finds the shipped markup by data attribute (`[data-analysis-kpi]`, `[data-kpi-value]`,
  `[data-analysis-data-notes]`) with a fallback to the `97293e7` markup, and fails the run when a probe
  does not find what it expects (4 cards, 13 header cells, exactly the dataset's 20 metric rows).
- `harness/measure-proto.mjs` — the same probes on the prototype, in every state and both views, at
  1480 / 1054 / 1024 / 768 / 390 / 320 CSS px, light and dark, 200% browser zoom (CSS viewport halved at
  2x) and 200% text size at 1480, 390 and 320. Output: `measurements/prototype.json`. Since the
  comprehensive review of 2026-10-10 the probes read the rendered text (text-node rectangles and
  `scrollWidth` against `clientWidth` of every block, `.sr-only` excluded), test cell text against the
  cell's content box on both sides (a right-aligned overflow runs to the inline start, which `scrollWidth`
  never counts), visit the start, every column boundary and the far-right end, where the table snaps, for a
  header straddling the sticky edge, hover a metrics
  row and fail on a translucent fill behind the sticky row header (the values beneath it would show through), assert their
  element counts (4 cards; 13 header cells in the 12-quarter window and 7 in Newest 6; exactly the
  dataset's 20 metric rows) so
  a probe that finds nothing fails the run, and record the Chromium, platform, commit and prototype tree
  hash of the run, refusing uncommitted prototype or harness files unless `--allow-dirty` records them, and
  writing the committed recording only from a committed tree and the pinned fonts, in the pinned browser (a dirty
  run, an online run, a run with other fonts or in another browser needs `--out` naming another file; a symbolic or hard link to the recording counts as it, and
  any other multiply linked output is refused). `EN_PROTO.state.noPad = true` removes the whole-column pad for
  the occlusion mutation proof (at 1024 the probe then reports the Q4 ’23 column straddling the edge).
- `harness/build-stamped.mjs` — builds a checkout's frontend for `measure-current.mjs` and stamps the build
  with its inputs (`frontend/.next/SOURCE_TREE.json`): it refuses uncommitted frontend files and the untracked
  env files `next build` loads (git ignores all four, so `git status` never shows them), reinstalls the checkout's
  `node_modules` with `npm ci` from the lockfile right before the build, so the packages the build runs are the
  lockfile's tarballs (`node_modules` is ignored by git, so an install made for another revision or edited since
  would otherwise build silently; npm keeps its network settings, but its node-options and script-shell settings are
  set back to npm's defaults on the command line, since they would run code in every install script), then refuses
  an install that is not the one `package-lock.json` describes (a package missing or at another version, or a
  top-level package the lockfile does not list; an optional platform package may be absent), runs `next build`
  itself on the Node running the script rather than through npm (npm's own configuration, its npmrc files and
  `npm_config_*` variables, can add Node options to everything it runs), with an allowlisted environment (what the
  toolchain needs to run and reach the network, the caller's `NEXT_PUBLIC_*` variables, and `NODE_OPTIONS` only
  while it holds nothing but heap sizes: its other flags, such as `--require`, run code in every build process, so
  they are refused; credentials, Sentry and Vercel variables are dropped), and records the stamp's format, the
  commit, the `frontend/` tree, the build id, Node and its heap sizes, the npm version and the install's package counts, the public variables, a content hash of
  `.next/static/media`, where the fonts `next/font` downloads at build time sit, a content hash of the build's
  whole output (everything under `.next` but Next's caches) and a content hash of `node_modules` after the build, so
  a file edited, added or removed in either after the stamp no longer matches it.
- `harness/build-hash.mjs` — how `build-stamped.mjs` and `measure-current.mjs` hash a build, the stamp format they
  share, and the controlled environment both run Next in (the build, and the harness's own server), so the stamp's
  writer and its checker agree: the media hash, which is reproducible across builds of one
  tree (the baseline pins it), and the output hash, which leaves out `cache/`, `next dev`'s `dev/`, the pages
  `next start` caches in `server/route-cache/` while it serves, and the stamp. It differs between two builds of one
  tree (the build id and the prerendered pages differ), so it binds the served bytes to one stamped build and is not
  pinned; and the install hash, everything under `node_modules` but a tool cache, which `next start` does not write.
  The baseline needs a stamp of the current format, `STAMP_FORMAT`, raised whenever what a stamp guarantees
  changes.
- `harness/browser-pin.mjs` — the browser both recordings were measured in, Chromium 141.0.7390.37 on linux x64
  (Playwright 1.56.1's build, the cloud image's global install). Layout is the browser's: another Chromium version,
  or the same one on another platform, can shape text and break lines differently, so the recordings' widths,
  clipping and occlusion are that browser's, and they compare like for like only from one browser. Both harnesses
  check it right after launch and write their recording only in it; a run in any other needs `--out`. The
  frontend's own `@playwright/test` (1.63) runs Chromium 153, in which the `97293e7` build measures differently
  in every configuration (the note under the commands below gives the numbers).
- `harness/build_states.py`, `harness/prune_states.py` — reproduce `prototype/data/` from a saved
  companyfacts payload.
- `measurements/` — the two recorded runs the proposal cites.
- `astra-prompt.md` — the briefing prompt the founder asked for, to paste into the implementing agent's
  session (GPT-6 Astra / Codex). The hand-over of record is the Engineering row in `tasks/todo.md`
  (`AGENTS.md` §7); the proposal's §7 and §9 carry the status and the founder's decisions, and the prompt
  points at them rather than restating them.
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
# current components: build the frontend from frontend/ (the critique environment's flags; no backend); the
# harness serves it. measurements/current.json records main at 97293e7, before Phase 1 landed. To reproduce it,
# build the frontend in a worktree of that revision (97293e7 has no harness, so the harness runs from this tree and
# --build names the worktree whose build it serves and measures); on current main the harness measures the shipped
# components instead, and the counts and geometry differ by design.
git worktree add ../en-97293e7 97293e7
# build-stamped.mjs installs the worktree's packages with `npm ci` and runs `next build` itself (not through npm)
# from the clean checkout, with an allowlisted environment, refusing NODE_OPTIONS flags other than heap sizes, and
# stamps frontend/.next/SOURCE_TREE.json with its format, commit, frontend/ tree, build id, Node and heap sizes,
# install, public variables, downloaded fonts and the hash of its whole output; the harness requires that stamp for
# the baseline, with exactly these two variables (.next is ignored by git)
NEXT_PUBLIC_ENABLE_ANALYSIS=true NEXT_PUBLIC_API_BASE_URL=http://localhost:8010 node tasks/analysis-redesign-2026-10/harness/build-stamped.mjs ../en-97293e7
# then, from this repository's root, with Playwright 1.56.1, whose Chromium (141.0.7390.37 on linux x64) is the
# browser both recordings pin (harness/browser-pin.mjs; the frontend's own Playwright is newer, and the recordings
# refuse its Chromium): the cloud image's global install is that version, and on any linux x64 machine these two
# lines give it
npm install --prefix /tmp/pw-1.56 --no-audit --no-fund playwright@1.56.1
/tmp/pw-1.56/node_modules/.bin/playwright install chromium
# the harness serves the build itself (`next start` through Next's own CLI, in the same controlled environment,
# with WAITLIST_MODE=false, which lets /analysis through the middleware, on port 3100 unless --port says otherwise)
NODE_PATH=/tmp/pw-1.56/node_modules node tasks/analysis-redesign-2026-10/harness/measure-current.mjs --build ../en-97293e7 --shots /tmp/shots
# The harness reads the served checkout's commit, frontend/ tree hash, uncommitted files under frontend/,
# .next/BUILD_ID and the build's time, refuses a build older than that checkout's last commit touching frontend/
# (it cannot see which tree a build came from, so build right before measuring), verifies before measuring that
# the server serves that build id, and records them with its own commit. A stamp (SOURCE_TREE.json, written by
# build-stamped.mjs) must name the served build id and the checkout's frontend/ tree, its media hash must match
# the build's .next/static/media and its output hash everything under .next but Next's caches, whenever one is
# present, and is recorded; the baseline needs a stamp of the current format (build-hash.mjs's STAMP_FORMAT) and the
# harness's own server, which the recording describes under server. The fixtures --data names (default: prototype/data) are recorded by a content hash of their .js
# files and, inside this repository, by their tree hash with their uncommitted files. It writes
# measurements/current.json only for a served build of 97293e7 (enforced whether --out names that file, an alias
# of it through symbolic or hard links, or it is the default; any other multiply linked output is refused), for the legacy state from the committed fixtures at the content hash the harness pins (retaking
# from other fixtures needs a new pin), from clean trees (no uncommitted frontend, harness or fixture files) and
# from a stamped build whose public variables and downloaded fonts match the pins (26 files, sha256 d7c8317fed90…;
# two builds of 97293e7 on 2026-10-11 hashed alike, and other fonts need a new pin), and in the pinned browser
# (browser-pin.mjs): a fresh measurement of any other build, state, data or browser (--build defaults to this
# repository) needs --out naming another file, and an --out that holds a recording of another commit is refused.

# prototype (no server needed). --fonts answers Google Fonts from a local directory: fonts.css is the CSS the page
# links to (prototype/index.html), fetched with a Chromium user agent so it names woff2 subsets, plus the 13 woff2
# files it names; the run records those inputs by content hash, and measurements/prototype.json is written only from
# the pinned ones (14 inputs, sha256 4bf26761317d…, fetched 2026-10-10 and reproduced byte for byte on 2026-10-11;
# should Google serve other bytes one day, a run with them needs --out). Without --fonts the page loads Google's
# live bytes, which no hash pins, so such a run needs --out too.
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
mkdir -p /tmp/fonts && curl -sS -A "$UA" -o /tmp/fonts/fonts.css "https://fonts.googleapis.com/css2?family=Geist+Mono:wght@400;500;600&family=Inter:opsz,wght@14..32,400;14..32,500;14..32,600&display=swap"
for u in $(grep -o 'https://fonts.gstatic.com[^)]*' /tmp/fonts/fonts.css | sort -u); do curl -sS -A "$UA" -o "/tmp/fonts/$(basename "$u")" "$u"; done
NODE_PATH=/tmp/pw-1.56/node_modules node tasks/analysis-redesign-2026-10/harness/measure-proto.mjs --fonts /tmp/fonts --shots /tmp/shots
```

Both scripts resolve Playwright through `createRequire` (`NODE_PATH`) and write their recording only in the
browser `harness/browser-pin.mjs` pins, Chromium 141.0.7390.37 on linux x64: Playwright 1.56.1's build, which
the cloud image's global install provides (`NODE_PATH=/opt/node-tools/node_modules`,
`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`) and the two install lines above give on any linux x64 machine. The
frontend's own `@playwright/test` (1.63) runs Chromium 153 and serves `--out` runs. Measured in it on
2026-10-11, the same `97293e7` build differed in all 20 configurations: the table was 2,035 px wide instead of
2,076 (4,070 instead of 4,151 with 200% text), the page overflowed 33 px at 390 instead of 39 and 95 px at 320 instead of 93, and no header straddled
the sticky edge at 1480. A recording retaken in that browser would no longer match the numbers the proposal
cites.
