import { redirect } from 'next/navigation'
import CompanySearch from '@/components/CompanySearch'
import DashboardPreview from '@/components/DashboardPreview'

export default function Home() {
  // Waitlist is enabled by default unless explicitly disabled
  const isWaitlistEnabled = process.env.WAITLIST_MODE !== 'false'

  if (isWaitlistEnabled) {
    redirect('/waitlist')
  }

  return (
    <main className="space-y-16 py-12 md:py-20 lg:py-24">
      {/* Focused Hero Section */}
      <section className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <h1 className="text-4xl font-bold tracking-tight text-text-primary-light dark:text-text-primary-dark sm:text-5xl md:text-6xl">
            The professional standard for{' '}
            <span className="text-mint-600 dark:text-mint-400">SEC Filing Analysis</span>
          </h1>
          <p className="mt-4 text-lg text-text-secondary-light dark:text-text-secondary-dark sm:mt-6">
            Go beyond the headlines. Instantly access institutional-grade, AI-powered summaries and insights for any public company.
          </p>
        </div>

        <div className="mx-auto mt-8 max-w-xl sm:mt-10">
          <CompanySearch />
        </div>
      </section>

      {/* Interactive Dashboard Preview */}
      <section className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <DashboardPreview />
      </section>
    </main>
  )
}
