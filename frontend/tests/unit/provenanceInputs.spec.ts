import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import type { AnalysisCitation, AnalysisCompletion, AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { admitCitationInputs, admitDatasetInputs, ProvenanceInputsRejection } from '@/features/analysis/lib/provenanceInputs'

/**
 * The page reads a provenance's `inputs` list without a guard, so the list is admitted where the analysis response
 * enters (features/analysis/lib/provenanceInputs.ts, E294): a missing list reads as the builders' empty one, a
 * malformed one refuses. analysis-presentation-api.spec.ts pins the two entry points; this file pins the admission and
 * the payloads committed beside the code. Chief design's preview probe on #1972 found the legacy e2e fixture crashing
 * the page when "Free cash flow, Q2 2026" opened: the prototype's pruning had left 88 operand records without the list.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SLOTS = ['provenance', 'yoy_provenance', 'qoq_provenance', 'cagr_provenance', 'window_pp_provenance'] as const

const reported = () => ({ version: 1, method: 'reported', validation: 'passed', reasons: [], formula: null })
const operand = (provenance: unknown) => ({ concept: 'operating_cash_flow', value: 1, period_end: '2026-06-30', provenance })
const datasetOf = (point: Record<string, unknown>, series: Record<string, unknown> = {}) =>
  ({ series: [{ concept: 'free_cash_flow', points: [{ period: '2026Q2', value: 1, ...point }], ...series }] }) as unknown as AnalysisDataset
const citationsOf = (provenance: unknown) => [{ n: 1, concept: 'free_cash_flow', provenance }] as unknown as AnalysisCitation[]
const rejection = (detail: string) => new ProvenanceInputsRejection(detail)

describe('the provenance inputs admission (E294)', () => {
  it("reads a missing list as the builders' empty list in each of the six slots, in place", () => {
    const dataset = datasetOf(
      { provenance: reported(), yoy_provenance: reported(), qoq_provenance: reported() },
      { cagr_provenance: reported(), window_pp_provenance: reported() },
    )
    expect(admitDatasetInputs(dataset)).toBe(dataset)
    const [series] = dataset.series
    for (const slot of ['provenance', 'yoy_provenance', 'qoq_provenance'] as const) expect(series.points[0][slot]).toEqual({ ...reported(), inputs: [] })
    for (const slot of ['cagr_provenance', 'window_pp_provenance'] as const) expect(series[slot]).toEqual({ ...reported(), inputs: [] })
    const citations = citationsOf(reported())
    expect(admitCitationInputs(citations)).toBe(citations)
    expect(citations[0].provenance).toEqual({ ...reported(), inputs: [] })
  })

  it('admits nested inputs at every depth and keeps each present list as sent', () => {
    const third = operand(reported())
    const second = operand({ ...reported(), method: 'calculated', formula: 'YTD6 - Q1', inputs: [third] })
    const first = { ...reported(), method: 'calculated', formula: 'operating_cash_flow - abs(capital_expenditures)', inputs: [second] }
    const firstInputs = first.inputs
    const dataset = datasetOf({ provenance: first })
    admitDatasetInputs(dataset)
    expect(first.inputs).toBe(firstInputs)
    expect(second.provenance.inputs).toEqual([third])
    expect(third.provenance).toEqual({ ...reported(), inputs: [] })
    const deep = operand(reported())
    const citations = citationsOf({ ...reported(), method: 'calculated', inputs: [operand({ ...reported(), inputs: [deep] })] })
    admitCitationInputs(citations)
    expect(deep.provenance).toEqual({ ...reported(), inputs: [] })
  })

  it('leaves an absent or null slot, and an operand without a provenance, as sent', () => {
    const bare = { concept: 'capital_expenditures', value: 2 }
    const dataset = datasetOf({ provenance: { ...reported(), inputs: [bare] }, qoq_provenance: null }, { cagr_provenance: null })
    const before = structuredClone(dataset)
    admitDatasetInputs(dataset)
    expect(dataset).toEqual(before)
    expect(Object.hasOwn(dataset.series[0].points[0], 'yoy_provenance')).toBe(false)
    expect(Object.hasOwn(bare, 'provenance')).toBe(false)
    const citations = citationsOf(null)
    admitCitationInputs(citations)
    expect(citations[0].provenance).toBeNull()
  })

  it.each([
    ['a null list', { ...reported(), inputs: null }, 'series[0].points[0].provenance.inputs is present and not a list'],
    ['an object for a list', { ...reported(), inputs: {} }, 'series[0].points[0].provenance.inputs is present and not a list'],
    ['a string for a list', { ...reported(), inputs: 'operands' }, 'series[0].points[0].provenance.inputs is present and not a list'],
    ['a nested non-list', { ...reported(), inputs: [operand({ ...reported(), inputs: 0 })] }, 'series[0].points[0].provenance.inputs[0].provenance.inputs is present and not a list'],
    ['an entry that is not a record', { ...reported(), inputs: [null] }, 'series[0].points[0].provenance.inputs[0] is not a record'],
    ['a provenance that is not a record', 'reported', 'series[0].points[0].provenance is not a record'],
    ['a nested provenance that is not a record', { ...reported(), inputs: [operand(['reported'])] }, 'series[0].points[0].provenance.inputs[0].provenance is not a record'],
  ])('refuses %s, naming where it sits', (_, provenance, detail) => {
    expect(() => admitDatasetInputs(datasetOf({ provenance }))).toThrow(rejection(detail))
    expect(() => admitCitationInputs(citationsOf(provenance))).toThrow(rejection(detail.replace('series[0].points[0]', 'citations[0]')))
  })

  it('refuses in every dataset slot, naming the slot', () => {
    const broken = { ...reported(), inputs: null }
    for (const slot of ['yoy_provenance', 'qoq_provenance'] as const) {
      expect(() => admitDatasetInputs(datasetOf({ [slot]: broken }))).toThrow(rejection(`series[0].points[0].${slot}.inputs is present and not a list`))
    }
    for (const slot of ['cagr_provenance', 'window_pp_provenance'] as const) {
      expect(() => admitDatasetInputs(datasetOf({}, { [slot]: broken }))).toThrow(rejection(`series[0].${slot}.inputs is present and not a list`))
    }
    const error = (() => { try { admitDatasetInputs(datasetOf({ provenance: broken })) } catch (caught) { return caught } })()
    expect(error).toBeInstanceOf(ProvenanceInputsRejection)
    expect(error).toBeInstanceOf(TypeError)
    expect((error as Error).message).toBe('Analysis provenance could not be read: series[0].points[0].provenance.inputs is present and not a list')
  })
})

/** Whether every provenance slot under `node` holds null or a record whose own `inputs` is a list of records, at any
 *  depth: what the admission accepts without completing anything. Returns the paths that fall short. */
function shortfalls(node: unknown, where: string, found: string[] = []): string[] {
  if (Array.isArray(node)) node.forEach((value, index) => shortfalls(value, `${where}[${index}]`, found))
  else if (node && typeof node === 'object') {
    for (const [key, value] of Object.entries(node)) {
      const at = `${where}.${key}`
      if ((SLOTS as readonly string[]).includes(key) && value !== null && value !== undefined) {
        const inputs = (value as { inputs?: unknown }).inputs
        if (typeof value !== 'object' || Array.isArray(value) || !Array.isArray(inputs)
          || inputs.some((input) => !input || typeof input !== 'object' || Array.isArray(input))) found.push(at)
      }
      shortfalls(value, at, found)
    }
  }
  return found
}

/** Committed JSON beside the frontend's code that is a projection of a dataset rather than a payload, with why it may
 *  leave its operands' lists out. An entry whose file now carries every list, or is gone, fails below. */
const PROJECTIONS: Record<string, string> = {
  'tests/unit/fixtures/chart-datasets.json': "a slimmed projection that dropped its provenance operands (its source note says so) for the chart and data-notes specs; the e2e gallery serves it through analysisLayoutApi.ts's datasetFixture, which adds the structural defaults",
  'tests/unit/fixtures/meta-data-notes.json': "a quality-only projection of a captured dataset, hash-pinned by its readers; analysisLayoutApi.ts's geometryFixture adds the structural defaults before the page reads it",
}

describe('the payloads committed beside the code (E294)', () => {
  const files = [...new Set(execFileSync('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z', '--', '*.json'], {
    cwd: FRONTEND, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024,
  }).split('\0').filter(Boolean))].filter((file) => existsSync(path.join(FRONTEND, file)))
  const scanned = new Map<string, string[]>()
  for (const file of files) {
    const text = readFileSync(path.join(FRONTEND, file), 'utf8')
    if (!text.includes('provenance"')) continue
    scanned.set(file, shortfalls(JSON.parse(text), '$'))
  }

  it("carry each provenance's inputs list, as the builders write it, but for the named projections", () => {
    // The walk reaches the payloads that matter: the teaser's and the landing's demo, which the page renders without
    // the API boundary, and the e2e page fixtures.
    expect([...scanned.keys()]).toEqual(expect.arrayContaining([
      'features/analysis/demo/demo-analysis.json', 'tests/e2e/fixtures/analysis-layout.json',
    ]))
    const short = [...scanned].filter(([file, paths]) => paths.length && !Object.hasOwn(PROJECTIONS, file))
      .map(([file, paths]) => `${file}: ${paths.length} provenance records without a list, first ${paths[0]}`)
    expect(short).toEqual([])
  })

  it('keeps each projection exemption only while its file still needs it', () => {
    const stale = Object.keys(PROJECTIONS).filter((file) => !scanned.get(file)?.length)
    expect(stale, 'exemptions whose file is gone or now carries every list').toEqual([])
  })

  it("lets the layout fixture's three states pass the admission unchanged, its variants' replacements included", () => {
    type Replacement = { path: Array<string | number>; value?: unknown; remove?: boolean }
    const archive = JSON.parse(readFileSync(path.join(FRONTEND, 'tests/e2e/fixtures/analysis-layout.json'), 'utf8')) as {
      legacy: { dataset: AnalysisDataset; completion: AnalysisCompletion }
      variants: Record<'clean' | 'discrepancy', Replacement[]>
    }
    for (const state of ['legacy', 'clean', 'discrepancy'] as const) {
      // As analysisLayoutApi.ts's fixtureFor builds the state the page receives.
      const fixture = structuredClone(archive.legacy)
      for (const replacement of state === 'legacy' ? [] : archive.variants[state]) {
        let parent = fixture as unknown as Record<string | number, unknown>
        for (const key of replacement.path.slice(0, -1)) parent = parent[key] as Record<string | number, unknown>
        const key = replacement.path.at(-1)!
        if (replacement.remove) delete parent[key]
        else parent[key] = structuredClone(replacement.value)
      }
      expect(admitDatasetInputs(structuredClone(fixture.dataset)), `${state} dataset`).toEqual(fixture.dataset)
      expect(admitCitationInputs(structuredClone(fixture.completion.citations)), `${state} citations`).toEqual(fixture.completion.citations)
    }
  })
})
