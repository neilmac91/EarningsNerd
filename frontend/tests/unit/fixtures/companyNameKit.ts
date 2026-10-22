/**
 * Another module for tests/unit/fixtures/companyNameForms.tsx. A helper that hands a served company name back as a plain
 * string (N86), which the gate follows to its calls in another module; one that hands back the display form (N104); one
 * that hands the name back inside an object (N113), which the gate does not follow (companyNameDisplay.spec.ts names it
 * as a gap); and one that gives back no name (N58), which the gate fails closed on, since it reads what another
 * module's function returns but not what that function makes of what it is handed.
 */
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'
import { formatCompanyName } from '@/lib/formatCompanyName'

export const nameOf = (ev: CalendarEvent): string => ev.company_name

export const displayNameOf = (ev: CalendarEvent): string => formatCompanyName(ev.company_name)

export const labelsOf = (ev: CalendarEvent): { title: string } => ({ title: ev.company_name })

export const lengthOf = (name: string): number => name.length
