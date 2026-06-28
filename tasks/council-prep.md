# LLM Council — Prep Doc (EarningsNerd beta + investor readiness)

> Working doc for running the `llm-council` skill against EarningsNerd's highest-stakes
> pre-beta decisions. Contains: working assumptions, a read-only audit of built-but-dormant
> functionality, and 7 paste-ready council questions. Nothing here has been *run* yet.

_Last updated: 2026-06-28_

---

## Working assumptions (correct me if wrong)

- **Goal:** balanced — improve the site for beta users *and* sharpen the investor story.
- **Investor stage:** not decided yet (Question #6 helps decide).
- **Uncertainties in play:** positioning, pricing, product focus/UX, trust/accuracy/moat.
- **Resources:** solo founder, launching closed beta within weeks → recommendations must be lean and high-leverage.
- **Current prod state (verified):** site live but pre-traffic (`WAITLIST_MODE=false`), invite-gated
  registration (`REGISTRATION_MODE=invite_only`), `TRUSTED_PROXY_HOPS=1`. **Stripe is live in prod**
  (live, non-test id; the beta promo gives beta users Pro free). Watch item: confirm the **backend
  PostHog key** is set so server-side funnel events fire.

---

## Standard pre-council prep (prepended to every question)

> **[Pre-council prep — for whoever runs this:** Before convening the council, review the EarningsNerd
> codebase and `CLAUDE.md` — plus the `tasks/` roadmap docs, `frontend/lib/featureFlags.ts`, and
> `backend/app/config.py` — to ground the framing in the project's *actual current state* (real
> feature-flag status, entitlements, pricing, roadmap, known gaps). Fold those findings into the brief
> each advisor receives so they give specific, grounded advice rather than generic takes. Also tell every
> advisor the founder is **solo and shipping beta within weeks**, so recommendations stay lean.**]**

---

# Part 1 — Dormant Functionality Audit (read-only; built-but-not-enabled)

Excludes things already correctly enabled in prod (invite gate, waitlist flip, quality gate,
edgartools sections, feedback widget, proxy-hops security fix). Grouped by activation effort.

### Bucket A — Flip-ready (complete; needs an env flip or a quick founder action)

| Item | Unlocks | Waiting on | Effort | Strategic? |
|---|---|---|---|---|
| `ENABLE_QUALITY_BADGE=true` | Honest "Full/Partial — retry" badge (backend verdict already exists) | Env flip | Hrs | **Yes** — launch-runbook says set at launch to match "honest about quality" claim |
| `STREAM_SECTION_REVEAL=true` | First content ~10s vs ~35–60s; identical final output, safe fallback | Env flip | Hrs | **Yes** (perceived latency) |
| `NEXT_PUBLIC_EXAMPLE_FILING_ID` | Zero-wait "see an example" aha (else falls back to /company/AAPL) | Run pregenerate job, paste id | Hrs | **Yes** — flagged as the single best activation lever |
| `ENABLE_CALENDAR` + `FMP_API_KEY` | Earnings calendar on dashboard | Provision FMP key | Hrs | Medium |
| `STRIPE_BETA_PROMO_CODE_ID` | $0 100%-off beta checkout (Pro free for beta users) | ✅ Done — live, non-test Promotion Code id (`promo_…`; a `co_` coupon id won't validate) set in prod | — | **Yes** (beta monetization) |
| `INTERNAL_JOB_TOKEN` + Cloud Scheduler | New-filing alerts, digests, facts backfill | Set secret + create cron jobs | Hrs | **Yes** — watchlist/alerts value prop is inert without it |
| Turnstile (2 keys) | Bot defense on auth/contact/waitlist | Provision Cloudflare keys | Hrs | Ops/security |
| `ENABLE_SECTION_TABS`, `ENABLE_FINANCIAL_CHARTS` | UX variants (components exist) | Env flip (+ UX glance) | Hrs | Low/cosmetic |
| `ENABLE_GUEST_DAILY_QUOTA=true` | Per-IP anon cost cap | Env flip | Hrs | ⚠️ Redis OFF in prod → fail-open may neuter this without Memorystore |

### Bucket B — Needs finishing (real dev work left)

| Item | State | What's left | Effort |
|---|---|---|---|
| `ENABLE_COMPARE` | Half-built | Picker can't tell which filings have summaries → dead-ends on 404; flow must be reworked | Days |
| `ENABLE_INSIDER_ACTIVITY` | Mostly done | Works but ~75s live SEC fan-out; needs latency/rate-limit validation (test plan exists) | Days |
| ~~`ENABLE_APPLE_SIGNIN` + `APPLE_CLIENT_ID`~~ | ✅ **LIVE in prod** (configured 2026-06-28) | — done; no longer dormant | — |
| `REVERSE_TRIAL_ENABLED` | Built, deliberately OFF | Must NOT re-enable until hashed-email trial ledger exists (re-grantable via re-registration churn) | Days |
| `ENABLE_FPI_FILINGS` | Phased program, "awaiting approval" | Multi-phase; flipping early risks ~7× currency distortion | Weeks |

### Bucket C — Experimental / eval-gated (won't affect beta UX directly)

| Item | What it does | Gate |
|---|---|---|
| `USE_STRUCTURED_OUTPUT` | JSON response_format — documented **top fix for "hit-and-miss" summary quality** | Must beat baseline in eval harness before flip |
| `AI_FAST_MODEL` / `AI_SECTION_RECOVERY_MODEL` | Cheaper-model cost levers | Eval sign-off |

### Bucket D — Already handled (don't lose the prod overrides)
`TRUSTED_PROXY_HOPS=1`, `REGISTRATION_MODE=invite_only`, `WAITLIST_MODE=false` are already set
correctly in prod. The *code defaults* are the unsafe/closed ones.

**Cross-cutting watch item:** Stripe is now **live in prod** (live promo code in place — beta users get
Pro free). Remaining check: confirm the **backend PostHog key** is set, or server-side funnel events
won't fire (blind on conversion analytics during beta).

---

# Part 2 — The 7 Council Questions

Each is paste-ready. The standard pre-council prep block above applies to all of them.

## 1. The Wedge — one job, one user to lead with  · _Positioning_

> `council this:` "EarningsNerd (earningsnerd.io) turns SEC 10-K/10-Q/20-F filings into structured AI
> summaries with verifiable citations, plus an 'Ask this Filing' copilot, peer comparison, insider
> (Form 4) activity, watchlists with change-alerts, and foreign-issuer/ADR support verified live on
> Alibaba in native RMB. Right now the site shows all of it. For a closed beta I must pick **one**
> headline job-to-be-done and **one** ideal user to lead with on the homepage and in onboarding —
> candidates: (a) retail/DIY investors who find filings intimidating, (b) serious individual investors /
> 'finance Twitter' who already read filings and want speed + an edge, (c) prosumers/analysts who need
> defensible, citable facts. More features dilute the message. Which single wedge + ICP do we lead with,
> and what do we deliberately de-emphasize or hide? I'm a solo founder launching beta in weeks."

_Stakes: drives the homepage, the activation flow, and the investor one-liner. Everything downstream depends on it._

## 2. The Moat — "why won't ChatGPT eat this?"  · _Trust/moat_  · **✅ COMPLETE (run #2, 2026-06-28 — full transcript: `.claude/council-transcripts/council-2026-06-28-q2-moat.md`)**

> `council this:` "Pressure-test EarningsNerd's defensibility — both for investors and for deciding where
> I spend scarce build time. A skeptic argues: 'Anyone can paste a 10-K into ChatGPT; Bloomberg/Koyfin/
> AlphaSense already serve professionals; SEC EDGAR data is free and public. This is an AI wrapper with a
> 12-month head start, not a moat.' My candidate moats: (a) citation/provenance verification + an eval
> harness gating numeric accuracy — a trust layer general LLMs lack; (b) foreign-issuer/ADR coverage in
> correct native currency that general tools get wrong; (c) workflow lock-in via watchlists, change-alerts,
> and saved history; (d) a proprietary verification dataset (claim → source span → pass/fail) accumulating
> with every summary. Are these real, durable moats or just features with a head start? What would actually
> make EarningsNerd defensible, and what is the strongest *honest* answer to 'why won't ChatGPT eat this?'
> I'm a solo, pre-revenue founder."

_Stakes: load-bearing assumption under fundraising and product focus._

**All 5 advisor positions (full transcript in `.claude/council-transcripts/council-2026-06-28-q2-moat.md`):**
- **Contrarian:** candidate moats are mostly features; none compound with scale; "ChatGPT won't bother — retail SEC analysis is a thin niche — so distribution into a wedge is your only defensible bet."
- **First Principles:** "moat" is the wrong lens at pre-seed; real question is "can this founder reach a wedge of users who care faster than the category commoditizes?" The Alibaba-in-RMB catch is proof of founder taste, not a moat.
- **Expansionist:** every verified citation mints a labeled (claim → source → pass/fail) pair → a proprietary "financial verification" data asset / API / trust-stamp others embed; "ChatGPT sells confidence, you sell accountability."
- **Executor** (run #2): the verification dataset is the only real candidate, but **only if instrumented now** ("a moat you can't measure is a story"); don't build more features (ADR-currency is copyable in a weekend); honest answer = OpenAI will never assume liability for a wrong financial number. Monday: queryable verification rows + clickable "verified against source" badge + write down the catch-rate stat.
- **Outsider** (run #2): the trust gap is the real story but it's buried in jargon; one side-by-side demo of ChatGPT getting a number wrong and you catching it beats any feature; (c) lock-in and (d) dataset are inert/invisible today.

**Chairman verdict (summary):** These are *features with a head start, not moats.* The one honest, durable answer is **accountability — "ChatGPT sells confidence; you sell verifiable, source-traced accuracy."** Treat the verification dataset as *evidence, not a future API.* Peer review's unanimous catch: the Expansionist over-romanticizes the dataset (self-graded labels are circular; span-verification may be deterministic, not a learned flywheel; no buyer). The gaping hole all advisors missed = **distribution + retention** (public summary pages + ticker/ADR SEO → Q5). **Do first:** build the one side-by-side ChatGPT-gets-it-wrong / EarningsNerd-catches-it demo with click-through to the source span — it's the user aha, the investor answer, and the best distribution content at once.

## 3. Pricing & Packaging — is $14 flat / Free-5 right?  · _Pricing_

> `council this:` "EarningsNerd's pricing is Free (5 summaries/month; no copilot, export, or alerts) vs Pro
> at $14/mo or $140/yr (unlimited summaries; 'Ask this Filing' copilot capped at 1000 questions/mo; PDF/CSV
> export; real-time alerts; 8-K coverage). Should I rethink this before beta? Specific tensions: (a) is $14
> too low if the real buyer is a serious investor who'd pay $30–50 for an edge — or too high for casual
> retail; (b) is gating the copilot (my most differentiated, most expensive feature) 100% behind Pro the
> right wall, or should free users get a taste to drive conversion; (c) is '5 summaries/month' the right
> free limit to convert vs frustrate. I'm solo and pre-revenue, so willingness-to-pay is completely
> unproven. What pricing + packaging would you ship for beta, and what would you test?"

_Stakes: highest-leverage revenue lever; cheap to change now, painful after beta users anchor on a price._

## 4. Beta Scope & the Aha Moment — what users see  · _Product UX_

> `council this:` "For closed beta I must decide what to ship vs hide. **Live & solid:** AI summaries,
> copilot, peer comparison, watchlist, dashboard feed, search. **Behind flags because incomplete:**
> multi-filing Compare (picker dead-ends on filings without summaries), insider activity (~75s load on
> large companies), earnings calendar (needs a paid API), financial charts (rough UX), foreign-issuer
> listings. Separately, my AI summaries have honest quality variance — some return 'partial,' and I have a
> feature-flagged badge that says so plus a Regenerate button. Two decisions: (1) which flagged features, if
> any, are worth turning on for beta vs leaving dark; (2) is surfacing a 'partial summary' badge a
> trust-builder (transparent, sourced) or a credibility-killer for first-time users and investor demos? And
> what is the single zero-to-wow activation moment I should engineer for a new user? Solo founder, beta in weeks."

_Stakes: first impressions in beta are irreversible._

## 5. Distribution — first 100 engaged users (and first 10 payers)  · _GTM_

> `council this:` "I'm a solo founder opening a closed beta of an AI SEC-filing tool — pre-traffic, no
> audience, crowded space (fintech newsletters, Koyfin, finance YouTube, ChatGPT). I have invite-gated
> magic-link onboarding and a 100%-off beta promo ready. What is the highest-leverage way to get the first
> 100 *engaged* beta users and convert the first 10 to paying, given I can't run paid acquisition and have
> very limited time? Pressure-test channel bets: 'finance Twitter' / Reddit (r/investing, r/SecurityAnalysis),
> a free public 'filing of the week' teardown as content, ADR/Alibaba-investor communities (leaning into the
> foreign-issuer edge), or design-partner outreach to newsletter writers. Which one or two would you
> concentrate on, and what's the concrete first move?"

_Stakes: product readiness ≠ traction; traction is what moves early investors. Biggest blind spot in the roadmap._

## 6. Fundraising Strategy — raise, from whom, what story?  · _Investor "not sure yet"_

> `council this:` "I'm a solo, pre-revenue founder of EarningsNerd (AI SEC-filing analysis), opening a closed
> beta in weeks, with a built-out, technically strong product but no traction or audience yet. I'm not sure
> whether to raise money at all, and if so from whom. Options: (a) raise a small angel/pre-seed round now on
> product + founder insight to buy runway; (b) bootstrap to traction first, then raise a seed round from
> strength; (c) don't raise — run it as a lean, profitable solo product. Pressure-test which path actually
> fits *this* business and *this* founder, what milestone would make each credible, and — if I raise — what
> the honest narrative is for a tool that's impressive technically but unproven in the market."

_Stakes: answers the open investor question directly; determines what the other questions optimize for._

## 7. Dormant Features — finish / flip / kill + sequence  · _Founder time allocation_

> `council this:` "I'm a solo founder of EarningsNerd, launching a closed beta in weeks, and my scarcest
> resource is my own time. I have a pile of functionality that's BUILT but dormant in production. Inventory:
> • **Flip-ready (hours each):** honest quality badge, streamed section reveal (faster perceived load), a
> zero-wait example-filing landing, earnings calendar (needs an API key), and the alerts/digest cron pipeline.
> (The $0 beta-checkout promo is already live in prod.)
> • **Needs real work (days–weeks):** multi-filing Compare (picker dead-ends, ~days), insider-activity panel
> (~75s load, needs validation, ~days), Apple sign-in (console setup), a reverse-trial (blocked on an
> anti-abuse ledger), and foreign-issuer/ADR support (multi-week, high-value but risky if rushed).
> • **Experimental, eval-gated:** structured-output mode — the documented top fix for inconsistent summary
> quality — and cheaper-model cost levers.
> For EACH major item I need a verdict — **finish now, flip on, defer, or kill outright** — and then a
> **sequenced activation order** for the run-up to beta. Bias toward ruthless prioritization: assume I can
> only ship a handful before launch. What's the highest-leverage activation sequence, and what should I have
> the courage to cut or leave dark rather than polish? What's the single thing to do first?"

_Stakes: pure founder-time-allocation. Polishing the wrong dormant feature (Compare, FPI) could cost weeks; a 2-hour flip (quality badge, example filing) might move activation more._

---

# Coverage

| # | Question | Covers |
|---|----------|--------|
| 1 | Wedge & ICP | Positioning |
| 2 | Trust & moat | Trust/moat (3 partials exist) |
| 3 | Pricing & packaging | Pricing |
| 4 | Beta scope & aha (what users see) | Product UX |
| 5 | Distribution / first 100 | GTM |
| 6 | Fundraising strategy | Investor "not sure yet" |
| 7 | Dormant features: finish/flip/kill + sequence | Founder time allocation |

---

# How to run (recommended)

- **Order:** #1 → #2 → #5 → #7 → #4 → #3 → #6
  (Positioning first; moat/distribution/sequencing next; pricing & fundraising last, since they depend on the earlier answers.)
- **#2:** complete from the 3 captured partials (add Executor + Outsider, then peer review + chairman) rather than re-running clean.
- **Per run:** 5 advisors (parallel) → anonymized peer review (parallel) → chairman synthesis → verdict in chat.
- Don't run all 7 at once — they're a lot to absorb and a lot of compute. A few at a time.

## Verdict log
_(filled in as questions are run)_

- [x] #1 Wedge — **VERDICT (run #1, 2026-06-28):** lead with **the serious individual investor who already reads 10-Ks (wedge b)**; JTBD = _"read this filing for me, tell me what changed since last quarter, and show me exactly where it says so."_ Homepage one-liner: _"Every new 10-K and 10-Q, read for you — what changed since last quarter, every claim linked to the source."_ Hide everything else (insiders, Compare, calendar, charts, ADR, copilot-as-hero, peers/watchlists) → land on ONE report, not a feature grid. First move: run `evals/` golden set to measure the boilerplate-degradation rate — that number gates whether a single-report wedge is shippable in weeks. (Full council write-up below.)
- [x] #2 Moat — ✅ complete (run #2, 2026-06-28): 5 advisors + peer review + chairman. Verdict: features-not-moats; lead with **accountability** ("ChatGPT sells confidence; you sell verifiable accuracy"); dataset = evidence not API; real work = distribution+retention. First move: the side-by-side "ChatGPT-wrong / we-catch-it" demo.
- [x] #3 Pricing — **run 2026-06-28** (full council; transcript: `.claude/council-transcripts/council-transcript-2026-06-28-q3-pricing.md`).
      **Unanimous:** **$14 must die before public launch** (every advisor — it hard-codes "toy" into an accountability moat; #1/#2). **Three tensions resolved.** (a) **Price level:** advertise **Pro at $39/mo ($390/yr)** during beta, delivered 100%-off as "Founding Member — normally $39, free for beta"; never show $14. De-risk by **testing $39 vs $29** (anchor high — you can discount from $39 forever, never re-anchor up from $14). (b) **Copilot wall:** not 100% Pro and not free-flat → **3 copilot questions, LIFETIME (not monthly), on the first filing, then hard wall** (it's the "now you test it" proof of the moat per #4/#2; bounded so the margin hit is trivial — but size cost-per-question first; drop to 2 if needed). Summaries stay hard-walled at 5. (c) **Free limit:** **keep 5 summaries/mo** — the lever is timing (wall hits mid-research, #5), not the count. **The one experiment:** a **fake-door price test, $39 vs $29, both routing to the comped checkout** (ships Monday on an existing flag, zero revenue risk, real intent) — framed on the **ANNUAL** plan ($390 vs $290 "locked for life"), since annual prepay is the strongest WTP signal. **Council blind spots (all 5 missed):** the annual plan IS the real WTP instrument (nobody tested it); nobody put a NUMBER on copilot inference cost (a 1000-q cap can go gross-margin-negative); WTP ≠ retention. Also instrument **distinct filings/user/30d** (subscription-vs-event signal) + **cost-per-engaged-user**. First Principles' lone dissent (credit packs / event not habit) noted but rejected — recurring alerts+watchlist+"what changed" is the habit loop (#1).
- [x] #4 Beta scope — **run 2026-06-28** (full council; transcript: `.claude/council-transcripts/council-transcript-2026-06-28-q4-beta-scope.md`).
      **Three calls.** (1) **Surface vs hide:** land on ONE report URL (the curated known-good ADR what-changed teardown); foreground only the **what-changed diff + click-to-source citations**, with the **copilot present-but-quiet** (one "Ask this filing" box pre-seeded with 2-3 example questions). Search = a quiet nav link. **HIDE peer comparison, dashboard feed, and — emphatically — the watchlist** (its alerts are inert per #7's deferred cron → a "Watch" button is a promise that silently breaks; unanimous). Kill the feature grid. (2) **The badge — route around it, don't flip it on, don't "flex" it:** onboarding/example/demo links run in `demo_mode` (badge **and** Regenerate suppressed → first-timers/investors never see "Partial"); show only a quiet green "Full" cue post-evals on user-initiated filings; do NOT ship a "Verified — N claims" count (invites audit, detonates the moat while depth is the #1 gap). When a user's OWN filing is partial, fall back to **"deepening this report…" with the partial content shown+sourced**, not a yellow retry. (3) **The aha = the ChatGPT-catch, not the diff:** a pre-rendered, **dated, reproducible** side-by-side ("ChatGPT: $X (wrong) / EarningsNerd: $Y →") whose number click-scrolls to the exact source span (wow <10s, zero typing), then the **immediate second beat** = the pre-seeded copilot prompt ("now you test it"). Catch = reason to believe; diff = reason to return. **Peer-review catches:** the second-session cliff (routing around "Partial" just relocates the hit to the user's first self-chosen filing — handle the off-rails failure path); define the activation PostHog event (source-span click); specify who curates/maintains the known-good set (drift risk). **First thing:** hand-pick & pin 3-5 known-good ADR filings as the locked onboarding set and capture ONE real, dated ChatGPT-wrong-number catch against the first — everything else hangs off that artifact.
- [x] #5 Distribution — **run 2026-06-28** (full council; transcript: `.claude/council-transcripts/council-transcript-2026-06-28-q5-distribution.md`).
      **Verdict:** concentrate on **(c) ADR/foreign-issuer communities via (b) curated teardowns**; deliberately do NOT do (a) broad finance Twitter or (d) newsletter outreach until there's a body of work. Lead with the period-over-period diff in native RMB (the deep-link works today; the dark FPI listing flag is not a blocker). Three additions the raw advice missed: (1) onboard new users onto *known-good* (non-"partial") filings only — BABA/PDD/SE/MELI/NVO; (2) at this scale 1:1 outreach beats broadcast; (3) instrument deep-links (UTM) + time-box the 100%-off promo so a payment trigger actually exists (the first-10-payers ask has no trigger while beta is free). **First move:** one screenshot-able Alibaba 20-F teardown (diff-first, RMB, verified not "partial", UTM'd) posted as a value-first reply to one real recent BABA-filing question.
      **↪ Reconciled with #1 (Wedge) + #2 (Moat) [2026-06-28]:** emphasis correction, not a reversal — Q5 was framed before #1/#2 landed, against a prep doc that still headlined the ADR edge. #1 chose ICP = serious individual investor who reads 10-Ks, message = "what changed since last quarter, with the receipts," and **hid ADR/20-F from the product surface**; #2 said lead with **accountability** ("ChatGPT sells confidence; you sell verifiable accuracy") and treat ADR-currency as a *copyable proof point, not a priority*, with the hero = the side-by-side "ChatGPT-gets-a-number-wrong / we-catch-it" demo. So: **demote the native-RMB angle from the lead *message* to (i) a beachhead *venue*** (the underserved ADR corner of the #1 ICP, where ChatGPT fails most visibly → the wedge is most vivid and competition thinnest) **and (ii) a marquee *proof point*.** The teardown must **lead with the catch/diff** (not "native currency") and funnel to the **same single what-changed report the homepage leads with** — no acquire-on-X / land-on-Y split (hiding the ADR *feature* in-product ≠ not publishing ADR *content*). Q5's core stands (community-seeded teardowns; defer broad finance-Twitter & newsletter outreach). **Upgraded first move (merges #5 + #2):** build the BABA teardown *as* the side-by-side where ChatGPT misstates an RMB figure and EarningsNerd catches it with click-through to the source span — at once #1's wedge, #2's positioning + first move, and #5's channel content. (Bonus: #1 verified click-to-source + what-changed diffing are **shipped/live**, so "lead with the diff" is deliverable today.)
- [ ] #6 Fundraising
- [x] #7 Dormant features — **run 2026-06-28** (full council; transcript: `.claude/council-transcripts/council-transcript-2026-06-28-q7-dormant-features.md`).
      **Verdict:** quality is the gate — run the `evals/` golden set FIRST (as a measurement, not a flip), then eval-gate **`USE_STRUCTURED_OUTPUT`** (the documented top fix for boilerplate degradation; it's the real #1, not "experimental" — #1/#2/#5 all collapse if the report isn't good). **Activation sequence:** (1) run evals — first verify the golden set actually contains ADR/degrading cases and write down the pass/fail partial-rate threshold; (2) eval-gate `USE_STRUCTURED_OUTPUT` (if it fails → STOP and fix the prompt, don't launch on a hit-and-miss base); (3) hand-curate a known-good (non-"partial") ADR filing whitelist; (4) pregenerate + paste `NEXT_PUBLIC_EXAMPLE_FILING_ID` using one of those; (5) flip `STREAM_SECTION_REVEAL`; (6) flip `ENABLE_QUALITY_BADGE` (only AFTER evals — don't stamp "Partial" on an unmeasured failure rate); (7) confirm the backend PostHog key. **DEFER to slack-time only:** `INTERNAL_JOB_TOKEN`+cron alerts (retention is a post-signal problem; fires on noise/nothing in a thin closed beta). **KILL/leave dark:** Compare, Insiders (~75s), FPI (weeks + ~7× distortion), Reverse Trial (until anti-abuse ledger), Calendar (paid key, off-spine), Turnstile + Guest Quota (invite-gated beta → no anon surface; Redis-off makes the quota fail-open theater anyway), section-tabs/charts (cosmetic). **First thing:** verify the eval harness can actually *see* the boilerplate/ADR bug it's gating — else its number is meaningless — then run it. _(Correction, 2026-06-28: Apple Sign-In is **already LIVE in prod**, so it's no longer dormant — the council ran with it listed as "defer"; that's now moot/satisfied, zero founder time needed.)_

---

## Run #1 — Wedge & ICP — Council Verdict (captured 2026-06-28)

> Run via the `llm-council` workflow (5 advisors → anonymized peer review → chairman), grounded in
> `CLAUDE.md`, `config.py`, `featureFlags.ts`, `tasks/research/competitors.md`, and
> `tasks/research/user-needs.md`. **Two premises in the brief turned out to be stale** — see the
> correction box below; both were caught by the council's code verification and independently
> re-verified against the working tree.

### ⚠️ Factual correction (verified against the code, not the brief)
The brief (inherited from `tasks/research/*` and my framing) asserted two things that are **false in the
current codebase** — the research docs are stale relative to shipped code:
- **Click-to-source IS shipped & live (not dark).** `provenance_service.py` builds `#:~:text=` SEC
  deep-links; `SourceTrace.tsx` renders them on risks (`SummaryRisks.tsx:21`) and `MetricSourceLink.tsx`
  on financials (`SummaryFinancials.tsx:58`, `FinancialMetricsTable.tsx:106`) — gated only on `source_url`
  existing, **not** on `ENABLE_QUALITY_BADGE`.
- **"What changed" diffing IS shipped & live.** `getWhatChanged` is fetched unconditionally
  (`frontend/app/filing/[id]/page-client.tsx:1110`) and `<WhatChanged>` renders when `has_changes`
  (`frontend/app/filing/[id]/page-client.tsx:1308`), backed
  by `change_report_service.build_change_report`. **Not** behind a dark flag.
→ Implication: the wedge's headline ("what changed, with the receipts") is **deliverable today**. The real
remaining gap is **content quality** (boilerplate degradation; only 4 XBRL metrics), not the trust plumbing.

### Where the council agreed (high-confidence)
- **ICP = serious individual investor (b)** — the finance-Twitter / already-reads-10-Ks reader. Demand
  already exists ("they self-serve on the SEC site; you just make them faster"). Retail (a) unanimously
  rejected: most don't read filings, are least able to catch AI errors → you'd manufacture demand *and*
  ship worst-case output to the most fragile audience.
- **JTBD = "read this filing for me, show me what changed, with the receipts."**
- **Hide list (unanimous):** insiders (75s load), multi-filing Compare (dead-ends), earnings calendar
  (paid key), financial charts (rough), ADR/20-F, copilot-as-hero + 1000-cap, raw peers/watchlists. Land
  on ONE generated report, not a feature grid.
- **The quality gap is a forcing function, not a reason to retreat** — a fixed narrative can't dodge a
  weak filing the way query-driven chat can; that exposure is what forces the fix.

### Where the council clashed
- **Headline wording:** "see what changed" (First Principles, Outsider) vs "verifiable structured analyst
  report" (Executor, Expansionist, Contrarian). **Dissolved by verification** — both are shipped, so the
  one-liner can carry both.
- **Is verifiability a pre-beta blocker?** Contrarian made it a hard go/no-go gate; Executor (alone)
  checked the repo and called it done. Verification sides with the Executor — the veto targets a solved
  problem.
- **Distribution & price:** Expansionist tied the wedge to a screenshot-driven growth loop and reframed
  $14-vs-$39–89 as a deliberate land-grab; Reviewer 2 flagged the blind spot — it's a *closed, invite-gated*
  beta with no public report URLs, and screenshot-virality would amplify the *failure* cases of a
  hit-and-miss pipeline. Both true at different horizons.

### Blind spots the peer review caught
- **CONTENT-IS-EMPTY ≠ missing receipts.** A green "verified" deep-link can sit on confident boilerplate —
  provenance verifies the *span exists*, not that the *claim is right*. For a "notices-a-wrong-number" ICP,
  a verified-looking citation on a hollow narrative is *more* dangerous than none.
- **The activation demo will lie** if it's AAPL/NVDA — mega-caps are exactly where the pipeline performs
  best and *hides* the variance.
- **There's a free, decisive empirical test nobody ran:** the `evals/` golden set can quantify the
  boilerplate-degradation rate *before* invites; `pregenerate_examples.py` + `HeroExample` can A/B a marquee
  report to finance-Twitter this week with zero new code.
- **$14 is a positioning *risk*, not just a land-grab** — 60–75% below the $39–89 band can read as "toy" to
  the prosumer who associates price with rigor.

### Recommendation (chairman)
Commit to **ICP = serious individual investor (b)**, **JTBD = "what changed since last quarter, with the
receipts."** Homepage one-liner: _"Every new 10-K and 10-Q, read for you — what changed since last quarter,
every claim linked to the source."_ Hide the breadth. The quality gap is MORE exposed and it's still the
right bet, because the wedge forces the one fix that matters. Before invites: (1) flip
`NEXT_PUBLIC_ENABLE_QUALITY_BADGE='true'` (one-line; backend verdict + `AI_QUALITY_GATE` quota protection
already exist) so partial-and-honest beats silent boilerplate; (2) run the `evals/` golden set and add a
hard floor — if a filing degrades to boilerplate, auto-retry on a stronger model or **refuse to render it**
rather than surface a hollow report with a green badge. Hold $14 for beta (free via the promo anyway); plan
to move toward the $39–89 band before public launch.

### The one thing to do first
**Run the `evals/` golden-set harness to measure what % of filings currently degrade to deterministic
boilerplate.** That single number — not the positioning debate — decides whether a single-report wedge is
shippable in weeks. Low rate → flip the quality badge and send invites. High rate → that's your only
pre-beta engineering task.
