# EarningsNerd iPhone App — Claude Design Prompt (Fable 5)

A ready-to-paste brief for designing the EarningsNerd iOS app in Claude Design with the
Fable 5 model. It extends the web design system (`frontend/DESIGN_SYSTEM.md` +
`frontend/tailwind.config.js`) to iOS rather than transplanting it, and bakes in Apple's
Human Interface Guidelines (Liquid Glass era) so the result is set up for App Store success.

**How to use**

1. Open Claude Design, select **Fable 5**, and paste everything below the divider as one message.
2. Strongly recommended: attach 4–6 screenshots of the live web app (Home, a company page, a
   filing summary, the copilot thread — in both light and dark) as visual grounding. The prompt
   carries every token, but reference pixels remove ambiguity about how the tokens compose.
3. Fable 5 works best with the full spec in one well-specified turn — send the whole brief at
   once rather than drip-feeding sections. If you want to explore, ask for the three app-icon
   directions first (§9) and continue from the one you pick.

**Why the prompt is shaped this way** (so future edits keep the properties that matter)

- **Concrete specs, not adjectives.** Fable-class models follow explicit hex/typeface/radius
  constraints precisely; vague direction ("keep it clean") shifts them to a generic house style.
  Every identity decision is stated as an exact value.
- **Goal + constraints, not step-by-step procedure.** Over-prescriptive prompts measurably
  degrade Fable 5 output. The brief defines what must be true and where the model has latitude,
  and lets it do the design work.
- **The reason, not only the request.** Fable 5 performs better when it knows who the work is
  for and what it enables — hence the product context up front.
- **A precedence rule for conflicts** (HIG vs. brand) so the model decides instead of hedging.

---

<!-- ═══════════════ COPY EVERYTHING BELOW THIS LINE INTO CLAUDE DESIGN ═══════════════ -->

# Design the EarningsNerd iPhone app

## 1. Mission and context

You are the founding product designer for the iPhone app of **EarningsNerd**
(earningsnerd.io), an AI-powered SEC-filing analysis platform. It turns dense 10-Ks and
10-Qs into clear, evidence-linked insight for individual investors — people who take
investing seriously but don't have a Bloomberg terminal. The product's personality is
**calm, precise, and evidence-first**: every AI claim links back to the filing's own words,
numbers are treated as sacred, and nothing is hyped. The web app has a mature, hard-won
design system; the iPhone app is the product's second surface.

Your goal: an iPhone app that passes two tests at once —

1. **Same product.** Held next to earningsnerd.io, it is unmistakably the same brand:
   the warm cream, the single sage accent, the monospaced numbers, the quiet confidence.
2. **Genuinely native.** Someone who has never seen the web app experiences a first-class
   iOS app — designed for one hand, short sessions, notifications, and the moment a filing
   drops — never a web port.

The deliverable is a design an iOS team can build from without re-litigating the design
system. Design for iPhone at **393×852 pt** (iPhone 16/17 class), current iOS design
language (Liquid Glass), portrait-first.

## 2. What the app does

**Core loop:** follow companies → get alerted when they file → read an AI summary in
minutes instead of the 200-page original → interrogate the filing with grounded Q&A →
verify any claim against the source text.

Surfaces to design (the web app already has all of these; the iPhone app is v1-complete
with them):

- **Home** — personalized dashboard feed ("what changed" headlines for watched companies),
  hot filings, trending tickers.
- **Search** — companies by name/ticker, plus SEC full-text search across filings.
- **Company page** — profile, filings list (10-K/10-Q/8-K), fundamentals charts
  (revenue, income, EPS, cash-flow trends), Form 4 insider activity, peer comparison.
- **Filing summary** — the hero surface. AI generation is a streaming job (typically
  30–120 s) with staged progress, then a sectioned summary (overview, financials, risks,
  guidance…) with collapsible sections and metric callouts.
- **Ask this Filing (copilot, Pro)** — chat scoped to a single filing. Answers carry
  numbered citation chips; each citation shows a verbatim excerpt, a **Verified** or
  **Cited** trust badge, and deep-links into the filing text.
- **Filing reader** — the actual filing text (Item 1A, MD&A…), long-form reading surface,
  the target of citation deep-links (arriving at a highlighted excerpt).
- **Watchlist** — followed companies with per-company alert toggles (real-time or daily
  digest).
- **Earnings calendar** — upcoming earnings for watched companies.
- **Compare / change report (Pro)** — period-over-period deltas and risk-factor diffs.
- **Auth & onboarding** — email/password, Google, **Sign in with Apple** (backend already
  supports it; App Store rules require it alongside Google).
- **Paywall / Pro upgrade** — Free tier: 5 AI summaries per month; Pro unlocks copilot,
  compare, higher limits. A reverse-trial (full Pro for N days at signup, no card) exists —
  design the moment it starts and the moment it ends.
- **Settings** — account, notification preferences (real-time vs digest, per-company),
  appearance, legal, data export/delete.

## 3. Brand DNA — non-negotiable identity tokens

These are exact values from the production design system. Treat them as law; they were
audited the hard way (contrast is measured against the warm cream, not white).

### 3.1 Color

**One brand accent: Sage. In both themes.** Sage is identity, never data: it must never
indicate price direction, and never appears inside a chart plot area. No other green, no
mint, no blue/teal/indigo as brand. No decorative gradients anywhere.

| Role | Light | Dark | Rules |
|---|---|---|---|
| Page background | `#F4F3EE` warm cream | `#0B1120` deep navy | Never stark white; never pure black. |
| Card / panel | `#FBFAF6` | `#1F2937` | Cards **lift, not tint**: lighter-than-page fill + hairline + soft shadow (light); fill-contrast + hairline, no shadow (dark). |
| Brand fill | `#4F7A63` | `#7FB295` | Fill only — never as text on cream. |
| Brand text/links (accent ink) | `#3C6650` | `#98C5AD` | The accent for text, links, active tab tint. |
| Brand pressed/active | `#345C48` | `#569272` | |
| Brand tint (soft bg) | `#ECF2EE` | `rgba(127,178,149,0.14)` | Tint/hover wash only — invisible as a card fill on cream. |
| Brand border | `#CFE0D6` | `rgba(127,178,149,0.28)` | |
| Text primary (headings AND body ink) | `#1A1A17` espresso | `#D7DADC` | One heading ink; hierarchy from size/weight, never a second color. |
| Text secondary | `#374151` | `#9CA3AF` | Muted text on dark uses **secondary** — the tertiary-dark value fails WCAG on navy. |
| Text tertiary | `#6B7280` | — (see rule) | Light-mode muted only. |
| Hairline | `#E5E7EB` | `#374151` / 10 % white | |

**Financial direction (data, never brand):**

| Signal | Text | Graphic/chip only (fails AA as text) | Dark (text-safe) | Soft tint |
|---|---|---|---|---|
| Gain | `#15803D` | `#16A34A` | `#34D399` | `#DCFCE7` / `rgba(52,211,153,0.14)` |
| Loss | `#B91C1C` | `#DC2626` | `#FB7185` | `#FEE2E2` / `rgba(251,113,133,0.14)` |
| Flat | `#6B7280` | — | `#9CA3AF` | — |

Direction is always **color + a redundant cue** (▲/▼ or explicit +/− sign) — never color
alone.

**Status:** success `#15803D`/`#22C55E` · warning `#92400E`/`#F59E0B` · error
`#B91C1C`/`#F87171` (destructive pressed `#991B1B`) · info `#2563EB`/`#60A5FA`
(in-tint label ink `#1D4ED8`). Loud status color is reserved for genuine state; progress
and step indicators use **brand sage**, not success-green — green is a terminal
confirmation only.

**Chart series — a fixed sequence, taken 1→N in order, never re-sorted** (same hexes in
both themes; each ≥3:1 on cream and navy): 1 `#3E8E84` teal · 2 `#B8812F` honey ·
3 `#5B7CC0` cornflower · 4 `#CF7159` coral · 5 `#6E7E9C` slate-blue · 6 `#8B7BC0`
periwinkle. At ≥5 series, add direct labels — color no longer carries alone. Gain/loss
never appear as series colors; sage never appears in a plot area.

**Contrast floors (audited against cream `#F4F3EE` and navy `#0B1120`, not white/black):**
text ≥ 4.5:1 in both themes (measured against the mixed tint when on a tinted ground);
non-text meaning-bearing graphics ≥ 3:1. Provide increased-contrast variants per the HIG
(darken light values, brighten dark ones) for every custom color.

### 3.2 Type — three fixed roles, translated to iOS

The web body stack is deliberately `-apple-system`-first, so on Apple hardware the web app
already renders SF Pro — **the iOS translation is native by design.** Use system fonts and
get Dynamic Type for free; do not embed Inter, Geist, or Newsreader.

| Role | Web | iPhone app |
|---|---|---|
| Headings | Inter w/ optical sizing, single weight 600 | **SF Pro, Semibold (one display weight)**, Dynamic Type styles (Large Title 34 → Headline 17). Heading ink = text primary. Hierarchy via size/weight only. |
| Body & UI | `-apple-system` → Inter | **SF Pro Text** via Dynamic Type: Body 17, Callout 16, Subheadline 15, Footnote 13, Caption 12/11. |
| Data | Geist Mono + `tabular-nums` | **SF Mono with monospaced digits** (already the web stack's Apple fallback). Mandatory for **every** money value, %, ticker symbol, XBRL figure, and verbatim filing excerpt — the "evidence register" is a core brand signature. 11 pt floor for dense numeric annotations. |
| Editorial serif | Newsreader (fallback "New York") | **New York**, in the **filing reader only** — serif marks the filing's own words. AI output is never serif; copilot answers stay body sans, excerpts stay mono. |

UPPERCASE tracked eyebrows only for tiny metric labels — never card titles (card titles are
sentence case, semibold). 12 pt UI-type floor. Support Dynamic Type fully, including AX
sizes: financial figures may reflow or compact (`$391.0B`) but must never truncate to `…`.

### 3.3 Shape, depth, motion

- **Radius scale 4 / 8 / 12 / 16 / 24 pt** for custom surfaces: buttons + inputs 12, cards
  16, chips capsule. Keep nested radii concentric with the display corners per the HIG;
  system-drawn controls (tab bar, glass groupings) keep their native shape.
- **Elevation:** light mode uses soft, small shadows (a two-layer ~1–3 pt blur at ~10 %
  ink) — never heavy drops; dark mode separates by fill + hairline with **no shadows**.
- **Motion tokens:** fast 150 ms (touch feedback) · base 200 ms (crossfades, skeleton →
  content) · slow 600 ms (entrances, draw-ins, count-up) · ambient 1800 ms (shimmer,
  pulse, citation-flash). Standard easing ≈ `cubic-bezier(0.4, 0, 0.2, 1)`; one bouncy
  spring reserved solely for the success check-pop. **Signature set (keep, nothing
  decorative beyond it):** number count-up (monospaced digits so nothing jitters),
  citation-flash on deep-link arrival, skeleton→content crossfade, sparkline draw-in,
  check-pop. Every animation has a Reduce Motion fallback: static bone, static tint, or
  instant final value.
- **New for iOS — haptics:** design a restrained haptic map (e.g. light impact on
  watchlist add, success notification when a summary completes, warning on quota hit).
  Same philosophy as motion: purposeful, never decorative.

### 3.4 Component vocabulary to carry over

Primary button: white label on `#4F7A63`, pressed `#345C48` (light); **navy-ink label on
`#7FB295`**, pressed `#569272` (dark) — white-on-`#569272` is 3.7:1 and is banned.
Secondary: panel fill + hairline; pressed state **brightens**, never dims (no opacity
presses anywhere). Ghost/tertiary: accent-ink text on transparent with tint press.
Badges: tint chips (interim-filing info chip, warning chip, beat/miss) plus a solid brand
chip for tinted grounds. Inline **Notice** (icon + title + message + action) for in-card
and form states; a standalone centered **GuidanceCard** for empty/upsell moments — never
nested inside a card. Inputs: brightest surface in the stack (white-ish fill on cream) so
fields read on both page and card. Citation chip: bracketed marker `[1]`, tappable,
carrying the Verified/Cited badge in its detail view. Skeletons use one shared shimmer;
sortable/financial rows keep ▲/▼ affordances.

## 4. iOS-native translation rules (decisions already made)

1. **Appearance follows the system.** Light = cream world, dark = navy world, switching
   with iOS appearance; optional manual override lives in Settings. No in-app toggle in
   the chrome.
2. **Hover does not exist.** Every web hover behavior becomes a pressed state using the
   active tokens above, plus context menus (long-press) for secondary actions.
   Focus rings are keyboard-only (Full Keyboard Access); rely on system focus effects.
3. **Liquid Glass lives in the functional layer only** — tab bar, navigation bars,
   toolbars, and (good candidate) the copilot composer floating above the thread. Use the
   regular variant over text-heavy content. **Content stays opaque:** cards, panels, and
   the reading surfaces never use glass — "cards lift, not tint" extends to "and never
   frost". Tint glass controls with the brand accent ink. Verify legibility with Reduce
   Transparency and Increase Contrast on.
4. **Navigation:** a bottom tab bar (≤5 tabs) is the primary structure — one-hand reach is
   the point. Propose the tab set (candidates: Home, Search, Watchlist, Calendar,
   Account; Search may suit the iOS 26 search-role tab). Within tabs, standard
   navigation stacks with large titles where they earn their space; swipe-back everywhere.
   Primary per-screen actions belong in the bottom half of the screen.
5. **Lists over tables.** Web data tables become insets/grouped lists or horizontally
   scrollable metric strips; a row = company or filing with logo/monogram, name, ticker
   (mono), and delta (direction color + sign). The existing logo-with-initials-monogram
   fallback pattern carries over — never a broken image.
6. **Charts:** Swift-Charts-style natives using the chart sequence above; axis labels
   11–12 pt mono; tooltips/scrubbing follow iOS conventions (drag to scrub, haptic ticks
   optional).
7. **The streaming summary job becomes a first-class iOS moment.** Design the in-app
   staged progress *and* a **Live Activity / Dynamic Island** treatment (generation takes
   30–120 s — users will background the app; the Live Activity is the retention moment).
8. **System integration surfaces to design (v1-scope, keep simple):** push notification
   anatomy for filing alerts (real-time and digest variants), a small/medium **widget**
   (watchlist deltas or next earnings), and the share-sheet export moment (summary → PDF).
   Sign in with Apple button follows Apple's brand rules (the one styling exemption, same
   as Google's).
9. **Numbers are load-bearing.** Every financial figure in SF Mono monospaced digits, with
   count-up on first presentation of KPI tiles; deltas always signed; direction never by
   color alone.
10. **Tone of voice in UI copy:** plain, factual, no hype, no exclamation points; AI
    content is always labeled and always one tap from its evidence.

## 5. Platform law (HIG) — the load-bearing specifics

- Safe areas everywhere (Dynamic Island, home indicator); full-bleed content scrolls under
  glass bars with the system scroll-edge effect.
- Minimum touch target 44×44 pt; comfortable spacing between adjacent targets.
- Dynamic Type support across all styles including accessibility sizes; test layouts at AX3.
- Dark Mode is a first-class appearance, not an inversion. Custom colors ship
  light/dark/increased-contrast variants.
- SF Symbols for iconography (choose weights that match text), custom glyphs only where no
  symbol exists (e.g. the copilot "quotes" evidence mark — note: a sparkle glyph is
  reserved exclusively for the "AI summary" label; don't scatter sparkles).
- Reduce Motion, Reduce Transparency, Increase Contrast, VoiceOver: every screen has a
  defined answer.
- Standard gestures: swipe-back, pull-to-refresh on feeds, swipe actions on list rows
  (e.g. watchlist add/remove, mark read).
- Where this brief's brand rules and the HIG conflict, **HIG wins on behavior and
  ergonomics; the brand wins on identity (color, type roles, tone)** — note any such call
  you make.

## 6. Screens to deliver

Design in **both appearances** (cream light + navy dark). Core set:

1. **Onboarding + auth** (value proposition in ≤3 beats; email/Google/Apple; reverse-trial
   start moment).
2. **Home** — feed with "what changed" headlines, hot filings, trending strip; pull-to-refresh.
3. **Search** — idle state (recents/suggestions), results (companies + full-text matches).
4. **Company page** — header (logo/monogram, ticker, price-free identity), fundamentals
   charts, filings list, insider activity, peers module.
5. **Filing summary** — (a) generation in progress: staged progress + its Dynamic
   Island/Live Activity companion; (b) complete: sectioned summary with metric callouts
   and "verify at source" affordances; (c) quota-hit state for free users.
6. **Ask this Filing** — thread with streaming answer, citation chips, citation detail
   (excerpt in mono + Verified badge + "open in filing"), composer; Pro-locked state.
7. **Filing reader** — New York serif long-form text, arrival-at-citation moment
   (highlight flash), section navigation.
8. **Watchlist** — rows with deltas, alert toggles, swipe actions, empty state.
9. **Earnings calendar** — upcoming for watched companies.
10. **Paywall** — Free vs Pro, 5-summaries/month framing, reverse-trial expiry moment.
11. **Settings** — notifications (real-time vs digest, per-company), appearance, account.
12. **Widget + notification** — one widget (small or medium) and the filing-alert
    notification, matching the system's widget/notification anatomy.

For each screen, include the states that carry the experience: loading skeleton, empty,
error, and (where relevant) streaming and gated/locked.

## 7. Component sheet

One artboard consolidating the translated system: buttons (all variants × default/pressed/
disabled/loading), chips & badges (incl. Verified/Cited, beat/miss, interim-filing),
inputs & the composer, list rows (company, filing, transaction), KPI tile with count-up
annotation, chart card (line + bar with scrub state), Notice + GuidanceCard, citation chip
+ popover, skeleton set, tab bar + nav bar in both appearances. Annotate with the exact
tokens used (hex, pt sizes, radius, motion timing) so engineering can map them 1:1 to
asset-catalog colors and code.

## 8. App icon

Design a layered iOS icon (Icon Composer model: background layer + unmasked foreground
layers; the system applies masking, specular highlights, and Liquid Glass effects — add no
custom shadows/bevels/glows). Deliver **three distinct concept directions**, each shown in
all six appearances (default, dark, clear light/dark, tinted light/dark), then recommend
one with a sentence on why. Starting territories (diverge if you find better):

- **The monogram** — an "EN"/"E" mark grown from the product's initials-monogram identity
  (the logo fallback every company row uses). A single-letter mnemonic is HIG-acceptable.
- **The evidence mark** — quotation/citation geometry: the product's soul is "claims that
  cite their source."
- **The statement abstracted** — filed-document / financial-statement geometry reduced to
  2–3 filled overlapping shapes.

Rules: filled overlapping shapes, no words (a single-letter mnemonic at most), no photos,
no screenshots, no thin strokes that die at 29 pt. Sage `#4F7A63`/cream/navy family only —
and because tinted/clear modes strip color, **the silhouette alone must carry the brand**.
Dark variant is designed (subdued, navy-at-home), not auto-inverted. 1024×1024 canvas.

## 9. Definition of done

- Every screen passes the **same-product test** (tokens match this brief exactly — no
  stray blues/mints/purples, no gradients, no stark white/pure black) and the **native
  test** (no web-isms: no hover affordances, no focus rings, no browser-card layouts, no
  cramped desktop density).
- Both appearances shown for every screen; contrast floors hold against cream and navy.
- One screen demonstrated at Dynamic Type AX3 to prove the layout strategy.
- Reduce Motion / Reduce Transparency answers stated for the signature animations and the
  glass layer.
- Every number on every screen is in the mono data face with a direction cue that isn't
  color-only.
- Sage never encodes financial direction; gain/loss never brand anything.
- 44 pt targets; primary actions reachable one-handed; safe areas respected.
- A short **decisions note** (≤1 page): the tab set you chose, any HIG-vs-brand calls, and
  anything you'd validate in usability testing first.

## 10. Working style

You have everything you need — act. Where the brief leaves latitude (tab set, icon
direction, widget subject, haptic map), make the call and record it in the decisions note
rather than asking. If you're weighing a choice, give a recommendation, not a survey.
Don't add screens, features, or flourishes beyond the brief; the restraint is the brand.
Never use generic AI-app aesthetics — purple gradients, glassmorphism cards, sparkle
confetti, dark-mode-only fintech noir. This product is warm cream, sage, espresso ink, and
monospaced evidence; its confidence is quiet.
