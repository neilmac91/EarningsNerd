'use client'

import { useEffect, useState } from 'react'
import { getApiUrl } from '@/lib/api/client'
import { useCountUp } from '@/hooks/useCountUp'

export default function WaitlistCounter() {
  const [target, setTarget] = useState<number | null>(null)

  useEffect(() => {
    let active = true
    const loadStats = async () => {
      try {
        const response = await fetch(`${getApiUrl()}/api/waitlist/stats`)
        if (!response.ok) return
        const data = await response.json()
        if (active) {
          setTarget(typeof data.total_signups === 'number' ? data.total_signups : 0)
        }
      } catch {
        if (active) setTarget(0)
      }
    }

    loadStats()
    return () => {
      active = false
    }
  }, [])

  // DS count-up (rAF, --duration-slow, reduced-motion + SSR safe) replacing the prior
  // hand-rolled raw-900ms tween; rendered in the data face so the width never jitters.
  const count = useCountUp(target ?? 0, { format: (v) => Math.round(v).toLocaleString() })

  return (
    <div className="inline-flex items-center justify-center rounded-full border border-brand-border bg-brand-weak px-4 py-2 text-sm font-medium text-brand-strong shadow-e1 dark:border-brand-dark/40 dark:bg-brand-dark/15 dark:text-brand-strong-dark">
      {/* Single inline child: the pill is a flex container, which strips whitespace-only
          text nodes *between* flex items — so the count + its surrounding spaces must live
          inside one element to keep "Join 1,234+ others" from collapsing to "Join1,234+". */}
      <span>
        {target === null ? (
          'Join the waitlist'
        ) : (
          <>
            Join <span className="tnum font-data">{count}</span>+ others on the waitlist
          </>
        )}
      </span>
    </div>
  )
}
