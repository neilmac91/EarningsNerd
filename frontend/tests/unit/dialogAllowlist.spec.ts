/* =============================================================================
   dialogAllowlist.spec.ts — guardrail (v3, DS-04)
   -----------------------------------------------------------------------------
   Dialog semantics ship ONLY through ui/Modal plus the documented bespoke layers:
     - the copilot rail / filing viewer / workspace sheets (the rail and workspace
       trap focus via useSheetFocusTrap) and SourceTrace's mobile source-detail
       sheet — role="dialog";
     - the calendar's DayDetailDialog — a native <dialog> + showModal(), whose top
       layer supplies the focus trap and Escape.
   Everything else composes <Modal>.

   The scan reads each file's TypeScript AST (comments never count) and reports
   three kinds of dialog:
     role   — a `role` that names dialog or alertdialog: a JSX attribute literal, a
              role={…} expression any of whose values does (role={isError ?
              'alertdialog' : 'dialog'} included), a `role:` object property (spread
              or createElement props) or setAttribute('role', …). A role={…} value
              that cannot be proven a literal (role={role}, role={c ? r : 'status'})
              counts too: inline the literals.
     native — a <dialog> element, or createElement('dialog').
     layer  — the dialog layer's own tokens in any string: z-modal or bg-overlay
              (variant prefixes such as backdrop: included). DESIGN_SYSTEM reserves
              both for dialogs and sheets, so a role-less hand-rolled modal — the
              shape CookieConsent's settings panel had — is caught too.
   A non-modal popover takes none of these: no dialog role, and z-overlay.
   Each allowlisted file is pinned, with its reason, to the number of sites of
   each kind it declares (the rawFetchAllowlist idiom). A new hand-rolled dialog,
   an extra one inside a sanctioned file, a kind drift and a stale entry all fail.

   Nothing DayDetailDialog renders may import ui/Modal: under showModal() a <body>
   portal is inert and painted beneath the top layer
   (lessons/frontend-native-modal-dialog-makes-body-portals-inert.md).
============================================================================= */

import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

type DialogKind = 'layer' | 'native' | 'role'
type Counts = Partial<Record<DialogKind, number>>

const ROOT = path.join(__dirname, '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
// Shrink-only: lower it when an entry goes; never raise it to fit a new hand-rolled dialog.
const MAX_ALLOWLIST_SIZE = 6
const ALLOW: Record<string, { counts: Counts; reason: string }> = {
  'components/ui/Modal.tsx': { counts: { layer: 1, role: 1 }, reason: 'the one dialog primitive' },
  'features/filings/components/copilot/AskCopilotRail.tsx': {
    counts: { layer: 1, role: 1 },
    reason: 'bespoke mobile sheet, trapped by useSheetFocusTrap',
  },
  'features/filings/components/copilot/FilingViewer.tsx': { counts: { layer: 1, role: 1 }, reason: 'bespoke filing-viewer sheet' },
  'features/filings/components/copilot/FilingWorkspace.tsx': {
    counts: { layer: 1, role: 1 },
    reason: 'bespoke workspace sheet, trapped by useSheetFocusTrap',
  },
  'features/filings/components/SourceTrace.tsx': { counts: { layer: 2, role: 1 }, reason: 'bespoke mobile source-detail sheet' },
  'features/calendar/components/DayDetailDialog.tsx': {
    counts: { layer: 1, native: 1 },
    reason: 'sanctioned native <dialog> + showModal() on the overlay backdrop — not pending migration',
  },
}

// A class token behind any variant prefix (dark:, backdrop:, [&>div]:, data-[open]:), with ! or an opacity suffix.
const LAYER_TOKEN = /(?:^|:)!?(?:z-modal|bg-overlay)(?:\/\d+)?$/
const hasLayerToken = (text: string) => text.split(/\s+/).some((token) => LAYER_TOKEN.test(token))

const namesDialog = (text: string) =>
  text
    .trim()
    .split(/\s+/)
    .some((token) => token === 'dialog' || token === 'alertdialog')

/** Every string or template chunk under `node` (the literals a role expression can evaluate to). */
function literalTexts(node: ts.Node): string[] {
  const out: string[] = []
  const visit = (n: ts.Node): void => {
    if (ts.isStringLiteralLike(n) || ts.isTemplateHead(n) || ts.isTemplateMiddle(n) || ts.isTemplateTail(n)) {
      out.push(n.text)
    }
    ts.forEachChild(n, visit)
  }
  visit(node)
  return out
}

/**
 * The values a role={…} expression can take: each proven string, or null for one that cannot be
 * proven (an identifier, call, member access or template with substitutions). Follows parens and
 * casts, both branches of ?:, the right of && (its left is falsy) and both sides of || and ??.
 */
function roleValues(expr: ts.Expression): (string | null)[] {
  if (
    ts.isParenthesizedExpression(expr) ||
    ts.isAsExpression(expr) ||
    ts.isSatisfiesExpression(expr) ||
    ts.isNonNullExpression(expr) ||
    ts.isTypeAssertionExpression(expr)
  ) {
    return roleValues(expr.expression)
  }
  if (ts.isConditionalExpression(expr)) return [...roleValues(expr.whenTrue), ...roleValues(expr.whenFalse)]
  if (ts.isBinaryExpression(expr)) {
    const op = expr.operatorToken.kind
    if (op === ts.SyntaxKind.AmpersandAmpersandToken) return roleValues(expr.right)
    if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken) {
      return [...roleValues(expr.left), ...roleValues(expr.right)]
    }
  }
  if (ts.isStringLiteralLike(expr)) return [expr.text]
  if ((ts.isIdentifier(expr) && expr.text === 'undefined') || expr.kind === ts.SyntaxKind.NullKeyword || expr.kind === ts.SyntaxKind.FalseKeyword) {
    return []
  }
  return [null]
}

const propertyName = (name: ts.PropertyName) =>
  ts.isIdentifier(name) || ts.isStringLiteral(name) ? name.text : undefined

const rolesDialog = (expr: ts.Expression) => roleValues(expr).some((v) => v === null || namesDialog(v))

function countDialogSites(source: string, fileName: string): Counts {
  const sourceFile = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    fileName.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  )
  const counts: Counts = {}
  const add = (kind: DialogKind) => {
    counts[kind] = (counts[kind] ?? 0) + 1
  }
  const visit = (node: ts.Node): void => {
    if (
      (ts.isStringLiteralLike(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) &&
      hasLayerToken(node.text)
    ) {
      add('layer')
    }
    if (ts.isJsxAttribute(node) && node.name.getText(sourceFile) === 'role' && node.initializer) {
      const init = node.initializer
      if (ts.isStringLiteral(init)) {
        if (namesDialog(init.text)) add('role')
      } else if (ts.isJsxExpression(init) && init.expression) {
        if (rolesDialog(init.expression)) add('role')
      }
    } else if (ts.isPropertyAssignment(node) && propertyName(node.name) === 'role') {
      if (literalTexts(node.initializer).some(namesDialog)) add('role')
    } else if (ts.isCallExpression(node)) {
      const callee = node.expression
      const method = ts.isPropertyAccessExpression(callee) ? callee.name.text : ts.isIdentifier(callee) ? callee.text : ''
      const [first, second] = node.arguments
      if (method === 'setAttribute' && first && ts.isStringLiteralLike(first) && first.text === 'role' && second) {
        if (literalTexts(second).some(namesDialog)) add('role')
      }
      if (method === 'createElement' && first && ts.isStringLiteralLike(first) && first.text === 'dialog') {
        add('native')
      }
    } else if (
      (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) &&
      node.tagName.getText(sourceFile) === 'dialog'
    ) {
      add('native')
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return counts
}

function walk(dir: string, out: string[] = []): string[] {
  if (!fs.existsSync(dir)) return out
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name)) out.push(p)
  }
  return out
}

let scanned: Map<string, Counts> | undefined
function scan(): Map<string, Counts> {
  if (scanned) return scanned
  const found = new Map<string, Counts>()
  for (const dir of SCAN_DIRS) {
    for (const file of walk(path.join(ROOT, dir))) {
      const counts = countDialogSites(fs.readFileSync(file, 'utf8'), file)
      if (Object.keys(counts).length > 0) found.set(path.relative(ROOT, file).split(path.sep).join('/'), counts)
    }
  }
  scanned = found
  return found
}

const MODAL_EXPORTS = new Set(['Modal', 'ModalHeader', 'ModalBody', 'ModalFooter'])

/** Local modules a file imports statically at runtime (type-only and dynamic import() not followed). */
function localImports(file: string): { modal: boolean; next: string[] } {
  const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  let modal = false
  const next: string[] = []
  for (const stmt of source.statements) {
    if (!ts.isImportDeclaration(stmt) || !ts.isStringLiteral(stmt.moduleSpecifier)) continue
    const clause = stmt.importClause
    if (clause?.isTypeOnly) continue
    const spec = stmt.moduleSpecifier.text
    const named = clause?.namedBindings && ts.isNamedImports(clause.namedBindings) ? clause.namedBindings.elements : []
    if (spec === '@/components/ui/Modal' || (spec === '@/components/ui' && named.some((el) => MODAL_EXPORTS.has((el.propertyName ?? el.name).text)))) {
      modal = true
    }
    const base = spec.startsWith('@/') ? path.join(ROOT, spec.slice(2)) : spec.startsWith('.') ? path.resolve(path.dirname(file), spec) : null
    if (!base || spec.startsWith('@/components/ui')) continue
    const hit = ['.tsx', '.ts', '/index.tsx', '/index.ts'].map((ext) => base + ext).find((p) => fs.existsSync(p))
    if (hit) next.push(hit)
  }
  return { modal, next }
}

describe('dialogs ship only through ui/Modal (or the documented bespoke layers)', () => {
  it('the detector sees every way to declare a dialog, and nothing else', () => {
    const kindsOf = (code: string) => countDialogSites(code, 'fixture.tsx')
    // role literals, any quote style, and role token lists
    expect(kindsOf('const a = <div role="dialog" />')).toEqual({ role: 1 })
    expect(kindsOf("const a = <div role='alertdialog' />")).toEqual({ role: 1 })
    expect(kindsOf('const a = <div role="alertdialog dialog" />')).toEqual({ role: 1 })
    // role={…} expressions (the AlertBell shape the old substring match could not see)
    expect(kindsOf("const a = <div role={isError ? 'alertdialog' : 'dialog'} />")).toEqual({ role: 1 })
    expect(kindsOf("const a = <div role={'dialog'} />")).toEqual({ role: 1 })
    expect(kindsOf('const a = <div role={`dialog`} />')).toEqual({ role: 1 })
    expect(kindsOf("const a = <div role={open && 'dialog'} />")).toEqual({ role: 1 })
    expect(kindsOf('const a = <div role={role} />')).toEqual({ role: 1 })
    expect(kindsOf("const a = <div role={cond ? r : 'status'} />")).toEqual({ role: 1 })
    expect(kindsOf("const a = <div role={(isError ? 'alertdialog' : 'alert') as const} />")).toEqual({ role: 1 })
    expect(kindsOf("const a = <div role={override ?? 'status'} />")).toEqual({ role: 1 })
    expect(kindsOf('const a = <div role={`${x}dialog`} />')).toEqual({ role: 1 })
    // role passed through props objects or the DOM
    expect(kindsOf("const p = { role: 'dialog' }; const a = <div {...p} />")).toEqual({ role: 1 })
    expect(kindsOf("createElement('div', { 'role': 'alertdialog' })")).toEqual({ role: 1 })
    expect(kindsOf("el.setAttribute('role', 'dialog')")).toEqual({ role: 1 })
    expect(kindsOf("const a = <div role={kind === 'error' ? ROLE : 'group'} />")).toEqual({ role: 1 })
    expect(kindsOf('const a = <><div role="dialog" /><div role="dialog" /></>')).toEqual({ role: 2 })
    // native dialogs
    expect(kindsOf('const a = <dialog open>hi</dialog>')).toEqual({ native: 1 })
    expect(kindsOf('const a = <dialog />')).toEqual({ native: 1 })
    expect(kindsOf("document.createElement('dialog')")).toEqual({ native: 1 })
    expect(kindsOf("React.createElement('dialog', null)")).toEqual({ native: 1 })
    // the dialog layer's tokens, in className strings, cx() arguments and template chunks
    expect(kindsOf('const a = <div className="fixed inset-0 z-modal" />')).toEqual({ layer: 1 })
    expect(kindsOf("cx('w-full', 'backdrop:bg-overlay', x)")).toEqual({ layer: 1 })
    expect(kindsOf("const a = 'lg:hidden fixed inset-0 z-30 bg-overlay/50'")).toEqual({ layer: 1 })
    expect(kindsOf('const a = `fixed ${pos} z-modal`')).toEqual({ layer: 1 })
    expect(kindsOf("const a = '[&>div]:z-modal'")).toEqual({ layer: 1 })
    expect(kindsOf("const a = 'data-[open]:bg-overlay'")).toEqual({ layer: 1 })
    expect(kindsOf("const a = '!z-modal'")).toEqual({ layer: 1 })
    expect(kindsOf("const a = 'lg:!z-modal'")).toEqual({ layer: 1 })
    expect(kindsOf('const a = <div className="fixed z-modal" role="dialog" />')).toEqual({ layer: 1, role: 1 })
    // not dialogs
    expect(kindsOf('// role="dialog" in a comment\n/* <dialog> */ const a = 1')).toEqual({})
    expect(kindsOf('const a = <div role="status" aria-haspopup="dialog" />')).toEqual({})
    expect(kindsOf("const a = <div role={variant === 'error' ? 'alert' : 'status'} />")).toEqual({})
    expect(kindsOf("const a = <div role={label ? 'img' : undefined} />")).toEqual({})
    expect(kindsOf("const a = <p role={isError ? 'alert' : undefined} />")).toEqual({})
    expect(kindsOf("const a = <p role={open && 'status'} />")).toEqual({})
    expect(kindsOf('const m = { role: m.role, content }')).toEqual({})
    expect(kindsOf("const m = { role: 'assistant' }")).toEqual({})
    expect(kindsOf("const a = <div role={interactive && 'group'} />")).toEqual({})
    expect(kindsOf('const a = <p>z-modal and bg-overlay in JSX text</p>')).toEqual({})
    expect(kindsOf('const a = <DayDetailDialog onClose={close} />')).toEqual({})
    expect(kindsOf("const s = 'role=\"dialog\"'; el.setAttribute('aria-haspopup', 'dialog')")).toEqual({})
    expect(kindsOf('// bg-overlay z-modal in a comment\nconst a = 1')).toEqual({})
    expect(kindsOf("const a = 'z-modals bg-overlayish text-overlay'")).toEqual({})
    // the non-modal popover shape (BellPopover): a labelled group on z-overlay
    expect(
      kindsOf(
        'const a = <div className="fixed inset-0 z-overlay"><div role="group"><div role={isError ? \'alert\' : undefined} /></div></div>',
      ),
    ).toEqual({})
  })

  it('dialog semantics appear only in allowlisted files', () => {
    const offenders = [...scan()]
      .filter(([file]) => !(file in ALLOW))
      .map(([file, counts]) => `${file}: ${JSON.stringify(counts)}`)
    expect(
      offenders,
      'Compose <Modal> from components/ui instead of hand-rolling a dialog (DESIGN_SYSTEM §4). A popover ' +
        'that is not modal takes no dialog role and rides z-overlay (see AlertBell).',
    ).toEqual([])
  })

  it('nothing DayDetailDialog renders imports ui/Modal (inert beneath the native top layer)', () => {
    const seen = new Set<string>()
    const offenders: string[] = []
    const queue = [path.join(ROOT, 'features/calendar/components/DayDetailDialog.tsx')]
    while (queue.length) {
      const file = queue.pop() as string
      if (seen.has(file)) continue
      seen.add(file)
      const { modal, next } = localImports(file)
      if (modal) offenders.push(path.relative(ROOT, file).split(path.sep).join('/'))
      queue.push(...next)
    }
    expect(seen, 'the walk must reach the bell rendered inside the dialog').toContain(
      path.join(ROOT, 'features/calendar/components/AlertBell.tsx'),
    )
    expect(offenders).toEqual([])
  })

  it('the allowlist is shrink-only', () => {
    expect(Object.keys(ALLOW).length, 'compose <Modal> instead of adding an entry').toBeLessThanOrEqual(MAX_ALLOWLIST_SIZE)
  })

  it.each(Object.entries(ALLOW))('%s still declares exactly its pinned dialog sites', (file, { counts, reason }) => {
    expect(fs.existsSync(path.join(ROOT, file)), `${file} is allowlisted but does not exist`).toBe(true)
    expect(reason.trim().length, `${file} needs a reason`).toBeGreaterThan(0)
    expect(
      scan().get(file) ?? {},
      `${file} drifted from its pin. An extra site is a second hand-rolled dialog — compose <Modal>; ` +
        'a removed one means the pin (or the whole entry) should shrink.',
    ).toEqual(counts)
  })
})
