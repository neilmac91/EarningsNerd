import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Card } from '@/components/ui'

/**
 * Card's hairline is its tone (components/ui/Card.tsx, DESIGN_SYSTEM.md Card / panel, E283). Each tone draws one
 * border colour at rest in each theme, so nothing is left to the stylesheet's order: the settings page's Delete account
 * card asked for a loss hairline on top of Card's own, and in dark Card's own won. `danger` draws the status error,
 * never the loss tone, a direction. `interactive` adds its hover and focus colours under their own variants, so it
 * never adds a second resting one. A caller cannot write a border colour on top: eslint.config.mjs's Card border
 * selector fails it (planted in designRules.spec.ts).
 */
type Tone = 'default' | 'danger'
const TONES: Tone[] = ['default', 'danger']

/** The border-colour classes of a class list at rest, light (no variant) and dark (`dark:` alone). */
function restingBorders(className: string) {
  const colour = (cls: string) => /^border(?:-[trblxyse])?-(?!(?:0|2|4|8|px|solid|dashed|dotted|double|hidden|none)$)(?!(?:collapse|separate|spacing)\b)(?![trblxyse](?:$|-))/.test(cls)
  const tokens = className.split(/\s+/).filter(Boolean)
  return {
    light: tokens.filter((t) => !t.includes(':') && colour(t)),
    dark: tokens.filter((t) => t.startsWith('dark:') && t.split(':').length === 2 && colour(t.slice('dark:'.length))),
  }
}

const classOf = (props: { tone?: Tone; interactive?: boolean }) => {
  const { container } = render(<Card {...props}>x</Card>)
  return (container.firstChild as HTMLElement).className
}

describe("Card's tone owns its hairline (E283)", () => {
  it.each(TONES)('%s draws one border colour at rest in each theme, interactive or not', (tone) => {
    for (const interactive of [false, true]) {
      const { light, dark } = restingBorders(classOf({ tone, interactive }))
      expect([light.length, dark.length], `${tone}${interactive ? ', interactive' : ''}: ${light} | ${dark}`).toEqual([1, 1])
    }
  })

  it('the default tone keeps the hairline pair, and danger draws the status error in both themes', () => {
    expect(restingBorders(classOf({}))).toEqual({ light: ['border-border-light'], dark: ['dark:border-white/10'] })
    expect(restingBorders(classOf({ tone: 'danger' }))).toEqual({ light: ['border-error-light/40'], dark: ['dark:border-error-dark/40'] })
  })

  it('reads a class list as it should: widths, styles and sides are no colour, and two colours count two', () => {
    expect(restingBorders('border border-2 border-t border-b-0 border-dashed border-collapse border-spacing-2 dark:border-0')).toEqual({ light: [], dark: [] })
    expect(restingBorders('border-loss-light/40 border-t-transparent dark:border-white/10 dark:border-loss-dark/30 dark:hover:border-brand-border')).toEqual({
      light: ['border-loss-light/40', 'border-t-transparent'],
      dark: ['dark:border-white/10', 'dark:border-loss-dark/30'],
    })
  })
})
