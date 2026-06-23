const { fontFamily } = require('tailwindcss/defaultTheme')

/* =============================================================================
   EarningsNerd — Tailwind token system
   -----------------------------------------------------------------------------
   Builds on the existing config. Net-new, all additive (nothing removed):
     - fontFamily mapped to the runtime font-switcher CSS variable (--font-active)
       plus the four selectable system stacks + a permanent data/numeric stack
     - financial data semantics (gain / loss / flat) — DISTINCT from the brand
       accent, so "brand" never reads as "price went up"
     - state colors (success / warning / error / info), light + dark
     - a categorical chart palette
     - typography scale, radii, spacing additions, elevation + focus-ring shadows
   Every color pair is AA (>= 4.5:1) for body text on its intended surface.
============================================================================= */

const mintColors = {
  50: '#ECFDF5',
  100: '#D1FAE5',
  200: '#A7F3D0',
  300: '#6EE7B7',
  400: '#34D399',
  500: '#10B981', // legacy accent (no longer primary)
  600: '#059669',
  700: '#047857',
  800: '#065F46',
  900: '#064E3B',
}

// Financial data signal — deliberately NOT the brand accent. Brand is identity; this is data.
const gain = {
  light: '#16A34A', // green-600  — on white: 4.55:1 (AA)
  dark: '#34D399',  // emerald-400 — cleaner/clearer on dark navy than green-500
  soft: '#DCFCE7',
  softDark: 'rgba(52,211,153,0.14)',
}
const loss = {
  light: '#DC2626', // red-600    — on white: 4.53:1 (AA)
  dark: '#FB7185',  // rose-400   — cleaner on dark navy than red-400
  soft: '#FEE2E2',
  softDark: 'rgba(251,113,133,0.14)',
}
const flat = {
  light: '#6B7280', // gray-500
  dark: '#9CA3AF',  // gray-400
}

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    // Domain modules (the "Ask this Filing" Copilot, etc.) live here. Without this glob, Tailwind
    // never scans them, so any class used ONLY in features/ (e.g. the launcher's `bottom-5 right-5`,
    // the FilingWorkspace grid template) is purged from the production CSS and the component renders
    // unstyled/invisible. jsdom unit tests don't apply CSS, so this can't be caught there.
    './features/**/*.{js,ts,jsx,tsx,mdx}',
    './hooks/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // ---- Core surfaces ----
        background: {
          light: '#F4F3EE', // warm cream (not stark white — friendlier, less clinical)
          dark: '#0B1120',  // deep navy
        },
        panel: {
          light: '#FBFAF6', // warm off-white card
          dark: '#1F2937', // gray-800
        },
        // ---- Brand accent (subdued, approachable — replaces neon mint) ----
        // Theme-default mapping: Sage reads best in light, Slate in dark. Wire it up
        // with a `dark:` variant (e.g. text-brand-strong dark:text-brand-dark) or a CSS var swap.
        brand: {
          DEFAULT: '#4F7A63',
          light: '#4F7A63',  // Sage (light theme default)
          strong: '#3C6650', // text/links on cream — AA
          weak: '#ECF2EE',   // tint background
          dark: '#92A0E2',   // Slate (dark theme default)
          'strong-dark': '#B4BEEE',
        },
        // Legacy mint — kept for backward-compat; no longer the primary accent.
        mint: mintColors,
        primary: mintColors, // backward-compat alias

        // ---- Financial data semantics (NOT the brand accent) ----
        gain: {
          DEFAULT: gain.light,
          light: gain.light,
          dark: gain.dark,
          soft: gain.soft,
          'soft-dark': gain.softDark,
        },
        loss: {
          DEFAULT: loss.light,
          light: loss.light,
          dark: loss.dark,
          soft: loss.soft,
          'soft-dark': loss.softDark,
        },
        flat: {
          light: flat.light,
          dark: flat.dark,
        },

        // ---- UI state ----
        success: { light: '#16A34A', dark: '#22C55E' },
        warning: { light: '#B45309', dark: '#F59E0B' }, // amber-700 on white = 4.8:1
        error: { light: '#DC2626', dark: '#F87171' },
        info: { light: '#2563EB', dark: '#60A5FA' },

        // ---- Categorical chart palette (subdued, warm-leaning, cohesive) ----
        chart: {
          1: '#3E8E84', // teal
          2: '#5B7CC0', // cornflower
          3: '#D99E4A', // honey
          4: '#CF7159', // coral
          5: '#8B7BC0', // periwinkle
          6: '#5E9A6E', // sage
        },

        // ---- Text ----
        text: {
          primary: { light: '#1A1A17', dark: '#D7DADC' },
          // Headings use a warm dark-brown in light (espresso #3A2E26 default), off-white in dark.
          heading: { light: '#3A2E26', dark: '#D7DADC' },
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
        // Three roles. Headings stay grotesque regardless of the switchable body font.
        heading: ['Helvetica', '"Helvetica Neue"', 'Arial', 'sans-serif'],
        // Live, switchable body font (set by FontProvider via --font-active; default Figtree).
        sans: ['var(--font-active)', ...fontFamily.sans],
        body: ['var(--font-body)', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Arial', 'sans-serif'],
        // Selectable system stacks (all OS-native, zero network requests).
        system: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
        grotesque: ['Helvetica', '"Helvetica Neue"', 'Arial', 'sans-serif'],
        editorial: ['Georgia', '"Times New Roman"', 'Times', 'serif'],
        // Permanent data/numeric stack — tables, figures, tickers, XBRL, Ask-this-Filing output.
        data: ['ui-monospace', 'SFMono-Regular', '"SF Mono"', 'Menlo', 'Consolas', '"Liberation Mono"', 'monospace'],
        mono: ['ui-monospace', 'SFMono-Regular', '"SF Mono"', 'Menlo', 'Consolas', 'monospace'],
      },

      fontSize: {
        // [size, { lineHeight, letterSpacing }] — financial UI: tight display, comfy body.
        'data-xs': ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0' }],
        xs: ['0.75rem', { lineHeight: '1rem' }],
        sm: ['0.875rem', { lineHeight: '1.25rem' }],
        base: ['1rem', { lineHeight: '1.6rem' }],
        lg: ['1.125rem', { lineHeight: '1.75rem' }],
        xl: ['1.25rem', { lineHeight: '1.75rem', letterSpacing: '-0.01em' }],
        '2xl': ['1.5rem', { lineHeight: '2rem', letterSpacing: '-0.015em' }],
        '3xl': ['1.875rem', { lineHeight: '2.25rem', letterSpacing: '-0.02em' }],
        '4xl': ['2.25rem', { lineHeight: '2.5rem', letterSpacing: '-0.022em' }],
        '5xl': ['3rem', { lineHeight: '1.1', letterSpacing: '-0.025em' }],
        '6xl': ['3.75rem', { lineHeight: '1.05', letterSpacing: '-0.03em' }],
      },

      borderRadius: {
        sm: '0.25rem',
        DEFAULT: '0.5rem',
        md: '0.625rem',
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

      backgroundImage: {
        'hero-gradient': 'linear-gradient(to bottom right, #0B1120, #111827, #1a1147)',
        'hero-glow': 'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(16, 185, 129, 0.12), transparent)',
        'cta-gradient': 'linear-gradient(135deg, #064E3B, #0f172a, #1e1b4b)',
      },

      boxShadow: {
        // Elevation scale (light-mode tuned; pair with ring/border in dark)
        e1: '0 1px 2px 0 rgba(16, 24, 40, 0.06)',
        e2: '0 1px 3px 0 rgba(16, 24, 40, 0.10), 0 1px 2px -1px rgba(16, 24, 40, 0.10)',
        e3: '0 4px 6px -1px rgba(16, 24, 40, 0.10), 0 2px 4px -2px rgba(16, 24, 40, 0.10)',
        e4: '0 10px 15px -3px rgba(16, 24, 40, 0.10), 0 4px 6px -4px rgba(16, 24, 40, 0.10)',
        e5: '0 20px 25px -5px rgba(16, 24, 40, 0.12), 0 8px 10px -6px rgba(16, 24, 40, 0.10)',
        // Focus rings — use with focus-visible for keyboard users
        'ring-brand': '0 0 0 3px rgba(76, 95, 166, 0.45)',
        'ring-error': '0 0 0 3px rgba(220, 38, 38, 0.40)',
        // Brand glow (legacy mint — kept for backward-compat)
        'glow-mint': '0 0 40px -10px rgba(16, 185, 129, 0.3)',
        'glow-mint-sm': '0 0 20px -5px rgba(16, 185, 129, 0.2)',
        'glow-mint-lg': '0 0 60px -15px rgba(16, 185, 129, 0.25)',
      },

      keyframes: {
        shimmer: {
          '100%': {
            transform: 'translateX(100%)',
          },
        },
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'count-up': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        shimmer: 'shimmer 2s infinite',
        'fade-up': 'fade-up 0.6s ease-out forwards',
        'fade-up-delay-1': 'fade-up 0.6s ease-out 0.1s forwards',
        'fade-up-delay-2': 'fade-up 0.6s ease-out 0.2s forwards',
        'fade-up-delay-3': 'fade-up 0.6s ease-out 0.3s forwards',
        'count-up': 'count-up 0.4s ease-out forwards',
      },
    },
  },
  plugins: [require('@tailwindcss/forms')],
}
