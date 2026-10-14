import { existsSync, readFileSync, readdirSync } from 'node:fs'
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
 *      root default; a 'use client' page cannot export metadata, so its directory carries a layout.tsx
 *      that does (as app/login/layout.tsx does).
 *   2. Every title reads '<Page name> | EarningsNerd' in sentence case (proper nouns, acronyms and the
 *      company's own name allowed).
 *   3. Every private route resolves robots to index: false. Each route is classified below, so a new
 *      route fails until someone decides which it is.
 *   4. Next replaces a nested openGraph wholesale, so every openGraph a page or layout sets carries
 *      images; the root's carries no title or description, so Next fills both from each page.
 *   5. No description says 'AI-powered' or carries an em-dash.
 *   6. The card's URL with its cache-busting ?v= is typed only in lib/socialCard.ts.
 *   7. The two generateMetadata routes (company, filing) are run in each state with serverApi mocked.
 *
 * The static checks read each file's TypeScript AST, so a `title:` inside page content never counts.
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
 * carries its title fails as stale, so the list only shrinks: delete the entry when its fix lands.
 */
const TITLE_RESIDUE: Record<string, { title: string; why: string }> = {
  'app/contact/page.tsx': { title: 'Contact Us | EarningsNerd', why: 'recased by brand-contact-security-presentation' },
  'app/search/page.tsx': { title: 'Search Filings | EarningsNerd', why: 'recased by brand-calendar-search' },
  'app/privacy/page.tsx': { title: 'Privacy Policy | EarningsNerd', why: 'legal page, edited only with a legal-date bump' },
  'app/terms/page.tsx': { title: 'Terms of Service | EarningsNerd', why: 'legal page, edited only with a legal-date bump' },
}
const DESCRIPTION_RESIDUE: Record<string, { text: string; why: string }> = {
  'app/terms/page.tsx': {
    text: 'Terms of Service for EarningsNerd: the rules for using our AI-powered SEC filing analysis.',
    why: 'legal page, edited only with a legal-date bump',
  },
}

/** Each route by its directory under app/ ('' is the home page). Private routes stay out of the index. */
const PRIVATE_ROUTES = [
  'admin/feedback', 'admin/invites', 'check-email', 'dashboard', 'dashboard/settings', 'dashboard/watchlist',
  'delete-account', 'forgot-password', 'login', 'register', 'reset-password', 'verify-email',
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

// ── The static reading ────────────────────────────────────────────────────────────────────────────

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (entry.name === 'page.tsx' || entry.name === 'layout.tsx') out.push(p)
  }
  return out
}

interface RouteFile {
  file: string
  isClient: boolean
  /** The `export const metadata` object, when there is one. */
  metadata?: ts.ObjectLiteralExpression
  generates: boolean
  source: ts.SourceFile
}

function readRouteFile(file: string): RouteFile {
  const text = readFileSync(file, 'utf8')
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const first = source.statements[0]
  const isClient = !!first && ts.isExpressionStatement(first) && ts.isStringLiteral(first.expression) && first.expression.text === 'use client'
  let metadata: ts.ObjectLiteralExpression | undefined
  let generates = false
  for (const stmt of source.statements) {
    const exported = ts.canHaveModifiers(stmt) && ts.getModifiers(stmt)?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword)
    if (!exported) continue
    if (ts.isVariableStatement(stmt)) {
      for (const decl of stmt.declarationList.declarations) {
        if (ts.isIdentifier(decl.name) && decl.name.text === 'metadata' && decl.initializer && ts.isObjectLiteralExpression(decl.initializer)) {
          metadata = decl.initializer
        }
        if (ts.isIdentifier(decl.name) && decl.name.text === 'generateMetadata') generates = true
      }
    }
    if (ts.isFunctionDeclaration(stmt) && stmt.name?.text === 'generateMetadata') generates = true
  }
  return { file, isClient, metadata, generates, source }
}

const prop = (obj: ts.ObjectLiteralExpression, name: string) =>
  obj.properties.find((p): p is ts.PropertyAssignment => ts.isPropertyAssignment(p) && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) && p.name.text === name)

/** A module-level `const NAME = '…'` the metadata refers to (app/page.tsx's DESCRIPTION). */
function constText(source: ts.SourceFile, name: string): string | undefined {
  for (const stmt of source.statements) {
    if (!ts.isVariableStatement(stmt)) continue
    for (const decl of stmt.declarationList.declarations) {
      if (ts.isIdentifier(decl.name) && decl.name.text === name && decl.initializer && ts.isStringLiteralLike(decl.initializer)) return decl.initializer.text
    }
  }
  return undefined
}

/** The strings a `title` or `description` value can take, or a problem when it cannot be read. */
function textsOf(node: ts.Expression, rf: RouteFile, key: string): string[] | string {
  if (ts.isStringLiteralLike(node)) return [node.text]
  if (ts.isIdentifier(node)) return constText(rf.source, node.text) !== undefined ? [constText(rf.source, node.text)!] : `${key} refers to ${node.text}, which is not a string constant in the file`
  // The home page titles itself from the served headline; every variant must hold the form.
  if (key === 'title' && ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'pageTitleFor') {
    return (Object.keys(HEADLINES) as HeadlineVariant[]).map(pageTitleFor)
  }
  return `${key} is ${node.getText()}, not a string the spec can read (write it as a literal)`
}

/** Every title and description in a metadata object, its openGraph and its twitter. */
function metadataTexts(rf: RouteFile, obj: ts.ObjectLiteralExpression) {
  const titles: string[] = []
  const descriptions: string[] = []
  const unreadable: string[] = []
  for (const scope of [obj, ...['openGraph', 'twitter'].map((k) => prop(obj, k)?.initializer).filter((n): n is ts.ObjectLiteralExpression => !!n && ts.isObjectLiteralExpression(n))]) {
    for (const [key, sink] of [['title', titles], ['description', descriptions]] as const) {
      const p = prop(scope, key)
      if (!p) continue
      const texts = textsOf(p.initializer, rf, key)
      if (typeof texts === 'string') unreadable.push(`${rel(rf.file)}: ${texts}`)
      else sink.push(...texts)
    }
  }
  return { titles, descriptions, unreadable }
}

const ROUTE_FILES = walk(APP).map(readRouteFile)
const byPath = new Map(ROUTE_FILES.map((rf) => [rel(rf.file), rf]))
const PAGES = ROUTE_FILES.filter((rf) => path.basename(rf.file) === 'page.tsx')
const routeOf = (page: RouteFile) => path.relative(APP, path.dirname(page.file)).split(path.sep).join('/')

/** The page, then its own layout, then each ancestor layout up to the root: Next's resolution order, deepest first. */
function chain(route: string): RouteFile[] {
  const out: RouteFile[] = []
  const page = byPath.get(path.posix.join('app', route, 'page.tsx'))
  if (page) out.push(page)
  const parts = route ? route.split('/') : []
  for (let i = parts.length; i >= 0; i -= 1) {
    const layout = byPath.get(path.posix.join('app', ...parts.slice(0, i), 'layout.tsx'))
    if (layout) out.push(layout)
  }
  return out
}

describe('route metadata: every route names itself, page first and brand last', () => {
  it('finds the routes it guards (the scan stays meaningful)', () => {
    expect(PAGES.length).toBeGreaterThanOrEqual(24)
    expect(ROUTE_FILES.filter((rf) => rf.metadata).length).toBeGreaterThanOrEqual(23)
  })

  it('classifies every route as public or private', () => {
    const routes = PAGES.map(routeOf).sort()
    expect(routes.filter((r) => !PRIVATE_ROUTES.includes(r) && !PUBLIC_ROUTES.includes(r)), 'routes neither public nor private').toEqual([])
    expect([...PRIVATE_ROUTES, ...PUBLIC_ROUTES].filter((r) => !routes.includes(r)), 'classified routes that no longer exist').toEqual([])
  })

  it.each(PAGES.map((p) => [routeOf(p) || '/', p] as const))('%s takes its title from its own page or layout', (_route, page) => {
    const route = routeOf(page)
    const own = [page, byPath.get(path.posix.join('app', route, 'layout.tsx'))].filter((rf): rf is RouteFile => !!rf)
    const titled = own.filter((rf) => rf.generates || (rf.metadata && prop(rf.metadata, 'title')))
    if (page.isClient) {
      const layout = own[1]
      expect(layout?.metadata && prop(layout.metadata, 'title'), `${rel(page.file)} is a client page with no layout.tsx exporting a metadata title beside it`).toBeTruthy()
    }
    expect(titled.length, `${rel(page.file)} has no title of its own, so its tab reads the root default`).toBeGreaterThan(0)
  })

  it('reads every metadata title as a string it can check', () => {
    const unreadable = ROUTE_FILES.flatMap((rf) => (rf.metadata ? metadataTexts(rf, rf.metadata).unreadable : []))
    expect(unreadable).toEqual([])
    expect(ROUTE_FILES.filter((rf) => rf.generates).map((rf) => rel(rf.file)).sort(), 'generateMetadata routes this spec runs').toEqual(GENERATED)
  })

  it.each(ROUTE_FILES.filter((rf) => rf.metadata).map((rf) => [rel(rf.file), rf] as const))('%s writes its titles as "Page name | EarningsNerd" in sentence case', (name, rf) => {
    const { titles } = metadataTexts(rf, rf.metadata!)
    const residue = TITLE_RESIDUE[name]
    const checked = residue ? titles.filter((t) => t !== residue.title) : titles
    expect(checked.flatMap((t) => titleProblems(t))).toEqual([])
  })

  it.each(Object.entries(TITLE_RESIDUE))('residue %s still carries its pinned title (delete the entry once fixed)', (name, { title }) => {
    const rf = byPath.get(name)
    expect(rf?.metadata && metadataTexts(rf, rf.metadata).titles, `stale residue: ${name}`).toContain(title)
  })

  it.each(ROUTE_FILES.filter((rf) => rf.metadata || rf.generates).map((rf) => [rel(rf.file), rf] as const))('%s writes descriptions with no "AI-powered" and no em-dash', (name, rf) => {
    const residue = DESCRIPTION_RESIDUE[name]?.text
    const texts = rf.metadata ? metadataTexts(rf, rf.metadata).descriptions : []
    // generateMetadata builds its strings from parts: read every literal inside it and the helpers beside it.
    if (rf.generates) {
      const visit = (node: ts.Node) => {
        if (ts.isStringLiteralLike(node) || ts.isTemplateLiteralToken(node)) texts.push(node.text)
        node.forEachChild(visit)
      }
      rf.source.statements.filter((s) => !ts.isImportDeclaration(s)).forEach(visit)
    }
    expect(texts.filter((t) => t !== residue).flatMap(descriptionProblems)).toEqual([])
  })

  it.each(Object.entries(DESCRIPTION_RESIDUE))('residue %s still carries its pinned description (delete the entry once fixed)', (name, { text }) => {
    const rf = byPath.get(name)
    expect(rf?.metadata && metadataTexts(rf, rf.metadata).descriptions, `stale residue: ${name}`).toContain(text)
  })

  it.each(PRIVATE_ROUTES.map((r) => [r] as const))('private route /%s stays out of the index', (route) => {
    // The deepest segment that sets robots decides it, as Next resolves it.
    const setter = chain(route).find((rf) => rf.metadata && prop(rf.metadata, 'robots'))
    const robots = setter?.metadata && prop(setter.metadata, 'robots')?.initializer
    const index = robots && ts.isObjectLiteralExpression(robots) ? prop(robots, 'index')?.initializer : undefined
    expect(index?.kind, `/${route} does not resolve robots to { index: false }`).toBe(ts.SyntaxKind.FalseKeyword)
  })

  it.each(ROUTE_FILES.filter((rf) => rf.metadata && prop(rf.metadata, 'openGraph')).map((rf) => [rel(rf.file), rf] as const))('%s carries the card in the openGraph it sets', (_name, rf) => {
    const og = prop(rf.metadata!, 'openGraph')!.initializer
    expect(ts.isObjectLiteralExpression(og) && prop(og, 'images'), 'a page-level openGraph replaces the root one, images included').toBeTruthy()
  })

  it('leaves the root openGraph and twitter untitled, so each page fills them with its own title', () => {
    const root = byPath.get('app/layout.tsx')!
    expect(prop(root.metadata!, 'title')?.initializer.getText()).toBe("'AI summaries of SEC filings | EarningsNerd'")
    for (const key of ['openGraph', 'twitter']) {
      const obj = prop(root.metadata!, key)!.initializer as ts.ObjectLiteralExpression
      expect(['title', 'description'].filter((k) => prop(obj, k)), `the root ${key} sets its own text`).toEqual([])
      expect(prop(obj, 'images'), `the root ${key} carries the card`).toBeTruthy()
    }
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

/** The checks every generated state shares: the title's form, the description's words, the card on any openGraph. */
function expectWellFormed(meta: Metadata, names: string[]) {
  expect(titleProblems(String(meta.title), names)).toEqual([])
  expect(descriptionProblems(String(meta.description ?? ''))).toEqual([])
  if (meta.openGraph) {
    expect(meta.openGraph.images, 'a page-level openGraph carries the site card').toEqual([SOCIAL_CARD])
    expect(meta.openGraph.title).toBe(meta.title)
  }
}

describe('company page metadata, in each state', () => {
  it('a covered company: its name, the card, and a description of what the page holds', async () => {
    const meta = await companyMetadata({ status: 'ok', data: APPLE })
    expectWellFormed(meta, ['Apple Inc.'])
    expect(meta.title).toBe('Apple Inc. (AAPL) SEC filings and AI summaries | EarningsNerd')
    expect(meta.description).toBe('Apple Inc. (AAPL) filings from SEC EDGAR, with AI summaries that show their work.')
    expect(meta.twitter).toMatchObject({ images: [SOCIAL_CARD.url] })
    expect(meta.robots).toBeUndefined()
  })

  it('an issuer that files no financial reports: the page’s own reason, never a promise of summaries', async () => {
    const reason = 'This issuer trades in the U.S. as an unsponsored ADR and does not file financial reports with the SEC.'
    const withReason = await companyMetadata({ status: 'ok', data: { ...ADR, coverage_reason: reason } }, 'NSRGY')
    expectWellFormed(withReason, ['Nestle S.A.'])
    expect(withReason.description).toBe(reason)
    expect(withReason.robots).toEqual({ index: false, follow: true })

    const bare = await companyMetadata({ status: 'ok', data: ADR }, 'NSRGY')
    expect(bare.description).toBe('Nestle S.A. does not file financial reports with the SEC, so EarningsNerd has no filings to analyze.')
    expect(bare.description).not.toMatch(/summar/i)
  })

  it('the backend unreachable: the ticker alone, never "AAPL (AAPL)"', async () => {
    const meta = await companyMetadata({ status: 'unavailable' })
    expectWellFormed(meta, [])
    expect(meta.title).toBe('AAPL SEC filings and AI summaries | EarningsNerd')
    expect(meta.description).toBe('AAPL filings from SEC EDGAR, with AI summaries that show their work.')
  })
})

describe('filing page metadata, in each state', () => {
  const FILING = { id: 42, filing_type: '10-K', filing_date: '2025-10-31T00:00:00+00:00', company: { id: 1, ticker: 'AAPL', name: 'Apple Inc.' } } as Filing
  const READY = { status: 'ok', data: { id: 9, filing_id: 42, business_overview: 'Apple designs devices and services.' } }

  it('a summary ready: the filed date, ": AI summary", indexable, the card', async () => {
    const meta = await filingMetadata({ status: 'ok', data: FILING }, READY)
    expectWellFormed(meta, ['Apple Inc.'])
    expect(meta.title).toBe('Apple Inc. (AAPL) 10-K, filed October 31, 2025: AI summary | EarningsNerd')
    expect(meta.robots).toBeUndefined()
  })

  it('a stub: no summary claimed in the title or the description, out of the index, the card', async () => {
    const meta = await filingMetadata({ status: 'ok', data: FILING }, { status: 'ok', data: null })
    expectWellFormed(meta, ['Apple Inc.'])
    expect(meta.title).toBe('Apple Inc. (AAPL) 10-K, filed October 31, 2025 | EarningsNerd')
    expect(meta.description).toBe('Apple Inc.’s 10-K, filed October 31, 2025, as published on SEC EDGAR.')
    expect(meta.robots).toEqual({ index: false, follow: true })
  })

  it('a stub with no company and no filed date: the clauses drop, nothing is invented', async () => {
    const bare = { ...FILING, filing_date: '', company: undefined } as unknown as Filing
    const meta = await filingMetadata({ status: 'ok', data: bare }, { status: 'ok', data: null })
    expectWellFormed(meta, [])
    expect(meta.title).toBe('10-K | EarningsNerd')
    expect(meta.description).toBe('10-K as published on SEC EDGAR.')
  })

  it('the backend unreachable: a generic title in sentence case, and "an SEC"', async () => {
    const meta = await filingMetadata({ status: 'unavailable' }, { status: 'unavailable' })
    expectWellFormed(meta, [])
    expect(meta.title).toBe('SEC filing | EarningsNerd')
    expect(meta.description).toBe('An SEC filing, as published on SEC EDGAR.')
  })

  it('a legacy ticker URL: canonical on the company page, title in sentence case', async () => {
    const meta = await filingMetadata({ status: 'ok', data: FILING }, READY, 'aapl')
    expectWellFormed(meta, [])
    expect(meta.title).toBe('AAPL SEC filings | EarningsNerd')
  })
})
