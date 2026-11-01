import { ArrowRightIcon } from '@/lib/icons'

/**
 * A control's label with a trailing arrow that keeps with its last word (E272, E274): the last word and the arrow
 * are one no-wrap run, so a label that wraps under 200% text carries the arrow onto its last line instead of parting
 * it from its words, as a flex row with the arrow after the label did. The arrow is aria-hidden, so the control's
 * name is the label's words alone. The run adds no ink or decoration of its own: the words keep their control's one
 * text run, its colour and its underline.
 */
export default function TrailingArrowLabel({ label }: { label: string }) {
  const last = label.lastIndexOf(' ') + 1
  return (
    <>
      {label.slice(0, last)}
      <span className="whitespace-nowrap">
        {label.slice(last)}
        <ArrowRightIcon aria-hidden="true" className="ml-1 inline-block h-4 w-4 align-text-bottom" />
      </span>
    </>
  )
}
