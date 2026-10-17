import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactElement } from 'react'
import { resetAccountQueries } from '@/features/auth/lib/accountQueryState'
import { queryKeys } from '@/lib/queryKeys'
import { WhatChanged, reportHasContent } from '@/features/filings/components/WhatChanged'
import { WordingChanges, receiptText } from '@/features/filings/components/WordingChanges'
import { changesPhrase, wordingHasContent } from '@/features/filings/lib/sectionChanges'
import type {
  ChangeReport,
  SectionChange,
  SectionChanges,
  SectionChangesOk,
  WordingLabel,
  WordingReceipt,
  WordingReviewState,
} from '@/features/summaries/api/summaries-api'

/**
 * The Item 1A wording block of the change report (E27, PR B): the filing's own risk-factor text
 * against the prior same-form original, as the backend's paragraph-paired diff serves it. Pins the
 * two forms a viewer can be served (every change for Pro; the counts, the first items and the Pro
 * prompt for everyone else), the redline convention (inserted words in <ins>, removed words in
 * <del>, each named for assistive tech; no brand tint or financial tone on either), the states that
 * are prose rather than a list, the events, and where the block sits inside "What changed".
 */

const mockAnalytics = vi.hoisted(() => ({
  wordingChangesViewed: vi.fn(),
  paywallPromptShown: vi.fn(),
  paywallCtaClicked: vi.fn(),
  wordingChangeLabeled: vi.fn(),
  wordingReviewCompleted: vi.fn(),
  wordingReceiptCopied: vi.fn(),
}))
vi.mock('@/lib/analytics', () => ({ default: mockAnalytics, analytics: mockAnalytics }))
const reviewApi = vi.hoisted(() => ({ getWordingReview: vi.fn(), setWordingLabel: vi.fn() }))
vi.mock('@/features/summaries/api/summaries-api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/summaries/api/summaries-api')>()),
  getWordingReview: reviewApi.getWordingReview,
  setWordingLabel: reviewApi.setWordingLabel,
}))
// UpgradeModal routes to /pricing through the app router, which vitest does not mount.
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))

const SIDE = { status: 'ok', extracted_at: '2026-10-12T00:00:00+00:00', reference_only: false, char_count: 2400, paragraph_count: 12 }
const PRIOR = { filing_id: 7, filing_type: '10-K', filing_date: '2024-11-01T00:00:00+00:00', period_end_date: '2024-09-28T00:00:00+00:00' }
const ITEMS: SectionChange[] = [
  { id: 'a1', kind: 'modified', index: 2, prior_index: 2, similarity: 0.82, moved: false, ops: [['equal', 'Our revenue depends on'], ['delete', 'a few'], ['insert', 'several large'], ['equal', 'customers.']] },
  { id: 'a2', kind: 'added', index: 5, after: 'We face new risks from export controls.' },
  { id: 'a3', kind: 'removed', prior_index: 6, before: 'Our offices in the region were closed.' },
  { id: 'a4', kind: 'moved', index: 9, prior_index: 3, after: 'Cybersecurity incidents could disrupt operations.' },
  { id: 'a5', kind: 'modified', index: 11, prior_index: 10, similarity: 0.9, moved: true, ops: [['equal', 'Interest rates may'], ['insert', 'continue to'], ['equal', 'rise.']] },
]
const FULL: SectionChangesOk = {
  section: 'item_1a',
  section_label: 'Risk factors',
  access: 'full',
  engine_version: 1,
  prior_filing: { ...PRIOR, accession_number: 'prior-annual-report' },
  status: 'ok',
  reason: null,
  current: SIDE,
  prior: { ...SIDE, paragraph_count: 11 },
  paragraphs: { prior: 11, later: 12, prior_excluded: 0, later_excluded: 0 },
  counts: { unchanged: 7, modified: 2, added: 1, removed: 1, moved: 1 },
  words: { later_total: 900, inserted: 14, deleted: 9, changed_ratio: 0.03 },
  has_changes: true,
  items: ITEMS,
  items_total: 5,
  truncated: false,
}
const TEASER: SectionChangesOk = { ...FULL, access: 'teaser', items: ITEMS.slice(0, 3), truncated: true }
const NONE: SectionChangesOk = {
  ...TEASER,
  has_changes: false,
  items: [],
  items_total: 0,
  truncated: false,
  counts: { unchanged: 12, modified: 0, added: 0, removed: 0, moved: 0 },
  words: { later_total: 900, inserted: 0, deleted: 0, changed_ratio: 0 },
}
const PENDING: SectionChanges = {
  section: 'item_1a',
  section_label: 'Risk factors',
  access: 'teaser',
  engine_version: 1,
  prior_filing: FULL.prior_filing,
  status: 'pending',
  reason: 'current_not_extracted',
}
const EMPTY_REPORT: ChangeReport = {
  has_prior: true,
  comparison_basis: 'Year over year',
  prior_filing: PRIOR,
  metrics: null,
  reporting_currency: 'USD',
  risks: null,
  key_changes: null,
  has_changes: false,
}
const METRICS_REPORT: ChangeReport = {
  ...EMPTY_REPORT,
  metrics: {
    headline: 'Revenue up 6.4%',
    items: [{ metric: 'revenue', label: 'Revenue', direction: 'up', pct: 6.4, current: 416e9, prior: 391e9, display: '+6.4%', tone: 'gain' }],
    data_quality: 'ok',
  },
  has_changes: true,
}
const context = { filingId: 42, ticker: 'AAPL', filingType: '10-K', isAuthenticated: false }
const LABELS = (rows: HTMLElement[]) => rows.map((row) => row.querySelector('p')?.textContent)

const REVIEW: WordingReviewState = {
  filing_id: 42,
  section: 'item_1a',
  section_label: 'Item 1A. Risk Factors',
  status: 'ok',
  engine_version: 1,
  items_total: 5,
  labels: {},
  counts: { reviewed: 0, follow_up: 0, unlabeled: 5 },
  completed_at: null,
  receipt: null,
}
const SHA_CURRENT = 'c'.repeat(64)
const SHA_PRIOR = 'p'.repeat(64)
const receiptFor = (labels: Record<string, WordingLabel>): WordingReceipt => {
  const followUps = Object.entries(labels).filter(([, label]) => label === 'follow_up').map(([id]) => id)
  return {
    version: 1,
    completed_at: '2026-10-13T12:00:00Z',
    section: 'item_1a',
    section_label: 'Item 1A. Risk Factors',
    filing: { filing_id: 42, filing_type: '10-K', filing_date: '2025-10-31T00:00:00+00:00', period_end_date: '2025-09-27T00:00:00+00:00', accession_number: 'current-annual-report' },
    prior_filing: { ...PRIOR, accession_number: 'prior-annual-report' },
    texts: {
      current: { sha256: SHA_CURRENT, extractor_version: 1, extracted_at: '2026-10-12T00:00:00Z' },
      prior: { sha256: SHA_PRIOR, extractor_version: 1, extracted_at: '2026-10-12T00:00:00Z' },
    },
    engine_version: 1,
    app_version: '1.1.0',
    paragraphs: FULL.paragraphs,
    counts: FULL.counts,
    words: FULL.words,
    items_total: 5,
    labels: { reviewed: 5 - followUps.length, follow_up: followUps.length },
    follow_up_ids: followUps,
  }
}

/** A stand-in for the server: labels accumulate, the fifth completes the review and freezes a receipt;
 *  each answer names whether that label completed the queue (completed_now), as the server does. */
function fakeReviewServer(initial: WordingReviewState = REVIEW) {
  let state = initial
  reviewApi.getWordingReview.mockImplementation(async () => state)
  reviewApi.setWordingLabel.mockImplementation(async (_filingId: number, itemId: string, label: WordingLabel | null) => {
    const labels = { ...state.labels }
    if (label === null) delete labels[itemId]
    else labels[itemId] = label
    const values = Object.values(labels)
    const reviewed = values.filter((value) => value === 'reviewed').length
    const complete = values.length === state.items_total
    const wasComplete = state.completed_at !== null
    state = {
      ...state,
      labels,
      counts: { reviewed, follow_up: values.length - reviewed, unlabeled: state.items_total - values.length },
      completed_at: complete ? '2026-10-13T12:00:00Z' : null,
      receipt: complete ? receiptFor(labels) : null,
    }
    return { ...state, completed_now: complete && !wasComplete }
  })
  return () => state
}

const signedInPro = { ...context, isAuthenticated: true }

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

const toggles = (row: HTMLElement) => within(row).getAllByRole('button')
const pressed = (row: HTMLElement) => toggles(row).map((button) => button.getAttribute('aria-pressed'))
const flush = () => act(() => new Promise((resolve) => setTimeout(resolve, 0)))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('what counts as content', () => {
  it('a wording comparison is content, even with nothing changed; a pending, missing or unsupported one is not', () => {
    expect(reportHasContent(EMPTY_REPORT)).toBe(false)
    expect(reportHasContent({ ...EMPTY_REPORT, section_changes: null })).toBe(false)
    expect(reportHasContent({ ...EMPTY_REPORT, section_changes: FULL })).toBe(true)
    expect(reportHasContent({ ...EMPTY_REPORT, section_changes: NONE })).toBe(true)
    expect(reportHasContent({ ...EMPTY_REPORT, section_changes: PENDING })).toBe(false)
    expect(reportHasContent({ ...EMPTY_REPORT, section_changes: { ...PENDING, status: 'no_prior', reason: 'no_prior' } })).toBe(false)
    expect(reportHasContent({ ...EMPTY_REPORT, section_changes: { ...PENDING, status: 'unavailable', reason: 'form_not_supported' } })).toBe(false)
    expect(reportHasContent(METRICS_REPORT)).toBe(true)
    expect(reportHasContent(null)).toBe(false)
  })

  it('a 10-Q whose risk factors only refer back to the annual report is not a comparison', () => {
    expect(wordingHasContent({ ...FULL, current: { ...SIDE, reference_only: true } })).toBe(false)
    expect(wordingHasContent(FULL)).toBe(true)
  })

  it.each([
    [{ unchanged: 7, modified: 2, added: 1, removed: 1, moved: 1 }, '5 paragraphs changed: 2 modified, 1 added, 1 removed and 1 moved'],
    [{ unchanged: 7, modified: 1, added: 0, removed: 0, moved: 0 }, '1 paragraph changed: 1 modified'],
    [{ unchanged: 7, modified: 0, added: 2, removed: 1, moved: 0 }, '3 paragraphs changed: 2 added and 1 removed'],
  ])('phrases the counts %j as "%s"', (counts, phrase) => {
    expect(changesPhrase(counts)).toBe(phrase)
  })
})

describe('the full list (Pro)', () => {
  it('heads the block one level under the section, states the counts, and lists every change in reading order under its label', () => {
    render(<WordingChanges block={FULL} Heading="h3" context={context} />)
    const heading = screen.getByRole('heading', { level: 3, name: /Risk factor wording/ })
    expect(heading).toHaveTextContent('Item 1A')
    expect(
      screen.getByText('Against the 10-K for the year ended Sep 28, 2024: 5 paragraphs changed: 2 modified, 1 added, 1 removed and 1 moved; 7 unchanged. 14 words added, 9 removed.'),
    ).toBeInTheDocument()
    expect(LABELS(screen.getAllByRole('listitem'))).toEqual(['Modified', 'Added', 'Removed', 'Moved', 'Modified and moved'])
    expect(screen.getByText(/underlined words were added and struck-through words removed/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Upgrade to Pro' })).toBeNull()
    expect(screen.queryByText(/more change/)).toBeNull()
    expect(screen.queryByRole('link', { name: 'Already Pro? Log in' })).toBeNull()
  })

  it('renders a modified paragraph as a redline: inserted words in <ins>, removed words in <del>, each named for assistive tech, in ink and not in a tone', () => {
    render(<WordingChanges block={FULL} Heading="h3" />)
    const [first] = screen.getAllByRole('listitem')
    const ins = first.querySelector('ins') as HTMLElement
    const del = first.querySelector('del') as HTMLElement
    expect(ins).toHaveTextContent('added: several large')
    expect(del).toHaveTextContent('removed: a few')
    expect(ins.querySelector('.sr-only')).toHaveTextContent('added:')
    expect(del.querySelector('.sr-only')).toHaveTextContent('removed:')
    // The paragraph reads straight through: single spaces join the segments, outside the marks.
    expect(first.querySelector('p + p')?.textContent).toBe('Our revenue depends on removed: a few added: several large customers.')
    expect(ins.className).toMatch(/underline/)
    expect(del.className).toMatch(/line-through/)
    for (const mark of [ins, del]) expect(mark.className).not.toMatch(/brand|gain|loss|flat|en-mark/)
  })

  it('wraps a whole added paragraph in <ins> and a removed one in <del>, with no underline or strike, and leaves a moved one plain', () => {
    render(<WordingChanges block={FULL} Heading="h3" />)
    const [, added, removed, moved] = screen.getAllByRole('listitem')
    const addedText = within(added).getByText('We face new risks from export controls.')
    const removedText = within(removed).getByText('Our offices in the region were closed.')
    expect(addedText.tagName).toBe('INS')
    expect(removedText.tagName).toBe('DEL')
    expect(addedText.className).toContain('no-underline')
    expect(removedText.className).toContain('no-underline')
    expect(moved.querySelector('ins, del')).toBeNull()
  })

  it('counts the view once for the form served, with no paywall event', () => {
    const { rerender } = render(<WordingChanges block={FULL} Heading="h3" context={context} />)
    rerender(<WordingChanges block={FULL} Heading="h3" context={context} />)
    expect(mockAnalytics.wordingChangesViewed).toHaveBeenCalledTimes(1)
    expect(mockAnalytics.wordingChangesViewed).toHaveBeenCalledWith({
      filingId: 42, ticker: 'AAPL', filingType: '10-K', access: 'full', status: 'ok', itemsTotal: 5, hasChanges: true,
    })
    expect(mockAnalytics.paywallPromptShown).not.toHaveBeenCalled()
  })

  it('counts the next filing’s view when the mounted block serves it after a client-side navigation', () => {
    const { rerender } = render(<WordingChanges block={FULL} Heading="h3" context={context} />)
    rerender(<WordingChanges block={FULL} Heading="h3" context={{ ...context, filingId: 43, ticker: 'MSFT' }} />)
    rerender(<WordingChanges block={FULL} Heading="h3" context={{ ...context, filingId: 43, ticker: 'MSFT' }} />)
    expect(mockAnalytics.wordingChangesViewed.mock.calls.map(([event]) => event.filingId)).toEqual([42, 43])
  })
})

describe('the teaser (anonymous and Free)', () => {
  it('shows the counts and the first items, says how many more there are, and offers Pro with a sign-in for a signed-out reader', () => {
    render(<WordingChanges block={TEASER} Heading="h3" context={context} />)
    expect(LABELS(screen.getAllByRole('listitem'))).toEqual(['Modified', 'Added', 'Removed'])
    expect(screen.getByText('2 more changes in this section. Pro shows every change.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Upgrade to Pro' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Already Pro? Log in' })).toHaveAttribute('href', '/login')
    expect(mockAnalytics.wordingChangesViewed).toHaveBeenCalledWith(expect.objectContaining({ access: 'teaser', itemsTotal: 5 }))
    expect(mockAnalytics.paywallPromptShown).toHaveBeenCalledTimes(1)
    expect(mockAnalytics.paywallPromptShown).toHaveBeenCalledWith({ filingId: 42, ticker: 'AAPL', filingType: '10-K', entryPoint: 'wording_changes' })
  })

  it('a signed-in Free reader gets the prompt without the sign-in link', () => {
    render(<WordingChanges block={TEASER} Heading="h3" context={{ ...context, isAuthenticated: true }} />)
    expect(screen.getByRole('button', { name: 'Upgrade to Pro' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Already Pro? Log in' })).toBeNull()
  })

  it('the prompt opens the upgrade dialog naming the feature, and counts the click', () => {
    render(<WordingChanges block={TEASER} Heading="h3" context={context} />)
    fireEvent.click(screen.getByRole('button', { name: 'Upgrade to Pro' }))
    const dialog = screen.getByRole('dialog', { name: 'Upgrade to Pro' })
    expect(within(dialog).getByText(/Risk factor wording review is a Pro feature/)).toBeInTheDocument()
    expect(mockAnalytics.paywallCtaClicked).toHaveBeenCalledWith({ filingId: 42, ticker: 'AAPL', filingType: '10-K', entryPoint: 'wording_changes' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Not now' }))
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('a teaser that was not cut has no prompt', () => {
    render(<WordingChanges block={{ ...TEASER, items: ITEMS, truncated: false }} Heading="h3" context={context} />)
    expect(screen.queryByRole('button', { name: 'Upgrade to Pro' })).toBeNull()
    expect(screen.queryByText(/more change/)).toBeNull()
    expect(mockAnalytics.paywallPromptShown).not.toHaveBeenCalled()
  })

  it('counts nothing while the anonymous seed stands in for a signed-in reader, then the form that reader is served', () => {
    const { rerender } = render(<WordingChanges block={TEASER} Heading="h3" context={{ ...context, provisional: true }} />)
    expect(mockAnalytics.wordingChangesViewed).not.toHaveBeenCalled()
    expect(mockAnalytics.paywallPromptShown).not.toHaveBeenCalled()
    rerender(<WordingChanges block={FULL} Heading="h3" context={{ ...context, provisional: false }} />)
    expect(mockAnalytics.wordingChangesViewed).toHaveBeenCalledTimes(1)
    expect(mockAnalytics.wordingChangesViewed).toHaveBeenCalledWith(expect.objectContaining({ access: 'full' }))
    expect(mockAnalytics.paywallPromptShown).not.toHaveBeenCalled()
  })
})

describe('the states', () => {
  it('says plainly when nothing changed, with no list and no prompt, whoever reads it', () => {
    render(<WordingChanges block={NONE} Heading="h3" context={context} />)
    expect(screen.getByText('No wording changes against the 10-K for the year ended Sep 28, 2024 (12 paragraphs compared).')).toBeInTheDocument()
    expect(screen.queryByRole('list')).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
    expect(mockAnalytics.wordingChangesViewed).toHaveBeenCalledWith(expect.objectContaining({ access: 'teaser', hasChanges: false, itemsTotal: 0 }))
    expect(mockAnalytics.paywallPromptShown).not.toHaveBeenCalled()
  })

  it('explains a prior that only referred back to the annual report instead of listing every paragraph as new', () => {
    const restated: SectionChangesOk = {
      ...FULL,
      prior_filing: { ...FULL.prior_filing!, filing_type: '10-Q' },
      prior: { ...SIDE, reference_only: true, paragraph_count: 1 },
      counts: { unchanged: 0, modified: 0, added: 12, removed: 0, moved: 0 },
      items_total: 12,
    }
    render(<WordingChanges block={restated} Heading="h3" context={context} />)
    expect(screen.getByText(/The prior 10-Q only referred back to the annual report’s risk factors/)).toBeInTheDocument()
    expect(screen.getByText(/12 paragraphs read as new\./)).toBeInTheDocument()
    expect(screen.queryByRole('list')).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('names the prior filing by its form alone when its period end is unknown', () => {
    render(<WordingChanges block={{ ...NONE, prior_filing: { ...FULL.prior_filing!, period_end_date: null } }} Heading="h3" />)
    expect(screen.getByText('No wording changes against the prior 10-K (12 paragraphs compared).')).toBeInTheDocument()
  })
})

describe('inside What changed', () => {
  it('renders the report for a wording comparison alone, the block as the only body', () => {
    render(<WhatChanged report={{ ...EMPTY_REPORT, section_changes: FULL }} context={context} />)
    const region = screen.getByRole('region', { name: 'What changed' })
    expect(within(region).getByRole('heading', { level: 3, name: /Risk factor wording/ })).toBeInTheDocument()
    expect(within(region).queryByRole('table')).toBeNull()
    expect(within(region).getByRole('link', { name: /Prior 10-K/ })).toHaveAttribute('href', '/filing/7')
  })

  it('places the block after the metric table, one heading level under the report', () => {
    render(<WhatChanged report={{ ...METRICS_REPORT, section_changes: TEASER }} headingLevel="h3" context={context} />)
    const region = screen.getByRole('region', { name: 'What changed' })
    const table = region.querySelector('table') as HTMLElement
    const heading = within(region).getByRole('heading', { level: 4, name: /Risk factor wording/ })
    expect(table.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(within(region).getByRole('button', { name: 'Upgrade to Pro' })).toBeInTheDocument()
  })

  it('renders nothing for a report with neither figures nor a comparison to show', () => {
    const { container } = render(<WhatChanged report={{ ...EMPTY_REPORT, section_changes: PENDING }} context={context} />)
    expect(container.innerHTML).toBe('')
    expect(mockAnalytics.wordingChangesViewed).not.toHaveBeenCalled()
  })

  it('counts nothing for the landing page sample, which has no viewer context', () => {
    render(<WhatChanged report={{ ...EMPTY_REPORT, section_changes: TEASER }} />)
    expect(screen.getByRole('button', { name: 'Upgrade to Pro' })).toBeInTheDocument()
    expect(mockAnalytics.wordingChangesViewed).not.toHaveBeenCalled()
    expect(mockAnalytics.paywallPromptShown).not.toHaveBeenCalled()
  })
})

describe('the review (Pro, signed in)', () => {
  it('shows no review to a signed-out reader of the full list, nor to the teaser', () => {
    render(<WordingChanges block={FULL} Heading="h3" context={context} />)
    expect(screen.queryByRole('button')).toBeNull()
    expect(screen.queryByTestId('wording-progress')).toBeNull()
    cleanup()
    render(<WordingChanges block={TEASER} Heading="h3" context={signedInPro} />)
    expect(screen.queryByRole('button', { name: /Reviewed/ })).toBeNull()
    expect(reviewApi.getWordingReview).not.toHaveBeenCalled()
  })

  it('every change carries two pressed-state toggles; a press marks it, counts the progress and the event, and a second press clears it', async () => {
    fakeReviewServer()
    renderWithClient(<WordingChanges block={FULL} Heading="h3" context={signedInPro} />)
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('0 of 5 changes marked.'))
    const rows = screen.getAllByRole('listitem')
    expect(toggles(rows[0]).map((button) => button.textContent)).toEqual(['Reviewed', 'Follow up'])
    expect(toggles(rows[0])[0]).toHaveAccessibleName('Reviewed: change 1 of 5')
    expect(pressed(rows[0])).toEqual(['false', 'false'])

    fireEvent.click(toggles(rows[0])[0])
    await waitFor(() => expect(pressed(rows[0])).toEqual(['true', 'false']))
    await waitFor(() => expect(reviewApi.setWordingLabel).toHaveBeenCalledWith(42, 'a1', 'reviewed'))
    await waitFor(() => expect(mockAnalytics.wordingChangeLabeled).toHaveBeenCalledWith({ filingId: 42, ticker: 'AAPL', filingType: '10-K', label: 'reviewed', kind: 'modified' }))
    expect(screen.getByTestId('wording-progress')).toHaveTextContent('1 of 5 changes marked.')

    fireEvent.click(toggles(rows[1])[1])
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('2 of 5 changes marked, 1 to follow up.'))
    expect(pressed(rows[1])).toEqual(['false', 'true'])

    // Reviewed replaces Follow up on the same change; pressing the set one again clears it.
    fireEvent.click(toggles(rows[1])[0])
    await waitFor(() => expect(pressed(rows[1])).toEqual(['true', 'false']))
    fireEvent.click(toggles(rows[1])[0])
    await waitFor(() => expect(reviewApi.setWordingLabel).toHaveBeenLastCalledWith(42, 'a2', null))
    await waitFor(() => expect(pressed(rows[1])).toEqual(['false', 'false']))
    expect(screen.getByTestId('wording-progress')).toHaveTextContent('1 of 5 changes marked.')
    expect(mockAnalytics.wordingReviewCompleted).not.toHaveBeenCalled()
  })

  it('j and k move between changes, 1 marks the focused one reviewed and 2 flags it, as toggles', async () => {
    fakeReviewServer()
    renderWithClient(<WordingChanges block={FULL} Heading="h3" context={signedInPro} />)
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('0 of 5'))
    const rows = screen.getAllByRole('listitem')
    expect(screen.getByRole('list')).toHaveAttribute('aria-keyshortcuts', 'j k 1 2')

    toggles(rows[0])[0].focus()
    // A handled key is claimed (preventDefault: the dispatch returns false); fireEvent returns that.
    expect(fireEvent.keyDown(toggles(rows[0])[0], { key: 'j' })).toBe(false)
    expect(rows[1]).toHaveFocus()
    expect(fireEvent.keyDown(rows[1], { key: '1' })).toBe(false)
    await waitFor(() => expect(reviewApi.setWordingLabel).toHaveBeenLastCalledWith(42, 'a2', 'reviewed'))
    await waitFor(() => expect(pressed(rows[1])).toEqual(['true', 'false']))
    // A held key repeats the event; the repeats mark nothing (one press, one toggle).
    expect(fireEvent.keyDown(rows[1], { key: '1', repeat: true })).toBe(false)
    await flush()
    expect(reviewApi.setWordingLabel).toHaveBeenCalledTimes(1)

    fireEvent.keyDown(rows[1], { key: 'ArrowDown' })
    expect(rows[2]).toHaveFocus()
    fireEvent.keyDown(rows[2], { key: '2' })
    await waitFor(() => expect(pressed(rows[2])).toEqual(['false', 'true']))
    fireEvent.keyDown(rows[2], { key: '2' })
    await waitFor(() => expect(reviewApi.setWordingLabel).toHaveBeenLastCalledWith(42, 'a3', null))

    fireEvent.keyDown(rows[2], { key: 'k' })
    expect(rows[1]).toHaveFocus()
    fireEvent.keyDown(rows[1], { key: 'k' })
    expect(rows[0]).toHaveFocus()
    fireEvent.keyDown(rows[0], { key: 'k' })
    expect(rows[0]).toHaveFocus()
    // The last row is the end of the list; a modifier leaves the key to the browser (not claimed).
    rows[4].focus()
    fireEvent.keyDown(rows[4], { key: 'j' })
    expect(rows[4]).toHaveFocus()
    expect(fireEvent.keyDown(rows[4], { key: '1', ctrlKey: true })).toBe(true)
    expect(fireEvent.keyDown(rows[4], { key: 'x' })).toBe(true)
    await flush()
    expect(reviewApi.setWordingLabel).not.toHaveBeenCalledWith(42, 'a5', 'reviewed')
  })

  it('labels are sent one at a time, in press order, so an earlier answer never lands over a later press', async () => {
    fakeReviewServer()
    const answers: Array<(state: WordingReviewState) => void> = []
    reviewApi.setWordingLabel.mockImplementation(
      (_filingId: number, _itemId: string, _label: WordingLabel | null) =>
        new Promise<WordingReviewState>((resolve) => {
          answers.push(resolve)
        }),
    )
    renderWithClient(<WordingChanges block={FULL} Heading="h3" context={signedInPro} />)
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('0 of 5'))
    const rows = screen.getAllByRole('listitem')
    fireEvent.click(toggles(rows[0])[0])
    fireEvent.click(toggles(rows[1])[1])
    // Both rows flip at once; only the first label is in flight until it is answered.
    await waitFor(() => expect(pressed(rows[1])).toEqual(['false', 'true']))
    expect(pressed(rows[0])).toEqual(['true', 'false'])
    await flush()
    expect(reviewApi.setWordingLabel).toHaveBeenCalledTimes(1)
    expect(reviewApi.setWordingLabel).toHaveBeenCalledWith(42, 'a1', 'reviewed')
    await act(async () => answers[0]({ ...REVIEW, labels: { a1: 'reviewed' }, counts: { reviewed: 1, follow_up: 0, unlabeled: 4 }, completed_now: false }))
    await waitFor(() => expect(reviewApi.setWordingLabel).toHaveBeenCalledTimes(2))
    expect(reviewApi.setWordingLabel).toHaveBeenLastCalledWith(42, 'a2', 'follow_up')
    await act(async () => answers[1]({ ...REVIEW, labels: { a1: 'reviewed', a2: 'follow_up' }, counts: { reviewed: 1, follow_up: 1, unlabeled: 3 }, completed_now: false }))
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('2 of 5 changes marked, 1 to follow up.'))
    expect(mockAnalytics.wordingReviewCompleted).not.toHaveBeenCalled()
  })

  it('the completion event follows the server’s transition, not the client’s guess', async () => {
    fakeReviewServer({ ...REVIEW, labels: { a1: 'reviewed', a2: 'reviewed', a3: 'reviewed', a4: 'reviewed' }, counts: { reviewed: 4, follow_up: 0, unlabeled: 1 } })
    renderWithClient(<WordingChanges block={FULL} Heading="h3" context={signedInPro} />)
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('4 of 5 changes marked.'))
    const rows = screen.getAllByRole('listitem')
    fireEvent.click(toggles(rows[4])[0])
    await waitFor(() => expect(mockAnalytics.wordingReviewCompleted).toHaveBeenCalledTimes(1))
    // The server answers a relabel while complete with completed_now false: no second event, whatever
    // the cache held when the press was made.
    fireEvent.click(toggles(rows[0])[1])
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('All 5 changes marked, 1 to follow up. Receipt below.'))
    expect(mockAnalytics.wordingReviewCompleted).toHaveBeenCalledTimes(1)
    // An answer that says the queue was completed by this label counts, and only that answer does.
    reviewApi.setWordingLabel.mockResolvedValueOnce({ ...REVIEW, labels: { a1: 'reviewed', a2: 'reviewed', a3: 'reviewed', a4: 'reviewed', a5: 'reviewed' }, counts: { reviewed: 5, follow_up: 0, unlabeled: 0 }, completed_at: '2026-10-13T13:00:00Z', receipt: receiptFor({ a1: 'reviewed', a2: 'reviewed', a3: 'reviewed', a4: 'reviewed', a5: 'reviewed' }), completed_now: true })
    fireEvent.click(toggles(rows[0])[0])
    await waitFor(() => expect(mockAnalytics.wordingReviewCompleted).toHaveBeenCalledTimes(2))
  })

  it('the last label completes the review: the receipt names the two texts, the event fires once, and the receipt copies as text', async () => {
    const server = fakeReviewServer({ ...REVIEW, labels: { a1: 'reviewed', a2: 'reviewed', a3: 'follow_up', a4: 'reviewed' }, counts: { reviewed: 3, follow_up: 1, unlabeled: 1 } })
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })
    renderWithClient(<WordingChanges block={FULL} Heading="h3" context={signedInPro} />)
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('4 of 5 changes marked, 1 to follow up.'))
    expect(screen.queryByTestId('wording-receipt')).toBeNull()

    fireEvent.click(toggles(screen.getAllByRole('listitem')[4])[0])
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('All 5 changes marked, 1 to follow up. Receipt below.'))
    const receipt = screen.getByTestId('wording-receipt')
    expect(receipt).toHaveTextContent('Review receipt')
    expect(receipt).toHaveTextContent('10-K current-annual-report (period ended 2025-09-27, filed 2025-10-31)')
    expect(receipt).toHaveTextContent('10-K prior-annual-report (period ended 2024-09-28, filed 2024-11-01)')
    expect(receipt).toHaveTextContent(`${'c'.repeat(12)}… / ${'p'.repeat(12)}…`)
    expect(receipt).toHaveTextContent('extractor v1 / v1, engine v1, app 1.1.0')
    expect(receipt).toHaveTextContent('4 reviewed, 1 to follow up')
    expect(mockAnalytics.wordingReviewCompleted).toHaveBeenCalledTimes(1)
    expect(mockAnalytics.wordingReviewCompleted).toHaveBeenCalledWith({ filingId: 42, ticker: 'AAPL', filingType: '10-K', itemsTotal: 5, followUps: 1 })

    fireEvent.click(within(receipt).getByRole('button', { name: 'Copy receipt' }))
    await waitFor(() => expect(within(receipt).getByRole('status')).toHaveTextContent('Receipt copied.'))
    const text = writeText.mock.calls[0][0] as string
    expect(text).toBe(receiptText(server()))
    expect(text.split('\n')[0]).toBe('EarningsNerd review receipt')
    expect(text).toContain(`Text SHA-256: current ${SHA_CURRENT}; prior ${SHA_PRIOR}`)
    expect(text).toContain('Paragraphs: 5 paragraphs changed: 2 modified, 1 added, 1 removed and 1 moved; 7 unchanged')
    expect(text).toContain('Follow-up change ids: a3')
    expect(text).toContain('Completed: 2026-10-13T12:00:00Z')
    expect(mockAnalytics.wordingReceiptCopied).toHaveBeenCalledWith({ filingId: 42, ticker: 'AAPL', filingType: '10-K' })

    // A label changed while the queue stays complete does not complete it again.
    fireEvent.click(toggles(screen.getAllByRole('listitem')[0])[1])
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('All 5 changes marked, 2 to follow up. Receipt below.'))
    expect(mockAnalytics.wordingReviewCompleted).toHaveBeenCalledTimes(1)
  })

  it('a label the server refuses is rolled back, and a receipt the server does not send is not shown', async () => {
    fakeReviewServer()
    let reject: (error: Error) => void = () => {}
    reviewApi.setWordingLabel.mockImplementation(() => new Promise<WordingReviewState>((_resolve, r) => { reject = r }))
    renderWithClient(<WordingChanges block={FULL} Heading="h3" context={signedInPro} />)
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('0 of 5'))
    const [first] = screen.getAllByRole('listitem')
    fireEvent.click(toggles(first)[0])
    // The row flips as it is pressed, before the server answers.
    await waitFor(() => expect(pressed(first)).toEqual(['true', 'false']))
    expect(screen.getByTestId('wording-progress')).toHaveTextContent('1 of 5 changes marked.')
    await act(async () => reject(new Error('offline')))
    await waitFor(() => expect(pressed(first)).toEqual(['false', 'false']))
    expect(screen.getByTestId('wording-progress')).toHaveTextContent('0 of 5 changes marked.')
    expect(mockAnalytics.wordingChangeLabeled).not.toHaveBeenCalled()
    expect(screen.queryByTestId('wording-receipt')).toBeNull()
  })

  it('a label that settles after the account changed writes nothing back, so the next account never sees it', async () => {
    // The reader has one change flagged; they press another, then log out (or another account signs
    // in) and leave the page before the server answers. resetAccountQueries removed the family; the
    // late answer must not recreate it with the last account's labels, and nothing counts the label.
    const theirs: WordingReviewState = { ...REVIEW, labels: { a3: 'follow_up' }, counts: { reviewed: 0, follow_up: 1, unlabeled: 4 } }
    fakeReviewServer(theirs)
    let resolve: (state: WordingReviewState & { completed_now: boolean }) => void = () => {}
    reviewApi.setWordingLabel.mockImplementation(() => new Promise((r) => { resolve = r }))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    const { unmount } = render(<QueryClientProvider client={client}><WordingChanges block={FULL} Heading="h3" context={signedInPro} /></QueryClientProvider>)
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('1 of 5'))
    const [first] = screen.getAllByRole('listitem')
    fireEvent.click(toggles(first)[0])
    await waitFor(() => expect(pressed(first)).toEqual(['true', 'false']))
    act(() => resetAccountQueries(client))
    unmount()
    expect(client.getQueryData(queryKeys.wordingReview.byFiling(42))).toBeUndefined()
    await act(async () => resolve({ ...theirs, labels: { a1: 'reviewed', a3: 'follow_up' }, counts: { reviewed: 1, follow_up: 1, unlabeled: 3 }, completed_now: false }))
    await flush()
    expect(client.getQueryData(queryKeys.wordingReview.byFiling(42))).toBeUndefined()
    expect(mockAnalytics.wordingChangeLabeled).not.toHaveBeenCalled()
  })

  it('a label the server refuses after the account changed rolls nothing back either', async () => {
    const theirs: WordingReviewState = { ...REVIEW, labels: { a3: 'follow_up' }, counts: { reviewed: 0, follow_up: 1, unlabeled: 4 } }
    fakeReviewServer(theirs)
    let reject: (error: Error) => void = () => {}
    reviewApi.setWordingLabel.mockImplementation(() => new Promise<WordingReviewState>((_resolve, r) => { reject = r }))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    const { unmount } = render(<QueryClientProvider client={client}><WordingChanges block={FULL} Heading="h3" context={signedInPro} /></QueryClientProvider>)
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('1 of 5'))
    const [first] = screen.getAllByRole('listitem')
    fireEvent.click(toggles(first)[0])
    await waitFor(() => expect(pressed(first)).toEqual(['true', 'false']))
    act(() => resetAccountQueries(client))
    unmount()
    await act(async () => reject(new Error('offline')))
    await flush()
    expect(client.getQueryData(queryKeys.wordingReview.byFiling(42))).toBeUndefined()
  })

  it('the toggles wait for the review read, and a review the server has nothing for leaves the list plain and re-reads the report', async () => {
    let resolve: (state: WordingReviewState) => void = () => {}
    reviewApi.getWordingReview.mockImplementation(() => new Promise<WordingReviewState>((r) => { resolve = r }))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    // The block on the page came from the what-changed read; a review that finds no comparison means
    // that read is stale, so the block is re-read (invalidated) against the live state.
    client.setQueryData(['what-changed', 42, 7], { ...EMPTY_REPORT, section_changes: FULL })
    render(
      <QueryClientProvider client={client}>
        <WordingChanges block={FULL} Heading="h3" context={signedInPro} />
      </QueryClientProvider>,
    )
    expect(screen.getByTestId('wording-progress')).toHaveTextContent('Loading your review…')
    const [first] = screen.getAllByRole('listitem')
    expect(toggles(first)[0]).toBeDisabled()
    expect(screen.getByText(/Keys: j and k/)).toBeInTheDocument()
    await act(async () => resolve({ ...REVIEW, status: 'unavailable', items_total: 0 }))
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('This review isn’t available for this comparison yet.'))
    expect(screen.queryByRole('button')).toBeNull()
    expect(screen.queryByText(/Keys: j and k/)).toBeNull()
    expect(screen.getAllByRole('listitem')).toHaveLength(5)
    expect(client.getQueryState(['what-changed', 42, 7])?.isInvalidated).toBe(true)
  })

  it('a review read that fails shows the failure with a Retry over the plain list, and the retry restores the toggles', async () => {
    const server = fakeReviewServer()
    reviewApi.getWordingReview.mockRejectedValueOnce(new Error('offline'))
    renderWithClient(<WordingChanges block={FULL} Heading="h3" context={signedInPro} />)
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('Your review didn’t load.'))
    const alert = screen.getByRole('alert')
    expect(alert).toHaveTextContent('Couldn’t load your review')
    expect(screen.getAllByRole('listitem')).toHaveLength(5)
    expect(screen.queryByRole('button', { name: /Reviewed: change/ })).toBeNull()
    const retry = within(alert).getByRole('button', { name: 'Retry' })
    expect(retry).not.toBeDisabled()
    fireEvent.click(retry)
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('0 of 5 changes marked.'))
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getAllByRole('button', { name: /Reviewed: change/ })).toHaveLength(5)
    expect(server().labels).toEqual({})
  })

  it('every change marked but no receipt: the text was re-read since, and one more mark issues a new receipt', async () => {
    const all: Record<string, WordingLabel> = { a1: 'reviewed', a2: 'reviewed', a3: 'follow_up', a4: 'reviewed', a5: 'reviewed' }
    fakeReviewServer({ ...REVIEW, labels: all, counts: { reviewed: 4, follow_up: 1, unlabeled: 0 }, completed_at: null, receipt: null })
    renderWithClient(<WordingChanges block={FULL} Heading="h3" context={signedInPro} />)
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('All 5 changes marked, 1 to follow up. No current receipt.'))
    expect(screen.queryByTestId('wording-receipt')).toBeNull()
    const reread = screen.getByTestId('wording-reread')
    expect(reread).toHaveTextContent('The filing text was re-read since your receipt')
    fireEvent.click(within(reread).getByRole('button', { name: 'Issue a new receipt' }))
    await waitFor(() => expect(reviewApi.setWordingLabel).toHaveBeenCalledWith(42, 'a1', 'reviewed'))
    await waitFor(() => expect(screen.getByTestId('wording-progress')).toHaveTextContent('All 5 changes marked, 1 to follow up. Receipt below.'))
    expect(screen.getByTestId('wording-receipt')).toBeInTheDocument()
    expect(screen.queryByTestId('wording-reread')).toBeNull()
    expect(mockAnalytics.wordingReviewCompleted).toHaveBeenCalledTimes(1)
  })
})

describe('the seed standing in for a signed-in reader', () => {
  it('withholds the teaser’s prompt while the seed stands in for a signed-in reader, and shows it to a signed-out one', () => {
    const { rerender } = render(<WordingChanges block={TEASER} Heading="h3" context={{ ...context, isAuthenticated: true, provisional: true }} />)
    expect(screen.queryByRole('button', { name: 'Upgrade to Pro' })).toBeNull()
    expect(screen.queryByText(/more change/)).toBeNull()
    expect(screen.getAllByRole('listitem')).toHaveLength(3)
    // Their own read settles on the teaser: a Free reader, so the prompt shows.
    rerender(<WordingChanges block={TEASER} Heading="h3" context={{ ...context, isAuthenticated: true, provisional: false }} />)
    expect(screen.getByRole('button', { name: 'Upgrade to Pro' })).toBeInTheDocument()
    cleanup()
    render(<WordingChanges block={TEASER} Heading="h3" context={{ ...context, isAuthenticated: false, provisional: true }} />)
    expect(screen.getByRole('button', { name: 'Upgrade to Pro' })).toBeInTheDocument()
  })
})
