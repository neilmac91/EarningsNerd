# Open PR/Issue Queue Drain — Execution Tracker (2026-06-11)

Approved runbook: close redundant PR, land feature work, then drain the
dependabot queue in risk order (security → backend floors → frontend devDep
majors → frontend runtime majors), serial with rebase+CI gates wherever PRs
share a manifest/lockfile; finish with Issue #240 and a legacy-deps issue.

## Phase 0 — Hygiene
- [x] Close PR #220 (fully redundant — every hunk already on main)

## Phase 1 — Feature work
- [x] Merge PR #242 (homepage v2; reviews resolved, CI green) → 5a0c159
- [ ] OPERATOR: set NEXT_PUBLIC_EXAMPLE_FILING_ID in Vercel (launch-runbook step 4)

## Phase 2 — Security
- [x] Merge PR #234 (@protobufjs/utf8, root lockfile) → f8188a5
- [x] Update-branch + merge PR #226 (frontend minors incl. next 16.2.6 security) → 11ca006
- [ ] Confirm PR #233 auto-closes (subsumed by #226)

## Phase 3 — Backend deps
- [x] Merge PR #222 (python-multipart floor) → 8f5d475
- [x] Merge PR #223 (email-validator floor) → 9149c0d
- [x] Merge PR #225 (sentry-sdk floor) → 5ac2906
- [ ] Merge PR #224 (pydantic floor — conflicted; waiting on dependabot auto-rebase)
- [x] Rebase + merge PR #235 (pinned bumps: bs4, arelle, posthog) → 62d5699

## Phase 4 — Frontend devDep majors (serial, rebase + CI gate between each)
- [ ] #227 jsdom 29
- [ ] #228 @vitejs/plugin-react 6
- [ ] #230 vercel CLI 53
- [ ] #231 TypeScript 6

## Phase 5 — Frontend runtime majors
- [ ] #232 @vercel/analytics 2.x
- [ ] #229 lucide-react 1.x

## Phase 6 — Engineering + debt
- [x] File tech-debt issue: remove legacy SEC packages → issue #244
      (verified: arelle-release + sec-edgar-downloader have zero imports;
      sec-parser still used by filing_parser.py)
- [x] Implement Issue #240 (accession-aware XBRL extraction) → PR from this
      branch. New `edgar/instance_extractor.py` (shared duration/period
      filters), instance-first fetch order, v2 cache keys, 10-Q/10-K xbrl
      timeout budget raise, 20 new unit tests; 341 backend tests pass.

## Review notes
- #220: verified hunk-by-hunk against main before closing (ci.yml, vercel.json,
  devops-automator.md all already applied).
- #224 conflict despite "different lines": see tasks/lessons.md (adjacent-line rule).
- `@dependabot rebase` comments are posted with backtick-escaping + a footer,
  so dependabot ignores them. Working levers: GitHub's update-branch API for
  conflict-free PRs; dependabot's own conflict-triggered auto-rebase otherwise.
- #240 fix deviates from the issue text deliberately: companyfacts (accession-
  aware since #239) outranks get_financials(), which is demoted to last resort
  because it IS the wrong-filing source the issue targets.

---

# Activation Roadmap — Execution Checklist

Source of truth: `tasks/activation-gap-analysis.md`. North star: anonymous visitor →
first successful, high-quality summary, fast and reliable.

Order: quick wins first (Q1→Q8), then strategic bets (S3 harness → S1 → S2 → S4 → S5).
Strategic bets pause for review before/after. Quick wins ship in batches.

## Quick Wins

- [x] **Q1 — Waitlist gate.** DECISION (user): keep gate up, open the demo. Added
      `/company`,`/filing` to ALLOWED_PREFIXES so waitlist visitors can try the full
      flow; homepage `/` stays gated. Default flip deferred to launch. ✅ guards tests pass.
- [x] **Q2 — Zero-wait example.** `backend/scripts/pregenerate_examples.py` resolves each
      QuickAccessBar ticker's latest 10-K, persists Company/Filing, and caches the summary via
      `generate_summary_background`. Homepage "See an Example" CTA deep-links to
      `/filing/{NEXT_PUBLIC_EXAMPLE_FILING_ID}` when set, else falls back to `/company/AAPL`.
      Cache population runs in prod (network+AI). ✅ eslint clean, 30 vitest pass, script imports.
- [x] **Q3 — "Stalled" warning at 15s.** Raised threshold to 45s + "usually 30–60s" hint.
      `page-client.tsx:618`. ✅ verified: eslint clean, 30 vitest pass.
- [x] **Q4 — XBRL timeout lottery.** XBRL now starts concurrently with the filing-document
      fetch (was serialized after it); enrichment budget raised 8s→18s.
      `summaries.py`. ✅ verified: 261 backend tests pass.
- [x] **Q5 — Default to the right filing.** "Recommended" banner + row badge for the latest
      10-K (else latest filing) on the company page, one-click summary CTA. Behind
      `ENABLE_RECOMMENDED_FILING` flag (default on). Also fixed a latent rules-of-hooks
      violation (useMemo after early returns). ✅ eslint clean, 30 vitest pass.
- [x] **Q6 — Stream resilience.** Added one automatic stream retry on transient failure
      (before content delivered). NOTE: roadmap's timeout-mismatch premise was partly
      inaccurate (stream excluded from endpoint middleware `main.py:237`; client 120s is an
      *inactivity* timeout reset by 3s heartbeats) — so timeout reshuffling was unnecessary;
      the real gap was no auto-retry. ✅ eslint clean, vitest pass.
- [x] **Q7 — Orphaned background tasks.** `run_generation_guarded` wrapper guarantees a
      terminal "error" state if a fire-and-forget task crashes; `/progress` flips stale
      (>180s) non-terminal rows to retryable error. ✅ 7 new unit tests pass.
- [x] **Q8 — Raw 500s on circuit-open.** Global FastAPI handler converts `CircuitOpenError`
      → 503 + Retry-After. ✅ 2 new unit tests pass.

## Strategic Bets (pause for review)

- [x] **S3 — Eval harness (BUILT; baselining needs API keys/network).** `backend/evals/`:
      canonical schema, deterministic scorers (schema-validity + numeric-accuracy-vs-XBRL +
      substantive-coverage), multi-provider registry (baseline/gemini-json/claude-sonnet/
      claude-opus/qwen/kimi/deepseek — Claude via native SDK, others OpenAI-compat, cost
      tracked), golden-set seed + auto-builder, runner+report, README. ✅ 12 offline scorer
      tests pass. Running the baseline/bake-off requires SEC network + provider keys (prod/CI).
      Per checkpoint rule, PAUSE before S1 (prompt/schema rewrite) for review.
- [x] **S1 — Prompt/schema conflict (BEHIND DEFAULT-OFF FLAG).** `AI_USE_STRUCTURED_OUTPUT`
      flag: structured mode uses new schema-first prompts (`prompts/10k|10q-structured-agent.md`,
      narrative-format block removed), enforces `response_format={"type":"json_object"}` at the
      API layer, and pins temperature to 0.1. Flag off = current behavior, byte-for-byte.
      ✅ 2 unit tests (off unchanged / on enforces JSON+schema prompt+temp); 152 unit+smoke pass.
      ADOPTION GATE: run the S3 harness `baseline` candidate with the flag on vs off; flip the
      default only if it beats baseline on schema-validity + numeric accuracy + coverage.
- [x] **S2 — Brittle section extraction (core).** Added the missing 10-K TOC/length guard:
      `_looks_like_toc` + `_accept_section` reject TOC slivers and fall through to the next
      pattern (the 10-K path previously accepted the first match unguarded). Added extraction-
      confidence logging (N/3 critical sections). ✅ 2 unit tests; 277 backend tests pass.
      FOLLOW-UP (smaller, deferred): replace Apple-specific segment regex in
      `filing_parser.py:754` with XBRL-derived segments.
- [x] **S4 — Semantic quality gate + honest degradation.** Backend: `assess_quality` verdict
      (coverage + XBRL numeric grounding) always attached to `raw_summary.quality`; flagged
      `AI_QUALITY_GATE` skips caching "partial" summaries so the next visit regenerates.
      Frontend (flagged `NEXT_PUBLIC_ENABLE_QUALITY_BADGE`): explicit Full/Partial badge +
      stops client-side notice-stripping + regenerate CTA. ✅ 4 verdict unit tests; 281 backend
      + 30 frontend tests pass. (Targeted per-section regen loop: deferred — `_recover_missing_sections`
      already regenerates empty sections; verdict now makes degradation honest.)
- [x] **S5 — Anonymous quota.** `guest_quota.check_and_increment_guest_quota` (atomic Redis
      INCR, fails open) enforces a per-IP daily cap for guests in the stream endpoint, only when
      actually generating (cached hits don't count) and never gating the first summary. Friendly
      429 "create a free account" when over. Behind `ENABLE_GUEST_DAILY_QUOTA` (default off),
      `GUEST_DAILY_SUMMARY_LIMIT=3`. ✅ 4 unit tests; 285 backend tests pass.

## Review log
(append outcomes per item as they ship)

---

# Homepage Redesign v2 — Execution Record (PR #241, 2026-06-11)

Spec: `tasks/homepage-redesign-v2.md`. Operator steps: `tasks/launch-runbook.md`.

- [x] **Phase 0 — Truth & Safety.** Honest social-proof claims (fabricated
      stats removed; XBRL claim softened per Codex review); hero mockup
      relabeled FY 2022 with Apple's actual filed figures; dark-on-mint
      CTA text sitewide (WCAG AA); reduced-motion guards; 🔥 aria-hidden;
      `/pricing` allowlisted + guest-safe pricing page.
- [x] **SB1 — Funnel instrumentation.** Server-side `generation_started/
      succeeded/failed/timed_out` (duration_ms, result_type,
      quality_verdict, entry_point; client distinct_id forwarded via
      `ph_id`); client-side `summary_viewed` + `example_cta_clicked`;
      entry_point attribution via `?entry=` + referrer.
- [x] **Phase 1 — Open & Index.** Duplicate WAITLIST_MODE redirect removed
      (middleware is single source; `/` prerenders statically);
      `app/robots.ts` + `app/sitemap.ts` proxying the backend sitemap
      (domain fixed, filing URLs added); homepage metadata + canonical +
      JSON-LD (Organization/WebSite/SearchAction); `/waitlist` metadata +
      example CTA; PNG og-image.
- [x] **Phase 2 — Activation-first hero.** Search focal (desktop
      autofocus); register demoted out of hero & CtaBanner; HeroMockup =
      real date-stamped AAPL FY2022 preview, clickable, server component;
      mobile ExampleSummaryCard.
- [x] **Phase 3 — Honest persuasion.** AccuracySection ("Where the numbers
      come from"); free-tier clarity line; "Real-Time XBRL" → "XBRL-
      Verified Financials".
- [x] **Ops prep.** Weekly `pregenerate_examples` Render cron;
      launch runbook with gate-flip checklist, PostHog funnel definition,
      Search Console + CWV steps.
- [ ] **Phase 4 — Measure (operator).** Gate flip, env vars, PostHog
      dashboard, 2-week baseline → A/B program. See runbook.

---

# Homepage Redesign Plan

## Status: SHIPPED (26df0ac, 2026-02-05) — SUPERSEDED by `tasks/homepage-redesign-v2.md`

> ⚠️ Do not "approve" or re-implement this plan: it shipped in full the same day
> it was written. The v2 review (branch `claude/wonderful-hawking-c3s4dl`,
> `tasks/homepage-redesign-v2.md`) re-scoped the homepage work around truth,
> reachability, activation, and measurement. v2 Phases 0–3 + SB1 shipped in
> PR #241 (2026-06-11); remaining operator steps live in
> `tasks/launch-runbook.md`.

---

## Executive Summary

Redesign the EarningsNerd homepage from a generic SaaS template into a **premium, dark-first financial platform** inspired by Stocktwits.com. The goal: make it look polished, expensive, and satisfying — like a Bloomberg-meets-modern-fintech experience that signals credibility to sophisticated investors.

---

## The Problem with the Current Design

| Issue | Impact |
|-------|--------|
| Homepage redirects to `/waitlist` — the actual homepage is never seen | Two disconnected pages, no cohesive story |
| Generic centered-text layout with basic search bar | Looks like every other SaaS template |
| No product visualization — users can't *see* what they're getting | No emotional hook, no "wow" moment |
| Header has only logo + theme toggle, no real navigation | Feels incomplete and unpolished |
| No social proof, trust signals, or credibility markers | Doesn't build confidence |
| Mint accent color is underutilized — flat and safe | Misses the opportunity for depth and energy |
| Footer is bare minimum (3 links) | Signals "early startup" not "professional platform" |
| Light/dark mode toggle adds complexity without a clear dark-first identity | Dilutes the brand presence |

---

## Design Direction: "Dark Elegance"

### Reference Analysis (Stocktwits Screenshot)

What makes it look expensive:
1. **Deep, rich dark background** — navy/indigo gradient, not flat black
2. **Oversized bold typography** — 60-72px headline with accent-colored key phrase
3. **Product mockups floating in hero** — two phone screens showing real app UI
4. **Full professional navigation** — logo, nav links, Sign Up/Log In CTAs
5. **Generous whitespace** — sections breathe, nothing feels cramped
6. **Subtle depth** — gradients, blurs, and layering create dimension
7. **One strong CTA** — "Get Started" with arrow, not competing with 5 buttons

### Our Adaptation

We keep what works (mint/emerald brand, Inter font, search-first UX) and layer on the premium treatment:

- **Dark-first hero** with a subtle radial gradient (deep slate to navy)
- **Bold headline** with the key phrase in a mint gradient
- **Product mockup** showing an actual EarningsNerd summary (not phones — a browser/dashboard mock that fits our desktop-first use case)
- **Professional header** with real navigation and dual CTAs
- **Social proof strip** under the hero
- **Visual feature sections** with icons and subtle animations
- **Multi-column footer** that signals maturity

---

## Section-by-Section Redesign

### 1. Header (Complete Overhaul)

**Current:** Logo icon + "EarningsNerd" text + theme toggle
**New:**

```
[Logo+Name]  [Trending] [Earnings] [How It Works] [Pricing]     [Log In]  [Get Started →]
```

- Sticky with backdrop-blur (keep this — it's good)
- Left: Logo icon + "EarningsNerd" wordmark
- Center: Navigation links (4-5 items)
- Right: "Log In" (ghost button) + "Get Started" (solid mint button)
- Remove theme toggle from header — commit to dark-first for the homepage
- Subtle bottom border with mint gradient accent line

**Files to modify:** `components/Header.tsx`
**New files:** `components/NavLink.tsx` (optional)

---

### 2. Hero Section (Complete Overhaul)

**Current:** Centered heading + subtext + search bar
**New:** Split layout — copy on left, product visual on right

```
LEFT (55%)                                RIGHT (45%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The #1 Platform for                       ┌──────────────────┐
  SEC Filing                              │  [Browser mockup  │
  Analysis                                │   showing actual  │
                                          │   EarningsNerd    │
AI-powered summaries that turn            │   summary page    │
100-page filings into 5-minute reads.     │   with charts,    │
                                          │   metrics, and    │
[Search any company...]                   │   sections]       │
                                          └──────────────────┘
AAPL  NVDA  TSLA  MSFT  META  GOOGL
```

- **Background:** Full-bleed dark gradient, using the `hero-dark` definition from the Tailwind config.
- **Headline:** 56-72px bold, "SEC Filing Analysis" in mint gradient text
- **Subheadline:** 18-20px, muted gray, one compelling sentence
- **Search bar:** Elevated with glow effect, glass-morphism border
- **Quick access tickers:** Below search, pill chips with hover lift
- **Product mockup:** Angled browser frame showing real summary UI with subtle float animation
- **Subtle ambient glow:** Radial mint/indigo gradient blob behind the mockup

**Files to modify:** `app/page.tsx`, `components/CompanySearch.tsx` (styling only), `components/QuickAccessBar.tsx` (styling only)
**New files:** `components/HeroMockup.tsx` (product screenshot component)

---

### 3. Social Proof Strip (New Section)

**Current:** Does not exist
**New:** Horizontal strip below hero

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Trusted by investors analyzing    500+    10,000+     SEC
  filings from these exchanges:    companies  filings   EDGAR
                                   covered   analyzed   verified
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

- Muted background (slightly lighter than hero)
- Animated count-up numbers
- "Powered by SEC EDGAR" badge for trust
- Subtle border-top and border-bottom

**New files:** `components/SocialProofStrip.tsx`

---

### 4. Hot Filings Section (Visual Refresh)

**Current:** Card list with buzz scores — functional but flat
**New:** Same data, elevated presentation

- Dark card backgrounds with subtle border glow on hover
- Buzz score as a visual bar/meter instead of just a number
- Company logos/icons where available
- "View Summary →" CTA on each card
- Section header with fire emoji + "Trending Now" label
- Limit to 4 cards in a 2x2 grid (cleaner than 5 in a list)

**Files to modify:** `components/HotFilings.tsx` (styling overhaul)

---

### 5. "How It Works" Section (New Design)

**Current:** Exists on waitlist page, not on homepage
**New:** Visual 3-step process with icons

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  🔍 Search  │ →  │  📄 Select  │ →  │  ⚡ Analyze │
│             │    │             │    │             │
│ Find any    │    │ Pick a 10-K │    │ Get AI      │
│ company     │    │ or 10-Q     │    │ insights    │
└─────────────┘    └─────────────┘    └─────────────┘
```

- Three large cards with connecting arrows/lines
- Each card has an icon, title, and one-line description
- Subtle number indicator (01, 02, 03)
- Cards have glass-morphism effect on dark background

**New files:** `components/HowItWorks.tsx`

---

### 6. Feature Showcase (New Section)

**Current:** Feature cards exist on waitlist but are text-only
**New:** Visual feature grid with icons and mini-illustrations

Four features in a 2x2 grid:
1. **AI-Powered Summaries** — Brain/sparkle icon, "100-page filings → 5-minute reads"
2. **Real-Time XBRL Data** — Chart icon, "Financial metrics pulled directly from XBRL tags"
3. **Risk Factor Analysis** — Shield icon, "Track new and evolving risk disclosures"
4. **Filing Comparison** — Columns icon, "Compare filings side-by-side across periods"

- Each card: icon + heading + 1-sentence description
- Hover state: subtle lift + border glow
- Dark card backgrounds with mint accent on icons

**New files:** `components/FeatureShowcase.tsx`

---

### 7. Market Movers / Trending Tickers (Keep + Polish)

**Current:** Horizontal scroll cards — already decent
**New:** Same concept, polished presentation

- Slightly larger cards with more breathing room
- Subtle gradient backgrounds based on positive/negative change
- Keep "Data from Stocktwits" attribution (required — verify contractual obligations before any removal)
- Add a "View All →" link

**Files to modify:** `components/TrendingTickers.tsx` (styling refinements)

---

### 8. CTA Section (New — Before Footer)

**Current:** No final CTA
**New:** Full-width banner with gradient background

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Ready to decode your next filing?

  [Get Started Free →]
  or see an example
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

- Gradient background (mint-900 to slate-900)
- Large headline with one dominant primary CTA
- "Get Started Free" as the primary button (solid mint, larger)
- "See an Example" as a secondary text link (ghost/underline style, not a competing button)
- Subtle radial glow behind the text

**New files:** `components/CtaBanner.tsx`

---

### 9. Footer (Complete Overhaul)

**Current:** Single row with copyright + 3 links
**New:** Multi-column professional footer

```
┌────────────────────────────────────────────────────────────┐
│  [Logo]                  Product        Resources    Legal │
│  EarningsNerd            Pricing        Blog         Privacy │
│  AI-powered SEC          Features       Help Center  Terms │
│  filing analysis         Hot Filings    Contact      Security │
│                          Trending       API Docs            │
│                                                             │
│  © 2026 EarningsNerd     [Twitter] [LinkedIn] [GitHub]     │
└────────────────────────────────────────────────────────────┘
```

- Dark background, slightly different shade from main content
- Logo + tagline on left
- 3-4 link columns
- Social icons
- Bottom bar with copyright

**Files to modify:** `components/Footer.tsx`

---

## Color & Typography Updates

### Color Palette Refinements

| Token | Current | New | Why |
|-------|---------|-----|-----|
| Hero background | `#111827` (gray-900) | Gradient: `#0B1120` → `#111827` → `#1a1147` | Depth and richness |
| Card backgrounds | `white/5` | `#0f172a` with `border-white/[0.06]` | Glass-morphism feel |
| Mint accent | `#10B981` | Keep, but add gradient usage: `#10B981` → `#06b6d4` (mint to cyan) | More energy |
| Text muted | `#9CA3AF` (gray-400) | `#94a3b8` (slate-400) | Warmer, more refined |
| Glow effects | None | `rgba(16, 185, 129, 0.15)` radial | Ambient energy |

### Typography Scale

| Element | Current | New |
|---------|---------|-----|
| Hero headline | `text-4xl sm:text-5xl md:text-6xl` | `text-5xl sm:text-6xl lg:text-7xl font-extrabold` |
| Hero subhead | `text-lg` | `text-xl text-slate-400 max-w-lg` |
| Section headings | `text-xl font-bold` | `text-3xl font-bold tracking-tight` |
| Body text | `text-sm` | `text-base` (slightly larger for readability) |

### New Tailwind Config Additions

```javascript
// Add to theme.extend
backgroundImage: {
  'hero-gradient': 'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(16, 185, 129, 0.15), transparent)',
  'hero-dark': 'linear-gradient(to bottom right, #0B1120, #111827, #1a1147)',
},
boxShadow: {
  'glow-mint': '0 0 40px -10px rgba(16, 185, 129, 0.3)',
  'glow-mint-sm': '0 0 20px -5px rgba(16, 185, 129, 0.2)',
},
```

---

## Implementation Plan

### Phase 1: Foundation (Design System Updates)
- [ ] Update `tailwind.config.js` with new tokens, gradients, shadows
- [ ] Update `globals.css` with new animations and utility classes
- [ ] Create `HeroMockup.tsx` — static product screenshot component
- [ ] Commit to dark-first homepage (remove theme toggle from homepage header)

### Phase 2: Header & Hero
- [ ] Redesign `Header.tsx` — add navigation links, dual CTAs, gradient accent line
- [ ] Redesign hero section in `page.tsx` — split layout, bold typography, search with glow
- [ ] Restyle `CompanySearch.tsx` — glass-morphism input with ambient glow
- [ ] Restyle `QuickAccessBar.tsx` — refined pill chips for dark background

### Phase 3: New Sections
- [ ] Build `SocialProofStrip.tsx` — trust metrics with animated counters
- [ ] Build `HowItWorks.tsx` — 3-step visual process
- [ ] Build `FeatureShowcase.tsx` — 2x2 feature grid with icons
- [ ] Build `CtaBanner.tsx` — final CTA section before footer

### Phase 4: Existing Section Polish
- [ ] Restyle `HotFilings.tsx` — elevated dark cards with glow borders
- [ ] Restyle `TrendingTickers.tsx` — larger cards, gradient accents
- [ ] Redesign `Footer.tsx` — multi-column professional layout

### Phase 5: Integration & Assembly
- [ ] Assemble all sections in `page.tsx` with proper spacing and flow
- [ ] Remove waitlist redirect (or make it configurable with the new homepage as default)
- [ ] Add scroll-triggered fade-in animations for each section
- [ ] Test responsive breakpoints (mobile, tablet, desktop)
- [ ] Performance audit — ensure no layout shift, lazy load mockup image

---

## Agent Assignments

| Agent | Role in This Project |
|-------|---------------------|
| **UI Designer** | Design system tokens, component specs, visual QA |
| **Brand Guardian** | Approve color/typography changes, ensure brand consistency |
| **Whimsy Injector** | Micro-interactions, hover states, scroll animations |
| **Content Writer** | Homepage copy — headline, subheadline, feature descriptions |
| **Accessibility Champion** | WCAG audit after implementation |
| **Frontend Developer** | Component implementation and assembly |
| **Growth Hacker** | CTA placement, conversion optimization review |
| **SEO Optimizer** | Meta tags, semantic HTML, structured data |
| **Performance Tester** | Lighthouse audit, Core Web Vitals check |

---

## Key Design Principles

1. **Dark = Premium.** The dark background isn't a theme toggle — it's the identity. Like Bloomberg, Robinhood, or Stocktwits. Finance professionals expect dark interfaces.

2. **Show, Don't Tell.** The product mockup in the hero does more selling than any paragraph of text. Investors want to see the output before they commit.

3. **Generous Space.** Every element should breathe. Padding of `py-20` to `py-28` between sections. Nothing should feel crowded.

4. **Subtle Motion.** Scroll-triggered fade-ins, hover glows, floating mockup. Motion adds polish but must respect `prefers-reduced-motion`.

5. **One Clear Action.** Every section should drive toward one thing: getting the user to search a company or sign up. No competing CTAs.

6. **Trust Through Data.** "500+ companies", "SEC EDGAR verified", "10,000+ filings analyzed" — concrete numbers build confidence.

---

## Success Criteria

- [ ] First impression: "This looks like a real platform, not a side project"
- [ ] Lighthouse Performance score > 90
- [ ] Lighthouse Accessibility score > 95
- [ ] Core Web Vitals: LCP < 2.5s, CLS < 0.1, INP < 200ms
- [ ] Mobile-first responsive design works at 375px+
- [ ] No layout shift on load
- [ ] All interactive elements have focus indicators (WCAG AA)

---

## Open Questions for You

1. **Waitlist vs. Live:** Should the homepage show the waitlist form inline, or should we go full "live product" mode with Log In / Sign Up?
2. **Product Mockup:** Do you have a screenshot of the summary page we can use? Or should I generate a static HTML mockup?
3. **Copy Tone:** The Stocktwits copy is bold and confident ("The Leading Social Platform"). Do you want similar boldness ("The #1 Platform for SEC Filing Analysis") or slightly more understated?
4. **Navigation Links:** Which pages are live and should appear in the nav? (Pricing, Trending, Hot Filings, etc.)
5. **Social Links:** Twitter/X, LinkedIn, GitHub — which should appear in the footer?

---

*Plan created: 2026-02-05*
*Awaiting approval before implementation begins.*

---
---

# Activation Gap Analysis — Investigation Plan & Progress (2026-06-09)

Diagnostic review (read-only): prioritized gap analysis + roadmap for activation
(anonymous visitor → first successful, high-quality summary). No application
code changes; deliverable is `tasks/activation-gap-analysis.md`.

## Phase 1 — Map reality
- [x] Confirm CLAUDE.md against actual code (entry points, routes, services)
- [x] Identify real entry points for a new visitor (landing, middleware, quick-access tickers)

## Phase 2 — Trace activation funnel (subagent: frontend)
- [x] Landing page → search → company page → filing page → stream → render
- [x] Auth/waitlist gates, error/empty/slow states, clicks and waits per step
- [x] SSE consumption, timeouts, retry behavior, progress UX

## Phase 3 — Trace backend pipeline (subagent: backend)
- [x] companies/filings/summaries routers; anonymous gating truth table
- [x] Generation orchestration steps, timeouts, fallbacks, failure modes
- [x] Rate limiting, circuit breaker, caching layers

## Phase 4 — AI quality audit (subagent: AI)
- [x] openai_service prompt construction, model params, retries, JSON repair
- [x] Prompts vs schema conflict; section extraction; XBRL grounding
- [x] Fallback/recovery machinery and silent-degradation paths
- [x] Spot-verify load-bearing claims directly (middleware.ts:40, summaries.py:44/47, openai_service.py:1922-1959, prompts/10k-analyst-agent.md:9-13)

## Phase 5 — Synthesize & deliver
- [x] Score gaps (Impact × Confidence ÷ Effort), split Quick Wins vs Strategic Bets
- [x] Write `tasks/activation-gap-analysis.md` (7 sections per spec)
- [x] Chat summary
- [x] Commit & push to `claude/earningsnerd-activation-diagnostic-qscmnn`

## Review
Report delivered at `tasks/activation-gap-analysis.md`. Top findings: waitlist
middleware gate can block the entire funnel; no zero-wait demo summary path;
prompt/JSON-schema conflict with no API-level structured-output enforcement;
brittle regex extraction + 8s XBRL budget driving "hit and miss" quality;
placeholder/fallback content indistinguishable from real content (silent
degradation). See report for full evidence and sequencing. Note: this section
relates to the earlier homepage-redesign plan above — that plan's "remove
waitlist redirect" item aligns with this report's #1 quick win.
