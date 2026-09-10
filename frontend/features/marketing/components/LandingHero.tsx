import CompanySearch from '@/features/companies/components/CompanySearch'
import HeroExample from '@/features/marketing/components/HeroExample'
import HeroHeadline from '@/features/marketing/components/HeroHeadline'
import MarketingCta from '@/features/marketing/components/MarketingCta'
import QuickAccessBar from '@/features/marketing/components/QuickAccessBar'
import { ArrowRightIcon } from '@/lib/icons'
import { exampleFilingHref } from '@/lib/featureFlags'
import { ACCESS_COPY, type AccessMode } from '@/features/marketing/lib/access'
import type { ExampleData } from '@/lib/serverApi'

/**
 * Landing hero: headline (the LCP element, no hero image), the "See a live example" primary CTA
 * with the access line beneath it, the company search as the secondary action, and the live
 * example summary card. The example card renders at EVERY width (its content is a superset of the
 * retired compact mobile card), so mobile sees the same evidence as desktop.
 */
export default function LandingHero({
  example,
  accessMode,
}: {
  example: ExampleData | null
  accessMode: AccessMode
}) {
  const access = ACCESS_COPY[accessMode]
  return (
    <section aria-labelledby="hero-h" className="bg-background-light dark:bg-background-dark">
      <div className="mx-auto max-w-7xl px-4 pb-14 pt-12 sm:px-6 sm:pb-20 sm:pt-16 lg:px-8 lg:pb-24 lg:pt-20">
        <div className="grid items-start gap-10 lg:grid-cols-2 lg:gap-16">
          <div className="min-w-0">
            <HeroHeadline />
            <p className="mt-5 max-w-[560px] text-base leading-relaxed text-text-secondary-light dark:text-text-secondary-dark sm:text-lg">
              AI summaries of 10-Ks and 10-Qs for investors who read the source. Nine sections,
              every figure grounded in SEC XBRL, every claim linked to the passage it came from.
            </p>

            <div className="mt-7 flex flex-col items-start gap-2.5">
              <MarketingCta href={exampleFilingHref('hero_example')} placement="hero" size="lg">
                See a live example
                <ArrowRightIcon className="h-4 w-4" aria-hidden="true" />
              </MarketingCta>
              <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{access.line}</p>
            </div>

            {/* Company search: the secondary action. */}
            <div className="mt-7 max-w-[560px]">
              <label
                htmlFor="company-search"
                className="mb-2 block text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark"
              >
                Or start with a company
              </label>
              <CompanySearch autoFocusDesktop placeholder="Search any company or ticker" />
              <QuickAccessBar />
            </div>
          </div>

          {/* The real pre-generated example summary (ISR), same card at every breakpoint. */}
          <div className="min-w-0" aria-label={`Example summary: ${example?.companyName ?? 'Apple Inc.'} ${example?.filingType ?? '10-K'}`}>
            <HeroExample example={example} />
          </div>
        </div>
      </div>
    </section>
  )
}
