import type { Metadata, Viewport } from 'next'
import './globals.css'
import { Providers } from './providers'
import { inter, geistMono, newsreader } from './fonts'
import { SiteHeader, SiteFooter } from '@/components/SiteChrome'
import VerificationBanner from '@/features/auth/components/VerificationBanner'
import EmailVerificationModal from '@/features/auth/components/EmailVerificationModal'
import CookieConsent from '@/components/CookieConsent'
import { PrivateAnalytics } from './private-analytics'
import { fetchSignupConfig } from '@/lib/serverApi'
import { resolveAccessMode } from '@/features/marketing/lib/access'
import { SOCIAL_CARD } from '@/lib/socialCard'

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
  // 'Page | EarningsNerd': the page first, the brand last (D-038). A plain string, no template: every
  // route's own layout or page writes its whole title, and routeMetadata.spec.ts holds the form.
  title: 'AI summaries of SEC filings | EarningsNerd',
  description: 'The summary that shows its work. AI summaries of 10-Ks and 10-Qs from SEC EDGAR, with figures checked against the company’s filed data where they can be.',
  keywords: ['SEC filings', '10-K', '10-Q', 'financial analysis', 'earnings', 'stock analysis', 'AI summaries', 'SEC EDGAR'],
  metadataBase: new URL('https://www.earningsnerd.io'),
  // No title or description here: Next fills og:title, og:description and the twitter pair from each
  // page's own title and description, so a shared /pricing link previews as Pricing, not as the site.
  openGraph: {
    type: 'website',
    images: [SOCIAL_CARD],
  },
  twitter: {
    card: 'summary_large_image',
    images: [SOCIAL_CARD.url],
  },
  icons: {
    // favicon.ico carries 16/32/48; the self-backgrounded appicon SVG scales
    // crisply and is legible on both light and dark tab chrome.
    icon: [
      { url: '/favicon.ico', sizes: '48x48' },
      { url: '/assets/earningsnerd-appicon.svg', type: 'image/svg+xml' },
    ],
    // Apple ignores SVG touch icons — this must be the PNG tile.
    apple: '/apple-touch-icon.png',
    // Safari pinned tabs recolour a one-colour mask; the mark is letterboxed in a square.
    other: [{ rel: 'mask-icon', url: '/assets/earningsnerd-mask-icon.svg', color: '#4F7A63' }],
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  // Extend the layout under the notch / home indicator so env(safe-area-inset-*) reports real values.
  // The bottom-anchored floating buttons (Ask, Feedback) use those insets to clear system UI.
  viewportFit: 'cover',
  // Browser chrome tint follows the OS scheme (a known limitation: it tracks
  // prefers-color-scheme, not the app's own theme toggle).
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#F4F3EE' },
    { media: '(prefers-color-scheme: dark)', color: '#0B1120' },
  ],
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  // The header's account CTA follows the backend's registration gate (invite-only vs open), read
  // through an hourly ISR fetch so a config flip on the service flips the chrome everywhere with
  // no redeploy (this fetch is the ISR floor for every route); unreachable backend = the
  // conservative invite copy.
  const accessMode = resolveAccessMode(await fetchSignupConfig())
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
          <SiteHeader accessMode={accessMode} />
          <VerificationBanner />
          {/* Skip-link target (SiteChrome.SkipToContent). A div, not <main>: pages render their own
              single <main> landmark. tabIndex=-1 makes it programmatically focusable only. */}
          <div id="main" tabIndex={-1} className="outline-none">
            {children}
          </div>
          <SiteFooter />
          <EmailVerificationModal />
          <CookieConsent />
          <PrivateAnalytics />
        </Providers>
      </body>
    </html>
  )
}
