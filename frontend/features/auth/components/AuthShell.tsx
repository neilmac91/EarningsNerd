'use client'

import Link from 'next/link'
import { ArrowLeftIcon, FileTextIcon, ShieldCheckIcon } from '@/lib/icons'
import EarningsNerdLogo from '@/components/EarningsNerdLogo'
import { ThemeToggle } from '@/components/ThemeToggle'
import { directionChip } from '@/lib/financialTone'

/**
 * Split-screen auth shell: focused form on the left, a constant branded value
 * pane on the right (hidden on mobile). Used by every auth page.
 */
export default function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 min-h-screen lg:grid-cols-2">
      {/* Form pane */}
      <div className="flex min-h-screen flex-col bg-background-light dark:bg-background-dark">
        <div className="flex items-center justify-between px-6 py-6 sm:px-10">
          <Link href="/" className="flex items-center gap-2.5 rounded-lg focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">
            <EarningsNerdLogo iconClassName="h-8 w-8" wordmarkClassName="text-lg" />
          </Link>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Link
              href="/"
              className="inline-flex items-center gap-1.5 text-sm font-medium text-text-secondary-light transition-colors hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
            >
              <ArrowLeftIcon className="h-4 w-4" />
              Back to home
            </Link>
          </div>
        </div>

        <div className="flex flex-1 items-center justify-center px-6 pb-16 sm:px-10">
          <div className="w-full max-w-[400px] animate-fade-up motion-reduce:animate-none">{children}</div>
        </div>
      </div>

      {/* Brand pane */}
      <AuthBrandPane />
    </div>
  )
}

function AuthBrandPane() {
  return (
    <div className="hidden overflow-hidden bg-brand-weak dark:bg-panel-dark lg:flex lg:flex-col lg:items-center lg:justify-center">
      <div className="w-full max-w-md px-12">
        <h2 className="text-3xl font-semibold leading-tight text-text-primary-light dark:text-text-primary-dark">
          The summary that
          <br />
          <span className="en-mark">shows its work</span>.
        </h2>
        <p className="mt-4 text-base leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
          Nine parts per filing, with figures checked against the company’s XBRL where they can be
          and quotes against the filing’s own text.
        </p>

        {/* Showcase card */}
        <div className="glass-card mt-10 rounded-2xl p-5">
          <div className="flex items-center gap-2 font-data text-xs text-text-secondary-light dark:text-text-secondary-dark">
            <FileTextIcon className="h-4 w-4 text-brand-strong dark:text-brand-strong-dark" aria-hidden="true" />
            Example · AAPL · 10-K · FY2025
          </div>
          {/* The summary's opening, as the live example states it; figures verified against the
              filing's XBRL (docs/brand/00-audit.md §4). No placeholder bars: words or nothing. */}
          <p className="mt-3 text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
            Total net sales rose 6.4% to $416.2B with net income of $112.0B and diluted EPS of $7.46,
            while operating cash flow declined to $111.5B from $118.3B.
          </p>
          <div className="mt-4 flex items-end justify-between border-t border-border-light pt-4 dark:border-white/10">
            <div>
              <p className="text-xs text-text-secondary-light dark:text-text-secondary-dark">Revenue</p>
              <p className="font-data text-lg font-semibold tabular-nums text-text-primary-light dark:text-text-primary-dark">$416.2B</p>
            </div>
            <div className={`rounded-full border px-2.5 py-1 font-data text-xs font-semibold tabular-nums ${directionChip.up}`}>
              ▲ +6.4% YoY
            </div>
          </div>
        </div>

        {/* Trust signals */}
        <div className="mt-10 flex items-center gap-6 text-xs font-medium text-text-secondary-light dark:text-text-secondary-dark">
          <span className="inline-flex items-center gap-1.5">
            <ShieldCheckIcon className="h-4 w-4 text-brand-strong dark:text-brand-strong-dark" />
            SEC EDGAR
          </span>
          <span className="inline-flex items-center gap-1.5">
            <FileTextIcon className="h-4 w-4 text-brand-strong dark:text-brand-strong-dark" />
            Filing-sourced figures
          </span>
        </div>
      </div>
    </div>
  )
}
