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

## 2. Theme-responsiveness is mandatory

Every color on a surface that renders in **both** themes must be a light/dark **pair**:
`bg-x-light dark:bg-x-dark`, `text-…-light dark:text-…-dark`. Never ship a single-theme color on a
shared surface (it caused white-on-cream and dark-on-cream bugs across the app).

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
- **Body & UI:** `-apple-system → Inter` (system-first; Apple hardware renders SF Pro, everyone
  else falls through to Inter — Inter sits BEFORE generic `system-ui` on purpose).
- **Data:** Geist Mono + `tabular-nums` — money, %, tickers, XBRL anchors, verbatim excerpts,
  Ask-this-Filing output. `.tabular` = mono evidence register; `.tnum` = tabular figures in the
  CURRENT (body) face — numerals inside prose/UI copy only. Data tables and KPI tiles are **not**
  `.tnum` surfaces: their numerics render mono (DataTable numeric cells, StatCard figures — the
  data-role rule).
- **Editorial serif (Newsreader)** is wired to exactly ONE surface: the real filing viewer
  (**`.filing-reader`**, 19/1.7, opsz auto — Item 1A, MD&A, notes). Serif = the filing's own words.
  On a public page the serif appears only inside a quoted passage the product located (the hero
  example's evidence row, the social card's excerpt), never for a headline, tagline or a claim of ours.
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
  provenance chip that carries a verification claim is never one of them: it is 12px (P-10, §4). UPPERCASE
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
DataTable, Skeleton, GuidanceCard, Notice, Modal, SegmentedControl) + `features/filings/components/AskFilingAnswer.tsx` (v2.2: reworked to
the SHIPPED copilot data model — see below). Controls expose their applicable interaction and
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
`<RetryButton failures={[useRetainedFailure(query, queryKey)]} focusTarget={headingRef}>`, never a hand-rolled
`<Button loading={isFetching}>`. `queryKey` is the key the query's own `useQuery` was given: it is the hold's
identity, so a key change (another user, a new search term) never holds the old query's error (gated in
`tests/unit/useRetainedFailure.spec.tsx`). The error UI stays up through any refetch until data replaces it;
the Retry is busy while the query has a fetch in flight (paused offline included), reads "Retrying…" only
while its own press runs, and hands focus to `focusTarget` (a `tabIndex={-1}` heading, or a text field with
`textField`) when it unmounts while focused. It lives beside its hook in `hooks/useRetainedFailure.tsx`, not in
`components/ui`: it is query-coupled, the DS primitives stay free of react-query, and `components/` root is app
chrome only. Every Retry is RetryButton, gated in `busyControlsStayFocusable.spec.ts` by wiring and by label.
A Retry that restarts a stream, not a query (the filing page's "Retry generation"), is RetryButton too, given the
stream's own failure, `{ failed: true, error, busy: false, retry }`: there is no query to hold, and the press
clears the error in the render that starts the stream, so the card leaves with the press when the run starts
and its hand-off target is the progress card's heading. A failure built by hand like this is pinned, with its
reason, in the gate's `ALLOW_HAND_BUILT_FAILURE`. Every other failure RetryButton is given must be
`useRetainedFailure`'s, the hook its module exports under any imported name (a same-named local is not it),
which the gate proves through same-file `const`s, through a component's prop to its call sites (under any
imported name), and under RetryButton's own import aliases; what it cannot prove (a `let`, a JSX spread on
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
                 Default buttons keep their fixed height; icon-sm stays a 32px square.

Ghost button     <Button variant="ghost">  — brand.strong text on transparent, tint hover
                 (`variant="tertiary"` is accepted as a deprecated alias of ghost — pre-v2 API)

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
                 lib/financialTone.directionText IS this recipe — route delta text through it.

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
                 is text in the data face, never a Badge (gate: earningsnerd/no-form-code-badge,
                 eslint.designRules.mjs); <Badge variant="warning"> = warning tint
                 (replaces raw-amber hand-rolls; "Superseded"). beat/miss/new double as tonal recipes via icon={null}.

Status chip      A row's status pill (admin InviteStatusBadge, FeedbackStatusBadge): icon + label on
                 STATUS_CHIP + STATUS_CHIP_INK[tone] from features/admin/lib/statusChip.ts, the one home
                 of the recipe (tones info / success / warning / neutral). The status INK sits on the
                 quiet ground, never the status tint. Light labels measure 5.0 to 7.1:1 on the white
                 chip. Dark carries no fill, so the row's white/5 hover tint is the only layer: 5.77 to
                 6.83:1 at rest, 4.97 to 5.89:1 on a hovered row (Badge's quiet white/5 on the chip as
                 well would drop info-dark to 4.26:1 there). The old recipe, info-light in its own 10%
                 tint, is 4.32:1. FeedbackTypeBadge, the neutral type chip beside the status chip in
                 FeedbackRow, keeps its light ground (black/[0.04]: 9.04:1, 8.50:1 hovered) and takes the
                 same dark one: no fill, its white/10 hairline kept, text-secondary-dark at 5.78:1 at
                 rest and 4.98:1 on a hovered row (its old white/5 fill measured 4.27:1 there). When
                 #1289's Badge status variants land, the recipe moves onto them.
                 Gate: tests/unit/statusChipContrast.spec.ts (each tone on both tables' rows, at rest and
                 hovered, both themes, the grounds read from InviteRow's and FeedbackRow's <tr> and the
                 pages' <tbody>; every layer between a chip and its <tr> read too, and a cell or wrapper
                 there carrying a bg- class fails; a chip colour under any variant but its theme's own
                 (hover:, focus-visible:, dark:hover:) and an opacity below 100 on the chip, a layer, the
                 <tr> or the <tbody> fail too; both badges held to the recipe; the type chip measured as
                 it renders on FeedbackRow's grounds).

Admin pages      A list's table (/admin/invites, /admin/feedback) scrolls inside its card, never the page, in
                 TableScroll (features/admin/components), a `relative overflow-x-auto` box. `relative` makes it the
                 containing block of what the rows position absolutely, their `sr-only` labels included, which were
                 laid out against the page, outside the box's clip (FeedbackRow's took the page to 1090px at 390).
                 While the table is wider than the box, "Scroll horizontally to read all columns." sits above it and
                 the box is a named region in the Tab order ("Scrollable table: <the card's title>", the brand ring),
                 through useOverflowRegion, as in SummaryBlocks' GenericTable. FeedbackRow's message column takes the
                 width the others leave (`w-full` on its cell; the button's intrinsic width contained, with a 16rem
                 floor), so the status select keeps its own at 1440. Gates: tests/unit/admin-invites-page.spec.tsx
                 and tests/unit/admin-feedback-page.spec.tsx (the box, the cue while the table fits and while it
                 overflows, the message column). The section nav (app/admin/layout.tsx) wraps its tabs (`flex-wrap`):
                 an unwrapped row took the page to 443px at 390 under 200% text. Gate:
                 tests/unit/admin-layout.spec.tsx.

Inline notice    <Notice variant="error|info|success">  — compact icon + title + message + action
                 for form/auth flows and in-card states (role="alert" on error; action slot takes a
                 small Button). GuidanceCard is a STANDALONE centered panel — never nest it inside a
                 Card; inside a Card, Notice is the right scale.

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
                 Gate: earningsnerd/no-hand-rolled-toggle-group (eslint.designRules.mjs) fails a
                 role="group" holding an aria-pressed <button> or <Button>, anywhere outside
                 components/ui/SegmentedControl.tsx. It reads the button in the group's own markup,
                 through a same-file wrapper component (one level) and through the DS Button imported
                 under another name. WordingChanges' review row (LabelToggle) carries the rule's one
                 disable: a second press clears its label, a state the control cannot hold (E62). A row
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
                 Keyboard: focus moves to the first action unless the user already moved it elsewhere (armed
                 once per open, callbacks through a ref); Escape closes in window capture with preventDefault
                 (stopPropagation alone still closes a native <dialog> beneath); Tab past the last action /
                 Shift+Tab before the first close it and resume the page's order at the trigger; a scroll that
                 moves the trigger, or a resize, closes it (fixed at its rect, it would detach; the page
                 scrolling behind a fixed dialog does not move it); every close returns focus to
                 the trigger unless the user moved on. While a native <dialog> is open, it portals into it.
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
                 z-header 50 (site header; its menus ride it) · z-overlay 60 (popovers incl. BellPopover, the
                 selection pill) · z-modal 70 (dialogs + the source and viewer sheets — scrim AND panel) ·
                 z-toast 80 (the skip link; sonner manages its own toast layer).
                 The copilot rail / workspace bottom sheets stay z-40 over z-scrim scrims, so the in-sheet
                 citation popovers (z-overlay) still sit above them. Never z-[N]; DataTable's internal z-[5]
                 sticky-cell layering is the one documented exemption.
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
                 lower items instead).
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
                 columns, mirroring its cells exactly — an empty Prior cell is an empty definition; the change
                 glyph inline-block and aria-hidden, the string verbatim, the em dash when the server sent none;
                 tone from `change_tone` through lib/financialTone.directionText + font-semibold for a move,
                 pinned token-for-token to DataTable's td); the per-ADS note as its own line under the figures;
                 the takeaway and its evidence chip. Figures `font-data text-sm tabular-nums`, prose text-sm,
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
                 Pro? Sign in" to /login. Events: `wording_changes_viewed` once per form served (not while the
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
                 one data-face line of facts the API returns (exchange · quote · CIK as EDGAR prints it, ten
                 digits · "Company on SEC EDGAR ↗"), then "Latest filing" form · period · filed date · "summary
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
                 between), the summary's opening, the figures as ONE hairline strip (<dl> grid-cols-3, border-y
                 + divide-x; ▲/▼ aria-hidden before the signed delta), one evidence row when the live summary
                 has a located risk excerpt (pickEvidence: source_verified under the source owner; heading =
                 excerptHeadings, blockquote clipped at 180 on a word with " …", a chip link "Located in the
                 filing"), the EDGAR receipt, and a text-link CTA. No browser-frame mockup, no card in the
                 card, no sparkle chip, no tinted CTA. The static fallback has no evidence row.

Trust strip      <TrustStrip>  under the hero: a hairline-topped list of plain statements, each scoped to what
                 the implementation establishes ("where a match is found"); "generated" stays distinct from
                 "the filing's own words".

Evidence rows    <SummaryRisks>  (P-03) — one hairline list inside the section: a row is an h3 (14/600, the
                 opening words of the row's own verbatim excerpt, unique per row via excerptHeadings — the
                 server withholds model titles), the excerpt in blockquote manners (border-l-2 hairline, no
                 fill, no radius, 14px secondary) and the provenance chip; a lead line above and a data-face
                 tally below ("3 of 4 excerpts located in the filing text · 1 withheld …"). No stripe, no
                 trend glyph, no nested evidence box. The row wraps a long unbreakable token
                 ([overflow-wrap:anywhere]).
                 Heading rule (riskHeadline.ts, inside excerptHeadings): a verbatim prefix of the excerpt, never
                 recased and never whitespace-normalised (one enclosing quote pair is dropped first, only when
                 it wraps the whole span). The first sentence stays whole when it fits in 100 characters; a
                 longer one is cut at its first ";" or ":" only where the clause can stand as a heading,
                 otherwise capped on a whole content word that splits no figure from its unit or label, no
                 date, name, bracket or quotation. Never at a comma or a dash. "…" whenever the excerpt goes
                 on; "Risk n" when no heading fits. Gates: riskHeadline.spec.ts (the rule, on the production,
                 backend-fixture and eval spans), riskTitle.spec.ts (what excerptHeadings adds around it),
                 SummaryRisks.spec.tsx (the wiring), tests/e2e/risk-evidence-rows.spec.ts (layout).

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
                 smoothly, or in one jump under prefers-reduced-motion. A box names itself only when it
                 starts to overflow, never on every resize (the name scans the whole reader). The AI
                 summary's `.markdown-body` is untouched. Gates: tests/unit/highlightInDom.spec.ts,
                 tests/unit/readerTableRegionName.spec.ts, tests/e2e/filing-reader-wide-tables.spec.ts
                 (synthetic fixture text, 1440x900 and a 390x844 touch sheet) and
                 tests/e2e/copilot-highlight-css.spec.ts (a far-right table cell revealed in its own box
                 in real layout, the page unmoved).

Ask answer       <AskFilingAnswer>  — the SHIPPED copilot contract: status reading|done|error (this reference
                 also draws a `streaming` caret state; the production renderer has none);
                 answer = GFM markdown (react-markdown + remark-gfm); markers [n] AND [F1]/[f1]/[F 1]
                 (case/whitespace tolerant) become chips showing the BRACKETED marker; unmatched markers
                 stay literal text — never a dead button. CopilotCitation = { n, excerpt, section_ref,
                 verified, fragment_url } — `verified` drives source attribution: checked sources show
                 “Source match found” with its scope (not whole-answer verification); unmatched sources
                 stay “Cited” in legacy/reference rendering. New Ask-this-Filing responses wait for
                 an admitted completion; failed referenced citations and draft answer text are
                 withheld before reaching this renderer. Numeric/text grouping is not a separate
                 attestation. Never conflate source matching with support for every answer claim.
                 REPO REALITY: this file is the design-system REFERENCE implementation (0 importers).
                 The wired production renderer is features/filings/components/copilot/CopilotMessage.tsx,
                 which implements the same contract plus viewer deep-linking, popovers and follow-ups —
                 change copilot rendering THERE, styled to this design. Its answers arrive whole: the
                 rail takes a message from reading (one pulse dot, "Reading the filing…") straight to
                 done or error; there is no streaming status, token text or caret.
                 Its links print what the model wrote: an answer's own links take the prose links' rule
                 (`.copilot-answer`) and keep their weight, and a source's locator ("Item 7. MD&A")
                 composes countControlClass('link') with the new-tab icon, "(opens in a new tab)" for a
                 screen reader (D-030).
```

- **Radius scale is 4 / 8 / 12 / 16 / 24** — buttons + inputs 12 (`rounded-lg`), chips full,
  cards 16 (`rounded-xl`). Config `md` (10px) is legacy off-scale — don't use in new code.
- **Skeleton a11y (codified v2.2):** `SkeletonText`/`SkeletonStat` carry their OWN `role="status"` +
  sr-only label — never wrap them in another `role="status"` (double announcement). Raw `<Skeleton>`
  bones are `aria-hidden` — a wrapper composed of raw bones needs `role="status"` + an sr-only label.
- **Evidence identity:** the Ask-this-Filing header tile uses the Phosphor `quotes` glyph, as does a
  provenance chip that cites a filing passage (braces for an XBRL figure); the Ask tab, the Ask callout and
  the follow-up prompts use `chat-circle-text`, the Filing tab and the Source launcher `file-text`.
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
The footer opens its own section with a visually hidden h2 ("Site links") before its h3 column
titles, so a page whose content ends at h1 (the 404, /analysis, /search) does not jump from h1 to h3.
`tests/e2e/text-floors.spec.ts` checks the routes and states it visits, in DOM order and in the
accessibility tree: home, /pricing, /company/AAPL, /filing/3 with a summary, a signed-in /dashboard,
the 404, /waitlist (its problem cards are h2, since the example beside the form has no heading),
/login, /register, /forgot-password, /check-email, /verify-email and /reset-password (the auth shell,
which has no site footer; the two token pages are opened without their emailed token), /contact,
/privacy, /terms, /security, /delete-account, /search while its flag is off (the 404), and four
page-level card states (a filing without a summary for a guest and for a signed-in reader whose run
fails, a writer error, an empty watchlist). Three census cases hold that list to its sources:
`STATIC_ENTRIES` in `app/sitemap.ts`, `AUTH_ROUTES` in `lib/authShellRoutes.ts`, and every
`page.tsx` under `app/`, static or dynamic (a dynamic route by a representative path, /company/AAPL
for `/company/[ticker]`), which the spec must visit or name in `NOT_VISITED` with its reason (the
admin pages, the API-rendered /analysis, /calendar and /dashboard/settings, the labs prototypes).
Each fails, naming the path, when a route has no entry, and a reason for a page the spec visits, or
that no longer exists, fails too.

## 6. Cards must *lift*, not tint

`brand-weak` (#ECF2EE) is **darker** than the cream page (#F4F3EE) — as a card *fill* it's
~1.02:1 (invisible). Cards on cream use a **lighter** fill (`panel-light`) + hairline + soft
`shadow-e*`; **brighten** on hover (`hover:bg-white`), never darken. In dark, separation is fill
contrast + hairline with `shadow-none`. `brand-weak` is an accent/hover/tint color only.

## 7. Marketing surfaces

Flat **solid** surfaces — no decorative gradients anywhere; the only glow is the theme-aware hero
search glow. The hero accent phrase sits on the primary ink and carries the brand device's mark
(`.en-mark`, below), not sage ink; sage ink stays for links and the wordmark's italic.
`.mockup-frame` is flat navy (the decorative slate gradient is retired), 16px radius, paired with
`shadow-e3`; its title-bar traffic-light dots are gone. Marketing cards use the `<Card>` recipe
(panel + hairline + e2, brighten on hover); the popular-company chips and the reporting tiles are
the same surface at e1, per the design. `.glass-card` is retired on the landing route (its
remaining consumer is `AuthShell`). Container rhythm on the landing: hero + header `max-w-7xl`,
every other section `max-w-5xl`, section padding `py-20 sm:py-24` (the measured-claims band is a
tighter hairline strip). Muted text on the cream page ground is `text-secondary`;
`text-tertiary-light` (`#636A77`, 4.9:1 on cream) carries captions, counts and micro-labels on either
ground; copy the reader must read stays secondary, including the point-of-use AI disclaimer
(`AiDisclaimer`) and the footer's "Data sourced from SEC EDGAR … Not investment advice" line. Gate:
`tests/e2e/text-floors.spec.ts` measures every tertiary-ink text on the main routes against its
rendered ground.

**The brand device: the margin and the mark** (2026-10 brand studio; `DESIGN.md` › Graphic device;
`docs/brand/06-system.md` §6). Four classes in `globals.css`, each a light/dark pair:
`.en-mark` (a phrase highlight: pale sage tint from 62% of the line box, a 2px `brand-border`
inset hairline at the baseline, `box-decoration-break: clone` so a wrapped phrase marks per line),
`.en-marked` (a located passage: 3px `brand` bar on the left, tint behind, square corners because a
stripe never sits on a rounded container, the filing's words inside it in `.filing-reader`'s face), `.en-margin` (a gutter with a hairline on its
inner edge; `w-11` from `sm`, `w-9` on phones) and `.en-margin-mark` (an 11px data-face bracket,
`brand-strong`, absolutely positioned on the line of the in-text marker it twins; the twin is
measured by `features/marketing/components/MarkedCopy.tsx`, never hard-coded). Rules: a mark means
"located" and a bracket means "cited"; one `.en-mark` per surface may sit under a phrase of ours as
the signature; none on a figure, a price, a status, a competitor's name or an unverified claim; no
margin without a marker; the hairline never scales with the type. The 11px mark is the one
sanctioned sub-12px text beside copy because it is a twin of a 12px marker, not copy; it still
carries no claim and is `aria-hidden` (the in-text marker is the accessible one).

## 8. Theme mechanics

- **One** `<ThemeToggle/>`, in the global `Header` (desktop + mobile). No page-level toggles.
- `app/layout.tsx` runs a **pre-paint theme bootstrap script** (saved `localStorage.theme`, else
  light; there is no system-preference detection) to prevent FOUC, and `ThemeProvider` re-syncs to
  the same value after hydration. Keep `suppressHydrationWarning` on `<html>`.
- Logo: `<EarningsNerdLogo mode="auto" />` follows the app theme — don't hardcode `mode="dark"`.
- Fonts are self-hosted via `next/font` (Inter with `axes: ['opsz']`, Geist Mono, Newsreader) —
  see `app/layout.tsx`; SF Pro / New York are platform-licensed and must never be embedded.

## 9. Exemptions

- **Google / Apple sign-in buttons**: keep their brand-mandated surfaces (white / black). Only
  their focus rings get rebranded.
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
  from the render where `loading` turns false (DataTable, AskFilingAnswer, the account settings and
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
