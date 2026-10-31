import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { componentTag, ELEMENT_MAKERS, heldValues, knownAsIn, leavesOf, propertyOf, scopeResolver, unwrapHeld, writtenChild, type Fn, type Held } from './heldValues'

/**
 * The missing-value token renders through one element (E88, CLAUDE.md rule 12): `MissingValue`
 * (components/ui/MissingValue.tsx) draws the token aria-hidden beside words for assistive tech, "unavailable" by
 * default or the site's own, so a screen reader never reads "em dash" for a value the page does not have
 * (frontend/DESIGN_SYSTEM.md §4, Missing value). The element's aria-hidden token is the one place the app writes it;
 * this gate fails the token wherever else it renders into the page, alone in a cell or not
 * (no-em-dash-copy.spec.ts fails it only where it is joined into copy, and reads the lone token as the convention).
 *
 * Every .ts and .tsx file under app/, components/, features/, lib/ and hooks/ that spells the token (the dash, a
 * `\u2014` escape, an entity JSX decodes, `&mdash;`, `&#8212;` or `&#x2014;`, or `String.fromCharCode(0x2014)`) is
 * read through the shared reader (tests/unit/heldValues.ts), which follows React's state for every gate (E159: what
 * useState, useReducer, useRef and the other hooks its header names keep), with `passThrough` on, so a value is followed from every
 * place a name is given it to every place it renders, and a call the reader cannot see is taken to give back what it
 * is handed. The token renders, and fails where it does, as:
 *  - JSX text, or an expression child whose value may hold it, of an intrinsic element, a fragment or a component
 *    the scan cannot read (an import, React's Fragment or Suspense): the dash or an entity as text, a literal or a
 *    template, a fallback (`??`, `||`), a conditional's arm, `&&`'s right, an array's elements, a name however it is
 *    given the token (a declaration, an assignment, `+=`, a default, a destructuring, a same-file call's argument, a
 *    same-file component's props and children, a loop's element, what is put in an object after it is made), a
 *    same-file function's return (a formatter's fallback, a callback's: `map`, `useMemo`), and a value built by code
 *    the reader cannot follow (an imported formatter handed the token as its fallback, `formatLocalDate(v, f, '—')`,
 *    `String()`, a method such as `trim()`, a template literal, `+`);
 *  - children given by props (`children` where none are written, a spread's) and `dangerouslySetInnerHTML`;
 *  - an intrinsic element's other props that show as text (HOST_TEXT_PROPS): a field's `value`, `defaultValue` and
 *    `placeholder` (an input's, a textarea's), an option's, an optgroup's or a track's `label`, and an iframe's
 *    `srcDoc`;
 *  - every prop of a component the scan cannot read but the attribute ones (ATTRIBUTE_PROPS: key, ref, className,
 *    style, id, role, tabIndex, htmlFor, href, src, type, name, aria-*, data-*, on*), since it may render any other
 *    (a title, a label, a fallback, a column's header), and the return of every function such a prop holds (a
 *    DataTable column's `render`), so `MissingValue` handed the token as its words fails too;
 *  - React's element calls (createElement, cloneElement and the JSX runtime's jsx, jsxs and jsxDEV, which app code
 *    may not write: earningsnerd/elements-built-with-jsx): their children and props alike;
 *  - what a same-file component returns, one rendered in the file or named for one (PascalCase), so a pass-through
 *    (`({ children }) => children`) handed the token, or a component that returns it as text, fails at its return.
 * A same-file component's element is followed into the component (its props and children bind its parameters), so
 * the token fails where the component renders it, and an element is a value of its own, read where it is written. A
 * same-file function called through Function.prototype's `call` or `apply`, or a `bind` of it, is read as the function
 * (the shared reader), so its fallback fails where the call renders it (M89).
 *
 * The element's own token is the one sanctioned site, pinned: ELEMENT_FILE holds exactly one finding, its JSX text
 * inside an aria-hidden element, and a second, or none, fails.
 *
 * Over-reads that fail closed: a prop of a component the scan cannot read that never renders as text (a DataTable's
 * `rowKey`), a function's return such a prop never renders, a value an imported function is handed but never gives
 * back, a `value` an intrinsic element never shows (a hidden input's, a checkbox's, a button's, an option's in a
 * select), and a member read by a key the scan cannot read, which may be any member. Out of scope by design, clean:
 * an intrinsic element's other attributes (an aria-label, a title, an alt, a CSV for a download's href), which are
 * not the page's text, so a formatter's string return keeps its fallback for those callers; a comparison and a parse
 * set (lib/format.ts's MISSING_TOKENS); data that arrives at run time (a filing's own table cell, which SummaryBlocks
 * renders verbatim and where a dash often means nil); and stylesheets, since the gate reads .ts and .tsx. Out of
 * reach, each planted as a gap in FORMS below and review-checked: a token that crosses
 * modules (an imported formatter's own fallback, an imported constant, a render prop handed to a component in another
 * module); a class's field read through `this`; a promise's `then`; a generator's `yield`; a missing value
 * in another glyph (a hyphen, an en dash, which are also signs and ranges; the voice guide's token is the em dash);
 * a value rendered outside the tree (a toast's message, an imperative `textContent`); a tag that may be a same-file
 * component or an import (`cond ? Local : Imported`), read as the same-file one; and the element itself set beside a
 * unit or a sign (`{v ?? <MissingValue />} sh`, which still shows "— sh"), clean here wherever it renders, which the
 * voice guide forbids and no-em-dash-copy.spec.ts names as its own gap.
 */

const FRONTEND_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCANNED_DIRS = ['app', 'components', 'features', 'lib', 'hooks']
/** The element, and the one file that may write the token. */
const ELEMENT_FILE = 'components/ui/MissingValue.tsx'
const TOKEN = '—'
/** A file that may spell the token; the reader runs on these alone. */
const SPELLINGS = /—|\\u2014|\\u\{0*2014\}|&mdash;|&#0*8212;|&#x0*2014;|fromCharCode|fromCodePoint/i
/** The props of a component the scan cannot read that never render as text: they reach an attribute, a handler or
 *  React itself. Every other prop may render. */
const ATTRIBUTE_PROPS = /^(?:key|ref|className|style|id|role|tabIndex|htmlFor|href|src|type|name|aria-.+|data-.+|on[A-Z].*)$/
/** The props an intrinsic element shows as text: its children and inner HTML, a field's value, default value and
 *  placeholder, an option's, an optgroup's or a track's label and an iframe's document. Its other attributes are not
 *  the page's text. */
const HOST_TEXT_PROPS = ['children', 'dangerouslySetInnerHTML', 'value', 'defaultValue', 'placeholder', 'label', 'srcDoc']

/** JSX text and a JSX attribute's string with the entities JSX decodes into the token; other text is as written. */
const decoded = (text: string) => text.replace(/&(?:mdash|#0*8212|#x0*2014);/gi, TOKEN)
const isTokenText = (text: string) => decoded(text).trim() === TOKEN

function sourceFiles(dir: string): string[] {
  if (!existsSync(dir)) return []
  const out: string[] = []
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry)
    if (statSync(full).isDirectory()) out.push(...sourceFiles(full))
    else if (/\.(ts|tsx)$/.test(entry) && !/\.(spec|test)\.(ts|tsx)$|\.d\.ts$/.test(entry)) out.push(full)
  }
  return out
}

type Leaf = 'token' | 'element'
/** Where a parent's children go: an intrinsic element's (a string to React), a same-file component's (followed into
    it) or a component the scan cannot read. */
type Kind = 'host' | 'own' | 'unread'
interface Finding {
  node: ts.Node
  line: number
  shown: string
}

/** Every place the token renders in one source outside the element (see the header). */
function findingsIn(text: string, file: string): Finding[] {
  if (!SPELLINGS.test(text)) return []
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
  const declarationOf = scopeResolver(source)
  const knownAs = knownAsIn(declarationOf)

  /** Whether a name reads React loaded at run time (`require('react')`, `await import('react')`). */
  const loadsReact = (id: ts.Identifier) => {
    const declaration = declarationOf(id)
    const init = declaration && ts.isVariableDeclaration(declaration) && declaration.initializer ? unwrapHeld(declaration.initializer) : undefined
    const load = init && ts.isAwaitExpression(init) ? unwrapHeld(init.expression) : init
    const loaded = load && ts.isCallExpression(load) ? load.arguments[0] : undefined
    const loader = !!load && ts.isCallExpression(load) && (load.expression.kind === ts.SyntaxKind.ImportKeyword || (ts.isIdentifier(load.expression) && load.expression.text === 'require'))
    return loader && !!loaded && ts.isStringLiteralLike(loaded) && /^react(?:\/|$)/.test(loaded.text)
  }
  const isImport = (declaration: ts.Node) => ts.isImportSpecifier(declaration) || ts.isImportClause(declaration) || ts.isNamespaceImport(declaration)
  /** React's element call a call is, by the name its callee is known by: a same-file function of that name, or a
      method of a same-file object, is the file's own. */
  const elementCall = (call: ts.CallExpression): string | undefined => {
    const name = knownAs(call.expression)?.name
    if (!name || (!ELEMENT_MAKERS.has(name) && name !== 'cloneElement')) return undefined
    const callee = unwrapHeld(call.expression)
    if (ts.isIdentifier(callee)) {
      const declaration = declarationOf(callee)
      const init = declaration && ts.isVariableDeclaration(declaration) && declaration.initializer ? unwrapHeld(declaration.initializer) : undefined
      if (declaration && (ts.isFunctionDeclaration(declaration) || (init && (ts.isArrowFunction(init) || ts.isFunctionExpression(init))))) return undefined
    } else if (ts.isPropertyAccessExpression(callee) || ts.isElementAccessExpression(callee)) {
      const base = unwrapHeld(callee.expression)
      const declaration = ts.isIdentifier(base) ? declarationOf(base) : undefined
      if (ts.isIdentifier(base) && declaration && !isImport(declaration) && !loadsReact(base)) return undefined
    }
    return name
  }
  /** `String.fromCharCode(0x2014)` or `String.fromCodePoint(0x2014)` on the global String. */
  const charCodeToken = (call: ts.CallExpression): boolean => {
    const callee = unwrapHeld(call.expression)
    if (!ts.isPropertyAccessExpression(callee) || !['fromCharCode', 'fromCodePoint'].includes(callee.name.text)) return false
    const base = unwrapHeld(callee.expression)
    const [code] = call.arguments
    return ts.isIdentifier(base) && base.text === 'String' && !declarationOf(base) && call.arguments.length === 1 && !!code && ts.isNumericLiteral(code) && Number(code.text) === 0x2014
  }
  const isToken = (e: ts.Expression): boolean => {
    if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) return (ts.isJsxAttribute(e.parent) ? decoded(e.text) : e.text).trim() === TOKEN
    return ts.isCallExpression(e) && charCodeToken(e)
  }
  const values = heldValues<Leaf>(
    source,
    (e) => {
      if (isToken(e)) return ['token']
      // An element is a value of its own: its children are read where they are written, so a held or returned element
      // is never read twice. A same-file component's element binds the component's parameters, followed there.
      if (ts.isJsxElement(e) || ts.isJsxSelfClosingElement(e) || ts.isJsxFragment(e)) return ['element']
      return ts.isCallExpression(e) && elementCall(e) ? ['element'] : undefined
    },
    { textLeaf: (jsxText) => (isTokenText(jsxText.text) ? ['token'] : undefined), passThrough: true },
  )
  const holds = (e: ts.Expression | undefined) => !!e && leavesOf(values.valueOf(e)).has('token')
  const kindOfType = (type: ts.Expression | undefined): Kind => (type && values.valueOf(type).fns?.size ? 'own' : 'unread')
  const kindOf = (opening: ts.JsxOpeningLikeElement): Kind => {
    const tag = componentTag(opening)
    return tag ? kindOfType(tag) : 'host'
  }
  const callKind = (call: ts.CallExpression, name: string): Kind => {
    const [type] = call.arguments
    if (name === 'cloneElement' || !type || ts.isSpreadElement(type)) return 'unread'
    return ts.isStringLiteralLike(unwrapHeld(type)) ? 'host' : kindOfType(type)
  }
  /** Whether a prop renders: an intrinsic element renders its children (when none are written) and the other props it
      shows as text (HOST_TEXT_PROPS), a component the scan cannot read any prop but the attribute ones. */
  const renders = (kind: Kind, prop: string, written: boolean): boolean => {
    if (prop === 'children') return !written
    return kind === 'host' ? HOST_TEXT_PROPS.includes(prop) : !ATTRIBUTE_PROPS.test(prop)
  }

  const findings: Finding[] = []
  const seen = new Set<ts.Node>()
  const flag = (node: ts.Node, shown: string) => {
    if (seen.has(node)) return
    seen.add(node)
    const { line } = source.getLineAndCharacterOfPosition(node.getStart(source))
    findings.push({ node, line: line + 1, shown: shown.replace(/\s+/g, ' ').trim().slice(0, 80) })
  }
  /** What a function returns: an arrow's expression body, and each `return` outside the functions nested in it. */
  const returnsOf = (fn: Fn): ts.Expression[] => {
    if (!fn.body) return []
    if (!ts.isBlock(fn.body)) return [fn.body]
    const out: ts.Expression[] = []
    const walk = (n: ts.Node): void => {
      if (ts.isFunctionLike(n)) return
      if (ts.isReturnStatement(n) && n.expression) out.push(n.expression)
      ts.forEachChild(n, walk)
    }
    ts.forEachChild(fn.body, walk)
    return out
  }
  /** Every function a value may be, its properties' and elements' included. */
  const fnsIn = (value: Held<Leaf>, out = new Set<Fn>(), visited = new Set<Held<Leaf>>()): Set<Fn> => {
    if (visited.has(value)) return out
    visited.add(value)
    for (const fn of value.fns ?? []) out.add(fn)
    for (const prop of value.props?.values() ?? []) fnsIn(prop, out, visited)
    return out
  }
  const returnsToken = (fn: Fn) => {
    for (const r of returnsOf(fn)) if (holds(r)) flag(r, r.getText(source))
  }
  /** A prop given to an element: the token in what renders, and in what any function in it returns for a component
      the scan cannot read. */
  const prop = (kind: Kind, name: string, written: boolean, value: Held<Leaf>, at: ts.Node) => {
    if (!renders(kind, name, written)) return
    if (leavesOf(value).has('token')) flag(at, at.getText(source))
    if (kind === 'unread') fnsIn(value).forEach(returnsToken)
  }
  const element = (el: ts.JsxElement | ts.JsxSelfClosingElement) => {
    const opening = ts.isJsxElement(el) ? el.openingElement : el
    const kind = kindOf(opening)
    if (kind === 'own') return
    const written = ts.isJsxElement(el) && el.children.some(writtenChild)
    for (const attr of opening.attributes.properties) {
      if (ts.isJsxSpreadAttribute(attr)) {
        const spread = values.valueOf(attr.expression)
        const keys = kind === 'host' ? HOST_TEXT_PROPS : [...(spread.props?.keys() ?? [])]
        for (const key of keys) prop(kind, key, written, propertyOf(spread, key), attr)
        continue
      }
      const init = attr.initializer
      const expression = !init ? undefined : ts.isJsxExpression(init) ? init.expression : init
      if (expression) prop(kind, attr.name.getText(source), written, values.valueOf(expression), attr)
    }
  }
  const call = (node: ts.CallExpression) => {
    const name = elementCall(node)
    if (!name) return
    const kind = callKind(node, name)
    if (kind === 'own') return
    const args = node.arguments
    const handed = name === 'createElement' || name === 'cloneElement' ? args.slice(2) : []
    for (const a of handed) if (holds(ts.isSpreadElement(a) ? a.expression : a)) flag(a, a.getText(source))
    const props = args[1] && !ts.isSpreadElement(args[1]) ? args[1] : undefined
    if (!props) return
    const value = values.valueOf(props)
    const keys = kind === 'host' ? HOST_TEXT_PROPS : [...(value.props?.keys() ?? [])]
    for (const key of keys) prop(kind, key, handed.length > 0, propertyOf(value, key), props)
  }
  /** Whether a parent renders its children here: a fragment, an intrinsic element and a component the scan cannot
      read do; a same-file component's children bind its parameters and are followed into it. */
  const rendersChildren = (parent: ts.Node) => ts.isJsxFragment(parent) || (ts.isJsxElement(parent) && kindOf(parent.openingElement) !== 'own')

  // The same-file components: each rendered here (a JSX tag's or an element call's type) or named for one.
  const components = new Set<Fn>()
  const collect = (node: ts.Node): void => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const tag = componentTag(node)
      for (const fn of (tag && values.valueOf(tag).fns) || []) components.add(fn)
    }
    if (ts.isCallExpression(node) && elementCall(node) && node.arguments[0] && !ts.isSpreadElement(node.arguments[0])) {
      for (const fn of values.valueOf(node.arguments[0]).fns ?? []) components.add(fn)
    }
    if (ts.isFunctionDeclaration(node) && node.name && /^[A-Z]/.test(node.name.text)) components.add(node)
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && /^[A-Z]/.test(node.name.text) && node.initializer) {
      for (const fn of values.valueOf(node.initializer).fns ?? []) components.add(fn)
    }
    ts.forEachChild(node, collect)
  }
  collect(source)

  const visit = (node: ts.Node): void => {
    if (ts.isJsxText(node) && isTokenText(node.text) && rendersChildren(node.parent)) flag(node, node.text)
    if (ts.isJsxExpression(node) && node.expression && rendersChildren(node.parent) && holds(node.expression)) flag(node, node.getText(source))
    if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) element(node)
    if (ts.isCallExpression(node)) call(node)
    ts.forEachChild(node, visit)
  }
  visit(source)
  components.forEach(returnsToken)
  return findings.sort((a, b) => a.line - b.line)
}

const relative = (file: string) => path.relative(FRONTEND_ROOT, file)
const shownAt = (file: string, f: Finding) => `${relative(file)}:${f.line} ${f.shown}`
/** Whether a finding is JSX text inside an aria-hidden element: the element's own token. */
const ariaHiddenText = (node: ts.Node) =>
  ts.isJsxText(node) &&
  ts.isJsxElement(node.parent) &&
  node.parent.openingElement.attributes.properties.some((attr) => {
    if (!ts.isJsxAttribute(attr) || attr.name.getText() !== 'aria-hidden' || !attr.initializer) return false
    const value = ts.isJsxExpression(attr.initializer) ? attr.initializer.expression : attr.initializer
    return !!value && ((ts.isStringLiteral(value) && value.text === 'true') || value.kind === ts.SyntaxKind.TrueKeyword)
  })

/** How a planted line reads: `flag` is a form the rule forbids that the gate names (or one it fails closed on), `clean`
    a look-alike that must pass, `gap` a form the rule forbids that the gate leaves to review (the header names it), so
    it passes until the gate reaches it and the mark flips; `setup` is a line the forms share, which the gate never
    names. */
type Mark = 'flag' | 'clean' | 'gap' | 'setup'
/** The self-check: one line per form, each with its mark and what it plants, read as one source and scored on every
    run, so a change to the gate that loses a form, or catches a look-alike, fails. A form the rule can take joins
    with its mark. */
const FORMS: Array<[Mark, string, string]> = [
  ['setup', "import { Component, Fragment, Suspense, cloneElement, createElement, useEffect, useMemo, useReducer, useRef, useState, type ReactNode } from 'react'", ''],
  ['setup', "import { jsx } from 'react/jsx-runtime'", ''],
  ['setup', "import { toast } from 'sonner'", ''],
  ['setup', "import { Badge, Button, DataTable, MissingValue, Notice } from '@/components/ui'", ''],
  ['setup', "import { formatLocalDate } from '@/lib/format'", ''],
  ['setup', "import { OWN_TOKEN, fmtOwnFallback } from './elsewhere'", ''],
  ['setup', 'type Row = { v?: string; id?: string }', ''],
  ['setup', "const DASH = '—'", 'a name the forms read, never rendered here'],
  ['setup', "const shown = (v?: string) => v ?? '—'", 'a formatter whose fallback is the token, rendered only where it is called'],
  ['setup', "function figure(v?: number) { if (v == null) return '—'; return String(v) }", 'a declared formatter, its early return the token'],
  ['setup', 'const shownOrNull = (v?: string) => v ?? null', 'a formatter that returns null for a missing value'],
  ['setup', "function* marks() { yield '—' }", 'a generator'],
  // The token rendered into the page outside the element.
  ['flag', 'export function M01() { return <td>—</td> }', "the dash as a cell's text"],
  ['flag', 'export function M02() { return <td>&mdash;</td> }', 'an entity JSX decodes'],
  ['flag', 'export function M03() { return <td>&#8212;</td> }', 'a decimal entity'],
  ['flag', 'export function M04() { return <td>&#x2014;</td> }', 'a hex entity'],
  ['flag', "export function M05() { return <td>{'—'}</td> }", 'a literal child'],
  ['flag', "export function M06() { return <td>{'\\u2014'}</td> }", 'an escape'],
  ['flag', 'export function M07() { return <td>{`—`}</td> }', 'a template child'],
  ['flag', "export function M08({ v }: { v?: string }) { return <td>{v ?? '—'}</td> }", 'a ?? fallback'],
  ['flag', "export function M09({ v }: { v?: string }) { return <td>{v || '—'}</td> }", 'an || fallback'],
  ['flag', "export function M10({ v }: { v?: string }) { return <td>{v ? v : '—'}</td> }", "a conditional's arm"],
  ['flag', "export function M11({ v }: { v?: string }) { return <td>{!v && '—'}</td> }", 'the right of &&'],
  ['flag', 'export function M12() { return <td>{DASH}</td> }', 'a name that holds it'],
  ['flag', 'export function M13({ v }: { v?: string }) { return <td>{shown(v)}</td> }', "a same-file formatter's fallback"],
  ['flag', 'export function M14({ v }: { v?: number }) { return <td>{figure(v)}</td> }', "a declared formatter's early return"],
  ['flag', "export function M15({ v }: { v?: string }) { return <span>{formatLocalDate(v, 'MMM d, yyyy', '—')}</span> }", "an imported formatter handed the token as its fallback, the watchlist's filed date"],
  ['flag', "export function M16({ v }: { v?: string }) { return <span>Period end: {formatLocalDate(v, 'MMM d, yyyy', '—')}</span> }", 'the same beside a label, the watchlist\'s "Period end: —"'],
  ['flag', "export function M17({ v }: { v?: string }) { return <p>{v ?? '—'} shares</p> }", 'beside a unit, which the em-dash gate fails too'],
  ['flag', 'export function M18() { return <span className="relative"><span aria-hidden="true">—</span><span className="sr-only">unavailable</span></span> }', "the element written by hand, as #1381 wrote it twice"],
  ['flag', 'export function M19({ v }: { v?: string }) { return <span>{v ?? <span aria-hidden="true">—</span>}</span> }', "a hidden dash with no words, What changed's Change before E88"],
  ['flag', 'export function M20() { return <Badge>—</Badge> }', "an imported component's children"],
  ['flag', "export function M21({ v }: { v?: string }) { return <Notice title={v ?? '—'} /> }", "an imported component's prop"],
  ['flag', 'export function M22() { return <Notice title="&mdash;" /> }', "an entity in an imported component's prop"],
  ['flag', "export function M23() { return <DataTable rows={[]} columns={[{ key: 'v', header: 'V', render: (r: Row) => r.v ?? '—' }]} /> }", "a column's render returns it"],
  ['flag', "export function M24() { const columns = [{ key: 'v', header: 'V', render: (r: Row) => r.v ?? '—' }]; return <DataTable rows={[]} columns={columns} /> }", 'a column list held in a name'],
  ['flag', 'export function M25() { return <td><>—</></td> }', "a fragment's text"],
  ['flag', 'export function M26() { return <td><Fragment>—</Fragment></td> }', "React's Fragment"],
  ['flag', 'export function M27() { return <Suspense fallback="—"><b>x</b></Suspense> }', "Suspense's fallback"],
  ['flag', 'export function M28() { const Pass = ({ children }: { children: ReactNode }) => <>{children}</>; return <td><Pass>—</Pass></td> }', 'a same-file pass-through renders the children it is handed'],
  ['flag', 'export function M29() { const Bare = ({ children }: { children: ReactNode }) => children; return <td><Bare>—</Bare></td> }', 'a component that returns its children bare'],
  ['flag', "export function M30() { const DashText = () => '—'; return <td><DashText /></td> }", 'a component that returns the token as text'],
  ['flag', 'export function M31() { const Cell = ({ value }: { value: string }) => <td>{value}</td>; return <Cell value="—" /> }', "a same-file component's prop"],
  ['flag', "export function M32() { return <td>{['—']}</td> }", 'an array child'],
  ['flag', "export function M33({ vs }: { vs: string[] }) { return <ul>{vs.map((v) => <li key={v}>{v || '—'}</li>)}</ul> }", "a map callback's cell"],
  ['flag', "export function M34({ v }: { v?: string }) { const text = useMemo(() => v ?? '—', [v]); return <td>{text}</td> }", "useMemo's callback"],
  ['flag', 'export function M35() { return <td children="—" /> }', 'children given by a prop'],
  ['flag', "export function M36() { return <td {...{ children: '—' }} /> }", 'children given by a spread'],
  ['flag', "export function M37() { return <td dangerouslySetInnerHTML={{ __html: '—' }} /> }", 'inner HTML'],
  ['flag', "export function M38() { return createElement('td', null, '—') }", "createElement's children"],
  ['flag', "export function M39() { return jsx('td', { children: '—' }) }", "the JSX runtime's children"],
  ['flag', "export function M40() { return cloneElement(<td />, undefined, '—') }", "a clone's children"],
  ['flag', 'export function M41() { return <td>{String.fromCharCode(0x2014)}</td> }', 'a char code'],
  ['flag', "export function M42({ v }: { v?: string }) { return <td>{`${v ?? '—'}`}</td> }", "a template's substitution"],
  ['flag', "export function M43({ v }: { v?: string }) { return <td>{String(v ?? '—')}</td> }", 'a global handed it'],
  ['flag', "export function M44({ v }: { v?: string }) { return <td>{(v ?? '—').trim()}</td> }", "a method's receiver"],
  ['flag', "export function M45({ v }: { v?: string }) { return <td>{'' + (v ?? '—')}</td> }", 'a + operand'],
  ['flag', "export function M46({ v }: { v?: string }) { let text = v; if (!text) text = '—'; return <td>{text}</td> }", 'an assignment'],
  ['flag', "export function M47({ v = '—' }: { v?: string }) { return <td>{v}</td> }", "a destructuring's default"],
  ['flag', "export function M48({ v }: { v?: string }) { let text = ''; text += v ?? '—'; return <td>{text}</td> }", '+='],
  ['flag', 'export function M49() { return <svg><text>—</text></svg> }', 'SVG text'],
  ['flag', 'export function M50() { return <MissingValue label="—" /> }', 'the element handed the token as its words'],
  ['flag', "export function M51() { return <DataTable rows={[]} columns={[]} rowKey={(r: Row) => r.id ?? '—'} /> }", 'fails closed: a prop the gate cannot tell never renders'],
  ['flag', "export function M52({ v }: { v?: string }) { return <input readOnly value={v ?? '—'} /> }", "an input's value"],
  ['flag', "export function M53({ v }: { v?: string }) { return <input defaultValue={v ?? '—'} /> }", "an input's default value"],
  ['flag', "export function M54({ v }: { v?: string }) { return <input placeholder={v ?? '—'} /> }", "an input's placeholder"],
  ['flag', "export function M55({ v }: { v?: string }) { return <textarea readOnly value={v ?? '—'} /> }", "a textarea's value"],
  ['flag', "export function M56({ v }: { v?: string }) { return <textarea defaultValue={v ?? '—'} /> }", "a textarea's default value"],
  ['flag', "export function M57({ v }: { v?: string }) { return <textarea placeholder={v ?? '—'} /> }", "a textarea's placeholder"],
  ['flag', "export function M58() { return <input readOnly {...{ value: '—' }} /> }", "a field's value given by a spread"],
  ['flag', "export function M59() { return createElement('input', { readOnly: true, value: '—' }) }", "createElement's field value"],
  ['flag', "export function M60({ v }: { v?: string }) { return <select><option value=\"\" label={v ?? '—'} /></select> }", "an option's label, which the select shows"],
  ['flag', 'export function M61() { return <iframe title="Note" srcDoc="—" /> }', "an iframe's document"],
  ['flag', "export function M62({ v }: { v?: string }) { return <input type=\"hidden\" name=\"v\" value={v ?? '—'} /> }", "fails closed: a hidden input's value, which never renders"],
  ['flag', "export function M63({ v }: { v?: string }) { return <input type=\"checkbox\" name=\"v\" value={v ?? '—'} /> }", "fails closed: a checkbox's value, which never renders"],
  ['flag', "export function M64({ v }: { v?: string }) { return <button type=\"submit\" name=\"v\" value={v ?? '—'}>Save</button> }", "fails closed: a button's value, which never renders"],
  ['flag', 'export function M65() { return <select defaultValue=""><option value="—">None</option></select> }', "fails closed: an option's value, which a select never shows"],
  // The element, and look-alikes that render no token.
  ['clean', 'export function M66() { return <td><MissingValue /></td> }', 'the element'],
  ['clean', 'export function M67({ v }: { v?: string }) { return <td>{v ?? <MissingValue label="no cohort" />}</td> }', 'the element with words of its own'],
  ['clean', 'export function M68({ v }: { v?: string }) { return <td>{shownOrNull(v) ?? <MissingValue />}</td> }', 'a formatter that returns null, the element in its place'],
  ['clean', "export function M69({ v }: { v?: string }) { return <span>Period end: {formatLocalDate(v, 'MMM d, yyyy') || <MissingValue />}</span> }", 'the element beside a label'],
  ['clean', "export function M70() { return <DataTable rows={[]} columns={[{ key: 'v', header: 'V', render: (r: Row) => r.v ?? <MissingValue /> }]} /> }", "a column's render returns the element"],
  ['clean', "export function M71({ v }: { v?: string }) { const csv = ['Name', v ?? '—'].join(','); return <a href={`data:text/csv,${encodeURIComponent(csv)}`}>Download CSV</a> }", 'a CSV cell, which never reaches the page'],
  ['clean', "export function M72({ v }: { v?: string }) { return <button type=\"button\" aria-label={formatLocalDate(v, 'MMM d, yyyy', '—')}>Open</button> }", 'an aria label'],
  ['clean', "export function M73({ v }: { v?: string }) { return <Button aria-label={v ?? '—'}>Open</Button> }", "an imported component's aria label"],
  ['clean', "export function M74({ v }: { v?: string }) { return <td title={v ?? '—'}>x</td> }", 'a title attribute'],
  ['clean', "export function M75({ v }: { v?: string }) { return <td>{v === '—' ? <MissingValue /> : v}</td> }", 'a comparison'],
  ['clean', "export function M76({ v }: { v?: string }) { return <li key={v ?? '—'} data-missing=\"—\">x</li> }", 'a key and a data attribute'],
  ['clean', "export function M77() { return <button type=\"button\" onClick={() => navigator.clipboard.writeText('—')}>Copy</button> }", 'a handler'],
  ['clean', 'export function M78({ a, b }: { a: string; b: string }) { return <p>{a}–{b}</p> }', 'an en dash in a range'],
  ['clean', 'export function M79() { return <p>Prior — current</p> }', "an em-dash in copy: the em-dash gate's to fail, not a missing value"],
  ['clean', "export function M80() { const Drop = ({ children }: { children?: ReactNode }) => <td>{children ? 'x' : null}</td>; return <Drop>—</Drop> }", 'a component that never renders the children it is handed'],
  ['clean', "export function M81() { const MISSING = new Set(['—']); return <td>{MISSING.has('x') ? <MissingValue /> : 'x'}</td> }", "a parse set, as lib/format.ts's MISSING_TOKENS"],
  // Forms the rule forbids that the gate leaves to review, each named in the header.
  ['gap', 'export function M82({ v }: { v?: string }) { return <td>{fmtOwnFallback(v)}</td> }', "an imported formatter's own fallback"],
  ['gap', 'export function M83() { return <td>{OWN_TOKEN}</td> }', 'an imported constant'],
  ['gap', "export const M84 = [{ key: 'v', header: 'V', render: (r: Row) => r.v ?? '—' }]", 'a column list handed to a component in another module'],
  ['flag', "export function M85() { const [mark] = useState('—'); return <td>{mark}</td> }", 'React state, which the reader follows (E159)'],
  ['flag', "export function M96() { const [mark] = useReducer((s: string) => s, '—'); return <td>{mark}</td> }", "a reducer's initial state (E159)"],
  ['flag', "export function M97({ v }: { v?: string }) { const [mark, setMark] = useState(v); if (!v) setMark('—'); return <td>{mark}</td> }", 'what a setter is handed (E159)'],
  ['flag', "export function M98() { const mark = useRef('—'); return <td>{mark.current}</td> }", "a ref's current (E159)"],
  ['clean', "export function M99() { const [mark] = useState('—'); return <td title={mark}>x</td> }", 'React state in a title attribute (E159)'],
  ['gap', "export class M86 extends Component { mark = '—'; render() { return <td>{this.mark}</td> } }", "a class's field read through this"],
  ['gap', "export async function M87(p: Promise<string | undefined>) { const v = await p.then((n) => n ?? '—'); return <td>{v}</td> }", "a promise's then"],
  ['gap', "export function M88() { return <td>{[...marks()].join('')}</td> }", "a generator's yield"],
  ['flag', 'export function M89({ v }: { v?: string }) { return <td>{shown.call(null, v)}</td> }', "Function.prototype's call"],
  ['gap', "export function M90({ v }: { v?: string }) { return <td>{v || '-'}</td> }", 'a missing value in another glyph, a hyphen'],
  ['gap', "export function M91({ v }: { v?: string }) { return <td>{v ?? '–'}</td> }", 'a missing value in another glyph, an en dash'],
  ['gap', "export function M92() { return <button type=\"button\" onClick={() => toast('—')}>Save</button> }", "a toast's message, rendered outside the tree"],
  ['gap', "export function M93() { const ref = useRef<HTMLTableCellElement>(null); useEffect(() => { if (ref.current) ref.current.textContent = '—' }); return <td ref={ref} /> }", 'an imperative write'],
  ['gap', "export function M94({ local }: { local: boolean }) { const Local = ({ children }: { children: ReactNode }) => <b>{children ? 'x' : null}</b>; const Tag = local ? Local : Badge; return <Tag>—</Tag> }", 'a tag that may be a same-file component or an import, read as the same-file one'],
  ['gap', 'export function M95({ v }: { v?: string }) { return <p>{v ?? <MissingValue />} shares</p> }', 'the element beside a unit, which the voice guide forbids'],
]

describe('the missing-value token renders through MissingValue alone (E88)', () => {
  const files = SCANNED_DIRS.flatMap((dir) => sourceFiles(path.join(FRONTEND_ROOT, dir)))
  const scanned = files.map((file) => ({ file, findings: findingsIn(readFileSync(file, 'utf8'), file) }))

  it('scores every planted form as its mark says (a self-check on fixed sources)', () => {
    const file = path.join(FRONTEND_ROOT, 'features/zzprobe/Probe.tsx')
    const named = new Set(findingsIn(FORMS.map(([, code]) => code).join('\n'), file).map((f) => f.line))
    const count = (mark: Mark) => FORMS.filter(([m]) => m === mark).length
    expect([count('flag'), count('clean'), count('gap')], 'the forms planted: flagged, clean and gaps').toEqual([70, 17, 12])
    const misread = FORMS.flatMap(([mark, code, why], i) =>
      named.has(i + 1) === (mark === 'flag') ? [] : [`line ${i + 1} (${mark}): ${why || code.slice(0, 60)}`],
    )
    expect(misread, 'the gate reads these forms against their marks: fix the gate, or flip the mark with its record').toEqual([])
  })

  it('writes the token once, in the element, aria-hidden', () => {
    const own = scanned.find(({ file }) => relative(file) === ELEMENT_FILE)
    expect(own, `${ELEMENT_FILE} is scanned`).toBeDefined()
    expect(own!.findings.map((f) => shownAt(own!.file, f)), 'the element writes the token exactly once').toHaveLength(1)
    expect(ariaHiddenText(own!.findings[0].node), 'the element hides its token from assistive tech').toBe(true)
  })

  it('finds the token rendered nowhere else in the app', () => {
    // A floor, so a walk that reads nothing cannot pass: the dirs hold hundreds of modules, and a handful spell the
    // token (the element, lib/format.ts's parse set, SummaryBlocks' numeric-column check).
    expect(files.length, 'the scan reads the app').toBeGreaterThan(300)
    expect(scanned.filter(({ file }) => SPELLINGS.test(readFileSync(file, 'utf8'))).length, 'the reader runs on the files that spell it').toBeGreaterThanOrEqual(3)
    const violations = scanned
      .filter(({ file }) => relative(file) !== ELEMENT_FILE)
      .flatMap(({ file, findings }) => findings.map((f) => shownAt(file, f)))
    expect(
      violations,
      'A missing value renders through MissingValue (components/ui): the token aria-hidden beside words for ' +
        'assistive tech, "unavailable" or a label of the site\'s own. Render <MissingValue /> where the value is ' +
        `missing; a formatter returns null or '' for it and its caller renders the element (DESIGN_SYSTEM.md §4).\n${violations.join('\n')}`,
    ).toEqual([])
  })
})
