'use client'

/* =============================================================================
   useCountUp — hooks/useCountUp.ts
   -----------------------------------------------------------------------------
   The count-up signature for financial figures (KPI tiles, executive snapshot).
   Interpolates 0 → value on first reveal (previous → next on updates) over
   --duration-slow with the --ease-standard curve, formatted per the content
   fundamentals ("$391.0B"). Render the result in the data face with
   tabular-nums (`tnum font-data` or `.tabular`) so width never jitters:

     const revenue = useCountUp(391.0, { format: (v) => `$${v.toFixed(1)}B` })
     <span className="tnum font-data">{revenue}</span>

   Reduced motion / SSR / no-JS: the FINAL formatted value renders instantly —
   the initial state IS the target, and the rAF loop only starts client-side
   when motion is allowed (same usePrefersReducedMotion as every consumer).
   The tween is armed in a LAYOUT effect: the start value (0) is committed
   BEFORE the browser paints, so hydrated mounts never flash value→0→value
   (a passive effect runs after paint — the final value would be visible for
   a frame before the tween reset it). Server render uses useEffect (layout
   effects warn on the server); it never runs there anyway.
   Replaces the retired `animate-count-up` keyframe, which was just a fade.
============================================================================= */

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { MOTION, easeStandard } from '../lib/motion'
import { usePrefersReducedMotion } from './usePrefersReducedMotion'

export interface CountUpOptions {
  /** ms — defaults to the slow token (600). Pass MOTION.* — never a raw number. */
  duration?: number
  /** Format the interpolated number — e.g. (v) => `$${v.toFixed(1)}B`. */
  format?: (value: number) => string
}

const defaultFormat = (v: number) => Math.round(v).toLocaleString('en-US')

// Isomorphic layout effect — useLayoutEffect in the browser (pre-paint),
// useEffect on the server (where it's a no-op and silences the SSR warning).
const useIsomorphicLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect

export function useCountUp(
  value: number,
  { duration = MOTION.slow, format = defaultFormat }: CountUpOptions = {},
): string {
  const reduced = usePrefersReducedMotion()
  // SSR markup + no-JS + first client frame all show the final value.
  const [display, setDisplay] = useState(value)
  const displayRef = useRef(value) // latest rendered number — restart point mid-animation
  const animatedRef = useRef(false)

  useIsomorphicLayoutEffect(() => {
    if (reduced) {
      animatedRef.current = true
      displayRef.current = value
      setDisplay(value)
      return
    }
    // First reveal counts 0 → value; later changes count from what's on screen.
    const from = animatedRef.current ? displayRef.current : 0
    animatedRef.current = true
    if (from === value) {
      setDisplay(value)
      return
    }
    // Commit the start value PRE-PAINT — the SSR markup showed the target, but
    // the first client paint must already be at `from` or the mount flashes.
    displayRef.current = from
    setDisplay(from)
    let raf = 0
    const t0 = performance.now()
    const tick = (now: number) => {
      const p = Math.min((now - t0) / duration, 1)
      const v = p >= 1 ? value : from + (value - from) * easeStandard(p)
      displayRef.current = v
      setDisplay(v)
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value, duration, reduced])

  return format(display)
}
