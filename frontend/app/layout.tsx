import type { Metadata } from 'next'
import { Figtree } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'
import { FontProvider } from '@/components/FontProvider'
import { SiteHeader, SiteFooter } from '@/components/SiteChrome'
import VerificationBanner from '@/components/VerificationBanner'
import EmailVerificationModal from '@/components/EmailVerificationModal'
import CookieConsent from '@/components/CookieConsent'
import { Analytics } from '@vercel/analytics/next'

// Body & UI role — self-hosted via next/font (no Google Fonts <link>, no FOUC).
// Exposed as the CSS variable globals.css reads for --font-body.
const figtree = Figtree({
  subsets: ['latin'],
  variable: '--font-figtree',
  display: 'swap',
})

// Inline pre-hydration script — runs synchronously in <head>, before paint, so the
// persisted body font is applied on the first frame (no flash-of-wrong-font). It only
// mutates an attribute (not server-rendered text), so React hydration stays consistent.
const FONT_BOOTSTRAP = `(function(){try{
  var f = localStorage.getItem('en-font');
  var allowed = ['figtree','grotesque','data'];
  document.documentElement.setAttribute('data-font', allowed.indexOf(f) > -1 ? f : 'figtree');
}catch(e){
  document.documentElement.setAttribute('data-font','figtree');
}})();`

// Pre-paint theme script — mirrors ThemeProvider (saved 'theme' else system preference) and
// sets the .dark class before first paint, so the (now theme-responsive) pages don't flash
// the wrong theme on load. ThemeProvider re-syncs to the same value after hydration.
const THEME_BOOTSTRAP = `(function(){try{
  var t = localStorage.getItem('theme');
  if (t !== 'light' && t !== 'dark') {
    t = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
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

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    // suppressHydrationWarning: the bootstrap script sets data-font (and ThemeProvider the
    // .dark class) on <html> before hydration.
    <html lang="en" data-font="figtree" className={`${figtree.variable} font-sans`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />
        <script dangerouslySetInnerHTML={{ __html: FONT_BOOTSTRAP }} />
      </head>
      <body>
        <FontProvider>
          <Providers>
            <SiteHeader />
            <VerificationBanner />
            {children}
            <SiteFooter />
            <EmailVerificationModal />
            <CookieConsent />
            <Analytics />
          </Providers>
        </FontProvider>
      </body>
    </html>
  )
}
