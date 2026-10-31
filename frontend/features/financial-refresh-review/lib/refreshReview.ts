/** Bounded fixture prototype: exact safe-integer values, no currency/scale conversion. */
export type RefreshMode = 'existing-periods' | 'include-new-periods'
export type Decision = 'accept' | 'keep'
export type ChangeKind = 'revised-comparative' | 'source-only' | 'new-period' | 'unchanged' | 'missing' | 'incomparable'

export interface SampleFact {
  readonly company: string
  readonly metric: string
  readonly label: string
  readonly periodStart: string | null
  readonly periodEnd: string
  readonly unit: string
  readonly context: string
  readonly value: number | null
  readonly sourceId: string
  readonly filedOn: string
}

export interface RefreshRow {
  readonly id: string
  readonly baseline: SampleFact
  readonly candidate: SampleFact
}

export interface Comparison {
  kind: ChangeKind
  eligible: boolean
  reason: string
}

export const BASELINE_ID = 'fictional-harbor-2025-02-10'
export const CANDIDATE_ID = 'fictional-harbor-2026-02-12'

export function compareRow(row: RefreshRow, mode: RefreshMode): Comparison {
  const { baseline: old, candidate: next } = row
  const blocked = (reason: string): Comparison => ({ kind: 'incomparable', eligible: false, reason })
  if (old.company !== next.company || old.metric !== next.metric || old.context !== next.context) {
    return blocked('Company, metric or reporting context differs. No automatic match.')
  }
  if (old.unit !== next.unit) return blocked('Units differ. This prototype does not convert currencies or scales.')
  if (!old.sourceId || !next.sourceId) return blocked('A source identifier is missing.')
  if (next.value === null) return { kind: 'missing', eligible: false, reason: 'No candidate value. The baseline stays available.' }
  if (old.value === null || !Number.isSafeInteger(old.value) || !Number.isSafeInteger(next.value)) {
    return blocked('This sample supports exact safe-integer amounts only.')
  }
  if (old.sourceId === next.sourceId) {
    if (old.value === next.value && old.periodStart === next.periodStart && old.periodEnd === next.periodEnd && old.filedOn === next.filedOn) {
      return { kind: 'unchanged', eligible: false, reason: 'Same value, period and source.' }
    }
    return blocked('The same source identifier has conflicting evidence.')
  }
  if (next.filedOn <= old.filedOn) return blocked('The proposed source must have a later filing date.')
  const samePeriod = old.periodStart === next.periodStart && old.periodEnd === next.periodEnd
  if (!samePeriod) {
    // Only an explicitly selected, later, non-overlapping period may be appended.
    const laterPeriod = next.periodEnd > old.periodEnd &&
      ((old.periodStart === null && next.periodStart === null) ||
        (old.periodStart !== null && next.periodStart !== null && next.periodStart > old.periodEnd && next.periodStart <= next.periodEnd))
    if (!laterPeriod) return blocked('Periods overlap or use different duration/instant contexts.')
    if (mode !== 'include-new-periods') return blocked('Select Include new periods to review this addition.')
    return { kind: 'new-period', eligible: true, reason: 'A later period will be added. The earlier period remains unchanged.' }
  }
  return old.value === next.value
    ? { kind: 'source-only', eligible: true, reason: 'Same value in a newer source. This is a provenance update, not a numerical revision.' }
    : { kind: 'revised-comparative', eligible: true, reason: 'A newer source reports a different value for the same period. This alone does not establish a formal restatement.' }
}

/** Keep records are explicit decisions; a missing decision never means acceptance. */
export function reviewRows(rows: readonly RefreshRow[], mode: RefreshMode, decisions: Readonly<Record<string, Decision>>) {
  return rows.map((row) => {
    const comparison = compareRow(row, mode)
    const requested = decisions[row.id]
    // Recompute eligibility: stale or forged accept decisions cannot bypass the current mode.
    const decision = requested === 'keep' ? 'keep' : requested === 'accept' && comparison.eligible ? 'accept' : null
    const values = decision === 'accept'
      ? comparison.kind === 'new-period' ? [row.baseline, row.candidate] : [row.candidate]
      : [row.baseline]
    return { ...row, comparison, decision, values }
  })
}

export function buildReceipt(rows: readonly RefreshRow[], mode: RefreshMode, decisions: Readonly<Record<string, Decision>>) {
  return {
    schemaVersion: 1,
    sampleData: true,
    baselineSnapshot: BASELINE_ID,
    proposedSnapshot: CANDIDATE_ID,
    metricDefinitionVersion: 'fictional-reported-integers-v1',
    mode,
    rows: reviewRows(rows, mode, decisions),
  }
}

/** Quote every cell and make spreadsheet-leading text/control characters inert. */
export function csvCell(value: string | number | null): string {
  const text = value === null ? '' : String(value)
  const inert = typeof value === 'string' && (/^[\s\u0000-\u001f]*[=+\-@]/.test(text) || /^[\u0000-\u001f]/.test(text)) ? `'${text}` : text
  return `"${inert.replace(/"/g, '""')}"`
}

export function currentValuesCsv(rows: readonly RefreshRow[], mode: RefreshMode, decisions: Readonly<Record<string, Decision>>): string {
  const columns = ['sample_data', 'baseline_snapshot', 'proposed_snapshot', 'metric_definition', 'metric', 'label', 'period_start', 'period_end', 'unit', 'context', 'value', 'source_id', 'filed_on', 'decision', 'comparison']
  const records = reviewRows(rows, mode, decisions).flatMap((row) => row.values.map((fact) => [
    'fictional', BASELINE_ID, CANDIDATE_ID, 'fictional-reported-integers-v1', fact.metric, fact.label,
    fact.periodStart, fact.periodEnd, fact.unit, fact.context, fact.value, fact.sourceId, fact.filedOn,
    row.decision ?? (row.comparison.kind === 'unchanged' ? 'unchanged' : 'unresolved'), row.comparison.kind,
  ]))
  return [columns, ...records].map((record) => record.map(csvCell).join(',')).join('\r\n') + '\r\n'
}
