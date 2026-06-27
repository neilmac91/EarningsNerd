import Link from 'next/link'
import EarningsNerdLogo from '@/components/EarningsNerdLogo'

const FOOTER_LINKS = {
  Product: [
    { label: 'Search Filings', href: '/search' },
    { label: 'Pricing', href: '/pricing' },
    { label: 'Hot Filings', href: '/#hot-filings' },
    { label: 'Trending', href: '/#trending' },
  ],
  Resources: [
    { label: 'Contact', href: '/contact' },
  ],
  Legal: [
    { label: 'Privacy', href: '/privacy' },
    { label: 'Terms', href: '/terms' },
    { label: 'Security', href: '/security' },
  ],
} as const

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
              AI-powered SEC filing analysis. Turn dense filings into clear, decision-ready insights.
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
                      className="text-sm text-text-secondary-light transition-colors hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-light"
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
            Data sourced from SEC EDGAR. Not investment advice.
          </p>
        </div>
      </div>
    </footer>
  )
}
