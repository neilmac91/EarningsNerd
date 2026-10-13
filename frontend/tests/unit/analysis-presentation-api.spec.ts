import { afterEach, describe, expect, it, vi } from 'vitest'
import api from '@/lib/api/client'
import {
  getAnalysisDataset, streamAnalysis,
  type AnalysisCitation, type AnalysisCompletion, type AnalysisDataset,
} from '@/features/analysis/api/analysis-api'
import type { DataNotesWire } from '@/features/analysis/lib/dataNotes'
import {
  decodeNarrativePresentation, structuredNarrativeParts,
  type NarrativePresentation,
} from '@/features/analysis/lib/narrativePresentation'

const quality = {
  version: 1 as const, method: 'calculated' as const, validation: 'needs_review' as const,
  reasons: ['legacy_calculation'], formula: null, inputs: [],
}
const notes: DataNotesWire = {
  version: 1,
  notes: [{
    key: '["review",["legacy_calculation"]]', id: 'analysis-data-note-b', letter: 'b',
    kind: 'review', reasons: ['legacy_calculation'], message: 'The saved inputs need review.',
    values: [{ concept: 'net_margin', label: 'Net margin', period: '2026Q2' }],
    comparisons: [], counts: { qoq: 0, yoy: 0, cagr: 0, window_pp: 0 },
  }],
  totals: { reviewValues: 1, reviewComparisons: 0, unavailable: 0, passed: 0, unknown: 0, calculated: 1, total: 1 },
}
const dataset: AnalysisDataset = {
  ticker: 'META', company_name: 'Meta Platforms', mode: 'quarterly', period_key: '2026Q2',
  snapshot_id: 'snapshot-1', data_notes: notes,
  periods: [{ key: '2026Q2', fiscal_year: 2026, fiscal_period: 'Q2', period_end: '2026-06-30' }],
  series: [{ concept: 'net_margin', label: 'Net margin', unit: 'percent', percent: true, cagr: null,
    points: [{ period: '2026Q2', value: 26.1, marker: 'F1', provenance: quality }] }],
  inflections: [],
}
const citation: AnalysisCitation = {
  n: 1, marker: 'F1', concept: 'net_margin', period: '2026Q2', value: 26.1,
  unit: 'percent', percent: true, derived: false, provenance: quality,
  excerpt: 'Net margin = 26.1% (Q2 2026)', verified: true, fragment_url: null, section_ref: null,
}
// The astral character makes Python code-point offsets incorrect for the browser.
const lead = '## Red flags\n\n📉 Margin declined.'
const tail = ' Source operands: Net margin 26.1% in Q2 2026 [1].'
const follow = '\n\nWatch the next filing.'
const completion: AnalysisCompletion = {
  kind: 'analysis', analysis_id: 7, snapshot_id: 'snapshot-1', narrative: lead + tail + follow,
  citations: [citation], grounded: 1, unverified: 0, cached: false, n_periods: 1,
}
const presentation: NarrativePresentation = {
  format_version: 'analysis-narrative-v1', snapshot_id: 'snapshot-1', data_notes_version: 1,
  offset_encoding: 'utf-16', notes,
  evidence: [{ observation_id: 'margin_decline', section: 'red_flags',
    tail: { start: lead.length, end: lead.length + tail.length, text: tail },
    operands: [{ marker: 'F1', concept: 'net_margin', label: 'Net margin', value: 26.1,
      unit: 'percent', percent: true, period: '2026Q2', citation_id: 1, derived: false, display_value: '26.1%' }],
  }],
}
const range = { mode: 'quarterly' as const, start_period: '2026Q2', end_period: '2026Q2' }

function serve(frame: Record<string, unknown>) {
  let sent = false
  const reader = {
    cancel: vi.fn(async () => {}), releaseLock: vi.fn(),
    read: vi.fn(async () => {
      if (sent) return { done: true, value: undefined }
      sent = true
      return { done: false, value: new TextEncoder().encode(`data: ${JSON.stringify(frame)}\n\n`) }
    }),
  }
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, body: { getReader: () => reader } })))
  return reader
}

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('analysis presentation API admission', () => {
  it('keeps authoritative note copy and letters while admitting the dataset', async () => {
    vi.spyOn(api, 'post').mockResolvedValue({ data: dataset })
    const report = await getAnalysisDataset('META', range)
    expect(report.data_notes).toEqual(notes)
    expect(report.series).toBe(dataset.series)
  })

  it.each([null, undefined, { ...notes, version: 2 }, { ...notes, notes: [] }])(
    'rejects present malformed report metadata (%j) instead of choosing a clean fallback', async (data_notes) => {
      vi.spyOn(api, 'post').mockResolvedValue({ data: { ...dataset, data_notes } })
      await expect(getAnalysisDataset('META', range)).rejects.toThrow('Invalid analysis data notes')
    },
  )

  it('accepts an older dataset only when additive metadata is absent', async () => {
    const older = { ...dataset }
    delete older.data_notes
    vi.spyOn(api, 'post').mockResolvedValue({ data: older })
    expect(await getAnalysisDataset('META', range)).toBe(older)
  })

  it('admits a bound completion once, retaining human periods, UTF-16 spans and exact following prose', async () => {
    const reader = serve({ type: 'complete', ...completion, narrative_presentation: presentation })
    const handlers = { onToken: vi.fn(), onComplete: vi.fn(), onError: vi.fn() }
    await streamAnalysis('META', range, handlers, undefined, dataset)
    expect(handlers.onError).not.toHaveBeenCalled()
    expect(handlers.onComplete).toHaveBeenCalledTimes(1)
    const result = handlers.onComplete.mock.calls[0][0] as AnalysisCompletion
    expect(result.narrative_presentation).toEqual(presentation)
    expect(structuredNarrativeParts(result.narrative, result.narrative_presentation!)).toEqual([
      { kind: 'markdown', text: lead },
      { kind: 'evidence', operands: [{ label: 'Net margin', value: '26.1%', period: '2026Q2', citation: 1, derived: false, formatted: true }] },
      { kind: 'markdown', text: follow },
    ])
    expect(reader.cancel).toHaveBeenCalledTimes(1)
  })

  const invalidEnvelopes = [
    ['missing envelope', null],
    ['unknown version', { ...presentation, format_version: 'analysis-narrative-v2' }],
    ['different snapshot', { ...presentation, snapshot_id: 'another' }],
    ['incorrect offset encoding', { ...presentation, offset_encoding: 'code-points' }],
    ['altered source text', { ...presentation, evidence: [{ ...presentation.evidence[0], tail: { ...presentation.evidence[0].tail, text: tail + '.' } }] }],
    ['Python code-point offset', { ...presentation, evidence: [{ ...presentation.evidence[0], tail: { start: lead.length - 1, end: lead.length + tail.length - 1, text: tail } }] }],
    ['wrong citation value', { ...presentation, evidence: [{ ...presentation.evidence[0], operands: [{ ...presentation.evidence[0].operands[0], value: 30 }] }] }],
    ['wrong citation unit', { ...presentation, evidence: [{ ...presentation.evidence[0], operands: [{ ...presentation.evidence[0].operands[0], unit: 'USD' }] }] }],
    ['missing operand', { ...presentation, evidence: [{ ...presentation.evidence[0], operands: [] }] }],
    ['extra operand', { ...presentation, evidence: [{ ...presentation.evidence[0], operands: [...presentation.evidence[0].operands, ...presentation.evidence[0].operands] }] }],
    ['overlapping tail', { ...presentation, evidence: [...presentation.evidence, { ...presentation.evidence[0], observation_id: 'second' }] }],
    ['rewritten report note', { ...presentation, notes: { ...notes, notes: [{ ...notes.notes[0], message: 'No concerns.' }] } }],
  ] as const

  it.each(invalidEnvelopes)('reports %s before making the SSE stream terminal', async (_, envelope) => {
    const reader = serve({ type: 'complete', ...completion, narrative_presentation: envelope })
    const handlers = { onToken: vi.fn(), onComplete: vi.fn(), onError: vi.fn() }
    await streamAnalysis('META', range, handlers, undefined, dataset)
    expect(handlers.onComplete).not.toHaveBeenCalled()
    expect(handlers.onError).toHaveBeenCalledTimes(1)
    // One reader-facing sentence for every decode failure, the data-notes decoder's included.
    expect(handlers.onError.mock.calls[0][0]).toBe('The analysis evidence could not be read consistently. Run analysis again to reload the report.')
    expect(reader.cancel).toHaveBeenCalledTimes(1)
  })

  it('logs a data-notes rejection for diagnostics and gives the reader the one recovery sentence', () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => {})
    const rewritten = { ...presentation, notes: { ...notes, notes: [{ ...notes.notes[0], message: 'No concerns.' }] } }
    expect(() => decodeNarrativePresentation(rewritten, completion, dataset))
      .toThrow(new TypeError('The analysis evidence could not be read consistently. Run analysis again to reload the report.'))
    expect(log).toHaveBeenCalledTimes(1)
    expect(log.mock.calls[0][0]).toBe('[analysis] data notes rejected:')
    expect(log.mock.calls[0][1]).toBeInstanceOf(TypeError)
    expect((log.mock.calls[0][1] as TypeError).message).toMatch(/^Invalid analysis data notes: /)
  })

  it('lets a data-notes failure that is not a rejection propagate unchanged', () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => {})
    const fault = new RangeError('engine fault')
    const exploding = new Proxy({}, { get() { throw fault } })
    expect(() => decodeNarrativePresentation({ ...presentation, notes: exploding }, completion, dataset)).toThrow(fault)
    expect(log).not.toHaveBeenCalled()
  })

  it('requires the currently displayed financial snapshot for new envelopes', () => {
    expect(() => decodeNarrativePresentation(presentation, completion)).toThrow('analysis evidence')
    expect(() => decodeNarrativePresentation(presentation, completion, { ...dataset, snapshot_id: 'other' })).toThrow('analysis evidence')
    expect(() => decodeNarrativePresentation(presentation, { ...completion, citations: [citation, citation] }, dataset)).toThrow('analysis evidence')
  })

  it('retains compatibility with an older completion that has no presentation envelope', async () => {
    serve({ type: 'complete', ...completion })
    const handlers = { onToken: vi.fn(), onComplete: vi.fn(), onError: vi.fn() }
    await streamAnalysis('META', range, handlers)
    expect(handlers.onError).not.toHaveBeenCalled()
    expect(handlers.onComplete).toHaveBeenCalledOnce()
    expect(handlers.onComplete.mock.calls[0][0]).not.toHaveProperty('narrative_presentation')
  })
})
