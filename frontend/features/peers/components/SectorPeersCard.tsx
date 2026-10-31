'use client'
/**
 * The company page's Sector peers panel (E251), the card its gate loads once the default metric's answer is a cohort
 * (SectorPeers.tsx): the company ranked against the other companies of its SEC industry code on one metric, drawn
 * through the trend charts' engine in the analysis charts' look (features/peers/lib/peerChart.ts): every value printed
 * on its bar (A4), the company the page is about in chart-1 and every other company a context bar in the context ink at
 * the narrower width, the plot opening at the subject, and one values stop reading a company at a time beside the
 * column-wash tooltip, as many companies as its eleven slots hold (cohort.ts `drawn`). Around it: the heading, the
 * subject's rank over the companies with a value, the metric picker, the footnote (which says what the chart shows where
 * a cohort is larger than its slots) and Sources & checks. A metric picked holds the plot's room with bones and the rank
 * line's with its own while it loads, and where its answer draws no chart says why in the plot's place, the reason
 * cohort.ts `noCohort` found, or that its read failed. No source-check badge (the badge's gate keeps it to Financial
 * trends): where a drawn value needs a check, the footnote says so and Sources & checks lists it.
 */
import { useContext, useId, useMemo, useState, type ReactNode } from 'react'
import { ThemeContext } from '@/components/ThemeProvider'
import { Card, Skeleton, cx, inputClasses } from '@/components/ui'
import ChartPlotFrame from '@/features/analysis/components/ChartPlotFrame'
import SourceChecks from '@/features/analysis/components/SourceChecks'
import { useChartFont } from '@/features/analysis/components/useChartFont'
import { unitCurrency } from '@/features/analysis/lib/charts/barChart'
import { CARD_HEIGHT, VALUES_DONT_FIT_HERE } from '@/features/analysis/lib/charts/layout'
import { chartTokens } from '@/features/analysis/lib/charts/theme'
import { needsSourceCheck } from '@/features/analysis/lib/provenance'
import type { PeerComparisonResponse, PeerEntry } from '@/features/peers/api/peers-api'
import { usePeers } from '@/features/peers/hooks/usePeers'
import { croppedOf, DEFAULT_METRIC, drawn, METRICS, metricOf, noCohort, rankOf, shows, type NoCohort } from '@/features/peers/lib/cohort'
import { peerChart } from '@/features/peers/lib/peerChart'
import { inSentence } from '@/lib/format'
import { formatCompanyName } from '@/lib/formatCompanyName'

// ---- The card's words (E251's defaults, for chief design's ruling) ----
const HEADING = 'Sector peers'
/** After the subject's ticker: "AAPL ranks #3 of 9 on revenue", its rank over the companies with a value. */
const ranksOn = (rank: number, of: number, label: string) => ` ranks #${rank} of ${of} on ${inSentence(label)}`
/** The line under the plot: what the companies are, where each figure comes from, an amount's reporting currency where
 *  it is not the dollar. It promises only what the endpoint does: one SIC code's companies (the service's cohort), each
 *  company's latest annual figure (its latest FY fact), and no promise of coverage. */
const footnoteOf = (label: string, currency: string | null) =>
  `Companies with the same SEC industry code, each with its most recent annual ${inSentence(label)} from SEC filings (XBRL)${currency && currency !== 'USD' ? `, reported in ${currency}` : ''}. Fiscal years can differ by company.`
/** Added to the footnote where the cohort ranks more companies than the chart's eleven slots draw, so a reader who
 *  counts the bars against the rank line's count is told why: the top it draws, of the companies ranked (the rank line's
 *  count, never peer_count's withheld entries), and the subject where it is drawn after them, from below. The top never
 *  parts a tie (cohort.ts), so it is the companies ranked that high; where one rank fills the slots, so no top can be
 *  named, the line says how many the chart shows. */
const croppedLine = ({ shown, of, top, subject }: { shown: number; of: number; top: number | null; subject: PeerEntry | null }) =>
  top == null
    ? `The chart shows ${shown} of the ${of} companies ranked.`
    : `The chart shows the top ${top} of the ${of} companies ranked${subject ? `, and ${subject.ticker}` : ''}.`
/** Added to the footnote where a drawn value needs a source check. */
const NEEDS_A_CHECK = 'Some figures here need a source check. Sources & checks lists them.'
/** In the plot's place, for a metric picked whose answer draws no chart, the reason cohort.ts `noCohort` found, the first
 *  that stops it: the company's own figure missing (it holds no fact for the metric) or withheld, either of which is
 *  "unavailable", as Sources & checks and the analysis data notes name a figure there is none of; fewer than two
 *  companies with a figure, which with the company's own means no other company has one; or an answer ranked on a
 *  metric the panel cannot name or format. */
function NoCohortLine({ why, label, ticker }: { why: NoCohort; label: string; ticker: string }): ReactNode {
  if (why === 'subject') return <><span className="font-data">{ticker}</span>’s {inSentence(label)} is unavailable, so it can’t be ranked.</>
  if (why === 'few') return `Too few sector peers have ${inSentence(label)} figures to compare.`
  return `Sector peers for ${inSentence(label)} can’t be shown here.`
}
/** In the plot's place, for a metric picked whose read failed. */
const failed = (label: string) => `Couldn’t load sector peers for ${inSentence(label)}. Try another metric.`

/** The picker's one width, the smallest step that holds its widest label, as Financial trends' (E253). */
const PICKER_WIDTH = 'w-56'

/** The rank line: the subject's ticker in the data face, then its rank. */
function RankLine({ ticker, rank, of, label }: { ticker: string; rank: number; of: number; label: string }) {
  return <><span className="font-data">{ticker}</span>{ranksOn(rank, of, label)}</>
}

/** The rank line's room while a metric picked loads (a bone over it) or has no rank to give (blank): the default answer's
 *  line laid out invisible in the line's own type, so the heading row keeps its height while the metric changes.
 *  aria-hidden, as every raw bone is: the plot's status names the wait, and its place the reason there is no rank. */
function HeldRankLine({ children, loading }: { children: ReactNode; loading: boolean }) {
  return (
    <div aria-hidden="true" data-held-rank className="grid w-fit max-w-full text-sm">
      <p className="invisible col-start-1 row-start-1">{children}</p>
      {loading && <Skeleton className="col-start-1 row-start-1" />}
    </div>
  )
}

/** A company's line in Sources & checks, each source check's and each "original SEC filing" link's: its ticker first,
 *  then its name as the tooltip gives it (formatCompanyName; two companies can answer one ticker, chief design's ruling
 *  on #1868), then its fiscal year, as Financial trends names a year's. "·" parts them, as in the tooltip, since a name
 *  can hold a comma ("META · Meta Platforms, Inc. · 2025"). */
const checkLabel = (entry: PeerEntry) =>
  [entry.ticker, formatCompanyName(entry.company_name), entry.fiscal_year ?? entry.period_end ?? 'period unavailable'].filter((part) => part !== '').join(' · ')

export default function SectorPeersCard({ ticker, answer, className }: {
  ticker: string
  /** The default metric's answer, a cohort the panel shows (the gate's read). */
  answer: PeerComparisonResponse
  /** The card's place on the page. */
  className?: string
}) {
  // The chart's inks are SVG attributes, not classes: the theme comes off the context (not useTheme), with a light
  // fallback, so a render without a provider (tests) never throws.
  const dark = useContext(ThemeContext)?.theme === 'dark'
  const tokens = chartTokens(dark)
  const fontReady = useChartFont()
  const headingId = useId()

  const [metric, setMetric] = useState(DEFAULT_METRIC)
  const picked = usePeers(ticker, metric)
  // The default metric is the gate's answer; a metric picked is its own read.
  const current = metric === DEFAULT_METRIC ? answer : picked.data
  const chart = useMemo(() => (shows(current) ? { ...peerChart(current), entries: drawn(current), answer: current } : null), [current])

  // The metric the view names: the one its answer ranks on (a bank's net interest income), or the one picked while there
  // is no answer to draw. The first option names the default answer's.
  const ranked = chart ? metricOf(chart.answer.concept) : null
  const label = ranked?.label ?? METRICS.find((option) => option.key === metric)!.label
  const options = METRICS.map((option) => ({ key: option.key, label: option.key === DEFAULT_METRIC ? metricOf(answer.concept)!.label : option.label }))
  const rank = chart ? rankOf(chart.answer) : null
  // The default answer's rank, a cohort's, whose line holds the room while a metric picked has no line of its own.
  const opening = rankOf(answer)!
  // An amount's reporting currency (CNY), named in the footnote; a margin or a multiple has none.
  const currency = chart && (ranked?.fmt === 'usd' || ranked?.fmt === 'eps') ? unitCurrency(chart.answer.unit ?? '').currency : null
  // Where the cohort is larger than the chart's slots, the footnote says what the chart shows; nothing where it draws
  // every company ranked.
  const cropped = chart ? croppedOf(chart.answer) : null
  const needsCheck = !!chart?.entries.some(needsSourceCheck)
  // Sources & checks: every company drawn, and every company whose value is withheld, which draws no bar, in every state:
  // with no chart, the withheld ones alone, a withheld subject the plot's place names among them.
  const withheld = (data: PeerComparisonResponse) => data.peers.filter((entry) => entry.provenance?.validation === 'unavailable')
  const checked = chart ? [...chart.entries, ...withheld(chart.answer)] : picked.data ? withheld(picked.data) : []

  return (
    <Card as="section" aria-labelledby={headingId} className={cx(className, 'p-cap-6')}>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 flex-col gap-0.5">
          <h2 id={headingId} className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">{HEADING}</h2>
          {chart && rank ? (
            <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
              <RankLine ticker={chart.answer.subject.ticker} rank={rank.rank} of={rank.of} label={label} />
            </p>
          ) : (
            <HeldRankLine loading={!picked.data && !picked.isError}>
              <RankLine ticker={answer.subject.ticker} rank={opening.rank} of={opening.of} label={metricOf(answer.concept)!.label} />
            </HeldRankLine>
          )}
        </div>
        {/* Nine metrics: a compact select of one width beside its label, never a segmented row. */}
        <label className="flex min-w-0 flex-wrap items-center gap-2 text-sm font-medium">
          Metric
          <select
            className={inputClasses({ select: true, density: 'compact', autoWidth: true, className: PICKER_WIDTH })}
            value={metric}
            onChange={(event) => setMetric(event.target.value)}
          >
            {options.map((option) => (
              <option key={option.key} value={option.key}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>

      {chart ? (
        <>
          <ChartPlotFrame model={chart.model} readouts={chart.reads} tokens={tokens} fontReady={fontReady} view="card">
            {({ layout, plot, busy }) => (
              // Busy while the plot waits for its font (G4): the plot holds bones of its own plan until then.
              <div data-testid="peers-chart" aria-busy={busy || undefined}>
                {plot}
                {/* Where A4 finds no label tier even at the widest slot, the bars print no values and the card says so, in
                    the line for a card no metrics table sits beside (layout.ts). */}
                {layout?.valuesDontFit && (
                  <p className="mt-2 text-xs" style={{ color: tokens.note }} data-chart-text="fit">{VALUES_DONT_FIT_HERE}</p>
                )}
              </div>
            )}
          </ChartPlotFrame>
          {/* The engine's own footnotes: a margin bar the axis clips is broken, and this line says its printed value is
              the true one. */}
          {chart.model.footnotes.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs" style={{ color: tokens.note }}>
              {chart.model.footnotes.map((footnote) => (
                <li key={`${footnote.mark}${footnote.text}`} data-chart-text="footnote">
                  {footnote.mark && <span className="mr-2 font-data">{footnote.mark}</span>}
                  {footnote.text}
                </li>
              ))}
            </ul>
          )}
        </>
      ) : picked.isError && !picked.data ? (
        <p className="flex items-center justify-center px-4 text-center text-sm" style={{ height: CARD_HEIGHT, color: tokens.note }} data-chart-text="unavailable">
          {failed(label)}
        </p>
      ) : picked.data ? (
        <p className="flex items-center justify-center px-4 text-center text-sm" style={{ height: CARD_HEIGHT, color: tokens.note }} data-chart-text="unavailable">
          {/* One inline run, so a ticker in the data face flows with its sentence rather than standing as a flex item. */}
          <span><NoCohortLine why={noCohort(picked.data) ?? 'few'} label={label} ticker={picked.data.subject.ticker} /></span>
        </p>
      ) : (
        // A metric picked, loading: the plot's bones at its height.
        <div role="status" aria-label="Loading sector peers">
          <Skeleton className="w-full rounded-lg" style={{ height: CARD_HEIGHT }} />
          <span className="sr-only">Loading…</span>
        </div>
      )}
      <p className="mt-3 text-xs text-text-tertiary-light dark:text-text-tertiary-dark">
        {footnoteOf(label, currency)}{cropped ? ` ${croppedLine(cropped)}` : ''}{needsCheck ? ` ${NEEDS_A_CHECK}` : ''}
      </p>
      <SourceChecks values={checked.map((entry) => ({ ...entry, label: checkLabel(entry) }))} />
    </Card>
  )
}
