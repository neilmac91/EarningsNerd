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
import { STATUS_CHIP, STATUS_CHIP_INK, type StatusChipTone } from '@/features/admin/lib/statusChip'

/**
 * The admin status chips' labels clear 4.5:1 on what is behind them, in both themes (audit ADM-16a,
 * ADM-16b; CLAUDE.md rule 11). The recipe has one home, features/admin/lib/statusChip.ts: each tone is
 * measured there once per theme per ground, from its classes resolved through tailwind.config.js, so a
 * token or recipe change is read as it ships: the label ink over the chip's ground, composited over the
 * table row the chip sits in, at rest and under the row's hover tint. Both badges are then held to that
 * recipe, status by status. A text- colour this spec cannot resolve fails, and so does a bg- or text-
 * arbitrary value (`bg-[...]`) that looks like a colour and is not a hex or rgb() it can read; a plain
 * unknown token name is skipped, since Tailwind emits no CSS for it either.
 */
const require = createRequire(import.meta.url)
const flattenColorPalette = (require('tailwindcss/lib/util/flattenColorPalette') as { default: (c: unknown) => Record<string, string> }).default
const ROOT = path.resolve(__dirname, '../..')
const COLORS = flattenColorPalette(resolveConfig(require(path.join(ROOT, 'tailwind.config.js')) as Config).theme.colors)

type Rgba = [number, number, number, number]

function rgba(color: string): Rgba {
  if (color.startsWith('#')) {
    const hex = color.slice(1)
    const [r, g, b, a = 255] = (hex.length <= 4 ? hex.split('').map((c) => c + c) : hex.match(/../g)!).map((v) => parseInt(v, 16))
    return [r, g, b, a / 255]
  }
  const [r, g, b, a = 1] = color.match(/[\d.]+/g)!.map(Number)
  return [r, g, b, a]
}

/**
 * A colour utility's value (`info-text`, `white`, `info-light/10`, `black/[0.04]`, an arbitrary
 * `[#1d4ed8]` or `[rgb(29,78,216)]`), or null for a non-colour one or one it cannot read.
 */
function colour(value: string): Rgba | null {
  if (value.startsWith('[') && value.endsWith(']')) {
    const inner = value.slice(1, -1).replace(/_/g, ' ')
    return /^#[0-9a-f]{3,8}$/i.test(inner) || /^rgba?\(/.test(inner) ? rgba(inner) : null
  }
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

/** An arbitrary value that is not a length, a url or a size: a colour this spec must read or refuse. */
const looksLikeColour = (value: string) => value.startsWith('[') && !/^\[(length:|url\(|position:|[\d.]+(px|rem|em|%)?\])/.test(value)

/** The chip's text and background colours in one theme, from its class list, and the colour-like classes it could not read. */
function chipColours(className: string, theme: 'light' | 'dark') {
  const found: { text?: Rgba; bg?: Rgba; unread: string[] } = { unread: [] }
  for (const cls of className.split(/\s+/)) {
    const parts = cls.split(':')
    const utility = parts.pop()!
    const variants = parts.join(':')
    if (variants !== (theme === 'dark' ? 'dark' : '')) continue
    const m = utility.match(/^(text|bg)-(.+)$/)
    if (!m) continue
    const value = colour(m[2])
    if (!value) {
      if (looksLikeColour(m[2])) found.unread.push(cls)
      continue
    }
    found[m[1] as 'text' | 'bg'] = value
  }
  return found
}

const TONES = Object.keys(STATUS_CHIP_INK) as StatusChipTone[]
const recipe = (tone: StatusChipTone) => `${STATUS_CHIP} ${STATUS_CHIP_INK[tone]}`

/** Every tone's label ratio on each row, in one theme, with any class the reader could not read. */
function measure(name: string, className: string, failures: string[]): number {
  let measured = 0
  for (const theme of ['light', 'dark'] as const) {
    const { text: ink, bg, unread } = chipColours(className, theme)
    for (const cls of unread) failures.push(`${name} (${theme}): ${cls} looks like a colour this spec cannot resolve`)
    // A dark: background left unset falls back to the light one, as the cascade does.
    const ground = bg ?? (theme === 'dark' ? chipColours(className, 'light').bg : undefined) ?? ([0, 0, 0, 0] as Rgba)
    if (!ink) {
      failures.push(`${name} (${theme}): no ${theme === 'dark' ? 'dark:' : ''}text- colour this spec can resolve`)
      continue
    }
    for (const [row, rowColour] of ROWS[theme]) {
      const r = ratio(over(ink, over(ground, rowColour)), over(ground, rowColour))
      measured += 1
      if (r < 4.5) failures.push(`${name} (${theme}, ${row}): ${r.toFixed(2)}:1`)
    }
  }
  return measured
}

const CHIPS: Array<[string, FunctionComponent<{ status: never }>, string[]]> = [
  ['InviteStatusBadge', InviteStatusBadge as FunctionComponent<{ status: never }>, ['pending', 'used', 'expired', 'revoked'] satisfies InviteStatus[]],
  ['FeedbackStatusBadge', FeedbackStatusBadge as FunctionComponent<{ status: never }>, ['new', 'triaged', 'resolved'] satisfies FeedbackStatus[]],
]

const classSet = (className: string) => [...new Set(className.split(/\s+/).filter(Boolean))].sort().join(' ')

describe('admin status chips: the label clears 4.5:1 on its actual ground, both themes (ADM-16a, ADM-16b)', () => {
  it('every tone of the status chip recipe, at rest and on a hovered row', () => {
    const failures: string[] = []
    let measured = 0
    for (const tone of TONES) measured += measure(`status chip ${tone}`, recipe(tone), failures)
    expect(failures).toEqual([])
    // Four tones, two themes, two rows: a reader that measured nothing must not pass.
    expect(measured).toBe(16)
  })

  it('both badges render every status on the recipe, so the measurement above is what ships', () => {
    const failures: string[] = []
    let rendered = 0
    for (const [name, Badge, statuses] of CHIPS) {
      for (const status of statuses) {
        const { container, unmount } = render(createElement(Badge, { status: status as never }))
        const chip = classSet((container.firstElementChild as HTMLElement).className)
        rendered += 1
        if (!TONES.some((tone) => classSet(recipe(tone)) === chip)) {
          failures.push(`${name} ${status}: "${chip}" is not STATUS_CHIP plus one STATUS_CHIP_INK tone`)
        }
        unmount()
      }
    }
    expect(failures).toEqual([])
    expect(rendered).toBe(7)
  })

  it('reads a tinted ground and its alpha, so the old recipe would fail', () => {
    // The Pending chip before this change: info.light inside its own 10% tint, on the panel row.
    const { text, bg } = chipColours('border-info-light/40 bg-info-light/10 text-info-light', 'light')
    const ground = over(bg!, colour('panel-light')!)
    expect(ratio(over(text!, ground), ground)).toBeLessThan(4.5)
    expect(colour('black/[0.04]')![3]).toBeCloseTo(0.04)
    expect(colour('text-xs')).toBeNull()
  })

  it('measures an arbitrary hex or rgb() ground and refuses one it cannot read', () => {
    // The ink's own colour as the chip's ground: 1:1, so it fails on contrast rather than passing.
    const sameInk: string[] = []
    measure('probe', 'bg-[rgb(29,78,216)] text-info-text dark:text-info-dark', sameInk)
    expect(sameInk).toContain('probe (light, row): 1.00:1')
    const unread: string[] = []
    measure('probe', 'bg-[hsl(224,76%,48%)] text-info-text dark:text-info-dark', unread)
    expect(unread).toContain('probe (light): bg-[hsl(224,76%,48%)] looks like a colour this spec cannot resolve')
    expect(chipColours('bg-[url(/x.png)] bg-white text-info-text', 'light').unread).toEqual([])
  })
})
