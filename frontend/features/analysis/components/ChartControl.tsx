import { useId, type Ref } from 'react'
import { Button } from '@/components/ui'

/** Icon-only chart-card header control. `secondary` (hairline border + resting surface), 32px hit
 *  area, 20px glyphs — the TSLA field test proved the ghost 28px/14px version read as unshipped
 *  (owner decision D3: keep icon-only, make the affordance visible at rest), and the AAPL
 *  follow-up sized the glyphs up from 16px, which still read tiny in production. Native `title`
 *  tooltips + aria semantics carry the labels. Used by the trend charts' cards. While its work runs the
 *  control is busy (`loading`: Button's spinner in the glyph's place, aria-busy, activation refused), never
 *  natively disabled (DESIGN_SYSTEM.md §4). A `hint` says what the label does not (the PNG export's "Image matches
 *  your theme.", coherence §5): the title reads the label, then the hint, and the button is described by the hint, so
 *  its name stays the label. Without a hint the control renders the button alone, as it always has. */
export default function ChartControl({
  label,
  hint,
  expanded,
  disabled,
  loading,
  onClick,
  buttonRef,
  children,
}: {
  label: string
  /** One sentence the label does not carry: the title's second, and the button's accessible description. */
  hint?: string
  /** Disclosure semantics (aria-expanded) — the expand control. */
  expanded?: boolean
  /** In place but inert until its chart can act (the spec renderer's export, until the plot paints). */
  disabled?: boolean
  /** Busy while its work runs (the spec renderer's export while a PNG is drawn, spec §3.9 `exporting`). */
  loading?: boolean
  onClick: () => void
  /** The button, for a card that returns focus to it (the spec renderer's Escape from the expanded view). */
  buttonRef?: Ref<HTMLButtonElement>
  children: React.ReactNode
}) {
  const hintId = useId()
  const button = (
    <Button
      ref={buttonRef}
      variant="secondary"
      size="icon-sm"
      aria-label={label}
      aria-describedby={hint ? hintId : undefined}
      title={hint ? `${label}. ${hint}` : label}
      aria-expanded={expanded}
      disabled={disabled}
      loading={loading}
      onClick={onClick}
      className="shrink-0"
    >
      {!loading && children}
    </Button>
  )
  if (!hint) return button
  // Beside the button, never in it: the button holds its glyph alone, which the busy state swaps for the spinner. The
  // line is `hidden`, which a description reads all the same: a screen reader says it once, as the button's
  // description, where an sr-only line would read again as text after the button in browse mode. It takes no box, so the
  // controls keep their gap and their places.
  return (
    <>
      {button}
      <span id={hintId} hidden>{hint}</span>
    </>
  )
}
