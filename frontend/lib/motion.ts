/* =============================================================================
   Motion constants — lib/motion.ts
   -----------------------------------------------------------------------------
   JS mirror of the CSS motion tokens (globals.css :root)
   for consumers that need NUMBERS, not var() strings: Recharts animationDuration
   (ui/Chart.tsx lineProps) and the useCountUp rAF loop. The CSS :root block and
   this file are the only sanctioned homes for raw motion values — keep in sync.
============================================================================= */

export const MOTION = {
  /** 150ms — hover + color feedback. */
  fast: 150,
  /** 200ms — crossfades, theme switch, skeleton→content. */
  base: 200,
  /** 600ms — entrances, draw-ins, count-up. */
  slow: 600,
  /** 1800ms — ambient loops + attention decay (shimmer, pulse, citation-flash). */
  ambient: 1800,
} as const

/* --ease-standard — cubic-bezier(0.4, 0, 0.2, 1) — as a JS progress function
   for rAF interpolation (useCountUp). Solved x→t by Newton–Raphson, then y(t). */
const P1X = 0.4
const P1Y = 0
const P2X = 0.2
const P2Y = 1

function bezierAxis(t: number, p1: number, p2: number): number {
  const u = 1 - t
  return 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t
}

export function easeStandard(x: number): number {
  if (x <= 0) return 0
  if (x >= 1) return 1
  let t = x
  for (let i = 0; i < 5; i++) {
    const err = bezierAxis(t, P1X, P2X) - x
    if (Math.abs(err) < 1e-4) break
    const slope = 3 * (1 - t) * (1 - t) * P1X + 6 * (1 - t) * t * (P2X - P1X) + 3 * t * t * (1 - P2X)
    if (slope === 0) break
    t -= err / slope
  }
  return bezierAxis(t, P1Y, P2Y)
}
