'use client'

import { useEffect, useState } from 'react'
import { ApiError } from '@/lib/api/client'
import { getWaitlistStats } from '@/features/waitlist/api/waitlist-api'
import { useCountUp } from '@/hooks/useCountUp'
import { fmtCount } from '@/lib/format'
import WaitlistPill, { PILL_LABEL } from './WaitlistPill'

/** The smallest count worth saying aloud. */
export const COUNT_FLOOR = 25

export default function WaitlistCounter({ className }: { className?: string }) {
  const [target, setTarget] = useState<number | null>(null)

  useEffect(() => {
    let active = true
    const loadStats = async () => {
      try {
        const data = await getWaitlistStats()
        if (active) {
          setTarget(typeof data.total_signups === 'number' ? data.total_signups : 0)
        }
      } catch (err) {
        // Preserve prior behavior: a non-OK HTTP response leaves the placeholder (target stays null);
        // only a network failure (no response, status 0) falls back to 0.
        if (active && !(err instanceof ApiError && err.status !== 0)) setTarget(0)
      }
    }

    loadStats()
    return () => {
      active = false
    }
  }, [])

  // DS count-up (rAF, --duration-slow, reduced-motion + SSR safe) replacing the prior
  // hand-rolled raw-900ms tween; rendered in the data face so the width never jitters. The tween
  // starts at 0, so the display is clamped to the floor: no frame ever reads "Join 0+ others".
  const count = useCountUp(target ?? 0, { format: (v) => fmtCount(Math.round(Math.max(v, COUNT_FLOOR))) })
  // A count is social proof of nothing until it is one (docs/brand/03-strategy.md, S5: never a
  // placeholder, never a counter at zero): below the floor the pill names the list, not the number.
  const showCount = target !== null && target >= COUNT_FLOOR

  return (
    <WaitlistPill className={className}>
      {/* Single inline child: the pill is a flex container, which strips whitespace-only
          text nodes *between* flex items — so the count + its surrounding spaces must live
          inside one element to keep "Join 1,234+ others" from collapsing to "Join1,234+". */}
      <span>
        {!showCount ? (
          PILL_LABEL
        ) : (
          <>
            {/* The count is a number: neutral ink inside the sage pill (the Separate Signals Rule). The counted label is
                short enough that the status above the form keeps its height as the count lands: "others on the
                waitlist" wrapped under 200% text where "Join the waitlist" did not, and the status grew 34px (E225,
                chief design on #1699). This label is still a character longer than the opening one and takes a line
                more at about 330 to 390px under 200% text, where the checking line in the status's cell is taller
                still (chief design on #1709; legal-readiness.spec.ts holds the form's place). */}
            Join <span data-waitlist-count className="tnum font-data text-text-primary-light dark:text-text-primary-dark">{count}+</span> others
          </>
        )}
      </span>
    </WaitlistPill>
  )
}
