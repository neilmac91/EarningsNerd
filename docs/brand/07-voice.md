# The voice (2026-10-11)

Phase 7 of the brand studio brief. The guide itself is `docs/voice-and-style.md` (rewritten: the
reference texture is now the brand's own, with the tone rules, the humour floor, a do-and-don't
table taken from the live site, five headlines and the tagline). This page records what was wired
into the product, so the handoff can point at each site. Every factual claim (prices, limits,
coverage, security statements) is unchanged.

## The lines

- **Tagline:** "The summary that shows its work." (footer, auth pane, social card, metadata,
  business card, merch.)
- **Hero headline:** variant A survives as served ("Read the filing faster. Keep the source in
  view."), now with the mark under its accent phrase; B and C of the copy test become "Read it
  faster. Check it anyway." and "The summary that shows its work."
  (`frontend/features/marketing/lib/headline.ts`).
- **Subhead:** "AI summaries of 10-Ks and 10-Qs for investors who still check the source. Each
  figure points to the XBRL fact or the passage it came from, or says that it could not."

## Microcopy, wired

| Surface | File | Before | After |
|---|---|---|---|
| Primary and secondary buttons | unchanged | "See a live example", "Request an invite", "Read the full example summary" | same: they were already plain |
| Access line | `frontend/features/marketing/lib/access.ts` | "Private beta · request an invite" | same |
| Claims strip | `MeasuredClaims.tsx` | "9-part format / Streams / XBRL + text / 10-K · 10-Q" | "Figures / Quotes / Nine parts / SEC EDGAR", each with the behaviour the product performs |
| Trust strip | `TrustStrip.tsx` | "Figures cite their XBRL fact or filing passage where a match is found" | "One summary per filing, generated once and shared" (the match behaviour is stated once, above) |
| Evidence section | `EvidenceSection.tsx` | "Where the numbers come from" + three hedged sentences | "Figures with their receipts." + the behaviour, once |
| Contents section | `SummaryContents.tsx` | "What a summary contains" + nine stale titles | "Nine parts, in the order you would read them." + the schema's nine |
| How it works | `HowItWorks.tsx` | "Search supported SEC filers…", "Select a supported annual or quarterly report…", "The AI analyzes selected filing sections and available XBRL data…" | "Any company that files with the SEC…", "A 10-K, 10-Q or 20-F. We fetch it from SEC EDGAR.", "Nine parts, written by the AI from the filing's text and XBRL…" |
| Pro section | `ProDepth.tsx` | "What Pro adds" / "Three ways to work with filing data beyond one summary." / "Answers can include source chips… whether a source match was found or the item is only cited" | "More ways to read one filing." / "Ask it a question, read its periods side by side, see what changed since the last one." / "The answer cites the XBRL figures and passages it used, and each chip says whether we matched the source or only cited it." |
| Trace demo | `TraceToSourceDemo.tsx` | "Where a source chip is available, hover or tap it…" | "Hover or tap the chip to see the section, the passage in the filing's own words, and a link into SEC EDGAR." |
| Pricing page | `frontend/app/pricing/page.tsx` | "Choose the plan that fits your workflow"; "For trying out EarningsNerd"; "Basic AI summaries"; "For professionals who need unlimited access"; a guest's "Create free account" under invite-only | the landing's pricing sentence; "For reading a few filings a month"; "The same summaries Pro reads"; "For reading every filing you follow"; the guest button follows the one access decision (`ACCESS_COPY`, read from `/api/auth/registration` through `getRegistrationConfig`) |
| Auth pane | `AuthShell.tsx` | "Explore SEC filings with cited summaries." + grey bars + FY2023 | the tagline with the mark + the FY2025 opening sentence + "$416.2B ▲ +6.4% YoY" |
| Waitlist page | `frontend/app/waitlist/page.tsx`, `WaitlistForm.tsx`, `WaitlistCounter.tsx` | "the signal without the slog", "Speed matters. Markets move fast…", "Act with clarity", "Risk factor signals… before the market reacts", the share text's "for retail investors", "Join 0+ others" | the hero subhead; "Filings are long." / "Checking takes an afternoon." / "You still read the filing."; "Check what you like"; "Risks in the filing's own words"; "for investors who still check the source"; the counter names the list below 25 signups (`COUNT_FLOOR`) |
| Waitlist headline (Phase 9, fix 1) | `frontend/app/waitlist/page.tsx` | "Read a 10-K in 5 minutes, not 5 hours." with "5 minutes" in sage, and the same line as the `<title>` | "The 10-K, read for you, with receipts." with the mark under "with receipts" (headline 4 of the five); the `<title>` follows. Sage no longer colours a number and no speed is claimed |
| Consent bar (Phase 9, fix 2) | `frontend/components/CookieConsent.tsx` | "We value your privacy" / "We use cookies to enhance your experience and analyze site usage. You can choose which cookies to accept."; the dialog opened with "provide personalized content" | "Cookies on this site" / "Essential cookies keep you signed in. Analytics and session recording stay off until you allow them." (true of `lib/analytics.ts`, which gates every event on consent); the dialog intro names the three categories it offers and nothing else |
| Empty states | `YourCompanies.tsx`, `dashboard/watchlist/page.tsx` | "No companies yet", "No watchlist companies yet" | unchanged: plain and true already |
| Generation error | `StreamingSummaryDisplay.tsx` | "Generation timed out. Please retry to continue." | "It timed out before the summary finished. Retry to pick it up again." (the heading "Generation interrupted" stays: five specs name it, and it is plain) |
| Stalled line | same | "Taking longer than usual. This looks like a complex filing; still working on it." | "Taking longer than usual. A long filing; still reading." |
| Loading quips | same, `WHIMSY_MESSAGES` | "Scanning 400 pages of footnotes so you don't have to…", "Cross-referencing the numbers with the narrative…", "Decoding the tone of the outlook…", signed "EarningsNerd analyst" | "Reading the footnotes so you can go straight to the ones that matter…", "Checking the figures against the company's XBRL…", "Finding where the filing says that…", "Reading the size-8 fine print…", "Reviewing the line called Other…", "Translating management's phrasing into plain English…", signed "Reading the filing" |
| Monthly-limit card | same | "You've hit this month's free limit" / "Your free summaries reset next month. Or go unlimited now with Pro." | unchanged: a person wrote it, and the moment costs the reader (no humour there) |
| 404 | `frontend/app/not-found.tsx` | "We couldn't find this page. The link may be mistyped or out of date. Search for a company from the homepage, or open your dashboard." | "We looked. The link is mistyped or out of date. Start from the homepage search, or open your dashboard." (the h1 "Page not found" stays: two e2e specs name it) |
| Footer | `frontend/components/Footer.tsx` | "Explore SEC filings with AI-assisted summaries." | "The summary that shows its work." |
| Metadata | `frontend/app/layout.tsx`, `page.tsx`, `manifest.ts` | "AI-assisted summaries of SEC filings, with financials, risks, trends, and source context…", "…with source labels where matches are found." | "The summary that shows its work. AI summaries of 10-Ks and 10-Qs, each figure traced to the filing's own XBRL or text…" |
| Email subjects | `backend/app/services/email_service.py:151,170` | "You're on the EarningsNerd waitlist! 🎉", "You just moved up the EarningsNerd waitlist!" | "You're on the EarningsNerd waitlist", "You moved up the EarningsNerd waitlist" (bodies de-exclaimed to match; "unlock" removed from the verification email) |
| Export mastheads | `export_service.py:40,117`, `excel_export_service.py:168`, `routers/contact.py:195` | "EarningsNerd — AI-Powered SEC Filing Analysis" | "EarningsNerd · AI summaries of SEC filings" (`tests/unit/test_export_service.py` updated with it) |

Coupled specs updated in the same change: `pro-depth.spec.tsx`, `hero-example-surface.spec.tsx`,
`waitlist-example.spec.tsx`, `landing-tweaks.spec.tsx`, `landing-sections-mounted.spec.ts`,
`PricingPage.spec.tsx` (with a new case: a guest under the invite gate sees "Request an invite"),
`backend/tests/unit/test_export_service.py`; in Phase 9, `CookieConsent.spec.tsx` (the new heading) and
`FinancialMetricsCards.spec.tsx` (a new case: a per-share "$7.46" keeps its cents in both layouts).
