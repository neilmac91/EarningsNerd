/* =============================================================================
   /calendar route (app/calendar/page.tsx)
   -----------------------------------------------------------------------------
   Public discovery surface, gated on the existing NEXT_PUBLIC_ENABLE_CALENDAR
   flag (lib/featureFlags.ts) — the route 404s while the flag is off, same
   pattern as ENABLE_ANALYSIS. Flip the flag once /api/calendar is seeded (or
   set NEXT_PUBLIC_CALENDAR_FIXTURES='true' to demo against fixtures).
============================================================================= */

import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { ENABLE_CALENDAR } from '@/lib/featureFlags'
import EarningsCalendarPage from '@/features/calendar/components/EarningsCalendarPage'

export const metadata: Metadata = {
  title: 'Earnings calendar — EarningsNerd',
  description:
    'The most-anticipated U.S. earnings, week by week — before-open and after-close lanes, honest estimated vs confirmed vs reported dates, and day-of alerts.',
}

export default function CalendarRoute() {
  if (!ENABLE_CALENDAR) notFound()
  return <EarningsCalendarPage />
}
