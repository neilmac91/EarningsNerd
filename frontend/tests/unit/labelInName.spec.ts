import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { bindingResolver, containerEscape } from './astBindings'

/**
 * Label in name (WCAG 2.5.3; E68 (3); lessons/frontend-hidden-name-tails-bring-their-own-space.md rule (c)): a control
 * that shows words keeps them at the start of its accessible name. An `aria-label` replaces the words a control shows,
 * so a control whose label starts with other words ("Source: Quote found in filing" on a chip that shows "Quote found
 * in filing") is named by words a speech user cannot see to say. A control with visible words takes no `aria-label`
 * and extends its name with a hidden tail instead, or takes a label that begins with those words.
 *
 * What it reads, in every tracked .tsx and .jsx file outside tests/ (git ls-files):
 *  - A control named by its content: `<a>`, `<button>`, `<summary>`, a component named `Link`, `…Link` or `…Button`
 *    (next/link's Link, the DS Button, RetryButton), and an element whose static `role` names a control (button, link,
 *    menuitem, tab, checkbox, radio, switch, option, treeitem). Not a field (`select` and the DS `Select`, whose
 *    children are its options, match none of these) and not a container a handler alone marks (a `radiogroup`'s name
 *    is no content of its own).
 *  - Its `aria-label`: the last written of the attribute and an `'aria-label'` entry of a plain spread (an object written
 *    in place, or a same-file const holding one, of named entries that nothing writes after it is made, as the ring scan
 *    reads one), since React applies props in order. The Source chip and the Copilot's citation chip name themselves
 *    that way.
 *  - Its face: the words it shows, read through wrapper elements and fragments. Not face: a visually hidden span
 *    (`sr-only`, unless a `not-sr-only` variant shows it), a keyboard hint (`kbd`, whose shortcut is no part of the
 *    name), a component that closes itself (an icon), and what an `aria-hidden` element shows where it is a status the
 *    name may say in words of its own: digits and glyphs, or a value the label names, read per element (inView()). An
 *    element that shows a word with a letter stays face, whole: a speech user sees it, and it is the label the name must
 *    begin with.
 *  - Both as words and values: a string, a template's chunks, and a const that holds one, in the file (by scope,
 *    `astBindings`) or exported by another module of the app (`@/…` or a relative import); any other expression is a
 *    value, the same value wherever it is written the same way. A conditional is read as its two branches (`cond && x`
 *    as x and nothing), and two conditionals on one condition, one in the label and one in the face, take the same
 *    branch together.
 *
 * The rule, for every pair of a label's and a face's branches: where the face shows words, the label's words begin with
 * them, a value matching only the same value. Past a face's value the label does not repeat (a countdown in "Resend
 * (30s)"), the scan stops: the words before it are the label's start. A face with no words (an icon) is the label's
 * alone. A label the scan cannot read on a control that shows words fails closed, as UNREAD lists.
 *
 * RESIDUE lists the controls that fail today, UNREAD the labels the scan cannot read, each per file with the reason it
 * waits; each list's size equals its cap, so a fix lowers the count and the cap in the same commit (allowlistCapsAreEqualities).
 *
 * Out of reach: a label or a face a prop or a parameter hands in, which goes to UNREAD (planted below); what a caller
 * hands a component of another module that sets its control's label and face from props (ChartControl's and
 * WordingChanges' own controls are in UNREAD; the DS Button passes `aria-label` through, which this reads where it is
 * written); a label a spread it cannot read may set (a props spread, an object built elsewhere, planted below); and a
 * name `aria-labelledby` points at.
 */

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const CONTROL_ROLES = new Set(['button', 'link', 'menuitem', 'menuitemcheckbox', 'menuitemradio', 'tab', 'checkbox', 'radio', 'switch', 'option', 'treeitem'])
/** A component named as a control: next/link's Link, the DS Button and its wrappers, a link component. */
const CONTROL_NAME = /^(?:Link|\w*Button|\w+Link)$/

type Element = ts.JsxElement | ts.JsxSelfClosingElement
/** A word or a value; `hidden` names the run an `aria-hidden` element shows it in, one run per element (see inView()). */
type Token = ({ word: string } | { value: string }) & { hidden?: number }
/** One branch of a label or a face: its tokens, and the condition branches it was read under. */
interface Branch { tokens: Token[]; when: Map<string, boolean> }
/** What a control's label or face reads as: its branches, or null where the scan cannot read it. */
type Reading = Branch[] | null

const openingOf = (el: Element) => (ts.isJsxElement(el) ? el.openingElement : el)
const unwrap = (e: ts.Expression): ts.Expression => {
  while (ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isNonNullExpression(e) || ts.isSatisfiesExpression(e)) e = e.expression
  return e
}
const attrOf = (el: Element, name: string) =>
  openingOf(el).attributes.properties.find((a): a is ts.JsxAttribute => ts.isJsxAttribute(a) && a.name.getText() === name)
const staticAttr = (el: Element, name: string): string | null => {
  const init = attrOf(el, name)?.initializer
  if (!init) return null
  if (ts.isStringLiteral(init)) return init.text
  if (ts.isJsxExpression(init) && init.expression) {
    const e = unwrap(init.expression)
    if (ts.isStringLiteralLike(e)) return e.text
  }
  return null
}
const classText = (el: Element) => attrOf(el, 'className')?.initializer?.getText() ?? ''
/** Words as a reader says them: letters and digits, lower case, apart. */
const words = (text: string): Token[] =>
  text.toLowerCase().replace(/&nbsp;/g, ' ').split(/[^\p{L}\p{N}]+/u).filter(Boolean).map((word) => ({ word }))

const seq = (parts: Reading[]): Reading => {
  let out: Branch[] = [{ tokens: [], when: new Map() }]
  for (const part of parts) {
    if (!part) return null
    const next: Branch[] = []
    for (const a of out) for (const b of part) {
      const when = merge(a.when, b.when)
      if (when) next.push({ tokens: [...a.tokens, ...b.tokens], when })
    }
    // A face of more branches than this reads no clearer for them.
    if (next.length > 32) return null
    out = next
  }
  return out
}
/** Two branches' conditions together, or null where one condition is taken both ways. */
function merge(a: Map<string, boolean>, b: Map<string, boolean>): Map<string, boolean> | null {
  const out = new Map(a)
  for (const [cond, branch] of b) {
    if (out.has(cond) && out.get(cond) !== branch) return null
    out.set(cond, branch)
  }
  return out
}
const one = (tokens: Token[]): Reading => [{ tokens, when: new Map() }]
/** A conditional's reading: each side's branches under its value of the condition, or null where a side is unread. Two
    sides that show nothing read as nothing, so a control of many `cond && <Icon />` keeps one branch. */
function branches(cond: string, yes: Reading, no: Reading): Reading {
  const side = (r: Reading, value: boolean): Reading => r && r.flatMap((b) => {
    const when = merge(b.when, new Map([[cond, value]]))
    return when ? [{ tokens: b.tokens, when }] : []
  })
  const both = [side(yes, true), side(no, false)]
  if (!both[0] || !both[1]) return null
  const all = [...both[0], ...both[1]]
  return all.every((b) => b.tokens.length === 0) ? one([]) : all
}
/** A class list that hides an element from sight at every width: a bare `sr-only` no `not-sr-only` variant undoes
    (`sr-only sm:not-sr-only` shows from sm, so its words are face). */
const visuallyHidden = (cls: string) => /(?<![\w:-])sr-only(?![\w-])/.test(cls) && !/not-sr-only/.test(cls)
/** Whether `aria-hidden` hides an element: written bare, as "true" or as {true}. */
function ariaHidden(el: Element): boolean {
  const attr = attrOf(el, 'aria-hidden')
  if (!attr) return false
  if (!attr.initializer) return true
  if (ts.isStringLiteral(attr.initializer)) return attr.initializer.text === 'true'
  const e = attr.initializer.expression && unwrap(attr.initializer.expression)
  return !!e && (e.kind === ts.SyntaxKind.TrueKeyword || (ts.isStringLiteralLike(e) && e.text === 'true'))
}
/** A plain object's key as React reads it: an identifier's text or a string literal's. undefined for any other key. */
const keyOf = (prop: ts.ObjectLiteralElementLike): string | undefined =>
  prop.name && (ts.isIdentifier(prop.name) || ts.isStringLiteral(prop.name)) ? prop.name.text : undefined

/**
 * Whether a label begins with a face's words. A face's value matches only the same value; past a value the label
 * does not repeat, the words before it are the start. A face that opens with a value fails where the label repeats that
 * value after words of its own ("Add {ticker} to your watchlist" on a chip that shows the ticker), and is out of the
 * scan's reach where the label never names it (what the value holds is unknown). A label value where the face shows
 * words is out of reach too: the value may hold them.
 */
function judge(label: Token[], face: Token[]): 'ok' | 'fail' | 'unread' {
  for (let i = 0; i < face.length; i++) {
    const ft = face[i]
    const lt = label[i]
    if ('value' in ft) {
      if (lt && 'value' in lt && lt.value === ft.value) continue
      if (i > 0) return 'ok'
      return label.some((t) => 'value' in t && t.value === ft.value) ? 'fail' : 'unread'
    }
    if (lt && 'value' in lt) return 'unread'
    if (!(lt && 'word' in lt && lt.word === ft.word)) return 'fail'
  }
  return 'ok'
}

/**
 * The face a label is judged against. A run `aria-hidden` marks drops out whole where it is a status the name may say in
 * words of its own: no word in it holds a letter (a count, "9+") and each value in it is one the label itself names (the
 * bell's count, in "Notifications ({unread} unread)"). One word with a letter keeps the whole run, digits and all, since a
 * reader sees it and it is the control's label (FilingIndex's "SEC.gov", "FY 2024", "10-K"). The scan cannot tell a value
 * that holds words from a count, so a hidden value the label names drops out either way (planted as a gap). With no label
 * to hand (`label` null), a run with a value stays.
 */
function inView(face: Token[], label: Token[] | null): Token[] {
  const status = (t: Token) => ('word' in t ? !/\p{L}/u.test(t.word) : !!label?.some((l) => 'value' in l && l.value === t.value))
  const kept = new Set(face.filter((t) => t.hidden !== undefined && !status(t)).map((t) => t.hidden))
  return face.filter((t) => t.hidden === undefined || kept.has(t.hidden))
}

/** Reads one source's controls. `exportedText` gives a string another module exports, or null. */
export function labelInName(source: string, file: string, exportedText: (specifier: string, name: string) => string | null): { line: number; kind: 'fail' | 'unread'; detail: string }[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, file.endsWith('.jsx') ? ts.ScriptKind.JSX : ts.ScriptKind.TSX)
  const resolve = bindingResolver(sf)
  const imports = new Map<string, { from: string; name: string }>()
  for (const statement of sf.statements) {
    if (!ts.isImportDeclaration(statement) || !statement.importClause?.namedBindings || !ts.isStringLiteral(statement.moduleSpecifier)) continue
    const bindings = statement.importClause.namedBindings
    if (ts.isNamedImports(bindings)) for (const spec of bindings.elements) imports.set(spec.name.text, { from: statement.moduleSpecifier.text, name: (spec.propertyName ?? spec.name).text })
  }

  /** The runs aria-hidden elements show, numbered as the scan meets them (one per element, in each branch it shows in). */
  let hiddenRuns = 0

  /** An expression's reading: its words where they are known, a value where not, its branches for a conditional. */
  const read = (expr: ts.Expression, seen = new Set<ts.Node>()): Reading => {
    const e = unwrap(expr)
    if (ts.isStringLiteralLike(e)) return one(words(e.text))
    if (ts.isTemplateExpression(e)) {
      return seq([one(words(e.head.text)), ...e.templateSpans.flatMap((span) => [read(span.expression, seen), one(words(span.literal.text))])])
    }
    if (ts.isConditionalExpression(e)) return branches(e.condition.getText(), read(e.whenTrue, seen), read(e.whenFalse, seen))
    if (ts.isIdentifier(e) && !seen.has(e)) {
      const binding = resolve(e)
      if (binding?.init && ts.isVariableDeclaration(binding.decl) && binding.decl.parent.flags & ts.NodeFlags.Const) {
        const init = unwrap(binding.init)
        if (ts.isStringLiteralLike(init) || ts.isTemplateExpression(init) || ts.isConditionalExpression(init)) return read(init, new Set([...seen, e]))
      }
      const imported = imports.get(e.text)
      if (!binding && imported) {
        const text = exportedText(imported.from, imported.name)
        if (text != null) return one(words(text))
      }
    }
    return one([{ value: e.getText().replace(/\s+/g, ' ') }])
  }

  /** What one expression in a face shows: JSX its face, null nothing, anything else as read() reads it. */
  const shown = (x: ts.Expression): Reading => {
    const u = unwrap(x)
    if (ts.isJsxElement(u) || ts.isJsxSelfClosingElement(u) || ts.isJsxFragment(u)) return face([u as ts.JsxChild])
    if (u.kind === ts.SyntaxKind.NullKeyword) return one([])
    return read(u)
  }
  /** A face's reading: the words and values its children show. */
  const face = (nodes: readonly ts.JsxChild[]): Reading =>
    seq(nodes.map((node): Reading => {
      if (ts.isJsxText(node)) return one(words(node.text))
      if (ts.isJsxExpression(node)) {
        if (!node.expression) return one([])
        const e = unwrap(node.expression)
        // `cond && x`: x where the condition holds, nothing where it does not.
        if (ts.isBinaryExpression(e) && e.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken) return branches(e.left.getText(), shown(e.right), one([]))
        if (ts.isConditionalExpression(e)) return branches(e.condition.getText(), shown(e.whenTrue), shown(e.whenFalse))
        // A same-file const holding JSX (`const chipInner = (<>…</>)`) is the face it holds.
        if (ts.isIdentifier(e)) {
          const binding = resolve(e)
          const init = binding?.init && unwrap(binding.init)
          if (init && (ts.isJsxElement(init) || ts.isJsxSelfClosingElement(init) || ts.isJsxFragment(init))) return face([init as ts.JsxChild])
        }
        return read(e)
      }
      if (ts.isJsxFragment(node)) return face(node.children)
      if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
        if (openingOf(node).tagName.getText() === 'kbd' || visuallyHidden(classText(node))) return one([])
        if (ts.isJsxSelfClosingElement(node)) return one([])
        const inner = face(node.children)
        // What aria-hidden marks is one run, which inView() keeps or drops whole against each label; an outer element's
        // run takes in an inner one's.
        if (!ariaHidden(node)) return inner
        const run = ++hiddenRuns
        return inner && inner.map((b) => ({ tokens: b.tokens.map((t): Token => ({ ...t, hidden: run })), when: b.when }))
      }
      return one([])
    }))

  /** A props spread the scan reads: an object written in place, or a same-file const holding one, of named entries only
      (no spread of its own, no computed key), that nothing writes after it is made (containerEscape), as the ring scan
      reads one. undefined: a spread it cannot read (a prop, an object built elsewhere). */
  const plainSpread = (spread: ts.JsxSpreadAttribute): ts.ObjectLiteralExpression | undefined => {
    let held: ts.Expression | undefined = unwrap(spread.expression)
    if (ts.isIdentifier(held)) {
      const binding = resolve(held)
      held = binding?.init && ts.isVariableDeclaration(binding.decl) && ts.getCombinedNodeFlags(binding.decl) & ts.NodeFlags.Const ? unwrap(binding.init) : undefined
    }
    if (!held || !ts.isObjectLiteralExpression(held)) return undefined
    const named = held.properties.every((p) => (ts.isPropertyAssignment(p) || ts.isShorthandPropertyAssignment(p) || ts.isMethodDeclaration(p)) && keyOf(p) !== undefined)
    return named && !containerEscape(held, sf, resolve) ? held : undefined
  }
  /** The aria-label a control is given: the last written of its attribute and a plain spread's entry, as React applies
      props in order. null where none is written, or the last is empty. */
  const labelOf = (el: Element): ts.Expression | null => {
    let label: ts.Expression | null = null
    for (const p of openingOf(el).attributes.properties) {
      if (ts.isJsxAttribute(p) && p.name.getText() === 'aria-label') {
        label = !p.initializer ? null : ts.isStringLiteral(p.initializer) ? p.initializer : p.initializer.expression ?? null
      } else if (ts.isJsxSpreadAttribute(p)) {
        for (const entry of plainSpread(p)?.properties ?? []) {
          if (keyOf(entry) !== 'aria-label') continue
          label = ts.isPropertyAssignment(entry) ? entry.initializer : ts.isShorthandPropertyAssignment(entry) ? entry.name : null
        }
      }
    }
    return label
  }

  const isControl = (el: Element): boolean => {
    const tag = openingOf(el).tagName.getText().split('.').pop()!
    if (tag === 'a' || tag === 'button' || tag === 'summary' || CONTROL_NAME.test(tag)) return true
    const role = staticAttr(el, 'role')
    return role != null && role.split(/\s+/).some((r) => CONTROL_ROLES.has(r))
  }

  const findings: { line: number; kind: 'fail' | 'unread'; detail: string }[] = []
  const show = (tokens: Token[]) => tokens.map((t) => ('word' in t ? t.word : `{${t.value}}`)).join(' ')
  const visit = (node: ts.Node): void => {
    if ((ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) && isControl(node)) {
      const labelExpr = labelOf(node)
      if (labelExpr) {
        const line = sf.getLineAndCharacterOfPosition(node.getStart()).line + 1
        const faces = ts.isJsxElement(node) ? face(node.children) : one([])
        const labels = read(labelExpr)
        const shows = faces === null || faces.some((b) => inView(b.tokens, null).length > 0)
        if (shows) {
          if (!faces || !labels) findings.push({ line, kind: 'unread', detail: `label ${labelExpr.getText().slice(0, 80)}` })
          else {
            // One finding a control: the first pair of branches that fails, else the first the scan cannot judge.
            let failed: string | null = null
            let unjudged: string | null = null
            for (const l of labels) for (const f of faces) {
              const visible = inView(f.tokens, l.tokens)
              if (!merge(l.when, f.when) || visible.length === 0) continue
              const verdict = judge(l.tokens, visible)
              const detail = `shows "${show(visible)}", named "${show(l.tokens)}"`
              if (verdict === 'fail') failed ??= detail
              else if (verdict === 'unread') unjudged ??= detail
            }
            if (failed) findings.push({ line, kind: 'fail', detail: failed })
            else if (unjudged) findings.push({ line, kind: 'unread', detail: unjudged })
          }
        }
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return findings
}

/** A string another module of the app exports as a const, read from its source. */
function exportedTextFrom(fromFile: string) {
  return (specifier: string, name: string): string | null => {
    const base = specifier.startsWith('@/') ? path.join(FRONTEND, specifier.slice(2)) : specifier.startsWith('.') ? path.resolve(path.dirname(fromFile), specifier) : null
    if (!base) return null
    const file = ['.ts', '.tsx', '/index.ts', '/index.tsx'].map((ext) => base + ext).find(existsSync)
    if (!file) return null
    const sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true)
    for (const statement of sf.statements) {
      if (!ts.isVariableStatement(statement) || !statement.modifiers?.some((m) => m.kind === ts.SyntaxKind.ExportKeyword)) continue
      if (!(statement.declarationList.flags & ts.NodeFlags.Const)) continue
      for (const decl of statement.declarationList.declarations) {
        if (ts.isIdentifier(decl.name) && decl.name.text === name && decl.initializer) {
          const init = unwrap(decl.initializer)
          if (ts.isStringLiteralLike(init)) return init.text
        }
      }
    }
    return null
  }
}

/** Every tracked .tsx and .jsx file outside tests/. */
const SOURCES = execFileSync('git', ['ls-files', '*.tsx', '*.jsx'], { cwd: FRONTEND, encoding: 'utf8' })
  .split('\n')
  .filter((rel) => rel && !rel.startsWith('tests/'))

/** The controls that fail today, per file, each with what waits on its fix (E68 (3)). Each fix's words are chief design's. */
const RESIDUE: Record<string, number> = {
  'features/analysis/components/DataNotesLink.tsx': 1, // the Notes chip shows "Notes a, b" and is named "Review data notes a, b" (D-061's chip)
  'features/analysis/components/NarrativePane.tsx': 1, // the citation chip shows "[1]" and is named "Citation 1: …", which says what the number is before it
  'features/feedback/components/FeedbackWidget.tsx': 1, // the launcher shows "Feedback" from sm and is named "Send feedback" or "Close feedback", where aria-expanded already says which
  'features/filings/components/FilingIndex.tsx': 1, // the filing row's SEC.gov link shows "SEC.gov" from 48rem (its only words, marked aria-hidden) and is named "View the 10-K filed … on SEC.gov (opens in a new tab)"
  'features/filings/components/SourceTrace.tsx': 4, // the Source chip's four triggers (the sheet's, the in-app jump, the link, the popover's) show its label ("Quote found in filing") and are named "Source: …", the link adding "(opens in a new tab)"; the demo below copies it
  'features/filings/components/copilot/CitationChip.tsx': 3, // the Copilot's citation chip (its jump, its link, its popover trigger) shows "[1]" and is named "Citation 1: …", as NarrativePane's is
  'features/marketing/components/TraceToSourceDemo.tsx': 1, // the landing's demo chip shows "Quote found in filing" and is named "Source: Quote found in filing", as SourceTrace's link is
  'features/notifications/components/NotificationBell.tsx': 1, // the bell's count badge ("3", "9+") is face and the name opens "Notifications (3 unread)"; the badge is a status the name already counts, so aria-hidden on it is the likely fix (inView())
  'features/watchlist/components/PopularTickerChips.tsx': 1, // the chip shows the ticker and is named "Add AAPL to your watchlist"
}
const RESIDUE_MAX = { files: 9, controls: 14 }
/** The labels the scan cannot read on a control that shows words, per file, with why. */
const UNREAD: Record<string, number> = {
  'features/admin/components/FeedbackRow.tsx': 1, // admin: the row's link opens with the message's preview, data, then shows "View details", and is named "View details for feedback N"
  'features/analysis/components/ChartControl.tsx': 1, // its label and face are its props (label, children), set by each caller
  'features/analysis/components/SourceValue.tsx': 1, // its face is its children, a prop, and its label opens with the label prop
  'features/auth/components/UserMenu.tsx': 1, // the account menu shows the reader's initials, data, and is named "Account menu"
  'features/calendar/components/MonthView.tsx': 1, // a day cell shows its date and events and is named by a label it computes
  'features/filings/components/WordingChanges.tsx': 1, // its label and face are its props (ariaLabel, children), set by each caller
}
const UNREAD_MAX = { files: 6, labels: 6 }

describe('label in name: a control that shows words keeps them at the start of its name (WCAG 2.5.3, E68 (3))', () => {
  const scan = SOURCES.map((rel) => {
    const file = path.join(FRONTEND, rel)
    return { rel, findings: labelInName(readFileSync(file, 'utf8'), rel, exportedTextFrom(file)) }
  })
  it('every control in the app, but for RESIDUE and UNREAD', () => {
    const problems: string[] = []
    for (const [kind, list] of [['fail', RESIDUE], ['unread', UNREAD]] as const) {
      const found = new Map<string, string[]>()
      for (const { rel, findings } of scan) for (const f of findings) if (f.kind === kind) found.set(rel, [...(found.get(rel) ?? []), `${rel}:${f.line} ${f.detail}`])
      for (const [rel, lines] of found) {
        const allowed = list[rel] ?? 0
        if (lines.length > allowed) problems.push(`${lines.length} ${kind} in ${rel}, ${allowed} listed:\n  ${lines.join('\n  ')}`)
        else if (lines.length < allowed) problems.push(`${lines.length} ${kind} in ${rel}, ${allowed} listed: lower its count`)
      }
      for (const rel of Object.keys(list)) if (!found.has(rel)) problems.push(`${rel} has no ${kind} left: delete its line`)
    }
    expect(problems, problems.join('\n')).toEqual([])
  })
  it('each list is as long as its cap', () => {
    expect({ files: Object.keys(RESIDUE).length, controls: Object.values(RESIDUE).reduce((a, b) => a + b, 0) }).toEqual(RESIDUE_MAX)
    expect({ files: Object.keys(UNREAD).length, labels: Object.values(UNREAD).reduce((a, b) => a + b, 0) }).toEqual(UNREAD_MAX)
  })
})

describe('the label-in-name reader, on planted controls', () => {
  /** An app module exporting LABEL, as lib/evidenceLabels.ts exports PASSAGE_FOUND. */
  const exported = (specifier: string, name: string) => (specifier === '@/lib/labels' && name === 'LABEL' ? 'Quote found in filing' : null)
  const verdict = (jsx: string, head = '') => {
    const findings = labelInName(`${head}\nexport function Probe({ open, name, t, label, children, s }: any) { return (${jsx}) }`, 'probe.tsx', exported)
    return findings.length ? findings[0].kind : 'ok'
  }

  it.each([
    ['a label of other words', '<button aria-label="Close dialog">Cancel</button>', 'fail'],
    ['a label that begins with the words', '<button aria-label="Cancel and close">Cancel</button>', 'ok'],
    ['case and punctuation aside', '<button aria-label="Ask this filing.">Ask this Filing</button>', 'ok'],
    ['an icon alone, named by its label', '<button aria-label="Close"><XIcon /></button>', 'ok'],
    ['a hidden tail, no label', "<button>Open filing{' '}<span className=\"sr-only\">(10-K)</span></button>", 'ok'],
    ['a hidden span left out of the face', '<button aria-label="Open filing">Open filing<span className="sr-only">, 10-K</span></button>', 'ok'],
    ['a keyboard hint left out of the name', '<button aria-label="Ask this Filing">Ask this Filing<kbd>⌘K</kbd></button>', 'ok'],
    ['a count marked aria-hidden', '<button aria-label="Notifications, 3 unread"><BellIcon /><span aria-hidden="true">3</span></button>', 'ok'],
    ['words marked aria-hidden, still the face', '<a href="/x" aria-label="View the filing on SEC.gov"><span aria-hidden="true">SEC.gov</span><ArrowIcon /></a>', 'fail'],
    ['a hidden run of words and digits, read whole', '<button aria-label="FY 2025 report"><span aria-hidden="true">FY 2024</span></button>', 'fail'],
    ['a hidden form code the label begins with', '<button aria-label="10-K filing"><span aria-hidden="true">10-K</span></button>', 'ok'],
    ['a hidden value the label names, a count it says', '<button aria-label={`Notifications (${t} unread)`}><BellIcon /><span aria-hidden="true">{t}</span></button>', 'ok'],
    ['a hidden value the label names, though it may hold words (a gap)', '<button aria-label={`Add ${t} to your watchlist`}><span aria-hidden="true">{t}</span></button>', 'ok'],
    ['a hidden value the label does not name', '<button aria-label="Open the list"><span aria-hidden="true">{t}</span></button>', 'unread'],
    ['a word shown only under a condition', "<button aria-label=\"Hide notes\">{open && 'Hide'} notes</button>", 'fail'],
    ['a condition the label and an && share', "<button aria-label={open ? 'Hide notes' : 'Notes'}>{open && 'Hide'} notes</button>", 'ok'],
    ['a hidden span a not-sr-only variant shows', '<button aria-label="Return to the list"><ArrowIcon /><span className="sr-only sm:not-sr-only">Back</span></button>', 'fail'],
    ['a template that repeats the value', '<button aria-label={`Remove ${name}`}>Remove {name}</button>', 'ok'],
    ['a label that puts words before the value shown', '<button aria-label={`Add ${t} to your watchlist`}>{t}</button>', 'fail'],
    ['words before a value the label does not repeat (a countdown)', "<button aria-label=\"Resend invite\">Resend {s > 0 ? `(${s}s)` : ''}</button>", 'ok'],
    ['a label and a face from two props', '<button aria-label={label}>{children}</button>', 'unread'],
    ['a label the scan cannot read', '<button aria-label={labelFor(name)}>Revoke</button>', 'unread'],
    ['one condition, both branches together', "<button aria-label={open ? 'Hide notes' : 'Show notes'}>{open ? 'Hide' : 'Show'}</button>", 'ok'],
    ['a conditional label on a fixed face', "<button aria-label={open ? 'Close feedback' : 'Send feedback'}>Feedback</button>", 'fail'],
    ['a field and its options', '<Select aria-label="Filter by form"><option>All forms</option></Select>', 'ok'],
    ['a group named on its own', '<div role="radiogroup" aria-label="Billing period"><button>Monthly</button></div>', 'ok'],
    ['an element whose role names a control', '<div role="tab" aria-label="Overview tab">Summary</div>', 'fail'],
    ['a link component', '<Link href="/pricing" aria-label="Go to pricing">Pricing</Link>', 'fail'],
    ['a same-file JSX const as the face', '<a href="/x" aria-label={`Source: ${label}`}>{inner}</a>', 'fail'],
  ] as const)('%s', (_name, jsx, expected) => {
    const head = jsx.includes('{inner}') ? 'const inner = (<><QuotesIcon />{"Quote"}</>)' : ''
    expect(verdict(jsx, head)).toBe(expected)
  })

  it('reads a const the file holds and one another module of the app exports', () => {
    expect(verdict("<button aria-label={`Source: ${PASSAGE}`}>{PASSAGE}</button>", "const PASSAGE = 'Quote found in filing'")).toBe('fail')
    expect(verdict('<button aria-label={`Source: ${LABEL}`}>{LABEL}</button>', "import { LABEL } from '@/lib/labels'")).toBe('fail')
    expect(verdict('<button aria-label={`${LABEL}, opens the source`}>{LABEL}</button>', "import { LABEL } from '@/lib/labels'")).toBe('ok')
    // Where the label writes the words out, only the const's words can decide: unread without them.
    expect(verdict('<button aria-label="Quote found in filing, opens the source">{LABEL}</button>', "import { LABEL } from '@/lib/labels'")).toBe('ok')
    expect(verdict('<button aria-label="Open the source">{LABEL}</button>', "import { LABEL } from '@/lib/labels'")).toBe('fail')
    expect(verdict('<button aria-label="Open the source">{OTHER}</button>', "import { OTHER } from '@/lib/labels'")).toBe('unread')
  })

  it('reads a label a plain spread sets, the last written winning', () => {
    const head = "const common = { 'aria-label': 'Close dialog', className: 'chip' }"
    expect(verdict('<button {...common}>Cancel</button>', head)).toBe('fail')
    expect(verdict('<button {...common} aria-label="Cancel and close">Cancel</button>', head)).toBe('ok')
    expect(verdict('<button aria-label="Cancel and close" {...common}>Cancel</button>', head)).toBe('fail')
    expect(verdict("<button {...{ 'aria-label': 'Close dialog' }}>Cancel</button>")).toBe('fail')
    // Out of reach, planted: a props spread, and an object something writes after it is made.
    expect(verdict('<button {...props}>Cancel</button>')).toBe('ok')
    expect(verdict('<button {...common}>Cancel</button>', `${head}\ncommon.className = 'other'`)).toBe('ok')
  })

  // Out of reach, planted: the scan cannot read a face a prop hands in, so the control goes to UNREAD whatever its label says.
  it('leaves a label and a face handed in by props to UNREAD, never to a verdict', () => {
    expect(verdict('<button aria-label={`Close ${label}`}>{children}</button>')).toBe('unread')
  })
})
