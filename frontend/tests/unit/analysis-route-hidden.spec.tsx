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
 * else in the source, so a second hand-typed list cannot keep advertising it with the flag off.
 */
const NAMES_FEATURE = /multi-period analysis/i

/** The analysis feature itself (its route, its components, its API errors) and the one typed home. */
const OWNERS = [/^lib\/planLimits\.ts$/, /^app\/analysis\//, /^features\/analysis\//]

/** Shrink-only: each file names the feature for a reason other than a plan list. */
const ALLOWED: Record<string, string> = {
  'components/Header.tsx': 'a nav label that links to the feature, listed only under ENABLE_ANALYSIS',
  'components/Footer.tsx': 'a nav label that links to the feature, listed only under ENABLE_ANALYSIS',
  'features/marketing/components/ProDepth.tsx':
    "the landing's product screen and extras grid for the feature; its flag gating is pub/F06, on the public-pages PR",
  'app/pricing/layout.tsx':
    "the /pricing JSON-LD offer description, in the founder-gated 'unlimited' pricing-claim cluster (pub/F05)",
}

/** Every string literal, template piece and JSX text in a source that names the feature, by line. */
function namingSites(file: string, text: string): string[] {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const sites: string[] = []
  const visit = (node: ts.Node): void => {
    if (
      ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateHead(node)
      || ts.isTemplateMiddle(node) || ts.isTemplateTail(node) || ts.isJsxText(node)
    ) {
      const words = node.text.replace(/\s+/g, ' ')
      if (NAMES_FEATURE.test(words)) {
        sites.push(`${file}:${source.getLineAndCharacterOfPosition(node.getStart()).line + 1} ${words.trim()}`)
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
    expect(namingSites('fixture.tsx', fixture).map((site) => site.split(' ')[0])).toEqual([
      'fixture.tsx:1', 'fixture.tsx:2', 'fixture.tsx:3', 'fixture.tsx:5',
    ])
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
    const allowedHits = new Set<string>()
    let ownerHits = 0
    for (const root of roots) {
      for (const file of walk(path.join(frontendDir, root))) {
        const rel = path.relative(frontendDir, file).split(path.sep).join('/')
        const sites = namingSites(rel, readFileSync(file, 'utf8'))
        if (sites.length === 0) continue
        if (OWNERS.some((owner) => owner.test(rel))) ownerHits += sites.length
        else if (rel in ALLOWED) allowedHits.add(rel)
        else offenders.push(...sites)
      }
    }
    expect(offenders).toEqual([])
    // Not vacuous: the typed home is scanned and holds the lines.
    expect(ownerHits).toBeGreaterThanOrEqual(4)
    // Shrink-only: an allowance whose file no longer names the feature goes.
    expect(Object.keys(ALLOWED).filter((rel) => !allowedHits.has(rel))).toEqual([])
  })
})
