'use client'

import Link from 'next/link'
import { ArrowLeft, FileText, ShieldCheck } from 'lucide-react'
import EarningsNerdLogoIcon from '@/components/EarningsNerdLogoIcon'
import { directionChip } from '@/lib/financialTone'

/**
 * Split-screen auth shell: focused form on the left, a constant branded value
 * pane on the right (hidden on mobile). Used by every auth page.
 */
export default function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Form pane */}
      <div className="flex min-h-screen flex-col bg-background-light dark:bg-background-dark">
        <div className="flex items-center justify-between px-6 py-6 sm:px-10">
          <Link href="/" className="flex items-center gap-2.5">
            <EarningsNerdLogoIcon className="h-8 w-8" />
            <span className="text-lg font-bold text-text-primary-light dark:text-text-primary-dark">
              EarningsNerd
            </span>
          </Link>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-text-secondary-light transition-colors hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-light"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to home
          </Link>
        </div>

        <div className="flex flex-1 items-center justify-center px-6 pb-16 sm:px-10">
          <div className="w-full max-w-[400px] animate-fade-up">{children}</div>
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
        <h2 className="text-3xl font-bold leading-tight text-text-primary-light dark:text-text-primary-dark">
          Decode any filing
          <br />
          in minutes.
        </h2>
        <p className="mt-4 text-base leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
          Business overview, financials, risks, and outlook — every number traced to the SEC source.
        </p>

        {/* Showcase card */}
        <div className="glass-card animate-float mt-10 rounded-2xl p-5">
          <div className="flex items-center gap-2 text-xs font-medium text-text-secondary-light dark:text-text-secondary-dark">
            <FileText className="h-4 w-4 text-brand-strong dark:text-brand-strong-dark" />
            AAPL · 10-K
          </div>
          <div className="mt-3 space-y-2" aria-hidden="true">
            <div className="h-2 w-3/4 rounded-full bg-brand-weak dark:bg-white/10" />
            <div className="h-2 w-full rounded-full bg-brand-weak dark:bg-white/10" />
            <div className="h-2 w-2/3 rounded-full bg-brand-weak dark:bg-white/10" />
          </div>
          <div className="mt-4 flex items-end justify-between border-t border-border-light pt-4 dark:border-white/10">
            <div>
              <p className="text-xs text-text-secondary-light dark:text-text-secondary-dark">Revenue</p>
              <p className="text-lg font-bold text-text-primary-light dark:text-text-primary-dark">$383.3B</p>
            </div>
            <div className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${directionChip.up}`}>
              +2.8% YoY
            </div>
          </div>
        </div>

        {/* Trust signals */}
        <div className="mt-10 flex items-center gap-6 text-xs font-medium text-text-secondary-light dark:text-text-secondary-dark">
          <span className="inline-flex items-center gap-1.5">
            <ShieldCheck className="h-4 w-4 text-brand-strong dark:text-brand-strong-dark" />
            SEC EDGAR
          </span>
          <span className="inline-flex items-center gap-1.5">
            <FileText className="h-4 w-4 text-brand-strong dark:text-brand-strong-dark" />
            XBRL-verified
          </span>
        </div>
      </div>
    </div>
  )
}
