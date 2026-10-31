import type { Metadata } from 'next'

// The page is a client component, so its metadata lives here, as app/login/layout.tsx does. The title
// names the page first and the brand last (decisions log); a private page stays out of the index.
export const metadata: Metadata = {
  title: 'Delete your account | EarningsNerd',
  robots: { index: false },
}

// The page's query container: its <main> narrows its gutter below 13em of this wrapper's text size (E231).
export default function DeleteAccountLayout({ children }: { children: React.ReactNode }) {
  return <div className="[container-type:inline-size]">{children}</div>
}
