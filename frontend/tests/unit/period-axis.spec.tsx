import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'

import {
  ANNUAL_AXIS_HEIGHT,
  PeriodAxisTick,
  QUARTERLY_AXIS_HEIGHT,
  annualTickLabel,
  periodAxisLabel,
  quarterlyTickLines,
} from '@/features/analysis/lib/periodAxis'
import { buildMarkSvg, MARK_STAMP } from '@/features/analysis/lib/chartExport'

describe('annualTickLabel', () => {
  it("renders bare two-digit years — '16, '17… — so every label centers on its bar", () => {
    // No FY prefix on any tick (the wider "FY '16" shifted off its bar — AAPL field test);
    // the axis caption underneath names the unit instead.
    expect(annualTickLabel('FY2016')).toBe("'16")
    expect(annualTickLabel('FY2017')).toBe("'17")
    expect(annualTickLabel('FY2025')).toBe("'25")
  })

  it('passes unrecognized keys through untouched', () => {
    expect(annualTickLabel('2024Q3')).toBe('2024Q3')
    expect(annualTickLabel('')).toBe('')
  })
})

describe('periodAxisLabel (the axis caption)', () => {
  it('names the tick unit per mode, styled from the chart theme tokens', () => {
    expect(periodAxisLabel('annual', false).value).toBe('Financial Year')
    expect(periodAxisLabel('quarterly', false).value).toBe('Fiscal Quarter')
    expect(periodAxisLabel('annual', false).style.fontSize).toBe(11)
    // Theme ink follows dark mode (chartTheme label values).
    expect(periodAxisLabel('annual', true).style.fill).not.toBe(periodAxisLabel('annual', false).style.fill)
  })

  it('axis heights reserve room for the caption below the tick row', () => {
    expect(ANNUAL_AXIS_HEIGHT).toBeGreaterThan(30) // Recharts default is ticks-only
    expect(QUARTERLY_AXIS_HEIGHT).toBeGreaterThan(ANNUAL_AXIS_HEIGHT) // two-line ticks stack taller
  })
})

describe('quarterlyTickLines', () => {
  it("stacks quarter over year in Q2'23 reading order", () => {
    expect(quarterlyTickLines('2023Q2')).toEqual(['Q2', "'23"])
    expect(quarterlyTickLines('2026Q1')).toEqual(['Q1', "'26"])
  })

  it('returns null for unrecognized keys', () => {
    expect(quarterlyTickLines('FY2023')).toBeNull()
  })
})

// The tick renders inside an <svg> like Recharts mounts it.
const renderTick = (element: React.ReactElement) => render(<svg>{element}</svg>)

describe('PeriodAxisTick', () => {
  it('renders a single compact annual label', () => {
    const { container } = renderTick(
      <PeriodAxisTick mode="annual" dark={false} x={50} y={10} payload={{ value: 'FY2016' }} />
    )
    const text = container.querySelector('text')
    expect(text?.textContent).toBe("'16")
    expect(text?.getAttribute('font-size')).toBe('11')
  })

  it('renders the two-line quarterly tick (quarter over year)', () => {
    const { container } = renderTick(
      <PeriodAxisTick mode="quarterly" dark={false} x={50} y={10} payload={{ value: '2023Q2' }} />
    )
    const spans = container.querySelectorAll('tspan')
    expect(spans).toHaveLength(2)
    expect(spans[0].textContent).toBe('Q2')
    expect(spans[1].textContent).toBe("'23")
    // The two-line stack is why quarterly axes reserve extra height.
    expect(QUARTERLY_AXIS_HEIGHT).toBeGreaterThan(30)
  })

  it('falls back to a single-line label for a quarterly key it cannot parse', () => {
    const { container } = renderTick(
      <PeriodAxisTick mode="quarterly" dark={false} x={50} y={10} payload={{ value: 'TTM' }} />
    )
    expect(container.querySelector('text')?.textContent).toBe('TTM')
    expect(container.querySelectorAll('tspan')).toHaveLength(0)
  })
})

describe('PNG watermark building blocks', () => {
  it('buildMarkSvg inlines the EN monogram with the requested fill', () => {
    const svg = buildMarkSvg('#3C6650')
    expect(svg).toContain('viewBox="0 0 94.6 73.2"')
    expect(svg.match(/fill="#3C6650"/g)).toHaveLength(3) // all three mark paths
    expect(svg).toContain('M2.8 28L26.2 28') // the E path
  })

  it('the brand footer strip fits its mark (never an in-plot overlay)', () => {
    // Footer, not overlay: live acceptance showed an overlaid mark colliding with axis text.
    expect(MARK_STAMP.markHeight).toBeLessThan(MARK_STAMP.stripHeight)
    expect(MARK_STAMP.stripHeight).toBeLessThanOrEqual(40) // slim — the chart stays the subject
  })

  it('theme fills stay on the sage brand ramp', () => {
    expect(MARK_STAMP.fillLight).toBe('#3C6650')
    expect(MARK_STAMP.fillDark).toBe('#7FB295')
    expect(MARK_STAMP.alpha).toBeLessThanOrEqual(1)
  })
})
