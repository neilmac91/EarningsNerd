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
}
const loss = {
  light: '#DC2626',  // red-600 — GRAPHIC/chip value only: 4.0:1 on cream / 4.4:1 on white (FAILS AA for text)
  text: '#B91C1C',   // red-700 — delta TEXT on cream/white (5.8:1); lib/financialTone directionText resolves to this
  dark: '#FB7185',  // rose-400 — 7.0:1 on navy, text-safe
  soft: '#FEE2E2',
  softDark: 'rgba(251,113,133,0.14)',
}
const flat = {
  light: '#6B7280', // gray-500
  dark: '#9CA3AF',  // gray-400
}

module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    // Domain modules (the "Ask this Filing" Copilot, etc.) live here. Without this glob, Tailwind
    // never scans them, so any class used ONLY in features/ is purged in production.
    './features/**/*.{js,ts,jsx,tsx,mdx}',
    './hooks/**/*.{js,ts,jsx,tsx,mdx}',
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
          // Legacy alias of DEFAULT — ~191 usages pending the brand-light sweep (MIGRATION
          // v2.1 §c). Deleted only at the end of the sweep, in its own commit. Do not use
          // in new code. (Re-added on sync: the v2.1 pack dropped it against its own
          // ground-truth note.)
          light: '#4F7A63',
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
        },
        loss: {
          DEFAULT: loss.light,
          light: loss.light,
          text: loss.text,
          dark: loss.dark,
          soft: loss.soft,
          'soft-dark': loss.softDark,
        },
        flat: {
          light: flat.light,
          dark: flat.dark,
        },

        // ---- UI state ---- (light values sized for the warm cream surface, not white)
        success: { light: '#15803D', dark: '#22C55E' }, // was #16A34A — 3.3:1 as text; green-700 holds 4.5:1 on cream
        warning: { light: '#92400E', dark: '#F59E0B' }, // was #B45309 — 3.8:1 inside its 13% tint; amber-800 holds 5.2:1 in-tint, 6.4:1 on cream
        error: { light: '#B91C1C', dark: '#F87171', emphasis: '#991B1B' }, // was #DC2626 (white label = 4.4:1); red-700 fill = 6.5:1, emphasis = destructive hover, 8.3:1
        info: { light: '#2563EB', dark: '#60A5FA' },

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
          // Axis labels: 11–12px data face + tabular-nums. Light = text.tertiary (4.6:1 on
          // the card charts sit on; on bare cream use secondary). Dark = text.SECONDARY
          // (tertiary-dark fails on navy — same rule as muted text).
          label: { light: '#6B7280', dark: '#9CA3AF' },
          crosshair: { light: 'rgba(107,114,128,0.45)', dark: 'rgba(156,163,175,0.4)' }, // flat @ ~45%, dashed 3 3
          ref: { light: '#6B7280', dark: '#9CA3AF' },   // zero/reference line = flat tokens — 4.4:1 / 7.4:1 (hairline-as-meaning ≥3:1)
          tip: { light: '#FBFAF6', dark: '#1F2937' },   // tooltip surface = panel + hairline; shadow-e2 light / shadow NONE dark
        },

        // ---- Text ----
        text: {
          primary: { light: '#1A1A17', dark: '#D7DADC' },
          // v2: ONE heading ink — same espresso as body (walnut #3A2E26 retired); hierarchy comes
          // from size + weight, never a second color.
          heading: { light: '#1A1A17', dark: '#D7DADC' },
          secondary: { light: '#374151', dark: '#9CA3AF' },
          tertiary: { light: '#6B7280', dark: '#4B5563' },
        },
        // ---- Borders ----
        border: {
          light: '#E5E7EB', // gray-200
          dark: '#374151', // gray-700
        },
      },

      fontFamily: {
        // Type v2 — three FIXED roles (not user-selectable). Must mirror the CSS vars in globals.css.
        // Headings: Inter loaded WITH the variable opsz axis — font-optical-sizing:auto gives the
        // SF-style Text↔Display optical cuts. ONE display weight: 600.
        // Option A (next/font) wiring per the v2 cutover (§d.4): webfonts are self-hosted
        // with hashed family names, exposed via --font-inter / --font-geist-mono /
        // --font-newsreader on <html> (app/layout.tsx). The literal names stay as
        // fallbacks. (Re-applied on sync: the v2.1 pack shipped literal-only stacks.)
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
        // fontFamily.system / fontFamily.grotesque stay purged (cutover decision — zero
        // class usage; the v2.1 pack resurrected them against its own ground-truth note).
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

      boxShadow: {
        // Elevation scale (light-mode tuned; pair with ring/border in dark)
        e1: '0 1px 2px 0 rgba(16, 24, 40, 0.06)',
        e2: '0 1px 3px 0 rgba(16, 24, 40, 0.10), 0 1px 2px -1px rgba(16, 24, 40, 0.10)',
        e3: '0 4px 6px -1px rgba(16, 24, 40, 0.10), 0 2px 4px -2px rgba(16, 24, 40, 0.10)',
        e4: '0 10px 15px -3px rgba(16, 24, 40, 0.10), 0 4px 6px -4px rgba(16, 24, 40, 0.10)',
        e5: '0 20px 25px -5px rgba(16, 24, 40, 0.12), 0 8px 10px -6px rgba(16, 24, 40, 0.10)',
        // Focus rings — use with focus-visible for keyboard users
        'ring-brand': '0 0 0 3px rgba(79, 122, 99, 0.50)',
        'ring-brand-dark': '0 0 0 3px rgba(127, 178, 149, 0.55)',
        'ring-error': '0 0 0 3px rgba(185, 28, 28, 0.45)',
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
        // Skeleton→content handoff (DataTable, AskFilingAnswer) on the loading flip.
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
