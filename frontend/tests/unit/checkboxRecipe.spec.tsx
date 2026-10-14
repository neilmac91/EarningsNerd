import { readdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { render, screen } from '@testing-library/react'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { buttonVariants, Checkbox } from '@/components/ui'

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
 *  - no file under app/, components/ or features/ renders a raw <input type="checkbox"> but Checkbox.tsx.
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
        else if (rel.endsWith('.tsx') && rel !== path.join('components', 'ui', 'Checkbox.tsx')) {
          const text = readFileSync(path.join(ROOT, rel), 'utf8')
          if (!text.includes('checkbox')) continue
          const sf = ts.createSourceFile(rel, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
          const visit = (node: ts.Node): void => {
            if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(sf) === 'input') {
              const type = node.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText(sf) === 'type')
              if (type?.initializer && /checkbox/.test(type.initializer.getText(sf))) found.push(`${rel}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1}`)
            }
            ts.forEachChild(node, visit)
          }
          visit(sf)
        }
      }
    }
    for (const dir of ['app', 'components', 'features']) walk(dir)
    expect(found, 'use <Checkbox> from components/ui').toEqual([])
  })
})
