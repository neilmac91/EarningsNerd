import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { FEATURED } from '@/features/fundamentals/lib/featuredMetrics'

/**
 * A metric that more than one surface names carries one name (E249; CLAUDE.md rule 12). /analysis names each concept
 * in `backend/app/services/trend_analysis/periods.py` (`_CONCEPT_LABELS`), and its name is the one the others take:
 * the filing page's Financial trends picker in `features/fundamentals/lib/featuredMetrics.ts` (`FEATURED`), and What
 * changed's chips, rows and headline, on the filing page, the dashboard and the company page's Compare periods card,
 * in `backend/app/services/dashboard_feed_service.py` (`_DELTA_METRICS`). The bank line read "Non-interest income" in
 * the picker and in What changed while /analysis wrote "Noninterest income" (chief design's note on #1817). This spec
 * reads the Python and holds every label the picker or What changed shares with /analysis to /analysis's.
 *
 * The EPS lines are the recorded exception: the picker and What changed write "Diluted EPS" and "EPS" where /analysis
 * writes "EPS (diluted)" and "EPS (basic)". Each is held to its exact pair, so changing either side, or giving the two
 * one name, is a deliberate edit here.
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

type Pair = { surface: string; analysis: string }
/** Each surface's EPS line beside /analysis's name for it. */
const PICKER_EXCEPTIONS: Record<string, Pair> = {
  eps_diluted: { surface: 'Diluted EPS', analysis: 'EPS (diluted)' },
  earnings_per_share: { surface: 'EPS', analysis: 'EPS (basic)' },
}
const WHAT_CHANGED_EXCEPTIONS: Record<string, Pair> = {
  earnings_per_share: { surface: 'EPS', analysis: 'EPS (basic)' },
}

/** Every entry whose label is not /analysis's, as `concept: "label" (analysis: "name")`, exceptions aside. */
function mismatches(
  labels: [string, string][],
  analysis: Record<string, string>,
  exceptions: Record<string, Pair>,
): string[] {
  return labels
    .filter(([concept, label]) => !(concept in exceptions) && label !== analysis[concept])
    .map(([concept, label]) => `${concept}: "${label}" (analysis: "${analysis[concept]}")`)
}

const analysis = analysisLabels(service('trend_analysis/periods.py'))
const picker: [string, string][] = FEATURED.map((m) => [m.key, m.label])
const whatChanged = whatChangedLabels(service('dashboard_feed_service.py'))

describe('one name per metric across the picker, What changed and /analysis (E249)', () => {
  it('reads every label each table holds', () => {
    // A reader that missed lines would pass the comparisons below vacuously, so each table is read whole: every concept
    // the picker names is one /analysis names, and What changed's list is read entry by entry.
    expect(picker.map(([concept]) => concept).filter((concept) => !(concept in analysis))).toEqual([])
    expect(whatChanged.map(([concept]) => concept)).toEqual([
      'revenue', 'net_interest_income', 'noninterest_income', 'net_income', 'earnings_per_share',
    ])
  })

  it("names each of the picker's metrics as /analysis does", () => {
    expect(mismatches(picker, analysis, PICKER_EXCEPTIONS)).toEqual([])
  })

  it("names each of What changed's metrics as /analysis does, its headline included", () => {
    expect(mismatches(whatChanged, analysis, WHAT_CHANGED_EXCEPTIONS)).toEqual([])
  })

  it('holds the EPS lines to their recorded pairs, so a change to either side is made here', () => {
    const recorded = (labels: [string, string][], exceptions: Record<string, Pair>) =>
      Object.entries(exceptions).map(([concept, pair]) => ({
        concept,
        surface: labels.find(([key]) => key === concept)?.[1],
        analysis: analysis[concept],
        pair,
      }))
    for (const { concept, surface, analysis: name, pair } of [
      ...recorded(picker, PICKER_EXCEPTIONS),
      ...recorded(whatChanged, WHAT_CHANGED_EXCEPTIONS),
    ]) {
      expect({ concept, surface, analysis: name }).toEqual({ concept, surface: pair.surface, analysis: pair.analysis })
    }
  })

  it("fails a label that leaves /analysis's name, a hyphen included (planted)", () => {
    const planted: [string, string][] = [['noninterest_income', 'Non-interest income'], ['net_income', 'Net income']]
    expect(mismatches(planted, analysis, {})).toEqual([
      'noninterest_income: "Non-interest income" (analysis: "Noninterest income")',
    ])
    expect(() => analysisLabels('_CONCEPT_LABELS = {}\n')).toThrow('no _CONCEPT_LABELS dict')
    expect(() => whatChangedLabels('DELTA = []\n')).toThrow('no _DELTA_METRICS list')
  })
})
