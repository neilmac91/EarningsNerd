import type { Metadata } from 'next'

// The page is a client component, so its metadata lives here, as app/login/layout.tsx does. The title
// names the page first and the brand last (D-035); a private page stays out of the index.
export const metadata: Metadata = {
  title: 'Watchlist insights | EarningsNerd',
  robots: { index: false },
}

export default function WatchlistLayout({ children }: { children: React.ReactNode }) {
  return children
}
