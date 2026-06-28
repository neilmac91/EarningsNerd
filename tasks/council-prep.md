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
  registration (`REGISTRATION_MODE=invite_only`), `TRUSTED_PROXY_HOPS=1`. **Stripe still in test mode**
  and **backend PostHog key unset** — both matter for a real beta.

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
| `STRIPE_BETA_PROMO_CODE_ID` | $0 100%-off beta checkout | Create **live** Stripe coupon (prod still test-mode) | Hrs | **Yes** (beta monetization) |
| `INTERNAL_JOB_TOKEN` + Cloud Scheduler | New-filing alerts, digests, facts backfill | Set secret + create cron jobs | Hrs | **Yes** — watchlist/alerts value prop is inert without it |
| Turnstile (2 keys) | Bot defense on auth/contact/waitlist | Provision Cloudflare keys | Hrs | Ops/security |
| `ENABLE_SECTION_TABS`, `ENABLE_FINANCIAL_CHARTS` | UX variants (components exist) | Env flip (+ UX glance) | Hrs | Low/cosmetic |
| `ENABLE_GUEST_DAILY_QUOTA=true` | Per-IP anon cost cap | Env flip | Hrs | ⚠️ Redis OFF in prod → fail-open may neuter this without Memorystore |

### Bucket B — Needs finishing (real dev work left)

| Item | State | What's left | Effort |
|---|---|---|---|
| `ENABLE_COMPARE` | Half-built | Picker can't tell which filings have summaries → dead-ends on 404; flow must be reworked | Days |
| `ENABLE_INSIDER_ACTIVITY` | Mostly done | Works but ~75s live SEC fan-out; needs latency/rate-limit validation (test plan exists) | Days |
| `ENABLE_APPLE_SIGNIN` + `APPLE_CLIENT_ID` | Backend built | Apple Developer Console setup or button 404s | Hrs–days (mostly console) |
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

**Cross-cutting risk:** planning docs are slightly ahead of actual prod — **Stripe still test-mode**
(can't take $0 beta checkouts on a test coupon) and **backend PostHog key unset** (blind on
server-side funnel events).

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

## 2. The Moat — "why won't ChatGPT eat this?"  · _Trust/moat_  · **(3 of 5 advisors already ran — complete from partials)**

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

**Partial results captured (to fold into the chairman synthesis):**
- **Contrarian:** candidate moats are mostly features; none compound with scale; "ChatGPT won't bother — retail SEC analysis is a thin niche — so distribution into a wedge is your only defensible bet."
- **First Principles:** "moat" is the wrong lens at pre-seed; real question is "can this founder reach a wedge of users who care faster than the category commoditizes?" The Alibaba-in-RMB catch is proof of founder taste, not a moat.
- **Expansionist:** every verified citation mints a labeled (claim → source → pass/fail) pair → a proprietary "financial verification" data asset / API / trust-stamp others embed; "ChatGPT sells confidence, you sell accountability."
- _Still needed:_ Executor + Outsider responses, then peer review + chairman.

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
> zero-wait example-filing landing, earnings calendar (needs an API key), the $0 beta-checkout promo, and the
> alerts/digest cron pipeline.
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

- [ ] #1 Wedge
- [~] #2 Moat — 3/5 advisors captured (Contrarian, First Principles, Expansionist); needs Executor + Outsider + review + chairman
- [ ] #3 Pricing
- [ ] #4 Beta scope
- [ ] #5 Distribution
- [ ] #6 Fundraising
- [ ] #7 Dormant features
