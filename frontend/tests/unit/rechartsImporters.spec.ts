import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/** Recharts reaches only the two charts not yet on the engine, and the analysis route loads none of it (E195).
 *  Shrink-only: moving either onto the engine deletes its line. The source is parsed, not text-matched
 *  (lessons/test-gates-must-be-as-wide-as-their-rule.md), in every script the repository tracks outside the test homes,
 *  in every extension `allowJs` admits. Whatever loads a module names it by a string, so the gate reads every string a
 *  script holds rather than a list of loaders: an import, `require()`, a require `createRequire()` makes under any name,
 *  AMD's `define([…])` and a worker's `new URL(…)` each hold one. A string naming recharts marks its file, and one naming
 *  a module the repository holds (`@/…`, `./…`, `../…`) is an edge the route walk follows. What no string shows fails
 *  the gate: an `import()` or `require()` of a computed specifier, a folder's context (`require.context()`,
 *  `import.meta.webpackContext()`), and an import of a local module the repository does not hold. Out of reach, planted
 *  below as gaps: a name no script holds (a bundler alias in `next.config.js`), and a computed specifier handed to any
 *  other loader. */
const IMPORTERS = [
  'features/fundamentals/components/FundamentalsTrendChart.tsx',
  'features/peers/components/PeerComparisonPanel.tsx',
]
/** The scripts that name recharts without loading it: Next's config transpiles the package. */
const MENTIONS = ['next.config.js']
/** What the analysis route loads with nothing importing it: each of the App Router's special files in the root segment
 *  (every route's, the home page aside) and in the route's own segment, and the client instrumentation every page loads. */
const CONVENTIONS = ['layout', 'template', 'error', 'global-error', 'loading', 'not-found', 'global-not-found', 'forbidden', 'unauthorized', 'default']
const SEGMENTS = [{ dir: 'app', names: CONVENTIONS }, { dir: 'app/analysis', names: [...CONVENTIONS, 'page'] }]

const SCRIPT = /\.(?:[cm]?[jt]sx?)$/
const EXTENSIONS = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.mts', '.cts']
const LOCAL = /^(?:@\/|\.{1,2}\/)/
const isRecharts = (specifier: string) => /^recharts(?:\/|$)/.test(specifier)

/** What a source names. `strings`: every string it holds (a comment holds none). `imports`: the ones an import, an
 *  export, `import x = require()`, an import type, `import()` or `require()` names, which must resolve. `opaque`, as
 *  source text: an `import()` or `require()` of a computed specifier, and a folder's context. */
function specifiers(fileName: string, source: string): { strings: string[]; imports: string[]; opaque: string[] } {
  const file = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, fileName.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const strings: string[] = []
  const imports: string[] = []
  const opaque: string[] = []
  const named = (node: ts.Node | undefined) => (node && ts.isStringLiteralLike(node) ? node.text : undefined)
  const imported = (node: ts.Node | undefined) => { const name = named(node); if (name !== undefined) imports.push(name) }
  const isRequire = (node: ts.Expression) => ts.isIdentifier(node) && node.text === 'require'
  const visit = (node: ts.Node) => {
    if (ts.isStringLiteralLike(node)) strings.push(node.text)
    if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier) imported(node.moduleSpecifier)
    if (ts.isImportEqualsDeclaration(node) && ts.isExternalModuleReference(node.moduleReference)) imported(node.moduleReference.expression)
    if (ts.isImportTypeNode(node) && ts.isLiteralTypeNode(node.argument)) imported(node.argument.literal)
    if (ts.isCallExpression(node)) {
      const callee = node.expression
      if (callee.kind === ts.SyntaxKind.ImportKeyword || isRequire(callee)) {
        if (named(node.arguments[0]) === undefined) opaque.push(node.getText(file))
        else imported(node.arguments[0])
      }
      if (ts.isPropertyAccessExpression(callee) && (isRequire(callee.expression) || ts.isMetaProperty(callee.expression))
        && (callee.name.text === 'context' || callee.name.text === 'webpackContext')) opaque.push(node.getText(file))
    }
    ts.forEachChild(node, visit)
  }
  visit(file)
  return { strings, imports, opaque }
}

/** A module the repository holds, as `@/…` or a relative path names it: its file, undefined when none matches; null for a
 *  package. */
function resolve(from: string, specifier: string): string | null | undefined {
  const base = specifier.startsWith('@/') ? specifier.slice(2)
    : specifier.startsWith('.') ? path.join(path.dirname(from), specifier) : null
  if (base == null) return null
  const candidates = [base, ...EXTENSIONS.map((extension) => base + extension), ...EXTENSIONS.map((extension) => path.join(base, `index${extension}`))]
  return candidates.find((candidate) => existsSync(candidate) && statSync(candidate).isFile())
}

describe('recharts importers', () => {
  const tracked = execFileSync('git', ['ls-files'], { encoding: 'utf8' }).split('\n')
    .filter((file) => SCRIPT.test(file) && !file.startsWith('tests/'))
  const routeEntries = [
    ...SEGMENTS.flatMap(({ dir, names }) => tracked.filter((file) => path.dirname(file) === dir && names.includes(path.basename(file).replace(SCRIPT, '')))),
    'instrumentation-client.ts',
  ]

  it('reads every string a module can be named by, and fails what no string shows (self-check on planted forms)', () => {
    const planted: Array<[string, boolean]> = [
      ["import { Bar } from 'recharts'", true],
      ["import type { BarProps } from 'recharts'", true],
      ["import 'recharts'", true],
      ["import Line from 'recharts/lib/cartesian/Line'", true],
      ["export * from 'recharts'", true],
      ["export { Bar } from 'recharts'", true],
      ["import R = require('recharts')", true],
      ["const { BarChart } = require('recharts')", true],
      ["const Chart = dynamic(() => import('recharts'))", true],
      ['const Chart = import(`recharts`)', true],
      ["type P = import('recharts').BarProps", true],
      // Loaders the reader does not list still take a string.
      ["import { createRequire as cr } from 'node:module'; cr(import.meta.url)('recharts')", true],
      ["const load = createRequire(import.meta.url); load('recharts')", true],
      ["(require as any)('recharts')", true],
      ["let load; load = require; load('recharts')", true],
      ["define(['recharts'], (R) => R)", true],
      ["const name = 'recharts'", true],
      ["// import { Bar } from 'recharts'", false],
      ["import { Bar } from 'recharts-plus'", false],
      // A stated gap: a bundler alias names recharts nowhere in the source.
      ["import { Bar } from 'charts'", false],
    ]
    for (const [source, names] of planted) {
      expect(specifiers('planted.tsx', source).strings.some(isRecharts), source).toBe(names)
    }
    // A local module is an edge whatever loads it.
    expect(specifiers('planted.tsx', "new Worker(new URL('./chart.worker.ts', import.meta.url))").strings).toContain('./chart.worker.ts')
    // What no string shows is opaque.
    for (const call of [
      'import(`./charts/${name}`)',
      "require('rech' + 'arts')",
      "require.context('../charts', true, /\\.tsx$/)",
      "import.meta.webpackContext('../charts', { recursive: false })",
    ]) expect(specifiers('planted.tsx', `const loaded = ${call}`).opaque, call).toEqual([call])
    expect(specifiers('planted.tsx', "const Chart = import('recharts')").opaque).toEqual([])
    // A stated gap: a computed specifier another loader takes is read as nothing.
    expect(specifiers('planted.tsx', 'const load = createRequire(import.meta.url); load(`./${name}`)').opaque).toEqual([])
    // resolve(): a file, undefined for a local module the repository does not hold, null for a package.
    expect(resolve('app/analysis/page.tsx', '../layout')).toBe('app/layout.tsx')
    expect(resolve('app/analysis/page.tsx', '@/features/no-such-module')).toBeUndefined()
    expect(resolve('app/analysis/page.tsx', 'react')).toBeNull()
  })

  it('only the charts not yet on the engine name recharts, with the config that transpiles it', () => {
    const read = tracked.map((file) => ({ file, ...specifiers(file, readFileSync(file, 'utf8')) }))
    expect(read.flatMap(({ file, opaque }) => opaque.map((call) => `${file}: ${call}`)), 'a module named by a computed specifier').toEqual([])
    expect(read.filter(({ strings }) => strings.some(isRecharts)).map(({ file }) => file).sort()).toEqual([...IMPORTERS, ...MENTIONS].sort())
  })

  it('the analysis route reaches none of it, through any chain of imports, re-exports, chunks or named modules', () => {
    for (const entry of ['app/layout.tsx', 'app/error.tsx', 'app/not-found.tsx', 'app/global-error.tsx', 'app/analysis/page.tsx', 'instrumentation-client.ts']) {
      expect(routeEntries, `${entry} is a route entry`).toContain(entry)
    }
    const seen = new Set<string>()
    const via = new Map<string, string>()
    const queue = [...routeEntries]
    const chainTo = (file: string) => { const chain = [file]; while (via.has(chain[0])) chain.unshift(via.get(chain[0])!); return chain.join(' → ') }
    const reached: string[] = []
    // The walk goes blind at a module an import names that it cannot find, or one no string names, so either fails it.
    const unread: string[] = []
    while (queue.length) {
      const file = queue.shift()!
      if (seen.has(file)) continue
      seen.add(file)
      const { strings, imports, opaque } = specifiers(file, readFileSync(file, 'utf8'))
      for (const call of opaque) unread.push(`${chainTo(file)}: ${call}`)
      if (strings.some(isRecharts)) reached.push(chainTo(file))
      for (const specifier of new Set([...imports, ...strings.filter((string) => LOCAL.test(string))])) {
        const next = resolve(file, specifier)
        if (next === undefined && imports.includes(specifier)) unread.push(`${chainTo(file)}: '${specifier}'`)
        else if (next && SCRIPT.test(next) && !seen.has(next)) {
          if (!via.has(next)) via.set(next, file)
          queue.push(next)
        }
      }
    }
    expect(seen.size, 'the walk reached the route’s modules').toBeGreaterThan(50)
    expect(seen.has('features/analysis/components/TrendChartsV2.tsx'), 'the walk follows the chart chunk’s dynamic import').toBe(true)
    expect(unread, 'a module the walk could not find or name').toEqual([])
    expect(reached, 'a chain from the analysis route to recharts').toEqual([])
  })
})
