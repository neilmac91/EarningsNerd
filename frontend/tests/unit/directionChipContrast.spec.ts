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
 * does not read, would pick one), a colour-like value it cannot read (an arbitrary value that is not a hex, a
 * comma-separated rgb() or rgba() with numbers as CSS spells them, channels to 255 and an alpha to 1, or a length or
 * size such as `text-[13px]`; `text-[var(--x)]` and `rgba(251,113,133,.)` fail), an opacity
 * modifier it cannot apply as written (on a colour that carries its own alpha, which Tailwind replaces; above 1; or off
 * Tailwind's opacity scale, such as `/98`, for which Tailwind emits nothing), an ink or tint under any other variant (a
 * hover, a breakpoint: the chip is measured as it rests) or marked important, an opacity utility below 100 under any
 * variant (`opacity-`, `text-opacity-`, `bg-opacity-`), or an arbitrary property (`[color:...]`) fails, so nothing
 * falls back to a default. A tint's opacity modifier (`bg-flat-dark/10`), an ink's (`text-loss-dark/70`, `/[70%]`,
 * `/[0.7]`) and an rgba token's alpha are applied, and each composite is rounded to 8-bit channels, as the browser
 * paints it. The grounds are the panel and the page; the auth shell's example sits on a glass card whose dark ground
 * lies between the two (its light tint is opaque). Out of reach: a class a caller adds beside the recipe; a utility
 * that changes what is painted without setting a colour or an opacity (a filter, a blend mode, a gradient); and a
 * hand-rolled tint of the same tokens, such as the insider panel's Buys and Sells tiles, which pair the tokens Badge's
 * beat and miss pair.
 */
const require = createRequire(import.meta.url)
const flattenColorPalette = (require('tailwindcss/lib/util/flattenColorPalette') as { default: (c: unknown) => Record<string, string> }).default
const ROOT = path.resolve(__dirname, '../..')
const THEME = resolveConfig(require(path.join(ROOT, 'tailwind.config.js')) as Config).theme
const COLORS = flattenColorPalette(THEME.colors)
/** The scale a colour's opacity modifier reads (`/10`), as Tailwind resolves it; a key off it emits no CSS. */
const OPACITY_SCALE = THEME.opacity as Record<string, string>

type Rgba = [number, number, number, number]
type Theme = 'light' | 'dark'
const THEMES: Theme[] = ['light', 'dark']
/** WCAG AA for text under 18pt (24px), or under 14pt (18.66px) bold: the chips' labels are 12px. */
const FLOOR = 4.5

/** A number as CSS spells one (`1`, `0.14`, `.5`): `1.` and `.` are not, and the browser drops a declaration with one. */
const NUMBER = String.raw`(?:\d+(?:\.\d+)?|\.\d+)`
const HEX = /^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/i
const RGB = new RegExp(String.raw`^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(${NUMBER})\s*)?\)$`)

/** A hex (#rgb, #rgba, #rrggbb, #rrggbbaa) or a comma-separated rgb()/rgba(), or null: a channel over 255 or an alpha over 1,
 *  which the browser would clamp, is not read as written but refused. */
function parse(value: string): Rgba | null {
  const hex = HEX.exec(value)
  if (hex) {
    const digits = hex[1].length <= 4 ? [...hex[1]].map((c) => c + c).join('') : hex[1]
    const [r, g, b, a = 255] = (digits.match(/../g) as string[]).map((v) => parseInt(v, 16))
    return [r, g, b, a / 255]
  }
  const fn = RGB.exec(value)
  if (!fn) return null
  const colour: Rgba = [Number(fn[1]), Number(fn[2]), Number(fn[3]), fn[4] === undefined ? 1 : Number(fn[4])]
  return colour.slice(0, 3).every((c) => c <= 255) && colour[3] <= 1 ? colour : null
}

/** One colour over an opaque ground, rounded to 8-bit channels as the browser paints it. */
const over = (top: Rgba, ground: Rgba): Rgba => [
  Math.round(top[0] * top[3] + ground[0] * (1 - top[3])),
  Math.round(top[1] * top[3] + ground[1] * (1 - top[3])),
  Math.round(top[2] * top[3] + ground[2] * (1 - top[3])),
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
/** An arbitrary value Tailwind reads as something other than a colour (`text-[13px]`, `bg-[url(...)]`). */
const NOT_A_COLOUR = /^(length:|url\(|position:|size:|(calc|clamp|min|max)\(|[\d.]+[a-z%]*$)/i
/** An opacity utility (`opacity-60`, `dark:text-opacity-60`, `bg-opacity-[.5]`) that fades what it is on. */
const OPACITY = /^(text-|bg-)?opacity-(.+)$/
/** An opacity utility's value that fades nothing. */
const FULL_OPACITY = /^(100|\[(1(\.0*)?|100(\.0*)?%)\])$/

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
    const inner = name.slice(1, -1).replace(/_/g, ' ')
    colour = parse(inner)
    if (!colour) {
      if (NOT_A_COLOUR.test(inner)) return null
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
    const arbitrary = new RegExp(String.raw`^\[(${NUMBER})(%?)\]$`).exec(modifier)
    const scaled = Object.hasOwn(OPACITY_SCALE, modifier) ? Number(OPACITY_SCALE[modifier]) : undefined
    const alpha = scaled ?? (arbitrary ? Number(arbitrary[1]) / (arbitrary[2] ? 100 : 1) : NaN)
    if (scaled === undefined && /^\d+$/.test(modifier)) {
      failures.push(`${where}: ${utility}'s opacity is off Tailwind's scale, so it emits no CSS for it`)
      return { kind, colour: null }
    }
    if (!Number.isFinite(alpha) || alpha > 1) {
      failures.push(`${where}: ${utility}'s opacity cannot be read as one between 0 and 1`)
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
    const bare = utility.replace(/^!/, '')
    const fade = OPACITY.exec(bare)
    if (fade && !FULL_OPACITY.test(fade[2])) {
      failures.push(`${name}: ${cls} fades the chip, which this spec does not measure`)
      continue
    }
    if (bare.startsWith('[')) {
      failures.push(`${name}: ${cls} is an arbitrary property this spec does not read`)
      continue
    }
    const resolved = colourOf(bare, name, failures)
    if (!resolved) continue
    const theme = parts.length === 0 ? 'light' : parts.length === 1 && parts[0] === 'dark' ? 'dark' : null
    if (utility.startsWith('!')) {
      failures.push(`${name}: ${cls} is an ink or tint marked important, which this spec does not rank against the others`)
      // Its theme reads no other ink or tint in its place, so dark never falls back to light's.
      if (theme !== null) found[theme][resolved.kind].push(null)
      continue
    }
    if (theme === null) {
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
      if (!(r >= FLOOR)) failures.push(`${name} (${theme}) on the ${label}: ${r.toFixed(2)}:1 in its tint, under ${FLOOR}:1`)
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

  it('fails a faint label, an opacity, a missing or doubled colour, an unmeasured variant and a value or property it cannot read', () => {
    const down = directionChip.down
    // rose-400, the dark loss ink before E282: 4.44:1 in its tint on the panel.
    expect(underTheFloor('plant', down.replace('dark:text-loss-dark', 'dark:text-[#FB7185]'))).toEqual([
      'plant (dark) on the panel: 4.44:1 in its tint, under 4.5:1',
    ])
    for (const faded of ['dark:text-loss-dark/70', 'dark:text-loss-dark/[70%]', 'dark:text-loss-dark/[0.7]']) {
      expect(underTheFloor('plant', down.replace('dark:text-loss-dark', faded))).toEqual([
        'plant (dark) on the panel: 3.64:1 in its tint, under 4.5:1',
        'plant (dark) on the page: 4.45:1 in its tint, under 4.5:1',
      ])
    }
    expect(underTheFloor('plant', 'text-loss-text dark:text-loss-dark')).toEqual(['plant (light): no tint', 'plant (dark): no tint'])
    expect(underTheFloor('plant', `${down} dark:text-gain-dark`)).toEqual(['plant (dark): 2 inks'])
    expect(underTheFloor('plant', `${down} hover:text-loss-light`)).toEqual([
      'plant: hover:text-loss-light is an ink or tint under a variant this spec does not measure',
    ])
    expect(underTheFloor('plant', down.replace('dark:bg-loss-soft-dark', 'dark:bg-loss-soft-dark/20'))).toEqual([
      'plant: bg-loss-soft-dark/20 sets an opacity on a colour with its own alpha, which Tailwind replaces',
    ])
    expect(underTheFloor('plant', down.replace('dark:text-loss-dark', 'dark:text-[#FB718]'))).toEqual([
      'plant: text-[#FB718] looks like a colour this spec cannot read',
    ])
    expect(underTheFloor('plant', down.replace('dark:text-loss-dark', 'dark:text-[var(--ink)]'))).toEqual([
      'plant: text-[var(--ink)] looks like a colour this spec cannot read',
    ])
    expect(underTheFloor('plant', `${down} text-[13px] text-[calc(1rem+1px)] text-[0.8cqw]`)).toEqual([])
    // Spellings the browser drops or clamps: refused, so the theme never falls back or reads past what is painted.
    expect(underTheFloor('plant', down.replace('dark:text-loss-dark', 'dark:text-loss-dark/[1.]'))).toEqual([
      "plant: text-loss-dark/[1.]'s opacity cannot be read as one between 0 and 1",
    ])
    for (const [from, to] of [
      ['dark:text-loss-dark', 'text-[rgba(255,150,161,1.)]'],
      ['dark:text-loss-dark', 'text-[rgba(255,150,161,0.)]'],
      ['dark:text-loss-dark', 'text-[rgba(251,113,133,.)]'],
      ['dark:text-loss-dark', 'text-[rgba(251,113,133,2)]'],
      ['dark:text-loss-dark', 'text-[rgb(300,113,133)]'],
      ['dark:bg-loss-soft-dark', 'bg-[rgba(251,113,133,.)]'],
    ]) {
      expect(underTheFloor('plant', down.replace(from, `dark:${to}`))).toEqual([`plant: ${to} looks like a colour this spec cannot read`])
    }
    // White's #fff, the dark tint idiom (bg-white/5), is read: the flat chip on it reads above the floor, and #fff and
    // #ffff read as white (white on white is 1:1).
    expect(underTheFloor('plant', directionChip.flat.replace('dark:bg-flat-dark/10', 'dark:bg-white/5'))).toEqual([])
    expect(underTheFloor('plant', 'text-loss-text bg-loss-soft dark:text-[#ffff] dark:bg-white')).toEqual([
      'plant (dark) on the panel: 1.00:1 in its tint, under 4.5:1',
      'plant (dark) on the page: 1.00:1 in its tint, under 4.5:1',
    ])
    expect(underTheFloor('plant', down.replace('dark:text-loss-dark', 'dark:text-loss-dark/98'))).toEqual([
      "plant: text-loss-dark/98's opacity is off Tailwind's scale, so it emits no CSS for it",
    ])
    expect(underTheFloor('plant', down.replace('dark:text-loss-dark', 'dark:text-[#FB7185]/[200%]'))).toEqual([
      "plant: text-[#FB7185]/[200%]'s opacity cannot be read as one between 0 and 1",
    ])
    expect(underTheFloor('plant', down.replace('dark:text-loss-dark', 'dark:!text-loss-dark'))).toEqual([
      'plant: dark:!text-loss-dark is an ink or tint marked important, which this spec does not rank against the others',
    ])
    // Tailwind emits an opacity utility after the ink, so it fades the label: refused, not measured.
    for (const fade of ['dark:text-opacity-60', 'opacity-60', 'dark:opacity-50', 'bg-opacity-90']) {
      expect(underTheFloor('plant', `${down} ${fade}`)).toEqual([`plant: ${fade} fades the chip, which this spec does not measure`])
    }
    for (const full of ['dark:text-opacity-100', 'opacity-[1]', 'opacity-[100%]']) expect(underTheFloor('plant', `${down} ${full}`)).toEqual([])
    expect(underTheFloor('plant', `${down} dark:[color:#FB7185]`)).toEqual([
      'plant: dark:[color:#FB7185] is an arbitrary property this spec does not read',
    ])
    // A dark chip with no dark classes keeps its light ink and tint, as the stylesheet does.
    expect(underTheFloor('plant', 'text-loss-text bg-loss-soft')).toEqual([])
  })
})
