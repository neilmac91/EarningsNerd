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
