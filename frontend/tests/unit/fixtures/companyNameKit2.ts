/**
 * A third module for tests/unit/fixtures/companyNameForms.tsx: a helper that hands back what another module's helper
 * hands back, so a served company name crosses two modules before it prints (N103). The gate follows it, as it follows
 * one module.
 */
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'
import { nameOf } from './companyNameKit'

export const shortNameOf = (ev: CalendarEvent): string => nameOf(ev).trim()
