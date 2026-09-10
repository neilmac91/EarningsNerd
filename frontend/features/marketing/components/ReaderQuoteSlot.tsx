import SectionImpression from '@/features/marketing/components/SectionImpression'
import { QuotesIcon } from '@/lib/icons'

// The design's own placeholder text, verbatim. It reads as a reserved space, not as a quote.
const QUOTE_PLACEHOLDER = "Reserved for a reader's words. Nothing appears here until a real reader supplies them."
const ATTRIBUTION_PLACEHOLDER = 'Name · what they invest in'

/**
 * Reader-quote slot (design tweak `showQuoteSlot`, off by default).
 *
 * Built to the design so the surface exists the day a real reader supplies their words, but the
 * landing page does NOT render it: no placeholder testimonial ever ships (RATIONALE.md, "Gaps
 * noted"). It is a dashed brand-border figure, the Phosphor quotes glyph, the blockquote in the
 * heading face on secondary ink (it sits on the page ground, where tertiary fails AA), and a
 * figcaption for the attribution.
 */
export default function ReaderQuoteSlot() {
  return (
    <section aria-label="Reader quote" className="pb-20 sm:pb-24">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <SectionImpression section="reader_quote">
          <figure className="grid grid-cols-[auto_1fr] items-start gap-5 rounded-xl border border-dashed border-brand-border p-6 dark:border-brand-border-dark sm:p-8 lg:p-10">
            <QuotesIcon className="h-6 w-6 text-brand-strong dark:text-brand-strong-dark" aria-hidden="true" />
            <div className="min-w-0">
              <blockquote className="font-heading text-xl text-text-secondary-light dark:text-text-secondary-dark lg:text-2xl">
                {QUOTE_PLACEHOLDER}
              </blockquote>
              <figcaption className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                {ATTRIBUTION_PLACEHOLDER}
              </figcaption>
            </div>
          </figure>
        </SectionImpression>
      </div>
    </section>
  )
}
