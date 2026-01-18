import type { Metadata } from 'next'
import { DM_Sans, Fraunces } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'

const dmSans = DM_Sans({ subsets: ['latin'], variable: '--font-sans' })
const fraunces = Fraunces({ subsets: ['latin'], variable: '--font-display' })

export const metadata: Metadata = {
  title: 'EarningsNerd - AI-Powered SEC Filing Analysis',
  description: 'Transform dense SEC filings into clear, actionable insights using AI. Search any public company, access its 10-K and 10-Q summaries, and instantly understand performance, risks, and trends.',
  keywords: ['SEC filings', '10-K', '10-Q', 'financial analysis', 'earnings', 'stock analysis', 'AI summaries', 'SEC EDGAR'],
  openGraph: {
    title: 'EarningsNerd - AI-Powered SEC Filing Analysis',
    description: 'Transform dense SEC filings into clear, actionable insights using AI.',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'EarningsNerd - AI-Powered SEC Filing Analysis',
    description: 'Transform dense SEC filings into clear, actionable insights using AI.',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              '@context': 'https://schema.org',
              '@type': 'SoftwareApplication',
              name: 'EarningsNerd',
              applicationCategory: 'FinanceApplication',
              description: 'AI-powered SEC filing analysis and summarization platform',
              url: 'https://earningsnerd.com',
              offers: {
                '@type': 'Offer',
                price: '0',
                priceCurrency: 'USD',
              },
            }),
          }}
        />
      </head>
      <body className={`${dmSans.variable} ${fraunces.variable}`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}

