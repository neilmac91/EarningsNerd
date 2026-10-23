'use client'

import { useId, useState } from 'react'
import { Card, CardTitle } from '@/components/ui/Card'
import { QuotesIcon } from '@/lib/icons'
import { SourceTracePanelBody } from '@/features/filings/components/SourceTrace'
import { PASSAGE_FOUND } from '@/features/filings/lib/evidenceLabels'
import { sourceTraceChipClass } from '@/features/filings/lib/sourceTraceChip'

/**
 * Landing-page demo of the product's Trace-to-Source chip with its provenance panel open, so a
 * first-time reader sees the passage in the filing's own words and the link to it without hovering.
 * The sentence is the live example's own takeaway for Services net sales and the passage the server
 * located for it (SAMPLE_TRACE, from the snapshot), so the label covers what was checked and nothing
 * else: the quoted words, no figure (the founder's review, 2026-10-22). The chip and the panel body are
 * the REAL SourceTrace recipes (sourceTraceChipClass / SourceTracePanelBody); only the open/closed
 * toggle is local, and the panel renders in flow (no portal, no pointer detection) so the demo is
 * static, SSR-safe and needs no matchMedia.
 */
export interface TraceSample {
  metric: string
  claim: string
  sectionRef: string | null
  excerpt: string
  url: string
}

/** `trace` comes from the server section (SAMPLE_TRACE in landing-samples), so this client
 *  boundary never imports the sample module (which also carries the analysis demo dataset). */
export default function TraceToSourceDemo({ trace }: { trace: TraceSample }) {
  const [open, setOpen] = useState(true)
  const panelId = useId()

  return (
    <Card className="p-5">
      <CardTitle>Trace to Source</CardTitle>
      <p className="mt-1.5 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        The label opens the passage a sentence rests on, in the filing’s own words.
      </p>
      {/* The claim box is the first inset to give way (E143): below a 20rem screen, as at 320–390px under 200% text, it
          drops its frame, fill and side padding, so the quote inside the panel keeps the width its words need. */}
      <div className="mt-4 rounded-lg py-3.5 [@media(min-width:20rem)]:border [@media(min-width:20rem)]:border-border-light [@media(min-width:20rem)]:bg-white [@media(min-width:20rem)]:px-4 dark:[@media(min-width:20rem)]:border-white/10 dark:[@media(min-width:20rem)]:bg-white/5">
        <p className="text-xs font-semibold uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-secondary-dark">
          {trace.metric}
        </p>
        <p className="mt-1 text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
          {trace.claim}{' '}
          <button
            type="button"
            aria-label={`Source: ${PASSAGE_FOUND}`}
            aria-expanded={open}
            aria-controls={panelId}
            onClick={() => setOpen((value) => !value)}
            className={sourceTraceChipClass()}
          >
            {/* The product chip's glyph for a filing passage; the selected tint belongs to the
                research pane, which the landing demo does not have. */}
            <QuotesIcon className="h-3 w-3 shrink-0" aria-hidden="true" />
            {PASSAGE_FOUND}
          </button>
        </p>
        {open && (
          <div
            id={panelId}
            role="group"
            aria-label="Source detail"
            className="mt-3 max-w-xs rounded-lg border border-border-light bg-panel-light p-3 shadow-e4 dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
          >
            <SourceTracePanelBody
              header={trace.sectionRef}
              isVerified
              note={null}
              url={trace.url}
              excerpt={
                <blockquote className="mt-1.5 border-l-2 border-brand-border pl-2 font-data text-xs leading-relaxed text-text-secondary-light dark:border-brand-border-dark dark:text-text-secondary-dark">
                  “{trace.excerpt}”
                </blockquote>
              }
            />
          </div>
        )}
      </div>
    </Card>
  )
}
