import { createElement } from 'react'
import { createRequire } from 'node:module'
import path from 'node:path'
import { render } from '@testing-library/react'
import type { Config } from 'tailwindcss'
import resolveConfig from 'tailwindcss/resolveConfig'
import { describe, expect, it } from 'vitest'
import { Badge } from '@/components/ui'
import { directionChip } from '@/lib/financialTone'

/**
 * A direction chip's label clears 4.5:1 in its tint, on the panel and on the page, in both themes (E282, D-074;
 * CLAUDE.md rule 11). The chips draw their label at 12px, so AA's small-text floor is the one that holds. Measured:
 * every tone of lib/financialTone's directionChip (the dashboard's What changed card, the auth shell's example) and
 * Badge's two direction variants, beat and miss, each read from its classes as it ships and resolved through
 * tailwind.config.js: the label's ink over the chip's tint, the tint composited on the ground. Light reads the bare
 * classes; dark reads the `dark:` ones, and a chip with no dark ink or tint keeps its light one there, as the
 * stylesheet does. A chip with no ink or no tint, two of either in one theme (the stylesheet's order, which this spec
 * does not read, would pick one), a colour-like value it cannot read, an opacity modifier on a colour that carries its
 * own alpha (Tailwind replaces that alpha, which this spec does not model), or an ink or tint under any other variant
 * (a hover, a breakpoint: the chip is measured as it rests) fails, so nothing falls back to a default. A tint's
 * opacity (`bg-flat-dark/10`), an ink's (`text-loss-dark/70`) and an rgba token's alpha are applied. Out of reach: a
 * class a caller adds beside the recipe, and a hand-rolled tint of the same tokens, such as the insider panel's Buys
 * and Sells tiles, which pair the tokens Badge's beat and miss pair.
 */
const require = createRequire(import.meta.url)
const flattenColorPalette = (require('tailwindcss/lib/util/flattenColorPalette') as { default: (c: unknown) => Record<string, string> }).default
const ROOT = path.resolve(__dirname, '../..')
const COLORS = flattenColorPalette(resolveConfig(require(path.join(ROOT, 'tailwind.config.js')) as Config).theme.colors)

type Rgba = [number, number, number, number]
type Theme = 'light' | 'dark'
const THEMES: Theme[] = ['light', 'dark']
/** WCAG AA for text under 18pt (24px), or under 14pt (18.66px) bold: the chips' labels are 12px. */
const FLOOR = 4.5

function parse(value: string): Rgba | null {
  const hex = /^#([0-9a-f]{6})$/i.exec(value)
  if (hex) return [parseInt(hex[1].slice(0, 2), 16), parseInt(hex[1].slice(2, 4), 16), parseInt(hex[1].slice(4, 6), 16), 1]
  const fn = /^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/.exec(value)
  if (fn) return [Number(fn[1]), Number(fn[2]), Number(fn[3]), fn[4] === undefined ? 1 : Number(fn[4])]
  return null
}

const over = (top: Rgba, ground: Rgba): Rgba => [
  top[0] * top[3] + ground[0] * (1 - top[3]),
  top[1] * top[3] + ground[1] * (1 - top[3]),
  top[2] * top[3] + ground[2] * (1 - top[3]),
  1,
]
const channel = (v: number) => {
  const s = v / 255
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}
const luminance = ([r, g, b]: Rgba) => 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
const ratio = (a: Rgba, b: Rgba) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/** Splits a class at its variant colons, never inside an arbitrary value's brackets. */
const classParts = (cls: string) => cls.split(/:(?![^[]*\])/)

/** A text- or bg- colour utility, resolved with its opacity; null when the utility sets no colour (`text-xs`). A colour it
 *  cannot read comes back as `colour: null`, with a failure saying why, so its theme never falls back to another. */
function colourOf(utility: string, where: string, failures: string[]): { kind: 'ink' | 'tint'; colour: Rgba | null } | null {
  const m = /^(text|bg)-(.+)$/.exec(utility)
  if (!m) return null
  const kind = m[1] === 'text' ? 'ink' : 'tint'
  const slash = m[2].search(/\/(?![^[]*\])/)
  const name = slash === -1 ? m[2] : m[2].slice(0, slash)
  const modifier = slash === -1 ? undefined : m[2].slice(slash + 1)
  let colour: Rgba | null
  if (name.startsWith('[')) {
    const inner = name.slice(1, -1)
    colour = parse(inner)
    if (!colour) {
      if (!/^(#|rgb)/i.test(inner)) return null
      failures.push(`${where}: ${utility} looks like a colour this spec cannot read`)
      return { kind, colour: null }
    }
  } else {
    const value = COLORS[name]
    if (value === undefined) return null
    colour = parse(value)
    if (!colour) {
      failures.push(`${where}: ${utility} resolves to ${value}, which this spec cannot read`)
      return { kind, colour: null }
    }
  }
  if (modifier !== undefined) {
    const alpha = /^\d+$/.test(modifier) ? Number(modifier) / 100 : /^\[([\d.]+)\]$/.test(modifier) ? Number(modifier.slice(1, -1)) : NaN
    if (!Number.isFinite(alpha)) {
      failures.push(`${where}: ${utility}'s opacity cannot be read`)
      return { kind, colour: null }
    }
    if (colour[3] < 1) {
      failures.push(`${where}: ${utility} sets an opacity on a colour with its own alpha, which Tailwind replaces`)
      return { kind, colour: null }
    }
    colour = [colour[0], colour[1], colour[2], alpha]
  }
  return { kind, colour }
}

/** The chip's ink and tint in each theme, from its classes; null for a theme it cannot resolve (a failure says why). */
function chipColours(name: string, className: string, failures: string[]): Record<Theme, { ink: Rgba; tint: Rgba } | null> {
  const found: Record<Theme, { ink: Array<Rgba | null>; tint: Array<Rgba | null> }> = { light: { ink: [], tint: [] }, dark: { ink: [], tint: [] } }
  for (const cls of className.split(/\s+/).filter(Boolean)) {
    const parts = classParts(cls)
    const utility = parts.pop() as string
    const resolved = colourOf(utility.replace(/^!/, ''), name, failures)
    if (!resolved) continue
    const theme = parts.length === 0 ? 'light' : parts.length === 1 && parts[0] === 'dark' ? 'dark' : null
    if (theme === null || utility.startsWith('!')) {
      failures.push(`${name}: ${cls} is an ink or tint under a variant this spec does not measure`)
      continue
    }
    found[theme][resolved.kind].push(resolved.colour)
  }
  const pick = (theme: Theme, kind: 'ink' | 'tint'): Rgba | null => {
    const own = found[theme][kind]
    const list = theme === 'dark' && own.length === 0 ? found.light[kind] : own
    if (list.length === 1) return list[0]
    if (list.includes(null)) return null
    failures.push(`${name} (${theme}): ${list.length === 0 ? `no ${kind}` : `${list.length} ${kind}s`}`)
    return null
  }
  return Object.fromEntries(
    THEMES.map((theme) => {
      const ink = pick(theme, 'ink')
      const tint = pick(theme, 'tint')
      return [theme, ink && tint ? { ink, tint } : null]
    }),
  ) as Record<Theme, { ink: Rgba; tint: Rgba } | null>
}

const GROUNDS: Record<Theme, Array<[string, string]>> = {
  light: [['panel', 'panel-light'], ['page', 'background-light']],
  dark: [['panel', 'panel-dark'], ['page', 'background-dark']],
}

/** Every label under the floor, as `name (theme) on ground: ink on tint X.XX:1`. */
function underTheFloor(name: string, className: string): string[] {
  const failures: string[] = []
  const colours = chipColours(name, className, failures)
  for (const theme of THEMES) {
    const chip = colours[theme]
    if (!chip) continue
    for (const [label, token] of GROUNDS[theme]) {
      const ground = parse(COLORS[token] ?? '')
      if (!ground || ground[3] < 1) {
        failures.push(`${token}: not an opaque colour this spec can read`)
        continue
      }
      const tint = over(chip.tint, ground)
      const r = ratio(over(chip.ink, tint), tint)
      if (r < FLOOR) failures.push(`${name} (${theme}) on the ${label}: ${r.toFixed(2)}:1 in its tint, under ${FLOOR}:1`)
    }
  }
  return failures
}

const badgeClasses = (variant: 'beat' | 'miss') => {
  const { container } = render(createElement(Badge, { variant }, 'x'))
  return (container.firstElementChild as HTMLElement).className
}

describe("direction chips: the label clears 4.5:1 in its tint on the panel and the page, both themes (E282)", () => {
  it("every tone of directionChip, and Badge's beat and miss, as they ship", () => {
    const recipes: Array<[string, string]> = [
      ...Object.entries(directionChip).map(([tone, cls]): [string, string] => [`directionChip.${tone}`, cls]),
      ['Badge beat', badgeClasses('beat')],
      ['Badge miss', badgeClasses('miss')],
    ]
    expect(recipes.map(([name]) => name)).toEqual(['directionChip.up', 'directionChip.down', 'directionChip.flat', 'Badge beat', 'Badge miss'])
    expect(recipes.flatMap(([name, cls]) => underTheFloor(name, cls))).toEqual([])
  })

  it('fails a faint label, an opacity, a missing or doubled colour, an unmeasured variant and a value it cannot read', () => {
    const down = directionChip.down
    // rose-400, the dark loss ink before E282: 4.44:1 in its tint on the panel.
    expect(underTheFloor('plant', down.replace('dark:text-loss-dark', 'dark:text-[#FB7185]'))).toEqual([
      'plant (dark) on the panel: 4.44:1 in its tint, under 4.5:1',
    ])
    expect(underTheFloor('plant', down.replace('dark:text-loss-dark', 'dark:text-loss-dark/70'))).toEqual([
      'plant (dark) on the panel: 3.65:1 in its tint, under 4.5:1',
      'plant (dark) on the page: 4.45:1 in its tint, under 4.5:1',
    ])
    expect(underTheFloor('plant', 'text-loss-text dark:text-loss-dark')).toEqual(['plant (light): no tint', 'plant (dark): no tint'])
    expect(underTheFloor('plant', `${down} dark:text-gain-dark`)).toEqual(['plant (dark): 2 inks'])
    expect(underTheFloor('plant', `${down} hover:text-loss-light`)).toEqual([
      'plant: hover:text-loss-light is an ink or tint under a variant this spec does not measure',
    ])
    expect(underTheFloor('plant', down.replace('dark:bg-loss-soft-dark', 'dark:bg-loss-soft-dark/20'))).toEqual([
      'plant: bg-loss-soft-dark/20 sets an opacity on a colour with its own alpha, which Tailwind replaces',
    ])
    expect(underTheFloor('plant', down.replace('dark:text-loss-dark', 'dark:text-[#FB71]'))).toEqual([
      'plant: text-[#FB71] looks like a colour this spec cannot read',
    ])
    // A dark chip with no dark classes keeps its light ink and tint, as the stylesheet does.
    expect(underTheFloor('plant', 'text-loss-text bg-loss-soft')).toEqual([])
  })
})
