import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { SourceTrace } from '@/features/filings/components/SourceTrace'
import CitationChip from '@/features/filings/components/copilot/CitationChip'
import { FilingViewerProvider } from '@/features/filings/components/copilot/FilingViewerContext'
import type { CopilotCitation } from '@/features/filings/api/copilot-api'

/**
 * EN-01: the evidence popovers are reachable by keyboard. Both chips render their popover through a
 * portal at the end of <body>, so the page's own tab order never reached the link: Tab left the chip
 * for the next chip and the popover closed on blur. useEvidencePopoverKeys hands the keys over:
 * Tab from the chip → the popover's action; Tab past it → the page resumes after the chip; Shift+Tab
 * → back to the chip; Escape → closed and the chip refocused, in window capture so the pane beneath
 * stays open (SourceTrace's own listener, CitationChip's through the hook's `ownsEscape`).
 */

const EVIDENCE = 'Our revenue is concentrated among a small number of large customers.'
const URL = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm'

const citation: CopilotCitation = {
  n: 1,
  excerpt: 'Revenue increased to $391.0B this year.',
  section_ref: 'Item 7 — MD&A',
  verified: true,
  fragment_url: 'https://www.sec.gov/x#:~:text=Revenue',
}

function finePointer() {
  return vi.spyOn(window, 'matchMedia').mockImplementation(
    (query: string) =>
      ({
        matches: false,
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

function Page({ chip }: { chip: React.ReactNode }) {
  return (
    <>
      <button type="button">before</button>
      <FilingViewerProvider>{chip}</FilingViewerProvider>
      <button type="button">after</button>
    </>
  )
}

/**
 * Stand-ins for the layers beneath a chip on the filing page: the copilot sheet's trap (a
 * document-level capture listener that closes on Escape) and the rail's window listener (bubble
 * phase, skips a prevented Escape).
 */
function listenBeneath() {
  const trap = vi.fn()
  const rail = vi.fn()
  const onTrap = (e: KeyboardEvent) => {
    if (e.key === 'Escape') trap()
  }
  const onRail = (e: KeyboardEvent) => {
    if (e.key === 'Escape' && !e.defaultPrevented) rail()
  }
  document.addEventListener('keydown', onTrap, true)
  window.addEventListener('keydown', onRail)
  return {
    trap,
    rail,
    remove: () => {
      document.removeEventListener('keydown', onTrap, true)
      window.removeEventListener('keydown', onRail)
    },
  }
}

const sourceChip = <SourceTrace url={URL} verified sectionRef="Item 1A · Risk Factors" excerpt={EVIDENCE} />
const citationChip = <CitationChip citation={citation} />

let matchMedia: ReturnType<typeof vi.spyOn>
let rects: ReturnType<typeof vi.spyOn>
beforeEach(() => {
  matchMedia = finePointer()
  // jsdom lays nothing out: give every element one rect so the page's tab order "renders".
  rects = vi.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue([{}] as unknown as DOMRectList)
})
afterEach(() => {
  matchMedia.mockRestore()
  rects.mockRestore()
})

describe.each([
  {
    name: 'SourceTrace',
    chip: sourceChip,
    trigger: () => screen.getByRole('button', { name: 'Source: Verified in filing' }),
    popover: () => screen.queryByRole('group', { name: 'Source detail' }),
    action: () => screen.getByRole('link', { name: /open in sec edgar/i }),
  },
  {
    name: 'CitationChip',
    chip: citationChip,
    trigger: () => screen.getByRole('button', { name: /citation 1: item 7 — md&a/i }),
    popover: () => screen.queryByRole('group', { name: /citation 1: item 7 — md&a/i }),
    action: () => screen.getByRole('link', { name: /open original/i }),
  },
])('$name popover keyboard contract', ({ chip, trigger, popover, action }) => {
  it('Tab from the focused chip reaches the popover action and keeps the popover open', () => {
    render(<Page chip={chip} />)
    const t = trigger()
    act(() => t.focus())
    expect(popover()).toBeInTheDocument()
    const prevented = !fireEvent.keyDown(t, { key: 'Tab' })
    expect(prevented).toBe(true)
    expect(document.activeElement).toBe(action())
    expect(popover()).toBeInTheDocument()
  })

  it('Tab from the action closes the popover and resumes the page after the chip', () => {
    render(<Page chip={chip} />)
    const t = trigger()
    act(() => t.focus())
    fireEvent.keyDown(t, { key: 'Tab' })
    const link = action()
    fireEvent.keyDown(link, { key: 'Tab' })
    expect(popover()).toBeNull()
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'after' }))
  })

  it('Shift+Tab from the action returns to the chip with the popover still open', () => {
    render(<Page chip={chip} />)
    const t = trigger()
    act(() => t.focus())
    fireEvent.keyDown(t, { key: 'Tab' })
    expect(document.activeElement).toBe(action())
    fireEvent.keyDown(action(), { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(t)
    expect(popover()).toBeInTheDocument()
  })

  it('Escape with focus on the action closes the popover and refocuses the chip', () => {
    const beneath = listenBeneath()
    try {
      render(<Page chip={chip} />)
      const t = trigger()
      act(() => t.focus())
      fireEvent.keyDown(t, { key: 'Tab' })
      expect(document.activeElement).toBe(action())
      fireEvent.keyDown(action(), { key: 'Escape' })
      expect(popover()).toBeNull()
      expect(document.activeElement).toBe(t)
      // The copilot sheet's trap and the rail's listener never saw it: the pane stays open.
      expect(beneath.trap).not.toHaveBeenCalled()
      expect(beneath.rail).not.toHaveBeenCalled()
    } finally {
      beneath.remove()
    }
  })

  it('Escape with focus on the chip closes only the popover; the next Escape reaches the pane beneath', () => {
    const beneath = listenBeneath()
    try {
      render(<Page chip={chip} />)
      const t = trigger()
      act(() => t.focus())
      expect(popover()).toBeInTheDocument()
      fireEvent.keyDown(t, { key: 'Escape' })
      expect(popover()).toBeNull()
      expect(document.activeElement).toBe(t)
      expect(beneath.trap).not.toHaveBeenCalled()
      expect(beneath.rail).not.toHaveBeenCalled()
      // One layer per press: with the popover closed, Escape belongs to the pane again.
      fireEvent.keyDown(t, { key: 'Escape' })
      expect(beneath.trap).toHaveBeenCalledTimes(1)
      expect(beneath.rail).toHaveBeenCalledTimes(1)
    } finally {
      beneath.remove()
    }
  })

  it('leaves Escape to a ui/Modal raised above an open popover', () => {
    render(
      <>
        <Page chip={chip} />
        <div data-ui-modal="true">
          <button type="button">modal action</button>
        </div>
      </>,
    )
    const t = trigger()
    fireEvent.mouseEnter(t)
    expect(popover()).toBeInTheDocument()
    const inModal = screen.getByRole('button', { name: 'modal action' })
    act(() => inModal.focus())
    // Not prevented by the popover: the modal's own listener owns this key.
    expect(fireEvent.keyDown(inModal, { key: 'Escape' })).toBe(true)
    expect(popover()).toBeInTheDocument()
  })

  it('a scroll re-anchors a keyboard-owned popover and closes a hover one', () => {
    render(<Page chip={chip} />)
    const t = trigger()
    // Focusing a chip below the fold scrolls it into view; that scroll must not close what focus opened.
    act(() => t.focus())
    expect(popover()).toBeInTheDocument()
    fireEvent.scroll(window)
    expect(popover()).toBeInTheDocument()
    // Nor while focus sits on the popover's own action.
    fireEvent.keyDown(t, { key: 'Tab' })
    expect(document.activeElement).toBe(action())
    fireEvent.scroll(window)
    expect(popover()).toBeInTheDocument()
    expect(document.activeElement).toBe(action())
    // A hover popover (focus elsewhere) still closes, as before.
    act(() => t.blur())
    act(() => screen.getByRole('button', { name: 'after' }).focus())
    fireEvent.mouseEnter(t)
    expect(popover()).toBeInTheDocument()
    fireEvent.scroll(window)
    expect(popover()).toBeNull()
  })

  it('a pointer still opens the popover on hover and closes it after leaving', () => {
    vi.useFakeTimers()
    try {
      render(<Page chip={chip} />)
      const t = trigger()
      fireEvent.mouseEnter(t)
      expect(popover()).toBeInTheDocument()
      fireEvent.mouseLeave(t)
      act(() => {
        vi.advanceTimersByTime(200)
      })
      expect(popover()).toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })
})

describe('SourceTrace without a viewer', () => {
  it('leaves Tab alone when the chip is itself the EDGAR anchor (no second stop for the same link)', () => {
    render(
      <>
        <SourceTrace url={URL} verified sectionRef="Item 1A · Risk Factors" excerpt={EVIDENCE} />
        <button type="button">after</button>
      </>,
    )
    const link = screen.getByRole('link', { name: 'Source: Verified in filing' })
    act(() => link.focus())
    expect(screen.getByRole('group', { name: 'Source detail' })).toBeInTheDocument()
    expect(fireEvent.keyDown(link, { key: 'Tab' })).toBe(true)
    expect(document.activeElement).toBe(link)
  })
})

describe('CitationChip without a viewer', () => {
  it('leaves Tab alone when the popover has no action (the chip itself is the EDGAR link)', () => {
    render(
      <>
        <CitationChip citation={citation} />
        <button type="button">after</button>
      </>,
    )
    const link = screen.getByRole('link', { name: /citation 1/i })
    act(() => link.focus())
    expect(screen.getByRole('group', { name: /citation 1/i })).toBeInTheDocument()
    // Not prevented: the browser's own Tab proceeds as usual.
    expect(fireEvent.keyDown(link, { key: 'Tab' })).toBe(true)
    expect(document.activeElement).toBe(link)
  })
})
