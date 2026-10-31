import { cx } from './cx'

/** The fill at a share of the month's limit: the brand's sage, then warning from 80% and error at 100%, the state of
    a limit nearly or wholly used (the status colours paint a state, never a decoration: DESIGN_SYSTEM.md §4 › Usage
    meter). */
export function usageMeterFill(percent: number): string {
  if (percent >= 100) return 'bg-error-light dark:bg-error-dark'
  if (percent >= 80) return 'bg-warning-light dark:bg-warning-dark'
  return 'bg-brand-strong dark:bg-brand-dark'
}

export interface UsageMeterProps {
  /** What the account has used this month. */
  used: number
  /** The month's limit; with none (null, or 0) the meter stays empty. */
  limit: number | null | undefined
  /** Names the meter as a progress bar, read with its value. Without one the meter is drawn only, beside counts the
      surface prints in words (the dashboard's plan card). */
  label?: string
  className?: string
}

/**
 * A plan's monthly usage as a bar (E196): a hairline track (the card's own fill in light, the page's ground a step below
 * the card in dark) and a fill that never runs past it,
 * the dashboard's plan card and the pricing page's usage box. The warning and error fills are the meter's own status
 * tints, so a surface draws the meter through this primitive rather than its classes
 * (tests/unit/statusTintResidue.spec.ts leaves components/ui alone).
 */
export function UsageMeter({ used, limit, label, className }: UsageMeterProps) {
  const percent = limit ? (used / limit) * 100 : 0
  const named = label ? { role: 'progressbar', 'aria-label': label, 'aria-valuenow': used, 'aria-valuemin': 0, 'aria-valuemax': limit ?? undefined } : {}
  return (
    <div
      className={cx('h-3 w-full rounded-full border border-border-light bg-panel-light dark:border-border-dark dark:bg-background-dark', className)}
      {...named}
    >
      <div
        className={cx('h-full rounded-full transition-[width] duration-base', usageMeterFill(percent))}
        style={{ width: `${Math.min(100, percent)}%` }}
      />
    </div>
  )
}
