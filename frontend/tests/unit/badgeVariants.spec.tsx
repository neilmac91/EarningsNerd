import { readdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { render } from '@testing-library/react'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { Badge } from '@/components/ui'

/**
 * chrome/F8, chrome/F9 (D-032): a status chip is its own Badge variant, never a data colour. `beat` and
 * `miss` are the earnings-surprise direction (gain/loss tokens, ▲/▼); the watchlist and dashboard rows
 * used them, glyph stripped, to say "Ready" and "Error", and the Badge header documented that as a
 * "tonal recipe". Badge now has `success` and `error`.
 *
 * Holds:
 *  - `success` and `error` exist, carry the status tokens and no automatic glyph, and their label clears
 *    4.5:1 on the chip's own ground in both themes (the ground is read from the variant's classes, so a
 *    move to a tint that drops the success ink under the floor fails here);
 *  - Badge.tsx no longer documents beat/miss/new as tonal recipes;
 *  - no `<Badge icon={null}>` in app/, components/ or features/ takes `beat` or `miss` (a literal, or a
 *    variable in a file that names either): a direction without its glyph is a status in data colours.
 *    STATUS_ON_DATA_COLOURS is shrink-only; the dashboard and watchlist PR remaps SummaryStatusBadge and
 *    deletes its line.
 */

const ROOT = path.resolve(__dirname, '../..')
const config = createRequire(import.meta.url)('../../tailwind.config.js') as {
  theme: { extend: { colors: Record<string, Record<string, string>> } }
}
const C = config.theme.extend.colors

const STATUS_ON_DATA_COLOURS: Record<string, string> = {
  'features/watchlist/components/SummaryStatusBadge.tsx':
    'Ready/Error/Needs attention on beat/miss: brand-dashboard-watchlist maps them to success/error/warning',
}

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

/** The label ink and the ground it sits on, from the chip's own classes, over the card it sits on. */
function chipPair(classes: string[], theme: 'light' | 'dark'): { ink: Rgb; ground: Rgb } {
  const own = classes.filter((c) => (theme === 'dark' ? c.startsWith('dark:') : !c.includes(':'))).map((c) => c.replace(/^dark:/, ''))
  const card = hex(theme === 'dark' ? C.panel.dark : C.panel.light)
  const bg = own.find((c) => c.startsWith('bg-'))?.slice(3)
  // The colour among the text utilities (BASE also sets the size, text-xs).
  const isColor = (name: string) => name === 'white' || typeof C[name.split('-')[0]]?.[name.split('-').slice(1).join('-')] === 'string'
  const text = own.filter((c) => c.startsWith('text-')).map((c) => c.slice(5)).find(isColor)
  if (!text) throw new Error(`no ${theme} label ink in ${classes.join(' ')}`)
  let ground = card
  if (bg) {
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
      const { ink, ground } = chipPair(classes, theme)
      expect(Math.round(contrast(ink, ground) * 100) / 100, `${variant} label in ${theme}`).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('the Badge header no longer offers beat/miss/new as tonal recipes', () => {
    const source = readFileSync(path.join(ROOT, 'components/ui/Badge.tsx'), 'utf8')
    expect(source).not.toMatch(/tonal\s+recipe/i)
  })

  it('no <Badge icon={null}> tells a status with beat or miss (shrink-only STATUS_ON_DATA_COLOURS)', () => {
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

    const fileOf = (hit: string) => hit.slice(0, hit.lastIndexOf(':'))
    const offending = new Set(found.map(fileOf))
    expect(found.filter((hit) => !(fileOf(hit) in STATUS_ON_DATA_COLOURS)), 'use the success, error or warning variant').toEqual([])
    expect(Object.keys(STATUS_ON_DATA_COLOURS).filter((file) => !offending.has(file)), 'fixed: delete its STATUS_ON_DATA_COLOURS line').toEqual([])
  })
})
