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

/** The most companies the chart draws: the eleven slots the 502 px desktop card holds (E251's plan, §2 item 5). */
export const SLOTS = 11

/** The metric an answer ranks on, from its `concept`, not the metric asked: a bank asked for revenue answers net
 *  interest income. Null for a concept the panel cannot name or format. */
export const metricOf = (concept: string): Metric | null => FEATURED.find((metric) => metric.key === concept) ?? null

/** The companies with a value, in the answer's order (value descending, the ticker breaking a tie). */
const valued = (answer: PeerComparisonResponse) => answer.peers.filter((entry) => entry.value != null)

/** How many of the top companies `limit` slots hold without parting a rank: a cut that would separate two companies of
 *  one rank (a tie, which the server ranks alike) moves up to the first of them, so "the top N" is always the companies
 *  ranked N or better. Null where one rank fills every slot and more, so no cut keeps it whole. */
function topWithin(withValue: PeerEntry[], limit: number): number | null {
  if (withValue.length <= limit) return withValue.length
  let top = limit
  while (top > 0 && withValue[top].rank === withValue[top - 1].rank) top -= 1
  return top > 0 ? top : null
}

/** The chart's companies, as many as its eleven slots hold, and what it leaves out: every company with a value where
 *  there are eleven or fewer; otherwise the top companies (the top eleven where the subject ranks among them, else the
 *  top ten and then the subject), never parting a rank, so a tie at the cut leaves a slot empty rather than show one of
 *  two companies of one rank. Where one rank fills the slots, the cut goes by the answer's order and names no top. */
function cut(answer: PeerComparisonResponse) {
  const withValue = valued(answer)
  const at = withValue.findIndex((entry) => entry.is_subject)
  const top = topWithin(withValue, SLOTS)
  if (at < (top ?? SLOTS)) return { shown: withValue.slice(0, top ?? SLOTS), top, subject: null, of: withValue.length }
  const above = topWithin(withValue, SLOTS - 1)
  return { shown: [...withValue.slice(0, above ?? SLOTS - 1), withValue[at]], top: above, subject: withValue[at], of: withValue.length }
}

/** What the chart draws: the companies with a value, in the answer's order, as many as its eleven slots hold, so it
 *  never leaves out a company a slot could hold but for a tie at the cut. Where the subject ranks among the top eleven,
 *  the top eleven; where it ranks lower, the top ten and then the subject. A cohort of eleven or fewer draws every
 *  company with a value. A withheld value draws nothing; Sources & checks lists it. */
export const drawn = (answer: PeerComparisonResponse): PeerEntry[] => cut(answer).shown

/** What the chart leaves out, for the card to say so: null where it draws every company with a value; otherwise how
 *  many it draws, of how many companies ranked (the rank line's count), the top it draws (null where one rank fills
 *  the slots, so no top can be named), and the subject where it is drawn after them, from below. */
export function croppedOf(answer: PeerComparisonResponse): { shown: number; of: number; top: number | null; subject: PeerEntry | null } | null {
  const { shown, of, top, subject } = cut(answer)
  return shown.length === of ? null : { shown: shown.length, of, top, subject }
}

/** Why an answer draws no chart: it ranks a metric the panel cannot name or format ('concept'); the subject's own figure
 *  is missing, where the service synthesises a subject that holds no fact, or withheld ('subject'); or fewer than two
 *  companies have a value ('few'). */
export type NoCohort = 'concept' | 'subject' | 'few'

/** The first reason, in that order, an answer is no cohort the panel shows, or null where it is one. Never `peer_count`,
 *  which counts withheld entries: a pair with one withheld value would draw a chart of one bar. */
export function noCohort(answer: PeerComparisonResponse): NoCohort | null {
  if (!metricOf(answer.concept)) return 'concept'
  const withValue = valued(answer)
  if (!withValue.some((entry) => entry.is_subject)) return 'subject'
  if (withValue.length < 2) return 'few'
  return null
}

/** Whether an answer is a cohort the panel shows: a metric it names, the subject's own figure and at least one other
 *  company's (no reason of noCohort's stops it). */
export const shows = (answer: PeerComparisonResponse | undefined): answer is PeerComparisonResponse => answer != null && noCohort(answer) == null

/** The subject's rank over the companies with a value, the rank's own population, never `peer_count`; null without
 *  one. */
export function rankOf(answer: PeerComparisonResponse): { rank: number; of: number } | null {
  const withValue = valued(answer)
  const rank = withValue.find((entry) => entry.is_subject)?.rank
  return rank == null ? null : { rank, of: withValue.length }
}
