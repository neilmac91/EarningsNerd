# Implement: EarningsNerd Design System (design handoff)

Source: `earningsnerd-design-system` handoff bundle (Claude Design export).
Primary design: `EarningsNerd Design System.dc.html` — a **design system** (tokens +
type roles + a font switcher), not a screen mockup. The `/code` folder ships four
production-ready files meant to be spliced into the existing Next.js App Router frontend.

## What the design changes (vs. current frontend)

The handoff `tailwind.config.js` / `globals.css` are **supersets** of the live files
(identical content globs, plugins, keyframes, animations, markdown + citation styles)
plus the intended design deltas:

- **Warm cream surface**: `background.light` `#FFFFFF` -> `#F4F3EE`; `panel.light` `#F9FAFB` -> `#FBFAF6`.
- **Subdued, theme-aware brand accent** (replaces neon mint as the *primary*; mint kept as legacy alias):
  Sage `#4F7A63`/`#3C6650` in light, Slate `#92A0E2`/`#B4BEEE` in dark.
- **Financial data semantics** distinct from brand: `gain`/`loss`/`flat` (+ soft tints).
- **UI state** colors (`success`/`warning`/`error`/`info`) + 6-color `chart` palette.
- **Three type roles**: headings = Helvetica/Arial (fixed), body = Figtree (webfont, switchable),
  technical/data = monospace. Plus type scale, radii, spacing, elevation (`e1..e5`) + focus rings.
- Softer text ink: `text.primary.light` `#111827` -> `#1A1A17`, `text.primary.dark` `#FFFFFF` -> `#D7DADC`;
  new `text.heading` (warm brown `#3A2E26` light / off-white dark).

Foundation changes are global but respect explicit utility overrides (Tailwind class
specificity beats the `h1`/`body` element rules), so existing components keep their styling.

## Decisions (sensible defaults - not blocking)

1. **Merge, don't blind-overwrite.** The handoff files are verified supersets, so the result
   is effectively the handoff version + re-added niceties (JSDoc type, detailed content-glob comment).
2. **Load Figtree via `next/font/google`** (self-hosted, no FOUC, no Google network request) instead
   of the README's `<link>` - strictly better and consistent with the current Inter setup. Drop Inter.
3. **Surface the `FontSwitcher`** in dashboard settings (Appearance section) so the feature is reachable.
4. **FontSwitcher active/focus state uses the new `brand` tokens** (`bg-brand-strong` / `dark:bg-brand-dark`,
   `shadow-ring-brand`) instead of the handoff's neon `bg-mint-500` / non-existent `shadow-ring-mint`
   - consistent with the design's whole point (move off neon mint) and fixes a broken class.

## Tasks

- [x] 1. `frontend/tailwind.config.js` - adopt design tokens (merge; keep @type + content-glob comment).
- [x] 2. `frontend/app/globals.css` - adopt font-role vars + helpers; wire `--font-body` to next/font Figtree.
- [x] 3. `frontend/components/FontProvider.tsx` - add (FontProvider + useFont + FontSwitcher), brand-token styling.
- [x] 4. `frontend/app/layout.tsx` - Figtree via next/font, `data-font` bootstrap script, wrap with FontProvider.
- [x] 5. `frontend/app/dashboard/settings/page.tsx` - add Appearance section with `<FontSwitcher />`.
- [x] 6. Verify: typecheck clean, lint clean (max-warnings 0), build OK (24 pages), 173 unit tests pass.
- [ ] 7. Commit, push to `claude/exciting-heisenberg-qts27r`, open draft PR.

## Review

Implemented as planned. 5 files touched in `frontend/`:
- `tailwind.config.js`, `app/globals.css` — design tokens + font roles (verified supersets of the originals;
  all prior animations/markdown/citation styles preserved).
- `components/FontProvider.tsx` (new) — context + `useFont()` + `<FontSwitcher />`.
- `app/layout.tsx` — Inter → Figtree (next/font, self-hosted), `data-font` pre-hydration bootstrap, FontProvider wrap.
- `app/dashboard/settings/page.tsx` — Appearance section surfacing the switcher.

`app/global-error.tsx` keeps its own self-contained Inter import (isolated crash page; not via the
removed `--font-inter` var) — intentionally left untouched.

### Foundational global shifts (intended by the design system, not regressions)
- Page surface: white → warm cream `#F4F3EE`; softer text ink; headings → Helvetica + warm-brown ink.
  (Element-level rules; explicit Tailwind utility colors/fonts on components still win, so existing
  styled components are unaffected.)
- Radius scale + type scale tokens are now design-system values (`rounded`/`rounded-md`/`text-base`
  line-heights changed app-wide) — the point of adopting the system. Mint kept as a legacy alias so
  no component accent breaks; brand→sage/slate migration of individual components can follow incrementally.

### Verification
- `npm run typecheck` ✓ · `npm run lint` (max-warnings 0) ✓ · `npm run build` ✓ (24/24 pages) · `vitest` ✓ 173/173.
