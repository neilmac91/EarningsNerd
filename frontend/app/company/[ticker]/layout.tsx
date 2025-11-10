import { generateMetadata as genMeta } from './metadata'

// Enable dynamic params for this route
export const dynamicParams = true
// Force dynamic rendering to avoid build-time issues
export const dynamic = 'force-dynamic'

export async function generateMetadata({ params }: { params: { ticker: string } }) {
  try {
    return await genMeta({ params })
  } catch (error) {
    // Fallback metadata if generation fails
    return {
      title: 'Company SEC Filings | EarningsNerd',
      description: 'AI-powered analysis of SEC filings.',
    }
  }
}

export default function CompanyLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return children
}

