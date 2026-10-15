import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import {
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

  // Pro's Copilot questions are capped (COPILOT_MONTHLY_QUESTION_CAP, a fair-use 429 past it), so no copy
  // offers "unlimited" questions (ASK-03, D-034). The cap is read from the usage response (qa_limit), never
  // typed. The Copilot's own surfaces carry no "unlimited" at all; everywhere else under the source roots
  // (pricing, marketing, the upgrade surfaces, any page) "unlimited" stays off a question noun within one
  // literal (a string, JSX text, a template with its parts joined; a markdown file's paragraph) or one element's
  // inline children read together (`<li>Unlimited <strong>Ask this Filing</strong> questions</li>`), its
  // whitespace collapsed so a wrapped line reads as one. "Unlimited" heads a list read to the sentence end, and
  // an item of it that names a question, answer, Ask this Filing, Copilot or Q&A noun and no count of its own
  // fails ("unlimited follow-up questions", "Unlimited, cited answers", "unlimited 10-K and 10-Q analysis,
  // exports, and filing Q&A"), while an item with its own count passes ("Unlimited summaries and 1,000
  // questions a month"); so does such a noun up to 30 characters before "unlimited" in the same sentence
  // ("Answers: unlimited on Pro"). A claim split across separate literals (two array items, a template's
  // substitution) is out of its reach and review-checked (whether Pro summaries stay "unlimited" is a founder
  // decision, pub/F05, and F41 keeps it on the plan cards, so that clause is not here).
  const COPILOT_DIR = path.join('features', 'filings', 'components', 'copilot')
  const NOUN = String.raw`(?:questions?|answers?|copilot|ask this filing|q&a)(?![\w&])`
  const NOUN_THEN_UNLIMITED = new RegExp(String.raw`\b${NOUN}[^.]{0,30}\bunlimited\b`, 'i')
  const NAMES_NOUN = new RegExp(String.raw`\b${NOUN}`, 'i')
  /** True when a text offers unlimited questions: a question noun shortly before "unlimited", or a list "unlimited" heads,
      read to the end of its sentence, with an item that names a question noun and carries no count of its own. */
  const promisesUnlimited = (text: string) =>
    NOUN_THEN_UNLIMITED.test(text) ||
    text.split(/(?<=[.!?])\s+/).some((sentence) => {
      const at = sentence.search(/\bunlimited\b/i)
      if (at < 0) return false
      const items = sentence.slice(at + 'unlimited'.length).split(/[,;]|\b(?:and|or|plus|with)\b/i)
      return items.some((item) => NAMES_NOUN.test(item) && !/\d/.test(item))
    })

  interface Held {
    line: number
    text: string
    /** An element's run: the texts of its children, each read alone first, so the run reports only what no child says. */
    parts?: string[]
  }

  /** Each literal a file holds, whitespace collapsed, with the line it starts on: a string, JSX text or a template
      with its parts joined (a markdown file's paragraph), so neighbouring array items never join; and each element's
      inline children read together, JSX text, a nested element's run and a string an expression holds (any other
      expression reads as a space). */
  function literals(file: string, source: string): Held[] {
    if (/\.mdx?$/.test(file)) {
      let line = 1
      return source.split(/\n\s*\n/).map((paragraph) => {
        const at = { line, text: paragraph.replace(/\s+/g, ' ') }
        line += paragraph.split('\n').length + 1
        return at
      })
    }
    const kind = file.endsWith('.tsx') ? ts.ScriptKind.TSX : file.endsWith('.jsx') ? ts.ScriptKind.JSX : file.endsWith('.js') ? ts.ScriptKind.JS : ts.ScriptKind.TS
    const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, kind)
    const out: Held[] = []
    const lineOf = (n: ts.Node) => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1
    const childText = (child: ts.JsxChild): string => {
      if (ts.isJsxText(child)) return child.text
      if (ts.isJsxElement(child)) return child.children.map(childText).join('')
      if (ts.isJsxExpression(child) && child.expression) {
        let value = child.expression
        while (ts.isParenthesizedExpression(value) || ts.isAsExpression(value)) value = value.expression
        if (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value)) return value.text
      }
      return ' '
    }
    const visit = (n: ts.Node) => {
      let text: string | null = null
      if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n) || ts.isJsxText(n)) text = n.text
      else if (ts.isTemplateExpression(n)) text = [n.head.text, ...n.templateSpans.map((span) => span.literal.text)].join(' ')
      if (text !== null) out.push({ line: lineOf(n), text: text.replace(/\s+/g, ' ') })
      if (ts.isJsxElement(n) && n.children.length > 1) {
        const parts = n.children.map((child) => childText(child).replace(/\s+/g, ' '))
        out.push({ line: lineOf(n), text: parts.join('').replace(/\s+/g, ' '), parts })
      }
      ts.forEachChild(n, visit)
    }
    visit(sf)
    return out
  }

  /** The held texts that offer unlimited questions: a literal, or an element's run that no child of it says alone. */
  const offers = (held: Held[]) => held.filter(({ text, parts }) => promisesUnlimited(text) && !(parts ?? []).some(promisesUnlimited))

  // Every source file under the roots, read and parsed once, before any one test's timeout starts.
  const SCANNED = SOURCE_ROOTS.flatMap((root) => walk(path.join(frontendDir, root))).map((file) => {
    const source = readFileSync(file, 'utf8')
    return { file, rel: path.relative(frontendDir, file), source, literals: literals(file, source) }
  })

  it('no Copilot or plan surface promises unlimited questions', () => {
    const offenders: string[] = []
    const scanned = new Set<string>()
    let copilotFiles = 0
    for (const { rel, source, literals: held } of SCANNED) {
      scanned.add(rel.split(path.sep).join('/'))
      if (rel.startsWith(COPILOT_DIR + path.sep)) {
        copilotFiles += 1
        source.split('\n').forEach((line, index) => {
          if (/\bunlimited\b/i.test(line)) offenders.push(`${rel}:${index + 1}: ${line.trim()}`)
        })
      } else {
        for (const { line, text } of offers(held)) offenders.push(`${rel}:${line}: ${text.trim()}`)
      }
    }
    // The scan reaches the plan surfaces outside the Copilot and subscription directories, not only those two.
    expect(copilotFiles, 'the scan reads the Copilot directory').toBeGreaterThan(10)
    for (const rel of ['app/pricing/page.tsx', 'app/pricing/layout.tsx', 'features/marketing/components/PricingSection.tsx', 'features/subscriptions/components/UpgradeModal.tsx']) {
      expect(scanned.has(rel), rel).toBe(true)
    }
    expect(offenders, "say what the plan includes, from the usage response: `Pro includes ${usage.qa_limit} questions a month.`").toEqual([])
  })

  it('the question clause reads a literal or an element\'s run: modifiers, a comma, Q&A, answers, a list and a wrapped line (self-check)', () => {
    for (const claim of [
      'Pro includes unlimited follow-up questions.',
      'Unlimited filing Q&A with Pro',
      'Unlimited Ask this Filing questions',
      'Pro includes unlimited\n            questions a month.',
      'Ask this Filing: unlimited on Pro',
      // A comma, a third modifier, and an answer noun before "unlimited".
      'Unlimited, cited answers',
      'Pro includes unlimited plain-English follow-up filing questions.',
      'Answers are unlimited on Pro',
      // The forms the review of c30e4f6d planted, and the pricing metadata's two sentences as #1311 shipped them.
      'Answers: unlimited on Pro',
      'Unlimited summaries, filing Q&A and exports',
      'go Pro for unlimited 10-K and 10-Q analysis, exports, and filing Q&A.',
      'Unlimited AI summaries of SEC 10-K and 10-Q filings, multi-period analysis, filing Q&A, alerts, and exports.',
    ]) {
      expect(promisesUnlimited(literals('claim.ts', JSON.stringify(claim))[0].text), claim).toBe(true)
    }
    for (const allowed of [
      'Unlimited summaries', 'Pro includes 1,000 questions a month.', 'Unlimited Multi-Period Analysis', 'Watchlists are unlimited on both plans.',
      // An item with its own count, and the metadata as it now reads: filing Q&A in a sentence "unlimited" does not head.
      'Unlimited summaries and 1,000 questions a month.',
      'EarningsNerd plans: free AI summaries of SEC filings every month, or go Pro for unlimited 10-K and 10-Q analysis and exports. Pro also includes filing Q&A.',
    ]) {
      expect(promisesUnlimited(allowed), allowed).toBe(false)
    }
    // Neighbouring array items are separate literals: "Unlimited watchlist" beside the questions line is no claim. An
    // element's run reads as one text, reported once, at the innermost element no child of which says it alone.
    const planted = literals('planted.tsx', [
      'const PRO = [',
      "  'Ask this Filing questions, 1,000 a month',",
      "  'Unlimited watchlist',",
      "  `Unlimited ${'follow-up'} questions`,",
      ']',
      'export const L = () => <ul><li>Unlimited <strong>Ask this Filing</strong> questions</li><li>Unlimited watchlist</li></ul>',
    ].join('\n'))
    expect(offers(planted).map(({ line, text }) => `${line} ${text.trim()}`)).toEqual([
      '4 Unlimited questions',
      '6 Unlimited Ask this Filing questions',
    ])
  })
})
