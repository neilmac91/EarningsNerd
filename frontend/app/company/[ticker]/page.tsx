import CompanyPageClient from './page-client'

// Enable dynamic params for this route
export const dynamicParams = true
// Force dynamic rendering to avoid build-time issues
export const dynamic = 'force-dynamic'

export default function CompanyPage() {
  return <CompanyPageClient />
}
