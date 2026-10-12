import { describe, expect, it } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { useRef, useState } from 'react'
import StreamingSummaryDisplay from '@/app/filing/[id]/StreamingSummaryDisplay'
import { GuidanceCard } from '@/components/ui'
import type { Filing } from '@/features/filings/api/filings-api'

const filing: Filing = {
  id: 3,
  company_id: 1,
  filing_type: '10-K',
  filing_date: '2026-02-01',
  period_end_date: '2025-12-31',
  accession_number: '0000320193-26-000001',
  document_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/',
  sec_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/',
  company: { id: 1, ticker: 'AAPL', name: 'APPLE INC.' },
} as Filing

const renderAt = (stage: string, elapsedSeconds = 0) =>
  render(
    <StreamingSummaryDisplay
      streamingText=""
      stage={stage}
      message=""
      filing={filing}
      elapsedSeconds={elapsedSeconds}
    />,
  )

// The progress card had a progressbar with an aria-label but no live region, so screen-reader
// users heard nothing while generation ran. The status node announces STAGE transitions only.
describe('StreamingSummaryDisplay live region', () => {
  it('announces the active pipeline stage through a polite status region', async () => {
    renderAt('parsing')
    await act(async () => {})
    // SkeletonText carries its own role="status" (DS §4), so locate ours by its announcement.
    const status = screen.getByText('Extracting financial statements, risk factors & MD&A.')
    expect(status).toHaveAttribute('role', 'status')
    expect(status).toHaveAttribute('aria-live', 'polite')
    expect(status.className).toContain('sr-only')
  })

  it('names the filing type when retrieving from EDGAR', async () => {
    renderAt('fetching')
    await act(async () => {})
    expect(screen.getByText('Retrieving 10-K filing from EDGAR.')).toHaveAttribute('aria-live', 'polite')
  })

  it('changes only on stage transitions, not on progress ticks', async () => {
    const { rerender } = renderAt('analyzing', 5)
    await act(async () => {})
    const live = () => screen.getByText(/^(Cross-referencing standardized XBRL financials|Generating investment analysis)\.$/)
    const before = live().textContent
    rerender(
      <StreamingSummaryDisplay streamingText="" stage="analyzing" message="" filing={filing} elapsedSeconds={20} />,
    )
    await act(async () => {})
    expect(live().textContent).toBe(before)
    rerender(
      <StreamingSummaryDisplay streamingText="" stage="summarizing" message="" filing={filing} elapsedSeconds={21} />,
    )
    await act(async () => {})
    expect(live()).toHaveTextContent('Generating investment analysis.')
  })

  it('has a generic announcement for early and unknown stages', async () => {
    const { rerender } = renderAt('queued')
    await act(async () => {})
    expect(screen.getByText('Starting summary generation.')).toHaveAttribute('aria-live', 'polite')
    rerender(<StreamingSummaryDisplay streamingText="" stage="mystery" message="" filing={filing} />)
    await act(async () => {})
    expect(screen.getByText('Generating your analysis.')).toHaveAttribute('aria-live', 'polite')
  })
})

describe('StreamingSummaryDisplay paywall routing', () => {
  it.each([true, false])('preserves monthly billing for a promised trial (eligible=%s)', (trialEligible) => {
    render(
      <StreamingSummaryDisplay
        streamingText=""
        stage="error"
        message="Monthly limit reached"
        filing={filing}
        trialEligible={trialEligible}
      />,
    )
    const label = trialEligible ? 'Start 7-day free trial' : 'Upgrade to Pro'
    expect(screen.getByRole('link', { name: label })).toHaveAttribute('href', trialEligible ? '/pricing?billing=monthly' : '/pricing')
  })
})

// EN-05: a failed generation used to leave focus where it was, usually <body> after page load, so a
// keyboard user tabbed through the whole site header to reach "Retry generation" (9 stops at 1440px on
// main), and the Retry's own press dropped focus to <body> again. Real-browser runs:
// tests/e2e/summary-generation-focus.spec.ts.
describe('StreamingSummaryDisplay focus around a failed generation', () => {
  interface Run { stage: string; error: string | null }
  const STREAMING: Run = { stage: 'fetching', error: null }
  const FAILED: Run = { stage: 'error', error: 'The filing could not be summarized right now.' }
  const LIMIT: Run = { stage: 'error', error: "You've reached your monthly limit. Upgrade to Pro for unlimited summaries." }

  /** page-client's slot for one generation: the stream's state, restarted the way useSummaryGeneration does. */
  function Page({ start }: { start: Run }) {
    const [run, setRun] = useState(start)
    return (
      <div>
        <button>elsewhere</button>
        {/* The stream's callbacks, from outside the display: a click() here moves no focus. */}
        <button onClick={() => setRun(FAILED)}>fail</button>
        <button onClick={() => setRun(LIMIT)}>limit</button>
        <button onClick={() => setRun({ ...FAILED, error: 'Server error. Please try again later.' })}>fail differently</button>
        <StreamingSummaryDisplay
          streamingText=""
          stage={run.stage}
          message=""
          filing={filing}
          error={run.error}
          // handleGenerateSummary clears the error in the same render that starts the stream.
          onRetry={() => setRun({ stage: 'initializing', error: null })}
        />
      </div>
    )
  }
  const settle = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })
  const outside = (name: string) => act(() => { screen.getByRole('button', { name }).click() })
  const heading = (name: string) => screen.getByRole('heading', { name })
  const retry = () => screen.getByRole('button', { name: 'Retry generation' })

  it('a failure that lands with focus on <body> focuses the card heading, one Tab before its Retry', async () => {
    render(<Page start={STREAMING} />)
    await settle()
    expect(document.activeElement).toBe(document.body)
    outside('fail')
    await settle()
    expect(document.activeElement).toBe(heading('Generation interrupted'))
    expect(heading('Generation interrupted')).toHaveAttribute('tabindex', '-1')
    // The reason rides on the focused title too, whatever the live announcement does when focus moves.
    expect(heading('Generation interrupted')).toHaveAccessibleDescription(FAILED.error!)
    // The heading, not the Retry: a key pressed as the card lands never restarts the run.
    expect(heading('Generation interrupted').compareDocumentPosition(retry()) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('focus somebody holds when the failure lands stays where it is', async () => {
    render(<Page start={STREAMING} />)
    await settle()
    const elsewhere = screen.getByRole('button', { name: 'elsewhere' })
    elsewhere.focus()
    outside('fail')
    await settle()
    expect(document.activeElement).toBe(elsewhere)
  })

  it('an error already there at mount (the fallback card) takes focus once the client render shows it', async () => {
    render(<Page start={FAILED} />)
    await settle()
    expect(document.activeElement).toBe(heading('Generation interrupted'))
  })

  it("the monthly-limit card takes focus the same way: its heading, ahead of the upgrade link", async () => {
    render(<Page start={STREAMING} />)
    await settle()
    outside('limit')
    await settle()
    expect(document.activeElement).toBe(heading("You've hit this month's free limit"))
    expect(screen.getByRole('link', { name: 'Upgrade to Pro' })).not.toHaveFocus()
  })

  it('Retry generation hands focus to the progress heading when its press restarts the run', async () => {
    render(<Page start={FAILED} />)
    await settle()
    retry().focus()
    fireEvent.click(retry(), { detail: 0 })
    await settle()
    expect(screen.queryByRole('button', { name: 'Retry generation' })).toBeNull()
    expect(document.activeElement).toBe(heading('Generating your analysis'))
    expect(heading('Generating your analysis')).toHaveAttribute('tabindex', '-1')
  })

  it('a restart that fails again brings focus back into the new card', async () => {
    render(<Page start={FAILED} />)
    await settle()
    retry().focus()
    fireEvent.click(retry(), { detail: 0 })
    await settle()
    expect(document.activeElement).toBe(heading('Generating your analysis'))
    // The progress card, its focused heading with it, leaves in the commit that shows the new card.
    outside('fail')
    await settle()
    expect(document.activeElement).toBe(heading('Generation interrupted'))
  })

  it('once the card is up it never takes focus back: a re-render while it shows leaves focus alone', async () => {
    render(<Page start={STREAMING} />)
    await settle()
    outside('fail')
    await settle()
    act(() => (document.activeElement as HTMLElement).blur())
    outside('fail differently')
    await settle()
    expect(screen.getByText('Server error. Please try again later.')).toBeInTheDocument()
    expect(document.activeElement).toBe(document.body)
  })
})

describe('GuidanceCard headingRef', () => {
  function WithRef({ title, description }: { title: string; description?: string }) {
    const ref = useRef<HTMLHeadingElement>(null)
    return <GuidanceCard variant="error" title={title} description={description} headingRef={ref} />
  }

  it('makes the title a focus target, described by the description, only when a ref is passed', () => {
    render(
      <>
        <GuidanceCard variant="error" title="Without a ref" description="Plain reason." />
        <WithRef title="With a ref" description="The reason." />
        <WithRef title="No description" />
      </>,
    )
    const plain = screen.getByRole('heading', { name: 'Without a ref' })
    expect(plain).not.toHaveAttribute('tabindex')
    expect(plain).not.toHaveAttribute('aria-describedby')
    expect(screen.getByText('Plain reason.')).not.toHaveAttribute('id')
    const target = screen.getByRole('heading', { name: 'With a ref' })
    expect(target).toHaveAttribute('tabindex', '-1')
    expect(target.className).toContain('outline-none')
    expect(target).toHaveAccessibleDescription('The reason.')
    expect(screen.getByRole('heading', { name: 'No description' })).not.toHaveAttribute('aria-describedby')
  })
})
