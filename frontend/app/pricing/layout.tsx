import type { Metadata } from 'next'
import { PRICE_VARIANTS } from './prices'

const SITE_URL = 'https://www.earningsnerd.io'

// The pricing page itself is a client component, so its metadata lives here.
export const metadata: Metadata = {
  title: 'Pricing | EarningsNerd',
  description:
    'EarningsNerd plans: free AI summaries of SEC filings every month, or go Pro for unlimited 10-K and 10-Q analysis, exports, and filing Q&A.',
  alternates: { canonical: '/pricing' },
}

// Product/Offer structured data for the pricing rich result. Uses the CONTROL anchor: the
// $39-vs-$29 fake-door A/B is a client-side display experiment and must not leak a variant price
// into what crawlers index.
const PRICING_JSON_LD = {
  '@context': 'https://schema.org',
  '@type': 'Product',
  '@id': `${SITE_URL}/pricing#product`,
  name: 'EarningsNerd Pro',
  description:
    'Unlimited AI summaries of SEC 10-K and 10-Q filings, multi-period analysis, filing Q&A, alerts, and exports.',
  brand: { '@type': 'Brand', name: 'EarningsNerd' },
  url: `${SITE_URL}/pricing`,
  offers: [
    {
      '@type': 'Offer',
      name: 'Pro (monthly)',
      price: PRICE_VARIANTS.control.monthly,
      priceCurrency: 'USD',
      url: `${SITE_URL}/pricing`,
      availability: 'https://schema.org/InStock',
    },
    {
      '@type': 'Offer',
      name: 'Pro (annual)',
      price: PRICE_VARIANTS.control.yearly,
      priceCurrency: 'USD',
      url: `${SITE_URL}/pricing`,
      availability: 'https://schema.org/InStock',
    },
  ],
}

// Escape `<` as the JSON-safe `<` so a `</script>` sequence inside the serialized JSON can
// never terminate the tag (the existing JSON-LD sites serialize static, hand-written objects; this
// one is the pattern to copy when the payload grows).
const JSON_LD_HTML = JSON.stringify(PRICING_JSON_LD).replace(/</g, '\\u003c')

export default function PricingLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON_LD_HTML }} />
      {children}
    </>
  )
}
