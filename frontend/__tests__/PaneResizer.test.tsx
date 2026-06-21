import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import PaneResizer from '@/features/filings/components/copilot/PaneResizer'

describe('PaneResizer', () => {
  it('exposes window-splitter ARIA', () => {
    render(<PaneResizer width={420} min={360} max={640} onResize={() => {}} />)
    const sep = screen.getByRole('separator', { name: /resize copilot/i })
    expect(sep).toHaveAttribute('aria-orientation', 'vertical')
    expect(sep).toHaveAttribute('aria-valuemin', '360')
    expect(sep).toHaveAttribute('aria-valuemax', '640')
    expect(sep).toHaveAttribute('aria-valuenow', '420')
    expect(sep).toHaveAttribute('tabindex', '0')
  })

  it('nudges width with arrows and jumps to the bounds, clamping', () => {
    const onResize = vi.fn()
    render(<PaneResizer width={362} min={360} max={640} onResize={onResize} />)
    const sep = screen.getByRole('separator')

    fireEvent.keyDown(sep, { key: 'ArrowLeft' }) // divider left → wider: 362 + 24
    expect(onResize).toHaveBeenLastCalledWith(386)

    fireEvent.keyDown(sep, { key: 'ArrowRight' }) // narrower: 362 - 24 = 338 → clamp to min 360
    expect(onResize).toHaveBeenLastCalledWith(360)

    fireEvent.keyDown(sep, { key: 'Home' })
    expect(onResize).toHaveBeenLastCalledWith(640)

    fireEvent.keyDown(sep, { key: 'End' })
    expect(onResize).toHaveBeenLastCalledWith(360)
  })
})
