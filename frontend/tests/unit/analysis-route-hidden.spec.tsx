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
    // Anti-vacuity: both surfaces rendered their lists.
    expect(proText).toContain('Change Report')
    expect(pricingText).toContain('Unlimited summaries')
  })

  it('names it on both while the flag is on', () => {
    h.enableAnalysis = true
    const { proText, pricingText } = surfaces()
    expect(proText).toContain('Multi-Period Analysis')
    expect(proText).toContain('Excel export')
    expect(pricingText).toContain('Multi-Period Analysis demo (locked)')
    expect(pricingText).toContain('Unlimited Multi-Period Analysis')
    expect(pricingText).toContain('PDF, CSV and Excel exports')
  })
})

/**
 * Shipped-flag truth for the plan lists (DSW-05, D-033, D-040): every plan line the analysis flag decides is
 * typed once, in lib/planLimits.ts's ANALYSIS_LINES, in #1311's `{ text, flag, off }` shape, and every list
 * reads its lines through shipped(), which lists a flagged line's text only while NEXT_PUBLIC_ENABLE_ANALYSIS
 * ships the feature (the route 404s while it is off) and its `off` reading, if any, otherwise. The upgrade
 * dialog's list is the shared sentence proIncludes(); the /pricing Pro card, its Product JSON-LD and the
 * landing's two plan cards take ANALYSIS_LINES entries into theirs. The scan below fails on a string or JSX
 * text naming the feature anywhere else in the source, so a second hand-typed list cannot keep advertising it
 * with the flag off. At an allowed site it reads only the part of the text that names the feature (ALLOWED
 * says why).
 */

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
    why: "the landing's Excel export tile, which ProDepth lists only under ENABLE_ANALYSIS (#1311)",
  },
  {
    file: 'features/marketing/components/ProDepth.tsx',
    phrase: 'Multi-Period Analysis',
    why: "the title of the landing's product-screen row for the feature, rendered only under ENABLE_ANALYSIS (#1311)",
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
