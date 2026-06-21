import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useRef } from 'react'
import { act, render, screen, fireEvent } from '@testing-library/react'
import AskAboutSelection, {
  shouldOfferAsk,
} from '@/features/filings/components/copilot/AskAboutSelection'

describe('shouldOfferAsk', () => {
  it('accepts meaningful selections and rejects trivial / huge ones', () => {
    expect(shouldOfferAsk('short')).toBe(false) // < 8 chars
    expect(shouldOfferAsk('   ')).toBe(false)
    expect(shouldOfferAsk('Revenue increased to $391.0B this fiscal year.')).toBe(true)
    expect(shouldOfferAsk('x'.repeat(5000))).toBe(false) // > 4000 chars
  })
})

function Harness({ onAsk }: { onAsk: (t: string) => void }) {
  const ref = useRef<HTMLDivElement>(null)
  return (
    <div>
      <div ref={ref} data-testid="container">
        <p>Some filing text the user might select.</p>
      </div>
      <AskAboutSelection containerRef={ref} enabled onAsk={onAsk} />
    </div>
  )
}

function mockSelection(text: string, commonAncestorContainer: Node) {
  vi.spyOn(window, 'getSelection').mockReturnValue({
    isCollapsed: false,
    rangeCount: 1,
    toString: () => text,
    getRangeAt: () => ({
      commonAncestorContainer,
      getBoundingClientRect: () => ({ top: 120, left: 60, width: 140, height: 16, bottom: 136, right: 200 }),
    }),
    removeAllRanges: vi.fn(),
  } as unknown as Selection)
}

describe('AskAboutSelection', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('offers the action for an in-container selection and calls onAsk on click', () => {
    const onAsk = vi.fn()
    render(<Harness onAsk={onAsk} />)
    const textNode = screen.getByTestId('container').querySelector('p')!.firstChild as Node
    const SELECTED = 'Some filing text the user might select.'
    mockSelection(SELECTED, textNode)

    fireEvent.mouseUp(document)
    act(() => {
      vi.runAllTimers()
    })

    fireEvent.click(screen.getByRole('button', { name: /ask about this/i }))
    expect(onAsk).toHaveBeenCalledWith(SELECTED)
  })

  it('does not offer when the selection is outside the container', () => {
    const onAsk = vi.fn()
    render(<Harness onAsk={onAsk} />)
    const outside = document.createElement('div')
    document.body.appendChild(outside)
    mockSelection('A long-enough selection but elsewhere.', outside)

    fireEvent.mouseUp(document)
    act(() => {
      vi.runAllTimers()
    })

    expect(screen.queryByRole('button', { name: /ask about this/i })).toBeNull()
    document.body.removeChild(outside)
  })
})
