import { render } from '@testing-library/react'
import { createElement } from 'react'
import { describe, expect, it } from 'vitest'

import RevenueBars from '@/features/marketing/components/RevenueBars'

/**
 * The landing page's revenue bars draw their own rules, one per $100B and the baseline, in plain DOM. They are the
 * homepage's gridlines, so they take the product's gridline ink, chart.grid, in both themes (chief design on #1771): in
 * the retired hairline the dark rules sat under APCA's low clip on their card. (This file also held the Recharts kit's
 * inks, components/ui/Chart.tsx's chartTheme and seriesColor, to their tokens until the kit left with Recharts, E195
 * (D); the trend charts' engine holds its own in tests/unit/chart-theme.spec.ts.)
 */
describe("the landing page's revenue bars rule their ticks in chart.grid", () => {
  it('in both themes, every rule', () => {
    const points = [{ period: 'FY2024', value: 391e9 }, { period: 'FY2025', value: 416e9 }]
    const { container } = render(createElement(RevenueBars, { points }))
    const rules = [...container.querySelectorAll('span.border-t')]
    expect(rules).toHaveLength(7) // $0 to $600B, one per $100B: the axis tops out a full tick above $416B
    const inks = (rule: Element) => [...rule.classList].filter((name) => /^(dark:)?border-(?!t$)/.test(name))
    expect(rules.map(inks)).toEqual(rules.map(() => ['border-chart-grid-light', 'dark:border-chart-grid-dark']))
  })
})
