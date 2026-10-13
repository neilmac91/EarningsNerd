import { createElement, type FunctionComponent } from 'react'
import { createRequire } from 'node:module'
import path from 'node:path'
import { render } from '@testing-library/react'
import type { Config } from 'tailwindcss'
import resolveConfig from 'tailwindcss/resolveConfig'
import { describe, expect, it } from 'vitest'
import InviteStatusBadge from '@/features/admin/components/InviteStatusBadge'
import FeedbackStatusBadge from '@/features/admin/components/FeedbackStatusBadge'
import type { FeedbackStatus, InviteStatus } from '@/features/admin/api/admin-api'

/**
 * The admin status chips' labels clear 4.5:1 on what is behind them, in both themes (audit ADM-16a,
 * ADM-16b; CLAUDE.md rule 11). Measured from the rendered chip's own classes, resolved through
 * tailwind.config.js, so a token or recipe change is read as it ships: the label ink over the chip's
 * ground, composited over the table row the chip sits in, at rest and under the row's hover tint. A
 * class this spec cannot resolve fails rather than passes.
 */
const require = createRequire(import.meta.url)
const flattenColorPalette = (require('tailwindcss/lib/util/flattenColorPalette') as { default: (c: unknown) => Record<string, string> }).default
const ROOT = path.resolve(__dirname, '../..')
const COLORS = flattenColorPalette(resolveConfig(require(path.join(ROOT, 'tailwind.config.js')) as Config).theme.colors)

type Rgba = [number, number, number, number]

function rgba(color: string): Rgba {
  if (color.startsWith('#')) {
    const hex = color.slice(1)
    const [r, g, b] = (hex.length === 3 ? hex.split('').map((c) => c + c) : hex.match(/../g)!).map((v) => parseInt(v, 16))
    return [r, g, b, 1]
  }
  const [r, g, b, a = 1] = color.match(/[\d.]+/g)!.map(Number)
  return [r, g, b, a]
}

/** A colour utility's value (`info-text`, `white`, `info-light/10`, `black/[0.04]`), or null for a non-colour one. */
function colour(value: string): Rgba | null {
  const m = value.match(/^(.+?)(?:\/(?:\[([\d.]+)\]|(\d+)))?$/)!
  const base = COLORS[m[1]]
  if (base === undefined) return null
  if (base === 'transparent') return [0, 0, 0, 0]
  const [r, g, b, a] = rgba(base)
  const alpha = m[2] !== undefined ? Number(m[2]) : m[3] !== undefined ? Number(m[3]) / 100 : 1
  return [r, g, b, a * alpha]
}

const over = (top: Rgba, ground: Rgba): Rgba => {
  const a = top[3]
  return [0, 1, 2].map((i) => top[i] * a + ground[i] * (1 - a)).concat(1) as Rgba
}
const luminance = (c: Rgba) =>
  c.slice(0, 3).map((v) => {
    const s = v / 255
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }).reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0)
const ratio = (a: Rgba, b: Rgba) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/** The rows a chip sits on (InviteRow, FeedbackRow: the tbody's panel, and the row's hover tint over it). */
const ROWS: Record<'light' | 'dark', Array<[string, Rgba]>> = {
  light: [
    ['row', colour('panel-light')!],
    ['hovered row', colour('background-light')!],
  ],
  dark: [
    ['row', colour('panel-dark')!],
    ['hovered row', over(colour('white/5')!, colour('panel-dark')!)],
  ],
}

/** The chip's text and background colours in one theme, from its rendered class list. */
function chipColours(className: string, theme: 'light' | 'dark') {
  const found: { text?: Rgba; bg?: Rgba } = {}
  for (const cls of className.split(/\s+/)) {
    const parts = cls.split(':')
    const utility = parts.pop()!
    const variants = parts.join(':')
    if (variants !== (theme === 'dark' ? 'dark' : '')) continue
    const m = utility.match(/^(text|bg)-(.+)$/)
    if (!m) continue
    const value = colour(m[2])
    if (!value) continue
    found[m[1] as 'text' | 'bg'] = value
  }
  return found
}

const CHIPS: Array<[string, FunctionComponent<{ status: never }>, string[]]> = [
  ['InviteStatusBadge', InviteStatusBadge as FunctionComponent<{ status: never }>, ['pending', 'used', 'expired', 'revoked'] satisfies InviteStatus[]],
  ['FeedbackStatusBadge', FeedbackStatusBadge as FunctionComponent<{ status: never }>, ['new', 'triaged', 'resolved'] satisfies FeedbackStatus[]],
]

describe('admin status chips: the label clears 4.5:1 on its actual ground, both themes (ADM-16a, ADM-16b)', () => {
  it('every status of both badges, at rest and on a hovered row', () => {
    const failures: string[] = []
    let measured = 0
    for (const [name, Badge, statuses] of CHIPS) {
      for (const status of statuses) {
        const { container, unmount } = render(createElement(Badge, { status: status as never }))
        const chip = container.firstElementChild as HTMLElement
        for (const theme of ['light', 'dark'] as const) {
          const { text: ink, bg } = chipColours(chip.className, theme)
          // A dark: background left unset falls back to the light one, as the cascade does.
          const ground = bg ?? (theme === 'dark' ? chipColours(chip.className, 'light').bg : undefined) ?? ([0, 0, 0, 0] as Rgba)
          if (!ink) {
            failures.push(`${name} ${status} (${theme}): no ${theme === 'dark' ? 'dark:' : ''}text- colour this spec can resolve`)
            continue
          }
          for (const [row, rowColour] of ROWS[theme]) {
            const r = ratio(over(ink, over(ground, rowColour)), over(ground, rowColour))
            measured += 1
            if (r < 4.5) failures.push(`${name} ${status} (${theme}, ${row}): ${r.toFixed(2)}:1`)
          }
        }
        unmount()
      }
    }
    expect(failures).toEqual([])
    // Seven statuses, two themes, two rows: a reader that measured nothing must not pass.
    expect(measured).toBe(28)
  })

  it('reads a tinted ground and its alpha, so the old recipe would fail', () => {
    // The Pending chip before this change: info.light inside its own 10% tint, on the panel row.
    const { text, bg } = chipColours('border-info-light/40 bg-info-light/10 text-info-light', 'light')
    const ground = over(bg!, colour('panel-light')!)
    expect(ratio(over(text!, ground), ground)).toBeLessThan(4.5)
    expect(colour('black/[0.04]')![3]).toBeCloseTo(0.04)
    expect(colour('text-xs')).toBeNull()
  })
})
