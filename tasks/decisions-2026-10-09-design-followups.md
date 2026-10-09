# Design critique 2026-10 follow-ups: the open decisions (2026-10-09)

The four design-critique PRs merged on 2026-10-09: #1146 (`cc2282a`), #1147 (`29493b5`), #1148
(`1a31b29`) and #1150 (`869c1da`). The closing report left decisions A to E open. The founder then
delegated them: "Thoroughly analyse the pros and cons of each of these outstanding decisions and take it
on yourself to proceed with your recommendation. I put my full trust in you. Spend lots of tokens if you
need to get this right. Do work that you're proud of". This record gives, for each decision, the
question, the evidence, the options with their pros and cons, the decision, what shipped, and when to
revisit it. Implementation is in the PR that adds this file.

## A. A Free user cannot replace a stored failed summary

**Question.** The filing page shows a stored summary row as its "Summary temporarily unavailable" card
when the row is failure filler, carries a writer error, or has no body. Its Retry sends `force=true`,
which the generate route gates to Pro, so a Free user hits a 403 with no way out. The same route replayed
an earlier pipeline's "Generating summary" marker row on every visit. The page treats that marker as "no
summary" and starts a run, gets the marker back, and stays on "generating" for every user.

**Evidence.** The current pipeline never stores a failure row: an error payload returns before the save
(`summary_pipeline.py`, the `summary_status == "error"` branch). The rows a reader can meet are older:
the writer-era fallback body and `writer_error` rows, earlier pipelines' in-progress markers, and the
background path's "requires OpenAI API key" placeholder, written only when the key is unset (local
development).

**Options.**
1. Keep both the Pro gate and the replay. Pro: no change. Con: a Free user's way out of our own failure
   is a dead end, and a marker row never resolves for anyone.
2. Frontend only: hide Retry from Free users, or offer the upgrade prompt on it. Pro: honest about the
   gate. Con: still a dead end, and it charges the user for our failure. Markers stay stuck.
3. Open `force` to every signed-in user. Pro: one line. Con: it reopens what the Pro gate closes: anyone
   could replace a good summary that every reader sees with a worse one, at our cost.
4. **Chosen.** A stored row the page cannot show is regenerated in place for any signed-in user, with or
   without `force`, and metered as a fresh generation. `force` over a summary the page shows stays
   Pro-only. Keep-better (never let a refresh downgrade the stored tier) protects only rows the page shows.
   Pro: both dead ends close. The Pro gate keeps its purpose, because nothing a reader can see is ever
   replaced by a non-Pro request. Cost stays inside each user's quota: the unit is counted when the
   provider starts and refunded when the run errors or comes back partial. Bookmarks survive, because
   the row is updated in place. One rule decides on the route and in keep-better: `is_summary_ready`,
   applied to the body the route would serve. A run admitted for an unready row treats that row as a
   missing summary at every step (two Codex review rounds on #1166):
   - The route clears nothing for it. A Pro Regenerate still clears the filing's XBRL and progress.
   - If another request makes the row ready before the run reaches the pipeline, or before a leader
     the run joined finishes, the run serves that summary.
   - If the row becomes ready while the run generates, the run keeps it.
   - If a leader the run joined fails, the run claims the generation, as a follower of a failed first
     generation does.

   So the waived Pro gate never pays for a second summary, never replaces one that readers already see,
   and never wipes XBRL that another run fetched. Con: a Free user's successful Retry spends one monthly
   unit. Two runs on different instances can still both generate inside that window, and each user is
   metered.
5. An operator drain of failure rows. A complement, not a substitute: users recover without it. Not run.
   No drain is authorized, and the production count of such rows is unknown.

**A′ stays declined:** auto-generating over stored failure filler when the page loads. A page view should
not spend a user's unit silently, so filler keeps its card and an explicit Retry. The marker row keeps its
existing auto-run, because the page already treats it as "no summary yet", as it does a missing row.

**Shipped.**
- `routers/summaries.py`: `refresh_unready`, judged by `is_summary_ready` on
  `source_safe_business_overview` (the body the route would replay). It is passed on as
  `replace_unready_only`, and the route clears nothing for such a row.
- `summary_pipeline.py`: keep-better applies only when the stored row passes the same rule. A
  `replace_unready_only` run serves or keeps a row that has become ready, and does not serve one that is
  still unready after a joined leader fails.
- The background path is otherwise unchanged; the keep-better rule also applies to admin
  refresh-stale.

`tests/unit/test_summary_unready_refresh.py` (17 cases) covers:
- the truth table;
- a failed refresh keeping the row;
- keep-better on both paths;
- a row made ready before the pipeline starts (served, with the other run's XBRL and progress intact);
- a row made ready during generation;
- a follower of a failed refresh claiming the generation;
- the flag's control.

Mutation proofs: dropping any one of the nine conditions fails between 1 and 11 of the 17 cases.

The company lead keeps "Open latest filing" over an unready row (#1147, tenth round): the page it opens
now resolves for everyone.

**Revisit** if failure rows turn out to be common in production. A drain is then cheaper than waiting for
visits.

## B. The hero's primary action

**Question.** Canvas 1d makes "Find filings" (search) the hero's one primary action, which demotes "See
a live example", today's tracked hero CTA.

**Evidence.** PostHog EU project, 90 days, bots excluded: 4 homepage visitors and 55 pageviews; 1 hero
example click; 7 searches, all by 1 person; 10 quick-access clicks by 3 people. That is no signal either
way. Production registration is invite-only (`/api/auth/registration` →
`{"mode": "invite_only", ...}`). Generating a summary needs an account, so a searcher can land on a filing
whose summary they cannot get.

**Options.**
1. "Find filings" primary. Pro: matches the canvas, and search-first suits returning users. Con: under
   invite-only it leads most visitors toward a gate they cannot pass, and it demotes the one path every
   visitor can finish.
2. **Chosen.** Keep "See a live example" primary, with search as the secondary action. Pro: every
   visitor can finish it, and the tracked `example_cta_clicked` (placement `hero`) stays continuous.
   Con: it departs from the canvas.
3. Two equal CTAs. Con: it breaks "one primary action per screen" (`frontend/DESIGN_SYSTEM.md`).

**Shipped.** The decision and its trigger are in `LandingHero.tsx`'s doc comment. **Revisit** when access
opens to the public (`resolveAccessMode` returns `public`). Search-first is then the better default.

## C. A stored body that is notices and headings alone

**Question.** The backend's readiness rule (`is_summary_ready`: sitemap, search `summary_ready`, and now
the route's unready refresh) does not strip internal notices. The filing page does
(`stripInternalNotices`, then `stripLeadingExecutiveHeading`) and shows the failure card when nothing is
left. A body made only of notices and an "Executive Summary" heading would read as ready in the backend
and as a failure on the page.

**Options.**
1. Mirror the page's notice stripping in Python. Con: the notice patterns would then exist in two
   languages and could drift, to guard a body no writer produces.
2. **Chosen.** Keep it declined, and prove the case cannot arise. Pro: the reason for declining becomes
   a gate. Con: the gate reads the frontend's source, which couples a backend test to two TypeScript
   files (the same pattern as `summaryPlaceholder.spec.ts` in the other direction).
3. Stop stripping notices on the page. Con: readers would see internal notices.

**Shipped.** `tests/unit/test_summary_writer_page_parity.py` drives the three writers over degenerate
inputs: the section projection, the structured fallback renderer with and without its validation notice,
and the XBRL timeout fallback, each with and without the risk projection. Every body must be empty or
still show content after the page's cleaning, and `is_summary_ready` must agree. The page's notice
patterns and heading rule are read from the TypeScript sources. Mutation proof: a renderer that stops
after its notice and heading fails 10 of 18 cases.

## D. copilot-eval reds on PRs that change no Copilot code

**Question.** The live Copilot eval accepts a run only with 18 of 18 rows scored and passed. On PRs that
do not touch the Copilot, a red run leaves the PR with no sanctioned way forward except another push.

**Evidence** (the 400 most recent `Copilot filing fidelity` runs, 2026-09-27 to 2026-10-09):
- After #1052 (2026-10-02, whole-excerpt citation check), 16 of the 73 runs on PRs that change no Copilot
  code had a red first attempt (22%; Dependabot excluded). The split was 11 of 38 runs in DeepSeek's peak
  hours and 5 of 35 off-peak.
- The logs name the reason for all 16: 11 runs were `Unverified or ambiguous referenced citation` only,
  3 were decision F only, and 2 were mixed. That is 17 citation rows against 5 F rows. The F-only triage
  rule covered 3 of the 16.
- The retained artifacts name the question of all 17 citation rows. 15 are BABA
  `viewed-native-revenue-2025`, and 2 are ASML `us-gaap-sales-net-income-2025` (both on 9 October). In
  every case the model cites table or KPI cells instead of one contiguous span of at least 24
  characters:
  - BABA: the condensed consolidating schedule's row "Revenue from third parties - 833,583 98,433
    64,331 - 996,347 137,300", cited as "Revenue from third parties ... 996,347 ... 137,300", or as the
    bare "996,347";
  - ASML: the KPI panel's "€32.7bn total net sales", one character under the floor, or reordered into
    "Total net sales\n€32.7bn".
  The whole-excerpt check is right to withhold all of these. The prompt already forbids them ("Never
  stitch separated table cells or sentences together, or insert an ellipsis into an excerpt"; "at least
  24 characters").
- #1111's private retry rescues some draws and not others. The post-#1111 BABA rows show both
  generations withheld. The short ASML excerpt is not offered a retry at all, because an excerpt under
  the floor never earns one.
- The replay tool the rule names predates #1111. It streams the aggregate candidate into every
  generation, so any report that holds a recovered row exits 3, and condition (3) could not be met; the
  F-only rule has been in that state since #1111. Its successor
  (`tasks/review-evidence/copilot-eval-triage-2026-10-09/`) replays each recorded generation and
  enforces decision F, as production does. On the 7 red reports that carry `generation_attempts` it
  exits 0, with every withheld row reproducing its recorded reasons; the predecessor exits 3 on 3 of
  them. Both #1148 rows reproduce.
- Dependabot PRs are red 11 of 11 for another reason: Dependabot-triggered runs get no Actions secrets
  (`OPENAI_API_KEY` is empty). This is known and handled by maintainer replacement PRs
  (`tasks/pr-disposition-2026-10-07.md`); no change here.
- Re-runs: the rule against re-running for a green result was broken three times in the window: twice
  by this work on #1148 (runs 37935449192 and 37958886664; the PR merged on the second re-run's green)
  and once on `codex/wave3-durable-background-tasks` (run 37700200842). All three first attempts carried
  the citation withhold.

**Options.**
1. Keep the F-only rule. Pro: the founder's text stands. Con: about one PR push in five that touches
   backend code waits on a withhold it did not cause. The only way out is another push, which is a
   re-draw by other means. The rule also invites re-runs, and it invited three.
2. Relax acceptance: allow one withheld row, or score withholds as passes. Pro: fewer reds. Con: it
   blinds the gate on exactly the PRs that change the Copilot. The founder kept acceptance unchanged on
   2026-10-02.
3. **Chosen.** Widen the triage rule from decision-F reasons to every named publication withhold that
   the offline replay reproduces under main's code. Every other condition stays: no model-facing,
   boundary or harness change in the PR; every other row passes; a PR comment; never re-run. Pro: the
   logic is the F rule's own. If the PR changes nothing the model sees, and main's code withholds the
   same candidate for the same reason, the PR did not cause the red. Acceptance, error counting,
   thresholds and exit codes stay unchanged, and a PR that changes the Copilot still needs a clean run.
   Con: a red PR takes one more step, the replay, which is free and takes minutes. A row the replay
   does not reproduce blocks, as does any other failure.
4. Fix the root cause: the model citing table or KPI cells as elided or short excerpts. Pro: it removes
   most reds and a real withhold that users meet. Con: it is a model-facing change, gated by the RUNBOOK
   on `--runs 3` aggregates and its own measurement. The prompt already forbids the behaviour, so a
   stronger instruction is not obviously the fix, and density-forcing prompts have a negative result on
   record. Recorded below as the follow-up for the Copilot workstream.

**Rule 12.** The prose rule against re-runs failed three times in a week. `copilot-eval.yml` now draws
once per head commit. Its first step after checkout, `backend/scripts/copilot_eval_draw_gate.py`, looks
for an earlier draw on the head in any run or attempt: an attempt whose runner step started. When one
exists, the run reports that draw's verdict and skips every later step, before it installs anything or
touches the provider credential. So a re-run attempt, a draft-to-ready toggle and a reopen all replay
the first draw.
- A draw that was cancelled or is still running counts as a draw, and not as a green one. Cancelling a
  draw that looks red buys no fresh one.
- A head where nothing drew still draws, including a re-run of an attempt that failed before its
  runner step.
- A failed read of the earlier runs fails closed.

The first version gated only re-run attempts and left toggles to the RUNBOOK text, because gating them
would also block predeclared protocols that toggle on a frozen head (the prompt candidate's Q1 to Q3).
Codex's review on #1166 showed the toggle and reopen paths bypassed that gate. A second version let a
PR-body line naming a committed preregistration exempt the head. Codex's next review showed that the
body can be edited after a red draw, so that line could buy another draw once the result was known.
Now nothing exempts a head. A protocol that needs several draws of the same code gives each draw its own
head, a commit that changes only its evidence folder. That is the RUNBOOK's "a new draw comes from a new
push", declared in its preregistration and visible in the PR's history.
`tests/unit/test_copilot_eval_rerun_refusal.py` pins the decision against a fake of GitHub's two reads,
matched to real payloads, including a body line that names a real preregistration and buys nothing. It
also pins the workflow: the gate runs first on every attempt, and no later step runs without its draw.

**Shipped.** The RUNBOOK triage paragraph (widened, with the self-application and toggle clauses, and
the successor replay tool named for condition (3)); the successor tool with its self-test and its
replays of the 13 red reports; the re-run refusal step and its test (mutation proofs: removing the step,
never firing it, letting it pass, moving it after the runner, or `continue-on-error` each fail the test);
and `lessons/ops-copilot-eval-red-is-triaged-never-rerun.md`. A disclosure comment on #1148. This PR does
not apply the widened rule to its own run.

**Revisit** once the excerpt behaviour is fixed. If the citation withhold stops recurring, the widened
rule should rarely fire. If it fires on a new question, investigate that question as here rather than
attributing by habit.

## E. Production verification

**Question.** The Vercel connector could not confirm the frontend deploys (403 on the team scope), and
the merged stack had not been looked at in production.

**Done.** A read-only check of https://www.earningsnerd.io and https://api.earningsnerd.io on 2026-10-09
(no login, no forms; screenshots and data in the session's scratchpad):
- **API.** The registration mode is `invite_only`. The company search carries `latest_filing`, and its
  dates end in `Z` (#1148's `iso_z`).
- **Pages.** The homepage, `/company/AAPL` and the example filing `/filing/3` serve the merged stack:
  - the hero, its access line, the search, the single-surface example and the trust strip;
  - the identity lead, the filings index and Compare periods;
  - the identity strip, the verification tally, the indexed sections and contents list, the risk tally,
    the Source pane (Filing · Ask; an aside on desktop, a sheet on phone) and the launcher.
- **Each page in desktop light, desktop dark, phone and reduced motion:**
  - no sideways scroll at 390px;
  - no running animation under reduced motion, including the company page's loading bones;
  - no stuck loader or error card;
  - the only console error is the expected 401 from `/api/auth/me` for a visitor.
- **As built, not a defect.** "What changed" is section 03 on the example: it follows the metrics
  section, which is 02 there. #1146's "section 02" assumed metrics first. The identity line shows no
  exchange because the API has none for the company.

**Fixed in this PR** (introduced or amplified by the stack, or one class away on a page it owns):
- Section 01 sat 44px below the contents list on wide screens. The phone-only jump nav lives inside the
  sections' `space-y` stack, and Tailwind 3 margins every child after a sibling that lacks the `hidden`
  attribute. The pattern predates #1146 at 24px, and #1146's wider rhythm made it 44px. The nav now sits
  outside the stack. `SummaryBlocks.spec.tsx` pins it: section 01 is the first child of the spaced stack.
- The company lead read "Summarize latest filing" until the summary read returned, then flipped to "Open
  latest summary" (#1147). "Summarize" now waits for the read to say there is no summary (`null`). While
  the read is pending, or when it fails, the lead opens the filing. `company-page-lead.spec.tsx` pins both.
- The Ask callout under the summary, and the trial notice in billing, kept the light theme's brand
  border in dark mode. Both now take `dark:border-white/10`, matching their `dark:bg-white/5`.

**Found, not changed here (each predates the stack; see follow-ups):**
- Black company logos are nearly invisible on the dark-mode logo circle.
- The header's auth placeholder swap shifts the layout by about 0.145 CLS on every page, and the example
  link's demo flag removes a badge after hydration.
- On phone, the site header stays above the Source sheet's scrim and stays clickable. The sheet is
  `aria-modal`, and the z ladder puts workspace sheets (z-40) under the header (z-50).
- The floating Source launcher covers the end of reading lines near the bottom of the viewport.
- The change report's "EPS" is basic EPS (7.49), while the summary text quotes diluted (7.46), and the
  results table rounds to 7.5.
- `/api/filings/{id}` dates still use `+00:00` (noted in #1148).

## Follow-ups (not done here)

1. **Copilot (RUNBOOK-gated):** the model cites table or KPI cells as elided or short excerpts (decision
   D). Candidates, each needing its own pre-registered measurement:
   - make the private regeneration's guidance name the failure ("a citation excerpt is one unbroken
     span of at least 24 characters: cite the whole table row or a sentence; never shorten a row with an
     ellipsis");
   - give table rows an explicit exception to "the shortest contiguous span … at most ~30 words";
   - offer the private regeneration to an excerpt under the floor, which today never gets one.
   Since #1111's retry, on PRs that change no Copilot code (37 runs, 111 draws of each question), the
   withhold message ended 5 BABA draws (about one in 22) and 2 ASML draws (about one in 55).
2. **Change report EPS:** label the figure "EPS (basic)", or prefer diluted EPS
   (`facts_service` keys `earnings_per_share` to `EarningsPerShareBasic` first).
3. **Dark-mode logos:** give a loaded logo a light chip in dark mode.
4. **Layout shift:** reserve the header's signed-out actions' width while `/me` resolves; read the demo
   flag where the server can see it.
5. **Phone Source sheet:** inert the header while the sheet is modal, or raise the sheet above it on the
   ladder (`bottomChromeLadder.spec.ts` pins the rungs).
6. **Launcher overlap:** pad the reading column's end by the launcher's height.
7. **A lint gate for light-only brand tints:** `border-brand-border` / `bg-brand-weak` with no `dark:`
   pair in the same class text (two such sites were found and fixed here).
8. **Copy, minor:** the XBRL timeout fallback ends "Click 'Regenerate Analysis' for the full AI-powered
   insights", an action only Pro users have. A structured payload with a whitespace headline leaves an
   empty Executive Summary paragraph. The page still shows the following sections, as the parity test
   pins.
9. **Pro Regenerate clears before it owns the generation:** the route clears the filing's XBRL and
   progress before the pipeline elects a leader. A second Regenerate of the same filing that joins the
   first wipes the XBRL the first one fetched, and nothing rebuilds it. This predates decision A, which
   no longer clears for an unready row. Fix: move the clearing to the leader path.
10. **A run that loses a save race:** keep-better, the concurrent-writer `IntegrityError` path and
    decision A's re-check all keep the stored row and return its id. The run still streams its own
    markdown, which the page replaces on `complete` with the stored row. Its unit stays counted, unless
    the result was partial and refunded. If a lost race should cost nothing, refund on all three paths
    together (Codex review on #1166, third finding of the second round).
