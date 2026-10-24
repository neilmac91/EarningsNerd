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
import { ENABLE_CALENDAR, LOGO_DEV_ENABLED } from '@/lib/featureFlags'
import EarningsCalendarPage from '@/features/calendar/components/EarningsCalendarPage'

export const metadata: Metadata = {
  title: 'Earnings calendar | EarningsNerd',
  description:
    'U.S. earnings dates, week by week: before the open or after the close, estimated or reported, with an optional email the morning a company you follow reports.',
}

export default function CalendarRoute() {
  if (!ENABLE_CALENDAR) notFound()
  return (
    <>
      {/* Every row carries a company mark once the week's events answer; the handshake runs with the HTML. */}
      {LOGO_DEV_ENABLED && <link rel="preconnect" href="https://img.logo.dev" />}
      <EarningsCalendarPage />
    </>
  )
}
