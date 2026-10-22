import { Inter, Geist_Mono, Newsreader } from 'next/font/google'

// The root's fonts, one instance each, imported by app/layout.tsx and app/global-error.tsx (E147). next/font declares a
// face for every loader call, and every module in the root's tree rides every page, so a second call anywhere declares
// a second family on every page. Gate: tests/unit/oneFontInstance.spec.ts.
//
// Type v2 — fixed roles, self-hosted via next/font (zero layout shift; the runtime
// font switcher is retired). Inter loads WITH the variable opsz axis: that is what
// gives the SF-style Text↔Display optical cuts (font-optical-sizing: auto in
// globals.css). -apple-system stays FIRST in --font-body, so Apple users render
// SF Pro (platform-licensed, zero bytes) and never download Inter; SF Pro / SF Mono /
// New York must NEVER be embedded as webfonts. globals.css + tailwind.config.js
// reference the emitted variables (--font-inter / --font-geist-mono / --font-newsreader).
export const inter = Inter({ subsets: ['latin'], axes: ['opsz'], variable: '--font-inter' })
export const geistMono = Geist_Mono({ subsets: ['latin'], variable: '--font-geist-mono' })
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
