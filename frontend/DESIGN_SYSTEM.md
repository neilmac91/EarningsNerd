# EarningsNerd Design System — usage conventions

**Drop-in replacement for `frontend/DESIGN_SYSTEM.md`** (synced July 2026: single Sage accent,
type v2, cream-audited contrast). Token *definitions* live in `frontend/tailwind.config.js`;
this doc is the *how/why* + the rules learned the hard way. Read it before touching any UI;
subagent briefs for UI work should link here and to [the root DESIGN.md](../DESIGN.md).

Read `DESIGN.md` first for the visual direction and portable token/component snapshot. This guide
retains implementation conventions, exceptions and verification gates; actual token definitions
and component code take precedence over stale snapshots. Follow the
[maintenance guidance in CLAUDE.md](../CLAUDE.md#design-documentation) when a change affects the
documented system. The [.impeccable/design.json sidecar](../.impeccable/design.json) is a preview
companion to `DESIGN.md`, not a replacement for the components or the checks below.

> TL;DR: **brand = ONE Sage accent in both themes** (the sage/slate split is retired).
> Mint/emerald/`primary`/blue/sky/teal are **not** brand. Contrast is audited against the warm
> cream `#F4F3EE`, not white. Type v2 has three fixed roles (the font switcher is retired).
> Cards lift off the cream with a soft shadow (not a tint). Verify in **both themes**.

## 1. Palette roles (don't mix them)

| Role | Light | Dark | Use for |
|------|-------|------|---------|
| **Brand** | `brand #4F7A63` (**fill only**) / `brand-strong #3C6650` (text/links) / `brand-emphasis #345C48` (active) / `brand-weak #ECF2EE` (tint) / `brand-border #CFE0D6` | `brand-dark #7FB295` (fill/accent) / `brand-strong-dark #98C5AD` (text/links) / `brand-fill-dark #569272` (active) / `brand-weak-dark` / `brand-border-dark` | Primary actions, links, accents, focus rings, active states |
| **Surface** | `background-light #F4F3EE` (cream page) / `panel-light #FBFAF6` (card) | `background-dark #0B1120` / `panel-dark #1F2937` | Page + card backgrounds |
| **Text** | `text-primary-light #1A1A17` (espresso — heading ink is the SAME value; walnut `#3A2E26` retired) / `secondary #374151` / `tertiary #636A77` (4.9:1 on cream, 5.2:1 on panel; was `#6B7280` at 4.35:1 before the 2026-10 critique's P-02) | `text-primary-dark #D7DADC` / `secondary #9CA3AF` | Body + headings (see §4) |
| **Border** | `border-light #E5E7EB` | `border-dark` / `white/10` | Hairlines |
| **Status** | success `#15803D` · warning `#92400E` · error `#B91C1C` (+ `error.emphasis #991B1B` destructive hover) · info `#2563EB` (in-tint label: `info.text #1D4ED8`) | success `#22C55E` · warning `#F59E0B` · error `#F87171` · info `#60A5FA` | Genuine state messages only |
| **Financial** | `gain.text #15803D` / `loss.text #B91C1C` for delta **text**; `gain.light #16A34A` / `loss.light #DC2626` are **graphic/chip-only** (3:1 non-text floor); `flat #6B7280` (+ `-soft` tints) | `gain.dark #34D399` / `loss.dark #FB7185` (text-safe on navy) | Money/% direction only — never brand |
| **Overlay** | `overlay` rgba(11,17,32,0.55) | same | The ONE modal/sheet scrim (`bg-overlay`, v3) — replaces every `bg-slate-950/60` / `bg-black/50` hand-roll |
| **Chart** | `chart-1..6`: `#3E8E84` teal · `#B8812F` honey · `#5B7CC0` cornflower · `#CF7159` coral · `#6E7E9C` slate-blue · `#8B7BC0` periwinkle | same hexes (≥3:1 vs both cream and navy) | Chart series — a SEQUENCE, taken 1→N in order, never re-sorted |

**Legacy / banned as brand:** `mint-*`, `emerald-*`, `primary-*` (back-compat **alias for mint**),
`green/blue/sky/teal/cyan/indigo-*` as a primary color, and `shadow-glow-mint*`. The old chart hexes
(`#D99E4A` honey, `#5E9A6E` green) are retired — the green competed with sage; honey failed the
3:1 graphic floor on cream.

**Contrast floors are audited against cream `#F4F3EE`, not white.** Text ≥ 4.5:1 in both themes;
text on a tinted bg is measured against the mixed tint; non-text UI (bars, sparklines,
hairlines-as-meaning) ≥ 3:1.

**The device's tint is a ground like any other** (`brand-weak` light, `brand-weak-dark` mixed over what
is behind it). The words on it are the primary ink pair: a marked block's excerpt is 15.4:1 on the light
tint and 10.7:1 on the dark tint over navy, and the Source pane's located passage takes the primary ink
too, since the reader's secondary ink measures 4.49:1 on the dark tint over the slate panel (D-044). The
marker and its twin sit beside the tint, not on it, in `brand-strong` (5.9:1 on cream, 9.8:1 on navy).
Gate: tests/e2e/risk-evidence-rows.spec.ts measures the marker, the twin and the excerpt in both themes.

## 2. Theme-responsiveness is mandatory

Every color on a surface that renders in **both** themes must be a light/dark **pair**:
`bg-x-light dark:bg-x-dark`, `text-…-light dark:text-…-dark`. Never ship a single-theme color on a
shared surface (it caused white-on-cream and dark-on-cream bugs across the app). Gate:
`tests/unit/themePairs.spec.ts` holds the light half app-wide, stylesheets included: each colour class on a
`-light` token, or on a token beside a `<name>-dark` (`brand-weak`, `gain`), needs a `dark:` colour class
on the same property under the same variants, in the same class list. A twin under a condition, or one
that is itself a light token, does not count, and a stylesheet rule block's `@apply` lines are one list.
Tokens with no dark sibling (the chart palette, `overlay`, and the `-text` and `-emphasis` inks) are not
read. Its residue is listed per file and class, with a cap equal to it, and every file under the scanned
directories is read or listed as holding no class list. The same gate refuses the other half bare: a
colour class on a `-dark` token with no `dark:` variant paints the dark theme's colour in the light theme
(a stylesheet block whose every selector names `.dark` is the dark theme's), except on a surface dark in
both themes on purpose, listed in its own residue (the logos' forced-dark mode, the debug payload panel).

- **A state's colour pairs too, and a bare one is not harmless.** The brand tint's states take the dark
  tokens the §1 table pairs with them: a hover hairline `hover:border-brand-border
  dark:hover:border-brand-border-dark`, an outline `ring-brand-border dark:ring-brand-border-dark`, the
  interactive Card's pressed fill `active:bg-brand-weak/60 dark:active:bg-brand-weak-dark`. Tailwind writes a
  `dark:` class at the same specificity as a `hover:` or `active:` one and later in the sheet, so where the
  element sets its resting colour under `dark:`, a bare light state colour loses to it and dark shows no hover
  or pressed change at all; where it sets none, as a ring, the light colour paints on navy (the Copilot's user
  bubble drew `#CFE0D6` on the panel at 10.7:1, where light's ring sits at 1.3:1).
- **Muted text on dark = `secondary`, never `tertiary-dark`** (`text-text-tertiary-dark` fails WCAG AA
  on dark panels). Pattern for muted: `text-text-tertiary-light dark:text-text-secondary-dark`.
- The theme-aware **effect classes** (`.glass-card`, `.mockup-frame`, `.hero-search-glow`,
  `.text-accent-strong` — a solid ink, not a gradient) switch on `.dark` in `globals.css`, each as
  a full light/dark pair — don't add `bg-*` overrides to them. The legacy `.text-gradient-mint`
  alias is **purged** (cutover scan returned 0 uses); only `.text-accent-strong` exists.

## 3. Type v2 — three fixed roles (the font switcher is retired)

- **Headings:** Inter loaded WITH the variable `opsz` axis (`font-optical-sizing: auto` = SF-style
  Text↔Display cuts). ONE display weight: **600** (700/800 collapse to it). One theme-aware ink via
  `--heading-color` (`#1A1A17` / `#D7DADC`) — hierarchy comes from size + weight, never a second color.
  Promotional emphasis shares the italic and filled-ground treatment in §7 across its current surfaces;
  it retains Inter 600 and leaves ordinary headings in their existing upright role.
- **Body & UI:** `-apple-system → Inter` (system-first; Apple hardware renders SF Pro, everyone
  else falls through to Inter — Inter sits BEFORE generic `system-ui` on purpose).
- **Data:** Geist Mono + `tabular-nums` — money, %, tickers, XBRL anchors, verbatim excerpts,
  Ask-this-Filing output, and a code a reader may retype (the waitlist referral link: Inter's
  contextual alternates draw an x between digits, as in `p4x8n2wd`, as a multiplication sign).
  `.tabular` = mono evidence register; `.tnum` = tabular figures in the CURRENT (body) face —
  numerals inside prose/UI copy only. Data tables and KPI tiles are **not** `.tnum` surfaces: their
  numerics render mono (DataTable numeric cells, StatCard figures — the data-role rule).
- **Editorial serif (Newsreader)** is wired to the filing's own words alone: the real filing viewer
  (**`.filing-reader`**, 19/1.7, opsz auto: Item 1A, MD&A, notes) and a passage the server located,
  set as a marked block (`.en-marked`, 16/26). Serif = the filing's own words. Inside the product the
  marked blocks are the filing page's Risks rows and the summary's located quotes (D-044), a quote's
  speaker staying in the body face (`font-sans`); on a public page the serif appears only inside
  a quoted passage the product located (the hero example's evidence row, the social card's excerpt),
  never for a headline, tagline or a claim of ours. Gate: tests/unit/designSystemDoneGate.spec.ts
  (EDITORIAL_SURFACES, an equality: the reader, the hero example, the Risks rows and the quote blocks;
  outside the reader the face sits only in a marked block's class list, scored on the planted forms of
  `tests/unit/fixtures/sourceVoiceForms.tsx`; globals.css sets it on `.filing-reader` alone).
  **`.markdown-body` is NOT serif**: it carries the reader's list + heading + table manners on the
  **body sans**, but FILLS its pane with no measure cap (it renders inside a card/pane, where any
  capped measure reads as dead space — field-tested twice) — its app consumer is
  the AI-generated summary, and AI output never renders in the filing's voice. Ask output stays mono.
  **Justified summary body:** at ≥sm (640px) only, `.markdown-body p` and the structured summary's
  paragraph blocks (`SummaryBlocks`, `sm:text-justify sm:[hyphens:auto]`) set `text-align: justify`
  + `hyphens: auto` — an app-wide, founder-requested decision (rule 11) so the AI summary reads as
  a finished document. Below 640px they stay ragged-right (v3 Q3): CSS justification opens uneven
  word-spacing/rivers in a narrow measure, and even `hyphens: auto` (with `<html lang="en">`) cannot
  hold them down in a phone-width pane. Scoped to the summary only — the real filing reader
  (`.filing-reader`) stays ragged-right. One-block revert.
  **Links in both surfaces, and in a Copilot answer:** Tailwind preflight strips anchor color AND
  underline, so a shared globals rule restores them. A prose link prints words the product does not
  write (the filing's, the model's), a figure or a date among them, so `:is(.markdown-body,
  .filing-reader, .copilot-answer) a:not([data-citation-kind])` rests in its prose's own ink with a
  quiet underline (`decoration-text-tertiary-light`, `dark:decoration-text-secondary-dark`,
  `underline-offset-4`) and turns sage, its underline with it, only under the pointer, the whole label
  turning, an emphasis inside it in an ink of its own included; keyboard focus draws the brand ring
  (D-030). A citation chip among the prose (`data-citation-kind`, CitationChip's
  anchor where no viewer is mounted, as in the homepage's Ask demo) is no prose link and keeps its
  own chip, and a link that wraps draws its ring around each line (`box-decoration-clone`). Gates:
  brandCopyRules.spec.ts rule 2's stylesheet check, with its planted forms in
  `tests/unit/fixtures/brandRule2Styles.css`; its markdown-link check, which fails an `a` the app
  hands react-markdown resting in sage; and `tests/e2e/prose-links.spec.ts`, which reads what the
  cascade paints.
- **Tracking ramp** (`--track-*`): +0.01em ≤12px · 0 at 13–19px · −0.012em 20–24px · −0.016em
  26–32px · −0.02em 34–44px · −0.025em 48px+ · `--track-eyebrow 0.08em` for uppercase micro-labels —
  as the utility **`tracking-eyebrow`** (v3). `tracking-wide/wider/widest/tight/tighter` and arbitrary
  `tracking-[…]` are off-ramp (lint-banned; the 40px pricing display figure is the one disabled site);
  headings take their tracking from the fontSize ramp.
- 12px UI-type floor for running copy; `text-data-xs` (11px) for dense numeric annotations and in-card
  captions / uppercase micro-labels (v3 b8 maps every former `text-[10–11px]` text site to it). The
  provenance chip that carries a verification claim is never one of them: it is 12px (P-10, §4), as are
  the in-text citation marker (CitationChip, the analysis narrative's chip) and every source-check label
  (gate: `tests/unit/dataXsAllowlist.spec.ts`, a shrink-only list of the files that use data-xs, its file and
  site totals an equality cap that the PR shrinking the list lowers in the same commit). UPPERCASE
  tracked eyebrows are reserved for metric labels — never card titles (`CardTitle` is sentence case,
  14px/600 heading ink; it shipped as an eyebrow in v2 and was fixed in v2.1) and never document headings.
- **Section title** (2026-10 critique P-05): the filing summary is a document, so its section headings are
  `h2` at **20/28** (`text-xl font-semibold`, the −0.012em ramp step) with a data-face index at 12px
  secondary (`01`, `02` …) that its table-of-contents entry repeats; a subheading inside a section is an
  `h3` at 14/600, sentence register. `CardTitle` stays the compact heading of a container, not of a
  document section.
- **Figtree and Helvetica are retired.** `--font-active` survives as a permanent alias of the body
  role so existing `font-sans` usage keeps resolving; don't reference Figtree in new code.

## 4. Canonical component patterns

**Compose the component layer, don't hand-roll** — `components/ui/*` (Button, Badge, Input, Card,
DataTable, Skeleton, GuidanceCard, Notice, Modal, SegmentedControl, MissingValue) + the copilot answer renderer
`features/filings/components/copilot/CopilotMessage.tsx` (see "Ask answer" below). Controls expose their applicable interaction and
availability states; data surfaces supply loading, empty and error treatments as supported by
their APIs. Passive Card and Badge primitives do not implement the full control-state set.

A control that is busy, or unavailable as a result of its own activation, never takes native
`disabled`: Chromium blurs a focused control that turns disabled, so keyboard focus falls to
`<body>`. Busy is `<Button loading>`. Unavailable is `aria-disabled` plus an early return in the
handler, styled with `primaryUnavailableClass` (primary Button), `secondaryUnavailableClass` (secondary
Button; it fades the label and hairline, not the element, so the focus ring keeps its strength) or
`fieldUnavailableClass` (field; it fades the text ink and leaves the hairline to the focus and invalid states,
hovered or not: v3.7 restates the focus border under `aria-disabled:hover:`, which outranked it).
A form that locks its text fields while it submits uses `readOnly`, never native `disabled` (`ContactForm` does;
the login and register forms leave their fields editable). Gate: `tests/unit/busyControlsStayFocusable.spec.ts`;
rules in `lessons/frontend-busy-controls-stay-focusable.md`.

An aria-disabled control never takes an element `opacity`. It is still focusable, and the opacity fades its
focus indicator with everything else it paints. The opaque ring's 3:1 floor is held by
`tests/unit/siteChromeFocusRing.spec.ts`. A hand-rolled busy or
unavailable look fades what the control draws in, at the fraction the opacity had, on the tokens it already
uses and as a light/dark pair: the label's ink (`aria-disabled:text-error-light/50
dark:aria-disabled:text-error-dark/50`; a glyph or spinner in `currentColor` follows it), the hairline
(`aria-disabled:border-border-light/50`; dark's `white/10` halves to `white/5`, because `/50` on an rgba token
replaces its alpha), a switch track's fill. Content with an ink of its own fades through `group`, in ink
(`group-aria-disabled:text-brand-strong/50`) or, for an image or a row of several inks, by its own opacity
(`group-aria-disabled:opacity-50` on the child): a child's opacity never reaches the control's ring. A natively
disabled state keeps `disabled:opacity-*`, since it cannot hold focus. The hover fill is left as the control
has it, as on `<Button loading>`; the faded ink and hairline hold under hover. Gate:
`tests/unit/ariaDisabledKeepsItsRing.spec.ts` (no `opacity-*` class behind the element's own `aria-disabled:`
variant anywhere in the app's source, and no other `opacity-*` class, except behind `disabled:`, on an element
that carries `aria-disabled` or on a use of a shared control that renders one with the caller's className:
`<Button loading>`, RetryButton, AlertBell).

A Retry of a failed query is
`<RetryButton failures={[useRetainedFailure(query, queryKey)]} focusTarget={headingRef} />`, never a hand-rolled
`<Button loading={isFetching}>`. `queryKey` is the key the query's own `useQuery` was given: it is the hold's
identity, so a key change (another user, a new search term) never holds the old query's error (gated in
`tests/unit/useRetainedFailure.spec.tsx`). The error UI stays up through any refetch until data replaces it;
the Retry is busy while the query has a fetch in flight (paused offline included), reads "Trying again…" only
while its own press runs, and hands focus to `focusTarget` (a `tabIndex={-1}` heading, or a text field with
`textField`) when it unmounts while focused. It lives beside its hook in `hooks/useRetainedFailure.tsx`, not in
`components/ui`: it is query-coupled, the DS primitives stay free of react-query, and `components/` root is app
chrome only. Every Retry is RetryButton, gated in `busyControlsStayFocusable.spec.ts` by wiring and by label.
Its label is the product's one retry verb (D-032): "Try again", busy "Trying again…", RetryButton's own, so a
call site passes none: TypeScript refuses a child, an aria-label and an aria-labelledby (RetryButtonProps declares
each `never`), RetryButton drops each at run time (one a spread or a cast brings in), and the gate fails a call
site that passes one, under any name an import gives RetryButton. It keeps the room of the spinner and "Trying
again…" at rest (Button's `reserveLoadingText`, below; D-032), so the swap never resizes it or moves what sits
beside it: without it, at 390px under 200% text the label wrapped and the card grew 22 to 24px (e2e
`filing-source-chip.spec.ts` holds the box through the swap, in both themes at 390 and 1440px). That room must
never cost reflow. So the Retry takes its own row under its message, as a Notice's action does, never a place
beside its message or another control in a row that cannot wrap (GuidanceCard's action row wraps and centres
two actions); a message carrying the backend's words breaks a long token (`break-words`); and where even its own
row is narrower than the spinner beside "again…" (a Notice inside a card at 200% text), the spinner goes above
the label (Button's reserve, below). Before, at 390px under 200% text, the homepage and full-text search alerts
pushed their Retry past the screen (the page 445 and 472px wide), the dashboard's account card put its Retry's
left edge off the screen at 320px, and the comparison card's Retry widened the page at 320px. A Notice inside a
card keeps its Retry and its title inside its own border too: its row wraps, and its text column goes under the
glyph where it cannot keep 9rem beside it (Inline notice, below). Before, under 200% text, the comparison card's
Retry ran 39px past the Notice's border at 320px and its title's "comparison" 62px (22px at 360px), and at 360px
the billing and ticker filings cards' Retry ran 15px past it. Gates: e2e `reflow-200.spec.ts`, "a failure's
controls stay inside their card" (the homepage search alert and the full-text search alert on /search, each at 320,
360 and 390px and with a long token, the
dashboard's account card at 320, 360 and 390px, the route and dashboard error boundaries at 320px, and the
comparison, billing and ticker filings cards at 320 and 360px, each held to its Notice's border at 360px and the
comparison card at 320px too; at rest and busy); `full-text-search.spec.tsx` for
the full-text search alert's layout;
`twoActionsWrap.spec.tsx` for GuidanceCard and the four page-replacing fallbacks; `button-wrap.spec.tsx` for the
reserve's rows. Its limit: at 320px under 200% text a `p-6` card (48px a side: billing, ticker filings, the
admin feedback and invites lists) leaves a Notice a 92px content box, narrower than the Retry's narrowest state
(138px, its padding and "again…"), so there the Retry sits 13px past the Notice's border, inside the card, the
page at its width. Main's resting Retry is 30px past it there, so the cards' padding causes it, not the reserve
or the Notice (E120). Where one Notice holds two failed reads, one
RetryButton takes both failures (the dashboard's plan strip, the pricing page's details Notice): its press retries
the ones that failed, and two buttons with one label could not say which read each retries. A retry control that is
not RetryButton yet (an error boundary's reset, the summary and answer stream restarts) reads the same words, and
so does the copy beside a Retry ("Try again in a moment."): the gate's one-verb clauses fail any other label, busy
text or "retry" in copy, naming the file and line.
A Retry that restarts a stream, not a query (the filing page's generation restart), is RetryButton too, given the
stream's own failure, `{ failed: true, error, busy: false, retry }`: there is no query to hold, and the press
clears the error in the render that starts the stream, so the card leaves with the press when the run starts
and its hand-off target is the progress card's heading. The card offers it only for a failure a retry can help
(`isNonRetryableStreamError`: Pro's fair-use pause, a sign-in or a permission error keeps its sentence and no
Retry), so a press that starts no run (signed out) keeps the card without it, and the target falls back to the
card's own heading. A failure built by hand like this is pinned, with its
reason, in the gate's `ALLOW_HAND_BUILT_FAILURE`. Every other failure RetryButton is given must be
`useRetainedFailure`'s, the hook its module exports under any imported name (a same-named local is not it),
which the gate proves through same-file `const`s, through a component's prop to its call sites (under any
imported name), and under any name an import of RetryButton's module gives it (an alias, a default import,
`H.RetryButton`); what it cannot prove (a `let`, a JSX spread on
RetryButton or into such a component, an empty list) fails as built by hand. A card that ends a run the user is
waiting on (a failed generation, the monthly limit) takes focus when it appears, on its title
(`GuidanceCard`'s `headingRef`: `tabIndex={-1}`, no outline, described by the card's description), and only when nobody holds focus (`useFocusOnArrival`,
`hooks/useFocusHandoff.ts`). Never on its button, where a key pressed as the card lands would act, and never
away from a field, a link or an open modal dialog the card is not in.

A grid that sets its columns under a variant also sets its base track in the same class string:
`grid grid-cols-1 md:grid-cols-3`, never `grid md:grid-cols-3`. Without the base, the phone layout is
one implicit `auto` track that sizes to its widest content, so one long company name scrolls the page
sideways. The base must render whenever the variant columns do: in text that is always there, or in the
same conditional branch (ternary arm, `&&` operand, `clsx` object key). `cx('grid grid-cols-1', wide &&
'md:grid-cols-2')` is right; `cx('grid', wide ? 'md:grid-cols-2' : 'grid-cols-1')` is not. Gate: the ESLint
rule `earningsnerd/responsive-grid-base-track` (`eslint.gridBaseTrack.mjs`); rules in
`lessons/frontend-variable-text-must-not-size-a-wrapping-row.md`.

```
Primary button   <Button>  ·  LIGHT: white label on bg-brand, hover bg-brand-strong, active bg-brand-emphasis
                 DARK: NAVY-INK label on bg-brand-dark (text-background-dark), hover bg-brand-strong-dark,
                 active bg-brand-fill-dark.  White-on-fill-dark is 3.7:1 — never revert to it.

Secondary button <Button variant="secondary">  — brand hairline on transparent; tints on hover
                 border border-brand-border bg-transparent text-brand-strong hover:bg-brand-weak
                 active:bg-brand-border/60  dark:border-brand-border-dark dark:text-brand-strong-dark
                 dark:hover:bg-brand-weak-dark dark:active:bg-brand-border-dark
                 (never hover:opacity — it darkens). Native disabled secondary/ghost controls keep their
                 transparent fill under hover and active in both themes; loading keeps the resting look.

Wrapping button  <Button wrap> (or buttonVariants({ wrap: true })) lets a text label wrap and replaces
                 its fixed height with min-h-8 / min-h-10 / min-h-12 plus size-owned vertical padding.
                 Constrain width at the call site; never override its height or whitespace.
                 Default buttons keep their fixed height above a 24rem viewport (below it, the Button
                 size row); icon-sm stays a 32px square.

Steady loading   <Button loading loadingText="…" reserveLoadingText="…"> keeps a loading label's room at
                 rest when it is longer than the resting one: what shows is laid over an invisible, aria-hidden
                 copy of the loading state (the spinner's box and that label) in one grid cell, so the swap
                 never resizes the button or moves what sits beside it. Each row wraps, its label based at its
                 longest word, so where the button is narrower than the spinner beside that word the spinner
                 goes above the label, and the room is never wider than that word with the padding.
                 RetryButton's "Trying again…" is its one use (tests/unit/button-wrap.spec.tsx holds the cell
                 and the rows; busyControlsStayFocusable.spec.ts holds RetryButton to reserving the busy text
                 it shows).

Ghost button     <Button variant="ghost">  — brand.strong text on transparent, tint hover
                 (`variant="tertiary"` is accepted as a deprecated alias of ghost — pre-v2 API)

Button size      sm, md and lg keep a fixed height (h-8 / h-10 / h-12: 32, 40 and 48px) and one line
                 (whitespace-nowrap) unless `wrap` is set (the row above); icon-sm is a fixed 32px square.
                 Below a 24rem viewport every labelled size takes the wrap state on its own: h-auto, the
                 size's min-h and vertical padding, whitespace-normal, centred on tight leading. A media
                 query's rem is the browser's text size, so that is 384px at the default size (a 390px
                 phone keeps one line) and 768px under a 200% text setting, where a 390px phone would
                 otherwise scroll sideways. The variant is `[@media(max-width:24rem)]:`, since Tailwind
                 drops `max-[24rem]:` while the screens are in px. In that state a caller's own min-h or
                 vertical padding wins over the size's (the header's account link keeps its 44px target
                 from min-h-11 on a 360px phone), through <Button className> and buttonVariants alike. A
                 taller target is set with min-h, never a fixed h-, which h-auto would beat there, and a
                 min-h or py goes through the factory's className option (<Button>, RetryButton and
                 MarketingCta pass theirs through it), never beside its output in cx() or a template,
                 where the narrow state cannot see it (tests/unit/buttonHeightIsAMinimum.spec.ts holds
                 both). A `whitespace-normal` className still loses to the base `whitespace-nowrap`
                 above 24rem (stylesheet order): use `wrap`.
                 Gates: tests/e2e/reflow-200.spec.ts (390px at both text sizes; 360px at both; a 768px
                 and an 834px tablet at 200%), tests/unit/button-wrap.spec.tsx (the narrow state keeps a
                 caller's min-h and py).

Link as button   buttonVariants({ variant, size })  — the class-string factory for <Link>/<a>
                 styled as buttons; <Button> composes the same factory. Raw fields that the
                 <Input> component can't wrap use inputClasses({ invalid, tone, density, select, autoWidth }).
                 Tone (v3.5): the border and focus ring are one tone, default or error, never one layered on
                 the other: `invalid` (the components' `error`) picks the error border, which holds on hover,
                 and the error ring. Each tone states its focus border even where it equals the rest border,
                 because the forms plugin's `input:where([type='text']):focus` border (#2563EB, 0,1,1)
                 outranks a bare `border-*` (0,1,0).
                 Destructive-confirm fields use tone="danger" (v3.8): the same neutral border at rest and
                 on hover, with an error border and ring only on focus (focus-within for a shell).
                 Danger describes the action, not the value; it does not imply aria-invalid. An actual
                 invalid value takes precedence and the raw field wires aria-invalid to match it.
                 Toolbar fields (v3.1): density="compact" on <Select>/inputClasses = 36px from sm
                 up, phones keep the standard 42px field height; a field inside a table row is compact too.
                 `density`, not `size` (a native attribute); each density has its own EXPLICIT padding sides
                 (never an override on top). A select stays raw when it needs a class on the element itself
                 (fieldUnavailableClass) or has no Shell; it takes `select: true` (the Select component's
                 padding: pr-9 clears the chevron). `autoWidth: true` sizes a field to its content (beside its
                 label in a flex row, a toolbar filter, a table cell), capped at its container. Never a class on
                 top that sets what the field sets (`w-auto` over its `w-full`, `py-1.5`, `text-xs`): cx and clsx
                 do no tailwind-merge, so stylesheet order decides, and `.w-full` follows `.w-auto`. Gate:
                 tests/unit/inputClassesNoOverrides.spec.tsx.

Accent text/link text-brand-strong dark:text-brand-strong-dark   (never brand.DEFAULT as text on cream)
                 A link that prints words the product does not write rests outside sage instead: a prose
                 link in its prose's ink (Links in both surfaces, above), and a Copilot source's locator
                 as the count control below.
Count control    A link or control whose label carries a count, a date, an index name or a price
                 (D-030) and turns sage under the pointer composes countControlClass(kind) from
                 components/ui/countControl.ts beside its own shape (size, padding, width, a border),
                 never the recipe by hand. The whole label rests in text-text-secondary-light
                 dark:text-text-secondary-dark as one text run and turns hover:text-brand-strong
                 dark:hover:text-brand-strong-dark under the pointer, keyboard focus drawing the ring
                 below: 'button' adds the brand tint and the pressed fill, 'link' an underline under
                 the pointer, 'inline' (a link set among lines of text) keeps its underline at rest,
                 since its ink no longer marks it, and 'summary' (a disclosure's) turns sage alone.
                 Its chrome (the ring, a hairline, a selected fill) may be sage where its recipe says
                 so; the label's ink never. Never a sage label with the count in a span of its own:
                 the control then rests in sage while it carries a value, and the rule keeps sage for
                 the pointer. Two count-carrying labels stay outside the helper, in the ink: one that
                 never turns sage (a calendar day's "+N more", whose cell's hover is the white
                 ground), and a countdown on a control that waits (aria-disabled), which rests in the
                 secondary ink at full strength beside its own label (check-email), so the number
                 stays legible. Gate: brandCopyRules.spec.ts rule 2. Its count-control check fails a
                 control resting in sage, its own or its parent's where it is rendered (held in the
                 same file or rendered by a component included, and a component that renders its
                 children inside a control counting as one), that holds its count in a span of its
                 own ink (written inline or held in the same file; a count a component renders inside
                 one is review-checked). Its one-source check fails a control whose label carries a
                 count and that classes written in its file turn sage under the pointer: on the
                 control, on the element holding the count (a label span, under the control's group
                 too), or on the control a same-file wrapper renders its children in, a class
                 helper's return or a className default included. It reads the label through the
                 file's bindings (a same-file variable, a same-file function's return) and inside an
                 app component in it that turns its children or a count of its own sage. The two
                 labels outside the helper are review-checked, and so is what the header names.
Focus ring       focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark;
                 destructive + invalid fields use shadow-ring-error / shadow-ring-error-dark. Opaque 3px rings
                 hold at least 3:1 on page, panel and tinted control surfaces. Clipped regions use
                 shadow-ring-brand-inset / shadow-ring-brand-inset-dark. There is no global :focus-visible rule, so
                 a control without the recipe draws the browser's own outline (`auto`), unlike its neighbours.
                 A control that is a block of its own (a logo link, an icon button, a menu row) takes a radius
                 (`rounded-lg`) so the ring follows its shape. A field the forms plugin styles (a text
                 input, textarea, select, checkbox or radio) also takes `focus:ring-0
                 focus:ring-offset-0`: @tailwindcss/forms rings it blue on any focus, and the
                 shadow utilities draw the brand ring inside that ring rather than instead of it. Every DS field
                 carries the reset (Input.tsx FIELD_BASE, v3.6; gate tests/unit/inputClassesNoOverrides.spec.tsx),
                 and a field that styles itself, on any page, takes it with a DS ring and its dark twin (gate: the
                 app-wide field describe in tests/unit/siteChromeFocusRing.spec.ts). Every Tab stop
                 in the site chrome carries it (the skip link the same triple on `focus:`). The same gate
                 covers raw controls in check-email, settings, invites and watchlist pages and their feature
                 modules, plus the shared Switch; field recipes retain their app-wide gates: gate
                 tests/unit/siteChromeFocusRing.spec.ts reads the AST of every chrome file, discovered from
                 app/layout.tsx, every route layout, template or error boundary under app/ (the admin
                 nav, global-error's fallback), AuthShell and SecondaryHeader through their imports (a lazy
                 `import()` included) and re-exports, into the DS primitives they render (a barrel's
                 named re-export by the names imported: Modal with its close ✕, Button, Skeleton), so a
                 new banner, menu, widget or primitive is scanned unlisted,
                 plus every control a page passes into SecondaryHeader's `actions` slot (the dashboard's
                 "Log out"; write them inline, as a variable or
                 a component of their own the scan cannot read them); `buttonVariants(…)` composes it; a
                 className it cannot read fails (it reads `cx(…)` by its static arguments), and so does a
                 props spread, except a component's own rest props passed to the element that takes its
                 className. An <iframe> in the Tab order (`tabIndex={-1}` takes it out), <audio> or
                 <video> with `controls` and a <details> with no <summary> of its own fail outright: the
                 browser focuses the frame's document, its own media controls or its own "Details"
                 summary, which no class reaches (Chromium 141). A
                 third-party component the chrome renders must be classified in the gate (a provider renders
                 no control); Sonner's Toaster takes the ring
                 through `toastOptions.classNames` with `!` on the shadow, since Sonner's own injected
                 :focus-visible shadow matches or outranks a utility class, and the gate pins every slot. It is
                 the rule's one gate; a page's other controls (the filing identity strip's breadcrumb) carry the
                 recipe but sit outside it.

Card / panel     bg-panel-light dark:bg-panel-dark + border + shadow-e2 dark:shadow-none
                 (e1 chips · e2 cards · e3 hero/featured · e4/e5 menus & overlays)

Input            <Input>  — fill is the BRIGHTEST surface so the field reads on BOTH the cream page
                 AND an off-white card: bg-white dark:bg-white/5 + hairline + brand focus ring

Delta text       text-gain-text dark:text-gain-dark  /  text-loss-text dark:text-loss-dark
                 (the 600-level gain/loss are chips + graphics only — the 3:1 non-text floor).
                 lib/financialTone.directionText IS this recipe — route delta text through it; a
                 direction chip (the dashboard's what-changed metrics) takes directionChip. Never sage on
                 a direction. Gates: earningsnerd/direction-text-tokens (eslint.designRules.mjs) bans the
                 600-level gain/loss as text anywhere (written on an icon or an SVG graphic, it colours
                 the graphic and passes), and sage on a TrendUp/TrendDown glyph, known by its spelling,
                 its import (any local name, a namespace member, Phosphor's unsuffixed name) or a binding
                 the file writes one to (an alias, a ternary, a lookup in a map of glyphs, as the
                 what-changed chip draws its `<Icon />`), on every element above it up to the first that
                 gives it an ink on every render (a theme text colour with no variant, or a class part the
                 rule cannot read, such as directionChip[tone]; a layout or type wrapper such as
                 `flex gap-1` or `text-sm` passes the ink through), or in a map that pairs one with its
                 classes; a glyph that reaches a binding as a parameter or a call's result, a glyph
                 returned from a .map callback and a glyph passed as a JSX prop (`icon={…}`) are past it.
                 A delta or a figure in sage with no glyph fails tests/unit/brandCopyRules.spec.ts rule 2
                 (D-030), a figure field such as `display` included. tests/unit/whatChangedChip.spec.tsx
                 renders the what-changed chip and holds its colour to directionChip for the server's
                 tone, which no lint can see.

Data note mark   <DataNoteMark> (analysis) — neutral † for a calculated origin, then a superscript
                 letter for its grouped data note. The letter is text-data-xs (11px minimum), zero
                 line-height, and does not size its row. Warning ink belongs only to unresolved review
                 concerns; unavailable values and missing validation use secondary ink. The mark is
                 aria-hidden inside the figure's source button; its accessible name states the note
                 and any inherited comparison note once; a shared figure/comparison note is named
                 once with its scope. The separate visual change mark does not repeat the spoken
                 note. Letters are snapshot-local, review notes first.
                 Data notes counts distinguish values, QoQ, YoY and annual window comparisons;
                 a missing validation record is never counted as a passed check. Preserve every
                 reason, including comparison-only concerns. Full-width status Badges and nowrap
                 labels do not belong in an analysis KPI or metrics cell.
                 MetricsTable opts into compact mark spacing so an amount and its affixes stay
                 together in a fixed period column; the other surfaces retain standard spacing.

Data table hover <DataTable> — ordinary rows use hover:bg-white dark:hover:bg-white/[0.03].
                 With stickyFirstColumn, first-column body cells stay opaque: light hover uses
                 group-hover:bg-white; dark hover retains dark:group-hover:bg-panel-dark. The
                 ordinary row tint must not replace that opaque fill and reveal scrolled values.

Missing value    <MissingValue label="…" className="…">  (components/ui, E88): a value the page does
                 not have, in a cell, a detail row or a line of copy. The token (—, the one sanctioned
                 em-dash) in the caller's ink, aria-hidden, beside sr-only words a screen reader reads in
                 its place: "unavailable" by default, the analysis evidence's word, or the site's own where
                 that would claim more than its data says ("no cohort", "no page", "no role listed",
                 "name unavailable", "no percentage", "no takeaway", "Not included"). `relative`, so the words stay
                 inside a truncating cell or a table's scroll box. A formatter returns null or '' for a
                 missing value and its caller renders the element (`fmt(v) ?? <MissingValue />`), so the
                 formatter's string fallback stays for a CSV, a title or an aria label. Never the token by
                 hand, a hidden dash with no words, or a span pair of one's own. Gates:
                 tests/unit/missingValueToken.spec.ts (the token renders nowhere but the element: JSX
                 text, a child, a fallback, a same-file or imported formatter's return, a prop or render
                 prop of a component it cannot read, an element call; its header names what it cannot
                 read, each planted as a gap) and tests/unit/MissingValue.spec.tsx (the reading, the
                 words a site passes and the positioned clip).

Analysis table   <MetricsTable> — equal rem period columns with semantic row headers. The label
                 column sticks only when the scrollport can also show one whole period; otherwise
                 it scrolls with the table and has its own snap stop. The MetricsTable Card is its
                 query container; the label width is capped to that content width, keeping labels
                 readable at Home without an oversized free-panning snap area. The scroll region
                 itself is not the container: its trailing snap padding must not shrink the cap.
                 useOverflowRegion(ref, { label, describedBy, enabled }) owns measurement and the
                 optional region props: role, Tab stop, name and description exist only while content
                 exceeds the box by more than one CSS pixel. It observes the box and first child,
                 rebinds replaced children and measures window resizes without ResizeObserver. Start
                 disabled while the box is not rendered. Hints and scroll behavior remain surface-owned.
                 The named region supports Left/Right by one measured column,
                 Home/End, PageUp/PageDown and mandatory snapping. Child controls retain their keys. Inline-end padding makes the entire scroll range a whole
                 number of columns. A layout effect measures before paint; resize and enlarged text
                 recompute rendered widths without accumulating padding or losing the prior column.
                 Scroll events from native resize snapping wait for current measurements before
                 updating the retained column.
                 Focused figure controls are scrolled wholly into view using the active sticky inset.
                 Phones below 640px start at
                 the newest period. “← Earlier quarters” (or years) appears only on phones while
                 earlier columns are off-screen; the hidden hint line retains its height at the
                 start so native keyboard scrolling does not shift the page. Generic table hints
                 keep their existing static behavior.
                 A table-only segmented window defaults to All, with Newest 6 and Earliest 6 when
                 more than six periods exist. Charts, KPI cards, data-note totals and full exports
                 retain the complete selected dataset. A status region announces the visible count.
                 Report context shares the table window with note locators; a new snapshot or report
                 resets it to All, and standalone tables retain local selection. Illustrative demo
                 and teaser tables use an explicit sample prop to suppress the window controls.
                 Headers show quarter/year on two lines with the complete quarter/year accessible name.
                 The annual final column names the full report range and CAGR; visible prose explains
                 that percent-unit rows instead show the recorded window’s percentage-point change.
                 The table's Notes chip lists only letters present in its visible cells, including
                 unavailable values and annual window comparisons, in report note order.
                 The change basis is stated once, while
                 a fallback YoY label sits on its own line above the complete change and note.
                 Data cells align at the top so missing values and mixed growth heights stay aligned. Only a period-derived Q4
                 receives a column dagger; ordinary arithmetic ratios do not create one.
                 The legend explains n/m and the fiscal-quarter basis. A Q4 header dagger applies
                 to flow figures calculated from annual totals less nine months, without labelling
                 the column's balance-sheet figures as calculated.
                 Table-only formatting keeps complete amounts and affixes together: normal precision
                 first, then fewer decimals, compact scale or scientific notation for large tokens.
                 Signs and percent/ratio units remain. USD keeps its dollar symbol; other currency
                 codes appear in the metric row heading (including per-share units), with signed
                 numeric amounts in its cells so long currency prefixes cannot widen the table.
                 Source evidence retains every original currency and value. The visible rounding note
                 directs readers to full-precision evidence; the dialog keeps the original value
                 and ordinary comparison display. Shared financial formatters remain unchanged.
                 DataTable's layout, colWidths, compact cellPadding, named scrollRegion, snapColumns
                 and Column.rowHeader options are opt-in; other consumers retain their geometry.

Analysis evidence <SourceValue> — the shared Modal presents financial display form, the supplied
                 value labelled “As stored” and human-readable units, then Checks, Method and recorded
                 source lineage. Checks distinguish SEC XBRL admission from compatible-input calculations;
                 neither claims an audit. Missing figures read “Unavailable”, with the effect of a gap
                 stated. Quarterly dialogs name the quarter end; source links name their figure and period.
                 Formula substitution uses operand identity, not list position; it only asserts an
                 equality for a passed calculation. Missing lineage is stated explicitly, never
                 represented as recorded inputs or a scheduled repair. Original SEC links and
                 nested inputs remain accessible; raw tags sit in technical disclosures. Annual
                 growth fractions and percentage-point changes retain their distinct units.
                 A noted comparison names the recorded input and period carrying its concern; if
                 its input identity is absent, say so instead of inventing an operand or fiscal period.

Analysis reflow  The page title and selected-company rows wrap. Narrative cards use p-4 sm:p-6;
                 export/refresh Buttons use size="sm" wrap and max-w-full. The shared wrap state
                 keeps min-h-8 and lets labels grow within the card without conflicting utilities.

Analysis reading <NarrativePane> — compact monetary amounts and quarter labels in prose, without
                 changing link destinations, code or source excerpts. Preserve enough precision
                 to keep a stated comparison meaningful. Up to three recognized source operands
                 remain inline with their original citation controls; longer lists fold beneath a
                 neutral summary that names every applicable note letter. Unrecognized content
                 remains visible. Printing opens Data notes and narrative evidence, then restores
                 the reader's disclosure choices. Source entries retain the exact supplied value
                 beside compact display and distinctly named filing links. A quiet source count
                 and Notes control replace repeated status labels.

Analysis periods <PeriodPicker> — shared SegmentedControl for Annual/Quarterly; unavailable modes
                 opt into focusable aria-disabled with visible described reasons. Other callers keep
                 native disabled. The unavailable segment retains the full-strength focus ring.
                 Recent-period presets are plain actions in the secondary ink that turn sage under
                 the pointer, keyboard focus drawing the ring, with Button sm's shape and weight
                 copied by hand (not ghost Buttons, whose label is sage at rest on a count, D-030),
                 not pressed toggles; they sit outside the Button size contract on purpose, so a
                 later change to Button's sizes does not reach them (their labels are three short
                 words and their row wraps). Visible From/To
                 labels wrap raw compact selects using inputClasses({ select: true, autoWidth: true });
                 font-data and tabular-nums belong to the select itself. Fields fill phones and use
                 intrinsic/em widths on desktop. Analysis's full-width route wrapper is an inline-size
                 query container. Below 13em of its actual text size, main uses px-2 and the control
                 Card uses px-1.5, preserving full selected tokens at enlarged phone text. The shared
                 field padding and font stay unchanged; ordinary 320px+ layouts retain their spacing.
                 The range comes before its count in the summary.
                 Moving an endpoint keeps the range ordered and within the server-provided cap and
                 announces an automatically moved other endpoint through role=status. Unavailable
                 annual years remain visible but disabled options. Table windows never alter selection.

Analysis KPI     <KpiStrip> — a definition list, two cards across at phone widths and four from lg.
                 An inline-size container query collapses it to one card below 17em of the
                 component’s actual text size; 320px at ordinary text still has two cards.
                 Each Card groups a metric-only dt and two dd rows: the 24px data-face value/source
                 button, then the actual reporting period and delta. Cards span three subgrid rows,
                 so wrapped labels do not move neighbouring values. The period and delta wrap as
                 independent inline items; an older populated point says "latest available" beside
                 its actual period. Missing comparisons leave the period visible. Cards use 12px
                 padding below sm and 16px above, preserving the two-up 320px treatment.

Data notes strip <DataNotes> — hairlines above and below a native details disclosure on the page
                 ground, below the KPIs. The title uses primary ink; counts use the data face, with
                 review counts in warning ink and every count beside its relevant note letters. When all
                 populated figures passed, “No figures need review” and a neutral checked count (in the strip's own ink: sage never colours a number, D-030) remain
                 independent of concerns on comparisons. Unknown validation,
                 unavailable and calculated counts remain separate. Expanded notes use two columns:
                 the letter, then its reason, affected metric/periods and distinct comparison counts.
                 Per-basis locators count actual latest-available headline membership, the revenue
                 or net-interest-income numeric YoY chart, and the table's QoQ-else-YoY fallback or
                 annual window column. Headline and locator membership share one selection helper.
                 A narrowed table window adds the number currently shown without changing distinct
                 report totals or counting repeated appearances. Annual window comparisons retain
                 their recorded range. Dataset-free citation supplements and illustrative sample notes
                 make no report-surface claims.
                 Existing Sources & methods prose, source date and snapshot reference stay inside.
                 Note chips reveal and focus the same stable note ID. Citation-only supplemental
                 notes remain in the narrative and do not increase the report's figure counts.
                 formatAnalysisPeriod formats quarters as Q2 2026 (Q2 ’26 in compact contexts);
                 FY2026 and all API/snapshot/selection keys retain their original identity.

Solid chip       <Badge variant="solid">  — the primary colorway as a chip (brand.strong fill +
                 white label; dark: NAVY ink on brand.dark) for brand-weak TINTED grounds where the
                 tint chips vanish. <Badge variant="info"> = the info STATE tint
                 (light label ink = info.text), never a form category: a form code (10-K, 10-Q, 6-K …)
                 is text in the data face, never a Badge and never a hand-rolled eyebrow chip (uppercase
                 tracking-eyebrow around the code, its class written inline or held in a same-file
                 constant; gate: earningsnerd/no-form-code-badge, eslint.designRules.mjs);
                 <Badge variant="warning"> = warning tint
                 (replaces raw-amber hand-rolls; "Superseded"). Badge's status set, BadgeStatusVariant
                 (<Badge variant="success|error|info-status|warning-status|neutral-status|tentative">) = a
                 STATUS chip (a summary is ready, a run failed, an invite pending): the status ink on the quiet
                 ground, since the success ink inside any tint of itself falls under 4.5:1 at 12px. info, warning
                 and neutral are the tints and the quiet chip, so their status forms take names of their
                 own. In dark the chip carries no fill, its hairline only, so a hovered row's white/5 is the
                 one layer under it: error-dark holds 4.6:1 there, where a fill of its own would take it to
                 3.9:1 (gates: tests/unit/badgeVariants.spec.tsx, success and error on the card and on a
                 hovered row; tests/unit/statusChipContrast.spec.ts, the whole set on the admin rows and the
                 summary status chip on the watchlist and dashboard rows, Status chip below). `tentative`, the
                 set's sixth, is a status not yet settled (the calendar's
                 estimated date, "Est."): neutral-status's ink on the hairline, dashed, with no fill in either
                 theme. A chip's ground, ink and hairline are its variant's: a class on top of a variant's
                 (`bg-transparent` over its `bg-white`) wins or loses by stylesheet order, since cx does no
                 tailwind-merge, so the "Est." chip, the neutral chip with that class, painted as a white pill,
                 and on a hovered dark row its white/5 took the label to 4.27:1 (E83). On the calendar's rows
                 the tentative label holds 5.21:1 at rest and 5.44:1 hovered in light, 5.78:1 and 4.98:1 in
                 dark. Gates: tests/unit/badgeVariants.spec.tsx (tentative is neutral-status's ink on a dashed
                 hairline with no fill under any variant; the calendar's status ladder, "Est.", "Confirmed"
                 and "Reported" as the week sheet, the day list and the day dialog render them, is tentative,
                 info-status and neutral-status class for class (Status chip below), each label measured on
                 its row at rest and hovered in both themes, the grounds read up from the rendered chip; and
                 no <Badge> in app/, components/ or features/ sets a ground, an ink or a hairline in its
                 className, any bg- or border utility or a text- colour, read through cx() and conditions and
                 templates, where an interpolation glued inside a class token (`text-${tone}-text`) is joined
                 from its string values or the className is unreadable; a className it cannot read or a
                 spread fails too).
                 beat/miss are the
                 earnings-surprise direction with their ▲/▼ and never tell a status (gate:
                 tests/unit/badgeVariants.spec.tsx, with no row exempt). `new` is the brand tint, `brand`'s
                 own classes (bg-brand-weak text-brand-strong and the sage hairline, dark pair), with a pulse
                 dot in that sage ink, static under reduced motion (D-032): a new filing is news, not a
                 caution. Its label holds 5.8:1 in light and 5.9:1 on the dark card (6.1:1 pressed); its one
                 use, the dashboard's What changed "New", strips the dot. Gates: tests/unit/badgeVariants.spec.tsx
                 (its classes equal brand's, the dot in its ink, the label on the interactive Card at rest and
                 pressed in both themes) and tests/unit/designSnapshotParity.spec.ts (DESIGN.md's badge-new
                 paints what the variant paints).

Checkbox         <Checkbox size="sm|md">  — the one checkbox (consent dialog, admin invites); never a raw
                 <input type="checkbox">. Checked: light brand-strong under the forms plugin's white
                 check (6.6:1); dark the Primary's recipe, brand-dark (6.1:1 on panel-dark) under a navy
                 check (7.8:1), drawn by `dark:checked:[background-image:var(--check-navy)]`, the
                 plugin's check path in #0B1120 declared in app/globals.css (white on brand-dark would be
                 2.4:1). Each fill is stated as `checked:bg-*` because a `dark:bg-*` ground outranks the
                 plugin's checked fill; the unchecked edge is the flat ink (4.6:1 / 5.8:1 on panel).
                 Gate: tests/unit/checkboxRecipe.spec.tsx (the check read from the stylesheet; the dark
                 state equal to the Primary's dark fill and label ink).

Toast            Sonner's Toaster, rendered by ThemedToaster (app/providers.tsx) with the theme from
                 ThemeProvider (never "system", which reads the OS setting, not the site's toggle) and no
                 richColors, for good: status shows in the icon only, the Separate Signals Rule applied
                 to a toast. Every toast is a panel card: border-border / bg-panel / primary ink, shadow-e4
                 light (the ladder's overlay step, as the popovers) and none in dark, each with `!` because
                 Sonner's two-attribute surface rules outrank a utility; the description is secondary ink;
                 a status toast (success, error, warning, info) keeps the panel and colours only its
                 icon, in its status ink. The close button
                 rests on the panel in secondary ink, and its hover takes `!` as its rest does (Sonner's
                 own hover loses to a forced rest): the quiet controls' tint (hover:!bg-brand-weak) with
                 the primary ink in light; in dark the primary ink over the panel it keeps, since the
                 button overhangs the card's corner and a translucent tint (brand-weak-dark) would show
                 the page through it. Gate: tests/unit/toastTokens.spec.tsx (token classes only; the
                 card's e4 and dark none; the close button's hover, forced, on opaque fills).

Status chip      A row's status pill (admin InviteStatusBadge, FeedbackStatusBadge): icon + label, a
                 <Badge> of its status set (components/ui/Badge.tsx, BadgeStatusVariant; the Badge entry
                 under Solid chip): pending and new on info-status, used and resolved on success, expired
                 and triaged on warning-status, revoked on neutral-status, the icon in Badge's `icon` slot.
                 The calendar's status ladder (StatusChip in EventRow, a label alone) is a status, so every
                 rung takes the set (E141): "Est." on `tentative`, the set's sixth, a date not yet settled,
                 with no fill in either theme, so the row is its ground (on the admin rows 5.21:1, and 4.90:1
                 under their cream hover, in light; 5.78:1 and 4.98:1 in dark); "Confirmed" on info-status, a
                 firm, upcoming date and the rung a reader scans for (not success, whose light ink is
                 gain.text's #15803D, the ink a reported row's beat prints in, and not the brand tint, which
                 is brand and activity); "Reported" on neutral-status, the event over, its EPS figure carrying
                 the news. It reads dashed, blue, quiet. On the calendar's rows, at rest and hovered, light
                 measures 5.21 and 5.44:1 (Est.), 6.70:1 (Confirmed) and 5.44:1 (Reported), dark 5.78 and
                 4.98:1 (Est. and Reported) and 5.77 and 4.97:1 (Confirmed). Before, Reported was the quiet
                 chip (10.31:1 in light; in dark its white/5 fill stacked on the hovered row's, 4.27:1) and
                 Confirmed the brand tint (5.77:1 in light, 5.93 and 5.14:1 in dark).
                 The status INK sits on the quiet ground, never the status tint. Light labels measure 5.0
                 to 7.1:1 on the white chip. Dark carries no fill, so the row's white/5 hover tint is the
                 only layer: the four the admin chips use hold 5.77 to 6.83:1 at rest and 4.97 to 5.89:1 on
                 a hovered row, and error, the set's fifth, 5.31:1 and 4.57:1 (a quiet white/5 fill on the
                 chip as well would drop error-dark to 3.92:1 there, info-dark to 4.26:1 and the neutral
                 ink to 4.27:1). The old recipe, info-light in its own 10% tint, is 4.32:1. The chips take
                 Badge's metrics, 600 with a 6px gap where the hand-rolled recipe was 500 with 4px, and
                 Badge's whitespace-nowrap, which the status cells already set: each chip is 2.2 to 2.7px
                 wider (4.4 to 5.4px under 200% text), one line, inside its cell at 1440 and 390px and at
                 390px under 200% text, and no page scrolls sideways (the tables scroll in their box,
                 Admin pages below). FeedbackTypeBadge, the neutral type chip beside the status chip in
                 FeedbackRow, takes Badge's metrics too (600, a 6px gap, whitespace-nowrap), so the row's
                 two chips share one weight, and keeps a ground and an ink of its own: its light ground
                 (black/[0.04]: 9.04:1, 8.50:1 hovered), and the status set's dark one: no fill, its
                 white/10 hairline kept, text-secondary-dark at 5.78:1 at rest and 4.98:1 on a hovered row
                 (its old white/5 fill measured 4.27:1 there).
                 The summary status chip (SummaryStatusBadge: the Watchlist insights cards and the
                 dashboard's "Your companies" rows) is a label alone on the same set: Ready on success,
                 Generating on info-status, No summary yet and Pending on neutral-status, Unavailable and
                 Needs regenerating on warning-status, Error on error. Both rows sit on Card's panel fill
                 with no hover fill of their own, so a label reads the same at rest and hovered: light 5.02
                 (Ready) to 7.09:1 (warning-status), dark 5.31 (Error) to 6.83:1. Before, Unavailable and
                 Needs regenerating took the warning tint (5.83 and 5.22:1, no hairline, so 2px shorter than
                 the chips beside them), No summary yet and Pending the quiet chip (10.31 and 4.98:1: the
                 neutral-status ink is the tertiary one, 5.44:1 in light, and dark drops the white/5 fill,
                 5.78:1), and Generating the brand tint (5.77 and 5.93:1, now 6.70 and 5.77:1).
                 What each member means, read from its uses so far (chief design on #1459), so a new status
                 chip lands on the member its state means: `info-status`: active or upcoming (an invite
                 pending, new feedback, a confirmed date, a summary being written); `success`: done (an invite
                 used, feedback resolved, a summary ready); `warning-status`: needs the reader (an invite
                 expired, feedback triaged, a summary unavailable or needing regenerating); `error`: failed (a
                 summary whose run failed); `neutral-status`: not started, over or not known (an invite
                 revoked, a reported date, no summary yet, a summary status the chip does not know);
                 `tentative`: not yet settled (an estimated date).
                 tests/unit/badgeVariants.spec.tsx holds this line to the set read from Badge's source, each
                 member named once; which member a new chip takes is review-checked.
                 Gate: tests/unit/statusChipContrast.spec.ts (every member of BadgeStatusVariant, six, read from
                 Badge's source and rendered through Badge, on both tables' rows, at rest and hovered, both
                 themes, the grounds read from InviteRow's and FeedbackRow's <tr> and the pages' <tbody>;
                 every layer between a chip and its <tr> read too, and a cell or wrapper there carrying a
                 bg- class fails; a chip colour under any variant but its theme's own (hover:,
                 focus-visible:, dark:hover:) and an opacity below 100 on the chip, a layer, the <tr> or the
                 <tbody> fail too; both badges held to the set, every status a chip Badge rendered for one
                 member with no class added and nothing on it or inside it that paints (a class inside but
                 the icon's size, an inline style, an SVG fill or stroke that is not currentColor), so a
                 hand-rolled chip, a copy of Badge's classes included, a tint, an added class or a label in
                 a tint of its own fails; the type chip measured as it renders on FeedbackRow's grounds, and
                 held to Badge's metrics: every class of Badge's BASE, with only a ground and an ink of its
                 own beside them, so a weight, a gap or a size of its own fails; and the summary status
                 chip: every chip summaryStatusBadge() returns, for each member of SummaryStatusKind read
                 from its source and for a prefix it does not know, with and without needs_regeneration,
                 rendered through Badge and measured on both rows at rest and hovered, both themes, the
                 grounds read from each row's source up to its <Card>, rendered as Card renders the props
                 written on it: the row is the element carrying the list's key (the watchlist's Card
                 itself, the dashboard's row <div> inside its Card), its tint at rest and hovered read over
                 the card's fill, and every other layer paints nothing; two fills under one variant fail,
                 since the stylesheet's order decides which paints (a fill written on the <Card> sits beside
                 Card's own: Card joins classes without merging them); every tracked source outside tests/
                 that can render the chip is one of the two rows; SummaryStatusBadge held to the set as the
                 admin badges are, rendering the variant summaryStatusBadge() returns).

Admin pages      A list's table (/admin/invites, /admin/feedback) scrolls inside its card, never the page, in
                 TableScroll (features/admin/components), a `relative overflow-x-auto` box. `relative` makes it the
                 containing block of what the rows position absolutely, their `sr-only` labels included, which were
                 laid out against the page, outside the box's clip (FeedbackRow's took the page to 1090px at 390).
                 While the table is wider than the box, "Scroll horizontally to read all columns." sits above it and
                 the box is a named region in the Tab order ("Scrollable table: <the card's title>", the brand ring),
                 through useOverflowRegion, as in SummaryBlocks' GenericTable. FeedbackRow's message column takes the
                 width the others leave (`w-full` on its cell; the button's intrinsic width contained, with a 16rem
                 floor), so the status select keeps its own at 1440. The reporter's address is never cut: it keeps
                 its own width up to 14rem and wraps inside that past it (`w-max max-w-[14rem]` and
                 `[overflow-wrap:anywhere]` on a block in the From cell; the message column holds the other columns at
                 their narrowest, so wrapping the cell itself broke a short address every few letters), and the table
                 keeps to its box at 1440 with a 50-character address (a nowrap cell took it to 1264px in 1214px).
                 Gates: tests/unit/admin-invites-page.spec.tsx and tests/unit/admin-feedback-page.spec.tsx (the box,
                 the cue while the table fits and while it overflows, the message column, the From cell) and
                 tests/e2e/admin-invite-chip-reflow.spec.ts (at 1440 the table inside its box with a 50-character
                 address shown whole, a short one and "Anonymous" on one line each). The section nav
                 (app/admin/layout.tsx) wraps its tabs (`flex-wrap`):
                 an unwrapped row took the page to 443px at 390 under 200% text. Gate:
                 tests/unit/admin-layout.spec.tsx. Each card header's filter row is a `min-w-0` flex item that wraps
                 its fields: a row that could not shrink took /admin/feedback to 336px at 320 under 200% text (its
                 255px status select in a 158px header). A select capped at the card there clips its closed face, as
                 the metric pickers' does (E34), and its open list shows every option whole. Gates:
                 tests/unit/admin-feedback-page.spec.tsx (the class) and tests/e2e/admin-invite-chip-reflow.spec.ts
                 (the page at 320px, at the default size and under a 200% root). An email chip (EmailChipsInput)
                 puts its address and the "already invited" marker in one `min-w-0` wrapping group: when they do not
                 fit on a line the marker goes under the address, which truncates, and the remove button stays the
                 chip's last child, inside the card (a marker that could not shrink squeezed the address out at 200%
                 text and pushed the button past the card). Its 16px radius (`rounded-xl`) is a pill on one line and
                 a rounded box once it wraps, as SourceTrace's chip. The chip row is an inline-size query container,
                 and below 8em of its own text size (`[@container(width<8em)]:`) that group is too narrow for
                 "· already" (the dot is held to its word by a no-break space), so the group dissolves (`contents`),
                 the chip wraps with no row gap and the address takes the first line whole (`order-first
                 basis-full`), wrapping anywhere (`whitespace-normal [overflow-wrap:anywhere]`) instead of
                 truncating: beside the remove button it kept 52px at 320px under 200% text ("al…", "bo…", a bare
                 "n" for an invalid address), too little to tell the chips apart. The marker, the invalid glyph and
                 the remove button follow on the lines under it. The marker is `flex-1`, so it wraps "invited" under
                 "· already" to give the button its line wherever both fit (390px under 200% text; at 320px the
                 button takes the line under the marker), and it never paints over the button (at 320px under 200%
                 text it once ran across it). The button keeps its 48px and its ring and ends the chip on whatever
                 line it lands (`ml-auto`), as it does above 8em. An invited chip needs about 9.6em on one line, so
                 the narrow state never splits a chip that fits; at the default size it starts at a 128px row, so a
                 chip that fits keeps the one-line pill from 320 up (a short address at 320, whose row is 14.9em, and
                 alice@example.com at 390 and 1440). Reading and Tab order stay address, marker, button. The em is
                 the text's actual size however it is enlarged (a media query's rem is only the browser's text
                 setting), as in the Analysis KPI strip. Gates: tests/unit/admin-invites-page.spec.tsx (the classes)
                 and tests/e2e/admin-invite-chip-reflow.spec.ts (what they paint at 320, 390 and 1440px, at the
                 default size and under a 200% root, in both themes, every address whole and every remove button
                 ending its chip at 320 and 390px under 200%, a short chip on one line at 320px at the default size,
                 and at every 10px from 320 to 480px under 200%).

Inline notice    <Notice variant="error|info|success">  — compact icon + title + message + action
                 for form/auth flows and in-card states (role="alert" on error; action slot takes a
                 small Button). GuidanceCard is a STANDALONE centered panel — never nest it inside a
                 Card; inside a Card, Notice is the right scale. Both action rows wrap: GuidanceCard's
                 centres two actions and sets the second under the first when they do not fit side by
                 side, and its description, like a Notice's, breaks a long word
                 (tests/unit/twoActionsWrap.spec.tsx). A Notice's own row wraps: its text column's
                 basis is 9rem (about 20 characters: 144px at the default size, 288px under 200% text),
                 so where it cannot keep that beside the glyph (a card on a phone at 200% text) it goes
                 under the glyph at the Notice's whole inner width. The glyph then sits alone at the top
                 left over the title, and the title, description and action share the full width; the
                 title breaks a long word, as the description does. No container query: a
                 container-type would collapse a Notice wherever a parent sizes it to its content. Gate:
                 e2e reflow-200.spec.ts (the Retry and every text run inside the Notice's border).
                 A Notice or GuidanceCard title is one phrase, no semicolon (gate: noticeTitlesAreOnePhrase.spec.ts).

Search field     <Input icon={<Magnifier/>}>  — leading glyph with an explicit pl-11 inset (px-3.5 +
                 a pl-11 override is Tailwind conflict-order-dependent — don't). Raw fields:
                 inputClasses({ leadingIcon: true }). A raw search field with a busy state (v3.4) reserves
                 the trailing inset always, inputClasses({ leadingIcon: true, trailingIcon: true }), marks the
                 input aria-busy and renders {busy && <FieldSpinner />} (16px, right-3), as <Input loading>
                 does. Never a 20px glyph at right-4 over the 14px inset (it covered the last 17–21px of
                 typed text), and never an inset that follows the busy flag: when the padding grows the caret
                 stays put, so a long query loses its end under the spinner. A "/" shortcut hint sits at
                 right-3 inside the same inset. Gate: tests/unit/inputClassesNoOverrides.spec.tsx.

Password field   PasswordField  — raw input + inputClasses({ trailingIcon: true }) (v3.3): an explicit pr-10
                 (40px) trailing inset for the reveal toggle at both densities (pr-10 on top of the field's
                 px-3.5 is conflict-order-dependent too). Sized for a control of at most 16px whose outer edge
                 sits 12px in (right-3, or right-0 with pr-3): it spans 12–28px from the edge, 13px before the
                 text. Combines with leadingIcon; a select takes neither inset (its chevron holds that side).

Search option    <CompanySearch> results (2026-10 critique 1d) — an option is the company (name 14/600, then
                 ticker · exchange in the data face, today's quote at the right only when the search returned
                 one: never a "Loading price..." that cannot resolve) over the filing identity strip of the
                 filing a pick lands on: "Latest 10-K · fiscal year ended … · filed … · summary ready" (the
                 search's `latest_filing`, backend latest_filing_service: the company list's forms, newest
                 that still stands). The listbox holds options only; the count and the "↑↓ to move · ↵ to
                 open" hint sit under it, aria-hidden, the hint from sm up.

Chat composer    <Textarea variant="composer">  — transparent, auto-growing, chrome-free field; the
                 app-owned shell carries inputClasses({ shell: true }) (v3.7): the field's tone with its
                 focus border and ring keyed to focus-within, the border restated under hover
                 (`hover:focus-within:border-brand`, both themes), since Tailwind emits focus-within before
                 hover and the hover border won while both held (never double chrome). Gate: rule (f) in
                 tests/unit/inputClassesNoOverrides.spec.tsx.

Semantic card    <Card as="section">  — same recipe on a semantic element.

Segmented ctrl   <SegmentedControl label options value onChange size="sm|md|adaptive" fullWidth>  — v3.1, the
                 ONE single-choice toggle group (lifted from the calendar's Week/Month switch; the calendar
                 and the filings form filter both use it). role="group" of <button aria-pressed> — every option
                 is visible, so not a radiogroup/tablist. Shell = panel + hairline + e1, rounded-lg, p-1;
                 segment rounded (8), 600 weight — 12px labels at 26px (sm; adaptive from sm up), 14px at 36px
                 (md; adaptive below sm); selected = the primary colorway (bg-brand + white; dark NAVY ink on
                 brand-dark). sm 26px · md 36px · adaptive 36px below sm, 26px from sm up. The 26px height is
                 1.625rem, so it scales with the root and holds its label at 200% text. `mono` options set
                 codes (10-K) in the data face. One selected colour per group — never an ink fill for "All".
                 `fullWidth` stretches the segments across a phone row and wraps them onto another row when
                 they do not fit (a form filter with amendments), so every option stays visible; from sm up
                 it is one auto-width row. Optional disabled options remain visible and use native
                 disabled semantics by default. `focusableDisabled` keeps unavailable options in
                 the Tab order with aria-disabled and `descriptionId`; activation is refused.
                 The controlled selected option keeps its primary colourway even if unavailable,
                 so newly loaded coverage never silently changes the selected mode. This is not
                 a busy-state API.
                 A long option set is not a segmented control: the company page's peer and trend
                 metric pickers (nine and up to 23 options) are a raw compact select beside a visible
                 "Metric" label, inputClasses({ select: true, density: 'compact', autoWidth: true }),
                 options in sentence case; the insider window (three codes) keeps the control. At a
                 32px root (200% text) on a 320px screen the select is capped at the card's inner width,
                 so its closed face clips the name ("Revenue" shows four letters); the open list shows
                 every name whole and nothing overflows (E34).
                 A mark a reader can clear is not one either: the wording review's Reviewed and
                 Follow up (WordingChanges.tsx) start unset and a second press clears them, so they
                 stay a pair of aria-pressed toggles in a labelled group, behind the rule's disable on
                 that line with its reason (D-046).
                 Gate: earningsnerd/no-hand-rolled-toggle-group (eslint.designRules.mjs) fails a
                 role="group" holding an aria-pressed <button> or <Button>, anywhere outside
                 components/ui/SegmentedControl.tsx. It reads the button in the group's own markup,
                 through a same-file wrapper component (one level) and through the DS Button imported
                 under another name. WordingChanges' review row (LabelToggle) carries the rule's one
                 disable: a second press clears its label, a state the control cannot hold (D-046). A row
                 without role="group" (FeedbackWidget's type row, E35), a wrapper imported from another
                 file and a wrapper that renders another wrapper are outside its reach (review-checked).
                 Gate: tests/unit/segmentedControlOptionCount.spec.ts fails a SegmentedControl given
                 more than five options (MAX_SEGMENTS, which the primitive exports), and pins a site it
                 cannot count statically (FilingIndex's form filter). FilingIndex counts that set, All
                 plus the company's forms, at run time and renders it past five as the toolbar's compact
                 select (the year filter's Select, density compact), so no SegmentedControl ever shows
                 more than five.

Index list       <FilingIndex> (features/filings/components) — the recipe for a list of primary documents:
                 ONE surface (the section Card), hairline rows and year groups (DataTable manners: hover
                 bg-white / dark:bg-white/[0.03], never darker), no stripes, no row tints, no per-type colour,
                 no per-row document icon (the md-up caret in the actions track is an aria-hidden navigation cue,
                 not a type signal). One grid template for the column header and every row (form · period ·
                 filed · actions) so values align across groups. The row is ONE <Link>, named by its own
                 content (no aria-label); a secondary target (EDGAR) is a SIBLING anchor absolutely placed in
                 the actions track — never an <a> inside the row link. 48px rows from md, 64px two-line rows
                 on phones with a 44px EDGAR square. Group headers are <h3><button aria-expanded
                 aria-controls>; collapsed lists stay in the DOM with `hidden`. One primary action per screen,
                 and on the company page it is the lead's (Company identity, below): the list only marks the
                 latest row "Latest", and rows never carry a primary button. Choosing a year filter opens
                 its group. Skeleton = the ledger's own tracks; errors = Notice + RetryButton in place.
                 Gate: a `border-l|s-(2|4|8)` side stripe on a rounded box is lint-banned
                 (earningsnerd/no-side-stripe, eslint.designRules.mjs).

Dialog           <Modal open onClose labelledBy="<id>" size="sm|md|lg" dismissible initialFocusRef>
                   <ModalHeader id="<id>" onClose icon={…?} tone="brand|success|warning|error">Title</ModalHeader>
                   <ModalBody>…</ModalBody>
                   <ModalFooter>…<Button>s (className="w-full sm:w-auto")</ModalFooter>
                 </Modal>
                 The ONE dialog primitive (v3, DS-04): portal to <body>, bg-overlay + z-modal scrim with
                 backdrop-blur, Card recipe at rounded-2xl, focus moves in on open (initialFocusRef ?? first
                 focusable ?? panel), Tab/Shift-Tab cycle inside, Escape closes when dismissible, focus RETURNS
                 to the opener, body scroll locked. The panel never outgrows the viewport: it stops at the
                 scrim's inset and scrolls inside, with scroll padding equal to its p-6 inset so a control
                 scrolled in by focus lands its ring clear of the edge; callers never size its height.
                 Destructive confirms use variant="destructive" and stay
                 dismissible. The trap arms once per open (onClose is read through a ref), so inline
                 callbacks are fine. The TOP open dialog owns Tab/Escape (window-capture listener), so a
                 dialog over the copilot sheet never lets a key reach the sheet — and content inside a panel
                 cannot handle Tab/Escape itself. The header icon tile takes the dialog's tone: brand for a
                 neutral prompt, a status hue for a state glyph (brand never signals a state).
                 The header's icon and title are one group that wraps beside the ✕, as a Notice's glyph and
                 text column do (Inline notice): the title's basis is 9rem (144px at the default size, 288px
                 under 200% text), so where it cannot keep that beside the icon (a phone at 200% text) it goes
                 under the icon at the group's whole width, the column gap below it (gap-y-1 and the title's
                 pt-2). The ✕ keeps its own column, the row's last control at the top right: the title never
                 sits under it or runs past the panel, and it breaks a word only when the word is wider than
                 the group (at 320px under 200% text the email verification prompt's title has 94px, so
                 "Verify" breaks). At the default size nothing moves: at 1440 and 390px the icon, the title
                 and the ✕ keep their boxes, in both themes. Before, at 390px under 200% text, the icon and the
                 ✕ left the title 60px: "Cookie preferences" painted under the ✕ and 26px past the panel's
                 edge, and "Verify your email to continue" under the ✕. No container query, as for the
                 Notice. Gate: e2e reflow-200.spec.ts (the consent dialog and the email verification prompt
                 at 390, 360 and 320px: the title beside the icon at the default size and under it at 200%
                 text, every painted line inside the panel and left of the ✕, a word broken only when it is
                 wider than the title, the page not scrolling sideways, nor the prompt's panel).
                 Dialog semantics ship only through Modal plus the documented bespoke layers: the copilot rail /
                 viewer / workspace sheets and SourceTrace (role="dialog"; the workspace shell is a dialog only
                 below lg, where it is a sheet, and a complementary landmark on lg+), and the calendar's
                 DayDetailDialog, a
                 sanctioned native <dialog> + showModal() that keeps the native top layer. Gate:
                 tests/unit/dialogAllowlist.spec.ts reads the TypeScript AST and pins each allowlisted file, with
                 a reason, to its count of each kind — a dialog/alertdialog role (literal, any value of a role={…}
                 expression, role: prop or setAttribute), a native <dialog>, and the dialog layer's own tokens
                 (z-modal, bg-overlay), so a role-less hand-rolled modal fails too. The list is shrink-only.
                 Never raise Modal from the calendar page: any layer it raises can sit over DayDetailDialog, and
                 under showModal() a <body> portal is inert and painted beneath the top layer. Nor give the day
                 <dialog> a transform/filter/contain/will-change or a non-opacity animation: it would become the
                 containing block that clips the popovers portalled into it. Both are gated in the same spec.

Popover          An anchored, light-dismiss surface that explains one control (the calendar's BellPopover) is
                 NOT a dialog: it makes nothing inert, traps nothing and locks nothing. No dialog role — a
                 role="group" named by its title and described by its message (an async failure is also
                 announced with role="alert") — on z-overlay, behind a transparent catcher so
                 an outside press closes only the popover; the panel is the Card recipe (dark:shadow-none).
                 Placed where it fits, from its measured height, never an assumed one: 18.75rem wide (300px
                 at the default text size) within 12px of the visible viewport (window.visualViewport: on a
                 phone whose page is wider than the screen, Chromium widens the layout viewport and
                 window.inner* to the page), below its trigger, above it when only that side holds it
                 whole (capped at its own height, so text that grows scrolls rather than reach over the
                 trigger), otherwise on the roomier side with its height capped there, scrolling inside
                 (overflow-y-auto, scroll-py-4); a trigger out of view leaves it inside the area too. When
                 neither side offers 6rem of the reader's text (96px at the default size; a landscape phone
                 at large text, or with the keyboard up), it spans the visible height over its trigger and
                 scrolls inside, the one placement that covers the trigger: a side that short would show
                 little more than the panel's padding. Gate: placeBellPopover's cases and the rendered
                 placement and width cases in BellPopover.spec.tsx (the width read at a 16px and a 32px root).
                 Keyboard: focus moves to the first action, without scrolling the page (a capped panel
                 scrolls itself to show that action and its ring), unless the user already moved it
                 elsewhere (armed once per open, callbacks through a ref); Escape closes in window capture
                 with preventDefault (stopPropagation alone still closes a native <dialog> beneath); Tab
                 past the last action / Shift+Tab before the first close it and resume the page's order at
                 the trigger; a scroll that moves the trigger, or a resize, closes it (fixed at its rect,
                 it would detach; the page scrolling behind a fixed dialog does not move it); every close
                 returns focus to the trigger unless the user moved on. While a native <dialog> is open, it
                 portals into it.
                 The evidence popovers (SourceTrace's "Source detail", CitationChip's citation card) are the
                 hover/focus variant of this contract: they open on hover or focus, so focus stays on the chip
                 until the user asks for more, and the same hand-off applies from there — Tab on the open chip
                 moves to the popover's link, Tab past it closes the popover and resumes the page after the
                 chip, Shift+Tab returns to the chip, Escape closes the popover alone and refocuses the chip
                 when focus was in the popover (a hover-opened one leaves focus where it is) — taken in window
                 capture, so the research pane or sheet beneath stays open until the next press
                 (`useEvidencePopoverKeys`, gated by tests/unit/evidencePopoverKeys.spec.tsx). A key typed
                 inside a modal layer that does not hold the chip is that layer's: SourceTrace's popover
                 leaves Escape to the copilot sheet a narrowed window turned the pane into
                 (tests/unit/SourceTraceEscapeLayer.spec.tsx). On the filing page a chip's activation is the
                 in-app jump: it opens the research pane on the Filing tab (the pane never stays silently
                 closed); an answer's [n] chip activated by the keyboard, which that switch hides with its
                 panel, hands focus to the selected Filing tab rather than to <body> (a pointer's click leaves
                 focus to the pointer) (FilingWorkspace; a chip outside the pane keeps or never takes focus,
                 as the browser decides); SourceTrace alone has a sheet, which a coarse pointer opens instead,
                 carrying "Show in filing" beside the EDGAR link. A chip that is itself the EDGAR anchor
                 (SourceTrace without a viewer, as on the landing demo) has no second stop, so Tab leaves it
                 as usual.

Stacking         z-sticky 30 (in-page sticky chrome) · z-consent 32 (the cookie-consent bar: above in-page
                 sticky chrome, BENEATH the sheet scrims and the z-40 research chrome) · z-scrim 35 (the
                 workspace / rail bottom-sheet scrims: above the bar, under the z-40 sheets they belong to) ·
                 z-header 50 (site header; its menus ride it: the notification menu and the account menu
                 sit on this one rung inside the header's stacking context, NotificationBell on the token
                 and UserMenu still on the numeric z-50; tests/unit/NotificationBell.spec.tsx holds both) ·
                 z-overlay 60 (popovers incl. BellPopover, the selection pill) · z-modal 70 (dialogs + the
                 source and viewer sheets — scrim AND panel) ·
                 z-toast 80 (the skip link; sonner manages its own toast layer).
                 The copilot rail / workspace bottom sheets stay z-40 over z-scrim scrims, so the in-sheet
                 citation popovers (z-overlay) still sit above them. Never z-[N]; DataTable's internal z-[5]
                 sticky-cell layering is the one documented exemption.
                 The header offset: the site header publishes its rendered height on <html> as
                 `--site-header-h` (components/Header.tsx), the one offset under it. Sticky and fixed chrome
                 below the header and every section's scroll margin read it, `top-[var(--site-header-h,4rem)]`
                 or `scroll-mt-[calc(var(--site-header-h,4rem)_+_4rem)]`, never a fixed `top-16`, so a bar that
                 wraps under enlarged text covers nothing. Gates: tests/unit/headerOffsetReadsTheVariable.spec.ts
                 and tests/e2e/reflow-200.spec.ts (the filing page's section nav at 200% text).
                 The open mobile menu scrolls inside the viewport: the header is a column no taller than it
                 (`flex max-h-dvh flex-col`), the bar keeps its own height (`w-full shrink-0`; a column's child
                 with auto side margins is not stretched) and the menu panel takes the rest
                 (`overflow-y-auto overscroll-contain`, its scroll padding the nav's inset, as the Modal
                 panel's). The cap is the bar's own height, never `--site-header-h`, which counts the open
                 menu. A sticky header taller than the viewport stays stuck to its top until the page's end,
                 so the menu's last rows (Log out, the account link) showed only there, 36,942px down the
                 landing at 200% text. Gate: tests/e2e/reflow-200.spec.ts (390x664 and 360x640 at 200%,
                 a guest and a signed-in reader: a wheel and focus bring the last row into view inside the
                 menu, a second wheel at its end leaves the page behind it unmoved, and neither the page nor
                 the menu scrolls sideways; the menu's own scroll width is read, since a row it clips adds
                 nothing to the page's), and at 1440x900 the bar spans its container with the logo in its
                 top-left place, which `w-full` holds.
                 The consent layer: a lower z alone would let the launcher cover a consent choice, so while
                 the bar is mounted CookieConsent publishes its height on <html> as `--consent-inset` plus
                 `data-consent-visible` (lib/consentLayer), and every bottom-anchored layer above it adds the
                 inset to its bottom offset — the Ask and feedback launchers and the coachmark through
                 `BOTTOM_CHROME_OFFSET`, the workspace / rail sheets through `bottom-[var(--consent-inset,0px)]`
                 (and the same subtraction from their vh cap), the desktop pane's sticky height likewise, and
                 the document's `scroll-padding-bottom` (globals.css) reserves it so a focus or scrollIntoView
                 never lands a control behind the bar. The desktop source pane measures its actual top
                 before and after it sticks, so its footer and composer fit without scrolling the page. The
                 coachmark is deferred, not dismissed, while the bar shows (`hooks/useConsentLayer`); the
                 saved confirmation is a sonner toast, never a fixed corner element. Real modals cover the
                 bar: beneath the settings dialog (z-modal) and beneath an open workspace / rail bottom sheet
                 (whose z-scrim scrim dims it) its choices are inert — a tap there reaches the scrim and
                 closes the sheet, storing nothing — and operable again once the modal closes, which is what
                 the sheet's aria-modal and focus trap already tell keyboard and AT users. In-page sticky
                 chrome stays below the bar: a section nav passing through the bar's region on a short phone
                 must not paint over a choice. The site header (z-50, top-anchored) stays above it: on a
                 short phone (320x568) its open mobile menu reaches the bar's region and covers a choice
                 until the user closes the menu (user-opened, user-closed; before, the bar covered the menu's
                 lower items instead). On a 390x844 phone a signed-in reader's open menu, with the Search and
                 Calendar links, ends just above the bar and can cover the Ask and feedback launchers until it
                 closes, since the header outranks them too (tests/e2e/consent-bar-yields.spec.ts).
                 New fixed bottom chrome joins this band, never above it: a floating control takes
                 `BOTTOM_CHROME_OFFSET` (a sheet takes `bottom-[var(--consent-inset,0px)]` and subtracts the
                 inset from its vh cap) and is pinned in the gate with its reason — the pin list is
                 shrink-only — while a transient confirmation is a sonner toast and a second bottom bar is a
                 documented ladder change, not a z-50.
                 Gate: tests/unit/bottomChromeLadder.spec.ts — no fixed chrome outranks the workspace layers
                 at the launcher corner (a file with fixed chrome is held to its highest z token anywhere and
                 to inline zIndex, so a z written apart from its `fixed` still counts; z-toast is exempt only
                 as the top-anchored skip link), no in-page sticky chrome outranks the bar (the top-anchored
                 site and page headers are pinned), the tokens sit on their rungs (sticky < consent < scrim <
                 the pinned workspace level 40 < header), the pinned bottom chrome takes the inset (the sheets'
                 anchor, no `bottom-0` behind any variant, the offset objects' `bottom` from
                 BOTTOM_CHROME_OFFSET, the bar's layout-effect publish, the scroll padding) and the pinned
                 scrims are full-viewport; every pin list is shrink-only in files, sites and z.

Metric cards     <FinancialMetricsTable> below md (768px): one stacked card per metric instead of the five-column
                 DataTable, switched by CSS alone (`md:hidden` cards, `hidden md:block` table — both in the DOM
                 inside ONE wrapper so a parent's `space-y` hands neither a sibling margin; the inactive one is
                 display:none, so it adds no accessible content, Tab stop or id — never a JS media query, which
                 would SSR one layout and flip after hydration; no DataTable responsive API either, as a shared
                 one is deferred work, so the switch stays local to this component).
                 Both presentations render ONE set of field renderers (nameField / currentField / perAdsField /
                 priorField / changeField / takeawayField), each marking its element `data-metric-field`; with
                 `data-metrics-layout="cards|table"`, `data-metric-card`, `data-direction` and `data-tone` these
                 are the parity anchors the render spec, the Playwright spec and the critique harness count —
                 keep them. A card: name + XBRL chip; a `<dl>` of Current / Prior / Change (visible short labels
                 in the table's header eyebrow with an sr-only "period", so the three groups sit on one line at
                 390px and AT hears the column names; the Prior and Change groups whenever the table has those
                 columns, mirroring its cells exactly: a figure served empty or as the token alone is
                 MissingValue in the cell and in the definition alike; the change glyph inline-block and
                 aria-hidden, the string verbatim, MissingValue when the server sent none; tone from
                 `change_tone` through lib/financialTone.directionText + font-semibold for a move,
                 pinned token-for-token to DataTable's td); the per-ADS note as its own line under the figures;
                 the takeaway and its evidence chip, MissingValue read as "no takeaway" where the summary wrote
                 none (E145). Figures `font-data text-sm tabular-nums`, prose text-sm,
                 chips as they are — never smaller than the md table. Wrap contract: `[overflow-wrap:anywhere]`
                 on the card (inherited; it also lowers a flex item's min-content, which `break-words` cannot)
                 and `min-w-0` groups; never nowrap / truncate / line-clamp / a clipping height on card text —
                 long values and an unbreakable token break inside their box. Sub-surface `rounded-lg border
                 border-border-light bg-white p-3 dark:border-white/10 dark:bg-white/5` inside the section panel
                 (HeroExample's; no nested shadow). The list is `role="list"` (WebKit drops list semantics from a
                 `list-style: none` list) named by the table caption, in both caption variants. Each chip's two
                 copies share a per-instance `layoutTwin`: a source sheet or popover opened from one closes when
                 a breakpoint hides its layout (a phone rotated across 768px), and focus that was in it goes to
                 the twin now shown, never to a display:none chip (SourceTrace). The research pane a chip opened
                 returns focus the same way: its opener is read as the copy now shown
                 (`features/filings/lib/layoutTwin.ts`, through FilingViewerContext). Gates:
                 tests/unit/FinancialMetricsCards.spec.tsx (content parity, both layouts, every data variant,
                 the breakpoint close) + tests/e2e/metrics-stacked-cards.spec.ts (the hidden layout, the one-line
                 row, wrapping, the 767/768 switch, the sibling-margin pin and rotation with a sheet open in a
                 real browser).

Filing identity  <FilingIdentity filing>  (features/filings, 2026-10 critique P-04) — the filing stated once:
                 a breadcrumb to the company (focus-ringed links), the company as the page h1 with its ticker
                 in the data face (hairline pill on panel), a marker only when true (Superseded), then ONE
                 data-face line: form (font-semibold ink) · period of report ("fiscal year ended Sep 24,
                 2022", from report_date — fiscal-year labels wait for XBRL dei fields; an 8-K's report
                 date is its event's, "event date Oct 27, 2022", and its crumb names the filed date) · filed date ·
                 exchange · "Original on SEC EDGAR ↗" (sage ink, brand-hairline underline). Middots are
                 aria-hidden with an sr-only comma. No form Badge, no "AI analysis" chip. Its `children` slot
                 takes the verification tally (VerificationTallyLine): scoped counts only — "6 of 6
                 checkable figures matched the company's XBRL · 3 of 4 risk excerpts located in the filing
                 text · 1 withheld"; the check glyph only when nothing was left unmatched. Checkable = the
                 rows the server could check (`source_checkable`: a concept it maps, of at least $1M);
                 per-share figures, ratios, margins and segment lines are never counted as misses.

Section ledger   <SummaryBlocks>  (P-05/P-07) — sections sit on the page ground with no card: index + h2 (see
                 §3), body `space-y-4`, `space-y-11` between sections; the sticky TOC sits on the reading
                 side (lg+), each entry `01 Title` with the index in the tertiary ink (secondary on navy;
                 sage never colours a number, D-030); below lg the jump chips
                 carry the same index. Hairlines live inside the content (row tables: header and every row
                 close with a hairline, outer cells flush with the text edge, no outer frame). Body ink for
                 paragraphs and bullets. The change report is the section after the first metrics section
                 (`<WhatChanged bare>`): Metric · Prior · Current · Change · Read as, the change the server's
                 display string (the em dash when it sends none: a zero prior) in its TONE's ink with a ▲/▼
                 text glyph for the arithmetic direction (aria-hidden; sr-only words state it where no signed
                 string does), "Read as" = the tone in words (Favorable / Unfavorable / Neutral); below sm a
                 stacked row per metric (name + change, then prior → current + Read as), switched by CSS.
                 A quote block whose evidence the server located (`evidence.verified`) is a marked block
                 (`en-marked px-3.5 py-2.5 font-editorial text-base leading-relaxed`, primary ink, the speaker
                 in the body face, `font-sans`), with no marker and no twin, since a quote has no heading to
                 carry one (D-044); any other quote keeps the neutral hairline (border-l-2, italic, secondary
                 ink). The speaker's line wraps (`flex-wrap`), so the evidence chip drops under the speaker
                 where the line cannot hold both. Gates: SummaryBlocks.spec.tsx, brandCopyRules.spec.ts rule 3
                 (the quote blocks take the block alone), tests/e2e/risk-evidence-rows.spec.ts (the located
                 quote's face, tint and ink, its words unbroken mid-word, and each quote's words, speaker and
                 chip inside its block at 320 and 390 under 200% text).
                 A fragment the page was OPENED with (/filing/{id}#what-changed, from Compare periods) is
                 honoured once its section renders (features/summaries/hooks/useSectionArrival); later
                 renders never move the reader. Where the page has no structured summary to hold it, the
                 report is a card of its own (features/summaries ChangeReportCard): under a legacy markdown
                 summary, under a stored summary that failed, under the signup gate, and under a run that
                 ended in an error or at the monthly limit. It needs no summary, carries the same id
                 (WHAT_CHANGED_ID, exported beside WhatChanged) and lands the same way. The report's last block
                 is the Item 1A wording comparison (Wording changes, next), where the filing has one; the
                 section and its links appear on either (reportHasContent, exported beside WhatChanged).

Wording changes  <WordingChanges block Heading context>  (features/filings, E27 / PR B) — the Item 1A wording
                 comparison of the change report: the filing's own risk-factor text against the prior same-form
                 original, paired paragraph by paragraph on the backend (section_diff), rendered last in the
                 report under a 14/600 subheading one level below it ("Risk factor wording", then "Item 1A" in the
                 data face). One sentence of counts in secondary ink with `tnum` ("Against the 10-K for the year
                 ended …: 13 paragraphs changed: 8 modified, 3 added, 1 removed and 1 moved; 41 unchanged. 120
                 words added, 64 removed."), then the changes as ONE hairline list in reading order (`<ol>`,
                 `border-t`, each row `border-b py-4`): a 12px data-face label word in tertiary ink (Modified,
                 Modified and moved, Added, Removed, Moved) over the paragraph at 14/relaxed. THE REDLINE
                 CONVENTION: in a modified paragraph the later text runs in secondary ink; an inserted phrase is
                 `<ins>` underlined (`decoration-2 underline-offset-2`, 500) in PRIMARY ink; a removed phrase is
                 `<del>` struck through (`decoration-1`) in TERTIARY ink (dark: secondary); each mark opens with an
                 sr-only word ("added: " / "removed: ") so assistive tech reads the edit, and a legend line under
                 the list says what the marks mean. A whole added paragraph is `<ins class="no-underline">` in
                 primary ink, a removed one `<del class="no-underline">` in muted ink, a moved one plain: the label
                 word carries the state. Neither the brand tint (`.en-mark` means "located") nor a financial tone
                 (money direction) may mean "edited"; no color is ever the only signal. States as prose, no list:
                 nothing changed ("No wording changes against … (N paragraphs compared)."); a prior 10-Q that only
                 referred back to the annual report's risk factors ("… N paragraphs read as new."); a current
                 filing that only refers back is not shown as compared (wordingHasContent), and a block that is
                 pending, has no prior or is unavailable renders nothing. The teaser (anonymous and Free: the
                 counts and the first `entitlements.section_changes_items` items) closes with one line ("N more
                 changes in this section. Pro shows every change."), a sm primary Button "Upgrade to Pro" that
                 opens UpgradeModal (feature "Risk factor wording review") and, signed out, the text link "Already
                 Pro? Log in" to /login. Events: `wording_changes_viewed` once per form served (not while the
                 anonymous seed stands in for a signed-in reader's own read: `context.provisional`), and the
                 paywall pair with entry_point `wording_changes`. The read is per viewer
                 (features/summaries/hooks/useWhatChanged: the key carries the signed-in reader's id; the
                 anonymous server seed is that entry's data and the placeholder for the others, and the read
                 waits for /me, cold or being re-read, so a refreshed token is the one it carries; a Pro
                 reader served the teaser off a fresh cached /me has /me and the report re-read once). While
                 the seed stands in for a signed-in reader (`context.provisional`), and when that reader's
                 own read fails and the seed stays in its place, the teaser's prompt is withheld.
                 THE REVIEW (the full list in front of a signed-in reader; features/summaries/hooks/
                 useWordingReview, PUT /wording-review/labels): each row's label line carries a
                 role="group" ("Mark change N of M") of two pressed-state toggles, "Reviewed" and "Follow
                 up", 32px, 12px text, `rounded-lg`, a hairline in secondary ink at rest and the brand-weak
                 fill with brand.strong ink and 600 weight when pressed (weight and fill together, never the
                 fill alone; `aria-pressed` carries the state; each is named "Reviewed: change N of M" so a
                 screen reader knows which change). Pressing the set toggle clears it. The list takes the
                 keys (`aria-keyshortcuts="j k 1 2"`): j/k and the arrows move focus between rows
                 (`tabIndex={-1}` rows with the brand ring; the toggles stay the Tab stops), 1 and 2 mark
                 the focused row, as toggles (a held key's repeats mark nothing). Above the list, a 14px
                 `tnum` progress line in secondary ink (`tabIndex={-1}`, the Retry's focus target; "3 of
                 12 changes marked, 1 to follow up."; "Loading your review…" until the read settles, the
                 toggles disabled meanwhile) and a 12px tertiary keys hint. The read's other states, each
                 over the plain list with no toggles and no hint: a failed read says "Your review didn’t
                 load." and shows a Notice (error) "Couldn’t load your review" with a sm RetryButton over
                 useRetainedFailure, as every Retry of a query (§4); a read the server has nothing for
                 ("unavailable": the comparison the block shows is gone, or the feature is off) says "This
                 review isn’t available for this comparison yet." and has the report re-read. A label is
                 applied to the cache as it is pressed and rolled back if the server refuses it; labels
                 are sent one at a time per review (the mutation's scope), so answers land in press order.
                 The server alone completes the review (every change labelled); the line then reads "All
                 12 changes marked, 1 to follow up. Receipt below." and the receipt follows the list as an
                 inset well (panel fill, one hairline, the 8px radius, no shadow, like Callout): a 14/600
                 title "Review receipt", a `<dl>` in the 12px data face (Completed, Filing, Against,
                 Fingerprints as the first 12 hex of each text's SHA-256, Versions, Marked) and a sm
                 secondary Button "Copy receipt" that writes the full plain-text receipt (every fingerprint
                 in full, the follow-up change ids, the completion time) with a role="status" "Receipt
                 copied." beside it. Every change marked but no receipt (the filing text was re-read since
                 it was frozen, so the server reports the review reopened): the line reads "… No current
                 receipt." and a row under the list explains and offers a sm secondary Button "Issue a new
                 receipt" (marks one change again, unchanged). Events: `wording_change_labeled` (label,
                 kind), `wording_review_completed` once per completion, on the transition the server
                 names in its answer (`completed_now`), never on the client's guess (items_total,
                 follow_ups), and `wording_receipt_copied`. The dashboard feed card
                 (features/dashboard/components/WhatChangedCard, `wordingLine`) carries the same counts
                 under its figures as one 12px `tnum` line in the Compare periods words ("12 paragraphs of
                 risk factors changed."), then the reader's own progress ("3 of 12 marked." / "Reviewed."),
                 reconciled against the live comparison exactly as the review is.

Company identity <CompanyIdentity company latest summaryReady actions>  (features/companies, critique 1b) — the
                 Filing identity vocabulary reused on the company lead (IDENTITY_* classes, Sep, TickerPill
                 exported from FilingIdentity): breadcrumb Home / company, the h1 with logo and ticker pill,
                 one data-face line of facts the API returns (exchange · CIK as EDGAR prints it, ten digits ·
                 "Company on SEC EDGAR ↗"; no market quote, the one figure there no filing sources, D-046,
                 though the search option keeps its own), then "Latest filing" form · period · filed date · "summary
                 ready" (only when the summary probe found one the filing page will show: isSummaryReady, not
                 a placeholder or a stored failure). Its actions: the ONE primary action, opening the latest
                 filing ("Open latest summary" when ready, "Open latest filing" over a stored row that is
                 not and while the summary read is pending or has failed, "Summarize latest filing" only
                 once the read finds none), with the watchlist toggle beside
                 it as a secondary Button (visible label, star, aria-
                 pressed, `loading` while it saves). Sector and fiscal-year convention wait for the payload.

Compare periods  <ComparePeriodsCard filing>  (features/filings, critique 1b + P-07) — the entry to a change
                 report: an <aside> Card (p-5, h2 18/600) beside the filings index on lg+ (grid-cols-1 base,
                 lg 1fr + 20rem), shown only for selectComparisonFiling (the newest annual report with an
                 earlier annual period listed). Up to three hairline rows: metric · the change in WhatChanged's
                 own vocabulary (exported Change: ▲/▼ glyph + the server's display string or —, in its tone's ink)
                 · the Read-as word; "N more in the change report."; one 12px line counting the wording comparison
                 the report carries ("12 paragraphs of risk factors changed." / "No wording changes in the risk
                 factors."); a sage text link "Open change report →" to /filing/{id}#what-changed. Same read and
                 query key as the filing page's section (useWhatChanged). States in place: ledger bones, Notice +
                 RetryButton, a plain line when nothing is comparable (a wording comparison alone keeps the link,
                 over the line that no figures compare). No risk diff until the backend serves one again.

Hero example     <HeroExample example>  (features/marketing, critique 1d) — the example IS the product, on ONE
                 surface (rounded-xl panel + hairline + e2, dark: fill + hairline): "Example summary" with the
                 quality Badge, the identity line (company, then ticker · form · filed in the data face, Sep
                 between; each middot in one item with the fact before it, so a wrapped line never starts or
                 stands with one; the form one nowrap run; the date an inline-block after "filed", so it moves
                 down whole and breaks only after its day), the summary's opening, the figures as ONE hairline
                 strip (border-y on a clipping wrapper round a wrapping flex <dl>: each figure flex-auto, never
                 an equal third, so where three do not fit they wrap one under another; a figure's own border-l
                 and border-t are the strip's rules, the <dl>'s negative margins putting a row's leading rule
                 and padding, and the first row's top rule, outside the clip; a value breaks inside only when
                 wider than the strip; ▲/▼ aria-hidden before the signed delta), one evidence row when the live summary
                 has a located risk excerpt (pickEvidence: source_verified under the source owner; heading =
                 excerptHeadings, blockquote clipped at 180 on a word with " …", a chip link "Located in the
                 filing"), the EDGAR receipt (a no-break space holds its middot to the word before it), and a
                 text-link CTA. No browser-frame mockup, no card in the
                 card, no sparkle chip, no tinted CTA. The static fallback has no evidence row. Under 200% text
                 the three figures sat in equal thirds and ran into each other at 390px, the identity line's
                 "filed Oct 31, 2025", one nowrap run, took the page to 329px at 320px, and the receipt's second
                 line began with its middot at 1440px (E81). Gate: tests/e2e/reflow-200.spec.ts (at 320, 390 and
                 1440px under 200% text each label whole, each value and change on one line inside its own figure
                 and the example, no two figures meeting, every form code on one line, no painted line starting
                 with a middot; at both text sizes the strip's rules as painted, a row's leading rule and the
                 first row's top rule clipped, every other rule inside the strip, the first figure's label flush
                 with the card; the page at 320px).

Trust strip      <TrustStrip>  under the hero: a hairline-topped list of plain statements, each scoped to what
                 the implementation establishes ("where a match is found"); "generated" stays distinct from
                 "the filing's own words".

Evidence rows    <SummaryRisks>  (P-03; a marked copy since D-044): one hairline list inside the section: a
                 row is an h3 (14/600, the opening words of the row's own verbatim excerpt, unique per row via
                 excerptHeadings, since the server withholds model titles), the excerpt and the provenance chip; a
                 lead line above and a data-face tally below ("3 of 4 excerpts located in the filing text · 1
                 withheld …"), both outside the margin. The brand device marks a row whose excerpt the server
                 located (source_verified, the chip's "Verified in filing", D-028): an EnRef on its heading
                 ([1], [2] … in reading order among the located rows, the chip's 12px, `aria-hidden` like its
                 twin, so the heading's name is its words alone and the chip carries the claim), the twin in
                 the margin MarkedCopy draws beside the list (components/ui, 2.25rem, 2.75rem from sm; the
                 rows take markedRowInsetClass, pl-3 sm:pl-3.5, inside it), and the excerpt as a marked block
                 (`en-marked px-3.5 py-2.5 font-editorial text-base leading-relaxed` in the primary ink,
                 HeroExample's recipe). One marker per row, so the twins never overprint. A row not located
                 keeps blockquote manners (border-l-2 hairline, no fill, no radius, 14px secondary) and no
                 marker; a list with no located row draws no margin. No stripe, no trend glyph, no nested
                 evidence box. Below a measure the margin gives way: MarkedCopy is a query container in em
                 (its own width at the reader's text size, which `sm:` and a rem column cannot follow), and
                 narrower than 13em it drops the margin and its twins, and the rows their inset
                 (components/ui/markedCopyLayout.ts); each marker stays in its heading. 13em is the middle of
                 the measured window: the margin stays at the default size on a 320px phone (the copy is 18em
                 wide on the filing page there, 15.4em in the landing's card) and goes under 200% text at
                 390px and below (10.2em at 390, 8em at 320 on the filing page), where it left the excerpt
                 171px and 101px of 32px serif and broke words mid-word; without it, and with the marked
                 block's side padding narrowed from 0.875rem to 0.5rem below the same measure
                 (markedBlockInsetClass), the excerpt keeps 291px and 221px and no word breaks, a filing's date
                 joined by a no-break space ("September 27,", 199px in CI's Chromium) included. The marked
                 block (`.en-marked`) keeps a word still longer than
                 its measure inside itself: `overflow-wrap: anywhere` breaks it inside the block, never past
                 it. The block never hyphenates (`hyphens: manual`): it quotes the filing, and CI's Chromium,
                 which carries a hyphenation dictionary, hyphenated ordinary words at every width under
                 `hyphens: auto` ("re-sults" at 1440px). The landing's evidence row needs the break: its card
                 left the block 115px of 32px serif at 320px under 200% text (about 139px with the narrowed
                 padding), and seven words ran up to 49px past it (gates: markedCopy.spec.tsx reads the rules,
                 since CI renders the landing with no
                 evidence row; risk-evidence-rows.spec.ts reads the painted words on the filing page). The row
                 wraps a long unbreakable token ([overflow-wrap:anywhere]) rather than push the page sideways.
                 Heading rule (riskHeadline.ts, inside excerptHeadings): a verbatim prefix of the excerpt, never
                 recased and never whitespace-normalised (one enclosing quote pair is dropped first, only when
                 it wraps the whole span). The first sentence stays whole when it fits in 100 characters; a
                 longer one is cut at its first ";" or ":" only where the clause can stand as a heading,
                 otherwise capped on a whole content word that splits no figure from its unit or label, no
                 date, name, bracket or quotation. Never at a comma or a dash. "…" whenever the excerpt goes
                 on; "Risk n" when no heading fits. Gates: riskHeadline.spec.ts (the rule, on the production,
                 backend-fixture and eval spans), riskTitle.spec.ts (what excerptHeadings adds around it),
                 SummaryRisks.spec.tsx (the wiring and the device's rows, the marker out of the heading's
                 name), tests/e2e/risk-evidence-rows.spec.ts (layout at 320, 390 and 1440, both themes,
                 default and 200% text: where the margin shows, each twin on its marker's line, none
                 overprinting, and its width; the margin and the rows' inset gone at 390px and below under
                 200% text; no word of a marked block broken mid-word, read a character at a time; the
                 marker, twin and excerpt at 4.5:1 or more),
                 brandCopyRules.spec.ts rule 3 (where the device renders, and only on located rows).

Callout          <Callout label tone="neutral|caution">  (P-08; replaces SummaryBlock) — an inset well:
                 `rounded border bg-panel-light px-4 py-3.5` (dark: white/10 hairline on panel-dark), no
                 shadow. The tone lives in the label word (caution = warning ink on the label only); the body
                 is 14px secondary. A thick left border on a rounded container — the side-tab stripe card —
                 is banned app-wide (gate: earningsnerd/no-side-stripe, which reads whole class strings,
                 template chunks and helper arguments included); a quotation keeps its unrounded 2px bar.

Provenance chip  <SourceTrace>  (P-10) — `sourceTraceChipClass(selected)`: 12px/500 data face, 20px tall from
                 its 16px leading + 1px padding + 1px hairline (no fixed or min height, so a long label wraps
                 in a phone card), 16px radius (a pill on one line, a rounded box when wrapped), panel fill,
                 secondary ink, hover brightens. Glyph = what it cites: `quotes` for a filing passage, braces
                 (`kind="xbrl"`, MetricSourceLink) for an XBRL figure, the arrow for "Cited". The chip the open
                 pane's Filing view is answering is `selected`: brand tint + aria-current (the highlight
                 request's sourceId + the viewer context's paneOpen), whether the pane shows its passage or
                 says why it cannot (text not in-app yet, passage not pinpointed). Labels and accessible names are unchanged
                 ("Source: Verified in filing"). The recipe lives in `features/filings/lib/sourceTraceChip.ts`, outside the
                 'use client' SourceTrace, so a server component can call it (the homepage example does; gate:
                 `tests/unit/serverCallsClientExport.spec.ts`).

Source pane      <FilingWorkspace>  (P-06) — the research pane is named for the source: header "Source" + the
                 filing in the data face, close button; tabs Filing · Ask (file-text / chat-circle-text glyphs,
                 underline tabs ≥36px, 44px in the sheet; arrows wrap from the focused tab); the Filing tab
                 ends in "Original on SEC EDGAR". aria-label "Filing source and Ask"; role dialog + aria-modal
                 below lg only. The floating launcher is "Source ⌘K", a secondary control (panel fill,
                 hairline, e3; aria-keyshortcuts) whose kbd hint is secondary ink on a cream key. A chip opens
                 the pane on Filing; the initial tab stays Ask until in-app filing text is reliably available.
                 Focus: at lg+ (a side pane, nothing trapped) a chip keeps focus as it opens the pane on Filing,
                 where the rail focuses nothing. Any other opener (an in-page Ask button or starter, the control
                 Ctrl/⌘+K or "/" was pressed on) keeps focus too, except that the rail moves it to its composer a
                 frame later when the visitor can ask and the Ask tab is shown (AskCopilotRail). The launcher and
                 the coachmark's Try leave with the open, so a keyboard press on either hands focus to the
                 selected tab (useFocusHandoff, keyboardOnly): a visitor who cannot ask still lands in the pane.
                 Below lg the sheet's trap (useSheetFocusTrap) focuses its first stop, Close, which precedes the
                 tabs, as the sheet opens, whatever opened it; the launcher's or Try's hand-off then finds focus
                 placed and leaves it. For a visitor who can ask, focus moves twice (the tab, or Close below lg,
                 then the composer a frame later, or once a free visitor's usage loads); that is accepted, since
                 the composer renders locked or not and the hand-off cannot tell the two apart. Closing (Escape,
                 ×) moves only focus that fell (on <body>, or still in the hidden pane), to the first that can
                 take it: the provenance chip that opened the pane, the control focused as it opened, the
                 launcher (it remounts on close). Focus the user moved elsewhere stays. Below lg the sheet's trap
                 restores to the chip or the launcher. Gates: tests/e2e/pane-close-focus.spec.ts holds the route
                 matrix on the real page (every open route x Escape and × at 1440, the sheet at 390);
                 tests/unit/FilingWorkspace.spec.tsx pins only the close path's own rules (an opener gone or
                 hidden since the open, a chip that opened it later, a pointer press, focus moved elsewhere).

Filing reader    <FilingViewer> (`.filing-reader`) fills its pane and never exceeds it: the reader-only
                 rule sets `width: 100%`, up to the 88ch rail (a column-flex child with auto inline
                 margins is not stretched, so without it the reader took its widest table's width;
                 `min-w-0` does not bound that). Each table sits in its own horizontal scroll box
                 (`ReaderTable`, `.filing-table-scroll`, which takes the table's 2rem rhythm wherever it
                 sits and, at the reader's top level, its escape from the 68ch measure); never make the
                 reader or the sheet scroll sideways for a table, and never `overflow-x-hidden` it away.
                 While, and only while, a table is wider than its box, the box is a scroll region:
                 `role="region"`, `tabIndex={0}`, `aria-label="Scrollable table: <the heading above it>"`
                 (the last heading before it whose own container, the reader or a blockquote or list item,
                 also holds it; ", table 2 of 3" when tables sit under headings that read the same, in one
                 section or several, so no two regions share a name), the brand focus ring; a table that
                 fits stays out of the tab order. The reader itself is a tab stop too (`role="region"`,
                 named "<filing> · filing text", `tabIndex={0}`, the ring inset as in MonthView), so the
                 arrow keys scroll it from the top: Chromium made the scroller one on its own only while
                 nothing in it was focusable. In the Source pane's Filing tab, Tab goes Filing tab →
                 reader → each scrolling table's region (and any link in the text) → "Original on SEC
                 EDGAR"; when the cited passage cannot be found, the notice's "Open original" link comes
                 before the reader. A citation jump (highlightInDom) scrolls the reader and the table's
                 box only, never the page (no scrollIntoView), and centres the passage in the reader's
                 on-screen part (above the fold and the consent bar, before the desktop pane sticks):
                 smoothly, or in one jump under prefers-reduced-motion. A passage the server located wears
                 the device's mark (D-044): `::highlight(copilot-citation)` (CITATION_HIGHLIGHT_CSS, a constructed
                 sheet) paints `.en-mark`'s tint and its 2px hairline, `.dark`'s pair in dark, the hairline an
                 unbroken underline where the tint ends (`text-underline-offset: calc(0.2632em - 2px)`,
                 Newsreader's descent below the baseline), and sets the passage in the primary ink, since the
                 reader's secondary ink is 4.49:1 on the dark tint over the slate panel. The Highlight API
                 paints colours and decorations only, so the tint fills the line's content area where
                 `.en-mark` starts it at 62% of the line box. Located means a verified citation of the
                 filing's text: a summary chip's verified excerpt (SourceTrace sends `verified` only with
                 the excerpt the server checked) or an Ask answer's passage. Any other jump lands in the
                 neutral find highlight, `::highlight(copilot-find)` (FIND_HIGHLIGHT_CSS, in the same sheet):
                 the brand sage at 22% in the reader's own ink, no hairline, one rule for both themes, the
                 reader's paint before D-044, so the reader still sees where it landed: a summary chip's
                 section heading (every metric chip, a verified XBRL figure's included, every Cited chip, and
                 a verified chip whose excerpt is too short to anchor), an excerpt the server did not locate,
                 and the text an Ask XBRL fact's jump finds (a fact has no passage). One of the two is
                 registered at a time. The block's `.citation-flash` stays the attention pulse, which fades;
                 the paint is what stays. A box names itself only when it
                 starts to overflow, never on every resize (the name scans the whole reader). The AI
                 summary's `.markdown-body` is untouched. Gates: tests/unit/highlightInDom.spec.ts (each
                 paint's look: the device's equals `.en-mark`'s, read from globals.css; the find paint is the
                 sage with no hairline and never the device's tint, with planted paints for both),
                 tests/unit/sourcePanePaint.spec.tsx (which paint each jump registers, through the real chip,
                 context, viewer and highlight chain), tests/unit/readerTableRegionName.spec.ts,
                 tests/e2e/filing-reader-wide-tables.spec.ts
                 (synthetic fixture text, 1440x900 and a 390x844 touch sheet) and
                 tests/e2e/copilot-highlight-css.spec.ts (what Chromium computes for each paint, the device's
                 against `.en-mark` on the same page, both themes; a far-right table cell revealed in its own
                 box in real layout, the page unmoved).

Ask answer       <CopilotMessage>: the SHIPPED copilot contract: status reading|done|error;
                 answer = GFM markdown (react-markdown + remark-gfm); markers [n] AND [F1]/[f1]/[F 1]
                 (case/whitespace tolerant) become chips showing the BRACKETED marker; unmatched markers
                 stay literal text — never a dead button. CopilotCitation = { n, excerpt, section_ref,
                 verified, fragment_url } — `verified` drives source attribution: checked sources show
                 “Source match found” with its scope (not whole-answer verification); unmatched sources
                 stay “Cited”. XBRL source rows carry the braces glyph and their tag. The done answer
                 counts “{n} matched source(s)” once. A plan gate (a spent free allowance, a Pro-only
                 403, the Pro fair-use 429) is the quiet answer card with role="status" and the server's
                 sentence, plus a lightning “Upgrade to Pro” except for the fair-use cap; the reading card
                 is that status region already, so the sentence is announced when it lands. The error tint
                 and role="alert" stay for real failures. New Ask-this-Filing responses wait for
                 an admitted completion; failed referenced citations and draft answer text are
                 withheld before reaching this renderer. Numeric/text grouping is not a separate
                 attestation. Never conflate source matching with support for every answer claim.
                 It also carries viewer deep-linking, popovers and follow-ups. Its answers arrive whole: the
                 rail takes a message from reading (one pulse dot, "Reading the filing…") straight to
                 done or error; there is no streaming status, token text or caret.
                 Its links print what the model wrote: an answer's own links take the prose links' rule
                 (`.copilot-answer`) and keep their weight, and a source's locator ("Item 7. MD&A")
                 composes countControlClass('link') with the new-tab icon, "(opens in a new tab)" for a
                 screen reader (D-030).
```

- **Radius scale is 4 / 8 / 12 / 16 / 24** — buttons + inputs 12 (`rounded-lg`), chips full,
  cards 16 (`rounded-xl`). Config `md` (10px) is legacy off-scale — don't use in new code.
  Chips are full while they keep to one line (Badge); a chip whose label can wrap takes 16
  (`rounded-xl`) instead, a pill on one line and a rounded box once it wraps, since a 9999px radius
  turns a wrapped chip into a capsule whose curve crosses its text (SourceTrace's provenance chip, the
  admin email chip in EmailChipsInput).
- **Skeleton a11y (codified v2.2):** `SkeletonText`/`SkeletonStat` carry their OWN `role="status"` +
  sr-only label — never wrap them in another `role="status"` (double announcement). Raw `<Skeleton>`
  bones are `aria-hidden` — a wrapper composed of raw bones needs `role="status"` + an sr-only label.
- **Evidence identity:** a provenance chip that cites a filing passage uses the Phosphor `quotes` glyph
  (braces for an XBRL figure, and on the Ask answer's XBRL source rows); the Ask tab, the Ask callout, the
  standalone Ask launcher and header (and the landing's Ask demo, which draws that header), "Ask about this"
  and the follow-up prompts use `chat-circle-text`,
  the Filing tab and the Source launcher `file-text`; an upgrade button that carries a glyph uses `lightning`
  (the rail's exhausted-state Upgrade and the taste line's text button carry none).
  `sparkle` appears ONLY on the "AI summary" chip.
- Sortable table headers contain buttons with ▲/▼ and the brand focus ring; `aria-sort` belongs
  to the enclosing header cell (`th`).
- **Class maps outside JSX must sit under a `content` glob.** Tailwind generates only the classes
  it finds in the modules `tailwind.config.js` `content` scans. A class composed in an unscanned
  module ships unstyled and nothing reports it: `lib/financialTone.directionChip` lost its /20
  borders and flat tint until `lib/` got a glob. `tests/unit/designSystemDoneGate.spec.ts` fails
  when an unscanned app module composes a hyphenated, variant, opacity or arbitrary-value class
  (bare single-word utilities like `italic` are indistinguishable from prose, so they are not checked).

## 5. Headings

Type v2 supersedes the old "no global heading color" rule: the global `h1–h6` rule now sets
`font-family: var(--font-heading)`, `font-optical-sizing: auto`, `font-weight: 600`, and
`color: var(--heading-color)` — theme-safe by construction (`.dark` re-points the var), so the
dark-hero bug that motivated the old rule can't recur. Don't add per-heading color overrides
unless the heading sits on a surface that inverts against its theme.

**Outline: never skip a level.** Pick the element for its place in the page outline and set the
size with classes: a section directly under the page h1 is an h2 whatever its type size (the pricing
plans, the analysis chart panels). `GuidanceCard` titles itself h3 by default, for a card inside an
h2 section; where the card stands in for the page's content directly under the h1, pass
`headingLevel="h2"` (the filing page's signup gate, failure and monthly-limit cards and a stored
summary's writer error; the watchlist's empty and error cards; the waitlist example's fallbacks).
A fallback that replaces the whole page passes `headingLevel="h1"` (app/error.tsx, the dashboard's
error boundary, the providers' GlobalErrorBoundary, the signed-in routes' account card
`features/auth/components/AccountLoadFailure.tsx`; global-error.tsx writes its own h1; gate:
tests/unit/errorBoundaryHeadings.spec.tsx).
The footer opens its own section with a visually hidden h2 ("Site links") before its h3 column
titles, so a page whose content ends at h1 (the 404, /analysis, /search) does not jump from h1 to h3.
`tests/e2e/text-floors.spec.ts` checks the routes and states it visits, in DOM order and in the
accessibility tree: home, /pricing, /company/AAPL, /filing/3 with a summary, a signed-in /dashboard,
the 404, the route error boundary, /waitlist (its problem cards are h2, since the example beside the form has no heading),
/login, /register, /forgot-password, /check-email, /verify-email and /reset-password (the auth shell,
which has no site footer; the two token pages are opened without their emailed token), /contact,
/privacy, /terms, /security, /delete-account, /calendar and /search (CI's e2e build turns both on:
the calendar reads its own fixtures with the clock pinned to one week, the search is answered and
run), a finished Multi-Period Analysis run on /analysis, and four
page-level card states (a filing without a summary for a guest and for a signed-in reader whose run
fails, a writer error, an empty watchlist). Three census cases hold that list to its sources:
`STATIC_ENTRIES` in `app/sitemap.ts`, `AUTH_ROUTES` in `lib/authShellRoutes.ts`, and every
`page.tsx` under `app/`, static or dynamic (a dynamic route by a representative path, /company/AAPL
for `/company/[ticker]`), which the spec must visit or name in `NOT_VISITED` with its reason (the
admin pages, /dashboard/settings and the labs prototypes).
Each fails, naming the path, when a route has no entry, and a reason for a page the spec visits, or
that no longer exists, fails too.

## 6. Cards must *lift*, not tint

`brand-weak` (#ECF2EE) is **darker** than the cream page (#F4F3EE) — as a card *fill* it's
~1.02:1 (invisible). Cards on cream use a **lighter** fill (`panel-light`) + hairline + soft
`shadow-e*`; **brighten** on hover (`hover:bg-white`), never darken. In dark, separation is fill
contrast + hairline with `shadow-none`. `brand-weak` is an accent/hover/tint color only.

## 7. Marketing surfaces

Flat **solid** surfaces — no decorative gradients anywhere; the only glow is the theme-aware hero
search glow. Every promotional headline accent uses `BrandEmphasis`, the shared C5 treatment
below, in all homepage variants, the authentication pane and the waitlist. The phrase uses dark
ink on solid sage. Sage ink stays for links and the wordmark's italic.
`.mockup-frame` is flat navy (the decorative slate gradient is retired), 16px radius, paired with
`shadow-e3`; its title-bar traffic-light dots are gone. Marketing cards use the `<Card>` recipe
(panel + hairline + e2, brighten on hover); the popular-company chips are the same surface at e1,
per the design. `.glass-card` is retired on the landing route (its remaining consumer is
`AuthShell`).

**Promotional emphasis (C5).** `features/marketing/components/BrandEmphasis.tsx` owns the
phrase span, `.en-mark.en-hero-emphasis`, and loads the existing
`scripts/brand/fonts/Inter-Variable-Italic-latin.woff2` through
`next/font/local`, with genuine italic, weight 600, optical sizing and `font-synthesis: none`.
This local face does not change `app/layout.tsx`, the root font variables or `app/global-error.tsx`;
the broader web/brand-image italic decision (E79) and root/error font deduplication (E147) remain
separate work. The class uses solid `brand.strong-dark` (`#98C5AD`) in both themes, opaque
`text.primary.light` (`#1A1A17`) in light and `background.dark` (`#0B1120`) at 90% in dark.
That is a local fill/ink role exception, with no new palette token, hairline, shadow or interaction.
Its inline block uses line-height `.9`, padding `calc(.04em - 1px) .18em .06em`, inline margins
`-.1em`, the existing `.5rem` radius and baseline alignment. The 1px top trim keeps the fill off
the preceding line's descender at default text size. The heading isolates a local stacking context;
the relative emphasis span sits at `z-index: -1`, with the fill on its `::before` behind the text.
That fill's base top inset is `max(0px, calc(6% - .06em))`: zero on one line for the default
headline, increasing with the box's height when enlarged text wraps the phrase, to clear
neighboring descenders without moving glyphs.
`max-width: 100%` and normal white space keep the phrase together
while its intrinsic width fits, then allow a word-boundary wrap under enlarged text. Check the
painted glyphs as well as line boxes at mobile/desktop widths, DPR2 and 200% text in both themes.
Every containing heading uses `isolate`; the shared component owns the font and paint classes.
A caller that ends the phrase with a full stop sets `trailingPeriod`: the component owns that stop
in an inline-block group with normal wrapping inside the filled phrase and no wrap between its
final line and the stop. The group and phrase keep their intrinsic minimum widths; the phrase
releases its negative end margin and reserves `.1em` from the group width. This keeps each word
inside the fill and the stop outside it under enlarged text. Its bottom padding is `.18em`, leaving
clearance below the p/y descenders in the longer phrases. Its fill top inset is bounded to
`max(0px, min(calc(6% - .06em), calc(.06em - 1px)))`: the cap keeps multi-line capitals inside
the fill while leaving preceding descenders clear. The default headline continues with a word
space and retains its original optical spacing.
Each heading is an inline-size query container. Below a `13rem` measure, the group retains its
`100%` width cap and intrinsic minimum, removes its side margins, and uses
`translateX(min(0px, calc((100cqi - 100%) / 2)))` to center only the part that exceeds the heading.
Fitting groups retain their normal alignment. The transformed group is relative at `z-index: -1`
to keep its new stacking context below neighboring ink. The phrase drops its negative start
margin while reserving `.3em` for the stop. Below `9rem`, its inline padding becomes `.12em`,
leaving visible screen-edge clearance around the longest words without breaking them.
This accommodates WebKit's wider italic metrics at enlarged text sizes; normal mobile text
does not enter these queries. The word remains padded inside its fill.
`brandCopyRules.spec.ts` counts calls to that component at the allowed promotional surfaces and
rejects a raw legacy mark there, while retaining the figure/quote and one-per-surface rules.
The bare `.en-mark` remains the reader annotation paint reference, not a promotional alternative.
Current OG/social, business-card and PDF-cover templates reproduce C5 with their medium
constraints; the mail template and runtime header stay in markup parity with solid fill and
italic client-font ink. Classic Outlook keeps the readable plain-text fallback. Historical
audit/direction screenshots record their original state and are not current templates.

**The landing's composition** (D-045, composition C). The two-column hero stays; every section after
it is one ruled row, `features/marketing/components/LandingRow.tsx`, in the page's order: on the hero's
container (`max-w-7xl`, so each rule runs the width of the hero's trust strip), a `border-t` hairline
and `py-12 sm:py-16`, then a 14rem label column beside the content. The label column holds the
section's number (12px data face, tertiary ink, secondary on navy: the `landing-row` CSS counter that
`app/page.tsx` resets on `<main>`, aria-hidden as the summary's section index is, so a section that
omits itself, Reporting this week or Notable filings with no data or the empty reader quote, takes no
number and leaves no gap), its title as the section's `h2` in the Title role (`text-2xl`, 24/32), and one line (14px
secondary), one short sentence: a second sentence opens the content column, in body secondary under a
`max-w-2xl` measure, as the evidence and contents rows' do. The columns open at
`[@media(min-width:64rem)]:` at the reader's text size (1024px, or 2048px under a 200% text setting)
and the label stacks above the content below it. No row alternates
and no landing file lays items out four across: the claims and the extras are two across, the Pro screens one
under another with each pitch above its screen, the contents a hairline list, and Reporting this week and Notable
filings hairline lines two across, one anatomy for both (`tests/unit/NotableFilings.spec.tsx` fails when they drift). Pricing on the landing is one native table (`PricingSection.tsx`): an sr-only caption,
the plans as `th scope="col"`, what each includes as `th scope="row"`, every cell a plan line read
through `shipped()` from `lib/planLimits.ts`, a dash with a visually hidden "Not included" where a plan
has none; it fits a 390px phone at the default size and, wider than its box (a phone at 200% text),
scrolls inside a box that `useOverflowRegion` names and puts in the Tab order, never the page.
`/pricing` does not share it and keeps its two plan cards. The page closes with one line
(`ClosingLine.tsx`): the live example as a text link and the access mode's call to action as a button
at the end of one sentence, under the last row's rule. Gates: `earningsnerd/no-four-up-grid`
(`eslint.designRules.mjs`, run on `LANDING_GRID_FILES`: the route, every marketing module and the
sections the route mounts from other features) fails a class that sets four column tracks or more under
any variant (a template, a grid shorthand, a column flow, or multi-column by its count or column width);
`tests/unit/landing-sections-mounted.spec.ts` holds `<main>` to the hero, the rows in
order and the close, each row's component to returning its `LandingRow` (or null) and the close to one
paragraph; `tests/unit/pricing-section.spec.tsx` holds the table's caption, headers and cells;
`tests/unit/landingRow.spec.tsx` the row's own shape; `tests/e2e/home-page-unauthenticated.spec.ts` reads
the painted numbers on the built page, 01 to the last row with no gap. The plan table and the Pro extras
claim no summary history while nothing enforces one (D-046), and the Change Report the same on both plans,
its line naming the metric deltas alone, while production serves no wording diff and omits the report's
risk lines (`tests/unit/changeReportPlanClaims.spec.tsx` fails a Pro chip on the row, or a risk or
language clause in its line and screen, while `ENABLE_SECTION_CHANGES` is off). Notable filings is the
row after Reporting this week (E90): one hairline line per filing the backend serves under D-046's rule, in
Reporting this week's anatomy (the mark at 32, the ticker in the data face with the form and its filed date where
Reporting this week has its day, the name beneath through `formatCompanyName`), each opening its company page, under
a line that says what the feed is and nothing the backend's query does not do; no reason chip.

Muted text on the cream page ground is `text-secondary`;
`text-tertiary-light` (`#636A77`, 4.9:1 on cream) carries captions, counts and micro-labels on either
ground; copy the reader must read stays secondary, including the point-of-use AI disclaimer
(`AiDisclaimer`) and the footer's "Data sourced from SEC EDGAR … Not investment advice" line. Gate:
`tests/e2e/text-floors.spec.ts` measures every tertiary-ink text on the main routes against its
rendered ground.

**Reflow at 200% text.** The pricing section's billing toggle (a radio group, not the
SegmentedControl) wraps its two segments whole onto a second row inside its one shell when they do not
fit side by side, each filling its row (`grow`), at `min-h-9` rather than a fixed height; no-break
spaces hold "Annual ·" and "save 20%", so the label breaks only after its middot. At 360px and 200%
text the unwrapped group took the page to 368px, its Annual label on three lines below its segment.
The site footer opens its columns at md at the reader's text size, `[@media(min-width:48rem)]:`
(768px at the default size, 1536px under a 200% text setting), not `md:`: its columns hold words that
cannot break, and at md's 768px under 200% text the footer took every route to 812px (the landing's
final CTA card took / to 886px the same way, until D-045 made the close one line). The landing's rows
open their label column at 64rem by the same rule. A form code in the landing's copy is one
`whitespace-nowrap` run (`FormCodeText` in the hero's subhead, the plan table's cells, the claims, How it
works and the Pro extras; a span of its own in the close, the extras' file kinds and the hero example's
identity line): before, the plan table painted "10-K and 10-" over "Q filings" at 320px, the claims and
How it works broke "10-Q" the same way at 320px under 200% text, and the subhead broke "10-Ks" at 390px
and "10-Qs" at 1440px under 200% text (E81). On the legal pages (/security, /terms and /privacy) the
gutter gives way before a word breaks, and the wrap is the last resort. Each page's `<main>` sits in a
`[container-type:inline-size]` wrapper and takes one class string (`lib/legalPageLayout.ts`), whose side
padding is `px-2` below 13em of the wrapper's text size, as /analysis's is: on a phone under 200% text each
gutter is 16px where `px-4` doubled to 32px, and nothing moves at the default size or on a tablet. A word
still wider than the column breaks inside it, `[overflow-wrap:anywhere]` on `<main>`, which every heading,
paragraph and address inherits. At 390px under 200% text no word breaks but an address, which breaks
anywhere by design (a 358px column; in 326px "Indemnification", 330px, left its "n" alone); at 320px
(288px) each title holds whole and six words still break, /security's "Authentication" and "Infrastructure"
and /terms' "EarningsNerd", "Subscriptions,", "MERCHANTABILITY," and "Indemnification", three of them by 1
to 5px; at 360px "Indemnification" alone.
Before E131, at 320px under 200% text /security reached 348px on its headings' "Authentication" and
"Infrastructure" and /terms 362px on "Indemnification". The auth shell's lockup yields to
the mark alone below a 12rem viewport (§8). Gate: `tests/e2e/reflow-200.spec.ts` (the toggle's labels
at 360 and 390px, every line but the last ending at the middot; every form code in the landing's rows and
its close on one painted line at 320 and 390px under 200% text and at 320px at the default size, and the
hero's at 320, 390 and 1440px under 200% text, and every waitlist code at 320 and 390px under 200% text;
a 768px and an 834px tablet over its route loop; a 320px phone under 200% text over it too, the three
legal pages among its routes; and, read a character at a time, every word of the legal pages whole at
390px under 200% text and each one's title at 320px).

**The brand device: the margin and the mark** (2026-10 brand studio; `DESIGN.md` › Graphic device;
`docs/brand/06-system.md` §6). Four classes in `globals.css`, each a light/dark pair:
`.en-mark` (a phrase highlight: pale sage tint from 62% of the line box, a 2px `brand-border`
inset hairline at the baseline, `box-decoration-break: clone` so a wrapped phrase marks per line),
`.en-marked` (a located passage: 3px `brand` bar on the left, tint behind, square corners because a
stripe never sits on a rounded container, the filing's words inside it in `.filing-reader`'s face), `.en-margin` (a gutter with a hairline on its
inner edge; `w-11` from `sm`, `w-9` on phones, giving way below a measure: Evidence rows, §4) and `.en-margin-mark` (an 11px data-face bracket,
`brand-strong`, absolutely positioned on the line of the in-text marker it twins; the twin is
measured by `components/ui/MarkedCopy.tsx`, never hard-coded). Rules: a mark means
"located" and a bracket means "cited"; one `BrandEmphasis` per surface may enclose a phrase of ours
as the signature; none on a figure, a price, a status, a competitor's name or an unverified claim; no
margin without a marker; the hairline never scales with the type. The 11px mark is the one
sanctioned sub-12px text beside copy because it is a twin of a 12px marker, not copy; it still
carries no claim and is `aria-hidden`, as the in-text marker (`EnRef`) is: the number points at a twin
assistive tech never reaches, and the chip beside the passage carries the claim, so a heading's name is
its words alone.
Inside the product the device marks every passage the server located, and nothing else (D-044): the
filing page's Risks rows (Evidence rows, §4), the summary's quotes whose evidence the server located
(Section ledger, §4: the marked block alone, no marker, no twin) and the Source pane's located passage
(Filing reader, §4).
One marker per row, so the twins never overprint; the one-emphasis limit stays for a phrase of ours.
Ask this Filing's answers and the Multi-Period narrative keep their citation chips: a cited line carries
several markers there, and their twins would overprint. Gate: brandCopyRules.spec.ts rule 3
(DEVICE_PLACES, an equality of places and their parts: the hero example's evidence row and the Risks
rows with the margin, the marker and the block, the quote blocks with the block alone; on a list's row a
marker or a marked block only under a test of its located flag, a risk's `source_verified` or an
evidence's `verified`; one marker per row and per line, and none inside a marked block; no margin
holding CopilotMessage, NarrativePane or CitationChip; its planted forms in
`tests/unit/fixtures/brandRule3Forms.tsx`).
Two forms, kept apart: `.en-marked` sets a located passage as a block (the 3px bar, the tint, square
corners, the filing's words in Newsreader: a Risks excerpt, a located quote), and the tint and 2px
hairline, `.en-mark`'s look, mark a located passage inside running text (the Source pane's
`copilot-citation` paint). Nothing unlocated takes either form (a jump the server did not locate lands in
the reader's neutral find highlight, `copilot-find`), a quote block never takes the tint and
hairline, the Source pane never takes `.en-marked`, and inside the product only the Risks rows carry a
marker and its twin. Gates: brandCopyRules.spec.ts rule 3 (no `en-mark` on, in or around a quote
block; the highlight's places, HIGHLIGHT_PLACES, an equality of one shared `BrandEmphasis` per surface; a class any string
names counts as a part, so a Source pane module that adds `en-marked` fails DEVICE_PLACES),
highlightInDom.spec.ts (the reader's located paint is `.en-mark`'s look, never the marked block's bar,
and its find paint never the device's, with planted paints) and sourcePanePaint.spec.tsx (a heading
fallback, a Cited jump and an XBRL fact never register the device's highlight; a located excerpt does).

## 8. Theme mechanics

- **One** `<ThemeToggle/>`, in the global `Header` (desktop + mobile; below a 24rem viewport it sits in the mobile menu's first row, not the bar, so the bar keeps one row under enlarged text and the toggle opens in view directly under it: tests/e2e/reflow-200.spec.ts). No page-level toggles.
- `app/layout.tsx` runs a **pre-paint theme bootstrap script** (saved `localStorage.theme`, else
  light; there is no system-preference detection) to prevent FOUC, and `ThemeProvider` re-syncs to
  the same value after hydration. Keep `suppressHydrationWarning` on `<html>`.
- Logo: `<EarningsNerdLogo mode="auto" />` follows the app theme — don't hardcode `mode="dark"`.
  The auth shell's lockup (the 2rem mark and the text-lg wordmark, about 10rem, 1.5rem in) yields to the mark alone
  below a 12rem viewport (384px under a 200% text setting, never at the default size), where it and its
  clear space no longer fit; its link keeps the site header logo's name, `aria-label="EarningsNerd home"`,
  with the wordmark `display: none` (sr-only text still lays out past the link, which the bar's checks
  read). At 360px and 200% text the lockup ran to 369px. Gate: `tests/e2e/reflow-200.spec.ts` (360px at
  200%, the bar's edge in the logo's clear space).
- Fonts are self-hosted via `next/font` (Inter with `axes: ['opsz']`, Geist Mono, Newsreader) —
  see `app/layout.tsx`; promotional emphasis also loads its shared local Inter italic face (§7).
  SF Pro / New York are platform-licensed and must never be embedded.

## 9. Exemptions

- **Google / Apple sign-in buttons**: keep their brand-mandated surfaces (white / black). Only
  their focus rings get rebranded. The exemption protects the provider's mandated look (Google: the
  white surface, the multicolour "G", the hairline and the label ink its branding guideline sets); it does
  not excuse a stale value. When the consent screens are set up (`tasks/todo.md` F38), check the button
  against Google's current guideline and record the values here.
- **Status + financial colors are semantic** — keep them; reserve loud status colors for genuine
  state. A default guidance/info container is subdued/brand-tinted, not loud blue (see `GuidanceCard`).
- **Progress / step / completion indicators use the BRAND accent (sage), not success-green.**
  Green is for a genuine terminal *confirmation* state; in-progress ticks are brand activity. The
  indicator itself (a bar, a ring, a tick) takes the sage; a step's number or a percentage beside it
  rests in the ink (D-030).

## 10. Charts (recharts)

**Financial source states (October 2026).** Consume the server’s separate `provenance.method`
and `provenance.validation`; a calculated figure is not an error. Multi-period analysis uses
neutral `† calculated` marks and lettered data notes with `SourceValue` buttons opening the shared
Modal with source links, formulas, operands and the applicable note. The report-level disclosure
groups concerns by reason and counts figures separately from inherited comparisons. Chart and
narrative Notes controls open the same note; filing fundamentals and peers retain their own
source-check presentation. Warning ink identifies an unresolved concern, never routine arithmetic.
Legacy concerns remain until their stored validation changes; missing metadata makes no passed-check
claim. Do not remove inherited concerns from growth. Unavailable table values use — with a note
letter and read “Unavailable” in the evidence view, never zero or a claim that the company did not
report them. Affected chart points use hollow series-colour markers with a 2px stroke and 11px note letters;
affected bars keep their series fill. Note letters use the neutral chart label ink, a 3px panel-colour
stroke and paint-order=stroke so growth letters remain legible over bars; those are SVG attributes
retained in PNG export. Value and YoY concerns are independent. PNG notes use the same grouped
reason sentences beneath the plot and list each recorded gap once. The plot is a named keyboard
region only while overflowing, measured by `useOverflowRegion` before paint and on resize.
Inside it, Recharts retains one named chart-values keyboard stop: Left/Right reads each period's
tooltip, including the YoY growth series that the quarterly metrics table's QoQ column does not
replace. Each tooltip row names its applicable value or YoY note independently; clean rows carry
no letter. Formatting follows the original data key before adding the note to the display name, so
growth remains a percentage. Inner Left/Right keys reveal the selected mark without competing
native pixel scrolling. Tooltips update without positional animation, wrap to the measured viewport
width and stay within its horizontal bounds. Pointer inspection clears keyboard ownership even
when the SVG remains focused, and does not scroll the chart. The next keyboard arrow releases
the retained hover through the chart’s normal mouse-leave event and resumes its keyboard period.
Outer arrow keys keep native scrolling. Tooltip changes use a live status; Tab leaves and Shift+Tab
returns without a trap. The viewport carries the brand focus ring for either keyboard stop. Time-series lines do not join missing points. PNG notes wrap beneath the plot and retain
source dates, material gaps and a concise disclosure. Use keyboard/touch source controls, not
native hover titles as the only way to inspect provenance. Dense quarterly charts retain every
period label inside a keyboard-accessible horizontal viewport; minimum plot width follows the
period count and axis space, so a narrow screen never overlaps labels or widens the page.

Series colors come from **`chart-1..6`** — a CVD-validated **sequence** (blue↔yellow axis
alternates early), taken 1→N in order, never skipped or re-sorted. At ≥5 series add direct
labels/markers — color no longer carries alone. **Gain/loss never appear as series colors**
(direction only) and **sage never appears inside a plot area**. Direction vocabulary is the app's
`lib/financialTone.ts` `Direction` (`'up' | 'down' | 'flat'`) — derive with `directionOf()`, color
with `directionTone()`/`directionTextTone()` from `ui/Chart.tsx`. Chart chrome (grid, axis, labels,
crosshair, tooltip) uses the `chart.grid/axis/label/crosshair/ref/tip` sub-tokens — theme-aware via
`useContext(ThemeContext)?.theme === 'dark'` (not `useTheme()`, which throws in provider-less
chart unit tests). Axis labels: 11–12px data face + tabular-nums; dark labels use `secondary`.
Tooltip cursors: `crosshairProps(dark)` on LINE charts; `barCursorProps(dark)` on BAR charts — a
category-band FILL wash (chart.1 teal @ 8% light / 16% dark), not a hairline. `yAxisProps` width 44
is a default — currency/ticker labels routinely override: `<YAxis {...yAxisProps(dark)} width={56} />`.

**Financial tone register (metric-aware).** Sign-based direction is a *default*, not a law: for
some metrics an increase is a cost/risk signal, for others direction carries no fixed valence.
The register ships from the backend on each analysis series as `tone`
(`trend_analysis_service._SERIES_TONE` — single source of truth, like `percent`) and is applied
via `features/analysis/lib/tonePolicy.applySeriesTone`:

| `tone` | Metrics (today) | Rendering |
|--------|-----------------|-----------|
| `inverted` | long-term debt, current liabilities | up = **loss** text, down = **gain** text |
| `neutral` | capex, investing CF, financing CF | always **flat** — a capex ramp or financing swing is a strategic choice, not good/bad news |
| `normal` | everything else | sign-based (up = gain, down = loss) |

Never invert or neutralize by hardcoding concept names in the frontend — consume the dataset's
`tone` field so backend concept changes can't silently desync the coloring.

## 11. Motion — tokens only

Four durations + two curves, defined ONCE (`globals.css` `:root`; JS mirror `lib/motion.ts` for
Recharts/rAF, which need numbers). **No raw ms or bezier strings anywhere else.**

| Token | Value | Use |
|-------|-------|-----|
| `--duration-fast` / `duration-fast` | 150ms | hover + color feedback |
| `--duration-base` / `duration-base` | 200ms | crossfades, theme switch, skeleton→content — also the bare `transition-*` default |
| `--duration-slow` / `duration-slow` | 600ms | entrances, draw-ins, count-up |
| `--duration-ambient` / `duration-ambient` | 1800ms | ambient loops + attention decay: shimmer, pulse, citation-flash |
| `--ease-standard` | cubic-bezier(0.4, 0, 0.2, 1) | everything |
| `--ease-pop` | cubic-bezier(0.34, 1.56, 0.64, 1) | the success check-pop ONLY |

- **Count-up is `hooks/useCountUp`** (rAF, slow/standard, `format` per content fundamentals —
  `"$391.0B"` — render in `tnum font-data`) — the `animate-count-up` keyframe is retired; it was a fade.
- **Skeleton→content**: `hooks/useContentIn(loading)` returns `animate-content-in motion-reduce:animate-none`
  from the render where `loading` turns false (DataTable, the account settings and
  watchlist pages) — never on first paint of never-loading views. It catches the flip during render, so
  the class lands on the same commit as the content it reveals.
- **Loading**: a page never swaps itself for a full-page spinner. It renders its own frame and header, and
  any control that needs no data (the watchlist's add field), over bones in the shapes of the cards that
  will replace them (`/dashboard/settings`: Profile's fields and Save, Billing's rows; `/dashboard/watchlist`:
  the insight card's name, actions and tiles; `app/dashboard/page.tsx` keeps its plainer card bones). The
  header never moves and the first card lands where its bones stood. Raw bones are `aria-hidden`, so the
  group carries one `role="status"` with a named wait ("Loading your settings"). Gate:
  `tests/unit/fullPageSpinnerGate.spec.ts` (a `min-h-screen` element holding only spinners and sr-only
  text), with a shrink-only allowlist of three server-seeded or legacy routes.
- **Stagger**: `animate-fade-up-stagger` + `--stagger-index` (0-based; step = fast; capped at 4;
  first paint only). `fade-up-delay-1/2/3` are retired.
- **Reduced motion**: one source for JS — `hooks/usePrefersReducedMotion`. Every animation stops. A
  Tailwind `animate-*` utility has `motion-reduce:animate-none` beside it in the class text that always
  renders with it, with the same variants in the same order (stacked `group-*`/`peer-*`/`after:` variants
  compose the selector in sequence) and `!` when the animation has it, or is written `motion-safe:`: a
  spinner becomes its static glyph,
  a skeleton a static bone, an entrance shows at once. A `globals.css` animation class stops itself in a
  `prefers-reduced-motion: reduce` block (citation-flash keeps a static tint). Count-up shows its final
  value, Recharts takes `lineProps(reduced)`, `scroll-behavior` is `auto`. Gates: the
  `earningsnerd/no-unguarded-animation` ESLint rule for the utilities; `tests/unit/designRules.spec.ts`
  for the globals.css classes; `tests/e2e/loading-and-motion.spec.ts` finds no animation under reduced
  motion on the home, sign-in and sign-up pages or in the dashboard loading states.
- **Nothing decorative** — `animate-float` is retired. Signature set: count-up, citation-flash,
  skeleton→content, sparkline draw-in, check-pop.

## 12. Definition-of-done for any theme/token change

1. **App-wide, not just the obvious page** — public *and* authenticated.
2. **Grep gate** — zero residual legacy brand colors AND legacy type roles:
   ```
   grep -rnE '\b(mint-[0-9]|glow-mint|(bg|text|ring|border|from|to)-primary-[0-9]|emerald-[0-9]|(from|to|bg|text|border|ring)-(sky|indigo|cyan|teal|violet|fuchsia)-[0-9]|bg-blue-[0-9]|Figtree|font-grotesque|#3A2E26|#D99E4A|#92A0E2|text-text-tertiary-dark)' app components features
   ```
   For motion changes also: raw durations outside the token homes —
   ```
   grep -rnE '[0-9]+(\.[0-9]+)?m?s\b|cubic-bezier' app components features | grep -v 'var(--'
   ```
   v3 token hygiene (MIGRATION-v3 §c) — expected hits: DataTable's internal `z-[5]`, the eslint-disabled
   aria-hidden glyphs (Badge ▲▼ `text-[10px]`, DataTable ▲▼ `text-[9px]`) and the brand-mandated
   GoogleSignInButton (`hover:bg-slate-50`, §9); nothing else:
   ```
   grep -rnE "tracking-(wider|widest|tight)|text-\[([0-9]|1[0-3])(\.5)?px\]|bg-slate-|bg-black/50|z-\[|alert\(" app components features hooks lib
   grep -rlnE --include='*.ts*' "role=(\"|'|\{[^}]*)(alert)?dialog|<dialog|z-modal|bg-overlay" app components features   # ≈ the dialog allowlist
   ```
   The grep is a quick look (it also lists files that only mention the tokens in comments); the
   AST gate in `tests/unit/dialogAllowlist.spec.ts` is the authority.
   The same rules run in CI as `no-restricted-syntax` design selectors in `eslint.config.mjs` (on string
   literals and template-literal chunks alike), `tests/unit/dialogAllowlist.spec.ts`, and
   `tests/unit/designTokenParity.spec.ts` (the JS color mirrors use only token hexes; MOTION equals the
   `--duration-*` values).
3. **Font-var gate** (repeat offender — missed in BOTH the v2 and v2.1 exports): every
   `fontFamily` stack in `tailwind.config.js` and every `:root` font var in `globals.css`
   leads with its `next/font` variable (`var(--font-inter)` / `var(--font-geist-mono)` /
   `var(--font-newsreader)`). next/font self-hosts under hashed family names exposed ONLY as
   these vars — a literal-only stack silently never resolves. Four sanctioned exceptions, all
   of which still reach a var: `fontFamily.body` and `--font-body` keep `-apple-system` first
   with the var ahead of the `'Inter'` literal; `fontFamily.sans` is `['var(--font-body)', …]`
   and `--font-active` is `var(--font-body)`, both reaching `--font-inter` one hop later. Do
   not "fix" those four to lead with a next/font var.
   Items 2 (first grep) and 3 are enforced by `tests/unit/designSystemDoneGate.spec.ts`, which
   reads the grep pattern out of this file and pins each exception to its exact shape — so
   editing this section without editing the gate fails, and vice versa.
4. **Verify in BOTH themes** on the Vercel preview — green CI ≠ correct visuals.
5. Run `npm run typecheck`, `npm run lint` (`--max-warnings 0`), `npm run build`, `npm run test`.
   `npm run test` includes `tests/unit/designSnapshotParity.spec.ts`, which fails until the root
   `DESIGN.md` and its sidecar match the changed tokens ([maintenance guidance](../CLAUDE.md#design-documentation)).
