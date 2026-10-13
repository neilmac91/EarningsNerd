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
  TRIAL_DAYS,
} from '@/lib/planLimits'

/**
 * Structural gate for free-tier plan copy (CLAUDE.md rules 4 and 12).
 *
 * The free summary and earnings-alert caps are defined once on the server
 * (backend/app/services/entitlements.py). Guest-facing copy cannot read the usage response, so
 * frontend/lib/planLimits.ts mirrors the two numbers — and this spec keeps the mirror honest:
 * (1) the mirrored values equal the backend constants; (2) no source file spells the caps out as
 * bare literals again ("5 summaries", "3 companies"), which is how the copy drifted before.
 *
 * The Pro trial's length is a claim of the same kind, with one difference: the backend's
 * PRO_TRIAL_DAYS defaults to 0 (backend/app/config.py), so the trial exists only while the UI flag
 * ENABLE_PRO_TRIAL and that setting are flipped together. So (3) the length is written only through
 * TRIAL_DAYS (no copy literal says "7 days" or a trial of any other typed length), (4) every read of
 * TRIAL_DAYS sits under ENABLE_PRO_TRIAL (directly, or through a const derived from it in the same
 * file), and (5) TRIAL_DAYS is the value the flag's own documentation and the backend name for the flip.
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

/** A copy literal: a string, a template's static parts, or JSX text. Comments are never read. */
function copyLiterals(sf: ts.SourceFile): Array<{ node: ts.Node; text: string }> {
  const out: Array<{ node: ts.Node; text: string }> = []
  const visit = (node: ts.Node) => {
    if (
      ts.isStringLiteral(node) ||
      ts.isNoSubstitutionTemplateLiteral(node) ||
      ts.isTemplateHead(node) ||
      ts.isTemplateMiddle(node) ||
      ts.isTemplateTail(node) ||
      ts.isJsxText(node)
    ) out.push({ node, text: node.text })
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

const parse = (file: string) =>
  ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
const sourceFiles = () =>
  SOURCE_ROOTS.flatMap((root) => walk(path.join(frontendDir, root))).filter((file) => /\.tsx?$/.test(file) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(file))

/** "7 days" that is not the trial: each with the file and the literal it reads. */
const NOT_THE_TRIAL: Record<string, string> = {
  'app/admin/invites/page.tsx 7 days': "an invite link's lifetime option",
}

/** The guard names in a file: ENABLE_PRO_TRIAL, and every const whose initializer reads a guard name. */
function guardNames(sf: ts.SourceFile): Set<string> {
  const guards = new Set(['ENABLE_PRO_TRIAL'])
  const decls: Array<[string, ts.Expression]> = []
  const visit = (node: ts.Node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) decls.push([node.name.text, node.initializer])
    ts.forEachChild(node, visit)
  }
  visit(sf)
  for (let grew = true; grew; ) {
    grew = false
    for (const [name, init] of decls) {
      if (!guards.has(name) && readsGuard(init, guards)) {
        guards.add(name)
        grew = true
      }
    }
  }
  return guards
}

/** Whether an expression reads a guard name, not negated. */
function readsGuard(expr: ts.Node, guards: Set<string>): boolean {
  let reads = false
  const visit = (node: ts.Node) => {
    if (ts.isIdentifier(node) && guards.has(node.text)) {
      const parent = node.parent
      const negated = ts.isPrefixUnaryExpression(parent) && parent.operator === ts.SyntaxKind.ExclamationToken
      if (!negated && !(ts.isPropertyAccessExpression(parent) && parent.name === node)) reads = true
    }
    ts.forEachChild(node, visit)
  }
  visit(expr)
  return reads
}

/** Whether a node renders only when a guard holds: inside `guard && …`, `guard ? … :`, or `if (guard) …`. */
function guarded(node: ts.Node, guards: Set<string>): boolean {
  for (let child = node, parent = node.parent; parent; child = parent, parent = parent.parent) {
    if (ts.isBinaryExpression(parent) && parent.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken && parent.right === child && readsGuard(parent.left, guards)) return true
    if (ts.isConditionalExpression(parent) && parent.whenTrue === child && readsGuard(parent.condition, guards)) return true
    if (ts.isIfStatement(parent) && parent.thenStatement === child && readsGuard(parent.expression, guards)) return true
  }
  return false
}

describe('the Pro trial length is stated only through TRIAL_DAYS, and only while the trial ships', () => {
  it('no copy literal types the trial length', () => {
    const offenders: string[] = []
    const allowed = new Set<string>()
    for (const file of sourceFiles()) {
      const rel = path.relative(frontendDir, file)
      if (rel === path.join('lib', 'planLimits.ts')) continue
      const sf = parse(file)
      for (const { node, text } of copyLiterals(sf)) {
        const typed = new RegExp(`\\b${TRIAL_DAYS}[- ]days?\\b`, 'i').test(text) || (/\b\d+[- ]days?\b/i.test(text) && /\btrial\b|\bdays? free\b/i.test(text))
        if (!typed) continue
        const key = `${rel} ${text.trim()}`
        if (key in NOT_THE_TRIAL) {
          allowed.add(key)
          continue
        }
        offenders.push(`${rel}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1} ${text.trim().slice(0, 80)}`)
      }
    }
    expect(offenders, 'write the trial length as {TRIAL_DAYS} from lib/planLimits').toEqual([])
    expect(Object.keys(NOT_THE_TRIAL).filter((key) => !allowed.has(key)), 'no longer in the code: delete it from NOT_THE_TRIAL').toEqual([])
  })

  it('every read of TRIAL_DAYS renders only under ENABLE_PRO_TRIAL', () => {
    const reads: string[] = []
    const unguarded: string[] = []
    for (const file of sourceFiles()) {
      const rel = path.relative(frontendDir, file)
      if (rel === path.join('lib', 'planLimits.ts')) continue
      const sf = parse(file)
      const guards = guardNames(sf)
      const visit = (node: ts.Node) => {
        if (ts.isIdentifier(node) && node.text === 'TRIAL_DAYS' && !ts.isImportSpecifier(node.parent)) {
          const where = `${rel}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1}`
          reads.push(where)
          if (!guarded(node, guards)) unguarded.push(where)
        }
        ts.forEachChild(node, visit)
      }
      visit(sf)
    }
    // Anti-vacuity: the signup gate, the paywall card and both pricing surfaces state the length.
    expect(reads.length, 'TRIAL_DAYS reads found').toBeGreaterThanOrEqual(4)
    expect(unguarded, 'state the trial only inside ENABLE_PRO_TRIAL (or a const derived from it)').toEqual([])
  })

  it('TRIAL_DAYS is the length the trial flips to, in the flag and in the backend', () => {
    const flags = readFileSync(path.join(frontendDir, 'lib/featureFlags.ts'), 'utf8')
    const config = readFileSync(path.resolve(frontendDir, '../backend/app/config.py'), 'utf8')
    expect(flags).toContain(`PRO_TRIAL_DAYS=${TRIAL_DAYS}`)
    expect(config).toContain(`PRO_TRIAL_DAYS=${TRIAL_DAYS}`)
    const bound = config.match(/PRO_TRIAL_DAYS: int = Field\(default=(\d+), ge=0, le=(\d+)\)/)
    expect(bound, 'PRO_TRIAL_DAYS field in backend/app/config.py').not.toBeNull()
    // The backend ships the trial off, which is why every read above is flag-guarded.
    expect(Number(bound![1])).toBe(0)
    expect(TRIAL_DAYS).toBeLessThanOrEqual(Number(bound![2]))
  })
})
