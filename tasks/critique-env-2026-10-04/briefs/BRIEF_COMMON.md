# Common brief — EarningsNerd critique environment (read fully before starting)

You are one of two ISOLATED assessment agents for an Impeccable `critique` of EarningsNerd. Do not look
for, read, or reuse the other assessment's output, any prior critique report, or `.impeccable/critique/`.
Do not modify application code, tokens, design documents, or anything under /home/user/EarningsNerd
(read-only). Write only under the evidence directory named below. Never post to GitHub, never create a
PR, never run `impeccable init|document|doctor|hooks`, never touch production state (the mock backend
below only proxies read-only public GETs; every authenticated/Pro/streaming state is simulated locally).

## Product and brief
EarningsNerd (https://www.earningsnerd.io) turns SEC 10-K/10-Q filings into filing-grounded AI summaries,
multi-period financial analysis and source-cited "Ask this Filing" answers for investors. Established
design direction, "The Investor's Research Desk": calm, precise, evidence-led; sage brand accent, warm
cream / espresso light theme, deep navy dark theme; restrained structural depth; no decorative gradients
or general glows; three type voices (Inter headings, system-first body, Geist Mono for data/evidence,
Newsreader ONLY for the original filing text in `.filing-reader`). Judge how well the implementation
serves THAT direction. An alternative palette/font/personality is a separate proposal, not a correction.
Do not penalize an intentional, documented choice solely because a generic rule dislikes it; instead
name it as "would change an established decision" if you still think it is wrong.

Authority: code > CLAUDE.md > lessons/ > docs. Read (in the checkout, not the critique pack):
/home/user/EarningsNerd/DESIGN.md, /home/user/EarningsNerd/frontend/DESIGN_SYSTEM.md (sections 1–12,
especially 3 type roles, 4 component patterns incl. Dialog/Popover/Stacking, 9 exemptions, 11 motion,
12 done-gate), and lessons as needed from /home/user/EarningsNerd/lessons/ (index in lessons/README.md;
the frontend-* files are the relevant ones). CLAUDE.md is injected for you already. PRODUCT.md does not
exist (a context gap already recorded; do not create it).

Established decisions you must treat as intentional (critique allowed, but label it): justified +
hyphenated AI-summary paragraphs at >=640px (ragged below; filing reader always ragged); serif only in
the filing reader; single sage accent, brand never as chart series or financial direction; cards lift
(panel + hairline + shadow) rather than tint; dark-mode primary buttons use navy ink; progress uses
brand, success green only for terminal confirmation; busy controls stay focusable (aria-disabled, never
native disabled); only `ui/Modal` plus the documented bespoke sheets may be dialogs; the full-text
/search route is hidden in production by founder decision (404; it is enabled in this test build only
so it can be inspected); the "Source match found / Verified in filing" wording scopes attribution and
must not imply whole-answer verification; the landing page's "demo=1" entry suppresses the quality
badge and the copilot nudge on purpose.

## Research task to evaluate (the critique's spine)
Find the intended company and period → read an analysis → inspect a cited claim in the original source
→ return to the research without losing context. Primary stable target: `frontend/app/filing/[id]/page.tsx`
(the filing page: `page-client.tsx`, `StreamingSummaryDisplay.tsx`, `features/summaries/components/*`,
`features/filings/components/*` incl. `copilot/*`, `SourceTrace.tsx`, `MetricSourceLink.tsx`). Modes:
homepage = Persuade; search / company / analysis controls = Operate; filing reading = Read. Supporting
surfaces: `app/page.tsx` (understand the product, start), `app/search/page.tsx` (find a company; note
production 404s it, the homepage ticker search `features/companies/components/CompanySearch.tsx` is the
live finder), `app/company/[ticker]/page.tsx` (select a filing/period), `app/analysis/page.tsx`
(interpret trends; Pro flagship). Anchor one multi-view critique on the filing page; do not average
unrelated surfaces into one unexplained score.

## Test environment (running now; do not restart or stop it)
- App: http://localhost:3000 — production build of commit 100fb7d6 (current main) with
  NEXT_PUBLIC_API_BASE_URL=http://localhost:8010, analysis+calendar+quality-badge flags on (as in
  production), full-text search ON (off in production), example filing id 3 (Apple FY2025 10-K, the
  public pre-generated example; production: /filing/3).
- Mock backend: http://localhost:8010 (source: /tmp/claude-0/-home-user-EarningsNerd/78df218f-8eea-5bb5-9669-b8dbafc877c6/scratchpad/critique-env/mock_api.py).
  Public GETs proxy real production responses (cached). State is selected per request by the cookie
  `en_scenario` (domain localhost) or header `X-EN-Scenario`, comma-joined tokens:
  anon (default) | free | pro — identity/plan; content — serve the fixture filing text for
  /api/filings/3/content; nosummary — summary 404 until a mocked generate-stream completes;
  summaryerror — summary GET 500; partial — summary with quality.tier=partial; genfail — generation
  stream ends in an error; askfail — ask-stream 500; exhausted — free user with no Copilot taste left;
  saved — summary already saved; watch — AAPL on watchlist; slow — +2.5s latency on summary/content
  reads; offline — every proxied read 503.
- PRODUCTION REALITY you must respect in findings: in production `GET /api/filings/{id}/content` returns
  has_content=false for every filing sampled (59 ids incl. 3, 16070, 39032), so the in-app filing viewer
  shows "The full filing text is not available to view in-app yet" + an SEC.gov link for every
  Trace-to-Source / citation click. The `content` scenario serves a SYNTHETIC, abridged fixture
  (/tmp/.../critique-env/fixtures/filing-3-content.md, labelled TEST FIXTURE) built from the real
  summary's cited excerpts so the in-app highlight path can be exercised. Any finding that depends on
  the fixture must say so ("fixture-dependent: code path real, production data absent").
- Analysis for `pro` uses the repo's own demo dataset (features/analysis/demo/demo-analysis.json,
  approximate Apple FY2019–FY2024 figures); the AI narrative is the demo completion streamed as tokens.
  Copilot answers for `pro`/`free` are canned completions (3 variants) with citations that resolve in
  the fixture. Say "mock-stream" when a finding depends on them.
- Browser: Playwright 1.63 + Chromium 141 (headless; executable /opt/pw-browsers/chromium). There is NO
  human-visible browser tab in this cloud session.

## Batched inspection evidence (already captured; one initial batch per the plan)
Directory: /tmp/claude-0/-home-user-EarningsNerd/78df218f-8eea-5bb5-9669-b8dbafc877c6/scratchpad/evidence/
Each job `<name>` has `<name>.png` (final state; full page when the job asked) plus step shots
`<name>__<shot>.png`, and `<name>.json` with: route, scenario, theme, viewport (desktop 1440x900,
mobile 390x844 iPhone-13 UA + touch, tablet 768x1024), console errors/warnings, failed requests (>=400),
`horizontalOverflow` (document scrollWidth vs clientWidth), `focusTrail` (active element after each Tab:
tag/name/rect/inViewport/focusVisible/boxShadow), `styles` (computed color/background/effective
background/contrast ratio vs WCAG AA/font/size/weight/line-height/letter-spacing/radius/shadow for
sampled selectors), `aria` (Playwright aria snapshot of body or a dialog), `texts`, `counts`, `rects`.
The job list is /tmp/.../critique-env/jobs-baseline.json (65 jobs; names encode surface-theme-
viewport-scenario-state). View screenshots with the Read tool. Prefer this batch; run targeted
captures only for disputed or uncertain findings (bounded: not an open-ended loop).

## Targeted captures (when you need them)
`cd /tmp/claude-0/-home-user-EarningsNerd/78df218f-8eea-5bb5-9669-b8dbafc877c6/scratchpad/critique-env && CHROMIUM_PATH=/opt/pw-browsers/chromium node capture.mjs --out <unique-name> --route /filing/3 --scenario pro,content --theme dark --viewport 390x844 --coach-seen --steps '<dsl>' [--full] [--styles 'sel,sel'] [--aria] [--reduced-motion] [--zoom 2]`
Steps DSL (semicolon-separated verb=arg): click, hover, focus, fill=sel|text, type=sel|text, press=Key,
wait=ms, waitfor=sel, scroll=sel|px, shot=name, fullshot=name, eval=js, keyfocus, tabtrail=n,
styles=sel,sel, aria=sel, text=sel, count=sel, rect=sel, viewport=WxH, setcookie=scenario, reload,
goto=path, hidecoach. Selectors: Playwright CSS/`text=`; `role:button:Name` (regex name);
`label:`, `placeholder:`. Use a unique --out prefix with your assessment letter (e.g. `A-...` / `B-...`)
so you never overwrite the baseline. Output goes to the same evidence directory.
You may also write your own Playwright script (import from
/home/user/EarningsNerd/frontend/node_modules/@playwright/test/index.mjs, launch chromium with
executablePath '/opt/pw-browsers/chromium', set cookie en_scenario on domain localhost, set
localStorage.theme via addInitScript) when the DSL cannot express a check.

## Output discipline
Return ONLY the structured object requested by your schema (no human-facing prose outside it). Every
issue needs: stable id, severity P0–P3 (P0 blocks the task; P1 major difficulty; P2 annoyance with
workaround; P3 polish), confidence (high/medium/low), classification (shared-system | route |
documentation), surface + mode, task impact, reproduction (route, scenario, theme, viewport, steps),
evidence (screenshot filename(s) and source file:line), observed vs desired, smallest practical change
+ affected components/consumers, whether it changes an established decision, suggested Impeccable
command (adapt|animate|audit|bolder|clarify|colorize|critique|delight|distill|document|harden|layout|
onboard|optimize|overdrive|polish|quieter|shape|typeset), effort (S/M/L), dependencies, acceptance
criteria another agent can verify. Distinguish a reproducible defect from an aesthetic preference.
Describe uncertainty instead of inventing precision. Record exact viewport dimensions. Record every
combination you could NOT inspect and why.
