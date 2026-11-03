import type { AnalysisCitation, AnalysisDataset } from '@/features/analysis/api/analysis-api'

/** A provenance's `inputs` list, admitted where the analysis response enters the page (rule 9; E294).
 *
 *  The backend's builders always write the list, empty for a reported figure (backend/app/services/fact_provenance.py),
 *  and the page reads it without a guard: in each calculated citation's label (NarrativePane) and in every source dialog
 *  (SourceValue, with figureDisplay's arithmetic line). But `provenance_for_fact` serves a stored current-version
 *  provenance as stored, and no backend boundary normalizes its shape, so one stored record without the list would crash
 *  the page where it is read. A missing list therefore reads as the builders' own empty list: the convention
 *  getAnalysisDataset keeps for `data_notes`, where an absent field is admitted and a malformed one refuses. A
 *  provenance that is not a record, a list that is not a list, or an entry in it that is not a record refuses the
 *  response, as the other decoders refuse a field the page would misread. Nested inputs are admitted at every depth.
 *  The page's six provenance slots are a point's `provenance`, `yoy_provenance` and `qoq_provenance`, a series'
 *  `cagr_provenance` and `window_pp_provenance`, and a citation's `provenance`; an absent or null slot stays as sent.
 *
 *  A payload the page renders without passing this boundary, such as the teaser's demo (features/analysis/demo), must
 *  carry every list itself: tests/unit/provenanceInputs.spec.ts checks each committed payload. */
export class ProvenanceInputsRejection extends TypeError {
  constructor(detail: string) {
    super(`Analysis provenance could not be read: ${detail}`)
    this.name = 'ProvenanceInputsRejection'
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

function admit(provenance: unknown, where: string): void {
  if (provenance === undefined || provenance === null) return
  if (!isRecord(provenance)) throw new ProvenanceInputsRejection(`${where} is not a record`)
  if (!Object.hasOwn(provenance, 'inputs')) {
    provenance.inputs = []
    return
  }
  const inputs = provenance.inputs
  if (!Array.isArray(inputs)) throw new ProvenanceInputsRejection(`${where}.inputs is present and not a list`)
  inputs.forEach((input, index) => {
    if (!isRecord(input)) throw new ProvenanceInputsRejection(`${where}.inputs[${index}] is not a record`)
    admit(input.provenance, `${where}.inputs[${index}].provenance`)
  })
}

/** Admits every provenance's `inputs` in the dataset, in place, and returns the dataset. */
export function admitDatasetInputs<T extends Pick<AnalysisDataset, 'series'>>(dataset: T): T {
  if (!Array.isArray(dataset?.series)) return dataset
  dataset.series.forEach((series, seriesIndex) => {
    if (!isRecord(series)) return
    const where = `series[${seriesIndex}]`
    if (Array.isArray(series.points)) {
      series.points.forEach((point, index) => {
        if (!isRecord(point)) return
        const at = `${where}.points[${index}]`
        admit(point.provenance, `${at}.provenance`)
        admit(point.yoy_provenance, `${at}.yoy_provenance`)
        admit(point.qoq_provenance, `${at}.qoq_provenance`)
      })
    }
    admit(series.cagr_provenance, `${where}.cagr_provenance`)
    admit(series.window_pp_provenance, `${where}.window_pp_provenance`)
  })
  return dataset
}

/** Admits every citation's `inputs`, in place, and returns the citations. */
export function admitCitationInputs(citations: AnalysisCitation[]): AnalysisCitation[] {
  citations.forEach((citation, index) => {
    if (isRecord(citation)) admit(citation.provenance, `citations[${index}].provenance`)
  })
  return citations
}
