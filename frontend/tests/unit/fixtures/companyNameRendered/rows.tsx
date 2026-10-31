/**
 * Planted forms for companyNameDisplay.spec.ts, scored with tests/unit/fixtures/companyNameForms.tsx: components and
 * helpers another module uses. companyNameForms.tsx renders N218, N219, N222 and N224 (its N218Use, N219Use, N222Use
 * and N224Use), calls N223 for a key and hands `rowName` to a DataTable column (its N220). Each form is the statement
 * its comment marks. Sample companies only.
 */
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'
import { formatCompanyName } from '@/lib/formatCompanyName'

/** N218 flag: a component of a lowercase name, rendered by another module under an alias, which returns a served
    name. */
export const rowLine = ({ ev }: { ev: CalendarEvent }) => ev.company_name

/** N219 flag: a component held as an object's member, rendered by another module as `<Rows.line />`. */
export const Rows = {
  line: ({ ev }: { ev: CalendarEvent }) => ev.company_name,
}

/** N220's helper, which hands back a served name for another module's DataTable column. */
export const rowName = (row: CalendarEvent) => row.company_name

/** N222 clean: a component another module renders, which returns the display form. */
export const shownLine = ({ ev }: { ev: CalendarEvent }) => formatCompanyName(ev.company_name)

/** N223 clean: a helper that hands back a served name, which another module calls for a key and never renders. */
export const rawKey = (ev: CalendarEvent) => ev.company_name

/** N224 gap: a component another module loads lazily through a promise's then and renders, which returns a served
    name. */
export const lazyLine = ({ ev }: { ev: CalendarEvent }) => ev.company_name
