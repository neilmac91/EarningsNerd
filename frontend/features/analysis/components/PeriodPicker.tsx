'use client'

import { useId, useMemo, useState } from 'react'
import { Button, SegmentedControl, inputClasses } from '@/components/ui'
import type { AnalysisCoverage, AnalysisMode } from '@/features/analysis/api/analysis-api'
import { formatAnalysisPeriod } from '@/features/analysis/lib/periodLabels'

export interface PeriodRange {
  start: string
  end: string
}

export interface PeriodOption {
  key: string
  label: string
  disabled: boolean
  derived: boolean
}

/** All available period labels, oldest first; unavailable years stay visible in the selects. */
export function optionsFor(coverage: AnalysisCoverage, mode: AnalysisMode): PeriodOption[] {
  return mode === 'annual'
    ? coverage.annual.map((period) => ({ key: period.key, label: formatAnalysisPeriod(period.key), disabled: !period.has_core, derived: false }))
    : coverage.quarterly.map((period) => ({ key: period.key, label: formatAnalysisPeriod(period.key), disabled: false, derived: period.derived }))
}

/** Newest bounded range. Disabled years cannot become endpoints or extend the period cap. */
export function latestRange(options: PeriodOption[], cap: number): PeriodRange | null {
  const end = options.findLastIndex((option) => !option.disabled)
  if (end < 0 || cap < 1) return null
  const start = options.findIndex((option, index) => index >= Math.max(0, end - cap + 1) && !option.disabled)
  return { start: options[start].key, end: options[end].key }
}

export function defaultRange(coverage: AnalysisCoverage, mode: AnalysisMode): PeriodRange | null {
  return latestRange(optionsFor(coverage, mode), coverage.limits[mode])
}

/** Keep the edited endpoint and pull the other into a valid, ordered, capped range. */
export function nextRange(
  options: PeriodOption[],
  range: PeriodRange | null,
  endpoint: keyof PeriodRange,
  key: string,
  cap: number,
): PeriodRange | null {
  const moved = options.findIndex((option) => option.key === key && !option.disabled)
  if (moved < 0 || cap < 1) return range
  let start = range ? options.findIndex((option) => option.key === range.start && !option.disabled) : moved
  let end = range ? options.findIndex((option) => option.key === range.end && !option.disabled) : moved
  if (endpoint === 'start') {
    start = moved
    end = Math.min(Math.max(start, end), start + cap - 1)
    while (end > start && options[end].disabled) end--
  } else {
    end = moved
    start = Math.max(Math.min(start < 0 ? end : start, end), end - cap + 1)
    while (start < end && options[start].disabled) start++
  }
  return { start: options[start].key, end: options[end].key }
}

export default function PeriodPicker({ coverage, mode, range, onModeChange, onRangeChange }: {
  coverage: AnalysisCoverage
  mode: AnalysisMode
  range: PeriodRange | null
  onModeChange: (mode: AnalysisMode) => void
  onRangeChange: (range: PeriodRange) => void
}) {
  const id = useId()
  const [announcement, setAnnouncement] = useState<{ key: string; text: string } | null>(null)
  const options = useMemo(() => optionsFor(coverage, mode), [coverage, mode])
  const cap = coverage.limits[mode]
  const selected = range ? options.filter((option) => option.key >= range.start && option.key <= range.end) : []
  const derivedCount = selected.filter((option) => option.derived).length
  const noun = mode === 'quarterly' ? selected.length === 1 ? 'quarter' : 'quarters' : selected.length === 1 ? 'year' : 'years'
  const limitNoun = mode === 'quarterly' ? cap === 1 ? 'quarter' : 'quarters' : cap === 1 ? 'year' : 'years'
  const selectionKey = (selection: PeriodRange | null) => `${coverage.ticker}:${mode}:${selection?.start}:${selection?.end}`
  const unavailableModes = {
    annual: !coverage.annual.some((period) => period.has_core),
    quarterly: coverage.quarterly.length === 0,
  }
  const presets = [...new Set((mode === 'quarterly' ? [4, 8, 12] : [5, 10]).map((count) => Math.min(count, cap)))].filter((count) => count > 0)
    .map((count) => {
      const preset = latestRange(options, count)
      return { count: preset ? options.filter((option) => option.key >= preset.start && option.key <= preset.end).length : 0, range: preset }
    })
    .filter((preset, index, all) => all.findIndex((item) => item.range?.start === preset.range?.start && item.range?.end === preset.range?.end) === index)
  const updateEndpoint = (endpoint: keyof PeriodRange, key: string) => {
    const next = nextRange(options, range, endpoint, key, cap)
    if (!next) return
    const other = endpoint === 'start' ? 'end' : 'start'
    const crossed = range && (endpoint === 'start' ? key > range.end : key < range.start)
    setAnnouncement(range && next[other] !== range[other] ? {
      key: selectionKey(next),
      text: `${other === 'start' ? 'From' : 'To'} moved to ${formatAnalysisPeriod(next[other])} to keep ${crossed ? 'the range ordered' : `at most ${cap} ${limitNoun}`}.`,
    } : null)
    onRangeChange(next)
  }

  return (
    <div className="flex min-w-0 flex-col gap-3">
      <div className="flex min-w-0 flex-wrap items-end gap-3">
        <SegmentedControl<AnalysisMode>
          label="Analysis mode"
          value={mode}
          onChange={(next) => { setAnnouncement(null); onModeChange(next) }}
          size="md"
          fullWidth
          focusableDisabled
          options={[
            { value: 'annual', label: 'Annual', disabled: unavailableModes.annual, descriptionId: unavailableModes.annual ? `${id}-annual` : undefined },
            { value: 'quarterly', label: 'Quarterly', disabled: unavailableModes.quarterly, descriptionId: unavailableModes.quarterly ? `${id}-quarterly` : undefined },
          ]}
        />
        {options.length > 0 && (
          <div className="flex w-full min-w-0 flex-wrap gap-3 sm:w-auto">
            {(['start', 'end'] as const).map((endpoint) => (
              <label key={endpoint} className="flex w-full min-w-0 flex-col gap-1.5 text-sm font-medium sm:w-auto">
                {endpoint === 'start' ? 'From' : 'To'}
                <select
                  className={inputClasses({ select: true, density: 'compact', autoWidth: true, className: 'w-full min-w-0 font-data tabular-nums sm:w-auto sm:min-w-[10.5em]' })}
                  value={range?.[endpoint] ?? ''}
                  onChange={(event) => updateEndpoint(endpoint, event.target.value)}
                >
                  {!range && <option value="" disabled>Select a period</option>}
                  {options.map((option) => (
                    <option key={option.key} value={option.key} disabled={option.disabled}>
                      {option.label}{option.derived ? ' †' : ''}{option.disabled ? ' (insufficient data)' : ''}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
        )}
      </div>
      {options.some((option) => !option.disabled) && (
        <div role="group" aria-label="Recent period presets" className="flex flex-wrap gap-2">
          {presets.map(({ count, range: preset }) => (
              <Button
                key={count}
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => { if (preset) { setAnnouncement(null); onRangeChange(preset) } }}
              >
                Last {count}
              </Button>
          ))}
        </div>
      )}
      {selected.length > 0 && range && <p className="font-data text-xs tabular-nums text-text-secondary-light dark:text-text-secondary-dark">
        {formatAnalysisPeriod(range.start)} – {formatAnalysisPeriod(range.end)} · {selected.length} {noun}
      </p>}
      <p className="text-xs text-text-secondary-light dark:text-text-secondary-dark">
        {derivedCount > 0 && <>† Fourth-quarter flows are calculated from annual totals. </>}
        {mode === 'quarterly' && options.length > 0 && <>Fiscal quarters. </>}
        {options.length > 0
          ? <>Data from {formatAnalysisPeriod(options[0].key)}; up to {cap} {limitNoun} at a time.</>
          : <>No {mode} periods available for this company yet.</>}
      </p>
      {(['annual', 'quarterly'] as const).filter((candidate) => unavailableModes[candidate]).map((candidate) => (
        <p key={candidate} id={`${id}-${candidate}`} className="text-xs text-text-secondary-light dark:text-text-secondary-dark">
          {candidate === 'annual' ? 'Annual' : 'Quarterly'} data isn&apos;t available for this company.
        </p>
      ))}
      <p role="status" className="text-xs text-text-secondary-light dark:text-text-secondary-dark">
        {announcement?.key === selectionKey(range) ? announcement.text : ''}
      </p>
    </div>
  )
}
