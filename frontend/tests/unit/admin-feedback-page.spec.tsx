import React from 'react'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock the admin API module so the page renders without real network calls.
vi.mock('@/features/admin/api/admin-api', () => ({
  listFeedback: vi.fn(),
  updateFeedbackStatus: vi.fn(),
}))

// sonner's Toaster is rendered globally in the real app, not here; stub toast calls.
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import AdminFeedbackPage from '@/app/admin/feedback/page'
import {
  listFeedback,
  updateFeedbackStatus,
  type FeedbackRecord,
} from '@/features/admin/api/admin-api'

const bugReport: FeedbackRecord = {
  id: 1,
  user_id: 42,
  user_email: 'alice@example.com',
  type: 'bug',
  message: 'The summary export button does nothing on Safari.',
  page_url: '/filing/123',
  status: 'new',
  created_at: '2026-06-20T00:00:00Z',
}

const featureRequest: FeedbackRecord = {
  id: 2,
  user_id: null,
  user_email: null,
  type: 'feature',
  message: 'Please add CSV download for the peers table.',
  page_url: null,
  status: 'triaged',
  created_at: '2026-06-21T00:00:00Z',
}

/** The page's heading outline: SecondaryHeader's h1 first, then the sections, never skipping a level. */
function expectOutline(h1: string) {
  const headings = screen.getAllByRole('heading')
  expect(headings[0]).toHaveTextContent(h1)
  const levels = headings.map((h) => Number(h.tagName.slice(1)))
  expect(levels[0]).toBe(1)
  expect(levels.filter((level) => level === 1)).toHaveLength(1)
  levels.slice(1).forEach((level, i) => expect(level).toBeLessThanOrEqual(levels[i] + 1))
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <AdminFeedbackPage />
    </QueryClientProvider>,
  )
}

describe('AdminFeedbackPage', () => {
  beforeEach(() => {
    vi.mocked(listFeedback).mockReset()
    vi.mocked(updateFeedbackStatus).mockReset()
  })

  it('renders feedback rows once the query resolves', async () => {
    vi.mocked(listFeedback).mockResolvedValue([bugReport, featureRequest])
    renderPage()

    expect(screen.getByRole('heading', { name: 'Feedback', level: 2 })).toBeInTheDocument()
    expectOutline('Feedback')

    // Both rows populate once the query resolves.
    expect(await screen.findByText(bugReport.message)).toBeInTheDocument()
    expect(screen.getByText(featureRequest.message)).toBeInTheDocument()
    // The user email shows for the identified reporter; anonymous shows for the null one.
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
    expect(screen.getByText('Anonymous')).toBeInTheDocument()
  })

  it('shows the empty state when there is no feedback', async () => {
    vi.mocked(listFeedback).mockResolvedValue([])
    renderPage()
    // One plain line in the card (ADM-08, ADM-10): no title, no nested GuidanceCard.
    const empty = await screen.findByText(/No feedback yet/i)
    expect(empty).toHaveAttribute('role', 'status')
    expect(empty).toHaveTextContent(/^No feedback yet\. Reports appear here as people send them\.$/)
    expect(screen.queryByText(/No Feedback Found/i)).not.toBeInTheDocument()
  })

  it('shows a load failure as a Notice with a Retry that refetches (ADM-12)', async () => {
    vi.mocked(listFeedback).mockRejectedValueOnce(new Error('network')).mockResolvedValue([bugReport])
    renderPage()
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Could not load the feedback.')
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText(bugReport.message)).toBeInTheDocument()
    expect(listFeedback).toHaveBeenCalledTimes(2)
  })

  it('changing a row status calls updateFeedbackStatus', async () => {
    vi.mocked(listFeedback).mockResolvedValue([bugReport])
    vi.mocked(updateFeedbackStatus).mockResolvedValue({ ...bugReport, status: 'resolved' })
    renderPage()

    await screen.findByText(bugReport.message)

    const statusSelect = screen.getByLabelText(`Set status for feedback ${bugReport.id}`)
    fireEvent.change(statusSelect, { target: { value: 'resolved' } })

    await waitFor(() => {
      expect(vi.mocked(updateFeedbackStatus)).toHaveBeenCalledWith(bugReport.id, 'resolved')
    })
  })
})

/**
 * The filter row shrinks with its card (DESIGN_SYSTEM.md §4 "Admin pages"; the chief designer's review of #1344: at
 * 320px under 200% text the row grew to its 255px status select inside a 158px header and took the page to 336px).
 * jsdom lays nothing out, so this pins the class; tests/e2e/admin-invite-chip-reflow.spec.ts measures the page.
 */
describe('AdminFeedbackPage: the filters stay inside the card', () => {
  it('lets the filter row shrink below its selects and wrap them, as the invites page does', async () => {
    vi.mocked(listFeedback).mockResolvedValue([bugReport])
    renderPage()
    await screen.findByText(bugReport.message)
    const row = screen.getByLabelText('Filter by status').parentElement!
    expect(row).toContainElement(screen.getByLabelText('Filter by type'))
    expect(row).toHaveClass('min-w-0', 'flex-wrap')
  })
})

/**
 * The table scrolls inside its card, never the page (DESIGN_SYSTEM.md §4 "Admin pages"; the #1309 capture review at
 * 390 found the page 1090px wide and, at 1440, the status selects cut off at the card's edge). Classes are what a
 * unit test can pin; the capture harness measures the layout they make in a real browser.
 */
describe('AdminFeedbackPage: the table scrolls inside its card', () => {
  afterEach(() => vi.restoreAllMocks())

  it("holds the table and its rows' visually hidden labels in a positioned scroll box", async () => {
    vi.mocked(listFeedback).mockResolvedValue([bugReport, featureRequest])
    renderPage()
    const box = (await screen.findByText(bugReport.message)).closest('table')!.parentElement!
    // Each row's status label is sr-only, so position: absolute. Unless the box is its containing block (relative),
    // the label is laid out against the page, outside the box's clip, and the page scrolls sideways to it.
    expect(within(box).getByText(`Set status for feedback ${bugReport.id}`)).toHaveClass('sr-only')
    expect(box).toHaveClass('relative', 'overflow-x-auto')
    // A table that fits says nothing and adds no Tab stop.
    expect(box).not.toHaveAttribute('role')
    expect(box).not.toHaveAttribute('tabindex')
    expect(screen.queryByText('Scroll horizontally to read all columns.')).not.toBeInTheDocument()
  })

  it('gives the message column the width the other columns leave, so the status select keeps its own', async () => {
    vi.mocked(listFeedback).mockResolvedValue([bugReport])
    renderPage()
    const message = await screen.findByRole('button', { name: bugReport.message })
    // w-full takes the rest of the row; a max-width here instead held the column at the message's own width.
    const cell = message.closest('td')!
    expect(cell).toHaveClass('w-full')
    expect(cell.className).not.toMatch(/(^|\s)max-w-/)
    // A one-line (truncate) message would size the column by its whole text: its intrinsic width is contained,
    // with a 16rem floor for the phone's scrolling table.
    expect(message).toHaveClass('[contain:inline-size]', 'min-w-64', 'truncate')
  })

  it("never cuts a reporter's address: a long one wraps inside its cell within 14rem", async () => {
    const longAddress = { ...bugReport, user_email: 'maximilian.featherstonehaugh@exampleenterprise.com' }
    vi.mocked(listFeedback).mockResolvedValue([longAddress, featureRequest])
    renderPage()
    const address = await screen.findByText(longAddress.user_email)
    // A nowrap cell sized the column by the whole address: at 1440, 50 characters took the table to 1264px in its
    // 1214px box (the chief designer's review of #1344, which ruled out truncating it).
    expect(address.closest('td')!.className).not.toMatch(/(^|\s)(whitespace-nowrap|truncate)(\s|$)/)
    // Its own width up to the cap, wrapping anywhere past it. The cap is on a block inside the cell: the message
    // column's w-full holds this one at its narrowest, where wrapping on the cell broke a short address every few
    // letters.
    expect(address).toHaveClass('block', 'w-max', 'max-w-[14rem]', '[overflow-wrap:anywhere]')
    expect(address).not.toHaveClass('truncate')
    expect(screen.getByText('Anonymous').parentElement).toHaveClass('block', 'w-max', 'max-w-[14rem]')
  })

  it('says the table scrolls, and makes it a named keyboard region, while it is wider than its box', async () => {
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(() => 356)
    vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(() => 1177)
    vi.mocked(listFeedback).mockResolvedValue([bugReport])
    renderPage()
    const region = await screen.findByRole('region', { name: 'Scrollable table: Feedback' })
    expect(region).toContainElement(screen.getByText(bugReport.message))
    expect(region).toHaveAttribute('tabindex', '0')
    expect(region).toHaveAccessibleDescription('Scroll horizontally to read all columns.')
    expect(region).toHaveClass('focus-visible:shadow-ring-brand', 'dark:focus-visible:shadow-ring-brand-dark')
  })
})
