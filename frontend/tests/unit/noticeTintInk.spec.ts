import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import type { Config } from 'tailwindcss'
import resolveConfig from 'tailwindcss/resolveConfig'
import { describe, expect, it } from 'vitest'
import { noticeTint, type NoticeVariant } from '@/components/ui'

/**
 * Words set in a status ink inside Notice's tint clear 4.5:1 on the panel and on the page, in both themes (E283;
 * CLAUDE.md rule 11). Notice itself sets its words in the primary and secondary inks and only its glyph in the
 * variant's (a graphic, 3:1), so the status ink sets words in the tint only where a borrower of noticeTint() writes
 * them so, and each such borrower is listed in INKED. The one today is the settings page's Delete account warning,
 * whose words wore the error ink on the loss tint, 4.32:1 in dark, until it took Notice's error tint (4.62:1).
 *
 * The tint is read from noticeTint() as it ships and the inks from the borrower's source, both resolved through
 * tailwind.config.js. Every class of the variant's ink family the borrower writes must be one of the inks listed, so a
 * faded or varied ink (`dark:text-error-dark/80`, `hover:text-error-light`) fails rather than passing unmeasured: light reads the bare `bg-` class, dark the `dark:bg-` one, each with its opacity modifier
 * (`/[0.06]`, or `/10` on Tailwind's opacity scale), composited on the ground and rounded to 8-bit channels, as the
 * browser paints it. A tint or ink it cannot read fails. Out of reach: an ink written outside the borrower's own file.
 */
const require = createRequire(import.meta.url)
const flattenColorPalette = (require('tailwindcss/lib/util/flattenColorPalette') as { default: (c: unknown) => Record<string, string> }).default
const ROOT = path.resolve(__dirname, '../..')
const THEME = resolveConfig(require(path.join(ROOT, 'tailwind.config.js')) as Config).theme
const COLORS = flattenColorPalette(THEME.colors)
const OPACITY_SCALE = THEME.opacity as Record<string, string>
const FLOOR = 4.5

type Rgb = [number, number, number]
type Theme = 'light' | 'dark'

/** The borrowers whose words take the variant's ink inside the tint, with the inks they write. */
const INKED: { file: string; variant: NoticeVariant; ink: Record<Theme, string> }[] = [
  { file: 'app/dashboard/settings/page.tsx', variant: 'error', ink: { light: 'text-error-light', dark: 'dark:text-error-dark' } },
]

function hex(value: string | undefined): Rgb {
  const m = /^#([0-9a-f]{6})$/i.exec(value ?? '')
  if (!m) throw new Error(`a colour this spec cannot read: ${value}`)
  return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16)) as Rgb
}
const channel = (v: number) => {
  const s = v / 255
  return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
}
const luminance = ([r, g, b]: Rgb) => 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
const ratio = (a: Rgb, b: Rgb) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}
const over = (top: Rgb, alpha: number, ground: Rgb): Rgb => top.map((c, i) => Math.round(c * alpha + ground[i] * (1 - alpha))) as Rgb

/** A tint's colour and opacity from its `bg-` class in one theme (`dark:` for dark), or a throw. */
function tint(classes: string, theme: Theme): { colour: Rgb; alpha: number } {
  const prefix = theme === 'dark' ? 'dark:bg-' : 'bg-'
  const found = classes.split(/\s+/).filter((c) => c.startsWith(prefix) && (theme === 'dark' || !c.includes(':')))
  if (found.length !== 1) throw new Error(`${theme}: ${found.length} tints in "${classes}"`)
  const m = /^(?:dark:)?bg-([a-z-]+)\/(?:\[(\d*\.?\d+)\]|(\d+))$/.exec(found[0])
  if (!m) throw new Error(`a tint this spec cannot read: ${found[0]}`)
  const alpha = m[2] !== undefined ? Number(m[2]) : Number(OPACITY_SCALE[m[3]])
  if (!(alpha > 0 && alpha <= 1)) throw new Error(`an opacity this spec cannot read: ${found[0]}`)
  return { colour: hex(COLORS[m[1]]), alpha }
}
const inkOf = (cls: string) => hex(COLORS[cls.replace(/^(?:dark:)?text-/, '')])
/** The classes of a variant's ink family a source writes that are not the inks the spec measures. */
function unmeasuredInks(source: string, variant: NoticeVariant, ink: Record<Theme, string>): string[] {
  const family = new RegExp(String.raw`(?<![\w:/-])(?:[\w-]+:)*text-${variant}-[\w-]+(?:\/[^\s'"\`]+)?(?=[\s'"\`]|$)`, 'g')
  return [...new Set(source.match(family) ?? [])].filter((cls) => !Object.values(ink).includes(cls))
}
const GROUNDS: Record<Theme, Record<string, Rgb>> = {
  light: { panel: hex(COLORS['panel-light']), page: hex(COLORS['background-light']) },
  dark: { panel: hex(COLORS['panel-dark']), page: hex(COLORS['background-dark']) },
}

describe("words in a status ink inside Notice's tint (E283)", () => {
  it.each(INKED)('$file: its $variant words clear 4.5:1 in the tint on the panel and the page, in both themes', ({ file, variant, ink }) => {
    const source = readFileSync(path.join(ROOT, file), 'utf8')
    expect(source, `${file} lends the ${variant} tint`).toContain(`noticeTint('${variant}')`)
    for (const cls of Object.values(ink)) expect(source, `${file} writes ${cls}`).toMatch(new RegExp(`(?:^|[\\s'"\`])${cls.replace(/[:/]/g, '\\$&')}(?=[\\s'"\`])`))
    expect(unmeasuredInks(source, variant, ink), `${file} writes the ${variant} ink only as measured`).toEqual([])
    const failing: string[] = []
    for (const theme of ['light', 'dark'] as Theme[]) {
      const { colour, alpha } = tint(noticeTint(variant), theme)
      for (const [name, ground] of Object.entries(GROUNDS[theme])) {
        const measured = ratio(inkOf(ink[theme]), over(colour, alpha, ground))
        if (measured < FLOOR) failing.push(`${theme} on the ${name}: ${measured.toFixed(2)}:1`)
      }
    }
    expect(failing).toEqual([])
  })

  it('fails what it should: the loss tint the warning wore, and a tint it cannot read', () => {
    // The loss tint (loss-soft-dark, an rgba token) under the error ink, on the dark panel: 4.32:1, under the floor.
    const m = /^rgba\((\d+),(\d+),(\d+),(\d*\.?\d+)\)$/.exec(COLORS['loss-soft-dark'] ?? '')
    if (!m) throw new Error(`loss-soft-dark is not the rgba this case reads: ${COLORS['loss-soft-dark']}`)
    const loss: Rgb = [Number(m[1]), Number(m[2]), Number(m[3])]
    const measured = ratio(inkOf('dark:text-error-dark'), over(loss, Number(m[4]), GROUNDS.dark.panel))
    expect(measured.toFixed(2)).toBe('4.32')
    expect(measured).toBeLessThan(FLOOR)
    expect(() => tint('bg-error-light', 'light')).toThrow('a tint this spec cannot read')
    expect(() => tint('bg-error-light/[0.06] bg-error-light/10', 'light')).toThrow('2 tints')
    expect(() => tint('dark:bg-error-dark/10', 'light')).toThrow('0 tints')
    const inks = { light: 'text-error-light', dark: 'dark:text-error-dark' }
    expect(unmeasuredInks(`<p className="text-error-light dark:text-error-dark">a</p><ul className="text-sm dark:text-error-dark/80 hover:text-error-light">`, 'error', inks))
      .toEqual(['dark:text-error-dark/80', 'hover:text-error-light'])
  })
})
