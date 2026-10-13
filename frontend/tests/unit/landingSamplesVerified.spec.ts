import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import * as samples from '@/features/marketing/lib/landing-samples'

/**
 * Sample figures on the landing page come only from the verified Apple FY2025 set (audit pub/F01,
 * pub/F07; docs/brand/00-audit.md §4), and read the way a real payload renders them. Before this spec
 * the product-screen specs pinned whatever the samples held, so drift went unseen: an Ask answer whose
 * Services figure the Copilot tool cannot fetch, a `[F1]` marker no live answer carries (the server
 * renumbers every marker [1], [2], [3] in first-appearance order, copilot/resolution.py), and a chip
 * labelled with the raw concept `NetIncomeLoss`.
 *
 * It reads every string and number in landing-samples.ts (the Multi-Period demo excepted: it is the
 * FY2019 to FY2024 pipeline snapshot, regenerated only through the pipeline, decision D7) and the hero's
 * static fallback in HeroExample.tsx, and checks:
 *  - every dollar figure and percentage is one the verified set yields (a value at one or two decimals
 *    of a billion, a per-share value, or a year-over-year change at one decimal);
 *  - every Change Report number is a verified raw value, and its percentage the change between them;
 *  - the verified set below is the one 00-audit.md §4 records, digit for digit;
 *  - the Ask answer's markers are sequential [n] matching its citations, never [F1]; an XBRL citation
 *    reads as copilot_tools.fact_to_citation writes one; a passage is the filing's sentence verbatim;
 *  - no figure row is labelled with a CamelCase or namespaced XBRL concept.
 */

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const AUDIT = readFileSync(path.join(FRONTEND, '../docs/brand/00-audit.md'), 'utf8')
const HERO = readFileSync(path.join(FRONTEND, 'features/marketing/components/HeroExample.tsx'), 'utf8')

/** FY2025 and FY2024, as docs/brand/00-audit.md §4 records them (USD unless per share). */
const VERIFIED: Record<string, readonly [number, number]> = {
  RevenueFromContractWithCustomerExcludingAssessedTax: [416_161_000_000, 391_035_000_000],
  NetIncomeLoss: [112_010_000_000, 93_736_000_000],
  EarningsPerShareDiluted: [7.46, 6.08],
  NetCashProvidedByUsedInOperatingActivities: [111_482_000_000, 118_254_000_000],
  PaymentsOfDividends: [15_421_000_000, 15_234_000_000],
  'Services net sales': [109_158_000_000, 96_169_000_000],
}
const RAW = new Set(Object.values(VERIFIED).flat())

const growth = ([current, prior]: readonly [number, number]) => ((current - prior) / Math.abs(prior)) * 100
const DOLLARS = new Set(
  [...RAW].flatMap((v) => (v >= 1e9 ? [`$${(v / 1e9).toFixed(1)}B`, `$${(v / 1e9).toFixed(2)}B`] : [`$${v.toFixed(2)}`])),
)
const PERCENTS = new Set(Object.values(VERIFIED).map((pair) => `${Math.abs(growth(pair)).toFixed(1)}%`))

const DOLLAR_RE = /\$\d[\d,]*(?:\.\d+)?[BMT]?/g
const PERCENT_RE = /\d+(?:\.\d+)?%/g

/** Every string and number reachable from a value, with the path that leads to it. */
function leaves(value: unknown, at: string, out: { at: string; value: string | number }[] = []) {
  if (typeof value === 'string' || typeof value === 'number') out.push({ at, value })
  else if (Array.isArray(value)) value.forEach((item, i) => leaves(item, `${at}[${i}]`, out))
  else if (value && typeof value === 'object') for (const [key, item] of Object.entries(value)) leaves(item, `${at}.${key}`, out)
  return out
}

// The Multi-Period demo is the pipeline snapshot (D7); the URL holds the accession, not a figure.
const SAMPLES = Object.entries(samples).filter(([name]) => name !== 'SAMPLE_ANALYSIS_DATASET' && name !== 'AAPL_FY25_EDGAR_URL')
const STRINGS = SAMPLES.flatMap(([name, value]) => leaves(value, name)).filter(
  (leaf): leaf is { at: string; value: string } => typeof leaf.value === 'string' && !leaf.at.endsWith('url'),
)

/** The hero's static fallback, as written in HeroExample.tsx (its figures render without the server). */
const FALLBACK_SOURCE = HERO.slice(HERO.indexOf('const FALLBACK: ExampleData = {'), HERO.indexOf('\n}\n', HERO.indexOf('const FALLBACK: ExampleData = {')))

describe('landing sample figures come from the verified Apple FY2025 set', () => {
  it('the verified set is the one docs/brand/00-audit.md §4 records', () => {
    const section = AUDIT.slice(AUDIT.indexOf('## 4. Facts the later phases must carry'))
    for (const [concept, pair] of Object.entries(VERIFIED)) {
      for (const v of pair) {
        const written = Number.isInteger(v) ? v.toLocaleString('en-US') : v.toFixed(2)
        expect(section, `${concept} ${written}`).toContain(written)
      }
    }
    expect(FALLBACK_SOURCE).toContain("ticker: 'AAPL'")
  })

  it('every dollar figure and percentage in the samples and the hero fallback is one the set yields', () => {
    const strays: string[] = []
    const texts = [...STRINGS, { at: 'HeroExample FALLBACK', value: FALLBACK_SOURCE }]
    for (const { at, value } of texts) {
      for (const figure of value.match(DOLLAR_RE) ?? []) if (!DOLLARS.has(figure)) strays.push(`${at}: ${figure}`)
      for (const pct of value.match(PERCENT_RE) ?? []) if (!PERCENTS.has(pct)) strays.push(`${at}: ${pct}`)
    }
    for (const [, delta] of FALLBACK_SOURCE.matchAll(/deltaPercent: (-?\d+(?:\.\d+)?)/g)) {
      if (!PERCENTS.has(`${Math.abs(Number(delta)).toFixed(1)}%`)) strays.push(`HeroExample FALLBACK deltaPercent: ${delta}`)
    }
    expect(strays).toEqual([])
    // Anti-vacuity: the scan reads the figures the page shows.
    expect(STRINGS.some((s) => s.value.includes('$416.2B'))).toBe(true)
    expect(FALLBACK_SOURCE).toContain('$112.0B')
  })

  it('every Change Report number is a verified value, and its percentage the change between them', () => {
    const items = samples.SAMPLE_CHANGE_REPORT.metrics?.items ?? []
    expect(items.length).toBeGreaterThan(0)
    for (const item of items) {
      expect(RAW.has(item.current as number), `${item.metric} current`).toBe(true)
      expect(RAW.has(item.prior as number), `${item.metric} prior`).toBe(true)
      expect((item.pct as number).toFixed(1), `${item.metric} pct`).toBe(growth([item.current as number, item.prior as number]).toFixed(1))
    }
  })
})

describe('the Ask this Filing sample reads as a live answer does', () => {
  const { answer, citations } = samples.SAMPLE_ASK

  it('numbers its markers [1], [2], [3] in order, one per citation, never [F1]', () => {
    const markers = [...answer.matchAll(/\[([^\]]+)\]/g)].map((m) => m[1])
    expect(markers).toEqual(citations.map((c, i) => String(i + 1)))
    expect(citations.map((c) => c.n)).toEqual(citations.map((c, i) => i + 1))
    for (const { at, value } of STRINGS) expect(value, at).not.toMatch(/\[F\s*\d+\]/i)
  })

  it('writes an XBRL citation as fact_to_citation does, and a passage as the filing words it', () => {
    const xbrl = citations.filter((c) => c.section_ref?.startsWith('XBRL'))
    const passages = citations.filter((c) => !c.section_ref?.startsWith('XBRL'))
    expect(xbrl.length).toBeGreaterThan(0)
    expect(passages.length).toBeGreaterThan(0)
    for (const c of xbrl) {
      // copilot_tools.py: `{label} = {value} {unit} ({period})` or `{label} YoY growth = {pct}% ({period})`,
      // with the section ref `XBRL · {raw_tag}`.
      expect(c.excerpt).toMatch(/^(?:Revenue|Net income|EPS \(diluted\)) (?:= \$[\d,.]+[BM]? USD|YoY growth = [\d.]+%) \(FY\d{4}\/FY\)$/)
      expect(c.section_ref).toMatch(/^XBRL · us-gaap:[A-Za-z]+$/)
      expect(Object.keys(VERIFIED)).toContain((c.section_ref as string).replace('XBRL · us-gaap:', ''))
    }
    for (const c of passages) expect(AUDIT.replace(/\s+/g, ' '), c.excerpt).toContain(c.excerpt)
    expect(AUDIT.replace(/\s+/g, ' ')).toContain(samples.SAMPLE_TRACE.excerpt)
  })
})

describe('figure rows carry a label, not an XBRL concept', () => {
  it('no xbrl_concept shown on a chip is CamelCase or namespaced', () => {
    const labels = samples.SAMPLE_FINANCIAL_METRICS.map((row) => row.xbrl_concept).filter((c): c is string => !!c)
    expect(labels.length).toBeGreaterThan(0)
    for (const label of labels) {
      expect(label).not.toMatch(/:|^[A-Z][a-z]+(?:[A-Z][a-z]*)+$/)
    }
  })
})
