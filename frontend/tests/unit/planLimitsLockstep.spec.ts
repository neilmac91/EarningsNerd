import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { bindingResolver } from './astBindings'
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
 * TRIAL_DAYS: no copy says "7 days" or a trial of any other typed length (digits, a number word, days or
 * weeks), whether as a literal or as a value spliced into JSX, a template or a `+` chain, and a spliced
 * value the reader cannot resolve where a length would stand fails; (4) every read of TRIAL_DAYS, under
 * whatever binding the file gives it, sits under a guard, where a guard is ENABLE_PRO_TRIAL itself or an
 * `&&` chain with a guard operand (directly, or through a const so derived, resolved to the declaration
 * the name binds to), never a negation, an `||`, a `??`, a ternary's else, a comparison, a `let` or a
 * parameter, each of which can be true with the flag off; and (5) TRIAL_DAYS is the value the flag's own
 * documentation and the backend name for the flip. Clauses (3) and (4) read every .ts, .tsx, .js and .jsx
 * file under the cap walk's roots (an .md or .mdx file there is read as copy, line by line), one reader per
 * file (trialReader, below, says what it follows). Out of reach, review-checked: a length said another way
 * ("a week", "a fortnight"), TRIAL_DAYS re-exported under another name by another module, and a guard
 * applied by an early return (`if (!ENABLE_PRO_TRIAL) return null`), which fails closed.
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

/** A gap for an expression whose value the file does not state: never a digit, never a word. */
const GAP = '\u0000'

/**
 * One reader for both trial clauses, per file, following bindings rather than names:
 *  - TRIAL_DAYS is the import of `TRIAL_DAYS` from lib/planLimits under any local name, a namespace import's
 *    member (`P.TRIAL_DAYS`, `P['TRIAL_DAYS']`), one destructured from it, and a const holding any of those.
 *    A local declaration of the same name shadows it, as the language does.
 *  - A guard is ENABLE_PRO_TRIAL (imported, or a namespace member), an `&&` chain with a guard operand, or a
 *    `const` whose initializer is a guard, resolved to the declaration a name binds to: a same-named const in
 *    another function is that function's own, and a `let` or a parameter is never a guard (it can be
 *    reassigned, or holds what a caller hands it).
 *  - Copy: every string literal and template, every `+` chain with a string in it, and each JSX root's whole
 *    text, read in order through its child elements, its `{…}` children (both branches of a ternary, the
 *    right side of `&&`, `||` and `??`) and the JSX entities and spaces it is written with. A spliced value
 *    reads as what it holds: a number (arithmetic and `String(…)` / `.toString()` / `Number(…)` evaluated), a
 *    string, a same-file const, TRIAL_DAYS itself (never a typed length), or, for anything the reader cannot
 *    resolve, a gap that fails where a trial length would stand (`{PLAN.trialDays}-day free trial`).
 */
const TRIAL = '\u0001'
const SPACE_FORMS = /&nbsp;|&#0*160;|&#x0*a0;|[\u00a0\u2007\u2009\u202f]/gi
const HYPHEN_FORMS = /&#0*8209;|&#x0*2011;|[\u2010\u2011\u2012\u2013\u2212]/gi
const NUMBER_WORDS = 'one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|twenty|thirty'
/** A length: digits or a number word at a word's start, or a value the reader could not resolve. */
const LENGTH = `(?:\\b(?:\\d+|${NUMBER_WORDS})|${GAP})`

/** Whether a piece of copy types a trial length: the trial's own "7 days", or any length in days or weeks
    (digits, a number word, or a value the reader could not resolve) beside "trial" or "days free". A count
    of what is left ("{n} days left in your Pro trial", the billing countdown) is not a length. */
function typesTrialLength(raw: string): boolean {
  const text = raw.replace(SPACE_FORMS, ' ').replace(HYPHEN_FORMS, '-').replace(/\s+/g, ' ')
  if (new RegExp(`\\b${TRIAL_DAYS}[- ]days?\\b`, 'i').test(text)) return true
  const trialContext = /\btrial\b|\bdays? free\b|\bweeks? free\b/i.test(text)
  return trialContext && new RegExp(`${LENGTH}[- ](?:days?|weeks?)\\b(?! (?:left|remaining|ago)\\b)`, 'i').test(text)
}

const PLAN_LIMITS = /(?:^|\/)planLimits$/
const FEATURE_FLAGS = /(?:^|\/)featureFlags$/

interface TrialReader {
  /** Every read of TRIAL_DAYS in the file, with whether a guard holds over it. */
  reads: Array<{ line: number; guarded: boolean }>
  /** The copy the file writes that types a trial length. */
  typed: Array<{ line: number; text: string }>
}

const unwrapExpr = (e: ts.Expression): ts.Expression => {
  while (ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isNonNullExpression(e) || ts.isSatisfiesExpression(e) || ts.isTypeAssertionExpression(e)) e = e.expression
  return e
}
const isConst = (decl: ts.Node): decl is ts.VariableDeclaration =>
  ts.isVariableDeclaration(decl) && !!(decl.parent.flags & ts.NodeFlags.Const)
/** An identifier in a reading position (not a declaration's or a property's name). */
const isReference = (id: ts.Identifier): boolean => {
  const p = id.parent
  if (ts.isImportSpecifier(p) || ts.isImportClause(p) || ts.isNamespaceImport(p) || ts.isImportEqualsDeclaration(p)) return false
  if ((ts.isPropertyAccessExpression(p) || ts.isQualifiedName(p)) && p.name === id) return false
  if ((ts.isPropertyAssignment(p) || ts.isPropertyDeclaration(p) || ts.isMethodDeclaration(p) || ts.isPropertySignature(p)) && p.name === id) return false
  if ((ts.isVariableDeclaration(p) || ts.isParameter(p) || ts.isFunctionDeclaration(p) || ts.isClassDeclaration(p)) && p.name === id) return false
  if (ts.isBindingElement(p) && (p.name === id || p.propertyName === id)) return false
  if (ts.isJsxAttribute(p) || ts.isExportSpecifier(p)) return false
  return true
}

export function trialReader(sf: ts.SourceFile): TrialReader {
  const resolve = bindingResolver(sf)
  const trialImports = new Set<string>()
  const flagImports = new Set<string>()
  const planNamespaces = new Set<string>()
  const flagNamespaces = new Set<string>()
  for (const statement of sf.statements) {
    if (!ts.isImportDeclaration(statement) || !statement.importClause || !ts.isStringLiteral(statement.moduleSpecifier)) continue
    const from = statement.moduleSpecifier.text
    const bindings = statement.importClause.namedBindings
    if (bindings && ts.isNamespaceImport(bindings)) {
      if (PLAN_LIMITS.test(from)) planNamespaces.add(bindings.name.text)
      if (FEATURE_FLAGS.test(from)) flagNamespaces.add(bindings.name.text)
    }
    if (bindings && ts.isNamedImports(bindings)) {
      for (const spec of bindings.elements) {
        const imported = (spec.propertyName ?? spec.name).text
        if (imported === 'TRIAL_DAYS' && PLAN_LIMITS.test(from)) trialImports.add(spec.name.text)
        if (imported === 'ENABLE_PRO_TRIAL') flagImports.add(spec.name.text)
      }
    }
  }
  const line = (node: ts.Node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
  const memberOf = (e: ts.Expression, namespaces: Set<string>, name: string): boolean => {
    const x = unwrapExpr(e)
    if (ts.isPropertyAccessExpression(x)) return ts.isIdentifier(x.expression) && namespaces.has(x.expression.text) && x.name.text === name
    if (ts.isElementAccessExpression(x)) return ts.isIdentifier(x.expression) && namespaces.has(x.expression.text) && ts.isStringLiteralLike(x.argumentExpression) && x.argumentExpression.text === name
    return false
  }

  /** Whether an expression is TRIAL_DAYS itself: its import, a namespace member, or a const holding either. */
  const isTrial = (expr: ts.Expression, seen = new Set<ts.Node>()): boolean => {
    const e = unwrapExpr(expr)
    if (memberOf(e, planNamespaces, 'TRIAL_DAYS')) return true
    if (!ts.isIdentifier(e)) return false
    const binding = resolve(e)
    if (!binding) return trialImports.has(e.text)
    if (seen.has(binding.decl)) return false
    seen.add(binding.decl)
    // `const { TRIAL_DAYS: n } = P`: destructured from the namespace.
    if (ts.isBindingElement(binding.decl)) {
      const key = (binding.decl.propertyName ?? binding.decl.name).getText()
      const pattern = binding.decl.parent
      const holder = ts.isVariableDeclaration(pattern.parent) ? pattern.parent : undefined
      return key === 'TRIAL_DAYS' && !!holder?.initializer && isConst(holder) && ts.isIdentifier(unwrapExpr(holder.initializer)) &&
        planNamespaces.has((unwrapExpr(holder.initializer) as ts.Identifier).text)
    }
    return isConst(binding.decl) && !!binding.init && isTrial(binding.init, seen)
  }

  /** Whether an expression is true only while the flag is. */
  const isGuard = (expr: ts.Node, seen = new Set<ts.Node>()): boolean => {
    const e = ts.isExpression(expr) ? unwrapExpr(expr) : expr
    if (ts.isBinaryExpression(e) && e.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken) return isGuard(e.left, seen) || isGuard(e.right, seen)
    if (ts.isExpression(e) && memberOf(e, flagNamespaces, 'ENABLE_PRO_TRIAL')) return true
    if (!ts.isIdentifier(e)) return false
    const binding = resolve(e)
    if (!binding) return flagImports.has(e.text) || e.text === 'ENABLE_PRO_TRIAL'
    if (seen.has(binding.decl) || !isConst(binding.decl) || !binding.init) return false
    seen.add(binding.decl)
    return isGuard(binding.init, seen)
  }
  /** Whether a node renders only when a guard holds: inside `guard && …`, `guard ? … :`, or `if (guard) …`. */
  const guarded = (node: ts.Node): boolean => {
    for (let child = node, parent = node.parent; parent; child = parent, parent = parent.parent) {
      if (ts.isBinaryExpression(parent) && parent.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken && parent.right === child && isGuard(parent.left)) return true
      if (ts.isConditionalExpression(parent) && parent.whenTrue === child && isGuard(parent.condition)) return true
      if (ts.isIfStatement(parent) && parent.thenStatement === child && isGuard(parent.expression)) return true
    }
    return false
  }

  /** The number an expression holds, when the file says so (literals, arithmetic, consts, String/Number). */
  const numberOf = (expr: ts.Expression, seen = new Set<ts.Node>()): number | null => {
    const e = unwrapExpr(expr)
    if (ts.isNumericLiteral(e)) return Number(e.text)
    if (ts.isPrefixUnaryExpression(e) && (e.operator === ts.SyntaxKind.MinusToken || e.operator === ts.SyntaxKind.PlusToken)) {
      const n = numberOf(e.operand, seen)
      return n === null ? null : e.operator === ts.SyntaxKind.MinusToken ? -n : n
    }
    if (ts.isBinaryExpression(e)) {
      const [a, b] = [numberOf(e.left, seen), numberOf(e.right, seen)]
      if (a === null || b === null) return null
      switch (e.operatorToken.kind) {
        case ts.SyntaxKind.PlusToken: return a + b
        case ts.SyntaxKind.MinusToken: return a - b
        case ts.SyntaxKind.AsteriskToken: return a * b
        case ts.SyntaxKind.SlashToken: return a / b
        default: return null
      }
    }
    if (ts.isCallExpression(e) && ts.isIdentifier(e.expression) && /^(?:Number|parseInt|parseFloat)$/.test(e.expression.text) && e.arguments[0]) {
      const arg = unwrapExpr(e.arguments[0])
      return ts.isStringLiteralLike(arg) && arg.text.trim() !== '' && !Number.isNaN(Number(arg.text)) ? Number(arg.text) : numberOf(arg, seen)
    }
    if (ts.isIdentifier(e) && !isTrial(e)) {
      const binding = resolve(e)
      if (binding && isConst(binding.decl) && binding.init && !seen.has(binding.decl)) return numberOf(binding.init, new Set([...seen, binding.decl]))
    }
    return null
  }

  const MAX_READINGS = 16
  const product = (parts: string[][]): string[] => {
    let out = ['']
    for (const options of parts) {
      out = out.flatMap((head) => options.map((option) => head + option))
      if (out.length > MAX_READINGS) out = out.slice(0, MAX_READINGS)
    }
    return out
  }
  /** What a spliced expression renders as, one string per reading (a ternary has two). */
  const valuesOf = (expr: ts.Expression, seen = new Set<ts.Node>()): string[] => {
    const e = unwrapExpr(expr)
    if (isTrial(e)) return [TRIAL]
    const n = numberOf(e)
    if (n !== null) return [String(n)]
    if (ts.isStringLiteralLike(e)) return [e.text]
    if (e.kind === ts.SyntaxKind.NullKeyword || e.kind === ts.SyntaxKind.TrueKeyword || e.kind === ts.SyntaxKind.FalseKeyword) return ['']
    if (ts.isTemplateExpression(e)) return product([[e.head.text], ...e.templateSpans.flatMap((span) => [valuesOf(span.expression, seen), [span.literal.text]])])
    if (ts.isConditionalExpression(e)) return [...valuesOf(e.whenTrue, seen), ...valuesOf(e.whenFalse, seen)]
    if (ts.isBinaryExpression(e)) {
      const op = e.operatorToken.kind
      if (op === ts.SyntaxKind.AmpersandAmpersandToken) return [...valuesOf(e.right, seen), '']
      if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken) return [...valuesOf(e.left, seen), ...valuesOf(e.right, seen)]
      if (op === ts.SyntaxKind.PlusToken) return product([valuesOf(e.left, seen), valuesOf(e.right, seen)])
      return [GAP]
    }
    if (ts.isJsxElement(e) || ts.isJsxFragment(e) || ts.isJsxSelfClosingElement(e)) return jsxText(e, seen)
    if (ts.isCallExpression(e)) {
      const callee = unwrapExpr(e.expression)
      if (ts.isIdentifier(callee) && callee.text === 'String' && e.arguments[0]) return valuesOf(e.arguments[0], seen)
      if (ts.isPropertyAccessExpression(callee) && /^(?:toString|toLocaleString|trim)$/.test(callee.name.text)) return valuesOf(callee.expression, seen)
      return [GAP]
    }
    if (ts.isIdentifier(e)) {
      if (e.text === 'undefined') return ['']
      const binding = resolve(e)
      if (binding && isConst(binding.decl) && binding.init && !seen.has(binding.decl)) return valuesOf(binding.init, new Set([...seen, binding.decl]))
    }
    return [GAP]
  }
  /** A JSX element's whole text as it renders, its children in order, one string per reading. */
  const jsxText = (node: ts.JsxElement | ts.JsxFragment | ts.JsxSelfClosingElement, seen: Set<ts.Node>): string[] => {
    if (ts.isJsxSelfClosingElement(node)) return ['']
    return product(node.children.map((child) => {
      if (ts.isJsxText(child)) return [child.text]
      if (ts.isJsxExpression(child)) return child.expression ? valuesOf(child.expression, seen) : ['']
      return jsxText(child, seen)
    }))
  }
  /** A JSX element or fragment that is not inside another one's children: its text is read whole. */
  const isJsxRoot = (node: ts.Node): boolean => {
    for (let p = node.parent; p; p = p.parent) {
      if (ts.isJsxElement(p) || ts.isJsxFragment(p)) return false
      if (ts.isJsxAttribute(p) || ts.isFunctionLike(p) || ts.isStatement(p)) return true
    }
    return true
  }

  const reads: TrialReader['reads'] = []
  const copy: Array<{ node: ts.Node; text: string }> = []
  const visit = (node: ts.Node) => {
    if (ts.isIdentifier(node) && isReference(node) && isTrial(node)) {
      // A const that only renames TRIAL_DAYS is not a render of it: its own reads are checked instead.
      const holder = node.parent
      const alias = ts.isVariableDeclaration(holder) && holder.initializer === node && isConst(holder)
      if (!alias) reads.push({ line: line(node), guarded: guarded(node) })
    }
    if ((ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node)) && memberOf(node, planNamespaces, 'TRIAL_DAYS')) {
      reads.push({ line: line(node), guarded: guarded(node) })
    }
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) copy.push({ node, text: node.text })
    if (ts.isTemplateExpression(node)) for (const text of valuesOf(node)) copy.push({ node, text })
    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken &&
      !(ts.isBinaryExpression(node.parent) && node.parent.operatorToken.kind === ts.SyntaxKind.PlusToken)) {
      for (const text of valuesOf(node)) copy.push({ node, text })
    }
    if ((ts.isJsxElement(node) || ts.isJsxFragment(node)) && isJsxRoot(node)) for (const text of jsxText(node, new Set())) copy.push({ node, text })
    ts.forEachChild(node, visit)
  }
  visit(sf)
  const typed = copy
    .filter(({ text }) => typesTrialLength(text))
    .map(({ node, text }) => ({ line: line(node), text: text.replace(new RegExp(GAP, 'g'), '{…}').replace(new RegExp(TRIAL, 'g'), '{TRIAL_DAYS}').trim() }))
  // One line per piece of copy: a root and a literal inside it can type the same length.
  const unique = new Map(typed.map((t) => [`${t.line} ${t.text}`, t]))
  return { reads, typed: [...unique.values()] }
}

const parsed = new Map<string, ts.SourceFile>()
/** Each source file is parsed once for the clauses that walk the whole tree. */
const parse = (file: string) => {
  let sf = parsed.get(file)
  if (!sf) {
    const kind = /\.tsx$/.test(file) ? ts.ScriptKind.TSX : /\.jsx$/.test(file) ? ts.ScriptKind.JSX : /\.m?js$/.test(file) ? ts.ScriptKind.JS : ts.ScriptKind.TS
    sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, kind)
    parsed.set(file, sf)
  }
  return sf
}
const readers = new Map<string, TrialReader>()
const readerOf = (file: string) => {
  let reader = readers.get(file)
  if (!reader) readers.set(file, (reader = trialReader(parse(file))))
  return reader
}
/** The code the trial clauses read: the cap walk's files, its .ts/.tsx/.js/.jsx ones parsed; .md and .mdx are read as copy. */
const sourceFiles = () =>
  SOURCE_ROOTS.flatMap((root) => walk(path.join(frontendDir, root))).filter((file) => !/\.(spec|test)\.[jt]sx?$|\.d\.ts$/.test(file))
const isCode = (file: string) => /\.[jt]sx?$/.test(file)

/** "7 days" that is not the trial: each with the file and the copy it reads. */
const NOT_THE_TRIAL: Record<string, string> = {
  'app/admin/invites/page.tsx 7 days': "an invite link's lifetime option",
}

const probe = (code: string) => trialReader(ts.createSourceFile('probe.tsx', code, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX))

describe('the Pro trial length is stated only through TRIAL_DAYS, and only while the trial ships', () => {
  it('no copy types the trial length', () => {
    const offenders: string[] = []
    const allowed = new Set<string>()
    for (const file of sourceFiles()) {
      const rel = path.relative(frontendDir, file)
      if (rel === path.join('lib', 'planLimits.ts')) continue
      const typed = isCode(file)
        ? readerOf(file).typed
        : readFileSync(file, 'utf8').split('\n').flatMap((text, i) => (typesTrialLength(text) ? [{ line: i + 1, text: text.trim() }] : []))
      for (const { line, text } of typed) {
        const key = `${rel} ${text}`
        if (key in NOT_THE_TRIAL) {
          allowed.add(key)
          continue
        }
        offenders.push(`${rel}:${line} ${text.slice(0, 80)}`)
      }
    }
    expect(offenders, 'write the trial length as {TRIAL_DAYS} from lib/planLimits').toEqual([])
    expect(Object.keys(NOT_THE_TRIAL).filter((key) => !allowed.has(key)), 'no longer in the code: delete it from NOT_THE_TRIAL').toEqual([])
    // Parses every source file (about 2s idle): the default 5s is too tight on a loaded runner.
  }, 30_000)

  it('every read of TRIAL_DAYS renders only under ENABLE_PRO_TRIAL', () => {
    const reads: string[] = []
    const unguarded: string[] = []
    for (const file of sourceFiles().filter(isCode)) {
      const rel = path.relative(frontendDir, file)
      if (rel === path.join('lib', 'planLimits.ts')) continue
      for (const read of readerOf(file).reads) {
        reads.push(`${rel}:${read.line}`)
        if (!read.guarded) unguarded.push(`${rel}:${read.line}`)
      }
    }
    // Anti-vacuity: the signup gate, the paywall card and both pricing surfaces state the length.
    expect(reads.length, 'TRIAL_DAYS reads found').toBeGreaterThanOrEqual(4)
    expect(unguarded, 'state the trial only inside ENABLE_PRO_TRIAL (or a const derived from it)').toEqual([])
  }, 30_000)

  it('the two clauses follow bindings, read copy whole, and refuse a guard that can hold with the flag off', () => {
    const imports = "import { TRIAL_DAYS } from '@/lib/planLimits'\nimport { ENABLE_PRO_TRIAL } from '@/lib/featureFlags'\n"
    const typed = (code: string) => probe(imports + code).typed.length > 0
    // Copy that types a length: each is flagged.
    const lengths: Record<string, string> = {
      'a literal': "const a = 'Start a 7-day free trial'",
      'JSX text': 'const a = <p>First 7 days free</p>',
      'a number in JSX': 'const a = <p>Start a {7}-day free trial</p>',
      'a number in a template': 'const a = `Start ${7}-day free trial`',
      'a local number const': 'const LEN = 7\nconst a = <p>First {LEN} days free</p>',
      'a const of a const': 'const N = 7\nconst LEN = N\nconst a = <p>First {LEN} days free</p>',
      'a + chain': "const a = 'Start ' + 7 + '-day free trial'",
      'a length in its own element': 'const a = <p>Start a <span className="font-data">7</span>-day free trial</p>',
      'a length in a nested element': 'const a = <p>get <strong><em>7</em></strong> days free, cancel anytime.</p>',
      'a length behind &&': 'const a = <p>Start a {ready && 7}-day free trial</p>',
      'a length in a ternary': 'const a = <p>Start a {monthly ? 7 : 14}-day free trial</p>',
      'arithmetic': 'const a = <p>Start a {3 + 4}-day free trial</p>',
      'String() of a number': 'const a = `Start a ${String(7)}-day free trial`',
      'toString() of a number': 'const LEN = 7\nconst a = `Start a ${LEN.toString()}-day free trial`',
      'a no-break space entity': 'const a = <p>First 7&nbsp;days free</p>',
      'a numeric space entity': 'const a = <p>First 7&#160;days free</p>',
      'a no-break space': 'const a = <p>First 7\u00a0days free</p>',
      'a non-breaking hyphen': 'const a = <p>Start a 7\u2011day free trial</p>',
      'a number word': 'const a = <p>Start a seven-day free trial</p>',
      'weeks': 'const a = <p>Start a 1-week free trial</p>',
      'a value the reader cannot resolve': 'const a = <p>Start a {PLAN.trialDays}-day free trial</p>',
      'a length imported from another module': "import { TRIAL_LEN } from '@/lib/other'\nconst a = <p>Start a {TRIAL_LEN}-day free trial</p>",
      'a call the reader cannot read': 'const a = `Start a ${trialLength()}-day free trial`',
    }
    // Copy that states the length through TRIAL_DAYS, or another fact: each passes.
    const lookAlikes: Record<string, string> = {
      'TRIAL_DAYS itself': 'const a = <p>Start a {TRIAL_DAYS}-day free trial</p>',
      'TRIAL_DAYS in a template': 'const a = `First ${TRIAL_DAYS} days free`',
      'TRIAL_DAYS renamed': "import { TRIAL_DAYS as LEN } from '@/lib/planLimits'\nconst a = <p>First {LEN} days free</p>",
      'TRIAL_DAYS through a namespace': "import * as plan from '@/lib/planLimits'\nconst a = <p>First {plan.TRIAL_DAYS} days free</p>",
      'TRIAL_DAYS held in a const': 'const LEN = TRIAL_DAYS\nconst a = <p>First {LEN} days free</p>',
      'another limit': 'const a = <p>Free accounts get {FREE_SUMMARY_LIMIT} summaries</p>',
      'a history length': 'const a = <p>Free keeps 90-day history</p>',
      'a countdown of what is left': 'const a = <p><strong>{trialDays} {trialDays === 1 ? \'day\' : \'days\'} left</strong> in your Pro trial</p>',
    }
    expect(Object.entries(lengths).filter(([, code]) => !typed(code)).map(([name]) => name), 'a typed length the clause missed').toEqual([])
    expect(Object.entries(lookAlikes).filter(([, code]) => typed(code)).map(([name]) => name), 'a look-alike the clause flagged').toEqual([])

    const loose = (code: string) => probe(imports + code).reads.filter((r) => !r.guarded).length
    // Each read is guarded: 0 loose.
    const guardedForms: Record<string, string> = {
      'the flag': 'const a = ENABLE_PRO_TRIAL && <p>{TRIAL_DAYS}</p>',
      'a derived && const': 'const show = ENABLE_PRO_TRIAL && monthly && !beta\nconst a = show && <p>{TRIAL_DAYS}</p>',
      'an && condition': 'const a = (ready && ENABLE_PRO_TRIAL) ? <p>{TRIAL_DAYS}</p> : null',
      'an if': 'function f() { if (ENABLE_PRO_TRIAL) return <p>{TRIAL_DAYS}</p>; return null }',
      'a renamed flag import': "import { ENABLE_PRO_TRIAL as TRIAL_ON } from '@/lib/featureFlags'\nconst a = TRIAL_ON && <p>{TRIAL_DAYS}</p>",
      'a namespace flag': "import * as flags from '@/lib/featureFlags'\nconst a = flags.ENABLE_PRO_TRIAL && <p>{TRIAL_DAYS}</p>",
      'a renamed TRIAL_DAYS under the flag': "import { TRIAL_DAYS as LEN } from '@/lib/planLimits'\nconst a = ENABLE_PRO_TRIAL && <p>{LEN}</p>",
      'a guard in each of two functions': 'function A({ m }) { const show = ENABLE_PRO_TRIAL && m; return show && <p>{TRIAL_DAYS}</p> }\nfunction B({ m }) { const show = ENABLE_PRO_TRIAL && !m; return show && <p>{TRIAL_DAYS}</p> }',
      'a shadowing local, not TRIAL_DAYS': 'function F({ TRIAL_DAYS }) { return <p>{TRIAL_DAYS}</p> }',
    }
    // Each read is loose: 1 or more.
    const looseForms: Record<string, string> = {
      'no guard': 'const a = <p>{TRIAL_DAYS}</p>',
      'a derived ||': 'const show = ENABLE_PRO_TRIAL || beta\nconst a = show && <p>{TRIAL_DAYS}</p>',
      'an inline ||': 'const a = (ENABLE_PRO_TRIAL || beta) && <p>{TRIAL_DAYS}</p>',
      'a parenthesised negation': 'const a = !(ENABLE_PRO_TRIAL) && <p>{TRIAL_DAYS}</p>',
      'a comparison': 'const a = ENABLE_PRO_TRIAL === false && <p>{TRIAL_DAYS}</p>',
      'an inverted ternary': 'const show = ENABLE_PRO_TRIAL ? false : true\nconst a = show && <p>{TRIAL_DAYS}</p>',
      'a ??': 'const a = (ENABLE_PRO_TRIAL ?? beta) && <p>{TRIAL_DAYS}</p>',
      'the else branch': 'const a = ENABLE_PRO_TRIAL ? null : <p>{TRIAL_DAYS}</p>',
      'a renamed TRIAL_DAYS import': "import { TRIAL_DAYS as TRIAL_LENGTH } from '@/lib/planLimits'\nconst a = <p>Pro starts with a {TRIAL_LENGTH}-day free trial.</p>",
      'a namespace member': "import * as plan from '@/lib/planLimits'\nconst a = <p>{plan.TRIAL_DAYS}</p>",
      'a namespace element access': "import * as plan from '@/lib/planLimits'\nconst a = <p>{plan['TRIAL_DAYS']}</p>",
      'destructured from the namespace': "import * as plan from '@/lib/planLimits'\nconst { TRIAL_DAYS: n } = plan\nconst a = <p>{n}</p>",
      'TRIAL_DAYS held in a const': 'const LEN = TRIAL_DAYS\nconst a = <p>{LEN}</p>',
      'a same-named const in another function': 'function A({ m }) { const showTrial = ENABLE_PRO_TRIAL && m; return showTrial && <p>{TRIAL_DAYS}</p> }\nfunction B({ m }) { const showTrial = m; return showTrial ? <p>Start with a {TRIAL_DAYS}-day free trial.</p> : null }',
      'a reassigned let': 'let show = ENABLE_PRO_TRIAL && monthly\nshow = true\nconst a = show && <p>{TRIAL_DAYS}</p>',
      'a parameter named like a guard': 'function F({ showTrial }) { return showTrial && <p>{TRIAL_DAYS}</p> }',
    }
    expect(Object.entries(guardedForms).filter(([, code]) => loose(code) !== 0).map(([name]) => name), 'a guarded read the clause called loose').toEqual([])
    expect(Object.entries(looseForms).filter(([, code]) => loose(code) === 0).map(([name]) => name), 'a loose read the clause called guarded').toEqual([])
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
