import { ArrowRightIcon, ArrowSquareOutIcon } from '@/lib/icons'
import { cx } from './cx'

/**
 * A control's label with a trailing glyph that keeps with its last word (E272, E274, E275, E276, E279): the glyph and
 * the last letter before it are one no-wrap run, so a label that wraps under 200% text carries the glyph onto its last
 * line instead of parting it from its words, as a flex row with the glyph after the label did. The run holds the last
 * letter, not the whole last word: a word has no break inside it, so where the word fits its line it stays whole with
 * the glyph after it, and where the word alone is wider than its line (a Copilot source's section name in a 110px row at
 * 320px under 200% text) it still breaks inside as its control lets a word break (overflow-wrap), the glyph after its
 * last part, rather than running past the control as a no-wrap word would (E279). The glyph is the arrow, or with
 * `glyph="external"` the external link's square; it is aria-hidden, so the control's name is the label's words alone,
 * and a link that opens a new tab says so itself, with an sr-only cue after this label, so the label stays one string.
 * The run adds no ink or decoration of its own: the words keep their control's one text run, its colour and its
 * underline. The label comes as children, not as a prop of its own, so a count in it stays where brandCopyRules.spec.ts
 * rule 2 reads a component's words (its children), and the count control's ink stays the gate's to hold (D-030).
 * `arrowClassName` sizes and spaces the glyph and may give it a motion of its own (the hero example's nudge under the
 * pointer); it sets no ink, so the glyph takes its control's. DESIGN_SYSTEM.md §4, Trailing arrow.
 */
export function TrailingArrowLabel({
  children: label,
  glyph = 'arrow',
  arrowClassName = 'ml-1 h-4 w-4',
}: {
  children: string
  glyph?: 'arrow' | 'external'
  arrowClassName?: string
}) {
  // The last letter, with any marks that combine with it.
  const tail = /\P{M}\p{M}*$/u.exec(label)?.[0] ?? ''
  return (
    <>
      {label.slice(0, label.length - tail.length)}
      <span className="whitespace-nowrap">
        {tail}
        {glyph === 'external' ? (
          <ArrowSquareOutIcon aria-hidden="true" className={cx('inline-block align-text-bottom', arrowClassName)} />
        ) : (
          <ArrowRightIcon aria-hidden="true" className={cx('inline-block align-text-bottom', arrowClassName)} />
        )}
      </span>
    </>
  )
}
