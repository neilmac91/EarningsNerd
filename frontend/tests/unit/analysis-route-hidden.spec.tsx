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
}))

import AnalysisLayout from '@/app/analysis/layout'
import UpgradeModal from '@/features/subscriptions/components/UpgradeModal'
import { analysisLine } from '@/lib/planLimits'

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

/**
 * Shipped-flag truth for the plan lists (DSW-05, D-033): every plan-benefit line that names Multi-Period
 * Analysis is typed once, in lib/planLimits.ts, and reaches a list only through analysisLine(), which
 * returns nothing while NEXT_PUBLIC_ENABLE_ANALYSIS is off (the route 404s then). The upgrade dialog's
 * list is the shared sentence proIncludes(); the /pricing Pro card and the landing's two plan cards spread
 * analysisLine() into theirs. The scan below fails on a string or JSX text naming the feature anywhere
 * else in the source, so a second hand-typed list cannot keep advertising it with the flag off. At an
 * allowed site it reads only the part of the text that names the feature (ALLOWED says why).
 */
const NAMES_FEATURE = /multi-period analysis/i

/** The analysis feature itself (its route, its components, its API errors) and the one typed home. */
const OWNERS = [/^lib\/planLimits\.ts$/, /^app\/analysis\//, /^features\/analysis\//]

/**
 * Shrink-only, and each entry is ONE site, not a file (lessons/arch-gate-reference-values-are-themselves-gated.md
 * (b)): a site in `file` that names the feature for a reason other than a plan list. A site takes an entry
 * when exactly one of its parts (between commas, semicolons and full stops) names the feature and that part
 * IS the entry's phrase, and each entry is taken by one site, so every allowed file's count of sites is
 * pinned with equality. A new line naming the feature in an allowed file, a claim built around an allowed
 * phrase in the part that names it ("unlimited Multi-Period Analysis") and an entry no site takes any more
 * all fail. A claim in another part of the same site ("Multi-Period Analysis, unlimited with Pro") is not
 * read: an entry pins the naming part, not the site's whole text, because #1311 makes the /pricing JSON-LD
 * description a template whose flag-conditional piece is "multi-period analysis, ", which a whole-text pin
 * would refuse. Review reads the other parts of an allowed site.
 */
const ALLOWED: Array<{ file: string; phrase: string; why: string }> = [
  {
    file: 'components/Header.tsx',
    phrase: 'Multi-period analysis',
    why: 'the nav label that links to the feature, listed only under ENABLE_ANALYSIS',
  },
  {
    file: 'components/Footer.tsx',
    phrase: 'Multi-Period Analysis',
    why: 'the footer link to the feature, listed only under ENABLE_ANALYSIS',
  },
  {
    file: 'features/marketing/components/ProDepth.tsx',
    phrase: 'Multi-Period Analysis as a workbook',
    why: "the landing's Excel export tile, shown with the flag off until pub/F06 gates it (#1311, the public-pages PR)",
  },
  {
    file: 'features/marketing/components/ProDepth.tsx',
    phrase: 'Multi-Period Analysis',
    why: "the title of the landing's product-screen row for the feature, shown with the flag off until pub/F06 gates it (#1311)",
  },
  {
    file: 'app/pricing/layout.tsx',
    phrase: 'multi-period analysis',
    why: "the /pricing JSON-LD offer description, founder-gated pricing copy (pub/F05); #1311 names the feature there only under the flag",
  },
]

/** Whether the one part of a site's text that names the feature is the allowed phrase. */
function takes(text: string, phrase: string): boolean {
  const naming = text.split(/[,;.]/).map((part) => part.trim()).filter((part) => NAMES_FEATURE.test(part))
  return naming.length === 1 && naming[0] === phrase
}

/** Every string literal, template piece and JSX text in a source that names the feature, by line. */
function namingSites(file: string, text: string): Array<{ line: number; text: string }> {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const sites: Array<{ line: number; text: string }> = []
  const visit = (node: ts.Node): void => {
    if (
      ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateHead(node)
      || ts.isTemplateMiddle(node) || ts.isTemplateTail(node) || ts.isJsxText(node)
    ) {
      const words = node.text.replace(/\s+/g, ' ')
      if (NAMES_FEATURE.test(words)) {
        sites.push({ line: source.getLineAndCharacterOfPosition(node.getStart()).line + 1, text: words.trim() })
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return sites
}

describe('The plan lists name Multi-Period Analysis only while NEXT_PUBLIC_ENABLE_ANALYSIS ships it', () => {
  it('leaves Multi-Period Analysis out while the flag is off', () => {
    h.enableAnalysis = false
    render(<UpgradeModal open onClose={() => {}} feature="PDF export" />)
    expect(
      screen.getByText('PDF export is a Pro feature. Pro includes unlimited summaries, hourly filing alerts, 8-K alerts and exports.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('dialog')).not.toHaveTextContent(/Multi-Period Analysis/i)
  })

  it('names Multi-Period Analysis while the flag is on', () => {
    h.enableAnalysis = true
    render(<UpgradeModal open onClose={() => {}} />)
    expect(
      screen.getByText('Pro includes unlimited summaries, hourly filing alerts, 8-K alerts, exports and Multi-Period Analysis.'),
    ).toBeInTheDocument()
  })

  it('gives every plan list its line only while the flag is on', () => {
    const lists = ['upgradeDialog', 'pricingPro', 'landingPro', 'landingFree'] as const
    h.enableAnalysis = false
    for (const list of lists) expect(analysisLine(list)).toEqual([])
    h.enableAnalysis = true
    for (const list of lists) expect(analysisLine(list)).toEqual([expect.stringMatching(NAMES_FEATURE)])
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

  it('an allowance takes only the site whose part naming the feature is its phrase (self-check)', () => {
    expect(takes('Multi-Period Analysis', 'Multi-Period Analysis')).toBe(true)
    expect(takes('Multi-Period Analysis as a workbook, with XBRL-backed metrics.', 'Multi-Period Analysis as a workbook')).toBe(true)
    expect(takes('Unlimited AI summaries of SEC 10-K and 10-Q filings, multi-period analysis, filing Q&A, alerts, and exports.', 'multi-period analysis')).toBe(true)
    // The piece a flag-conditional JSON-LD description leaves (#1311): the part is still the phrase.
    expect(takes('multi-period analysis,', 'multi-period analysis')).toBe(true)
    // A claim built around an allowed phrase, or a second naming, is a new site.
    expect(takes('Hourly checks for new filings on your watchlist, including 8-Ks, and unlimited Multi-Period Analysis.', 'Multi-Period Analysis')).toBe(false)
    expect(takes('Unlimited Multi-Period Analysis', 'Multi-Period Analysis')).toBe(false)
    expect(takes('Multi-Period Analysis as a workbook, with XBRL-backed metrics.', 'Multi-Period Analysis')).toBe(false)
    expect(takes('Multi-Period Analysis, then Multi-Period Analysis again', 'Multi-Period Analysis')).toBe(false)
    // Not read, as the ALLOWED comment says: a claim in another part of an allowed site.
    expect(takes('Multi-Period Analysis, unlimited with Pro', 'Multi-Period Analysis')).toBe(true)
  })

  it('no other source file types a line that names Multi-Period Analysis', () => {
    const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
    const roots = ['app', 'features', 'components', 'lib', 'hooks']
    const walk = (dir: string): string[] =>
      readdirSync(dir).flatMap((name) => {
        const full = path.join(dir, name)
        if (statSync(full).isDirectory()) return walk(full)
        return /\.(ts|tsx)$/.test(name) ? [full] : []
      })
    const offenders: string[] = []
    const taken = new Set<number>()
    let ownerHits = 0
    for (const root of roots) {
      for (const file of walk(path.join(frontendDir, root))) {
        const rel = path.relative(frontendDir, file).split(path.sep).join('/')
        const sites = namingSites(rel, readFileSync(file, 'utf8'))
        if (OWNERS.some((owner) => owner.test(rel))) {
          ownerHits += sites.length
          continue
        }
        for (const site of sites) {
          const entry = ALLOWED.findIndex((allowed, i) => !taken.has(i) && allowed.file === rel && takes(site.text, allowed.phrase))
          if (entry === -1) offenders.push(`${rel}:${site.line} ${site.text}`)
          else taken.add(entry)
        }
      }
    }
    expect(offenders).toEqual([])
    // Not vacuous: the typed home is scanned and holds the lines.
    expect(ownerHits).toBeGreaterThanOrEqual(4)
    // Shrink-only: an allowance no site takes any more goes.
    expect(ALLOWED.filter((_, i) => !taken.has(i)).map(({ file, phrase }) => `${file}: ${phrase}`)).toEqual([])
  })
})
