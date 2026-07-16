import type { Metadata } from 'next'

// The pricing page itself is a client component, so its metadata lives here.
export const metadata: Metadata = {
  title: 'Pricing | EarningsNerd',
  description:
    'EarningsNerd plans: free AI summaries of SEC filings every month, or go Pro for unlimited 10-K and 10-Q analysis, exports, and filing Q&A.',
  alternates: { canonical: '/pricing' },
}

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  return children
}
