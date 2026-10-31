import { describe, expect, it } from 'vitest'

// The trend charts' tick strings (the engine prints them with the typographic apostrophe) and the PNG's watermark.
// periodAxis.tsx, the Recharts axis that read these strings, went with today's charts (E195).
import { annualTickLabel, quarterlyTickLines } from '@/features/analysis/lib/periodLabels'
import { buildMarkSvg, MARK_STAMP } from '@/features/analysis/lib/chartExport'

describe('annualTickLabel', () => {
  it("renders bare two-digit years — '16, '17… — so every label centers on its bar", () => {
    // No FY prefix on any tick (the wider "FY '16" shifted off its bar — AAPL field test);
    // the chart's subtitle names the fiscal basis instead.
    expect(annualTickLabel('FY2016')).toBe("'16")
    expect(annualTickLabel('FY2017')).toBe("'17")
    expect(annualTickLabel('FY2025')).toBe("'25")
  })

  it('passes unrecognized keys through untouched', () => {
    expect(annualTickLabel('2024Q3')).toBe('2024Q3')
    expect(annualTickLabel('')).toBe('')
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
