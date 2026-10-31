'use client'
/**
 * The company page's Sector peers panel, as the page imports it (E251): a small gate that reads the company's cohort on
 * the default metric and renders nothing until that answer is one the panel shows (cohort.ts `shows`: a metric the panel
 * names, the subject's own figure and at least one other company's). Only then does the card load, in a chunk of its
 * own, so the trend charts' engine stays out of the company page's first load and reaches only a company with a cohort,
 * as Financial trends keeps it out of the filing page's (SummaryDisplay.tsx; tests/e2e/company-first-load.spec.ts holds
 * it on the build). Production answers cohorts since the founder's SIC backfill of 2026-10-31. Visibility rides on the
 * default answer, never on a latch: a metric picked in the card that draws no chart keeps the card and says why. The
 * page keys the panel's boundary by ticker, so a soft navigation to another company starts it afresh, its card chunk
 * included.
 */
import { lazy, Suspense, useState } from 'react'
import { usePeers } from '@/features/peers/hooks/usePeers'
import { DEFAULT_METRIC, shows } from '@/features/peers/lib/cohort'

/** The card's chunk. The engine measures its viewport and waits for its font in the browser, and the card renders only
 *  once the read has answered, which happens in the browser alone, so it never renders on the server. */
const loadCard = () => import('./SectorPeersCard')

export default function SectorPeers({ ticker, className }: {
  ticker: string
  /** The card's place on the page (its margin), which the page's boundary gives its fallback too. */
  className?: string
}) {
  // A lazy card of this gate's own, made as it mounts. React.lazy keeps a rejected import for good, so one lazy for the
  // module would put the boundary's card on every company after a single failed chunk, until a reload; the page mounts
  // the gate afresh for each company (its boundary is keyed by ticker), so the next company asks for the chunk again.
  const [Card] = useState(() => lazy(loadCard))
  const { data } = usePeers(ticker, DEFAULT_METRIC)
  if (!shows(data)) return null
  // While the chunk loads nothing shows, as before the answer; a chunk that fails to load throws to the page's
  // ChartErrorBoundary.
  return (
    <Suspense fallback={null}>
      <Card ticker={ticker} answer={data} className={className} />
    </Suspense>
  )
}
