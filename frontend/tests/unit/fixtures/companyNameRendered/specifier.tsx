/**
 * A planted form for companyNameDisplay.spec.ts, scored with tests/unit/fixtures/companyNameForms.tsx: a module's
 * default export.
 */
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'

/** N217 flag: a component of a lowercase name exported as the module's default by an export specifier. */
const line = ({ ev }: { ev: CalendarEvent }) => ev.company_name

export { line as default }
