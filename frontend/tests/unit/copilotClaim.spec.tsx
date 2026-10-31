import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// The rail reads the signed-in user and the usage response and renders UpgradeModal (useRouter): stub them
// so the empty state renders offline.
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: async () => ({ id: 1 }) }))
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getUsage: async () => ({
    summaries_used: 0, summaries_limit: null, is_pro: true, month: '2026-10',
    qa_used: 0, qa_limit: 1000, copilot_free_taste_used: 0, copilot_free_taste_total: 0,
  }),
}))

import { queryKeys } from '@/lib/queryKeys'
import { COPILOT_CLAIM } from '@/features/filings/components/copilot/copilotClaim'
import AskCopilotRail from '@/features/filings/components/copilot/AskCopilotRail'
import AskFilingCallout from '@/features/filings/components/copilot/AskFilingCallout'
import CopilotCoachmark from '@/features/filings/components/copilot/CopilotCoachmark'

/**
 * One claim about answers (D-034; docs/brand/08-applications.md §3): the rail's empty state, the
 * end-of-summary callout and the coachmark say the same scoped sentence, COPILOT_CLAIM, and say it by
 * importing it. Each surface is rendered and must show the sentence, so a surface that types a sentence
 * of its own fails here; and no source literal outside copilotClaim.ts spells the sentence, in any case
 * (the render checks match it in any case too), so a surface that types a copy of it fails too (the copy
 * would drift alone). What the sentence may say is brandCopyRules.spec.ts rule 1's job, which scans
 * copilotClaim.ts like any other source.
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const HOME = 'features/filings/components/copilot/copilotClaim.ts'
const SURFACES = [
  'features/filings/components/copilot/AskCopilotRail.tsx',
  'features/filings/components/copilot/AskFilingCallout.tsx',
  'features/filings/components/copilot/CopilotCoachmark.tsx',
]

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

const visit = (node: ts.Node, fn: (n: ts.Node) => void) => {
  fn(node)
  ts.forEachChild(node, (child) => visit(child, fn))
}

/** The text of a string literal, a template part or JSX text, whitespace collapsed as the page renders it, lower-cased. */
function literalText(node: ts.Node): string | null {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isJsxText(node)) return node.text.replace(/\s+/g, ' ').toLowerCase()
  if (ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) return node.text.replace(/\s+/g, ' ').toLowerCase()
  return null
}

/** Every source file, parsed once at import (about 700 of them), outside any one test's timeout. */
const SOURCES = SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir))).map((file) => ({
  rel: path.relative(ROOT, file).split(path.sep).join('/'),
  sf: ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS),
}))

describe('one scoped claim about answers (COPILOT_CLAIM)', () => {
  it('is the sentence the answer card can keep', () => {
    expect(COPILOT_CLAIM).toBe('Answers come from this filing, with cited passages you can check.')
  })

  it('the end-of-summary callout says it', () => {
    render(<AskFilingCallout filingType="10-K" subjectLabel="AAPL’s 10-K" onAsk={vi.fn()} />)
    expect(screen.getByText(COPILOT_CLAIM, { exact: false })).toBeInTheDocument()
  })

  it('the coachmark says it', () => {
    render(<CopilotCoachmark onTry={vi.fn()} onDismiss={vi.fn()} />)
    expect(screen.getByText(COPILOT_CLAIM)).toBeInTheDocument()
  })

  it("the rail's empty state says it", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    queryClient.setQueryData(queryKeys.currentUser(), { id: 1 })
    render(
      <QueryClientProvider client={queryClient}>
        <AskCopilotRail
          filingId={42} filingType="10-Q" ticker="AAPL" companyName="Apple Inc." summaryAvailable
          isPro isAuthenticated open onOpenChange={vi.fn()}
        />
      </QueryClientProvider>,
    )
    expect(screen.getByText(COPILOT_CLAIM, { exact: false })).toBeInTheDocument()
  })

  it('no source literal outside copilotClaim.ts spells the sentence, in any case: each surface imports it', () => {
    const rels = new Set(SOURCES.map(({ rel }) => rel))
    expect(rels.size, 'the scan reads the app').toBeGreaterThan(100)
    for (const rel of [HOME, ...SURFACES]) expect(rels.has(rel), rel).toBe(true)
    const claim = COPILOT_CLAIM.toLowerCase()
    const copies: string[] = []
    for (const { rel, sf } of SOURCES) {
      if (rel === HOME) continue
      visit(sf, (n) => {
        if (literalText(n)?.includes(claim)) copies.push(`${rel}:${sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1}`)
      })
    }
    expect(copies, 'render {COPILOT_CLAIM} from ./copilotClaim instead of typing the sentence').toEqual([])
  })
})
