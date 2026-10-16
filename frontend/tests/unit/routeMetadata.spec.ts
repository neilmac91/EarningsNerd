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

/**
 * Route metadata (D-038; docs/brand/08-applications.md §1). Every route names itself in the tab and in
 * a shared link's preview, page first and brand last, and every shared page previews with the site card:
 *
 *   1. Each route's title comes from its own page or from a layout in its own directory, never from the
 *      root default, which the root layout holds, so the home page titles itself; a 'use client' page
 *      cannot export metadata, so its directory carries a layout that does (as app/login/layout.tsx does).
 *   2. Every title reads '<Page name> | EarningsNerd' in sentence case (proper nouns, acronyms and the
 *      company's own name allowed), each headline variant the home page's experiment serves included. A
 *      generated page holds every title template it can return in that form, and titles every state.
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
 * environment, so each must be one text in every environment: no process, window, document or globalThis
 * read reaches it, in its own file or through a declaration it names, followed into every project module
 * it imports (lib/featureFlags.ts reads each flag from process.env). Robots and the card are read from each
 * file's TypeScript AST, and what that reading cannot see fails loudly.
 *
 * Limits, left to review and to part 7's runs: a spread of another object hides its openGraph or twitter
 * from the card reading; a package's code is not followed; a generated title built without a string or a
 * template that ends with the brand is read only in the states part 7 runs.
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

function readRouteFile(file: string, text = readFileSync(file, 'utf8')): RouteFile {
  const source = parse(file, text)
  const first = source.statements[0]
  const isClient = !!first && ts.isExpressionStatement(first) && ts.isStringLiteral(first.expression) && first.expression.text === 'use client'
  let exportsMetadata = false
  let metadata: ts.ObjectLiteralExpression | undefined
  let unreadable: string | undefined
  let generates = false
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

/** The globals a value reads the environment through; each flag in lib/featureFlags.ts reads process.env. */
const ENV_GLOBALS = new Set(['process', 'window', 'document', 'globalThis'])

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

/** What a name stands for at a module's top level: its declaration, or what it imports, followed to the module that declares it. */
function declarationsOf(name: string, source: ts.SourceFile, visiting = new Set<string>()): Reached {
  const out: Reached = []
  for (const stmt of source.statements) {
    if (ts.isVariableStatement(stmt)) {
      for (const decl of stmt.declarationList.declarations) if (bindsName(decl.name, name) && decl.initializer) out.push([decl.initializer, source])
    } else if ((ts.isFunctionDeclaration(stmt) || ts.isClassDeclaration(stmt)) && stmt.name?.text === name) {
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

/** What a module exports under a name, followed through a local it renames and a re-export; a name it cannot place reads the whole module. */
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
  return out.length ? out : [[source, source]]
}

/** A name that refers to nothing by itself: a member's or a key's own name. */
const isOwnName = (n: ts.Identifier) => {
  const p = n.parent
  return (
    ((ts.isPropertyAccessExpression(p) || ts.isPropertyAssignment(p) || ts.isMethodDeclaration(p) || ts.isPropertySignature(p)) && p.name === n) ||
    (ts.isBindingElement(p) && p.propertyName === n)
  )
}

/**
 * Where a value can read the environment: an ENV_GLOBALS name in it, or in what a name in it stands for, followed
 * through its module and every project module it imports. Returns the read as 'file:line', or undefined.
 */
function envRead(node: ts.Node, source: ts.SourceFile, seen = new Set<ts.Node>()): string | undefined {
  if (seen.has(node)) return undefined
  seen.add(node)
  let found: string | undefined
  const visit = (n: ts.Node): void => {
    if (found) return
    if (!ts.isIdentifier(n)) return n.forEachChild(visit)
    if (ENV_GLOBALS.has(n.text)) found = `${rel(source.fileName)}:${source.getLineAndCharacterOfPosition(n.getStart(source)).line + 1}`
    else if (!isOwnName(n)) for (const [decl, file] of declarationsOf(n.text, source)) found ??= envRead(decl, file, seen)
  }
  visit(node)
  return found
}

/** Each title and description member of a static metadata literal, its own, its openGraph's and its twitter's, with the node that gives its value. */
function textMembers(metadata: ts.ObjectLiteralExpression): Array<[string, ts.Node]> {
  const scopes: Array<[string, ts.ObjectLiteralExpression]> = [['', metadata]]
  for (const key of ['openGraph', 'twitter']) {
    const value = prop(metadata, key)?.initializer
    if (value && ts.isObjectLiteralExpression(value)) scopes.push([`${key}.`, value])
  }
  return scopes.flatMap(([prefix, scope]) =>
    ['title', 'description'].flatMap((key): Array<[string, ts.Node]> => {
      const m = member(scope, key)
      if (!m) return []
      return [[`${prefix}${key}`, ts.isPropertyAssignment(m) ? m.initializer : ts.isShorthandPropertyAssignment(m) ? m.name : m]]
    }),
  )
}

/** Each title or description in a file's static metadata that can read the environment: the test sees only one branch of it. */
const envProblems = (rf: RouteFile): string[] =>
  rf.metadata
    ? textMembers(rf.metadata).flatMap(([key, node]) => {
        const at = envRead(node, rf.source)
        return at ? [`${rel(rf.file)}: ${key} reads the environment (${at}), so this test checks one branch of it`] : []
      })
    : []

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

/** Every title template in a file: a string or a template literal that ends with the brand, each substitution read as a name. */
function titleTemplates(source: ts.SourceFile): string[] {
  const out: string[] = []
  const visit = (n: ts.Node): void => {
    const text =
      ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)
        ? n.text
        : ts.isTemplateExpression(n)
          ? n.head.text + n.templateSpans.map((span) => `Ⓝ${span.literal.text}`).join('')
          : undefined
    if (text?.endsWith(BRAND)) out.push(text)
    n.forEachChild(visit)
  }
  visit(source)
  return out
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
      const untitled = states.filter((obj) => !member(obj, 'title')).map((obj) => `${name}:${line(obj)} returns a state with no title, so its tab reads the root default`)
      expect(states.length, `${name} returns no state the spec can read`).toBeGreaterThan(0)
      expect([...unreadable, ...untitled, ...titleTemplates(rf.source).flatMap((t) => titleProblems(t))]).toEqual([])
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
    for (const text of [
      "const TITLE = process.env.NEXT_PUBLIC_X === 'true' ? 'A | EarningsNerd' : 'B | EarningsNerd'\nexport const metadata = { title: TITLE }",
      "import { ENABLE_ANALYSIS as on } from '@/lib/featureFlags'\nconst title = `Pricing${on ? ' and analysis' : ''} | EarningsNerd`\nexport const metadata = { openGraph: { title, images: [SOCIAL_CARD] } }",
      "import * as flags from '@/lib/featureFlags'\nexport const metadata = { description: `Plans${flags.ENABLE_ANALYSIS ? ', with analysis' : ''}.` }",
      "export const metadata = { title: typeof window === 'undefined' ? 'A | EarningsNerd' : 'B | EarningsNerd' }",
    ]) expect(env(text), text).toHaveLength(1)
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
  return { title: \`\${label} SEC filings | EarningsNerd\` }
}`,
    )
    expect(titleTemplates(generated.source).flatMap((t) => titleProblems(t))).toEqual(['"Ⓝ OTC Filings | EarningsNerd": "Filings" is capitalised mid-title (sentence case)'])
    const { states, unreadable } = returnedStates(generated)
    expect([states.length, states.filter((obj) => !member(obj, 'title')).length, unreadable]).toEqual([3, 1, []])
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
