# Voice and style

How EarningsNerd copy is written. This applies to every user-facing English string: page
copy, headings, buttons and CTAs, empty/error/loading states, tooltips, form helper text,
toasts, meta titles and descriptions. The product is openly AI-powered; say so plainly.
The copy itself should sound like a sharp human who knows the product.

Reference texture: harvey.ai. Short, specific, confident. Headlines of a few words, subheads
of one plain sentence, claims backed by concrete detail, no throat-clearing.

## The four rules

1. **Short.** Headlines a few words. One idea per sentence. If you wouldn't say it aloud,
   cut it.
2. **Specific over abstract.** Name what the product does and who it's for. Prefer a real
   detail or number ("10-K and 10-Q summaries", "5 summaries a month") to a vague benefit
   ("actionable insights").
3. **Confident and plain.** Lead with the user's outcome. State the AI plainly without
   over-explaining it. Drop the hype. No exclamation marks.
4. **Restraint over decoration.** Cut adjectives that don't earn their place and any
   sentence that only exists to set up the next one. No emoji in headings or banners.

Before → after, to calibrate:

- "Unlock the power of AI to seamlessly analyze filings — effortlessly."
  → "Read any 10-K in minutes, not hours."
- "Our platform is designed to help you make smarter, faster, more confident investment
  decisions." → "See what changed in a company's filings, and why it matters."
- "In today's fast-paced markets, staying ahead has never been more important."
  → Cut it. Open with the point.

## Dashes

- **No em-dashes (—) in copy.** Restructure the sentence instead of swapping in another
  dash: split it into two sentences, use a colon, or just cut the aside.
- **Hyphens stay** in compound terms: 10-K, real-time, cold-start, day-of.
- **En-dashes (–) stay** in genuine numeric or date ranges: Q1–Q4, 30–60s, FY2019–FY2024.
- **The bare `—` null-value token stays.** Tables and detail rows render `—` for missing
  data (see `MISSING_TOKENS` in `frontend/lib/format.ts`). That is a data convention, not
  prose. It is the only sanctioned em-dash and the CI gate
  (`frontend/tests/unit/no-em-dash-copy.spec.ts`) allowlists exactly the bare `'—'` literal.

## House conventions

- Meta titles: `Page name | EarningsNerd`.
- Compact label separators use the middot: `AAPL · 10-K`, `Free for beta members · no card
  required`. Never an em-dash.
- Card and section titles are sentence case (also a DESIGN_SYSTEM.md rule).
- "AI-powered", lowercase p, except at the start of a sentence or in title-case page titles.
- Ellipsis character `…` on loading states ("Signing in…") is fine.
- Buzzwords to avoid: unlock, seamless(ly), empower, effortless(ly), supercharge, transform,
  actionable insights, decision-ready, game-changing, "in today's fast-paced world".
  Say what the thing does instead.

## Claims

- Preserve every factual and product claim exactly: prices, plan limits, coverage, retention
  periods, response times, security certifications. Never invent features, capabilities,
  metrics, pricing, or testimonials.
- If a claim can't be confirmed, leave it unchanged and flag it. Never restate an unverified
  claim more confidently.
- Legal body text (privacy, terms) is not restyled in copy passes. Legal wording changes go
  through their own review and bump `lib/legalDates.ts`.

## Copy that is also code

Before editing a string, check what it's wired to:

- Strings compared in logic (the `delete my account` confirm phrase, the pricing
  `Current Plan` CTA) change only with their comparison site, in the same edit.
- Object keys (OAuth error codes), analytics event names, storage keys, and backend status
  values are not copy.
- Shared constants (`AiDisclaimer.SEC_EDGAR_NOT_ADVICE`) are edited in place, never forked.
- Copy duplicated across frontend and backend (the beta invite message in
  `features/admin/lib/shareLinks.ts` and `backend/app/services/email_service.py`) must be
  changed on both sides in the same PR.
- Component tests assert exact copy. Any copy change runs `npx vitest run` before push and
  updates the coupled assertion in the same PR (see `lessons/test-vitest-for-copy-changes.md`).
