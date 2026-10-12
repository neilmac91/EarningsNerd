import { useRef } from 'react'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useOverflowRegion } from '@/hooks/useOverflowRegion'

let width: number
let contentWidth: number
const observers: { resize: () => void; observe: ReturnType<typeof vi.fn>; unobserve: ReturnType<typeof vi.fn>; disconnect: ReturnType<typeof vi.fn> }[] = []

beforeEach(() => {
  width = 320
  contentWidth = 320
  observers.length = 0
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(() => width)
  vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(() => contentWidth)
  vi.stubGlobal('ResizeObserver', class {
    observe = vi.fn()
    unobserve = vi.fn()
    disconnect = vi.fn()
    constructor(public resize: () => void) { observers.push(this) }
  })
})

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

function Viewport({ enabled = true, child = 'first', label = 'Report periods' }: { enabled?: boolean; child?: string; label?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const { overflowing, regionProps } = useOverflowRegion(ref, { label, describedBy: 'scroll-hint', enabled })
  if (!enabled) return null
  return <>
    {overflowing && <p id="scroll-hint">Scroll to read all periods.</p>}
    <div ref={ref} data-testid="viewport" {...regionProps}><div key={child}>{child}</div></div>
  </>
}

describe('useOverflowRegion', () => {
  it('adds and removes the named keyboard stop as the box or content resizes, including label updates', () => {
    const { rerender, unmount } = render(<Viewport />)
    const box = screen.getByTestId('viewport')
    expect(box).not.toHaveAttribute('role')
    expect(box).not.toHaveAttribute('tabindex')
    expect(box).not.toHaveAttribute('aria-label')
    expect(box).not.toHaveAttribute('aria-describedby')
    expect(observers[0].observe.mock.calls.map(([target]) => target)).toEqual([box, box.firstElementChild])
    contentWidth = width + 1
    act(() => observers[0].resize())
    expect(box).not.toHaveAttribute('role')
    contentWidth = 700
    act(() => observers[0].resize())
    expect(screen.getByRole('region', { name: 'Report periods' })).toBe(box)
    expect(box).toHaveAttribute('tabindex', '0')
    expect(box).toHaveAccessibleDescription('Scroll to read all periods.')
    rerender(<Viewport label="Updated report periods" />)
    expect(box).toHaveAccessibleName('Updated report periods')
    expect(observers).toHaveLength(1)
    width = 800
    act(() => observers[0].resize())
    expect(box).not.toHaveAttribute('role')
    expect(box).not.toHaveAttribute('tabindex')
    expect(box).not.toHaveAttribute('aria-label')
    expect(box).not.toHaveAttribute('aria-describedby')
    expect(screen.queryByText('Scroll to read all periods.')).not.toBeInTheDocument()
    unmount()
    expect(observers[0].disconnect).toHaveBeenCalledOnce()
  })

  it('rebinds content observation when a rendered child is replaced', async () => {
    const { rerender } = render(<Viewport />)
    const first = screen.getByText('first')
    contentWidth = 700
    await act(async () => { rerender(<Viewport child="replacement" />) })
    expect(observers[0].unobserve).toHaveBeenCalledWith(first)
    expect(observers[0].observe).toHaveBeenCalledWith(screen.getByText('replacement'))
    expect(screen.getByRole('region')).toHaveAttribute('tabindex', '0')
  })

  it('measures a conditionally mounted box and clears the stale state when disabled', () => {
    const { rerender } = render(<Viewport enabled={false} />)
    expect(observers).toHaveLength(0)
    contentWidth = 700
    rerender(<Viewport />)
    expect(screen.getByRole('region')).toHaveAttribute('tabindex', '0')
    rerender(<Viewport enabled={false} />)
    expect(observers[0].disconnect).toHaveBeenCalledOnce()
    contentWidth = 320
    rerender(<Viewport />)
    expect(screen.getByTestId('viewport')).not.toHaveAttribute('role')
  })

  it('measures initially and on window resize when ResizeObserver is unavailable', () => {
    vi.stubGlobal('ResizeObserver', undefined)
    contentWidth = 700
    render(<Viewport />)
    expect(screen.getByRole('region')).toHaveAttribute('tabindex', '0')
    width = 800
    fireEvent(window, new Event('resize'))
    expect(screen.getByTestId('viewport')).not.toHaveAttribute('role')
  })
})
