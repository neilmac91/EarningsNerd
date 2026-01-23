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
                <div className="flex min-h-screen flex-col items-center justify-center bg-white p-4 text-center dark:bg-slate-900">
                    <div className="mx-auto max-w-md space-y-4">
                        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
                            Something went wrong!
                        </h2>
                        <p className="text-slate-600 dark:text-slate-400">
                            We apologize for the inconvenience. An unexpected error has occurred.
                        </p>
                        <div className="flex justify-center gap-4">
                            <button
                                onClick={() => reset()}
                                className="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                            >
                                Try again
                            </button>
                            <button
                                onClick={() => window.location.reload()}
                                className="rounded-lg border border-slate-300 bg-white px-4 py-2 font-medium text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
                            >
                                Reload Page
                            </button>
                        </div>
                        {process.env.NODE_ENV === 'development' && (
                            <div className="mt-8 overflow-auto rounded-lg bg-red-50 p-4 text-left text-sm text-red-900 dark:bg-red-900/20 dark:text-red-200">
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
