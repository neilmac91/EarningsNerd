/**
 * A planted form for companyNameDisplay.spec.ts, scored with tests/unit/fixtures/companyNameForms.tsx: a module's
 * default export.
 */
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'

/** N212 flag: an anonymous component exported as the module's default (Codex's form), which returns a served name. */
// eslint-disable-next-line import/no-anonymous-default-export -- planted AST form: an anonymous default export, which app code may not write.
export default ({ ev }: { ev: CalendarEvent }) => ev.company_name
