/* =============================================================================
   serverCallsClientExport.spec.ts — server code never calls a client module's export
   -----------------------------------------------------------------------------
   Rule-12 gate for lessons/frontend-client-exports-need-next-build.md. Every export of a
   'use client' module is a client reference wherever server code imports it: a component may be
   rendered (`<Sep />`) or passed to a client component, but calling it on the server throws
   ("Attempted to call X() from the server but X is on the client") and fails the prerender. tsc,
   eslint and vitest cannot see the boundary, and `next build` sees it only on a path the build
   renders: the homepage example's evidence row called sourceTraceChipClass() from SourceTrace.tsx;
   CI built `/` with no example filing, so without that row, and only Vercel's build, reading the
   live example summary, rendered the call and failed.

   The scan reads the TypeScript AST of the server code: every module reachable through static
   imports (`@/` and relative) from the App Router's own files under app/ (page, layout, template,
   not-found, loading, default, route, sitemap, robots, manifest and the image and icon files) that
   do not open with 'use client', and from middleware.ts and instrumentation.ts, without passing
   through a 'use client' module. In each, a call or `new` whose callee is a name imported from a
   'use client' module fails. A name imported through a module without the directive is followed
   through its re-exports (`export { x } from`, `export * from`, `import { x } …; export { x }`) to
   the module that defines it, so the `@/components/ui` barrel's buttonVariants (Button.tsx) counts.

   Limits: a dynamic import(), a client export held in a variable or an object before the call, a
   local binding that shadows an imported name, and client exports reached through a package.
============================================================================= */

import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

const ROOT = path.join(__dirname, '../..')
const ROOT_SERVER_FILES = ['middleware.ts', 'instrumentation.ts']
const ROUTER_FILE =
  /^(page|layout|template|not-found|loading|default|route|sitemap|robots|manifest|opengraph-image|twitter-image|icon|apple-icon)\.tsx?$/

interface Binding {
  from: string
  name: string
}

interface Module {
  file: string
  source: ts.SourceFile
  client: boolean
  /** Local name → the module and export it was imported as ('default', or '*' for a namespace). */
  imports: Map<string, Binding>
  /** Exported name → the module and export it re-exports (`export { a as b } from './m'`). */
  reexports: Map<string, Binding>
  /** Exported name → the local binding it exports (`export { a as b }`). */
  localExports: Map<string, string>
  /** `export * from` targets, in order. */
  stars: string[]
  /** Names this module declares and exports itself ('default' included). */
  declared: Set<string>
  /** Every module it imports or re-exports from, type-only aside. */
  deps: string[]
}

type Read = (file: string) => string | null

const isFile = (file: string) => fs.existsSync(file) && fs.statSync(file).isFile()
const readDisk: Read = (file) => (isFile(file) ? fs.readFileSync(file, 'utf8') : null)

function graph(root: string, read: Read) {
  const cache = new Map<string, Module>()

  const resolve = (fromFile: string, spec: string): string | null => {
    let base: string
    if (spec.startsWith('@/')) base = path.join(root, spec.slice(2))
    else if (spec.startsWith('.')) base = path.resolve(path.dirname(fromFile), spec)
    else return null
    for (const candidate of [base, `${base}.ts`, `${base}.tsx`, path.join(base, 'index.ts'), path.join(base, 'index.tsx')]) {
      if (/\.tsx?$/.test(candidate) && read(candidate) !== null) return candidate
    }
    return null
  }

  const load = (file: string): Module => {
    const cached = cache.get(file)
    if (cached) return cached
    const source = ts.createSourceFile(
      file, read(file) ?? '', ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
    )
    const first = source.statements[0]
    const m: Module = {
      file,
      source,
      client: !!first && ts.isExpressionStatement(first) && ts.isStringLiteral(first.expression) &&
        first.expression.text === 'use client',
      imports: new Map(),
      reexports: new Map(),
      localExports: new Map(),
      stars: [],
      declared: new Set(),
      deps: [],
    }
    cache.set(file, m)
    const exported = (node: ts.Node) =>
      ts.canHaveModifiers(node) && (ts.getModifiers(node) ?? []).some((mod) => mod.kind === ts.SyntaxKind.ExportKeyword)
    const isDefault = (node: ts.Node) =>
      ts.canHaveModifiers(node) && (ts.getModifiers(node) ?? []).some((mod) => mod.kind === ts.SyntaxKind.DefaultKeyword)
    for (const st of source.statements) {
      if (ts.isImportDeclaration(st)) {
        const from = resolve(file, (st.moduleSpecifier as ts.StringLiteral).text)
        const clause = st.importClause
        if (!from || clause?.isTypeOnly) continue
        m.deps.push(from)
        if (!clause) continue
        if (clause.name) m.imports.set(clause.name.text, { from, name: 'default' })
        const named = clause.namedBindings
        if (named && ts.isNamespaceImport(named)) m.imports.set(named.name.text, { from, name: '*' })
        if (named && ts.isNamedImports(named)) {
          for (const el of named.elements) {
            if (!el.isTypeOnly) m.imports.set(el.name.text, { from, name: (el.propertyName ?? el.name).text })
          }
        }
      } else if (ts.isExportDeclaration(st)) {
        if (st.isTypeOnly) continue
        const from = st.moduleSpecifier ? resolve(file, (st.moduleSpecifier as ts.StringLiteral).text) : null
        if (st.moduleSpecifier && !from) continue
        if (from) m.deps.push(from)
        if (!st.exportClause) {
          if (from) m.stars.push(from)
        } else if (ts.isNamedExports(st.exportClause)) {
          for (const el of st.exportClause.elements) {
            if (el.isTypeOnly) continue
            const original = (el.propertyName ?? el.name).text
            if (from) m.reexports.set(el.name.text, { from, name: original })
            else m.localExports.set(el.name.text, original)
          }
        }
      } else if (ts.isExportAssignment(st)) {
        m.declared.add('default')
      } else if (exported(st)) {
        if (isDefault(st)) m.declared.add('default')
        else if (ts.isVariableStatement(st)) {
          for (const d of st.declarationList.declarations) if (ts.isIdentifier(d.name)) m.declared.add(d.name.text)
        } else if ((ts.isFunctionDeclaration(st) || ts.isClassDeclaration(st) || ts.isEnumDeclaration(st)) && st.name) {
          m.declared.add(st.name.text)
        }
      }
    }
    return m
  }

  const exportsName = (file: string, name: string, seen = new Set<string>()): boolean => {
    if (seen.has(file)) return false
    seen.add(file)
    const m = load(file)
    return m.declared.has(name) || m.reexports.has(name) || m.localExports.has(name) ||
      m.stars.some((star) => exportsName(star, name, seen))
  }

  /** The 'use client' module behind an export, following re-exports, else null. */
  const clientOrigin = (file: string, name: string, seen = new Set<string>()): string | null => {
    const key = `${file}#${name}`
    if (seen.has(key)) return null
    seen.add(key)
    const m = load(file)
    if (m.client) return file
    const re = m.reexports.get(name)
    if (re) return clientOrigin(re.from, re.name, seen)
    const local = m.localExports.get(name)
    if (local !== undefined) {
      const imported = m.imports.get(local)
      return imported && imported.name !== '*' ? clientOrigin(imported.from, imported.name, seen) : null
    }
    if (m.declared.has(name)) return null
    const star = m.stars.find((s) => exportsName(s, name))
    return star ? clientOrigin(star, name, seen) : null
  }

  /** Every module reachable from the entries without passing through a 'use client' module. */
  const serverModules = (entries: string[]): Module[] => {
    const seen = new Set<string>()
    const queue = entries.filter((file) => !load(file).client)
    const out: Module[] = []
    while (queue.length) {
      const file = queue.pop() as string
      if (seen.has(file)) continue
      seen.add(file)
      const m = load(file)
      out.push(m)
      for (const dep of m.deps) if (!seen.has(dep) && !load(dep).client) queue.push(dep)
    }
    return out
  }

  /** `file:line: callee()` for each call in a server module of an export of a 'use client' module. */
  const offenders = (modules: Module[]): string[] => {
    const found: string[] = []
    for (const m of modules) {
      const visit = (node: ts.Node): void => {
        if (ts.isCallExpression(node) || ts.isNewExpression(node)) {
          const callee = node.expression
          let target: Binding | null = null
          if (ts.isIdentifier(callee)) {
            const imported = m.imports.get(callee.text)
            if (imported && imported.name !== '*') target = imported
          } else if (ts.isPropertyAccessExpression(callee) && ts.isIdentifier(callee.expression)) {
            const imported = m.imports.get(callee.expression.text)
            if (imported?.name === '*') target = { from: imported.from, name: callee.name.text }
          }
          const client = target && clientOrigin(target.from, target.name)
          if (client) {
            const line = m.source.getLineAndCharacterOfPosition(node.getStart(m.source)).line + 1
            const rel = (f: string) => path.relative(root, f).split(path.sep).join('/')
            found.push(`${rel(m.file)}:${line}: ${callee.getText(m.source)}() is an export of ${rel(client)}`)
          }
        }
        ts.forEachChild(node, visit)
      }
      visit(m.source)
    }
    return found
  }

  return { load, clientOrigin, serverModules, offenders }
}

function walk(dir: string, out: string[] = []): string[] {
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name)
    if (fs.statSync(p).isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(p) && !p.endsWith('.d.ts')) out.push(p)
  }
  return out
}

/** A graph over in-memory files, for the fixtures. */
function memory(files: Record<string, string>) {
  const root = '/virtual'
  const g = graph(root, (file) => files[path.relative(root, file)] ?? null)
  const scan = (...entries: string[]) => g.offenders(g.serverModules(entries.map((e) => path.join(root, e))))
  return { ...g, scan }
}

describe('server calls of client exports: the scan', () => {
  const CLIENT = "'use client'\nexport const chipClass = () => 'chip'\nexport function Chip() { return null }\n"

  it('flags a call through a direct import, a barrel re-export, an export star and a namespace', () => {
    const tree = memory({
      'lib/chip.tsx': CLIENT,
      'lib/index.ts': "export { chipClass } from './chip'\n",
      'lib/star.ts': "export * from './chip'\nexport const plain = () => 'plain'\n",
      'app/page.tsx': [
        "import { chipClass } from '@/lib/chip'",
        "import { chipClass as viaBarrel } from '@/lib'",
        "import { chipClass as viaStar, plain } from '@/lib/star'",
        "import * as ui from '@/lib/index'",
        'export default function Page() {',
        '  return <a className={[chipClass(), viaBarrel(), viaStar(), ui.chipClass(), plain()].join(" ")} />',
        '}',
      ].join('\n'),
    })
    expect(tree.scan('app/page.tsx')).toEqual([
      'app/page.tsx:6: chipClass() is an export of lib/chip.tsx',
      'app/page.tsx:6: viaBarrel() is an export of lib/chip.tsx',
      'app/page.tsx:6: viaStar() is an export of lib/chip.tsx',
      'app/page.tsx:6: ui.chipClass() is an export of lib/chip.tsx',
    ])
  })

  it('follows the server code down its imports, and stops at a client module', () => {
    const tree = memory({
      'lib/chip.tsx': CLIENT,
      'features/Hero.tsx': "import { chipClass } from '@/lib/chip'\nexport const Hero = () => <a className={chipClass()} />\n",
      'features/ClientCard.tsx': "'use client'\nimport { chipClass } from '@/lib/chip'\nexport const ClientCard = () => <a className={chipClass()} />\n",
      'features/OnlyFromClient.tsx': "import { chipClass } from '@/lib/chip'\nexport const Inner = () => <a className={chipClass()} />\n",
      'features/Wrapper.tsx': "'use client'\nimport { Inner } from './OnlyFromClient'\nexport const Wrapper = () => <Inner />\n",
      'app/page.tsx': [
        "import { Hero } from '@/features/Hero'",
        "import { ClientCard } from '@/features/ClientCard'",
        "import { Wrapper } from '@/features/Wrapper'",
        "import { Chip } from '@/lib/chip'",
        'export default function Page() { return <><Hero /><ClientCard /><Wrapper /><Chip /></> }',
      ].join('\n'),
    })
    // Rendering a client component is fine; only the server module's own call fails.
    expect(tree.scan('app/page.tsx')).toEqual(['features/Hero.tsx:2: chipClass() is an export of lib/chip.tsx'])
  })

  it('passes a re-exported server helper and a client page', () => {
    const tree = memory({
      'lib/chip.tsx': CLIENT,
      'lib/plain.ts': "export const plainClass = () => 'plain'\n",
      'lib/index.ts': "export * from './chip'\nexport * from './plain'\n",
      'app/page.tsx': "import { plainClass } from '@/lib'\nexport default function Page() { return <a className={plainClass()} /> }\n",
      'app/client/page.tsx': "'use client'\nimport { chipClass } from '@/lib'\nexport default function Page() { return <a className={chipClass()} /> }\n",
    })
    expect(tree.scan('app/page.tsx', 'app/client/page.tsx')).toEqual([])
  })
})

describe('server calls of client exports: the tree', () => {
  const g = graph(ROOT, readDisk)
  const entries = [
    ...walk(path.join(ROOT, 'app')).filter((file) => ROUTER_FILE.test(path.basename(file))),
    ...ROOT_SERVER_FILES.map((file) => path.join(ROOT, file)).filter(isFile),
  ]
  const server = g.serverModules(entries)
  const rel = (file: string) => path.relative(ROOT, file).split(path.sep).join('/')

  it('reaches the server code it guards, and resolves the ui barrel', () => {
    const files = new Set(server.map((m) => rel(m.file)))
    expect(files).toContain('app/page.tsx')
    expect(files).toContain('features/marketing/components/HeroExample.tsx')
    expect(files.size).toBeGreaterThan(50)
    const barrel = path.join(ROOT, 'components/ui/index.ts')
    expect(rel(g.clientOrigin(barrel, 'buttonVariants') ?? '')).toBe('components/ui/Button.tsx')
    expect(g.clientOrigin(barrel, 'cx')).toBeNull()
  })

  it('no server module calls an export of a client module', () => {
    expect(
      g.offenders(server),
      "An export of a 'use client' module is a client reference on the server: render it or pass it to a client " +
        'component, never call it. Move a shared helper (a class recipe, a formatter) into a module without the ' +
        'directive. See lessons/frontend-client-exports-need-next-build.md.',
    ).toEqual([])
  })
})
