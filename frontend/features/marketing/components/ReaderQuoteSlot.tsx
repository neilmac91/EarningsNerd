import LandingRow from '@/features/marketing/components/LandingRow'
import { READER_QUOTE } from '@/features/marketing/lib/readerQuote'
import { QuotesIcon } from '@/lib/icons'

/**
 * Reader-quote slot. Renders nothing while `READER_QUOTE` is null (the slot is built, the words are a
 * real reader's to supply), so the page never shows a placeholder testimonial (RATIONALE.md, "Gaps
 * noted"; docs/brand/01-interview.md §2) and takes no number among the landing's rows. Once filled it is
 * a ruled row like every section after the hero (D-045): a dashed brand-border figure, the Phosphor
 * quotes glyph, the blockquote in the heading face on secondary ink (it sits on the page ground, where
 * tertiary fails AA), and a figcaption for the attribution.
 */
export default function ReaderQuoteSlot() {
  if (!READER_QUOTE) return null
  return (
    <LandingRow id="reader-quote" title="Reader quote" impression="reader_quote">
      <figure className="grid grid-cols-[auto_1fr] items-start gap-5 rounded-xl border border-dashed border-brand-border p-6 dark:border-brand-border-dark sm:p-8 lg:p-10">
        <QuotesIcon className="h-6 w-6 text-brand-strong dark:text-brand-strong-dark" aria-hidden="true" />
        <div className="min-w-0">
          <blockquote className="font-heading text-xl text-text-secondary-light dark:text-text-secondary-dark lg:text-2xl">
            {READER_QUOTE.quote}
          </blockquote>
          <figcaption className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            {READER_QUOTE.attribution}
          </figcaption>
        </div>
      </figure>
    </LandingRow>
  )
}
