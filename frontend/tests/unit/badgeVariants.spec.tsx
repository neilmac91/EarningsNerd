import { readdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { render } from '@testing-library/react'
import type { Config } from 'tailwindcss'
import resolveConfig from 'tailwindcss/resolveConfig'
import ts from 'typescript'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { Badge, Card, type BadgeVariant } from '@/components/ui'
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'
import { DayDetailDialog } from '@/features/calendar/components/DayDetailDialog'
import { WeekView } from '@/features/calendar/components/WeekView'
import type { EarningsAlertsApi } from '@/features/calendar/hooks/useCalendar'

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
 *    (the dashboard's What changed card), at rest and pressed, the grounds read from Card's own classes;
 *  - `tentative` (E83) is neutral-status's ink on a dashed hairline with no fill in either theme, and the calendar's
 *    "Est." chip is that chip as Badge renders it, whose label clears 4.5:1 on its rows at rest and hovered in both
 *    themes; and no <Badge> sets a ground, an ink or a hairline in its className (the cases at the end).
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

/** Every .tsx under app/, components/ and features/ but Badge.tsx itself: the files whose <Badge> call sites the scans
    read. */
function badgeCallerFiles(): string[] {
  const files: string[] = []
  const walk = (dir: string) => {
    for (const entry of readdirSync(path.join(ROOT, dir), { withFileTypes: true })) {
      const rel = path.join(dir, entry.name)
      if (entry.isDirectory()) walk(rel)
      else if (rel.endsWith('.tsx') && rel !== path.join('components', 'ui', 'Badge.tsx')) files.push(rel)
    }
  }
  for (const dir of ['app', 'components', 'features']) walk(dir)
  return files
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
    const found: string[] = []
    for (const file of badgeCallerFiles()) {
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

/**
 * The tentative chip (E83). The calendar's "Est." chip took the neutral chip and handed it `bg-transparent
 * dark:bg-transparent` as a className, but cx only joins classes and the stylesheet emits `bg-white` after
 * `bg-transparent` (and `dark:bg-white/5` after `dark:bg-transparent`), so it painted as a white pill, and on a hovered
 * dark row its white/5 stacked on the row's: 4.27:1. A chip's ground, ink and hairline are its variant's to state.
 * Colours here are read through the resolved palette (`text-tertiary-light`, `white/5`), as Tailwind names them.
 */
const PALETTE = (
  createRequire(import.meta.url)('tailwindcss/lib/util/flattenColorPalette') as { default: (colors: unknown) => Record<string, string> }
).default(resolveConfig(config as unknown as Config).theme.colors)

/** A palette colour (`panel-light`, `white/5`) as rgb and alpha: an opacity suffix replaces the token's own alpha, as
    Tailwind's does on an rgba token. Undefined for a name the palette has no colour for. */
function paletteColour(value: string): { rgb: Rgb; alpha: number } | undefined {
  const [name, pct] = value.split('/')
  const token = PALETTE[name]
  const rgba = token?.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)$/)
  if (!token || (!/^#[0-9a-f]{3}([0-9a-f]{3})?$/i.test(token) && !rgba)) return undefined
  const six = token.length === 4 ? token.replace(/^#(.)(.)(.)$/, '#$1$1$2$2$3$3') : token
  const rgb: Rgb = rgba ? [Number(rgba[1]), Number(rgba[2]), Number(rgba[3])] : hex(six)
  return { rgb, alpha: pct ? Number(pct) / 100 : rgba?.[4] !== undefined ? Number(rgba[4]) : 1 }
}

/** The colour fill an element's classes give it in one theme, at rest or hovered (every layer under the pointer is
    hovered), as the cascade ranks them: in dark a dark: fill outranks a hover: one, which Tailwind emits earlier at
    one specificity, and a theme left unset falls back to the bare fill. A dialog's `backdrop:` fill paints behind it,
    outside its box, so it is not read. A fill under any other variant this reader does not model, or one it cannot
    read, fails. */
function fillOf(el: Element, theme: 'light' | 'dark', hovered: boolean, failures: string[]): string | undefined {
  const found = new Map<string, string>()
  for (const cls of (el.getAttribute('class') ?? '').split(/\s+/).filter(Boolean)) {
    const parts = cls.split(/:(?![^[]*\])/)
    const utility = parts.pop()!
    if (!/^!?bg-/.test(utility) || parts.includes('backdrop')) continue
    const variant = parts.sort().join(':')
    const value = utility.replace(/^!?bg-/, '')
    if (utility.startsWith('!') || !['', 'hover', 'dark', 'dark:hover'].includes(variant)) {
      failures.push(`<${el.tagName.toLowerCase()}> ${cls}: a fill under a variant this reader does not model`)
    } else if (value !== 'transparent' && !paletteColour(value)) {
      failures.push(`<${el.tagName.toLowerCase()}> ${cls}: a fill this reader cannot read`)
    } else found.set(variant, value)
  }
  const order = theme === 'dark' ? (hovered ? ['dark:hover', 'dark', 'hover', ''] : ['dark', '']) : hovered ? ['hover', ''] : ['']
  const key = order.find((k) => found.has(k))
  return key === undefined ? undefined : found.get(key)
}

/** What a chip's label sits on, in one theme, at rest or hovered: every fill from the chip up to the first opaque one,
    painted from that one up. Null, with a failure, when no opaque fill lies above it. */
function groundOf(chip: Element, theme: 'light' | 'dark', hovered: boolean, failures: string[]): Rgb | null {
  const fills: Array<{ rgb: Rgb; alpha: number }> = []
  for (let el: Element | null = chip; el; el = el.parentElement) {
    const value = fillOf(el, theme, hovered, failures)
    const fill = value === undefined || value === 'transparent' ? undefined : paletteColour(value)
    if (!fill) continue
    fills.push(fill)
    if (fill.alpha === 1) return fills.reduceRight<Rgb>((under, { rgb, alpha }) => over(rgb, alpha, under), [0, 0, 0])
  }
  failures.push(`no opaque fill above the chip in ${theme}`)
  return null
}

/** A class list's ink in one theme: its text- colour, under dark: in dark (the bare one where dark sets none). */
function inkOf(classes: string[], theme: 'light' | 'dark'): string | undefined {
  const pick = (variant: string) =>
    classes
      .map((c) => c.split(/:(?![^[]*\])/))
      .find((parts) => parts.slice(0, -1).join(':') === variant && /^text-/.test(parts[parts.length - 1]) && paletteColour(parts[parts.length - 1].slice(5)))
      ?.pop()
      ?.slice(5)
  return (theme === 'dark' ? pick('dark') : undefined) ?? pick('')
}

const classSet = (className: string) => [...new Set(className.split(/\s+/).filter(Boolean))].sort().join(' ')
const badgeClasses = (variant: BadgeVariant) =>
  (render(<Badge variant={variant}>Est.</Badge>).container.firstElementChild as HTMLElement).className.split(/\s+/)

const ALERTS: EarningsAlertsApi = {
  identityPending: false,
  isOn: () => false,
  isPending: () => false,
  toggle: () => {},
  blocked: null,
  clearBlocked: () => {},
}
const ESTIMATED: CalendarEvent = {
  ticker: 'TSM',
  company_name: 'Taiwan Semiconductor',
  event_date: '2026-07-30',
  event_time: 'bmo',
  status: 'estimated',
  confidence: 'high',
  eps_estimate: 2.3,
  eps_actual: null,
  anticipation_score: 88,
}

describe('the tentative chip (E83)', () => {
  // jsdom has no showModal(); the day dialog opens itself with it.
  const dialogProto = HTMLElement.prototype as HTMLElement & { showModal?: () => void }
  beforeAll(() => {
    dialogProto.showModal = function (this: HTMLElement) {
      this.setAttribute('open', '')
    }
  })
  afterAll(() => {
    delete dialogProto.showModal
  })

  it("is neutral-status's ink on a dashed hairline, with no fill in either theme", () => {
    const tentative = badgeClasses('tentative')
    expect(tentative).toEqual(expect.arrayContaining(['border', 'border-dashed']))
    expect([inkOf(tentative, 'light'), inkOf(tentative, 'dark')], "neutral-status's ink").toEqual([
      inkOf(badgeClasses('neutral-status'), 'light'),
      inkOf(badgeClasses('neutral-status'), 'dark'),
    ])
    // A fill under any variant, bare, dark: or a state's, would paint under the label.
    expect(tentative.filter((c) => /(^|:)!?bg-/.test(c) && !/(^|:)bg-transparent$/.test(c)), 'a fill on the tentative chip').toEqual([])
  })

  it('is the "Est." chip as the week sheet, the day list and the day dialog render it, its label at 4.5:1 or more on its row at rest and hovered, both themes', () => {
    const day = { iso: ESTIMATED.event_date, isToday: false, holidayName: null, events: [ESTIMATED] }
    // The sheet's compact row and the list's roomy row both render (CSS shows one by the view's width), then the dialog's.
    const views = [
      render(<WeekView days={[day]} alerts={ALERTS} signedIn={false} onShowMore={() => {}} />).container,
      render(<DayDetailDialog iso={day.iso} events={[ESTIMATED]} alerts={ALERTS} signedIn={false} onClose={() => {}} />).container,
    ]
    const chips = views.flatMap((view) => [...view.querySelectorAll('span')].filter((el) => el.textContent === 'Est.'))
    const where = ['the week sheet', 'the day list', 'the day dialog']
    expect(chips).toHaveLength(where.length)
    const tentative = classSet(badgeClasses('tentative').join(' '))
    const failures: string[] = []
    let measured = 0
    chips.forEach((chip, i) => {
      if (classSet(chip.className) !== tentative) failures.push(`${where[i]}: "${classSet(chip.className)}" is not Badge's tentative chip, "${tentative}"`)
      for (const theme of ['light', 'dark'] as const) {
        for (const hovered of [false, true]) {
          const ground = groundOf(chip, theme, hovered, failures)
          const ink = inkOf(chip.className.split(/\s+/), theme)
          const colour = ink === undefined ? undefined : paletteColour(ink)
          if (!ground || !colour) {
            if (!colour) failures.push(`${where[i]} (${theme}): no ink this case can read`)
            continue
          }
          const ratio = Math.round(contrast(over(colour.rgb, colour.alpha, ground), ground) * 100) / 100
          measured += 1
          if (ratio < 4.5) failures.push(`${where[i]} (${theme}${hovered ? ', a hovered row' : ''}): ${ratio.toFixed(2)}:1`)
        }
      }
    })
    expect(failures).toEqual([])
    // Three rows, two themes, at rest and hovered: a chip or a ground read short must not pass.
    expect(measured).toBe(12)
  })
})

/** The classes a className passes, read statically: a string, or the strings in a cx() or clsx() call, a condition,
    a logical pair, a template's chunks, an array or an object's keys; null where a class could come from elsewhere
    (a variable, another call). */
function staticClasses(node: ts.Node | undefined): string[] | null {
  if (node === undefined) return []
  const all = (nodes: readonly ts.Node[]): string[] | null => {
    const out: string[] = []
    for (const n of nodes) {
      const classes = staticClasses(n)
      if (classes === null) return null
      out.push(...classes)
    }
    return out
  }
  if (ts.isStringLiteralLike(node) || ts.isTemplateLiteralToken(node)) return node.text.split(/\s+/).filter(Boolean)
  if (ts.isJsxExpression(node) || ts.isParenthesizedExpression(node)) return staticClasses(node.expression)
  if (ts.isConditionalExpression(node)) return all([node.whenTrue, node.whenFalse])
  if (ts.isBinaryExpression(node)) {
    return node.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken ? staticClasses(node.right) : all([node.left, node.right])
  }
  if (ts.isTemplateExpression(node)) return all([node.head, ...node.templateSpans.flatMap((span) => [span.expression, span.literal])])
  if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && ['cx', 'clsx'].includes(node.expression.text)) return all(node.arguments)
  if (ts.isArrayLiteralExpression(node)) return all(node.elements)
  if (ts.isObjectLiteralExpression(node)) {
    const keys: string[] = []
    for (const p of node.properties) {
      if (!ts.isPropertyAssignment(p) || !(ts.isStringLiteral(p.name) || ts.isIdentifier(p.name))) return null
      keys.push(...p.name.text.split(/\s+/).filter(Boolean))
    }
    return keys
  }
  if (node.kind === ts.SyntaxKind.FalseKeyword || node.kind === ts.SyntaxKind.NullKeyword || (ts.isIdentifier(node) && node.text === 'undefined')) return []
  return null
}

/** Whether a class sets a chip's ground, ink or hairline, under any variant: any bg- or border utility, and a text- one
    that names a colour (a palette colour, or an arbitrary value that is no length). */
function paintsChip(cls: string): boolean {
  const utility = cls.split(/:(?![^[]*\])/).pop()!.replace(/^!/, '')
  if (/^(bg|border)(-|$)/.test(utility)) return true
  const value = utility.match(/^text-(.+)$/)?.[1]
  if (value === undefined) return false
  if (value.startsWith('[')) return !/^\[(length:|[\d.]+(px|rem|em|%)?\])/.test(value)
  return PALETTE[value.split('/')[0]] !== undefined
}

/** Every <Badge> in a source with a className or a spread this scan finds fault with, as `file:line: why`. */
function badgeClassFaults(file: string, source: string): string[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const faults: string[] = []
  const visit = (node: ts.Node): void => {
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(sf) === 'Badge') {
      const at = `${file}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1}`
      for (const prop of node.attributes.properties) {
        if (ts.isJsxSpreadAttribute(prop)) faults.push(`${at}: a spread, which may pass a className this scan cannot read`)
        else if (prop.name.getText(sf) === 'className') {
          const classes = staticClasses(prop.initializer)
          const painting = classes?.filter(paintsChip) ?? []
          if (classes === null) faults.push(`${at}: a className this scan cannot read`)
          else if (painting.length) faults.push(`${at}: ${painting.join(' ')}`)
        }
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return faults
}

describe("a Badge's ground, ink and hairline are its variant's (E83)", () => {
  it('no <Badge> in app/, components/ or features/ sets a ground, an ink or a hairline in its className', () => {
    const found = badgeCallerFiles().flatMap((file) => {
      const source = readFileSync(path.join(ROOT, file), 'utf8')
      return source.includes('<Badge') ? badgeClassFaults(file, source) : []
    })
    expect(found, "give the chip a variant of its own (components/ui/Badge.tsx): a class on top of a variant's wins or loses by stylesheet order").toEqual([])
  })

  it('reads a className through cx() and conditions, and tells a ground, an ink or a hairline from a layout class', () => {
    const probe = [
      '<Badge variant="pro" className="shrink-0 text-center !whitespace-normal text-xs" />',
      '<Badge className={cx("ml-1", on && "bg-white", on ? "text-sm" : "dark:text-brand-strong-dark")}>x</Badge>',
      '<Badge className={`border-dashed ${on ? "hover:!text-[#fff]" : ""}`} />',
      '<Badge className={chip} />',
      '<Badge {...props} />',
      '<Badge className={clsx({ "text-text-tertiary-light": on, "mt-1": true })} />',
    ].join('\n')
    expect(badgeClassFaults('probe.tsx', probe)).toEqual([
      'probe.tsx:2: bg-white dark:text-brand-strong-dark',
      'probe.tsx:3: border-dashed hover:!text-[#fff]',
      'probe.tsx:4: a className this scan cannot read',
      'probe.tsx:5: a spread, which may pass a className this scan cannot read',
      'probe.tsx:6: text-text-tertiary-light',
    ])
  })
})
