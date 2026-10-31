/** Planted JSX forms: JSDoc resolves the same served API type as a TypeScript component. */
import { formatCompanyName } from '@/lib/formatCompanyName'

/** N251 flag: a JavaScript component prints the served name as a JSX child.
 * @param {{ event: import('@/features/calendar/api/calendar-api').CalendarEvent }} props
 */
export function N251({ event }) {
  return <span>{event.company_name}</span>
}

/** N252 clean: a JavaScript component prints the display form as a JSX child.
 * @param {{ event: import('@/features/calendar/api/calendar-api').CalendarEvent }} props
 */
export function N252({ event }) {
  return <span>{formatCompanyName(event.company_name)}</span>
}
