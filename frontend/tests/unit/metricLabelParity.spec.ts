import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { FEATURED } from '@/features/fundamentals/lib/featuredMetrics'
import { SAMPLE_CHANGE_REPORT } from '@/features/marketing/lib/landing-samples'
import { CONCEPT_NAMES } from '@/features/analysis/lib/figureDisplay'

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
 * lists both and shows one of them per report, the diluted line where both sides of the pair carry it (a 10-K's own
 * restated prior year can complete the pair), else the basic one (E259), so both entries are read here and neither is
 * an exception.
 */

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const service = (file: string) => readFileSync(path.resolve(frontendDir, '../backend/app/services', file), 'utf8')

/** The `"concept": "Label",` lines of `_CONCEPT_LABELS`, one entry to a line as periods.py writes them. Every line of the
 *  dict that is not blank or a comment must be one, so an entry written another way fails here rather than going unread:
 *  the source dialog's names are held equal to this table, every concept and no other (E309). */
function analysisLabels(source: string): Record<string, string> {
  const body = source.match(/^_CONCEPT_LABELS: dict\[str, str\] = \{\n([\s\S]*?)^\}/m)?.[1]
  if (!body) throw new Error('periods.py has no _CONCEPT_LABELS dict')
  const entries = [...body.matchAll(/^ {4}"([a-z0-9_]+)": "([^"\n]*)",$/gm)].map((m) => [m[1], m[2]])
  const lines = body.split('\n').filter((line) => line.trim() && !line.trim().startsWith('#'))
  if (entries.length !== lines.length) {
    throw new Error(`_CONCEPT_LABELS has ${lines.length} entry lines and the reader reads ${entries.length}: write each as    "key": "Label",`)
  }
  return Object.fromEntries(entries)
}

/** The `("concept", "Label"),` entries of `_DELTA_METRICS`, in its headline order. Every line of the list that is not
 *  blank or a comment must be one, so an entry written another way fails here rather than going unread. */
function whatChangedLabels(source: string): [string, string][] {
  const body = source.match(/^_DELTA_METRICS = \[\n([\s\S]*?)^\]/m)?.[1]
  if (!body) throw new Error('dashboard_feed_service.py has no _DELTA_METRICS list')
  const entries: [string, string][] = [...body.matchAll(/^ {4}\("([a-z0-9_]+)", "([^"\n]*)"\),$/gm)].map((m) => [m[1], m[2]])
  const lines = body.split('\n').filter((line) => line.trim() && !line.trim().startsWith('#'))
  if (entries.length !== lines.length) {
    throw new Error(`_DELTA_METRICS has ${lines.length} entry lines and the reader reads ${entries.length}: write each as    ("key", "Label"),`)
  }
  return entries
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

  it("names EPS in the sample's hand-written headline as What changed does", () => {
    const names = new Set(whatChanged.map(([, label]) => label))
    const headline = SAMPLE_CHANGE_REPORT.metrics?.headline ?? ''
    const eps = [...headline.matchAll(/\b(?:(?:basic|diluted)\s+)?EPS\b(?:\s*\((?:basic|diluted)\))?/gi)].map((m) => m[0])
    expect(eps.length).toBeGreaterThan(0)
    expect(eps.filter((name) => !names.has(name))).toEqual([])
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
    expect(() => analysisLabels('_CONCEPT_LABELS: dict[str, str] = {\n    "revenue": "Revenue",\n    "total_debt": "Total debt",  # planted\n}\n'))
      .toThrow('2 entry lines and the reader reads 1')
    expect(() => whatChangedLabels('DELTA = []\n')).toThrow('no _DELTA_METRICS list')
    expect(() => whatChangedLabels('_DELTA_METRICS = [\n    ("revenue", "Revenue"),\n    ("net_income", "Net income"),  # planted\n]\n'))
      .toThrow('2 entry lines and the reader reads 1')
  })
})

/** Each line that spells a concept's name from its key, as `file:line` and its text: a `replace` or `replaceAll` on
 *  `concept`, a member, an optional or asserted one, or a bare name (`input.concept.replaceAll('_', ' ')`,
 *  `concept!.replace(…)`). A name comes from conceptName (features/analysis/lib/figureDisplay.ts), /analysis's own: the
 *  key re-spelled gave the source dialog "Operating Cash Flow" under a Method line reading "Operating cash flow", and
 *  "eps diluted" (E309). conceptName's own fallback, for a concept /analysis does not name, is the one line allowed. */
const KEY_AS_NAME = /\bconcept[?!]?\.replace(?:All)?\(/
const NAME_FALLBACK = [path.join('features', 'analysis', 'lib', 'figureDisplay.ts'), "const words = concept.replaceAll('_', ' ')"]
function keyNames(files: string[], read: (file: string) => string): [string, string][] {
  return files.flatMap((file) => read(file).split('\n').flatMap((line, index): [string, string][] =>
    KEY_AS_NAME.test(line) ? [[`${file}:${index + 1}`, line.trim()]] : []))
}

const SOURCE_ROOTS = ['app', 'components', 'features', 'hooks', 'lib']
const sources = SOURCE_ROOTS.flatMap((root) => readdirSync(path.resolve(frontendDir, root), { recursive: true, encoding: 'utf8' })
  .filter((file) => /\.tsx?$/.test(file))
  .map((file) => path.join(root, file)))

describe('one name per concept in the source dialog and the narrative\'s citations (E309)', () => {
  it("names every concept as /analysis does, each of its concepts and no other", () => {
    expect(CONCEPT_NAMES).toEqual(analysis)
  })

  it("leaves no source spelling a concept's name from its key, conceptName's own fallback aside", () => {
    expect(sources).toContain(path.join('features', 'analysis', 'components', 'SourceValue.tsx'))
    // The fallback is pinned as the one hit, so its allowance cannot outlive it.
    const hits = keyNames(sources, (file) => readFileSync(path.resolve(frontendDir, file), 'utf8'))
    expect(hits.map(([at, text]) => [at.replace(/:\d+$/, ''), text])).toEqual([NAME_FALLBACK])
  })

  it("fails a name spelled from the key: the dialog's, the citation link's, a bare or asserted concept's (planted)", () => {
    const planted: Record<string, string> = {
      'dialog.tsx': "<p className=\"font-medium capitalize\">{input.concept.replaceAll('_', ' ')}</p>",
      'citation.tsx': "aria-label={`Original filing for source ${citation.n}: ${citation.concept?.replaceAll('_', ' ') || 'figure'}`}",
      'bare.tsx': "<ModalHeader id={id}>{label ?? concept?.replaceAll('_', ' ')} · {period}</ModalHeader>",
      'asserted.tsx': "const label = input.concept!.replace(/_/g, ' ')",
      'named.tsx': '<p className="font-medium">{conceptName(input.concept)}</p>',
      'other.tsx': "const id = conceptName(concept).replaceAll(' ', '-')",
    }
    expect(keyNames(Object.keys(planted), (file) => planted[file]).map(([at]) => at))
      .toEqual(['dialog.tsx:1', 'citation.tsx:1', 'bare.tsx:1', 'asserted.tsx:1'])
  })
})
