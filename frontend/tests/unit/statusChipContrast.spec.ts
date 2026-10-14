import { createElement, type FunctionComponent } from 'react'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { render } from '@testing-library/react'
import type { Config } from 'tailwindcss'
import resolveConfig from 'tailwindcss/resolveConfig'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import InviteStatusBadge from '@/features/admin/components/InviteStatusBadge'
import FeedbackStatusBadge from '@/features/admin/components/FeedbackStatusBadge'
import FeedbackTypeBadge from '@/features/admin/components/FeedbackTypeBadge'
import type { FeedbackStatus, FeedbackType, InviteStatus } from '@/features/admin/api/admin-api'
import { STATUS_CHIP, STATUS_CHIP_INK, type StatusChipTone } from '@/features/admin/lib/statusChip'

/**
 * The admin chips' labels clear 4.5:1 on what is behind them, in both themes (audit ADM-16a, ADM-16b;
 * CLAUDE.md rule 11). What is behind them is read from the code, never written here: each table's
 * <tbody> ground (app/admin/invites/page.tsx, app/admin/feedback/page.tsx) and its row's own tint
 * (InviteRow's and FeedbackRow's <tr>), from their className strings in the TypeScript AST, at rest and
 * hovered, and every layer between a chip and that <tr> (its cell, and any wrapper inside it), walked up
 * from each chip's element in the row's source. Those layers must paint nothing: a bg- utility on one,
 * under any variant, fails, because a fill there is a design change that comes with a change to this
 * spec. A <tr> or <tbody> it cannot find, a chip it cannot find or one with no <tr> above it, a component
 * between a chip and its row, a className that is not a plain string (a layer may carry none) or a layer
 * with props spread into it, a tbody with no ground it can resolve or a translucent one, and a ground
 * under a variant it does not model all fail; nothing falls back to a literal, and an inline style or a
 * stylesheet rule is out of reach. The status chip recipe has one home, features/admin/lib/statusChip.ts:
 * each tone is measured there once per theme on every one of those grounds, from its classes resolved
 * through tailwind.config.js, so a token, recipe or row change is read as it ships: the label ink over
 * the chip's ground, composited over the row. Both status badges are then held to that recipe, status by
 * status, and FeedbackTypeBadge, the chip beside FeedbackRow's status chip, is measured as it renders on
 * that row's grounds. A text- colour this spec cannot resolve fails, and so does a bg- or text- arbitrary
 * value (`bg-[...]`) that looks like a colour and is not a hex or rgb() it can read, or a chip's text- or
 * bg- colour under the important modifier, which this spec does not rank against the plain ones. A plain
 * unknown token name is skipped, since Tailwind emits no CSS for it either, and an arbitrary property
 * (`[background-color:...]`) is out of reach too.
 */
const require = createRequire(import.meta.url)
const flattenColorPalette = (require('tailwindcss/lib/util/flattenColorPalette') as { default: (c: unknown) => Record<string, string> }).default
const ROOT = path.resolve(__dirname, '../..')
const COLORS = flattenColorPalette(resolveConfig(require(path.join(ROOT, 'tailwind.config.js')) as Config).theme.colors)

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
 * string or absent and sets no bg- utility under any variant, so that the grounds measured here are what
 * the chip sits on. Returns the layers it read; a chip it cannot find, a walk that meets a component or no
 * <tr>, a layer it cannot read and a background on one each fail, naming the file and line.
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
        for (const cls of (className ?? '').split(/\s+/).filter(Boolean)) {
          if (/^!?bg-/.test(classParts(cls).pop()!)) failures.push(`${where}: ${cls} sets a background this spec does not model`)
        }
      }
      if (!up) failures.push(`${at(element)} <${chip}>: no <tr> above it, so this spec cannot read what is behind it`)
    }
  }
  return layers
}

/**
 * A class list's bg- colours by variant ('', 'hover', 'dark', 'dark:hover'), an important one (`!bg-`) keyed
 * under its variant with a leading `!`; one it cannot read, or a variant outside `modelled`, fails.
 */
function backgrounds(className: string, where: string, modelled: string[], failures: string[]): Map<string, Rgba> {
  const found = new Map<string, Rgba>()
  for (const cls of className.split(/\s+/).filter(Boolean)) {
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

/** The chip's text and background colours in one theme, from its class list, and the colour-like classes it could not read. */
function chipColours(className: string, theme: Theme) {
  const found: { text?: Rgba; bg?: Rgba; unread: string[] } = { unread: [] }
  for (const cls of className.split(/\s+/)) {
    const parts = classParts(cls)
    const utility = parts.pop()!
    const variants = parts.join(':')
    if (variants !== (theme === 'dark' ? 'dark' : '')) continue
    // A colour under the important modifier is refused like one it cannot read: in the browser it outranks
    // the plain ones, and this spec does not rank it.
    const m = utility.match(/^(!?)(text|bg)-(.+)$/)
    if (!m) continue
    const value = colour(m[3])
    if (value && !m[1]) found[m[2] as 'text' | 'bg'] = value
    else if (value || looksLikeColour(m[3])) found.unread.push(cls)
  }
  return found
}

const TONES = Object.keys(STATUS_CHIP_INK) as StatusChipTone[]
const recipe = (tone: StatusChipTone) => `${STATUS_CHIP} ${STATUS_CHIP_INK[tone]}`

/** A chip's label ratio on each ground, in both themes, with any class the reader could not read. */
function measure(name: string, className: string, grounds: Grounds, failures: string[]): number {
  let measured = 0
  for (const theme of THEMES) {
    const { text: ink, bg, unread } = chipColours(className, theme)
    for (const cls of unread) failures.push(`${name} (${theme}): ${cls} looks like a colour this spec cannot resolve`)
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
/** The self-checks' own <tr> and <tbody>: their grounds come from class strings written in each case, not from the code. */
const PROBE = { row: 'probe <tr>', body: 'probe <tbody>' }

describe('admin status chips: the label clears 4.5:1 on its actual ground, both themes (ADM-16a, ADM-16b)', () => {
  it('every tone of the status chip recipe, on the rows of both tables at rest and hovered', () => {
    const failures = [...GROUND_FAILURES]
    let measured = 0
    for (const tone of TONES) measured += measure(`status chip ${tone}`, recipe(tone), EVERY_GROUND, failures)
    expect(failures).toEqual([])
    // Four tones, two themes, two tables, each row at rest and hovered: a reader that found no ground must not pass.
    expect(measured).toBe(32)
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

  it('reads the row tint and the tbody ground it is given, and fails on one it cannot find', () => {
    // The second review's mutation: InviteRow's dark hover at white/10.
    const hovered: string[] = []
    const grounds = tableGrounds('probe', 'hover:bg-background-light dark:hover:bg-white/10', 'bg-panel-light dark:bg-panel-dark', PROBE, hovered)
    measure('status chip info', recipe('info'), grounds, hovered)
    expect(hovered).toEqual(['status chip info (dark, probe hovered row): 4.23:1'])
    // With no dark tint of its own, a hovered dark row shows the light hover tint; a row's dark:bg- outranks it.
    expect(tableGrounds('probe', 'hover:bg-background-light', 'bg-panel-light dark:bg-panel-dark', PROBE, []).dark[1][1]).toEqual(colour('background-light'))
    expect(tableGrounds('probe', 'hover:bg-background-light dark:bg-white/5', 'dark:bg-panel-dark', PROBE, []).dark[1][1]).toEqual(over(colour('white/5')!, colour('panel-dark')!))
    // An important tint is read as that fill, and outranks every plain one: dark:!bg-white/10 holds on a hovered
    // row over the plain dark:hover:bg-white/5, as the cascade paints it.
    const important: string[] = []
    const marked = tableGrounds('probe', 'hover:bg-background-light dark:hover:bg-white/5 dark:!bg-white/10', 'bg-panel-light dark:bg-panel-dark', PROBE, important)
    measure('status chip info', recipe('info'), marked, important)
    expect(important).toEqual(['status chip info (dark, probe row): 4.23:1', 'status chip info (dark, probe hovered row): 4.23:1'])
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
