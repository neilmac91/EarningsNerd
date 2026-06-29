import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import FilingWorkspace from '@/features/filings/components/copilot/FilingWorkspace'
import {
  FilingViewerProvider,
  useFilingViewer,
} from '@/features/filings/components/copilot/FilingViewerContext'
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
