/** Planted JavaScript forms: a component can return text without JSX. */
import { formatCompanyName } from '@/lib/formatCompanyName'

/** N253 flag: a JavaScript component returns the served name as text.
 * @param {{ event: import('@/features/calendar/api/calendar-api').CalendarEvent }} props
 */
export function N253({ event }) {
  return event.company_name
}

/** N254 clean: a JavaScript component returns the display form as text.
 * @param {{ event: import('@/features/calendar/api/calendar-api').CalendarEvent }} props
 */
export function N254({ event }) {
  return formatCompanyName(event.company_name)
}
