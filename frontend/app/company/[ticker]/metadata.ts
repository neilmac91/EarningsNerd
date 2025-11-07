import { Metadata } from 'next'

export async function generateMetadata({ params }: { params: { ticker: string } }): Promise<Metadata> {
  const ticker = params.ticker.toUpperCase()
  
  // In a real app, you'd fetch company data here
  // For now, we'll use dynamic metadata
  return {
    title: `${ticker} SEC Filings & 10-K Summary | EarningsNerd`,
    description: `AI-powered analysis of ${ticker} SEC filings. Get instant summaries of 10-K and 10-Q reports with financial highlights, risk factors, and management insights.`,
    keywords: [`${ticker}`, 'SEC filings', '10-K', '10-Q', 'financial analysis', 'earnings', 'stock analysis'],
    openGraph: {
      title: `${ticker} SEC Filing Analysis | EarningsNerd`,
      description: `AI-powered summaries of ${ticker} SEC filings and financial reports.`,
      type: 'website',
    },
    twitter: {
      card: 'summary_large_image',
      title: `${ticker} SEC Filing Analysis | EarningsNerd`,
      description: `AI-powered summaries of ${ticker} SEC filings and financial reports.`,
    },
  }
}

