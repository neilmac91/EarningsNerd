# Theme-responsive marketing + brown-heading fix

User chose "Theme-responsive marketing": make the landing/marketing pages fully respect
light/dark (cream in light, navy in dark) + a global theme toggle, AND fix the brown-heading
regression. Branch: claude/dark-theme-fix (off merged main).

## Root cause of the brown bug
globals.css global rule `h1-h6 { color: var(--heading-color) }` paints light-theme brown
(#3A2E26) on the always-dark landing in light theme (site defaults to light). Only the hero
h1 (app/page.tsx:128, no explicit color) actually breaks today, but the rule is a footgun.

## Design decisions (light-theme variants for dark-only marketing effects)
- Page/sections: `bg-slate-950 text-white` wrapper -> `bg-background-light text-text-primary-light dark:bg-background-dark dark:text-text-primary-dark`.
- hero-gradient: light = warm cream with subtle sage/slate tint; dark = current navy/purple. Make theme-aware.
- cta-gradient: light = soft sage->cream; dark = current. hero-glow: light = faint sage; dark = current mint->keep subtle.
- .glass-card: light = translucent white (rgba(255,255,255,0.7)) + light border; dark = current dark glass.
- .mockup-frame: light = soft gray gradient + light border; dark = current.
- .hero-search-glow: rebrand mint->brand, theme-aware (sage light / slate dark).
- .text-gradient-mint -> rebrand to brand gradient (sage/slate), theme-aware. (Keep class name or add brand alias.)
- Accent: legacy mint -> brand (sage light `brand-strong`/`brand-light`, slate dark `brand-dark`/`brand-strong-dark`).
- Headings on these surfaces: explicit `text-text-primary-light dark:text-text-primary-dark`.

## Phases
- [ ] P1 globals.css: remove heading-color footgun (keep font); make .glass-card/.mockup-frame/.hero-search-glow/.text-gradient theme-aware + rebranded.
- [ ] P2 tailwind.config.js: theme-aware (or -light variants of) hero-gradient/cta-gradient/hero-glow.
- [ ] P3 layout.tsx: add pre-paint theme bootstrap script (read 'theme' + system pref, set .dark before paint) to kill FOUC. Keep suppressHydrationWarning.
- [ ] P4 Global chrome: add <ThemeToggle/> to SiteHeader (components/SiteChrome.tsx / Header.tsx); make Header + Footer theme-responsive.
- [ ] P5 Marketing components -> theme-responsive token pairs + mint->brand + explicit heading colors:
      app/page.tsx, HowItWorks, FeatureShowcase, AccuracySection, CtaBanner, HeroExample, SocialProofStrip,
      HotFilings, CompanySearch (hero variant), AuthShell, DashboardPreview, AccuracySection. (agents, with mapping)
- [ ] P6 Verify: typecheck, lint, build, vitest; check both themes render (preview). PR (draft).

## Notes
- FOUC script is REQUIRED now (theme-responsive landing would flash without it).
- ThemeProvider default stays 'light' + system-pref; the bootstrap script must mirror that logic.
- Keep mint as legacy alias in tailwind (don't remove) — only swap usages.
