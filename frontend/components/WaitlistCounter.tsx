'use client'

import { useEffect, useMemo, useState } from 'react'
import { getApiUrl } from '@/lib/api'

const formatCount = (value: number) => value.toLocaleString()

export default function WaitlistCounter() {
  const [target, setTarget] = useState<number | null>(null)
  const [display, setDisplay] = useState(0)

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

  useEffect(() => {
    if (target === null) return
    const start = performance.now()
    const duration = 900
    const startValue = display

    const animate = (now: number) => {
      const progress = Math.min(1, (now - start) / duration)
      const nextValue = Math.round(startValue + (target - startValue) * progress)
      setDisplay(nextValue)
      if (progress < 1) {
        requestAnimationFrame(animate)
      }
    }

    requestAnimationFrame(animate)
  }, [target])

  const label = useMemo(() => {
    if (target === null) {
      return 'Join the waitlist'
    }
    return `Join ${formatCount(display)}+ others on the waitlist`
  }, [display, target])

  return (
    <div className="inline-flex items-center justify-center rounded-full border border-mint-200 bg-mint-50 px-4 py-2 text-sm font-medium text-mint-800 shadow-sm dark:border-mint-500/30 dark:bg-mint-500/10 dark:text-mint-200">
      {label}
    </div>
  )
}
