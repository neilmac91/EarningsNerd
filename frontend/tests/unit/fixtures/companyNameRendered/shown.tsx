/**
 * A planted form for companyNameDisplay.spec.ts, scored with tests/unit/fixtures/companyNameForms.tsx: a module's
 * default export.
 */
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'
import { formatCompanyName } from '@/lib/formatCompanyName'

/** N221 clean: a component of a lowercase name exported as the module's default, which returns the display form. */
export default function shown({ ev }: { ev: CalendarEvent }) {
  return formatCompanyName(ev.company_name)
}
