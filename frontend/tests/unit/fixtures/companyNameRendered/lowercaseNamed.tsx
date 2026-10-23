/**
 * A planted form for companyNameDisplay.spec.ts, scored with tests/unit/fixtures/companyNameForms.tsx: a module's
 * default export.
 */
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'

/** N214 flag: a component of a lowercase name exported as the module's default, which returns a served name. */
export default function row({ ev }: { ev: CalendarEvent }) {
  return ev.company_name
}
