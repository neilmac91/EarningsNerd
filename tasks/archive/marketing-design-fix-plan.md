# Marketing design-fix plan (preview feedback round)

PR #403 / branch claude/dark-theme-fix. User reviewed the Vercel preview and flagged 3 issues.
Decisions (via clarifying questions): gradients -> FLAT SOLID surfaces; accent word -> SOLID brand accent.

## Confirmed tokens (tailwind.config.js)
- background.light #F4F3EE (cream) / background.dark #0B1120 (deep navy)
- panel.light #FBFAF6 / panel.dark #1F2937 (gray-800)
- brand.strong #3C6650 (sage, AA on cream) / brand.strong-dark #B4BEEE (slate) / brand.weak #ECF2EE (tint) / brand.dark #92A0E2
- text.primary.light #1A1A17 (espresso near-black) — ticker ink; text.heading.light #3A2E26 (warm brown)

## Issue 1 — CTA gradient (emerald->navy->indigo), DARK screenshot -> FLAT SOLID
- CtaBanner.tsx L10: `bg-cta-gradient-light dark:bg-cta-gradient` -> `bg-brand-weak dark:bg-panel-dark` + `border border-border-light dark:border-white/10`.
- Remove the decorative ambient-glow blob div in CtaBanner (flat solid).

## Issue 2 — "SEC filing" two-hue text gradient -> SOLID brand accent
- app/page.tsx L130: `<span class="text-gradient-mint">` -> `text-brand-strong dark:text-brand-strong-dark` (sage #3C6650 light / slate #B4BEEE dark).
- globals.css: remove the `.text-gradient-mint` rule (light + .dark) — retired, no remaining usages.

## Issue 3 — QuickAccessBar "Popular companies" tickers white in light -> espresso (FULL conversion; was missed)
- L27 label slate-400 -> secondary pair.
- L36 chip: `border-white/10 bg-white/5` -> `border-border-light bg-panel-light dark:border-white/10 dark:bg-white/5`; hover mint -> brand (`hover:border-brand-strong hover:bg-brand-weak dark:hover:border-brand-dark dark:hover:bg-white/10`, drop colored shadow -> `hover:shadow-e2`); focus `ring-mint-500 ring-offset-slate-900` -> `ring-brand-light ring-offset-background-light dark:ring-offset-background-dark`.
- L39 ticker `text-white` -> `text-text-primary-light dark:text-text-primary-dark` (ESPRESSO fix).
- L40 name slate-400 + group-hover mint -> secondary pair + group-hover brand.

## "Not applicable elsewhere" — flat-solid + de-hue the rest (sweep findings)
- app/page.tsx L120 hero `bg-hero-gradient-light dark:bg-hero-gradient` -> `bg-background-light dark:bg-background-dark` (drops the purple corner; dark hero stays deep navy).
- app/page.tsx L122 + AuthShell L47: remove the decorative `bg-hero-glow*` overlay divs (flat solid).
- AuthShell L46 brand pane `bg-hero-gradient*` -> `bg-background-light dark:bg-background-dark` (or panel) — solid.
- ExampleSummaryCard.tsx (MISSED component): L39 avatar `from-mint-400 to-cyan-400` -> brand gradient (match HeroExample); L42/53-54 text-white -> primary pair; L43/47/53 slate -> secondary; metric deltas -> gain/loss if financial. (Verify where it renders during impl.)
- TrendingCompanies.tsx L47-48: off-brand `from-sky-500 to-indigo-500` icon tile + text-white -> standard brand icon tile `bg-brand-strong/10 text-brand-strong dark:bg-brand-dark/15 dark:text-brand-strong-dark`. [JUDGMENT CALL — overrides a deliberate keep from the migration; aligns with "single brand accent".]

## tailwind cleanup
- Remove the 6 now-unused backgroundImage tokens: hero-gradient, hero-glow, cta-gradient (+ -light variants). Grep to confirm zero refs before removal.

## Verify
- grep: zero remaining `hero-gradient|cta-gradient|hero-glow|text-gradient-mint`.
- typecheck, lint (--max-warnings 0), build (24 pages), vitest. Push to #403; check both themes on preview.
