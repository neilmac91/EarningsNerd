'use client'

import * as Sentry from '@sentry/nextjs'

type Props = {
  className?: string
}

export default function SentryTestButton({ className }: Props) {
  const handleClick = () => {
    const error = new Error('Sentry test error: EarningsNerd client')
    Sentry.captureException(error, {
      tags: { source: 'sentry-test-button' },
      level: 'error',
    })
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className={
        className ??
        'rounded-md border border-border-light px-3 py-1 text-xs font-medium text-text-secondary-light transition-colors hover:text-text-primary-light dark:border-border-dark dark:text-text-secondary-dark dark:hover:text-text-primary-dark'
      }
    >
      Trigger Sentry Test
    </button>
  )
}
