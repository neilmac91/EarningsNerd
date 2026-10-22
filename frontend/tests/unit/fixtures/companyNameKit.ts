/**
 * Another module for tests/unit/fixtures/companyNameForms.tsx: a helper that hands a served company name back as a
 * plain string, the cross-module form the gate cannot follow (companyNameDisplay.spec.ts names it as a gap), and one
 * that gives back no name, which the gate fails closed on, since it cannot see what an import returns.
 */
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'

export const nameOf = (ev: CalendarEvent): string => ev.company_name

export const lengthOf = (name: string): number => name.length
