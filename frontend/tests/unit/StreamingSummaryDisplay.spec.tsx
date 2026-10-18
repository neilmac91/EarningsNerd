import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { useRef, useState } from 'react'
import StreamingSummaryDisplay from '@/app/filing/[id]/StreamingSummaryDisplay'
import { GuidanceCard } from '@/components/ui'
import type { Filing } from '@/features/filings/api/filings-api'

// The trial ships behind ENABLE_PRO_TRIAL (flipped with the backend's PRO_TRIAL_DAYS); a live flag lets a
// case turn it on without re-importing the component.
const flags = vi.hoisted(() => ({ ENABLE_PRO_TRIAL: false }))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  get ENABLE_PRO_TRIAL() {
    return flags.ENABLE_PRO_TRIAL
  },
}))
beforeEach(() => {
  flags.ENABLE_PRO_TRIAL = false
})

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
    const status = screen.getByText('Reading the statements, risk factors and MD&A.')
    expect(status).toHaveAttribute('role', 'status')
    expect(status).toHaveAttribute('aria-live', 'polite')
    expect(status.className).toContain('sr-only')
  })

  it('names the filing type when fetching from SEC EDGAR', async () => {
    renderAt('fetching')
    await act(async () => {})
    expect(screen.getByText('Fetching the 10-K from SEC EDGAR.')).toHaveAttribute('aria-live', 'polite')
  })

  it('changes only on stage transitions, not on progress ticks', async () => {
    const { rerender } = renderAt('analyzing', 5)
    await act(async () => {})
    const live = () => screen.getByText(/^(Checking figures against the company’s XBRL|Writing the summary)\.$/)
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
    expect(live()).toHaveTextContent('Writing the summary.')
  })

  it('has a generic announcement for early and unknown stages', async () => {
    const { rerender } = renderAt('queued')
    await act(async () => {})
    expect(screen.getByText('Starting summary generation.')).toHaveAttribute('aria-live', 'polite')
    rerender(<StreamingSummaryDisplay streamingText="" stage="mystery" message="" filing={filing} />)
    await act(async () => {})
    expect(screen.getByText('Generating the summary.')).toHaveAttribute('aria-live', 'polite')
  })
})

// A pending step reads in tertiary ink at full opacity (4.9:1 and up), never faded: opacity-40 put it at
// 2.1:1 (filing/F14). The real-browser contrast census is tests/e2e/text-floors.spec.ts.
describe('StreamingSummaryDisplay step log', () => {
  it('shows a pending step with its empty marker, its label at full opacity in tertiary ink', async () => {
    renderAt('fetching')
    await act(async () => {})
    const pending = screen.getByText('Writing the summary')
    // Its marker: the empty hairline circle (no check, no dot) beside the label.
    const marker = pending.previousElementSibling as HTMLElement
    expect(marker.className.split(/\s+/)).toEqual(expect.arrayContaining(['rounded-full', 'border', 'border-border-light', 'dark:border-border-dark']))
    expect(marker.childElementCount).toBe(0)
    // Whole class tokens: a translucent ink (`text-text-tertiary-light/40`) fades it as opacity-40 did.
    expect(pending.className.split(/\s+/)).toEqual(expect.arrayContaining(['text-text-tertiary-light', 'dark:text-text-secondary-dark']))
    expect(pending.className).not.toMatch(/text-text-(?:tertiary|secondary)-(?:light|dark)\//)
    for (let el: HTMLElement | null = pending; el; el = el.parentElement) expect(el.className).not.toMatch(/\bopacity-/)
    expect(screen.getByText('Fetching the 10-K from SEC EDGAR').className).toContain('font-medium')
  })

  it('reads the four steps in the product voice, the first naming the filing’s own form', async () => {
    renderAt('fetching')
    await act(async () => {})
    const labels = screen.getAllByRole('listitem').map((item) => item.textContent)
    expect(labels).toEqual([
      'Fetching the 10-K from SEC EDGAR',
      'Reading the statements, risk factors and MD&A',
      'Checking figures against the company’s XBRL',
      'Writing the summary',
    ])
  })

  it('says a slow run is still running, without guessing why', async () => {
    renderAt('fetching', 50)
    await act(async () => {})
    expect(screen.getByText('Taking longer than usual. Still working on it.')).toBeInTheDocument()
    expect(screen.getByText('Still running')).toBeInTheDocument()
  })
})

// No glyph beside a section heading (DESIGN.md › Icons): the sparkle is the AI summary chip's alone, and
// both headings say what they are in words. The progress card's head and the streamed summary's head
// carried a 20px sparkle each until the design owner's call on #1288's MEANING thread.
describe('StreamingSummaryDisplay headings', () => {
  it('sets no icon in or beside "Generating the summary" or "AI-generated summary"', async () => {
    render(<StreamingSummaryDisplay streamingText="Revenue rose." stage="summarizing" message="" filing={filing} />)
    await act(async () => {})
    for (const name of ['Generating the summary', 'AI-generated summary']) {
      const heading = screen.getByRole('heading', { level: 2, name })
      // The heading's own row (the nearest flex row holding it), the heading included, at any depth: a glyph
      // inside the heading or wrapped in a span beside it is a glyph beside a section heading all the same.
      const row = heading.closest('div.flex') as HTMLElement
      expect(row, name).not.toBeNull()
      expect(row.querySelector('svg'), name).toBeNull()
    }
  })

  // The capture review at 200% text on a 390px phone: the percent printed over "Generating the summary",
  // "Usually 30–60s" collided with it, and the meta line broke "10-|K". The header row wraps, the percent
  // keeps to the right edge on a line of its own, and the form code is one unbreakable run.
  it('lets the percent move beneath the heading, and keeps the form code whole', async () => {
    renderAt('fetching')
    await act(async () => {})
    const classes = (el: Element) => el.className.split(/\s+/)
    const heading = screen.getByRole('heading', { level: 2, name: 'Generating the summary' })
    const row = heading.parentElement!.parentElement!
    expect(classes(row)).toContain('flex-wrap')
    const percent = row.lastElementChild!
    expect(percent).toHaveTextContent(/\d+%/)
    expect(classes(percent)).toEqual(expect.arrayContaining(['ml-auto', 'flex-none']))
    const meta = heading.nextElementSibling as HTMLElement
    expect(meta).toHaveTextContent('10-K · Processing…')
    expect(classes(within(meta).getByText('10-K'))).toContain('whitespace-nowrap')
  })
})

describe('StreamingSummaryDisplay paywall routing', () => {
  it.each([true, false])('preserves monthly billing for a promised trial (eligible=%s)', (trialEligible) => {
    flags.ENABLE_PRO_TRIAL = true
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

  it('promises no trial while the trial does not ship, whatever the page says about the user', () => {
    render(<StreamingSummaryDisplay streamingText="" stage="error" message="Monthly limit reached" filing={filing} trialEligible />)
    expect(screen.getByRole('link', { name: 'Upgrade to Pro' })).toHaveAttribute('href', '/pricing')
    expect(screen.queryByText(/free trial/)).toBeNull()
  })
})

// The pipeline's sentences keep their em-dashes until the next functional change to summary_stages (F35,
// D-046, E92); the card shows the mapped sentence (features/summaries/lib/streamErrorCopy.ts), and the raw one
// still routes it.
describe('StreamingSummaryDisplay failure reason', () => {
  it('shows a backend sentence in the product voice', async () => {
    render(
      <StreamingSummaryDisplay
        streamingText=""
        stage="error"
        message=""
        error={'Unable to retrieve this filing at the moment \u2014 please try again shortly.'}
        filing={filing}
      />,
    )
    await act(async () => {})
    expect(screen.getByRole('heading', { name: 'Generation interrupted' })).toBeInTheDocument()
    expect(screen.getByText('We could not generate this summary. Try again shortly.')).toBeInTheDocument()
    expect(screen.queryByText(/\u2014/)).toBeNull()
  })
})

// EN-05: a failed generation used to leave focus where it was, usually <body> after page load, so a
// keyboard user tabbed through the whole site header to reach the card's Retry (9 stops at 1440px on
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
        <button onClick={() => setRun({ ...FAILED, error: 'The server could not start the summary. Try again in a moment.' })}>fail differently</button>
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
  const retry = () => screen.getByRole('button', { name: 'Try again' })

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

  it('its Try again hands focus to the progress heading when its press restarts the run', async () => {
    render(<Page start={FAILED} />)
    await settle()
    retry().focus()
    fireEvent.click(retry(), { detail: 0 })
    await settle()
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull()
    expect(document.activeElement).toBe(heading('Generating the summary'))
    expect(heading('Generating the summary')).toHaveAttribute('tabindex', '-1')
  })

  it('a restart that fails again brings focus back into the new card', async () => {
    render(<Page start={FAILED} />)
    await settle()
    retry().focus()
    fireEvent.click(retry(), { detail: 0 })
    await settle()
    expect(document.activeElement).toBe(heading('Generating the summary'))
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
    expect(screen.getByText('The server could not start the summary. Try again in a moment.')).toBeInTheDocument()
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
