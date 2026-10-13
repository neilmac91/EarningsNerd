import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import WhatChangedCard, { wordingLine } from '@/features/dashboard/components/WhatChangedCard'
import type { FeedItem } from '@/features/dashboard/api/dashboard-api'

/**
 * The dashboard feed card's one line on the risk factors' wording (E17, PR B): the Compare periods
 * card's words for the counts, then the Pro reader's own progress through the change queue. Nothing
 * when the filing has no comparison yet, or its own section only refers back to the annual report.
 */

vi.mock('@/lib/analytics', () => ({ default: { dashboardFeedClicked: vi.fn() } }))
vi.mock('@/components/CompanyLogo', () => ({ default: () => null }))
vi.mock('next/link', () => ({ default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a> }))

const ITEM: FeedItem = {
  filing_id: 42,
  accession_number: 'current-annual-report',
  company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.' },
  filing_type: '10-K',
  filing_date: '2025-10-31T00:00:00+00:00',
  period_end_date: '2025-09-27T00:00:00+00:00',
  summary_id: 7,
  summary_status: 'ready',
  what_changed: null,
  wording_changes: { items_total: 12, has_changes: true, reference_only: false, prior_reference_only: false, review: null },
}

afterEach(cleanup)

describe('the wording line', () => {
  it.each([
    [null, null],
    [undefined, null],
    [{ ...ITEM.wording_changes!, reference_only: true }, null],
    [{ ...ITEM.wording_changes!, prior_reference_only: true }, 'Risk factors restated in full.'],
    [{ ...ITEM.wording_changes!, has_changes: false, items_total: 0 }, 'No wording changes in the risk factors.'],
    [ITEM.wording_changes!, '12 paragraphs of risk factors changed.'],
    [{ ...ITEM.wording_changes!, items_total: 1 }, '1 paragraph of risk factors changed.'],
    [{ ...ITEM.wording_changes!, review: { labeled: 0, completed_at: null } }, '12 paragraphs of risk factors changed.'],
    [{ ...ITEM.wording_changes!, review: { labeled: 3, completed_at: null } }, '12 paragraphs of risk factors changed. 3 of 12 marked.'],
    [{ ...ITEM.wording_changes!, review: { labeled: 12, completed_at: '2026-10-13T12:00:00Z' } }, '12 paragraphs of risk factors changed. Reviewed.'],
  ])('reads %j as %j', (wording, line) => {
    expect(wordingLine(wording)).toBe(line)
  })

  it('sits under the figures on the card, in the muted data line, and is absent without a comparison', () => {
    render(<WhatChangedCard item={{ ...ITEM, wording_changes: { ...ITEM.wording_changes!, review: { labeled: 3, completed_at: null } } }} />)
    const line = screen.getByText('12 paragraphs of risk factors changed. 3 of 12 marked.')
    expect(line.className).toMatch(/text-xs/)
    expect(line.className).toMatch(/tnum/)
    cleanup()
    render(<WhatChangedCard item={{ ...ITEM, wording_changes: null }} />)
    expect(screen.queryByText(/risk factors/)).toBeNull()
    cleanup()
    render(<WhatChangedCard item={{ ...ITEM, wording_changes: undefined }} />)
    expect(screen.queryByText(/risk factors/)).toBeNull()
  })
})
