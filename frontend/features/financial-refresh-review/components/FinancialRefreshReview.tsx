'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { downloadBlob } from '@/lib/downloadBlob'
import { FICTIONAL_ROWS } from '../data/fictionalExample'
import { buildReceipt, currentValuesCsv, reviewRows, type Decision, type RefreshMode, type SampleFact } from '../lib/refreshReview'

const SECONDARY = 'text-text-secondary-light dark:text-text-secondary-dark'
const CHANGE_LABELS = {
  'revised-comparative': 'Revised comparative',
  'source-only': 'New source, same value',
  'new-period': 'New period',
  unchanged: 'Unchanged', missing: 'Unavailable', incomparable: 'Needs review',
}

function FactValue({ fact, label }: { fact: SampleFact; label: string }) {
  return (
    <div className="min-w-0">
      <dt className={`text-xs ${SECONDARY}`}>{label} · period ended {fact.periodEnd}</dt>
      <dd className="mt-1 font-data text-lg tabular-nums text-text-primary-light dark:text-text-primary-dark">
        {fact.value === null ? 'Unavailable' : fact.value.toLocaleString('en-US')}
        <span className={`ml-2 text-xs ${SECONDARY}`}>{fact.unit}</span>
      </dd>
    </div>
  )
}

export function FinancialRefreshReview() {
  const [mode, setMode] = useState<RefreshMode>('existing-periods')
  const [decisions, setDecisions] = useState<Record<string, Decision>>({})
  const [message, setMessage] = useState('')
  const reviewed = reviewRows(FICTIONAL_ROWS, mode, decisions)
  const accepted = reviewed.filter((row) => row.decision === 'accept').length
  const kept = reviewed.filter((row) => row.decision === 'keep').length
  const unresolved = reviewed.length - accepted - kept

  function changeMode(next: RefreshMode) {
    setMode(next)
    setDecisions({})
    setMessage('Review scope changed. Previous decisions were cleared.')
  }

  function decide(id: string, decision: Decision) {
    const row = reviewed.find((item) => item.id === id)
    if (!row || (decision === 'accept' && !row.comparison.eligible)) return
    setDecisions((previous) => ({ ...previous, [id]: decision }))
    setMessage(`${row.baseline.label}: ${decision === 'accept' ? 'proposed change accepted' : 'baseline kept'}.`)
  }

  function exportValues() {
    downloadBlob(new Blob([currentValuesCsv(FICTIONAL_ROWS, mode, decisions)], { type: 'text/csv;charset=utf-8' }), 'fictional-financial-values.csv')
    setMessage('Current values exported. Unresolved rows retain their baseline values and are labeled unresolved.')
  }

  function exportReceipt() {
    downloadBlob(new Blob([JSON.stringify(buildReceipt(FICTIONAL_ROWS, mode, decisions), null, 2)], { type: 'application/json' }), 'fictional-refresh-receipt.json')
    setMessage('Decision receipt exported with both sample sources and every review state.')
  }

  return (
    <main className="min-h-screen bg-background-light px-4 py-10 text-text-primary-light dark:bg-background-dark dark:text-text-primary-dark sm:px-6">
      <div className="mx-auto max-w-5xl space-y-8">
        <header className="max-w-3xl space-y-3">
          <p className={`text-sm ${SECONDARY}`}>EarningsNerd lab · fictional example</p>
          <h1 className="text-3xl font-semibold">Financial refresh review</h1>
          <p className={`text-base ${SECONDARY}`}>See what a newer filing would change before updating your numbers. Keep your original snapshot and a record of every decision.</p>
          <p className={`text-sm ${SECONDARY}`}>Harbor Components is fictional. These sample figures and source IDs demonstrate the review workflow. No SEC data is loaded. Decisions last until you reload this page.</p>
        </header>

        <section aria-labelledby="scope-heading" className="space-y-3">
          <h2 id="scope-heading" className="text-xl font-semibold">Choose the review scope</h2>
          <SegmentedControl<RefreshMode>
            label="Review scope" size="md" fullWidth value={mode} onChange={changeMode}
            options={[{ value: 'existing-periods', label: 'Existing periods' }, { value: 'include-new-periods', label: 'Include new periods' }]}
          />
          <p className={`text-sm ${SECONDARY}`}>Changing scope clears your decisions. New periods are added separately; earlier periods are preserved.</p>
        </section>

        <section aria-labelledby="changes-heading" className="space-y-3">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h2 id="changes-heading" className="text-xl font-semibold">Review proposed changes</h2>
            <p className={`text-sm ${SECONDARY}`} aria-live="polite">{accepted} accepted · {kept} kept · {unresolved} unresolved</p>
          </div>
          <Card className="divide-y divide-border-light dark:divide-border-dark">
            {reviewed.map((row) => (
              <article key={row.id} aria-labelledby={`metric-${row.id}`} className="space-y-4 p-4 sm:p-cap-5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 id={`metric-${row.id}`} className="text-base font-semibold">{row.baseline.label}</h3>
                  <p className={`text-sm ${SECONDARY}`}>{CHANGE_LABELS[row.comparison.kind]}</p>
                </div>
                <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <FactValue fact={row.baseline} label="Frozen baseline" />
                  <FactValue fact={row.candidate} label="Proposed source" />
                </dl>
                <p className={`text-sm ${SECONDARY}`}>{row.comparison.reason}</p>
                <details className={`text-sm ${SECONDARY}`}>
                  <summary className="w-fit cursor-pointer rounded focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark">Inspect sample evidence</summary>
                  <dl className="mt-3 grid grid-cols-1 gap-3 break-words sm:grid-cols-2">
                    {[row.baseline, row.candidate].map((fact, index) => (
                      <div key={index}>
                        <dt className="font-medium">{index === 0 ? 'Baseline evidence' : 'Proposed evidence'}</dt>
                        <dd className="mt-1 font-data text-xs">{fact.sourceId} · filed {fact.filedOn}</dd>
                        <dd className="mt-1">{fact.periodStart ? `${fact.periodStart} to ${fact.periodEnd}` : `At ${fact.periodEnd}`} · {fact.context} · {fact.unit}</dd>
                      </div>
                    ))}
                  </dl>
                </details>
                <div className="flex flex-wrap items-center gap-2">
                  {/* Accept and Keep are states the row holds, so aria-pressed is right here; the period presets that
                      decision 8 turned into plain actions (#1275) are the other case. A brand or a11y sweep keeps it. */}
                  {row.comparison.eligible && (
                    <Button size="sm" variant={row.decision === 'accept' ? 'primary' : 'secondary'} aria-pressed={row.decision === 'accept'} onClick={() => decide(row.id, 'accept')}>
                      {row.comparison.kind === 'new-period' ? 'Add period' : row.comparison.kind === 'source-only' ? 'Accept source' : 'Accept value'}
                      {' '}<span className="sr-only">for {row.baseline.label}</span>
                    </Button>
                  )}
                  <Button size="sm" variant={row.decision === 'keep' ? 'primary' : 'secondary'} aria-pressed={row.decision === 'keep'} onClick={() => decide(row.id, 'keep')}>
                    Keep baseline{' '}<span className="sr-only">for {row.baseline.label}</span>
                  </Button>
                  <p className={`text-sm ${SECONDARY}`}>
                    {row.decision === 'accept' ? 'Accepted' : row.decision === 'keep' ? 'Kept by you' : 'Not decided'}
                  </p>
                </div>
                <p className={`break-words text-sm ${SECONDARY}`}>
                  In current export: {row.values.map((fact) => `${fact.periodEnd}: ${fact.value === null ? 'Unavailable' : fact.value.toLocaleString('en-US')} ${fact.unit} (${fact.sourceId})`).join('; ')}
                </p>
              </article>
            ))}
          </Card>
        </section>

        <section aria-labelledby="export-heading" className="space-y-3">
          <h2 id="export-heading" className="text-xl font-semibold">Take the numbers and the receipt</h2>
          <p className={`max-w-3xl text-sm ${SECONDARY}`}>The CSV contains the current values shown above, with periods, units, sources and decisions. Undecided or blocked rows retain the baseline. Keeping a baseline is your choice to retain it, not a successful refresh. The JSON receipt also contains every proposed value and reason.</p>
          <div className="flex flex-wrap gap-3">
            <Button onClick={exportValues}>Export current values CSV</Button>
            <Button variant="secondary" onClick={exportReceipt}>Export decision receipt JSON</Button>
            <Button variant="ghost" onClick={() => { setDecisions({}); setMessage('All decisions cleared. The frozen baseline is unchanged.') }}>Reset decisions</Button>
          </div>
          <p role="status" className={`min-h-6 text-sm ${SECONDARY}`}>{message}</p>
        </section>
      </div>
    </main>
  )
}
