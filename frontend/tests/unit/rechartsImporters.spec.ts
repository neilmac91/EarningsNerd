import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/** Recharts left the frontend in E195 (D): the trend charts' engine draws the analysis charts and the filing page's
 *  Financial trends (D-064, D-067), the company page's peers chart left with its panel (D-066), and the package went
 *  with its chart kit (components/ui/Chart.tsx) and the config that transpiled it. So no script the frontend tracks
 *  outside its test homes names recharts, in any extension `allowJs` admits, and the lockfile installs it nowhere: not
 *  at the root, not under another package (a chart library that wraps it), not under another name (an npm alias). The
 *  source is parsed, not text-matched (lessons/test-gates-must-be-as-wide-as-their-rule.md). Whatever loads a module
 *  names it by a string, so the gate reads every string a script holds rather than a list of loaders, and a string
 *  naming recharts, as a package or as a path, fails its file. What no string shows fails too: an `import()` or
 *  `require()` of a computed specifier and a folder loader (`require.context()`, `import.meta.webpackContext()`,
 *  `import.meta.glob()`), cast or bare. Out of the reader's reach, planted below as gaps: a name no script holds (a
 *  bundler alias set outside the tracked scripts) and a computed specifier handed to any other loader; neither has a
 *  Recharts to reach while the lockfile installs none. While the analysis route's charts and then the two Recharts
 *  charts left one by one, the gate also walked that route's imports for a chain to a script naming recharts, and an
 *  e2e case scanned its built scripts for Recharts' class names; with no script naming it and no install of it, neither
 *  has anything left to find. */

const SCRIPT = /\.(?:[cm]?[jt]sx?)$/
const FOLDER_LOADERS = ['context', 'webpackContext', 'glob']
const isRecharts = (string: string) => /(?:^|\/)recharts(?:\/|$)/.test(string)

/** What a source names. `strings`: every string it holds (a comment holds none). `opaque`, as source text: an
 *  `import()` or `require()` of a computed specifier, and a folder loader. */
function specifiers(fileName: string, source: string): { strings: string[]; opaque: string[] } {
  const file = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, fileName.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const strings: string[] = []
  const opaque: string[] = []
  // A callee as the bundler sees it: parentheses, casts and non-null marks compile away.
  const bare = (node: ts.Expression): ts.Expression => (ts.isParenthesizedExpression(node) || ts.isAsExpression(node)
    || ts.isTypeAssertionExpression(node) || ts.isSatisfiesExpression(node) || ts.isNonNullExpression(node) ? bare(node.expression) : node)
  const isRequire = (node: ts.Expression) => { const callee = bare(node); return ts.isIdentifier(callee) && callee.text === 'require' }
  const visit = (node: ts.Node) => {
    if (ts.isStringLiteralLike(node)) strings.push(node.text)
    if (ts.isCallExpression(node)) {
      const callee = bare(node.expression)
      if ((callee.kind === ts.SyntaxKind.ImportKeyword || isRequire(callee)) && !(node.arguments[0] && ts.isStringLiteralLike(node.arguments[0]))) {
        opaque.push(node.getText(file))
      }
      if (ts.isPropertyAccessExpression(callee) && (isRequire(callee.expression) || ts.isMetaProperty(bare(callee.expression)))
        && FOLDER_LOADERS.includes(callee.name.text)) opaque.push(node.getText(file))
    }
    ts.forEachChild(node, visit)
  }
  visit(file)
  return { strings, opaque }
}

/** The lockfile's entries that install recharts: under its own name at the root (`node_modules/recharts`) or nested
 *  in another package's node_modules, or under another name (an npm alias records the package's own `name`). */
function installs(lock: { packages?: Record<string, { name?: string }> }): string[] {
  return Object.entries(lock.packages ?? {})
    .filter(([key, entry]) => key.split('node_modules/').pop() === 'recharts' || entry.name === 'recharts')
    .map(([key]) => key)
}

describe('Recharts stays out of the frontend (E195 (D))', () => {
  const tracked = execFileSync('git', ['ls-files'], { encoding: 'utf8' }).split('\n')
    .filter((file) => SCRIPT.test(file) && !file.startsWith('tests/'))

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
      // Loaders the reader does not list, each found by a review round, still take a string.
      ["createRequire(import.meta.url)('recharts')", true],
      ["const load = createRequire(import.meta.url); load('recharts')", true],
      ["import { createRequire as cr } from 'node:module'; cr(import.meta.url)('recharts')", true],
      ["import * as nodeModule from 'node:module'; nodeModule.createRequire(import.meta.url)('recharts')", true],
      ["(require)('recharts')", true],
      ["(require as any)('recharts')", true],
      ["const load = require; load('recharts')", true],
      ["let load; load = require; load('recharts')", true],
      ["load(require); load('recharts')", true],
      ["const { resolve } = require; resolve('recharts')", true],
      ["require.resolve('recharts')", true],
      ["import.meta.resolve('recharts')", true],
      ["define(['recharts'], (R) => R)", true],
      ["const peers = import.meta.glob('/node_modules/recharts/es6/index.js', { eager: true })", true],
      ["const name = 'recharts'", true],
      // A config that transpiles or aliases the package names it too.
      ["module.exports = { transpilePackages: ['recharts'] }", true],
      ["module.exports = { turbopack: { resolveAlias: { charts: 'recharts' } } }", true],
      ["// import { Bar } from 'recharts'", false],
      ["import { Bar } from 'recharts-plus'", false],
      // A stated gap: a bundler alias set outside the tracked scripts names recharts nowhere in the source.
      ["import { Bar } from 'charts'", false],
    ]
    for (const [source, names] of planted) {
      expect(specifiers('planted.tsx', source).strings.some(isRecharts), source).toBe(names)
    }
    // What no string shows is opaque, cast or bare.
    for (const call of [
      'import(`./charts/${name}`)',
      "require('rech' + 'arts')",
      '(require as any)(name)',
      'require!(name)',
      "require.context('../charts', true, /\\.tsx$/)",
      "(require as any).context('../charts', true, /\\.tsx$/)",
      "import.meta.webpackContext('../charts', { recursive: false })",
      "(import.meta as any).webpackContext('../charts', { recursive: false })",
      "import.meta.glob('../../peers/components/*.tsx', { eager: true })",
    ]) expect(specifiers('planted.tsx', `const loaded = ${call}`).opaque, call).toEqual([call])
    expect(specifiers('planted.tsx', "const Chart = import('recharts')").opaque).toEqual([])
    // A stated gap: a computed specifier another loader takes is read as nothing.
    expect(specifiers('planted.tsx', 'const load = createRequire(import.meta.url); load(`./${name}`)').opaque).toEqual([])
  })

  it('no script names recharts, or names a module by a computed specifier or a folder', () => {
    const read = tracked.map((file) => ({ file, ...specifiers(file, readFileSync(file, 'utf8')) }))
    expect(read.length, 'the scripts were read').toBeGreaterThan(300)
    expect(read.flatMap(({ file, opaque }) => opaque.map((call) => `${file}: ${call}`)), 'a module named by a computed specifier or a folder').toEqual([])
    expect(read.filter(({ strings }) => strings.some(isRecharts)).map(({ file, strings }) => `${file}: ${strings.filter(isRecharts).join(', ')}`), 'a script naming recharts').toEqual([])
  })

  it('the lockfile installs no recharts, at the root, under another package or under another name (self-check on planted entries)', () => {
    expect(installs({
      packages: {
        '': { name: 'earningsnerd-frontend' },
        'node_modules/recharts': {},
        'node_modules/@tremor/react/node_modules/recharts': {},
        'node_modules/charts': { name: 'recharts' },
        'node_modules/recharts/node_modules/eventemitter3': {},
        'node_modules/recharts-scale': {},
        'node_modules/react-recharts': {},
      },
    })).toEqual(['node_modules/recharts', 'node_modules/@tremor/react/node_modules/recharts', 'node_modules/charts'])
    const lock = JSON.parse(readFileSync('package-lock.json', 'utf8'))
    expect(Object.keys(lock.packages).length, 'the lockfile was read').toBeGreaterThan(500)
    expect(installs(lock)).toEqual([])
  })
})
