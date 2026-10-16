import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import {
  ANALYSIS_MAX_ANNUAL_PERIODS,
  ANALYSIS_MAX_QUARTERLY_PERIODS,
  FREE_SUMMARY_LIMIT,
  FREE_EARNINGS_ALERT_LIMIT,
  FREE_COPILOT_QUESTIONS,
  FREE_HISTORY_RETENTION_DAYS,
} from '@/lib/planLimits'

/**
 * Structural gate for free-tier plan copy (CLAUDE.md rules 4 and 12).
 *
 * The free summary and earnings-alert caps are defined once on the server
 * (backend/app/services/entitlements.py). Guest-facing copy cannot read the usage response, so
 * frontend/lib/planLimits.ts mirrors the two numbers — and this spec keeps the mirror honest:
 * (1) the mirrored values equal the backend constants; (2) no source file spells the caps out as
 * bare literals again ("5 summaries", "3 companies"), which is how the copy drifted before.
 */
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const entitlements = readFileSync(path.resolve(frontendDir, '../backend/app/services/entitlements.py'), 'utf8')

const backendConst = (name: string): number => {
  const match = entitlements.match(new RegExp(`^${name}\\s*=\\s*(\\d+)`, 'm'))
  if (!match) throw new Error(`${name} not found in backend/app/services/entitlements.py`)
  return Number(match[1])
}

/** A field of the `_FREE = Entitlements(...)` literal, e.g. `copilot_free_taste=3,`. */
const freeEntitlementField = (name: string): number => {
  const block = entitlements.match(/_FREE = Entitlements\(([\s\S]*?)\n\)/)
  const match = block?.[1].match(new RegExp(`\\b${name}\\s*=\\s*(\\d+)`))
  if (!match) throw new Error(`${name} not found in the _FREE entitlements block`)
  return Number(match[1])
}

const SOURCE_ROOTS = ['app', 'features', 'components', 'lib', 'hooks']
const LITERAL_PATTERNS: Array<{ label: string; pattern: RegExp }> = [
  // Copy: the caps written out in prose.
  { label: 'free summary cap spelled out', pattern: /\b\d+ (?:free )?(?:AI )?summar(?:y|ies)\b/i },
  { label: 'free summary cap as a numeric fallback', pattern: /summaries_limit\s*(?:\|\||\?\?)\s*\d+/ },
  { label: 'earnings-alert cap spelled out', pattern: /alerts for \d+ compan|\b\d+ earnings(?:-day)? alerts?\b/i },
  { label: 'free Copilot question taste spelled out', pattern: /\b\d+ (?:free )?Ask this Filing questions?\b|\bFree accounts get \d+ questions?\b/i },
  { label: 'free history retention spelled out', pattern: /\b\d+-day (?:summary )?history\b|\bFree keeps \d+ days\b/i },
  // Behaviour: a free-tier cap constant assigned a literal, or a count compared against one
  // (the calendar pre-flight and fixture checks drifted this way before the mirror existed).
  { label: 'free-tier cap constant assigned a literal', pattern: /\bFREE_[A-Z0-9_]*(?:LIMIT|CAP)\b\s*=\s*\d+/ },
  { label: 'count compared against a literal cap', pattern: /(?:currentCount\(\)|enabled\.size|alertCount|alertTickers\.size)\s*(?:>=|>|===|==)\s*\d+/ },
]

/** Files that enforce a cap functionally must take it from the mirror, not a local literal. */
const FUNCTIONAL_CAP_SITES = [
  'features/calendar/hooks/useCalendar.ts',
  'features/calendar/api/calendar-fixtures.ts',
  'features/calendar/components/AlertBell.tsx',
  'app/dashboard/page.tsx',
]

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = path.join(dir, entry)
    if (entry === 'node_modules' || entry === '.next') return []
    if (statSync(full).isDirectory()) return walk(full)
    return /\.(tsx?|jsx?|mdx?)$/.test(entry) ? [full] : []
  })
}

describe('free-tier plan limits move in lockstep with the backend', () => {
  it('mirrors FREE_TIER_SUMMARY_LIMIT', () => {
    expect(FREE_SUMMARY_LIMIT).toBe(backendConst('FREE_TIER_SUMMARY_LIMIT'))
  })

  it('mirrors FREE_EARNINGS_ALERT_LIMIT', () => {
    expect(FREE_EARNINGS_ALERT_LIMIT).toBe(backendConst('FREE_EARNINGS_ALERT_LIMIT'))
  })

  it('mirrors the free Copilot taste and history retention', () => {
    expect(FREE_COPILOT_QUESTIONS).toBe(freeEntitlementField('copilot_free_taste'))
    expect(FREE_HISTORY_RETENTION_DAYS).toBe(freeEntitlementField('history_retention_days'))
  })

  it('functional cap sites import the mirrored constants', () => {
    for (const rel of FUNCTIONAL_CAP_SITES) {
      const source = readFileSync(path.join(frontendDir, rel), 'utf8')
      expect(source, `${rel} must import from '@/lib/planLimits'`).toMatch(/from '@\/lib\/planLimits'/)
    }
  })

  it('no source file spells a free-tier cap out as a bare literal', () => {
    const offenders: string[] = []
    for (const root of SOURCE_ROOTS) {
      for (const file of walk(path.join(frontendDir, root))) {
        if (file.endsWith(path.join('lib', 'planLimits.ts'))) continue
        const lines = readFileSync(file, 'utf8').split('\n')
        lines.forEach((line, index) => {
          for (const { label, pattern } of LITERAL_PATTERNS) {
            if (pattern.test(line)) offenders.push(`${path.relative(frontendDir, file)}:${index + 1} (${label}): ${line.trim()}`)
          }
        })
      }
    }
    expect(offenders, 'use FREE_SUMMARY_LIMIT / FREE_EARNINGS_ALERT_LIMIT from lib/planLimits instead').toEqual([])
  })
})

/**
 * Multi-Period Analysis period caps (the /analysis metadata and lead, the landing's feature row, the
 * /pricing Pro card). The backend's Settings defaults (backend/app/config.py: ANALYSIS_MAX_ANNUAL_PERIODS,
 * ANALYSIS_MAX_QUARTERLY_PERIODS) are the truth the picker reads from the coverage response; copy that
 * renders before it takes the mirror in lib/planLimits.ts. So (1) the mirror equals the defaults, and
 * (2) no copy types a count of years or quarters outside the few that state a different fact
 * (PERIOD_COUNT_OTHER_FACTS).
 *
 * Copy is what a .ts or .tsx file under SOURCE_ROOTS writes as text, read through the AST (comments are
 * not copy): each string, template and `+` chain, and each JSX tree's text as React renders it. A tree's
 * text children lose the whitespace JSX drops and have their entities decoded (`&nbsp;`), and its literal
 * children (`{10}`, `{'10'}`, `{' '}`) and nested elements' text (`<strong>10</strong>`) are joined in
 * order, so a count split across markup reads whole. A part that is not a literal (a name, a call, a
 * condition) reads as a hole no count spans, which is how `{ANALYSIS_MAX_ANNUAL_PERIODS} fiscal years`
 * passes. A typed count is digits, a "+" allowed after them, or a number word up to twelve; then spaces or
 * hyphens (a no-break space and the Unicode hyphens among them); an optional "fiscal" or "financial"; then
 * year, quarter or an abbreviation (yr, qtr, FY, FQ), singular or plural (TYPED_PERIOD_COUNT).
 *
 * Outside the gate, left to review, each planted as a gap in PLANTED_FORMS: a count spelled past twelve or
 * as a phrase ("fifteen years", "a decade", "a dozen quarters"); another word between the count and its
 * unit ("10 calendar years", "10 or more years"); another unit ("10 annual periods", the shorthand "10Y");
 * and a count held in a name or chosen by a condition (`{annual ? 10 : 12} fiscal years`), which reads as
 * a hole. Model-written text is not copy: the demo payload's sample narrative
 * (features/analysis/demo/demo-analysis.json) states its own window, "six fiscal years", as a model would.
 */
const config = readFileSync(path.resolve(frontendDir, '../backend/app/config.py'), 'utf8')
const settingDefault = (name: string): number => {
  const match = config.match(new RegExp(`^\\s+${name}\\s*:\\s*int\\s*=\\s*(\\d+)`, 'm'))
  if (!match) throw new Error(`${name} not found in backend/app/config.py`)
  return Number(match[1])
}

const NUMBER_WORDS = 'one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve'
/** Spaces (`\s` reads a no-break space as one) and hyphens, the Unicode hyphens and dashes among them. */
const SEPARATOR = '[-\\u2010-\\u2015\\s]+'
const UNITS = 'years?|yrs?|quarters?|qtrs?|FYs?|FQs?'
const TYPED_PERIOD_COUNT_SOURCE = `\\b(?:\\d+\\+?|${NUMBER_WORDS})${SEPARATOR}(?:(?:fiscal|financial)${SEPARATOR})?(?:${UNITS})\\b`
/** Digits (a "+" allowed after them) or a number word, a separator, an optional "fiscal" or "financial", then a unit. */
const TYPED_PERIOD_COUNT = new RegExp(TYPED_PERIOD_COUNT_SOURCE, 'i')
/** Cheap raw-text prefilter: a file whose source never spells a unit has no copy the scan can flag, so it
 * skips the parse. Every TYPED_PERIOD_COUNT hit ends in a unit. */
const MENTIONS_A_PERIOD = new RegExp(`(?:${UNITS})\\b`, 'i')

/**
 * Copy that types a count of years for a fact other than the analysis caps. Keyed by file and phrase;
 * shrink-only: an entry whose phrase no longer holds a typed count in its file's copy fails the spec
 * (delete it, and lower PERIOD_COUNT_OTHER_FACTS_MAX in the same commit), and the table's length equals
 * PERIOD_COUNT_OTHER_FACTS_MAX, an equality and never a ceiling (D-040;
 * lessons/test-allowlist-caps-are-equalities.md). A new hit is written from the mirror; one that states
 * another fact is argued in here with the cap raised in the same reviewed diff.
 */
const PERIOD_COUNT_OTHER_FACTS_MAX = 6
const PERIOD_COUNT_OTHER_FACTS: Array<{ file: string; phrase: string; why: string }> = [
  // The privacy policy's retention periods: how long data is kept, not how far back analysis reaches.
  // A legal page (it imports LEGAL_DATES), off limits without the founder.
  { file: 'app/privacy/page.tsx', phrase: 'after 2 years of inactivity', why: 'account-data retention period' },
  { file: 'app/privacy/page.tsx', phrase: 'Retained for 1 year from the search date', why: 'search-history retention period' },
  { file: 'app/privacy/page.tsx', phrase: 'Retained for 1 year from submission date', why: 'contact-form retention period' },
  { file: 'app/privacy/page.tsx', phrase: 'Retained for 1 year from signup date', why: 'waitlist retention period' },
  { file: 'app/privacy/page.tsx', phrase: 'Retained for 7 years from transaction date', why: 'billing-record retention (tax law)' },
  { file: 'app/privacy/page.tsx', phrase: 'retained for 7 years for tax compliance', why: 'billing-record retention (tax law)' },
]

/** Rendered copy: its text, and for each UTF-16 unit of it the source position it was read from. */
type Rendered = { text: string; at: number[] }
/** What a part that is not a literal renders as: no digit, letter, space or hyphen, so no count spans it. */
const HOLE = '\ufffc'
const join = (parts: readonly Rendered[]): Rendered =>
  ({ text: parts.map((part) => part.text).join(''), at: parts.flatMap((part) => part.at) })
/** A literal's text read from `from` on (an escape shifts the positions after it by a character or two). */
const literal = (text: string, from: number, last: number): Rendered =>
  ({ text, at: Array.from({ length: text.length }, (_, index) => Math.min(from + index, last)) })

const ENTITIES: Record<string, string> = {
  nbsp: '\u00a0', ensp: '\u2002', emsp: '\u2003', thinsp: '\u2009', hyphen: '\u2010', dash: '\u2010',
  ndash: '\u2013', mdash: '\u2014', amp: '&', lt: '<', gt: '>', quot: '"', apos: "'",
}
const ENTITY = /^&(?:#(\d{1,7})|#x([\da-f]{1,6})|([a-z]+));/i
/** JSX text or a JSX attribute string as written from source position `from`, its entities decoded. */
function decoded(text: string, from: number): Rendered {
  const out: Rendered = { text: '', at: [] }
  for (let index = 0; index < text.length;) {
    const entity = text[index] === '&' ? ENTITY.exec(text.slice(index)) : null
    const point = entity && (entity[1] ? Number(entity[1]) : entity[2] ? parseInt(entity[2], 16) : null)
    const char = !entity ? undefined
      : point !== null ? (point <= 0x10ffff ? String.fromCodePoint(point) : undefined)
        : ENTITIES[entity[3].toLowerCase()]
    const value = char ?? text[index]
    out.text += value
    for (let unit = 0; unit < value.length; unit++) out.at.push(from + index)
    index += char === undefined ? 1 : entity![0].length
  }
  return out
}

/** A JSX text child as React renders it (Babel's rule): each line trimmed where it meets a line break,
 * blank lines dropped, the rest joined by one space; its entities decoded. */
function jsxText(node: ts.JsxText, sf: ts.SourceFile): Rendered {
  const lines: Array<{ from: number; text: string }> = []
  let from = node.pos
  sf.text.slice(node.pos, node.end).split(/(\r\n|\n|\r)/).forEach((part, index) => {
    if (index % 2 === 0) lines.push({ from, text: part })
    from += part.length
  })
  const lastWithText = lines.reduce((found, line, index) => (/[^ \t]/.test(line.text) ? index : found), 0)
  const parts: Rendered[] = []
  lines.forEach((line, index) => {
    let start = 0
    let end = line.text.length
    if (index > 0) while (start < end && /[ \t]/.test(line.text[start])) start++
    if (index < lines.length - 1) while (end > start && /[ \t]/.test(line.text[end - 1])) end--
    if (start === end) return
    parts.push(decoded(line.text.slice(start, end), line.from + start))
    if (index !== lastWithText) parts.push({ text: ' ', at: [line.from + end] })
  })
  return join(parts)
}

type Wrapper = ts.ParenthesizedExpression | ts.AsExpression | ts.SatisfiesExpression | ts.NonNullExpression | ts.TypeAssertion
const isWrapper = (node: ts.Node): node is Wrapper => ts.isParenthesizedExpression(node) || ts.isAsExpression(node)
  || ts.isSatisfiesExpression(node) || ts.isNonNullExpression(node) || ts.isTypeAssertionExpression(node)
const isConcat = (node: ts.Node): node is ts.BinaryExpression =>
  ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken

/** What a node renders as text: its literals and JSX read through, any other part a hole. */
function rendered(node: ts.Node, sf: ts.SourceFile): Rendered {
  if (isWrapper(node)) return rendered(node.expression, sf)
  if (ts.isStringLiteral(node) && ts.isJsxAttribute(node.parent)) return decoded(node.text, node.getStart(sf) + 1)
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateHead(node)
    || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) return literal(node.text, node.getStart(sf) + 1, node.end - 1)
  if (ts.isNumericLiteral(node)) return literal(node.text, node.getStart(sf), node.end - 1)
  if (ts.isTemplateExpression(node)) {
    return join([node.head, ...node.templateSpans.flatMap((span) => [span.expression, span.literal])].map((part) => rendered(part, sf)))
  }
  if (isConcat(node)) return join([rendered(node.left, sf), rendered(node.right, sf)])
  if (ts.isJsxElement(node) || ts.isJsxFragment(node)) return join(node.children.map((child) => rendered(child, sf)))
  if (ts.isJsxText(node)) return jsxText(node, sf)
  if (ts.isJsxExpression(node)) return node.expression ? rendered(node.expression, sf) : { text: '', at: [] }
  return { text: HOLE, at: [node.getStart(sf)] }
}

/** A node its parent renders as part of its own text: a `+` operand, a template's substitution, or a JSX
 * tree's child, bare or in braces, through any parentheses or casts. So each part of copy is read once. */
function renderedByParent(node: ts.Node): boolean {
  let parent = node.parent
  while (parent && isWrapper(parent)) parent = parent.parent
  if (!parent) return false
  if (isConcat(parent) || ts.isTemplateSpan(parent) || ts.isJsxElement(parent) || ts.isJsxFragment(parent)) return true
  return ts.isJsxExpression(parent) && (ts.isJsxElement(parent.parent) || ts.isJsxFragment(parent.parent))
}

/** Every piece of copy in one source: each string, template, `+` chain and JSX tree that no other renders. */
function copyTexts(sf: ts.SourceFile): Rendered[] {
  const out: Rendered[] = []
  const visit = (node: ts.Node) => {
    if ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateExpression(node)
      || isConcat(node) || ts.isJsxElement(node) || ts.isJsxFragment(node)) && !renderedByParent(node)) {
      out.push(rendered(node, sf))
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

/** Whether an occurrence of `phrase` in `text` spans the range [start, end). */
function covers(text: string, phrase: string, start: number, end: number): boolean {
  for (let at = text.indexOf(phrase); at >= 0 && at <= start; at = text.indexOf(phrase, at + 1)) {
    if (end <= at + phrase.length) return true
  }
  return false
}

/** Each typed count in one source's copy, as `file:line: context`, less those inside a phrase that
 * PERIOD_COUNT_OTHER_FACTS argues for the file; `argued` collects every entry that covers one. */
function typedPeriodCounts(source: string, rel: string, argued = new Set<number>()): string[] {
  if (!MENTIONS_A_PERIOD.test(source)) return []
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, rel.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const found: string[] = []
  for (const copy of copyTexts(sf)) {
    for (const match of copy.text.matchAll(new RegExp(TYPED_PERIOD_COUNT_SOURCE, 'gi'))) {
      const start = match.index
      const end = start + match[0].length
      const covering = PERIOD_COUNT_OTHER_FACTS.flatMap((entry, index) =>
        (entry.file === rel && covers(copy.text, entry.phrase, start, end) ? [index] : []))
      covering.forEach((index) => argued.add(index))
      if (covering.length) continue
      const line = sf.getLineAndCharacterOfPosition(copy.at[start]).line + 1
      const context = copy.text.slice(Math.max(0, start - 40), end + 40).replaceAll(HOLE, '{…}').replace(/\s+/g, ' ').trim()
      found.push(`${rel}:${line}: ${context}`)
    }
  }
  return found
}

/**
 * The rule's forms, scored on every run (lessons/test-gates-must-be-as-wide-as-their-rule.md): a `flag`
 * source holds exactly one typed count, a `clean` look-alike none, and a `gap` breaks the rule in a form
 * the header leaves to review, so the scan reads none in it either. Each new form a review names joins here.
 */
const PLANTED_FORMS: Array<{ kind: 'flag' | 'clean' | 'gap'; form: string; source: string }> = [
  { kind: 'flag', form: 'a string', source: "export const copy = 'Compare up to 12 quarters'" },
  { kind: 'flag', form: 'JSX text', source: 'export const copy = <p>Up to 10 fiscal years</p>' },
  { kind: 'flag', form: 'JSX text over two lines', source: 'export const copy = (\n  <p>\n    Compare up to 10\n    fiscal years\n  </p>\n)' },
  { kind: 'flag', form: 'a JSX attribute string', source: 'export const copy = <Row description="Up to 10 fiscal years" />' },
  { kind: 'flag', form: "a template's static part", source: 'export const copy = `Up to ${n} companies and 10 years`' },
  { kind: 'flag', form: 'the count in emphasis markup', source: 'export const copy = <p>Up to <strong>10</strong> fiscal years</p>' },
  { kind: 'flag', form: 'a number word in markup, in a fragment', source: 'export const copy = <>Up to <em>ten</em> years</>' },
  { kind: 'flag', form: 'the qualifier in markup', source: 'export const copy = <p>Up to 10 <em>fiscal</em> years</p>' },
  { kind: 'flag', form: 'a hyphenated count in markup', source: 'export const copy = <p><span className="font-data">10</span>-year trends</p>' },
  { kind: 'flag', form: 'a numeric literal child', source: 'export const copy = <p>{10} fiscal years</p>' },
  { kind: 'flag', form: 'a string literal child', source: "export const copy = <p>Up to {'10'} fiscal years</p>" },
  { kind: 'flag', form: "a {' '} child between markup and the unit", source: "export const copy = <p>Up to <b>10</b>{' '}fiscal years</p>" },
  { kind: 'flag', form: 'a template child with a literal substitution', source: 'export const copy = <p>{`Up to ${10}`} fiscal years</p>' },
  { kind: 'flag', form: 'a parenthesized cast child', source: "export const copy = <p>{('10' as string)} years</p>" },
  { kind: 'flag', form: 'a + chain', source: "export const copy = 'Up to ' + 10 + ' fiscal years'" },
  { kind: 'flag', form: 'a template substitution of a literal', source: 'export const copy = `${12} quarters`' },
  { kind: 'flag', form: 'a no-break space entity', source: 'export const copy = <p>Up to 10&nbsp;years</p>' },
  { kind: 'flag', form: 'a numeric entity in an attribute', source: 'export const copy = <Row title="12&#160;quarters" />' },
  { kind: 'flag', form: 'a non-breaking hyphen', source: "export const copy = '10\\u2011year trends'" },
  { kind: 'flag', form: 'a count with a plus', source: 'export const copy = <p>10+ years of filings</p>' },
  { kind: 'flag', form: 'yrs', source: "export const copy = '10 yrs of history'" },
  { kind: 'flag', form: 'FYs', source: "export const copy = 'the last 10 FYs'" },
  { kind: 'flag', form: 'qtrs', source: "export const copy = 'the last 12 qtrs'" },
  { kind: 'flag', form: 'FQs', source: "export const copy = 'the last 12 FQs'" },
  { kind: 'flag', form: "a condition's literal branch", source: "export const copy = <p>{annual ? '10 fiscal years' : null}</p>" },
  { kind: 'flag', form: 'a tree behind &&', source: 'export const copy = <div>{open && <p>Up to 10 years</p>}</div>' },
  { kind: 'clean', form: 'the mirror in JSX', source: 'export const copy = <p>Up to {ANALYSIS_MAX_ANNUAL_PERIODS} fiscal years</p>' },
  { kind: 'clean', form: 'the mirror in a template', source: 'export const copy = `Unlimited Multi-Period Analysis: ${ANALYSIS_MAX_ANNUAL_PERIODS}-year trends`' },
  { kind: 'clean', form: 'the mirror in markup', source: 'export const copy = <p>Up to <strong>{ANALYSIS_MAX_QUARTERLY_PERIODS}</strong> quarters</p>' },
  { kind: 'clean', form: 'a live count', source: 'export const copy = <p>Showing {shown} of {total} quarters</p>' },
  { kind: 'clean', form: 'period labels', source: 'export const copy = <p>FY2025 results · Q3 2025 · Q1 FY 2025</p>' },
  { kind: 'clean', form: 'form names', source: "export const copy = '10-K and 10-Q filings'" },
  { kind: 'clean', form: 'units with no count', source: 'export const copy = <p>Fiscal year · year-over-year · quarterly deltas · yearly billing</p>' },
  { kind: 'clean', form: 'a comment', source: '// Up to 10 fiscal years\nexport const copy = null' },
  { kind: 'clean', form: 'a count and a unit in blocks on their own lines', source: 'export const copy = (\n  <ul>\n    <li>10</li>\n    <li>years</li>\n  </ul>\n)' },
  { kind: 'clean', form: 'a count of something else', source: "export const copy = '10 filings a year, $10 per year'" },
  { kind: 'gap', form: 'a number word past twelve', source: "export const copy = 'fifteen years of filings'" },
  { kind: 'gap', form: 'a decade', source: "export const copy = 'a decade of filings'" },
  { kind: 'gap', form: 'a dozen', source: "export const copy = 'a dozen quarters'" },
  { kind: 'gap', form: 'another word between count and unit', source: "export const copy = '10 calendar years, 10 or more years'" },
  { kind: 'gap', form: 'another unit', source: "export const copy = '10 annual periods'" },
  { kind: 'gap', form: 'finance shorthand', source: "export const copy = '10Y revenue trend'" },
  { kind: 'gap', form: 'a count held in a name', source: 'const N = 10\nexport const copy = <p>{N} fiscal years</p>' },
  { kind: 'gap', form: 'a count chosen by a condition', source: 'export const copy = <p>{annual ? 10 : 12} fiscal years</p>' },
]

describe('Multi-Period Analysis period caps move in lockstep with the backend', () => {
  it('mirrors ANALYSIS_MAX_ANNUAL_PERIODS and ANALYSIS_MAX_QUARTERLY_PERIODS', () => {
    expect(ANALYSIS_MAX_ANNUAL_PERIODS).toBe(settingDefault('ANALYSIS_MAX_ANNUAL_PERIODS'))
    expect(ANALYSIS_MAX_QUARTERLY_PERIODS).toBe(settingDefault('ANALYSIS_MAX_QUARTERLY_PERIODS'))
  })

  it('the pattern reads every way a period count is typed, and only those', () => {
    for (const typed of ['10 fiscal years', 'up to ten fiscal years', '12 quarters', 'twelve fiscal quarters',
      '10-year trends', '10-fiscal-year window', 'ten-year', '12-quarter view', '5 years', '1 year', '3 financial years',
      '10+ years', '10 yrs', '1 yr', '10 FYs', '12 qtrs', '12 FQs', '10\u00a0years', '10\u2011year trends']) {
      expect(TYPED_PERIOD_COUNT.test(typed), typed).toBe(true)
      expect(MENTIONS_A_PERIOD.test(typed), `prefilter keeps ${typed}`).toBe(true)
    }
    for (const prose of ['fiscal years', 'quarterly deltas', 'Fiscal year', 'year-over-year', '10-K and 10-Q',
      '-year trends, quarterly deltas', 'FY2025', 'Q3 2025', 'Q1 FY 2025', 'yearly billing', 'often years', 'canine years']) {
      expect(TYPED_PERIOD_COUNT.test(prose), prose).toBe(false)
    }
  })

  it('scores the planted forms: one typed count in each form it names, none in a look-alike or a named gap', () => {
    const misread = PLANTED_FORMS.flatMap(({ kind, form, source }) => {
      const hits = typedPeriodCounts(source, 'planted.tsx')
      return hits.length === (kind === 'flag' ? 1 : 0) ? [] : [`${kind} (${form}): ${JSON.stringify(hits)}`]
    })
    expect(misread).toEqual([])
    for (const kind of ['flag', 'clean', 'gap'] as const) expect(PLANTED_FORMS.some((form) => form.kind === kind), kind).toBe(true)
  })

  it('no copy types a count of years or quarters', () => {
    const offenders: string[] = []
    const argued = new Set<number>()
    let read = 0
    for (const root of SOURCE_ROOTS) {
      for (const file of walk(path.join(frontendDir, root))) {
        if (!/\.tsx?$/.test(file) || /\.(spec|test)\.tsx?$|\.d\.ts$/.test(file)) continue
        read++
        const rel = path.relative(frontendDir, file).split(path.sep).join('/')
        offenders.push(...typedPeriodCounts(readFileSync(file, 'utf8'), rel, argued))
      }
    }
    expect(read, 'the scan reads the source tree').toBeGreaterThan(100)
    expect(offenders, 'write the caps from ANALYSIS_MAX_ANNUAL_PERIODS / ANALYSIS_MAX_QUARTERLY_PERIODS in lib/planLimits').toEqual([])
    const stale = PERIOD_COUNT_OTHER_FACTS.filter((_, index) => !argued.has(index)).map((entry) => `${entry.file}: ${entry.phrase}`)
    expect(stale, 'PERIOD_COUNT_OTHER_FACTS is shrink-only: delete the entries whose phrase holds no typed count').toEqual([])
    expect(PERIOD_COUNT_OTHER_FACTS.length, 'PERIOD_COUNT_OTHER_FACTS_MAX equals the table: lower it with a deleted entry; write a new count from the mirror')
      .toBe(PERIOD_COUNT_OTHER_FACTS_MAX)
  })

  it('the scan reads the files that state the caps', () => {
    for (const rel of ['app/analysis/page.tsx', 'features/analysis/components/AnalysisPageClient.tsx', 'features/marketing/components/ProDepth.tsx']) {
      expect(readFileSync(path.join(frontendDir, rel), 'utf8'), `${rel} states the caps from the mirror`).toMatch(/ANALYSIS_MAX_ANNUAL_PERIODS[\s\S]*ANALYSIS_MAX_QUARTERLY_PERIODS/)
    }
    // The /pricing Pro card lists ANALYSIS_LINES.pricingPro, typed once in lib/planLimits.ts (D-040).
    expect(readFileSync(path.join(frontendDir, 'lib/planLimits.ts'), 'utf8'), 'the Pro card states the annual cap from the mirror')
      .toMatch(/pricingPro: \{ text: `[^`]*\$\{ANALYSIS_MAX_ANNUAL_PERIODS\}-year trends/)
  })
})
