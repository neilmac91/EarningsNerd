import { Inter, Geist_Mono, Newsreader } from 'next/font/google'

// The root's fonts, one instance each, imported by app/layout.tsx and app/global-error.tsx (E147). next/font declares a
// face for every loader call, and every module in the root's tree rides every page, so a second call anywhere declares
// a second family on every page. Gate: tests/unit/oneFontInstance.spec.ts.
//
// Type v2 — fixed roles, self-hosted via next/font (Inter's fallback metric-matched, Geist Mono's monospace; the runtime
// font switcher is retired). Inter loads WITH the variable opsz axis: that is what
// gives the SF-style Text↔Display optical cuts (font-optical-sizing: auto in
// globals.css). -apple-system stays FIRST in --font-body, so Apple hardware renders
// SF Pro (platform-licensed, zero bytes); the preload still fetches Inter's Latin file
// there. SF Pro / SF Mono / New York must NEVER be embedded as webfonts. globals.css +
// tailwind.config.js reference the emitted variables (--font-inter / --font-geist-mono /
// --font-newsreader).
export const inter = Inter({ subsets: ['latin'], axes: ['opsz'], variable: '--font-inter' })
// Geist Mono falls back to a monospace face while it loads (E199; trend-chart spec §3.2 G1). next/font's default,
// "Geist Mono Fallback", is Arial at size-adjust 134.59%: proportional, its digits 0.75 em to Geist Mono's 0.6, so every
// figure, ticker and chart label painted wider than its layout until the face arrived. adjustFontFallback: false drops
// that face (webpack's loader keeps it beside a fallback list otherwise) and `fallback` ends --font-geist-mono in the
// platform's monospace. `subsets` chooses only the files preloaded, and this instance rides every route: latin-ext
// (14.7 KB: †, ₹, ₪, ₱) is declared with its unicode-range all the same and loads where its text paints, and the spec
// renderer's charts wait for it before they paint (TrendChartsV2's CHART_TEXT; spec §0.5).
export const geistMono = Geist_Mono({
  subsets: ['latin'],
  adjustFontFallback: false,
  fallback: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
  variable: '--font-geist-mono',
})
// axes: opsz — the editorial role promises optical sizing (font-optical-sizing: auto);
// preload: false — the serif is opt-in for the filing's own words (long-form filing reading,
// and inside the product a passage the server located, set as a marked block: D-044), so
// ~120KB of woff2 must not ride the critical path of every route.
export const newsreader = Newsreader({
  subsets: ['latin'],
  style: ['normal', 'italic'],
  axes: ['opsz'],
  variable: '--font-newsreader',
  preload: false,
})
