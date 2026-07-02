import type { Metadata, Viewport } from 'next'
import { Inter, Geist_Mono, Newsreader } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'
import { SiteHeader, SiteFooter } from '@/components/SiteChrome'
import VerificationBanner from '@/components/VerificationBanner'
import EmailVerificationModal from '@/components/EmailVerificationModal'
import CookieConsent from '@/components/CookieConsent'
import { Analytics } from '@vercel/analytics/next'

// Type v2 — fixed roles, self-hosted via next/font (zero layout shift; the runtime
// font switcher is retired). Inter loads WITH the variable opsz axis: that is what
// gives the SF-style Text↔Display optical cuts (font-optical-sizing: auto in
// globals.css). -apple-system stays FIRST in --font-body, so Apple users render
// SF Pro (platform-licensed, zero bytes) and never download Inter; SF Pro / SF Mono /
// New York must NEVER be embedded as webfonts. globals.css + tailwind.config.js
// reference the emitted variables (--font-inter / --font-geist-mono / --font-newsreader).
const inter = Inter({ subsets: ['latin'], axes: ['opsz'], variable: '--font-inter' })
const geistMono = Geist_Mono({ subsets: ['latin'], variable: '--font-geist-mono' })
// axes: opsz — the editorial role promises optical sizing (font-optical-sizing: auto);
// preload: false — the serif is opt-in for long-form filing reading only, so ~120KB of
// woff2 must not ride the critical path of every route.
const newsreader = Newsreader({
  subsets: ['latin'],
  style: ['normal', 'italic'],
  axes: ['opsz'],
  variable: '--font-newsreader',
  preload: false,
})

// Pre-paint theme script — mirrors ThemeProvider (saved 'theme' else light) and sets the
// .dark class before first paint, so the (theme-responsive) pages don't flash the wrong theme
// on load. Default is LIGHT when there's no stored preference (no system-preference detection),
// so this must stay in lockstep with ThemeProvider's `savedTheme ?? 'light'` to avoid a
// hydration theme flip. ThemeProvider re-syncs to the same value after hydration.
const THEME_BOOTSTRAP = `(function(){try{
  var t = localStorage.getItem('theme');
  if (t === 'dark') document.documentElement.classList.add('dark');
}catch(e){}})();`

export const metadata: Metadata = {
  title: 'EarningsNerd - AI-Powered SEC Filing Analysis',
  description: 'Transform dense SEC filings into clear, actionable insights using AI. Search any public company, access its 10-K and 10-Q summaries, and instantly understand performance, risks, and trends.',
  keywords: ['SEC filings', '10-K', '10-Q', 'financial analysis', 'earnings', 'stock analysis', 'AI summaries', 'SEC EDGAR'],
  metadataBase: new URL('https://www.earningsnerd.io'),
  openGraph: {
    title: 'EarningsNerd - AI-Powered SEC Filing Analysis',
    description: 'Transform dense SEC filings into clear, actionable insights using AI.',
    type: 'website',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'EarningsNerd - SEC filing summaries in minutes',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'EarningsNerd - AI-Powered SEC Filing Analysis',
    description: 'Transform dense SEC filings into clear, actionable insights using AI.',
    images: ['/og-image.png'],
  },
  icons: {
    icon: '/assets/earningsnerd-icon-dark.svg',
    apple: '/assets/earningsnerd-icon-light.svg',
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  // Extend the layout under the notch / home indicator so env(safe-area-inset-*) reports real values.
  // The bottom-anchored floating buttons (Ask, Feedback) use those insets to clear system UI.
  viewportFit: 'cover',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    // suppressHydrationWarning: the THEME pre-paint script sets the .dark class on
    // <html> before hydration.
    <html
      lang="en"
      className={`${inter.variable} ${geistMono.variable} ${newsreader.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />
      </head>
      <body>
        <Providers>
          <SiteHeader />
          <VerificationBanner />
          {children}
          <SiteFooter />
          <EmailVerificationModal />
          <CookieConsent />
          <Analytics />
        </Providers>
      </body>
    </html>
  )
}
