import Link from 'next/link'
import EarningsNerdLogo from '@/components/EarningsNerdLogo'
import { ENABLE_ANALYSIS, ENABLE_CALENDAR } from '@/lib/featureFlags'

type FooterLink = { label: string; href: string }

// Product column mirrors the nav's live products: only surfaces a user can actually reach. Analysis
// and Calendar are flag-gated (their routes 404 while off, same as the nav entries); Pricing is
// always live. Full-text search is intentionally absent (ENABLE_FULLTEXT_SEARCH — hidden product),
// and the old "Hot Filings" (#hot-filings, no such anchor) and "Trending" (#trending, only renders
// under the off-by-default ENABLE_MARKET_MOVERS flag) links were dead and have been dropped.
const FOOTER_LINKS: Record<string, FooterLink[]> = {
  Product: [
    ...(ENABLE_ANALYSIS ? [{ label: 'Multi-Period Analysis', href: '/analysis' }] : []),
    ...(ENABLE_CALENDAR ? [{ label: 'Calendar', href: '/calendar' }] : []),
    { label: 'Pricing', href: '/pricing' },
  ],
  Resources: [
    { label: 'Contact', href: '/contact' },
  ],
  Legal: [
    { label: 'Privacy', href: '/privacy' },
    { label: 'Terms', href: '/terms' },
    { label: 'Security', href: '/security' },
  ],
}

const CURRENT_YEAR = new Date().getFullYear()

export default function Footer() {
  return (
    <footer className="border-t border-border-light bg-background-light dark:border-white/[0.06] dark:bg-background-dark">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid gap-10 md:grid-cols-[1.5fr_1fr_1fr_1fr]">
          {/* Brand column */}
          <div>
            <EarningsNerdLogo variant="icon-only" iconClassName="h-8 w-8" mode="auto" />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
              AI-powered SEC filing analysis. Read any 10-K or 10-Q in minutes.
            </p>
          </div>

          {/* Link columns */}
          {Object.entries(FOOTER_LINKS).map(([category, links]) => (
            <div key={category}>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-text-tertiary-light dark:text-text-secondary-dark">
                {category}
              </h3>
              <ul className="mt-4 space-y-3">
                {links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-sm text-text-secondary-light transition-colors hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-border-light pt-8 dark:border-white/[0.06] sm:flex-row">
          <p className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">
            &copy; {CURRENT_YEAR} EarningsNerd. All rights reserved.
          </p>
          <p className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">
            Data sourced from SEC EDGAR. AI-generated content, for informational purposes only.
            Not investment advice. Not affiliated with the SEC.
          </p>
        </div>

        <p className="mt-4 text-center text-xs text-text-tertiary-light dark:text-text-secondary-dark">
          Company logos by{' '}
          <a
            href="https://logo.dev"
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-2 hover:text-text-secondary-light dark:hover:text-text-primary-dark"
          >
            Logo.dev
          </a>
          . Logos and trademarks are the property of their respective owners.
        </p>
      </div>
    </footer>
  )
}
