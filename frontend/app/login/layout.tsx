import type { Metadata } from 'next'

// The login page itself is a client component, so its metadata lives here. Auth flows carry no
// indexable content: a specific title (not the site default) + canonical + noindex.
export const metadata: Metadata = {
  title: 'Sign in | EarningsNerd',
  description: 'Sign in to your EarningsNerd account.',
  alternates: { canonical: '/login' },
  robots: { index: false },
}

export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return children
}
