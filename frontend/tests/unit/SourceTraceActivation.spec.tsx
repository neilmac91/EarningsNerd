import { useEffect } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { SourceTrace } from '@/features/filings/components/SourceTrace'
import {
  FilingViewerProvider,
  useFilingViewer,
} from '@/features/filings/components/copilot/FilingViewerContext'

/**
 * EN-01: a provenance chip's activation always reaches the source. With a viewer mounted (the filing
 * page), a fine-pointer activation requests the highlight AND asks the page to open the pane; on a
 * coarse pointer the tap opens the documented sheet, which holds the in-app jump ("Show in filing")
 * beside "Open in SEC EDGAR". The chip is recorded as the opener so the pane can return focus to it.
 */

const EVIDENCE = 'Our revenue is concentrated among a small number of large customers.'
const URL = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm#:~:text=revenue'

function RequestProbe() {
  const viewer = useFilingViewer()
  return (
    <div data-testid="probe">
      {viewer?.request ? `${viewer.request.nonce}:${viewer.request.citation.excerpt}` : 'none'}
    </div>
  )
}

type Peek = (() => HTMLElement | null) | undefined

/** Hands the provider's peekOpener to the test after each render (never mutating a prop in render). */
function OpenerProbe({ onPeek }: { onPeek: (peek: Peek) => void }) {
  const viewer = useFilingViewer()
  const peek = viewer?.peekOpener
  useEffect(() => {
    onPeek(peek)
  }, [peek, onPeek])
  return null
}

function mockPointer(coarse: boolean) {
  return vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        matches: coarse && query === '(pointer: coarse)',
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        onchange: null,
        dispatchEvent: () => false,
      }) as unknown as MediaQueryList,
  )
}

describe('SourceTrace activation with a viewer (fine pointer)', () => {
  let matchMedia: ReturnType<typeof vi.spyOn>
  beforeEach(() => {
    matchMedia = mockPointer(false)
  })
  afterEach(() => matchMedia.mockRestore())

  it('requests the highlight, asks the page to open the pane once per activation, and closes the popover', () => {
    const onRequestOpen = vi.fn()
    render(
      <FilingViewerProvider onRequestOpen={onRequestOpen}>
        <SourceTrace url={URL} verified sectionRef="Item 1A · Risk Factors" excerpt={EVIDENCE} />
        <RequestProbe />
      </FilingViewerProvider>,
    )
    const chip = screen.getByRole('button', { name: 'Source: Verified in filing' })
    fireEvent.mouseEnter(chip)
    expect(screen.getByRole('group', { name: 'Source detail' })).toBeInTheDocument()

    fireEvent.click(chip)
    expect(screen.getByTestId('probe')).toHaveTextContent(`1:${EVIDENCE}`)
    expect(onRequestOpen).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('group', { name: 'Source detail' })).toBeNull()

    // Repeated activation of the same citation works every time (a new nonce, a new open request).
    fireEvent.click(chip)
    expect(screen.getByTestId('probe')).toHaveTextContent(`2:${EVIDENCE}`)
    expect(onRequestOpen).toHaveBeenCalledTimes(2)
  })

  it('records the chip as the opener the pane returns focus to', () => {
    let peek: Peek
    render(
      <FilingViewerProvider onRequestOpen={() => {}}>
        <SourceTrace url={URL} verified sectionRef="Item 1A · Risk Factors" excerpt={EVIDENCE} />
        <OpenerProbe onPeek={(p) => (peek = p)} />
      </FilingViewerProvider>,
    )
    expect(peek?.()).toBeNull()
    const chip = screen.getByRole('button', { name: 'Source: Verified in filing' })
    fireEvent.click(chip)
    expect(peek?.()).toBe(chip)
  })

  it('opens the pane even without an excerpt (a metric falls back to its section heading)', () => {
    const onRequestOpen = vi.fn()
    render(
      <FilingViewerProvider onRequestOpen={onRequestOpen}>
        <SourceTrace url={URL} verified sectionRef="Consolidated Statements of Operations" label="Revenue · SEC XBRL" />
        <RequestProbe />
      </FilingViewerProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Source: Revenue · SEC XBRL' }))
    expect(screen.getByTestId('probe')).toHaveTextContent('1:Consolidated Statements of Operations')
    expect(onRequestOpen).toHaveBeenCalledTimes(1)
  })
})

describe('SourceTrace activation with a viewer (coarse pointer: the touch sheet)', () => {
  let matchMedia: ReturnType<typeof vi.spyOn>
  let rects: ReturnType<typeof vi.spyOn>
  beforeEach(() => {
    matchMedia = mockPointer(true)
    // jsdom lays nothing out; give elements one rect so the sheet's focus trap sees them as rendered.
    rects = vi.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue([{}] as unknown as DOMRectList)
  })
  afterEach(() => {
    matchMedia.mockRestore()
    rects.mockRestore()
  })

  function renderTouch(onRequestOpen = vi.fn()) {
    const out: { peek?: Peek } = {}
    render(
      <FilingViewerProvider onRequestOpen={onRequestOpen}>
        <SourceTrace url={URL} verified sectionRef="Item 1A · Risk Factors" excerpt={EVIDENCE} />
        <RequestProbe />
        <OpenerProbe onPeek={(p) => (out.peek = p)} />
      </FilingViewerProvider>,
    )
    return { onRequestOpen, out, chip: screen.getByRole('button', { name: 'Source: Verified in filing' }) }
  }

  it('a tap opens the Source detail sheet, never a silent jump: the sheet holds the EDGAR link and the in-app jump', () => {
    const { onRequestOpen, chip } = renderTouch()
    expect(chip).toHaveAttribute('aria-haspopup', 'dialog')
    fireEvent.click(chip)

    const sheet = screen.getByRole('dialog', { name: 'Source detail' })
    expect(screen.getByTestId('probe')).toHaveTextContent('none')
    expect(onRequestOpen).not.toHaveBeenCalled()
    expect(within(sheet).getByRole('link', { name: /open in sec edgar/i })).toHaveAttribute('href', URL)
    expect(within(sheet).getByRole('button', { name: 'Show in filing' })).toBeInTheDocument()
    // The trap moved focus into the sheet, onto its first real stop (the scrim is no tab stop).
    expect(document.activeElement).toBe(within(sheet).getByRole('button', { name: 'Close source detail' }))
    const scrim = sheet.querySelector('button[aria-hidden="true"]')
    expect(scrim).toHaveAttribute('tabindex', '-1')
  })

  it('"Show in filing" closes the sheet, requests the highlight once with the chip as opener, and asks the page to open the pane', () => {
    const { onRequestOpen, out, chip } = renderTouch()
    fireEvent.click(chip)
    fireEvent.click(screen.getByRole('button', { name: 'Show in filing' }))

    expect(screen.queryByRole('dialog', { name: 'Source detail' })).toBeNull()
    expect(screen.getByTestId('probe')).toHaveTextContent(`1:${EVIDENCE}`)
    expect(onRequestOpen).toHaveBeenCalledTimes(1)
    expect(out.peek?.()).toBe(chip)
    // The sheet's trap handed focus back to the chip, the opener that outlives the sheet.
    expect(document.activeElement).toBe(chip)
  })

  it('without a highlight target the sheet offers only the EDGAR link', () => {
    render(
      <FilingViewerProvider onRequestOpen={() => {}}>
        <SourceTrace url={URL} verified sectionRef="1A" />
      </FilingViewerProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Source: Verified in filing' }))
    const sheet = screen.getByRole('dialog', { name: 'Source detail' })
    expect(within(sheet).getByRole('link', { name: /open in sec edgar/i })).toHaveAttribute('href', URL)
    expect(within(sheet).queryByRole('button', { name: 'Show in filing' })).toBeNull()
  })

  it('Escape closes the sheet and returns focus to the chip', () => {
    const { chip } = renderTouch()
    fireEvent.click(chip)
    const sheet = screen.getByRole('dialog', { name: 'Source detail' })
    fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Escape' })
    expect(sheet).not.toBeInTheDocument()
    expect(document.activeElement).toBe(chip)
  })

  it('Tab cycles inside the open sheet (its focus is contained)', () => {
    const { chip } = renderTouch()
    fireEvent.click(chip)
    const sheet = screen.getByRole('dialog', { name: 'Source detail' })
    const last = within(sheet).getByRole('link', { name: /open in sec edgar/i })
    last.focus()
    fireEvent.keyDown(last, { key: 'Tab' })
    expect(document.activeElement).toBe(within(sheet).getByRole('button', { name: 'Close source detail' }))
    fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(last)
  })

  it('the close button returns focus to the chip too', () => {
    const { chip } = renderTouch()
    fireEvent.click(chip)
    fireEvent.click(screen.getByRole('button', { name: 'Close source detail' }))
    expect(screen.queryByRole('dialog', { name: 'Source detail' })).toBeNull()
    expect(document.activeElement).toBe(chip)
  })
})
