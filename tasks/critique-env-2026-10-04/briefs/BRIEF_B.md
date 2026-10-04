# Assessment B — Detector + browser evidence. Isolated from Assessment A.

Read BRIEF_COMMON.md first (same directory). You produce deterministic and browser evidence; you do NOT
write a design opinion, score heuristics, or read anything named `A-*`. Distinguish actual defects from
approved exceptions and from false positives, with proof.

## 1. Deterministic scan (run ONCE; do not rerun unless the first attempt failed)
Launcher: `/root/.claude/plugins/cache/impeccable/impeccable/4.5.0/skills/impeccable/scripts/impeccable`
(engine VERSION file says 0.1.11; plugin 4.5.0). Run from the repository root
`/home/user/EarningsNerd` so the project's `.impeccable/design.json` and DESIGN.md context load:
  `"$LAUNCHER" detect --json $(sed -e 's/^/frontend\//' -e '/^#/d' -e '/^$/d' /tmp/claude-0/-home-user-EarningsNerd/78df218f-8eea-5bb5-9669-b8dbafc877c6/scratchpad/critique-env/detect_targets.txt | tr '\n' ' ') > /tmp/claude-0/-home-user-EarningsNerd/78df218f-8eea-5bb5-9669-b8dbafc877c6/scratchpad/evidence/B-detect.json 2> .../evidence/B-detect.stderr; echo exit=$?`
The target list is the primary route's wrappers + component dependencies + the four supporting route
wrappers (100 scannable files; do not scan the whole tree). Exit 0 = clean, 2 = findings, 1 = a
target could not be scanned (report which). Record the exact command, exit code, counts per rule and
per file, advisory vs primary findings. If the entrypoint is missing or crashes after a real attempt,
report "deterministic scan unavailable" with the actual error and continue with browser evidence; an
attempted scan that fails is a limitation, never zero findings.
Classify EVERY primary finding (and summarize advisories) as: defect | approved-exception (cite the
exact DESIGN_SYSTEM.md / DESIGN.md / lessons sentence that sanctions it, e.g. DataTable's internal
`z-[5]`, the aria-hidden ▲▼ glyph sizes, the Google button surfaces, the 40px pricing figure
tracking, the justified summary paragraphs, the single sage accent, Newsreader in the reader) |
false-positive (explain why the rule misfires here) | out-of-scope (not on the critiqued surfaces).
Do not treat a detector dislike of an intentional, documented choice as a defect.

## 2. Browser evidence (headless Playwright; no human tab exists)
Preflight mutable injection on a fresh page: set `document.title` and append a `<script>` tag via
page.evaluate; if that works, start the overlay server in the background and inject it:
  `"$LAUNCHER" live-server --background` (prints connection JSON incl. the port; record it and the stop
  method `"$LAUNCHER" live-server stop`), then for each of 5 representative views
  (/, /search with results, /company/AAPL, /analysis?ticker=AAPL as `pro` after the stream completes,
  /filing/3 as `pro,content` with the rail open) at desktop 1440x900 AND mobile 390x844: open a NEW
  page per view, scroll to top, `page.addScriptTag({url: 'http://localhost:PORT/detect.js'})`, wait
  2–3 s, collect every console message whose text mentions `impeccable` (and any errors), save the
  raw console lines to `.../evidence/B-overlay-console.json`, take a screenshot `B-overlay-<view>-
  <viewport>.png`. Stop the live server afterwards and record that you did. Because the session is
  headless, state plainly that no user-visible overlay tab exists; the console output is the signal.
  If injection fails, report the fallback signal (what you could and could not run).
Write your own small Playwright script for this (see the common brief for import/launch details; the
harness DSL has no addScriptTag). Keep it bounded: one pass.

## 3. Deterministic browser checks (from the baseline evidence + bounded targeted runs, prefix `B-`)
Work through the baseline records in the evidence directory (jobs in jobs-baseline.json):
a. Contrast: aggregate every `styles[]` sample across the records; list each visible text sample
   below WCAG AA (4.5:1, or 3:1 for large text) with selector, text, colors, effective background,
   theme, file. Check both themes on the filing page, company page and analysis page. Note that the
   probe measures computed colors against the blended effective background, which is the method
   DESIGN_SYSTEM.md requires (cream, not white).
b. Horizontal overflow: list every record whose `horizontalOverflow` is non-null; reproduce the worst
   one and ROOT-CAUSE it in CSS/markup (which element exceeds its container, its computed width, which
   flex/grid ancestor lacks `min-w-0` or which table forces min-content width, whether
   `scrollIntoView` moves the window horizontally). Candidate already observed by the orchestrator's
   smoke run: /filing/3 as `pro,content` at 1440x900 after a citation click reported document
   scrollWidth 1793 vs clientWidth 1440 and the page shifted left (evidence `smoke-filing__highlight.png`);
   verify independently, measure `.filing-reader` scrollWidth/clientWidth and its widest descendant,
   and test whether it also occurs without the wide fixture table (eval-remove the table, re-measure)
   and at 390x844. State fixture-dependence precisely.
c. Keyboard/focus: analyze every `focusTrail` (home, company, filing, analysis, genfail, ask-keyboard,
   rail flows): any focused element with no visible focus ring (boxShadow/outline both none), focus
   landing on `body`, focus on an element outside the viewport, native `disabled` on a busy control,
   Escape/close returning focus to the opener (the `keyfocus` after Escape), the Ctrl+K open path.
   Check dialog semantics from the `aria` snapshots: role/aria-modal/labels of the rail sheet, the
   source sheet, the upgrade modal; tab/tabpanel wiring; heading levels order on the filing page.
d. Touch targets on mobile records: compute from `rects`/`focusTrail` rects (and targeted `rect=`
   captures) the size of the citation chips, Trace-to-Source chips, filter chips, the launcher, tab
   controls, close buttons, header icons; list anything under 24x24 CSS px (WCAG 2.5.8 minimum) and
   under 44x44 (the repo's own header target), noting the documented inline-target exception.
e. States: confirm from the records which states rendered as designed and which did not: loading
   (`filing-light-desktop-anon-loading` t0/t1200/t3700), empty (`nosummary` anon → signup gate),
   generating (`free-generating` t0…done), generation error (`genfail` + Retry focus), summary GET
   error (`summaryerror`), partial badge, offline (503), not-found (999999999), legacy ticker URL,
   copilot error (`askfail`), free teaser/exhausted/upgrade modal, reduced motion (`reduced-motion`:
   inspect whether the streaming indicator / citation flash / spinners still animate: use a targeted
   capture with `--reduced-motion` and `styles=` on `.animate-pulse,.animate-spin,.citation-flash`
   reading computed `animation-name`/`animation-duration`), zoom 200% (`zoom200`: overflow/clipping).
f. Console/network hygiene: list console errors and failed requests per record, separating
   environment artifacts (e.g. /_vercel/insights 404, PostHog key warning, net::ERR_ABORTED on an
   SSE stream after completion) from real defects (React warnings, hydration mismatches, 4xx on
   product endpoints the UI did not expect).
g. Evidence/trust surface: on the filing page record the exact wording and placement of the AI
   disclaimer, the "Verified in filing"/"Cited"/"SEC XBRL" chips, the quality badge, the "Source
   match found" copy and the "A source match does not verify every claim" line; confirm the
   non-demo page shows the quality badge and the demo URL hides it; confirm the ask-flow popover and
   source sheet expose the EDGAR link; note the `Open original` link target in the pane header
   (filing.sec_url = the EDGAR folder index vs document_url = the primary document) and whether the
   in-app "not available" state is the production behavior (it is: content has_content=false for all
   59 sampled filings; cite that).
h. Supporting surfaces: company page density (count of filings shown, chip filters, "Show full
   history" result), search results list (row anatomy, result count, empty state copy), analysis
   charts (series count vs the 5+-series labelling rule, legend/markers, tone coloring of inverted/
   neutral series, table numerals mono/right-aligned), homepage LCP hero (the H1 size at desktop and
   mobile, the search field, the example card), mobile menu.
Each check returns: id, check, result (pass|fail|partial|not-run), evidence files, numbers, source
file:line where the cause lives, severity (P0–P3) and confidence if it is a defect, and whether it is
fixture-dependent or mock-stream-dependent.

## 4. Tool and run notes
Record: plugin 4.5.0 (marketplace install, user scope), engine 0.1.11, Playwright 1.63.0, Chromium
141.0.7390.37, app commit 100fb7d6, build flags (see env.sh), servers and their stop methods, the
live-server port, any step you skipped and why, and the exact list of targeted captures you ran.

## Return (schema enforced)
detector: {command, exit_code, scanned_files, primary_count, advisory_count, by_rule: [{rule, count}],
  by_file: [{file, count}], findings: [{rule, file, line, message, classification, justification,
  severity, confidence}], raw_json_path, limitations}
overlay: {attempted, injection_preflight, live_server_port, views: [{view, viewport, injected,
  console_findings: [string], screenshot}], user_visible_overlay: false, stopped, limitations}
browser_checks: [{id, check, result, evidence[], numbers, source_refs[], severity, confidence,
  fixture_dependent, mock_dependent, notes}]
contrast_failures: [{file, theme, selector, text, color, effective_background, ratio, required}]
overflow: [{file, scrollWidth, clientWidth, root_cause, source_refs[], fixture_dependent}]
focus_findings: [{file, step, element, problem, source_refs[]}]
touch_targets: [{file, element, w, h, verdict}]
state_matrix: [{state, record, rendered_as_designed, notes}]
console_hygiene: {environment_artifacts: [string], real_defects: [{record, message}]}
false_positives: [string]
skipped_steps: [{step, reason}]
versions: {plugin, engine, playwright, chromium, commit, flags}
targeted_captures_run: [string]
