'use client'

import type { HTMLAttributes } from 'react'
import { MinusIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'
import { directionChip, directionText, type Direction } from '@/lib/financialTone'
import { cx } from './cx'

const GLYPH = { up: TrendUpIcon, down: TrendDownIcon, flat: MinusIcon } as const

export interface DeltaChipProps extends HTMLAttributes<HTMLSpanElement> {
  label: string
  direction: Direction
  /** Semantic tone is independent of direction (e.g. rising expenses can be unfavorable). */
  tone: Direction
  /** Server-formatted signed figure; null when no meaningful comparison exists. */
  display?: string | null
}

/** Non-interactive financial annotation. Sage belongs to navigation and the New badge. */
export function DeltaChip({ label, direction, tone, display, className, ...rest }: DeltaChipProps) {
  const Icon = GLYPH[direction]
  return (
    <span
      {...rest}
      className={cx('inline-flex min-w-0 max-w-full flex-wrap items-center gap-x-1.5 rounded-xl border px-2.5 py-1 text-xs font-medium [overflow-wrap:anywhere]', directionChip[tone], className)}
    >
      <span className="min-w-0">{label}</span>
      <span className={cx('inline-flex min-w-0 items-center gap-0.5', directionText[tone])}>
        <Icon aria-hidden="true" className="h-3.5 w-3.5 flex-shrink-0" />
        {display ? <span className="min-w-0 font-data font-semibold tabular-nums">{display}</span> : (
          <span className="sr-only">{direction === 'flat' ? ' unchanged' : direction === 'up' ? ' up' : ' down'}</span>
        )}
      </span>
    </span>
  )
}
