import { existsSync, readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import ts from 'typescript'

/**
 * The module graph the brand and focus-ring gates walk (siteChromeFocusRing.spec.ts, brandCopyRules.spec.ts):
 * every module `roots` reach, transitively, through `@/` or relative imports (lazy `import('…')` included)
 * and re-exports, .ts barrels included. A module reached at all is read whole, but a named re-export
 * (`export { Modal } from './Modal'`) leads on only when a reached module takes that name; an `export *`
 * passes the names on. Type-only imports and re-exports render nothing and are not followed.
 *
 * A JSON module an import reaches is not returned: the walk resolves .ts and .tsx modules only, and the copy
 * gates (brandVoiceRules, no-em-dash-copy, brandCopyRules) read .ts and .tsx sources, so no copy gate reads
 * the strings a JSON module holds. Copy held in data a page imports is review-checked: today that is
 * features/analysis/demo/demo-analysis.json, which features/marketing/lib/landing-samples.ts (the landing's
 * samples) and features/analysis/components/AnalysisTeaser.tsx import.
 *
 * Paths are relative to `root` (the frontend directory), with forward slashes.
 */

const parse = (source: string, fileName: string) => ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)

/** The specifier of an `import('…')` call, the lazy form of an import (`dynamic(() => import('…'))`). */
export const lazyImport = (node: ts.Node): string | undefined =>
  ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword && node.arguments[0] && ts.isStringLiteralLike(node.arguments[0])
    ? node.arguments[0].text
    : undefined

export const isLocal = (spec: string) => spec.startsWith('@/') || spec.startsWith('.')

/** The names an import takes from its module: '*' for a namespace or side-effect import, 'default' for a default one. */
export function importedNames(clause: ts.ImportClause | undefined): Set<string> | '*' {
  if (!clause || (clause.namedBindings && ts.isNamespaceImport(clause.namedBindings))) return '*'
  const names = new Set<string>()
  if (clause.name) names.add('default')
  if (clause.namedBindings && ts.isNamedImports(clause.namedBindings)) {
    for (const el of clause.namedBindings.elements) if (!el.isTypeOnly) names.add((el.propertyName ?? el.name).text)
  }
  return names
}

/** Every module (.ts and .tsx) reached from `roots`, the roots included, sorted. */
export function walkImports(roots: string[], root: string): string[] {
  const resolveImport = (from: string, spec: string): string | null => {
    let base: string
    if (spec.startsWith('@/')) base = path.join(root, spec.slice(2))
    else if (spec.startsWith('.')) base = path.resolve(path.dirname(path.join(root, from)), spec)
    else return null
    for (const candidate of [`${base}.tsx`, `${base}.ts`, path.join(base, 'index.tsx'), path.join(base, 'index.ts')]) {
      if (existsSync(candidate)) return path.relative(root, candidate).split(path.sep).join('/')
    }
    return null
  }
  // What the walk takes from each module it reaches: all of it ('*') or the names it imports. A module
  // reached again for a name it was not taken for is read again, for the re-exports that name leads to.
  const taken = new Map<string, Set<string> | '*'>()
  const queue: string[] = []
  const take = (file: string | null, names: Set<string> | '*') => {
    if (!file || (names !== '*' && names.size === 0)) return
    const had = taken.get(file)
    if (had === '*' || (had && names !== '*' && [...names].every((name) => had.has(name)))) return
    taken.set(file, names === '*' || !had ? names : new Set([...had, ...names]))
    queue.push(file)
  }
  for (const file of roots) take(file, '*')
  while (queue.length) {
    const file = queue.shift()!
    const names = taken.get(file)!
    const sf = parse(readFileSync(path.join(root, file), 'utf8'), file)
    for (const stmt of sf.statements) {
      if (ts.isImportDeclaration(stmt) && !stmt.importClause?.isTypeOnly && ts.isStringLiteral(stmt.moduleSpecifier)) {
        take(resolveImport(file, stmt.moduleSpecifier.text), importedNames(stmt.importClause))
      } else if (ts.isExportDeclaration(stmt) && !stmt.isTypeOnly && stmt.moduleSpecifier && ts.isStringLiteral(stmt.moduleSpecifier)) {
        const target = resolveImport(file, stmt.moduleSpecifier.text)
        const clause = stmt.exportClause
        if (!clause) take(target, names)
        else if (ts.isNamespaceExport(clause)) take(target, names === '*' || names.has(clause.name.text) ? '*' : new Set())
        else {
          const picked = clause.elements.filter((el) => !el.isTypeOnly && (names === '*' || names.has(el.name.text)))
          take(target, new Set(picked.map((el) => (el.propertyName ?? el.name).text)))
        }
      }
    }
    // A module loaded lazily, wherever in the file its import() sits, is rendered all the same: taken whole.
    const lazy = (node: ts.Node): void => {
      const spec = lazyImport(node)
      if (spec !== undefined) take(resolveImport(file, spec), '*')
      ts.forEachChild(node, lazy)
    }
    lazy(sf)
  }
  return [...taken.keys()].sort()
}

/** Every file under `dir` (relative to `root`) whose name is one of `names`, sorted: the route files Next
    composes from the file system, which no import reaches. */
export function routeFiles(dir: string, names: string[], root: string): string[] {
  const out: string[] = []
  const walk = (rel: string) => {
    for (const entry of readdirSync(path.join(root, rel), { withFileTypes: true })) {
      const next = `${rel}/${entry.name}`
      if (entry.isDirectory()) walk(next)
      else if (names.includes(entry.name)) out.push(next)
    }
  }
  walk(dir)
  return out.sort()
}
