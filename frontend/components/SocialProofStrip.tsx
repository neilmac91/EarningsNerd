'use client'

import { useEffect, useRef, useState, memo } from 'react'

const STATS: readonly { label: string; value: number; suffix: string; display?: string }[] = [
  { label: 'Companies covered', value: 500, suffix: '+' },
  { label: 'Filings analyzed', value: 10000, suffix: '+' },
  { label: 'Data source', value: 0, suffix: '', display: 'SEC EDGAR' },
]

function AnimatedNumber({ target, suffix }: { target: number; suffix: string }) {
  const [count, setCount] = useState(0)
  const ref = useRef<HTMLSpanElement>(null)
  const hasAnimated = useRef(false)

  useEffect(() => {
    if (hasAnimated.current) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated.current) {
          hasAnimated.current = true
          const duration = 1200
          const startTime = performance.now()

          const animate = (currentTime: number) => {
            const elapsed = currentTime - startTime
            const progress = Math.min(elapsed / duration, 1)
            // Ease-out cubic
            const eased = 1 - Math.pow(1 - progress, 3)
            setCount(Math.floor(eased * target))

            if (progress < 1) {
              requestAnimationFrame(animate)
            }
          }

          requestAnimationFrame(animate)
          observer.disconnect()
        }
      },
      { threshold: 0.3 }
    )

    if (ref.current) observer.observe(ref.current)
    return () => observer.disconnect()
  }, [target])

  return (
    <span ref={ref} className="tabular-nums">
      {count.toLocaleString()}{suffix}
    </span>
  )
}

function SocialProofStrip() {
  return (
    <section className="border-y border-white/[0.06] bg-slate-900/50">
      <div className="mx-auto flex max-w-5xl flex-col items-center gap-8 px-4 py-10 sm:flex-row sm:justify-center sm:gap-16 sm:px-6 lg:px-8">
        {STATS.map((stat) => (
          <div key={stat.label} className="text-center">
            <div className="text-3xl font-bold text-white">
              {stat.display ? (
                stat.display
              ) : (
                <AnimatedNumber target={stat.value} suffix={stat.suffix} />
              )}
            </div>
            <div className="mt-1 text-sm text-slate-400">{stat.label}</div>
          </div>
        ))}
      </div>
    </section>
  )
}

export default memo(SocialProofStrip)
