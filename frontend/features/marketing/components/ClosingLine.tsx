import ExampleCtaLink from '@/features/marketing/components/ExampleCtaLink'
import MarketingCta from '@/features/marketing/components/MarketingCta'
import SectionImpression from '@/features/marketing/components/SectionImpression'
import { ACCESS_COPY, type AccessMode } from '@/features/marketing/lib/access'
import { exampleFilingHref } from '@/lib/featureFlags'
import { ArrowRightIcon } from '@/lib/icons'

/**
 * The landing page's close (D-045): one line under the last row's rule, not a banner. The sentence carries
 * the live example as a text link (placement `cta_banner`, the activation funnel's name for the page's last
 * example link, kept so the funnel's series continues) and ends on the access mode's call to action as a
 * button, both from the page's ONE access decision (ACCESS_COPY), never hardcoded here. It is no section of
 * its own, so it takes no number among the rows and no heading in the outline.
 */
export default function ClosingLine({ accessMode }: { accessMode: AccessMode }) {
  const access = ACCESS_COPY[accessMode]
  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      <SectionImpression section="cta_banner">
        <p
          data-landing-close=""
          className="border-t border-border-light py-12 text-lg text-text-primary-light dark:border-white/10 dark:text-text-primary-dark sm:py-16"
        >
          Start with a real filing:{' '}
          <ExampleCtaLink
            href={exampleFilingHref('cta_banner_example')}
            placement="cta_banner"
            className="rounded-sm font-semibold text-brand-strong underline underline-offset-4 transition-colors duration-fast hover:text-brand-emphasis dark:text-brand-strong-dark dark:hover:text-brand-dark"
          >
            read the Apple <span className="whitespace-nowrap">10-K</span> summary
          </ExampleCtaLink>{' '}
          first, then read your own.{' '}
          <MarketingCta href={access.href} size="md" className="ml-1 align-middle">
            {access.cta}
            <ArrowRightIcon className="h-4 w-4" aria-hidden="true" />
          </MarketingCta>
        </p>
      </SectionImpression>
    </div>
  )
}
