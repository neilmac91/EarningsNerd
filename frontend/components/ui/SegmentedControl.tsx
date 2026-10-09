'use client'

/* =============================================================================
   SegmentedControl — components/ui/SegmentedControl.tsx   (v3.1, 2026-10)
   -----------------------------------------------------------------------------
   The ONE single-choice toggle group: lifted from the calendar's Week / Month
   switch (its recipe, unchanged), shared by the calendar view and the filings
   index's form filter. A role="group" of real <button>s with aria-pressed —
   every option is visible, so this is not a radiogroup or a tablist.
     - shell:    panel fill + hairline + e1 lift, rounded-lg (12), p-1.
                 dark: fill contrast + hairline, shadow-none.
     - segment:  rounded (8) · 12/600 · secondary ink → primary on hover.
                 Selected = the primary-button colorway: bg-brand + white;
                 dark FLIPS to navy ink on brand-dark (white on brand.fill-dark
                 is 3.7:1 — never revert to it).
     - sizes:    sm 26px (desktop toolbars — the calendar) · md 36px (touch) ·
                 adaptive = 36px below sm, 26px from sm up.
     - mono:     an option whose label is a code (10-K, 10-Q) sets it in the
                 data face, so a form code reads the same here as in the rows.
   Focus-visible = ring-brand. No hover:opacity anywhere (it darkens).
============================================================================= */

import { type ReactNode } from 'react'
import { cx } from './cx'

export type SegmentedControlSize = 'sm' | 'md' | 'adaptive'

export interface SegmentedOption<T extends string> {
  value: T
  label: ReactNode
  /** Set the label in the data face (form codes, tickers): Geist Mono + tabular figures. */
  mono?: boolean
}

export interface SegmentedControlProps<T extends string> {
  /** Names the group for assistive tech ("Calendar view", "Filter by form"). */
  label: string
  options: readonly SegmentedOption<T>[]
  value: T
  onChange: (value: T) => void
  size?: SegmentedControlSize
  /** Stretch the segments across the row below sm (phone toolbars); auto width from sm up. */
  fullWidth?: boolean
  className?: string
}

const SHELL = cx(
  'inline-flex rounded-lg border border-border-light bg-panel-light p-1 shadow-e1',
  'dark:border-white/10 dark:bg-panel-dark dark:shadow-none',
)

const SEGMENT = cx(
  'inline-flex items-center justify-center rounded font-semibold transition-colors duration-fast',
  'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
)

const SIZE: Record<SegmentedControlSize, string> = {
  sm: 'h-[26px] px-3.5 text-xs',
  md: 'h-9 px-3 text-sm',
  adaptive: 'h-9 px-3 text-sm sm:h-[26px] sm:px-3.5 sm:text-xs',
}

const SELECTED = 'bg-brand text-white shadow-e1 dark:bg-brand-dark dark:text-background-dark'
const RESTING = cx(
  'text-text-secondary-light hover:text-text-primary-light',
  'dark:text-text-secondary-dark dark:hover:text-text-primary-dark',
)

export function SegmentedControl<T extends string>({
  label,
  options,
  value,
  onChange,
  size = 'sm',
  fullWidth = false,
  className,
}: SegmentedControlProps<T>) {
  return (
    <div role="group" aria-label={label} className={cx(SHELL, fullWidth && 'flex w-full sm:inline-flex sm:w-auto', className)}>
      {options.map((option) => {
        const selected = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            onClick={() => {
              if (!selected) onChange(option.value)
            }}
            className={cx(
              SEGMENT,
              SIZE[size],
              fullWidth && 'flex-1 sm:flex-none',
              option.mono && 'font-data tabular-nums',
              selected ? SELECTED : RESTING,
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
