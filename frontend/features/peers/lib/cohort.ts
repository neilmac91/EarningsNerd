/**
 * The company page's Sector peers panel reads a peers answer through these (E251): which metrics it offers, which
 * companies it draws, whether it shows at all, the subject's rank and the metric the answer ranks on. Engine-free and
 * pure, so the small component the page imports statically decides with them and the engine's chunk loads only for a
 * company with a cohort (SectorPeers.tsx).
 */
import { FEATURED } from '@/features/fundamentals/lib/featuredMetrics'
import type { PeerComparisonResponse, PeerEntry } from '@/features/peers/api/peers-api'

/** The metric the panel opens on. Its answer alone decides whether the panel shows. */
export const DEFAULT_METRIC = 'revenue'

/** A metric as Financial trends names and formats it (features/fundamentals/lib/featuredMetrics.ts). */
export type Metric = (typeof FEATURED)[number]

/** The picker's metrics, the retired panel's nine, each label and format read from FEATURED. */
export const METRICS: Metric[] = [
  'revenue', 'net_income', 'gross_profit', 'operating_income', 'net_margin', 'operating_margin', 'gross_margin',
  'eps_diluted', 'total_assets',
].map((key) => FEATURED.find((metric) => metric.key === key)!)

/** How many companies the chart draws by value before the subject: the top ten, then the subject wherever it ranks. */
export const TOP = 10

/** The metric an answer ranks on, from its `concept`, not the metric asked: a bank asked for revenue answers net
 *  interest income. Null for a concept the panel cannot name or format. */
export const metricOf = (concept: string): Metric | null => FEATURED.find((metric) => metric.key === concept) ?? null

/** The companies with a value, in the answer's order (value descending, the ticker breaking a tie). */
const valued = (answer: PeerComparisonResponse) => answer.peers.filter((entry) => entry.value != null)

/** What the chart draws: the companies with a value, the top ten in the answer's order and then the subject where it
 *  ranks lower (eleven bars at most, the retired panel's rule). A withheld value draws nothing; Sources & checks lists
 *  it. */
export function drawn(answer: PeerComparisonResponse): PeerEntry[] {
  const withValue = valued(answer)
  const top = withValue.slice(0, TOP)
  const subject = withValue.find((entry) => entry.is_subject)
  return subject && !top.includes(subject) ? [...top, subject] : top
}

/** Whether an answer is a cohort the panel shows: the subject holds a value and at least one other company does, on a
 *  metric it can name. Never `peer_count`, which counts withheld entries: a pair with one withheld value would draw a
 *  chart of one bar. */
export function shows(answer: PeerComparisonResponse | undefined): answer is PeerComparisonResponse {
  if (!answer || !metricOf(answer.concept)) return false
  const withValue = valued(answer)
  return withValue.length >= 2 && withValue.some((entry) => entry.is_subject)
}

/** The subject's rank over the companies with a value, the rank's own population, never `peer_count`; null without
 *  one. */
export function rankOf(answer: PeerComparisonResponse): { rank: number; of: number } | null {
  const withValue = valued(answer)
  const rank = withValue.find((entry) => entry.is_subject)?.rank
  return rank == null ? null : { rank, of: withValue.length }
}
