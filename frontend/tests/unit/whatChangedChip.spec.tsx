import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import type { FeedItem, WhatChangedItem } from '@/features/dashboard/api/dashboard-api'
import WhatChangedCard from '@/features/dashboard/components/WhatChangedCard'
import { directionChip } from '@/lib/financialTone'

/**
 * The what-changed chip on the dashboard feed (audit DSW-08, filing/F03; D-030, DESIGN.md "Separate
 * Signals"). Its glyph is picked from a map and drawn as `<Icon />`, a variable earningsnerd/direction-
 * text-tokens cannot follow (the rule's header lists it as a known limit), so this spec holds the chip:
 * - the colour is directionChip for the TONE the server sent with the signed display string, not for the
 *   direction (costs that rose are a loss: tone 'loss', direction 'up');
 * - the glyph follows the DIRECTION and is aria-hidden;
 * - a figure carries the direction in its sign, so the sr-only word appears only when no figure shows;
 * - the figure is in the data face.
 */

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))
vi.mock('@/lib/analytics', () => ({ default: { dashboardFeedClicked: vi.fn() } }))
vi.mock('@/components/CompanyLogo', () => ({ default: () => null }))
vi.mock('@/lib/icons', async (importOriginal) => {
  const glyph = (name: string) => {
    const Glyph = (props: Record<string, unknown>) => <svg data-glyph={name} {...props} />
    Glyph.displayName = `Glyph(${name})`
    return Glyph
  }
  return {
    ...(await importOriginal<typeof import('@/lib/icons')>()),
    TrendUpIcon: glyph('up'),
    TrendDownIcon: glyph('down'),
    MinusIcon: glyph('flat'),
  }
})

const metric = (over: Partial<WhatChangedItem>): WhatChangedItem => ({
  metric: 'revenue', label: 'Revenue', direction: 'up', pct: 6.4, current: 416_161, prior: 391_035,
  display: '+6.4%', tone: 'gain', ...over,
})

const feedItem = (items: WhatChangedItem[]): FeedItem => ({
  filing_id: 11, accession_number: null, company: { id: 7, ticker: 'AAPL', name: 'Apple Inc.' },
  filing_type: '10-K', filing_date: '2025-10-31', period_end_date: '2025-09-27', summary_id: 3,
  summary_status: 'ready', what_changed: { items, data_quality: 'ok' },
})

/** The chip that holds `label`: the span the card draws per metric. */
const chipOf = (label: string) => screen.getByText(label, { selector: 'span.rounded-full' }) as HTMLElement

afterEach(cleanup)

describe('the what-changed chip', () => {
  it('takes its colour from the tone the server sent, its glyph from the direction', () => {
    render(
      <WhatChangedCard
        item={feedItem([
          metric({}),
          metric({ metric: 'opex', label: 'Operating expenses', direction: 'up', display: '+8.1%', tone: 'loss' }),
          metric({ metric: 'ni', label: 'Net income', direction: 'down', display: '−3.0%', tone: 'loss' }),
          metric({ metric: 'eps', label: 'EPS', direction: 'flat', display: '0.0%', tone: 'flat' }),
        ])}
      />,
    )
    const cases: Array<[string, keyof typeof directionChip, string]> = [
      ['Revenue', 'up', 'up'],
      ['Operating expenses', 'down', 'up'],
      ['Net income', 'down', 'down'],
      ['EPS', 'flat', 'flat'],
    ]
    for (const [label, tone, glyph] of cases) {
      const chip = chipOf(label)
      for (const token of directionChip[tone].split(' ')) expect(chip.classList).toContain(token)
      expect(chip.className).not.toMatch(/(^|\s|:)(text|bg)-brand/)
      const icon = chip.querySelector('svg[data-glyph]')
      expect(icon?.getAttribute('data-glyph')).toBe(glyph)
      expect(icon?.getAttribute('aria-hidden')).toBe('true')
    }
  })

  it('shows the figure in the data face, with no sr-only word beside it', () => {
    render(<WhatChangedCard item={feedItem([metric({})])} />)
    const chip = chipOf('Revenue')
    const figure = screen.getByText('+6.4%')
    expect(chip).toContainElement(figure)
    expect(figure).toHaveClass('font-data')
    expect(chip.querySelector('.sr-only')).toBeNull()
  })

  it('says the direction to a screen reader when no figure shows, and nothing for flat', () => {
    render(
      <WhatChangedCard
        item={feedItem([
          metric({ display: '' }),
          metric({ metric: 'ni', label: 'Net income', direction: 'down', display: '', tone: 'loss' }),
          metric({ metric: 'eps', label: 'EPS', direction: 'flat', display: '0.0%', tone: 'flat' }),
        ])}
      />,
    )
    expect(chipOf('Revenue').querySelector('.sr-only')?.textContent?.trim()).toBe('up')
    expect(chipOf('Net income').querySelector('.sr-only')?.textContent?.trim()).toBe('down')
    expect(chipOf('EPS').querySelector('.sr-only')).toBeNull()
    expect(chipOf('EPS').querySelector('.font-data')).toBeNull()
  })
})
