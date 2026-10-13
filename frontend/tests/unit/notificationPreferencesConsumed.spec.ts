import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * No dead preference ships (DSW-01). Every alert preference the settings form renders or saves, and
 * every <option> value it offers, must be read by the code that sends alerts: the backend modules
 * below, read as text (the planLimitsLockstep pattern). A field counts as read when a consumer reads
 * `prefs.<field>` (an assignment does not count: coerce_to_entitlement writes realtime and notify_8k);
 * an option value counts when a consumer has it as a string literal. Comments are ignored.
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

const formText = readFileSync(path.join(frontendDir, FORM), 'utf8')
const source = ts.createSourceFile(FORM, formText, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)

/** Python with `#` comments dropped (a `#` inside a string literal is rare here and only widens). */
const consumerCode = CONSUMERS.map((rel) =>
  readFileSync(path.resolve(frontendDir, '..', rel), 'utf8')
    .split('\n')
    .map((line) => line.replace(/(^|\s)#.*$/, ''))
    .join('\n'),
).join('\n')

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

describe('Notification preferences the form offers are read by the alert jobs', () => {
  it('finds the form\'s preferences (the scan is not vacuous)', () => {
    expect([...fields.keys()]).toEqual(expect.arrayContaining(['notify_10k', 'notify_10q', 'notify_8k', 'realtime']))
  })

  it('every field the form renders or saves is read as prefs.<field> by a consumer', () => {
    const unread = [...fields].filter(([field]) => !new RegExp(`\\bprefs\\.${escape(field)}\\b(?!\\s*=(?!=))`).test(consumerCode))
    expect(unread.map(([field, at]) => `${FORM}:${at} ${field} has no reader in ${CONSUMERS.join(', ')}`)).toEqual([])
  })

  it('every <option> value the form offers is a literal a consumer acts on', () => {
    const unread = [...options].filter(([value]) => !new RegExp(`['"]${escape(value)}['"]`).test(consumerCode))
    expect(unread.map(([value, at]) => `${FORM}:${at} option "${value}" has no reader in ${CONSUMERS.join(', ')}`)).toEqual([])
  })
})
