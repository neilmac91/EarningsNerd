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
 * Multi-Period Analysis period caps (the /analysis metadata and lead, the landing's feature row). The
 * backend's Settings defaults (backend/app/config.py: ANALYSIS_MAX_ANNUAL_PERIODS,
 * ANALYSIS_MAX_QUARTERLY_PERIODS) are the truth the picker reads from the coverage response; copy that
 * renders before it takes the mirror in lib/planLimits.ts. So (1) the mirror equals the defaults, and
 * (2) no copy literal (a string, a template's static part, JSX text; comments are not copy) types a
 * count of fiscal years or quarters, in digits or words.
 */
const config = readFileSync(path.resolve(frontendDir, '../backend/app/config.py'), 'utf8')
const settingDefault = (name: string): number => {
  const match = config.match(new RegExp(`^\\s+${name}\\s*:\\s*int\\s*=\\s*(\\d+)`, 'm'))
  if (!match) throw new Error(`${name} not found in backend/app/config.py`)
  return Number(match[1])
}

const TYPED_PERIOD_COUNT = /\b(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+(?:(?:fiscal|financial)\s+years?|(?:fiscal\s+)?quarters?)\b/i

function copyTexts(file: string): Array<{ line: number; text: string }> {
  const sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
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

  it('no copy types a count of fiscal years or quarters', () => {
    const offenders: string[] = []
    for (const root of SOURCE_ROOTS) {
      for (const file of walk(path.join(frontendDir, root))) {
        if (!/\.tsx?$/.test(file) || /\.(spec|test)\.tsx?$|\.d\.ts$/.test(file)) continue
        for (const { line, text } of copyTexts(file)) {
          if (TYPED_PERIOD_COUNT.test(text)) offenders.push(`${path.relative(frontendDir, file)}:${line}: ${text.trim().slice(0, 100)}`)
        }
      }
    }
    expect(offenders, 'write the caps from ANALYSIS_MAX_ANNUAL_PERIODS / ANALYSIS_MAX_QUARTERLY_PERIODS in lib/planLimits').toEqual([])
  })

  it('the scan reads the files that state the caps', () => {
    for (const rel of ['app/analysis/page.tsx', 'features/analysis/components/AnalysisPageClient.tsx', 'features/marketing/components/ProDepth.tsx']) {
      expect(readFileSync(path.join(frontendDir, rel), 'utf8'), `${rel} states the caps from the mirror`).toMatch(/ANALYSIS_MAX_ANNUAL_PERIODS[\s\S]*ANALYSIS_MAX_QUARTERLY_PERIODS/)
    }
  })
})
