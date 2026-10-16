import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EventRow } from '@/features/calendar/components/EventRow'
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'
import type { EarningsAlertsApi } from '@/features/calendar/hooks/useCalendar'
import * as icons from '@/lib/icons'

/**
 * A calendar row marks nothing beyond its status (audit CAL-10). The flame that used to sit beside a
 * ticker scoring 93 or more painted the warning colour, a status colour, on a ranking the day's order
 * already shows (lessons/frontend-status-colors-for-status-only.md), from a score of our own (a curated
 * large-cap list plus follow counts) that no reader can check. A future marker needs a stated rule and
 * the neutral ink. This spec renders a top-scoring row both ways and reads the sources: no flame, no
 * threshold, and no FlameIcon left in lib/icons to reach for.
 */

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

const EVENT: CalendarEvent = {
  ticker: 'AAPL',
  company_name: 'Apple Inc.',
  event_date: '2026-10-29',
  event_time: 'amc',
  status: 'estimated',
  confidence: 'high',
  eps_estimate: 1.6,
  eps_actual: null,
  anticipation_score: 100,
}

const ALERTS: EarningsAlertsApi = {
  identityPending: false,
  isOn: () => false,
  isPending: () => false,
  toggle: () => {},
  blocked: null,
  clearBlocked: () => {},
}

describe('the calendar event row (CAL-10)', () => {
  it.each([true, false])('a top-scoring row carries no anticipation marker (roomy: %s)', (roomy) => {
    render(
      <ul>
        <EventRow ev={EVENT} alerts={ALERTS} signedIn={false} roomy={roomy} />
      </ul>,
    )
    const row = screen.getByRole('listitem')
    expect(within(row).queryByLabelText(/anticipated/i)).toBeNull()
    expect(row.querySelector('[class*="text-warning"]')).toBeNull()
    // The link names the company and its status; the bell is the row's one other control.
    expect(within(row).getByRole('link')).toHaveTextContent('AAPL')
    expect(within(row).getAllByRole('button')).toHaveLength(1)
  })

  it('no flame or anticipation threshold is left in the calendar, and lib/icons no longer exports the flame', () => {
    const source = readFileSync(path.join(ROOT, 'features/calendar/components/EventRow.tsx'), 'utf8')
    expect(source).not.toMatch(/FlameIcon|ANTICIPATION_FLAME_THRESHOLD/)
    expect(Object.keys(icons)).not.toContain('FlameIcon')
  })
})

/**
 * The row at enlarged text (the 2026-10-14 capture review of #1301, at 390px under a 32px root): a roomy
 * row's status chip ran under its EPS figure and the figure under the bell, the name and the "usually"
 * note truncated, and the week sheet's compact rows showed the note only as a hover title while the
 * page's footer explains "usually". jsdom has no layout, so these hold the row's contract; the capture
 * harness measures the layout itself.
 */
describe('the calendar event row wraps and shows what it carries', () => {
  const ESTIMATED: CalendarEvent = { ...EVENT, ticker: 'TSM', company_name: 'Taiwan Semiconductor', event_time: 'bmo' }
  const renderRow = (roomy: boolean, ev: CalendarEvent = ESTIMATED) =>
    render(
      <ul>
        <EventRow ev={ev} alerts={ALERTS} signedIn={false} roomy={roomy} />
      </ul>,
    ).container.querySelector('li') as HTMLElement

  it.each([true, false])('an estimated row shows its "usually" note on a line of its own after the lane glyph (roomy: %s)', (roomy) => {
    const row = renderRow(roomy)
    const line = within(row).getByText('usually before open').parentElement as HTMLElement
    expect(line.firstElementChild?.tagName.toLowerCase()).toBe('svg')
    expect(line.firstElementChild).toHaveAttribute('aria-hidden', 'true')
    expect(line).toHaveTextContent(/^usually before open$/)
    // Shown, not a hover title (the bell's own title names its action), and nothing truncates.
    expect(within(row).getByRole('link').querySelector('[title]')).toBeNull()
    expect(row.querySelector('.truncate')).toBeNull()
    expect(within(row).getByText('Taiwan Semiconductor')).toHaveClass('break-words')
  })

  it('a row with no note shows none', () => {
    const row = renderRow(true, { ...ESTIMATED, status: 'confirmed' })
    expect(within(row).queryByText(/usually/)).toBeNull()
  })

  it('a roomy row stacks below 16em of its text: no logo, the bell beside the ticker alone, the chip and the rest full width', () => {
    const row = renderRow(true)
    expect(row).toHaveClass('[container-type:inline-size]')
    const link = within(row).getByRole('link')
    // Wide, the EPS wraps under the name (to the right) before it squeezes it; stacked, it starts the line.
    expect(link).toHaveClass('flex-wrap', 'justify-end', '[@container(width<16em)]:justify-start', '[@container(width<16em)]:pr-2')
    expect(link.firstElementChild).toHaveClass('[@container(width<16em)]:hidden') // the decorative logo
    // Stacked, the ticker alone keeps the bell's column and height, on a line of its own; the chip wraps under it
    // at full width. Kept on the whole line, that column ran a 167px "Confirmed" under the bell in the day dialog
    // at 390px and 200% text (the chip wider than the 142px the column left).
    const ticker = within(row).getByText('TSM')
    expect(ticker).toHaveClass('flex', 'items-center', '[@container(width<16em)]:min-h-11', '[@container(width<16em)]:basis-full', '[@container(width<16em)]:pr-12')
    const line = ticker.parentElement as HTMLElement
    expect(line).toHaveClass('flex-wrap')
    expect(line.className).not.toMatch(/\[@container\(width<16em\)\]:(min-h|pr)-/)
    expect(within(line).getByText('Est.')).toBeInTheDocument()
    expect(line.parentElement).toHaveClass('[@container(width<16em)]:basis-full')
    // The bell is the link's sibling, never inside it; stacked, it sits at the ticker line's height.
    const bell = within(row).getByRole('button')
    expect(link).not.toContainElement(bell)
    expect(bell).toHaveClass('[@container(width<16em)]:top-2', '[@container(width<16em)]:translate-y-0')
  })

  it("a compact row's name keeps its longest word whole while the line allows (the EPS wraps first)", () => {
    const row = renderRow(false)
    const name = within(row).getByText('Taiwan Semiconductor')
    // No min-w-0: a flex item's floor is its longest word, and max-w-full caps that floor at the line.
    expect(name).toHaveClass('max-w-full', 'break-words')
    expect(name).not.toHaveClass('min-w-0')
    expect(name.parentElement).toHaveClass('flex-wrap')
  })
})
