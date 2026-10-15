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
 * (2) no copy literal (a string, a template's static part, JSX text; comments are not copy) types a
 * count of years or quarters, in digits or words, spaced or hyphenated ("10 fiscal years", "10-year",
 * "twelve quarters"), outside the few that state a different fact (PERIOD_COUNT_OTHER_FACTS).
 */
const config = readFileSync(path.resolve(frontendDir, '../backend/app/config.py'), 'utf8')
const settingDefault = (name: string): number => {
  const match = config.match(new RegExp(`^\\s+${name}\\s*:\\s*int\\s*=\\s*(\\d+)`, 'm'))
  if (!match) throw new Error(`${name} not found in backend/app/config.py`)
  return Number(match[1])
}

/** A digit or a number word, a hyphen or a space, an optional "fiscal" or "financial", then year or quarter. */
const TYPED_PERIOD_COUNT = /\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)[-\s]+(?:(?:fiscal|financial)[-\s]+)?(?:years?|quarters?)\b/i
/** Cheap raw-text prefilter: a file with no "year" or "quarter" anywhere has no copy the scan can flag,
 * so it skips the parse. Every TYPED_PERIOD_COUNT hit contains one of the two words. */
const MENTIONS_A_PERIOD = /years?\b|quarters?\b/i

/**
 * Copy that types a count of years for a fact other than the analysis caps. Keyed by file and phrase;
 * shrink-only: an entry whose phrase no longer appears in a flagged literal of its file fails the spec
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

function copyTexts(file: string): Array<{ line: number; text: string }> {
  const source = readFileSync(file, 'utf8')
  if (!MENTIONS_A_PERIOD.test(source)) return []
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const out: Array<{ line: number; text: string }> = []
  const visit = (node: ts.Node) => {
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateHead(node)
      || ts.isTemplateMiddle(node) || ts.isTemplateTail(node) || ts.isJsxText(node)) {
      out.push({ line: sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1, text: node.text })
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

describe('Multi-Period Analysis period caps move in lockstep with the backend', () => {
  it('mirrors ANALYSIS_MAX_ANNUAL_PERIODS and ANALYSIS_MAX_QUARTERLY_PERIODS', () => {
    expect(ANALYSIS_MAX_ANNUAL_PERIODS).toBe(settingDefault('ANALYSIS_MAX_ANNUAL_PERIODS'))
    expect(ANALYSIS_MAX_QUARTERLY_PERIODS).toBe(settingDefault('ANALYSIS_MAX_QUARTERLY_PERIODS'))
  })

  it('the pattern reads every way a period count is typed, and only those', () => {
    for (const typed of ['10 fiscal years', 'up to ten fiscal years', '12 quarters', 'twelve fiscal quarters',
      '10-year trends', '10-fiscal-year window', 'ten-year', '12-quarter view', '5 years', '1 year', '3 financial years']) {
      expect(TYPED_PERIOD_COUNT.test(typed), typed).toBe(true)
      expect(MENTIONS_A_PERIOD.test(typed), `prefilter keeps ${typed}`).toBe(true)
    }
    for (const prose of ['fiscal years', 'quarterly deltas', 'Fiscal year', 'year-over-year', '10-K and 10-Q',
      '-year trends, quarterly deltas', 'FY2025', 'Q3 2025', 'yearly billing']) {
      expect(TYPED_PERIOD_COUNT.test(prose), prose).toBe(false)
    }
  })

  it('no copy types a count of years or quarters', () => {
    const offenders: string[] = []
    const seen = new Set<number>()
    for (const root of SOURCE_ROOTS) {
      for (const file of walk(path.join(frontendDir, root))) {
        if (!/\.tsx?$/.test(file) || /\.(spec|test)\.tsx?$|\.d\.ts$/.test(file)) continue
        const rel = path.relative(frontendDir, file).split(path.sep).join('/')
        for (const { line, text } of copyTexts(file)) {
          if (!TYPED_PERIOD_COUNT.test(text)) continue
          // An argued phrase is taken out of the literal; whatever count is left still has to go.
          let rest = text
          PERIOD_COUNT_OTHER_FACTS.forEach((entry, index) => {
            if (entry.file === rel && rest.includes(entry.phrase)) {
              seen.add(index)
              rest = rest.replace(entry.phrase, '')
            }
          })
          if (TYPED_PERIOD_COUNT.test(rest)) offenders.push(`${rel}:${line}: ${text.trim().slice(0, 100)}`)
        }
      }
    }
    expect(offenders, 'write the caps from ANALYSIS_MAX_ANNUAL_PERIODS / ANALYSIS_MAX_QUARTERLY_PERIODS in lib/planLimits').toEqual([])
    const stale = PERIOD_COUNT_OTHER_FACTS.filter((_, index) => !seen.has(index)).map((entry) => `${entry.file}: ${entry.phrase}`)
    expect(stale, 'PERIOD_COUNT_OTHER_FACTS is shrink-only: delete the entries whose phrase is gone').toEqual([])
    expect(PERIOD_COUNT_OTHER_FACTS.length, 'PERIOD_COUNT_OTHER_FACTS_MAX equals the table: lower it with a deleted entry; write a new count from the mirror')
      .toBe(PERIOD_COUNT_OTHER_FACTS_MAX)
  })

  it('the scan reads the files that state the caps', () => {
    for (const rel of ['app/analysis/page.tsx', 'features/analysis/components/AnalysisPageClient.tsx', 'features/marketing/components/ProDepth.tsx']) {
      expect(readFileSync(path.join(frontendDir, rel), 'utf8'), `${rel} states the caps from the mirror`).toMatch(/ANALYSIS_MAX_ANNUAL_PERIODS[\s\S]*ANALYSIS_MAX_QUARTERLY_PERIODS/)
    }
    expect(readFileSync(path.join(frontendDir, 'app/pricing/page.tsx'), 'utf8'), 'the Pro card states the annual cap from the mirror')
      .toMatch(/\$\{ANALYSIS_MAX_ANNUAL_PERIODS\}-year trends/)
  })
})
