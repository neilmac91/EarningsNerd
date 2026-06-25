import { useState, useEffect } from 'react'

const prefersReducedMotion = (): boolean =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

export function useCountUp(end: number, duration: number = 800) {
  // Initialize to 0 unconditionally so server and first client render agree (no hydration
  // mismatch); the effect below honors reduced-motion once mounted on the client.
  const [count, setCount] = useState(0)

  useEffect(() => {
    // WCAG 2.3.3 (Animation from Interactions): if the user prefers reduced motion, snap to
    // the final value with no tween instead of running the count-up animation.
    if (prefersReducedMotion()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- reduced-motion path snaps to the final value (WCAG 2.3.3) instead of tweening; intentional mount-time sync
      setCount(end)
      return
    }

    let startTime: number | null = null
    let animationFrame: number

    const animate = (timestamp: number) => {
      if (!startTime) startTime = timestamp
      const progress = timestamp - startTime
      const percentage = Math.min(progress / duration, 1)

      // Ease out quart
      const easeOut = 1 - Math.pow(1 - percentage, 4)

      setCount(end * easeOut)

      if (progress < duration) {
        animationFrame = requestAnimationFrame(animate)
      } else {
        setCount(end)
      }
    }

    animationFrame = requestAnimationFrame(animate)

    return () => cancelAnimationFrame(animationFrame)
  }, [end, duration])

  return count
}
