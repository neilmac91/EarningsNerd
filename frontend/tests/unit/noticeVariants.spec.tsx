import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { Notice, noticeTint, type NoticeVariant } from '@/components/ui'
import { CheckCircleIcon, InfoIcon, WarningCircleIcon, WarningIcon } from '@/lib/icons'

/**
 * Notice's five variants (DESIGN_SYSTEM.md §4 › Inline notice; E196 (2)). The four states each take their own tint,
 * the hairline and ground in the state's colour, with the glyph in its ink. Guidance is no state, so `neutral` takes
 * no state's tint: the hairline alone, no ground, and its glyph in the brand's ink. An error interrupts the reader
 * (role="alert"); the others are a status. The glyph tells a warning (the triangle) from an error (the circle) where
 * amber and red do not.
 */
const STATES = ['error', 'warning', 'info', 'success'] as const
const GLYPH: Record<NoticeVariant, typeof InfoIcon> = {
  error: WarningCircleIcon,
  warning: WarningIcon,
  info: InfoIcon,
  success: CheckCircleIcon,
  neutral: InfoIcon,
}

/** The Notice's root, its glyph's box and its glyph's drawing. */
function notice(variant: NoticeVariant) {
  const { container } = render(<Notice variant={variant} title="Title" description="Line" />)
  const root = container.firstElementChild as HTMLElement
  const glyphBox = root.querySelector('span[aria-hidden="true"]') as HTMLElement
  return { root, glyphBox, drawing: glyphBox.querySelector('svg')?.innerHTML }
}

const drawingOf = (Glyph: typeof InfoIcon) => render(<Glyph />).container.querySelector('svg')?.innerHTML

describe('Notice variants', () => {
  it.each(STATES)('%s: a state, in its own tint and ink', (state) => {
    const { root, glyphBox, drawing } = notice(state)
    expect(root).toHaveAttribute('role', state === 'error' ? 'alert' : 'status')
    expect(root.classList).toContain(`border-${state}-light/25`)
    expect(root.classList).toContain(`bg-${state}-light/[0.06]`)
    expect(root.classList).toContain(`dark:bg-${state}-dark/10`)
    expect(glyphBox.classList).toContain(`text-${state}-light`)
    expect(drawing).toBe(drawingOf(GLYPH[state]))
  })

  it('neutral: guidance, the hairline alone with no ground, and its glyph in the brand ink', () => {
    const { root, glyphBox, drawing } = notice('neutral')
    expect(root).toHaveAttribute('role', 'status')
    expect(root.classList).toContain('border-border-light')
    expect(root.classList).toContain('dark:border-white/10')
    expect([...root.classList].filter((name) => /(^|:)bg-/.test(name))).toEqual([])
    expect([...root.classList].filter((name) => /(error|warning|info|success)-/.test(name))).toEqual([])
    expect(glyphBox.classList).toContain('text-brand-strong')
    expect(glyphBox.classList).toContain('dark:text-brand-strong-dark')
    expect(drawing).toBe(drawingOf(InfoIcon))
  })

  it('a warning and an error draw different glyphs, so the two never rest on colour alone', () => {
    expect(notice('warning').drawing).not.toBe(notice('error').drawing)
  })

  it("lends each variant's tint, the one its own frame paints", () => {
    for (const variant of [...STATES, 'neutral'] as const) {
      const { root } = notice(variant)
      for (const name of noticeTint(variant).split(/\s+/)) expect(root.classList, `${variant}: ${name}`).toContain(name)
    }
  })
})
