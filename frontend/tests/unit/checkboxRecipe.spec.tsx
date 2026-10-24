import { readdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { render, screen } from '@testing-library/react'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { buttonVariants, Checkbox } from '@/components/ui'
import { heldValues, knownAsIn, leavesOf, propertyOf, scopeResolver, type Held } from './heldValues'

/**
 * ADM-37: the checkbox is one recipe, components/ui/Checkbox.tsx. The admin invites page and the consent
 * dialog each hand-rolled one, and in dark the checked box was brand-strong on panel-dark (2.2:1), or
 * panel-dark itself where the page set `dark:bg-panel-dark` (the forms plugin paints the checked fill with
 * `[type='checkbox']:checked`, which that class outranks), so a checked box read as empty.
 *
 * Holds:
 *  - the recipe states its checked fill in each theme, and each fill clears 3:1 against its panel and
 *    under its check; the unchecked edge clears 3:1 against its panel (WCAG 1.4.11). The check is the
 *    plugin's white one unless the recipe overrides its background-image with a globals.css variable
 *    (`checked:[background-image:var(--x)]`); then the check's colour is the fill that variable draws;
 *  - in dark the checked box is the Primary button's dark recipe (DESIGN.md Primary): its fill is the
 *    Primary's dark fill and its check is the Primary's navy label ink, never white on sage;
 *  - the recipe takes the plugin's ring off and draws the brand ring in both themes;
 *  - no file under app/, components/ or features/ but Checkbox.tsx renders a raw checkbox: an <input>, or React's
 *    createElement('input', …), whose type, read as a value (rawCheckboxes), may be "checkbox".
 */

const ROOT = path.resolve(__dirname, '../..')
const C = (createRequire(import.meta.url)('../../tailwind.config.js') as { theme: { extend: { colors: Record<string, Record<string, string>> } } }).theme.extend.colors

const hex = (name: string): string => {
  const [family, ...rest] = name.split('-')
  const value = C[family]?.[rest.join('-')]
  if (typeof value !== 'string' || !value.startsWith('#')) throw new Error(`no hex token for ${name}`)
  return value
}
const lum = (h: string) => {
  const ch = (i: number) => {
    const s = parseInt(h.slice(1 + i * 2, 3 + i * 2), 16) / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * ch(0) + 0.7152 * ch(1) + 0.0722 * ch(2)
}
const contrast = (a: string, b: string) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x)
  return Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100
}

const GLOBALS_CSS = readFileSync(path.join(ROOT, 'app/globals.css'), 'utf8')
/** The check the forms plugin draws on a checked box when nothing overrides its background-image. */
const PLUGIN_CHECK = '#FFFFFF'

/** The colour a globals.css check variable draws: `--x: url("data:image/svg+xml,…fill='%23RRGGBB'…")`. */
function checkFromVar(name: string, css: string = GLOBALS_CSS): string {
  const declared = css.match(new RegExp(`${name}:\\s*url\\("data:image/svg\\+xml,([^"]*)"\\)`))
  if (!declared) throw new Error(`app/globals.css declares no ${name} check`)
  const fill = decodeURIComponent(declared[1]).match(/fill='(#[0-9A-Fa-f]{6})'/)
  if (!fill) throw new Error(`${name} draws no hex fill`)
  return fill[1].toUpperCase()
}

/** The check's colour under a variant prefix ('checked:' or 'dark:checked:'): the override's, or the plugin's. */
function checkColour(classes: string[], prefix: string): string {
  const override = classes.find((c) => c.startsWith(`${prefix}[background-image:`))
  if (!override) return PLUGIN_CHECK
  const name = override.match(/^[^[]*\[background-image:var\((--[\w-]+)\)\]$/)?.[1]
  if (!name) throw new Error(`${override} is not a var() check`)
  return checkFromVar(name)
}

/** The files the absence scan reads: every module under the scanned roots but the recipe's own. */
const scanned = (rel: string) => /\.tsx?$/.test(rel) && rel !== path.join('components', 'ui', 'Checkbox.tsx')

/**
 * The lines of the raw checkboxes a source renders: an `<input>` element, or React's `createElement('input', …)` under
 * any local name, whose type may be "checkbox". The type is read as a value through the shared model (heldValues.ts)
 * from each of its writers: the `type` attribute's value and each spread's `type` (`<input {...props} />` where
 * `props = { type: 'checkbox' as const }`), held in a same-file binding, a conditional's arms, a property written
 * under a key the scan cannot read or React's state (what useState, useReducer, useRef and the other hooks the
 * model's header names keep, E159); in any letter case, since the browser reads the value so (`type="Checkbox"` draws
 * one). A writer that a later attribute overrides still counts, which fails closed. Out of reach, as in the model: a
 * value from another module, a tag held in a variable (`const Tag = 'input'`) and a type set on the DOM node.
 */
function rawCheckboxes(file: string, text: string): number[] {
  if (!/checkbox/i.test(text)) return []
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const { valueOf } = heldValues<'checkbox'>(sf, (e) => (ts.isStringLiteralLike(e) && e.text.toLowerCase() === 'checkbox' ? ['checkbox'] : undefined))
  const knownAs = knownAsIn(scopeResolver(sf))
  const isCheckbox = (value: Held<'checkbox'> | undefined) => !!value && leavesOf(value).has('checkbox')
  const lines: number[] = []
  const visit = (node: ts.Node): void => {
    let checkbox = false
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(sf) === 'input') {
      checkbox = node.attributes.properties.some((p) => {
        if (ts.isJsxSpreadAttribute(p)) return isCheckbox(propertyOf(valueOf(p.expression), 'type'))
        if (p.name.getText(sf) !== 'type' || !p.initializer) return false
        const written = ts.isJsxExpression(p.initializer) ? p.initializer.expression : p.initializer
        return !!written && isCheckbox(valueOf(written))
      })
    } else if (ts.isCallExpression(node) && knownAs(node.expression)?.name === 'createElement') {
      const [tag, props] = node.arguments
      checkbox = !!tag && ts.isStringLiteralLike(tag) && tag.text === 'input' && !!props && isCheckbox(propertyOf(valueOf(props), 'type'))
    }
    if (checkbox) lines.push(sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1)
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return lines
}

/** The classes the rendered Checkbox carries. */
function recipe(): string[] {
  render(<Checkbox aria-label="Email invites" defaultChecked />)
  return (screen.getByRole('checkbox', { name: 'Email invites' }) as HTMLInputElement).className.split(/\s+/)
}

describe('the shared Checkbox recipe (ADM-37)', () => {
  const pick = (classes: string[], prefix: string) => {
    const hit = classes.find((c) => c.startsWith(prefix) && !c.slice(prefix.length).includes(':'))
    if (!hit) throw new Error(`no ${prefix}* class in ${classes.join(' ')}`)
    return hit.slice(prefix.length)
  }

  it.each([
    ['light', 'checked:', 'border-', 'panel-light'],
    ['dark', 'dark:checked:', 'dark:border-', 'panel-dark'],
  ] as const)('%s: the checked fill and the unchecked edge clear 3:1, and the check clears 3:1 on the fill', (_theme, checked, edgePrefix, panel) => {
    const classes = recipe()
    const fill = hex(pick(classes, `${checked}bg-`))
    const edge = hex(pick(classes, edgePrefix))
    expect(contrast(fill, hex(panel)), 'checked fill on its panel').toBeGreaterThanOrEqual(3)
    expect(contrast(checkColour(classes, checked), fill), 'the check on the fill').toBeGreaterThanOrEqual(3)
    expect(contrast(edge, hex(panel)), 'unchecked edge on its panel').toBeGreaterThanOrEqual(3)
  })

  it("dark: the checked box is the Primary button's dark recipe, navy ink on its sage fill", () => {
    const classes = recipe()
    const primary = buttonVariants({ variant: 'primary' }).split(/\s+/)
    const primaryFill = pick(primary, 'dark:bg-')
    const primaryInk = pick(primary, 'dark:text-')
    expect(pick(classes, 'dark:checked:bg-'), "the Primary's dark fill").toBe(primaryFill)
    expect(checkColour(classes, 'dark:checked:'), "the Primary's dark label ink").toBe(hex(primaryInk))
  })

  it('self-check: the check resolver reads the fill a globals.css variable draws, and fails on one it does not declare', () => {
    expect(checkFromVar('--probe', `--probe: url("data:image/svg+xml,%3csvg fill='%23FFFFFF'%3e%3c/svg%3e");`)).toBe('#FFFFFF')
    expect(() => checkFromVar('--check-undeclared')).toThrow('app/globals.css declares no --check-undeclared check')
    expect(checkColour(['checked:bg-brand-strong'], 'checked:'), "no override is the plugin's white").toBe(PLUGIN_CHECK)
  })

  it('a dark ground never comes without its own checked fill', () => {
    const classes = recipe()
    if (classes.some((c) => c.startsWith('dark:bg-'))) expect(classes.some((c) => c.startsWith('dark:checked:bg-'))).toBe(true)
  })

  it('takes the plugin ring off and draws the brand ring in both themes', () => {
    expect(recipe()).toEqual(
      expect.arrayContaining(['focus:ring-0', 'focus-visible:outline-none', 'focus-visible:shadow-ring-brand', 'dark:focus-visible:shadow-ring-brand-dark']),
    )
  })

  it('no page or component hand-rolls a checkbox', () => {
    const found: string[] = []
    const walk = (dir: string) => {
      for (const entry of readdirSync(path.join(ROOT, dir), { withFileTypes: true })) {
        const rel = path.join(dir, entry.name)
        if (entry.isDirectory()) walk(rel)
        else if (scanned(rel)) {
          for (const line of rawCheckboxes(rel, readFileSync(path.join(ROOT, rel), 'utf8'))) found.push(`${rel}:${line}`)
        }
      }
    }
    for (const dir of ['app', 'components', 'features']) walk(dir)
    expect(found, 'use <Checkbox> from components/ui').toEqual([])
  })

  it('self-check: the scan reads the type from each of its writers, in any letter case, and no other property', () => {
    const probe = [
      "import React, { createElement as h } from 'react'",
      "const KIND = 'checkbox'",
      "const props = { type: 'checkbox' as const }",
      "const other = { type: 'text', name: 'checkbox' }",
      'const keyed: Record<string, string> = {}',
      "keyed[field] = 'checkbox'",
      'export const A = () => <input type="checkbox" />',
      'export const B = () => <input type="Checkbox" />',
      'export const C = () => <input type={KIND} />',
      'export const D = () => <input {...props} />',
      "export const E = (on: boolean) => <input {...(on ? { type: 'checkbox' } : {})} />",
      'export const F = () => <input {...keyed} />',
      "export const G = () => h('input', { type: 'checkbox' })",
      "export const H = () => React.createElement('input', props)",
      'export const I = () => <input type="text" />',
      'export const J = () => <input {...other} />',
      "export const K = (on: boolean) => <input type={on ? 'radio' : 'text'} />",
      "export const L = () => h('label', { type: 'checkbox' })",
      'export const M = () => <Checkbox aria-label="x" />',
      // React's state (E159): what an initial value, a setter or a ref holds.
      "export const O = () => { const [type] = useState('checkbox'); return <input type={type} /> }",
      "export const P = (on: boolean) => { const [type, setType] = useState('text'); if (on) setType('checkbox'); return <input type={type} /> }",
      "export const Q = () => { const kind = useRef('checkbox'); return <input type={kind.current} /> }",
      // Out of reach (the header): a tag held in a variable.
      "const Tag = 'input'",
      'export const N = () => <Tag type="checkbox" />',
    ].join('\n')
    expect(rawCheckboxes('probe.tsx', probe)).toEqual([7, 8, 9, 10, 11, 12, 13, 14, 20, 21, 22])
    expect(rawCheckboxes('probe.tsx', 'export const B = () => <input type="CHECKBOX" />'), 'a file whose only spelling is upper case').toEqual([1])
    expect(rawCheckboxes('probe.ts', "import { createElement } from 'react'\nexport const G = () => createElement('input', { type: 'checkbox' })"), 'a .ts module').toEqual([2])
    expect(['a.tsx', 'a.ts', 'a.css', path.join('components', 'ui', 'Checkbox.tsx')].map(scanned), 'the files the scan reads').toEqual([true, true, false, false])
  })
})
