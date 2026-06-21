import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import FilingWorkspace from '@/features/filings/components/copilot/FilingWorkspace'

describe('FilingWorkspace', () => {
  beforeEach(() => window.localStorage.clear())

  it('renders the summary children and the rail', () => {
    render(
      <FilingWorkspace open={false} rail={<div data-testid="rail">rail</div>}>
        <div data-testid="summary">summary</div>
      </FilingWorkspace>,
    )
    expect(screen.getByTestId('summary')).toBeInTheDocument()
    expect(screen.getByTestId('rail')).toBeInTheDocument()
  })

  it('shows the resize separator only when the Copilot is open', () => {
    const { rerender } = render(
      <FilingWorkspace open={false} rail={<div>rail</div>}>
        <div>s</div>
      </FilingWorkspace>,
    )
    expect(screen.queryByRole('separator')).toBeNull()

    rerender(
      <FilingWorkspace open rail={<div>rail</div>}>
        <div>s</div>
      </FilingWorkspace>,
    )
    expect(screen.getByRole('separator', { name: /resize copilot/i })).toBeInTheDocument()
  })

  it('persists a keyboard resize to localStorage', () => {
    render(
      <FilingWorkspace open rail={<div>rail</div>}>
        <div>s</div>
      </FilingWorkspace>,
    )
    const before = Number(screen.getByRole('separator').getAttribute('aria-valuenow'))
    fireEvent.keyDown(screen.getByRole('separator'), { key: 'ArrowLeft' }) // widen by 24
    const after = Number(screen.getByRole('separator').getAttribute('aria-valuenow'))

    expect(after).toBe(before + 24)
    expect(Number(window.localStorage.getItem('copilot:paneWidth'))).toBe(after)
  })

  it('clamps to the max width on Home', () => {
    render(
      <FilingWorkspace open rail={<div>rail</div>}>
        <div>s</div>
      </FilingWorkspace>,
    )
    const sep = screen.getByRole('separator')
    fireEvent.keyDown(sep, { key: 'Home' })
    expect(screen.getByRole('separator').getAttribute('aria-valuenow')).toBe(
      sep.getAttribute('aria-valuemax'),
    )
  })
})
