'use client'

import { useId, useState, type ReactNode } from 'react'
import { Modal, ModalBody, ModalHeader } from '@/components/ui'
import { formatLocalDate } from '@/lib/format'
import type { AnalysisPoint } from '@/features/analysis/api/analysis-api'
import { FCF_DEFINITION, needsSourceCheck, qualityReasons, sourceUrl, type FactInput, type QualityValue } from '@/features/analysis/lib/provenance'
import { compactFigure, exactFigure, formulaWords, substitutedFormula } from '@/features/analysis/lib/figureDisplay'
import { formatAnalysisPeriod } from '@/features/analysis/lib/periodLabels'
import type { DataNote } from '@/features/analysis/lib/dataNotes'
import DataNoteMark, { dataNoteDescription } from './DataNoteMark'

const sourceLinkClass = 'rounded text-brand-strong underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark'
const legacyLineage = (value: number | null) => value == null
  ? 'Source inputs are not recorded for this calculation. Check the original filing before relying on it.'
  : 'Source lineage is not recorded for this saved calculation. The figure is shown as stored. Check the original filing before relying on it.'

function Checks({ value, note, unavailable = false }: { value: QualityValue; note?: DataNote | null; unavailable?: boolean }) {
  const missing = unavailable || note?.kind === 'unavailable'
  const review = !missing && (note ? note.kind === 'review' : needsSourceCheck(value))
  const passed = !missing && !note && value.provenance?.validation === 'passed'
  const status = missing ? 'Unavailable' : review ? 'Needs review' : passed ? 'Automated checks passed' : 'No validation record'
  const passedExplanation = value.provenance?.method === 'reported'
    ? 'Taken from the company’s XBRL data as filed with the SEC.'
    : value.provenance?.method === 'calculated' ? 'Calculated from reported figures with compatible periods and units.' : null
  return <div className="space-y-1">
    <p className={review ? 'font-medium text-warning-light dark:text-warning-dark' : 'font-medium'}>
      {status}{note && <> · Note {note.letter}</>}
    </p>
    {passed && passedExplanation && <p>{passedExplanation}</p>}
    {!missing && !review && !passed && <p>No automated check result is recorded for this figure. No verification claim is made.</p>}
    {note ? <p>{note.message}</p> : qualityReasons(value).map((reason) => <p key={reason}>{reason}</p>)}
  </div>
}

function SourceInput({ input, nested = false }: { input: FactInput; nested?: boolean }) {
  const provenance = input.provenance
  const href = sourceUrl(input.source_url) ?? sourceUrl(provenance?.source_url)
  const calculated = provenance?.method === 'calculated'
  return (
    <li className="min-w-0 space-y-1 border-t border-border-light pt-2 [overflow-wrap:anywhere] dark:border-white/10">
      <p className="font-medium capitalize">{input.concept.replaceAll('_', ' ')}</p>
      <p className="font-data">{input.value == null ? 'Unavailable' : exactFigure(input.value, input)}</p>
      <p>{[input.period_start, input.period_end].filter(Boolean).join(' to ')}</p>
      <p>{calculated ? (provenance?.inputs.length ? 'Calculated from recorded inputs.' : 'Calculated figure.') : provenance?.method === 'reported' ? 'Reported in the source filing.' : 'Source method is not recorded.'}</p>
      {provenance?.formula && <p>{formulaWords(provenance.formula)}</p>}
      <Checks value={input} unavailable={input.value == null} />
      {href && <a href={href} target="_blank" rel="noopener noreferrer" className={sourceLinkClass} aria-label={`Open original SEC filing for ${input.concept.replaceAll('_', ' ')}, ${[input.period_start, input.period_end].filter(Boolean).join(' to ') || 'period not recorded'}${input.accession ? `, filing ${input.accession}` : ''}`}>Open original SEC filing</a>}
      {input.accession && <p className="font-data">Filing {input.accession}</p>}
      {input.raw_tag && <details><summary tabIndex={0} className={sourceLinkClass}>Technical source details</summary><p className="font-data">{input.raw_tag}</p></details>}
      {calculated && !provenance?.inputs.length && <p>{legacyLineage(input.value)}</p>}
      {!!provenance?.inputs.length && <ul className={nested ? 'space-y-2' : 'space-y-2 pl-3'}>{provenance.inputs.map((operand, index) => <SourceInput key={index} input={operand} nested />)}</ul>}
    </li>
  )
}

/** A value stays readable; its button opens the same source detail on mouse, touch and keyboard. */
export interface SourceComparison extends QualityValue {
  label: string
  display: string
  note?: DataNote | null
}

export default function SourceValue({ point, label, concept, children, note, comparison, compactMarks = false }: {
  point: Pick<AnalysisPoint, 'provenance' | 'reconciled' | 'source_url' | 'derived' | 'period' | 'period_end' | 'accession' | 'raw_tag' | 'unit' | 'value'>
  label: string
  concept?: string
  children: ReactNode
  note?: DataNote | null
  comparison?: SourceComparison
  compactMarks?: boolean
}) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const provenance = point.provenance
  const calculated = provenance?.method === 'calculated' || (!provenance && point.derived)
  const href = sourceUrl(point.source_url) ?? sourceUrl(provenance?.source_url)
  const figure = { concept, unit: point.unit }
  const display = compactFigure(point.value, figure)
  const period = formatAnalysisPeriod(point.period)
  const arithmetic = substitutedFormula(provenance)
  const description = [calculated ? 'calculated' : '', dataNoteDescription(note), comparison?.note ? `comparison carries ${dataNoteDescription(comparison.note)}` : ''].filter(Boolean).join(', ')
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={`${label}, ${period}: ${point.value == null ? 'unavailable' : display}${description ? `, ${description}` : ''}. View source and calculation`}
        className="rounded text-inherit underline decoration-border-light decoration-dotted underline-offset-4 focus-visible:outline-none focus-visible:shadow-ring-brand dark:decoration-border-dark dark:focus-visible:shadow-ring-brand-dark"
      >
        {children}<DataNoteMark calculated={calculated} note={note} compact={compactMarks} />
      </button>
      <Modal open={open} onClose={() => setOpen(false)} labelledBy={id} size="lg">
        <ModalHeader id={id} onClose={() => setOpen(false)}>{label} · {period}</ModalHeader>
        <ModalBody className="space-y-4 text-sm text-text-secondary-light [overflow-wrap:anywhere] dark:text-text-secondary-dark">
          {point.period_end && <p>{/^\d{4}Q[1-4]$/.test(point.period) ? 'Quarter' : /^FY\d{4}$/.test(point.period) ? 'Fiscal year' : 'Period'} ended {formatLocalDate(point.period_end, 'd MMM yyyy')}.</p>}
          <div className="space-y-1">
            <p className="font-data text-2xl text-text-primary-light dark:text-text-primary-dark">{display}<DataNoteMark calculated={calculated} note={note} /></p>
            {point.value != null && <p className="font-data text-xs">As stored: {exactFigure(point.value, figure)}</p>}
          </div>
          <section className="space-y-1">
            <h3 className="font-semibold">Checks</h3>
            <Checks value={point} note={note} unavailable={point.value == null} />
            {point.value == null && <p>Changes that need this {/^\d{4}Q[1-4]$/.test(point.period) ? 'quarter' : 'period'} are not shown.</p>}
          </section>
          <section className="space-y-1">
            <h3 className="font-semibold">Method</h3>
            <p>{provenance?.method === 'reported' ? 'Reported in the source filing.' : calculated ? (provenance?.inputs.length ? 'Calculated by EarningsNerd from recorded inputs.' : 'Calculated figure.') : 'Source method is not recorded for this saved figure.'}</p>
            {provenance?.formula && <p>{formulaWords(provenance.formula)}</p>}
            {arithmetic && point.value != null && <p className="font-data text-xs">{provenance?.validation !== 'passed' && 'Recorded inputs: '}{arithmetic}{provenance?.validation === 'passed' && <> = {exactFigure(point.value, figure)}</>}</p>}
          </section>
          <section className="space-y-2">
            <h3 className="font-semibold">{calculated ? 'Inputs and source filings' : 'Source filing'}</h3>
            {href && <a href={href} target="_blank" rel="noopener noreferrer" className={sourceLinkClass} aria-label={`Open original SEC filing for ${label}, ${period}`}>Open original SEC filing</a>}
            {point.accession && <p className="font-data">Filing {point.accession}</p>}
            {point.raw_tag && <details><summary tabIndex={0} className={sourceLinkClass}>Technical source details</summary><p className="font-data">{point.raw_tag}</p></details>}
            {calculated && !provenance?.inputs.length && <p>{legacyLineage(point.value)}</p>}
            {!!provenance?.inputs.length && <ul className="space-y-3">{provenance.inputs.map((input, index) => <SourceInput key={index} input={input} />)}</ul>}
          </section>
          {comparison && <section className="space-y-2 border-t border-border-light pt-3 dark:border-white/10">
            <h3 className="font-semibold">{comparison.label} comparison</h3>
            <p className="font-data">{comparison.display}</p>
            <Checks value={comparison} note={comparison.note} />
            {comparison.provenance?.formula && <p>Calculation: {formulaWords(comparison.provenance.formula)}</p>}
            {!!comparison.provenance?.inputs.length && <ul className="space-y-3">{comparison.provenance.inputs.map((input, index) => <SourceInput key={index} input={input} />)}</ul>}
          </section>}
          {concept === 'free_cash_flow' && <p>{FCF_DEFINITION}</p>}
          <p className="text-xs">Source links establish where figures came from. Automated checks do not constitute an audit of the company’s accounts.</p>
        </ModalBody>
      </Modal>
    </>
  )
}
