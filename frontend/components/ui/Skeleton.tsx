/* =============================================================================
   Skeleton — components/ui/Skeleton.tsx
   -----------------------------------------------------------------------------
   Formalizes the shimmer: base bone + a gradient sweep driven by the config's
   `animate-shimmer` keyframe, token-timed (duration-ambient / ease-standard —
   the shared ambient-loop cadence). Reduced-motion users get a static bone
   (motion-reduce:animate-none).
   Compose per surface: SkeletonText for streaming summaries (mono),
   SkeletonStat for KPI tiles, or raw <Skeleton> for anything else.
============================================================================= */

import { type HTMLAttributes } from 'react'
import { cx } from './cx'

/** A caller's own max width (`max-w-md`); a breakpoint's (`sm:max-w-md`) applies only from its breakpoint. */
const OWN_MAX_WIDTH = /(?:^|\s)max-w-/

export function Skeleton({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden="true"
      // A bone keeps its rem width, so under enlarged text a wide one ran past its container and scrolled the page
      // sideways while it showed (E233). It stops at its container unless the caller sets its own max width: cx only
      // joins classes, so beside a caller's max-w-* Tailwind's emission order, not the caller, would pick the winner.
      className={cx(
        'relative overflow-hidden rounded bg-text-primary-light/[0.08] dark:bg-white/[0.08]',
        !OWN_MAX_WIDTH.test(className ?? '') && 'max-w-full',
        className,
      )}
      {...rest}
    >
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/70 to-transparent motion-reduce:animate-none dark:via-white/[0.07]" />
    </div>
  )
}

const LINE_WIDTHS = ['w-full', 'w-11/12', 'w-4/5']

export function SkeletonText({
  lines = 3,
  mono = false,
  className,
}: {
  lines?: number
  /** Mono rhythm — use for filing summaries / Ask-this-Filing while streaming. */
  mono?: boolean
  className?: string
}) {
  return (
    <div role="status" aria-label="Loading" className={cx('flex flex-col', mono ? 'gap-3' : 'gap-2.5', className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={cx('h-3', i === lines - 1 ? 'w-2/3' : LINE_WIDTHS[i % LINE_WIDTHS.length])} />
      ))}
      <span className="sr-only">Loading…</span>
    </div>
  )
}

/** KPI-tile shape: label / figure / delta. */
export function SkeletonStat({ className }: { className?: string }) {
  return (
    <div role="status" aria-label="Loading" className={cx('flex flex-col gap-2', className)}>
      <Skeleton className="h-2.5 w-16" />
      <Skeleton className="h-6 w-24" />
      <Skeleton className="h-2.5 w-20" />
      <span className="sr-only">Loading…</span>
    </div>
  )
}
