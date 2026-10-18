import { readdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { render } from '@testing-library/react'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { Badge, Card } from '@/components/ui'

/**
 * chrome/F8, chrome/F9 (D-032): a status chip is its own Badge variant, never a data colour. `beat` and
 * `miss` are the earnings-surprise direction (gain/loss tokens, ▲/▼); the watchlist and dashboard rows
 * used them, glyph stripped, to say "Ready" and "Error", and the Badge header documented that as a
 * "tonal recipe". Badge now has `success` and `error`.
 *
 * Holds:
 *  - `success` and `error` exist, carry the status tokens and no automatic glyph, and their label clears
 *    4.5:1 on the chip's own ground in both themes, on the card at rest and on a row hovered with the
 *    product's row tint (`hover:bg-brand-weak dark:hover:bg-white/5`): the ground is read from the variant's
 *    classes, so a move to a tint that drops the success ink under the floor fails here, and so does a dark
 *    fill of the chip's own over the row's (error-dark falls to 3.9:1 there);
 *  - Badge.tsx no longer documents beat/miss/new as tonal recipes;
 *  - no `<Badge icon={null}>` in app/, components/ or features/ takes `beat` or `miss` (a literal, or a
 *    variable in a file that names either): a direction without its glyph is a status in data colours.
 *    No file is exempt: the watchlist and dashboard rows say "Ready" and "Error" on success and error;
 *  - `new` is the brand tint with its sage dot (D-032, E51): the `brand` chip's own classes, so it cannot drift
 *    back to the warning tint or apart from the brand chip, a pulse dot in the label's ink that stops under
 *    reduced motion, and a label that clears 4.5:1 in both themes on the interactive Card its one use sits on
 *    (the dashboard's What changed card), at rest and pressed, the grounds read from Card's own classes.
 */

const ROOT = path.resolve(__dirname, '../..')
const config = createRequire(import.meta.url)('../../tailwind.config.js') as {
  theme: { extend: { colors: Record<string, Record<string, string>> } }
}
const C = config.theme.extend.colors

type Rgb = [number, number, number]
const hex = (h: string): Rgb => [0, 2, 4].map((i) => parseInt(h.replace('#', '').slice(i, i + 2), 16)) as Rgb
const over = (top: Rgb, alpha: number, under: Rgb): Rgb => top.map((v, i) => v * alpha + under[i] * (1 - alpha)) as Rgb
const lum = (c: Rgb) => {
  const ch = (v: number) => {
    const s = v / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])
}
const contrast = (a: Rgb, b: Rgb) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/** `success-light` → its hex; `white` → #FFFFFF. */
const color = (name: string): Rgb => {
  if (name === 'white') return hex('#FFFFFF')
  const [family, ...rest] = name.split('-')
  const value = C[family]?.[rest.join('-')]
  if (typeof value !== 'string' || !value.startsWith('#')) throw new Error(`no hex token for ${name}`)
  return hex(value)
}

/** What a status chip sits on: the card, or the card under the product's row tint on a hovered row
    (`hover:bg-brand-weak dark:hover:bg-white/5`, the row token across the product). */
const rowGround = (theme: 'light' | 'dark', hovered: boolean): Rgb => {
  const card = hex(theme === 'dark' ? C.panel.dark : C.panel.light)
  if (!hovered) return card
  return theme === 'dark' ? over(hex('#FFFFFF'), 0.05, card) : hex(C.brand.weak)
}

/** The label ink and the ground it sits on, from the chip's own classes, over the row it sits on. */
function chipPair(classes: string[], theme: 'light' | 'dark', hovered = false): { ink: Rgb; ground: Rgb } {
  const own = classes.filter((c) => (theme === 'dark' ? c.startsWith('dark:') : !c.includes(':'))).map((c) => c.replace(/^dark:/, ''))
  const card = rowGround(theme, hovered)
  const bg = own.find((c) => c.startsWith('bg-'))?.slice(3)
  // The colour among the text utilities (BASE also sets the size, text-xs).
  const isColor = (name: string) => name === 'white' || typeof C[name.split('-')[0]]?.[name.split('-').slice(1).join('-')] === 'string'
  const text = own.filter((c) => c.startsWith('text-')).map((c) => c.slice(5)).find(isColor)
  if (!text) throw new Error(`no ${theme} label ink in ${classes.join(' ')}`)
  let ground = card
  if (bg && bg !== 'transparent') {
    const [name, pct] = bg.split('/')
    ground = pct ? over(color(name), Number(pct) / 100, card) : color(name)
  }
  return { ink: color(text), ground }
}

describe('Badge status variants (chrome/F8, chrome/F9)', () => {
  it.each(['success', 'error'] as const)('%s is a status chip: status tokens, no glyph, a label that clears 4.5:1 in both themes', (variant) => {
    const { container } = render(<Badge variant={variant}>Ready</Badge>)
    const chip = container.firstElementChild as HTMLElement
    const classes = chip.className.split(/\s+/)
    expect(classes).toEqual(expect.arrayContaining([`text-${variant}-light`, `dark:text-${variant}-dark`]))
    expect(chip.textContent).toBe('Ready')
    for (const theme of ['light', 'dark'] as const) {
      for (const hovered of [false, true]) {
        const { ink, ground } = chipPair(classes, theme, hovered)
        expect(Math.round(contrast(ink, ground) * 100) / 100, `${variant} label in ${theme}${hovered ? ' on a hovered row' : ''}`).toBeGreaterThanOrEqual(4.5)
      }
    }
  })

  it('the Badge header no longer offers beat/miss/new as tonal recipes', () => {
    const source = readFileSync(path.join(ROOT, 'components/ui/Badge.tsx'), 'utf8')
    expect(source).not.toMatch(/tonal\s+recipe/i)
  })

  it('no <Badge icon={null}> tells a status with beat or miss', () => {
    const files: string[] = []
    const walk = (dir: string) => {
      for (const entry of readdirSync(path.join(ROOT, dir), { withFileTypes: true })) {
        const rel = path.join(dir, entry.name)
        if (entry.isDirectory()) walk(rel)
        else if (rel.endsWith('.tsx') && rel !== path.join('components', 'ui', 'Badge.tsx')) files.push(rel)
      }
    }
    for (const dir of ['app', 'components', 'features']) walk(dir)

    const found: string[] = []
    for (const file of files) {
      const text = readFileSync(path.join(ROOT, file), 'utf8')
      if (!text.includes('<Badge')) continue
      const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
      let namesDirection = false
      const scanLiterals = (node: ts.Node): void => {
        if (ts.isStringLiteralLike(node) && (node.text === 'beat' || node.text === 'miss')) namesDirection = true
        ts.forEachChild(node, scanLiterals)
      }
      scanLiterals(sf)
      const visit = (node: ts.Node): void => {
        if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(sf) === 'Badge') {
          const attr = (name: string) =>
            node.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText(sf) === name)
          const icon = attr('icon')?.initializer
          const iconNull = !!icon && ts.isJsxExpression(icon) && icon.expression?.kind === ts.SyntaxKind.NullKeyword
          const variant = attr('variant')?.initializer
          const literal = variant && ts.isStringLiteral(variant) ? variant.text : undefined
          const direction = literal ? literal === 'beat' || literal === 'miss' : !!variant && namesDirection
          if (iconNull && direction) found.push(`${file}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1}`)
        }
        ts.forEachChild(node, visit)
      }
      visit(sf)
    }

    expect(found, 'use the success, error or warning variant').toEqual([])
  })
})

/** A colour token's value, or undefined for a utility that is no colour (`text-xs`): `brand-weak` → its hex,
    `brand-weak-dark` → its rgba, `brand` → its DEFAULT; an opacity suffix (`/60`) is read apart. */
const tokenValue = (name: string): string | undefined => {
  const bare = name.split('/')[0]
  if (bare === 'white') return '#FFFFFF'
  const [family, ...rest] = bare.split('-')
  const value = C[family]?.[rest.length ? rest.join('-') : 'DEFAULT']
  return typeof value === 'string' ? value : undefined
}
/** A fill class's colour over what lies under it (`brand-weak`, `brand-weak-dark`, `brand-weak/60`); an opacity
    replaces the token's own alpha, as Tailwind's does on an rgba token. */
const paint = (fill: string, under: Rgb): Rgb => {
  const [, pct] = fill.split('/')
  const value = tokenValue(fill)
  const rgba = value?.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/)
  if (!value || (!value.startsWith('#') && !rgba)) throw new Error(`no colour token ${fill}`)
  const [rgb, alpha]: [Rgb, number] = rgba
    ? [[Number(rgba[1]), Number(rgba[2]), Number(rgba[3])], rgba[4] === undefined ? 1 : Number(rgba[4])]
    : [hex(value), 1]
  return over(rgb, pct ? Number(pct) / 100 : alpha, under)
}
/** A theme's own colour class on one property (`bg`, `text`) under the given state variants (none, `active`). */
const own = (classes: string[], theme: 'light' | 'dark', property: 'bg' | 'text', state: string[] = []): string | undefined => {
  const wanted = (theme === 'dark' ? ['dark', ...state] : state).join(':')
  for (const parts of classes.map((c) => c.split(':'))) {
    const utility = parts[parts.length - 1]
    const value = utility.slice(property.length + 1)
    if (parts.slice(0, -1).join(':') === wanted && utility.startsWith(`${property}-`) && tokenValue(value)) return value
  }
  return undefined
}

describe('the new chip (D-032, E51)', () => {
  it('is the brand tint with its sage dot, and its label clears 4.5:1 in both themes on the card it sits on', () => {
    const chip = (variant: 'new' | 'brand') => render(<Badge variant={variant}>New</Badge>).container.firstElementChild as HTMLElement
    const fresh = chip('new')
    // The brand chip's own classes, both themes: a new filing is news, not a caution, so no warning tint.
    expect(fresh.className, 'the new chip takes the brand tint (Badge.tsx TINT)').toBe(chip('brand').className)
    // Its affordance is a pulse dot in the label's ink, which is sage here, and it stops under reduced motion.
    const dot = fresh.querySelector('span[aria-hidden="true"]')
    expect(dot?.className.split(/\s+/)).toEqual(expect.arrayContaining(['bg-current', 'animate-pulse', 'motion-reduce:animate-none']))

    // Its one use sits on an interactive Card (WhatChangedCard): the card's fill at rest, and its pressed fill over
    // the page when pressed (a dark press with no twin of its own keeps the resting fill, which outranks it).
    const card = (render(<Card interactive />).container.firstElementChild as HTMLElement).className.split(/\s+/)
    const classes = fresh.className.split(/\s+/)
    for (const theme of ['light', 'dark'] as const) {
      const rest = paint(own(card, theme, 'bg') ?? '', hex(theme === 'dark' ? C.background.dark : C.background.light))
      const press = own(card, theme, 'bg', ['active'])
      const pressed = press ? paint(press, hex(theme === 'dark' ? C.background.dark : C.background.light)) : rest
      const ink = own(classes, theme, 'text', [])
      const fill = own(classes, theme, 'bg', [])
      if (!ink || !fill) throw new Error(`no ${theme} ink or fill in ${fresh.className}`)
      for (const [state, ground] of [['at rest', rest], ['pressed', pressed]] as const) {
        const ratio = Math.round(contrast(paint(ink, ground), paint(fill, ground)) * 100) / 100
        expect(ratio, `the new chip's label in ${theme}, on the card ${state}`).toBeGreaterThanOrEqual(4.5)
      }
    }
  })
})
