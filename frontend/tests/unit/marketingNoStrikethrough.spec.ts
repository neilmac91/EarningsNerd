import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { wordingHasContent } from '@/features/filings/lib/sectionChanges'
import { SAMPLE_CHANGE_REPORT } from '@/features/marketing/lib/landing-samples'
import { isLocal, lazyImport, resolveModule, routeFiles, walkImports } from './importWalk'

/**
 * Nothing on the landing page is struck through (the founder's review, 2026-10-22; D-058). The catch card struck
 * through $391.0B, Apple's correct FY2024 total net sales, as "From memory", while the table above showed the same
 * figure as the prior period: a filed figure marked as wrong, and a mark screen readers never heard. The landing's
 * figures are filed or calculated, never wrong.
 *
 * The scan reads every module the landing route reaches (app/page.tsx with the root layout, error and not-found
 * files, through the import graph, importWalk.ts, .js and .jsx modules included), so a shared component the landing
 * renders, such as the Financial Highlights table, is read as well as features/marketing. It reads every stylesheet
 * those modules name (an import, a CSS module's binding, an `export … from`, a `require()`, a lazy `import()`) and
 * every stylesheet those pull in: an `@import`, quoted or in a `url()` with or without quotes, and a CSS module's
 * `composes … from`. A bare path (`@import 'partials/x.css'`) is read against the sheet, as CSS reads it, when a file
 * is there; otherwise it names a package's sheet, which is not read. And, as the gate did before it walked the graph,
 * it reads every module and stylesheet in features/marketing.
 *
 * A module draws a strike-through with "line-through" (a class, or a CSS value in a style object, a template or a
 * stylesheet) or with an element that strikes through by default (<del>, <s> or <strike>, written as JSX, as markup in
 * a string, or through one of React's element makers: createElement, jsx, jsxs and jsxDEV, the compiled _jsx forms,
 * and any name a module imports or binds one to, `createElement as h`). Markup and CSS are read in any case
 * (`<DEL>`, `Line-Through`); a JSX tag in capitals names a component. Comments are not read. A class or tag built by
 * concatenation, a tag held in a variable, a maker handed in from another module, and markup set from data stay
 * review-checked; the e2e reflow spec reads the rendered evidence row's own text decoration. A Markdown renderer turns
 * data into elements no source holds (GFM's `~~` is a <del>), so the landing imports none, which a case below holds.
 *
 * One module keeps its strike-through by meaning: the change report's removed words (WordingChanges). The landing
 * reaches it by one path and does not render it: only WhatChanged renders it, for a report with a wording block, and
 * only the Change Report demo (ChangeReportDemo) renders WhatChanged, with a report that has none. The last case holds
 * that path. The pricing page's former price is on another route.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const ROOT_FILES = ['page.tsx', 'layout.tsx', 'template.tsx', 'loading.tsx', 'error.tsx', 'not-found.tsx']
const MARKETING = 'features/marketing'
const REMOVED_WORDS = 'features/filings/components/WordingChanges.tsx'
const WHAT_CHANGED = 'features/filings/components/WhatChanged.tsx'
const CHANGE_REPORT_DEMO = 'features/marketing/components/ChangeReportDemo.tsx'
const SUMMARY_RENDERER = 'features/summaries/components/SummaryDisplay.tsx'
// The Markdown renderers the app uses: each turns data into elements, and GFM's `~~` is a <del>.
const MARKDOWN = /^(?:react-markdown|remark-gfm|rehype-raw)(?:\/|$)/

const STRIKE_TAGS = new Set(['del', 's', 'strike'])
// "<s" alone would also match <span>, <section>, <svg> and <select>, so the tag must end there.
const STRIKE_TEXT = /line-through|<(?:del|s|strike)(?=[\s>/])/i
const STRIKE_CSS = /line-through/i
// React's element makers, by the name a module reads one from (`React.createElement`, a compiled module's `_jsx`).
const ELEMENT_MAKERS = new Set(['createElement', 'jsx', 'jsxs', 'jsxDEV', '_jsx', '_jsxs', '_jsxDEV'])

const scriptKind = (file: string) =>
  file.endsWith('.ts') ? ts.ScriptKind.TS : file.endsWith('.jsx') ? ts.ScriptKind.JSX : file.endsWith('.js') ? ts.ScriptKind.JS : ts.ScriptKind.TSX
const parse = (file: string, source: string) => ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, scriptKind(file))
const read = (file: string, root = FRONTEND) => readFileSync(path.join(root, file), 'utf8')
const withoutCssComments = (source: string) => source.replace(/\/\*[\s\S]*?\*\//g, '')

const textOf = (node: ts.Node): string | null =>
  ts.isStringLiteralLike(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node) || ts.isJsxText(node)
    ? node.text
    : null

/** The names a module makes elements with: React's makers, and each name it imports or binds one to
    (`import { createElement as h }`, `const h = React.createElement`, `const { createElement: h } = React`). */
function elementMakers(sf: ts.SourceFile): Set<string> {
  const names = new Set(ELEMENT_MAKERS)
  const visit = (node: ts.Node) => {
    if (ts.isImportSpecifier(node) && ELEMENT_MAKERS.has((node.propertyName ?? node.name).text)) names.add(node.name.text)
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer && ts.isPropertyAccessExpression(node.initializer)) {
      if (ELEMENT_MAKERS.has(node.initializer.name.text)) names.add(node.name.text)
    }
    if (ts.isBindingElement(node) && ts.isIdentifier(node.name)) {
      const taken = node.propertyName && ts.isIdentifier(node.propertyName) ? node.propertyName.text : node.name.text
      if (ELEMENT_MAKERS.has(taken)) names.add(node.name.text)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return names
}

const calleeName = (callee: ts.Expression) => (ts.isIdentifier(callee) ? callee.text : ts.isPropertyAccessExpression(callee) ? callee.name.text : null)

/** Whether a module or stylesheet draws a strike-through, read from its syntax, so a comment that names one does not. */
export function strikesIn(file: string, source: string): boolean {
  if (file.endsWith('.css')) return STRIKE_CSS.test(withoutCssComments(source))
  const sf = parse(file, source)
  const makers = elementMakers(sf)
  const strikes = (node: ts.Node): boolean => {
    const text = textOf(node)
    if (text !== null && STRIKE_TEXT.test(text)) return true
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && STRIKE_TAGS.has(node.tagName.getText(sf))) return true
    if (ts.isCallExpression(node) && makers.has(calleeName(node.expression) ?? '')) {
      const [tag] = node.arguments
      if (tag && ts.isStringLiteralLike(tag) && STRIKE_TAGS.has(tag.text.toLowerCase())) return true
    }
    return ts.forEachChild(node, (child) => strikes(child) || undefined) ?? false
  }
  return strikes(sf)
}

/** Every module a module names: its imports, its `export … from`s, its `require()`s and its lazy `import()`s. */
export function specifiersIn(file: string, source: string): string[] {
  const specs: string[] = []
  const visit = (node: ts.Node) => {
    if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) {
      specs.push(node.moduleSpecifier.text)
    }
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'require') {
      const [spec] = node.arguments
      if (spec && ts.isStringLiteralLike(spec)) specs.push(spec.text)
    }
    const lazy = lazyImport(node)
    if (lazy !== undefined) specs.push(lazy)
    ts.forEachChild(node, visit)
  }
  visit(parse(file, source))
  return specs
}

const fromFile = (file: string, spec: string) => (spec.startsWith('@/') ? spec.slice(2) : path.posix.join(path.posix.dirname(file), spec))

/** The local stylesheets a module names, in any form. */
export const stylesheetsIn = (file: string, source: string) =>
  specifiersIn(file, source)
    .filter((spec) => isLocal(spec) && /\.css$/i.test(spec))
    .map((spec) => fromFile(file, spec))

// `@import` as CSS takes it: a quoted path, or a `url()` with or without quotes.
const IMPORT_AT = /@import\s+(?:url\(\s*(['"]?)([^'")\s]+)\1\s*\)|(['"])([^'"]+)\3)/gi
// A CSS module's `composes: name from './x.module.css'`.
const COMPOSES_FROM = /composes\s*:[^;}]*?\bfrom\s+(['"])([^'"]+)\1/gi

/** The stylesheet a stylesheet's import names, relative to `root`, or null for an address (`https:`, `//`, `/`) or a
    package's sheet (`~pkg`, or a bare path that names no file beside the sheet). */
function sheetImport(sheet: string, spec: string, root: string): string | null {
  if (/^(?:[a-z][a-z\d+.-]*:|\/|~)/i.test(spec)) return null
  const target = fromFile(sheet, spec)
  return isLocal(spec) || existsSync(path.join(root, target)) ? target : null
}

/** The local stylesheets a stylesheet pulls in with `@import` or `composes … from`. */
export const cssImportsIn = (sheet: string, source: string, root = FRONTEND) => {
  const css = withoutCssComments(source)
  const specs = [...[...css.matchAll(IMPORT_AT)].map((match) => match[2] ?? match[4]), ...[...css.matchAll(COMPOSES_FROM)].map((match) => match[2])]
  return specs.map((spec) => sheetImport(sheet, spec, root)).filter((target): target is string => target !== null)
}

/** The stylesheets `sheets` reach through their own imports, `sheets` included. */
export function withCssImports(sheets: string[], root = FRONTEND): string[] {
  const seen = new Set<string>()
  const queue = [...sheets]
  while (queue.length) {
    const sheet = queue.shift()!
    if (seen.has(sheet)) continue
    seen.add(sheet)
    queue.push(...cssImportsIn(sheet, read(sheet, root), root))
  }
  return [...seen].sort()
}

/** Every module and stylesheet under `dir`, the gate's reading before it walked the import graph. */
function sources(dir: string, root: string, out: string[] = []): string[] {
  for (const entry of readdirSync(path.join(root, dir), { withFileTypes: true })) {
    const rel = `${dir}/${entry.name}`
    if (entry.isDirectory()) sources(rel, root, out)
    else if (/\.(?:[jt]sx?|css)$/.test(entry.name) && !entry.name.endsWith('.d.ts')) out.push(rel)
  }
  return out
}

/** What the scan reads under `root`: the modules the landing reaches, those and every module in features/marketing,
    and every stylesheet those name or features/marketing holds, with the stylesheets those pull in. */
export function landingReading(root = FRONTEND): { walked: string[]; modules: string[]; sheets: string[] } {
  const roots = routeFiles('app', ROOT_FILES, root).filter((file) => path.posix.dirname(file) === 'app')
  const walked = walkImports(roots, root)
  const marketing = existsSync(path.join(root, MARKETING)) ? sources(MARKETING, root) : []
  const modules = [...new Set([...walked, ...marketing.filter((file) => !file.endsWith('.css'))])].sort()
  const named = modules.flatMap((file) => stylesheetsIn(file, read(file, root)))
  const sheets = withCssImports([...new Set([...named, ...marketing.filter((file) => file.endsWith('.css'))])], root)
  return { walked, modules, sheets }
}

/** Writes `files` (path → source) under a new temporary root, runs `fn` on it, and removes it. */
function withTree(files: Record<string, string>, fn: (root: string) => void) {
  const root = mkdtempSync(path.join(tmpdir(), 'strike-walk-'))
  try {
    for (const [file, source] of Object.entries(files)) {
      mkdirSync(path.dirname(path.join(root, file)), { recursive: true })
      writeFileSync(path.join(root, file), source)
    }
    fn(root)
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
}

describe('the landing page strikes through no figure', () => {
  const { walked, modules, sheets } = landingReading()
  const importersOf = (target: string) => modules.filter((file) => specifiersIn(file, read(file)).some((spec) => resolveModule(FRONTEND, file, spec) === target))

  it('no module or stylesheet the landing reaches draws a strike-through', () => {
    expect(walked, 'the scan reads the landing route and the evidence row').toEqual(
      expect.arrayContaining(['app/page.tsx', 'features/marketing/components/EvidenceSection.tsx', 'features/summaries/components/FinancialMetricsTable.tsx']),
    )
    expect(modules.filter((file) => file.startsWith(`${MARKETING}/`)).length, 'the scan reads every marketing module').toBeGreaterThan(10)
    expect(sheets, 'the scan reads the stylesheets the landing imports').toContain('app/globals.css')
    expect([...modules, ...sheets].filter((file) => file !== REMOVED_WORDS && strikesIn(file, read(file)))).toEqual([])
  })

  it.each([
    ['a strike-through class', `export const A = () => <span className="line-through">$391.0B</span>`],
    ['a class in a template', 'export const A = ({ c }: { c: string }) => <span className={`${c} line-through`}>$391.0B</span>'],
    ['a style object', `export const A = () => <span style={{ textDecoration: 'line-through' }}>$391.0B</span>`],
    ['a style object’s longhand', `export const A = () => <span style={{ textDecorationLine: 'line-through' }}>$391.0B</span>`],
    ['a style value in capitals', `export const A = () => <span style={{ textDecoration: 'LINE-THROUGH' }}>$391.0B</span>`],
    ['a deletion', `export const A = () => <del>$391.0B</del>`],
    ['a strike element', `export const A = () => <s className="x">$391.0B</s>`],
    ['an old strike element', `export const A = () => <strike>$391.0B</strike>`],
    ['markup in a string', `export const A = () => <span dangerouslySetInnerHTML={{ __html: '<del>$391.0B</del>' }} />`],
    ['markup in capitals', `export const A = () => <span dangerouslySetInnerHTML={{ __html: '<S>$391.0B</S>' }} />`],
    ['an element made by createElement', `import { createElement } from 'react'\nexport const A = () => createElement('del', null, '$391.0B')`],
    ['an element made by React.createElement', `export const A = () => React.createElement('s', null, '$391.0B')`],
    ['an element named in capitals', `export const A = () => React.createElement('DEL', null, '$391.0B')`],
    ['an element made under an imported name', `import { createElement as h } from 'react'\nexport const A = () => h('del', null, '$391.0B')`],
    ['an element made by the JSX runtime', `import { jsx as _jsx } from 'react/jsx-runtime'\nexport const A = () => _jsx('s', { children: '$391.0B' })`],
    ['an element made by a compiled module’s maker', `export const A = () => _jsxs('strike', { children: ['$391.0B'] })`],
    ['an element made by a maker held in a constant', `const make = React.createElement\nexport const A = () => make('del', null, '$391.0B')`],
    ['an element made by a maker taken from React', `const { createElement: make } = React\nexport const A = () => make('del', null, '$391.0B')`],
  ])('fails a planted %s', (_, source) => {
    expect(strikesIn('features/x/Planted.tsx', source)).toBe(true)
  })

  it.each([
    ['a stylesheet rule', `.was { text-decoration: line-through; }`],
    ['a stylesheet @apply', `.was { @apply line-through; }`],
    ['a stylesheet value in another case', `.was { text-decoration: Line-Through; }`],
  ])('fails a planted %s', (_, source) => {
    expect(strikesIn('features/x/planted.module.css', source)).toBe(true)
  })

  it.each([
    ['a span', `export const A = () => <span>$391.0B</span>`],
    ['a section, an svg, a select, details and strong', `export const A = () => <section><svg viewBox="0 0 1 1" /><select /><details /><strong>$391.0B</strong></section>`],
    ['a comment that names a strike-through', `// No line-through here: the figure is filed.\nexport const A = () => <span>$391.0B</span>`],
    ['a JSX comment holding markup', `export const A = () => <p>{/* was <del>$391.0B</del> */}$416.2B</p>`],
    ['a block comment holding a tag', `/* <s>old</s> */\nexport const A = () => <span>$416.2B</span>`],
    ['an element whose name starts like one', `export const A = () => <Sparkline data={[]} />`],
    ['a component named in capitals', `export const A = ({ S }: { S: () => null }) => <S />`],
    ['a call that is no element maker', `export const A = ({ t }: { t: (key: string) => string }) => <span>{t('s')}</span>`],
  ])('passes %s, which strikes nothing through', (_, source) => {
    expect(strikesIn('features/x/Planted.tsx', source)).toBe(false)
  })

  it('reads a strike-through after an address on the same line, which a comment strip by pattern would hide', () => {
    expect(strikesIn('features/x/Planted.tsx', `export const A = () => <a href="https://www.sec.gov" className="line-through">$391.0B</a>`)).toBe(true)
  })

  it('passes a stylesheet comment that names a strike-through', () => {
    expect(strikesIn('features/x/planted.css', `/* no line-through on figures */\n.figure { font-weight: 500; }`)).toBe(false)
  })

  it('finds every stylesheet a module names, and the ones a stylesheet pulls in', () => {
    const planted = [
      `import styles from './figure.module.css'`,
      `import '@/app/extra.css'`,
      `import { tokens } from './tokens'`,
      `import 'katex/dist/katex.min.css'`,
      `const Lazy = () => import('./lazy.css')`,
      `const legacy = require('./legacy.module.css')`,
      `export { default as panel } from './panel.module.css'`,
    ].join('\n')
    expect(stylesheetsIn('features/x/Planted.tsx', planted)).toEqual([
      'features/x/figure.module.css',
      'app/extra.css',
      'features/x/lazy.css',
      'features/x/legacy.module.css',
      'features/x/panel.module.css',
    ])
    const sheet = [
      `@tailwind base;`,
      `@import './partials/figures.css';`,
      `@import url("../shared.css");`,
      `@import url(./unquoted.css) layer(base);`,
      `@import 'katex/dist/katex.min.css';`,
      `@import url(https://fonts.googleapis.com/css2?family=Inter);`,
      `.figure { composes: base from './base.module.css'; }`,
      `/* @import './old.css'; */`,
    ].join('\n')
    expect(cssImportsIn('app/globals.css', sheet)).toEqual(['app/partials/figures.css', 'shared.css', 'app/unquoted.css', 'app/base.module.css'])
  })

  it('reads every marketing module and stylesheet, follows each stylesheet’s imports, and walks into a .jsx module', () => {
    withTree(
      {
        'app/page.tsx': `import Hero from '@/features/x/Hero'\nimport './landing.css'\nexport default function Page() { return <Hero /> }`,
        'app/landing.css': `@import url(./partials/a.css);`,
        'app/partials/a.css': `@import 'b.css';`,
        'app/partials/b.css': `.was { text-decoration: LINE-THROUGH; }`,
        'features/x/Hero.jsx': `export default function Hero() { return <del>$391.0B</del> }`,
        'features/marketing/Unused.tsx': `export const U = () => <s>$391.0B</s>`,
        'features/marketing/unused.css': `.was { text-decoration: line-through; }`,
      },
      (root) => {
        const reading = landingReading(root)
        expect(reading.walked).toEqual(['app/page.tsx', 'features/x/Hero.jsx'])
        expect(reading.modules).toEqual(['app/page.tsx', 'features/marketing/Unused.tsx', 'features/x/Hero.jsx'])
        expect(reading.sheets).toEqual(['app/landing.css', 'app/partials/a.css', 'app/partials/b.css', 'features/marketing/unused.css'])
        expect([...reading.modules, ...reading.sheets].filter((file) => strikesIn(file, read(file, root)))).toEqual([
          'features/marketing/Unused.tsx',
          'features/x/Hero.jsx',
          'app/partials/b.css',
          'features/marketing/unused.css',
        ])
      },
    )
  })

  it('renders no Markdown, whose elements no source holds', () => {
    // A landing that must render Markdown reads the data it renders for GFM's `~~` here first.
    expect(specifiersIn(SUMMARY_RENDERER, read(SUMMARY_RENDERER)).filter((spec) => MARKDOWN.test(spec)), 'the pattern names the app’s renderers').toEqual([
      'react-markdown',
      'remark-gfm',
    ])
    expect(modules.filter((file) => specifiersIn(file, read(file)).some((spec) => MARKDOWN.test(spec)))).toEqual([])
  })

  it('keeps its one exemption only while the landing reaches it by one path and does not render it', () => {
    // An exemption the landing no longer reaches is a stale entry: delete it here. One the landing renders is a
    // strike-through on the landing: WhatChanged shows WordingChanges only for a report with a wording block
    // (wordingHasContent), and the Change Report demo hands it a report with none.
    expect(walked).toContain(REMOVED_WORDS)
    expect(strikesIn(REMOVED_WORDS, read(REMOVED_WORDS))).toBe(true)
    expect(importersOf(REMOVED_WORDS)).toEqual([WHAT_CHANGED])
    expect(importersOf(WHAT_CHANGED)).toEqual([CHANGE_REPORT_DEMO])
    const demo = parse(CHANGE_REPORT_DEMO, read(CHANGE_REPORT_DEMO))
    const reports: string[] = []
    const visit = (node: ts.Node) => {
      if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(demo) === 'WhatChanged') {
        for (const attribute of node.attributes.properties) {
          if (ts.isJsxSpreadAttribute(attribute)) reports.push(attribute.getText(demo))
          else if (attribute.name.getText(demo) === 'report') reports.push(attribute.initializer?.getText(demo) ?? '')
        }
      }
      ts.forEachChild(node, visit)
    }
    visit(demo)
    expect(reports).toEqual(['{SAMPLE_CHANGE_REPORT}'])
    expect(wordingHasContent(SAMPLE_CHANGE_REPORT.section_changes)).toBe(false)
  })
})
