'use client'
/**
 * The spec renderer's font wait (G3, G4), for every chart its plots draw: TrendChartsV2 holds it for the four trend
 * charts' grid, and a chart drawn elsewhere on the engine waits the same way (E195 (D)).
 */
import { useEffect, useState } from 'react'

/** G4's wait: the font the plan's widths assume (layout.ts ADVANCE), or this long, whichever comes first. */
const CHART_FACE = '11px "Geist Mono"'
/** The text the wait loads and checks the face for. The Font Loading API picks a family's faces by their
 *  unicode-range, and with no text it takes a space, so the latin face alone; no route preloads latin-ext (app/fonts.ts,
 *  spec §0.5). So the sample names the latin face ("0") and every glyph past it that the plot can print and Geist Mono
 *  draws, all in latin-ext: the ₹, ₪ and ₱ that moneyPrefix prints (no plot prints † since E194, D-061). Geist Mono
 *  has no ₩ or ₫, so moneyPrefix prints KRW's and VND's codes instead (E203). */
const CHART_TEXT = '0₹₪₱'
const FONT_WAIT_MS = 1500

/** Spec G4: the plots paint once Geist Mono's latin and latin-ext faces have loaded, or after 1,500 ms, so no text
 *  paints at the planner's positions in a fallback face, and no glyph swaps after a plot's first paint (G3). Until then
 *  each card holds its plot's exact box, on the server and through hydration (D9). A browser without the Font Loading
 *  API paints at once. */
export function useChartFont() {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    const fonts = typeof document === 'undefined' ? undefined : document.fonts
    if (!fonts?.load || fonts.check(CHART_FACE, CHART_TEXT)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- mount-time latch: the server and hydration hold the plot's box, the client paints after
      setReady(true)
      return
    }
    let live = true
    const done = () => { if (live) setReady(true) }
    const timer = window.setTimeout(done, FONT_WAIT_MS)
    fonts.load(CHART_FACE, CHART_TEXT).then(done, done)
    return () => {
      live = false
      window.clearTimeout(timer)
    }
  }, [])
  return ready
}
