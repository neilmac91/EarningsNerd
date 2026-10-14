'use client'

import { useState } from 'react'
import { Button, Input, Select, secondaryUnavailableClass } from '@/components/ui'
import { downloadBlob } from '@/lib/downloadBlob'
import type { ParagraphComparison } from '../lib/compareParagraphs'
import type { RedlinePair } from '../lib/filingPair'
import { createReviewReceipt, reviewChanges, type ReviewLabels, type ReviewStatus } from '../lib/review'

export default function ComparisonReview({ pair, comparison }: { pair: RedlinePair; comparison: ParagraphComparison }) {
  const [query, setQuery] = useState('')
  const [labels, setLabels] = useState<ReviewLabels>({})
  const changes = reviewChanges(comparison, labels)
  const reviewed = changes.filter((change) => change.reviewStatus === 'reviewed').length
  const followUp = changes.filter((change) => change.reviewStatus === 'needs-follow-up').length

  function exportReceipt() {
    const receipt = createReviewReceipt(pair, comparison, labels, new Date().toISOString())
    downloadBlob(new Blob([JSON.stringify(receipt, null, 2)], { type: 'application/json' }), 'filing-redlines-review.json')
  }

  return (
    <div className="space-y-5 pt-5">
      <p role="status" className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
        <span className="font-data">{comparison.added.length}</span> added · <span className="font-data">{comparison.removed.length}</span> removed · <span className="font-data">{comparison.unchangedCount}</span> matched paragraphs
      </p>
      {changes.length === 0 && <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">No paragraph changes in the supplied text. This does not establish that the full filings are unchanged.</p>}

      <div className="space-y-3">
        <h3 className="text-base font-semibold">Your review</h3>
        <p role="status" className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
          {reviewed} of {changes.length} reviewed · {changes.length - reviewed} remaining · {followUp} needs follow-up
        </p>
        <p className="max-w-3xl text-sm text-text-secondary-light dark:text-text-secondary-dark">
          These labels track your work; they do not verify a source or judge materiality. Needs follow-up stays in the remaining count. Search and labels stay in browser memory only and reset on reload or a new comparison.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <Input label="Find in changed paragraphs" hint="Literal text, case insensitive; no pattern syntax." value={query} onChange={(event) => setQuery(event.target.value)} className="min-w-0 flex-1" />
          <Button variant="secondary" aria-disabled={!query || undefined} className={!query ? secondaryUnavailableClass : undefined} onClick={() => { if (query) setQuery('') }}>Clear search</Button>
          <Button variant="secondary" onClick={exportReceipt}>Download all changes (JSON)</Button>
        </div>
        <p className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">The receipt includes every change and its review label, even when search hides it.</p>
      </div>

      <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
        {(['removed', 'added'] as const).map((kind) => {
          const title = kind === 'removed' ? 'Removed from the later text' : 'Added in the later text'
          const all = changes.filter((change) => change.kind === kind)
          const visible = all.filter((change) => change.text.toLowerCase().includes(query.toLowerCase()))
          return (
            <section key={kind} className="min-w-0" aria-label={title}>
              <div className="mb-4 space-y-1">
                <h3 className="text-base font-semibold">{title}</h3>
                <p className="font-data text-xs text-text-secondary-light dark:text-text-secondary-dark">{visible.length} of {all.length} shown</p>
              </div>
              {visible.length ? (
                <ol className="divide-y divide-border-light border-y border-border-light dark:divide-border-dark dark:border-border-dark" aria-label={`${title} paragraphs`}>
                  {visible.map((change) => (
                    <li key={change.id} className="space-y-3 py-4">
                      <blockquote className="whitespace-pre-wrap font-data text-sm leading-relaxed text-text-primary-light [overflow-wrap:anywhere] dark:text-text-primary-dark">{change.text}</blockquote>
                      <Select label={`${kind === 'removed' ? 'Removed' : 'Added'} paragraph ${change.occurrence} review status`} density="compact" value={change.reviewStatus} onChange={(event) => {
                        const status = event.target.value as ReviewStatus
                        setLabels((current) => ({ ...current, [change.id]: status }))
                      }}>
                        <option value="unreviewed">Unreviewed</option>
                        <option value="reviewed">Reviewed</option>
                        <option value="needs-follow-up">Needs follow-up</option>
                      </Select>
                    </li>
                  ))}
                </ol>
              ) : <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{all.length ? 'No paragraphs match this search. Clear it to see the changes.' : `No ${kind} paragraphs in the supplied text.`}</p>}
            </section>
          )
        })}
      </div>
    </div>
  )
}
