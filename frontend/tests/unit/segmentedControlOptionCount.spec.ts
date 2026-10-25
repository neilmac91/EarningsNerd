/* =============================================================================
   segmentedControlOptionCount.spec.ts: a long set of options is a select
   -----------------------------------------------------------------------------
   DESIGN.md (the SegmentedControl paragraph): "A long set of options, such as a
   chart's metric picker, is not a segmented control: it is a compact select sized
   to its content beside its label". The company page's metric pickers (nine and
   up to 23 options) left the control for that select in #1292; this gate keeps
   the next long set from arriving as segments.

   The cap is five options: MAX_SEGMENTS, exported by the primitive
   (components/ui/SegmentedControl.tsx) and read here as MAX_OPTIONS, so the
   component and this gate cannot drift apart. Every segment shows at once and a
   label never breaks, so the set has to be taken in at a glance on a phone at
   200% text. Five is the most the control holds by design, the filings form
   filter of a domestic filer (All, 10-K, 10-Q, 10-K/A, 10-Q/A), and the usual
   ceiling for the pattern (Apple's HIG: about five segments on iPhone; Material's
   segmented button: "only 2-5 options", chips past five). Six or more is a menu,
   and a menu is the select. The rule holds at run time too: the filings form
   filter is All plus the company's forms, a set this scan cannot count, so it is
   pinned in UNRESOLVED, and FilingIndex counts it as it renders: past
   MAX_SEGMENTS options (a filer with both domestic and foreign forms) it renders
   the toolbar's compact select instead, so its SegmentedControl never shows more
   than five (FilingIndex.spec.tsx renders both sides). The sites today: the
   insider window 3 (90D, 180D, 1Y) and the calendar view 2 (Week, Month), both
   counted; the filings form filter, pinned; the five other sites hold two or
   three (the analysis mode, the feedback form's type, and the
   comparison source, review scope and evidence workspace switches of three
   prototypes).

   The scan reads the TypeScript AST of every .tsx under app/, components/ and
   features/, finds each <SegmentedControl> (an import renamed with `as`, and
   `ui.SegmentedControl`, included) and counts its `options` prop when the count
   is static: an array literal (a spread adds the count of the array it spreads),
   a same-file const array (through `as const`, `satisfies` and a type annotation)
   or a `.map` over one. A site it cannot count is pinned per file in UNRESOLVED
   with its reason, shrink-only, or the spec fails naming it: no site is skipped.

   Limits: a wrapper component that renders the control from its own props is a
   site the scan cannot count (pin it with its reason); a `.filter` or a slice is
   not followed; a control rendered without JSX (createElement) is not seen.
============================================================================= */

import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { MAX_SEGMENTS } from '@/components/ui/SegmentedControl'
import { bindingResolver, type Binding } from './astBindings'

const ROOT = path.join(__dirname, '../..')
const SCAN_DIRS = ['app', 'components', 'features']
const CONTROL = 'SegmentedControl'
// The primitive's own cap, so raising it there moves this gate with it, and the pin below fails.
const MAX_OPTIONS = MAX_SEGMENTS

// Shrink-only: lower MAX_UNRESOLVED when an entry goes; never raise it to fit a new site.
const MAX_UNRESOLVED = 1
const UNRESOLVED: Record<string, { sites: number; reason: string }> = {
  'features/filings/components/FilingIndex.tsx': {
    sites: 1,
    reason:
      'The form filter is "All" plus the distinct forms of the loaded list (sortForms over the filings), a set ' +
      'known only at run time, so this scan cannot count it. FilingIndex counts it as it renders: the list serves ' +
      '10-K, 10-Q and their amendments, and 20-F, 6-K and 40-F with FPI filings on, so a domestic filer shows five ' +
      'segments (All, 10-K, 10-Q, 10-K/A, 10-Q/A), and past MAX_SEGMENTS options (a filer with both domestic and ' +
      'foreign forms) the filter renders as the toolbar\'s compact select instead. This SegmentedControl holds at ' +
      'most five segments (FilingIndex.spec.tsx renders both sides).',
  },
}

/** One <SegmentedControl> in a source file: its 1-based line, its `label`, and its option count or why there is none. */
interface Site {
  line: number
  label: string | null
  count: number | null
  why?: string
}

type Counted = { count: number } | { why: string }

const unwrap = (e: ts.Expression): ts.Expression => {
  while (
    ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isSatisfiesExpression(e) ||
    ts.isNonNullExpression(e) || ts.isTypeAssertionExpression(e)
  ) {
    e = e.expression
  }
  return e
}

/** A same-file `const` declaration's initializer (never `let`, `var` or `using`). */
function constInit(binding: Binding | undefined): ts.Expression | undefined {
  const decl = binding?.decl
  if (!decl || !ts.isVariableDeclaration(decl) || !ts.isVariableDeclarationList(decl.parent)) return undefined
  return (decl.parent.flags & ts.NodeFlags.BlockScoped) === ts.NodeFlags.Const ? decl.initializer : undefined
}

/** The static length of an `options` value, or the expression the count stopped at. */
function countOptions(
  value: ts.Expression,
  resolve: (ref: ts.Identifier) => Binding | undefined,
  sf: ts.SourceFile,
  seen: ReadonlySet<ts.Node> = new Set(),
): Counted {
  const e = unwrap(value)
  if (ts.isArrayLiteralExpression(e)) {
    let count = 0
    for (const element of e.elements) {
      if (!ts.isSpreadElement(element)) {
        count += 1
        continue
      }
      const spread = countOptions(element.expression, resolve, sf, seen)
      if ('why' in spread) return spread
      count += spread.count
    }
    return { count }
  }
  if (ts.isIdentifier(e)) {
    const init = constInit(resolve(e))
    if (!init || seen.has(init)) return { why: `${e.text} is not a same-file const array` }
    return countOptions(init, resolve, sf, new Set(seen).add(init))
  }
  // `.map` keeps the length of the array it maps.
  if (ts.isCallExpression(e) && ts.isPropertyAccessExpression(e.expression) && e.expression.name.text === 'map') {
    return countOptions(e.expression.expression, resolve, sf, seen)
  }
  return { why: e.getText(sf).replace(/\s+/g, ' ').slice(0, 80) }
}

/** Every <SegmentedControl> in a source file, in order, counted where the count is static. */
function readSites(source: string, fileName = 'probe.tsx'): Site[] {
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const resolve = bindingResolver(sf)
  // The local names the control goes by in this file: its own, and any `import { SegmentedControl as X }`.
  const names = new Set([CONTROL])
  for (const statement of sf.statements) {
    const bindings = ts.isImportDeclaration(statement) ? statement.importClause?.namedBindings : undefined
    if (!bindings || !ts.isNamedImports(bindings)) continue
    for (const spec of bindings.elements) if ((spec.propertyName ?? spec.name).text === CONTROL) names.add(spec.name.text)
  }
  const isControl = (tag: ts.JsxTagNameExpression) =>
    ts.isIdentifier(tag) ? names.has(tag.text) : ts.isPropertyAccessExpression(tag) && tag.name.text === CONTROL
  const attribute = (attributes: ts.JsxAttributes, name: string) =>
    attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText(sf) === name)

  const sites: Site[] = []
  const visit = (node: ts.Node): void => {
    if ((ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) && isControl(node.tagName)) {
      const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
      const labelInit = attribute(node.attributes, 'label')?.initializer
      const label = labelInit && ts.isStringLiteral(labelInit) ? labelInit.text : null
      const optionsInit = attribute(node.attributes, 'options')?.initializer
      const value = optionsInit && ts.isJsxExpression(optionsInit) ? optionsInit.expression : undefined
      const counted: Counted = value ? countOptions(value, resolve, sf) : { why: 'no options={...} attribute' }
      sites.push('count' in counted ? { line, label, count: counted.count } : { line, label, count: null, why: counted.why })
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return sites
}

const overCap = (sites: Site[]) => sites.filter((site) => site.count !== null && site.count > MAX_OPTIONS)

function walk(dir: string, out: string[] = []): string[] {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name)
    if (fs.statSync(p).isDirectory()) walk(p, out)
    else if (p.endsWith('.tsx')) out.push(p)
  }
  return out
}

function scan(): Map<string, Site[]> {
  const found = new Map<string, Site[]>()
  for (const file of SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))) {
    const sites = readSites(fs.readFileSync(file, 'utf8'), file)
    if (sites.length) found.set(path.relative(ROOT, file).split(path.sep).join('/'), sites)
  }
  return found
}

const PROBE = `import { SegmentedControl } from '@/components/ui'

const SIX = [
  { value: 'a', label: 'A' }, { value: 'b', label: 'B' }, { value: 'c', label: 'C' },
  { value: 'd', label: 'D' }, { value: 'e', label: 'E' }, { value: 'f', label: 'F' },
] as const
const WINDOWS: { days: number; label: string }[] = [
  { days: 90, label: '90D' },
  { days: 180, label: '180D' },
  { days: 365, label: '1Y' },
]

export function Probe() {
  return (
    <>
      <SegmentedControl label="Six" options={SIX} value="a" onChange={() => {}} />
      <SegmentedControl<string>
        label="Three"
        options={WINDOWS.map((w) => ({ value: String(w.days), label: w.label }))}
        value="90"
        onChange={() => {}}
      />
    </>
  )
}
`

const FORMS_PROBE = `import { SegmentedControl as Toggle } from '@/components/ui'
import * as ui from '@/components/ui'

let mutable = [{ value: 'a', label: 'A' }]
const TWO = [{ value: 'x', label: 'X' }, { value: 'y', label: 'Y' }] satisfies { value: string; label: string }[]

export function Probe({ forms }: { forms: string[] }) {
  const local = [{ value: 'one', label: 'One' }]
  return (
    <>
      <Toggle label="From a prop" options={forms.map((f) => ({ value: f, label: f }))} value="" onChange={() => {}} />
      <Toggle label="Mutable" options={mutable} value="a" onChange={() => {}} />
      <Toggle label="Spread" options={[{ value: 'all', label: 'All' }, ...TWO]} value="all" onChange={() => {}} />
      <ui.SegmentedControl label="Local" options={local} value="one" onChange={() => {}} />
    </>
  )
}
`

describe('the cap', () => {
  it('is five, the number DESIGN.md states, read from the primitive', () => {
    expect(MAX_OPTIONS, 'DESIGN.md: a SegmentedControl holds at most five options; a longer set is a select').toBe(5)
  })
})

describe('the option reader', () => {
  it('counts a six-option site and a three-option site in a fixed probe, and only the six is over the cap', () => {
    const sites = readSites(PROBE)
    expect(sites).toEqual([
      { line: 16, label: 'Six', count: 6 },
      { line: 17, label: 'Three', count: 3 },
    ])
    expect(overCap(sites).map((site) => site.label)).toEqual(['Six'])
  })

  it('reports a site it cannot count, never skipping it, and reads a renamed import, a namespace, a spread and a local const', () => {
    expect(readSites(FORMS_PROBE)).toEqual([
      { line: 11, label: 'From a prop', count: null, why: 'forms is not a same-file const array' },
      { line: 12, label: 'Mutable', count: null, why: 'mutable is not a same-file const array' },
      { line: 13, label: 'Spread', count: 3 },
      { line: 14, label: 'Local', count: 1 },
    ])
  })
})

describe('SegmentedControl option count (DESIGN.md: a long set of options is a compact select)', () => {
  const found = scan()
  const all = [...found].flatMap(([file, sites]) => sites.map((site) => ({ file, ...site })))
  const uncounted = (file: string) => (found.get(file) ?? []).filter((site) => site.count === null)

  it(`no site holds more than ${MAX_OPTIONS} options`, () => {
    const over = all
      .filter((site) => site.count !== null && site.count > MAX_OPTIONS)
      .map((site) => `${site.file}:${site.line} "${site.label}" has ${site.count} options`)
    expect(
      over,
      'A long set of options is a compact select sized to its content beside its label, not a SegmentedControl ' +
        '(DESIGN.md, the SegmentedControl paragraph; the company page metric pickers are the recipe).',
    ).toEqual([])
  })

  it('counts every site statically, or its file pins it in UNRESOLVED with a reason', () => {
    const unpinned = [...found.keys()]
      .filter((file) => uncounted(file).length > (UNRESOLVED[file]?.sites ?? 0))
      .flatMap((file) => uncounted(file).map((site) => `${file}:${site.line} "${site.label}": ${site.why}`))
    expect(
      unpinned,
      'Pass a static options array (a literal, or a same-file const), or pin the file in UNRESOLVED with why its ' +
        'set stays within the cap.',
    ).toEqual([])
  })

  it('reads the sites the rule was written for: the insider window 3, the calendar view 2, the filings form filter pinned', () => {
    expect(found.get('features/insiders/components/InsiderActivityPanel.tsx')?.map((site) => [site.label, site.count])).toEqual([
      ['Time window', 3],
    ])
    expect(found.get('features/calendar/components/EarningsCalendarPage.tsx')?.map((site) => [site.label, site.count])).toEqual([
      ['Calendar view', 2],
    ])
    expect(uncounted('features/filings/components/FilingIndex.tsx').map((site) => site.label)).toEqual(['Filter by form'])
  })

  it.each(Object.entries(UNRESOLVED))('%s still has its pinned uncounted sites (lower the pin as they go)', (file, { sites }) => {
    expect(uncounted(file).length).toBe(sites)
  })

  it('UNRESOLVED is shrink-only, and every entry has a reason', () => {
    expect(Object.keys(UNRESOLVED).length).toBe(MAX_UNRESOLVED)
    for (const [file, { reason }] of Object.entries(UNRESOLVED)) expect(reason.trim().length, file).toBeGreaterThan(0)
  })
})
