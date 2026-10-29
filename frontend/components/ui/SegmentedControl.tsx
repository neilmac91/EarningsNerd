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
     - segment:  rounded (8) · 600 · 12px at 26px, 14px at 36px · secondary ink →
                 primary on hover.
                 Selected = the primary-button colorway: bg-brand + white;
                 dark FLIPS to navy ink on brand-dark (white on brand.fill-dark
                 is 3.7:1 — never revert to it).
     - sizes:    sm 1.625rem, 26px at the default root (desktop toolbars — the
                 calendar) · md 36px, the comfortable size (fields keep the 44px
                 touch height; a phone segment is at least 79px wide, clear of
                 WCAG 2.5.8's 24px) · adaptive = 36px below sm, 1.625rem from sm
                 up, a device's switch (a phone's touch size), so it stays at sm. Heights are rem (px figures here are at
                 the 16px root), so enlarged text keeps its segments: at a 32px
                 root text-xs's 32px line box overflowed a fixed 26px.
     - mono:     an option whose label is a code (10-K, 10-Q) sets it in the
                 data face, so a form code reads the same here as in the rows.
     - labels never break (10-K/A breaks at its hyphen and slash otherwise);
                 fullWidth wraps whole segments onto another row instead, below
                 40rem: 640px at the default size and 1280px under 200% text, a
                 rem switch because what the row must hold is set in rem. At sm,
                 640px at any text size, one row of five forms ran past its card
                 under 200% text (E183, chief design on #1570, comment 6380853186;
                 tests/e2e/reflow-200.spec.ts).
     - cap:      at most MAX_SEGMENTS (five) options; a longer set is a compact
                 select beside its label (DESIGN.md). A set known only at run
                 time (the filings form filter) checks itself against it.
   Focus-visible = ring-brand. No hover:opacity anywhere (it darkens).
============================================================================= */

import { type ReactNode } from 'react'
import { cx } from './cx'

export type SegmentedControlSize = 'sm' | 'md' | 'adaptive'

/** The most options one control holds (DESIGN.md, the SegmentedControl paragraph): every segment shows at once
 *  and a label never breaks, so a longer set is a compact select. FilingIndex's form filter, a set known only at
 *  run time, renders as the select past it; tests/unit/segmentedControlOptionCount.spec.ts holds every set it can
 *  count statically to it. */
export const MAX_SEGMENTS = 5

export interface SegmentedOption<T extends string> {
  value: T
  label: ReactNode
  /** Set the label in the data face (form codes, tickers): Geist Mono + tabular figures. */
  mono?: boolean
  /** Unavailable before selection (for example, a mode with no data). */
  disabled?: boolean
  /** ID of visible explanatory copy, useful when an unavailable option stays focusable. */
  descriptionId?: string
}

export interface SegmentedControlProps<T extends string> {
  /** Names the group for assistive tech ("Calendar view", "Filter by form"). */
  label: string
  options: readonly SegmentedOption<T>[]
  value: T
  onChange: (value: T) => void
  size?: SegmentedControlSize
  /** Stretch the segments across the row below 40rem (phone toolbars, and narrow ones under enlarged text), wrapping
   *  onto another row when they do not fit, so every option stays visible; one auto-width row from 40rem up. */
  fullWidth?: boolean
  /** Keep unavailable modes in the Tab order so their explanation can be read. Defaults to native disabled. */
  focusableDisabled?: boolean
  className?: string
}

const SHELL = cx(
  'inline-flex rounded-lg border border-border-light bg-panel-light p-1 shadow-e1',
  'dark:border-white/10 dark:bg-panel-dark dark:shadow-none',
)

const SEGMENT = cx(
  'inline-flex items-center justify-center whitespace-nowrap rounded font-semibold transition-colors duration-fast',
  'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark aria-disabled:cursor-not-allowed disabled:cursor-not-allowed disabled:opacity-40',
)

const SIZE: Record<SegmentedControlSize, string> = {
  sm: 'h-[1.625rem] px-3.5 text-xs',
  md: 'h-9 px-3 text-sm',
  adaptive: 'h-9 px-3 text-sm sm:h-[1.625rem] sm:px-3.5 sm:text-xs',
}

const SELECTED = 'bg-brand text-white shadow-e1 dark:bg-brand-dark dark:text-background-dark'
const RESTING = cx(
  'text-text-secondary-light hover:text-text-primary-light',
  'dark:text-text-secondary-dark dark:hover:text-white',
)
const UNAVAILABLE = 'bg-background-light text-text-secondary-light dark:bg-background-dark dark:text-text-secondary-dark'

export function SegmentedControl<T extends string>({
  label,
  options,
  value,
  onChange,
  size = 'sm',
  fullWidth = false,
  focusableDisabled = false,
  className,
}: SegmentedControlProps<T>) {
  return (
    <div role="group" aria-label={label} className={cx(SHELL, fullWidth && 'flex w-full flex-wrap gap-y-1 [@media(min-width:40rem)]:inline-flex [@media(min-width:40rem)]:w-auto [@media(min-width:40rem)]:flex-nowrap', className)}>
      {options.map((option) => {
        const selected = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            disabled={option.disabled && !focusableDisabled}
            aria-disabled={option.disabled && focusableDisabled ? true : undefined}
            aria-describedby={option.descriptionId}
            onClick={() => {
              if (!selected && !option.disabled) onChange(option.value)
            }}
            className={cx(
              SEGMENT,
              SIZE[size],
              fullWidth && 'flex-1 [@media(min-width:40rem)]:flex-none',
              option.mono && 'font-data tabular-nums',
              selected ? SELECTED : option.disabled && focusableDisabled ? UNAVAILABLE : RESTING,
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
