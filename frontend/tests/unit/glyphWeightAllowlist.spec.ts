/* =============================================================================
   glyphWeightAllowlist.spec.ts — guardrail (E196 (5), chief design on #1707)
   -----------------------------------------------------------------------------
   Glyphs are Phosphor at regular weight (DESIGN.md › Icons; app/providers.tsx
   makes it the default). A glyph takes a heavier weight only where regular's
   stroke, a sixteenth of the glyph's size, falls under a device pixel, and fills
   only to show a toggle is on. Chief design's review of #1707 set the rule: the
   contact form's 24px sent check stays regular, where bold would have made it
   the one glyph to gain ink beside the "sent" family's regular envelope and
   check, and the summary step log's 12px check keeps bold, where regular's
   0.75px stroke renders grey and broken on its disc.

   The scan reads each file's TypeScript AST (a .js file as JSX, as Next allows)
   and counts every `weight` JSX attribute and every `weight:` property whose
   value names a Phosphor weight other than regular (thin, light, bold, fill,
   duotone), a conditional's branches included. A `weight` attribute whose value
   names no weight at all (a variable) counts too, since it could name any. Each
   listed file is pinned, with its reason, to its count: a new heavier weight, an
   extra one in a listed file and a stale entry all fail.

   Limits: a weight spread in from another object ({...props}) and a `weight:`
   property set from a variable are not read; review reads them.
============================================================================= */

import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

const ROOT = path.join(__dirname, '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const NOT_REGULAR = new Set(['thin', 'light', 'bold', 'fill', 'duotone'])

const ALLOW: Record<string, { count: number; reason: string }> = {
  'app/company/[ticker]/page-client.tsx': { count: 1, reason: "the watchlist toggle's star fills while the company is on the list" },
  'app/filing/[id]/StreamingSummaryDisplay.tsx': {
    count: 1,
    reason: "the step log's 12px done check at bold: regular's stroke would be 0.75px, under a device pixel",
  },
  'features/calendar/components/AlertBell.tsx': { count: 1, reason: 'the alert bell fills while its alert is on' },
  'features/calendar/components/MonthView.tsx': {
    count: 1,
    reason: "the day cell's 10px bell, shown while the company's alert is on, at fill: regular's stroke would be 0.625px",
  },
}

/** The string literals in `node` and its descendants. */
function literals(node: ts.Node): string[] {
  const out: string[] = []
  const visit = (n: ts.Node): void => {
    if (ts.isStringLiteralLike(n)) out.push(n.text)
    ts.forEachChild(n, visit)
  }
  visit(node)
  return out
}

/** The glyph weights other than regular in `source`: `weight` attributes and `weight:` properties. */
function countNonRegularWeights(source: string, fileName: string): number {
  const sourceFile = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    fileName.endsWith('.tsx') ? ts.ScriptKind.TSX : /\.jsx?$/.test(fileName) ? ts.ScriptKind.JSX : ts.ScriptKind.TS,
  )
  let count = 0
  const visit = (node: ts.Node): void => {
    if (ts.isJsxAttribute(node) && node.name.getText(sourceFile) === 'weight' && node.initializer) {
      const named = literals(node.initializer)
      if (named.length === 0 || named.some((w) => NOT_REGULAR.has(w))) count += 1
    } else if (ts.isPropertyAssignment(node) && node.name.getText(sourceFile).replace(/['"]/g, '') === 'weight') {
      if (literals(node.initializer).some((w) => NOT_REGULAR.has(w))) count += 1
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return count
}

function walk(dir: string, out: string[] = []): string[] {
  if (!fs.existsSync(dir)) return out
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.[jt]sx?$/.test(entry.name)) out.push(p)
  }
  return out
}

function scan(): Record<string, number> {
  const found: Record<string, number> = {}
  for (const dir of SCAN_DIRS) {
    for (const file of walk(path.join(ROOT, dir))) {
      const count = countNonRegularWeights(fs.readFileSync(file, 'utf8'), file)
      if (count > 0) found[path.relative(ROOT, file).split(path.sep).join('/')] = count
    }
  }
  return found
}

describe('a glyph is regular, heavier only under a device pixel or as a toggle\'s on state (E196 (5))', () => {
  it('the detector counts every weight other than regular, and nothing else', () => {
    const count = (code: string) => countNonRegularWeights(code, 'fixture.tsx')
    expect(count('const a = <CheckIcon weight="bold" className="h-3 w-3" />')).toBe(1)
    expect(count("const a = <StarIcon weight={on ? 'fill' : 'regular'} />")).toBe(1)
    expect(count('const a = <BellIcon weight={weight} />')).toBe(1)
    expect(count("const a = <XIcon weight={'thin'} />")).toBe(1)
    expect(count("const p: IconProps = { size: 24, weight: 'bold' }")).toBe(1)
    expect(count("const p = { 'weight': 'duotone' }")).toBe(1)
    expect(count('const a = (\n  <CheckIcon\n    weight="fill"\n  />\n)')).toBe(1)
    // A .js module is read as JSX, as Next compiles it.
    expect(countNonRegularWeights('export const a = () => <XIcon weight="bold" />', 'mark.js')).toBe(1)
    // Regular, no weight, a font's weight and a weight's type are not a glyph drawn heavier.
    expect(count('const a = <CheckIcon weight="regular" />')).toBe(0)
    expect(count("const a = <CheckIcon weight={'regular'} />")).toBe(0)
    expect(count('const a = <CheckIcon className="h-6 w-6" />')).toBe(0)
    expect(count("const ICON_DEFAULTS: IconProps = { size: 24, weight: 'regular' }")).toBe(0)
    expect(count('interface Panel { weight: number }\nconst font = (weight: number) => `${weight} 12px Inter`')).toBe(0)
    expect(count('const s = { fontWeight: 700, weight: 600 }')).toBe(0)
    expect(count("const a = <span className=\"font-bold\">bold</span>")).toBe(0)
  })

  it('every weight other than regular is pinned to its file, with its reason', () => {
    const allowed = Object.fromEntries(Object.entries(ALLOW).map(([file, { count }]) => [file, count]))
    expect(scan()).toEqual(allowed)
  })

  it('names a reason for every entry', () => {
    for (const [file, { reason }] of Object.entries(ALLOW)) expect(reason.trim().length, file).toBeGreaterThan(10)
  })
})
