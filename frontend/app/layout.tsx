import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'
import Header from '@/components/Header' // Will be created in the next step

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
})

export const metadata: Metadata = {
  title: 'EarningsNerd - AI-Powered SEC Filing Analysis',
  description: 'Transform dense SEC filings into clear, actionable insights using AI. Search any public company, access its 10-K and 10-Q summaries, and instantly understand performance, risks, and trends.',
  keywords: ['SEC filings', '10-K', '10-Q', 'financial analysis', 'earnings', 'stock analysis', 'AI summaries', 'SEC EDGAR'],
  metadataBase: new URL('https://www.earningsnerd.io'),
  openGraph: {
    title: 'EarningsNerd - AI-Powered SEC Filing Analysis',
    description: 'Transform dense SEC filings into clear, actionable insights using AI.',
    type: 'website',
    images: [
      {
        url: '/og-image.svg',
        width: 1200,
        height: 630,
        alt: 'EarningsNerd - SEC filing summaries in minutes',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'EarningsNerd - AI-Powered SEC Filing Analysis',
    description: 'Transform dense SEC filings into clear, actionable insights using AI.',
    images: ['/og-image.svg'],
  },
  icons: {
    icon: '/assets/earningsnerd-icon-dark.svg',
    apple: '/assets/earningsnerd-icon-light.svg',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${inter.variable} font-sans`} suppressHydrationWarning>
      <head />
      <body>
        <Providers>
          <Header />
          {children}
        </Providers>
      </body>
    </html>
  )
}
