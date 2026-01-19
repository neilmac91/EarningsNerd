'use client'

import Link from 'next/link'
import { ChevronLeft } from 'lucide-react'
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
    <header className="sticky top-0 z-40 border-b border-gray-200/70 bg-white/80 backdrop-blur dark:border-white/10 dark:bg-slate-950/80">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-5 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-center gap-4">
          {backHref && (
            <Link
              href={backHref}
              className="inline-flex items-center text-sm font-medium text-slate-600 transition hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
            >
              <ChevronLeft className="mr-1 h-4 w-4" />
              {backLabel}
            </Link>
          )}
          <div className="flex items-center gap-3">
            <EarningsNerdLogoIcon className="h-8 w-8" />
            <div>
              {title && (
                <h1 className="text-lg font-semibold text-slate-900 dark:text-white">{title}</h1>
              )}
              {subtitle && (
                <p className="text-xs text-slate-500 dark:text-slate-400">{subtitle}</p>
              )}
            </div>
          </div>
        </div>
        {actions && <div className="flex items-center gap-3">{actions}</div>}
      </div>
    </header>
  )
}
