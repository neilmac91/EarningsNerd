import { type HTMLAttributes } from 'react'
import { cx } from '@/components/ui/cx'

/** What the counter's pill says until a count worth saying lands: the label the waitlist page's status holds (E222). */
export const PILL_LABEL = 'Join the waitlist'

/** The waitlist counter's sage pill. The waitlist page's status holds an invisible one in its cell (WaitlistAccessStatus). */
export default function WaitlistPill({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...rest}
      className={cx(
        'inline-flex items-center justify-center rounded-full border border-brand-border bg-brand-weak px-4 py-2 text-sm font-medium text-brand-strong shadow-e1 dark:border-brand-dark/40 dark:bg-brand-dark/15 dark:text-brand-strong-dark',
        className,
      )}
    />
  )
}
