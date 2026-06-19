import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { Providers } from './providers'
import { SiteHeader, SiteFooter } from '@/components/SiteChrome'
import VerificationBanner from '@/components/VerificationBanner'
import EmailVerificationModal from '@/components/EmailVerificationModal'
import CommandPalette from '@/components/CommandPalette'
import CookieConsent from '@/components/CookieConsent'
import { Analytics } from '@vercel/analytics/next'

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
        url: '/og-image.png',
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
    images: ['/og-image.png'],
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
          <SiteHeader />
          <VerificationBanner />
          {children}
          <SiteFooter />
          <CommandPalette />
          <EmailVerificationModal />
          <CookieConsent />
          <Analytics />
        </Providers>
      </body>
    </html>
  )
}
