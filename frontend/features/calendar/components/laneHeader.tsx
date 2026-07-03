'use client'

/* Shared lane header — Before open / After close / During·unspecified.
   Used by WeekView (dense + roomy) and DayDetailDialog. */

import { cx } from '@/components/ui/cx'
import { ClockIcon, MoonIcon, SunIcon } from '@/lib/icons'
import type { LaneKey } from '../lib/lanes'

const LANE_ICON: Record<LaneKey, typeof SunIcon> = { bmo: SunIcon, amc: MoonIcon, other: ClockIcon }

export function WeekViewLaneHeader({ laneKey, label, dense }: { laneKey: LaneKey; label: string; dense?: boolean }) {
  const Icon = LANE_ICON[laneKey]
  return (
    <div
      className={cx(
        'flex items-center gap-1.5 text-text-tertiary-light dark:text-text-secondary-dark',
        dense ? 'px-1 pb-1 pt-2' : 'px-2 pb-1 pt-3',
      )}
    >
      <Icon aria-hidden="true" className="h-3 w-3 flex-none" />
      <span className="text-xs font-semibold uppercase tracking-[0.08em]">{label}</span>
      <span aria-hidden="true" className="h-px flex-1 bg-border-light/60 dark:bg-white/[0.06]" />
    </div>
  )
}
