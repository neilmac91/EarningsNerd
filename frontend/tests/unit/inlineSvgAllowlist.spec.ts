/* =============================================================================
   inlineSvgAllowlist.spec.ts — guardrail (E196 (5))
   -----------------------------------------------------------------------------
   Icons are Phosphor through lib/icons (DESIGN.md › Icons): a glyph is never drawn
   inline. Notice and GuidanceCard drew their state glyphs as hand-made SVG
   "matched to Phosphor regular weight", the summary's step list drew its check,
   the dialog's close its ✕ and the contact form's sent state its check, five
   copies that only looked like the system's glyphs (the 2026-10-24 callout
   review). They take lib/icons' WarningCircle, Info, CheckCircle, MagnifyingGlass,
   Check and X.

   An inline <svg> stays only where it draws something no glyph is: a chart, the
   two-tone spinner, or a mark that is someone's own (the brand's logo, Google's
   and Apple's sign-in marks). The scan reads each file's TypeScript AST (comments
   and strings never count; a .js file is read as JSX, as Next allows) and counts
   every JSX <svg> element, a member tag that renders one (<motion.svg>), every
   createElement('svg') and every createElementNS(…, 'svg'). Each listed file is
   pinned, with its reason, to its count: a new inline <svg>, an extra one in a
   listed file and a stale entry all fail.

   Limits: markup in a string (dangerouslySetInnerHTML, a data: URL), an SVG file
   imported as a component, createElement under another name (const h =
   React.createElement) and the compiled JSX runtime's calls (_jsx('svg')), which no
   source here writes, are not read; review reads them.
============================================================================= */

import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

const ROOT = path.join(__dirname, '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']

const ALLOW: Record<string, { count: number; reason: string }> = {
  'components/EarningsNerdLogoIcon.tsx': { count: 1, reason: "the brand's own mark" },
  'components/ui/Button.tsx': { count: 1, reason: 'the two-tone spinner (a ring at 30% and its arc), which no Phosphor glyph draws' },
  'components/ui/Input.tsx': { count: 1, reason: "FieldSpinner, the button's two-tone spinner at 16px" },
  'features/analysis/components/TrendChartSvg.tsx': { count: 2, reason: 'the trend chart and its sticky axis gutter' },
  'features/analysis/components/chartMarks.tsx': { count: 2, reason: "a legend's series swatch, drawn as the chart draws its series, and an absent series' dashed line" },
  'features/auth/components/AppleSignInButton.tsx': { count: 1, reason: "Apple's logo, as Apple's sign-in guidelines give it" },
  'features/auth/components/GoogleSignInButton.tsx': { count: 1, reason: "Google's G, as Google's sign-in guidelines give it" },
}

/** The inline SVG elements in `source`: JSX <svg> elements and createElement('svg') calls. */
function countInlineSvg(source: string, fileName: string): number {
  const sourceFile = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    fileName.endsWith('.tsx') ? ts.ScriptKind.TSX : /\.jsx?$/.test(fileName) ? ts.ScriptKind.JSX : ts.ScriptKind.TS,
  )
  let count = 0
  const isSvg = (arg: ts.Expression | undefined) => arg !== undefined && ts.isStringLiteralLike(arg) && arg.text === 'svg'
  const visit = (node: ts.Node): void => {
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && /(?:^|\.)svg$/.test(node.tagName.getText(sourceFile))) {
      count += 1
    } else if (ts.isCallExpression(node)) {
      const callee = node.expression
      const method = ts.isPropertyAccessExpression(callee) ? callee.name.text : ts.isIdentifier(callee) ? callee.text : ''
      const [first, second] = node.arguments
      if ((method === 'createElement' && isSvg(first)) || (method === 'createElementNS' && isSvg(second))) count += 1
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
      const count = countInlineSvg(fs.readFileSync(file, 'utf8'), file)
      if (count > 0) found[path.relative(ROOT, file).split(path.sep).join('/')] = count
    }
  }
  return found
}

describe('a glyph comes from lib/icons; an inline <svg> is a chart, a spinner or a mark (E196 (5))', () => {
  it('the detector counts every inline <svg> element, and nothing else', () => {
    const count = (code: string) => countInlineSvg(code, 'fixture.tsx')
    expect(count('const a = <svg viewBox="0 0 24 24" />')).toBe(1)
    expect(count('const a = <svg viewBox="0 0 24 24"><path d="M5 12h14" /></svg>')).toBe(1)
    expect(count('const a = (\n  <svg\n    viewBox="0 0 24 24"\n  >\n    <circle r="9" />\n  </svg>\n)')).toBe(1)
    expect(count('const a = <svg><svg /></svg>')).toBe(2)
    expect(count("const a = createElement('svg', { viewBox: '0 0 24 24' })")).toBe(1)
    expect(count("const a = React.createElement('svg', null)")).toBe(1)
    expect(count("const a = document.createElementNS('http://www.w3.org/2000/svg', 'svg')")).toBe(1)
    expect(count('const a = <motion.svg viewBox="0 0 24 24" />')).toBe(1)
    // A .js module is read as JSX, as Next compiles it.
    expect(countInlineSvg('export const a = () => <svg><path d="M5 12h14" /></svg>', 'mark.js')).toBe(1)
    expect(countInlineSvg('export const a = () => <svg />', 'mark.jsx')).toBe(1)
    // An SVG element made inside a <svg> by createElementNS is not one.
    expect(count("const a = document.createElementNS('http://www.w3.org/2000/svg', 'style')")).toBe(0)
    // A Phosphor glyph, a component named for its icon, a comment and a string are not inline SVG.
    expect(count("import { InfoIcon } from '@/lib/icons'\nconst a = <InfoIcon className=\"h-4 w-4\" />")).toBe(0)
    expect(count('const a = <SvgMark />')).toBe(0)
    expect(count('// drawn inside the <svg>\nconst a = <span />')).toBe(0)
    expect(count("const a = '<svg viewBox=\"0 0 24 24\"></svg>'")).toBe(0)
  })

  it('every inline <svg> is pinned to its file, with its reason', () => {
    const allowed = Object.fromEntries(Object.entries(ALLOW).map(([file, { count }]) => [file, count]))
    expect(scan()).toEqual(allowed)
  })

  it('names a reason for every entry', () => {
    for (const [file, { reason }] of Object.entries(ALLOW)) expect(reason.trim().length, file).toBeGreaterThan(10)
  })
})
