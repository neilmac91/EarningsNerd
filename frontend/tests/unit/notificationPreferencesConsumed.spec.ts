import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * No dead preference ships (DSW-01). Every alert preference the settings form renders or saves, and every
 * value it offers for one, must be read by the code that sends alerts: the three job services below, read as
 * text (the planLimitsLockstep pattern) and split into their top-level `def` and `class` blocks (decorators
 * included). A block counts only when the alert jobs reach it: the entry points JOB_ENTRIES and every block one
 * of them names, followed through the three files. A field counts as read when such a block reads
 * `prefs.<field>` (an assignment does not count); an option value counts when such a block has it as a string
 * literal. So the preferences write path (apply_preference_update and the defaults and coercion only it
 * reaches), a helper only the write path calls (a `_normalize_digest` sanitizer), a GET serializer and a
 * module constant cannot stand in for a job honouring the field. Comments and docstrings are ignored.
 *
 * The values the form offers are read where they are written, in each form a choice takes: any element's
 * `value="…"` or `value={'…'}` (an <option>, a radio input, a custom item; `value={prefs.x}` is the control's
 * state, a field), each entry's `value` in an `options` prop (SegmentedControl, the design system's single
 * choice, or any select wrapper), and a literal a save or mutate call writes into a field (`save({ digest:
 * 'weekly' })`, each branch of a condition over literals). A value or an `options` entry may also be the element,
 * or one of its fields, of the array a `.map` takes (`DIGESTS.map((d) => <option value={d}>)`,
 * `CHOICES.map((c) => ({ value: c.value }))`), the array written in place or as a const in the form. A `value`
 * or an `options` written any other way fails the scan, so a choice it cannot read never ships unread.
 *
 * Limits: a block is reached by name (a same-named function in another module is not told apart, and a call
 * made through a variable or getattr is not followed, which only narrows), and a reached block counts as a
 * whole, so a read whose value the job then drops still counts; review reads what the job does with it.
 *
 * The digest frequency select failed this: users.py stored `digest` and no job read it, so a "Weekly" choice
 * still mailed daily. It comes back only with a reader here.
 */
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const FORM = 'features/settings/components/NotificationPreferencesForm.tsx'
const CONSUMERS = [
  'backend/app/services/notification_service.py',
  'backend/app/services/filing_scan_service.py',
  'backend/app/services/notification_delivery_service.py',
]

/** Where the alert jobs start: the hourly scan, the daily digest, the delivery drain, and the per-filing decision they share. */
const JOB_ENTRIES = ['run_filing_scan', 'run_daily_digest', 'drain', 'evaluate_delivery']

/**
 * A Python source's top-level `def`/`class` blocks by name (decorators included), with `#` comments and
 * triple-quoted strings dropped. Module-level statements go: a constant there is a value list, not a job
 * reading it. (A `#` or triple quote inside a string literal is rare here and only narrows.)
 */
function blocks(python: string): Map<string, string> {
  const lines = python
    .replace(/"""[\s\S]*?"""|'''[\s\S]*?'''/g, '')
    .split('\n')
    .map((line) => line.replace(/(^|\s)#.*$/, ''))
  const out = new Map<string, string[]>()
  let current: string[] | null = null
  let decorators: string[] = []
  for (const line of lines) {
    // A column-0 closing bracket (`) -> Tuple[bool, bool]:`) still belongs to the signature above it.
    if (/^[^\s)\]}]/.test(line)) {
      if (line.startsWith('@')) {
        decorators.push(line)
        continue
      }
      const block = /^(?:async\s+)?def\s+(\w+)|^class\s+(\w+)/.exec(line)
      current = null
      if (block) {
        const name = block[1] ?? block[2]
        current = out.get(name) ?? []
        out.set(name, current)
        current.push(...decorators)
      }
      decorators = []
    }
    if (current) current.push(line)
  }
  return new Map([...out].map(([name, code]) => [name, code.join('\n')]))
}

/** The code the alert jobs run: every block named from JOB_ENTRIES on, through the given sources. */
function jobCode(sources: string[], entries: string[] = JOB_ENTRIES): string {
  const all = new Map<string, string>()
  for (const python of sources) for (const [name, code] of blocks(python)) all.set(name, `${all.get(name) ?? ''}\n${code}`)
  const reached = new Set<string>()
  const queue = entries.filter((name) => all.has(name))
  while (queue.length) {
    const name = queue.pop()!
    if (reached.has(name)) continue
    reached.add(name)
    for (const other of all.keys()) {
      if (!reached.has(other) && new RegExp(`\\b${other}\\b`).test(all.get(name)!)) queue.push(other)
    }
  }
  return [...reached].map((name) => all.get(name)).join('\n')
}

/** The form's preferences: the fields it renders or saves, the option values it offers, and the option values it writes in a form the scan cannot read. */
function formPreferences(file: string, text: string) {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const line = (node: ts.Node) => source.getLineAndCharacterOfPosition(node.getStart()).line + 1
  const fields = new Map<string, number>()
  const options = new Map<string, number>()
  const unreadable: string[] = []

  const unwrap = (node: ts.Expression): ts.Expression =>
    ts.isAsExpression(node) || ts.isSatisfiesExpression(node) || ts.isParenthesizedExpression(node) ? unwrap(node.expression) : node
  const literal = (node: ts.Expression | undefined): string | null => {
    if (!node) return null
    const inner = unwrap(node)
    return ts.isStringLiteral(inner) || ts.isNoSubstitutionTemplateLiteral(inner) ? inner.text : null
  }
  /** The array literal an expression names: written in place, or a const in this file. */
  const arrayOf = (node: ts.Expression): ts.ArrayLiteralExpression | null => {
    const inner = unwrap(node)
    if (ts.isArrayLiteralExpression(inner)) return inner
    if (!ts.isIdentifier(inner)) return null
    let found: ts.ArrayLiteralExpression | null = null
    const find = (n: ts.Node): void => {
      if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === inner.text && n.initializer) {
        const init = unwrap(n.initializer)
        if (ts.isArrayLiteralExpression(init)) found = init
      }
      ts.forEachChild(n, find)
    }
    find(source)
    return found
  }
  /** The values a `value={…}` takes: a literal, or the elements (or one field of each) of the array a `.map` callback walks. */
  const optionValues = (expression: ts.Expression): string[] | null => {
    const direct = literal(expression)
    if (direct !== null) return [direct]
    const field = ts.isPropertyAccessExpression(expression) ? expression.name.text : null
    const root = field ? expression.expression : expression
    if (!ts.isIdentifier(root)) return null
    for (let node: ts.Node | undefined = expression.parent; node; node = node.parent) {
      if (!(ts.isArrowFunction(node) || ts.isFunctionExpression(node))) continue
      const [element] = node.parameters
      if (!element || !ts.isIdentifier(element.name) || element.name.text !== root.text) continue
      const call = node.parent
      if (!ts.isCallExpression(call) || call.arguments[0] !== node || !ts.isPropertyAccessExpression(call.expression)
        || call.expression.name.text !== 'map') return null
      const array = arrayOf(call.expression.expression)
      if (!array) return null
      const values = array.elements.map((item) => {
        if (!field) return literal(item as ts.Expression)
        const object = unwrap(item as ts.Expression)
        if (!ts.isObjectLiteralExpression(object)) return null
        const prop = object.properties.find(
          (p): p is ts.PropertyAssignment => ts.isPropertyAssignment(p) && !!p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) && p.name.text === field,
        )
        return literal(prop?.initializer)
      })
      return values.every((value): value is string => value !== null) ? values : null
    }
    return null
  }

  /** The values an `options` prop offers: each entry's `value`, the array written in place or a const in this file, or a
      `.map` whose callback returns `{ value: … }` over one. */
  const optionsValues = (expression: ts.Expression): string[] | null => {
    const valueOf = (object: ts.Expression) => {
      const inner = unwrap(object)
      if (!ts.isObjectLiteralExpression(inner)) return undefined
      return inner.properties.find(
        (p): p is ts.PropertyAssignment => ts.isPropertyAssignment(p) && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) && p.name.text === 'value',
      )?.initializer
    }
    const array = arrayOf(expression)
    if (array) {
      const values = array.elements.map((item) => literal(valueOf(item as ts.Expression)))
      return values.every((value): value is string => value !== null) ? values : null
    }
    const call = unwrap(expression)
    const callback = ts.isCallExpression(call) && ts.isPropertyAccessExpression(call.expression) && call.expression.name.text === 'map' ? call.arguments[0] : undefined
    if (!callback || !(ts.isArrowFunction(callback) || ts.isFunctionExpression(callback))) return null
    const body = ts.isBlock(callback.body)
      ? callback.body.statements.find((statement): statement is ts.ReturnStatement => ts.isReturnStatement(statement))?.expression
      : callback.body
    const value = body && valueOf(body)
    return value ? optionValues(value) : null
  }
  /** The string literals an expression can be: a literal, each branch of a condition, each side of `||` or `??`. */
  const literalsOf = (expression: ts.Expression): string[] => {
    const inner = unwrap(expression)
    const direct = literal(inner)
    if (direct !== null) return [direct]
    if (ts.isConditionalExpression(inner)) return [...literalsOf(inner.whenTrue), ...literalsOf(inner.whenFalse)]
    const op = ts.isBinaryExpression(inner) ? inner.operatorToken.kind : undefined
    if (ts.isBinaryExpression(inner) && (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken)) return [...literalsOf(inner.left), ...literalsOf(inner.right)]
    return []
  }

  const visit = (node: ts.Node): void => {
    // type BoolPref = 'notify_10k' | … : every member is a field the form can save.
    if (ts.isTypeAliasDeclaration(node) && ts.isUnionTypeNode(node.type)) {
      for (const member of node.type.types) {
        if (ts.isLiteralTypeNode(member) && ts.isStringLiteral(member.literal)) fields.set(member.literal.text, line(member))
      }
    }
    if (ts.isCallExpression(node)) {
      const callee = node.expression.getText(source)
      // setBool('notify_10k')
      if (callee === 'setBool') {
        for (const arg of node.arguments) if (ts.isStringLiteral(arg)) fields.set(arg.text, line(arg))
      }
      // save({ digest: … }) / mutation.mutate({ … }): each field it writes, and each literal it writes into one.
      if (callee === 'save' || callee.endsWith('.mutate')) {
        for (const arg of node.arguments) {
          if (!ts.isObjectLiteralExpression(arg)) continue
          for (const prop of arg.properties) {
            if (prop.name && (ts.isIdentifier(prop.name) || ts.isStringLiteral(prop.name))) fields.set(prop.name.text, line(prop))
            if (ts.isPropertyAssignment(prop)) for (const value of literalsOf(prop.initializer)) options.set(value, line(prop))
          }
        }
      }
    }
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node))) {
      const tag = node.tagName.getText(source)
      for (const attr of node.attributes.properties) {
        if (!ts.isJsxAttribute(attr) || !attr.initializer) continue
        const name = attr.name.getText(source)
        const init = attr.initializer
        const expression = ts.isJsxExpression(init) ? init.expression : undefined
        // checked={prefs.x} / value={prefs.x}: a preference the form renders as a control's state.
        if ((name === 'checked' || name === 'value') && expression && ts.isPropertyAccessExpression(expression) && expression.expression.getText(source) === 'prefs') {
          fields.set(expression.name.text, line(init))
          continue
        }
        // value="weekly", value={'weekly'}, a value a .map writes (an <option>, a radio, any item); options={[{ value: … }]}.
        const values = name === 'value'
          ? ts.isStringLiteral(init) ? [init.text] : expression ? optionValues(expression) : null
          : name === 'options'
            ? expression ? optionsValues(expression) : null
            : undefined
        if (values === undefined) continue
        if (values) for (const value of values) options.set(value, line(attr))
        else unreadable.push(`${file}:${line(attr)} <${tag} ${attr.getText(source)}>`)
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return { fields, options, unreadable }
}

const form = formPreferences(FORM, readFileSync(path.join(frontendDir, FORM), 'utf8'))
const consumerCode = jobCode(CONSUMERS.map((rel) => readFileSync(path.resolve(frontendDir, '..', rel), 'utf8')))

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const readsField = (code: string, field: string) => new RegExp(`\\bprefs\\.${escape(field)}\\b(?!\\s*=(?!=))`).test(code)
const hasLiteral = (code: string, value: string) => new RegExp(`['"]${escape(value)}['"]`).test(code)

describe('Notification preferences the form offers are read by the alert jobs', () => {
  it('finds the form\'s preferences and the jobs\' code (the scan is not vacuous)', () => {
    expect([...form.fields.keys()]).toEqual(expect.arrayContaining(['notify_10k', 'notify_10q', 'notify_8k', 'realtime']))
    for (const entry of JOB_ENTRIES) expect(consumerCode, entry).toMatch(new RegExp(`def ${entry}\\(`))
  })

  it('counts a read only in code the jobs reach, never the write path, a helper only it calls, a serializer, a constant or a docstring (self-check)', () => {
    const service = [
      '"""Helpers. prefs.weekly_note is only mentioned here."""',
      'VALID_DIGESTS = ("immediate", "daily", "weekly")',
      'def apply_preference_update(db, prefs, data):',
      '    prefs.digest = _normalize_digest(prefs)',
      '',
      'def _normalize_digest(prefs):',
      '    return prefs.digest if prefs.digest in ("daily", "weekly") else "daily"',
      '',
      'def serialize_preferences(prefs):',
      '    return {"notify_10q": prefs.notify_10q}',
      '',
      '@cached',
      'def evaluate_delivery(',
      '    prefs, ent, filing_type,',
      ') -> tuple:',
      '    # prefs.notify_10k in a comment is no read',
      '    prefs.realtime = False',
      '    return _enabled(prefs, filing_type), filing_type == "8-K"',
      '',
      'def _enabled(prefs, filing_type):',
      '    return bool(prefs.notify_8k)',
    ].join('\n')
    const job = ['async def run_daily_digest(db):', '    eligible, _ = evaluate_delivery(prefs, ent, "10-K")'].join('\n')
    const code = jobCode([service, job])
    expect(readsField(code, 'notify_8k')).toBe(true)
    expect(hasLiteral(code, '8-K')).toBe(true)
    expect(code).toContain('@cached')
    expect(readsField(code, 'digest')).toBe(false)
    expect(readsField(code, 'notify_10q')).toBe(false)
    expect(readsField(code, 'realtime')).toBe(false)
    expect(readsField(code, 'notify_10k')).toBe(false)
    expect(readsField(code, 'weekly_note')).toBe(false)
    expect(hasLiteral(code, 'weekly')).toBe(false)
    // A job that calls the helper itself makes it a reader.
    expect(readsField(jobCode([service, `${job}\n    _normalize_digest(prefs)`]), 'digest')).toBe(true)
  })

  it('reads the values every kind of choice offers, in place and through a .map, and refuses any other (self-check)', () => {
    const fixture = [
      "const DIGESTS = ['daily', 'weekly'] as const",
      "const CHOICES = [{ value: 'immediate', label: 'Now' }]",
      'export const A = () => <select>{DIGESTS.map((d) => <option key={d} value={d}>{d}</option>)}</select>',
      'export const B = () => <select>{CHOICES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}</select>',
      "export const C = () => <select><option value=\"monthly\">Monthly</option><option value={'hourly'}>Hourly</option></select>",
      "export const D = () => <select>{['quarterly'].map((q) => <option key={q} value={q}>{q}</option>)}</select>",
      'export const E = ({ v }: { v: string }) => <option value={v} />',
      'export const F = () => <select>{load().map((x) => <option key={x} value={x}>{x}</option>)}</select>',
      // The choices the review of #1291 found unread (DSW-01's "Weekly still mails daily" through another control):
      // a SegmentedControl's options, in place, as a const and through a .map; a radio input; a literal a save writes.
      "export const G = () => <SegmentedControl label=\"Digest\" options={[{ value: 'fortnightly', label: 'Fortnightly' }]} value={prefs.digest} onChange={(digest) => save({ digest })} />",
      "const PERIODS = [{ value: 'yearly', label: 'Yearly' }] as const",
      'export const H = () => <SegmentedControl label="Period" options={PERIODS} value={prefs.period} onChange={() => {}} />',
      "const KINDS = ['annual', 'interim'] as const",
      'export const I = () => <SegmentedControl label="Kind" options={KINDS.map((k) => ({ value: k, label: k }))} value={prefs.kind} onChange={() => {}} />',
      'export const J = () => <input type="radio" name="digest" value="biweekly" checked={prefs.digest === \'biweekly\'} readOnly />',
      "export const K = () => <button type=\"button\" onClick={() => save({ digest: on ? 'never' : 'hourly' })}>Never</button>",
      'export const L = () => <SegmentedControl label="x" options={load()} value={prefs.l} onChange={() => {}} />',
      "export const M = () => <SegmentedControl label=\"x\" options={[{ value: v, label: 'V' }]} value={prefs.m} onChange={() => {}} />",
    ].join('\n')
    const { options, unreadable } = formPreferences('fixture.tsx', fixture)
    expect([...options.keys()].sort()).toEqual([
      'annual', 'biweekly', 'daily', 'fortnightly', 'hourly', 'immediate', 'interim', 'monthly', 'never', 'quarterly', 'weekly', 'yearly',
    ])
    expect(unreadable).toEqual([
      'fixture.tsx:7 <option value={v}>',
      'fixture.tsx:8 <option value={x}>',
      'fixture.tsx:16 <SegmentedControl options={load()}>',
      "fixture.tsx:17 <SegmentedControl options={[{ value: v, label: 'V' }]}>",
    ])
  })

  it('every field the form renders or saves is read as prefs.<field> by the jobs', () => {
    const unread = [...form.fields].filter(([field]) => !readsField(consumerCode, field))
    expect(unread.map(([field, at]) => `${FORM}:${at} ${field} has no reader the jobs reach in ${CONSUMERS.join(', ')}`)).toEqual([])
  })

  it('every value the form offers is a literal the jobs act on, and the scan reads each one', () => {
    expect(form.unreadable, 'write the value as a literal or through a .map over a literal array').toEqual([])
    const unread = [...form.options].filter(([value]) => !hasLiteral(consumerCode, value))
    expect(unread.map(([value, at]) => `${FORM}:${at} option "${value}" has no reader the jobs reach in ${CONSUMERS.join(', ')}`)).toEqual([])
  })
})
