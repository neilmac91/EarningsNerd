import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ChartErrorBoundary } from '@/components/ChartErrorBoundary'

// The fallback names what the boundary wraps (chrome/F10): one chart on the filing page, the
// grid of chart panels on Multi-Period Analysis when TrendCharts passes noun="charts".

function Thrower(): never {
  throw new Error('chart failed to draw')
}

const ONE = 'This chart could not be drawn.'
const MANY = 'These charts could not be drawn.'

describe('ChartErrorBoundary fallback copy', () => {
  let consoleError: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    // React and componentDidCatch log the caught error; keep the test output quiet.
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleError.mockRestore()
  })

  it('names one chart by default', () => {
    render(
      <ChartErrorBoundary>
        <Thrower />
      </ChartErrorBoundary>,
    )
    expect(screen.getByText(ONE)).toBeTruthy()
    expect(screen.queryByText(MANY)).toBeNull()
  })

  it('names the grid when noun="charts"', () => {
    render(
      <ChartErrorBoundary noun="charts">
        <Thrower />
      </ChartErrorBoundary>,
    )
    expect(screen.getByText(MANY)).toBeTruthy()
    expect(screen.queryByText(ONE)).toBeNull()
  })
})
