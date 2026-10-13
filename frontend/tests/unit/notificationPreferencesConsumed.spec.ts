import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * No dead preference ships (DSW-01). Every alert preference the settings form renders or saves, and
 * every <option> value it offers, must be read by the code that sends alerts: the three job services
 * below, read as text (the planLimitsLockstep pattern). A field counts as read when a job function reads
 * `prefs.<field>` (an assignment does not count); an option value counts when a job function has it as a
 * string literal. Only function and class bodies count, and never the preferences write path that
 * notification_service.py also holds (WRITE_PATH: the defaults, the entitlement coercion and the prefs
 * API's write), so a sanitizer or a constant moved there cannot stand in for a job honouring the field.
 * Comments and docstrings are ignored.
 *
 * The digest frequency select failed this: users.py stored `digest` and no job read it, so a
 * "Weekly" choice still mailed daily. It comes back only with a reader here.
 */
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const FORM = 'features/settings/components/NotificationPreferencesForm.tsx'
const CONSUMERS = [
  'backend/app/services/notification_service.py',
  'backend/app/services/filing_scan_service.py',
  'backend/app/services/notification_delivery_service.py',
]

/** notification_service.py's preferences write path: it stores and coerces, it sends nothing. */
const WRITE_PATH = ['get_or_create_preferences', 'coerce_to_entitlement', 'apply_preference_update']

/**
 * The code that can honour a preference: the top-level `def`/`class` blocks (decorators included) other
 * than the write path, with `#` comments and triple-quoted strings dropped. Module-level statements go
 * too: a constant there is a value list, not a job reading it. (A `#` or triple quote inside a string
 * literal is rare here and only narrows.)
 */
function readerCode(python: string): string {
  const lines = python
    .replace(/"""[\s\S]*?"""|'''[\s\S]*?'''/g, '')
    .split('\n')
    .map((line) => line.replace(/(^|\s)#.*$/, ''))
  const kept: string[] = []
  let keep = false
  let decorators: string[] = []
  for (const line of lines) {
    // A column-0 closing bracket (`) -> Tuple[bool, bool]:`) still belongs to the signature above it.
    if (/^[^\s)\]}]/.test(line)) {
      if (line.startsWith('@')) {
        decorators.push(line)
        continue
      }
      const block = /^(?:async\s+)?def\s+(\w+)|^class\s+\w+/.exec(line)
      keep = Boolean(block) && !WRITE_PATH.includes(block?.[1] ?? '')
      if (keep) kept.push(...decorators)
      decorators = []
    }
    if (keep) kept.push(line)
  }
  return kept.join('\n')
}

const formText = readFileSync(path.join(frontendDir, FORM), 'utf8')
const source = ts.createSourceFile(FORM, formText, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)

const consumerCode = CONSUMERS.map((rel) => readerCode(readFileSync(path.resolve(frontendDir, '..', rel), 'utf8'))).join('\n')

const line = (node: ts.Node) => source.getLineAndCharacterOfPosition(node.getStart()).line + 1

const fields = new Map<string, number>()
const options = new Map<string, number>()

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
    // save({ digest: … }) / mutation.mutate({ … })
    if (callee === 'save' || callee.endsWith('.mutate')) {
      for (const arg of node.arguments) {
        if (!ts.isObjectLiteralExpression(arg)) continue
        for (const prop of arg.properties) {
          if (prop.name && (ts.isIdentifier(prop.name) || ts.isStringLiteral(prop.name))) fields.set(prop.name.text, line(prop))
        }
      }
    }
  }
  // checked={prefs.x} / value={prefs.x}: a preference the form renders as a control's state.
  if (ts.isJsxAttribute(node) && ['checked', 'value'].includes(node.name.getText(source))) {
    const init = node.initializer
    if (init && ts.isJsxExpression(init) && init.expression && ts.isPropertyAccessExpression(init.expression)
      && init.expression.expression.getText(source) === 'prefs') {
      fields.set(init.expression.name.text, line(init))
    }
  }
  // <option value="weekly">
  if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(source) === 'option') {
    for (const attr of node.attributes.properties) {
      if (ts.isJsxAttribute(attr) && attr.name.getText(source) === 'value' && attr.initializer && ts.isStringLiteral(attr.initializer)) {
        options.set(attr.initializer.text, line(attr))
      }
    }
  }
  ts.forEachChild(node, visit)
}
visit(source)

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const readsField = (code: string, field: string) => new RegExp(`\\bprefs\\.${escape(field)}\\b(?!\\s*=(?!=))`).test(code)
const hasLiteral = (code: string, value: string) => new RegExp(`['"]${escape(value)}['"]`).test(code)

describe('Notification preferences the form offers are read by the alert jobs', () => {
  it('finds the form\'s preferences (the scan is not vacuous)', () => {
    expect([...fields.keys()]).toEqual(expect.arrayContaining(['notify_10k', 'notify_10q', 'notify_8k', 'realtime']))
  })

  it('counts a job function\'s read, never the write path, a module constant or a docstring (self-check)', () => {
    const fixture = [
      '"""Helpers. prefs.weekly_note is only mentioned here."""',
      'VALID_DIGESTS = ("immediate", "daily", "weekly")',
      'def apply_preference_update(db, prefs, data):',
      '    if prefs.digest not in ("immediate", "daily", "weekly"):',
      '        prefs.digest = "daily"',
      '',
      '@cached',
      'def evaluate_delivery(',
      '    prefs, ent, filing_type,',
      ') -> tuple:',
      '    # prefs.notify_10k in a comment is no read',
      '    prefs.realtime = False',
      '    return bool(prefs.notify_8k), filing_type == "8-K"',
    ].join('\n')
    const code = readerCode(fixture)
    expect(readsField(code, 'notify_8k')).toBe(true)
    expect(hasLiteral(code, '8-K')).toBe(true)
    expect(code).toContain('@cached')
    expect(readsField(code, 'digest')).toBe(false)
    expect(readsField(code, 'realtime')).toBe(false)
    expect(readsField(code, 'notify_10k')).toBe(false)
    expect(readsField(code, 'weekly_note')).toBe(false)
    expect(hasLiteral(code, 'weekly')).toBe(false)
  })

  it('every field the form renders or saves is read as prefs.<field> by a consumer', () => {
    const unread = [...fields].filter(([field]) => !readsField(consumerCode, field))
    expect(unread.map(([field, at]) => `${FORM}:${at} ${field} has no reader in ${CONSUMERS.join(', ')}`)).toEqual([])
  })

  it('every <option> value the form offers is a literal a consumer acts on', () => {
    const unread = [...options].filter(([value]) => !hasLiteral(consumerCode, value))
    expect(unread.map(([value, at]) => `${FORM}:${at} option "${value}" has no reader in ${CONSUMERS.join(', ')}`)).toEqual([])
  })
})
