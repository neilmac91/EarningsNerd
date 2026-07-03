/* =============================================================================
   Earnings calendar — lane + ranking helpers (features/calendar/lib/lanes.ts)
   -----------------------------------------------------------------------------
   §3.7: each day shows the TOP 5 by anticipation_score desc, split into
   Before Open / After Close lanes with a small During/unspecified group for
   dmh/null. "+N more" counts everything past the cap — never overflow a cell.
============================================================================= */

import type { CalendarEvent } from '../api/calendar-api'

export type LaneKey = 'bmo' | 'amc' | 'other'

export interface Lane {
  key: LaneKey
  label: string
  rows: CalendarEvent[]
}

export const LANE_LABELS: Record<LaneKey, string> = {
  bmo: 'Before open',
  amc: 'After close',
  other: 'During · unspecified',
}

export const DAY_CAP = 5

export function rankEvents(events: CalendarEvent[]): CalendarEvent[] {
  return [...events].sort((a, b) => b.anticipation_score - a.anticipation_score)
}

export function laneOf(ev: CalendarEvent): LaneKey {
  if (ev.event_time === 'bmo') return 'bmo'
  if (ev.event_time === 'amc') return 'amc'
  return 'other'
}

/** Rank, cap (cap=0 means "all"), and group into non-empty lanes. */
export function groupIntoLanes(events: CalendarEvent[], cap: number = DAY_CAP): { lanes: Lane[]; hidden: number } {
  const ranked = rankEvents(events)
  const visible = cap > 0 ? ranked.slice(0, cap) : ranked
  const buckets: Record<LaneKey, CalendarEvent[]> = { bmo: [], amc: [], other: [] }
  for (const ev of visible) buckets[laneOf(ev)].push(ev)
  const lanes = (['bmo', 'amc', 'other'] as const)
    .filter((k) => buckets[k].length > 0)
    .map((k) => ({ key: k, label: LANE_LABELS[k], rows: buckets[k] }))
  return { lanes, hidden: Math.max(0, ranked.length - visible.length) }
}

/** Honest wording for an estimated event's habitual slot (§3.3 note: the
    habitual slot is right ~3 times in 4, so it is labelled "usually …"). */
export function habitualSlotNote(ev: CalendarEvent): string | null {
  if (ev.status !== 'estimated') return null
  const slot =
    ev.event_time === 'bmo'
      ? 'usually before open'
      : ev.event_time === 'amc'
        ? 'usually after close'
        : ev.event_time === 'dmh'
          ? 'usually during market hours'
          : null
  if (ev.confidence === 'low') return slot ? `${slot}, date may move` : 'date may move'
  return slot
}

/** Group a flat range response by event_date for O(1) day lookups. */
export function indexByDate(events: CalendarEvent[]): Map<string, CalendarEvent[]> {
  const map = new Map<string, CalendarEvent[]>()
  for (const ev of events) {
    const list = map.get(ev.event_date)
    if (list) list.push(ev)
    else map.set(ev.event_date, [ev])
  }
  return map
}
