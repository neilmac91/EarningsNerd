import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/** Recharts reaches only the two charts not yet on the engine, and the analysis route loads none of it (E195).
 *  Shrink-only: moving either onto the engine deletes its line. The source is parsed, not text-matched
 *  (lessons/test-gates-must-be-as-wide-as-their-rule.md): every script the repository tracks outside the test homes,
 *  in every extension `allowJs` admits, and every form `specifiers()` lists. A module named where no reader of the
 *  source can see it (a computed specifier, a folder's context) fails the gate rather than passing it. Out of reach,
 *  planted below as gaps: a name that never appears in a script (a bundler alias in `next.config.js`), and a require
 *  handed on as an argument or destructured (`load(require)`, `const { resolve } = require`). */
const IMPORTERS = [
  'features/fundamentals/components/FundamentalsTrendChart.tsx',
  'features/peers/components/PeerComparisonPanel.tsx',
]
/** What the analysis route loads with nothing importing it: each of the App Router's special files in the root segment
 *  (every route's, the home page aside) and in the route's own segment, and the client instrumentation every page loads. */
const CONVENTIONS = ['layout', 'template', 'error', 'global-error', 'loading', 'not-found', 'global-not-found', 'forbidden', 'unauthorized', 'default']
const SEGMENTS = [{ dir: 'app', names: CONVENTIONS }, { dir: 'app/analysis', names: [...CONVENTIONS, 'page'] }]

const SCRIPT = /\.(?:[cm]?[jt]sx?)$/
const EXTENSIONS = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.mts', '.cts']
const isRecharts = (specifier: string) => /^recharts(?:\/|$)/.test(specifier)

/** Every module a source names: static and type-only imports, side-effect imports, re-exports, `import x = require()`,
 *  and a loader called with a literal or template specifier: `import()`, `require()` and `require.resolve()` (with
 *  a require `createRequire()` makes, or a name bound to either), `import.meta.resolve()` and a worker's or asset's
 *  `new URL(…, import.meta.url)`. Comments and strings name nothing. A loader called with a computed specifier, and a
 *  context that loads a whole folder (`require.context()`, `import.meta.webpackContext()`), name modules the reader
 *  cannot see: each is kept, as its source text, in `opaque`. */
function specifiers(fileName: string, source: string): { named: string[]; opaque: string[] } {
  const file = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, fileName.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const named: string[] = []
  const opaque: string[] = []
  // The names a require goes by in the file: its own, and any bound to it or to what createRequire() returns.
  const requires = new Set(['require'])
  const isRequire = (node: ts.Expression) => (ts.isIdentifier(node) && requires.has(node.text))
    || (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'createRequire')
  const isImportMeta = (node: ts.Expression) => ts.isMetaProperty(node) && node.keywordToken === ts.SyntaxKind.ImportKeyword
  const bind = (node: ts.Node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer && isRequire(node.initializer)) requires.add(node.name.text)
    ts.forEachChild(node, bind)
  }
  bind(file)
  const literal = (node: ts.Node | undefined) =>
    node && (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) ? named.push(node.text) : undefined
  const load = (call: ts.Node, specifier: ts.Node | undefined) => { if (literal(specifier) === undefined) opaque.push(call.getText(file)) }
  const visit = (node: ts.Node) => {
    if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier) literal(node.moduleSpecifier)
    if (ts.isImportEqualsDeclaration(node) && ts.isExternalModuleReference(node.moduleReference)) literal(node.moduleReference.expression)
    if (ts.isCallExpression(node)) {
      const callee = node.expression
      if (callee.kind === ts.SyntaxKind.ImportKeyword || isRequire(callee)) load(node, node.arguments[0])
      else if (ts.isPropertyAccessExpression(callee) && (isRequire(callee.expression) || isImportMeta(callee.expression))) {
        if (callee.name.text === 'resolve') load(node, node.arguments[0])
        if (callee.name.text === 'context' || callee.name.text === 'webpackContext') opaque.push(node.getText(file))
      }
    }
    if (ts.isNewExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'URL') {
      const base = node.arguments?.[1]
      if (base && ts.isPropertyAccessExpression(base) && isImportMeta(base.expression) && base.name.text === 'url') load(node, node.arguments?.[0])
    }
    if (ts.isImportTypeNode(node) && ts.isLiteralTypeNode(node.argument)) literal(node.argument.literal)
    ts.forEachChild(node, visit)
  }
  visit(file)
  return { named, opaque }
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

  it('reads every form a module can name recharts by, and nothing else (self-check on planted forms)', () => {
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
      ["// import { Bar } from 'recharts'", false],
      ["const name = 'recharts'", false],
      ["import { Bar } from 'recharts-plus'", false],
    ]
    for (const [source, names] of planted) {
      expect(specifiers('planted.tsx', source).named.some(isRecharts), source).toBe(names)
    }
    // The other loaders: a require createRequire() makes or a name holds, resolve(), and a worker's URL.
    for (const source of [
      "const load = createRequire(import.meta.url); load('recharts')",
      "createRequire(import.meta.url)('recharts')",
      "const load = require; load('recharts')",
      "require.resolve('recharts')",
      "import.meta.resolve('recharts')",
    ]) expect(specifiers('planted.mjs', source).named, source).toContain('recharts')
    expect(specifiers('planted.tsx', "new Worker(new URL('./chart.worker.ts', import.meta.url))").named).toEqual(['./chart.worker.ts'])
    // A computed module, or a folder's context, is never read as none.
    for (const call of [
      'import(`./charts/${name}`)',
      "require('rech' + 'arts')",
      "require.context('../charts', true, /\\.tsx$/)",
      "import.meta.webpackContext('../charts', { recursive: false })",
      'new URL(`./${name}.ts`, import.meta.url)',
    ]) expect(specifiers('planted.tsx', `const loaded = ${call}`).opaque, call).toEqual([call])
    expect(specifiers('planted.tsx', "const Chart = import('recharts')").opaque).toEqual([])
    // The stated gaps: a require handed on or destructured is read as nothing.
    for (const source of ["load(require); load('recharts')", "const { resolve } = require; resolve('recharts')"]) {
      expect(specifiers('planted.tsx', source), source).toEqual({ named: [], opaque: [] })
    }
    // A local module the repository does not hold is not a package: the walk fails on it.
    expect(resolve('app/analysis/page.tsx', './layout')).toBe('app/analysis/layout.tsx')
    expect(resolve('app/analysis/page.tsx', '@/features/no-such-module')).toBeUndefined()
    expect(resolve('app/analysis/page.tsx', 'react')).toBeNull()
  })

  it('only the charts not yet on the engine import recharts', () => {
    const read = tracked.map((file) => ({ file, ...specifiers(file, readFileSync(file, 'utf8')) }))
    expect(read.flatMap(({ file, opaque }) => opaque.map((call) => `${file}: ${call}`)), 'a module named by a computed specifier').toEqual([])
    expect(read.filter(({ named }) => named.some(isRecharts)).map(({ file }) => file).sort()).toEqual(IMPORTERS)
  })

  it('the analysis route reaches none of it, through any chain of imports, re-exports or chunks', () => {
    for (const entry of ['app/layout.tsx', 'app/error.tsx', 'app/not-found.tsx', 'app/global-error.tsx', 'app/analysis/page.tsx', 'instrumentation-client.ts']) {
      expect(routeEntries, `${entry} is a route entry`).toContain(entry)
    }
    const seen = new Set<string>()
    const via = new Map<string, string>()
    const queue = [...routeEntries]
    const chainTo = (file: string) => { const chain = [file]; while (via.has(chain[0])) chain.unshift(via.get(chain[0])!); return chain.join(' → ') }
    const reached: string[] = []
    // The walk goes blind at a module it cannot find or name, so either fails it.
    const unread: string[] = []
    while (queue.length) {
      const file = queue.shift()!
      if (seen.has(file)) continue
      seen.add(file)
      const { named, opaque } = specifiers(file, readFileSync(file, 'utf8'))
      for (const call of opaque) unread.push(`${chainTo(file)}: ${call}`)
      for (const specifier of named) {
        if (isRecharts(specifier)) reached.push(chainTo(file))
        const next = resolve(file, specifier)
        if (next === undefined) unread.push(`${chainTo(file)}: '${specifier}'`)
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
