import type { Metadata } from 'next'
import FullTextSearch from '@/features/search/components/FullTextSearch'

export const metadata: Metadata = {
  title: 'Search Filings | EarningsNerd',
  description:
    'Full-text search across SEC filings and their exhibits since 2001. Find every filing that mentions a phrase, risk, or product.',
}

export default function SearchPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:px-8">
      <FullTextSearch />
    </main>
  )
}
