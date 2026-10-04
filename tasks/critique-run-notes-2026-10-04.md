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

## Process identity (Astra final follow-up, 2026-10-04 20:55–21:55 UTC; applied on PR #1089 after head d021366)
Astra's final follow-up (final-handoff-corrections.txt with acceptance-addendum.md attached) asked for two amendments: a complete
process-ownership check in the lifecycle scripts, and alignment of the living handoff with the addendum. This section supersedes
the "Shutdown" bullet of the previous section: `mock.pid`/`next.pid` and the command-line-substring check no longer exist. Earlier
sections stand as written; the critique archive and the detector record `scans/detect-8e09b1b.*` are unchanged.
- Identity records. `start_mock.sh` / `start_next.sh` launch each server under `setsid`, give it its readiness budget (the mock's
  `/health` now also reports its pid, so readiness is tied to the started process; Next must answer on :3000 while the pid is
  alive), then write `mock.proc` / `next.proc` through `lifecycle.sh`: pid, pgid, sid (both equal to pid), starttime
  (`/proc/<pid>/stat` field 22), boot identity (`/proc/sys/kernel/random/boot_id`, else `btime:<n>`; with neither readable nothing
  is recorded and nothing verifies), physical cwd and the stable command line (Next is launched directly from
  `node_modules/next/dist/bin/next`, not via `npx`, and names itself `next-server (v16.3.6)`; the record is taken after four
  identical samples 0.25 s apart). `lc_verify` is used by both the already-running check and `stop_env.sh`: every field must
  match the live process and the cwd must be the expected directory; zombies count as not running; records are validated field
  by field (known keys, no duplicates, no carriage returns or trailing whitespace, canonical integers; nothing is scraped out of
  arbitrary digits). A mismatch is refused even when the command substring matches: nothing is signalled, the record is moved
  to `<name>.proc.rejected.<UTC timestamp>`, and the leftover is reported on every later run (exit 1) until the operator removes
  it. Only a verified owner's process group is signalled (SIGTERM, SIGKILL after 10 s; "stopped" only once no live member of
  the group remains; the record is kept if members survive). Linux is the supported environment (`/proc`, `setsid`, `curl`);
  elsewhere the scripts exit 2 with a clear message and change nothing. Details: `tasks/critique-env-2026-10-04/README.md`
  "Lifecycle".
- Defects the proof caught on the way (fixed before the transcript below): `npx` rewrote its command line after the record was
  taken (the owned Next server was then refused) → direct launch and a stable-command-line wait; a defunct process still has a
  `/proc` entry → state Z/X counts as not running; the scripts derived their directories with the logical `pwd` while `/proc`
  reports physical paths → `pwd -P`.
- Independent review. A three-lens adversarial pass (identity bypass; false refusal of the owned server; documentation and repo
  rules) over the scripts and the first transcript returned 29 findings, 11 of them should-fix or blocking; all 11 and most of
  the informational ones are applied: fail-closed boot identity with the `btime` fallback; strict record syntax; the group-aware
  shutdown wait with no bare-pid fallbacks; timestamped refused records and sticky leftovers; the pid handoff read verbatim and
  validated, with a per-invocation temp file and a wait bound to the launcher's lifetime; readiness tied to the pid; unreadable
  `/proc` entries distinguished from mismatches (still refused); `curl` as a prerequisite; a record path that is not a regular
  file refused; a fail-closed default branch in `stop_env.sh`; `sort -V` and a guarded `$HOME` for the best-effort live-server
  launcher; README coverage of the `.unverified` outcome, the start exit codes (0 / 1 / 3), the "record written either way"
  behaviour and the move-the-checkout caveat. Not changed: a pid-namespace discriminator (single-host use) and a demonstration
  of SIGTERM-ignoring group members (the group wait covers it; not reproduced here).
- Proof transcript (final run on the committed scripts; hashes in the header). Case (a) a same-command process in another
  directory, case (b) a same-directory process with a mismatched start time, then stale, sticky-refusal, malformed and
  non-Linux cases, with the normal owned shutdown in step 6:
```text
# process-ownership proof — 2026-10-04T21:54:39Z — Linux 6.18.44-fc-v70 — boot_id b109227a-44a6-46c4-88da-83e6c767cde2
# repo HEAD d021366e27cb339fee37cf7877fb7a81940f510a; working-tree scripts:
#   306c0230c8512470dccb8e8dfb048541a7ea1ec159f89f714fa85797015e4ff7  lifecycle.sh
#   b81ca891dcf1d0b10a2db503a940190e192a208e6c3d152aa20614a60fda4961  start_mock.sh
#   fbd7da59ecb31be8a064d8fcba3edb75e7ac20250f3565b9c826672c0171bc7a  start_next.sh
#   1f777057dc9037fc23ff7bbfa7ff942ccf0b72a382e747ab5e418d99913a1f58  stop_env.sh

## 1. start the mock; a second start must verify the record and not start another
mock api up (pid 27913, recorded in mock.proc, /health reports the same pid)
exit=0
  mock.proc: pid=27913
  mock.proc: pgid=27913
  mock.proc: sid=27913
  mock.proc: starttime=400735
  mock.proc: boot_id=b109227a-44a6-46c4-88da-83e6c767cde2
  mock.proc: cwd=/home/user/EarningsNerd/tasks/critique-env-2026-10-04
  mock.proc: cmd=python3 mock_api.py
  mock.proc: started_at=2026-10-04T21:54:40Z
mock api already running (pid 27913, verified)
exit=0

## 2. decoy A: same command, OTHER directory (/tmp/claude-0/-home-user-EarningsNerd/78df218f-8eea-5bb5-9669-b8dbafc877c6/scratchpad/proof2/tasks/decoy-env), port 8011, own session
decoy A pid 27982 ALIVE (state S; cwd /tmp/claude-0/-home-user-EarningsNerd/78df218f-8eea-5bb5-9669-b8dbafc877c6/scratchpad/proof2/tasks/decoy-env; cmd 'python3 mock_api.py')

## 2a. forged mock.proc: decoy A's pid/pgid/sid/starttime, but cwd claims this environment -> stop_env.sh must refuse
forged mock.proc: pid=27982 pgid=27982 sid=27982 starttime=400856 cwd=/home/user/EarningsNerd/tasks/critique-env-2026-10-04 cmd=python3 mock_api.py
next: not started by this environment (no next.proc)
mock api: record mock.proc REJECTED (pid 27982 working directory differs (record /home/user/EarningsNerd/tasks/critique-env-2026-10-04, live /tmp/claude-0/-home-user-EarningsNerd/78df218f-8eea-5bb5-9669-b8dbafc877c6/scratchpad/proof2/tasks/decoy-env)); the process was left alone and the record was moved to mock.proc.rejected.20261004T215442Z
mock api: leftovers from earlier runs need attention:
  mock.proc.rejected.20261004T215442Z: refused earlier (pid 27982); handle the process by hand, then remove the file
exit=1
decoy A pid 27982 ALIVE (state S; cwd /tmp/claude-0/-home-user-EarningsNerd/78df218f-8eea-5bb5-9669-b8dbafc877c6/scratchpad/proof2/tasks/decoy-env; cmd 'python3 mock_api.py')
real mock pid 27913 ALIVE (state S; cwd /home/user/EarningsNerd/tasks/critique-env-2026-10-04; cmd 'python3 mock_api.py')
  mock.proc.rejected.20261004T215442Z
(real record restored)

## 3. decoy B: same command, SAME directory, port 8012, own session; record carries the real server's starttime
decoy B pid 28040 ALIVE (state S; cwd /home/user/EarningsNerd/tasks/critique-env-2026-10-04; cmd 'python3 mock_api.py')

## 3a. forged mock.proc: decoy B's pid/pgid/sid but a mismatched starttime (simulated pid reuse) -> stop_env.sh must refuse
forged mock.proc: pid=28040 pgid=28040 sid=28040 starttime=400735 cwd=/home/user/EarningsNerd/tasks/critique-env-2026-10-04 cmd=python3 mock_api.py
next: not started by this environment (no next.proc)
mock api: record mock.proc REJECTED (pid 28040 start time differs (record 400735, live 401015): the pid was reused); the process was left alone and the record was moved to mock.proc.rejected.20261004T215443Z
mock api: leftovers from earlier runs need attention:
  mock.proc.rejected.20261004T215443Z: refused earlier (pid 28040); handle the process by hand, then remove the file
exit=1
decoy B pid 28040 ALIVE (state S; cwd /home/user/EarningsNerd/tasks/critique-env-2026-10-04; cmd 'python3 mock_api.py')
real mock pid 27913 ALIVE (state S; cwd /home/user/EarningsNerd/tasks/critique-env-2026-10-04; cmd 'python3 mock_api.py')
  mock.proc.rejected.20261004T215443Z
(real record restored)

## 4. start next (records for both servers now exist)
next up (pid 28101, recorded in next.proc)
exit=0
  next.proc: pid=28101
  next.proc: pgid=28101
  next.proc: sid=28101
  next.proc: starttime=401176
  next.proc: boot_id=b109227a-44a6-46c4-88da-83e6c767cde2
  next.proc: cwd=/home/user/EarningsNerd/frontend
  next.proc: cmd=next-server (v16.3.6)
  next.proc: started_at=2026-10-04T21:54:45Z
http://localhost:8010/health -> HTTP 200
http://localhost:3000/ -> HTTP 200
  process tree of next's group (expect a single process):
    28101 28101 28101 Ssl  next-server (v16.3.6)

## 5. simulated non-Linux host (uname shim says Darwin): stop_env.sh must exit 2 and touch nothing
stop_env.sh: the critique lifecycle scripts support Linux only (they need /proc and setsid); nothing was changed.
Stop any critique servers manually and remove the *.proc records yourself.
exit=2
  still present: mock.proc
  still present: next.proc
http://localhost:8010/health -> HTTP 200
http://localhost:3000/ -> HTTP 200

## 6. normal owned shutdown
next: stopped pid 28101 (process group 28101, verified owner)
mock api: stopped pid 27913 (process group 27913, verified owner)
exit=0
mock pid 27913 is a ZOMBIE (exited, awaiting reap)
next pid 28101 is a ZOMBIE (exited, awaiting reap)
  ls: cannot access 'mock.proc': No such file or directory
  ls: cannot access 'next.proc': No such file or directory
http://localhost:8010/health -> no answer
http://localhost:3000/ -> no answer
  live processes whose cwd is this environment or frontend/ (expect none):
    none (decoy B excluded: it is the proof's own)
decoy A pid 27982 ALIVE (state S; cwd /tmp/claude-0/-home-user-EarningsNerd/78df218f-8eea-5bb5-9669-b8dbafc877c6/scratchpad/proof2/tasks/decoy-env; cmd 'python3 mock_api.py')
decoy B pid 28040 ALIVE (state S; cwd /home/user/EarningsNerd/tasks/critique-env-2026-10-04; cmd 'python3 mock_api.py')

## 6a. stale record: the real (now dead) mock pid -> removed, nothing signalled
next: not started by this environment (no next.proc)
mock api: pid 27913 is a zombie/dead process (state Z), not a running server; removing stale mock.proc
exit=0
  ls: cannot access 'mock.proc*': No such file or directory

## 6b. sticky refusal: a refused record is kept as mock.proc.rejected.<ts> and reported on every later run until removed
forged mock.proc: pid=28040 pgid=28040 sid=28040 starttime=400735 cwd=/home/user/EarningsNerd/tasks/critique-env-2026-10-04 cmd=python3 mock_api.py
next: not started by this environment (no next.proc)
mock api: record mock.proc REJECTED (pid 28040 start time differs (record 400735, live 401015): the pid was reused); the process was left alone and the record was moved to mock.proc.rejected.20261004T215446Z
mock api: leftovers from earlier runs need attention:
  mock.proc.rejected.20261004T215446Z: refused earlier (pid 28040); handle the process by hand, then remove the file
exit=1
next: not started by this environment (no next.proc)
mock api: not started by this environment (no mock.proc)
mock api: leftovers from earlier runs need attention:
  mock.proc.rejected.20261004T215446Z: refused earlier (pid 28040); handle the process by hand, then remove the file
exit=1 (second run, no record: leftover still reported)
next: not started by this environment (no next.proc)
mock api: not started by this environment (no mock.proc)
exit=0 (after the operator removed the leftover)

## 7. forged record at START time: mock.proc describes decoy A (other directory) -> start_mock.sh must refuse it and start a fresh server
forged mock.proc: pid=27982 pgid=27982 sid=27982 starttime=400856 cwd=/home/user/EarningsNerd/tasks/critique-env-2026-10-04 cmd=python3 mock_api.py
mock api: record mock.proc REJECTED (pid 27982 working directory differs (record /home/user/EarningsNerd/tasks/critique-env-2026-10-04, live /tmp/claude-0/-home-user-EarningsNerd/78df218f-8eea-5bb5-9669-b8dbafc877c6/scratchpad/proof2/tasks/decoy-env)); the process was left alone and the record was moved to mock.proc.rejected.20261004T215446Z
mock api: earlier refusals need attention (starting anyway):
  mock.proc.rejected.20261004T215446Z: refused earlier (pid 27982); handle the process by hand, then remove the file
mock api up (pid 28954, recorded in mock.proc, /health reports the same pid)
exit=0
  mock.proc
  mock.proc.rejected.20261004T215446Z
  new mock.proc: pid=28954
  new mock.proc: pgid=28954
  new mock.proc: sid=28954
  new mock.proc: starttime=401481
  new mock.proc: boot_id=b109227a-44a6-46c4-88da-83e6c767cde2
  new mock.proc: cwd=/home/user/EarningsNerd/tasks/critique-env-2026-10-04
  new mock.proc: cmd=python3 mock_api.py
  new mock.proc: started_at=2026-10-04T21:54:47Z
decoy A pid 27982 ALIVE (state S; cwd /tmp/claude-0/-home-user-EarningsNerd/78df218f-8eea-5bb5-9669-b8dbafc877c6/scratchpad/proof2/tasks/decoy-env; cmd 'python3 mock_api.py')
next: not started by this environment (no next.proc)
mock api: stopped pid 28954 (process group 28954, verified owner)
mock api: leftovers from earlier runs need attention:
  mock.proc.rejected.20261004T215446Z: refused earlier (pid 27982); handle the process by hand, then remove the file
exit=1 (1: the refused record is still reported as a leftover)
next: not started by this environment (no next.proc)
mock api: not started by this environment (no mock.proc)
exit=0 (after removing the leftover)

## 8. malformed records are refused by syntax, never signalled
next: not started by this environment (no next.proc)
mock api: record mock.proc REJECTED (pid '12 34' is not a positive integer); the process was left alone and the record was moved to mock.proc.rejected.20261004T215448Z
mock api: leftovers from earlier runs need attention:
  mock.proc.rejected.20261004T215448Z: refused earlier (pid 12 34); handle the process by hand, then remove the file
exit=1
  mock.proc.rejected.20261004T215448Z
next: not started by this environment (no next.proc)
mock api: record mock.proc REJECTED (missing field for START); the process was left alone and the record was moved to mock.proc.rejected.20261004T215448Z
mock api: leftovers from earlier runs need attention:
  mock.proc.rejected.20261004T215448Z: refused earlier (pid 27982); handle the process by hand, then remove the file
exit=1
  mock.proc.rejected.20261004T215448Z
next: not started by this environment (no next.proc)
mock api: record mock.proc REJECTED (duplicate key 'pid' (line 2)); the process was left alone and the record was moved to mock.proc.rejected.20261004T215448Z
mock api: leftovers from earlier runs need attention:
  mock.proc.rejected.20261004T215448Z: refused earlier (pid 1); handle the process by hand, then remove the file
exit=1 (duplicate key)
next: not started by this environment (no next.proc)
mock api: record mock.proc REJECTED (line 1 contains a carriage return); the process was left alone and the record was moved to mock.proc.rejected.20261004T215448Z
mock api: leftovers from earlier runs need attention:
  mock.proc.rejected.20261004T215448Z: refused earlier (pid 27913
); handle the process by hand, then remove the file
exit=1 (CRLF record)
decoy A pid 27982 ALIVE (state S; cwd /tmp/claude-0/-home-user-EarningsNerd/78df218f-8eea-5bb5-9669-b8dbafc877c6/scratchpad/proof2/tasks/decoy-env; cmd 'python3 mock_api.py')

## 9. cleanup of the proof's own decoys (killed by this proof script, not by stop_env.sh)
Terminated
Terminated
decoy A pid 27982 GONE
decoy B pid 28040 GONE
  no record files remain
```
- Correction to "Production reality" above (dated 2026-10-04 21:50 UTC; earlier text left as written): the enumerated id list omits
  16050 (MDLZ 10-Q 2013-08-08). The original probes in the critique session (15:54 UTC) covered ids 1–40 and 50, 100, 500, 1000,
  5000, 10000, 15000, 16050, 16069, 16070, 20000, 25000, 30000, 35000, 37000, 38000, 38500, 39000, 39032 — 59 ids, every one
  `has_content=false`. The 59 count stands; it remains a dated sample of those ids.
- Handoff alignment. `tasks/critique-handoff-2026-10-04.md` now carries the addendum's EN-01/EN-02/EN-03 acceptance wording
  verbatim, its criteria in the evidence and dependency cells, and its shared evidence rules in Validation; scope, order, the
  three main-based PRs and every deferred item are unchanged. Three independent verifier lenses (coverage, scope preservation,
  accuracy) ran for up to three rounds; their corrections: consent control names (`Accept All`, `Reject All`, `Customize`, from
  `CookieConsent.tsx`), the empty-state copy quoted literally from `FilingViewer.tsx`, a stray "EN-08" label replaced by the
  archive's section reference, the stale shutdown description in Validation, and the sampled-id count caveat (resolved above).
- `mock_api.py` change: `/health` adds `pid` (test tooling only). Servers stopped by `./stop_env.sh` in step 6 of the transcript;
  the proof's own decoys were killed by the proof script.
