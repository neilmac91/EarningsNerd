import type { ReactNode } from 'react'
import SectionImpression from '@/features/marketing/components/SectionImpression'

/**
 * One ruled row of the landing page (D-045, composition C): a hairline rule across the container, then a fixed
 * label column on the left (the section's number, its title as the section's h2, and one line) beside the
 * section's content. Every section after the hero is one of these, in the page's order, and none alternates or
 * lays its items out four-up (tests/unit/landing-sections-mounted.spec.ts; the ESLint rule
 * earningsnerd/no-four-up-grid). The label column is the margin of a 10-K, so the page reads as a filing's items.
 *
 * The number is the row's place among the rows that render, counted in CSS: app/page.tsx resets the
 * `landing-row` counter on <main> and each row adds one. A section that omits itself (Reporting this week with no
 * data, the reader quote while it is empty) takes no number, so the row after it follows on with no gap, and a row
 * mounted later takes its place in the count with no renumbering. It is the summary's section index in the data
 * face, and decorative as that index is (aria-hidden): the h2 names the section.
 *
 * The rows share the hero's container (max-w-7xl), so every rule runs the width of the hero's trust strip and the
 * label column starts under the logo. The columns open at 64rem at the reader's text size (1024px at the default
 * size, 2048px under a 200% text setting), not at `lg:`: the label column is 14rem, which doubles with the text,
 * and a title's words cannot shrink below their own width (lessons/frontend-columns-open-at-a-rem-breakpoint.md).
 * Below it the label stacks above the content.
 */
export default function LandingRow({
  id,
  title,
  line,
  impression,
  children,
}: {
  /** The section's anchor; its h2 is `${id}-h`, which names the section. */
  id: string
  title: string
  /** The one line under the title, if the section has one. */
  line?: ReactNode
  /** The `homepage_section_viewed` key this section has always reported (SectionImpression). */
  impression: string
  children: ReactNode
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-h`}
      data-landing-row=""
      className="mx-auto max-w-7xl px-4 [counter-increment:landing-row] sm:px-6 lg:px-8"
    >
      <SectionImpression section={impression}>
        <div className="grid grid-cols-1 gap-x-16 gap-y-8 border-t border-border-light py-12 dark:border-white/10 sm:py-16 [@media(min-width:64rem)]:grid-cols-[14rem_minmax(0,1fr)]">
          <div className="min-w-0">
            <span
              aria-hidden="true"
              data-landing-row-number=""
              className="block font-data text-xs leading-5 tabular-nums text-text-tertiary-light before:content-[counter(landing-row,decimal-leading-zero)] dark:text-text-secondary-dark"
            />
            <h2 id={`${id}-h`} className="mt-1 text-2xl">
              {title}
            </h2>
            {line ? (
              <p className="mt-3 text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">{line}</p>
            ) : null}
          </div>
          <div className="min-w-0">{children}</div>
        </div>
      </SectionImpression>
    </section>
  )
}
