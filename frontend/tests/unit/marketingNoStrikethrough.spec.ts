import { mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { wordingHasContent } from '@/features/filings/lib/sectionChanges'
import { SAMPLE_CHANGE_REPORT } from '@/features/marketing/lib/landing-samples'
import { isLocal, lazyImport, routeFiles, walkImports } from './importWalk'

/**
 * Nothing on the landing page is struck through (the founder's review, 2026-10-22; D-058). The catch card struck
 * through $391.0B, Apple's correct FY2024 total net sales, as "From memory", while the table above showed the same
 * figure as the prior period: a filed figure marked as wrong, and a mark screen readers never heard. The landing's
 * figures are filed or calculated, never wrong.
 *
 * The scan reads every module the landing route reaches (app/page.tsx with the root layout, error and not-found
 * files, through the import graph, importWalk.ts, .js and .jsx modules included), so a shared component the landing
 * renders, such as the Financial Highlights table, is read as well as features/marketing. It also reads every stylesheet those modules import, in any
 * form (`import './globals.css'`, a CSS module's `import styles from './x.module.css'`, a stylesheet's own `@import`),
 * and, as the gate did before it walked the graph, every module and stylesheet in features/marketing.
 *
 * A module draws a strike-through with "line-through" (a class, or a CSS value in a style object, a template or a
 * stylesheet) or with an element that strikes through by default (<del>, <s> or <strike>, written as JSX, as markup in
 * a string, or through createElement). Comments are not read. A class or tag built by concatenation, or a tag held in a
 * variable, stays review-checked; the e2e reflow spec reads the rendered evidence row's own text decoration.
 *
 * One module keeps its strike-through by meaning: the change report's removed words (WordingChanges). The summary
 * renderer's imports reach it, and the landing does not render it: its Change Report demo (ChangeReportDemo) passes a
 * report with no wording block, which the last case checks. The pricing page's former price is on another route.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const ROOT_FILES = ['page.tsx', 'layout.tsx', 'template.tsx', 'loading.tsx', 'error.tsx', 'not-found.tsx']
const LANDING_ROOTS = routeFiles('app', ROOT_FILES, FRONTEND).filter((file) => path.posix.dirname(file) === 'app')
const MARKETING = 'features/marketing'
const REMOVED_WORDS = 'features/filings/components/WordingChanges.tsx'

const STRIKE_TAGS = new Set(['del', 's', 'strike'])
// "<s" alone would also match <span>, <section>, <svg> and <select>, so the tag must end there.
const STRIKE_TEXT = /line-through|<(?:del|s|strike)(?=[\s>/])/
const CREATES_ELEMENT = /(?:^|\.)(?:createElement|jsxs?|jsxDEV)$/

const scriptKind = (file: string) =>
  file.endsWith('.ts') ? ts.ScriptKind.TS : file.endsWith('.jsx') ? ts.ScriptKind.JSX : file.endsWith('.js') ? ts.ScriptKind.JS : ts.ScriptKind.TSX
const parse = (file: string, source: string) => ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, scriptKind(file))
const read = (file: string) => readFileSync(path.join(FRONTEND, file), 'utf8')

const textOf = (node: ts.Node): string | null =>
  ts.isStringLiteralLike(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node) || ts.isJsxText(node)
    ? node.text
    : null

/** Whether a module or stylesheet draws a strike-through, read from its syntax, so a comment that names one does not. */
export function strikesIn(file: string, source: string): boolean {
  if (file.endsWith('.css')) return /line-through/.test(source.replace(/\/\*[\s\S]*?\*\//g, ''))
  const sf = parse(file, source)
  const strikes = (node: ts.Node): boolean => {
    const text = textOf(node)
    if (text !== null && STRIKE_TEXT.test(text)) return true
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && STRIKE_TAGS.has(node.tagName.getText(sf))) return true
    if (ts.isCallExpression(node) && CREATES_ELEMENT.test(node.expression.getText(sf))) {
      const [tag] = node.arguments
      if (tag && ts.isStringLiteralLike(tag) && STRIKE_TAGS.has(tag.text)) return true
    }
    return ts.forEachChild(node, (child) => strikes(child) || undefined) ?? false
  }
  return strikes(sf)
}

const fromFile = (file: string, spec: string) => (spec.startsWith('@/') ? spec.slice(2) : path.posix.join(path.posix.dirname(file), spec))

/** The local stylesheets a module imports, in any form: a side-effect import, a CSS module's binding, a lazy import(). */
export function stylesheetsIn(file: string, source: string): string[] {
  const specs: string[] = []
  const visit = (node: ts.Node) => {
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) specs.push(node.moduleSpecifier.text)
    const lazy = lazyImport(node)
    if (lazy !== undefined) specs.push(lazy)
    ts.forEachChild(node, visit)
  }
  visit(parse(file, source))
  return specs.filter((spec) => isLocal(spec) && spec.endsWith('.css')).map((spec) => fromFile(file, spec))
}

/** The local stylesheets a stylesheet pulls in with `@import`. */
export const cssImportsIn = (sheet: string, source: string) =>
  [...source.replace(/\/\*[\s\S]*?\*\//g, '').matchAll(/@import\s+(?:url\(\s*)?['"]([^'"]+\.css)['"]/g)]
    .map(([, spec]) => spec)
    .filter(isLocal)
    .map((spec) => fromFile(sheet, spec))

/** The stylesheets `sheets` reach through their own `@import`s, `sheets` included. */
function withCssImports(sheets: string[]): string[] {
  const seen = new Set<string>()
  const queue = [...sheets]
  while (queue.length) {
    const sheet = queue.shift()!
    if (seen.has(sheet)) continue
    seen.add(sheet)
    queue.push(...cssImportsIn(sheet, read(sheet)))
  }
  return [...seen].sort()
}

/** Every module and stylesheet under `dir`, the gate's reading before it walked the import graph. */
function sources(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(path.join(FRONTEND, dir), { withFileTypes: true })) {
    const rel = `${dir}/${entry.name}`
    if (entry.isDirectory()) sources(rel, out)
    else if (/\.(?:[jt]sx?|css)$/.test(entry.name) && !entry.name.endsWith('.d.ts')) out.push(rel)
  }
  return out
}

describe('the landing page strikes through no figure', () => {
  const walked = walkImports(LANDING_ROOTS, FRONTEND)
  const marketing = sources(MARKETING)
  const modules = [...new Set([...walked, ...marketing.filter((file) => !file.endsWith('.css'))])].sort()
  const imported = modules.flatMap((file) => stylesheetsIn(file, read(file)))
  const sheets = withCssImports([...new Set([...imported, ...marketing.filter((file) => file.endsWith('.css'))])])

  it('no module or stylesheet the landing reaches draws a strike-through', () => {
    expect(walked, 'the scan reads the landing route and the evidence row').toEqual(
      expect.arrayContaining(['app/page.tsx', 'features/marketing/components/EvidenceSection.tsx', 'features/summaries/components/FinancialMetricsTable.tsx']),
    )
    expect(marketing.length, 'the scan reads every marketing module').toBeGreaterThan(10)
    expect(sheets, 'the scan reads the stylesheets the landing imports').toContain('app/globals.css')
    expect([...modules, ...sheets].filter((file) => file !== REMOVED_WORDS && strikesIn(file, read(file)))).toEqual([])
  })

  it.each([
    ['a strike-through class', `export const A = () => <span className="line-through">$391.0B</span>`],
    ['a class in a template', 'export const A = ({ c }: { c: string }) => <span className={`${c} line-through`}>$391.0B</span>'],
    ['a style object', `export const A = () => <span style={{ textDecoration: 'line-through' }}>$391.0B</span>`],
    ['a style object’s longhand', `export const A = () => <span style={{ textDecorationLine: 'line-through' }}>$391.0B</span>`],
    ['a deletion', `export const A = () => <del>$391.0B</del>`],
    ['a strike element', `export const A = () => <s className="x">$391.0B</s>`],
    ['an old strike element', `export const A = () => <strike>$391.0B</strike>`],
    ['markup in a string', `export const A = () => <span dangerouslySetInnerHTML={{ __html: '<del>$391.0B</del>' }} />`],
    ['an element made by createElement', `import { createElement } from 'react'\nexport const A = () => createElement('del', null, '$391.0B')`],
    ['an element made by React.createElement', `export const A = () => React.createElement('s', null, '$391.0B')`],
  ])('fails a planted %s', (_, source) => {
    expect(strikesIn('features/x/Planted.tsx', source)).toBe(true)
  })

  it.each([
    ['a stylesheet rule', `.was { text-decoration: line-through; }`],
    ['a stylesheet @apply', `.was { @apply line-through; }`],
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
  ])('passes %s, which strikes nothing through', (_, source) => {
    expect(strikesIn('features/x/Planted.tsx', source)).toBe(false)
  })

  it('reads a strike-through after an address on the same line, which a comment strip by pattern would hide', () => {
    expect(strikesIn('features/x/Planted.tsx', `export const A = () => <a href="https://www.sec.gov" className="line-through">$391.0B</a>`)).toBe(true)
  })

  it('passes a stylesheet comment that names a strike-through', () => {
    expect(strikesIn('features/x/planted.css', `/* no line-through on figures */\n.figure { font-weight: 500; }`)).toBe(false)
  })

  it('finds every stylesheet a module imports, and the ones a stylesheet imports', () => {
    const planted = [
      `import styles from './figure.module.css'`,
      `import '@/app/extra.css'`,
      `import { tokens } from './tokens'`,
      `import 'katex/dist/katex.min.css'`,
      `const Lazy = () => import('./lazy.css')`,
    ].join('\n')
    expect(stylesheetsIn('features/x/Planted.tsx', planted)).toEqual(['features/x/figure.module.css', 'app/extra.css', 'features/x/lazy.css'])
    expect(cssImportsIn('app/globals.css', `@tailwind base;\n@import './partials/figures.css';\n@import url("../shared.css");\n/* @import './old.css'; */`)).toEqual([
      'app/partials/figures.css',
      'shared.css',
    ])
  })

  it('walks into a .jsx module the landing imports (allowJs), and reads it', () => {
    const root = mkdtempSync(path.join(tmpdir(), 'strike-walk-'))
    try {
      for (const dir of ['app', 'features/x']) mkdirSync(path.join(root, dir), { recursive: true })
      writeFileSync(path.join(root, 'app/page.tsx'), `import Hero from '@/features/x/Hero'\nexport default function Page() { return <Hero /> }`)
      writeFileSync(path.join(root, 'features/x/Hero.jsx'), `export default function Hero() { return <del>$391.0B</del> }`)
      expect(walkImports(['app/page.tsx'], root)).toEqual(['app/page.tsx', 'features/x/Hero.jsx'])
      expect(strikesIn('features/x/Hero.jsx', readFileSync(path.join(root, 'features/x/Hero.jsx'), 'utf8'))).toBe(true)
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })

  it('keeps its one exemption only while the landing reaches it and does not render it', () => {
    // An exemption the landing no longer reaches is a stale entry: delete it here. One the landing renders is a
    // strike-through on the landing: the Change Report demo's report must carry no wording block (WhatChanged shows
    // WordingChanges only for one, wordingHasContent).
    expect(walked).toContain(REMOVED_WORDS)
    expect(strikesIn(REMOVED_WORDS, read(REMOVED_WORDS))).toBe(true)
    expect(wordingHasContent(SAMPLE_CHANGE_REPORT.section_changes)).toBe(false)
  })
})
