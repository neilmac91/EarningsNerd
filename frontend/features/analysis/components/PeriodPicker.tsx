'use client'

import { useMemo } from 'react'
import { cx } from '@/components/ui'
import type { AnalysisCoverage, AnalysisMode } from '@/features/analysis/api/analysis-api'

export interface PeriodRange {
  start: string
  end: string
}

interface PeriodChip {
  key: string
  label: string
  disabled: boolean
  derived: boolean
}

/**
 * The available periods for a mode as ordered chips (oldest → newest). Selection is a contiguous
 * range: clicking a chip moves the nearer endpoint (single-anchor UX — no drag needed), clamped
 * to the mode's period cap. Years without a top line + net income are disabled; fully-derived Q4
 * columns carry a † badge.
 */
export function chipsFor(coverage: AnalysisCoverage, mode: AnalysisMode): PeriodChip[] {
  if (mode === 'annual') {
    return coverage.annual.map((p) => ({
      key: p.key,
      label: p.key,
      disabled: !p.has_core,
      derived: false,
    }))
  }
  return coverage.quarterly.map((p) => ({
    key: p.key,
    label: `${p.fiscal_period} ’${String(p.fiscal_year).slice(2)}`,
    disabled: false,
    derived: p.derived,
  }))
}

/** Default range: the newest `cap` periods (what a fresh visit should analyze). */
export function defaultRange(coverage: AnalysisCoverage, mode: AnalysisMode): PeriodRange | null {
  const chips = chipsFor(coverage, mode).filter((c) => !c.disabled)
  if (chips.length === 0) return null
  const cap = mode === 'annual' ? coverage.limits.annual : coverage.limits.quarterly
  const window = chips.slice(-cap)
  return { start: window[0].key, end: window[window.length - 1].key }
}

/** Move the nearer endpoint of [start, end] to `clicked`, clamped to `cap` periods. */
export function nextRange(
  keys: string[],
  range: PeriodRange,
  clicked: string,
  cap: number
): PeriodRange {
  const index = keys.indexOf(clicked)
  const startIndex = keys.indexOf(range.start)
  const endIndex = keys.indexOf(range.end)
  if (index === -1 || startIndex === -1 || endIndex === -1) return range

  let nextStart = startIndex
  let nextEnd = endIndex
  if (index < startIndex) nextStart = index
  else if (index > endIndex) nextEnd = index
  else if (Math.abs(index - startIndex) <= Math.abs(endIndex - index)) nextStart = index
  else nextEnd = index

  // Clamp to the cap by pulling the OTHER endpoint toward the one just moved.
  if (nextEnd - nextStart + 1 > cap) {
    if (nextStart !== startIndex) nextEnd = nextStart + cap - 1
    else nextStart = nextEnd - cap + 1
  }
  return { start: keys[nextStart], end: keys[nextEnd] }
}

export default function PeriodPicker({
  coverage,
  mode,
  range,
  onModeChange,
  onRangeChange,
}: {
  coverage: AnalysisCoverage
  mode: AnalysisMode
  range: PeriodRange | null
  onModeChange: (mode: AnalysisMode) => void
  onRangeChange: (range: PeriodRange) => void
}) {
  const chips = useMemo(() => chipsFor(coverage, mode), [coverage, mode])
  const keys = useMemo(() => chips.map((c) => c.key), [chips])
  const cap = mode === 'annual' ? coverage.limits.annual : coverage.limits.quarterly
  const startIndex = range ? keys.indexOf(range.start) : -1
  const endIndex = range ? keys.indexOf(range.end) : -1
  const inRange = (index: number) =>
    startIndex !== -1 && endIndex !== -1 && index >= startIndex && index <= endIndex
  const selectedCount = startIndex !== -1 && endIndex !== -1 ? endIndex - startIndex + 1 : 0

  const hasQuarters = coverage.quarterly.length > 0

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {/* Mode toggle — segmented control. */}
        <div
          role="group"
          aria-label="Analysis mode"
          className="inline-flex rounded-xl border border-border-light bg-background-light p-0.5 dark:border-white/10 dark:bg-white/5"
        >
          {(['annual', 'quarterly'] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => onModeChange(m)}
              disabled={m === 'quarterly' && !hasQuarters}
              aria-pressed={mode === m}
              className={cx(
                'rounded-[10px] px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40',
                mode === m
                  ? 'bg-brand text-white dark:bg-brand-dark dark:text-background-dark'
                  : 'text-text-secondary-light hover:bg-brand-weak dark:text-text-secondary-dark dark:hover:bg-white/10'
              )}
            >
              {m === 'annual' ? 'Annual' : 'Quarterly'}
            </button>
          ))}
        </div>
        <span className="tnum font-data text-xs text-text-tertiary-light dark:text-text-secondary-dark">
          {selectedCount > 0 ? `${selectedCount} of ${cap} periods` : `up to ${cap} periods`}
        </span>
      </div>

      {chips.length === 0 ? (
        <p className="text-sm text-text-tertiary-light dark:text-text-secondary-dark">
          No {mode} periods available for this company yet.
        </p>
      ) : (
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Select period range">
          {chips.map((chip, index) => (
            <button
              key={chip.key}
              type="button"
              disabled={chip.disabled}
              onClick={() => range && onRangeChange(nextRange(keys, range, chip.key, cap))}
              aria-pressed={inRange(index)}
              title={
                chip.disabled
                  ? 'Not enough reported data in this period'
                  : chip.derived
                    ? 'Computed Q4 (full year minus the three reported quarters)'
                    : undefined
              }
              className={cx(
                'tnum font-data rounded-full px-2.5 py-1 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40',
                inRange(index)
                  ? 'bg-brand text-white dark:bg-brand-dark dark:text-background-dark'
                  : 'bg-background-light text-text-secondary-light hover:bg-brand-weak dark:bg-white/5 dark:text-text-secondary-dark dark:hover:bg-white/10'
              )}
            >
              {chip.label}
              {chip.derived ? '†' : ''}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
