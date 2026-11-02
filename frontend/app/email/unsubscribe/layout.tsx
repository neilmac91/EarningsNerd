import type { Metadata } from 'next'

// The page is a client component, so its metadata lives here, as app/verify-email/layout.tsx does. The title names
// the page first and the brand last (decisions log); a page an email's own link opens stays out of the index.
export const metadata: Metadata = {
  title: 'Unsubscribe | EarningsNerd',
  robots: { index: false },
}

// The page's query container: its <main> narrows its gutter below 13em of this wrapper's text size, as /delete-account's
// does (lib/legalPageLayout.ts), so its title's long word holds whole on a phone under 200% text.
export default function UnsubscribeLayout({ children }: { children: React.ReactNode }) {
  return <div className="[container-type:inline-size]">{children}</div>
}
