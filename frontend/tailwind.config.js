const { fontFamily } = require('tailwindcss/defaultTheme')

/* =============================================================================
   EarningsNerd — Tailwind token system
   -----------------------------------------------------------------------------
   Replaces the existing config. Additive except the documented retirements
   (animate-count-up, fade-up-delay-1/2/3 — see DESIGN_SYSTEM.md §11):
     - fontFamily = the three FIXED type-v2 roles (heading / body / data; the
       runtime font switcher is retired) + legacy aliases so old classes resolve
     - financial data semantics (gain / loss / flat) — DISTINCT from the sage
       brand accent, so "brand" never reads as "price went up"
     - state colors (success / warning / error / info), light + dark
     - a categorical chart palette
     - typography scale, radii, spacing additions, elevation + focus-ring shadows
     - motion: transitionDuration / transitionTimingFunction + every animation
       reference the --duration-* / --ease-* tokens (raw ms + bezier values live
       ONLY in globals.css :root and the JS mirror lib/motion.ts)
   Every color pair is AA (>= 4.5:1) for body text on its intended surface.
============================================================================= */

// Financial data signal — deliberately NOT the sage brand. Sage is identity; this is data.
const gain = {
  light: '#16A34A',  // green-600 — GRAPHIC/chip value only: 3.0:1 on cream (meets the 3:1 non-text floor for bars/sparklines, FAILS AA for text)
  text: '#15803D',   // green-700 — delta TEXT on cream/white (4.5:1); lib/financialTone directionText resolves to this
  dark: '#34D399',  // emerald-400 — 9.7:1 on navy, text-safe
  soft: '#DCFCE7',
  softDark: 'rgba(52,211,153,0.14)',
  // Change text on the analysis figure surfaces (the metrics table's well and the KPI cards), held to APCA
  // |Lc| >= 75: green-800 is Lc 82.6 on the light well and 81.3 on panel (the 700 is 72.4 / 71.1). Dark matches
  // loss.dataDark (rose-200, Lc -83.1 / -80.1) in lightness and chroma, so neither direction reads louder: Lc -83.5 on
  // the dark well and -80.5 on panel, OKLCH chroma 0.056 against rose-200's 0.056 (emerald-300 #6EE7B7, at 0.130 and
  // -78.5 / -75.5, outshouted the loss beside it; emerald-400 is -65.6 / -62.6). Level inks give colour-blind readers
  // no lightness cue: under deuteranopia (Machado 2009, full severity) the pair is ΔE76 2.1 (emerald-300's was 7.2),
  // protanopia 8.8. The sign carries direction for every reader (the drawn minus is as wide as the plus).
  data: '#166534',
  dataDark: '#B6E4CE',
}
const loss = {
  light: '#DC2626',  // red-600 — GRAPHIC/chip value only: 4.0:1 on cream / 4.4:1 on white (FAILS AA for text)
  text: '#B91C1C',   // red-700 — delta TEXT on cream/white (5.8:1); lib/financialTone directionText resolves to this
  dark: '#FB7185',  // rose-400 — 7.0:1 on navy, text-safe
  soft: '#FEE2E2',
  softDark: 'rgba(251,113,133,0.14)',
  // Figure surfaces, APCA |Lc| >= 75: red-700 already holds Lc 78.4 / 77.2 in light; dark needs rose-200,
  // Lc -83.1 on the dark well and -80.1 on panel (rose-400 is -49.7 / -46.7, the weakest ink on the table).
  data: '#B91C1C',
  dataDark: '#FECDD3',
}
const flat = {
  light: '#6B7280', // gray-500
  dark: '#9CA3AF',  // gray-400
}

// E120 (chief design, 2026-10-19): under enlarged text a surface's inset stops growing at narrow widths.
// Padding step N becomes `p-cap-N` = min(N × 0.25rem, N vw): the step itself from a 25rem viewport up
// (400px at the default text size, 800px under a 200% text setting) and N% of the viewport below it, so a
// p-6 card keeps 24px at 1440px, 23.4px at 390px and 19.2px at 320px, and 19.2px at 320px under 200% text
// instead of 48px. A Card, a frame and a dialog's sections take it from step 5, a frame inside a dialog's
// body from step 4 (gate: the ESLint rule earningsnerd/surface-padding-cap, eslint.designRules.mjs, which
// reads these keys). The Modal panel's scroll padding takes the same value as its capped inset.
const PADDING_CAP_STEPS = [3, 4, 5, 6, 8, 10]
const paddingCap = Object.fromEntries(PADDING_CAP_STEPS.map((n) => [`cap-${n}`, `min(${n * 0.25}rem, ${n}vw)`]))

module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    // Domain modules (the "Ask this Filing" Copilot, etc.) live here. Without this glob, Tailwind
    // never scans them, so any class used ONLY in features/ is purged in production.
    './features/**/*.{js,ts,jsx,tsx,mdx}',
    './hooks/**/*.{js,ts,jsx,tsx,mdx}',
    // Shared class maps (lib/financialTone's directionChip, etc.) are composed here, not in JSX.
    // Without this glob, every class used ONLY in lib/ is purged in production — the chips lost
    // their /20 borders and the flat tint. designSystemDoneGate.spec.ts fails when an unscanned app
    // module composes a hyphenated, variant, opacity or arbitrary-value class.
    './lib/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // ---- Core surfaces (unchanged) ----
        background: {
          light: '#F4F3EE', // warm cream (not stark white — friendlier, less clinical)
          dark: '#0B1120',  // deep navy
        },
        panel: {
          light: '#FBFAF6', // warm off-white card
          dark: '#1F2937', // gray-800
        },
        // ---- Brand accent: a single Sage across BOTH themes ----
        // Sage replaces the former Sage/Slate split AND the legacy neon mint.
        // USAGE: DEFAULT is a FILL (white text on it) — never use it as text on
        // cream; use `strong` for accent text/links. `*-dark` values are brightened
        // to read as text/accents on navy. Never use brand in a numeric/price context.
        brand: {
          DEFAULT: '#4F7A63', strong: '#3C6650', emphasis: '#345C48',
          weak: '#ECF2EE', border: '#CFE0D6',
          dark: '#7FB295', 'strong-dark': '#98C5AD', 'fill-dark': '#569272',
          'weak-dark': 'rgba(127,178,149,0.14)', 'border-dark': 'rgba(127,178,149,0.28)',
        },

        // ---- Financial data semantics (NOT the brand accent) ----
        gain: {
          DEFAULT: gain.light,
          light: gain.light,
          text: gain.text,
          dark: gain.dark,
          soft: gain.soft,
          'soft-dark': gain.softDark,
          data: gain.data,
          'data-dark': gain.dataDark,
        },
        loss: {
          DEFAULT: loss.light,
          light: loss.light,
          text: loss.text,
          dark: loss.dark,
          soft: loss.soft,
          'soft-dark': loss.softDark,
          data: loss.data,
          'data-dark': loss.dataDark,
        },
        flat: {
          light: flat.light,
          dark: flat.dark,
        },

        // ---- UI state ---- (light values sized for the warm cream surface, not white)
        success: { light: '#15803D', dark: '#22C55E' }, // was #16A34A — 3.3:1 as text; green-700 holds 4.5:1 on cream
        warning: { light: '#92400E', dark: '#F59E0B' }, // was #B45309 — 3.8:1 inside its 13% tint; amber-800 holds 5.2:1 in-tint, 6.4:1 on cream
        error: { light: '#B91C1C', dark: '#F87171', emphasis: '#991B1B' }, // was #DC2626 (white label = 4.4:1); red-700 fill = 6.5:1, emphasis = destructive hover, 8.3:1
        // info.text (blue-700): the in-tint LABEL ink — #2563EB inside its own 10% tint
        // is 4.3:1 on cream (icon/graphic only there); #1D4ED8 holds 5.6:1 in-tint, 6.0:1 bare.
        info: { light: '#2563EB', text: '#1D4ED8', dark: '#60A5FA' },

        // ---- Categorical chart palette (subdued, warm-leaning, cohesive) ----
        // SEQUENCE, not a pick-list: series take 1→N in order, never skipped or re-sorted.
        // CVD-validated (deuteranopia + protanopia, Machado 2009 sim, ΔE Lab):
        //   · resequenced so the blue↔yellow axis — the one hue axis dichromats keep —
        //     alternates early; every ADJACENT pair holds ΔE ≥ 41 through 5 series
        //   · chart.2 honey darkened #D99E4A → #B8812F (was 2.1:1 on cream — failed the
        //     3:1 non-text floor); every value is now ≥3:1 vs BOTH cream #F4F3EE and
        //     navy #0B1120, so one hex per series serves both themes
        //   · known limits: chart.5+6 converge for dichromats (ΔE ~16), chart.6 vs
        //     chart.3 is near-identical for protanopes (ΔE 3) — at ≥5 series color no
        //     longer carries alone: add direct labels, markers, or dash patterns
        // Gain/loss NEVER appear as series colors (direction only — see Chart.tsx),
        // and the sage brand NEVER appears inside a plot area.
        chart: {
          1: '#3E8E84', // teal        — cream 3.5:1 · navy 4.9:1
          2: '#B8812F', // honey       — cream 3.0:1 · navy 5.6:1 (darkened from #D99E4A)
          3: '#5B7CC0', // cornflower  — cream 3.7:1 · navy 4.6:1
          4: '#CF7159', // coral       — cream 3.1:1 · navy 5.5:1
          5: '#6E7E9C', // slate-blue  — cream 3.7:1 · navy 4.6:1 (non-green — never competes with sage)
          6: '#8B7BC0', // periwinkle  — cream 3.3:1 · navy 5.1:1 (protan-twin of chart.3 — label directly)
          // ---- Chart chrome sub-tokens (all derived from surface/text/flat tokens) ----
          grid: { light: 'rgba(229,231,235,0.6)', dark: 'rgba(255,255,255,0.06)' }, // hairline @ 60% — quieter than the axis
          axis: { light: '#E5E7EB', dark: 'rgba(255,255,255,0.10)' },               // = the hairline itself
          // Axis labels: 11–12px data face + tabular-nums. Light = the flat ink #6B7280 (4.6:1 on
          // the card charts sit on; on bare cream use secondary). Dark = text.TERTIARY, gray-400 #9CA3AF
          // (7.4:1 on navy), chrome that stays quieter than the secondary ink.
          label: { light: '#6B7280', dark: '#9CA3AF' },
          crosshair: { light: 'rgba(107,114,128,0.45)', dark: 'rgba(156,163,175,0.4)' }, // flat @ ~45%, dashed 3 3
          ref: { light: '#6B7280', dark: '#9CA3AF' },   // zero/reference line = flat tokens — 4.4:1 / 7.4:1 (hairline-as-meaning ≥3:1)
          tip: { light: '#FBFAF6', dark: '#1F2937' },   // tooltip surface = panel + hairline; shadow-e2 light / shadow NONE dark
          // ---- The trend charts' spec renderer (docs/design/analysis-trend-charts-spec-2026-10.md §3.8) ----
          // Behind NEXT_PUBLIC_CHARTS_V2 until the founder's F66 decision; features/analysis/lib/charts/theme.ts
          // mirrors them, and no class names them yet. Light/dark pairs of their own, not dark siblings of
          // chart-1…6 or new chart.label/grid values: those would repaint the landing page's RevenueBars
          // and today's charts (Chart.tsx). APCA Lc on the card (panel): tests/unit/chart-apca.spec.ts.
          s1: { light: '#3E8E84', dark: '#62B2A6' }, // = chart-1 · dark Lc −49.7 (chart-1 is −32.0 on the dark card)
          s2: { light: '#B8812F', dark: '#D3A55C' }, // = chart-2 · dark Lc −54.2
          s3: { light: '#5B7CC0', dark: '#8CA6E3' }, // = chart-3 · dark Lc −50.9
          s4: { light: '#CF7159', dark: '#E8927C' }, // = chart-4 · dark Lc −51.9
          s5: { light: '#6E7E9C', dark: '#97A6C2' }, // = chart-5 · dark Lc −50.1
          s6: { light: '#8B7BC0', dark: '#AFA2DE' }, // = chart-6 · dark Lc −52.8
          tick: { light: '#636A77', dark: '#B8BEC7' },     // = text.tertiary · dark Lc −63.6 (tertiary-dark, gray-400, is −48.6)
          value: { light: '#374151', dark: '#D7DADC' },    // = text.secondary · dark the plot's own, the old text.primary.dark (#1606 raised that to #EAECEF)
          gridline: { light: '#DCD9D0', dark: '#525C6B' }, // Lc 16.8 / −15.0: visible, quieter than the zero rule
          review: { light: '#92400E', dark: '#FBBF24' },   // = warning · dark Lc −70.2 (warning-dark is −56.9)
        },

        // ---- Text ----
        text: {
          // primary.dark #EAECEF, the figure surfaces' ink (was #D7DADC, 1.05:1 from the gray-300 secondary): APCA Lc
          // -94.8 on navy and -91.8 on panel, and 1.24:1 above secondary, so in dark body copy stands over its
          // supporting text by ink as well as by size and weight (light's pair is 1.69:1).
          primary: { light: '#1A1A17', dark: '#EAECEF' },
          // v2: ONE heading ink — same espresso as body (walnut #3A2E26 retired); hierarchy comes
          // from size + weight, never a second color.
          heading: { light: '#1A1A17', dark: '#EAECEF' },
          // secondary.dark #D1D5DB (gray-300; was gray-400 #9CA3AF, APCA Lc -48.6 on panel for 12px copy): Lc -77.3 on
          // panel, -80.3 on navy, so secondary reads in dark as it does in light (90.9 on panel). Secondary carries
          // anything that must be read.
          secondary: { light: '#374151', dark: '#D1D5DB' },
          // tertiary.light #636A77 (P-02, 2026-10 critique; was gray-500 #6B7280 = 4.35:1 on cream, an AA
          // fail at 12px): 4.9:1 on cream, 5.2:1 on panel, 4.8:1 in the brand-weak tint. tertiary.dark is its
          // dark twin, de-emphasised but readable: gray-400 #9CA3AF, the ink tertiary text has always shown in dark
          // (5.8:1 on panel, 7.4:1 on navy; it was secondary.dark's value, and #4B5563 failed as text at 2.9:1).
          tertiary: { light: '#636A77', dark: '#9CA3AF' },
        },
        // ---- Borders ----
        border: {
          light: '#E5E7EB', // gray-200
          dark: '#374151', // gray-700
        },

        // ---- Analysis figure surfaces (the metrics table's sheet, the KPI cards' figures) ----
        // Measured with APCA (apca-w3 0.1.9) against the actual ground; targets by role: figures and metric names
        // |Lc| >= 90 (Bronze: non-body text no smaller than 12px), change lines and labels >= 75, marks >= 60, rules >= 15
        // and a hovered row's rules >= 30. The table's heading row and metric column stay on panel (DataTable's well frame).
        // well: the sheet the figures sit on inside the panel Card. Platinum white is cooler and brighter than the warm
        // panel framing it; near-black is the navy ground itself, so the sheet reads as recessed in dark.
        well: { light: '#FCFCFD', dark: '#0B1120' },
        // rule: row hairlines and the sheet's outline, on the sheet and on the panel-coloured frame (border-light is Lc
        // 10.0 on the sheet, 8.8 on panel): 16.5 / 15.3 light, -18.8 / -15.9 dark. strong: a hovered row's two rules, the
        // hover that leaves every text pair unchanged: 35.8 / 34.5 light, -33.8 / -30.9 dark.
        rule: { light: '#D9DCE1', dark: '#545E6D', 'strong-light': '#B5BAC2', 'strong-dark': '#768090' },
        // figure: values and metric names. Espresso is Lc 102.5 on the sheet and 101.3 on panel; dark is -94.8 on the
        // sheet and -91.8 on panel (gray-200 #E5E7EB is -88.7 on panel), the value text.primary.dark took app-wide.
        figure: { light: '#1A1A17', dark: '#EAECEF' },
        // note: flat changes, †, neutral letters and the missing-value token on the sheet: Lc 75.4 / -80.3.
        note: { light: '#636A77', dark: '#D1D5DB' },

        // v3: the ONE modal/sheet scrim (brand navy @ 55%), both themes —
        // replaces the bg-slate-950/60 and bg-black/50 hand-rolls.
        overlay: 'rgba(11, 17, 32, 0.55)',
      },

      fontFamily: {
        // Type v2 — three FIXED roles (not user-selectable). Must mirror the CSS vars in globals.css.
        // next/font declares each family under its plain name and exposes it as a CSS var
        // (--font-inter / --font-geist-mono / --font-newsreader, declared once in app/fonts.ts), the
        // contract, so every stack LEADS with its next/font variable; the literals are fallbacks (Option B /
        // non-Next consumers). EXCEPTION: `body` is system-first BY DESIGN — -apple-system stays
        // first and the var precedes generic system-ui; do not "fix" it to lead. PACKAGING GATE:
        // every fontFamily stack and :root font var leads with its next/font variable (body: the
        // var leads the WEBFONT portion) — this wiring was missed in BOTH the v2 and v2.1 exports.
        // Headings: Inter loaded WITH the variable opsz axis — font-optical-sizing:auto gives the
        // SF-style Text↔Display optical cuts. ONE display weight: 600.
        heading: ['var(--font-inter)', 'Inter', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
        // Body & UI: system-first — Apple hardware renders SF Pro (platform license, zero bytes);
        // everyone else falls through to Inter. Inter sits BEFORE generic system-ui on purpose.
        sans: ['var(--font-body)', ...fontFamily.sans],
        body: ['-apple-system', 'BlinkMacSystemFont', 'var(--font-inter)', 'Inter', 'system-ui', '"Segoe UI"', 'Roboto', 'sans-serif'],
        // Editorial serif — opt-in, long-form filing reading only.
        editorial: ['var(--font-newsreader)', 'Newsreader', '"New York"', 'ui-serif', 'Georgia', 'serif'],
        // Technical & data: Geist Mono + tabular-nums — money, %, tickers, XBRL, verbatim excerpts.
        data: ['var(--font-geist-mono)', '"Geist Mono"', 'ui-monospace', 'SFMono-Regular', '"SF Mono"', 'Menlo', 'Consolas', 'monospace'],
        mono: ['var(--font-geist-mono)', '"Geist Mono"', 'ui-monospace', 'SFMono-Regular', '"SF Mono"', 'Menlo', 'Consolas', 'monospace'],
        // The data role for an analysis figure: Geist Mono, with a true minus. "EN Figure Minus" (app/globals.css) is a
        // one-glyph face that draws Geist Mono's own U+2212 for U+002D, so the hyphen-minus the shared formatters write
        // stays the DOM text (copy, the accessibility tree, the Excel export) and paints as a minus. The rest is `data`.
        figure: ['"EN Figure Minus"', 'var(--font-geist-mono)', '"Geist Mono"', 'ui-monospace', 'SFMono-Regular', '"SF Mono"', 'Menlo', 'Consolas', 'monospace'],
        // fontFamily.system / .grotesque were PURGED at the v2 cutover (zero usage, confirmed by
        // scan) — do not reintroduce. The v2.1 export resurrected them; #497 re-removed them.
      },

      fontSize: {
        // [size, { lineHeight, letterSpacing }] — letter-spacing references the --track-* ramp
        // defined ONCE in globals.css :root (tracked OUT ≤12px, 0 through body, tightening as
        // display sizes grow). Change the ramp there — never hard-code ems here.
        'data-xs': ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0' }], // tabular annotations don't track out
        xs: ['0.75rem', { lineHeight: '1rem', letterSpacing: 'var(--track-caption)' }],
        sm: ['0.875rem', { lineHeight: '1.25rem' }],
        base: ['1rem', { lineHeight: '1.6rem' }],
        lg: ['1.125rem', { lineHeight: '1.75rem' }],
        xl: ['1.25rem', { lineHeight: '1.75rem', letterSpacing: 'var(--track-title3)' }],
        '2xl': ['1.5rem', { lineHeight: '2rem', letterSpacing: 'var(--track-title3)' }],
        '3xl': ['1.875rem', { lineHeight: '2.25rem', letterSpacing: 'var(--track-title2)' }],
        '4xl': ['2.25rem', { lineHeight: '2.5rem', letterSpacing: 'var(--track-title1)' }],
        '5xl': ['3rem', { lineHeight: '1.1', letterSpacing: 'var(--track-display)' }],
        '6xl': ['3.75rem', { lineHeight: '1.05', letterSpacing: 'var(--track-display)' }],
      },

      // v3: the ONE eyebrow tracking — 12px UPPERCASE metric labels only.
      // Replaces every tracking-wider / tracking-[0.08em] hand-roll.
      letterSpacing: {
        eyebrow: 'var(--track-eyebrow)',
      },

      // v3: semantic stacking ladder — never z-[N]. (DataTable's internal z-[5]
      // sticky-cell layering is the one documented exemption.)
      zIndex: {
        sticky: '30', // in-page sticky chrome (mobile section nav)
        // The cookie-consent bar: above in-page sticky chrome, beneath the modal sheets / scrims
        // and the z-40 workspace launchers and coachmark, which add its height
        // (--consent-inset, lib/consentLayer.ts) to their bottom offsets while it is mounted.
        // Gate: tests/unit/bottomChromeLadder.spec.ts pins each token to its rung.
        consent: '32',
        // Retained ladder rung. Modal bottom sheets use modal for both scrim and panel,
        // above the site header; their launchers keep the workspace level.
        scrim: '35',
        header: '50', // site header
        overlay: '60', // popovers, the selection pill; the skip link rides toast
        modal: '70', // dialogs + sheets — scrim AND panel
        toast: '80',
      },

      borderRadius: {
        sm: '0.25rem',
        DEFAULT: '0.5rem',
        md: '0.625rem', // legacy off-scale (10px) — the scale is 4/8/12/16/24; don't use in new code
        lg: '0.75rem',
        xl: '1rem',
        '2xl': '1.5rem',
      },

      spacing: {
        // financial dashboards pack tightly — add the in-between steps we actually use
        4.5: '1.125rem',
        13: '3.25rem',
        18: '4.5rem',
        gutter: '1.5rem',
      },
      // The capped inset steps (PADDING_CAP_STEPS above): p-cap-6, px-cap-6, sm:p-cap-8 and the scroll padding
      // that matches a capped inset (scroll-py-cap-6).
      padding: paddingCap,
      scrollPadding: paddingCap,

      boxShadow: {
        // Elevation scale (light-mode tuned; pair with ring/border in dark)
        e1: '0 1px 2px 0 rgba(16, 24, 40, 0.06)',
        e2: '0 1px 3px 0 rgba(16, 24, 40, 0.10), 0 1px 2px -1px rgba(16, 24, 40, 0.10)',
        e3: '0 4px 6px -1px rgba(16, 24, 40, 0.10), 0 2px 4px -2px rgba(16, 24, 40, 0.10)',
        e4: '0 10px 15px -3px rgba(16, 24, 40, 0.10), 0 4px 6px -4px rgba(16, 24, 40, 0.10)',
        e5: '0 20px 25px -5px rgba(16, 24, 40, 0.12), 0 8px 10px -6px rgba(16, 24, 40, 0.10)',
        // Opaque focus ink holds 3:1 on page, panel and tinted controls in each theme.
        // Inset twins keep clipped scroll regions and calendar cells visibly focused.
        'ring-brand': '0 0 0 3px rgba(79, 122, 99, 1)',
        'ring-brand-dark': '0 0 0 3px rgba(127, 178, 149, 1)',
        'ring-brand-inset': 'inset 0 0 0 3px rgba(79, 122, 99, 1)',
        'ring-brand-inset-dark': 'inset 0 0 0 3px rgba(127, 178, 149, 1)',
        'ring-error': '0 0 0 3px rgba(185, 28, 28, 1)',
        'ring-error-dark': '0 0 0 3px rgba(248, 113, 113, 1)',
        // Brand glow — sage (replaces the legacy mint glow)
        'glow-brand': '0 0 40px -10px rgba(79, 122, 99, 0.30)',
        'glow-brand-sm': '0 0 20px -5px rgba(79, 122, 99, 0.20)',
        'glow-brand-lg': '0 0 60px -15px rgba(79, 122, 99, 0.25)',
      },

      // ---- Motion (tokens defined in globals.css :root; JS mirror lib/motion.ts) ----
      // DEFAULTs re-point Tailwind's bare `transition-*` utilities: 200ms + standard.
      transitionDuration: {
        DEFAULT: 'var(--duration-base)',
        fast: 'var(--duration-fast)', // 150ms — hover + color feedback
        base: 'var(--duration-base)', // 200ms — crossfades, theme, skeleton→content
        slow: 'var(--duration-slow)', // 600ms — entrances, draw-ins, count-up
        ambient: 'var(--duration-ambient)', // 1800ms — loops + attention decay
      },
      transitionTimingFunction: {
        DEFAULT: 'var(--ease-standard)',
        standard: 'var(--ease-standard)',
        pop: 'var(--ease-pop)', // success check-pop only
      },

      keyframes: {
        shimmer: { '100%': { transform: 'translateX(100%)' } },
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        // Skeleton→content handoff (DataTable, the account settings and watchlist pages) on the loading flip.
        'content-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        // count-up keyframe RETIRED — it was a fade impostor. The real signature
        // is hooks/useCountUp (rAF, duration-slow, ease-standard, tabular-nums).
      },
      // All token-timed. Pair with `motion-reduce:animate-none` at the use site
      // (the globals.css classes self-guard; these utilities can't).
      animation: {
        shimmer: 'shimmer var(--duration-ambient) var(--ease-standard) infinite',
        // Overrides Tailwind's raw 2s default so Badge dots + streaming carets sit on the scale.
        pulse: 'pulse var(--duration-ambient) var(--ease-standard) infinite',
        'fade-up': 'fade-up var(--duration-slow) var(--ease-standard) forwards',
        // Stagger — replaces the hand-rolled fade-up-delay-1/2/3. Set --stagger-index
        // (0-based) per item; step = duration-fast, capped at 4 steps so long lists
        // don't queue. Static class ⇒ first paint only: theme toggles and re-renders
        // never replay it (only a remount does).
        'fade-up-stagger':
          'fade-up var(--duration-slow) var(--ease-standard) calc(min(var(--stagger-index, 0), 4) * var(--duration-fast)) both',
        'content-in': 'content-in var(--duration-base) var(--ease-standard) both',
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
}
