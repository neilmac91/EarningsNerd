import type { Metadata } from 'next'

// The register page itself is a client component, so its metadata lives here. Auth flows carry no
// indexable content: a specific title (not the site default) + canonical + noindex.
export const metadata: Metadata = {
  title: 'Create an account | EarningsNerd',
  description: 'Create a free EarningsNerd account to generate AI summaries of SEC filings.',
  alternates: { canonical: '/register' },
  robots: { index: false },
}

export default function RegisterLayout({ children }: { children: React.ReactNode }) {
  return children
}
