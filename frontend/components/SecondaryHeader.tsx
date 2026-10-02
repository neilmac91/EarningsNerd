'use client'

import Link from 'next/link'
import { CaretLeftIcon } from '@/lib/icons'
import EarningsNerdLogoIcon from './EarningsNerdLogoIcon'

type SecondaryHeaderProps = {
  title?: string
  subtitle?: string
  backHref?: string
  backLabel?: string
  actions?: React.ReactNode
}

export default function SecondaryHeader({
  title,
  subtitle,
  backHref,
  backLabel = 'Back',
  actions,
}: SecondaryHeaderProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-border-light dark:border-white/10 bg-panel-light/80 dark:bg-panel-dark/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-5 sm:px-6 lg:px-8">
        {/* The subtitle (often per-user, e.g. "Welcome back, <name>") never sizes the row: it is
            inline-size contained, so only the back link, title and actions decide where the row
            wraps, and the title block grows into the free space where the subtitle truncates. A late
            or long subtitle therefore can't change the header's height and move the page below. */}
        <div className="flex min-w-0 grow flex-wrap items-center gap-x-1 gap-y-4 sm:gap-x-4">
          {backHref && (
            // Below sm the back link is its caret alone (the label stays as its accessible name), so
            // the subtitle keeps room for a name. The 44px target reaches into the gutter, keeping
            // the caret on the page edge.
            <Link
              href={backHref}
              className="-ml-3.5 inline-flex min-h-11 min-w-11 items-center justify-center text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark transition hover:text-text-primary-light dark:hover:text-text-primary-dark sm:ml-0 sm:min-h-0 sm:min-w-0 sm:justify-start"
            >
              <CaretLeftIcon aria-hidden="true" className="h-4 w-4 sm:mr-1" />
              <span className="sr-only sm:not-sr-only">{backLabel}</span>
            </Link>
          )}
          <div className="flex min-w-0 grow items-center gap-3">
            <EarningsNerdLogoIcon className="h-8 w-8 shrink-0" />
            <div className="min-w-0 grow">
              {title && (
                <h1 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">{title}</h1>
              )}
              {subtitle && (
                <p className="truncate text-xs text-text-secondary-light [contain:inline-size] dark:text-text-secondary-dark">
                  {/* The tooltip sits on the text, not the <p>, which spans the whole free width. */}
                  <span title={subtitle}>{subtitle}</span>
                </p>
              )}
            </div>
          </div>
        </div>
        {actions && <div className="flex items-center gap-3">{actions}</div>}
      </div>
    </header>
  )
}
