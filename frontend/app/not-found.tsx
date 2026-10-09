'use client'

import Link from 'next/link'
import { buttonVariants, Card } from '@/components/ui'
import { MagnifyingGlassIcon } from '@/lib/icons'

/**
 * The EarningsNerd 404: rendered for every notFound() call (a filing id or ticker the backend does
 * not know, a flag-gated route such as /analysis or /search when its flag is off) and for any URL
 * the app does not serve. Next's stock page in its place read "404 | This page could not be found."
 * in the OS colour scheme, with no way back. It renders inside the root layout, so the site header,
 * footer and the skip link's #main wrapper surround it; this <main> is the page's one landmark.
 * Next sends the 404 status and a noindex robots tag; the <title> below is hoisted into <head>, as
 * Next's own 404 does. A client component, like app/error.tsx: buttonVariants() is a client export,
 * which a server component cannot call (lessons/frontend-client-exports-need-next-build.md).
 */
export default function NotFound() {
  return (
    <main className="flex min-h-[60vh] items-center justify-center bg-background-light px-4 py-16 dark:bg-background-dark">
      <title>Page not found | EarningsNerd</title>
      <Card data-not-found-card className="flex w-full max-w-md flex-col items-center px-6 py-10 text-center">
        <span
          aria-hidden="true"
          className="flex h-11 w-11 items-center justify-center rounded-full border border-brand-border bg-brand-weak text-brand-strong dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-brand-strong-dark"
        >
          <MagnifyingGlassIcon className="h-5 w-5" />
        </span>
        <h1 className="mt-4 text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">Page not found</h1>
        <p className="mt-2 max-w-[38ch] text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
          We couldn&apos;t find this page. The link may be mistyped or out of date. Search for a company
          from the homepage, or open your dashboard.
        </p>
        <div className="mt-6 flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
          <Link href="/" className={buttonVariants({ variant: 'primary' })}>
            Go to the homepage
          </Link>
          <Link href="/dashboard" className={buttonVariants({ variant: 'secondary' })}>
            Open your dashboard
          </Link>
        </div>
      </Card>
    </main>
  )
}
