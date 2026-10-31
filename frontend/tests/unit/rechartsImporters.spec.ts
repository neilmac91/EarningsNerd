import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/** Recharts left the frontend in E195 (D): the trend charts' engine draws the analysis charts and the filing page's
 *  Financial trends (D-064, D-067), the company page's peers chart left with its panel (D-066), and the package went
 *  with its chart kit (components/ui/Chart.tsx) and the config that transpiled it. So no file the frontend tracks,
 *  this gate aside, names the package: the read is git grep's, over every tracked file whatever its kind (scripts,
 *  configs, the manifest and the lockfile, docs, tests; lessons/test-absence-claims-come-from-git-grep.md), and a
 *  comment counts, so prose names the library Recharts. A name is the package's whole lower-case name, alone, quoted,
 *  as a path segment or versioned (`recharts@3.10.1`), never a longer one. No script outside the test homes loads a
 *  module by what no text shows: an `import()` or `require()` of a computed specifier, or a folder loader
 *  (`require.context()`, `import.meta.webpackContext()`, `import.meta.glob()`), cast or bare; for these the source is
 *  parsed, not text-matched (lessons/test-gates-must-be-as-wide-as-their-rule.md). And the lockfile installs recharts
 *  nowhere: not at the root, not nested under a package that depends on it, not under another name (an npm alias).
 *  Out of reach, each planted below as a gap: a computed specifier handed to a loader the parser does not list; an
 *  alias set where no tracked file holds it; and a dependency whose published dist inlines Recharts' code under its
 *  own name and declares no dependency on it, which names the package nowhere the tree or the lockfile shows. Code
 *  that arrives those ways ships, so tests/e2e/no-recharts-in-build.spec.ts reads every script of the production build
 *  for Recharts' class names. */

/** This gate's own file: the one tracked file that names the package, in its planted forms. */
const SELF = 'tests/unit/rechartsImporters.spec.ts'
const SCRIPT = /\.(?:[cm]?[jt]sx?)$/
const FOLDER_LOADERS = ['context', 'webpackContext', 'glob']
/** The package's name in text: lower case as npm writes it, the whole name (a longer name such as `recharts-plus` or
 *  `rechartsImporters` is another), alone, quoted, as a path segment or before a version's `@`. */
const RECHARTS = /(?<![\w$-])recharts(?![\w$-])/
const namesRecharts = (text: string) => RECHARTS.test(text)
/** Where a text names the package, for the failure message. */
const nameIn = (text: string) => {
  const at = text.search(RECHARTS)
  return JSON.stringify(text.slice(Math.max(0, at - 40), at + 40))
}

/** What a script loads that no text shows, as source text: an `import()` or `require()` of a computed specifier, and a
 *  folder loader. */
function opaqueLoads(fileName: string, source: string): string[] {
  const file = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, fileName.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const opaque: string[] = []
  // A callee as the bundler sees it: parentheses, casts and non-null marks compile away.
  const bare = (node: ts.Expression): ts.Expression => (ts.isParenthesizedExpression(node) || ts.isAsExpression(node)
    || ts.isTypeAssertionExpression(node) || ts.isSatisfiesExpression(node) || ts.isNonNullExpression(node) ? bare(node.expression) : node)
  const isRequire = (node: ts.Expression) => { const callee = bare(node); return ts.isIdentifier(callee) && callee.text === 'require' }
  const visit = (node: ts.Node) => {
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
  return opaque
}

/** The lockfile's entries that install recharts: under its own name at the root (`node_modules/recharts`) or nested
 *  in another package's node_modules, or under another name (an npm alias records the package's own `name`). */
function installs(lock: { packages?: Record<string, { name?: string } & Record<string, unknown>> }): string[] {
  return Object.entries(lock.packages ?? {})
    .filter(([key, entry]) => key.split('node_modules/').pop() === 'recharts' || entry.name === 'recharts')
    .map(([key]) => key)
}

describe('Recharts stays out of the frontend (E195 (D))', () => {
  const tracked = execFileSync('git', ['ls-files'], { encoding: 'utf8' }).split('\n').filter(Boolean)
  const scripts = tracked.filter((file) => SCRIPT.test(file) && !file.startsWith('tests/'))

  it('reads the package name wherever a text holds it, and fails what no text shows (self-check on planted forms)', () => {
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
      // Loaders the parser does not list, each found by a review round, still name the package in text.
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
      // A config that transpiles or aliases the package names it, and so do a manifest and a lockfile.
      ["module.exports = { transpilePackages: ['recharts'] }", true],
      ["module.exports = { turbopack: { resolveAlias: { charts: 'recharts' } } }", true],
      ['{ "compilerOptions": { "paths": { "charts": ["./node_modules/recharts"] } } }', true],
      ['"dependencies": { "recharts": "^3.10.1" }', true],
      ['"node_modules/recharts": { "version": "3.10.1" }', true],
      // A versioned name: a CDN script's URL.
      ['<script src="https://cdn.jsdelivr.net/npm/recharts@3.10.1/umd/Recharts.min.js"></script>', true],
      // A comment counts: the read is git grep's.
      ["// import { Bar } from 'recharts'", true],
      // Look-alikes: a longer name, this gate's own file name, the library's name in prose, and a class name, which
      // is the build scan's to find in shipped code.
      ["import { Bar } from 'recharts-plus'", false],
      ['see tests/unit/rechartsImporters.spec.ts', false],
      ['Recharts left the app with its chart kit.', false],
      ["const surface = '.recharts-surface'", false],
      // A stated gap: an alias set where no tracked file holds it names the package nowhere in the tree.
      ["import { Bar } from 'charts'", false],
    ]
    for (const [source, names] of planted) {
      expect(namesRecharts(source), source).toBe(names)
    }
    // What no text shows is opaque, cast or bare.
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
    ]) expect(opaqueLoads('planted.tsx', `const loaded = ${call}`), call).toEqual([call])
    expect(opaqueLoads('planted.tsx', "const Chart = import('recharts')")).toEqual([])
    // A stated gap: a computed specifier another loader takes is read as nothing.
    expect(opaqueLoads('planted.tsx', 'const load = createRequire(import.meta.url); load(`./${name}`)')).toEqual([])
  })

  it('no tracked file names recharts but this gate, and no script loads a module by what no text shows', () => {
    // The read reaches every kind of file the frontend tracks, and the parse every script outside the test homes.
    expect(tracked, 'the files read').toEqual(expect.arrayContaining([SELF, 'package.json', 'package-lock.json', 'next.config.js',
      'tailwind.config.js', 'eslint.config.mjs', 'app/layout.tsx', 'scripts/check-pricing-agreement.mjs', 'DESIGN_SYSTEM.md',
      'tests/e2e/charts-v2.spec.ts']))
    expect(tracked.length, 'the tracked files were read').toBeGreaterThan(500)
    expect(scripts, 'the scripts parsed').toEqual(expect.arrayContaining(['next.config.js', 'tailwind.config.js', 'eslint.config.mjs',
      'app/layout.tsx', 'scripts/check-pricing-agreement.mjs']))
    expect(scripts.flatMap((file) => opaqueLoads(file, readFileSync(file, 'utf8')).map((call) => `${file}: ${call}`)),
      'a module named by a computed specifier or a folder').toEqual([])
    const naming = tracked.filter((file) => file !== SELF).flatMap((file) => {
      const text = readFileSync(file).toString('latin1')
      return namesRecharts(text) ? [`${file}: ${nameIn(text)}`] : []
    })
    expect(naming, 'a tracked file naming recharts').toEqual([])
  })

  it('the lockfile installs no recharts, at the root, under a package or under another name (self-check on planted entries)', () => {
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
    // A stated gap: a wrapper whose published dist inlines Recharts' code under its own name, declaring no dependency
    // on it, installs no recharts entry; what it would ship is tests/e2e/no-recharts-in-build.spec.ts's to find.
    expect(installs({ packages: { '': { name: 'earningsnerd-frontend' }, 'node_modules/@acme/inlined-charts': { version: '1.0.0' } } }),
      'a stated gap: a wrapper that inlines the package').toEqual([])
    const lock = JSON.parse(readFileSync('package-lock.json', 'utf8'))
    expect(Object.keys(lock.packages).length, 'the lockfile was read').toBeGreaterThan(500)
    expect(installs(lock)).toEqual([])
  })
})
