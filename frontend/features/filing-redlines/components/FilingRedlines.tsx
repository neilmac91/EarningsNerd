'use client'

import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Button, Card, Input, Notice, SegmentedControl } from '@/components/ui'
import { getFiling } from '@/features/filings/api/filings-api'
import { fetchFilingContent } from '@/features/filings/api/filing-content-api'
import { compareParagraphs } from '../lib/compareParagraphs'
import { parseFilingId, validateFilingPair, type RedlinePair, type RedlineSource } from '../lib/filingPair'
import { fictionalPair, fictionalEarlierText, fictionalCurrentText } from '../data/fictionalExample'

type Comparison = ReturnType<typeof compareParagraphs>
type View =
  | { kind: 'idle' | 'loading' }
  | { kind: 'error'; message: string; pair?: RedlinePair }
  | { kind: 'ready'; pair: RedlinePair; comparison: Comparison }

const exampleView = (): View => ({
  kind: 'ready', pair: fictionalPair,
  comparison: compareParagraphs(fictionalEarlierText, fictionalCurrentText),
})
const sourceLinkClass = 'rounded text-sm text-brand-strong underline underline-offset-4 focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark'

function SourceIdentity({ label, source, fictional }: { label: string; source: RedlineSource; fictional: boolean }) {
  return (
    <div className="min-w-0 space-y-2 [overflow-wrap:anywhere]">
      <h3 className="text-sm font-semibold">{label}</h3>
      <p className="text-sm text-text-primary-light dark:text-text-primary-dark">{source.companyName}</p>
      <p className="font-data text-xs text-text-secondary-light dark:text-text-secondary-dark">
        {source.ticker} · 10-K<br />
        Period ended {source.reportDate} · Filed {source.filingDate}
      </p>
      <p className="font-data text-xs text-text-tertiary-light dark:text-text-secondary-dark">{source.accession}</p>
      {source.originalUrl ? (
        <a href={source.originalUrl} target="_blank" rel="noopener noreferrer" className={sourceLinkClass}>
          Open {label.toLowerCase()} original ↗
        </a>
      ) : (
        <p className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">
          {fictional ? 'Illustrative text; no SEC source.' : 'Original document link unavailable.'}
        </p>
      )}
    </div>
  )
}

function ParagraphList({ title, paragraphs, empty }: { title: string; paragraphs: string[]; empty: string }) {
  return (
    <section className="min-w-0" aria-label={title}>
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <h3 className="text-base font-semibold">{title}</h3>
        <span className="font-data text-sm text-text-secondary-light dark:text-text-secondary-dark">{paragraphs.length}</span>
      </div>
      {paragraphs.length ? (
        <ol className="divide-y divide-border-light border-y border-border-light dark:divide-border-dark dark:border-border-dark" aria-label={`${title} paragraphs`}>
          {paragraphs.map((paragraph, index) => (
            <li key={index} className="py-4">
              <blockquote className="whitespace-pre-wrap font-data text-sm leading-relaxed text-text-primary-light [overflow-wrap:anywhere] dark:text-text-primary-dark">
                {paragraph}
              </blockquote>
            </li>
          ))}
        </ol>
      ) : <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{empty}</p>}
    </section>
  )
}

export default function FilingRedlines() {
  const [mode, setMode] = useState<'example' | 'cached'>('example')
  const [earlierId, setEarlierId] = useState('')
  const [currentId, setCurrentId] = useState('')
  const [view, setView] = useState<View>(exampleView)
  const generation = useRef(0)
  const activeRequest = useRef<number | null>(null)

  useEffect(() => () => { generation.current += 1; activeRequest.current = null }, [])

  function invalidate() {
    generation.current += 1
    activeRequest.current = null
  }

  function changeMode(next: 'example' | 'cached') {
    invalidate()
    setMode(next)
    setView(next === 'example' ? exampleView() : { kind: 'idle' })
  }

  function editId(which: 'earlier' | 'current', value: string) {
    invalidate()
    if (which === 'earlier') setEarlierId(value)
    else setCurrentId(value)
    setView({ kind: 'idle' })
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (activeRequest.current !== null) return
    const earlier = parseFilingId(earlierId)
    const current = parseFilingId(currentId)
    if (earlier === null || current === null || earlier === current) {
      setView({ kind: 'error', message: 'Enter two distinct positive filing IDs from your local filing URLs.' })
      return
    }
    const request = ++generation.current
    activeRequest.current = request
    setView({ kind: 'loading' })
    let pair: RedlinePair | undefined
    try {
      const filings = await Promise.all([getFiling(earlier), getFiling(current)])
      if (generation.current !== request) return
      pair = validateFilingPair(filings[0], filings[1], earlier, current)
      const content = await Promise.all([fetchFilingContent(earlier), fetchFilingContent(current)])
      if (generation.current !== request) return
      if (content[0].filingId !== earlier || content[1].filingId !== current) {
        throw new Error('The returned text does not match the selected filings. No comparison was made.')
      }
      if (content.some((item) => !item.hasContent || !item.markdownContent?.trim())) {
        throw new Error('Cached text is unavailable for one or both filings. Open the originals below; no comparison was made.')
      }
      const comparison = compareParagraphs(content[0].markdownContent!, content[1].markdownContent!)
      setView({ kind: 'ready', pair, comparison })
    } catch (error) {
      if (generation.current === request) {
        setView({ kind: 'error', pair, message: error instanceof Error ? error.message : 'The filings could not be read. No comparison was made.' })
      }
    } finally {
      if (activeRequest.current === request) activeRequest.current = null
    }
  }

  const pair = view.kind === 'ready' || view.kind === 'error' ? view.pair : undefined
  return (
    <main className="min-h-screen bg-background-light text-text-primary-light dark:bg-background-dark dark:text-text-primary-dark">
      <div className="mx-auto max-w-6xl space-y-8 px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
        <header className="max-w-3xl space-y-3">
          <p className="text-sm font-medium text-brand-strong dark:text-brand-strong-dark">Research lab · Prototype</p>
          <h1 className="text-3xl font-semibold">Read what changed.</h1>
          <p className="text-base text-text-secondary-light dark:text-text-secondary-dark">
            Compare the words in two annual filings. See paragraphs that appeared or disappeared, with the originals close at hand.
          </p>
        </header>

        <div className="space-y-5">
          <SegmentedControl
            label="Comparison source" size="md" fullWidth value={mode} onChange={changeMode}
            options={[{ value: 'example', label: 'Fictional example' }, { value: 'cached', label: 'Cached filings' }]}
          />
          {mode === 'example' ? (
            <p className="max-w-3xl text-sm text-text-secondary-light dark:text-text-secondary-dark">
              This example uses invented excerpts from a fictional company. It demonstrates the comparison; it is not investment research.
            </p>
          ) : (
            <Card as="section" className="p-5 sm:p-6" aria-labelledby="select-filings-title">
              <h2 id="select-filings-title" className="text-lg font-semibold">Choose two cached annual filings</h2>
              <p className="mt-2 max-w-3xl text-sm text-text-secondary-light dark:text-text-secondary-dark">
                Use two original 10-Ks for the same company. In this local prototype, the filing ID is the number in a filing URL, such as /filing/42.
              </p>
              <form onSubmit={submit} className="mt-5 space-y-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <Input label="Earlier filing ID" inputMode="numeric" value={earlierId} onChange={(event) => editId('earlier', event.target.value)} autoComplete="off" />
                  <Input label="Later filing ID" inputMode="numeric" value={currentId} onChange={(event) => editId('current', event.target.value)} autoComplete="off" />
                </div>
                <Button type="submit" loading={view.kind === 'loading'} loadingText="Reading cached filings…">Compare cached text</Button>
                <p className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">
                  Reads existing cached text only. It does not fetch or generate missing filing text.
                </p>
              </form>
            </Card>
          )}
        </div>

        {view.kind === 'error' && <Notice variant="error" title="Comparison unavailable" description={view.message} />}
        {view.kind === 'loading' && <p role="status" className="text-sm text-text-secondary-light dark:text-text-secondary-dark">Checking the filing pair and reading available text…</p>}

        {pair && (
          <Card as="section" className="p-5 sm:p-6" aria-labelledby="comparison-title">
            <div className="mb-6 space-y-2">
              <h2 id="comparison-title" className="text-xl font-semibold">{pair.fictional ? 'Fictional example comparison' : 'Selected filing comparison'}</h2>
              <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                {pair.fictional ? 'Two short illustrative excerpts.' : 'Available cached text; full-filing coverage has not been verified.'}
              </p>
            </div>
            <div className="grid grid-cols-1 gap-6 border-b border-border-light pb-6 md:grid-cols-2 dark:border-border-dark">
              <SourceIdentity label="Earlier" source={pair.earlier} fictional={pair.fictional} />
              <SourceIdentity label="Later" source={pair.current} fictional={pair.fictional} />
            </div>
            {view.kind === 'ready' && (
              <>
                <p role="status" className="py-5 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  <span className="font-data">{view.comparison.added.length}</span> added · <span className="font-data">{view.comparison.removed.length}</span> removed · <span className="font-data">{view.comparison.unchangedCount}</span> matched paragraphs
                </p>
                {view.comparison.added.length === 0 && view.comparison.removed.length === 0 && (
                  <p className="mb-5 text-sm text-text-secondary-light dark:text-text-secondary-dark">No paragraph changes in the supplied text. This does not establish that the full filings are unchanged.</p>
                )}
                <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
                  <ParagraphList title="Removed from the later text" paragraphs={view.comparison.removed} empty="No removed paragraphs in the supplied text." />
                  <ParagraphList title="Added in the later text" paragraphs={view.comparison.added} empty="No added paragraphs in the supplied text." />
                </div>
              </>
            )}
          </Card>
        )}

        <section className="max-w-3xl space-y-2" aria-labelledby="reading-title">
          <h2 id="reading-title" className="text-base font-semibold">How to read this comparison</h2>
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Whitespace within paragraphs is normalized for matching. Reordered paragraphs are treated as matched; a changed sentence appears as a removed paragraph and an added paragraph. Displayed text is preserved, including markdown syntax.
          </p>
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Each input is limited to 120,000 characters and 400 paragraphs. Formatting differences can create apparent changes. These labels describe text changes, not materiality or investment advice.
          </p>
        </section>
      </div>
    </main>
  )
}
