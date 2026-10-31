/**
 * A planted form for companyNameDisplay.spec.ts, scored with tests/unit/fixtures/companyNameForms.tsx: a module's
 * default export.
 */
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'

/** N215 flag: a component held in a const of a lowercase name and exported as the module's default. */
const line = ({ ev }: { ev: CalendarEvent }) => ev.company_name

export default line
