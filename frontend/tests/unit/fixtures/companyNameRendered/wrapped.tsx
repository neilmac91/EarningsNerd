/**
 * A planted form for companyNameDisplay.spec.ts, scored with tests/unit/fixtures/companyNameForms.tsx: a module's
 * default export.
 */
import { memo } from 'react'
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'

/** N216 flag: a component of a lowercase name wrapped in memo and exported as the module's default. */
const line = ({ ev }: { ev: CalendarEvent }) => ev.company_name

export default memo(line)
