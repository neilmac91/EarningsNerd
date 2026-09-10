'use client'

import { useId, useState } from 'react'
import { Card, CardTitle } from '@/components/ui/Card'
import { CheckCircleIcon } from '@/lib/icons'
import {
  SourceTracePanelBody,
  sourceTraceChipClass,
} from '@/features/filings/components/SourceTrace'

/**
 * Landing-page demo of the product's Trace-to-Source chip with its provenance panel open, so a
 * first-time reader sees the section, the verbatim passage and the EDGAR link without hovering.
 * The chip and the panel body are the REAL SourceTrace recipes (sourceTraceChipClass /
 * SourceTracePanelBody); only the open/closed toggle is local, and the panel renders in flow
 * (no portal, no pointer detection) so the demo is static, SSR-safe and needs no matchMedia.
 */
export interface TraceSample {
  claim: string
  sectionRef: string
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
        Every metric and risk claim carries a chip. Hover or tap it to see the section, the passage,
        and a link into SEC EDGAR.
      </p>
      <div className="mt-4 rounded-lg border border-border-light bg-white px-4 py-3.5 dark:border-white/10 dark:bg-white/5">
        <p className="text-[13px] leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
          {trace.claim}{' '}
          <button
            type="button"
            aria-label="Source: Verified in filing"
            aria-expanded={open}
            aria-controls={panelId}
            onClick={() => setOpen((value) => !value)}
            className={sourceTraceChipClass(true)}
          >
            <CheckCircleIcon className="h-3 w-3 shrink-0" aria-hidden="true" />
            Verified in filing
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
