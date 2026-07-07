# Copy voice pass — change summary (2026-07-07)

Site-wide rewrite of user-facing English copy into the voice defined in
`docs/voice-and-style.md` (short, specific, confident, plain; no em-dashes in copy).
Branch: `claude/earningsnerd-copy-voice-rr0pvy`. Roughly 80 user-visible em-dash sites
removed across public, app, and admin surfaces; every factual claim preserved except one
deliberate fix approved by Neil (coverage claim, below). New CI gate:
`frontend/tests/unit/no-em-dash-copy.spec.ts` keeps em-dashes out of copy permanently.

## Highest-visibility before → after

| Where | Before | After |
|---|---|---|
| Site title (root) | EarningsNerd - AI-Powered SEC Filing Analysis | EarningsNerd \| AI-powered SEC filing analysis |
| Root meta description | Transform dense SEC filings into clear, actionable insights using AI. … instantly understand performance, risks, and trends. | AI summaries of SEC filings. Search any public company and read its 10-K or 10-Q in minutes: financials, risks, and trends, straight from SEC EDGAR. |
| Home meta title | EarningsNerd — Understand any SEC filing in minutes | EarningsNerd \| Understand any SEC filing in minutes |
| Hero subhead | AI-powered summaries that turn dense, 100-page SEC filings into clear, decision-ready insights. Financials, risks, and trends — all in one place. | AI summaries that turn 100-page SEC filings into a clear five-minute read. Financials, risks, and trends, all in one place. |
| Hero helper | Your first summary is free — no signup needed. | Your first summary is free. No signup needed. |
| Footer tagline | AI-powered SEC filing analysis. Turn dense filings into clear, decision-ready insights. | AI-powered SEC filing analysis. Read any 10-K or 10-Q in minutes. |
| How-it-works coverage step | Find any public company by name or ticker symbol. We cover 500+ companies on SEC EDGAR. | Find any public company by name or ticker. We cover every company that files with the SEC. |
| How-it-works step 3 | Get instant insights / …delivers a structured summary — financials, risks, and trends. | Get the summary / …writes a structured summary: financials, risks, and trends. |
| QuickAccessBar | Popular companies — click to explore | Popular companies |
| CTA banner | Stop spending hours on filings. Get the insights that matter in minutes. | Stop spending hours on filings. Read what matters in minutes. |
| Waitlist hero subhead | EarningsNerd turns dense SEC filings into clear, decision-ready insights on business performance… | EarningsNerd turns SEC filings into clear summaries of business performance… |
| Waitlist trust card | Momentum is real / Join investors who want faster, clearer insights. | A numbered spot / Join the list and get a position. Each referral moves you up 5 spots. |
| Pricing beta banner | 🎉 You're a beta member — Pro is on us. (CTA: Claim Pro — Free) | You're a beta member. Pro is on us. (CTA: Claim Pro) |
| Register subhead | 5 free AI summaries a month — no credit card required. | 5 free AI summaries a month. No credit card required. |
| Upgrade modal | Unlock unlimited summaries, real-time filing alerts, 8-K coverage… | Pro includes unlimited summaries, real-time filing alerts, 8-K coverage… |
| Generation loaders | 9 rotating quips incl. "Turning caffeine into investment insights…", "Looking for hidden gems in the appendix…" | Trimmed to the 6 product-true ones ("Scanning 400 pages of footnotes so you don't have to…", "Translating corporate-speak into plain English…", …) |
| Watchlist next-steps | Flag this filing for regeneration before distributing to clients. / …exporting a briefing pack for your next meeting. / Ingest filings for this company… | This summary needs regenerating. Open the filing and run it again. / Summary is current. Nothing to do here. / Open the company page to load its filings from SEC EDGAR. |
| Crash pages | We apologize for the inconvenience. An unexpected error has occurred. / …Our team has been notified and is working to fix it. | The error has been logged. Try again, or reload the page. / The error has been reported and we'll look into it. |

Plus, pattern-wide: em-dash asides restructured into sentences or colons; compact-label
em-dashes moved to the house middot (`AAPL · figures as reported in this 10-K`,
`Sources · sample data`); meta titles standardized on `Page | EarningsNerd`; success
states de-exclaimed ("Password updated!", "Email verified!", "Message Sent!", waitlist
"You're on the waitlist!"); emoji removed from headings and banners (📄 📅 🎉; feedback
type chips kept); card/section titles sentence-cased per DESIGN_SYSTEM.

## Copy that is also code (handled in lockstep)

- Coupled specs updated with their copy: `QuickAccessBar`, `fundamentals-trend-chart`,
  `narrative-pane`, `additional-info-accordions`, `analysis-teaser`.
- The `delete my account` confirm phrase, pricing `Current Plan` CTA, OAuth error keys,
  status keys, storage keys, and analytics values are untouched.
- The beta invite message was reworded identically on both sides of its duplication:
  `frontend/features/admin/lib/shareLinks.ts` and `backend/app/services/email_service.py`.
- The earnings-alerts cap 403 detail (surfaces verbatim in the AlertBell popover) was
  de-dashed in `backend/app/routers/watchlist.py` and its frontend fixture mirror.

## Claim changes (all others preserved verbatim)

- **Coverage claim (Neil-approved):** "We cover 500+ companies on SEC EDGAR" contradicted
  the social-proof strip's "Every SEC-registered company". Neil confirmed EDGAR-wide
  coverage is accurate; the step now reads "We cover every company that files with the SEC."
- "…generate an AI summary **instantly**" (ticker filings view) dropped "instantly";
  the product's own progress card says "Usually 30–60s".

## Flagged for follow-up (left as-is)

1. **Apple example figures differ across surfaces:** the hero example card shows FY2022
   figures ($394.3B revenue / $99.8B net income / $6.11 EPS) while the auth-page brand
   pane shows FY2023 ($383.3B, +2.8% YoY). Both are real filings, but they read
   inconsistent side by side and the FY2022 example is getting stale.
2. **`frontend/features/analysis/demo/demo-analysis.json`** (free-tier Multi-Period
   sample) has 4 em-dashes in its narrative. It's cached real pipeline output with
   aligned citation markers; regenerate it via the pipeline rather than hand-editing.
3. **Backend email templates** (`email_service.py`) still carry em-dashes outside the
   invite line (security-notice email, digest rows) plus marketing-toned subjects with
   exclamation marks. User-facing but not site copy; needs its own pass.
4. **AI-generated output** (summaries, copilot answers, analysis narratives) can still
   contain em-dashes; controlling that means prompt changes, which are eval-gated
   (`backend/evals/RUNBOOK.md`). Separate pass.
5. **Security page** hype-adjacent lines left untouched to preserve claims:
   "industry-standard security measures", "enterprise-grade cloud infrastructure with
   99.9% uptime guarantees", "the highest level of payment security certification".
   The 99.9% figure's attribution (GCP SLA?) is Neil's to confirm before rewording.
6. **Privacy/Terms body text** untouched by design (legal wording change needs its own
   review and a `legalDates` bump). Only the terms meta description changed.
7. **Footer links** "Hot Filings" and "Trending" point at homepage anchors of sections
   that no longer render (flag-hidden/replaced). Structural cleanup, not copy.
8. **Social share texts** (waitlist Twitter/LinkedIn copy) and **CookieConsent** left
   as-is: platform-native voice and conventional consent language respectively.
