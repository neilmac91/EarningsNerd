/**
 * Another module for tests/unit/fixtures/companyNameForms.tsx. A helper that hands a served company name back as a plain
 * string (N86), which the gate follows to its calls in another module; one that hands back the display form (N104); one
 * that hands the name back inside an object (N113), which the gate does not follow (companyNameDisplay.spec.ts names it
 * as a gap); one that gives back no name (N58), which the gate fails closed on, since it reads what another module's
 * function returns but not what that function makes of what it is handed; one that hands a served name to the
 * callback it is given (N122), so a state's setter handed to it is called where the gate does not look (a gap); two
 * reducers, one that gives back the action it is dispatched (N124, N128) and one that hands back the served name of
 * the event it is dispatched (N125); an overloaded helper exported through a const alias (N129), whose body the gate
 * reaches past its signatures; a helper chosen by a conditional (N130), whose arms the gate reads both of; and an
 * object whose getter hands back a served name (N151), which a read of its property in another module calls.
 */
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'
import { formatCompanyName } from '@/lib/formatCompanyName'

export const nameOf = (ev: CalendarEvent): string => ev.company_name

export const displayNameOf = (ev: CalendarEvent): string => formatCompanyName(ev.company_name)

export const labelsOf = (ev: CalendarEvent): { title: string } => ({ title: ev.company_name })

export const lengthOf = (name: string): number => name.length

export const pickFirst = (events: CalendarEvent[], onPick: (name: string) => void): void => onPick(events[0]?.company_name ?? '')

export const keepLatest = (_current: string, next: string): string => next

export const nameFromEvent = (_current: string, ev: CalendarEvent): string => ev.company_name

export function overloadedNameOf(ev: CalendarEvent): string
export function overloadedNameOf(ev: CalendarEvent, fallback: string): string
export function overloadedNameOf(ev: CalendarEvent, fallback = ''): string {
  return ev.company_name || fallback
}

export const aliasedNameOf = overloadedNameOf

const RAW_NAMES = true as boolean

export const chosenNameOf = RAW_NAMES ? nameOf : displayNameOf

export const latestEvent = {
  event: undefined as CalendarEvent | undefined,
  get name(): string {
    return this.event?.company_name ?? ''
  },
}
