import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Metadata } from 'next'
import type { Company } from '@/features/companies/api/companies-api'
import type { Filing } from '@/features/filings/api/filings-api'
import { HEADLINES, pageTitleFor, type HeadlineVariant } from '@/features/marketing/lib/headline'
import { SOCIAL_CARD } from '@/lib/socialCard'
import { bindingResolver, containerEscape, type Binding } from './astBindings'

/**
 * Route metadata (D-038; docs/brand/08-applications.md §1). Every route names itself in the tab and in
 * a shared link's preview, page first and brand last, and every shared page previews with the site card:
 *
 *   1. Each route's title comes from its own page or from a layout in its own directory, never from the
 *      root default, which the root layout holds, so the home page titles itself; a 'use client' page
 *      cannot export metadata, so its directory carries a layout that does (as app/login/layout.tsx does).
 *   2. Every title reads '<Page name> | EarningsNerd' in sentence case (proper nouns, acronyms and the
 *      company's own name allowed), each headline variant the home page's experiment serves included. A
 *      generated page holds every title template it can return in that form, read with every substitution a
 *      name and in each reading of it (each branch of a condition, `||`, `??` or `&&`, a comma's right side,
 *      each same-file const a substitution names and each entry of a same-file object or array literal nothing
 *      writes after it is made read as its text, any other substitution as a name); a title template with more
 *      than 64 readings fails rather than be read in part. It titles every state (a title of undefined or
 *      null titles none).
 *   3. Every private route resolves robots to index: false. No public route resolves it to noindex
 *      from its page's static metadata or from any layout above the page, the root included: Next takes
 *      robots from the deepest segment that sets it, the page over its layouts. The two generated pages
 *      set none in their indexable states, so the layouts above them decide there; each keeps one state
 *      out by design (part 7). Each route is classified below, so a new route fails until someone
 *      decides which it is.
 *   4. Next replaces a nested openGraph or twitter wholesale, so every one a page or layout sets carries
 *      the site card itself ([SOCIAL_CARD], [SOCIAL_CARD.url]), in every object literal that sets one,
 *      whichever state of a generated page returns it; the root's carry no title or description, so Next
 *      fills both from each page.
 *   5. No description says 'AI-powered' or carries an em-dash.
 *   6. The card's URL with its cache-busting ?v= is typed only in lib/socialCard.ts.
 *   7. The two generateMetadata routes (company, filing) are run in each state with serverApi mocked;
 *      each state sets its own openGraph and twitter with the card, or neither, so the root's apply.
 *
 * The route files are every page and layout under app/ with an extension Next serves (next.config.js's
 * pageExtensions, else Next's default). Titles and descriptions are checked as Next reads them: each module
 * that exports metadata is imported and its metadata evaluated, so a string built from an imported constant
 * (a plan cap that lib/planLimits mirrors from config) is checked as it renders. The test runs in one
 * environment, so each must be one text in every environment. No process, window, document, global, self
 * or globalThis read reaches it, in its own file or through a name it reads: a name is followed to the
 * binding in scope (a key, a member or a parameter named window is not the global, and a type holds no
 * value), to its module's declarations and into every project module it imports, a namespace import's
 * member by its name (lib/featureFlags.ts reads each flag from process.env). And no name it reads changes
 * after its declaration: assigned again, written into, or, an object or array the file makes, handed whole
 * to a call or to another name (changeOf). That holds for the static metadata's title and description, its
 * openGraph's and its twitter's, every spread and computed key in those, and each state a generateMetadata
 * returns, where a call to lib/serverApi is the page's data (part 7 runs it), read for its arguments alone (in
 * static metadata it is followed into lib/serverApi like any call).
 * A route file names its metadata only in its declaration, so nothing writes it after. Robots and the card
 * are read from each file's TypeScript AST, and what that reading cannot see fails loudly; each static
 * module's evaluated robots and card are held to that reading too, so a write its literal does not show
 * fails in this environment as well.
 *
 * Limits, left to review and to part 7's runs: a value another module changes, or one held inside another
 * object or array before it changes; a package's code; a generated title built without a string or a
 * template that ends with the brand, read only in the states part 7 runs.
 */

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const APP = path.join(FRONTEND, 'app')
const rel = (file: string) => path.relative(FRONTEND, file).split(path.sep).join('/')

const BRAND = ' | EarningsNerd'
/** Capitalised mid-title by right: names, the brand, the feature's product name, the months. */
const PROPER_NOUNS = [
  'EarningsNerd',
  'Multi-Period Analysis',
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

/**
 * Titles owned by other open PRs or by off-limits pages, pinned exactly. An entry whose file no longer
 * carries its title fails as stale, so the list only shrinks: delete the entry when its fix lands, and lower
 * RESIDUE_MAX with it in the same commit.
 */
const TITLE_RESIDUE: Record<string, { title: string; why: string }> = {
  'app/privacy/page.tsx': { title: 'Privacy Policy | EarningsNerd', why: 'legal page, edited only with a legal-date bump' },
  'app/terms/page.tsx': { title: 'Terms of Service | EarningsNerd', why: 'legal page, edited only with a legal-date bump' },
}
const DESCRIPTION_RESIDUE: Record<string, { text: string; why: string }> = {
  'app/terms/page.tsx': {
    text: 'Terms of Service for EarningsNerd: the rules for using our AI-powered SEC filing analysis.',
    why: 'legal page, edited only with a legal-date bump',
  },
}
/** Each residue's size, an equality (lessons/test-allowlist-caps-are-equalities.md, D-040): it moves with its list. */
const RESIDUE_MAX = { titles: 2, descriptions: 1 }

/** Each route by its directory under app/ ('' is the home page). Private routes stay out of the index. */
const PRIVATE_ROUTES = [
  'admin/feedback', 'admin/invites', 'check-email', 'dashboard', 'dashboard/settings', 'dashboard/watchlist',
  'delete-account', 'forgot-password', 'login', 'register', 'reset-password', 'verify-email',
  // Default-off prototypes (lib/featureFlags.ts); each page sets its own robots.
  'labs/filing-redlines', 'labs/financial-refresh-review', 'labs/research-evidence-packs',
]
const PUBLIC_ROUTES = [
  '', 'analysis', 'calendar', 'company/[ticker]', 'contact', 'filing/[id]', 'pricing', 'privacy', 'search',
  'security', 'terms', 'waitlist',
]
/** The routes whose metadata is computed per request; part 7 runs them. */
const GENERATED = ['app/company/[ticker]/page.tsx', 'app/filing/[id]/page.tsx']

/** Sentence case after the brand suffix: only a sentence's first word, a proper noun or an acronym is capitalised. */
function titleProblems(title: string, names: string[] = []): string[] {
  if (!title.endsWith(BRAND)) return [`"${title}" does not end with "${BRAND}" (the page first, the brand last)`]
  let head = title.slice(0, -BRAND.length)
  const problems: string[] = []
  if (!head.trim()) problems.push(`"${title}" has no page name`)
  if (head.includes('|') || head.includes('EarningsNerd')) problems.push(`"${title}" names the brand before the page`)
  for (const name of [...names.filter(Boolean), ...PROPER_NOUNS]) head = head.split(name).join('Ⓝ')
  for (const sentence of head.split(/(?<=[.?!])\s+/)) {
    const words = sentence.split(/\s+/).map((w) => w.replace(/^[("'‘“]+|[)"'’”,.:;?!]+$/g, '')).filter(Boolean)
    words.slice(1).forEach((word) => {
      if (/^[A-Z][a-z]/.test(word)) problems.push(`"${title}": "${word}" is capitalised mid-title (sentence case)`)
    })
  }
  return problems
}

const descriptionProblems = (text: string): string[] => [
  ...(/AI-powered/i.test(text) ? [`"${text}" says "AI-powered"`] : []),
  ...(text.includes('—') ? [`"${text}" carries an em-dash`] : []),
]

/** An evaluated title or description: a string is checked; anything else (a title template's object, null) cannot be. */
const textProblems = (value: unknown, check: (text: string) => string[]): string[] =>
  typeof value === 'string'
    ? check(value)
    : value === null || value === undefined
      ? [`a title of ${String(value)} renders no title and drops the layout's`]
      : [`${JSON.stringify(value)} is not a string the spec can check (write the whole text)`]

// ── The route files ───────────────────────────────────────────────────────────────────────────────

const requireNode = createRequire(import.meta.url)
/** What next.config.js exports, as Next's config loader requires it. */
const NEXT_CONFIG: unknown = requireNode(path.join(FRONTEND, 'next.config.js'))
/** The extensions Next routes a page or a layout under: next.config.js's own list, else Next's default. */
const PAGE_EXTENSIONS: string[] =
  (NEXT_CONFIG as { pageExtensions?: string[] }).pageExtensions ??
  (requireNode('next/dist/server/config-shared') as { defaultConfig: { pageExtensions: string[] } }).defaultConfig.pageExtensions
const escapeRegExp = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const ROUTE_FILE = new RegExp(`^(page|layout)\\.(${PAGE_EXTENSIONS.map(escapeRegExp).join('|')})$`)

/** Every page and layout under a directory, under each extension Next serves. */
function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (ROUTE_FILE.test(entry.name)) out.push(p)
  }
  return out
}

interface RouteFile {
  file: string
  isClient: boolean
  /** Whether the module hands Next a `metadata` export in any form, so the title checks import it. */
  exportsMetadata: boolean
  /** The `export const metadata` object literal, when it is one: the robots and card readers need it. */
  metadata?: ts.ObjectLiteralExpression
  /** Why the file's metadata export cannot be read as an object literal, when it cannot. */
  unreadable?: string
  generates: boolean
  source: ts.SourceFile
}

/** `{ … } satisfies Metadata`, `{ … } as Metadata`, `<Metadata>{ … }` and parentheses still hold the object literal. */
const unwrap = (node: ts.Expression): ts.Expression =>
  ts.isSatisfiesExpression(node) || ts.isAsExpression(node) || ts.isTypeAssertionExpression(node) || ts.isParenthesizedExpression(node)
    ? unwrap(node.expression)
    : node

/** Each extension parsed as its own language, so a .ts file's `<Metadata>{ … }` reads as a type assertion, not JSX. */
const SCRIPT_KINDS: Record<string, ts.ScriptKind> = {
  '.tsx': ts.ScriptKind.TSX,
  '.ts': ts.ScriptKind.TS,
  '.jsx': ts.ScriptKind.JSX,
  '.js': ts.ScriptKind.JS,
}
const parse = (file: string, text: string) =>
  ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, SCRIPT_KINDS[path.extname(file)] ?? ts.ScriptKind.TSX)

/** Whether a declared name binds a name: itself, or a destructuring (`{ metadata }`, `[metadata]`) that holds it. */
const bindsName = (binding: ts.BindingName, name: string): boolean =>
  ts.isIdentifier(binding) ? binding.text === name : binding.elements.some((e) => !ts.isOmittedExpression(e) && bindsName(e.name, name))

// ── Names and their bindings ──────────────────────────────────────────────────────────────────────

/** A name that refers to nothing by itself: a member's, a key's, an attribute's or an import's own name. */
function isOwnName(n: ts.Identifier): boolean {
  const p = n.parent
  return (
    ((ts.isPropertyAccessExpression(p) || ts.isPropertyAssignment(p) || ts.isMethodDeclaration(p) || ts.isPropertySignature(p) ||
      ts.isPropertyDeclaration(p) || ts.isGetAccessorDeclaration(p) || ts.isSetAccessorDeclaration(p) || ts.isEnumMember(p) ||
      ts.isJsxAttribute(p)) && p.name === n) ||
    ((ts.isBindingElement(p) || ts.isImportSpecifier(p) || ts.isExportSpecifier(p)) && p.propertyName === n)
  )
}

/** A type holds no value: an annotation, an `as` or `satisfies` target, a type argument. An instantiation expression's value is read. */
function isTypeOnly(n: ts.Node): boolean {
  return ts.isTypeNode(n) && !ts.isExpressionWithTypeArguments(n)
}

/** Each file's lexical name resolution (astBindings.ts), built once. */
const RESOLVERS = new Map<ts.SourceFile, (ref: ts.Identifier) => Binding | undefined>()
function resolverOf(source: ts.SourceFile): (ref: ts.Identifier) => Binding | undefined {
  let resolve = RESOLVERS.get(source)
  if (!resolve) RESOLVERS.set(source, (resolve = bindingResolver(source)))
  return resolve
}

/** Each declaration's uses in its file (a name that resolves to it, other than its own name), found once per file. */
const USES = new Map<ts.SourceFile, Map<ts.Node, ts.Identifier[]>>()
function usesOf(decl: ts.Node, source: ts.SourceFile): ts.Identifier[] {
  let index = USES.get(source)
  if (!index) {
    const found = new Map<ts.Node, ts.Identifier[]>()
    const resolve = resolverOf(source)
    const visit = (n: ts.Node): void => {
      if (isTypeOnly(n)) return
      if (ts.isIdentifier(n) && !isOwnName(n)) {
        const binding = resolve(n)
        if (binding && n !== (binding.decl as { name?: ts.Node }).name) found.set(binding.decl, [...(found.get(binding.decl) ?? []), n])
      }
      n.forEachChild(visit)
    }
    visit(source)
    USES.set(source, (index = found))
  }
  return index.get(decl) ?? []
}

function readRouteFile(file: string, text = readFileSync(file, 'utf8')): RouteFile {
  const source = parse(file, text)
  const first = source.statements[0]
  const isClient = !!first && ts.isExpressionStatement(first) && ts.isStringLiteral(first.expression) && first.expression.text === 'use client'
  let exportsMetadata = false
  let metadata: ts.ObjectLiteralExpression | undefined
  let unreadable: string | undefined
  let generates = false
  let metadataDecl: ts.VariableDeclaration | undefined
  for (const stmt of source.statements) {
    // `export { metadata }` and `export * from` hand Next metadata this reading cannot see.
    if (ts.isExportDeclaration(stmt)) {
      const clause = stmt.exportClause
      const names = !clause ? ['*'] : ts.isNamedExports(clause) ? clause.elements.map((e) => e.name.text) : [clause.name.text]
      if (names.some((n) => ['*', 'metadata', 'generateMetadata'].includes(n))) unreadable = `${stmt.getText()} exports metadata the spec cannot read`
      if (names.some((n) => n === '*' || n === 'metadata')) exportsMetadata = true
      continue
    }
    const exported = ts.canHaveModifiers(stmt) && ts.getModifiers(stmt)?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword)
    if (!exported) continue
    if (ts.isVariableStatement(stmt)) {
      for (const decl of stmt.declarationList.declarations) {
        if (ts.isIdentifier(decl.name) && decl.name.text === 'metadata') {
          exportsMetadata = true
          metadataDecl = decl
          const value = decl.initializer && unwrap(decl.initializer)
          if (value && ts.isObjectLiteralExpression(value)) metadata = value
          else unreadable = `metadata is ${decl.initializer?.getText() ?? 'declared with no value'}, not an object literal the spec can read`
        }
        if (ts.isIdentifier(decl.name) && decl.name.text === 'generateMetadata') generates = true
        // A destructuring hands Next a metadata or generateMetadata export this reading cannot see.
        for (const name of ['metadata', 'generateMetadata']) {
          if (ts.isIdentifier(decl.name) || !bindsName(decl.name, name)) continue
          exportsMetadata ||= name === 'metadata'
          unreadable = `${name} is bound by ${decl.name.getText()}, which the spec cannot read`
        }
      }
    }
    if (ts.isFunctionDeclaration(stmt) && stmt.name?.text === 'generateMetadata') generates = true
  }
  // Next reads the export as the module leaves it: a write after the literal (`metadata.robots = …`,
  // `Object.assign(metadata, …)`, a name that holds it) is one this reading cannot see, so the file names its
  // metadata only in its declaration.
  const again = metadataDecl && !unreadable ? usesOf(metadataDecl, source)[0] : undefined
  if (again) {
    let statement: ts.Node = again
    while (!ts.isSourceFile(statement.parent) && !ts.isBlock(statement.parent)) statement = statement.parent
    const at = source.getLineAndCharacterOfPosition(again.getStart(source)).line + 1
    const text = statement.getText(source).replace(/\s+/g, ' ')
    unreadable = `metadata is named again after its declaration (line ${at}: ${text.length > 100 ? `${text.slice(0, 99)}…` : text}), so what Next reads may not be its literal`
  }
  return { file, isClient, exportsMetadata, metadata, unreadable, generates, source }
}

const ROUTE_FILES = walk(APP).map((file) => readRouteFile(file))
const byPath = new Map(ROUTE_FILES.map((rf) => [rel(rf.file), rf]))
const isPage = (rf: RouteFile) => path.basename(rf.file).startsWith('page.')
const PAGES = ROUTE_FILES.filter(isPage)
/** A route file's segment: its directory under app/ ('' is the root). */
const routeOf = (rf: RouteFile) => path.relative(APP, path.dirname(rf.file)).split(path.sep).join('/')

/** Each segment's page and layout, whatever its extension; a second one in a segment (page.tsx beside page.js) is a twin. */
const PAGE_IN = new Map<string, RouteFile>()
const LAYOUT_IN = new Map<string, RouteFile>()
const TWINS: string[] = []
for (const rf of ROUTE_FILES) {
  const bySegment = isPage(rf) ? PAGE_IN : LAYOUT_IN
  const twin = bySegment.get(routeOf(rf))
  if (twin) TWINS.push(`${rel(twin.file)} and ${rel(rf.file)}`)
  else bySegment.set(routeOf(rf), rf)
}
const ROOT_LAYOUT = LAYOUT_IN.get('')!

// next/font is compiled away by Next's build and its runtime module is empty, so the root layout's three
// loaders are stubbed for the import that reads its metadata.
vi.mock('next/font/google', () => {
  const font = () => ({ className: '', variable: '', style: { fontFamily: '' } })
  return { Inter: font, Geist_Mono: font, Newsreader: font }
})

/**
 * The metadata each module exports, evaluated: the module is imported, as Next imports it, so a title or a
 * description built from an imported constant is checked as it renders, never asked to be typed.
 */
const EVALUATED = new Map<RouteFile, Metadata | undefined>(
  await Promise.all(
    ROUTE_FILES.filter((rf) => rf.exportsMetadata).map(
      async (rf) => [rf, ((await import(/* @vite-ignore */ rf.file)) as { metadata?: Metadata }).metadata] as const,
    ),
  ),
)

/**
 * Every title and description an evaluated metadata object sets: its own, its openGraph's and its twitter's. A
 * title key set to null or undefined counts, since Next then renders no title and drops the layout's.
 */
function textsIn(meta: Metadata | undefined) {
  type Texts = { title?: unknown; description?: unknown }
  const scopes = ([meta, meta?.openGraph, meta?.twitter] as Array<Texts | null | undefined>).filter((scope): scope is Texts => !!scope)
  return {
    titles: scopes.filter((scope) => 'title' in scope).map((scope) => scope.title),
    descriptions: scopes.map((scope) => scope.description).filter((value) => value !== undefined && value !== null),
  }
}

// ── One text in every environment ─────────────────────────────────────────────────────────────────

/**
 * The globals a value reads the environment through: process (each flag in lib/featureFlags.ts reads
 * process.env), the browser's window and document, and the global object as globalThis, global or self.
 * A limit: its other names and the browser's other environment globals (`top`, `parent`, `frames`,
 * `navigator`, `location`) are not read, so a metadata text that reads one passes.
 */
const ENV_GLOBALS = new Set(['process', 'window', 'document', 'globalThis', 'global', 'self'])

/** The module whose calls fetch a generated page's data: part 7 runs each state with it mocked. */
const DATA_SOURCE = /^@\/lib\/serverApi$/

/** Project modules, parsed once; undefined where the path is not a file. */
const MODULES = new Map<string, ts.SourceFile | undefined>()
function moduleAt(file: string): ts.SourceFile | undefined {
  if (!MODULES.has(file)) MODULES.set(file, existsSync(file) && statSync(file).isFile() ? parse(file, readFileSync(file, 'utf8')) : undefined)
  return MODULES.get(file)
}

/** The module a project import names ('@/…' from the frontend root, './…' from the importer); a package is not followed. */
function importedModule(from: ts.SourceFile, specifier: string): ts.SourceFile | undefined {
  const base = specifier.startsWith('@/')
    ? path.join(FRONTEND, specifier.slice(2))
    : specifier.startsWith('.')
      ? path.resolve(path.dirname(from.fileName), specifier)
      : undefined
  if (base === undefined) return undefined
  for (const suffix of ['', '.ts', '.tsx', '.js', '.jsx', '/index.ts', '/index.tsx']) {
    const found = moduleAt(base + suffix)
    if (found) return found
  }
  return undefined
}

type Reached = Array<[ts.Node, ts.SourceFile]>

/**
 * What a name stands for at a module's top level: its declaration (a variable's whole declaration, so the name's
 * own binding is read with its value), or what it imports, followed to the module that declares it.
 */
function declarationsOf(name: string, source: ts.SourceFile, visiting = new Set<string>()): Reached {
  const out: Reached = []
  for (const stmt of source.statements) {
    if (ts.isVariableStatement(stmt)) {
      for (const decl of stmt.declarationList.declarations) if (bindsName(decl.name, name)) out.push([decl, source])
    } else if ((ts.isFunctionDeclaration(stmt) || ts.isClassDeclaration(stmt) || ts.isEnumDeclaration(stmt)) && stmt.name?.text === name) {
      out.push([stmt, source])
    } else if (ts.isImportDeclaration(stmt) && ts.isStringLiteral(stmt.moduleSpecifier) && stmt.importClause && !stmt.importClause.isTypeOnly) {
      const { name: local, namedBindings } = stmt.importClause
      const element = namedBindings && ts.isNamedImports(namedBindings) ? namedBindings.elements.find((e) => !e.isTypeOnly && e.name.text === name) : undefined
      const imported =
        local?.text === name
          ? 'default'
          : namedBindings && ts.isNamespaceImport(namedBindings) && namedBindings.name.text === name
            ? '*'
            : element && (element.propertyName ?? element.name).text
      const target = imported && importedModule(source, stmt.moduleSpecifier.text)
      if (target) out.push(...(imported === '*' ? ([[target, target]] as Reached) : exportsOf(imported!, target, visiting)))
    }
  }
  return out
}

/** Whether a module declares a name as a type alone (an interface or a type alias), which holds no value. */
const declaresType = (name: string, source: ts.SourceFile) =>
  source.statements.some((s) => (ts.isInterfaceDeclaration(s) || ts.isTypeAliasDeclaration(s)) && s.name.text === name)

/**
 * What a module exports under a name, followed through a local it renames and a re-export; a type exports no
 * value, and a name it cannot place otherwise reads the whole module.
 */
function exportsOf(name: string, source: ts.SourceFile, visiting = new Set<string>()): Reached {
  const key = `${source.fileName}#${name}`
  if (visiting.has(key)) return []
  visiting.add(key)
  const out: Reached = []
  for (const stmt of source.statements) {
    if (name === 'default' && ts.isExportAssignment(stmt)) out.push([stmt.expression, source])
    const isDefault = ts.canHaveModifiers(stmt) && ts.getModifiers(stmt)?.some((m) => m.kind === ts.SyntaxKind.DefaultKeyword)
    if (name === 'default' && isDefault) out.push([stmt, source])
    if (!ts.isExportDeclaration(stmt)) continue
    const from = stmt.moduleSpecifier && ts.isStringLiteral(stmt.moduleSpecifier) ? importedModule(source, stmt.moduleSpecifier.text) : undefined
    if (stmt.exportClause && ts.isNamedExports(stmt.exportClause)) {
      for (const e of stmt.exportClause.elements.filter((e) => e.name.text === name)) {
        const inner = (e.propertyName ?? e.name).text
        if (from) out.push(...exportsOf(inner, from, visiting))
        else if (inner !== name) out.push(...declarationsOf(inner, source, visiting))
      }
    } else if (!stmt.exportClause && from) out.push(...exportsOf(name, from, visiting))
  }
  if (name !== 'default') out.push(...declarationsOf(name, source, visiting))
  return out.length || declaresType(name, source) ? out : [[source, source]]
}

/** The module a namespace import's member reads, and the member's name: `limits.FREE_SUMMARY_LIMIT`, `limits['X']`. */
function namespaceMember(n: ts.Node, source: ts.SourceFile): { target: ts.SourceFile; name: string } | undefined {
  if (!ts.isPropertyAccessExpression(n) && !(ts.isElementAccessExpression(n) && ts.isStringLiteralLike(n.argumentExpression))) return undefined
  const holder = n.expression
  if (!ts.isIdentifier(holder) || resolverOf(source)(holder)) return undefined
  for (const stmt of source.statements) {
    if (!ts.isImportDeclaration(stmt) || !ts.isStringLiteral(stmt.moduleSpecifier) || stmt.importClause?.isTypeOnly) continue
    const bindings = stmt.importClause?.namedBindings
    if (!bindings || !ts.isNamespaceImport(bindings) || bindings.name.text !== holder.text) continue
    const target = importedModule(source, stmt.moduleSpecifier.text)
    const name = ts.isPropertyAccessExpression(n) ? n.name.text : (n.argumentExpression as ts.StringLiteralLike).text
    return target && { target, name }
  }
  return undefined
}

/** Whether a call fetches a generated page's data: its callee is imported from DATA_SOURCE. */
function dataCall(call: ts.CallExpression, source: ts.SourceFile): boolean {
  const callee = unwrap(call.expression)
  if (!ts.isIdentifier(callee) || resolverOf(source)(callee)) return false
  return source.statements.some(
    (s) =>
      ts.isImportDeclaration(s) && ts.isStringLiteral(s.moduleSpecifier) && DATA_SOURCE.test(s.moduleSpecifier.text) &&
      !!s.importClause?.namedBindings && ts.isNamedImports(s.importClause.namedBindings) &&
      s.importClause.namedBindings.elements.some((e) => e.name.text === callee.text),
  )
}

/** What a binding holds: a variable's value (destructured: the value its pattern takes apart, and each default on the way;
 *  a loop's: what it iterates), a parameter's default (a parameter is an input otherwise), a function's whole declaration. */
function valuesOf(binding: Binding): ts.Node[] {
  if (ts.isFunctionDeclaration(binding.decl)) return [binding.decl]
  const out: ts.Node[] = []
  let n: ts.Node = binding.decl
  for (; ts.isBindingElement(n) || ts.isObjectBindingPattern(n) || ts.isArrayBindingPattern(n); n = n.parent) {
    if (ts.isBindingElement(n) && n.initializer) out.push(n.initializer)
  }
  if ((ts.isVariableDeclaration(n) || ts.isParameter(n)) && n.initializer) out.push(n.initializer)
  const loop = ts.isVariableDeclaration(n) && ts.isVariableDeclarationList(n.parent) ? n.parent.parent : undefined
  if (loop && (ts.isForOfStatement(loop) || ts.isForInStatement(loop))) out.push(loop.expression)
  return out
}

const MUTATORS = new Set(['push', 'pop', 'shift', 'unshift', 'splice', 'sort', 'reverse', 'fill', 'copyWithin', 'set', 'add', 'delete', 'clear'])
const WRITERS = new Set(['Object.assign', 'Object.defineProperty', 'Object.defineProperties', 'Object.setPrototypeOf', 'Reflect.set', 'Reflect.defineProperty', 'Reflect.deleteProperty'])
/** Calls that read their argument and never change it. */
const READERS = new Set(['Object.keys', 'Object.values', 'Object.entries', 'Object.freeze', 'Object.isFrozen', 'Object.getOwnPropertyNames', 'JSON.stringify', 'Array.isArray', 'Array.from', 'structuredClone', 'String', 'Number', 'Boolean'])
const isAssignment = (kind: ts.SyntaxKind) => kind >= ts.SyntaxKind.FirstAssignment && kind <= ts.SyntaxKind.LastAssignment
const isGenerateMetadata = (fn: ts.Node) =>
  (ts.isFunctionDeclaration(fn) && fn.name?.text === 'generateMetadata') ||
  ((ts.isArrowFunction(fn) || ts.isFunctionExpression(fn)) && ts.isVariableDeclaration(fn.parent) && ts.isIdentifier(fn.parent.name) && fn.parent.name.text === 'generateMetadata')

/** Whether a node is a target its parent assigns to: the left side of `=`, or a slot of a destructuring that is. */
function assignedTo(node: ts.Node): boolean {
  let n = node
  while (ts.isArrayLiteralExpression(n.parent) || ts.isObjectLiteralExpression(n.parent) || ts.isSpreadElement(n.parent) || ts.isSpreadAssignment(n.parent) ||
    ts.isShorthandPropertyAssignment(n.parent) || (ts.isPropertyAssignment(n.parent) && n.parent.initializer === n) || ts.isParenthesizedExpression(n.parent)) n = n.parent
  const p = n.parent
  return (ts.isBinaryExpression(p) && p.left === n && isAssignment(p.operatorToken.kind)) || ((ts.isForOfStatement(p) || ts.isForInStatement(p)) && p.initializer === n)
}

/** How one use changes the binding it names, if it does (see changeOf). */
function changeAt(use: ts.Identifier, madeHere: boolean): string | undefined {
  // The access path the use roots: `x`, `x.a`, `x['a'].b`, through parentheses and casts.
  let top: ts.Node = use
  for (let p = top.parent; ; p = top.parent) {
    if ((ts.isPropertyAccessExpression(p) || ts.isElementAccessExpression(p)) && p.expression === top) top = p
    else if (ts.isParenthesizedExpression(p) || ts.isNonNullExpression(p) || ts.isAsExpression(p) || ts.isSatisfiesExpression(p) || ts.isTypeAssertionExpression(p)) top = p
    else break
  }
  const p = top.parent
  if (assignedTo(top)) return top === use ? 'is assigned' : 'is written into'
  if ((ts.isPrefixUnaryExpression(p) || ts.isPostfixUnaryExpression(p)) && (p.operator === ts.SyntaxKind.PlusPlusToken || p.operator === ts.SyntaxKind.MinusMinusToken)) return 'is assigned'
  if (ts.isDeleteExpression(p)) return 'is deleted from'
  if (ts.isCallExpression(p) && p.expression === top && top !== use) {
    const method = ts.isPropertyAccessExpression(top) ? top.name.text : ts.isElementAccessExpression(top) && ts.isStringLiteralLike(top.argumentExpression) ? top.argumentExpression.text : ''
    if (MUTATORS.has(method)) return `is changed by ${method}()`
  }
  if (ts.isCallExpression(p) && p.arguments.some((a) => a === top)) {
    const callee = p.expression.getText()
    if (WRITERS.has(callee) && p.arguments[0] === top) return `is written into by ${callee}()`
    if (madeHere && top === use && !READERS.has(callee)) return 'is handed to a call that may change it'
  }
  const heldAgain = (ts.isVariableDeclaration(p) && p.initializer === top) || (ts.isBinaryExpression(p) && p.right === top && isAssignment(p.operatorToken.kind))
  if (madeHere && top === use && heldAgain) return 'is held under another name that may change it'
  return undefined
}

/**
 * How a file changes a name after declaring it, if it does: a variable assigned again (`=`, `+=`, `++`, a
 * destructuring or a loop that assigns it) or written into (a member assigned or deleted, a mutating method such
 * as `push`, `Object.assign` and its kin), or, when it holds an object or an array the file makes, handed whole
 * to a call (one that only reads it, such as `Object.keys`, apart) or to another name, where it may change
 * unseen. Read for a module's names and for generateMetadata's own locals; a helper's locals are read with the
 * whole helper, its writes and their conditions included, and a parameter is an input. The use being read is
 * not a change.
 */
function changeOf(binding: Binding, reading: ts.Identifier, source: ts.SourceFile): { node: ts.Node; what: string } | undefined {
  let root: ts.Node = binding.decl
  while (ts.isBindingElement(root) || ts.isObjectBindingPattern(root) || ts.isArrayBindingPattern(root)) root = root.parent
  if (!ts.isVariableDeclaration(root)) return undefined
  for (let p: ts.Node | undefined = root.parent; p; p = p.parent) {
    if (ts.isFunctionLike(p)) {
      if (!isGenerateMetadata(p)) return undefined
      break
    }
  }
  const init = root.initializer && unwrap(root.initializer)
  const madeHere = root === binding.decl && !!init && (ts.isObjectLiteralExpression(init) || ts.isArrayLiteralExpression(init))
  for (const use of usesOf(binding.decl, source)) {
    if (use === reading) continue
    const what = changeAt(use, madeHere)
    if (what) return { node: use, what: `${use.text} ${what} after its declaration` }
  }
  return undefined
}

/**
 * Where a value can take another form in another environment, as 'file:line, what': an ENV_GLOBALS read in it, or
 * in what a name in it stands for, followed to the binding in scope (so a key, a member or a parameter named window
 * is never the global), its module's declarations and every project module it imports, a namespace import's member
 * by its name; or a name in it that its file changes after declaring it (changeOf). A type holds no value and is not
 * read. In what a generateMetadata returns (`generated`), a call to DATA_SOURCE is the page's data, read for its
 * arguments alone; anywhere else it is followed like any call, into the module's own reads.
 */
function envRead(node: ts.Node, source: ts.SourceFile, generated: boolean, seen = new Set<ts.Node>()): string | undefined {
  if (seen.has(node)) return undefined
  seen.add(node)
  const resolve = resolverOf(source)
  const at = (n: ts.Node, what: string) => `${rel(source.fileName)}:${source.getLineAndCharacterOfPosition(n.getStart(source)).line + 1}, ${what}`
  let found: string | undefined
  const follow = (n: ts.Node, file = source) => {
    found ??= envRead(n, file, generated, seen)
  }
  const visit = (n: ts.Node): void => {
    if (found || isTypeOnly(n)) return
    if (generated && ts.isCallExpression(n) && dataCall(n, source)) return n.arguments.forEach(visit)
    const member = namespaceMember(n, source)
    if (member) return exportsOf(member.name, member.target).forEach(([decl, file]) => follow(decl, file))
    if (!ts.isIdentifier(n)) return n.forEachChild(visit)
    if (isOwnName(n)) return
    const binding = resolve(n)
    if (binding) {
      const change = changeOf(binding, n, source)
      if (change) found = at(change.node, change.what)
      else valuesOf(binding).forEach((value) => follow(value))
      return
    }
    if (ENV_GLOBALS.has(n.text)) found = at(n, `reads ${n.text}`)
    else declarationsOf(n.text, source).forEach(([decl, file]) => follow(decl, file))
  }
  visit(node)
  return found
}

/**
 * Each node a metadata object takes a title or a description from, its own, its openGraph's and its twitter's:
 * each scope's `title` and `description` members, every spread and computed key in a scope (either may hold
 * one), and an openGraph or a twitter that is not an object literal, whole.
 */
function textMembers(metadata: ts.ObjectLiteralExpression): Array<[string, ts.Node]> {
  const scopes: Array<[string, ts.ObjectLiteralExpression]> = [['', metadata]]
  const out: Array<[string, ts.Node]> = []
  for (const key of ['openGraph', 'twitter']) {
    const set = member(metadata, key)
    if (!set) continue
    const value = ts.isPropertyAssignment(set) ? unwrap(set.initializer) : undefined
    if (value && ts.isObjectLiteralExpression(value)) scopes.push([`${key}.`, value])
    else out.push([key, ts.isShorthandPropertyAssignment(set) ? set.name : (value ?? set)])
  }
  for (const [prefix, scope] of scopes) {
    for (const key of ['title', 'description']) {
      const m = member(scope, key)
      if (m) out.push([`${prefix}${key}`, ts.isPropertyAssignment(m) ? m.initializer : ts.isShorthandPropertyAssignment(m) ? m.name : m])
    }
    for (const p of scope.properties) {
      const scopeName = prefix ? `${prefix.slice(0, -1)}'s` : 'its'
      if (ts.isSpreadAssignment(p)) out.push([`${scopeName} spread of ${p.expression.getText()}`, p.expression])
      else if (p.name && ts.isComputedPropertyName(p.name)) out.push([`${scopeName} computed key [${p.name.expression.getText()}]`, p])
    }
  }
  return out
}

/**
 * Each title or description a route file sets that can take another form in another environment, where the test
 * sees one: its static metadata's, and each state its generateMetadata returns.
 */
const envProblems = (rf: RouteFile): string[] =>
  [
    ...(rf.metadata ? [{ literal: rf.metadata, generated: false }] : []),
    ...(rf.generates ? returnedStates(rf).states.map((literal) => ({ literal, generated: true })) : []),
  ].flatMap(({ literal, generated }) =>
    textMembers(literal).flatMap(([key, node]) => {
      const at = envRead(node, rf.source, generated)
      return at ? [`${rel(rf.file)}: ${key} can differ by environment (${at}), so this test checks one form of it`] : []
    }),
  )

// ── The AST reading: robots and the card ──────────────────────────────────────────────────────────

const prop = (obj: ts.ObjectLiteralExpression, name: string) =>
  obj.properties.find((p): p is ts.PropertyAssignment => ts.isPropertyAssignment(p) && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) && p.name.text === name)

/** A member of an object literal by its name, in any form: `name: value`, the shorthand `name`, a method. */
const member = (obj: ts.ObjectLiteralExpression, name: string) =>
  obj.properties.find((p) => !!p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) && p.name.text === name)

const UNREADABLE = Symbol('a robots the spec cannot read')

/**
 * The robots a file's static metadata sets: undefined when it sets none, and UNREADABLE when it may set one
 * this reading cannot see (a metadata export that is not an object literal, a spread or a computed key in
 * the metadata, or a robots that is not a plain `robots: …` property). Every robots check reads through it.
 */
function robotsOf(rf: RouteFile): ts.Expression | typeof UNREADABLE | undefined {
  if (rf.unreadable) return UNREADABLE
  if (!rf.metadata) return undefined
  if (rf.metadata.properties.some((p) => ts.isSpreadAssignment(p) || (p.name && ts.isComputedPropertyName(p.name)))) return UNREADABLE
  const robots = member(rf.metadata, 'robots')
  if (!robots) return undefined
  return ts.isPropertyAssignment(robots) ? robots.initializer : UNREADABLE
}

/**
 * Whether a robots value keeps its page out of an index, as Next renders it (resolveRobots in
 * next/dist/lib/metadata/resolvers/resolve-basics.js). A string goes out as written. An object goes out as
 * index or noindex from its index (an absent one writes neither) plus its other directives, and its
 * googleBot, a string or an object of the same shape, goes out as a googlebot tag of its own, which Google
 * obeys alongside robots. So noindex is: a `noindex`, `none` or `unavailable_after` directive in a string;
 * an index that is not the literal true; an `unavailable_after` key (the page leaves the index on that
 * date); or a googleBot that is any of these. A value or key this reading cannot see counts as noindex
 * too, so it fails loudly and is written as a literal instead.
 */
function robotsNoindex(robots: ts.Expression): boolean {
  if (ts.isStringLiteralLike(robots)) return robots.text.split(/[\s,]+/).some((d) => /^(noindex|none|unavailable_after(:.*)?)$/i.test(d))
  if (!ts.isObjectLiteralExpression(robots)) return true
  if (robots.properties.some((p) => !ts.isPropertyAssignment(p) || !(ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)))) return true
  const index = prop(robots, 'index')?.initializer
  const googleBot = prop(robots, 'googleBot')?.initializer
  return (!!index && index.kind !== ts.SyntaxKind.TrueKeyword) || !!prop(robots, 'unavailable_after') || (!!googleBot && robotsNoindex(googleBot))
}

/** Whether a file's static metadata keeps its route out of the index: undefined when it sets no robots. */
function setsNoindex(rf: RouteFile): boolean | undefined {
  const robots = robotsOf(rf)
  return robots === undefined ? undefined : robots === UNREADABLE || robotsNoindex(robots)
}

/** What a page-level openGraph or twitter must carry: the site card itself, not any image and not none. */
const CARD_IMAGES = { openGraph: '[SOCIAL_CARD]', twitter: '[SOCIAL_CARD.url]' } as const
function cardProblems(obj: ts.ObjectLiteralExpression, key: keyof typeof CARD_IMAGES): string[] {
  const set = member(obj, key)
  if (!set) return []
  const scope = ts.isPropertyAssignment(set) ? set.initializer : undefined
  if (!scope || !ts.isObjectLiteralExpression(scope)) return [`${key} is ${(scope ?? set).getText()}, not an object literal the spec can read`]
  const imagesProp = prop(scope, 'images')
  const images = imagesProp?.initializer.getText().replace(/\s+/g, '')
  // A spread after the images may replace them; one before them cannot.
  const later = imagesProp ? scope.properties.slice(scope.properties.indexOf(imagesProp) + 1).filter(ts.isSpreadAssignment) : []
  return [
    ...(images === CARD_IMAGES[key]
      ? []
      : [`${key}.images is ${images ?? 'missing'}, not ${CARD_IMAGES[key]} (a page-level ${key} replaces the root one, images included)`]),
    ...later.map((spread) => `${key} spreads ${spread.expression.getText()} after its images, which may replace the card`),
  ]
}

/** Every object literal in a file that sets openGraph or twitter: the static metadata, and each state a generated page returns. */
function socialLiterals(source: ts.SourceFile): ts.ObjectLiteralExpression[] {
  const out: ts.ObjectLiteralExpression[] = []
  const visit = (node: ts.Node) => {
    if (ts.isObjectLiteralExpression(node) && (member(node, 'openGraph') || member(node, 'twitter'))) out.push(node)
    node.forEachChild(visit)
  }
  visit(source)
  return out
}

/** The most readings one title template is expanded into (each condition doubles them); a title template with more
    fails (titleTemplates), so no reading is dropped unread. */
const MAX_TEMPLATE_READINGS = 64
/** What stands in for the readings past MAX_TEMPLATE_READINGS: it rides on into every reading built from it. */
const MORE = '\u0000'
/** Each text the parts render, in order, the same text once; past MAX_TEMPLATE_READINGS, the rest are one MORE. */
const readings = (parts: string[][]): string[] =>
  parts.reduce<string[]>((heads, options) => {
    const next = [...new Set(heads.flatMap((head) => options.map((option) => head + option)))]
    return next.length > MAX_TEMPLATE_READINGS ? [...next.slice(0, MAX_TEMPLATE_READINGS), MORE] : next
  }, [''])

/** What stands in for a same-file container this spec cannot read whole, with the reason between two of them: it rides
    on into every reading built from it, and a title template with one fails (titleTemplates), never read as a name. */
const UNREAD = '\u0001'
const unread = (why: string) => `${UNREAD}${why}${UNREAD}`

/** The one text an expression the file writes renders (a literal, a same-file const, a branch-free template); null for
    any other, a name or a choice among texts. */
const staticKey = (expression: ts.Expression, source: ts.SourceFile, seen: Set<ts.Node>): string | null => {
  const texts = substitutionTexts(expression, source, seen)
  return texts.length === 1 && ![UNREAD, MORE, 'Ⓝ'].some((mark) => texts[0].includes(mark)) ? texts[0] : null
}

/** The key a member is read by: a written name, or a key the file writes (staticKey); null for any other key. */
const memberKey = (e: ts.PropertyAccessExpression | ts.ElementAccessExpression, source: ts.SourceFile, seen: Set<ts.Node>): string | null =>
  ts.isPropertyAccessExpression(e) ? e.name.text : staticKey(e.argumentExpression, source, seen)

type Container = ts.ObjectLiteralExpression | ts.ArrayLiteralExpression

/**
 * What a container literal holds at a key, every entry for a key the file does not write, or why this cannot say. An
 * object gives a key the last entry written for it, so the entries are read from the end: a spread, a computed key the
 * file does not write (staticKey) or a method or accessor met before the key's own entry may give it another value
 * (Codex on 8a27892c: a computed key the file writes, `{ ['otc']: … }`, is read as that key). An array is read by its
 * index; a spread or a hole in it is not read. A key the literal does not hold renders "undefined".
 */
function entriesAt(literal: Container, key: string | null, source: ts.SourceFile, seen: Set<ts.Node>): { entries: ts.Expression[] } | { why: string } {
  if (ts.isArrayLiteralExpression(literal)) {
    const gap = literal.elements.find((element) => ts.isSpreadElement(element) || ts.isOmittedExpression(element))
    if (gap) return { why: ts.isSpreadElement(gap) ? 'a spread' : 'a hole' }
    if (key === null) return { entries: [...literal.elements] }
    const at = Number(key)
    return { entries: Number.isInteger(at) && at >= 0 && at < literal.elements.length ? [literal.elements[at]] : [] }
  }
  const out: ts.Expression[] = []
  for (const property of [...literal.properties].reverse()) {
    if (ts.isSpreadAssignment(property)) return { why: 'a spread' }
    const name = ts.isComputedPropertyName(property.name) ? staticKey(property.name.expression, source, seen) : property.name.text
    if (name === null) return { why: 'a computed key' }
    if (key !== null && name !== key) continue
    if (ts.isPropertyAssignment(property)) out.push(property.initializer)
    else if (ts.isShorthandPropertyAssignment(property)) out.push(property.name)
    else return { why: 'a method or an accessor' }
    if (key !== null) break
  }
  return { entries: out }
}

/**
 * The object or array literal an expression holds, through a same-file const, `Object.freeze` or the one entry such a
 * literal holds at a member's key, or why this cannot read it whole: something may change it after it is made
 * (astBindings' containerEscape: a write into it, a call it is handed to, an export). Anything else, undefined: a value
 * the file does not hold as a container. `seen` carries the consts followed, so a literal that names itself ends.
 */
function heldContainer(expression: ts.Expression, source: ts.SourceFile, seen: Set<ts.Node>): { literal: Container; seen: Set<ts.Node> } | { why: string } | undefined {
  let e = unwrap(expression)
  while (ts.isNonNullExpression(e)) e = unwrap(e.expression)
  let node: ts.Expression = e
  let next = seen
  if (ts.isIdentifier(e)) {
    const decl = resolverOf(source)(e)?.decl
    if (!decl || !ts.isVariableDeclaration(decl) || !decl.initializer || !(decl.parent.flags & ts.NodeFlags.Const) || seen.has(decl)) return undefined
    node = unwrap(decl.initializer)
    next = new Set([...seen, decl])
  } else if (ts.isPropertyAccessExpression(e) || ts.isElementAccessExpression(e)) {
    const outer = heldContainer(e.expression, source, seen)
    if (!outer || 'why' in outer) return outer
    const at = entriesAt(outer.literal, memberKey(e, source, seen), source, outer.seen)
    if ('why' in at) return at
    if (at.entries.length !== 1) return undefined
    node = unwrap(at.entries[0])
    next = outer.seen
  }
  if (ts.isCallExpression(node) && node.arguments.length === 1 && node.expression.getText(source) === 'Object.freeze') node = unwrap(node.arguments[0])
  if (!ts.isObjectLiteralExpression(node) && !ts.isArrayLiteralExpression(node)) return undefined
  const escape = containerEscape(node, source, resolverOf(source))
  if (escape) return { why: `${escape.how} at line ${source.getLineAndCharacterOfPosition(escape.at.getStart(source)).line + 1}` }
  return { literal: node, seen: next }
}

/**
 * The texts a template substitution can render: a literal's own, each branch of a condition, `||`, `??` or `&&` (whose
 * left side renders where it does not hold, read as its own texts), a comma's right side, a `+` chain's and a nested
 * template's readings, what a same-file const holds, and what a same-file object or array literal holds at a member's
 * key (heldContainer, entriesAt), every entry for a key the file does not write (Codex on 5291bc97). A container this
 * cannot read whole (one something may change, or one whose spread, computed key or accessor may give the key its
 * value) reads as UNREAD, which fails a title (Codex on 8a27892c). Anything else (a name the file does not hold as a
 * const, a call, a member of any other value) reads as a name, Ⓝ.
 */
function substitutionTexts(expression: ts.Expression, source: ts.SourceFile, seen = new Set<ts.Node>()): string[] {
  const e = unwrap(expression)
  if (ts.isStringLiteralLike(e) || ts.isNumericLiteral(e)) return [e.text]
  if (ts.isTemplateExpression(e)) return templateTexts(e, source, seen)
  if (ts.isConditionalExpression(e)) return [...substitutionTexts(e.whenTrue, source, seen), ...substitutionTexts(e.whenFalse, source, seen)]
  if (ts.isBinaryExpression(e)) {
    const op = e.operatorToken.kind
    if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken || op === ts.SyntaxKind.AmpersandAmpersandToken) {
      return [...substitutionTexts(e.left, source, seen), ...substitutionTexts(e.right, source, seen)]
    }
    if (op === ts.SyntaxKind.CommaToken) return substitutionTexts(e.right, source, seen)
    if (op === ts.SyntaxKind.PlusToken) return readings([substitutionTexts(e.left, source, seen), substitutionTexts(e.right, source, seen)])
  }
  if (ts.isPropertyAccessExpression(e) || ts.isElementAccessExpression(e)) {
    const held = heldContainer(e.expression, source, seen)
    if (held && 'why' in held) return [unread(held.why)]
    if (held) {
      const at = entriesAt(held.literal, memberKey(e, source, seen), source, held.seen)
      if ('why' in at) return [unread(at.why)]
      return at.entries.length ? at.entries.flatMap((entry) => substitutionTexts(entry, source, held.seen)) : ['undefined']
    }
  }
  if (ts.isIdentifier(e)) {
    const binding = resolverOf(source)(e)
    const decl = binding?.decl
    if (decl && ts.isVariableDeclaration(decl) && decl.initializer && decl.parent.flags & ts.NodeFlags.Const && !seen.has(decl)) {
      return substitutionTexts(decl.initializer, source, new Set([...seen, decl]))
    }
  }
  return ['Ⓝ']
}
const templateTexts = (t: ts.TemplateExpression, source: ts.SourceFile, seen = new Set<ts.Node>()): string[] =>
  readings([[t.head.text], ...t.templateSpans.flatMap((span) => [substitutionTexts(span.expression, source, seen), [span.literal.text]])])

/**
 * Every title template in a file: a string or a template literal that ends with the brand, a template read with
 * every substitution a name (Ⓝ), so a word after one is mid-title whatever it holds, and in each reading of it
 * (substitutionTexts). A title template with more than MAX_TEMPLATE_READINGS readings fails, never read in part, and
 * so does one with a reading that ends without the brand: a template some reading of which ends with it is a title,
 * so a state the file holds text for that drops it breaks the route-title rule (Codex on c0d1e726). The reading with
 * every substitution a name is apart, since it ends without the brand wherever a substitution holds it.
 */
function titleTemplates(source: ts.SourceFile): string[] {
  const out: string[] = []
  const visit = (n: ts.Node): void => {
    if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) {
      if (n.text.endsWith(BRAND)) out.push(n.text)
    } else if (ts.isTemplateExpression(n)) {
      const read = templateTexts(n, source)
      const texts = [n.head.text + n.templateSpans.map((span) => `Ⓝ${span.literal.text}`).join(''), ...read]
      const titled = texts.filter((text) => text.endsWith(BRAND))
      const line = () => source.getLineAndCharacterOfPosition(n.getStart(source)).line + 1
      if (titled.length && texts.some((text) => text.includes(MORE))) {
        throw new Error(`${rel(source.fileName)}:${line()}: the title template ${n.getText(source)} has more than ${MAX_TEMPLATE_READINGS} readings, more than this spec reads: write the title each state takes as its own template, so every reading is read`)
      }
      const unreadable = texts.find((text) => text.includes(UNREAD))
      if (titled.length && unreadable) {
        throw new Error(`${rel(source.fileName)}:${line()}: the title template ${n.getText(source)} reads a same-file container this spec cannot read whole (${unreadable.split(UNREAD)[1]}): write its entries as plain keys and values, or each state's title as its own template`)
      }
      const unbranded = read.filter((text) => !text.endsWith(BRAND))
      if (titled.length && unbranded.length) {
        throw new Error(`${rel(source.fileName)}:${line()}: the title template ${n.getText(source)} reads ${unbranded.map((text) => JSON.stringify(text)).join(', ')} in some state, without "${BRAND.trim()}" at its end: every state's title ends with the brand`)
      }
      out.push(...titled)
    }
    n.forEachChild(visit)
  }
  visit(source)
  return [...new Set(out)]
}

/** Whether a returned state titles nothing: no title, or one written as undefined, null or void, which Next renders as none. */
function untitled(state: ts.ObjectLiteralExpression): boolean {
  const title = member(state, 'title')
  if (!title) return true
  if (!ts.isPropertyAssignment(title)) return false
  const value = unwrap(title.initializer)
  return value.kind === ts.SyntaxKind.NullKeyword || ts.isVoidExpression(value) || (ts.isIdentifier(value) && value.text === 'undefined')
}

/** Whether an evaluated robots keeps its page out of an index, as robotsNoindex reads a literal: undefined when unset. */
function evaluatedNoindex(robots: unknown): boolean | undefined {
  if (robots === undefined || robots === null) return undefined
  if (typeof robots === 'string') return robots.split(/[\s,]+/).some((d) => /^(noindex|none|unavailable_after(:.*)?)$/i.test(d))
  if (typeof robots !== 'object') return true
  const { index, unavailable_after: until, googleBot } = robots as Record<string, unknown>
  return (index !== undefined && index !== true) || until !== undefined || (googleBot !== undefined && evaluatedNoindex(googleBot) === true)
}

/** What a static metadata literal alone says of robots, as setsNoindex reads it: undefined when it sets none, null where a
    spread, a computed key or a robots that is not a plain property leaves the literal silent on it. */
function literalNoindex(rf: RouteFile): boolean | undefined | null {
  if (!rf.metadata || rf.metadata.properties.some((p) => ts.isSpreadAssignment(p) || (p.name && ts.isComputedPropertyName(p.name)))) return null
  const robots = member(rf.metadata, 'robots')
  if (!robots) return undefined
  return ts.isPropertyAssignment(robots) ? robotsNoindex(robots.initializer) : null
}

/** The states a file's generateMetadata returns, each an object literal; a return of anything else is reported. */
function returnedStates(rf: RouteFile): { states: ts.ObjectLiteralExpression[]; unreadable: string[] } {
  const states: ts.ObjectLiteralExpression[] = []
  const unreadable: string[] = []
  const line = (n: ts.Node) => rf.source.getLineAndCharacterOfPosition(n.getStart(rf.source)).line + 1
  const returned = (value: ts.Expression | undefined, at: ts.Node) => {
    const literal = value && unwrap(value)
    if (literal && ts.isObjectLiteralExpression(literal)) states.push(literal)
    else unreadable.push(`${rel(rf.file)}:${line(at)}: generateMetadata returns ${value?.getText() ?? 'nothing'}, not an object literal the spec can read`)
  }
  const visit = (n: ts.Node): void => {
    if (ts.isFunctionLike(n)) return // a nested function's returns are its own
    if (ts.isReturnStatement(n)) returned(n.expression, n)
    n.forEachChild(visit)
  }
  for (const stmt of rf.source.statements) {
    const fns: Array<ts.FunctionLikeDeclaration | undefined> = ts.isFunctionDeclaration(stmt) && stmt.name?.text === 'generateMetadata'
      ? [stmt]
      : ts.isVariableStatement(stmt)
        ? stmt.declarationList.declarations
            .filter((d) => ts.isIdentifier(d.name) && d.name.text === 'generateMetadata')
            .map((d) => (d.initializer && (ts.isArrowFunction(d.initializer) || ts.isFunctionExpression(d.initializer)) ? d.initializer : undefined))
        : []
    for (const fn of fns) {
      if (!fn?.body) unreadable.push(`${rel(rf.file)}: generateMetadata is not a function the spec can read`)
      else if (ts.isBlock(fn.body)) fn.body.forEachChild(visit)
      else returned(fn.body, fn.body)
    }
  }
  return { states, unreadable }
}

/** The page, then its own layout, then each ancestor layout up to the root: Next's resolution order, deepest first. */
function chain(route: string): RouteFile[] {
  const out: RouteFile[] = []
  const page = PAGE_IN.get(route)
  if (page) out.push(page)
  const parts = route ? route.split('/') : []
  for (let i = parts.length; i >= 0; i -= 1) {
    const layout = LAYOUT_IN.get(parts.slice(0, i).join('/'))
    if (layout) out.push(layout)
  }
  return out
}

describe('route metadata: every route names itself, page first and brand last', () => {
  it('finds the routes it guards (the scan stays meaningful)', () => {
    expect(typeof NEXT_CONFIG, 'next.config.js exports an object, so its pageExtensions is the list Next reads').toBe('object')
    expect(PAGES.length).toBeGreaterThanOrEqual(24)
    expect([...EVALUATED.values()].filter(Boolean).length).toBeGreaterThanOrEqual(23)
    expect(TWINS, 'a segment holds one page and one layout (Next serves one of them)').toEqual([])
  })

  it('classifies every route as public or private', () => {
    const routes = PAGES.map(routeOf).sort()
    expect(routes.filter((r) => !PRIVATE_ROUTES.includes(r) && !PUBLIC_ROUTES.includes(r)), 'routes neither public nor private').toEqual([])
    expect([...PRIVATE_ROUTES, ...PUBLIC_ROUTES].filter((r) => !routes.includes(r)), 'classified routes that no longer exist').toEqual([])
  })

  it.each(PAGES.map((p) => [routeOf(p) || '/', p] as const))('%s takes its title from its own page or layout', (_route, page) => {
    const route = routeOf(page)
    // The root layout holds the site default, not the home page's own title: for '/' only the page counts.
    const layout = route ? LAYOUT_IN.get(route) : undefined
    const titled = (rf?: RouteFile) => !!rf && (rf.generates || EVALUATED.get(rf)?.title != null)
    if (page.isClient) expect(titled(layout), `${rel(page.file)} is a client page with no layout beside it exporting a metadata title`).toBe(true)
    expect(titled(page) || titled(layout), `${rel(page.file)} has no title of its own, so its tab reads the root default`).toBe(true)
  })

  it('reads every metadata export as an object literal, the form the robots and card readers take', () => {
    expect(ROUTE_FILES.flatMap((rf) => (rf.unreadable ? [`${rel(rf.file)}: ${rf.unreadable}`] : []))).toEqual([])
    expect(ROUTE_FILES.filter((rf) => rf.generates).map((rf) => rel(rf.file)).sort(), 'generateMetadata routes this spec runs').toEqual(GENERATED)
  })

  it.each([...EVALUATED].map(([rf, meta]) => [rel(rf.file), meta] as const))('%s writes its titles as "Page name | EarningsNerd" in sentence case', (name, meta) => {
    const residue = TITLE_RESIDUE[name]?.title
    expect(textsIn(meta).titles.filter((t) => t !== residue).flatMap((t) => textProblems(t, (text) => titleProblems(text)))).toEqual([])
  })

  it('writes each title and description as one text in every environment (no flag or env read reaches it)', () => {
    expect(ROUTE_FILES.flatMap((rf) => envProblems(rf))).toEqual([])
  })

  it('titles the home page in that form for every headline variant (HeroHeadline gives the tab the served one)', () => {
    expect((Object.keys(HEADLINES) as HeadlineVariant[]).map(pageTitleFor).flatMap((t) => titleProblems(t))).toEqual([])
  })

  it.each(ROUTE_FILES.filter((rf) => rf.generates).map((rf) => [rel(rf.file), rf] as const))(
    '%s titles every state it returns, and writes each title template in the form',
    (name, rf) => {
      // Part 7 runs the states it lists; these read every state the code returns and every title it can build.
      const { states, unreadable } = returnedStates(rf)
      const line = (n: ts.Node) => rf.source.getLineAndCharacterOfPosition(n.getStart(rf.source)).line + 1
      const untitledStates = states
        .filter(untitled)
        .map((obj) => `${name}:${line(obj)} returns a state with no title (or one of undefined or null), so its tab reads the root default`)
      expect(states.length, `${name} returns no state the spec can read`).toBeGreaterThan(0)
      expect([...unreadable, ...untitledStates, ...titleTemplates(rf.source).flatMap((t) => titleProblems(t))]).toEqual([])
    },
  )

  it.each(Object.entries(TITLE_RESIDUE))('residue %s still carries its pinned title (delete the entry once fixed)', (name, { title }) => {
    const rf = byPath.get(name)
    expect(textsIn(rf && EVALUATED.get(rf)).titles, `stale residue: ${name}`).toContain(title)
  })

  it.each(ROUTE_FILES.filter((rf) => EVALUATED.has(rf) || rf.generates).map((rf) => [rel(rf.file), rf] as const))('%s writes descriptions with no "AI-powered" and no em-dash', (name, rf) => {
    const residue = DESCRIPTION_RESIDUE[name]?.text
    const texts: unknown[] = textsIn(EVALUATED.get(rf)).descriptions
    // generateMetadata builds its strings from parts: read every literal inside it and the helpers beside it.
    if (rf.generates) {
      const visit = (node: ts.Node) => {
        if (ts.isStringLiteralLike(node) || ts.isTemplateLiteralToken(node)) texts.push(node.text)
        node.forEachChild(visit)
      }
      rf.source.statements.filter((s) => !ts.isImportDeclaration(s)).forEach(visit)
    }
    expect(texts.filter((t) => t !== residue).flatMap((t) => textProblems(t, descriptionProblems))).toEqual([])
  })

  it.each(Object.entries(DESCRIPTION_RESIDUE))('residue %s still carries its pinned description (delete the entry once fixed)', (name, { text }) => {
    const rf = byPath.get(name)
    expect(textsIn(rf && EVALUATED.get(rf)).descriptions, `stale residue: ${name}`).toContain(text)
  })

  it('holds each residue at its size (an equality, never a ceiling)', () => {
    expect(Object.keys(TITLE_RESIDUE).length, 'TITLE_RESIDUE changed its entries: move RESIDUE_MAX.titles with it in the same commit').toBe(RESIDUE_MAX.titles)
    expect(Object.keys(DESCRIPTION_RESIDUE).length, 'DESCRIPTION_RESIDUE changed its entries: move RESIDUE_MAX.descriptions with it in the same commit').toBe(
      RESIDUE_MAX.descriptions,
    )
  })

  it.each(PRIVATE_ROUTES.map((r) => [r] as const))('private route /%s stays out of the index', (route) => {
    // The deepest segment that sets robots decides it, as Next resolves it; only a literal { index: false } passes.
    const setter = chain(route).find((rf) => robotsOf(rf) !== undefined)
    const robots = setter && robotsOf(setter)
    const index = robots && robots !== UNREADABLE && ts.isObjectLiteralExpression(robots) ? prop(robots, 'index')?.initializer : undefined
    expect(index?.kind, `/${route} does not resolve robots to { index: false }`).toBe(ts.SyntaxKind.FalseKeyword)
  })

  it.each(PUBLIC_ROUTES.map((r) => [r] as const))('public route /%s stays in the index', (route) => {
    // The deepest segment that sets robots decides it, as Next resolves it (mergeMetadata assigns robots per
    // segment, root to leaf, page last); the root layout counts. A generated page has no static metadata and
    // sets no robots in its indexable states (part 7 asserts it), so for it the walk goes on to the layouts,
    // from its own segment up to the root, and the deepest of them that sets robots decides those states.
    const setter = chain(route).find((rf) => setsNoindex(rf) !== undefined)
    expect(setter && setsNoindex(setter) ? rel(setter.file) : undefined, `/${route} resolves robots to noindex`).toBeUndefined()
  })

  it('self-check: the robots and card readers flag what they must', () => {
    const file = (text: string) => readRouteFile('app/zzprobe/page.tsx', text)
    const probe = (body: string) => file(`export const metadata = ${body}`)
    // No robots at all, then the forms that keep a page in the index.
    expect(setsNoindex(probe("{ title: 'Probe | EarningsNerd' }"))).toBeUndefined()
    expect(setsNoindex(probe("{ title: 'Probe | EarningsNerd' } satisfies Metadata"))).toBeUndefined()
    for (const robots of [
      '{ index: true, follow: false }',
      '{ follow: false }',
      "'index, follow'",
      "'max-image-preview:none'",
      "{ index: true, googleBot: 'index, follow' }",
    ]) expect(setsNoindex(probe(`{ robots: ${robots} }`)), `${robots} keeps the page in the index`).toBe(false)
    // One case per form Next renders as noindex.
    for (const robots of [
      '{ index: false }',
      '{ index: false, follow: true }',
      "'noindex'",
      "'noindex, nofollow'",
      "'NoIndex, follow'",
      "'none'",
      "'unavailable_after: 2026-01-01'",
      "{ unavailable_after: '2026-01-01' }",
      '{ index: true, googleBot: { index: false } }',
      "{ googleBot: 'noindex' }",
      "{ googleBot: 'none' }",
    ]) expect(setsNoindex(probe(`{ robots: ${robots} }`)), `${robots} is noindex`).toBe(true)
    expect(setsNoindex(probe('{ robots: { index: false } } satisfies Metadata')), 'read through satisfies').toBe(true)
    // What this reading cannot see counts as noindex, so it fails loudly.
    for (const text of [
      'export const metadata = { robots: ROBOTS }',
      'export const metadata = { robots: { index: INDEX } }',
      'export const metadata = { robots: { ...BASE } }',
      'export const metadata = { robots: { index: true, googleBot: BOT } }',
      'export const metadata = { robots }',
      "export const metadata = { ...NOINDEX, title: 'Probe | EarningsNerd' }",
      "export const metadata = { ['robots']: { index: true } }",
      'export const metadata = NOINDEX',
      "export { metadata } from './shared'",
      "export * from './shared'",
      'export const { metadata } = SHARED',
      'export const [, metadata] = LIST',
    ]) expect(setsNoindex(file(text)), `${text} counts as noindex`).toBe(true)
    expect(file('export const { meta: metadata } = SHARED').exportsMetadata, 'a destructured export is imported for its titles').toBe(true)
    expect(file('export const { generateMetadata } = SHARED').unreadable).toBe('generateMetadata is bound by { generateMetadata }, which the spec cannot read')
    expect(file('export const metadata = NOINDEX').unreadable).toBe('metadata is NOINDEX, not an object literal the spec can read')
    expect(file("export * as shared from './shared'").unreadable, 'a namespace export hands Next no metadata').toBeUndefined()
    // A write after the literal is one the AST reading cannot see (the review of #1312's forms), so the file names its
    // metadata only in its declaration; a parameter or a local of the same name is not the export.
    for (const after of [
      "if (FLAG) metadata.title = 'Other | EarningsNerd'",
      'metadata.robots = { index: false }',
      "metadata['robots'] = 'noindex'",
      "metadata.openGraph = { title: 'Probe | EarningsNerd', images: [] }",
      'Object.assign(metadata, EXTRA)',
      "const shared = metadata\nshared.robots = 'noindex'",
      'delete metadata.alternates',
    ]) expect(setsNoindex(file(`export const metadata = { title: 'Probe | EarningsNerd' }\n${after}`)), `${after} counts as noindex`).toBe(true)
    expect(file("export const metadata = { title: 'Probe | EarningsNerd' }\nif (FLAG) metadata.title = 'Other | EarningsNerd'").unreadable).toBe(
      "metadata is named again after its declaration (line 2: if (FLAG) metadata.title = 'Other | EarningsNerd'), so what Next reads may not be its literal",
    )
    expect(file("export const metadata = { title: 'Probe | EarningsNerd' }\nconst pick = (metadata: object) => metadata\nfunction f() { const metadata = 1; return metadata }").unreadable).toBeUndefined()
    // The evaluated robots read as robotsNoindex reads a literal: unset, the forms that keep a page in, the forms that keep it out.
    expect([undefined, null, { index: true, follow: false }, { follow: false }, 'index, follow', { index: true, googleBot: 'index, follow' }].map(evaluatedNoindex))
      .toEqual([undefined, undefined, false, false, false, false])
    expect([{ index: false }, 'noindex', 'NoIndex, follow', 'none', 'unavailable_after: 2026-01-01', { unavailable_after: '2026-01-01' }, { index: true, googleBot: { index: false } }, { googleBot: 'noindex' }].map(evaluatedNoindex))
      .toEqual([true, true, true, true, true, true, true, true])
    const card = (body: string) => {
      const metadata = probe(body).metadata!
      return [...cardProblems(metadata, 'openGraph'), ...cardProblems(metadata, 'twitter')]
    }
    expect(card("{ title: 'Probe | EarningsNerd' }")).toEqual([])
    expect(card('{ openGraph: { images: [SOCIAL_CARD] }, twitter: { images: [ SOCIAL_CARD.url ] } }')).toEqual([])
    expect(card('{ openGraph: { images: [] } }')).toHaveLength(1)
    expect(card("{ openGraph: { type: 'website' } }")).toHaveLength(1)
    expect(card("{ openGraph: { images: ['/other.png'] } }")).toHaveLength(1)
    expect(card('{ twitter: { images: [SOCIAL_CARD] } }')).toHaveLength(1)
    expect(card('{ openGraph }'), 'a shorthand openGraph').toHaveLength(1)
    expect(card('{ openGraph: { images: [SOCIAL_CARD], ...EXTRA_OG }, twitter: { images: [SOCIAL_CARD.url], ...EXTRA_TW } }'), 'a spread after the images').toHaveLength(2)
    expect(card('{ openGraph: { ...BASE_OG, images: [SOCIAL_CARD] } }'), 'a spread before the images, which they override').toEqual([])
    // A title of null renders none and drops the layout's, so it is not read as "no title of its own".
    expect(textsIn({ title: null } as Metadata).titles.flatMap((t) => textProblems(t, (text) => titleProblems(text)))).toEqual([
      "a title of null renders no title and drops the layout's",
    ])
    // Every object literal that sets one is read, so a generated page's state that drops the card fails too.
    const cards = (text: string) => socialLiterals(file(text).source).flatMap((obj) => [...cardProblems(obj, 'openGraph'), ...cardProblems(obj, 'twitter')])
    expect(
      cards(`export async function generateMetadata() {
        if (otc) return { title, description, openGraph: { title, description, type: 'website' } }
        return { title, openGraph: { title, images: [SOCIAL_CARD] }, twitter: { title, images: [SOCIAL_CARD.url] } }
      }`),
    ).toEqual(["openGraph.images is missing, not [SOCIAL_CARD] (a page-level openGraph replaces the root one, images included)"])
  })

  it('self-check: the environment and the generated-title readers flag what they must', () => {
    const env = (text: string) => envProblems(readRouteFile(path.join(APP, 'zzprobe/layout.tsx'), text))
    // The lens's probe: the pricing layout's title and description behind ENABLE_ANALYSIS.
    expect(
      env(`import { ENABLE_ANALYSIS } from '@/lib/featureFlags'
export const metadata = {
  title: ENABLE_ANALYSIS ? 'Pricing And Multi-Year Plans | EarningsNerd' : 'Pricing | EarningsNerd',
  description: ENABLE_ANALYSIS ? 'AI-powered plans, with multi-period analysis.' : 'Plans for every investor.',
}`),
    ).toHaveLength(2)
    const flag = "import { ENABLE_ANALYSIS } from '@/lib/featureFlags'\n"
    for (const text of [
      "const TITLE = process.env.NEXT_PUBLIC_X === 'true' ? 'A | EarningsNerd' : 'B | EarningsNerd'\nexport const metadata = { title: TITLE }",
      "import { ENABLE_ANALYSIS as on } from '@/lib/featureFlags'\nconst title = `Pricing${on ? ' and analysis' : ''} | EarningsNerd`\nexport const metadata = { openGraph: { title, images: [SOCIAL_CARD] } }",
      "import * as flags from '@/lib/featureFlags'\nexport const metadata = { description: `Plans${flags.ENABLE_ANALYSIS ? ', with analysis' : ''}.` }",
      "export const metadata = { title: typeof window === 'undefined' ? 'A | EarningsNerd' : 'B | EarningsNerd' }",
      // The review of #1312's forms: a spread before the images in openGraph and in twitter, a reassigned let, a
      // spread source written after, and the global object under its other names.
      `${flag}const SHARE = { title: ENABLE_ANALYSIS ? 'A | EarningsNerd' : 'B | EarningsNerd' }\nexport const metadata = { openGraph: { ...SHARE, images: [SOCIAL_CARD] } }`,
      `${flag}const SHARE = { description: ENABLE_ANALYSIS ? 'A.' : 'B.' }\nexport const metadata = { twitter: { card: 'summary_large_image', ...SHARE, images: [SOCIAL_CARD.url] } }`,
      `${flag}let title = 'A | EarningsNerd'\nif (ENABLE_ANALYSIS) title = 'B | EarningsNerd'\nexport const metadata = { title }`,
      `${flag}const SHARE = { title: 'A | EarningsNerd' }\nif (ENABLE_ANALYSIS) SHARE.title = 'B | EarningsNerd'\nexport const metadata = { openGraph: { ...SHARE, images: [SOCIAL_CARD] } }`,
      "export const metadata = { title: global.process.env.X ? 'A | EarningsNerd' : 'B | EarningsNerd' }",
      "export const metadata = { description: self.location ? 'A.' : 'B.' }",
      // The rest of the family, ahead of a review: the other ways a file changes a value after making it, a computed
      // key, a destructured environment value, an openGraph that is not a literal, a generated page's flag.
      "const SHARE = { title: 'A | EarningsNerd' }\nObject.assign(SHARE, EXTRA)\nexport const metadata = { openGraph: { ...SHARE, images: [SOCIAL_CARD] } }",
      "const TITLES = ['A | EarningsNerd']\nif (on) TITLES.push('B | EarningsNerd')\nexport const metadata = { title: TITLES[TITLES.length - 1] }",
      "const SHARE = { title: 'A | EarningsNerd' }\nflagged(SHARE)\nexport const metadata = { openGraph: { ...SHARE, images: [SOCIAL_CARD] } }",
      "const SHARE = { title: 'A | EarningsNerd' }\nconst ALIAS = SHARE\nALIAS.title = 'B | EarningsNerd'\nexport const metadata = { openGraph: { ...SHARE, images: [SOCIAL_CARD] } }",
      "let count = 3\ncount++\nexport const metadata = { description: `${count} plans.` }",
      "const KEY = 'title'\nexport const metadata = { openGraph: { [KEY]: process.env.X, images: [SOCIAL_CARD] } }",
      "const { X } = process.env\nexport const metadata = { title: X }",
      `${flag}const OG = { title: ENABLE_ANALYSIS ? 'A | EarningsNerd' : 'B | EarningsNerd', images: [SOCIAL_CARD] }\nexport const metadata = { openGraph: OG }`,
      // A call to lib/serverApi in static metadata is no generated page's data: it is followed, into the base URL's
      // process.env read (the review of 3a1368ec's check of the PR's other widenings).
      "import { fetchSignupConfig } from '@/lib/serverApi'\nexport const metadata = { title: `${String(fetchSignupConfig())} | EarningsNerd` }",
    ]) expect(env(text), text).toHaveLength(1)
    // Texts that read no environment, whatever names they hold: a key, a member or a parameter named window,
    // document or process, a value-imported type, a namespace import's constant, a spread source read twice or
    // handed to a call that only reads it.
    for (const text of [
      "const ALERT = { window: 'day-of' }\nexport const metadata = { description: `With ${ALERT.window} alerts.` }",
      "const LABELS = { document: 'Security', process: 'How we work' }\nexport const metadata = { title: `${LABELS.document} | EarningsNerd` }",
      "const named = (process: string) => process\nexport const metadata = { title: `${named('Probe')} | EarningsNerd` }",
      "import { Company } from '@/features/companies/api/companies-api'\nconst nameOf = (c: Pick<Company, 'name'>) => c.name\nexport const metadata = { title: `Probe${nameOf({ name: '' })} | EarningsNerd` }",
      "import * as limits from '@/lib/planLimits'\nexport const metadata = { description: `Up to ${limits.FREE_EARNINGS_ALERT_LIMIT} companies.` }",
      "const SHARE = { title: 'A | EarningsNerd' }\nexport const metadata = { openGraph: { ...SHARE, images: [SOCIAL_CARD] }, twitter: { ...SHARE, images: [SOCIAL_CARD.url] } }",
      "const SHARE = { title: 'A | EarningsNerd' }\nconst KEYS = Object.keys(SHARE)\nexport const metadata = { description: `${KEYS.length} keys.`, openGraph: { ...SHARE, images: [SOCIAL_CARD] } }",
      // A type holds no value: a class named in an annotation is not read for its body, and an interface a class
      // implements exports no value, so its module is not read whole.
      "class Store { read() { return typeof window } }\nconst label = (store: Store | null) => (store ? 'Store' : 'Probe')\nexport const metadata = { title: `${label(null)} | EarningsNerd` }",
      "import { Company } from '@/features/companies/api/companies-api'\nclass Named implements Company { name = 'Probe' }\nexport const metadata = { title: `${new Named().name} | EarningsNerd` }",
    ]) expect(env(text), text).toEqual([])
    // Constants, imported or not, and a helper that reads none: one text in every environment.
    expect(
      env(`import { FREE_SUMMARY_LIMIT } from '@/lib/planLimits'
import { DEFAULT_HEADLINE, pageTitleFor } from '@/features/marketing/lib/headline'
const DESCRIPTION = \`Up to \${FREE_SUMMARY_LIMIT} summaries a month.\`
export const metadata = { title: pageTitleFor(DEFAULT_HEADLINE), description: DESCRIPTION, openGraph: { title: 'Probe | EarningsNerd' } }`),
    ).toEqual([])
    // A flag read in another project module, through the constant it exports.
    const root = mkdtempSync(path.join(tmpdir(), 'route-env-'))
    try {
      writeFileSync(path.join(root, 'copy.ts'), "import { ENABLE_ANALYSIS } from '@/lib/featureFlags'\nexport const PRICING_TITLE = ENABLE_ANALYSIS ? 'A | EarningsNerd' : 'B | EarningsNerd'\n")
      expect(envProblems(readRouteFile(path.join(root, 'layout.tsx'), "import { PRICING_TITLE } from './copy'\nexport const metadata = { title: PRICING_TITLE }"))).toHaveLength(1)
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
    // A generated page: a state part 7 does not run has its title template read, and a state with no title is reported.
    const generated = readRouteFile(
      path.join(APP, 'zzprobe/page.tsx'),
      `export async function generateMetadata() {
  if (otc) return { title: \`\${label} OTC Filings | EarningsNerd\`, openGraph: { title, images: [SOCIAL_CARD] }, twitter: { title, images: [SOCIAL_CARD.url] } }
  if (delisted) return { description, openGraph: { images: [SOCIAL_CARD] }, twitter: { images: [SOCIAL_CARD.url] } }
  if (gone) return { title: undefined, openGraph: { images: [SOCIAL_CARD] }, twitter: { images: [SOCIAL_CARD.url] } }
  return { title: \`\${label} SEC filings | EarningsNerd\` }
}`,
    )
    expect(titleTemplates(generated.source).flatMap((t) => titleProblems(t))).toEqual(['"Ⓝ OTC Filings | EarningsNerd": "Filings" is capitalised mid-title (sentence case)'])
    const { states, unreadable } = returnedStates(generated)
    expect([states.length, states.filter(untitled).length, unreadable]).toEqual([4, 2, []])
    // The review of #1312's forms: words a condition, `||` or a const holds inside a brand-ending template are its
    // title's words too, whichever branch the state takes; a substitution the file holds no text for reads as a name.
    const readingsOf = (body: string) =>
      titleTemplates(readRouteFile(path.join(APP, 'zzprobe/page.tsx'), `import { ENABLE_ANALYSIS } from '@/lib/featureFlags'\n${body}`).source).flatMap((t) => titleProblems(t))
    expect(readingsOf("export const title = (label: string) => `${label} SEC filings${ENABLE_ANALYSIS ? ' With Multi-Year Trends' : ''} | EarningsNerd`")).toEqual([
      '"Ⓝ SEC filings With Multi-Year Trends | EarningsNerd": "With" is capitalised mid-title (sentence case)',
      '"Ⓝ SEC filings With Multi-Year Trends | EarningsNerd": "Multi-Year" is capitalised mid-title (sentence case)',
      '"Ⓝ SEC filings With Multi-Year Trends | EarningsNerd": "Trends" is capitalised mid-title (sentence case)',
    ])
    expect(readingsOf("export const title = (label: string, otc: boolean) => `${label} ${otc ? 'OTC Filings' : 'SEC filings'} | EarningsNerd`")).toEqual([
      '"Ⓝ OTC Filings | EarningsNerd": "Filings" is capitalised mid-title (sentence case)',
    ])
    expect(readingsOf("const suffix = amended ? ': Amended Filing' : ''\nexport const title = (label: string) => `${label}${suffix || ''} | EarningsNerd`")).toEqual([
      '"Ⓝ: Amended Filing | EarningsNerd": "Amended" is capitalised mid-title (sentence case)',
      '"Ⓝ: Amended Filing | EarningsNerd": "Filing" is capitalised mid-title (sentence case)',
    ])
    expect(readingsOf("export const title = (subject: string, filed: string, hasContent: boolean) => `${subject}${filed}${hasContent ? ': AI summary' : ''} | EarningsNerd`")).toEqual([])
    // Codex on 5291bc97: `&&` renders its right side where its left holds, a comma its right side, and a same-file object
    // or array literal nothing writes renders what it holds at the key, every entry for a key the file does not write.
    const withBadCaps = ['With', 'Bad', 'Caps'].map((word) => `"Ⓝ With Bad Caps | EarningsNerd": "${word}" is capitalised mid-title (sentence case)`)
    expect(readingsOf("export const title = (label: string, on: boolean) => `${label}${on && ' With Bad Caps'} | EarningsNerd`")).toEqual(withBadCaps)
    expect(readingsOf("export const title = (label: string) => `${label}${(0, ' With Bad Caps')} | EarningsNerd`")).toEqual(withBadCaps)
    const otcFilings = ['"Ⓝ OTC Filings | EarningsNerd": "Filings" is capitalised mid-title (sentence case)']
    const heldAt = (use: string, decl = "const SUFFIX = { otc: ' OTC Filings', sec: ' SEC filings' }") =>
      readingsOf(`${decl}\nexport const title = (label: string, kind: 'otc' | 'sec') => \`\${label}${use} | EarningsNerd\``)
    expect(heldAt('${SUFFIX[kind]}')).toEqual(otcFilings)
    expect(heldAt('${SUFFIX.otc}')).toEqual(otcFilings)
    expect(heldAt("${SUFFIX['otc']}")).toEqual(otcFilings)
    expect(heldAt('${SUFFIX.sec}')).toEqual([])
    expect(heldAt('${PARTS[0]}', "const PARTS = [' OTC Filings'] as const")).toEqual(otcFilings)
    expect(heldAt('${T.a.b}', "const T = Object.freeze({ a: { b: ' OTC Filings' } })")).toEqual(otcFilings)
    // Codex on 8a27892c: a computed key the file writes is that key, and an object's last entry for a key is its value.
    expect(heldAt('${SUFFIX.otc}', "const SUFFIX = { ['otc']: ' OTC Filings' }")).toEqual(otcFilings)
    expect(heldAt('${SUFFIX.otc}', "const KEY = 'otc'\nconst SUFFIX = { [KEY]: ' OTC Filings' }")).toEqual(otcFilings)
    expect(heldAt('${SUFFIX[KEY]}', "const KEY = 'otc'\nconst SUFFIX = { otc: ' OTC Filings', sec: ' SEC filings' }")).toEqual(otcFilings)
    expect(heldAt('${SUFFIX.otc}', "const BASE = { otc: ' sec filings' }\nconst SUFFIX = { ...BASE, otc: ' OTC Filings' }")).toEqual(otcFilings)
    expect(heldAt('${SUFFIX.otc}', "const SUFFIX = { otc: ' OTC Filings', otc: ' sec filings' }")).toEqual([])
    // A container this cannot read whole fails the title, never read as a name: a spread, a computed key the file does
    // not write or an accessor after the key's entry, and a literal something writes after it is made.
    const unreadAt = (why: string) => new RegExp(`reads a same-file container this spec cannot read whole \\(${why}\\)`)
    expect(() => heldAt('${SUFFIX.otc}', "const BASE = { otc: ' OTC Filings' }\nconst SUFFIX = { otc: ' sec filings', ...BASE }")).toThrow(unreadAt('a spread'))
    expect(() => heldAt('${SUFFIX.otc}', "const SUFFIX = { otc: ' sec filings', [String(Date.now())]: ' OTC Filings' }")).toThrow(unreadAt('a computed key'))
    expect(() => heldAt('${SUFFIX.otc}', "const SUFFIX = { otc: ' sec filings', get otc() { return ' OTC Filings' } }")).toThrow(unreadAt('a method or an accessor'))
    expect(() => heldAt('${SUFFIX.sec}', "const SUFFIX = { otc: ' sec filings', sec: ' OTC Filings' }\nSUFFIX.sec = ' sec filings'")).toThrow(unreadAt('an entry assigned at line 3'))
    // A template some reading of which ends with the brand is a title in every state (Codex on c0d1e726): a reading
    // without it fails loudly, never filtered out of the readings judged. The templates above end with it in each one.
    expect(() => readingsOf("const suffix = on ? 'EarningsNerd' : 'Other'\nexport const title = `Page | ${suffix}`")).toThrow(
      /^app\/zzprobe\/page\.tsx:3: the title template `Page \| \$\{suffix\}` reads "Page \| Other" in some state, without "\| EarningsNerd" at its end/,
    )
    expect(() => readingsOf("export const title = (label: string, on: boolean) => `${label}${on ? ' | EarningsNerd' : ''}`")).toThrow(/reads "Ⓝ" in some state/)
    // Every substitution is a name as well: a word after one is mid-title whatever the file holds for it today.
    expect(readingsOf("const prefix = ''\nexport const title = `${prefix} Filings | EarningsNerd`")).toEqual([
      '"Ⓝ Filings | EarningsNerd": "Filings" is capitalised mid-title (sentence case)',
    ])
    // Seven conditions (the review of 3a1368ec: the first 64 of 128 readings were read, none with the capitals). The
    // same text is one reading, so these are read whole; 64 readings that differ are read whole too, and 128 that
    // differ are more than the spec reads, so the title fails loudly rather than be read in part.
    const conditions = (words: string[]) =>
      "export const title = (l: string) => `${l} filings${c1 ? '' : ' With Bad Caps'}" +
      words.map((word, k) => `\${c${k + 2} ? '' : ' ${word}'}`).join('') +
      ' | EarningsNerd`'
    const capitals = '"Ⓝ filings With Bad Caps | EarningsNerd": "With" is capitalised mid-title (sentence case)'
    expect(readingsOf(conditions(['x', 'x', 'x', 'x', 'x', 'x']))).toContain(capitals)
    expect(readingsOf(conditions(['a', 'b', 'c', 'd', 'e']))).toContain(capitals)
    expect(() => readingsOf(conditions(['a', 'b', 'c', 'd', 'e', 'f']))).toThrow(/^app\/zzprobe\/page\.tsx:2: the title template .* has more than 64 readings/)
    // A generated state's texts are held to one environment too, its locals followed to their values; a call to
    // lib/serverApi is the page's data, read for its arguments alone.
    const generatedEnv = (body: string) => envProblems(readRouteFile(path.join(APP, 'zzprobe/page.tsx'), body))
    expect(
      generatedEnv(`${flag}export async function generateMetadata() {
  const title = ENABLE_ANALYSIS ? 'A | EarningsNerd' : 'B | EarningsNerd'
  return { title, openGraph: { title, images: [SOCIAL_CARD] } }
}`),
    ).toHaveLength(2)
    expect(
      generatedEnv(`export async function generateMetadata() {
  let title = 'A | EarningsNerd'
  if (process.env.X) title = 'B | EarningsNerd'
  return { title }
}`),
    ).toHaveLength(1)
    expect(
      generatedEnv(`import { fetchCompanyServer } from '@/lib/serverApi'
export async function generateMetadata({ params }: { params: Promise<{ ticker: string }> }) {
  const { ticker } = await params
  const result = await fetchCompanyServer(ticker.toUpperCase())
  const title = \`\${result.status === 'ok' ? result.data.name : ticker} SEC filings | EarningsNerd\`
  return { title, openGraph: { title, images: [SOCIAL_CARD] } }
}`),
    ).toEqual([])
  })

  it('self-check: the walk reads a page or a layout under every extension Next serves, a planted .ts layout included', () => {
    expect(PAGE_EXTENSIONS, 'next.config.js sets no pageExtensions, so Next serves its default list').toEqual(['tsx', 'ts', 'jsx', 'js'])
    const root = mkdtempSync(path.join(tmpdir(), 'route-walk-'))
    try {
      const plant = (file: string, text = 'export default function Probe() { return null }\n') => {
        mkdirSync(path.dirname(path.join(root, file)), { recursive: true })
        writeFileSync(path.join(root, file), text)
      }
      const served = ['company/layout.ts', 'company/page.tsx', 'zzprobe/layout.jsx', 'zzprobe/page.js']
      served.forEach((file) => plant(file))
      // Not a page or a layout Next serves: another extension, a test beside a page, another special file.
      for (const file of ['zzprobe/page.mdx', 'zzprobe/page.test.tsx', 'zzprobe/layout.css', 'zzprobe/template.tsx', 'zzprobe/route.ts']) plant(file)
      expect(walk(root).map((f) => path.relative(root, f).split(path.sep).join('/')).sort()).toEqual(served)
      // The planted .ts layout parses as TypeScript, a type assertion included, and its noindex is read.
      plant('company/layout.ts', "import type { Metadata } from 'next'\nexport const metadata = <Metadata>{ robots: { index: false } }\n")
      const layout = readRouteFile(path.join(root, 'company/layout.ts'))
      expect([layout.unreadable, setsNoindex(layout)]).toEqual([undefined, true])
    } finally {
      rmSync(root, { recursive: true, force: true })
    }
  })

  it('sets no robots in the root layout, so no public page is noindexed site-wide', () => {
    const robots = robotsOf(ROOT_LAYOUT)
    expect(robots === UNREADABLE ? UNREADABLE.description : robots?.getText(), 'the root layout sets robots').toBeUndefined()
  })

  it('reads robots and the card as each static module evaluates them, so a write its literal does not show fails here too', () => {
    const problems = [...EVALUATED].flatMap(([rf, meta]) => {
      if (!meta) return []
      const name = rel(rf.file)
      const out: string[] = []
      const literal = literalNoindex(rf)
      const value = evaluatedNoindex(meta.robots)
      if (literal !== null && literal !== value) {
        out.push(`${name}: its literal reads robots as ${literal === undefined ? 'unset' : literal ? 'noindex' : 'indexed'}, its evaluated metadata as ${value === undefined ? 'unset' : value ? 'noindex' : 'indexed'}`)
      }
      const images = (scope: unknown) => JSON.stringify((scope as { images?: unknown }).images)
      if (meta.openGraph && images(meta.openGraph) !== JSON.stringify([SOCIAL_CARD])) out.push(`${name}: its evaluated openGraph.images is ${images(meta.openGraph)}, not [SOCIAL_CARD]`)
      if (meta.twitter && images(meta.twitter) !== JSON.stringify([SOCIAL_CARD.url])) out.push(`${name}: its evaluated twitter.images is ${images(meta.twitter)}, not [SOCIAL_CARD.url]`)
      return out
    })
    expect(problems).toEqual([])
  })

  it.each(ROUTE_FILES.map((rf) => [rel(rf.file), socialLiterals(rf.source)] as const).filter(([, literals]) => literals.length))(
    '%s carries the site card in every openGraph and twitter it sets',
    (_name, literals) => {
      expect(literals.flatMap((obj) => [...cardProblems(obj, 'openGraph'), ...cardProblems(obj, 'twitter')])).toEqual([])
    },
  )

  it('leaves the root openGraph and twitter untitled, so each page fills them with its own title', () => {
    const root = EVALUATED.get(ROOT_LAYOUT)
    expect(root?.title).toBe('AI summaries of SEC filings | EarningsNerd')
    for (const [key, scope] of [['openGraph', root?.openGraph], ['twitter', root?.twitter]] as const) {
      expect(scope, `the root sets a ${key}`).toBeTruthy()
      expect(['title', 'description'].filter((k) => (scope as Record<string, unknown>)[k] !== undefined), `the root ${key} sets its own text`).toEqual([])
    }
    expect([...cardProblems(ROOT_LAYOUT.metadata!, 'openGraph'), ...cardProblems(ROOT_LAYOUT.metadata!, 'twitter')], 'the root carries the site card').toEqual([])
  })

  it("types the card's versioned URL only in lib/socialCard.ts", () => {
    const sources = (dir: string, out: string[] = []): string[] => {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, entry.name)
        if (entry.isDirectory()) sources(p, out)
        else if (/\.(tsx?|mjs|js)$/.test(entry.name)) out.push(p)
      }
      return out
    }
    const typed = ['app', 'components', 'features', 'lib', 'hooks']
      .map((d) => path.join(FRONTEND, d))
      .filter(existsSync)
      .flatMap((d) => sources(d))
      .filter((file) => /og-image\.png\?v=/.test(readFileSync(file, 'utf8')))
      .map(rel)
    expect(typed).toEqual(['lib/socialCard.ts'])
    expect(SOCIAL_CARD.url).toMatch(/^\/og-image\.png\?v=\d+$/)
  })
})

// ── The two generated routes, run in each state ───────────────────────────────────────────────────

const server = vi.hoisted(() => ({
  fetchCompanyServer: vi.fn(),
  fetchFilingServer: vi.fn(),
  fetchFilingSummaryServer: vi.fn(),
}))
vi.mock('@/lib/serverApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/serverApi')>()),
  fetchCompanyServer: server.fetchCompanyServer,
  fetchFilingServer: server.fetchFilingServer,
  fetchFilingSummaryServer: server.fetchFilingSummaryServer,
}))
vi.mock('@/app/company/[ticker]/page-client', () => ({ default: () => null }))
vi.mock('@/app/filing/[id]/page-client', () => ({ default: () => null }))

afterEach(() => {
  vi.clearAllMocks()
})

const APPLE = { id: 1, cik: '320193', ticker: 'AAPL', name: 'Apple Inc.' } as Company
const ADR = { id: 2, cik: '1', ticker: 'NSRGY', name: 'Nestle S.A.', coverage_status: 'unsupported_foreign' } as Company

async function companyMetadata(result: unknown, ticker = 'AAPL'): Promise<Metadata> {
  server.fetchCompanyServer.mockResolvedValue(result)
  const { generateMetadata } = await import('@/app/company/[ticker]/page')
  return generateMetadata({ params: Promise.resolve({ ticker }) })
}

async function filingMetadata(filing: unknown, summary: unknown, id = '42'): Promise<Metadata> {
  server.fetchFilingServer.mockResolvedValue(filing)
  server.fetchFilingSummaryServer.mockResolvedValue(summary)
  const { generateMetadata } = await import('@/app/filing/[id]/page')
  return generateMetadata({ params: Promise.resolve({ id }) })
}

/**
 * The checks every generated state shares: the title's form, the description's words, and the site card. A
 * state sets its own openGraph and twitter, each with the card and the state's title ('own'), or neither
 * ('root'): Next then keeps the root's, which carry the card and no title, so it fills og:title and
 * twitter:title from the state's own (the root test above holds both).
 */
function expectWellFormed(meta: Metadata, names: string[], card: 'own' | 'root') {
  expect(titleProblems(String(meta.title), names)).toEqual([])
  expect(descriptionProblems(String(meta.description ?? ''))).toEqual([])
  if (card === 'root') {
    expect([meta.openGraph, meta.twitter], 'this state sets no openGraph or twitter of its own').toEqual([undefined, undefined])
    return
  }
  expect(meta.openGraph?.images, 'a page-level openGraph carries the site card').toEqual([SOCIAL_CARD])
  expect(meta.twitter?.images, 'a page-level twitter carries the site card').toEqual([SOCIAL_CARD.url])
  expect([meta.openGraph?.title, meta.twitter?.title], 'og:title and twitter:title').toEqual([meta.title, meta.title])
}

describe('company page metadata, in each state', () => {
  it('a covered company: its name, the card, and a description of what the page holds', async () => {
    const meta = await companyMetadata({ status: 'ok', data: APPLE })
    expectWellFormed(meta, ['Apple Inc.'], 'own')
    expect(meta.title).toBe('Apple Inc. (AAPL) SEC filings and AI summaries | EarningsNerd')
    expect(meta.description).toBe('Apple Inc. (AAPL) filings from SEC EDGAR, with AI summaries that show their work.')
    expect(meta.robots).toBeUndefined()
  })

  it('an issuer that files no financial reports: the page’s own reason, never a promise of summaries', async () => {
    const reason = 'This issuer trades in the U.S. as an unsponsored ADR and does not file financial reports with the SEC.'
    const withReason = await companyMetadata({ status: 'ok', data: { ...ADR, coverage_reason: reason } }, 'NSRGY')
    expectWellFormed(withReason, ['Nestle S.A.'], 'own')
    expect(withReason.description).toBe(reason)
    expect(withReason.robots).toEqual({ index: false, follow: true })

    const bare = await companyMetadata({ status: 'ok', data: ADR }, 'NSRGY')
    expectWellFormed(bare, ['Nestle S.A.'], 'own')
    expect(bare.description).toBe('Nestle S.A. does not file financial reports with the SEC, so EarningsNerd has no filings to analyze.')
    expect(bare.description).not.toMatch(/summar/i)

    // The tab and the shared preview say what the page holds too, as the description does.
    for (const meta of [withReason, bare]) {
      expect(meta.title).toBe('Nestle S.A. (NSRGY): no SEC financial reports | EarningsNerd')
      expect(String(meta.title), 'the title promises filings or summaries the page cannot hold').not.toMatch(/summar|filings/i)
      expect(meta.openGraph?.title).toBe(meta.title)
      expect(meta.twitter?.title).toBe(meta.title)
    }
  })

  // 'not-found' is the page's real 404; its metadata takes the same branch as an unreachable backend.
  it.each(['unavailable', 'not-found'])('the company %s: the ticker alone, never "AAPL (AAPL)"', async (status) => {
    const meta = await companyMetadata({ status })
    expectWellFormed(meta, [], 'own')
    expect(meta.title).toBe('AAPL SEC filings and AI summaries | EarningsNerd')
    expect(meta.description).toBe('AAPL filings from SEC EDGAR, with AI summaries that show their work.')
  })
})

describe('filing page metadata, in each state', () => {
  const FILING = { id: 42, filing_type: '10-K', filing_date: '2025-10-31T00:00:00+00:00', company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.' } } as Filing
  const READY = { status: 'ok', data: { id: 9, filing_id: 42, business_overview: 'Apple designs devices and services.' } }

  it('a summary ready: the filed date, ": AI summary", indexable, the card', async () => {
    const meta = await filingMetadata({ status: 'ok', data: FILING }, READY)
    expectWellFormed(meta, ['Apple Inc.'], 'own')
    expect(meta.title).toBe('Apple Inc. (AAPL) 10-K filed October 31, 2025: AI summary | EarningsNerd')
    expect(meta.robots).toBeUndefined()
  })

  it('a stub: no summary claimed in the title or the description, out of the index, the card', async () => {
    const meta = await filingMetadata({ status: 'ok', data: FILING }, { status: 'ok', data: null })
    expectWellFormed(meta, ['Apple Inc.'], 'own')
    expect(meta.title).toBe('Apple Inc. (AAPL) 10-K filed October 31, 2025 | EarningsNerd')
    expect(meta.description).toBe('Apple Inc.’s 10-K, filed October 31, 2025, as published on SEC EDGAR.')
    expect(meta.robots).toEqual({ index: false, follow: true })
  })

  it('a stub with no company and no filed date: the clauses drop, nothing is invented', async () => {
    const bare = { ...FILING, filing_date: '', company: undefined } as unknown as Filing
    const meta = await filingMetadata({ status: 'ok', data: bare }, { status: 'ok', data: null })
    expectWellFormed(meta, [], 'own')
    expect(meta.title).toBe('10-K | EarningsNerd')
    expect(meta.description).toBe('10-K as published on SEC EDGAR.')
  })

  // 'not-found' is the page's real 404; its metadata takes the same branch as an unreachable backend. Neither
  // knows the filing, so neither sets an openGraph or twitter of its own: the root's carry the card.
  it.each(['unavailable', 'not-found'])('the filing %s: a generic title in sentence case, and "an SEC"', async (status) => {
    const meta = await filingMetadata({ status }, { status })
    expectWellFormed(meta, [], 'root')
    expect(meta.title).toBe('SEC filing | EarningsNerd')
    expect(meta.description).toBe('An SEC filing, as published on SEC EDGAR.')
  })

  it('a legacy ticker URL: canonical on the company page, title in sentence case', async () => {
    const meta = await filingMetadata({ status: 'ok', data: FILING }, READY, 'aapl')
    // Canonical on the company page, so it sets no card of its own: the root's apply.
    expectWellFormed(meta, [], 'root')
    expect(meta.title).toBe('AAPL SEC filings | EarningsNerd')
  })
})
