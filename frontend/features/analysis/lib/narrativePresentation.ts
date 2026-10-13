import type { AnalysisCitation, AnalysisCompletion, AnalysisDataset } from '../api/analysis-api'
import { decodeCitationDataNotes } from './dataNotesContract'
import type { DataNotesWire } from './dataNotes'
import { SOURCE_OPERANDS_PREFIX, type NarrativePart } from './narrativeDisplay'

export const NARRATIVE_FORMAT_VERSION = 'analysis-narrative-v1'

export interface NarrativeEvidenceOperand {
  marker: string
  concept: string
  label: string
  value: number
  unit: string | null
  percent: boolean
  period: string
  citation_id: number
  derived: boolean
  display_value: string
}

export interface NarrativeEvidence {
  observation_id: string
  section: string
  tail: { start: number; end: number; text: string }
  operands: NarrativeEvidenceOperand[]
}

export interface NarrativePresentation {
  format_version: typeof NARRATIVE_FORMAT_VERSION
  snapshot_id: string
  data_notes_version: 1
  notes: DataNotesWire
  offset_encoding: 'utf-16'
  evidence: NarrativeEvidence[]
}

const record = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)
const text = (value: unknown): value is string => typeof value === 'string' && value.length > 0
function invalid(): never {
  throw new TypeError('The analysis evidence could not be read consistently. Run analysis again to reload the report.')
}

function decodeOperand(value: unknown, citations: Map<number, AnalysisCitation>): NarrativeEvidenceOperand {
  if (!record(value) || !Number.isSafeInteger(value.citation_id)) return invalid()
  const citation = citations.get(value.citation_id as number)
  if (!citation || !text(value.marker) || !text(value.label) || !text(value.display_value)
    || typeof value.value !== 'number' || !Number.isFinite(value.value)
    || typeof value.percent !== 'boolean' || typeof value.derived !== 'boolean'
    || !(value.unit === null || text(value.unit))
    || value.marker !== citation.marker || value.concept !== citation.concept
    || value.period !== citation.period || value.value !== citation.value
    || value.unit !== (citation.unit ?? null) || value.percent !== citation.percent
    || value.derived !== (citation.derived === true)) return invalid()
  return value as unknown as NarrativeEvidenceOperand
}

/** Validate the additive envelope once at SSE ingress, before the stream becomes terminal.
 * Older completions omit it and keep the strict, fail-open legacy presentation path. */
export function decodeNarrativePresentation(
  value: unknown,
  completion: Pick<AnalysisCompletion, 'snapshot_id' | 'narrative' | 'citations'>,
  dataset?: AnalysisDataset,
): NarrativePresentation {
  if (!record(value) || value.format_version !== NARRATIVE_FORMAT_VERSION
    || value.offset_encoding !== 'utf-16' || value.data_notes_version !== 1
    || !text(value.snapshot_id) || value.snapshot_id !== completion.snapshot_id
    || !dataset || value.snapshot_id !== dataset.snapshot_id || !Array.isArray(value.evidence)) return invalid()
  if (completion.citations.some((citation) => !record(citation)
    || !Number.isSafeInteger(citation.n) || citation.n <= 0)) return invalid()
  const citations = new Map(completion.citations.map((citation) => [citation.n, citation]))
  if (citations.size !== completion.citations.length) return invalid()
  // The data-notes decoder's TypeError names the broken field for diagnostics; the reader gets the one
  // recovery sentence every other decode failure here gives.
  let notes: DataNotesWire
  try {
    notes = decodeCitationDataNotes(value.notes, dataset, completion.citations)
  } catch {
    return invalid()
  }
  let previousEnd = 0
  const observations = new Set<string>()
  const evidence = value.evidence.map((entry): NarrativeEvidence => {
    if (!record(entry) || !text(entry.observation_id) || observations.has(entry.observation_id)
      || entry.section !== 'red_flags' || !record(entry.tail)
      || !Number.isSafeInteger(entry.tail.start) || !Number.isSafeInteger(entry.tail.end)
      || typeof entry.tail.start !== 'number' || typeof entry.tail.end !== 'number'
      || entry.tail.start < previousEnd || entry.tail.end <= entry.tail.start
      || entry.tail.end > completion.narrative.length || !text(entry.tail.text)
      || !entry.tail.text.startsWith(SOURCE_OPERANDS_PREFIX) || !entry.tail.text.endsWith('.')
      || completion.narrative.slice(entry.tail.start, entry.tail.end) !== entry.tail.text
      || !Array.isArray(entry.operands) || entry.operands.length === 0) return invalid()
    previousEnd = entry.tail.end
    observations.add(entry.observation_id)
    const operands = entry.operands.map((operand) => decodeOperand(operand, citations))
    const tailCitations = [...entry.tail.text.matchAll(/\[(\d+)\]/g)].map((match) => Number(match[1]))
    if (tailCitations.length !== operands.length
      || tailCitations.some((number, index) => number !== operands[index].citation_id)) return invalid()
    return {
      observation_id: entry.observation_id, section: entry.section,
      tail: { start: entry.tail.start, end: entry.tail.end, text: entry.tail.text },
      operands,
    }
  })
  return {
    format_version: NARRATIVE_FORMAT_VERSION, snapshot_id: value.snapshot_id,
    data_notes_version: 1, offset_encoding: 'utf-16', notes, evidence,
  }
}

/** Spans were admitted against this exact completed narrative. No grammar guessing occurs. */
export function structuredNarrativeParts(narrative: string, presentation: NarrativePresentation): NarrativePart[] {
  const parts: NarrativePart[] = []
  let start = 0
  for (const entry of presentation.evidence) {
    if (entry.tail.start > start) parts.push({ kind: 'markdown', text: narrative.slice(start, entry.tail.start) })
    parts.push({ kind: 'evidence', operands: entry.operands.map((operand) => ({
      label: operand.label, value: operand.display_value, period: operand.period,
      citation: operand.citation_id, derived: operand.derived, formatted: true,
    })) })
    start = entry.tail.end
  }
  if (start < narrative.length || !parts.length) parts.push({ kind: 'markdown', text: narrative.slice(start) })
  return parts
}
