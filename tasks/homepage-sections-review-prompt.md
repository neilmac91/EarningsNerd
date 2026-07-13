# Homepage "Trending Filings" & "Market Movers" — Keep / Fix / Kill Investigation Prompt (Claude Fable 5)

> **What this is.** A ready-to-run prompt for a Claude Code session on `claude-fable-5` that
> decides the fate of the two weakest homepage sections: a comprehensive value review of
> **Trending Filings** and **Market Movers** as they exist today, external research into what it
> would take (free/open-source first) to make each genuinely live up to its name, a validated
> investigation summary, and a remediation plan — with a **hard stop for founder approval before
> any product code changes**. It follows Anthropic's
> [Prompting Claude Fable 5 guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5)
> (goal-over-steps, effort framing, anti-overplanning, grounded progress claims, explicit
> boundaries, parallel subagents, fresh-context adversarial verification, lead-with-the-outcome
> reporting) and the cross-model
> [prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
> (XML structure, role, context and motivation, investigate before answering).
>
> **How to run**
> 1. Start a fresh Claude Code session on this repo with model `claude-fable-5`
>    (effort `xhigh` recommended for the research + validation depth; `high` is fine).
> 2. No attachments needed — the observed homepage symptoms are transcribed inside, and the
>    session re-verifies them against live prod with read-only requests.
> 3. Paste everything below the cut line as the first message.
> 4. Expect a long autonomous run. It ends with `tasks/homepage-sections-review-findings.md`,
>    a remediation plan, and a decision request in chat. **No product code changes are made in
>    this session.** After you approve an option, the same session (context intact) can be told
>    to implement it.

---8<--- copy everything below this line ---8<---

<role>
You are acting as EarningsNerd's fractional head of product and staff engineer, running a
keep/fix/kill review of two homepage sections. You treat homepage real estate as expensive:
every section must either earn its slot with evidence or make way. You are skeptical in both
directions — of feature-keeping bias (sunk cost, "it might be useful someday") and of
feature-killing bias (rubber-stamping the founder's hunch because he voiced it first). You are
comfortable recommending deletion, and equally comfortable saying "this is worth keeping —
here is the cheapest honest fix." You never manufacture value to justify keeping a feature,
and you never dismiss one without checking what it would cost to make it good.
</role>

<context>
EarningsNerd (https://www.earningsnerd.io) turns SEC filings (10-K/10-Q/6-K…) into grounded,
filing-only AI summaries for investors. Solo founder (Neil), FastAPI + Postgres on Cloud Run,
Next.js on Vercel. A new Pro-tier product just launched, so the homepage is now a sales surface
for paying clients — credibility and signal-to-noise matter more than ever. That is why you are
being asked now.

The homepage currently stacks: hero search bar → Popular Companies banner → Reporting This Week
(earnings-calendar section, `ReportingThisWeek`, which fully omits itself when empty) → value
props → **Trending Filings** → **Market Movers** → CTA. There is also a dedicated Calendar page
in the nav.

Neil's hypothesis — to be tested, not assumed: the *idea* behind Trending Filings and Market
Movers is good, but the execution doesn't deliver what the labels promise; the Popular Companies
banner, the calendar surfaces, and the hero search already cover most of what users want, so
these two sections add noise. He is explicitly fine with hiding either or both, temporarily or
permanently, if the cost/benefit doesn't justify fixing them. There is no sunk-cost constraint
in either direction.

Observed symptoms (screenshots taken 2026-07-06, logged-in homepage — treat as evidence, not as
the verdict):

- **Trending Filings** showed four cards, ALL Alibaba (BABA) 6-K filings, filed 11, 19, 19, and
  28 days ago. Every card: PULSE tier "On the radar", components "Filing cadence 57% / Filing
  type 43%", badges "Recent" and "Active Filer", a "View AI Summary" button. Nothing about this
  reads as "trending": one company, weeks-old filings, and a score visibly driven by cadence and
  form type rather than any demand or market signal.
- **Market Movers** ("What's moving in the market today") showed "SOURCE: CURATED" with the
  banner *"Showing curated fallback trending tickers. Last error: No symbols passed FMP
  validation"* above a static NVDA / TSLA / AAPL / MSFT list, with the footer still claiming
  "Data from Stocktwits & FMP". The section was advertising live market data while serving a
  hardcoded fallback and printing an internal error string to end users.
</context>

<verified_code_map>
A prior code scan (2026-07-06) mapped both features end-to-end. Treat these as established
facts — spot-check any claim you place load-bearing weight on (the file:line refs make that
cheap), but do not re-derive the map from scratch.

Naming: the UI labels don't match code names. "Trending Filings" = `HotFilings` component →
`GET /api/hot_filings`; "Market Movers" = `TrendingTickers` component → `GET /api/trending_tickers`.
Both mounted unconditionally in `frontend/app/page.tsx` (Trending Filings :187-198, Market
Movers :224-230), server-prefetched via `frontend/lib/serverApi.ts:139,143`.

**Trending Filings (HotFilings):**
- Chain: `frontend/features/filings/components/HotFilings.tsx` → `backend/app/routers/hot_filings.py:12`
  → `backend/app/services/hot_filings.py:93` (`_calculate_hot_filings` :123) → FMP earnings
  calendar (`app/integrations/fmp.py:312`) + Finnhub news sentiment (`app/integrations/finnhub.py:48`)
  → PULSE display via `app/services/pulse_service.py:47`, rendered by `FilingPulse.tsx`.
- Scoring: candidates = most recent `max(limit*3, 20)` filings by date, **no date floor**
  (`hot_filings.py:124-131`). `buzz_score` = 8 weighted components: recency (≤5.0, decays to 0
  over 72h), search_activity (7-day UserSearch count ×3), filing_velocity (30-day filing count
  ×2), filing_type_bonus (1.5 for 10-K/10-Q/20-F/40-F/6-K), earnings_calendar (1.0–4.0 via FMP),
  news_buzz/headlines/sentiment (Finnhub). Sort desc, take top `limit`.
- The observed "Filing cadence 57% / Filing type 43%" is exactly a filing >72h old (recency=0)
  with zero search/earnings/news signal: velocity 2.0/(2.0+1.5)=57%, type 1.5/3.5=43%. I.e. the
  PULSE on every screenshot card contained **no demand or market signal at all**.
- **Root cause of one-company sweep: there is no deduplication by company anywhere in the
  chain** (`hot_filings.py:125-131` selects per-filing with no distinct/group-by; :315-326 builds
  one record per filing; :331-332 sorts and truncates). Company-level components (search,
  velocity, earnings, news) are identical across all of a company's filings, and
  filing_velocity actively amplifies clustering — a prolific filer's filings all rise together.
- Badges: `sources` always starts with "recency" (`hot_filings.py:274`) → **"Recent" appears on
  every card by construction**; "Active Filer" = filed ≥1 other filing in 30 days.
- Ops: in-memory cache, 15-min TTL (`hot_filings.py:75,101-121`); admin-token manual refresh
  endpoint; **no cron/scheduler anywhere** — refresh is lazy on request.

**Market Movers (TrendingTickers):**
- Chain: `frontend/features/companies/components/TrendingTickers.tsx` (10-min refetch; 2-min
  price-only refresh via `GET /api/trending_tickers/refresh-prices`) →
  `backend/app/routers/trending.py:25` → `backend/app/services/trending_service.py:64` →
  Stocktwits trending (`app/integrations/stocktwits.py:38`, keyless) validated against FMP
  (`app/integrations/fmp.py`).
- Pipeline (`trending_service.py:180-258`): Stocktwits fetch → heuristic pre-filter (crypto/forex/
  warrants, `stocktwits.py:94-138`) → cached ETF-set exclusion → **FMP validation**: symbol passes
  only if `FMPProfile.is_valid_stock` (`fmp.py:51-67`) — not ETF/fund, exchange ∈ {NASDAQ, NYSE,
  AMEX, NYSEArca}, actively trading — → top 10 enriched with quotes.
- The observed error string is set at `trending_service.py:239` when zero symbols pass step 4.
  Fallback cascade (`:64-150`): fresh fetch → stale in-memory cache → 24h persistent file cache
  (`.cache/trending_tickers.json`) → **hardcoded curated list NVDA/TSLA/AAPL/MSFT/AMZN**
  (`:473-480`). The banner text incl. `Last error: …` is built at `:140-142` and rendered
  verbatim to end users at `TrendingTickers.tsx:285-289`.
- The router never passes `force_refresh` (`trending.py:33`), so the UI "Refresh" button cannot
  actually force a live refetch — it re-reads the same ≤10-min cache.
- Note: the ETF-set cache has a Redis tier, but **prod runs no Redis** (ADR-0004, L1 in-memory
  only) — check what that implies for prod behavior.

**Cross-cutting:**
- **No per-section feature flag exists.** `frontend/lib/featureFlags.ts` gates other features
  only; both sections render unconditionally. Sibling precedent: `ReportingThisWeek` fully omits
  itself when empty (`page.tsx:180-182`); these two do not.
- **Analytics: exactly two PostHog events**, both click-only — `hot_filing_summary_clicked`
  (`HotFilings.tsx:160-164`) and `market_mover_clicked` (`TrendingTickers.tsx:94-102`). No
  impression/section-view events, so CTR is currently unknowable; Refresh clicks untracked.
- Config: `FMP_API_KEY` etc. serve BOTH sections (movers validation/quotes/ETF + hot-filings
  earnings calendar); `FINNHUB_API_KEY` serves Trending Filings only; Stocktwits is keyless;
  **`ALPHA_VANTAGE_*` is configured in `app/config.py:256-259` but unused by either feature.**
  When FMP is unconfigured, validation is skipped and symbols pass through unvalidated
  (`trending_service.py:317-326`).
- Tests: `backend/tests/unit/test_stocktwits_fmp.py` (~415 LOC), `test_pulse_service.py`,
  `test_hot_filings_tz.py`, `frontend/tests/unit/filing-pulse.spec.tsx`. **Gaps: no test renders
  either component; nothing asserts dedupe behavior; the fallback/banner strings are asserted
  nowhere.**
- Footprint: Trending Filings ≈ 672 backend + 257 frontend LOC; Market Movers ≈ 717 backend +
  370 frontend LOC; plus `fmp.py` (426 LOC) genuinely shared by both, and page/queryKey/serverApi
  glue.
</verified_code_map>

<mission>
Decide, independently for each of the two sections, with evidence:

**KEEP AS-IS** / **FIX** (specify exactly what) / **REBUILD** (specify on which data source) /
**MERGE** (fold its residual value into an adjacent surface — Popular Companies, calendar,
search) / **HIDE** (temporarily pending a later rebuild, or permanently).

Hiding is a fully acceptable outcome. So is a cheap fix that makes a section honest. A verdict
without a single clear recommendation is a failure mode — produce one recommendation per
section, with confidence (high/medium/low) and the two or three decisive reasons.

Deliverables: (1) a validated investigation summary written to
`tasks/homepage-sections-review-findings.md`, (2) a remediation plan with checkable, sized
items, (3) a decision request in chat. Then **stop — no product code changes in this session**.
After approval, you may be asked to implement the chosen option in this same session; plan for
that continuity, but do not start it unbidden.
</mission>

<questions_to_answer>
These are the questions the report must answer — not a step recipe. Sequence and parallelize
them however you judge best; several are independent and suit parallel subagents.

1. **The bar.** Write down, before researching any fixes, what "Trending Filings" and "Market
   Movers" would each need to show — content, freshness, honesty of labeling — for a retail/
   prosumer investor to get value that the hero search, Popular Companies banner, and calendar
   surfaces don't already provide. Every later option is judged against this bar, and overlap
   with the existing surfaces counts against a section, not for it.

2. **Current-state truth.** Do the transcribed symptoms still hold right now? Verify with
   read-only GETs against live prod (`https://api.earningsnerd.io/api/hot_filings?limit=4`,
   `https://api.earningsnerd.io/api/trending_tickers`, and the public homepage). Confirm or
   correct the mapped root causes. State plainly where each section's current labeling is
   dishonest (e.g. "Recent" on every card by construction; "What's moving in the market today"
   over a hardcoded list; an error string shown to end users; a Refresh button that can't
   refresh).

3. **Why Market Movers is actually failing.** "No symbols passed FMP validation" has several
   candidate explanations a quick scan suggested — test, extend, or replace them: (a) the prod
   FMP key is invalid/expired or the plan changed; (b) FMP's current free/legacy tier no longer
   serves the profile endpoint or symbol coverage the validator needs; (c) Stocktwits trending
   is now dominated by symbols that legitimately fail `is_valid_stock` (crypto/OTC/indices);
   (d) FMP changed its exchange naming so the allowlist in `fmp.py:51-67` no longer matches
   (e.g. "NASDAQ Global Select" vs "NASDAQ"). Check current FMP and Stocktwits docs/ToS, and the
   shape of the live prod responses. You cannot read prod env secrets — say what you could and
   couldn't establish.

4. **Engagement evidence.** With only two click events and no impression tracking, what can and
   cannot be known about real usage today? Treat the gap itself as a finding. List the exact
   PostHog queries Neil should run (event names, date range, the question each answers), and
   make minimal instrumentation (enough to compute per-section CTR) a plan item so a future
   keep/kill call is data-driven.

5. **External landscape (web research, cited).** What data sources could make each section
   genuinely real, at what cost? Free/open-source first. Starting points, not an exhaustive
   list — follow the evidence:
   - *Trending Filings:* SEC EDGAR full-text search API (efts.sec.gov) and current-filings
     feeds; capabilities of `edgartools` (already a repo dependency); internal demand signals
     already in the DB (the `UserSearch` table already powers `search_activity`; summary
     generations are another demand signal); whether any public EDGAR popularity/traffic signal
     still exists.
   - *Market Movers:* current Stocktwits trending API status and its ToS for commercial use;
     FMP free-tier reality (endpoints, limits — this doubles as evidence for Q3); Finnhub free
     tier movers/quotes; the already-configured-but-unused Alpha Vantage integration (its
     TOP_GAINERS_LOSERS endpoint); yfinance and similar libraries **including their ToS
     posture**; any other free sources for gainers/losers/actives.
   For each candidate: data quality vs the bar, cost, rate limits, commercial-use licensing,
   implementation effort (S/M/L + rough hours), failure modes, and ongoing maintenance load.
   Verify against live documentation — your trained knowledge of pricing/limits/ToS is stale by
   default. Every external claim carries a URL and access date. Discard candidates that violate
   the budget rule or ToS; say so explicitly rather than silently dropping them.

6. **Options and cost-benefit.** Per section, an options matrix (hide now / minimal honest fix /
   rebuild on source X / merge into adjacent surface / keep as-is), scored on user value vs the
   bar, build effort, ongoing cost and ops load, and risk. Then the single recommendation. Every
   recommendation ships with 30-day kill criteria / success metrics measurable with the
   instrumentation you propose. If a verdict is HIDE: specify the reversible mechanism (the
   `featureFlags.ts` pattern exists; `ReportingThisWeek`'s self-omission is the sibling
   precedent), what happens to the backend endpoints, integrations, and tests, and what if
   anything is preserved for a later rebuild. Cheap optimizations to the existing pipelines
   (company dedupe, a freshness floor, honest badge semantics, suppressing the raw error string,
   a working refresh) belong in the "minimal honest fix" option with effort estimates, whatever
   the final verdict.
</questions_to_answer>

<validation>
The analysis is not done until it has been attacked. Before writing the final report:

- **Claim audit.** Re-verify every load-bearing claim: code claims by reading the cited lines,
  external claims against the cited primary source, prod-behavior claims against the live
  responses you captured. Anything you could not verify stays in the report labeled
  **UNVERIFIED** — do not silently drop or silently keep it.
- **Symptom reproduction.** Your root-cause explanations must predict the screenshots: show
  that the mechanisms you identified produce exactly "four BABA cards, 57/43 PULSE, Recent on
  every card" and exactly the observed fallback banner. If a mechanism doesn't fully predict
  the observation, say what's missing.
- **Adversarial pass.** For each section, dispatch a fresh-context subagent given only your
  evidence summary and asked to argue the *opposite* of your verdict as strongly as the evidence
  allows (the repo's `/llm-council` skill is an alternative harness for this). Record in the
  report what survived, what you changed, and why. Fresh-context verifiers outperform
  self-critique — do not skip this because you feel confident.
- **Estimate audit.** Check effort estimates against the actual code touchpoints listed in the
  plan — an estimate that doesn't enumerate its files is a guess.
- Throughout the report, distinguish fact / inference / judgment, and attach confidence to each
  verdict.
</validation>

<deliverables>
1. **`tasks/homepage-sections-review-findings.md`** — structure:
   - TL;DR verdict table (section / verdict / confidence / one-line why) — first thing in the file
   - The bar (Q1)
   - Current state and root causes, confirmed (Q2–Q3)
   - Engagement evidence and the PostHog queries for Neil (Q4)
   - External landscape — candidates table with citations + access dates (Q5)
   - Options matrix and recommendation per section, with kill criteria (Q6)
   - Remediation plan: **Phase A** (zero-risk prep — e.g. instrumentation, copy fixes you'd do
     under any verdict) and **Phase B** (the recommended option), checkable items, each sized
     (S/M/L + hours) with the files it touches
   - Validation log: what was checked, how, what failed, what changed after the adversarial
     pass, what remains UNVERIFIED
   - Appendix: research notes
2. **Final chat message**: lead with the verdict table and the decision you need from Neil —
   the supporting detail lives in the file. Then stop and wait.
3. If the investigation surfaces a durable operating lesson (or a doc/code contradiction), note
   it in the findings file so the implementation PR can fix the doc and add the `lessons/` entry
   per CLAUDE.md's self-improvement loop.
</deliverables>

<boundaries>
- **No product code changes, no dependency installs, no new accounts or API-key signups.** The
  only files you write are `tasks/homepage-sections-review-findings.md` (and `tasks/todo.md` if
  you want a checklist mirror). If measurement genuinely requires a scratch script, it goes in
  `backend/scripts/` with a docstring header and is disclosed in the report.
- **Read-only against prod.** Public GETs only; no POSTs, no auth probing, no admin/refresh
  endpoints, no load testing. Keep request volume trivial.
- Any live sec.gov access goes through the repo's edgar service layer conventions (SEC caps at
  10 req/s per IP; see CLAUDE.md rule 5) — for this investigation, prefer reading docs over
  hammering endpoints.
- Scope is these two sections and their plumbing. Do not redesign the homepage, and do not
  evaluate unrelated features. If you find something materially broken elsewhere while
  auditing (e.g. a dead integration used by another feature), note it in the appendix and move
  on.
- CLAUDE.md governs throughout — in particular: contract tests are locked; prod has no Redis;
  all config through `app/config.py` Settings; entitlements only via `entitlements.py`.
- When the evidence is thin, say so and attach lower confidence — do not extend the
  investigation indefinitely to chase certainty. If you have enough information to call it,
  call it.
</boundaries>

<how_to_work>
- You are operating autonomously. Neil is not watching in real time and cannot answer questions
  mid-run, so do not pause to ask "Should I…?" — the single intended pause is the final approval
  gate. Pause earlier only if genuinely blocked on something only he can provide (say exactly
  what, and what you'll do with it).
- When you have enough information to act, act. Do not re-derive facts established in the
  verified code map, re-litigate decisions Neil has already made (hiding is pre-authorized as an
  acceptable outcome), or narrate options you will not pursue.
- Delegate independent workstreams (the external-research candidates, the adversarial passes) to
  parallel subagents and keep working while they run. Intervene if a subagent goes off track or
  is missing context.
- Before reporting progress or findings, audit each claim against a tool result from this
  session. Only report work you can point to evidence for; if something is not yet verified,
  say so explicitly. If a check fails, report it with the output — never paper over it.
- Neil's hypothesis is context, not the conclusion. If the evidence says a section is worth
  fixing, recommend that plainly — he is paying for your judgment, not your agreement. Equally:
  do not invent speculative future value to save a section the evidence condemns.
- Budget rule: primary recommendations must be implementable at $0/month (free tiers,
  open-source, data already in the repo/DB). Paid options belong in the comparison table with
  verified current pricing, and may be the primary recommendation only if nothing free clears
  the bar — in which case say that explicitly.
- Write the final chat message for someone who saw none of your work: outcome first, complete
  sentences, no working shorthand, every file or term introduced in plain language. Readability
  over brevity; selectivity over compression.
</how_to_work>
