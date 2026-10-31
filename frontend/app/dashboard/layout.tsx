import type { Metadata } from 'next'
import { LOGO_DEV_ENABLED } from '@/lib/featureFlags'

// The page is a client component, so its metadata lives here, as app/login/layout.tsx does. The title
// names the page first and the brand last (decisions log); a private page stays out of the index.
export const metadata: Metadata = {
  title: 'Dashboard | EarningsNerd',
  robots: { index: false },
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {/* Every dashboard route shows company marks once its reads answer (Your companies, the feed, the
          watchlist); the handshake with the mark CDN runs with the HTML, as on the landing. */}
      {LOGO_DEV_ENABLED && <link rel="preconnect" href="https://img.logo.dev" />}
      {children}
    </>
  )
}
