import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/** Recharts reaches only the two charts not yet on the engine, and the analysis route loads none of it (E195).
 *  Shrink-only: moving either onto the engine deletes its line. The source is parsed, not text-matched
 *  (lessons/test-gates-must-be-as-wide-as-their-rule.md): every script the repository tracks outside the test homes,
 *  in every extension `allowJs` admits, and every form a module can name another by. */
const IMPORTERS = [
  'features/fundamentals/components/FundamentalsTrendChart.tsx',
  'features/peers/components/PeerComparisonPanel.tsx',
]
/** What the analysis route loads: the root layout (every route's), the route's own layout and page, and the client
 *  instrumentation every page loads. */
const ROUTE_ENTRIES = ['app/layout.tsx', 'app/analysis/layout.tsx', 'app/analysis/page.tsx', 'instrumentation-client.ts']

const SCRIPT = /\.(?:[cm]?[jt]sx?)$/
const EXTENSIONS = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.mts', '.cts']
const isRecharts = (specifier: string) => /^recharts(?:\/|$)/.test(specifier)

/** Every module a source names: static and type-only imports, side-effect imports, re-exports, `import x = require()`,
 *  `require()` and `import()` with a literal or template specifier. Comments and strings name nothing. */
function specifiers(fileName: string, source: string): string[] {
  const file = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, fileName.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const found: string[] = []
  const literal = (node: ts.Node | undefined) =>
    node && (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) ? found.push(node.text) : undefined
  const visit = (node: ts.Node) => {
    if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) && node.moduleSpecifier) literal(node.moduleSpecifier)
    if (ts.isImportEqualsDeclaration(node) && ts.isExternalModuleReference(node.moduleReference)) literal(node.moduleReference.expression)
    if (ts.isCallExpression(node) && (node.expression.kind === ts.SyntaxKind.ImportKeyword
      || (ts.isIdentifier(node.expression) && node.expression.text === 'require'))) literal(node.arguments[0])
    if (ts.isImportTypeNode(node) && ts.isLiteralTypeNode(node.argument)) literal(node.argument.literal)
    ts.forEachChild(node, visit)
  }
  visit(file)
  return found
}

/** A module the repository holds, as `@/…` or a relative path names it; null for a package. */
function resolve(from: string, specifier: string): string | null {
  const base = specifier.startsWith('@/') ? specifier.slice(2)
    : specifier.startsWith('.') ? path.join(path.dirname(from), specifier) : null
  if (base == null) return null
  const candidates = [base, ...EXTENSIONS.map((extension) => base + extension), ...EXTENSIONS.map((extension) => path.join(base, `index${extension}`))]
  return candidates.find((candidate) => existsSync(candidate) && statSync(candidate).isFile()) ?? null
}

describe('recharts importers', () => {
  const tracked = execFileSync('git', ['ls-files'], { encoding: 'utf8' }).split('\n')
    .filter((file) => SCRIPT.test(file) && !file.startsWith('tests/'))

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
      expect(specifiers('planted.tsx', source).some(isRecharts), source).toBe(names)
    }
  })

  it('only the charts not yet on the engine import recharts', () => {
    const importers = tracked.filter((file) => specifiers(file, readFileSync(file, 'utf8')).some(isRecharts))
    expect(importers.sort()).toEqual(IMPORTERS)
  })

  it('the analysis route reaches none of it, through any chain of imports, re-exports or chunks', () => {
    for (const entry of ROUTE_ENTRIES) expect(existsSync(entry), `${entry} is a route entry`).toBe(true)
    const seen = new Set<string>()
    const via = new Map<string, string>()
    const queue = [...ROUTE_ENTRIES]
    const reached: string[] = []
    while (queue.length) {
      const file = queue.shift()!
      if (seen.has(file)) continue
      seen.add(file)
      for (const specifier of specifiers(file, readFileSync(file, 'utf8'))) {
        if (isRecharts(specifier)) {
          const chain = [file]
          while (via.has(chain[0])) chain.unshift(via.get(chain[0])!)
          reached.push(chain.join(' → '))
        }
        const next = resolve(file, specifier)
        if (next && SCRIPT.test(next) && !seen.has(next)) {
          if (!via.has(next)) via.set(next, file)
          queue.push(next)
        }
      }
    }
    expect(seen.size, 'the walk reached the route’s modules').toBeGreaterThan(50)
    expect(seen.has('features/analysis/components/TrendChartsV2.tsx'), 'the walk follows the chart chunk’s dynamic import').toBe(true)
    expect(reached, 'a chain from the analysis route to recharts').toEqual([])
  })
})
