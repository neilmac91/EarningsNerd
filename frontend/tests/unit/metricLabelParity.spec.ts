import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { FEATURED } from '@/features/fundamentals/lib/featuredMetrics'
import { SAMPLE_CHANGE_REPORT } from '@/features/marketing/lib/landing-samples'

/**
 * A metric that more than one surface names carries one name (E249; CLAUDE.md rule 12). /analysis names each concept
 * in `backend/app/services/trend_analysis/periods.py` (`_CONCEPT_LABELS`), and its name is the one the others take:
 * the filing page's Financial trends picker in `features/fundamentals/lib/featuredMetrics.ts` (`FEATURED`), and What
 * changed's chips, rows and headline, on the filing page, the dashboard and the company page's Compare periods card,
 * in `backend/app/services/dashboard_feed_service.py` (`_DELTA_METRICS`), whose names the landing's What changed sample
 * (`features/marketing/lib/landing-samples.ts`, `SAMPLE_CHANGE_REPORT`) takes in turn. The bank line read
 * "Non-interest income" in the picker and in What changed while /analysis wrote "Noninterest income" (chief design's
 * note on #1817). This spec reads the Python and holds every label the picker, What changed or the sample shares with
 * /analysis to /analysis's.
 *
 * The EPS lines take /analysis's names, "EPS (diluted)" and "EPS (basic)" (chief design's ruling on #1862). What changed
 * lists both and shows one of them per report, the diluted line where both filings carry it, else the basic one
 * (E259), so both entries are read here and neither is an exception.
 */

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const service = (file: string) => readFileSync(path.resolve(frontendDir, '../backend/app/services', file), 'utf8')

/** The `"concept": "Label",` lines of `_CONCEPT_LABELS`, one entry to a line as periods.py writes them. */
function analysisLabels(source: string): Record<string, string> {
  const body = source.match(/^_CONCEPT_LABELS: dict\[str, str\] = \{\n([\s\S]*?)^\}/m)?.[1]
  if (!body) throw new Error('periods.py has no _CONCEPT_LABELS dict')
  return Object.fromEntries([...body.matchAll(/^ {4}"([a-z0-9_]+)": "([^"\n]*)",$/gm)].map((m) => [m[1], m[2]]))
}

/** The `("concept", "Label"),` entries of `_DELTA_METRICS`, in its headline order. */
function whatChangedLabels(source: string): [string, string][] {
  const body = source.match(/^_DELTA_METRICS = \[\n([\s\S]*?)^\]/m)?.[1]
  if (!body) throw new Error('dashboard_feed_service.py has no _DELTA_METRICS list')
  return [...body.matchAll(/^ {4}\("([a-z0-9_]+)", "([^"\n]*)"\),$/gm)].map((m) => [m[1], m[2]])
}

/** Every entry whose label is not /analysis's, as `concept: "label" (analysis: "name")`. */
function mismatches(labels: [string, string][], analysis: Record<string, string>): string[] {
  return labels
    .filter(([concept, label]) => label !== analysis[concept])
    .map(([concept, label]) => `${concept}: "${label}" (analysis: "${analysis[concept]}")`)
}

const analysis = analysisLabels(service('trend_analysis/periods.py'))
const picker: [string, string][] = FEATURED.map((m) => [m.key, m.label])
const whatChanged = whatChangedLabels(service('dashboard_feed_service.py'))
const sample: [string, string][] = (SAMPLE_CHANGE_REPORT.metrics?.items ?? []).map((item) => [item.metric, item.label])

describe('one name per metric across the picker, What changed, its landing sample and /analysis (E249, E259)', () => {
  it('reads every label each table holds', () => {
    // A reader that missed lines would pass the comparisons below vacuously, so each table is read whole: every concept
    // the picker names is one /analysis names, What changed's list is read entry by entry, and the sample shows only
    // lines What changed writes.
    expect(picker.map(([concept]) => concept).filter((concept) => !(concept in analysis))).toEqual([])
    expect(whatChanged.map(([concept]) => concept)).toEqual([
      'revenue', 'net_interest_income', 'noninterest_income', 'net_income', 'eps_diluted', 'earnings_per_share',
    ])
    expect(sample.length).toBeGreaterThan(0)
    expect(sample.map(([concept]) => concept).filter((concept) => !whatChanged.some(([key]) => key === concept))).toEqual([])
  })

  it("names each of the picker's metrics as /analysis does", () => {
    expect(mismatches(picker, analysis)).toEqual([])
  })

  it("names each of What changed's metrics as /analysis does, its headline included", () => {
    expect(mismatches(whatChanged, analysis)).toEqual([])
  })

  it("names each line of the landing's What changed sample as What changed does", () => {
    const names = Object.fromEntries(whatChanged)
    expect(sample.filter(([concept, label]) => label !== names[concept])).toEqual([])
  })

  it("fails a label that leaves /analysis's name, a hyphen or a word order included (planted)", () => {
    const planted: [string, string][] = [
      ['noninterest_income', 'Non-interest income'], ['eps_diluted', 'Diluted EPS'], ['net_income', 'Net income'],
    ]
    expect(mismatches(planted, analysis)).toEqual([
      'noninterest_income: "Non-interest income" (analysis: "Noninterest income")',
      'eps_diluted: "Diluted EPS" (analysis: "EPS (diluted)")',
    ])
    expect(() => analysisLabels('_CONCEPT_LABELS = {}\n')).toThrow('no _CONCEPT_LABELS dict')
    expect(() => whatChangedLabels('DELTA = []\n')).toThrow('no _DELTA_METRICS list')
  })
})
