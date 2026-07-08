import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'

import { AxisSeriesTag, chartTheme, seriesColor } from '@/components/ui'

// Recharts injects this (the right-axis band) into the `label` element at runtime.
const VIEWBOX = { x: 400, y: 24, width: 64, height: 200 }

function renderTag(props: React.ComponentProps<typeof AxisSeriesTag>) {
  return render(
    <svg>
      <AxisSeriesTag {...props} />
    </svg>
  )
}

describe('AxisSeriesTag', () => {
  it('draws a series-color swatch but the NAME in neutral ink (series color is graphic-only)', () => {
    const color = seriesColor(1) // honey — 3.0:1 on cream, fails AA as text
    const { container } = renderTag({ color, label: 'Equity', dark: false, viewBox: VIEWBOX })
    const rect = container.querySelector('rect')
    const text = container.querySelector('text')
    expect(rect?.getAttribute('fill')).toBe(color) // swatch carries the hue (graphic ≥3:1)
    expect(text?.textContent).toBe('Equity')
    expect(text?.getAttribute('fill')).toBe(chartTheme(false).label) // neutral AA ink (#6B7280)
    expect(text?.getAttribute('fill')).not.toBe(color) // the name is NEVER the sub-4.5:1 series hue
  })

  it('flips only the neutral ink for dark mode (swatch hue is theme-independent)', () => {
    const color = seriesColor(2)
    const { container } = renderTag({ color, label: 'Net income', dark: true, viewBox: VIEWBOX })
    expect(container.querySelector('text')?.getAttribute('fill')).toBe(chartTheme(true).label)
    expect(container.querySelector('rect')?.getAttribute('fill')).toBe(color)
  })

  it('right-aligns the name to the axis band edge', () => {
    const { container } = renderTag({ color: '#000', label: 'Equity', dark: false, viewBox: VIEWBOX })
    const text = container.querySelector('text')
    expect(text?.getAttribute('text-anchor')).toBe('end')
    expect(Number(text?.getAttribute('x'))).toBe(VIEWBOX.x + VIEWBOX.width)
  })

  it('renders nothing until Recharts injects a viewBox', () => {
    const { container } = renderTag({ color: '#000', label: 'Equity', dark: false })
    expect(container.querySelector('g')).toBeNull()
  })
})
