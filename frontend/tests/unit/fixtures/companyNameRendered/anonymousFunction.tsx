/**
 * A planted form for companyNameDisplay.spec.ts, scored with tests/unit/fixtures/companyNameForms.tsx: a module's
 * default export.
 */
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'

/** N213 flag: a function of no name exported as the module's default, which returns a served name. */
// eslint-disable-next-line import/no-anonymous-default-export -- planted AST form: an anonymous default export, which app code may not write.
export default function ({ ev }: { ev: CalendarEvent }) {
  return ev.company_name
}
