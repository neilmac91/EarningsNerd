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
 * TRIAL_DAYS: no copy says "7 days" or a trial of any other typed length, whether as a literal or as a
 * number spliced into JSX text, a template or a `+` chain (`{7}-day free trial`, `${7}-day`, a local
 * `const LEN = 7`); (4) every read of TRIAL_DAYS sits under a guard, where a guard is ENABLE_PRO_TRIAL
 * itself or an `&&` chain with a guard operand (directly, or through a const so derived in the same
 * file), never a negation, an `||`, a `??`, a ternary or a comparison, each of which can be true with
 * the flag off; and (5) TRIAL_DAYS is the value the flag's own documentation and the backend name for
 * the flip.
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

/** A gap for an expression whose value the file does not state: never a digit, never a word. */
const GAP = '\u0000'

/** The number constants a file declares (`const N = 7`, `as const` allowed), by name. */
function numberConsts(sf: ts.SourceFile): Map<string, string> {
  const out = new Map<string, string>()
  const visit = (node: ts.Node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      let init: ts.Expression = node.initializer
      while (ts.isAsExpression(init) || ts.isParenthesizedExpression(init)) init = init.expression
      if (ts.isNumericLiteral(init)) out.set(node.name.text, init.text)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

/** Copy as it renders when a number is spliced into it: a JSX element's children in order, a template,
    or a `+` chain with a string in it. A number literal, or a file's number const, reads as its digits;
    a string as its text; any other expression as a gap. */
function composedCopy(sf: ts.SourceFile): Array<{ node: ts.Node; text: string }> {
  const numbers = numberConsts(sf)
  const valueOf = (expr: ts.Expression | undefined): string => {
    while (expr && (ts.isParenthesizedExpression(expr) || ts.isAsExpression(expr))) expr = expr.expression
    if (!expr) return GAP
    if (ts.isNumericLiteral(expr)) return expr.text
    if (ts.isStringLiteralLike(expr)) return expr.text
    if (ts.isIdentifier(expr) && numbers.has(expr.text)) return numbers.get(expr.text)!
    return GAP
  }
  const plusOperands = (expr: ts.Expression): ts.Expression[] =>
    ts.isBinaryExpression(expr) && expr.operatorToken.kind === ts.SyntaxKind.PlusToken
      ? [...plusOperands(expr.left), ...plusOperands(expr.right)]
      : [expr]
  const out: Array<{ node: ts.Node; text: string }> = []
  const visit = (node: ts.Node) => {
    if ((ts.isJsxElement(node) || ts.isJsxFragment(node)) && node.children.some(ts.isJsxExpression)) {
      const text = node.children.map((child) => (ts.isJsxText(child) ? child.text : ts.isJsxExpression(child) ? valueOf(child.expression) : GAP)).join('')
      out.push({ node, text })
    }
    if (ts.isTemplateExpression(node)) {
      out.push({ node, text: node.head.text + node.templateSpans.map((span) => valueOf(span.expression) + span.literal.text).join('') })
    }
    if (
      ts.isBinaryExpression(node) &&
      node.operatorToken.kind === ts.SyntaxKind.PlusToken &&
      !(ts.isBinaryExpression(node.parent) && node.parent.operatorToken.kind === ts.SyntaxKind.PlusToken)
    ) {
      const operands = plusOperands(node)
      if (operands.some(ts.isStringLiteralLike)) out.push({ node, text: operands.map(valueOf).join('') })
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

/** Whether a piece of copy types a trial length: "7 days", or any "N-day" beside "trial" or "days free". */
const typesTrialLength = (text: string) =>
  new RegExp(`\\b${TRIAL_DAYS}[- ]days?\\b`, 'i').test(text) || (/\b\d+[- ]days?\b/i.test(text) && /\btrial\b|\bdays? free\b/i.test(text))

const parsed = new Map<string, ts.SourceFile>()
/** Each source file is parsed once for the clauses that walk the whole tree. */
const parse = (file: string) => {
  let sf = parsed.get(file)
  if (!sf) {
    sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
    parsed.set(file, sf)
  }
  return sf
}
const sourceFiles = () =>
  SOURCE_ROOTS.flatMap((root) => walk(path.join(frontendDir, root))).filter((file) => /\.tsx?$/.test(file) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(file))

/** "7 days" that is not the trial: each with the file and the literal it reads. */
const NOT_THE_TRIAL: Record<string, string> = {
  'app/admin/invites/page.tsx 7 days': "an invite link's lifetime option",
}

/** The guard names in a file: ENABLE_PRO_TRIAL, and every const whose initializer is a guard. */
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
      if (!guards.has(name) && isGuard(init, guards)) {
        guards.add(name)
        grew = true
      }
    }
  }
  return guards
}

/** Whether an expression is true only while the flag is: a guard name itself, or an `&&` chain with a
    guard operand (parentheses allowed). A negation, `||`, `??`, a ternary or a comparison is not: each
    can be true with the flag off. */
function isGuard(expr: ts.Node, guards: Set<string>): boolean {
  if (ts.isParenthesizedExpression(expr)) return isGuard(expr.expression, guards)
  if (ts.isIdentifier(expr)) return guards.has(expr.text)
  if (ts.isBinaryExpression(expr) && expr.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken) {
    return isGuard(expr.left, guards) || isGuard(expr.right, guards)
  }
  return false
}

/** Whether a node renders only when a guard holds: inside `guard && …`, `guard ? … :`, or `if (guard) …`. */
function guarded(node: ts.Node, guards: Set<string>): boolean {
  for (let child = node, parent = node.parent; parent; child = parent, parent = parent.parent) {
    if (ts.isBinaryExpression(parent) && parent.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken && parent.right === child && isGuard(parent.left, guards)) return true
    if (ts.isConditionalExpression(parent) && parent.whenTrue === child && isGuard(parent.condition, guards)) return true
    if (ts.isIfStatement(parent) && parent.thenStatement === child && isGuard(parent.expression, guards)) return true
  }
  return false
}

/** The TRIAL_DAYS reads in a file that render outside a guard (line numbers). */
function unguardedTrialReads(sf: ts.SourceFile): { reads: number[]; unguarded: number[] } {
  const guards = guardNames(sf)
  const reads: number[] = []
  const unguarded: number[] = []
  const visit = (node: ts.Node) => {
    if (ts.isIdentifier(node) && node.text === 'TRIAL_DAYS' && !ts.isImportSpecifier(node.parent)) {
      const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
      reads.push(line)
      if (!guarded(node, guards)) unguarded.push(line)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return { reads, unguarded }
}

/** The copy in a file that types a trial length: literals and composed copy, with their lines. */
function typedTrialCopy(sf: ts.SourceFile): Array<{ line: number; text: string }> {
  return [...copyLiterals(sf), ...composedCopy(sf)]
    .filter(({ text }) => typesTrialLength(text))
    .map(({ node, text }) => ({ line: sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1, text: text.trim() }))
}

const probe = (code: string) => ts.createSourceFile('probe.tsx', code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)

describe('the Pro trial length is stated only through TRIAL_DAYS, and only while the trial ships', () => {
  it('no copy literal types the trial length', () => {
    const offenders: string[] = []
    const allowed = new Set<string>()
    for (const file of sourceFiles()) {
      const rel = path.relative(frontendDir, file)
      if (rel === path.join('lib', 'planLimits.ts')) continue
      for (const { line, text } of typedTrialCopy(parse(file))) {
        const key = `${rel} ${text}`
        if (key in NOT_THE_TRIAL) {
          allowed.add(key)
          continue
        }
        offenders.push(`${rel}:${line} ${text.replace(new RegExp(GAP, 'g'), '{…}').slice(0, 80)}`)
      }
    }
    expect(offenders, 'write the trial length as {TRIAL_DAYS} from lib/planLimits').toEqual([])
    expect(Object.keys(NOT_THE_TRIAL).filter((key) => !allowed.has(key)), 'no longer in the code: delete it from NOT_THE_TRIAL').toEqual([])
    // Parses every source file (about 2s idle): the default 5s is too tight on a loaded runner.
  }, 30_000)

  it('every read of TRIAL_DAYS renders only under ENABLE_PRO_TRIAL', () => {
    const reads: string[] = []
    const unguarded: string[] = []
    for (const file of sourceFiles()) {
      const rel = path.relative(frontendDir, file)
      if (rel === path.join('lib', 'planLimits.ts')) continue
      const found = unguardedTrialReads(parse(file))
      reads.push(...found.reads.map((line) => `${rel}:${line}`))
      unguarded.push(...found.unguarded.map((line) => `${rel}:${line}`))
    }
    // Anti-vacuity: the signup gate, the paywall card and both pricing surfaces state the length.
    expect(reads.length, 'TRIAL_DAYS reads found').toBeGreaterThanOrEqual(4)
    expect(unguarded, 'state the trial only inside ENABLE_PRO_TRIAL (or a const derived from it)').toEqual([])
  }, 30_000)

  it('the two clauses see a spliced number and refuse a guard that can hold with the flag off', () => {
    const typed = (code: string) => typedTrialCopy(probe(code)).length > 0
    expect(typed('const a = <p>Start a {7}-day free trial</p>'), 'a number in JSX text').toBe(true)
    expect(typed('const a = `Start ${7}-day free trial`'), 'a number in a template').toBe(true)
    expect(typed('const LEN = 7\nconst a = <p>First {LEN} days free</p>'), 'a local number const').toBe(true)
    expect(typed("const a = 'Start ' + 7 + '-day free trial'"), 'a + chain').toBe(true)
    expect(typed('const a = <p>Start a {TRIAL_DAYS}-day free trial</p>'), 'TRIAL_DAYS itself').toBe(false)
    expect(typed('const a = <p>Free accounts get {FREE_SUMMARY_LIMIT} summaries</p>'), 'another limit').toBe(false)

    const loose = (code: string) => unguardedTrialReads(probe(`${code}`)).unguarded.length
    expect(loose('const a = ENABLE_PRO_TRIAL && <p>{TRIAL_DAYS}</p>'), 'the flag').toBe(0)
    expect(loose('const show = ENABLE_PRO_TRIAL && monthly && !beta\nconst a = show && <p>{TRIAL_DAYS}</p>'), 'a derived && const').toBe(0)
    expect(loose('const a = (ready && ENABLE_PRO_TRIAL) ? <p>{TRIAL_DAYS}</p> : null'), 'an && condition').toBe(0)
    expect(loose('const show = ENABLE_PRO_TRIAL || beta\nconst a = show && <p>{TRIAL_DAYS}</p>'), 'a derived ||').toBe(1)
    expect(loose('const a = (ENABLE_PRO_TRIAL || beta) && <p>{TRIAL_DAYS}</p>'), 'an inline ||').toBe(1)
    expect(loose('const a = !(ENABLE_PRO_TRIAL) && <p>{TRIAL_DAYS}</p>'), 'a parenthesised negation').toBe(1)
    expect(loose('const a = ENABLE_PRO_TRIAL === false && <p>{TRIAL_DAYS}</p>'), 'a comparison').toBe(1)
    expect(loose('const show = ENABLE_PRO_TRIAL ? false : true\nconst a = show && <p>{TRIAL_DAYS}</p>'), 'an inverted ternary').toBe(1)
    expect(loose('const a = (ENABLE_PRO_TRIAL ?? beta) && <p>{TRIAL_DAYS}</p>'), 'a ??').toBe(1)
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
