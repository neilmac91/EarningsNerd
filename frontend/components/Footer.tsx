'use client'

import { CONTACT_ADDRESSES, contactMailto } from '@/lib/contactAddresses'
import Link from 'next/link'
import EarningsNerdLogo from '@/components/EarningsNerdLogo'
import { openCookieSettings } from '@/lib/cookieSettings'
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
    { label: CONTACT_ADDRESSES.support, href: contactMailto('support') },
  ],
  Legal: [
    { label: 'Privacy', href: '/privacy' },
    { label: 'Terms', href: '/terms' },
    { label: 'Security', href: '/security' },
  ],
}

// One recipe for the column links and for "Cookie settings", a button that reads as one of them (it opens a dialog
// and goes nowhere), each with the brand focus ring. `text-left` is for the button, which centres its text by
// default, so a label that ever wraps lines up with the links; on an inline link it changes nothing.
const FOOTER_LINK =
  'text-left text-sm [overflow-wrap:anywhere] text-text-secondary-light transition-colors hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark'

export default function Footer() {
  // Read where the footer renders, on the server and again in the browser. The two can disagree for a few hours
  // around New Year, or on a page built last year, so the year's paragraph lets its own text differ at hydration
  // (suppressHydrationWarning covers that text only): React sets the browser's year rather than discarding the
  // server's markup.
  const year = new Date().getFullYear()
  return (
    <footer className="border-t border-border-light bg-background-light dark:border-white/[0.06] dark:bg-background-dark">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        {/* The footer opens its own outline section, so its column titles (h3) never follow a page
            whose content ends at h1 (the 404, /analysis, /search) with a skipped level. */}
        <h2 className="sr-only">Site links</h2>
        {/* Four columns from md at the reader's text size: 48rem is 768px at the default size and 1536px under a
            200% text setting. An fr column never shrinks below its longest word, so md's 768px opened them at
            200% text and the Legal column took the page to 812px (tests/e2e/reflow-200.spec.ts). */}
        <div className="grid grid-cols-1 gap-10 [@media(min-width:48rem)]:grid-cols-[1.5fr_1fr_1fr_1fr]">
          {/* Brand column */}
          <div>
            <EarningsNerdLogo variant="icon-only" iconClassName="h-8 w-8" mode="auto" />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
              The summary that shows its work.
            </p>
          </div>

          {/* Link columns */}
          {Object.entries(FOOTER_LINKS).map(([category, links]) => (
            <div key={category}>
              <h3 className="text-xs font-semibold uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-secondary-dark">
                {category}
              </h3>
              <ul className="mt-4 space-y-3">
                {links.map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className={FOOTER_LINK}>
                      {link.label}
                    </Link>
                  </li>
                ))}
                {/* The way back to the cookie settings after a first choice, which /privacy's withdrawal sentence
                    promises ("through our cookie consent banner or settings"): it opens CookieConsent's dialog on
                    the stored choices (lib/cookieSettings.ts). It takes focus first, so ui/Modal returns focus
                    here on close whatever pressed it (Safari does not focus a clicked button). The auth routes
                    have no site footer (lib/authShellRoutes.ts). */}
                {category === 'Legal' && (
                  <li>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.currentTarget.focus()
                        openCookieSettings()
                      }}
                      className={FOOTER_LINK}
                    >
                      Cookie settings
                    </button>
                  </li>
                )}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-border-light pt-8 dark:border-white/[0.06] sm:flex-row">
          <p suppressHydrationWarning className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">
            &copy; {year} EarningsNerd. All rights reserved.
          </p>
          <p className="text-xs text-text-secondary-light dark:text-text-secondary-dark">
            Data sourced from SEC EDGAR. AI-generated content, for informational purposes only.
            Not investment advice. Not affiliated with the SEC.
          </p>
        </div>

        {/* Logo.dev's Community plan asks a commercial site for this link on a public page, in the form
            its attribution page gives (the whole phrase as the link text); its dashboard loads the page
            to find it. tests/unit/Footer.spec.tsx holds the link. */}
        <p className="mt-4 text-center text-xs text-text-tertiary-light dark:text-text-secondary-dark">
          <a
            href="https://logo.dev"
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-2 hover:text-text-secondary-light dark:hover:text-text-primary-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
          >
            Logos provided by Logo.dev
          </a>
          . Logos and trademarks are the property of their respective owners.
        </p>
      </div>
    </footer>
  )
}
