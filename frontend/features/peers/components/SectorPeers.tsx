'use client'
/**
 * The company page's Sector peers panel, as the page imports it (E251): a small gate that reads the company's cohort on
 * the default metric and renders nothing until that answer is one the panel shows (cohort.ts `shows`: the subject and at
 * least one other company with a value). Only then does the card load, in a chunk of its own, so the trend charts'
 * engine stays out of the company page's first load and reaches only a company with a cohort, as Financial trends keeps
 * it out of the filing page's (SummaryDisplay.tsx). Production stores no SIC codes until the founder's backfill, so
 * every company answers itself alone there and the panel shows nothing. Visibility rides on the default answer, never
 * on a latch: a metric picked in the card that has too few companies keeps the card and says so. The page keys the
 * panel's boundary by ticker, so a soft navigation to another company starts it afresh.
 */
import dynamic from 'next/dynamic'
import { usePeers } from '@/features/peers/hooks/usePeers'
import { DEFAULT_METRIC, shows } from '@/features/peers/lib/cohort'

// The engine measures its viewport and waits for its font in the browser, so the card loads client-side. A chunk that
// fails to load throws to the page's ChartErrorBoundary, as the analysis grid's does (TrendCharts.tsx); while it loads
// nothing shows, as before the answer.
const SectorPeersCard = dynamic(() => import('./SectorPeersCard'), {
  ssr: false,
  loading: ({ error }) => {
    if (error) throw error
    return null
  },
})

export default function SectorPeers({ ticker, className }: {
  ticker: string
  /** The card's place on the page (its margin), which the page's boundary gives its fallback too. */
  className?: string
}) {
  const { data } = usePeers(ticker, DEFAULT_METRIC)
  if (!shows(data)) return null
  return <SectorPeersCard ticker={ticker} answer={data} className={className} />
}
