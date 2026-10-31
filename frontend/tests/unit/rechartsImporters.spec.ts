import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, statSync } from 'node:fs'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/** Recharts left the frontend in E195 (D): the trend charts' engine draws the analysis charts and the filing page's
 *  Financial trends (D-064, D-067), the company page's peers chart left with its panel (D-066), and the package went
 *  with its chart kit (components/ui/Chart.tsx) and the config that transpiled it. This gate holds it out three ways.
 *  1. The text of every file the frontend tracks, read as git grep reads it (lessons/test-absence-claims-come-from-
 *     git-grep.md): every kind (scripts, configs, the manifest, docs, tests), comments included, so prose names the
 *     library Recharts; a tracked path missing from the working tree is skipped, as git grep skips it. A name is the
 *     package's whole lower-case name, alone, quoted, as a path segment or versioned (`recharts@3.10.1`), never a
 *     longer one. Two files are read for control: this gate and tests/e2e/no-recharts-in-build.spec.ts plant its
 *     forms, so the read must find exactly them. The lockfile is left to 3, since it may name the package without
 *     installing it (another package's optional peer).
 *  2. The parse of every script outside the test homes: each string it holds as the parser cooks it, escapes decoded,
 *     so `'re\x63harts'` is the name 1 cannot see; and each load no string shows, an `import()` or `require()` of a
 *     computed specifier or a folder loader (`require.context()`, `import.meta.webpackContext()`,
 *     `import.meta.glob()`), cast or bare (lessons/test-gates-must-be-as-wide-as-their-rule.md: the widening keeps the
 *     old reading beside the new). A file either reading finds is reported once.
 *  3. The lockfile's entries: none installs recharts, under its own name (at the root, or nested under a package that
 *     depends on it), under another name (an alias records the package's `name`) or from a recharts tarball or
 *     repository (`resolved`); an optional peer that is not installed is no install.
 *  Out of reach, each planted below as a gap: a computed specifier handed to a loader the parser does not list; an
 *  alias set where no tracked file holds it; and a dependency whose published dist inlines Recharts' code under its
 *  own name and declares no dependency on it, which names the package nowhere the tree or the lockfile shows. Code
 *  that arrives those ways ships, so tests/e2e/no-recharts-in-build.spec.ts reads the production build's scripts for
 *  Recharts' class names. */

/** This gate's own file and the build scan's: the tracked files that plant the package's name, for control. */
const SELF = 'tests/unit/rechartsImporters.spec.ts'
const BUILD_SCAN = 'tests/e2e/no-recharts-in-build.spec.ts'
const PLANTED_HOMES = [BUILD_SCAN, SELF]
const LOCKFILE = 'package-lock.json'
const SCRIPT = /\.(?:[cm]?[jt]sx?)$/
const FOLDER_LOADERS = ['context', 'webpackContext', 'glob']
/** The package's name in text: lower case as npm writes it, the whole name (a longer name such as `recharts-plus` or
 *  `rechartsImporters` is another), alone, quoted, as a path segment or before a version's `@`. */
const RECHARTS = /(?<![\w$-])recharts(?![\w$-])/
const namesRecharts = (text: string) => RECHARTS.test(text)
/** A file's bytes as text: latin1 keeps every byte, so no binary throws and an ASCII name reads as written. */
const textOf = (file: string) => readFileSync(file).toString('latin1')

/** What a script names that its raw text may hide, from its syntax tree. `names`: each string the script holds, as the
 *  parser cooks it (string literals, template chunks, an import's or export's specifier among them), that names the
 *  package. `opaque`, as source text: an `import()` or `require()` of a computed specifier, and a folder loader. */
function parse(fileName: string, source: string): { names: string[]; opaque: string[] } {
  const file = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, fileName.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const names: string[] = []
  const opaque: string[] = []
  // A callee as the bundler sees it: parentheses, casts and non-null marks compile away.
  const bare = (node: ts.Expression): ts.Expression => (ts.isParenthesizedExpression(node) || ts.isAsExpression(node)
    || ts.isTypeAssertionExpression(node) || ts.isSatisfiesExpression(node) || ts.isNonNullExpression(node) ? bare(node.expression) : node)
  const isRequire = (node: ts.Expression) => { const callee = bare(node); return ts.isIdentifier(callee) && callee.text === 'require' }
  const cooked = (node: ts.Node) => ts.isStringLiteralLike(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)
  const visit = (node: ts.Node) => {
    if (cooked(node) && namesRecharts((node as ts.LiteralLikeNode).text)) names.push((node as ts.LiteralLikeNode).text)
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
  return { names, opaque }
}

/** Whether either reading finds the package's name in a source: its raw text, or its cooked strings. */
const flags = (source: string) => namesRecharts(source) || parse('planted.tsx', source).names.length > 0

/** The lockfile's entries that install recharts: under its own name at the root (`node_modules/recharts`) or nested
 *  in another package's node_modules, under another name (an alias records the package's own `name`), or from a
 *  recharts tarball or repository (`resolved`). A package that only names it, as a peer, installs nothing. */
function installs(lock: { packages?: Record<string, { name?: string; resolved?: string } & Record<string, unknown>> }): string[] {
  return Object.entries(lock.packages ?? {})
    .filter(([key, entry]) => key.split('node_modules/').pop() === 'recharts' || entry.name === 'recharts'
      || (typeof entry.resolved === 'string' && namesRecharts(entry.resolved)))
    .map(([key]) => key)
}

describe('Recharts stays out of the frontend (E195 (D))', () => {
  // -z: a path git would C-quote (a non-ASCII byte, a quote, a backslash, a tab) comes back as written.
  const tracked = execFileSync('git', ['ls-files', '-z'], { encoding: 'utf8' }).split('\0').filter(Boolean)
  const present = tracked.filter((file) => existsSync(file) && statSync(file).isFile())
  const scripts = present.filter((file) => SCRIPT.test(file) && !file.startsWith('tests/'))
  /** Each script's parse, once. */
  const parsed = new Map<string, ReturnType<typeof parse>>()
  const parseOf = (file: string) => parsed.get(file) ?? parsed.set(file, parse(file, readFileSync(file, 'utf8'))).get(file)!
  /** The files whose raw text names the package, and the scripts whose cooked strings do. */
  const textRead = (files: string[]) => files.filter((file) => namesRecharts(textOf(file)))
  const cookedRead = (files: string[]) => files.filter((file) => parseOf(file).names.length > 0)

  it('reads the package name wherever a text or a decoded string holds it, and fails what neither shows (self-check on planted forms)', () => {
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
      // Loaders the parser does not list, each found by a review round, still name the package.
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
      // A config that transpiles or aliases the package names it, and so does a manifest.
      ["module.exports = { transpilePackages: ['recharts'] }", true],
      ["module.exports = { turbopack: { resolveAlias: { charts: 'recharts' } } }", true],
      ['{ "compilerOptions": { "paths": { "charts": ["./node_modules/recharts"] } } }', true],
      ['"dependencies": { "recharts": "^3.10.1" }', true],
      // A versioned name: a CDN script's URL.
      ['<script src="https://cdn.jsdelivr.net/npm/recharts@3.10.1/umd/Recharts.min.js"></script>', true],
      // A comment counts: the text read is git grep's.
      ["// import { Bar } from 'recharts'", true],
      // Look-alikes: a longer name (its escaped spelling too), this gate's own file name, the library's name in prose,
      // and a class name, which is the build scan's to find in shipped code.
      ["import { Bar } from 'recharts-plus'", false],
      ["import { Bar } from 're\\x63harts-plus'", false],
      ['see tests/unit/rechartsImporters.spec.ts', false],
      ['Recharts left the app with its chart kit.', false],
      ["const surface = '.recharts-surface'", false],
      // A stated gap: an alias set where no tracked file holds it names the package nowhere in the tree.
      ["import { Bar } from 'charts'", false],
    ]
    for (const [source, names] of planted) {
      expect(flags(source), source).toBe(names)
    }
    // Escaped spellings: the raw text holds no name, and the cooked strings do, so the parse is what finds them.
    for (const source of [
      "import { Bar } from 're\\x63harts'",
      "export * from 're\\u0063harts'",
      "const { BarChart } = require('rech\\u{61}rts')",
      'const Chart = import(`rech\\x61rts`)',
      "module.exports = { transpilePackages: ['rech\\x61rts'] }",
      "const peers = 'node_modules/\\x72echarts/es6/index.js'",
    ]) {
      expect(namesRecharts(source), `${source}: the raw text`).toBe(false)
      expect(parse('planted.tsx', source).names.length, `${source}: the cooked strings`).toBeGreaterThan(0)
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
    ]) expect(parse('planted.tsx', `const loaded = ${call}`).opaque, call).toEqual([call])
    expect(parse('planted.tsx', "const Chart = import('recharts')").opaque).toEqual([])
    // A stated gap: a computed specifier another loader takes is read as nothing.
    expect(parse('planted.tsx', 'const load = createRequire(import.meta.url); load(`./${name}`)').opaque).toEqual([])
  })

  it('no tracked file names recharts but the two that plant it, and no script loads a module by what no string shows', () => {
    // The read reaches every kind of file the frontend tracks, and the parse every script outside the test homes.
    expect(present, 'the files read').toEqual(expect.arrayContaining([...PLANTED_HOMES, 'package.json', LOCKFILE, 'next.config.js',
      'tailwind.config.js', 'eslint.config.mjs', 'app/layout.tsx', 'scripts/check-pricing-agreement.mjs', 'DESIGN_SYSTEM.md',
      'tests/e2e/charts-v2.spec.ts']))
    expect(present.length, 'the tracked files were read').toBeGreaterThan(500)
    expect(scripts, 'the scripts parsed').toEqual(expect.arrayContaining(['next.config.js', 'tailwind.config.js', 'eslint.config.mjs',
      'app/layout.tsx', 'scripts/check-pricing-agreement.mjs']))
    expect(scripts.flatMap((file) => parseOf(file).opaque.map((call) => `${file}: ${call}`)),
      'a module named by a computed specifier or a folder').toEqual([])
    // Each reading reads contents, not paths: the cooked one finds this gate's planted strings, and the text one must
    // find exactly the two planted homes below. A file both readings find is reported once.
    expect(cookedRead([SELF]), 'the cooked read reaches a file’s strings').toEqual([SELF])
    const naming = [...new Set([...textRead(present.filter((file) => file !== LOCKFILE)), ...cookedRead(scripts)])].sort()
    const evidence = naming.filter((file) => !PLANTED_HOMES.includes(file)).map((file) => {
      const text = textOf(file)
      const at = text.search(RECHARTS)
      return at >= 0 ? `${file}: ${JSON.stringify(text.slice(Math.max(0, at - 40), at + 40))}`
        : `${file}: ${JSON.stringify(parseOf(file).names[0])} (a decoded string)`
    })
    expect(naming, `a tracked file naming recharts:\n${evidence.join('\n')}`).toEqual(PLANTED_HOMES)
  })

  it('the lockfile installs no recharts, by name, alias or source, and a peer is no install (self-check on planted entries)', () => {
    expect(installs({
      packages: {
        '': { name: 'earningsnerd-frontend' },
        'node_modules/recharts': {},
        'node_modules/@tremor/react/node_modules/recharts': {},
        'node_modules/charts': { name: 'recharts' },
        'node_modules/charts-from-tarball': { resolved: 'https://registry.npmjs.org/recharts/-/recharts-3.10.1.tgz' },
        'node_modules/recharts/node_modules/eventemitter3': {},
        'node_modules/recharts-scale': {},
        'node_modules/react-recharts': { resolved: 'https://registry.npmjs.org/react-recharts/-/react-recharts-1.0.0.tgz' },
        // A package that names it as an optional peer, uninstalled: no install, and the text read leaves the lockfile.
        'node_modules/chart-adapter': { version: '1.0.0', peerDependencies: { recharts: '^3.0.0' }, peerDependenciesMeta: { recharts: { optional: true } } },
      },
    })).toEqual(['node_modules/recharts', 'node_modules/@tremor/react/node_modules/recharts', 'node_modules/charts',
      'node_modules/charts-from-tarball'])
    // A stated gap: a wrapper whose published dist inlines Recharts' code under its own name, declaring no dependency
    // on it, installs no recharts entry; what it would ship is tests/e2e/no-recharts-in-build.spec.ts's to find.
    expect(installs({ packages: { '': { name: 'earningsnerd-frontend' }, 'node_modules/@acme/inlined-charts': { version: '1.0.0' } } }),
      'a stated gap: a wrapper that inlines the package').toEqual([])
    const lock = JSON.parse(readFileSync(LOCKFILE, 'utf8'))
    expect(Object.keys(lock.packages).length, 'the lockfile was read').toBeGreaterThan(500)
    expect(installs(lock)).toEqual([])
  })
})
