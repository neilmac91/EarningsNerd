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

  it('resizes on pointer drag (pane width = distance from pointer to the right edge)', () => {
    const onResize = vi.fn()
    render(<PaneResizer width={420} min={360} max={640} onResize={onResize} />)
    const sep = screen.getByRole('separator')

    fireEvent(sep, new MouseEvent('pointerdown', { bubbles: true }))
    window.dispatchEvent(new MouseEvent('pointermove', { clientX: window.innerWidth - 500 }))
    expect(onResize).toHaveBeenLastCalledWith(500)

    window.dispatchEvent(new MouseEvent('pointerup'))
  })

  it('keeps the drag alive across a parent re-render with a new onResize identity', () => {
    // Regression guard: an unmemoized onResize used to recreate the drag handlers, whose [stop]
    // effect cleanup tore the drag down after the first move. The handlers must stay stable.
    const { rerender } = render(<PaneResizer width={420} min={360} max={640} onResize={vi.fn()} />)
    const sep = screen.getByRole('separator')

    fireEvent(sep, new MouseEvent('pointerdown', { bubbles: true }))
    expect(document.body.style.userSelect).toBe('none') // drag active

    // Simulate what FilingWorkspace does on each move: re-render with a brand-new callback identity.
    const onResize2 = vi.fn()
    rerender(<PaneResizer width={444} min={360} max={640} onResize={onResize2} />)
    expect(document.body.style.userSelect).toBe('none') // drag NOT torn down

    window.dispatchEvent(new MouseEvent('pointermove', { clientX: window.innerWidth - 520 }))
    expect(onResize2).toHaveBeenLastCalledWith(520) // latest callback receives the move

    window.dispatchEvent(new MouseEvent('pointerup'))
    expect(document.body.style.userSelect).toBe('')
  })
})
