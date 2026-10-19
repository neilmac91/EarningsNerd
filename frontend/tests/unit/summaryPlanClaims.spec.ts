import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { PRO_FAIR_USE_LINE, PRO_SUMMARY_MONTHLY_CAP } from '@/lib/planLimits'

/**
 * Two claims a plan makes about summaries, held to what the code does (docs/brand/decisions-log.md D-046; CLAUDE.md
 * rules 4 and 12; lessons/brand-a-promise-names-what-the-code-enforces.md):
 *
 * 1. No summary-history claim while no retention is enforced. The pricing surfaces said Free "keeps 90 days" of
 *    summaries and Pro has "Full history" (pub/F03, F41), but nothing reads `history_retention_days`:
 *    backend/app/services/entitlements.py declares it as forward-looking, and no code ages out, hides or deletes a
 *    Free account's summaries. The first case lists every read of that field in backend/app (an attribute read
 *    anywhere, or the name in any module but entitlements.py, where the dataclass declares it and the plan blocks
 *    set it) and every summary model the scheduled purge (services/retention_service.py) imports, in each import
 *    form the self-check plants, at the module's top or indented inside a function (precompute_service.py imports
 *    Summary that way); both lists are empty. A PR that enforces a retention through either fails it, and states
 *    the claim in that PR with this gate moved beside it. Out of reach: a retention with its window hardcoded in
 *    another module, and a model reached through a module object (`import app.models`, `from app import models`), a
 *    star import or a relative one, none of which backend/app uses for app.models.
 *    The second reads every copy literal (a string, a template with each substitution read as `{x}`, JSX text) of
 *    every tracked module under app, components, features, hooks and lib, and fails one that claims a summary
 *    history, its length or window, or that summaries are kept, "kept" after "summary" or "keeps" before it
 *    (HISTORY_CLAIMS). The company page's filing history ("Show full history", "Full history on SEC EDGAR") and a
 *    company's "reporting history" are about filings, so the feature's bare name counts only as a whole literal
 *    ("Full history"); the dashboard's "Saved summaries" are the ones a reader saves, and name no window. The planted
 *    forms score the reach; out of reach, planted as gaps: a claim split across literals or around an expression,
 *    and one said in other words.
 * 2. Pro's fair-use guardrail is one sentence (E58): PRO_FAIR_USE_LINE in lib/planLimits.ts, built from
 *    PRO_SUMMARY_MONTHLY_CAP (which planLimitsLockstep.spec.ts holds to backend/app/config.py), placed by the /pricing
 *    FAQ and the filing page's monthly-limit card, and typed nowhere else: no other copy literal names a fair-use
 *    ceiling on summaries, and no module but lib/planLimits.ts reads PRO_SUMMARY_MONTHLY_CAP, so the number reaches
 *    copy only through the sentence (a typed "300 new summaries" is planLimitsLockstep.spec.ts's to fail).
 *    PricingPage.spec.tsx and StreamingSummaryDisplay.spec.tsx see the sentence rendered.
 */

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const BACKEND_APP = path.resolve(FRONTEND, '../backend/app')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']

const HISTORY_CLAIMS: Array<[string, RegExp]> = [
  ['a summary history', /\bsummary history\b/i],
  ['a history length', /(?:\b\d+|\{x\})-day (?:summary )?history\b|(?:\b\d+|\{x\}) days of (?:\w+ )?summar(?:y|ies)\b/i],
  ['days kept', /\bkeeps? (?:\d+|\{x\}) days\b/i],
  ['summaries kept', /\bsummar(?:y|ies)\b[^.]{0,60}\bkept\b|\b(?:keeps?|keeping|kept)\b[^.]{0,60}\bsummar(?:y|ies)\b/i],
  // A window needs a verb that holds or ends the summary: "unlimited summaries for {x} days" (a trial) is not one.
  ['a retention window', /\bsummar(?:y|ies)\b[^.]{0,60}\b(?:saved|stored|held|available|expire[sd]?|deleted|removed)\b[^.]{0,20}?(?:\b\d+|\{x\}) days\b/i],
  ['a history of summaries', /\bhistory of (?:your |the )?summaries\b/i],
  ['a retention', /\b(?:history|summary|summaries) retention\b|\bretain(?:s|ed)? (?:your )?summaries\b/i],
  ['the feature by name', /^\s*(?:full|unlimited|complete)(?: summary)? history\s*$/i],
]

/** A fair-use ceiling named on summaries (PRO_FAIR_USE_LINE's own subject), in either order. */
const SUMMARY_FAIR_USE = /\bfair[- ]use\b[^.]*\bsummar|\bsummar[^.]*\bfair[- ]use\b/i

interface Literal {
  rel: string
  line: number
  text: string
}

/** Every copy literal of a source: strings, templates (`{x}` for each substitution) and JSX text. */
function literals(source: string, rel: string): Literal[] {
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, rel.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const out: Literal[] = []
  const add = (node: ts.Node, text: string) =>
    out.push({ rel, line: sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1, text: text.replace(/\s+/g, ' ').trim() })
  const visit = (node: ts.Node) => {
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) add(node, node.text)
    else if (ts.isTemplateExpression(node)) add(node, [node.head.text, ...node.templateSpans.map((s) => `{x}${s.literal.text}`)].join(''))
    else if (ts.isJsxText(node) && !node.containsOnlyTriviaWhiteSpaces) add(node, node.text)
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

const historyFindings = (lits: Literal[]) =>
  lits.flatMap((l) => HISTORY_CLAIMS.filter(([, re]) => re.test(l.text)).map(([label]) => `${l.rel}:${l.line} (${label}) ${JSON.stringify(l.text)}`))

const MODULES = execFileSync('git', ['ls-files', '--', ...SCAN_DIRS], { cwd: FRONTEND, encoding: 'utf8' })
  .split('\n')
  .filter((rel) => /\.tsx?$/.test(rel) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(rel))
const LITERALS = MODULES.flatMap((rel) => literals(readFileSync(path.join(FRONTEND, rel), 'utf8'), rel))

/** Every module and name a Python file imports from app.models: one line or a parenthesised list, every import
 * statement, a submodule (`from app.models.summary import ...`, `import app.models.summary`), an alias, each at the
 * module's top or indented inside a function body. */
function modelImports(source: string): string[] {
  const names: string[] = []
  for (const m of source.matchAll(/^[ \t]*from (app\.models(?:\.\w+)*) import (\([^)]*\)|[^\n]+)$/gm)) {
    if (m[1] !== 'app.models') names.push(m[1])
    const list = m[2].replace(/#[^\n]*/g, '').replace(/[()]/g, '')
    names.push(...list.split(',').map((name) => name.trim().split(/\s+as\s+/)[0]).filter(Boolean))
  }
  for (const m of source.matchAll(/^[ \t]*import (app\.models(?:\.\w+)*)/gm)) names.push(m[1])
  return names
}

describe('no summary-history claim while no retention is enforced (D-046)', () => {
  it('nothing enforces a summary retention: no read of history_retention_days, no summary model in the purge', () => {
    const python = execFileSync('git', ['ls-files', '--', '.'], { cwd: BACKEND_APP, encoding: 'utf8' })
      .split('\n')
      .filter((rel) => rel.endsWith('.py'))
    expect(python.length).toBeGreaterThan(100)
    const reads: string[] = []
    for (const rel of python) {
      readFileSync(path.join(BACKEND_APP, rel), 'utf8').split('\n').forEach((line, index) => {
        const read = /\.history_retention_days\b/.test(line) || (rel !== 'services/entitlements.py' && /\bhistory_retention_days\b/.test(line))
        if (read) reads.push(`backend/app/${rel}:${index + 1} ${line.trim()}`)
      })
    }
    expect(reads, 'a retention is enforced now: state it on the pricing surfaces in this PR and move this gate with it').toEqual([])
    const models = modelImports(readFileSync(path.join(BACKEND_APP, 'services/retention_service.py'), 'utf8'))
    expect(models.length).toBeGreaterThan(0)
    expect(models.filter((name) => /summar/i.test(name))).toEqual([])
  })

  it('reads every import form the purge could bring a summary model in by (a self-check on planted forms)', () => {
    const planted: Array<[string, boolean]> = [
      ['from app.models import ContactSubmission, PasswordResetToken', false],
      ['from app.models import ContactSubmission  # a Summary is never purged', false],
      ['from app.models import (\n    ContactSubmission,\n    Summary,\n)', true],
      ['from app.models import ContactSubmission\nfrom app.models import Summary', true],
      ['from app.models.summary import Summary', true],
      ['from app.models.summary import SummaryArchive as Archive', true],
      ['from app.models import Summary as S', true],
      ['import app.models.summary', true],
      // Imports inside a function body, the form precompute_service.py uses for Summary.
      ['def purge(db):\n    from app.models import Summary\n    db.query(Summary).delete()', true],
      ['def purge(db):\n\timport app.models.summary\n\tdb.query(app.models.summary.Summary).delete()', true],
      ['def purge(db):\n    from app.models import LoginAttempt\n    db.query(LoginAttempt).delete()', false],
    ]
    expect(planted.map(([source]) => modelImports(source).some((name) => /summar/i.test(name)))).toEqual(planted.map(([, flag]) => flag))
  })

  it('no copy claims a summary history, its length or that summaries are kept', () => {
    expect(MODULES.length).toBeGreaterThan(300)
    expect(LITERALS.length).toBeGreaterThan(5000)
    expect(historyFindings(LITERALS)).toEqual([])
  })

  it('reads every form of the claim, and passes the filings history (a self-check on planted forms)', () => {
    const planted: Array<[string, boolean | 'gap']> = [
      ["export const A = '90-day summary history'", true],
      ['export const B = `${N}-day summary history`', true],
      ['export const B2 = `Free: ${N}-day history`', true],
      ['export const C = () => <p>Free keeps 90 days.</p>', true],
      ['export const D = `Free keeps ${N} days.`', true],
      ["export const E = { title: 'Full history', tags: ['Unlimited'] }", true],
      ['export const F = () => <h4>Full summary history</h4>', true],
      ["export const G = 'Every summary you have read, kept.'", true],
      ['export const H = () => <li>Unlimited history</li>', true],
      ["export const I = 'The history of your summaries, for good'", true],
      ["export const J = 'Summary retention: 90 days'", true],
      // Chief design's forms on c96ba0b0: "keeps" before the summary, a window, and days of summaries.
      ["export const T = 'Pro keeps every summary you read.'", true],
      ['export const U = `Summaries saved for ${N} days`', true],
      ['export const V = `Free summaries expire after ${N} days`', true],
      ['export const W = `${N} days of summaries`', true],
      ['export const K = () => <button>Show full history</button>', false],
      ['export const L = () => <a href="/x">Full history on SEC EDGAR</a>', false],
      ["export const M = (t: string) => `Fetching ${t}'s full SEC reporting history.`", false],
      ["export const O = 'Company search and historical filings'", false],
      ["export const P = () => window.history.replaceState({}, '', '/x')", false],
      ['// Free keeps 90 days: a comment is not copy', false],
      ["export const Q = 'Your existing summaries remain accessible.'", false],
      ['export const X = () => <h2>Saved summaries</h2>', false],
      ['export const Y = `Unlimited summaries for ${N} days on the trial`', false],
      ["export const R = () => <p>Full{' '}history</p>", 'gap'],
      ["export const S = 'We hold on to everything you read.'", 'gap'],
    ]
    const found = new Set(historyFindings(literals(planted.map(([code]) => code).join('\n'), 'features/probe/Claims.tsx')).map((f) => Number(f.split(':')[1].split(' ')[0])))
    expect([...found].sort((a, b) => a - b)).toEqual(planted.flatMap(([, flag], i) => (flag === true ? [i + 1] : [])))
  })
})

describe("Pro's fair-use guardrail is one sentence, read at the FAQ and the limit card (E58, D-046)", () => {
  it('is built from the mirrored cap, never a typed number', () => {
    expect(PRO_FAIR_USE_LINE).toContain(`${PRO_SUMMARY_MONTHLY_CAP} new summaries a month`)
    const source = readFileSync(path.join(FRONTEND, 'lib/planLimits.ts'), 'utf8')
    expect(source).toMatch(/export const PRO_FAIR_USE_LINE = `[^`]*\$\{PRO_SUMMARY_MONTHLY_CAP\}[^`]*`/)
  })

  it('the /pricing FAQ and the filing page’s monthly-limit card place it', () => {
    for (const rel of ['app/pricing/page.tsx', 'app/filing/[id]/StreamingSummaryDisplay.tsx']) {
      const sf = ts.createSourceFile(rel, readFileSync(path.join(FRONTEND, rel), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
      let imported = false
      let placed = 0
      const visit = (node: ts.Node) => {
        if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier) && node.moduleSpecifier.text === '@/lib/planLimits') {
          const named = node.importClause?.namedBindings
          imported = !!named && ts.isNamedImports(named) && named.elements.some((el) => el.name.text === 'PRO_FAIR_USE_LINE' && !el.propertyName)
        }
        if (ts.isJsxExpression(node) && node.expression && ts.isIdentifier(node.expression) && node.expression.text === 'PRO_FAIR_USE_LINE') placed++
        ts.forEachChild(node, visit)
      }
      visit(sf)
      expect({ rel, imported, placed }).toEqual({ rel, imported: true, placed: 1 })
    }
  })

  it('no other copy names a fair-use ceiling on summaries', () => {
    const elsewhere = LITERALS.filter((l) => l.rel !== 'lib/planLimits.ts' && SUMMARY_FAIR_USE.test(l.text))
    expect(elsewhere.map((l) => `${l.rel}:${l.line} ${JSON.stringify(l.text)}`)).toEqual([])
    expect(LITERALS.filter((l) => l.rel === 'lib/planLimits.ts' && SUMMARY_FAIR_USE.test(l.text))).toHaveLength(1)
  })

  it('no module but lib/planLimits.ts reads PRO_SUMMARY_MONTHLY_CAP, so the number reaches copy only through the sentence', () => {
    const reads = MODULES.filter((rel) => rel !== 'lib/planLimits.ts').flatMap((rel) =>
      capReads(readFileSync(path.join(FRONTEND, rel), 'utf8'), rel).map((line) => `${rel}:${line}`),
    )
    expect(reads, "state Pro's ceiling by placing PRO_FAIR_USE_LINE, never by reading the cap").toEqual([])
    expect(capReads(readFileSync(path.join(FRONTEND, 'lib/planLimits.ts'), 'utf8'), 'lib/planLimits.ts').length, 'the read finds the declaration').toBeGreaterThan(0)
  })

  it('reads the cap under any name a module gives it, and passes the sentence and a comment (a self-check on planted forms)', () => {
    const flagged: Record<string, string> = {
      'a named import read in JSX': "import { PRO_SUMMARY_MONTHLY_CAP } from '@/lib/planLimits'\nexport const A = () => <p>Pro accounts can generate up to {PRO_SUMMARY_MONTHLY_CAP} new summaries a month.</p>",
      'a renamed import': "import { PRO_SUMMARY_MONTHLY_CAP as CAP } from '@/lib/planLimits'\nexport const B = `${CAP} a month`",
      'a namespace member': "import * as plan from '@/lib/planLimits'\nexport const C = plan.PRO_SUMMARY_MONTHLY_CAP",
      'a string key': "import * as plan from '@/lib/planLimits'\nexport const D = plan['PRO_SUMMARY_MONTHLY_CAP']",
    }
    const passing: Record<string, string> = {
      'the sentence': "import { PRO_FAIR_USE_LINE } from '@/lib/planLimits'\nexport const E = () => <p>{PRO_FAIR_USE_LINE}</p>",
      'a comment': '// PRO_SUMMARY_MONTHLY_CAP reaches copy only through PRO_FAIR_USE_LINE\nexport const F = null',
    }
    expect(Object.keys(flagged).filter((name) => capReads(flagged[name], 'probe.tsx').length === 0), 'a read the check missed').toEqual([])
    expect(Object.keys(passing).filter((name) => capReads(passing[name], 'probe.tsx').length > 0), 'a look-alike the check flagged').toEqual([])
  })
})

/** The lines on which a module names PRO_SUMMARY_MONTHLY_CAP in code: an identifier (an import under any local name, a
 * reference, a namespace member, a destructured key) or a string key (`plan['PRO_SUMMARY_MONTHLY_CAP']`). A comment
 * is not a read. Out of reach: a name the module computes (`plan[`PRO_${kind}`]`). */
function capReads(source: string, rel: string): number[] {
  if (!source.includes('PRO_SUMMARY_MONTHLY_CAP')) return []
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, rel.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const lines = new Set<number>()
  const visit = (node: ts.Node) => {
    if ((ts.isIdentifier(node) || ts.isStringLiteralLike(node)) && node.text === 'PRO_SUMMARY_MONTHLY_CAP') {
      lines.add(sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return [...lines]
}
