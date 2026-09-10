import { Card } from '@/components/ui/Card'
import MarketingCta from '@/features/marketing/components/MarketingCta'
import SectionImpression from '@/features/marketing/components/SectionImpression'
import { ACCESS_COPY, type AccessMode } from '@/features/marketing/lib/access'
import { exampleFilingHref } from '@/lib/featureFlags'
import { ArrowRightIcon } from '@/lib/icons'

/**
 * Final CTA (design section 9): one featured card, copy on the left, the two actions on the
 * right. The primary action repeats the hero's "See a live example" (placement `cta_banner` for
 * the activation funnel); the secondary action and the access line come from the page's ONE
 * access decision (ACCESS_COPY), never hardcoded here.
 */
export default function CtaBanner({ accessMode }: { accessMode: AccessMode }) {
  const access = ACCESS_COPY[accessMode]
  return (
    <section aria-labelledby="cta-h" className="border-t border-border-light py-20 dark:border-white/10 sm:py-24">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <SectionImpression section="cta_banner">
          <Card elevation="e3" className="grid items-center gap-8 rounded-2xl p-8 sm:p-12 md:grid-cols-2 lg:p-14">
            <div>
              <h2 id="cta-h" className="text-3xl lg:text-4xl">
                Start with a real filing.
              </h2>
              <p className="mt-3 text-lg text-text-secondary-light dark:text-text-secondary-dark">
                Read the Apple 10-K summary first. Then read your own.
              </p>
            </div>
            <div className="flex flex-col items-start gap-3">
              <MarketingCta href={exampleFilingHref('cta_banner_example')} placement="cta_banner" size="lg">
                See a live example
                <ArrowRightIcon className="h-4 w-4" aria-hidden="true" />
              </MarketingCta>
              <MarketingCta variant="secondary" size="lg" href={access.href}>
                {access.cta}
              </MarketingCta>
              <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{access.line}</p>
            </div>
          </Card>
        </SectionImpression>
      </div>
    </section>
  )
}
