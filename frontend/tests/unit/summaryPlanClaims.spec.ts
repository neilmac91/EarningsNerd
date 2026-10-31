import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { pythonTokens } from './pythonTokens'
import { isNonRetryableStreamError, isPaywallStreamError } from '@/features/summaries/api/summaries-api'
import { STREAM_ERROR_COPY } from '@/features/summaries/lib/streamErrorCopy'
import { fmtCount } from '@/lib/format'
import { ANALYSIS_LINES, ANALYSIS_MONTHLY_CAP, PRO_SUMMARY_MONTHLY_CAP } from '@/lib/planLimits'

/**
 * Three claims a plan makes about summaries, held to what the code does (docs/brand/decisions-log.md D-046; CLAUDE.md
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
 * 2. Pro's fair-use guardrail is one sentence (E58, D-050): ANALYSIS_LINES.fairUse in lib/planLimits.ts, in two forms
 *    keyed to the analysis flag (both ceilings while it ships Multi-Period Analysis, the summary ceiling alone while
 *    not), built from PRO_SUMMARY_MONTHLY_CAP and ANALYSIS_MONTHLY_CAP (which planLimitsLockstep.spec.ts holds to
 *    backend/app/services/entitlements.py), read through proFairUseLine(), placed by the /pricing FAQ and the filing
 *    page's monthly-limit card, and typed nowhere else: no other copy literal names a fair-use ceiling on summaries or
 *    analyses, and no module but lib/planLimits.ts reads either cap, nor any module the usage response's
 *    analysis_limit, so the pages' numbers reach copy only through the sentence (a typed count, "300 summary
 *    generations", "300 new summaries" or "1,000 analysis generations", is planLimitsLockstep.spec.ts's to fail). One
 *    route is the backend's: the analysis route's 429 at the ceiling, which the narrative card shows as written
 *    (analysis-api.ts), states the number as the sentence does ("1,000 analysis generations, regenerations
 *    included"), and backend/tests/unit/test_analysis_stream.py holds its words. PricingPage.spec.tsx and
 *    StreamingSummaryDisplay.spec.tsx see the sentence rendered, PricingPage.spec.tsx in both forms.
 * 3. The ceiling counts what the meter counts (Codex on #1395, review comment 4314197512). Every run the usage gate
 *    admits takes a unit of PRO_SUMMARY_MONTHLY_CAP once its provider request is issued, a Pro regeneration (`force`)
 *    among them, so a count in "new summaries" overstates the allowance. The fair-use sentence and the line the filing
 *    page shows at the ceiling (STREAM_ERROR_COPY's one line for a stream error no retry can help, not the paywall,
 *    that names a limit on summaries: admission.py's pause) count summary generations, regenerations included, and
 *    no copy literal that names a limit (CEILING_CUES) counts new summaries. The planted forms score the reach: the
 *    two sentences before the review are flagged, and the backend's own pause (a key the map replaces, which names
 *    no limit) passes; out of reach, planted as gaps: a count split around an expression, and one said in other
 *    words. The premise is read where it would change: the stream route sends `force` into the one pipeline as
 *    `force_regenerate`, and the pipeline's modules and the usage service read that flag only at today's sites
 *    (FORCE_READS), none of them a meter. A PR that exempts a regeneration from the meter in one of them fails here,
 *    and restates the ceiling in that PR with this gate moved beside it. Out of reach: an exemption under another
 *    name or outside those modules. The analysis ceiling is held the same way (E122): the sentence counts analysis
 *    generations, regenerations included, and no ceiling counts new analyses (NEW_ANALYSES). The premise: a reader's
 *    forced refresh takes a unit, since the route meters every fresh completion but a system-invalidated one, and the
 *    narrative marks a run invalidated only when it is not forced; the route and the narrative read `force` only at
 *    today's sites (ANALYSIS_FORCE_READS), and the meter's other modules read it nowhere. Out of reach as for
 *    summaries: an exemption under another name or outside those modules.
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

/** A fair-use ceiling named on summaries (the fair-use sentence's own subject), in either order. */
const SUMMARY_FAIR_USE = /\bfair[- ]use\b[^.]*\bsummar|\bsummar[^.]*\bfair[- ]use\b/i
/** A fair-use ceiling named on analyses, in either order: the sentence's analysis form names it beside the summaries. */
const ANALYSIS_FAIR_USE = /\bfair[- ]use\b[^.]*\banalys|\banalys[^.]*\bfair[- ]use\b/i

/** What makes a literal a ceiling sentence: it names a limit or a bound, or counts by the month. */
const CEILING_CUES = /\bfair[- ]use\b|\b(?:limits?|ceilings?|caps?|capped|allowance|quota)\b|\bup to\b|\b(?:a|per|each|every|this|next) month\b|\bmonth's\b|\bmonthly\b/i
/** The count the meter does not keep: new summaries, while a regeneration takes a unit too. */
const NEW_SUMMARIES = /\bnew[- ](?:AI )?summar(?:y|ies)\b/i
/** The same for the analysis ceiling: new analyses, while a reader's forced refresh takes a unit too, under the
    feature's own name among them ("new Multi-Period Analyses"). */
const NEW_ANALYSES = /\bnew[-\u2010-\u2015\s]+(?:(?:AI|multi[-\u2010-\u2015\s]?period|trend)[-\u2010-\u2015\s]+)*analys[ie]s\b/i

/** Where the summary pipeline reads its force flag today, as code, per module under backend/app: the orchestrator's
 * parameter and its pass-through, the run's field, the stored-summary short-circuit (load_filing), the in-place
 * save (finalize), and the excerpt a forced run keeps unsaved until its summary is written: enrichment's persist
 * choice (`persist=False`) and finalize's `replace_excerpt` on the INSERT. None of them is a meter: admit's usage
 * gate, the charge at provider start (GenerationRun.begin_charge), the refunds and the usage service count a
 * regeneration as they count any run. */
const FORCE_READS: Record<string, number> = {
  'services/summary_pipeline.py': 3,
  'services/summary_stages/admission.py': 1,
  'services/summary_stages/enrichment.py': 1,
  'services/summary_stages/finalize.py': 6,
  'services/summary_stages/generation_run.py': 1,
}

/** Where the analysis route and its narrative read `force` today, as code, per module under backend/app: the route's
 * cap gate (a forced run never takes the free path) and its hand-off to the narrative (the keyword and the request's
 * field), and the narrative's run field, its parameters and the run's own copy, its cache read (a forced run never
 * re-serves) and its invalidation mark (a forced run is never marked invalidated, so the route's one exemption never
 * covers it). The meter's other modules (services/analysis_data_access.py, services/subscription_service.py, the
 * façade the route calls, services/trend_analysis_service.py, and the rest of services/trend_analysis/) read it
 * nowhere. */
const ANALYSIS_FORCE_READS: Record<string, number> = {
  'routers/analysis.py': 3,
  'services/trend_analysis/narrative.py': 8,
}

/** The reads of a name in a Python module: names only, so a comment or a docstring is not one. */
const nameReads = (source: string, name: string) => pythonTokens(source).filter((t) => t.kind === 'name' && t.text === name).length
const forceReads = (source: string) => nameReads(source, 'force_regenerate')

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

/** Every ceiling sentence that counts new summaries or new analyses. */
const newCountFindings = (lits: Literal[]) =>
  lits
    .filter((l) => CEILING_CUES.test(l.text) && (NEW_SUMMARIES.test(l.text) || NEW_ANALYSES.test(l.text)))
    .map((l) => `${l.rel}:${l.line} ${JSON.stringify(l.text)}`)

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

describe("Pro's fair-use guardrail is one sentence, read at the FAQ and the limit card (E58, D-046, D-050)", () => {
  const { text: BOTH, off: SUMMARY_ONLY } = ANALYSIS_LINES.fairUse

  it('is built from the mirrored caps, never a typed number, in a form for each state of the analysis flag', () => {
    expect(BOTH).toContain(`up to ${PRO_SUMMARY_MONTHLY_CAP} summary and ${fmtCount(ANALYSIS_MONTHLY_CAP)} analysis generations a month`)
    expect(SUMMARY_ONLY).toContain(`up to ${PRO_SUMMARY_MONTHLY_CAP} summary generations a month`)
    expect(SUMMARY_ONLY, 'with the flag off the sentence names no analysis').not.toMatch(/analys/i)
    const source = readFileSync(path.join(FRONTEND, 'lib/planLimits.ts'), 'utf8')
    expect(source).toMatch(
      /fairUse: \{\s*text: `[^`]*\$\{PRO_SUMMARY_MONTHLY_CAP\}[^`]*\$\{fmtCount\(ANALYSIS_MONTHLY_CAP\)\}[^`]*`,\s*flag: 'analysis',\s*off: `[^`]*\$\{PRO_SUMMARY_MONTHLY_CAP\}[^`]*`,\s*\}/,
    )
  })

  it('the /pricing FAQ and the filing page’s monthly-limit card place it', () => {
    for (const rel of ['app/pricing/page.tsx', 'app/filing/[id]/StreamingSummaryDisplay.tsx']) {
      const sf = ts.createSourceFile(rel, readFileSync(path.join(FRONTEND, rel), 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
      let imported = false
      let placed = 0
      const visit = (node: ts.Node) => {
        if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier) && node.moduleSpecifier.text === '@/lib/planLimits') {
          const named = node.importClause?.namedBindings
          imported = !!named && ts.isNamedImports(named) && named.elements.some((el) => el.name.text === 'proFairUseLine' && !el.propertyName)
        }
        const call = ts.isJsxExpression(node) && node.expression && ts.isCallExpression(node.expression) ? node.expression : null
        if (call && ts.isIdentifier(call.expression) && call.expression.text === 'proFairUseLine' && call.arguments.length === 0) placed++
        ts.forEachChild(node, visit)
      }
      visit(sf)
      expect({ rel, imported, placed }).toEqual({ rel, imported: true, placed: 1 })
    }
  })

  it('no other copy names a fair-use ceiling on summaries or analyses', () => {
    for (const [subject, re] of [['summaries', SUMMARY_FAIR_USE], ['analyses', ANALYSIS_FAIR_USE]] as const) {
      const elsewhere = LITERALS.filter((l) => l.rel !== 'lib/planLimits.ts' && re.test(l.text))
      expect(elsewhere.map((l) => `${l.rel}:${l.line} ${JSON.stringify(l.text)}`), subject).toEqual([])
    }
    // In lib/planLimits.ts, the sentence's two forms and nothing else.
    const own = (re: RegExp) => LITERALS.filter((l) => l.rel === 'lib/planLimits.ts' && re.test(l.text)).map((l) => l.text)
    const asRead = (form: string) => form.replace(/\d[\d,]*/g, '{x}')
    expect(own(SUMMARY_FAIR_USE)).toEqual([asRead(BOTH), asRead(SUMMARY_ONLY)])
    expect(own(ANALYSIS_FAIR_USE)).toEqual([asRead(BOTH)])
  })

  it('no module but lib/planLimits.ts reads either cap, so the numbers reach copy only through the sentence', () => {
    for (const cap of CAPS) {
      const reads = MODULES.filter((rel) => rel !== 'lib/planLimits.ts').flatMap((rel) =>
        capReads(readFileSync(path.join(FRONTEND, rel), 'utf8'), rel, cap).map((line) => `${rel}:${line}`),
      )
      expect(reads, `state Pro's ceilings by placing proFairUseLine(), never by reading ${cap}`).toEqual([])
      expect(capReads(readFileSync(path.join(FRONTEND, 'lib/planLimits.ts'), 'utf8'), 'lib/planLimits.ts', cap).length, `the read finds ${cap}'s declaration`).toBeGreaterThan(0)
    }
    const usageReads = MODULES.flatMap((rel) =>
      capReads(readFileSync(path.join(FRONTEND, rel), 'utf8'), rel, USAGE_ANALYSIS_LIMIT).map((line) => `${rel}:${line}`),
    )
    expect(usageReads, "state Pro's analysis ceiling by placing proFairUseLine(), never by reading the usage response's analysis_limit").toEqual([])
    // The field read is the one the usage response carries the ceiling in, so a rename cannot leave the check reading nothing.
    expect(readFileSync(path.join(FRONTEND, 'features/subscriptions/api/subscriptions-api.ts'), 'utf8'), 'the usage type declares analysis_limit').toMatch(
      /^\s*analysis_limit\s*:\s*number\b/m,
    )
    expect(readFileSync(path.join(BACKEND_APP, 'routers/subscriptions.py'), 'utf8'), 'the usage response sends the ceiling as analysis_limit').toMatch(
      /\banalysis_limit=ANALYSIS_MONTHLY_CAP\b/,
    )
  })

  it("reads the usage response's analysis_limit as any read but its type's own member (a self-check on planted forms)", () => {
    const flagged: Record<string, string> = {
      'a property': 'export const A = (usage: Usage) => <p>{usage.analysis_limit} a month</p>',
      'an optional chain': 'export const B = (data?: Usage) => data?.analysis_limit',
      'a string key': "export const C = (usage: Usage) => usage['analysis_limit']",
      'a destructured name': 'export const D = ({ analysis_limit: cap }: Usage) => cap',
    }
    const passing: Record<string, string> = {
      "the response type's member": 'export interface Usage {\n  analysis_limit: number\n}',
      'a comment': '// analysis_limit reaches no page\nexport const E = null',
    }
    expect(Object.keys(flagged).filter((name) => capReads(flagged[name], 'probe.tsx', USAGE_ANALYSIS_LIMIT).length === 0), 'a read the check missed').toEqual([])
    expect(Object.keys(passing).filter((name) => capReads(passing[name], 'probe.tsx', USAGE_ANALYSIS_LIMIT).length > 0), 'a look-alike the check flagged').toEqual([])
  })

  it('reads a cap under any name a module gives it, and passes the sentence and a comment (a self-check on planted forms)', () => {
    for (const cap of CAPS) {
      const flagged: Record<string, string> = {
        'a named import read in JSX': `import { ${cap} } from '@/lib/planLimits'\nexport const A = () => <p>Pro accounts can generate up to {${cap}} new summaries a month.</p>`,
        'a renamed import': `import { ${cap} as CAP } from '@/lib/planLimits'\nexport const B = \`\${CAP} a month\``,
        'a namespace member': `import * as plan from '@/lib/planLimits'\nexport const C = plan.${cap}`,
        'a string key': `import * as plan from '@/lib/planLimits'\nexport const D = plan['${cap}']`,
      }
      const passing: Record<string, string> = {
        'the sentence': "import { proFairUseLine } from '@/lib/planLimits'\nexport const E = () => <p>{proFairUseLine()}</p>",
        'a comment': `// ${cap} reaches copy only through proFairUseLine()\nexport const F = null`,
      }
      expect(Object.keys(flagged).filter((name) => capReads(flagged[name], 'probe.tsx', cap).length === 0), `a read of ${cap} the check missed`).toEqual([])
      expect(Object.keys(passing).filter((name) => capReads(passing[name], 'probe.tsx', cap).length > 0), `a look-alike the check flagged for ${cap}`).toEqual([])
    }
  })
})

describe("Pro's ceilings count what the meters count: generations, regenerations included (Codex on #1395, E122)", () => {
  it('the FAQ and the line at the ceiling count generations, regenerations included, and no ceiling counts new summaries or analyses', () => {
    expect(
      newCountFindings(LITERALS),
      'a regeneration takes a unit of the ceiling: count summary and analysis generations, regenerations included, never new summaries or analyses',
    ).toEqual([])
    const atCeiling = Object.entries(STREAM_ERROR_COPY)
      .filter(([key, shown]) => isNonRetryableStreamError(key) && !isPaywallStreamError(key) && CEILING_CUES.test(shown) && /\bsummar/i.test(shown))
      .map(([, shown]) => shown)
    expect(atCeiling, "streamErrorCopy.ts has one line for Pro's ceiling, and it names the limit").toHaveLength(1)
    for (const sentence of [ANALYSIS_LINES.fairUse.text, ANALYSIS_LINES.fairUse.off, ...atCeiling]) {
      expect(sentence, 'it names the unit it counts').toMatch(/\bgenerat/i)
      expect(sentence, 'and that a regeneration is one').toMatch(/\bregenerations included\b/)
    }
    expect(ANALYSIS_LINES.fairUse.text, 'the analysis ceiling counts generations too').toMatch(/\banalysis generations\b/)
  })

  it('reads a ceiling counted in new summaries, and passes the counted unit and the look-alikes (a self-check on planted forms)', () => {
    const planted: Array<[string, boolean | 'gap']> = [
      // The two sentences before the review, then chief design's typed plant and first example for E122.
      ["export const A = `Pro's unlimited summaries have a fair-use ceiling: an account can generate up to ${CAP} new summaries a month.`", true],
      ["export const B = `Your account has reached this month's limit on new summaries. It resets next month. Contact support with any questions.`", true],
      ["export const C = 'Pro accounts can generate up to 300 new summaries a month.'", true],
      ['export const D = `Up to ${S} new summaries and ${A} new analyses a month; results already generated never count`', true],
      ['export const E = () => <p>Your plan includes {CAP} new summaries each month.</p>', true],
      ["export const F = 'Your new-summary allowance resets next month.'", true],
      ["export const G = `Pro's unlimited summaries have a fair-use ceiling: an account can run up to ${CAP} summary generations a month, regenerations included.`", false],
      ["export const H = `Your account has reached this month's limit for generating summaries, regenerations included. It resets next month. Contact support with any questions.`", false],
      ["export const I = `We've temporarily paused new summary generation on your account due to unusually high recent volume. Please try again later or contact support.`", false],
      ['export const J = `${n} new summaries are ready to read`', false],
      ['export const K = `${FREE} AI summaries a month`', false],
      ["export const L = 'Your free summaries reset next month. Or go unlimited now with Pro.'", false],
      ['// Up to 300 new summaries a month: a comment is not copy', false],
      // The analysis ceiling (E122): counted in new analyses, it is flagged; counted in generations, it passes.
      ['export const O = `Pro accounts can run up to ${A} new analyses a month.`', true],
      ["export const P = 'Your new-analysis allowance resets next month.'", true],
      ["export const Q = `Pro's unlimited summaries and Multi-Period Analysis have fair-use ceilings: an account can run up to ${S} summary and ${A} analysis generations a month, regenerations included.`", false],
      ['export const R = `${n} new analyses are ready to read`', false],
      ['export const T = `Pro accounts can run up to ${A} new Multi-Period Analyses a month.`', true],
      ['export const M = `Up to ${CAP} new ${noun} a month`', 'gap'],
      ["export const N = 'Up to 300 summaries of filings you have not summarized yet, each month.'", 'gap'],
    ]
    const found = new Set(newCountFindings(literals(planted.map(([code]) => code).join('\n'), 'features/probe/Ceiling.tsx')).map((f) => Number(f.split(':')[1].split(' ')[0])))
    expect([...found].sort((a, b) => a - b)).toEqual(planted.flatMap(([, flag], i) => (flag === true ? [i + 1] : [])))
  })

  it('a regeneration takes a unit: the route sends force through the one pipeline, and no module of it reads the flag at a meter', () => {
    const route = pythonTokens(readFileSync(path.join(BACKEND_APP, 'routers/summaries.py'), 'utf8'))
    expect(
      route.some((t, i) => t.kind === 'name' && t.text === 'force_regenerate' && route[i + 1]?.text === '=' && route[i + 2]?.text === 'force'),
      'routers/summaries.py no longer sends force into stream_filing_summary as force_regenerate: find where a Pro regeneration goes, and whether it still takes a unit',
    ).toBe(true)
    const stages = execFileSync('git', ['ls-files', '--', 'services/summary_stages'], { cwd: BACKEND_APP, encoding: 'utf8' })
      .split('\n')
      .filter((rel) => rel.endsWith('.py'))
    expect(stages.length).toBeGreaterThan(5)
    const reads = Object.fromEntries(
      ['services/summary_pipeline.py', 'services/subscription_service.py', ...stages]
        .map((rel) => [rel, forceReads(readFileSync(path.join(BACKEND_APP, rel), 'utf8'))] as const)
        .filter(([, count]) => count > 0),
    )
    expect(
      reads,
      'a summary pipeline module reads force_regenerate in a new place: if a regeneration no longer takes a unit of the monthly ' +
        'ceiling, restate the fair-use sentence (ANALYSIS_LINES.fairUse) and the line at the ceiling in that PR, then move these counts',
    ).toEqual(FORCE_READS)
  })

  it("a reader's forced analysis refresh takes a unit: the route and the narrative read force only at today's sites", () => {
    const trend = execFileSync('git', ['ls-files', '--', 'services/trend_analysis'], { cwd: BACKEND_APP, encoding: 'utf8' })
      .split('\n')
      .filter((rel) => rel.endsWith('.py'))
    expect(trend.length).toBeGreaterThan(3)
    const reads = Object.fromEntries(
      ['routers/analysis.py', 'services/analysis_data_access.py', 'services/subscription_service.py', 'services/trend_analysis_service.py', ...trend]
        .map((rel) => [rel, nameReads(readFileSync(path.join(BACKEND_APP, rel), 'utf8'), 'force')] as const)
        .filter(([, count]) => count > 0),
    )
    expect(
      reads,
      "an analysis module reads force in a new place: if a reader's forced refresh no longer takes a unit of the monthly " +
        'ceiling, restate the fair-use sentence (ANALYSIS_LINES.fairUse) in that PR, then move these counts',
    ).toEqual(ANALYSIS_FORCE_READS)
    // The two sites that keep a forced refresh metered, by what they say: the narrative never marks a forced run
    // invalidated, and the route exempts only an invalidated completion.
    const restate = 'if a forced refresh can now go unmetered, restate the fair-use sentence (ANALYSIS_LINES.fairUse) in that PR, then move this line'
    const narrative = readFileSync(path.join(BACKEND_APP, 'services/trend_analysis/narrative.py'), 'utf8')
    expect(narrative, `narrative.py's invalidation mark changed: ${restate}`).toMatch(/^\s*run\.invalidated = cached is not None and not run\.force$/m)
    const route = readFileSync(path.join(BACKEND_APP, 'routers/analysis.py'), 'utf8')
    expect(route, `routers/analysis.py's meter exemption changed: ${restate}`).toMatch(
      /^\s*exempt = event\.get\("invalidated"\) and event\.get\("analysis_id"\) is not None$/m,
    )
  })

  it('reads the flag as code, never in a comment or a docstring (a self-check on planted forms)', () => {
    const planted: Array<[string, number]> = [
      ['# force_regenerate never reaches the meter', 0],
      ['def admit(run):\n    """Under force_regenerate the stored row is replaced in place."""', 0],
      ['if run.force_regenerate:\n    return', 1],
      ['stream(force_regenerate=force_regenerate)', 2],
    ]
    expect(planted.map(([source]) => forceReads(source))).toEqual(planted.map(([, count]) => count))
  })
})

/** Pro's two monthly ceilings, as lib/planLimits.ts mirrors them. */
const CAPS = ['PRO_SUMMARY_MONTHLY_CAP', 'ANALYSIS_MONTHLY_CAP'] as const
/** The usage response's analysis ceiling (`Usage.analysis_limit` in features/subscriptions/api/subscriptions-api.ts), the
 * ceiling's other route to a page. */
const USAGE_ANALYSIS_LIMIT = 'analysis_limit'

/** The lines on which a module names a cap in code: an identifier (an import under any local name, a reference, a
 * namespace member, a destructured key) or a string key (`plan['PRO_SUMMARY_MONTHLY_CAP']`). A comment is not a read,
 * nor a type's own member (`analysis_limit: number` in the usage response's type). Out of reach: a name the module
 * computes (`plan[`PRO_${kind}`]`). */
function capReads(source: string, rel: string, cap: (typeof CAPS)[number] | typeof USAGE_ANALYSIS_LIMIT): number[] {
  if (!source.includes(cap)) return []
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, rel.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const lines = new Set<number>()
  const visit = (node: ts.Node) => {
    const member = node.parent !== undefined && ts.isPropertySignature(node.parent) && node.parent.name === node
    if ((ts.isIdentifier(node) || ts.isStringLiteralLike(node)) && node.text === cap && !member) {
      lines.add(sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return [...lines]
}
