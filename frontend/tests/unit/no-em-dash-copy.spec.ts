import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { heldValues, knownAsIn, leavesOf, scopeResolver, unwrapHeld } from './heldValues'

/**
 * Copy-voice structural guard: no em-dashes in user-facing copy
 * (docs/voice-and-style.md). The 2026-07 copy pass removed every em-dash from
 * string literals, template literals, and JSX text across the app source;
 * this spec keeps them out. Comments are naturally exempt (the AST walk never
 * sees them), and the ONE sanctioned use — the bare '—' missing-value token
 * rendered in tables and detail rows (lib/format.ts MISSING_TOKENS) — is
 * exempted where it stands alone: JSX text whose trim is '—' as the sole
 * meaningful child of its element (`<td>—</td>`), and a string or
 * no-substitution template literal whose text is exactly '—' (the token)
 * wherever its value is never joined into copy. Any other text with an
 * em-dash fails where it is written, a template's head, middle or tail
 * included, since the template joins it to what its substitutions render.
 *
 * The token's value is followed by the reading the voice and glyph gates
 * share (tests/unit/heldValues.ts), resolved by scope: from every place a
 * name is given it (a declaration, an assignment, a parameter's or a
 * destructuring's default, a destructuring, a property put on an object
 * after it is made, an array's element, a same-file function's parameter
 * at each call, a same-file component's children, JSX text included) to
 * every place it is read. It is joined into copy, and fails there, as an operand
 * of `+`, either side of `+=`, a template's substitution, a child beside
 * sibling children (JSX's, and React's `createElement` and `cloneElement`
 * under any local name: a child is held to the JSX text's test), an
 * argument or the receiver of `concat`, an element or the separator of
 * `join`, the replacement of `replace` and `replaceAll`, and the fill of
 * `padStart` and `padEnd`. So a spaced dash beside an expression fails in
 * each spelling: `— {speaker}`, `{'—'} {speaker}`, `'—' + ' ' + speaker`,
 * and `const DASH = '—'` or `let DASH; DASH = '—'` read as
 * `{DASH} {speaker}` (BG-02). An element is a value of its own, so a token
 * that is the sole child of a `<span>` stands alone wherever the span goes.
 * A fragment is not: it renders its children into its parent, so it is read
 * as its children, held (`const F = <>—</>` read as `{F} shares`) or written
 * among siblings (`<p><>—</> shares</p>`). So is React's Fragment under every
 * name the file gives it: `Fragment` imported from 'react', renamed or not and
 * keyed or not; `React.Fragment` or `R.Fragment` under a default or namespace
 * import of 'react'; a same-file alias or destructuring of one; and
 * `createElement(Fragment, …)`, `React.createElement(React.Fragment, …)` or
 * `createElement(React['Fragment'], …)`. A component named Fragment that the file declares, or imports from
 * anywhere but 'react', is not React's and stays an element.
 * What a same-file function returns is its call's value, read where the
 * call is (E76): a formatter's `'—'` fallback fails wherever its call is
 * joined into copy (a unit after it, `{shares(n)} shares` or
 * `${shares(n)} sh`, a sign before it, a middot or an sr-only label beside
 * it), and a callback's wherever its result goes (`map`'s into `join`,
 * `useMemo`'s beside a sibling). A formatter whose value sits beside copy
 * returns no figure for a missing value (`null`), and its caller renders the
 * token in an element of its own in its place. Out of reach, each planted
 * as a gap in the self-check and review-checked: an element that holds the
 * token, set beside a unit (`{v ?? <Missing />} sh`: an element is one value
 * to this reading, which cannot tell it from What changed's dash beside its
 * arrow and sr-only labels, and a component named Fragment that is not
 * React's is one); React's `jsx` and `jsxs` from 'react/jsx-runtime', which
 * this reading does not follow, a fragment written as their call included;
 * React's Fragment handed in through a prop or a parameter (`<As>—</As>`
 * given `As={Fragment}`); a call's value wrapped in another call or a
 * method (`String(f(n))`, `f(n).trim()`); a token that crosses modules (an
 * export read in another file, an imported formatter's fallback); React
 * state; a class's field read through `this`; a promise's `then`; and a
 * generator's `yield`.
 *
 * If you're writing copy and want a dash: restructure the sentence (split it,
 * use a colon, or a middot separator for compact labels). En-dashes (–) in
 * genuine ranges (Q1–Q4, 30–60s) are allowed and not checked here.
 */

const FRONTEND_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCANNED_DIRS = ['app', 'components', 'features', 'lib', 'hooks']
const EM_DASH = '—'
/** React's calls that make an element, children from their third argument on. */
const ELEMENT_CALLS = new Set(['createElement', 'cloneElement'])

function sourceFiles(dir: string): string[] {
  if (!existsSync(dir)) return []
  const out: string[] = []
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry)
    if (statSync(full).isDirectory()) {
      out.push(...sourceFiles(full))
    } else if (/\.(ts|tsx)$/.test(entry) && !/\.(spec|test)\.(ts|tsx)$/.test(entry)) {
      out.push(full)
    }
  }
  return out
}

/** Whether a JSX child is the only meaningful child of its element (whitespace-only text, and an
    expression that holds nothing or only a comment, aside). A fragment is no element: it renders its
    children into its own parent, so a child alone in a fragment written among siblings is not alone.
    `fragment` says which parents are fragments: `<>`, and React's Fragment under any name. */
function soleChild(child: ts.JsxChild, fragment: (parent: ts.JsxElement | ts.JsxFragment) => boolean): boolean {
  const parent = child.parent
  if (!ts.isJsxElement(parent) && !ts.isJsxFragment(parent)) return false
  const meaningful = parent.children.filter(
    (c) => !(ts.isJsxText(c) && c.containsOnlyTriviaWhiteSpaces) && !(ts.isJsxExpression(c) && !c.expression),
  )
  if (meaningful.length !== 1 || meaningful[0] !== child) return false
  return fragment(parent) && (ts.isJsxElement(parent.parent) || ts.isJsxFragment(parent.parent)) ? soleChild(parent, fragment) : true
}

/** Whether an import binding (default, namespace or named) is one of 'react''s. */
function importedFromReact(binding: ts.Node): boolean {
  let n: ts.Node | undefined = binding
  while (n && !ts.isImportDeclaration(n)) n = n.parent
  return !!n && ts.isStringLiteral(n.moduleSpecifier) && n.moduleSpecifier.text === 'react'
}

/** What the shared model reads as a leaf here: the token, and an element, a value of its own (a fragment, `<>` or
    React's Fragment under any name, is no element: the shared reading holds its children). */
type Leaf = 'token' | 'element'

/** Every em-dash in `text` outside the sanctioned token, as `file:line text`. */
function violationsIn(text: string, file: string): string[] {
  if (!text.includes(EM_DASH)) return []
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const declarationOf = scopeResolver(source)
  const knownAs = knownAsIn(declarationOf)
  const calleeName = (call: ts.CallExpression) => knownAs(call.expression)?.name ?? ''
  const isToken = (n: ts.Node) => (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) && n.text === EM_DASH
  /** Whether a name is React: a default or namespace import of 'react', or a same-file alias of one (React's UMD
      global does not compile in a module here: TS2686). */
  const isReact = (raw: ts.Expression, seen = new Set<ts.Node>()): boolean => {
    const e = unwrapHeld(raw)
    if (!ts.isIdentifier(e)) return false
    const declaration = declarationOf(e)
    if (!declaration) return false
    if (seen.has(declaration)) return false
    seen.add(declaration)
    if (ts.isImportClause(declaration) || ts.isNamespaceImport(declaration)) return importedFromReact(declaration)
    return ts.isVariableDeclaration(declaration) && !!declaration.initializer && isReact(declaration.initializer, seen)
  }
  /** Whether an expression or a tag names React's Fragment: `Fragment` imported from 'react' under any local name,
      React's `.Fragment` (`React.Fragment`, `R.Fragment`, `React['Fragment']`), or a same-file alias or destructuring of
      one. A component named Fragment that the file declares, or imports from anywhere else, is not React's. */
  const isReactFragment = (raw: ts.Expression | ts.JsxTagNameExpression, seen = new Set<ts.Node>()): boolean => {
    const e = ts.isJsxNamespacedName(raw) ? raw : unwrapHeld(raw)
    if (ts.isPropertyAccessExpression(e)) return e.name.text === 'Fragment' && isReact(e.expression)
    if (ts.isElementAccessExpression(e)) return ts.isStringLiteralLike(e.argumentExpression) && e.argumentExpression.text === 'Fragment' && isReact(e.expression)
    if (!ts.isIdentifier(e)) return false
    const declaration = declarationOf(e)
    if (!declaration || seen.has(declaration)) return false
    seen.add(declaration)
    if (ts.isImportSpecifier(declaration)) return (declaration.propertyName ?? declaration.name).text === 'Fragment' && importedFromReact(declaration)
    if (ts.isVariableDeclaration(declaration)) return !!declaration.initializer && isReactFragment(declaration.initializer, seen)
    if (ts.isBindingElement(declaration) && ts.isObjectBindingPattern(declaration.parent) && ts.isVariableDeclaration(declaration.parent.parent)) {
      const key = declaration.propertyName ?? declaration.name
      const from = declaration.parent.parent.initializer
      return ts.isIdentifier(key) && key.text === 'Fragment' && !!from && isReact(from)
    }
    return false
  }
  /** The parents that render their children into their own parent: `<>`, and React's Fragment under any name. */
  const fragment = (parent: ts.JsxElement | ts.JsxFragment) => ts.isJsxFragment(parent) || isReactFragment(parent.openingElement.tagName)
  /** An element is a value of its own; a fragment, a JSX one or React's `createElement(Fragment, …)`, is its children. */
  const isElement = (e: ts.Expression) =>
    (ts.isJsxElement(e) && !fragment(e)) ||
    (ts.isJsxSelfClosingElement(e) && !isReactFragment(e.tagName)) ||
    (ts.isCallExpression(e) &&
      ELEMENT_CALLS.has(calleeName(e)) &&
      !(calleeName(e) === 'createElement' && !!e.arguments[0] && isReactFragment(e.arguments[0])))
  const values = heldValues<Leaf>(
    source,
    (e) => (isToken(e) ? ['token'] : isElement(e) ? ['element'] : undefined),
    // The shared reading follows each same-file call into what the function returns (E76), so a formatter's fallback
    // fails where its call is joined into copy; the self-check's E76 plants (88 to 97) fail if it stops.
    { textLeaf: (jsxText) => (jsxText.text.trim() === EM_DASH ? ['token'] : undefined) },
  )
  const holdsToken = (e: ts.Expression | undefined) => !!e && leavesOf(values.valueOf(ts.isSpreadElement(e) ? e.expression : e)).has('token')

  /** The expressions a node joins into copy (see the header). */
  const joinedAt = (node: ts.Node): Array<ts.Expression | undefined> => {
    if (ts.isBinaryExpression(node) && (node.operatorToken.kind === ts.SyntaxKind.PlusToken || node.operatorToken.kind === ts.SyntaxKind.PlusEqualsToken)) {
      return [node.left, node.right]
    }
    if (ts.isTemplateSpan(node)) return [node.expression]
    if (ts.isJsxExpression(node) && !ts.isJsxAttribute(node.parent)) return soleChild(node, fragment) ? [] : [node.expression]
    if (!ts.isCallExpression(node)) return []
    const name = calleeName(node)
    const args = node.arguments
    const callee = unwrapHeld(node.expression)
    const receiver = ts.isPropertyAccessExpression(callee) ? callee.expression : undefined
    if (ELEMENT_CALLS.has(name)) {
      const children = args.slice(2)
      return children.length > 1 || children.some(ts.isSpreadElement) ? [...children] : []
    }
    if (name === 'concat') return [receiver, ...args]
    if (name === 'join') return [receiver, args[0]]
    if (name === 'replace' || name === 'replaceAll' || name === 'padStart' || name === 'padEnd') return [args[1]]
    return []
  }

  const violations: string[] = []
  const report = (at: ts.Node, shown: string) => {
    const { line } = source.getLineAndCharacterOfPosition(at.getStart(source))
    violations.push(`${path.relative(FRONTEND_ROOT, file)}:${line + 1} ${shown.trim().slice(0, 80)}`)
  }
  const visit = (node: ts.Node) => {
    // Text with an em-dash fails where it is written, unless it is the token: JSX text as its element's sole child, a
    // literal wherever it is not joined (below). A template's head, middle or tail is never the token.
    if (ts.isJsxText(node) && node.text.includes(EM_DASH) && !(node.text.trim() === EM_DASH && soleChild(node, fragment))) report(node, node.text)
    if ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) && node.text.includes(EM_DASH) && node.text !== EM_DASH) report(node, node.text)
    if ((ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) && node.text.includes(EM_DASH)) report(node, node.text)
    // The token, wherever its value is joined into copy.
    for (const joined of joinedAt(node)) if (holdsToken(joined)) report(joined!, EM_DASH)
    ts.forEachChild(node, visit)
  }
  visit(source)
  return violations
}

const emDashViolations = (file: string): string[] => violationsIn(readFileSync(file, 'utf8'), file)

describe('no em-dashes in user-facing copy (voice guard)', () => {
  it('reads every form of the missing-value token (a self-check on fixed sources)', () => {
    const file = path.join(FRONTEND_ROOT, 'features/zzprobe/Probe.tsx')
    const src = [
      'export const A = ({ speaker, v }: { speaker: string; v?: string }) => (',
      '  <>',
      '    <td>—</td>',
      "    <td>{'—'}</td>",
      "    <td>{v ?? '—'}</td>",
      '    <td>{/* empty */}{`—`}</td>',
      "    <span title={'—'}>{speaker}</span>",
      '    <cite>— {speaker}</cite>',
      "    <cite>{'—'} {speaker}</cite>",
      "    <cite>{v ? '—' : ''} {speaker}</cite>",
      "    <cite>{speaker} {v || ('—')}</cite>",
      '  </>',
      ')',
      "export const B = (speaker: string) => '—' + ' ' + speaker",
      "export const C = (speaker: string) => `${'—'} ${speaker}`",
      'export const D = (speaker: string) => `—${speaker}`',
      "export const E = (speaker: string) => { let s = speaker; s += '—'; return s }",
      "export const MISSING = '—'",
      "export const F = (x?: string) => (x !== '—' ? x : null) ?? `—`",
      "const DASH = '—'",
      'export const G = ({ speaker }: { speaker: string }) => <cite>{DASH} {speaker}</cite>',
      "export const H = (speaker: string) => DASH + ' ' + speaker",
      "const NONE = '—'",
      'export const I = ({ v }: { v?: string }) => <td>{v ?? NONE}</td>',
      'const HELD = NONE',
      'export const J = (x: string) => `${HELD}${x}`',
      "const BOX = { token: '—' } as const",
      'export const K = ({ speaker }: { speaker: string }) => <cite>{BOX.token} {speaker}</cite>',
      'export const L = ({ v }: { v?: string }) => <td>{v ?? BOX.token}</td>',
      'const SHORT = { DASH } as const',
      'export const M = ({ speaker }: { speaker: string }) => <cite>{SHORT.DASH} {speaker}</cite>',
      'export const N = ({ v }: { v?: string }) => <td>{v ?? SHORT.DASH}</td>',
      "const TOKEN = '—'",
      "export function O({ speaker }: { speaker: string }) { const TOKEN = 'none'; return <cite>{TOKEN} {speaker}</cite> }",
      "export const P = (TOKEN: string) => TOKEN + ' ' + TOKEN",
      "const CELL = { token: '—' } as const",
      "export function Q({ speaker }: { speaker: string }) { const CELL = { token: 'none' }; return <cite>{CELL.token} {speaker}</cite> }",
      "const MARK = 'x'",
      "export function R({ speaker }: { speaker: string }) { const MARK = '—'; return <cite>{MARK} {speaker}</cite> }",
      'export const S = ({ speaker }: { speaker: string }) => <cite>{MARK} {speaker}</cite>',
      "const ROOT = '—'",
      'export function T({ speaker }: { speaker: string }) { const ALIAS = ROOT; return <cite>{ALIAS} {speaker}</cite> }',
      'export function U({ speaker }: { speaker: string }) { const ALIAS = ROOT; return <cite>{ALIAS} {speaker}</cite> }',
      "let LATE = ''",
      "LATE = '—'",
      'export const V = ({ speaker }: { speaker: string }) => <cite>{LATE} {speaker}</cite>',
      "let OR = '', AND = 'x', NULLISH: string | undefined",
      "OR ||= '—'",
      "AND &&= '—'",
      "NULLISH ??= '—'",
      'export const W = ({ speaker }: { speaker: string }) => <cite>{OR} {speaker} {AND} {speaker} {NULLISH} {speaker}</cite>',
      "export function X(speaker: string, dash = '—') { return <cite>{dash} {speaker}</cite> }",
      "export const Y = ({ speaker, dash = '—' }: { speaker: string; dash?: string }) => <cite>{dash} {speaker}</cite>",
      'const BAG: { token?: string } = {}',
      "BAG.token = '—'",
      'export const Z = ({ speaker }: { speaker: string }) => <cite>{BAG.token} {speaker}</cite>',
      'const { token: PICKED } = BOX',
      'export const AA = ({ speaker }: { speaker: string }) => <cite>{PICKED} {speaker}</cite>',
      "var TWICE: string; var TWICE = '—'",
      'export const AB = ({ speaker }: { speaker: string }) => <cite>{TWICE} {speaker}</cite>',
      "const cite = (mark: string, who: string) => mark + ' ' + who",
      "export const AC = ({ speaker }: { speaker: string }) => <p>{cite('—', speaker)}</p>",
      'const Lead = ({ children }: { children: ReactNode }) => <cite>{children} said</cite>',
      'export const AD = () => <Lead>—</Lead>',
      "const DASHED = <span>{'—'}</span>",
      'export const AE = ({ speaker }: { speaker: string }) => <cite>{DASHED} {speaker}</cite>',
      "const BUILT = h('span', null, '—')",
      'export const AF = ({ speaker }: { speaker: string }) => <cite>{BUILT} {speaker}</cite>',
      "export const AG = (speaker: string) => createElement('cite', null, '—', ' ', speaker)",
      "export const AH = () => createElement('td', null, '—')",
      "export const AI = (speaker: string) => [DASH, speaker].join(' ')",
      "export const AJ = (parts: string[]) => parts.join('—')",
      "export const AK = (speaker: string) => speaker.concat(' ', NONE)",
      "export const AL = (note: string) => note.replace('--', '—').replaceAll('-', '—')",
      "export const AM = (n: string) => n.padStart(4, '—').padEnd(8, '—')",
      'export const AN = (speaker: string) => { let s = DASH; s += speaker; return s }',
      "const fallback = (v?: string) => v ?? '—'",
      'export const AO = ({ v, speaker }: { v?: string; speaker: string }) => <cite>{fallback(v)} {speaker}</cite>',
      "export function AP({ speaker }: { speaker: string }) { const [mark] = useState('—'); return <cite>{mark} {speaker}</cite> }",
      "class Line { mark = '—'; show(speaker: string) { return <cite>{this.mark} {speaker}</cite> } }",
      "import { createElement as h } from 'react'",
      "export const AQ = (speaker: string) => h('cite', null, NONE, ' ', speaker)",
      "export const AR = () => createElement('cite', null, ...[DASH, ' said'])",
      "export const AS = () => DASH.concat(' said')",
      "export const AT = (el: ReactElement, speaker: string) => cloneElement(el, null, '—', ' ', speaker)",
      'const Said = ({ mark, who }: { mark: string; who: string }) => <cite>{mark} {who}</cite>',
      'export const AU = () => <Said mark="—" who="x" />',
      "const count = (n?: number) => (n == null ? '—' : String(n))",
      'export const AV = ({ n }: { n?: number }) => <p>Excludes {count(n)} shares sold</p>',
      'export const AW = (n?: number) => `${count(n)} sh`',
      "export const AX = ({ n }: { n: number }) => <p>{n < 0 ? '−' : '+'}{count(n)}</p>",
      'export const AY = ({ n }: { n?: number }) => <p>Net buying{n !== 0 && <> · {count(n)}</>}</p>',
      "function figure(v?: number) { if (v == null) return '—'; return String(v) }",
      'export const AZ = ({ v }: { v?: number }) => <span><span className="sr-only">Prior </span>{figure(v)}<span aria-hidden="true"> → </span></span>',
      "export const BA = ({ n }: { n?: number }) => { const size = count(n); return <p>{'−'}{size}</p> }",
      "export const BB = (vs: number[]) => vs.map((v) => (v ? String(v) : '—')).join(' sh, ')",
      "export function BC({ v }: { v?: number }) { const shown = useMemo(() => v ?? '—', [v]); return <p>{shown} shares</p> }",
      'const shownOrNull = (v?: number) => (v == null ? null : String(v))',
      'const GONE = <span className="relative"><span aria-hidden="true">—</span><span className="sr-only">unavailable</span></span>',
      'export const BD = ({ v }: { v?: number }) => <span><span className="sr-only">Prior </span>{shownOrNull(v) ?? GONE}<span aria-hidden="true"> → </span></span>',
      'export const BE = ({ v }: { v?: number }) => <td>{count(v)}</td>',
      'const FRAG = <>—</>',
      'export const BF = () => <p>{FRAG} shares</p>',
      'export const BG = () => <p>{<>—</>} shares</p>',
      'export const BH = () => <p><>—</> shares</p>',
      'export const BI = () => <td>{FRAG}</td>',
      'export const BJ = () => <td><>—</></td>',
      'export const BK = ({ v }: { v?: number }) => <p>{shownOrNull(v) ?? GONE} sh</p>',
      'export const BL = (n?: number) => `${String(count(n))} sh`',
      'export const BM = (n?: number) => `${count(n).trim()} sh`',
      "import { DASH_ELSEWHERE, fmtElsewhere } from './elsewhere'",
      'export const BN = ({ speaker }: { speaker: string }) => <cite>{DASH_ELSEWHERE} {speaker}</cite>',
      "export const BO = ({ v }: { v?: string }) => <p>Period end: {fmtElsewhere(v, '—')}</p>",
      "export async function BP(p: Promise<number | undefined>) { const v = await p.then((n) => n ?? '—'); return <p>{v} sh</p> }",
      "function* marks() { yield '—' }",
      "export const BQ = () => <p>{[...marks()].join('')} sh</p>",
      "import { Fragment, Fragment as Frag } from 'react'",
      "import React from 'react'",
      "import * as ReactNs from 'react'",
      "import { Fragment as Piece } from './pieces'",
      "import { jsx } from 'react/jsx-runtime'",
      'export const CA = () => <p><Fragment>—</Fragment> shares</p>',
      'export const CB = () => <p><Frag>—</Frag> shares</p>',
      'export const CC = () => <p><React.Fragment>—</React.Fragment> shares</p>',
      'export const CD = () => <p><ReactNs.Fragment>—</ReactNs.Fragment> shares</p>',
      'export const CE = () => <p><Fragment key="k">—</Fragment> shares</p>',
      'const HELD_FRAGMENT = <Fragment>—</Fragment>',
      'export const CF = () => <p>{HELD_FRAGMENT} shares</p>',
      'const ALIASED = React.Fragment',
      'const { Fragment: PICKED_FRAGMENT } = React',
      'export const CG = () => <p><ALIASED>—</ALIASED> shares</p>',
      'export const CH = () => <p><PICKED_FRAGMENT>—</PICKED_FRAGMENT> shares</p>',
      "export const CI = () => <p>{createElement(Fragment, null, '—')} shares</p>",
      "export const CJ = () => createElement('p', null, createElement(Fragment, null, '—'), ' shares')",
      "export const CK = () => <p>{React.createElement(React.Fragment, null, '—')} shares</p>",
      'export const CL = () => <td><Fragment>—</Fragment></td>',
      'export const CM = () => <td><React.Fragment key="k">—</React.Fragment></td>',
      'export const CN = () => <td>{HELD_FRAGMENT}</td>',
      "export const CO = () => <td>{createElement(Fragment, null, '—')}</td>",
      "export const CP = () => createElement('td', null, React.createElement(ReactNs.Fragment, null, '—'))",
      'export function CQ() { const Fragment = ({ children }: { children: ReactNode }) => <b>{children}</b>; return <p><Fragment>—</Fragment> shares</p> }',
      'export const CR = () => <p><Piece>—</Piece> shares</p>',
      "export const CS = () => <p>{jsx(Fragment, { children: '—' })} shares</p>",
      'const Wrap = ({ As }: { As: ElementType }) => <p><As>—</As> shares</p>',
      'export const CT = () => <Wrap As={Fragment} />',
      "export const CU = () => <p>{createElement(React['Fragment'], null, '—')} shares</p>",
    ].join('\n')
    // Lines 3 to 7 stand alone (the text, the literal, a fallback, a template beside an empty expression, an
    // attribute's value) and 18 to 19 hold the token where nothing joins it (a name no line reads, a comparison, a
    // fallback returned by a function no line calls). Lines 8 to 11 sit beside sibling children (as text, a literal, a conditional's branch,
    // the right of `||` in parentheses), 14 is a `+` operand, 15 a template's substitution, 16 a template's head
    // and 17 the right of `+=`. A name holding the token is followed to its reads: DASH (20) is rendered beside a
    // sibling at 21 and is a `+` operand at 22; NONE (23) stands alone as a fallback at 24, and HELD (25), which holds
    // NONE, is a template's substitution at 26. BOX (27) holds the token in a property: its `BOX.token` read sits
    // beside a sibling at 28 and stands alone as a fallback at 29. SHORT (30) holds DASH by its shorthand: its
    // `SHORT.DASH` read sits beside a sibling at 31 and stands alone as a fallback at 32. A read is the name's by scope:
    // TOKEN (33) is read by no line, since O's TOKEN (34) and P's parameter (35) are their own values; CELL (36) is read
    // by no line, since Q declares its own CELL (37); R's MARK (39), a token a nested scope declares, is read beside a
    // sibling at 39, and S's read is of the outer MARK (40); T's and U's ALIAS, one name in two functions, each hold
    // ROOT (41) and are each read beside a sibling (42, 43).
    // A name is given the token in every way the shared model reads (the review's case, 44 to 46): an assignment
    // (LATE, read at 46), `||=`, `&&=` and `??=` (47 to 50, read at 51), a parameter's default (52), a destructuring's
    // default (53), a property put on an object after it is made (BAG, read at 56), a destructuring of a holder
    // (PICKED, read at 58), a `var` declared twice, one binding (TWICE, read at 60), a same-file function's parameter at
    // a call (cite's `mark` takes the token at 62 and is a `+` operand at 61), a same-file component's children
    // (Lead's, given JSX text at 64 and read beside text at 63) and its prop, a string attribute included (Said's `mark`,
    // given at 87 and read beside a sibling at 86). An element is a value of its own: a token that is the
    // sole child of a span (65) or of a span `createElement` makes under its local name `h` (67) stands alone where the
    // element goes (66, 68). The other joins: `createElement`'s children beside siblings (69, and under `h` at 82; a sole
    // child at 70 stands alone, a spread child at 83 may be several) and `cloneElement`'s (85), an element of `join`'s
    // receiver (71) and its separator (72), an argument of `concat` (73) and its receiver (84), the replacement of
    // `replace` and `replaceAll` (74, twice), the fill of `padStart` and `padEnd` (75, twice) and the left of `+=` (76).
    // A same-file function's return is its call's value (E76): fallback's (77) is read beside a sibling at 78. The
    // forms E76 found, each a formatter's fallback joined where it is called: a unit after it, in JSX text (count, 88,
    // at 89) and in a template (90), a sign before it (91), a middot inside a conditional fragment (92, twice: the call
    // beside the middot, and the fragment, read as its children, beside "Net buying"), a declared formatter's early
    // return beside an sr-only label and the arrow (figure, 93, at 94) and a name given a call's value, read beside a
    // sign (95); and a callback's return, `map`'s into `join` (96) and `useMemo`'s beside text (97). The forms that
    // replace them pass: a formatter that returns null for a missing value, with the token in an element of its own in
    // its place (98 to 100), and a fallback that is its cell's sole child (101). A fragment is
    // read as its children: FRAG (102) fails beside a unit at 103, as do a fragment in an expression (104) and one
    // written among siblings (105), and one alone in a cell passes, held (106) or written (107). Planted gaps, each out
    // of reach and read where it is written: React state (79), a class's field (80), an element that holds the token
    // beside a unit (108), a call's value wrapped in `String` (109) or a method (110), an export read from another file
    // (111, read at 112), an imported formatter's fallback (113), a promise's `then` (114) and a generator's `yield`
    // (115, read at 116). React's Fragment under any name is a fragment too (117 to 121 import it, React, a namespace,
    // a component named Fragment from elsewhere and the jsx runtime): beside a unit the named import (122), a renamed
    // one (123), `React.Fragment` (124), a namespace's `.Fragment` (125), a keyed one (126), one held (127, read at
    // 128), an alias (129, at 131), a destructuring of React (130, at 132), `createElement(Fragment, …)` in an
    // expression (133) and as a child beside a sibling (134), `React.createElement(React.Fragment, …)` (135) and
    // `createElement(React['Fragment'], …)` (146) fail; alone in a cell (136 to 140) they pass. A component named
    // Fragment that the file declares (141) or imports from elsewhere (142) stays an element and passes beside a unit,
    // as the element gap does. Planted gaps: a fragment written as a jsx-runtime call (143) and React's Fragment handed
    // in through a prop (144, given at 145).
    expect(violationsIn(src, file)).toEqual(
      [8, 9, 10, 11, 14, 15, 16, 17, 21, 22, 26, 28, 31, 39, 42, 43, 46, 51, 51, 51, 52, 53, 56, 58, 60, 61, 63, 69, 71, 72, 73, 74, 74, 75, 75, 76, 78, 82, 83, 84, 85, 86, 89, 90, 91, 92, 92, 94, 95, 96, 97, 103, 104, 105, 122, 123, 124, 125, 126, 128, 131, 132, 133, 134, 135, 146].map(
        (line) => `features/zzprobe/Probe.tsx:${line} —`,
      ),
    )
  })

  it('finds no em-dash in any string literal, template literal, or JSX text', () => {
    const violations = SCANNED_DIRS.flatMap((dir) => sourceFiles(path.join(FRONTEND_ROOT, dir))).flatMap(
      emDashViolations,
    )
    expect(
      violations,
      `Em-dash found in copy. Restructure the sentence instead (docs/voice-and-style.md): ` +
        `split it, use a colon, or a middot for compact labels.\n${violations.join('\n')}`,
    ).toEqual([])
  })
})
