import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import ts from 'typescript'

// Mutable holders the hoisted mocks can read (vi.mock factories are hoisted above imports).
const h = vi.hoisted(() => ({
  enableAnalysis: false,
  notFound: vi.fn(() => {
    throw new Error('NEXT_NOT_FOUND')
  }),
}))

vi.mock('next/navigation', () => ({ notFound: h.notFound, useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/lib/featureFlags', () => ({
  get ENABLE_ANALYSIS() {
    return h.enableAnalysis
  },
  ENABLE_PRO_TRIAL: false,
  ENABLE_FPI_FILINGS: false,
}))

import AnalysisLayout from '@/app/analysis/layout'
import ProDepth from '@/features/marketing/components/ProDepth'
import PricingSection from '@/features/marketing/components/PricingSection'
import UpgradeModal from '@/features/subscriptions/components/UpgradeModal'
import { ANALYSIS_LINES, shipped, type PlanLine } from '@/lib/planLimits'

describe('Analysis route gating (NEXT_PUBLIC_ENABLE_ANALYSIS)', () => {
  beforeEach(() => {
    h.notFound.mockClear()
  })

  it('404s /analysis when the flag is off', () => {
    h.enableAnalysis = false
    expect(() => AnalysisLayout({ children: 'gated' })).toThrow('NEXT_NOT_FOUND')
    expect(h.notFound).toHaveBeenCalledTimes(1)
  })

  it('renders the route when the flag is on', () => {
    h.enableAnalysis = true
    const out = AnalysisLayout({ children: 'visible' })
    expect(h.notFound).not.toHaveBeenCalled()
    expect(out).toBeTruthy()
  })
})

const NAMES_FEATURE = /multi-period analysis/i

/**
 * The public pages sell Multi-Period Analysis only while the flag ships it (audit pub/F06): the route
 * 404s with the flag off, so the landing's Pro section and pricing cards must not list it. The /pricing
 * page's plan list and its Product JSON-LD are held the same way in PricingPage.spec.tsx, which carries
 * that page's harness.
 */
describe('The public pages follow NEXT_PUBLIC_ENABLE_ANALYSIS', () => {
  const surfaces = () => {
    const pro = render(<ProDepth />)
    const proText = pro.container.textContent ?? ''
    pro.unmount()
    const pricing = render(<PricingSection accessMode="public" showBeta={false} />)
    const pricingText = pricing.container.textContent ?? ''
    pricing.unmount()
    return { proText, pricingText }
  }

  it('names no Multi-Period feature on the landing while the flag is off', () => {
    h.enableAnalysis = false
    const { proText, pricingText } = surfaces()
    expect(proText).not.toMatch(/Multi-Period|periods side by side|Excel export|XLSX/i)
    // The Excel export is the analysis workbook, so the Pro list drops it with the route.
    expect(pricingText).not.toMatch(/Multi-Period|Excel|XLSX/i)
    expect(pricingText).toContain('PDF and CSV exports')
    // Anti-vacuity: both surfaces rendered their lists (the landing's plan table, D-045, its rows).
    expect(proText).toContain('Change Report')
    expect(pricingText).toContain('Priority support')
  })

  it('names it on both while the flag is on', () => {
    h.enableAnalysis = true
    const { proText, pricingText } = surfaces()
    expect(proText).toContain('Multi-Period Analysis')
    expect(proText).toContain('Excel export')
    // The plan table gives the feature a row of its own: its label, then its Free and Pro cells, each an entry.
    expect(pricingText).toContain(`${ANALYSIS_LINES.landingRow.text}${ANALYSIS_LINES.landingFree.text}${ANALYSIS_LINES.landingPro.text}`)
    expect(pricingText).toContain('PDF, CSV and Excel exports')
  })
})

/**
 * Shipped-flag truth for the plan lists (DSW-05, D-033, D-040): every plan line the analysis flag decides is
 * typed once, in lib/planLimits.ts's ANALYSIS_LINES, in #1311's `{ text, flag, off }` shape, and every list
 * reads its lines through shipped(), which lists a flagged line's text only while NEXT_PUBLIC_ENABLE_ANALYSIS
 * ships the feature (the route 404s while it is off) and its `off` reading, if any, otherwise. The upgrade
 * dialog's list is the shared sentence proIncludes(); the /pricing Pro card, its Product JSON-LD and the
 * landing's plan table take ANALYSIS_LINES entries into theirs. Each surface renders both ways: the dialog
 * below, the landing's table above, /pricing and its JSON-LD in PricingPage.spec.tsx; READERS pins the modules
 * that take the entries to those surfaces, so a new reader comes with its render case.
 *
 * The scan fails on a string or JSX text naming the feature anywhere else in the source, so a second
 * hand-typed list cannot keep advertising it with the flag off. Exempt: the ANALYSIS_LINES declaration
 * itself (not the rest of lib/planLimits.ts) and the route's own files, app/analysis/ and the
 * features/analysis/ files that no module outside those two directories imports, directly or through
 * others, type-only imports aside (routeOnly() reads the import graph). An analysis component mounted
 * elsewhere (SourceChecks on the filing page; KpiStrip, MetricsTable and DataNotes in the landing's demo)
 * is scanned like any other file, and ALLOWED pins each remaining site by its whole text.
 *
 * Limits of a syntactic scan, each left to the render cases: a binding that carries an entry's text around
 * shipped() (`ANALYSIS_LINES.landingPro.text` in a plain list, or an alias of ANALYSIS_LINES) holds no
 * literal, and READERS reads the modules that import ANALYSIS_LINES from lib/planLimits.ts (by name, by
 * namespace or in a re-export), not a module that takes it from one of them.
 */

/** Shrink-only, and each entry is ONE site, pinned by its whole text: a site that names the feature for a reason other than a plan list. */
const ALLOWED: Array<{ file: string; text: string; why: string }> = [
  {
    file: 'components/Header.tsx',
    text: 'Multi-period analysis',
    why: 'the nav label that links to the feature, listed only under ENABLE_ANALYSIS',
  },
  {
    file: 'components/Footer.tsx',
    text: 'Multi-Period Analysis',
    why: 'the footer link to the feature, listed only under ENABLE_ANALYSIS',
  },
  {
    file: 'features/marketing/components/ProDepth.tsx',
    text: 'Multi-Period Analysis as a workbook, with metrics from the filed data.',
    why: "the landing's Excel export tile, which ProDepth lists only under ENABLE_ANALYSIS (#1311)",
  },
  {
    file: 'features/marketing/components/ProDepth.tsx',
    text: 'Multi-Period Analysis',
    why: "the title of the landing's product-screen row for the feature, rendered only under ENABLE_ANALYSIS (#1311)",
  },
]

/** Every module that takes ANALYSIS_LINES entries, with the surface it renders and where that renders both ways. */
const READERS: Record<string, string> = {
  'app/pricing/layout.tsx': "the /pricing Product JSON-LD's description (PricingPage.spec.tsx, both ways)",
  'app/pricing/page.tsx': 'the /pricing plan cards (PricingPage.spec.tsx, both ways)',
  'features/marketing/components/PricingSection.tsx': "the landing's plan table, its Multi-Period row and exports cell (the describe above, both ways)",
}

/** Every string literal, template piece and JSX text in a source that names the feature, with its line and span. */
function namingSites(file: string, text: string): Array<{ line: number; text: string; start: number; end: number }> {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const sites: Array<{ line: number; text: string; start: number; end: number }> = []
  const visit = (node: ts.Node): void => {
    if (
      ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateHead(node)
      || ts.isTemplateMiddle(node) || ts.isTemplateTail(node) || ts.isJsxText(node)
    ) {
      const words = node.text.replace(/\s+/g, ' ')
      if (NAMES_FEATURE.test(words)) {
        const start = node.getStart()
        sites.push({ line: source.getLineAndCharacterOfPosition(start).line + 1, text: words.trim(), start, end: node.getEnd() })
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return sites
}

/** The span of a top-level `const <name> = …` initializer, or null when the source declares none. */
function declarationSpan(file: string, text: string, name: string): { start: number; end: number } | null {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
  for (const statement of source.statements) {
    if (!ts.isVariableStatement(statement)) continue
    for (const declaration of statement.declarationList.declarations) {
      if (ts.isIdentifier(declaration.name) && declaration.name.text === name && declaration.initializer) {
        return { start: declaration.initializer.getStart(), end: declaration.initializer.getEnd() }
      }
    }
  }
  return null
}

/** The value imports of one source (static, re-exports and `import()`), resolved to the files in `files`, with the names each takes ('*' for a namespace). */
function valueImports(file: string, text: string, files: ReadonlySet<string>): Array<{ target: string; names: string[] }> {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const resolve = (spec: string): string | null => {
    const base = spec.startsWith('@/')
      ? spec.slice(2)
      : spec.startsWith('.')
        ? path.posix.normalize(path.posix.join(path.posix.dirname(file), spec))
        : null
    if (base === null) return null
    return [base, `${base}.ts`, `${base}.tsx`, `${base}/index.ts`, `${base}/index.tsx`].find((candidate) => files.has(candidate)) ?? null
  }
  const found: Array<{ target: string; names: string[] }> = []
  const take = (spec: string, names: string[]) => {
    const target = resolve(spec)
    if (target) found.push({ target, names })
  }
  const visit = (node: ts.Node): void => {
    if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
      const clause = node.importClause
      if (!clause) take(node.moduleSpecifier.text, [])
      else if (!clause.isTypeOnly) {
        const bindings = clause.namedBindings
        const named = bindings && ts.isNamedImports(bindings) ? bindings.elements.filter((element) => !element.isTypeOnly) : []
        const names = [
          ...(clause.name ? ['default'] : []),
          ...(bindings && ts.isNamespaceImport(bindings) ? ['*'] : []),
          ...named.map((element) => (element.propertyName ?? element.name).text),
        ]
        if (names.length) take(node.moduleSpecifier.text, names)
      }
    } else if (ts.isExportDeclaration(node) && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier) && !node.isTypeOnly) {
      const clause = node.exportClause
      const names = clause && ts.isNamedExports(clause)
        ? clause.elements.filter((element) => !element.isTypeOnly).map((element) => (element.propertyName ?? element.name).text)
        : ['*']
      if (names.length) take(node.moduleSpecifier.text, names)
    } else if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
      const [spec] = node.arguments
      if (spec && ts.isStringLiteralLike(spec)) take(spec.text, ['*'])
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return found
}

const inRoute = (file: string): boolean => /^(app|features)\/analysis\//.test(file)

/** The route's own files: those under app/analysis/ and features/analysis/ that no module outside them reaches through value imports. */
function routeOnly(sources: ReadonlyMap<string, string>): Set<string> {
  const files = new Set(sources.keys())
  const reached = new Set<string>()
  const queue = [...files].filter((file) => !inRoute(file))
  while (queue.length) {
    const file = queue.pop()!
    for (const { target } of valueImports(file, sources.get(file)!, files)) {
      if (!reached.has(target)) {
        reached.add(target)
        queue.push(target)
      }
    }
  }
  return new Set([...files].filter((file) => inRoute(file) && !reached.has(file)))
}

const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const sourceTree = (): Map<string, string> => {
  const walk = (dir: string): string[] =>
    readdirSync(dir).flatMap((name) => {
      const full = path.join(dir, name)
      if (statSync(full).isDirectory()) return walk(full)
      return /\.(ts|tsx)$/.test(name) ? [full] : []
    })
  const files = ['app', 'features', 'components', 'lib', 'hooks'].flatMap((root) => walk(path.join(frontendDir, root)))
  return new Map(files.map((file) => [path.relative(frontendDir, file).split(path.sep).join('/'), readFileSync(file, 'utf8')]))
}

describe('The plan lists name Multi-Period Analysis only while NEXT_PUBLIC_ENABLE_ANALYSIS ships it', () => {
  it('leaves Multi-Period Analysis out while the flag is off', () => {
    h.enableAnalysis = false
    render(<UpgradeModal open onClose={() => {}} feature="PDF export" />)
    expect(
      screen.getByText('PDF export is a Pro feature. Pro includes unlimited summaries, hourly filing alerts, 8-K alerts and exports.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('dialog')).not.toHaveTextContent(NAMES_FEATURE)
  })

  it('names Multi-Period Analysis while the flag is on', () => {
    h.enableAnalysis = true
    render(<UpgradeModal open onClose={() => {}} />)
    expect(
      screen.getByText('Pro includes unlimited summaries, hourly filing alerts, 8-K alerts, exports and Multi-Period Analysis.'),
    ).toBeInTheDocument()
  })

  it('shipped() lists each analysis line only while the flag is on, and its off reading otherwise', () => {
    const lines: readonly PlanLine[] = Object.values(ANALYSIS_LINES)
    h.enableAnalysis = false
    expect(shipped(lines)).toEqual(lines.flatMap((line) => (line.off ? [line.off] : [])))
    expect(shipped(lines).join(' ')).not.toMatch(/multi-period|excel/i)
    h.enableAnalysis = true
    expect(shipped(lines)).toEqual(lines.map((line) => line.text))
    // A line with no flag lists either way.
    h.enableAnalysis = false
    expect(shipped([{ text: 'Unlimited summaries' }])).toEqual(['Unlimited summaries'])
  })

  it('the scan sees strings, template pieces and JSX text, and skips comments and identifiers (self-check)', () => {
    const fixture = [
      "const PRO = ['Unlimited summaries', 'Unlimited Multi-Period Analysis']",
      'const line = `${n}-year Multi-Period Analysis`',
      'const el = <li>Pro includes multi-period',
      '  analysis and exports</li>',
      "const tile = <Tile title=\"Multi-Period Analysis\" />",
      '// Multi-Period Analysis in a comment is no claim',
      "const capture = <div data-capture=\"multi-period-analysis\" />",
    ].join('\n')
    expect(namingSites('fixture.tsx', fixture).map((site) => site.line)).toEqual([1, 2, 3, 5])
  })

  it('the route-only reading follows value imports, re-exports and import(), and skips type-only imports (self-check)', () => {
    const fixture = new Map([
      [
        'app/page.tsx',
        [
          "import Shared from '@/features/analysis/components/Shared'",
          "import type { Dataset } from '@/features/analysis/api/api'",
          "import { type Note } from '@/features/analysis/lib/notes'",
          "const Lazy = dynamic(() => import('@/features/analysis/components/Lazy'))",
        ].join('\n'),
      ],
      ['lib/barrel.ts', "export { figure } from '@/features/analysis/lib/reexported'"],
      ['features/analysis/components/Shared.tsx', "import { deep } from '../lib/deep'"],
      ['features/analysis/lib/deep.ts', ''],
      ['features/analysis/components/Lazy.tsx', ''],
      ['features/analysis/lib/reexported.ts', ''],
      ['features/analysis/api/api.ts', ''],
      ['features/analysis/lib/notes.ts', ''],
      ['features/analysis/components/Page.tsx', "import Shared from './Shared'\nimport { only } from '../lib/only'"],
      ['features/analysis/lib/only.ts', ''],
      ['app/analysis/page.tsx', "import Page from '@/features/analysis/components/Page'"],
    ])
    expect([...routeOnly(fixture)].sort()).toEqual([
      'app/analysis/page.tsx',
      'features/analysis/api/api.ts',
      'features/analysis/components/Page.tsx',
      'features/analysis/lib/notes.ts',
      'features/analysis/lib/only.ts',
    ])
  })

  it('no other source file types a line that names Multi-Period Analysis', () => {
    const sources = sourceTree()
    const owned = routeOnly(sources)
    const offenders: string[] = []
    const taken = new Set<number>()
    let declarationHits = 0
    for (const [rel, text] of sources) {
      if (owned.has(rel)) continue
      const declaration = rel === 'lib/planLimits.ts' ? declarationSpan(rel, text, 'ANALYSIS_LINES') : null
      for (const site of namingSites(rel, text)) {
        if (declaration && site.start >= declaration.start && site.end <= declaration.end) {
          declarationHits += 1
          continue
        }
        const entry = ALLOWED.findIndex((allowed, i) => !taken.has(i) && allowed.file === rel && allowed.text === site.text)
        if (entry === -1) offenders.push(`${rel}:${site.line} ${site.text}`)
        else taken.add(entry)
      }
    }
    expect(offenders).toEqual([])
    // Not vacuous: the declaration is found, and the scan reads every line in it that names the feature.
    const namingLines = (Object.values(ANALYSIS_LINES) as readonly PlanLine[])
      .flatMap((line) => [line.text, line.off ?? ''])
      .filter((text) => NAMES_FEATURE.test(text)).length
    expect(namingLines).toBeGreaterThan(0)
    expect(declarationHits).toBe(namingLines)
    // The route is exempt and the analysis files mounted elsewhere are not.
    expect(owned).toContain('features/analysis/components/AnalysisPageClient.tsx')
    expect(owned).toContain('app/analysis/page.tsx')
    for (const mounted of ['features/analysis/components/SourceChecks.tsx', 'features/analysis/components/KpiStrip.tsx']) {
      expect(sources.has(mounted), mounted).toBe(true)
      expect(owned.has(mounted), mounted).toBe(false)
    }
    // Shrink-only: an allowance no site takes any more goes.
    expect(ALLOWED.filter((_, i) => !taken.has(i)).map(({ file, text }) => `${file}: ${text}`)).toEqual([])
  })

  it('every module that takes ANALYSIS_LINES entries is a surface rendered both ways (READERS)', () => {
    const sources = sourceTree()
    const files = new Set(sources.keys())
    const readers = [...sources]
      .filter(([rel]) => rel !== 'lib/planLimits.ts')
      .filter(([rel, text]) =>
        valueImports(rel, text, files).some(
          ({ target, names }) => target === 'lib/planLimits.ts' && (names.includes('ANALYSIS_LINES') || names.includes('*')),
        ),
      )
      .map(([rel]) => rel)
      .sort()
    expect(readers).toEqual(Object.keys(READERS).sort())
  })
})
