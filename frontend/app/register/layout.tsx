import type { Metadata } from 'next'

// The register page itself is a client component, so its metadata lives here. Auth flows carry no
// indexable content: a specific title (not the site default) + canonical + noindex.
export const metadata: Metadata = {
  title: 'Create an account | EarningsNerd',
  description: 'Create your EarningsNerd account.',
  alternates: { canonical: '/register' },
  robots: { index: false },
}

export default function RegisterLayout({ children }: { children: React.ReactNode }) {
  return children
}
