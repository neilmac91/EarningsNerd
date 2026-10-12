import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Three glyphs carry one meaning each (DESIGN.md › Icons; docs/brand/06-system.md §4): the quotes glyph
 * marks a passage from the filing, the curly braces an XBRL fact, and the sparkle the AI summary alone.
 * Spent elsewhere (on an upgrade button, a status badge, a reader's quote) the glyph stops meaning
 * anything (chrome/F24). This gate counts, per file, every use of SparkleIcon, QuotesIcon and
 * BracketsCurlyIcon from @/lib/icons or the Phosphor package (under any local name), every hand-drawn
 * stand-in (a local component named for one of them that draws its own <svg>), and the ✨ emoji:
 *
 *  - MEANING lists the sites that use a glyph for its meaning. A new one is a design decision, made in
 *    review against DESIGN.md.
 *  - RESIDUE lists what the audit found spent elsewhere on 2026-10-12, with the PR that removes it.
 *    Shrink-only: a fixed use fails until its count is lowered, a new one fails, and the list is capped
 *    at the seed (RESIDUE_MAX).
 */

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const GLYPHS = ['SparkleIcon', 'QuotesIcon', 'BracketsCurlyIcon'] as const
type Glyph = (typeof GLYPHS)[number]
const ICON_MODULES = new Set(['@/lib/icons', '@phosphor-icons/react'])
/** A local component drawing one of the glyphs by hand. */
const HAND_DRAWN: Array<[Glyph, RegExp]> = [
  ['SparkleIcon', /sparkle/i],
  ['QuotesIcon', /quote/i],
  ['BracketsCurlyIcon', /brace|bracket/i],
]

type Counts = Partial<Record<Glyph, number>>

const MEANING: Record<string, Counts> = {
  // The AI summary's marks: the generating header and the summary card's head.
  'app/filing/[id]/StreamingSummaryDisplay.tsx': { SparkleIcon: 2 },
  // Source chips: a located passage (quotes) or an XBRL fact (braces).
  'features/filings/components/SourceTrace.tsx': { QuotesIcon: 1, BracketsCurlyIcon: 1 },
  'features/marketing/components/HeroExample.tsx': { QuotesIcon: 1 },
  'features/marketing/components/TraceToSourceDemo.tsx': { QuotesIcon: 1 },
  'features/marketing/components/CatchCard.tsx': { BracketsCurlyIcon: 1 },
}

const RESIDUE: Record<string, Counts> = {
  'app/filing/[id]/StreamingSummaryDisplay.tsx': { SparkleIcon: 2 }, // brand-filing-page: the waiting notice and the free-limit card
  'app/dashboard/watchlist/page.tsx': { SparkleIcon: 1 }, // brand-dashboard-watchlist: "Analyze trends" (DSW-18)
  'features/admin/components/FeedbackStatusBadge.tsx': { SparkleIcon: 1 }, // brand-admin: the "New" status
  'features/filings/components/copilot/CopilotMessage.tsx': { SparkleIcon: 2 }, // brand-copilot: follow-up chips, upgrade button
  'features/filings/components/copilot/AskCopilotRail.tsx': { SparkleIcon: 2 }, // brand-copilot: launcher and rail header
  'features/filings/components/copilot/CopilotTeaser.tsx': { SparkleIcon: 1 }, // brand-copilot: upgrade button
  'features/filings/components/copilot/AskAboutSelection.tsx': { SparkleIcon: 1 }, // brand-copilot: the selection prompt
  'features/settings/components/BillingPanel.tsx': { SparkleIcon: 1 }, // brand-settings-subscriptions: the Pro badge
  'features/subscriptions/components/TrialBanner.tsx': { SparkleIcon: 1 }, // brand-settings-subscriptions: the trial banner
  'features/subscriptions/components/SubscriptionGate.tsx': { SparkleIcon: 1 }, // brand-settings-subscriptions (DSW-35 deletes it)
  'features/summaries/components/GenerateSignupGate.tsx': { SparkleIcon: 1 }, // brand-filing-page: the sign-up gate
  'features/feedback/components/FeedbackWidget.tsx': { SparkleIcon: 1 }, // brand-chrome-primitives: the "✨ Idea" option
  'features/marketing/components/ReaderQuoteSlot.tsx': { QuotesIcon: 1 }, // brand-public-pages: a reader's words, not the filing's (BG-28)
  'features/marketing/components/AskFilingDemo.tsx': { QuotesIcon: 1 }, // brand-public-pages: the Ask this Filing mark
  'features/filings/components/AskFilingAnswer.tsx': { QuotesIcon: 2 }, // brand-copilot: a hand-drawn quotes glyph as the Ask this Filing mark
}
const RESIDUE_MAX = { files: 15, uses: 19 }

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

/** The reserved-glyph uses in one source: imported glyphs (each reference, or the bare import when it has
    none), hand-drawn stand-ins (the declaration and each use) and the ✨ emoji in a literal. */
export function glyphUses(source: string, fileName: string): Counts {
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, fileName.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const counts: Counts = {}
  const bump = (glyph: Glyph, n = 1) => {
    counts[glyph] = (counts[glyph] ?? 0) + n
  }
  const local = new Map<string, Glyph>()
  for (const stmt of sf.statements) {
    if (!ts.isImportDeclaration(stmt) || !ts.isStringLiteral(stmt.moduleSpecifier) || !ICON_MODULES.has(stmt.moduleSpecifier.text)) continue
    const bindings = stmt.importClause?.namedBindings
    if (bindings && ts.isNamedImports(bindings)) {
      for (const el of bindings.elements) {
        const imported = (el.propertyName ?? el.name).text as Glyph
        if (GLYPHS.includes(imported)) local.set(el.name.text, imported)
      }
    }
  }
  // Hand-drawn stand-ins: a function or const named for a glyph whose body draws an <svg>.
  const drawn = new Map<string, Glyph>()
  const drawsSvg = (node: ts.Node) => {
    let svg = false
    const find = (n: ts.Node) => {
      if ((ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)) && n.tagName.getText(sf) === 'svg') svg = true
      if (!svg) ts.forEachChild(n, find)
    }
    find(node)
    return svg
  }
  const declare = (node: ts.Node): void => {
    const name = (ts.isFunctionDeclaration(node) || ts.isVariableDeclaration(node)) && node.name && ts.isIdentifier(node.name) ? node.name.text : null
    if (name && !local.has(name) && /^[A-Z]/.test(name) && drawsSvg(node)) {
      const hit = HAND_DRAWN.find(([, re]) => re.test(name))
      if (hit) drawn.set(name, hit[0])
    }
    ts.forEachChild(node, declare)
  }
  declare(sf)
  const refs = new Map<string, number>()
  const visit = (node: ts.Node): void => {
    if (ts.isIdentifier(node) && (local.has(node.text) || drawn.has(node.text)) && !ts.isImportSpecifier(node.parent)) {
      // A closing tag repeats its opening tag's name: one use.
      if (!ts.isJsxClosingElement(node.parent)) refs.set(node.text, (refs.get(node.text) ?? 0) + 1)
    }
    if ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isJsxText(node)) && node.text.includes('✨')) bump('SparkleIcon')
    ts.forEachChild(node, visit)
  }
  visit(sf)
  for (const [name, glyph] of local) bump(glyph, Math.max(refs.get(name) ?? 0, 1))
  for (const [name, glyph] of drawn) bump(glyph, refs.get(name) ?? 1)
  return counts
}

const rel = (file: string) => path.relative(ROOT, file).split(path.sep).join('/')

describe('reserved glyphs keep their one meaning', () => {
  const uses = new Map<string, Counts>()
  for (const file of SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))) {
    const r = rel(file)
    if (r === 'lib/icons.ts') continue
    const counts = glyphUses(readFileSync(file, 'utf8'), r)
    if (Object.keys(counts).length) uses.set(r, counts)
  }

  it('every use is a meaning site or listed residue, at its current count', () => {
    const problems: string[] = []
    const files = new Set([...uses.keys(), ...Object.keys(MEANING), ...Object.keys(RESIDUE)])
    for (const file of files) {
      for (const glyph of GLYPHS) {
        const actual = uses.get(file)?.[glyph] ?? 0
        const meant = MEANING[file]?.[glyph] ?? 0
        const residue = RESIDUE[file]?.[glyph] ?? 0
        if (actual > meant + residue) {
          problems.push(`${file}: ${actual} ${glyph}, ${meant + residue} allowed. ${glyph} is reserved (DESIGN.md › Icons): use LightningIcon or no icon on commerce, another glyph elsewhere`)
        } else if (actual < meant + residue) {
          problems.push(`${file}: ${actual} ${glyph}, ${meant + residue} listed: ${residue ? 'lower its RESIDUE count (stale)' : 'lower its MEANING count'}`)
        }
      }
    }
    expect(problems).toEqual([])
  })

  it('the residue only shrinks', () => {
    const counts = Object.values(RESIDUE).flatMap((c) => Object.values(c))
    expect(Object.keys(RESIDUE).length, 'RESIDUE gained a file').toBeLessThanOrEqual(RESIDUE_MAX.files)
    expect(counts.reduce((sum, n) => sum + (n ?? 0), 0), 'RESIDUE gained a use').toBeLessThanOrEqual(RESIDUE_MAX.uses)
  })

  it('the scan catches what it is for (a self-check on fixed sources)', () => {
    const src = [
      "import { SparkleIcon as Spark, QuotesIcon, ArrowRightIcon } from '@/lib/icons'",
      "import { BracketsCurlyIcon } from '@phosphor-icons/react'",
      'function QuoteMark() { return <svg viewBox="0 0 24 24"><path d="M0 0" /></svg> }',
      'export const A = () => (<><Spark /><Spark className="h-4 w-4"></Spark><QuoteMark /><ArrowRightIcon /><span>✨ Idea</span></>)',
      'const config = { Icon: QuotesIcon }',
    ].join('\n')
    expect(glyphUses(src, 'probe.tsx')).toEqual({ SparkleIcon: 3, QuotesIcon: 3, BracketsCurlyIcon: 1 })
  })
})
