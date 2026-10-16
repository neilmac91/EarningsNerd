import type { Metadata } from 'next'
import { ANALYSIS_LINES, shipped } from '@/lib/planLimits'
import { PRO_PRICING } from './prices'

const SITE_URL = 'https://www.earningsnerd.io'

// The pricing page itself is a client component, so its metadata lives here. Pro's questions have a monthly cap, so
// "unlimited" never heads a list that names filing Q&A: Q&A has a sentence of its own (planLimitsLockstep.spec.ts).
export const metadata: Metadata = {
  title: 'Pricing | EarningsNerd',
  description:
    'EarningsNerd plans: free AI summaries of SEC filings every month, or go Pro for unlimited 10-K and 10-Q analysis and exports. Pro also includes filing Q&A.',
  alternates: { canonical: '/pricing' },
}

// Product/Offer structured data uses the same approved offer as the visible pricing surfaces, and
// names multi-period analysis only while ENABLE_ANALYSIS ships it, as the Pro lists do (/analysis
// 404s while the flag is off): its piece is lib/planLimits.ts ANALYSIS_LINES.productJsonLd, read
// through shipped() at render, as the page and PricingSection read their lines.
const pricingJsonLd = () => ({
  '@context': 'https://schema.org',
  '@type': 'Product',
  '@id': `${SITE_URL}/pricing#product`,
  name: 'EarningsNerd Pro',
  description: `${shipped([
    { text: 'Unlimited AI summaries of SEC 10-K and 10-Q filings' },
    ANALYSIS_LINES.productJsonLd,
    { text: 'alerts' },
  ]).join(', ')}, and exports. Pro also includes filing Q&A.`,
  brand: { '@type': 'Brand', name: 'EarningsNerd' },
  url: `${SITE_URL}/pricing`,
  offers: [
    {
      '@type': 'Offer',
      name: 'Pro (monthly)',
      price: PRO_PRICING.monthly,
      priceCurrency: 'USD',
      url: `${SITE_URL}/pricing`,
      availability: 'https://schema.org/InStock',
    },
    {
      '@type': 'Offer',
      name: 'Pro (annual)',
      price: PRO_PRICING.yearly,
      priceCurrency: 'USD',
      url: `${SITE_URL}/pricing`,
      availability: 'https://schema.org/InStock',
    },
  ],
})

// Escape `<` as the JSON-safe `<` so a `</script>` sequence inside the serialized JSON can
// never terminate the tag (the existing JSON-LD sites serialize static, hand-written objects; this
// one is the pattern to copy when the payload grows).
const jsonLdHtml = () => JSON.stringify(pricingJsonLd()).replace(/</g, '\\u003c')

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdHtml() }} />
      {children}
    </>
  )
}
