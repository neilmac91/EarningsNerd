'use client'

import * as Sentry from '@sentry/nextjs'

import { Inter } from 'next/font/google'
import { useEffect } from 'react'

const inter = Inter({ subsets: ['latin'] })

export default function GlobalError({
    error,
    reset,
}: {
    error: Error & { digest?: string }
    reset: () => void
}) {
    useEffect(() => {
        Sentry.captureException(error)
    }, [error])

    return (
        <html lang="en" className={inter.className}>
            <body>
                <div className="flex min-h-screen flex-col items-center justify-center bg-background-light p-4 text-center dark:bg-background-dark">
                    <div className="mx-auto max-w-md space-y-4">
                        <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
                            Something went wrong
                        </h2>
                        <p className="text-text-secondary-light dark:text-text-secondary-dark">
                            The error has been logged. Try again, or reload the page.
                        </p>
                        <div className="flex justify-center gap-4">
                            <button
                                onClick={() => reset()}
                                className="rounded-lg bg-brand px-4 py-2 font-medium text-white transition-colors hover:bg-brand-strong active:bg-brand-emphasis dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark focus:outline-none focus:shadow-ring-brand "
                            >
                                Try again
                            </button>
                            <button
                                onClick={() => window.location.reload()}
                                className="rounded-lg border border-border-light bg-white px-4 py-2 font-medium text-text-secondary-light transition-colors hover:bg-background-light focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 dark:border-border-dark dark:bg-panel-dark dark:text-text-secondary-dark dark:hover:bg-white/5"
                            >
                                Reload page
                            </button>
                        </div>
                        {process.env.NODE_ENV === 'development' && (
                            <div className="mt-8 overflow-auto rounded-lg bg-error-light/10 p-4 text-left text-sm text-error-light dark:bg-error-dark/10 dark:text-error-dark">
                                <p className="font-mono">{error.message}</p>
                                {error.digest && <p className="mt-2 font-mono text-xs">Digest: {error.digest}</p>}
                            </div>
                        )}
                    </div>
                </div>
            </body>
        </html>
    )
}
