'use client'

import { useId, useState, type ReactNode } from 'react'
import { Modal, ModalBody, ModalHeader } from '@/components/ui'
import type { AnalysisPoint } from '@/features/analysis/api/analysis-api'
import { FCF_DEFINITION, qualityReasons, sourceUrl, validationLabel, type FactInput } from '@/features/analysis/lib/provenance'
import type { QualityValue } from '@/features/analysis/lib/provenance'
import type { DataNote } from '@/features/analysis/lib/dataNotes'
import DataNoteMark, { dataNoteDescription } from './DataNoteMark'

const sourceLinkClass = 'rounded text-brand-strong underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark'

function SourceInput({ input }: { input: FactInput }) {
  const href = sourceUrl(input.source_url ?? input.provenance?.source_url)
  return (
    <li className="space-y-1 border-t border-border-light pt-2 dark:border-white/10">
      <p className="font-medium">{input.concept.replaceAll('_', ' ')}: {input.value == null ? 'Unavailable' : input.value.toLocaleString(undefined, { maximumFractionDigits: 8 })} {input.unit}</p>
      <p>{[input.period_start, input.period_end].filter(Boolean).join(' to ')}</p>
      {href && <a href={href} target="_blank" rel="noopener noreferrer" className={sourceLinkClass}>Open original SEC filing</a>}
      {input.accession && <p className="font-data break-all">Filing {input.accession}</p>}
      {input.raw_tag && <details><summary className={sourceLinkClass}>Technical source details</summary><p className="break-all">{input.raw_tag}</p></details>}
      {!!input.provenance?.inputs.length && <ul className="space-y-2 pl-3">{input.provenance.inputs.map((operand, index) => <SourceInput key={index} input={operand} />)}</ul>}
    </li>
  )
}

/** A value stays readable; its button opens the same source detail on mouse, touch and keyboard. */
export interface SourceComparison extends QualityValue {
  label: string
  display: string
  note?: DataNote | null
}

export default function SourceValue({ point, label, concept, children, note, comparison }: {
  point: Pick<AnalysisPoint, 'provenance' | 'reconciled' | 'source_url' | 'derived' | 'period' | 'period_end' | 'accession' | 'unit' | 'value'>
  label: string
  concept?: string
  children: ReactNode
  note?: DataNote | null
  comparison?: SourceComparison
}) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const provenance = point.provenance
  const calculated = provenance?.method === 'calculated' || (!provenance && point.derived)
  const href = sourceUrl(point.source_url ?? provenance?.source_url)
  const reasons = qualityReasons(point)
  const description = [calculated ? 'calculated' : '', dataNoteDescription(note), comparison?.note ? `comparison carries ${dataNoteDescription(comparison.note)}` : ''].filter(Boolean).join(', ')
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={`${label}, ${point.period}: ${point.value == null ? 'unavailable' : point.value}${description ? `, ${description}` : ''}. View source and calculation`}
        className="rounded text-inherit underline decoration-border-light decoration-dotted underline-offset-4 focus-visible:outline-none focus-visible:shadow-ring-brand dark:decoration-border-dark dark:focus-visible:shadow-ring-brand-dark"
      >
        {children}<DataNoteMark calculated={calculated} note={note} />
      </button>
      <Modal open={open} onClose={() => setOpen(false)} labelledBy={id} size="lg">
        <ModalHeader id={id} onClose={() => setOpen(false)}>{label} · {point.period}</ModalHeader>
        <ModalBody className="space-y-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          <p className="font-data text-lg text-text-primary-light dark:text-text-primary-dark">{point.value == null ? 'Unavailable' : point.value.toLocaleString(undefined, { maximumFractionDigits: 8 })} {point.unit}</p>
          <p>{provenance?.method === 'reported' ? 'Reported in the source filing.' : calculated ? 'Calculated by EarningsNerd from source figures.' : 'Source method unavailable for this saved figure.'} {validationLabel(point)}.</p>
          {note && <p><span className="font-medium">Data note {note.letter}.</span> {note.message}</p>}
          {!note && reasons.map((reason) => <p key={reason}>{reason}</p>)}
          {point.period_end && <p>Period ended {point.period_end}.</p>}
          {provenance?.formula && <p>Calculation: <span className="font-data break-words">{provenance.formula.replaceAll('_', ' ')}</span></p>}
          {concept === 'free_cash_flow' && <p>{FCF_DEFINITION}</p>}
          {href && <a href={href} target="_blank" rel="noopener noreferrer" className={sourceLinkClass}>Open original SEC filing</a>}
          {!calculated && point.accession && <p className="font-data break-all">Filing {point.accession}</p>}
          {!!provenance?.inputs.length && <><h3 className="font-semibold">Calculation inputs</h3><ul className="space-y-3">{provenance.inputs.map((input, index) => <SourceInput key={index} input={input} />)}</ul></>}
          {comparison && <section className="space-y-2 border-t border-border-light pt-3 dark:border-white/10">
            <h3 className="font-semibold">{comparison.label} comparison</h3>
            <p className="font-data">{comparison.display}</p>
            <p>{validationLabel(comparison)}.</p>
            {comparison.note ? <p>Data note {comparison.note.letter}. {comparison.note.message}</p> : qualityReasons(comparison).map((reason) => <p key={reason}>{reason}</p>)}
            {comparison.provenance?.formula && <p>Calculation: <span className="font-data break-words">{comparison.provenance.formula.replaceAll('_', ' ')}</span></p>}
            {!!comparison.provenance?.inputs.length && <ul className="space-y-3">{comparison.provenance.inputs.map((input, index) => <SourceInput key={index} input={input} />)}</ul>}
          </section>}
          <p className="text-xs">Source links establish where figures came from. Automated checks do not constitute an audit of the company’s accounts.</p>
        </ModalBody>
      </Modal>
    </>
  )
}
