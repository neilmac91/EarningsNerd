import { useCallback, useEffect, useState } from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen, fireEvent } from '@testing-library/react'
import FilingWorkspace from '@/features/filings/components/copilot/FilingWorkspace'
import {
  FilingViewerProvider,
  useFilingViewer,
} from '@/features/filings/components/copilot/FilingViewerContext'
import { SourceTrace } from '@/features/filings/components/SourceTrace'
import CitationChip from '@/features/filings/components/copilot/CitationChip'
import type { CopilotCitation } from '@/features/filings/api/copilot-api'

type Props = Partial<React.ComponentProps<typeof FilingWorkspace>>

function renderWorkspace(props: Props = {}, extra?: React.ReactNode) {
  const onOpenChange = props.onOpenChange ?? vi.fn()
  const utils = render(
    <FilingViewerProvider>
      <FilingWorkspace
        open
        onOpenChange={onOpenChange}
        summaryAvailable
        secUrl="https://sec.gov/x"
        copilotBody={<div data-testid="copilot">copilot</div>}
        filingBody={<div data-testid="filing">filing</div>}
        {...props}
      >
        <div data-testid="summary">summary</div>
      </FilingWorkspace>
      {extra}
    </FilingViewerProvider>,
  )
  return { onOpenChange, ...utils }
}

describe('FilingWorkspace', () => {
  beforeEach(() => window.localStorage.clear())

  it('mounts the summary and BOTH bodies, with the [Answer · Filing] tabs', () => {
    renderWorkspace()
    expect(screen.getByTestId('summary')).toBeInTheDocument()
    // Both bodies stay mounted (stream-safe); the inactive one is hidden via CSS, not unmounted.
    expect(screen.getByTestId('copilot')).toBeInTheDocument()
    expect(screen.getByTestId('filing')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /answer/i })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: /filing/i })).toHaveAttribute('aria-selected', 'false')
  })

  it('switches the active view via the tabs', () => {
    renderWorkspace()
    fireEvent.click(screen.getByRole('tab', { name: /filing/i }))
    expect(screen.getByRole('tab', { name: /filing/i })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: /answer/i })).toHaveAttribute('aria-selected', 'false')
    // "Open original" appears on the filing tab.
    expect(screen.getByRole('link', { name: /open original/i })).toHaveAttribute(
      'href',
      'https://sec.gov/x',
    )

    fireEvent.click(screen.getByRole('tab', { name: /answer/i }))
    expect(screen.getByRole('tab', { name: /answer/i })).toHaveAttribute('aria-selected', 'true')
  })

  it('flips to the filing view when a citation requests a highlight', () => {
    function Citer() {
      const v = useFilingViewer()!
      const c = {
        n: 1,
        excerpt: 'x',
        section_ref: null,
        verified: true,
        fragment_url: null,
      } as CopilotCitation
      return (
        <button type="button" onClick={() => v.requestHighlight(c)}>
          cite
        </button>
      )
    }
    renderWorkspace({}, <Citer />)
    expect(screen.getByRole('tab', { name: /answer/i })).toHaveAttribute('aria-selected', 'true')
    fireEvent.click(screen.getByRole('button', { name: 'cite' }))
    expect(screen.getByRole('tab', { name: /filing/i })).toHaveAttribute('aria-selected', 'true')
  })

  it('moves between tabs with arrow keys (roving tabindex)', () => {
    renderWorkspace()
    const answer = screen.getByRole('tab', { name: /answer/i })
    expect(answer).toHaveAttribute('tabindex', '0')
    expect(screen.getByRole('tab', { name: /filing/i })).toHaveAttribute('tabindex', '-1')

    fireEvent.keyDown(answer, { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: /filing/i })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: /filing/i })).toHaveAttribute('tabindex', '0')
  })

  it('wires tabs to their panels (aria-controls / role=tabpanel)', () => {
    renderWorkspace()
    const answerTab = screen.getByRole('tab', { name: /answer/i })
    const panelId = answerTab.getAttribute('aria-controls')!
    const panel = document.getElementById(panelId)!
    expect(panel).toHaveAttribute('role', 'tabpanel')
    expect(panel).toHaveAttribute('aria-labelledby', answerTab.id)
  })

  it('closes via the header close button', () => {
    const onOpenChange = vi.fn()
    renderWorkspace({ onOpenChange })
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('shows the launcher (and no tabs/resizer) when closed', () => {
    renderWorkspace({ open: false })
    expect(screen.getByRole('button', { name: /ask this filing/i })).toBeInTheDocument()
    expect(screen.queryByRole('tab')).toBeNull()
    expect(screen.queryByRole('separator')).toBeNull()
  })

  it('renders nothing Copilot-related without a summary', () => {
    renderWorkspace({ summaryAvailable: false })
    expect(screen.getByTestId('summary')).toBeInTheDocument()
    expect(screen.queryByRole('tab')).toBeNull()
    expect(screen.queryByRole('button', { name: /ask this filing/i })).toBeNull()
    expect(screen.queryByRole('separator')).toBeNull()
  })

  it('silences the first-run nudge in demo mode but keeps the launcher', () => {
    // Non-demo, closed: the contextual coachmark nudge appears alongside the launcher.
    const { unmount } = renderWorkspace({ open: false })
    expect(screen.getByRole('button', { name: /ask this filing/i })).toBeInTheDocument()
    expect(screen.getByText(/ask this filing anything/i)).toBeInTheDocument()
    unmount()

    // Demo mode, closed: launcher still present, but the nudge is suppressed (calm first impression).
    renderWorkspace({ open: false, demoMode: true })
    expect(screen.getByRole('button', { name: /ask this filing/i })).toBeInTheDocument()
    expect(screen.queryByText(/ask this filing anything/i)).toBeNull()
  })

  it('shows the resize separator when open and persists a keyboard resize', () => {
    renderWorkspace()
    const sep = screen.getByRole('separator', { name: /resize copilot/i })
    const before = Number(sep.getAttribute('aria-valuenow'))
    fireEvent.keyDown(sep, { key: 'ArrowLeft' })
    const after = Number(screen.getByRole('separator').getAttribute('aria-valuenow'))
    expect(after).toBe(before + 24)
    expect(Number(window.localStorage.getItem('copilot:paneWidth'))).toBe(after)
  })
})

/**
 * EN-01: the page wiring. A provenance chip in the summary opens the pane on the Filing tab through
 * the provider's onRequestOpen; an open pane switches without closing; a closed pane never reopens on
 * its own; the copilot body survives; focus returns to the chip that opened the pane.
 */
const EVIDENCE = 'Our revenue is concentrated among a small number of large customers.'
const URL = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm'

function CopilotCounter() {
  const [n, setN] = useState(0)
  return (
    <button type="button" onClick={() => setN((v) => v + 1)}>
      asked {n}
    </button>
  )
}

// An Ask answer's citation, rendered by the real CitationChip inside the Answer panel.
const ANSWER_CITATION: CopilotCitation = { n: 1, excerpt: EVIDENCE, section_ref: 'Item 1A', verified: true, fragment_url: `${URL}#:~:text=Our%20revenue` }

/** A hypothetical in-pane caller that records itself as the opener (CitationChip no longer does). */
function InPaneOpener() {
  const viewer = useFilingViewer()!
  return (
    <button type="button" onClick={(e) => viewer.requestHighlight(ANSWER_CITATION, e.currentTarget)}>
      in-pane opener
    </button>
  )
}

function Page({ initialOpen = false }: { initialOpen?: boolean }) {
  const [open, setOpen] = useState(initialOpen)
  const [tick, setTick] = useState(0)
  const openForSource = useCallback(() => setOpen(true), [])
  return (
    <FilingViewerProvider filingId={3} ticker="AAPL" filingType="10-K" onRequestOpen={openForSource}>
      <button type="button" onClick={() => setTick((t) => t + 1)}>
        unrelated {tick}
      </button>
      <FilingWorkspace
        open={open}
        onOpenChange={setOpen}
        summaryAvailable
        secUrl={URL}
        copilotBody={
          <>
            <CopilotCounter />
            <CitationChip citation={ANSWER_CITATION} />
            <InPaneOpener />
          </>
        }
        filingBody={<div data-testid="filing">filing</div>}
      >
        <p>
          Total net sales rose. <SourceTrace url={URL} verified sectionRef="Item 1A · Risk Factors" excerpt={EVIDENCE} />
        </p>
      </FilingWorkspace>
    </FilingViewerProvider>
  )
}

// The shell keeps its dialog role while hidden, but an aria-hidden element has no accessible name in
// the a11y tree, so it is located by its attributes rather than by role + name.
const dialog = () => document.querySelector<HTMLElement>('[role="dialog"][aria-label="Ask this Filing"]')!
const chip = () => screen.getByRole('button', { name: 'Source: Verified in filing' })
const filingTab = () => screen.getByRole('tab', { name: /filing/i })
const answerChip = () => screen.getByRole('button', { name: /^Citation 1:/ })

describe('FilingWorkspace opened by a provenance chip (EN-01)', () => {
  beforeEach(() => window.localStorage.clear())

  it('a chip activation opens a closed pane on the Filing tab', () => {
    render(<Page />)
    expect(dialog()).toHaveAttribute('aria-hidden', 'true')
    fireEvent.click(chip())
    expect(dialog()).toHaveAttribute('aria-hidden', 'false')
    expect(filingTab()).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('filing').parentElement).not.toHaveClass('hidden')
    // The launcher is gone and no Ask affordance took the activation as its own.
    expect(screen.queryByRole('button', { name: /ask this filing/i })).toBeNull()
  })

  it('a chip activation while the pane is open switches it to Filing without closing it', () => {
    render(<Page initialOpen />)
    expect(screen.getByRole('tab', { name: /answer/i })).toHaveAttribute('aria-selected', 'true')
    fireEvent.click(chip())
    expect(dialog()).toHaveAttribute('aria-hidden', 'false')
    expect(filingTab()).toHaveAttribute('aria-selected', 'true')
  })

  it('a pane the user closed stays closed through re-renders and reopens only on a new activation', () => {
    render(<Page />)
    fireEvent.click(chip())
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(dialog()).toHaveAttribute('aria-hidden', 'true')
    // Unrelated state changes re-render everything; the stale request must not reopen the pane.
    fireEvent.click(screen.getByRole('button', { name: /unrelated/i }))
    fireEvent.click(screen.getByRole('button', { name: /unrelated/i }))
    expect(dialog()).toHaveAttribute('aria-hidden', 'true')
    fireEvent.click(chip())
    expect(dialog()).toHaveAttribute('aria-hidden', 'false')
    expect(filingTab()).toHaveAttribute('aria-selected', 'true')
  })

  it('the copilot body keeps its state across chip activations and tab switches (continuity)', () => {
    render(<Page initialOpen />)
    fireEvent.click(screen.getByRole('button', { name: /asked 0/ }))
    fireEvent.click(screen.getByRole('button', { name: /asked 1/ }))
    fireEvent.click(chip())
    expect(filingTab()).toHaveAttribute('aria-selected', 'true')
    fireEvent.click(screen.getByRole('tab', { name: /answer/i }))
    expect(screen.getByRole('button', { name: /asked 2/ })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    fireEvent.click(chip())
    fireEvent.click(screen.getByRole('tab', { name: /answer/i }))
    expect(screen.getByRole('button', { name: /asked 2/ })).toBeInTheDocument()
  })

  it('when the pane closes with focus fallen to <body>, focus returns to the chip that opened it, once', () => {
    render(<Page />)
    const c = chip()
    fireEvent.click(c) // a click without focus: the opener is recorded, focus stays on <body>
    expect(document.activeElement).toBe(document.body)
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(document.activeElement).toBe(c)

    // A later launcher-driven open and close does not return to the stale chip: the opener was taken.
    // Focus falls to the launcher instead (EN-05a). This case pinned <body> here before: that was the
    // bug, not the contract (lessons/frontend-dialog-opener-outlives-the-dialog.md (b)).
    act(() => c.blur())
    expect(document.activeElement).toBe(document.body)
    fireEvent.click(screen.getByRole('button', { name: /ask this filing/i }))
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(document.activeElement).not.toBe(c)
    expect(document.activeElement).toBe(screen.getByRole('button', { name: /ask this filing/i }))
  })

  it('closing from the pane\'s own Close button returns focus to the chip (focus is still on the hidden Close when the effect runs)', () => {
    render(<Page />)
    const chip = screen.getByRole('button', { name: 'Source: Verified in filing' })
    fireEvent.click(chip)
    expect(dialog().getAttribute('aria-hidden')).toBe('false')
    // A keyboard user tabbed to Close and pressed it; jsdom, like Chromium at the moment the effect
    // runs, still reports the now-hidden Close as the active element.
    const close = screen.getByRole('button', { name: 'Close' })
    act(() => close.focus())
    expect(document.activeElement).toBe(close)
    fireEvent.click(close)
    expect(dialog().getAttribute('aria-hidden')).toBe('true')
    expect(document.activeElement).toBe(chip)
  })

  it('focus the pane never held is left alone on close', () => {
    render(<Page />)
    const other = screen.getByRole('button', { name: /unrelated/i })
    act(() => other.focus())
    fireEvent.click(chip())
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(document.activeElement).toBe(other)
  })
})

/**
 * EN-01 follow-up: a keyboard activation of an answer's [n] chip switches the pane to the Filing tab,
 * which hides the chip with its panel. Focus goes to the selected Filing tab instead of falling to
 * <body>; a switch that leaves focus somewhere visible is not moved.
 */
describe('FilingWorkspace view switch from inside the pane (EN-01 follow-up)', () => {
  beforeEach(() => window.localStorage.clear())

  it('an answer citation hands focus to the Filing tab when it hides its own chip', () => {
    render(<Page initialOpen />)
    const cite = answerChip()
    act(() => cite.focus())
    fireEvent.click(cite)
    expect(filingTab()).toHaveAttribute('aria-selected', 'true')
    // jsdom, like Chromium when the effect runs, still reports the hidden chip as active: it fell.
    expect(document.activeElement).toBe(filingTab())
  })

  it('a switch with focus already fallen to <body> also lands on the selected tab', () => {
    render(<Page initialOpen />)
    fireEvent.click(answerChip()) // a keyboard click (detail 0) after the chip remounted and focus fell
    expect(document.activeElement).toBe(filingTab())
  })

  // Pre-merge review of #1113: a pointer's click leaves focus to the pointer. With the tab focused, the
  // arrow keys would drive the tablist (ArrowLeft flips back to Answer) and Space would stop scrolling.
  it('a pointer click on an answer citation switches to Filing and hands no focus to the tab', () => {
    render(<Page initialOpen />)
    const cite = answerChip()
    act(() => cite.focus()) // Chromium focuses a clicked button
    fireEvent.click(cite, { detail: 1 })
    expect(filingTab()).toHaveAttribute('aria-selected', 'true')
    expect(document.activeElement).not.toBe(filingTab())
  })

  // The marker ends with its click's task: a keyboard click inside the panels that switches nothing
  // (the composer, an answer's text) must not arm a hand-off for a later switch from outside the pane.
  it('a click inside the pane that switches nothing arms no hand-off for a later summary chip (the marker ends with its task)', async () => {
    render(<Page initialOpen />)
    fireEvent.click(screen.getByRole('button', { name: /asked 0/ }))
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
    act(() => (document.activeElement as HTMLElement | null)?.blur())
    fireEvent.click(chip()) // a summary chip clicked without focus (Safari and Firefox on macOS)
    expect(filingTab()).toHaveAttribute('aria-selected', 'true')
    expect(document.activeElement).toBe(document.body)
  })

  it('a summary chip keeps its focus when it switches an open pane, and the tabs keep theirs', () => {
    render(<Page initialOpen />)
    const c = chip()
    act(() => c.focus())
    fireEvent.click(c)
    expect(filingTab()).toHaveAttribute('aria-selected', 'true')
    expect(document.activeElement).toBe(c)

    const answer = screen.getByRole('tab', { name: /answer/i })
    act(() => answer.focus())
    fireEvent.keyDown(answer, { key: 'ArrowRight' })
    expect(document.activeElement).toBe(filingTab())
    fireEvent.keyDown(filingTab(), { key: 'ArrowLeft' })
    expect(document.activeElement).toBe(screen.getByRole('tab', { name: /answer/i }))
  })

  it('a summary chip stays the opener through an answer citation: closing returns focus to it', () => {
    render(<Page />)
    const c = chip()
    act(() => c.focus())
    fireEvent.click(c)
    fireEvent.click(screen.getByRole('tab', { name: /answer/i }))
    const cite = answerChip()
    act(() => cite.focus())
    fireEvent.click(cite)
    expect(document.activeElement).toBe(filingTab())
    // A keyboard user tabs to Close and presses it; focus goes back to the chip that opened the pane.
    const close = screen.getByRole('button', { name: 'Close' })
    act(() => close.focus())
    fireEvent.click(close)
    expect(dialog()).toHaveAttribute('aria-hidden', 'true')
    expect(document.activeElement).toBe(c)
  })

  it('an element inside the pane is never where a closing pane returns focus', () => {
    render(<Page initialOpen />)
    const inPane = screen.getByRole('button', { name: 'in-pane opener' })
    act(() => inPane.focus())
    fireEvent.click(inPane) // records itself as the opener
    const close = screen.getByRole('button', { name: 'Close' })
    act(() => close.focus())
    fireEvent.click(close)
    expect(dialog()).toHaveAttribute('aria-hidden', 'true')
    // Hidden with the pane, it cannot take focus in a browser; it is not a return target. The launcher,
    // which remounted with the close, takes it (EN-05a).
    expect(document.activeElement).not.toBe(inPane)
    expect(document.activeElement).toBe(screen.getByRole('button', { name: /ask this filing/i }))
  })

  it('opening a closed pane hands nothing off, whether the chip held focus or not', () => {
    render(<Page />)
    const c = chip()
    act(() => c.focus())
    fireEvent.click(c)
    expect(dialog()).toHaveAttribute('aria-hidden', 'false')
    expect(document.activeElement).toBe(c)
    // Back to Answer before closing, so the next open switches the view as it opens.
    fireEvent.click(screen.getByRole('tab', { name: /answer/i }))
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))

    // A click that never focused the chip (Safari does not focus buttons on click) opens the pane
    // on Filing with focus on <body>, and it stays there: the open itself takes no focus (EN-01).
    act(() => (document.activeElement as HTMLElement | null)?.blur())
    fireEvent.click(chip())
    expect(dialog()).toHaveAttribute('aria-hidden', 'false')
    expect(filingTab()).toHaveAttribute('aria-selected', 'true')
    expect(document.activeElement).toBe(document.body)
  })

  it('a summary chip clicked without focus switches an open pane and leaves focus on <body> (Safari)', () => {
    render(<Page initialOpen />)
    expect(screen.getByRole('tab', { name: /answer/i })).toHaveAttribute('aria-selected', 'true')
    expect(document.activeElement).toBe(document.body)
    fireEvent.click(chip()) // Safari and Firefox on macOS do not focus a clicked button
    expect(filingTab()).toHaveAttribute('aria-selected', 'true')
    // Not handed to the tab: the arrow keys and Space keep scrolling the page, not driving the tablist.
    expect(document.activeElement).toBe(document.body)
  })
})

/**
 * EN-05a: the other routes that open the pane. The page's Ask entries (the callout's button and
 * starters, a follow-up) and the rail's Ctrl/⌘+K and "/" open it without recording an opener, and the
 * launcher and the coachmark's Try leave the DOM as it opens. This stand-in page opens the pane the
 * same ways: an Ask button outside the pane, a Ctrl+K listener on window, the launcher and the Try.
 * It also closes on Escape from a window listener, as AskCopilotRail does, so Escape and × are each
 * a close path.
 */
function AskPage() {
  const [open, setOpen] = useState(false)
  const [askShown, setAskShown] = useState(true)
  const openForSource = useCallback(() => setOpen(true), [])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen(true)
      } else if (e.key === 'Escape' && open && !e.defaultPrevented) {
        setOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])
  return (
    <FilingViewerProvider filingId={3} ticker="AAPL" filingType="10-K" onRequestOpen={openForSource}>
      <button type="button">elsewhere</button>
      {askShown && (
        <button type="button" onClick={() => setOpen(true)}>
          Ask in page
        </button>
      )}
      <button type="button" onClick={() => setAskShown(false)}>
        remove ask
      </button>
      <FilingWorkspace
        open={open}
        onOpenChange={setOpen}
        summaryAvailable
        secUrl={URL}
        copilotBody={<CopilotCounter />}
        filingBody={<div data-testid="filing">filing</div>}
      >
        <p>
          Total net sales rose. <SourceTrace url={URL} verified sectionRef="Item 1A · Risk Factors" excerpt={EVIDENCE} />
        </p>
      </FilingWorkspace>
    </FilingViewerProvider>
  )
}

const launcher = () => screen.getByRole('button', { name: /ask this filing/i })
const answerTab = () => screen.getByRole('tab', { name: /answer/i })
const askInPage = () => screen.getByRole('button', { name: 'Ask in page' })
const elsewhere = () => screen.getByRole('button', { name: 'elsewhere' })
/** The launcher's hand-off runs in a microtask after the commit that removed it (useFocusHandoff). */
const settle = () => act(async () => {})
/** A keyboard user's Escape from wherever focus is (the rail's window listener closes the pane). */
const pressEscape = () => fireEvent.keyDown(document.activeElement ?? document.body, { key: 'Escape' })
/** A keyboard user's ×: Tab to it and press Enter (a click with detail 0). */
const pressClose = () => {
  const close = screen.getByRole('button', { name: 'Close' })
  act(() => close.focus())
  fireEvent.click(close)
}

describe('FilingWorkspace returns focus on close for every route that opens it, lg+ (EN-05a)', () => {
  beforeEach(() => window.localStorage.clear())

  for (const [path, close] of [
    ['Escape', pressEscape],
    ['×', pressClose],
  ] as const) {
    it(`a keyboard press on the launcher hands focus into the pane; ${path} returns it to the launcher`, async () => {
      render(<AskPage />)
      act(() => launcher().focus())
      fireEvent.click(launcher()) // Enter or Space: a click with detail 0
      await settle()
      expect(dialog()).toHaveAttribute('aria-hidden', 'false')
      // The launcher left with the open; a visitor who cannot ask has no composer to take focus, so
      // the hand-off is all there is: the selected tab, the pane's first stop.
      expect(document.activeElement).toBe(answerTab())
      close()
      expect(dialog()).toHaveAttribute('aria-hidden', 'true')
      expect(document.activeElement).toBe(launcher())
    })

    it(`an Ask button outside the pane keeps focus as it opens and gets it back on ${path}`, async () => {
      render(<AskPage />)
      act(() => askInPage().focus())
      fireEvent.click(askInPage())
      await settle()
      expect(dialog()).toHaveAttribute('aria-hidden', 'false')
      expect(document.activeElement).toBe(askInPage())
      // The rail focuses its composer on open; the user works in the pane, then closes it.
      act(() => answerTab().focus())
      close()
      expect(dialog()).toHaveAttribute('aria-hidden', 'true')
      expect(document.activeElement).toBe(askInPage())
    })

    it(`Ctrl+K pressed on a control outside the pane returns focus to it on ${path}`, () => {
      render(<AskPage />)
      act(() => elsewhere().focus())
      fireEvent.keyDown(elsewhere(), { key: 'k', ctrlKey: true })
      expect(dialog()).toHaveAttribute('aria-hidden', 'false')
      act(() => answerTab().focus())
      close()
      expect(document.activeElement).toBe(elsewhere())
    })

    it(`the coachmark's Try by keyboard hands focus into the pane; ${path} returns it to the launcher`, async () => {
      render(<AskPage />)
      const tryIt = screen.getByRole('button', { name: /try it/i })
      act(() => tryIt.focus())
      fireEvent.click(tryIt)
      await settle()
      expect(screen.queryByRole('button', { name: /try it/i })).toBeNull()
      expect(document.activeElement).toBe(answerTab())
      close()
      expect(document.activeElement).toBe(launcher())
    })
  }

  it('Ctrl+K pressed with nothing focused returns focus to the launcher', () => {
    render(<AskPage />)
    expect(document.activeElement).toBe(document.body)
    fireEvent.keyDown(document.body, { key: 'k', ctrlKey: true })
    act(() => answerTab().focus())
    pressEscape()
    expect(document.activeElement).toBe(launcher())
  })

  it('an opener that left the page while the pane was open falls back to the launcher', () => {
    render(<AskPage />)
    act(() => askInPage().focus())
    fireEvent.click(askInPage())
    fireEvent.click(screen.getByRole('button', { name: 'remove ask' }))
    expect(screen.queryByRole('button', { name: 'Ask in page' })).toBeNull()
    act(() => answerTab().focus())
    pressClose()
    expect(document.activeElement).toBe(launcher())
  })

  it('an opener still on the page that no longer takes focus (hidden since the open) is passed over for the launcher', async () => {
    render(<AskPage />)
    act(() => askInPage().focus())
    fireEvent.click(askInPage())
    await settle()
    // jsdom focuses a display:none element; a browser does not. A no-op focus() stands in for that.
    const refused = vi.spyOn(askInPage(), 'focus').mockImplementation(() => {})
    act(() => answerTab().focus())
    pressClose()
    expect(refused).toHaveBeenCalled()
    expect(document.activeElement).toBe(launcher())
  })

  it('a chip activated while a Ctrl+K-opened pane is open is where focus returns, ahead of the control Ctrl+K was pressed on', () => {
    render(<AskPage />)
    act(() => elsewhere().focus())
    fireEvent.keyDown(elsewhere(), { key: 'k', ctrlKey: true })
    expect(dialog()).toHaveAttribute('aria-hidden', 'false')
    act(() => chip().focus())
    fireEvent.click(chip())
    expect(filingTab()).toHaveAttribute('aria-selected', 'true')
    act(() => filingTab().focus())
    pressEscape()
    expect(dialog()).toHaveAttribute('aria-hidden', 'true')
    expect(document.activeElement).toBe(chip())
  })

  it('a pointer press on the launcher hands nothing off; a close with focus on <body> still lands on the launcher', async () => {
    render(<AskPage />)
    act(() => launcher().focus()) // Chromium focuses a clicked button
    fireEvent.click(launcher(), { detail: 1 })
    await settle()
    // Not handed to the tab: a pointer's press leaves focus to the pointer (the arrow keys would
    // drive the tablist), as the citation hand-off does.
    expect(document.activeElement).toBe(document.body)
    pressEscape()
    expect(document.activeElement).toBe(launcher())
  })

  it('focus the user moved out of the pane before closing it is left alone', async () => {
    render(<AskPage />)
    act(() => launcher().focus())
    fireEvent.click(launcher())
    await settle()
    act(() => elsewhere().focus())
    pressEscape()
    expect(dialog()).toHaveAttribute('aria-hidden', 'true')
    expect(document.activeElement).toBe(elsewhere())
  })

  it('a launcher press while the Filing view is selected hands focus to the Filing tab', async () => {
    render(<AskPage />)
    fireEvent.click(chip())
    expect(filingTab()).toHaveAttribute('aria-selected', 'true')
    pressClose()
    expect(document.activeElement).toBe(chip())
    act(() => launcher().focus())
    fireEvent.click(launcher())
    await settle()
    expect(filingTab()).toHaveAttribute('aria-selected', 'true')
    expect(document.activeElement).toBe(filingTab())
  })
})

describe('FilingWorkspace sheet below lg, opened by a provenance chip (EN-01)', () => {
  let matchMedia: ReturnType<typeof vi.spyOn>
  let rects: ReturnType<typeof vi.spyOn>
  beforeEach(() => {
    window.localStorage.clear()
    // Below lg the shell is a modal bottom sheet (focus trapped); the pointer stays fine so the chip
    // itself opens the pane rather than the source sheet.
    matchMedia = vi.spyOn(window, 'matchMedia').mockImplementation(
      (query: string) =>
        ({
          matches: query === '(max-width: 1023.98px)',
          media: query,
          addEventListener: () => {},
          removeEventListener: () => {},
          addListener: () => {},
          removeListener: () => {},
          onchange: null,
          dispatchEvent: () => false,
        }) as unknown as MediaQueryList,
    )
    rects = vi.spyOn(HTMLElement.prototype, 'getClientRects').mockReturnValue([{}] as unknown as DOMRectList)
  })
  afterEach(() => {
    matchMedia.mockRestore()
    rects.mockRestore()
  })

  it('the sheet takes focus on open and returns it to the chip on close; a launcher-opened sheet returns to the launcher', () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      render(<Page />)
      const c = chip()
      act(() => c.focus())
      fireEvent.click(c)
      expect(dialog()).toHaveAttribute('aria-hidden', 'false')
      expect(dialog().contains(document.activeElement)).toBe(true)
      fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Escape' })
      expect(dialog()).toHaveAttribute('aria-hidden', 'true')
      expect(document.activeElement).toBe(c)
      // Focus returning to the chip opens its detail popover, as any focus on a chip does.
      expect(screen.getByRole('group', { name: 'Source detail' })).toBeInTheDocument()

      // The launcher takes focus; the chip's popover closes after its blur delay, as in a browser.
      const launcher = screen.getByRole('button', { name: /ask this filing/i })
      act(() => launcher.focus())
      act(() => {
        vi.advanceTimersByTime(200)
      })
      expect(screen.queryByRole('group', { name: 'Source detail' })).toBeNull()
      fireEvent.click(launcher)
      expect(dialog().contains(document.activeElement)).toBe(true)
      fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Escape' })
      expect(dialog()).toHaveAttribute('aria-hidden', 'true')
      // The opener was taken on the first close, so this close returns to the launcher, not the chip.
      expect(document.activeElement).toBe(screen.getByRole('button', { name: /ask this filing/i }))
    } finally {
      vi.useRealTimers()
    }
  })

  it('an opener inside the sheet falls back to the launcher; a summary chip survives an answer citation', () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    try {
      render(<Page />)
      fireEvent.click(screen.getByRole('button', { name: /ask this filing/i }))
      const inPane = screen.getByRole('button', { name: 'in-pane opener' })
      act(() => inPane.focus())
      fireEvent.click(inPane) // an in-pane caller that records itself
      fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Escape' })
      expect(dialog()).toHaveAttribute('aria-hidden', 'true')
      expect(document.activeElement).toBe(screen.getByRole('button', { name: /ask this filing/i }))

      const c = chip()
      act(() => c.focus())
      fireEvent.click(c)
      fireEvent.click(screen.getByRole('tab', { name: /answer/i }))
      const cite = answerChip()
      act(() => cite.focus())
      fireEvent.click(cite)
      expect(document.activeElement).toBe(filingTab())
      // The focused chip's card closes after its blur delay (in Chromium the answer re-renders the
      // chip and the card goes with it); until then it would own the first Escape, as it should.
      act(() => {
        vi.advanceTimersByTime(200)
      })
      expect(screen.queryByRole('group', { name: /^Citation 1:/ })).toBeNull()
      fireEvent.keyDown(document.activeElement as HTMLElement, { key: 'Escape' })
      expect(dialog()).toHaveAttribute('aria-hidden', 'true')
      expect(document.activeElement).toBe(c)
    } finally {
      vi.useRealTimers()
    }
  })

  // EN-05a leaves the sheet as it was: its trap moves focus in on open and returns it to the chip or
  // the launcher on close; the desktop opener and the launcher's hand-off add nothing below lg.
  it('the sheet path is unchanged: an Ask button or a keyboard press on the launcher, closed by Escape or ×, returns to the launcher', async () => {
    render(<AskPage />)
    for (const open of [() => askInPage(), () => launcher()]) {
      for (const close of [pressEscape, pressClose]) {
        act(() => open().focus())
        fireEvent.click(open())
        await settle()
        expect(dialog()).toHaveAttribute('aria-hidden', 'false')
        // The trap's first focusable, before any hand-off could run.
        expect(document.activeElement).toBe(answerTab())
        close()
        expect(dialog()).toHaveAttribute('aria-hidden', 'true')
        expect(document.activeElement).toBe(launcher())
      }
    }
  })
})
