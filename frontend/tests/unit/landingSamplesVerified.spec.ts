import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import demo from '@/features/analysis/demo/demo-analysis.json'
import type { AnalysisCompletion, AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { resolveDataNotes } from '@/features/analysis/lib/dataNotes'
import { decodeDataNotes } from '@/features/analysis/lib/dataNotesContract'
import { decodeNarrativePresentation } from '@/features/analysis/lib/narrativePresentation'
import * as samples from '@/features/marketing/lib/landing-samples'

/**
 * Sample figures on the landing page come only from the verified Apple FY2025 set (audit pub/F01,
 * pub/F07; docs/brand/00-audit.md §4), and read the way a real payload renders them. Before this spec
 * the product-screen specs pinned whatever the samples held, so drift went unseen: an Ask answer whose
 * Services figure the Copilot tool cannot fetch, a `[F1]` marker no live answer carries (the server
 * renumbers every marker [1], [2], [3] in first-appearance order, copilot/resolution.py), and a chip
 * labelled with the raw concept `NetIncomeLoss`.
 *
 * It reads every string and number in landing-samples.ts (the Multi-Period demo excepted from that scan:
 * it is one pipeline run, FY2020 to FY2025, regenerated only through the pipeline, decision D-046 D7, and
 * holds figures for years and concepts the verified set does not) and the hero's static fallback in
 * HeroExample.tsx, and checks:
 *  - every dollar figure and percentage is one the verified set yields (a value at one or two decimals
 *    of a billion, a per-share value, or a year-over-year change at one decimal);
 *  - each hero fallback figure and each Financial Highlights row holds its own label's verified values
 *    (that scan pools figures across concepts, so Revenue showing net income's figure would pass it);
 *  - every Change Report number is a verified raw value, and its percentage the change between them;
 *  - the verified set below is the one 00-audit.md §4 records, digit for digit;
 *  - the Ask answer's markers are sequential [n] matching its citations, never [F1]; an XBRL citation
 *    reads as copilot_tools.fact_to_citation writes one, its label names the concept its section ref
 *    holds, its figure is that concept's FY2025 value (or growth), and the figure the answer puts
 *    before its marker rounds from it; a passage is the filing's sentence verbatim;
 *  - the Copilot teaser's blurred sample (CopilotTeaser.tsx, read from its source as the hero fallback
 *    is) states only the verified Services pair, a dimensioned fact the tool cannot fetch, so it cites
 *    passages: its markers run [1], [2] with one matched source each, it names the drivers the
 *    filing's Item 7 sentence names, and it shows no XBRL marker, locator, tag or braces glyph;
 *  - no figure row is labelled with a CamelCase or namespaced XBRL concept;
 *  - the Multi-Period demo (features/analysis/demo/demo-analysis.json, the teaser's and the landing's) is the
 *    run its comment names, ending at FY2025: its FY2025 and FY2024 revenue, net income, diluted EPS and
 *    operating cash flow are the verified values, tagged and filed as the verified 10-K; its citations are
 *    its own dataset's figures; its data notes and narrative evidence pass the admission the live API path
 *    applies; no key or string in it names a model; and the landing's three-series view counts data notes from
 *    those three series alone.
 */

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const AUDIT = readFileSync(path.join(FRONTEND, '../docs/brand/00-audit.md'), 'utf8')
const HERO = readFileSync(path.join(FRONTEND, 'features/marketing/components/HeroExample.tsx'), 'utf8')
const CONFIG = readFileSync(path.join(FRONTEND, '../backend/app/config.py'), 'utf8')

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

  it("holds each hero fallback figure and each Highlights row to its own label's verified values", () => {
    // The concept behind each label the two show, as the Ask chip clause below ties its labels.
    const ROW_CONCEPT: Record<string, string> = {
      Revenue: 'RevenueFromContractWithCustomerExcludingAssessedTax',
      'Net income': 'NetIncomeLoss',
      'Diluted EPS': 'EarningsPerShareDiluted',
    }
    const SCALE: Record<string, number> = { B: 1e9, M: 1e6, '': 1 }
    /** A verified value as `shown` writes its figure: in its unit, to its decimals. */
    const asShown = (v: number, shown: string) => {
      const [, places = '', unit = ''] = shown.match(/^\$\d+(?:\.(\d+))?([BM]?)$/) ?? []
      return `$${(v / SCALE[unit]).toFixed(places.length)}${unit}`
    }
    /** A change as the hero's formatDelta and a payload's change_display write it. */
    const signed = (pct: number) => `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`
    const verified = (at: string, label: string) => {
      const pair = VERIFIED[ROW_CONCEPT[label]]
      expect(pair, `${at} ${label}: a label with a verified concept`).toBeDefined()
      return pair
    }

    // HeroExample.tsx's fallback metrics, `{ label, value, deltaPercent }`, as written there.
    const fallback = [...FALLBACK_SOURCE.matchAll(/\{ label: '([^']+)', value: '([^']+)', deltaPercent: (-?\d+(?:\.\d+)?) \}/g)]
    expect(fallback.length, 'the hero fallback has figures').toBeGreaterThan(0)
    expect(fallback.length, 'every fallback metric reads as { label, value, deltaPercent }').toBe(FALLBACK_SOURCE.match(/\blabel:/g)?.length)
    for (const [, label, value, delta] of fallback) {
      const [current, prior] = verified('HeroExample FALLBACK', label)
      expect(`${value} ${signed(Number(delta))}`, `HeroExample FALLBACK ${label}`).toBe(`${asShown(current, value)} ${signed(growth([current, prior]))}`)
    }

    const rows = samples.SAMPLE_FINANCIAL_METRICS
    expect(rows.length, 'the Highlights table has rows').toBeGreaterThan(0)
    for (const row of rows) {
      const [current, prior] = verified('SAMPLE_FINANCIAL_METRICS', row.metric)
      expect(`${row.current_period} vs ${row.prior_period} ${row.change_display}`, `SAMPLE_FINANCIAL_METRICS ${row.metric}`).toBe(
        `${asShown(current, row.current_period)} vs ${asShown(prior, row.prior_period)} ${signed(growth([current, prior]))}`,
      )
    }
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

  it("ties each XBRL chip's figure to its own concept, and the answer's figure to the chip it cites", () => {
    // fact_to_citation's label for each concept the samples cite.
    const LABEL_CONCEPT: Record<string, string> = {
      Revenue: 'RevenueFromContractWithCustomerExcludingAssessedTax',
      'Net income': 'NetIncomeLoss',
      'EPS (diluted)': 'EarningsPerShareDiluted',
    }
    const SCALE: Record<string, number> = { B: 1e9, M: 1e6, '': 1 }
    const decimals = (n: string) => (n.split('.')[1] ?? '').length
    const xbrl = citations.filter((c) => c.section_ref?.startsWith('XBRL'))
    expect(xbrl.length).toBeGreaterThan(0)
    for (const c of xbrl) {
      const m = c.excerpt.match(/^(Revenue|Net income|EPS \(diluted\)) (?:= \$([\d,.]+)([BM]?) USD|YoY growth = ([\d.]+)%) \(FY(\d{4})\/FY\)$/)
      expect(m, c.excerpt).not.toBeNull()
      const [, label, value, unit = '', pct, year] = m as RegExpMatchArray
      const concept = (c.section_ref as string).replace('XBRL · us-gaap:', '')
      expect(LABEL_CONCEPT[label], `[${c.n}] label ${label}`).toBe(concept)
      expect(year, `[${c.n}] period`).toBe('2025')
      const pair = VERIFIED[concept]
      // The figure the answer places just before this chip's marker, in the same sentence.
      const before = answer.slice(0, answer.indexOf(`[${c.n}]`)).split(/\]|\.\s/).pop() ?? ''
      if (value !== undefined) {
        const chip = Number(value.replace(/,/g, ''))
        expect(chip, `[${c.n}] ${c.excerpt}`).toBe(Number((pair[0] / SCALE[unit]).toFixed(decimals(value))))
        const said = [...before.matchAll(/\$(\d[\d,]*(?:\.\d+)?)([BM]?)/g)].pop()
        expect(said, `the answer states a figure before [${c.n}]`).toBeDefined()
        const [, n, u = ''] = said as RegExpMatchArray
        expect(u, `[${c.n}] unit`).toBe(unit)
        expect(Number(n.replace(/,/g, '')), `[${c.n}] answer figure`).toBe(Number(chip.toFixed(decimals(n))))
      } else {
        expect(pct, `[${c.n}] ${c.excerpt}`).toBe(growth(pair).toFixed(decimals(pct)))
        const said = [...before.matchAll(/(\d+(?:\.\d+)?)%/g)].pop()
        expect(said, `the answer states a percentage before [${c.n}]`).toBeDefined()
        const n = (said as RegExpMatchArray)[1]
        expect(Number(n), `[${c.n}] answer percentage`).toBe(Number(Number(pct).toFixed(decimals(n))))
      }
    }
  })
})

describe("the Copilot teaser's sample cites passages, as a live Services answer does", () => {
  // The teaser answers a Services question. Services net sales is a dimensioned fact: companyfacts does not
  // carry it and the Copilot tool cannot fetch it, so a live answer cites its figures to passages of the
  // filing, never to an XBRL chip, while the landing's Ask demo answers total net sales with XBRL chips
  // (docs/brand/08-applications.md §1, Sample data).
  const TEASER = readFileSync(path.join(FRONTEND, 'features/filings/components/copilot/CopilotTeaser.tsx'), 'utf8')
  const BLOCK = TEASER.slice(TEASER.indexOf('{/* Blurred sample answer'), TEASER.indexOf('{/* Value props */}'))
  /** What the sample renders: its JSX comments and tags dropped, whitespace collapsed. */
  const TEXT = BLOCK.replace(/\{\/\*[\s\S]*?\*\/\}/g, ' ').replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
  const SERVICES = VERIFIED['Services net sales']

  it('reads the sample the teaser renders', () => {
    expect(BLOCK.length, 'the sample sits between its comment and the value props').toBeGreaterThan(0)
    expect(TEXT).toContain('AAPL · 10-K · FY2025')
  })

  it('states only the verified Services pair and its growth', () => {
    const dollars = new Set(SERVICES.flatMap((v) => [`$${(v / 1e9).toFixed(1)}B`, `$${(v / 1e9).toFixed(2)}B`]))
    const figures = TEXT.match(DOLLAR_RE) ?? []
    const percents = TEXT.match(PERCENT_RE) ?? []
    expect(figures, 'the sample states the Services figures').toContain(`$${(SERVICES[0] / 1e9).toFixed(1)}B`)
    for (const figure of figures) expect(dollars, `teaser ${figure}: a Services value`).toContain(figure)
    expect(percents, 'the teaser states the Services change, at one decimal').toEqual([`${growth(SERVICES).toFixed(1)}%`])
  })

  it('names the drivers in the words of the Item 7 sentence it cites', () => {
    const sentence = AUDIT.replace(/\s+/g, ' ').match(/"(Services net sales increased during 2025[^"]*)"/)?.[1] ?? ''
    const drivers = sentence.match(/higher net sales from (.+)\.$/)?.[1]
    expect(drivers, '00-audit.md §4 records the Item 7 sentence').toBeTruthy()
    const before = TEXT.slice(0, TEXT.indexOf('[2]')).trim()
    expect(before.endsWith(drivers as string), `the sentence before [2] names "${drivers}"`).toBe(true)
  })

  it('cites passages: markers [1] and [2], one matched source each, and no XBRL marker, locator, tag or glyph', () => {
    const markers = [...TEXT.matchAll(/\[([^\]]+)\]/g)].map((m) => m[1])
    expect(markers).toEqual(['1', '2'])
    expect(TEXT).toContain(`${markers.length} matched sources`)
    expect(TEXT).not.toMatch(/\[F\s*\d+\]|\bXBRL\b|us-gaap:/i)
    expect(BLOCK, 'braces mark an XBRL figure (DESIGN_SYSTEM.md, Evidence identity)').not.toContain('BracketsCurly')
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

describe('the Multi-Period demo is one pipeline run, ending at the verified fiscal year (D-046 D7)', () => {
  // The teaser and the landing read the payload as checked in, without the decoders the live API path applies.
  const dataset = demo.dataset as unknown as AnalysisDataset
  const completion = demo.completion as unknown as AnalysisCompletion
  const points = (concept: string) => dataset.series.find((series) => series.concept === concept)?.points ?? []

  it('covers FY2020 to FY2025, the window and run its comment names', () => {
    expect(dataset.periods.map((period) => period.key)).toEqual(['FY2020', 'FY2021', 'FY2022', 'FY2023', 'FY2024', 'FY2025'])
    expect(dataset.period_key).toBe('FY2020..FY2025')
    expect(demo._comment).toContain('Apple Inc., annual, FY2020 to FY2025, on a local backend on 2026-10-20')
    expect(demo._comment).toContain('USD 0.00046')
  })

  it('holds the verified FY2025 and FY2024 values for each concept the two share, from the verified 10-K', () => {
    // The demo's concept and the us-gaap tag the verified set (docs/brand/00-audit.md §4) names it by.
    const SHARED: Record<string, string> = {
      revenue: 'RevenueFromContractWithCustomerExcludingAssessedTax',
      net_income: 'NetIncomeLoss',
      eps_diluted: 'EarningsPerShareDiluted',
      operating_cash_flow: 'NetCashProvidedByUsedInOperatingActivities',
    }
    const accession = samples.AAPL_FY25_EDGAR_URL.match(/\/(\d{18})\/$/)?.[1]
    expect(accession, 'the landing names its 10-K by accession').toBeDefined()
    for (const [concept, tag] of Object.entries(SHARED)) {
      const shown = ['FY2025', 'FY2024'].map((period) => points(concept).find((point) => point.period === period))
      expect(shown.map((point) => point?.value), `${concept} FY2025, FY2024`).toEqual([...VERIFIED[tag]])
      for (const point of shown) {
        expect(point?.raw_tag, `${concept} ${point?.period} tag`).toBe(`us-gaap:${tag}`)
        expect(point?.accession?.replace(/-/g, ''), `${concept} ${point?.period} filing`).toBe(accession)
      }
    }
  })

  it("cites its own dataset's figures, and carries the data notes and evidence the live path admits", () => {
    const byMarker = new Map<string, [string, string | undefined, unknown]>()
    for (const series of dataset.series) {
      for (const point of series.points) if (point.marker) byMarker.set(point.marker, [series.concept, point.period, point.value])
      const cagr = series as typeof series & { cagr_marker?: string }
      if (cagr.cagr_marker) byMarker.set(cagr.cagr_marker, [series.concept, series.cagr_window ?? undefined, series.cagr])
    }
    expect(completion.kind).toBe('analysis')
    expect(completion.citations.length).toBe(completion.grounded)
    for (const citation of completion.citations) {
      expect([citation.concept, citation.period, citation.value], `[${citation.n}] ${citation.excerpt}`).toEqual(byMarker.get(citation.marker as string))
    }
    expect(completion.unverified).toBe(0)
    expect(completion.mismatched).toBe(0)
    // streamAnalysis and getAnalysisDataset (features/analysis/api/analysis-api.ts) admit a live payload through these.
    expect(decodeDataNotes(dataset.data_notes, dataset)).toEqual(dataset.data_notes)
    expect(() => decodeNarrativePresentation(completion.narrative_presentation, completion, dataset)).not.toThrow()
  })

  it('names no model anywhere, its comment and its usage record included (the run stays unnamed in the repository)', () => {
    // Production's default model, read from backend/app/config.py so the check follows a model change, beside the
    // families a payload could otherwise name.
    const configured = CONFIG.match(/^\s+AI_DEFAULT_MODEL\s*:\s*str\s*=\s*"([^"]+)"/m)?.[1] ?? ''
    expect(configured, 'backend/app/config.py declares AI_DEFAULT_MODEL').not.toBe('')
    const MODEL = new RegExp(`deepseek|gpt-|claude|gemini|llama|mistral|${configured.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`, 'i')
    expect(Object.keys(demo.completion.usage).filter((key) => /model/i.test(key)), 'model keys in completion.usage').toEqual([])
    const named = leaves(demo, 'demo').flatMap(({ at, value }) => {
      const found = typeof value === 'string' ? value.match(MODEL)?.[0] : undefined
      return found ? [`${at}: ${found}`] : []
    })
    expect(named, 'payload strings that name a model').toEqual([])
  })

  it("lets the landing's three series count their own data notes, never the whole run's", () => {
    const landing = samples.SAMPLE_ANALYSIS_DATASET
    expect(landing.series.map((series) => series.concept)).toEqual(['revenue', 'net_income', 'net_margin'])
    expect(Object.hasOwn(landing, 'data_notes'), 'the landing view carries notes counted over every series of the run').toBe(false)
    expect(resolveDataNotes(landing).totals.total, 'figures the landing counts').toBe(landing.series.length * landing.periods.length)
    // The reading the landing relies on, over the whole run, gives the pipeline's own notes.
    const { data_notes: pipelineNotes, ...withoutNotes } = dataset
    const { notes, totals } = resolveDataNotes(withoutNotes)
    expect({ notes, totals }).toEqual({ notes: pipelineNotes?.notes, totals: pipelineNotes?.totals })
  })
})
