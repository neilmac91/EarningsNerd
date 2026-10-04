<!-- Repository copy of the run notes for the 2026-10-04 Impeccable critique of frontend/app/filing/[id]/page.tsx.
Companion to tasks/critique-handoff-2026-10-04.md and the archive under .impeccable/critique/. Paths such as
critique-env/… and evidence/… name files in the critique package delivered in the session, not repository paths. Since PR #1089
the environment lives at tasks/critique-env-2026-10-04/ (its later tooling corrections are recorded in the last section). -->

# Run notes — EarningsNerd critique (2026-10-04)

## Provenance
- Repository: neilmac91/EarningsNerd, branch claude/awesome-hamilton-snivyc at commit 100fb7d6 (== origin/main at run time; the
  critique pack's reference commit). Working tree clean; no application files changed.
- Runtime build: `next build` (Next 16.3.6, React 18) of that commit, served with `next start -p 3000`, flags:
  NEXT_PUBLIC_API_BASE_URL=http://localhost:8010, NEXT_PUBLIC_EXAMPLE_FILING_ID=3, ENABLE_ANALYSIS=true, ENABLE_CALENDAR=true,
  ENABLE_QUALITY_BADGE=true (all three match production markup), ENABLE_FULLTEXT_SEARCH=true (production: OFF, /search 404s),
  ENABLE_FINANCIAL_CHARTS=false, ENABLE_PRO_TRIAL=false, WAITLIST_MODE=false, PostHog/Sentry unset.
- Production could not be matched to the checkout byte-for-byte (Vercel build id not exposed); production probes used only to
  confirm flag state, route availability and API data shape.
- Impeccable: plugin impeccable@impeccable 4.5.0 installed via `claude plugin marketplace add pbakaus/impeccable` +
  `claude plugin install impeccable@impeccable --scope user` (Claude Code CLI 2.1.289); skill path
  /root/.claude/plugins/cache/impeccable/impeccable/4.5.0/skills/impeccable; engine VERSION 0.1.11 (launcher binary downloaded on
  first `context` run). The plugin's slash command is not registered in this already-running cloud session; the installed
  SKILL.md and reference/critique.md playbook were loaded and followed from disk. Storage slug: frontend-app-filing-id-page-tsx.
  No `.impeccable/critique/ignore.md` existed. PRODUCT.md absent (context gap; not created).
- Browser: Playwright 1.63.0 (repo pin) driving the preinstalled Chromium 141.0.7390.37 (/opt/pw-browsers/chromium) headless.
  No human-visible browser tab exists in this cloud session.

## Environment (recorded stop method: critique-env/stop_env.sh)
- Mock backend :8010 (critique-env/mock_api.py): public GETs proxied to https://api.earningsnerd.io and cached; identity/plan,
  saved/watch state, errors, empty summary, generation/ask/analysis streams simulated per request by cookie `en_scenario`.
  No production mutation.
- Filing-text fixture (critique-env/fixtures/filing-3-content.md): SYNTHETIC abridged 10-K markdown embedding every citation
  excerpt / section ref from the real production summary of filing 3, so in-app highlight paths could be exercised.
- Production reality: GET /api/filings/{id}/content → has_content=false for all 59 ids sampled (1–40, 50, 100, 500, 1000, 5000,
  10000, 15000, 16069, 16070, 20000, 25000, 30000, 35000, 37000, 38000, 38500, 39000, 39032). The in-app viewer therefore always
  shows its "not available in-app yet" state in production today.

## Inspection coverage
- Batched matrix: 65 jobs (critique-env/jobs-baseline.json), viewports 1440x900 desktop, 390x844 mobile (iPhone 13 UA, touch),
  768x1024 tablet; themes light/dark; states anon/free/pro, saved, partial, nosummary (signup gate / generation), genfail,
  summaryerror, askfail, exhausted, slow (loading), offline, not-found, legacy ticker URL; interactions: rail open/ask/cite/
  return, keyboard (Ctrl+K, Tab trails, Escape), source popover + touch sheet, reduced motion, 200% zoom, pane resize.
- Extras: 320x256 (WCAG reflow) and 1023/1024x768 (lg breakpoint edge), upgrade modal over the sheet, coachmark targets.
- Harness defect during the first batch (style/focus probes did not execute) was fixed and the whole matrix re-captured; only
  the re-captured records are used. Known gaps: text-selection "Ask about this" capture broken (DSL split); two aria snapshots
  timed out; no real screen reader; hover states only via fine-pointer emulation; headless rendering.

## Orchestrator verification pass (after Assessment A returned; before B's output entered synthesis)
Targeted captures V-* and V-probe-results.json (evidence dir), plus source reads:
- Trace-to-Source chip with the Copilot pane closed (scenario pro, no content): click/Enter → the "Ask this Filing" dialog stays
  aria-hidden="true", display none; its internal tab silently flips to "Filing". Touch (390x844): no source sheet, no pane.
  Keyboard: the focus-opened popover (role=group "Source detail") never enters the Tab order (4-step trail: inPopover=false
  every time), so "Open in SEC EDGAR" is unreachable without a pointer. CONFIRMED (A-01).
- Cookie banner (CookieConsent.tsx:296 fixed bottom z-50) above the z-40 launcher/sheet: confirmed visually at 1440x900
  (launcher absent) and 390x844 dark (sheet composer under the banner). CONFIRMED (A-02).
- Phone metrics table: rows ~400px tall, takeaway/provenance column off-screen, "CI" header clipped. CONFIRMED (A-03).
- Reader overflow with text present: document scrollWidth 1793 vs 1440 (two independent records + smoke run). CONFIRMED, fixture-
  dependent (A-04).
- Risk cards "Filing excerpt N" + TrendDown glyph + 12px evidence: confirmed visually; backend payload itself carries
  summary="Filing excerpt" / source_section_ref="Filing excerpt" for every risk (production data). CONFIRMED (A-05).
- Desktop pane Escape: focus lands on <body> after Escape (launcher-click and Ctrl+K paths). CONFIRMED.
- /analysis?ticker=AAPL as Pro: empty Company picker, no chart (AnalysisPageClient.tsx:49 never reads the query). CONFIRMED.
- Company page: 10× "Generate Filing Summary" + "Summarize this filing", 0× any "view summary" state although every listed
  Apple filing already has a production summary. CONFIRMED.
- Focus styling: logo link, theme toggle and "← Back" rely on the browser default outline (no brand ring). CONFIRMED.
- Chip accessible name "Source: Source" for unverified metrics (MetricSourceLink.tsx:28 + SourceTrace aria-label). CONFIRMED.
- 200% zoom "overflow" (zoom200 record, 1798px): NOT reproduced at natural 720/640/600/480px widths (document scrollWidth ==
  clientWidth; the only elements past the edge are the horizontally scrolling jump-strip chips inside their own scroller).
  Treated as an emulation artifact; dropped.
- No app/not-found.tsx → Next default 404 on /filing/999999999. CONFIRMED. No <main> landmark on /analysis. CONFIRMED.

## Dispute resolution (after B returned)
- B read a Trace-to-Source click as "sheet opens on the Filing tab" (traceViewerDialogs / sourceSheetDialogs). Its own numbers show the
  always-mounted workspace dialog in its closed state (reader width 0, z auto, focus still on the chip). V-trace-results.json re-tested
  five conditions (desktop click with and without consent, desktop Enter, mobile tap with and without consent): the dialog stays
  aria-hidden="true" / display:none / 0x0 in every case; only its hidden tab flips to "Filing". A-01 stands (CONFIRMED P1).
- B stated no in-app link builds /analysis?ticker=…; the homepage Pro section does (features/marketing/components/ProDepth.tsx:110).
- Detector exit code 1 came from the two comment lines of detect_targets.txt reaching the launcher as bogus tokens (an orchestrator
  brief flaw); every real target was scanned (B-detect.json, B-detect.stderr). Counted as a limitation, not re-run.
- Servers stopped before final reporting via critique-env/stop_env.sh (recorded below).
stopped at 16:41:00Z

## Founder scope answers (2026-10-04, after the report)
- Priority: "The verify step (Recommended)". Chip intent while has_content=false: "Open the pane to its empty state (Recommended)".
- Scope: "Top 3 (EN-01, EN-02, EN-03) (Recommended)". Decision changes allowed: consent layer in the stacking ladder; filing-derived
  risk headline (accepted, deferred outside top 3); 'open original' → document_url.
- IMPLEMENTATION_HANDOFF.md filled accordingly; no code changed; nothing posted to GitHub; no PR created.

## Post-PR baseline check (2026-10-04 18:30 UTC)
- PR #1089 (docs-only archive) is green and mergeable (frontend-tests, backend-tests, e2e-tests, lighthouse,
  migrations-postgres, secret-scan, eval-baseline passed; deploy-backend/review-gate skipped). Draft; waits on the founder.
- origin/main moved to fdbbcb2 (#1085 retry/focus convention + gate expansion, #1086, #1088 ledgers). No cited component file
  changed; DESIGN_SYSTEM.md §4 gained the RetryButton/useRetainedFailure/useFocusHandoff rule. Handoff updated accordingly.

## Tooling corrections (Astra follow-up, 2026-10-04 19:35–19:45 UTC; applied on PR #1089 after head 8e09b1b)
Astra's review of head 8e09b1be asked for five narrowly scoped tooling/handoff corrections. No application code, token or design
document changed; the sections above stand as written (the archive still records the original exit-1 detector run and the critique's
own numbers). Everything below happened after the critique, in `tasks/critique-env-2026-10-04/`.
- Shutdown. `start_mock.sh` / `start_next.sh` now run each server under `setsid` in its own session and process group, and the
  child writes its own PID to `mock.pid` / `next.pid`. `stop_env.sh` has no pattern kills: for each PID file it checks the PID still
  exists, checks `/proc/<pid>/cmdline` contains the expected command (`mock_api.py`, `next start`), then SIGTERMs that process group
  (SIGKILL after 10 s); a mismatched PID is reported and left alone, stale files are removed; the Impeccable live server is stopped
  through its launcher only when `live-server.started` exists. Proof (an unrelated process whose argv contains both former pkill
  patterns, and a forged PID file pointing at an unrelated `sleep`, both survive):
```text
# stop_env.sh proof — 2026-10-04T19:38:15Z
## before
mock.pid=684 next.pid=694
decoy1 pid 1076 cmd: decoy mock_api.py next start -p 3000 600 
decoy2 pid 1077 cmd: sleep 600 
## run 1: real pid files
next: stopped pid 694 (process group 694)
mock api: stopped pid 684 (process group 684)
## after run 1
mock pid 684 gone
ports 3000/8010 free
decoy1 pid 1076 alive: decoy mock_api.py next start -p 3000 600 
decoy2 pid 1077 alive
ls: cannot access 'mock.pid': No such file or directory
ls: cannot access 'next.pid': No such file or directory
## run 2: forged mock.pid pointing at decoy2 (cmdline mismatch) and stale next.pid
next: pid 999999 not running; removing stale next.pid
mock api: pid 1077 is not ours (cmdline: sleep 600 ); leaving it alone
decoy2 pid 1077 alive (left alone)
ls: cannot access 'mock.pid': No such file or directory
ls: cannot access 'next.pid': No such file or directory
## run 3: nothing started
next: not started by this environment (no next.pid)
mock api: not started by this environment (no mock.pid)
## cleanup decoys
decoys killed by the proof script
```
  After run 1, `ps` showed no next/mock_api processes from this environment and ports 3000/8010 were free.
- Browser. `browser.mjs` (shared by `capture.mjs`, `verify_probe.mjs`, `verify_trace.mjs`): an explicit `CHROMIUM_PATH` wins and must
  exist; otherwise Playwright's own Chromium when installed; otherwise a Chromium under `PLAYWRIGHT_BROWSERS_PATH` or `/opt/pw-browsers`;
  otherwise an error naming both remedies. `env.sh` offers `/opt/pw-browsers/chromium` only when `CHROMIUM_PATH` is unset and the file
  exists. Module paths come from `fileURLToPath`/`pathToFileURL` (no raw `URL.pathname`), so checkout paths with spaces work. Smoke
  check against the rebuilt mock + `next start`: `CHROMIUM_PATH` unset → `[capture] chromium: /opt/pw-browsers/chromium` (Playwright
  1.63's default `chromium-1243` is absent in this image, so the preinstall step was taken), `/filing/3` scenario `pro,content` at
  1440x900 captured in 3203 ms, 2 console errors (the known `/_vercel/insights/script.js` 404 pair), no horizontal overflow;
  `CHROMIUM_PATH=/opt/pw-browsers/chromium` → `anon,content` 390x844 mobile captured in 1849 ms; `CHROMIUM_PATH="/no such/dir with
  spaces/chrome"` → exit 1 with `CHROMIUM_PATH is set to "/no such/dir with spaces/chrome" but no file exists there` and no evidence
  written. Smoke captures are `evidence/smoke-*.{png,json}` (gitignored run state).
- Detector. `run_detect.sh` drops `#` comments and blank lines from `detect_targets.txt`, validates each path under `frontend/`,
  passes the 31 paths as an argument array and records the scan under `scans/`. Record committed: `scans/detect-8e09b1b.json`,
  `.meta.json`, `.stderr` (empty). Source `8e09b1be19ea447ab8fea72574cf377f9154f741`; scanned `frontend/` tree
  `ebb81d3076655cacd83642b81e7e2f2f0e183aa7` (identical at the critiqued `100fb7d6`; `origin/main` `fdbbcb2` carries `047c28fa…`
  because of #1085); engine 0.1.11; exit 2 (findings); 4 distinct findings, all severity `warning`: `side-tab` ×3
  (`SummaryBlock.tsx:42`, `SummaryBlocks.tsx:184`, `app/company/[ticker]/page-client.tsx:612`) and `bounce-easing` ×1
  (`globals.css:64`). These are the four in-scope findings the archive's "Deterministic scan (B)" already classifies; its two
  out-of-scope entries and its exit 1 belong to the original run and are not revised. Two consecutive runs produced byte-identical
  output (sha256 `453c2e3bb4a18329af71dfc8ded38c0cce88c89a23d2a63ee60e2042dc96638f`).
- Fixture and cache provenance. `build_fixture.py` without flags now compares a regeneration against the committed fixture
  (`committed fixture MATCHES the regenerated text`, exit 0) instead of overwriting it; `--force` rewrote byte-identical content
  (sha256 `66647fd01c7e7523319a80284a45138261b9888745b7753198d3977b6fc39d5c` before and after) and wrote `fixtures/PROVENANCE.json`
  (source `GET /api/summaries/filing/3`, cached `cache/summary-filing-3.json` fetched 2026-10-04T18:55:29Z, sha256 `1412895e…`,
  synthetic=true, labelled abridged fixture). `mock_api.py` serves the fixture only for `/api/filings/3/content` under the `content`
  scenario; other ids pass through unchanged. `cache_manifest.py` wrote `fixtures/CACHE_MANIFEST.json` listing the six cached
  production responses (path, status, size, sha256, fetch time); the cache directory itself stays gitignored.
- Handoff. `tasks/critique-handoff-2026-10-04.md` now uses repository paths, marks quoted screenshot/record names as archive members
  of the core evidence package, states the no-content finding as a dated observation about the 59 sampled ids, adds the scan record,
  and carries the acceptance clarifications (EN-01 plan-independent source access with Ask entitlements untouched; EN-02 usable
  consent choices alongside the research chrome; EN-03 all data/provenance and accessible content retained, no forced heights or
  truncation). Scope (EN-01 → EN-02 → EN-03, three PRs from current `main`, all deferred items) is unchanged.
- Servers stopped by `./stop_env.sh` at 19:38:15Z (run 1 above); nothing from this environment remained running.
