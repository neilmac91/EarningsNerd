/* =============================================================================
   Earnings calendar — FIXTURES (features/calendar/api/calendar-fixtures.ts)
   -----------------------------------------------------------------------------
   ⚠ NOT PRODUCTION DATA. This module stands in for the backend while
   GET /api/calendar is being built. It is reachable ONLY through the dynamic
   imports in calendar-api.ts, gated on NEXT_PUBLIC_CALENDAR_FIXTURES='true' —
   delete the flag (or this file) and the page runs purely against the API.

   Shape honesty: everything here matches the §3.3 earnings_events contract,
   including the alert-cap 403s (free cap carries code='earnings_alert_limit';
   the pro cap is a terse generic message with no code).
============================================================================= */

import {
  type CalendarEvent,
  type EventTime,
  EarningsAlertError,
  EARNINGS_ALERT_LIMIT_CODE,
} from './calendar-api'
import { addDaysIso, isoDayOfWeek, diffDays, marketHolidayName, todayEasternIso } from '../lib/dates'

const LATENCY_MS = 450

/** Curated 2026 Q2/Q3 season anchors (several verified against live feeds in
    tasks/earnings-calendar-strategy.md's appendix). Each repeats every 91 days
    (13 weeks — same weekday) so any navigated range has plausible data.
    [ticker, name, anchorDate, slot, anticipationBase, epsBase] */
const COMPANIES: Array<[string, string, string, EventTime, number, number]> = [
  ['GIS', 'General Mills', '2026-06-29', 'bmo', 56, 1.05],
  ['MU', 'Micron Technology', '2026-06-30', 'amc', 84, 2.5],
  ['CCL', 'Carnival', '2026-06-30', 'bmo', 62, 0.32],
  ['PAYX', 'Paychex', '2026-07-01', 'bmo', 54, 1.18],
  ['STZ', 'Constellation Brands', '2026-07-01', 'amc', 58, 3.32],
  ['AYI', 'Acuity', '2026-07-02', 'bmo', 44, 4.3],
  ['LEVI', 'Levi Strauss', '2026-07-08', 'bmo', 52, 0.31],
  ['AZZ', 'AZZ', '2026-07-08', null, 40, 1.55],
  ['DAL', 'Delta Air Lines', '2026-07-09', 'bmo', 71, 2.05],
  ['PSMT', 'PriceSmart', '2026-07-09', 'amc', 42, 1.32],
  ['WDFC', 'WD-40', '2026-07-09', 'amc', 41, 1.42],
  ['HELE', 'Helen of Troy', '2026-07-09', 'dmh', 39, 1.6],
  ['JPM', 'JPMorgan Chase', '2026-07-14', 'bmo', 93, 4.55],
  ['WFC', 'Wells Fargo', '2026-07-14', 'bmo', 78, 1.4],
  ['C', 'Citigroup', '2026-07-14', 'bmo', 76, 1.62],
  ['PEP', 'PepsiCo', '2026-07-14', 'bmo', 79, 2.03],
  ['FAST', 'Fastenal', '2026-07-14', 'bmo', 51, 0.29],
  ['JBHT', 'J.B. Hunt', '2026-07-14', 'amc', 49, 1.34],
  ['BAC', 'Bank of America', '2026-07-15', 'bmo', 81, 0.86],
  ['GS', 'Goldman Sachs', '2026-07-15', 'bmo', 80, 9.6],
  ['MS', 'Morgan Stanley', '2026-07-15', 'bmo', 78, 1.96],
  ['UNH', 'UnitedHealth', '2026-07-15', 'bmo', 83, 4.45],
  ['ASML', 'ASML Holding', '2026-07-15', 'bmo', 82, 6.1],
  ['JNJ', 'Johnson & Johnson', '2026-07-16', 'bmo', 79, 2.68],
  ['TSM', 'Taiwan Semiconductor', '2026-07-16', 'bmo', 88, 2.3],
  ['ABT', 'Abbott Laboratories', '2026-07-16', 'bmo', 71, 1.25],
  ['NFLX', 'Netflix', '2026-07-16', 'amc', 90, 7.08],
  ['AXP', 'American Express', '2026-07-17', 'bmo', 74, 3.9],
  ['SCHW', 'Charles Schwab', '2026-07-17', 'bmo', 68, 1.08],
  ['KO', 'Coca-Cola', '2026-07-21', 'bmo', 77, 0.83],
  ['LMT', 'Lockheed Martin', '2026-07-21', 'bmo', 66, 6.5],
  ['GOOGL', 'Alphabet', '2026-07-22', 'amc', 96, 2.34],
  ['TSLA', 'Tesla', '2026-07-22', 'amc', 97, 0.48],
  ['IBM', 'IBM', '2026-07-22', 'amc', 72, 2.8],
  ['T', 'AT&T', '2026-07-23', 'bmo', 70, 0.54],
  ['INTC', 'Intel', '2026-07-23', 'amc', 82, 0.12],
  ['ADP', 'ADP', '2026-07-29', 'bmo', 63, 2.28],
  ['BA', 'Boeing', '2026-07-29', 'bmo', 74, -0.9],
  ['MSFT', 'Microsoft', '2026-07-29', 'amc', 98, 3.68],
  ['META', 'Meta Platforms', '2026-07-29', 'amc', 95, 6.35],
  ['V', 'Visa', '2026-07-29', 'amc', 84, 2.63],
  ['QCOM', 'Qualcomm', '2026-07-29', 'amc', 75, 2.85],
  ['NOW', 'ServiceNow', '2026-07-29', 'amc', 71, 3.95],
  ['HOOD', 'Robinhood', '2026-07-29', 'amc', 69, 0.42],
  ['AAPL', 'Apple', '2026-07-30', 'amc', 99, 1.66],
  ['AMZN', 'Amazon', '2026-07-30', 'amc', 97, 1.48],
  ['MA', 'Mastercard', '2026-07-30', 'bmo', 83, 4.12],
  ['CAT', 'Caterpillar', '2026-07-30', 'bmo', 72, 4.9],
  ['CMCSA', 'Comcast', '2026-07-30', 'bmo', 64, 1.21],
  ['SBUX', 'Starbucks', '2026-07-30', 'amc', 73, 0.65],
  ['XOM', 'Exxon Mobil', '2026-07-31', 'bmo', 80, 1.92],
  ['CVX', 'Chevron', '2026-07-31', 'bmo', 76, 2.45],
  ['PLTR', 'Palantir', '2026-08-03', 'amc', 86, 0.16],
  ['AMD', 'AMD', '2026-08-04', 'amc', 89, 1.12],
  ['UBER', 'Uber', '2026-08-05', 'bmo', 79, 0.88],
  ['DIS', 'Disney', '2026-08-05', 'bmo', 81, 1.45],
  ['SHOP', 'Shopify', '2026-08-06', 'bmo', 74, 0.34],
  ['COIN', 'Coinbase', '2026-08-06', 'amc', 77, 1.05],
  ['NVDA', 'NVIDIA', '2026-08-26', 'amc', 100, 1.24],
  ['CRM', 'Salesforce', '2026-09-03', 'amc', 78, 2.78],
  ['AVGO', 'Broadcom', '2026-09-03', 'amc', 85, 1.72],
  ['ORCL', 'Oracle', '2026-09-09', 'amc', 82, 1.48],
  ['ADBE', 'Adobe', '2026-09-15', 'amc', 74, 5.15],
  ['FDX', 'FedEx', '2026-09-17', 'amc', 70, 5.3],
  ['NKE', 'Nike', '2026-09-24', 'amc', 75, 0.71],
]

function hash(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0
  return h
}

function buildEvents(from: string, to: string): CalendarEvent[] {
  const today = todayEasternIso()
  const out: CalendarEvent[] = []
  for (const [ticker, name, anchor, slot, score, epsBase] of COMPANIES) {
    const h = hash(ticker)
    for (let k = -8; k <= 8; k++) {
      let date = addDaysIso(anchor, k * 91)
      let guard = 0
      while ((isoDayOfWeek(date) === 0 || isoDayOfWeek(date) === 6 || marketHolidayName(date)) && guard < 5) {
        date = addDaysIso(date, -1)
        guard++
      }
      if (date < from || date > to) continue
      const dd = diffDays(today, date) // negative = past
      let status: CalendarEvent['status']
      let confidence: CalendarEvent['confidence']
      if (dd < 0) {
        status = 'reported'
        confidence = 'high'
      } else if (dd <= (score >= 80 ? 21 : 12) && (h + k) % 4 !== 0) {
        status = 'confirmed'
        confidence = 'high'
      } else {
        status = 'estimated'
        confidence = dd <= 14 ? ((h + k) % 2 ? 'high' : 'medium') : dd <= 45 ? 'medium' : score < 70 ? 'low' : 'medium'
      }
      const est = score < 50 && h % 3 === 0 ? null : Math.round(epsBase * (1 + 0.02 * k) * 100) / 100
      const actual =
        status === 'reported' && est !== null ? Math.round(est * (1 + (((h + k) % 9) - 4) / 50) * 100) / 100 : null
      out.push({
        ticker,
        company_name: name,
        event_date: date,
        event_time: slot,
        status,
        confidence,
        eps_estimate: est,
        eps_actual: actual,
        anticipation_score: Math.max(0, Math.min(100, score + ((h + k) % 7) - 3)),
      })
    }
  }
  return out
}

const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

export async function fixtureCalendar(from: string, to: string): Promise<CalendarEvent[]> {
  await wait(LATENCY_MS)
  return buildEvents(from, to)
}

// ---- Alert-toggle fixture state (in-memory; free plan by default) ----------
// FIXTURE_PLAN lets a dev exercise every cap behavior without a backend.
type FixturePlan = 'free' | 'pro' | 'pro-at-cap'
const FIXTURE_PLAN: FixturePlan = (process.env.NEXT_PUBLIC_CALENDAR_FIXTURE_PLAN as FixturePlan) || 'free'
const enabled = new Set<string>(['NVDA', 'AAPL'])

export async function fixtureAlertTickers(): Promise<string[]> {
  await wait(120)
  return Array.from(enabled)
}

export async function fixtureEnableAlert(ticker: string): Promise<void> {
  await wait(280)
  if (FIXTURE_PLAN === 'free' && enabled.size >= 3 && !enabled.has(ticker)) {
    throw new EarningsAlertError(
      403,
      'Free includes earnings alerts for 3 companies — upgrade to Pro for more.',
      EARNINGS_ALERT_LIMIT_CODE,
    )
  }
  if (FIXTURE_PLAN === 'pro-at-cap' && !enabled.has(ticker)) {
    // The pro guardrail is invisible until hit: terse, generic, no code, no numbers.
    throw new EarningsAlertError(403, "You've reached the maximum number of earnings alerts.")
  }
  enabled.add(ticker)
}

export async function fixtureDisableAlert(ticker: string): Promise<void> {
  await wait(280)
  enabled.delete(ticker)
}
