import type { ReactNode } from 'react'
import { cx } from '@/components/ui'

export type CalloutTone = 'neutral' | 'caution'

interface CalloutProps {
  /** The callout's label word ("Note", "Red flag"); it carries the tone, the body never does. */
  label?: string | null
  tone?: CalloutTone
  children: ReactNode
}

/**
 * A labelled inset well inside a summary section (2026-10 critique P-08). It replaces SummaryBlock,
 * the last side-tab stripe card: panel fill, one hairline, the 8px radius and no shadow, so the well
 * reads as part of its section rather than a card lifted off it. Tone lives in the label word alone
 * (`caution` sets the label in warning ink); the body stays secondary ink in both tones.
 */
export function Callout({ label, tone = 'neutral', children }: CalloutProps) {
  return (
    <div className="rounded border border-border-light bg-panel-light px-4 py-3.5 dark:border-white/10 dark:bg-panel-dark">
      {label && (
        <p
          className={cx(
            'mb-1 text-sm font-semibold',
            tone === 'caution'
              ? 'text-warning-light dark:text-warning-dark'
              : 'text-text-primary-light dark:text-text-primary-dark',
          )}
        >
          {label}
        </p>
      )}
      <div className="text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">{children}</div>
    </div>
  )
}
