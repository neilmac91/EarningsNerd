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
    <Card className="p-cap-5">
      <CardTitle>Trace to Source</CardTitle>
      <p className="mt-1.5 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        The label opens the passage a sentence rests on, in the filing’s own words.
      </p>
      {/* The demo's boxes give way from the outside in (E143, chief design's rule on #1462): below
          a 24rem viewport (384px at the default size, 768px under a 200% text setting) the claim box gives up its frame,
          its border, fill and side padding, and sits on the card, which is already the summary's surface; the panel keeps
          its frame and shadow with the capped inset (p-cap-3), the card's inset is capped too (p-cap-5), and the quote
          keeps its rule and its pl-2. At 320px under 200% text that leaves the quote 183px, where "advertising," needs
          171px (gate: tests/e2e/reflow-200.spec.ts, the Trace to Source demo). */}
      <div className="mt-4 rounded-lg border border-border-light bg-white px-4 py-3.5 dark:border-white/10 dark:bg-white/5 [@media(max-width:24rem)]:border-0 [@media(max-width:24rem)]:bg-transparent [@media(max-width:24rem)]:px-0 dark:[@media(max-width:24rem)]:bg-transparent">
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
            className="mt-3 max-w-xs rounded-lg border border-border-light bg-panel-light p-cap-3 shadow-e4 dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
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
