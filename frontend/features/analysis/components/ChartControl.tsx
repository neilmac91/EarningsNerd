import type { Ref } from 'react'
import { Button } from '@/components/ui'

/** Icon-only chart-card header control. `secondary` (hairline border + resting surface), 32px hit
 *  area, 20px glyphs — the TSLA field test proved the ghost 28px/14px version read as unshipped
 *  (owner decision D3: keep icon-only, make the affordance visible at rest), and the AAPL
 *  follow-up sized the glyphs up from 16px, which still read tiny in production. Native `title`
 *  tooltips + aria semantics carry the labels. Shared by both trend-chart renderers. */
export default function ChartControl({
  label,
  expanded,
  disabled,
  onClick,
  buttonRef,
  children,
}: {
  label: string
  /** Disclosure semantics (aria-expanded) — the expand control. */
  expanded?: boolean
  /** In place but inert until its chart can act (the spec renderer's export, until the plot paints). */
  disabled?: boolean
  onClick: () => void
  /** The button, for a card that returns focus to it (the spec renderer's Escape from the expanded view). */
  buttonRef?: Ref<HTMLButtonElement>
  children: React.ReactNode
}) {
  return (
    <Button
      ref={buttonRef}
      variant="secondary"
      size="icon-sm"
      aria-label={label}
      title={label}
      aria-expanded={expanded}
      disabled={disabled}
      onClick={onClick}
      className="shrink-0"
    >
      {children}
    </Button>
  )
}
