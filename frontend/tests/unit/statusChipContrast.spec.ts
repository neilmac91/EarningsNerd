import { createElement, type FunctionComponent, type ReactElement } from 'react'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { render } from '@testing-library/react'
import type { Config } from 'tailwindcss'
import resolveConfig from 'tailwindcss/resolveConfig'
import ts from 'typescript'
import { describe, expect, it, vi } from 'vitest'
import { Badge, Card, type BadgeProps, type BadgeVariant } from '@/components/ui'
import InviteStatusBadge from '@/features/admin/components/InviteStatusBadge'
import FeedbackStatusBadge from '@/features/admin/components/FeedbackStatusBadge'
import FeedbackTypeBadge from '@/features/admin/components/FeedbackTypeBadge'
import type { FeedbackStatus, FeedbackType, InviteStatus } from '@/features/admin/api/admin-api'
import SummaryStatusBadge, { summaryStatusBadge } from '@/features/watchlist/components/SummaryStatusBadge'

/**
 * Badge, marked: every chip Badge renders in this file carries `data-badge`, the variant it was given, and nothing
 * else changes, so the cases that hold the admin badges and the summary status chip to Badge's status set can tell a
 * chip Badge rendered from a copy of its classes by hand.
 */
vi.mock('@/components/ui/Badge', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/components/ui/Badge')>()
  const Marked = (props: BadgeProps) => createElement(actual.Badge, { ...props, 'data-badge': props.variant ?? 'neutral' } as BadgeProps)
  return { ...actual, Badge: Marked }
})

/**
 * The status chips' labels clear 4.5:1 on what is behind them, in both themes (CLAUDE.md rule 11): the admin
 * lists' (audit ADM-16a, ADM-16b) and the summary status chip's on the watchlist and dashboard rows, below. What is
 * behind the admin chips is read from the code, never written here: each table's
 * <tbody> ground (app/admin/invites/page.tsx, app/admin/feedback/page.tsx) and its row's own tint
 * (InviteRow's and FeedbackRow's <tr>), from their className strings in the TypeScript AST, at rest and
 * hovered, and every layer between a chip and that <tr> (its cell, and any wrapper inside it), walked up
 * from each chip's element in the row's source. Those layers must paint nothing: a bg- utility on one,
 * under any variant, fails, because a fill there is a design change that comes with a change to this
 * spec. A <tr> or <tbody> it cannot find, a chip it cannot find or one with no <tr> above it, a component
 * between a chip and its row, a className that is not a plain string (a layer may carry none) or a layer
 * with props spread into it, a tbody with no ground it can resolve or a translucent one, and a ground
 * under a variant it does not model all fail; nothing falls back to a literal. The status chips are Badge's
 * status set (components/ui/Badge.tsx), read from Badge itself: the members of its BadgeStatusVariant type,
 * from its source, each rendered through Badge and measured once per theme on every one of those grounds,
 * from its classes resolved through tailwind.config.js, so a token, variant or row change is read as it
 * ships: the label ink over the chip's ground, composited over the row. A member that is not a string
 * literal, or no such type, fails. Both status badges are then held to that set, status by status: each
 * renders a chip Badge rendered with one of the set's variants and no class of its own, so a chip that
 * hand-rolls its classes (a copy of Badge's included), adds one to Badge's or takes a tint fails, and
 * nothing inside the chip paints: a class on anything inside it but the icon's size (`h-3.5 w-3.5`), an
 * inline style on the chip or inside it, or an SVG paint attribute that is not currentColor or none fails,
 * so a label wrapped in a tint of its own is refused and the ink measured is the ink that ships; and
 * FeedbackTypeBadge, the chip beside FeedbackRow's status chip, is measured as it renders on that row's
 * grounds, and held to Badge's metrics: every class of Badge's BASE, read from its source, on the chip, and
 * beside them only a ground and an ink of its own (a bg-, text- or border- colour, or the bare border
 * hairline), so a weight, a gap or a size of its own fails. A text- colour this spec cannot resolve fails, and
 * so does a bg- or text- arbitrary value (`bg-[...]`) that looks like a colour and is not a hex or rgb() it
 * can read, or a chip's text- or bg- colour under the important modifier, which this spec does not rank
 * against the plain ones. A chip's text- or bg- colour under any variant but its theme's own (bare in
 * light, dark: in dark), such as hover:, focus-visible: or dark:hover:, fails too: the chip is measured as
 * it rests, on its row at rest and hovered, and no state or breakpoint of its own is modelled. An opacity
 * below 100 under any variant (`opacity-`, `text-opacity-` or `bg-opacity-`, an arbitrary value included),
 * or an arbitrary one it cannot read, fails on the chip, on a layer between it and its row, and on the <tr>
 * and the <tbody>: every colour here is measured at full opacity. A plain unknown token name is skipped,
 * since Tailwind emits no CSS for it either. Out of reach: a stylesheet rule, and an inline style on what
 * is measured (Badge's own chips set none; on an admin chip, or inside it, one fails, as above); an
 * arbitrary property (`[background-color:...]`, `[opacity:...]`); anything above the <tbody> (above the <Card>
 * for the summary rows), so an opacity on the <table> or a page wrapper, which fades the chip and its ground
 * together, is not measured; and a utility that changes what is painted without setting a colour or an opacity (a
 * gradient, a blend mode, a filter), except that any bg- utility on a layer fails, as above.
 *
 * The summary status chip (SummaryStatusBadge) is read and held the same way on the two rows it renders on: the
 * Watchlist insights page's company cards (app/dashboard/watchlist/page.tsx) and the dashboard's "Your companies"
 * rows (features/dashboard/components/YourCompanies.tsx), each file rendering it once. Each row's grounds are read
 * from its source: the walk up from the chip to the first <Card>, whose fill is the opaque ground, read as it
 * renders (Card itself, given the props written on it, each a plain string or a bare boolean; any other prop, a
 * style or a spread among them, fails). The row is the element on that walk that carries the list's `key`: the
 * watchlist's <Card>, one per company, which is then its own ground at rest and hovered (a hover fill replaces its
 * own, so a translucent one fails, since the page would show through), and the dashboard's row <div> inside its one
 * <Card>, whose tint at rest and hovered is read over the card's ground as a <tr>'s is over its <tbody>. Every other
 * element on the walk is a layer that must paint nothing, as above; no <Card>, no keyed row, or a chip count other
 * than one fails. The status kinds the chip knows are read from SummaryStatusKind in its source, a member that is
 * not a string literal failing: every chip summaryStatusBadge() returns for each kind and for a prefix it does not
 * know, with and without needs_regeneration, is rendered through Badge and measured on both rows, at rest and
 * hovered, in both themes; and SummaryStatusBadge, for each of those, must render Badge's chip for the variant
 * summaryStatusBadge() returns, a member of the status set, held as the admin badges are (no class of its own and
 * nothing on or inside it that paints), so a tint, the quiet chip or a hand-rolled chip fails.
 */
const require = createRequire(import.meta.url)
const flattenColorPalette = (require('tailwindcss/lib/util/flattenColorPalette') as { default: (c: unknown) => Record<string, string> }).default
const ROOT = path.resolve(__dirname, '../..')
const THEME = resolveConfig(require(path.join(ROOT, 'tailwind.config.js')) as Config).theme
const COLORS = flattenColorPalette(THEME.colors)
/** The scales the opacity utilities read, by prefix (`opacity-`, `text-opacity-`, `bg-opacity-`), as Tailwind resolves them. */
const OPACITY: Record<string, Record<string, string>> = { '': THEME.opacity, 'text-': THEME.textOpacity, 'bg-': THEME.backgroundOpacity }

type Rgba = [number, number, number, number]
type Theme = 'light' | 'dark'
/** What a chip sits on, per theme: a label and the opaque colour behind the chip. */
type Grounds = Record<Theme, Array<[string, Rgba]>>
const THEMES: Theme[] = ['light', 'dark']

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

/** An arbitrary value that is not a length, a url or a size: a colour this spec must read or refuse. */
const looksLikeColour = (value: string) => value.startsWith('[') && !/^\[(length:|url\(|position:|[\d.]+(px|rem|em|%)?\])/.test(value)
/** A class's variants and its utility last, split on the colons outside an arbitrary value (`bg-[color:var(--x)]` stays whole). */
const classParts = (cls: string) => cls.split(/:(?![^[]*\])/)

/**
 * An opacity utility's value as a fraction (`opacity-60`, `text-opacity-50`, `bg-opacity-[.5]`, `opacity-[35%]`):
 * NaN for an arbitrary value it cannot read, undefined for a utility that sets no opacity or a plain key
 * Tailwind emits no CSS for.
 */
function opacity(utility: string): number | undefined {
  const m = utility.match(/^!?((?:text-|bg-)?)opacity-(.+)$/)
  if (!m) return undefined
  const [, prefix, value] = m
  if (value.startsWith('[') && value.endsWith(']')) {
    const inner = value.slice(1, -1)
    return /^[\d.]+%$/.test(inner) ? parseFloat(inner) / 100 : /^[\d.]+$/.test(inner) ? Number(inner) : NaN
  }
  return Object.hasOwn(OPACITY[prefix], value) ? Number(OPACITY[prefix][value]) : undefined
}

/** Why a class, under any variant, fades what this spec measures at full opacity, or null when it does not. */
function fades(cls: string): string | null {
  const value = opacity(classParts(cls).pop()!)
  if (value === undefined || value >= 1) return null
  return Number.isNaN(value) ? `${cls} looks like an opacity this spec cannot resolve` : `${cls} sets an opacity below 100, which this spec does not model`
}

/** A JSX element's className: its text when it is a plain string (or a string in braces), undefined when it has none, null otherwise. */
function classNameOf(element: ts.JsxOpeningLikeElement, sf: ts.SourceFile): string | null | undefined {
  const attr = element.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText(sf) === 'className')
  if (!attr) return undefined
  const value = attr.initializer && ts.isJsxExpression(attr.initializer) ? attr.initializer.expression : attr.initializer
  return value && (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value)) ? value.text : null
}

/** The className of the one <tag> in a .tsx source, or null with a failure that names the file. */
function oneClassName(source: string, file: string, tag: string, failures: string[]): string | null {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  // Each <tag>'s className, null when it has none this spec can read.
  const found: Array<string | null> = []
  const visit = (node: ts.Node): void => {
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(sf) === tag) {
      found.push(classNameOf(node, sf) ?? null)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  if (found.length === 1 && found[0] !== null) return found[0]
  failures.push(
    found.length === 1
      ? `${file}: the <${tag}> has no className string this spec can read`
      : `${file}: ${found.length} <${tag}> elements, where this spec reads exactly one`,
  )
  return null
}

/**
 * The layers between each <chip> in a row's source and the row's <tr>: every element the walk up from the
 * chip meets, which must be an HTML element with no props spread into it, whose className is a plain
 * string or absent and sets no bg- utility and no opacity below 100 under any variant, so that the grounds
 * measured here are what the chip sits on. Returns the layers it read; a chip it cannot find, a walk that
 * meets a component or no <tr>, a layer it cannot read and a background or an opacity on one each fail,
 * naming the file and line.
 */
function chipLayers(source: string, file: string, chips: string[], failures: string[]): string[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const at = (node: ts.Node) => `${file}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1}`
  const isRow = (node: ts.Node) => ts.isJsxElement(node) && node.openingElement.tagName.getText(sf) === 'tr'
  const layers: string[] = []
  for (const chip of chips) {
    // Each <chip>: the self-closing element, or the element an opening tag starts.
    const found: ts.Node[] = []
    const visit = (node: ts.Node): void => {
      if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(sf) === chip) {
        found.push(ts.isJsxOpeningElement(node) ? node.parent : node)
      }
      ts.forEachChild(node, visit)
    }
    visit(sf)
    if (found.length === 0) failures.push(`${file}: no <${chip}>, so this spec cannot read what is behind it`)
    for (const element of found) {
      // Braces, conditionals and fragments render no box of their own; every element up to the <tr> is a layer,
      // a self-closing one that takes the chip in a prop (`<Cell render={<Chip />} />`) included.
      let up: ts.Node | undefined = element.parent
      for (; up && !isRow(up); up = up.parent) {
        const opening = ts.isJsxElement(up) ? up.openingElement : ts.isJsxSelfClosingElement(up) ? up : undefined
        if (!opening) continue
        const where = `${at(up)} <${opening.tagName.getText(sf)}>, between <${chip}> and its <tr>`
        if (!ts.isIdentifier(opening.tagName) || !/^[a-z]/.test(opening.tagName.text)) {
          failures.push(`${where}: a component, and this spec does not read what it renders`)
          continue
        }
        const className = classNameOf(opening, sf)
        if (className === null || opening.attributes.properties.some(ts.isJsxSpreadAttribute)) {
          failures.push(`${where}: no className string this spec can read`)
          continue
        }
        layers.push(`${at(up)} <${opening.tagName.text}>`)
        paintsNothing(className ?? '', where, failures)
      }
      if (!up) failures.push(`${at(element)} <${chip}>: no <tr> above it, so this spec cannot read what is behind it`)
    }
  }
  return layers
}

/** A layer under a chip paints nothing: a bg- utility or an opacity below 100, under any variant, each fails, naming where. */
function paintsNothing(className: string, where: string, failures: string[]): void {
  for (const cls of className.split(/\s+/).filter(Boolean)) {
    const faded = fades(cls)
    if (/^!?bg-/.test(classParts(cls).pop()!)) failures.push(`${where}: ${cls} sets a background this spec does not model`)
    else if (faded) failures.push(`${where}: ${faded}`)
  }
}

/**
 * A class list's bg- colours by variant ('', 'hover', 'dark', 'dark:hover'), an important one (`!bg-`) keyed
 * under its variant with a leading `!`; one it cannot read, a variant outside `modelled`, or an opacity below
 * 100 under any variant, fails.
 */
function backgrounds(className: string, where: string, modelled: string[], failures: string[]): Map<string, Rgba> {
  const found = new Map<string, Rgba>()
  for (const cls of className.split(/\s+/).filter(Boolean)) {
    const faded = fades(cls)
    if (faded) {
      failures.push(`${where}: ${faded}`)
      continue
    }
    const parts = classParts(cls)
    const utility = parts.pop()!
    const m = utility.match(/^!?bg-(.+)$/)
    if (!m) continue
    const value = colour(m[1])
    if (!value) {
      if (looksLikeColour(m[1])) failures.push(`${where}: ${cls} looks like a colour this spec cannot resolve`)
      continue
    }
    const variant = parts.sort().join(':')
    if (modelled.includes(variant)) found.set(`${utility.startsWith('!') ? '!' : ''}${variant}`, value)
    else failures.push(`${where}: ${cls} is a ground under a variant this spec does not model`)
  }
  return found
}

/** The ground that wins among the variants in `order`, highest first: an important one ahead of every plain one, as the cascade ranks them. */
function winner(found: Map<string, Rgba>, order: string[]): Rgba | undefined {
  const key = [...order.map((variant) => `!${variant}`), ...order].find((k) => found.has(k))
  return key === undefined ? undefined : found.get(key)
}

/** One table's grounds: its tbody's own, under its row's tint at rest and hovered, in each theme. */
function tableGrounds(table: string, row: string, body: string, where: { row: string; body: string }, failures: string[]): Grounds {
  const under = backgrounds(body, where.body, ['', 'dark'], failures)
  const tint = backgrounds(row, where.row, ['', 'hover', 'dark', 'dark:hover'], failures)
  const grounds: Grounds = { light: [], dark: [] }
  for (const theme of THEMES) {
    // A dark: ground left unset falls back to the light one, as the cascade does. In dark, a row's dark:bg-
    // also outranks its hover:bg-: Tailwind emits the dark variant later, at the same specificity. An
    // important ground (`!bg-`) outranks every plain one that applies, whatever its variant.
    const ground = winner(under, theme === 'dark' ? ['dark', ''] : [''])
    const rest = winner(tint, theme === 'dark' ? ['dark', ''] : [''])
    const hover = winner(tint, theme === 'dark' ? ['dark:hover', 'dark', 'hover', ''] : ['hover', ''])
    if (!ground) {
      failures.push(`${where.body} (${theme}): no bg- ground this spec can resolve`)
      continue
    }
    if (ground[3] < 1) {
      failures.push(`${where.body} (${theme}): a translucent ground, and this spec does not read what shows through it`)
      continue
    }
    grounds[theme].push([`${table} row`, rest ? over(rest, ground) : ground], [`${table} hovered row`, hover ? over(hover, ground) : ground])
  }
  return grounds
}

/** The tables the chips sit in: each row component and the chips it renders, and the page whose <tbody> renders its rows. */
const TABLES = {
  invites: { row: 'features/admin/components/InviteRow.tsx', chips: ['InviteStatusBadge'], body: 'app/admin/invites/page.tsx' },
  feedback: { row: 'features/admin/components/FeedbackRow.tsx', chips: ['FeedbackTypeBadge', 'FeedbackStatusBadge'], body: 'app/admin/feedback/page.tsx' },
}
/** Why a table's grounds could not be read; every measuring case below fails on any of them. */
const GROUND_FAILURES: string[] = []
/** The layers read between each chip and its row's <tr>, as `file:line <tag>`. */
const LAYERS: string[] = []
const GROUNDS = Object.fromEntries(
  Object.entries(TABLES).map(([table, files]) => {
    const read = (file: string, tag: string) => oneClassName(readFileSync(path.join(ROOT, file), 'utf8'), file, tag, GROUND_FAILURES)
    const [row, body] = [read(files.row, 'tr'), read(files.body, 'tbody')]
    // These grounds are what a chip sits on only while every layer between it and the <tr> paints nothing.
    LAYERS.push(...chipLayers(readFileSync(path.join(ROOT, files.row), 'utf8'), files.row, files.chips, GROUND_FAILURES))
    const where = { row: `${files.row} <tr>`, body: `${files.body} <tbody>` }
    return [table, row === null || body === null ? { light: [], dark: [] } : tableGrounds(table, row, body, where, GROUND_FAILURES)]
  }),
) as Record<keyof typeof TABLES, Grounds>
const EVERY_GROUND: Grounds = {
  light: Object.values(GROUNDS).flatMap((g) => g.light),
  dark: Object.values(GROUNDS).flatMap((g) => g.dark),
}

/**
 * The chip's text and background colours in one theme, from its class list (bare in light, dark: in dark),
 * the colour-like classes it could not read, and why it refuses others there: a text- or bg- colour under any
 * other variant (hover:, focus-visible:, dark:hover:), and an opacity below 100 under any variant. A dark:
 * class applies in dark alone and any other in both themes, so a refusal names it in each theme it applies in.
 */
function chipColours(className: string, theme: Theme) {
  const found: { text?: Rgba; bg?: Rgba; unread: string[]; refused: string[] } = { unread: [], refused: [] }
  for (const cls of className.split(/\s+/).filter(Boolean)) {
    const parts = classParts(cls)
    const utility = parts.pop()!
    const dark = parts.includes('dark')
    if (dark && theme === 'light') continue
    const faded = fades(cls)
    if (faded) found.refused.push(faded)
    const m = utility.match(/^(!?)(text|bg)-(.+)$/)
    const value = m && colour(m[3])
    if (!m || (!value && !looksLikeColour(m[3]))) continue
    if (parts.length > (dark ? 1 : 0)) found.refused.push(`${cls} is a chip colour under a variant this spec does not model`)
    // A bare colour in dark is the light one, read there only where dark sets none.
    else if (dark !== (theme === 'dark')) continue
    // A colour under the important modifier is refused like one it cannot read: in the browser it outranks
    // the plain ones, and this spec does not rank it.
    else if (value && !m[1]) found[m[2] as 'text' | 'bg'] = value
    else found.unread.push(cls)
  }
  return found
}

/** What an element inside a chip may carry: the icon's size, as the admin badges fill Badge's icon slot, which paints nothing. */
const ICON_SIZE = new Set(['h-3.5', 'w-3.5'])
/** The SVG presentation attributes that paint, and the values that leave the chip's ink in charge. */
const PAINT_ATTRIBUTES = ['fill', 'stroke', 'color', 'opacity', 'fill-opacity', 'stroke-opacity']
const INHERITS_INK = new Set(['currentColor', 'none'])

type Chip = { className: string; badge: string | null; inner: string[] }

/**
 * The first element a component renders, read and unmounted: its className, the variant Badge marked it with when
 * Badge rendered it, and whatever on it or inside it could paint over what its classes say: its own inline style, and
 * inside it any class but the icon's size, any inline style, and an SVG paint attribute that does not inherit the ink.
 */
function chipOf(element: ReactElement): Chip {
  const { container, unmount } = render(element)
  const chip = container.firstElementChild as HTMLElement
  const inner: string[] = []
  if (chip.hasAttribute('style')) inner.push(`its own style "${chip.getAttribute('style')}"`)
  for (const node of chip.querySelectorAll('*')) {
    const tag = `<${node.tagName.toLowerCase()}>`
    for (const cls of (node.getAttribute('class') ?? '').split(/\s+/).filter(Boolean)) {
      if (!ICON_SIZE.has(cls)) inner.push(`${tag} class ${cls}`)
    }
    if (node.hasAttribute('style')) inner.push(`${tag} style "${node.getAttribute('style')}"`)
    for (const attribute of PAINT_ATTRIBUTES) {
      const value = node.getAttribute(attribute)
      if (value !== null && !INHERITS_INK.has(value)) inner.push(`${tag} ${attribute}="${value}"`)
    }
  }
  const read = { className: chip.className, badge: chip.getAttribute('data-badge'), inner }
  unmount()
  return read
}

/**
 * The members of a type alias in a source, a union of string literals (`type T = 'a' | 'b'`), each a string literal. A
 * member it cannot read, or no such type, is a failure that every case reading the members reports; `what` names them.
 */
function literalMembers(source: string, file: string, name: string, what: string, failures: string[]): string[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const alias = sf.statements.find((s): s is ts.TypeAliasDeclaration => ts.isTypeAliasDeclaration(s) && s.name.text === name)
  if (!alias) {
    failures.push(`${file}: no ${name} type, so this spec cannot read ${what}`)
    return []
  }
  return (ts.isUnionTypeNode(alias.type) ? alias.type.types : [alias.type]).flatMap((member) => {
    if (ts.isLiteralTypeNode(member) && ts.isStringLiteral(member.literal)) return [member.literal.text]
    failures.push(`${file}: ${member.getText(sf)} in ${name} is not a string literal this spec can read`)
    return []
  })
}

/** Badge's status set, from its source: the members of its BadgeStatusVariant type. */
const statusSet = (source: string, file: string, failures: string[]) =>
  literalMembers(source, file, 'BadgeStatusVariant', "Badge's status set", failures)

const BADGE = 'components/ui/Badge.tsx'
/** Why Badge's status set could not be read; every case that reads it fails on any of them. */
const SET_FAILURES: string[] = []
const STATUS_VARIANTS = statusSet(readFileSync(path.join(ROOT, BADGE), 'utf8'), BADGE, SET_FAILURES)
/** A variant's classes, as Badge renders them. */
const badgeClasses = (variant: string) => chipOf(createElement(Badge, { variant: variant as BadgeVariant }, 'x')).className

/**
 * Badge's metrics, from its source: the classes of its BASE, which every chip it renders carries (the layout, padding,
 * type size and weight, gap and nowrap). A BASE that is not a string literal, or no BASE, is a failure.
 */
function badgeMetrics(source: string, file: string, failures: string[]): string[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const base = sf.statements
    .filter(ts.isVariableStatement)
    .flatMap((s) => [...s.declarationList.declarations])
    .find((d) => ts.isIdentifier(d.name) && d.name.text === 'BASE')
  if (!base) {
    failures.push(`${file}: no BASE, so this spec cannot read Badge's metrics`)
    return []
  }
  if (base.initializer && ts.isStringLiteralLike(base.initializer)) return base.initializer.text.split(/\s+/).filter(Boolean)
  failures.push(`${file}: BASE is not a string literal this spec can read`)
  return []
}

/** Why Badge's metrics could not be read; the case that holds the type chip to them fails on any of them. */
const METRIC_FAILURES: string[] = []
const METRICS = badgeMetrics(readFileSync(path.join(ROOT, BADGE), 'utf8'), BADGE, METRIC_FAILURES)

/** A ground or an ink, in either theme: a bg-, text- or border- colour this spec resolves, or the bare border hairline. */
function paints(cls: string): boolean {
  const utility = cls.startsWith('dark:') ? cls.slice('dark:'.length) : cls
  const m = utility.match(/^(bg|text|border)-(.+)$/)
  return utility === 'border' || (m !== null && colour(m[2]) !== null)
}

/**
 * Why a chip's classes are not Badge's metrics with only a ground and an ink of its own beside them, or null when they
 * are: a class of Badge's metrics it lacks, and a class of its own that is no ground or ink (a weight, a gap, a size).
 */
function offTheMetrics(name: string, className: string, metrics: string[]): string | null {
  const classes = className.split(/\s+/).filter(Boolean)
  const lacks = metrics.filter((cls) => !classes.includes(cls))
  const own = classes.filter((cls) => !metrics.includes(cls) && !paints(cls))
  const why = [
    ...(lacks.length ? [`lacks Badge's ${lacks.join(', ')}`] : []),
    ...(own.length ? [`sets ${own.join(', ')}, which is no ground or ink`] : []),
  ]
  return why.length ? `${name}: ${why.join(' and ')}` : null
}

/** A chip's label ratio on each ground, in both themes, with any class the reader could not read. */
function measure(name: string, className: string, grounds: Grounds, failures: string[]): number {
  let measured = 0
  for (const theme of THEMES) {
    const { text: ink, bg, unread, refused } = chipColours(className, theme)
    for (const cls of unread) failures.push(`${name} (${theme}): ${cls} looks like a colour this spec cannot resolve`)
    for (const why of refused) failures.push(`${name} (${theme}): ${why}`)
    // A dark: background left unset falls back to the light one, as the cascade does.
    const chip = bg ?? (theme === 'dark' ? chipColours(className, 'light').bg : undefined) ?? ([0, 0, 0, 0] as Rgba)
    if (!ink) {
      failures.push(`${name} (${theme}): no ${theme === 'dark' ? 'dark:' : ''}text- colour this spec can resolve`)
      continue
    }
    for (const [label, ground] of grounds[theme]) {
      const behind = over(chip, ground)
      const r = ratio(over(ink, behind), behind)
      measured += 1
      if (r < 4.5) failures.push(`${name} (${theme}, ${label}): ${r.toFixed(2)}:1`)
    }
  }
  return measured
}

const CHIPS: Array<[string, FunctionComponent<{ status: never }>, string[]]> = [
  ['InviteStatusBadge', InviteStatusBadge as FunctionComponent<{ status: never }>, ['pending', 'used', 'expired', 'revoked'] satisfies InviteStatus[]],
  ['FeedbackStatusBadge', FeedbackStatusBadge as FunctionComponent<{ status: never }>, ['new', 'triaged', 'resolved'] satisfies FeedbackStatus[]],
]

const classSet = (className: string) => [...new Set(className.split(/\s+/).filter(Boolean))].sort().join(' ')

/**
 * Why a chip is not Badge's chip for one member of its status set, as Badge renders it, or null when it is: one Badge
 * did not render (its classes hand-rolled, a copy of Badge's included), Badge's chip for a variant outside the set,
 * Badge's chip with a class of the caller's added, or Badge's chip with something on it or inside it that may paint
 * over what the measurement reads (an inline style, a class inside it but the icon's size, an SVG fill of its own).
 */
function offTheSet(name: string, { className, badge, inner }: Chip): string | null {
  const chip = classSet(className)
  if (badge === null) return `${name}: "${chip}" is no chip Badge rendered, so its classes are hand-rolled`
  if (!STATUS_VARIANTS.includes(badge)) return `${name}: Badge's ${badge}, which is not in its status set`
  const own = classSet(badgeClasses(badge))
  if (chip !== own) return `${name}: "${chip}" is not Badge's ${badge} as it renders, "${own}"`
  return inner.length === 0 ? null : `${name}: Badge's ${badge} with ${inner.join(', ')}, which may paint over what is measured`
}

/** The self-checks' own <tr> and <tbody>: their grounds come from class strings written in each case, not from the code. */
const PROBE = { row: 'probe <tr>', body: 'probe <tbody>' }

/** The rows the summary status chip renders on, each file rendering it once (the header above). */
const SUMMARY_ROWS = {
  watchlist: 'app/dashboard/watchlist/page.tsx',
  dashboard: 'features/dashboard/components/YourCompanies.tsx',
}

/**
 * What is under a summary chip: the props its <Card> is given, its row's className (null where the card is its own
 * row), where each sits, and the layers between the chip and the card, as `file:line <tag>`.
 */
type SummaryStack = { card: Record<string, string | boolean>; row: string | null; where: { card: string; row: string }; layers: string[] }

/**
 * The props written on a <Card>, as Card takes them: each a plain string or a bare boolean, `key` aside. Any other prop
 * (an expression, a style, a handler) or a spread fails, since this spec cannot tell what Card would paint with it.
 */
function cardProps(opening: ts.JsxOpeningLikeElement, sf: ts.SourceFile, where: string, failures: string[]): Record<string, string | boolean> | null {
  const props: Record<string, string | boolean> = {}
  let read = true
  for (const prop of opening.attributes.properties) {
    const name = ts.isJsxAttribute(prop) ? prop.name.getText(sf) : null
    if (name === 'key') continue
    const init = ts.isJsxAttribute(prop) ? prop.initializer : undefined
    const value = init && ts.isJsxExpression(init) ? init.expression : init
    if (name !== null && init === undefined) props[name] = true
    else if (name !== null && value && (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value))) props[name] = value.text
    else if (name !== null && value && (value.kind === ts.SyntaxKind.TrueKeyword || value.kind === ts.SyntaxKind.FalseKeyword)) {
      props[name] = value.kind === ts.SyntaxKind.TrueKeyword
    } else {
      failures.push(`${where}: ${prop.getText(sf)} is a prop this spec cannot read, so it cannot tell what the card paints`)
      read = false
    }
  }
  return read ? props : null
}

/**
 * What is under the one <chip> in a row's source: the walk up from it to the first <Card>, the card whose fill is the
 * opaque ground. The row is the element on the way that carries the list's `key`; when that is the <Card> itself (one
 * card per item), the card is its own row. Every other element on the way is a layer, held as chipLayers holds one: an
 * HTML element with no props spread into it, whose className is a plain string or absent and paints nothing. A chip
 * count other than one, a component on the way, a layer or a card prop it cannot read, no keyed row and no <Card> each
 * fail, naming the file and line.
 */
function summaryStack(source: string, file: string, chip: string, failures: string[]): SummaryStack | null {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const at = (node: ts.Node) => `${file}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1}`
  const found: ts.Node[] = []
  const visit = (node: ts.Node): void => {
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(sf) === chip) {
      found.push(ts.isJsxOpeningElement(node) ? node.parent : node)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  if (found.length !== 1) {
    failures.push(`${file}: ${found.length} <${chip}> elements, where this spec reads exactly one`)
    return null
  }
  const layers: string[] = []
  let row: { className: string; where: string } | null = null
  // Braces, conditionals, fragments and a .map callback render no box of their own; every element up to the <Card> is
  // the row or a layer, a self-closing one that takes the chip in a prop included.
  for (let up = found[0].parent; up; up = up.parent) {
    const opening = ts.isJsxElement(up) ? up.openingElement : ts.isJsxSelfClosingElement(up) ? up : undefined
    if (!opening) continue
    const tag = opening.tagName.getText(sf)
    const where = `${at(up)} <${tag}>`
    const keyed = opening.attributes.properties.some((p) => ts.isJsxAttribute(p) && p.name.getText(sf) === 'key')
    if (tag === 'Card') {
      if (!row && !keyed) {
        failures.push(`${at(found[0])} <${chip}>: no element with a key between it and its <Card>, so this spec cannot tell which one is the row`)
        return null
      }
      const card = cardProps(opening, sf, where, failures)
      return card && { card, row: row?.className ?? null, where: { card: where, row: row?.where ?? where }, layers }
    }
    if (!ts.isIdentifier(opening.tagName) || !/^[a-z]/.test(opening.tagName.text)) {
      failures.push(`${where}, between <${chip}> and its <Card>: a component, and this spec does not read what it renders`)
      continue
    }
    const className = classNameOf(opening, sf)
    if (className === null || opening.attributes.properties.some(ts.isJsxSpreadAttribute)) {
      failures.push(`${where}, between <${chip}> and its <Card>: no className string this spec can read`)
      continue
    }
    if (keyed && !row) {
      row = { className: className ?? '', where }
      continue
    }
    layers.push(where)
    paintsNothing(className ?? '', `${where}, between <${chip}> and its <Card>`, failures)
  }
  failures.push(`${at(found[0])} <${chip}>: no <Card> above it, so this spec cannot read what is behind it`)
  return null
}

/** Card's classes as it renders with the props a row's source gives it. */
function cardClasses(props: Record<string, string | boolean>): string {
  const { container, unmount } = render(createElement(Card, props))
  const className = (container.firstElementChild as HTMLElement).className
  unmount()
  return className
}

/**
 * A card that is its own row: its own ground at rest and hovered, in each theme. Its hover fill replaces its own, so a
 * translucent one would show the page, which this spec does not read, and fails, as one at rest does.
 */
function cardGrounds(name: string, card: string, where: string, failures: string[]): Grounds {
  const fill = backgrounds(card, where, ['', 'hover', 'dark', 'dark:hover'], failures)
  const grounds: Grounds = { light: [], dark: [] }
  for (const theme of THEMES) {
    const states: Array<[string, Rgba | undefined]> = [
      [`${name} card`, winner(fill, theme === 'dark' ? ['dark', ''] : [''])],
      [`${name} hovered card`, winner(fill, theme === 'dark' ? ['dark:hover', 'dark', 'hover', ''] : ['hover', ''])],
    ]
    for (const [label, ground] of states) {
      if (!ground) failures.push(`${where} (${theme}, ${label}): no bg- ground this spec can resolve`)
      else if (ground[3] < 1) failures.push(`${where} (${theme}, ${label}): a translucent ground, and this spec does not read what shows through it`)
      else grounds[theme].push([label, ground])
    }
  }
  return grounds
}

/** A summary row's grounds: a card that is its own row, or a row's tint over its card's ground, as a <tr>'s over its <tbody>. */
function summaryGrounds(name: string, stack: SummaryStack, failures: string[]): Grounds {
  const card = cardClasses(stack.card)
  return stack.row === null
    ? cardGrounds(name, card, stack.where.card, failures)
    : tableGrounds(name, stack.row, card, { row: stack.where.row, body: stack.where.card }, failures)
}

/** Why the summary rows' grounds could not be read; every case measuring on them fails on any of them. */
const SUMMARY_GROUND_FAILURES: string[] = []
/** The layers read between the summary chip and its card, on both rows. */
const SUMMARY_LAYERS: string[] = []
const SUMMARY_GROUNDS = Object.fromEntries(
  Object.entries(SUMMARY_ROWS).map(([name, file]) => {
    const stack = summaryStack(readFileSync(path.join(ROOT, file), 'utf8'), file, 'SummaryStatusBadge', SUMMARY_GROUND_FAILURES)
    SUMMARY_LAYERS.push(...(stack?.layers ?? []))
    return [name, stack ? summaryGrounds(name, stack, SUMMARY_GROUND_FAILURES) : { light: [], dark: [] }]
  }),
) as Record<keyof typeof SUMMARY_ROWS, Grounds>
const EVERY_SUMMARY_GROUND: Grounds = {
  light: Object.values(SUMMARY_GROUNDS).flatMap((g) => g.light),
  dark: Object.values(SUMMARY_GROUNDS).flatMap((g) => g.dark),
}

const SUMMARY_BADGE = 'features/watchlist/components/SummaryStatusBadge.tsx'
/** Why the status kinds the chip knows could not be read; every summary case fails on any of them. */
const KIND_FAILURES: string[] = []
/** The status prefixes the chip knows, from its source: the members of its SummaryStatusKind type. */
const SUMMARY_KINDS = literalMembers(readFileSync(path.join(ROOT, SUMMARY_BADGE), 'utf8'), SUMMARY_BADGE, 'SummaryStatusKind', 'the status kinds the chip knows', KIND_FAILURES)
/** A prefix the chip does not know, for which needs_regeneration decides. */
const UNKNOWN_PREFIX = 'queued'
if (SUMMARY_KINDS.includes(UNKNOWN_PREFIX)) KIND_FAILURES.push(`${SUMMARY_BADGE}: ${UNKNOWN_PREFIX} is a kind the chip knows, so this spec reads no prefix it does not`)
/** Every status the chip can be given, as [summary_status, needs_regeneration]: each kind and the unknown prefix, with and without the flag. */
const SUMMARY_INPUTS = [...SUMMARY_KINDS, UNKNOWN_PREFIX].flatMap((status): Array<[string, boolean]> => [[status, true], [status, false]])

describe('admin status chips: the label clears 4.5:1 on its actual ground, both themes (ADM-16a, ADM-16b)', () => {
  it("every member of Badge's status set, on the rows of both tables at rest and hovered", () => {
    const failures = [...GROUND_FAILURES, ...SET_FAILURES]
    let measured = 0
    for (const variant of STATUS_VARIANTS) measured += measure(`Badge ${variant}`, badgeClasses(variant), EVERY_GROUND, failures)
    expect(failures).toEqual([])
    // Five status variants, two themes, two tables, each row at rest and hovered: a reader that found no ground, or a
    // set read short, must not pass.
    expect(measured).toBe(40)
  })

  it("both badges render every status as Badge's chip for one member of its status set, so the measurement above is what ships", () => {
    const failures = [...SET_FAILURES]
    let read = 0
    for (const [name, Chip, statuses] of CHIPS) {
      for (const status of statuses) {
        const why = offTheSet(`${name} ${status}`, chipOf(createElement(Chip, { status: status as never })))
        read += 1
        if (why) failures.push(why)
      }
    }
    expect(failures).toEqual([])
    expect(read).toBe(7)
  })

  it("reads Badge's status set from its type, fails on one it cannot read, and tells Badge's chip from a copy, a tint, an added class and a chip with something painted on it or inside it", () => {
    const lost: string[] = []
    statusSet("export type BadgeVariant = 'pro'", 'probe.tsx', lost)
    expect(statusSet("export type BadgeStatusVariant = 'success' | Other | (typeof SET)[number]", 'probe.tsx', lost)).toEqual(['success'])
    expect(lost).toEqual([
      "probe.tsx: no BadgeStatusVariant type, so this spec cannot read Badge's status set",
      'probe.tsx: Other in BadgeStatusVariant is not a string literal this spec can read',
      'probe.tsx: (typeof SET)[number] in BadgeStatusVariant is not a string literal this spec can read',
    ])
    const own = classSet(badgeClasses('info-status'))
    const planted: Array<[string, ReactElement]> = [
      ['a copy of its classes', createElement('span', { className: badgeClasses('info-status') }, 'x')],
      ['the info tint', createElement(Badge, { variant: 'info' }, 'x')],
      ['a class added', createElement(Badge, { variant: 'info-status', className: 'gap-1' }, 'x')],
      ['info-status itself', createElement(Badge, { variant: 'info-status' }, 'x')],
      ['a tint on its label', createElement(Badge, { variant: 'info-status' }, createElement('span', { className: 'bg-info-light/10 text-info-light' }, 'x'))],
      ['its own style', createElement(Badge, { variant: 'info-status', style: { opacity: 0.5 } }, 'x')],
      ['a style on its icon', createElement(Badge, { variant: 'info-status', icon: createElement('svg', { className: 'h-3.5 w-3.5', style: { color: 'red' } }) }, 'x')],
      ['a fill of its icon\'s own', createElement(Badge, { variant: 'info-status', icon: createElement('svg', { className: 'h-3.5 w-3.5', fill: '#ff0000' }) }, 'x')],
      ['its icon as the admin badges give it', createElement(Badge, { variant: 'info-status', icon: createElement('svg', { className: 'h-3.5 w-3.5', fill: 'currentColor' }, createElement('path', { d: 'M0 0h1v1H0z' })) }, 'x')],
    ]
    expect(planted.map(([name, element]) => offTheSet(name, chipOf(element)))).toEqual([
      `a copy of its classes: "${own}" is no chip Badge rendered, so its classes are hand-rolled`,
      "the info tint: Badge's info, which is not in its status set",
      `a class added: "${classSet(`${own} gap-1`)}" is not Badge's info-status as it renders, "${own}"`,
      null,
      "a tint on its label: Badge's info-status with <span> class bg-info-light/10, <span> class text-info-light, which may paint over what is measured",
      'its own style: Badge\'s info-status with its own style "opacity: 0.5;", which may paint over what is measured',
      'a style on its icon: Badge\'s info-status with <svg> style "color: red;", which may paint over what is measured',
      'a fill of its icon\'s own: Badge\'s info-status with <svg> fill="#ff0000", which may paint over what is measured',
      null,
    ])
  })

  it('the feedback type chip, every type as it renders, on FeedbackRow at rest and hovered', () => {
    const failures = [...GROUND_FAILURES]
    let measured = 0
    for (const type of ['bug', 'feature', 'general'] satisfies FeedbackType[]) {
      const { container, unmount } = render(createElement(FeedbackTypeBadge, { type }))
      measured += measure(`FeedbackTypeBadge ${type}`, (container.firstElementChild as HTMLElement).className, GROUNDS.feedback, failures)
      unmount()
    }
    expect(failures).toEqual([])
    // Three types, two themes, the row at rest and hovered.
    expect(measured).toBe(12)
  })

  it("the feedback type chip takes Badge's metrics, so FeedbackRow's two chips share one weight, with a ground and an ink of its own", () => {
    const failures = [...METRIC_FAILURES]
    for (const type of ['bug', 'feature', 'general'] satisfies FeedbackType[]) {
      const why = offTheMetrics(`FeedbackTypeBadge ${type}`, chipOf(createElement(FeedbackTypeBadge, { type })).className, METRICS)
      if (why) failures.push(why)
    }
    expect(failures).toEqual([])
  })

  it("reads Badge's metrics from its BASE, fails on one it cannot read, and tells them from a recipe of a chip's own", () => {
    const lost: string[] = []
    expect(badgeMetrics("const TINT = 'border'", 'probe.tsx', lost)).toEqual([])
    expect(badgeMetrics("const BASE = cx('inline-flex', 'text-xs')", 'probe.tsx', lost)).toEqual([])
    expect(lost).toEqual(["probe.tsx: no BASE, so this spec cannot read Badge's metrics", 'probe.tsx: BASE is not a string literal this spec can read'])
    const own = 'border border-border-light bg-black/[0.04] text-text-secondary-light dark:border-white/10 dark:bg-transparent dark:text-text-secondary-dark'
    const metrics = 'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold'
    expect([
      offTheMetrics('the old recipe', `inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${own}`, metrics.split(' ')),
      offTheMetrics("Badge's metrics", `${metrics} ${own}`, metrics.split(' ')),
      offTheMetrics('a size of its own', `${metrics} text-sm ${own}`, metrics.split(' ')),
    ]).toEqual([
      "the old recipe: lacks Badge's gap-1.5, whitespace-nowrap, font-semibold and sets gap-1, font-medium, which is no ground or ink",
      null,
      'a size of its own: sets text-sm, which is no ground or ink',
    ])
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
    const panel = tableGrounds('probe', '', 'bg-panel-light dark:bg-panel-dark', PROBE, [])
    // The ink's own colour as the chip's ground: 1:1, so it fails on contrast rather than passing.
    const sameInk: string[] = []
    measure('probe', 'bg-[rgb(29,78,216)] text-info-text dark:text-info-dark', panel, sameInk)
    expect(sameInk).toContain('probe (light, probe row): 1.00:1')
    const unread: string[] = []
    measure('probe', 'bg-[hsl(224,76%,48%)] text-info-text dark:text-info-dark', panel, unread)
    expect(unread).toContain('probe (light): bg-[hsl(224,76%,48%)] looks like a colour this spec cannot resolve')
    // The fourth review's probe: a chip colour under the important modifier, ground or ink, is refused rather
    // than measured as if it were absent; an important utility that is not a colour is left alone.
    const important: string[] = []
    measure('probe', '!bg-[rgb(29,78,216)] text-info-text dark:text-info-dark', panel, important)
    expect(important).toEqual(['probe (light): !bg-[rgb(29,78,216)] looks like a colour this spec cannot resolve'])
    expect(chipColours('text-info-text dark:!text-info-dark', 'dark').unread).toEqual(['dark:!text-info-dark'])
    expect(chipColours('bg-[url(/x.png)] !text-xs bg-white text-info-text', 'light').unread).toEqual([])
  })

  it('refuses a chip colour under a variant it does not model, and an opacity below 100 wherever it reads classes', () => {
    // The principal review's mutations, a dark hover fill on the chip and the chip faded, each refused in every
    // theme it applies in; a text- utility that sets no colour under a variant, and a full opacity, are left alone.
    const panel = tableGrounds('probe', '', 'bg-panel-light dark:bg-panel-dark', PROBE, [])
    const chip: string[] = []
    const planted = 'dark:hover:bg-white/20 focus-visible:!text-white opacity-60 dark:text-opacity-[.5] hover:text-xs opacity-100'
    expect(measure('probe', `bg-white text-info-text dark:bg-transparent dark:text-info-dark ${planted}`, panel, chip)).toBe(4)
    expect(chip).toEqual([
      'probe (light): focus-visible:!text-white is a chip colour under a variant this spec does not model',
      'probe (light): opacity-60 sets an opacity below 100, which this spec does not model',
      'probe (dark): dark:hover:bg-white/20 is a chip colour under a variant this spec does not model',
      'probe (dark): focus-visible:!text-white is a chip colour under a variant this spec does not model',
      'probe (dark): opacity-60 sets an opacity below 100, which this spec does not model',
      'probe (dark): dark:text-opacity-[.5] sets an opacity below 100, which this spec does not model',
    ])
    // The same opacity refusal on what the chip sits in: the <tbody>, the <tr>, and a layer between them.
    const under: string[] = []
    tableGrounds('probe', 'hover:bg-background-light group-hover:opacity-[var(--fade)]', 'bg-panel-light dark:bg-panel-dark dark:bg-opacity-50', PROBE, under)
    chipLayers('<tr><td className="px-4 hover:opacity-100 aria-disabled:opacity-50"><Chip /></td></tr>', 'probe.tsx', ['Chip'], under)
    expect(under).toEqual([
      'probe <tbody>: dark:bg-opacity-50 sets an opacity below 100, which this spec does not model',
      'probe <tr>: group-hover:opacity-[var(--fade)] looks like an opacity this spec cannot resolve',
      'probe.tsx:1 <td>, between <Chip> and its <tr>: aria-disabled:opacity-50 sets an opacity below 100, which this spec does not model',
    ])
  })

  it('reads the row tint and the tbody ground it is given, and fails on one it cannot find', () => {
    // The second review's mutation: InviteRow's dark hover at white/10.
    const hovered: string[] = []
    const grounds = tableGrounds('probe', 'hover:bg-background-light dark:hover:bg-white/10', 'bg-panel-light dark:bg-panel-dark', PROBE, hovered)
    measure('Badge info-status', badgeClasses('info-status'), grounds, hovered)
    expect(hovered).toEqual(['Badge info-status (dark, probe hovered row): 4.23:1'])
    // With no dark tint of its own, a hovered dark row shows the light hover tint; a row's dark:bg- outranks it.
    expect(tableGrounds('probe', 'hover:bg-background-light', 'bg-panel-light dark:bg-panel-dark', PROBE, []).dark[1][1]).toEqual(colour('background-light'))
    expect(tableGrounds('probe', 'hover:bg-background-light dark:bg-white/5', 'dark:bg-panel-dark', PROBE, []).dark[1][1]).toEqual(over(colour('white/5')!, colour('panel-dark')!))
    // An important tint is read as that fill, and outranks every plain one: dark:!bg-white/10 holds on a hovered
    // row over the plain dark:hover:bg-white/5, as the cascade paints it.
    const important: string[] = []
    const marked = tableGrounds('probe', 'hover:bg-background-light dark:hover:bg-white/5 dark:!bg-white/10', 'bg-panel-light dark:bg-panel-dark', PROBE, important)
    measure('Badge info-status', badgeClasses('info-status'), marked, important)
    expect(important).toEqual(['Badge info-status (dark, probe row): 4.23:1', 'Badge info-status (dark, probe hovered row): 4.23:1'])
    const lost: string[] = []
    oneClassName('<tbody className={cx("bg-panel-light")} />', 'probe.tsx', 'tbody', lost)
    oneClassName('<tr><td /></tr>', 'probe.tsx', 'tr', lost)
    oneClassName('<td />', 'probe.tsx', 'tr', lost)
    tableGrounds('probe', 'odd:bg-white dark:bg-[color:var(--row)]', 'divide-y bg-white/5 dark:bg-[hsl(0,0%,10%)]', PROBE, lost)
    expect(lost).toEqual([
      'probe.tsx: the <tbody> has no className string this spec can read',
      'probe.tsx: the <tr> has no className string this spec can read',
      'probe.tsx: 0 <tr> elements, where this spec reads exactly one',
      'probe <tbody>: dark:bg-[hsl(0,0%,10%)] looks like a colour this spec cannot resolve',
      'probe <tr>: odd:bg-white is a ground under a variant this spec does not model',
      'probe <tr>: dark:bg-[color:var(--row)] looks like a colour this spec cannot resolve',
      'probe <tbody> (light): a translucent ground, and this spec does not read what shows through it',
      'probe <tbody> (dark): a translucent ground, and this spec does not read what shows through it',
    ])
  })

  it('reads every layer between a chip and its row, and fails on a background there or a layer it cannot read', () => {
    // The rows' own: InviteRow's status cell, FeedbackRow's type cell, and its status cell and the wrapper inside it.
    expect(LAYERS).toHaveLength(4)
    // The third review's mutation, a dark fill on a chip's cell, and hover fills on a wrapper inside one; the
    // fourth review's chip in a self-closing component's prop.
    const probe = [
      '<tr className="hover:bg-background-light">',
      '  <td className="px-4 dark:bg-white/5"><Chip /></td>',
      '  <td><div className="flex hover:!bg-black/5 dark:hover:bg-white/10"><>{open && <Chip />}</></div></td>',
      '  <td className={cx("px-4")}><Chip /></td>',
      '  <td {...cell}><Tooltip><Chip /></Tooltip></td>',
      '  <td><Cell render={<Chip />} /></td>',
      '</tr>',
      'const lone = <span><Chip /></span>',
    ].join('\n')
    const lost: string[] = []
    expect(chipLayers(probe, 'probe.tsx', ['Chip', 'Badge'], lost)).toEqual(['probe.tsx:2 <td>', 'probe.tsx:3 <div>', 'probe.tsx:3 <td>', 'probe.tsx:6 <td>', 'probe.tsx:8 <span>'])
    expect(lost).toEqual([
      'probe.tsx:2 <td>, between <Chip> and its <tr>: dark:bg-white/5 sets a background this spec does not model',
      'probe.tsx:3 <div>, between <Chip> and its <tr>: hover:!bg-black/5 sets a background this spec does not model',
      'probe.tsx:3 <div>, between <Chip> and its <tr>: dark:hover:bg-white/10 sets a background this spec does not model',
      'probe.tsx:4 <td>, between <Chip> and its <tr>: no className string this spec can read',
      'probe.tsx:5 <Tooltip>, between <Chip> and its <tr>: a component, and this spec does not read what it renders',
      'probe.tsx:5 <td>, between <Chip> and its <tr>: no className string this spec can read',
      'probe.tsx:6 <Cell>, between <Chip> and its <tr>: a component, and this spec does not read what it renders',
      'probe.tsx:8 <Chip>: no <tr> above it, so this spec cannot read what is behind it',
      'probe.tsx: no <Badge>, so this spec cannot read what is behind it',
    ])
  })
})

describe('the summary status chip: the label clears 4.5:1 on the watchlist cards and the dashboard rows, both themes', () => {
  it('every chip summaryStatusBadge() returns, rendered through Badge, on both rows at rest and hovered', () => {
    const failures = [...SUMMARY_GROUND_FAILURES, ...KIND_FAILURES]
    const chips = new Map<string, { label: string; variant: string }>()
    for (const [status, needs] of SUMMARY_INPUTS) {
      const { label, variant } = summaryStatusBadge(status, needs)
      chips.set(`${label} ${variant}`, { label, variant })
    }
    let measured = 0
    for (const { label, variant } of chips.values()) {
      const { className } = chipOf(createElement(Badge, { variant: variant as BadgeVariant }, label))
      measured += measure(`"${label}" (${variant})`, className, EVERY_SUMMARY_GROUND, failures)
    }
    expect(failures).toEqual([])
    // Seven chips (Ready, Generating, No summary yet, Unavailable, Error, Needs regenerating, Pending), two themes, two
    // rows, each at rest and hovered: a reader that found no ground, or kinds read short, must not pass.
    expect(chips.size).toBe(7)
    expect(measured).toBe(56)
  })

  it("SummaryStatusBadge renders every status as Badge's chip for the member of its status set summaryStatusBadge() returns, so the measurement above is what ships", () => {
    const failures = [...SET_FAILURES, ...KIND_FAILURES]
    let read = 0
    for (const [status, needs] of SUMMARY_INPUTS) {
      const name = `SummaryStatusBadge ${status}${needs ? ', needs regeneration' : ''}`
      const chip = chipOf(createElement(SummaryStatusBadge, { status, needsRegeneration: needs }))
      const { variant } = summaryStatusBadge(status, needs)
      const why = offTheSet(name, chip)
      read += 1
      if (why) failures.push(why)
      else if (chip.badge !== variant) failures.push(`${name}: Badge's ${chip.badge}, where summaryStatusBadge() returns ${variant}, the chip measured above`)
    }
    expect(failures).toEqual([])
    // Five kinds and a prefix the chip does not know, each with and without needs_regeneration.
    expect(read).toBe(12)
  })

  it("reads what is under a summary chip from its row's source, the card as Card renders it, and fails on what it cannot read", () => {
    // The rows' own layers: the watchlist card's three wrappers around the chip, and the dashboard row's status cluster.
    expect(SUMMARY_LAYERS).toHaveLength(4)
    const ok: string[] = []
    // A card per item is its own row, read at rest and hovered from Card's own classes: the interactive card brightens
    // to white under the pointer in light and keeps its fill in dark, where dark:bg- outranks hover:bg-; its pressed
    // fill is a state this spec does not model, so it fails.
    const own = summaryStack('<Card key={id} as="section" interactive className={"p-6"}><div className="flex"><>{open && <Chip />}</></div></Card>', 'probe.tsx', 'Chip', ok)
    expect(own).toEqual({ card: { as: 'section', interactive: true, className: 'p-6' }, row: null, where: { card: 'probe.tsx:1 <Card>', row: 'probe.tsx:1 <Card>' }, layers: ['probe.tsx:1 <div>'] })
    const pressed: string[] = []
    const grounds = summaryGrounds('probe', own!, pressed)
    expect(grounds).toEqual({
      light: [['probe card', colour('panel-light')], ['probe hovered card', colour('white')]],
      dark: [['probe card', colour('panel-dark')], ['probe hovered card', colour('panel-dark')]],
    })
    expect(pressed).toEqual([
      'probe.tsx:1 <Card>: active:bg-brand-weak/60 is a ground under a variant this spec does not model',
      'probe.tsx:1 <Card>: dark:active:bg-brand-weak-dark is a ground under a variant this spec does not model',
    ])
    // A row inside a card: its tint at rest and hovered over the card's ground, as a <tr>'s over its <tbody>. The
    // second review's admin mutation, a dark hover at white/10, drops info-status under the floor here too.
    const inCard = summaryStack('<Card className="divide-y"><div key={id} className="px-4 hover:bg-white dark:hover:bg-white/10"><span><Chip /></span></div></Card>', 'probe.tsx', 'Chip', ok)
    expect(inCard).toEqual({ card: { className: 'divide-y' }, row: 'px-4 hover:bg-white dark:hover:bg-white/10', where: { card: 'probe.tsx:1 <Card>', row: 'probe.tsx:1 <div>' }, layers: ['probe.tsx:1 <span>'] })
    const hovered: string[] = []
    measure('Badge info-status', badgeClasses('info-status'), summaryGrounds('probe', inCard!, hovered), hovered)
    expect(hovered).toEqual(['Badge info-status (dark, probe hovered row): 4.23:1'])
    expect(ok).toEqual([])
    // What it cannot read fails: a fill on a layer, a component on the way, a layer's className it cannot read, no
    // <Card>, no keyed row, a card prop it cannot read (an expression, a style, a spread), two chips, a translucent
    // card, and a kinds type it cannot read.
    const lost: string[] = []
    for (const source of [
      '<Card key={id}><div className="flex dark:bg-white/5"><Chip /></div></Card>',
      '<Card key={id}><Tooltip><Chip /></Tooltip></Card>',
      '<Card key={id}><div className={cx("flex")}><Chip /></div></Card>',
      '<div key={id}><Chip /></div>',
      '<Card><div className="flex"><Chip /></div></Card>',
      '<Card key={id} className={cx("p-6")} style={{ opacity: 0.5 }} {...rest}><Chip /></Card>',
      '<Card key={id}><Chip /><Chip /></Card>',
    ]) summaryStack(source, 'probe.tsx', 'Chip', lost)
    cardGrounds('probe', 'bg-panel-light hover:bg-white/50 dark:bg-panel-dark', 'probe <Card>', lost)
    literalMembers("export type SummaryStatusKind = 'ready' | Other", 'probe.tsx', 'SummaryStatusKind', 'the status kinds the chip knows', lost)
    literalMembers("export type Kind = 'ready'", 'probe.tsx', 'SummaryStatusKind', 'the status kinds the chip knows', lost)
    expect(lost).toEqual([
      'probe.tsx:1 <div>, between <Chip> and its <Card>: dark:bg-white/5 sets a background this spec does not model',
      'probe.tsx:1 <Tooltip>, between <Chip> and its <Card>: a component, and this spec does not read what it renders',
      'probe.tsx:1 <div>, between <Chip> and its <Card>: no className string this spec can read',
      'probe.tsx:1 <Chip>: no <Card> above it, so this spec cannot read what is behind it',
      'probe.tsx:1 <Chip>: no element with a key between it and its <Card>, so this spec cannot tell which one is the row',
      'probe.tsx:1 <Card>: className={cx("p-6")} is a prop this spec cannot read, so it cannot tell what the card paints',
      'probe.tsx:1 <Card>: style={{ opacity: 0.5 }} is a prop this spec cannot read, so it cannot tell what the card paints',
      'probe.tsx:1 <Card>: {...rest} is a prop this spec cannot read, so it cannot tell what the card paints',
      'probe.tsx: 2 <Chip> elements, where this spec reads exactly one',
      'probe <Card> (light, probe hovered card): a translucent ground, and this spec does not read what shows through it',
      'probe.tsx: Other in SummaryStatusKind is not a string literal this spec can read',
      'probe.tsx: no SummaryStatusKind type, so this spec cannot read the status kinds the chip knows',
    ])
  })
})
