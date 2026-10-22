import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * A page declares one Inter, the layout's optical-size instance (E147). next/font declares a face for every loader call,
 * and every module in the root's tree rides every page, so the global error page's own `Inter({ subsets: ['latin'] })`
 * declared a second Inter family, without the opsz axis or the `--font-inter` variable, on every page; which of the two a
 * run of text took was the browser's choice. The root's fonts now have one module, `app/fonts.ts`, which the layout and
 * the global error page import.
 *
 * The gate reads every TypeScript module under app/, components/, features/, hooks/ and lib/ through its syntax tree and
 * fails a call of a `next/font/google` loader outside `app/fonts.ts`, under any name an import gives it (a named import, an
 * alias, a namespace's member), a second call of one loader inside it, and a re-export of the package, which would let a
 * module call a loader the scan cannot place. It also holds the layout and the global error page to the module's `inter`.
 *
 * Out of its reach: `next/font/local` (BrandEmphasis's genuine Inter italic is its own face, D-057), a loader reached
 * through a value the scan cannot follow (a loader passed to a function, or held in a `let`), and modules outside the
 * five directories, which ship no page code.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const FONTS = 'app/fonts.ts'
const PACKAGE = 'next/font/google'

interface Finding {
  file: string
  line: number
  why: string
}

/** Every call of a next/font/google loader in one module, with the loader's own name, and every re-export of the package. */
function loaderCalls(file: string, source: string): { calls: { loader: string; line: number }[]; reexports: number[] } {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const named = new Map<string, string>()
  const namespaces = new Set<string>()
  const reexports: number[] = []
  const lineOf = (n: ts.Node) => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1
  for (const statement of sf.statements) {
    if (ts.isImportDeclaration(statement) && ts.isStringLiteral(statement.moduleSpecifier) && statement.moduleSpecifier.text === PACKAGE) {
      const bindings = statement.importClause?.namedBindings
      if (bindings && ts.isNamedImports(bindings)) {
        for (const el of bindings.elements) named.set(el.name.text, (el.propertyName ?? el.name).text)
      }
      if (bindings && ts.isNamespaceImport(bindings)) namespaces.add(bindings.name.text)
    }
    if (ts.isExportDeclaration(statement) && statement.moduleSpecifier && ts.isStringLiteral(statement.moduleSpecifier) && statement.moduleSpecifier.text === PACKAGE) {
      reexports.push(lineOf(statement))
    }
  }
  const calls: { loader: string; line: number }[] = []
  const visit = (n: ts.Node) => {
    if (ts.isCallExpression(n)) {
      const callee = n.expression
      if (ts.isIdentifier(callee) && named.has(callee.text)) calls.push({ loader: named.get(callee.text)!, line: lineOf(n) })
      if (ts.isPropertyAccessExpression(callee) && ts.isIdentifier(callee.expression) && namespaces.has(callee.expression.text)) {
        calls.push({ loader: callee.name.text, line: lineOf(n) })
      }
    }
    ts.forEachChild(n, visit)
  }
  visit(sf)
  return { calls, reexports }
}

/** What the rule fails across a set of modules (path relative to frontend/ → source). */
function fontFindings(modules: Record<string, string>): Finding[] {
  const findings: Finding[] = []
  for (const [file, source] of Object.entries(modules)) {
    const { calls, reexports } = loaderCalls(file, source)
    for (const line of reexports) findings.push({ file, line, why: `re-exports ${PACKAGE}` })
    if (file !== FONTS) {
      for (const call of calls) findings.push({ file, line: call.line, why: `calls ${call.loader}() outside ${FONTS}` })
      continue
    }
    const seen = new Set<string>()
    for (const call of calls) {
      if (seen.has(call.loader)) findings.push({ file, line: call.line, why: `calls ${call.loader}() a second time` })
      seen.add(call.loader)
    }
  }
  return findings
}

/** The names a module imports from the fonts module. */
function fontsImports(file: string, source: string): string[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const out: string[] = []
  for (const statement of sf.statements) {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) continue
    if (!['./fonts', '@/app/fonts'].includes(statement.moduleSpecifier.text)) continue
    const bindings = statement.importClause?.namedBindings
    if (bindings && ts.isNamedImports(bindings)) out.push(...bindings.elements.map((el) => (el.propertyName ?? el.name).text))
  }
  return out
}

const read = (rel: string) => readFileSync(path.join(FRONTEND, rel), 'utf8')
const APP = execFileSync('git', ['ls-files', '-z', 'app', 'components', 'features', 'hooks', 'lib'], { cwd: FRONTEND, encoding: 'utf8' })
  .split('\0')
  .filter((f) => /\.(ts|tsx)$/.test(f))

describe('one instance of each root font (E147)', () => {
  it('reads the forms it must fail and passes their look-alikes', () => {
    const forms: Record<string, string> = {
      'app/global-error.tsx': "import { Inter } from 'next/font/google'\nconst inter = Inter({ subsets: ['latin'] })\n",
      'features/a/Aliased.tsx': "import { Inter as Sans } from 'next/font/google'\nexport const sans = Sans({ subsets: ['latin'] })\n",
      'lib/namespace.ts': "import * as google from 'next/font/google'\nexport const mono = google.Geist_Mono({ subsets: ['latin'] })\n",
      'lib/reexport.ts': "export { Inter } from 'next/font/google'\n",
      [FONTS]: "import { Inter } from 'next/font/google'\nexport const a = Inter({ subsets: ['latin'] })\nexport const b = Inter({ subsets: ['latin'], axes: ['opsz'] })\n",
      'features/b/LookAlike.tsx': "import { Inter } from './typefaces'\nexport const x = Inter({})\n",
      'features/c/Local.tsx': "import localFont from 'next/font/local'\nexport const italic = localFont({ src: './i.woff2' })\n",
      'features/d/UsesTheModule.tsx': "import { inter } from '@/app/fonts'\nexport const c = inter.className\n",
    }
    expect(fontFindings(forms)).toEqual([
      { file: 'app/global-error.tsx', line: 2, why: 'calls Inter() outside app/fonts.ts' },
      { file: 'features/a/Aliased.tsx', line: 2, why: 'calls Inter() outside app/fonts.ts' },
      { file: 'lib/namespace.ts', line: 2, why: 'calls Geist_Mono() outside app/fonts.ts' },
      { file: 'lib/reexport.ts', line: 1, why: 're-exports next/font/google' },
      { file: FONTS, line: 3, why: 'calls Inter() a second time' },
    ])
  })

  it('reads the app (anti-vacuity): the fonts module calls each root loader once', () => {
    expect(APP.length).toBeGreaterThan(200)
    expect(APP).toContain(FONTS)
    expect(loaderCalls(FONTS, read(FONTS)).calls.map((c) => c.loader).sort()).toEqual(['Geist_Mono', 'Inter', 'Newsreader'])
  })

  it('calls no next/font/google loader outside app/fonts.ts, and each inside it once', () => {
    const modules = Object.fromEntries(APP.map((file) => [file, read(file)]))
    expect(fontFindings(modules), `the root's fonts are declared once, in ${FONTS}: import its instances`).toEqual([])
  })

  it("gives the layout and the global error page the fonts module's Inter", () => {
    expect(fontsImports('app/layout.tsx', read('app/layout.tsx'))).toContain('inter')
    expect(fontsImports('app/global-error.tsx', read('app/global-error.tsx'))).toContain('inter')
  })
})
