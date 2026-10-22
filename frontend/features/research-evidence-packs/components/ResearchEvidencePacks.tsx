'use client'

import { useEffect, useRef, useState, type FormEvent, type MouseEvent } from 'react'
import { Badge, Button, Card, Input, Select, SegmentedControl, Textarea, type BadgeStatusVariant } from '@/components/ui'
import { getFiling } from '@/features/filings/api/filings-api'
import { fetchFilingContent } from '@/features/filings/api/filing-content-api'
import { downloadBlob } from '@/lib/downloadBlob'
import { earlierExample, exampleLedger, laterExample } from '../data/fictionalExample'
import { captureSource, createEntry, exportEvidence, parseFilingId, proposeSource, recordReview, sourceDocument, sourceIdentity, updateInterpretation, type EvidenceEntry, type SourceDocument, type SourceSnapshot } from '../lib/evidenceLedger'

const secondary = 'text-text-secondary-light dark:text-text-secondary-dark'
const sourceLink = 'rounded text-brand-strong underline underline-offset-4 focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark'
/** An entry's review status is a status under D-032, so its chip is a member of Badge's status set, by the set's meanings
    (chief design on #1459, E140): not started, needs the reader, done. tests/unit/statusChipContrast.spec.ts measures
    each on the evidence card. */
export const reviewStatusChip: Record<EvidenceEntry['status'], { label: string; variant: BadgeStatusVariant }> = {
  unreviewed: { label: 'Unreviewed', variant: 'neutral-status' },
  'review-needed': { label: 'Review needed', variant: 'warning-status' },
  reviewed: { label: 'User reviewed', variant: 'success' },
}

export function ReviewStatusChip({ status }: { status: EvidenceEntry['status'] }) {
  const { label, variant } = reviewStatusChip[status]
  return <Badge variant={variant}>{label}</Badge>
}

function SourceQuote({ source }: { source: SourceSnapshot }) {
  return <div className="min-w-0 space-y-3">
    <p className="break-words text-sm font-semibold">{source.companyName} · <span className="font-data">{source.form}</span></p>
    <p className={`break-words font-data text-xs ${secondary}`}>Period {source.reportDate} · Filed {source.filedDate}<br />{source.accession} · Cached paragraph {source.paragraph}</p>
    <blockquote className="whitespace-pre-wrap break-words font-data text-sm leading-relaxed">{source.quote}</blockquote>
    {source.fictional ? <p className={`text-xs ${secondary}`}>Fictional example: invented source, no SEC original.</p> :
      <a href={source.originalUrl!} target="_blank" rel="noopener noreferrer" className={sourceLink}>Open SEC original ↗</a>}
  </div>
}

function EvidenceCard({ entry, capture, onChange }: { entry: EvidenceEntry; capture: () => SourceSnapshot | null; onChange: (entry: EvidenceEntry) => void }) {
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const heading = useRef<HTMLHeadingElement>(null)
  const current = entry.revisions[entry.revisions.length - 1]
  const review = (decision: 'reviewed' | 'accepted' | 'kept', event: MouseEvent<HTMLButtonElement>) => {
    try {
      const next = recordReview(entry, decision, note, new Date().toISOString())
      if (decision !== 'reviewed' && document.activeElement === event.currentTarget) heading.current?.focus()
      onChange(next)
      setNote('')
      setError('')
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Review unavailable.') }
  }
  return <Card as="article" className="min-w-0 space-y-5 p-5" aria-label={`Evidence ${entry.id}`}>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h3 ref={heading} tabIndex={-1} className="text-lg font-semibold focus:outline-none">Evidence {entry.id}</h3>
      <ReviewStatusChip status={entry.status} />
    </div>
    <div className="space-y-3">
      <h4 className="text-sm font-semibold">Current source · revision {entry.revisions.length}</h4>
      <SourceQuote source={current} />
    </div>
    <Textarea label={`My interpretation for evidence ${entry.id}`} value={entry.interpretation} maxLength={10_000} rows={3}
      hint="Your words, separate from the source. Editing them reopens review."
      onChange={(event) => onChange(updateInterpretation(entry, event.target.value))} />
    <Button variant="secondary" onClick={() => {
      try {
        const candidate = capture()
        if (!candidate) throw new Error('Load a later filing and select a paragraph first.')
        onChange(proposeSource(entry, candidate)); setNote(''); setError('')
      } catch (reason) { setError(reason instanceof Error ? reason.message : 'Source proposal unavailable.') }
    }}>Compare selected source</Button>
    {entry.proposal && <section className="space-y-3 border-t border-border-light pt-4 dark:border-border-dark" aria-label={`Source proposal for evidence ${entry.id}`}>
      <h4 className="text-sm font-semibold">Proposed source · review needed</h4>
      <p className={`text-sm ${secondary}`}>{entry.proposal.quote === current.quote
        ? 'The same excerpt appears in this later cached text. That does not verify your interpretation.'
        : 'The selected excerpt differs. Decide whether your interpretation still holds before reusing it.'}</p>
      <SourceQuote source={entry.proposal} />
    </section>}
    <Textarea label={`Review note for evidence ${entry.id}`} value={note} maxLength={10_000} rows={2}
      hint="Record what you checked and why you kept or changed the source."
      onChange={(event) => setNote(event.target.value)} />
    <div className="flex flex-wrap gap-3">
      {entry.proposal ? <>
        <Button onClick={(event) => review('accepted', event)}>Accept new revision</Button>
        <Button variant="secondary" onClick={(event) => review('kept', event)}>Keep prior source</Button>
      </> : <Button onClick={(event) => review('reviewed', event)}>Record review</Button>}
    </div>
    {error && <p role="alert" className="text-sm text-error-light dark:text-error-dark">{error}</p>}
    {(entry.revisions.length > 1 || entry.reviews.length > 0) && <div className="space-y-4 border-t border-border-light pt-4 dark:border-border-dark">
      <h4 className="text-sm font-semibold">Decision history</h4>
      {entry.revisions.slice(0, -1).map((source, index) => <div key={index} className="space-y-2">
        <p className={`text-xs ${secondary}`}>Preserved source revision {index + 1}</p><SourceQuote source={source} />
      </div>)}
      {entry.reviews.map((item, index) => <div key={index} className={`space-y-1 text-sm ${secondary}`}>
        <p className="font-semibold">{item.decision === 'accepted' ? 'Accepted new source' : item.decision === 'kept' ? 'Kept prior source' : 'Recorded review'} · {item.reviewedAt.slice(0, 10)}</p>
        <p className="whitespace-pre-wrap break-words">{item.note}</p>
        <p className="whitespace-pre-wrap break-words">Interpretation then: {item.interpretation || '(None recorded)'}</p>
        {item.candidate && <p className="break-words font-data text-xs">Candidate considered: {item.candidate.accession}</p>}
      </div>)}
    </div>}
  </Card>
}

export default function ResearchEvidencePacks() {
  const [mode, setMode] = useState<'example' | 'cached'>('example')
  const [loaded, setLoaded] = useState<SourceDocument | null>(laterExample)
  const [paragraph, setParagraph] = useState(0)
  const [filingId, setFilingId] = useState('')
  const [entries, setEntries] = useState<EvidenceEntry[]>(exampleLedger)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const generation = useRef(0)
  const inFlight = useRef(false)
  useEffect(() => () => { generation.current += 1 }, [])

  const invalidate = () => { generation.current += 1; inFlight.current = false; setLoading(false); setError(''); setLoaded(null); setParagraph(0) }
  const load = async (event: FormEvent) => {
    event.preventDefault()
    if (inFlight.current) return
    const id = parseFilingId(filingId)
    if (id === null) { setError('Enter a positive filing ID from a local /filing/{id} URL.'); return }
    const epoch = ++generation.current
    inFlight.current = true; setLoading(true); setError(''); setLoaded(null); setParagraph(0)
    try {
      const filing = await getFiling(id)
      if (epoch !== generation.current) return
      const identity = sourceIdentity(filing, id)
      const content = await fetchFilingContent(id)
      if (epoch !== generation.current) return
      setLoaded(sourceDocument(identity, content))
    } catch (reason) {
      if (epoch === generation.current) setError(reason instanceof Error ? reason.message : 'Could not load cached text.')
    } finally {
      if (epoch === generation.current) { inFlight.current = false; setLoading(false) }
    }
  }
  // `selected` previews the paragraph; a snapshot that enters the ledger is stamped when the reader acts on it
  // (Save, Compare), not when the page last rendered, so a paragraph left open carries no stale capturedAt into
  // revisions and exports.
  const selected = loaded ? captureSource(loaded, paragraph, new Date().toISOString()) : null
  const capture = () => (loaded ? captureSource(loaded, paragraph, new Date().toISOString()) : null)
  const changeEntry = (entry: EvidenceEntry) => setEntries((previous) => previous.map((item) => item.id === entry.id ? entry : item))
  const exportPack = (format: 'json' | 'markdown') => {
    downloadBlob(new Blob([exportEvidence(entries, format, new Date().toISOString())], { type: format === 'json' ? 'application/json' : 'text/markdown;charset=utf-8' }), `research-evidence-pack.${format === 'json' ? 'json' : 'md'}`)
    setNotice(`Exported ${entries.length} evidence ${entries.length === 1 ? 'entry' : 'entries'} with source revisions and decision history.`)
  }

  return <main className="mx-auto max-w-6xl space-y-8 px-4 py-10 sm:px-6">
    <header className="max-w-3xl space-y-4">
      <Badge>Local prototype</Badge>
      <h1 className="text-3xl font-semibold sm:text-4xl">Evidence worth revisiting</h1>
      <p className={`text-lg ${secondary}`}>Keep the filing’s words beside your interpretation. When a later filing arrives, review the source before carrying your research forward.</p>
      <p className={`text-sm ${secondary}`}>This tab is your workspace. Refreshing or switching modes resets it; export first. User review records your decision, not verified truth or investment advice.</p>
    </header>
    <div className="flex flex-wrap items-center justify-between gap-4">
      <SegmentedControl label="Evidence workspace" size="md" fullWidth value={mode}
        options={[{ value: 'example', label: 'Fictional example' }, { value: 'cached', label: 'Cached filings' }]}
        onChange={(value) => { invalidate(); setMode(value); setEntries(value === 'example' ? exampleLedger() : []); setLoaded(value === 'example' ? laterExample : null); setNotice('Workspace reset. Previous entries are not stored.'); }} />
      <div className="flex flex-wrap gap-2"><Button variant="secondary" onClick={() => exportPack('markdown')}>Export Markdown</Button><Button variant="secondary" onClick={() => exportPack('json')}>Export JSON</Button></div>
    </div>
    <p role="status" className={`text-sm ${secondary}`}>{notice || (mode === 'example' ? 'Invented excerpts from a fictional company. Try comparing the selected 2026 source with the saved 2025 evidence.' : 'Read only from the existing local filing cache. No SEC fetch, AI generation or server save is added.')}</p>
    <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
      <Card as="section" className="min-w-0 space-y-5 p-5" aria-label="Source selection">
        <h2 className="text-xl font-semibold">1. Select source evidence</h2>
        {mode === 'example' ? <Select label="Example filing" value={loaded?.identity.filingId ?? 2} onChange={(event) => { setLoaded(event.target.value === '1' ? earlierExample : laterExample); setParagraph(0) }}>
          <option value="1">2025 fictional annual filing</option><option value="2">2026 fictional annual filing</option>
        </Select> : <form onSubmit={load} className="space-y-3">
          <Input label="Filing ID" inputMode="numeric" value={filingId} onChange={(event) => { invalidate(); setFilingId(event.target.value) }} hint="Use the number in a local /filing/{id} URL. Original 10-K and 10-Q filings only." />
          <Button type="submit" loading={loading} loadingText="Loading cached text…">Load cached filing</Button>
        </form>}
        {error && <p role="alert" className="text-sm text-error-light dark:text-error-dark">{error}</p>}
        {selected && loaded ? <>
          <Select label="Cached paragraph" value={paragraph} onChange={(event) => setParagraph(Number(event.target.value))}>
            {loaded.paragraphs.map((_text, index) => <option key={index} value={index}>Paragraph {index + 1} of {loaded.paragraphs.length}</option>)}
          </Select>
          <SourceQuote source={selected} />
          <p className={`text-xs ${secondary}`}>Exact excerpt from the cached text. Paragraph numbers refer to this cache; full-filing coverage and SEC page alignment are unverified.</p>
          <Button onClick={() => {
            const snapshot = capture()
            if (!snapshot) return
            setEntries((previous) => [...previous, createEntry((previous.at(-1)?.id ?? 0) + 1, snapshot)]); setNotice('Added an unreviewed source snapshot to the evidence pack.')
          }}>Save as new evidence</Button>
        </> : <p className={`text-sm ${secondary}`}>Load available cached text to choose an exact paragraph. Missing text cannot become evidence.</p>}
      </Card>
      <section className="min-w-0 space-y-4" aria-label="Evidence ledger">
        <h2 className="text-xl font-semibold">2. Review before reuse</h2>
        {entries.length ? entries.map((entry) => <EvidenceCard key={entry.id} entry={entry} capture={capture} onChange={changeEntry} />) :
          <Card className="p-5"><p className={secondary}>Your evidence pack is empty. Select a paragraph, then save your first source snapshot.</p></Card>}
      </section>
    </div>
  </main>
}
