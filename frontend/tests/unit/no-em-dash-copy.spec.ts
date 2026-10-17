import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { ELEMENT_MAKERS, heldValues, knownAsIn, leavesOf, propertyOf, scopeResolver, unwrapHeld, writtenChild, type HeldValues } from './heldValues'

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
 * sibling children (JSX's; those React's element calls hand an element, under
 * any local name: `createElement`'s and `cloneElement`'s from the third
 * argument, or else the `children` of its props, which the JSX runtime's
 * `jsx`, `jsxs` and `jsxDEV` always use; and an array's elements written as
 * children, which React renders beside each other: a child is held to the JSX
 * text's test), an argument or the receiver of `concat`, an element or the
 * separator of `join`, the replacement of `replace` and `replaceAll`, and the
 * fill of `padStart` and `padEnd`. So a spaced dash beside an expression fails in
 * each spelling: `— {speaker}`, `{'—'} {speaker}`, `'—' + ' ' + speaker`,
 * and `const DASH = '—'` or `let DASH; DASH = '—'` read as
 * `{DASH} {speaker}` (BG-02). An element is a value of its own, so a token
 * that is the sole child of a `<span>` stands alone wherever the span goes.
 * A fragment is not: it renders its children into its parent, so it is read
 * as its children, held (`const F = <>—</>` read as `{F} shares`) or written
 * among siblings (`<p><>—</> shares</p>`). The family is React's element API
 * (React 19, which the App Router renders with, and the React 18 types the app
 * compiles against). An element is a fragment when its type renders its
 * children into its parent: React's Fragment, StrictMode, Profiler, Activity,
 * ViewTransition, Suspense (whose fallback renders in its children's place
 * while they wait) or a same-file context's Provider, made by JSX,
 * `createElement`, the JSX runtime's `jsx`, `jsxs` or `jsxDEV`, or given its
 * children by its props (`<Fragment children="—" />`). A type is a value, read
 * by the shared reading from where the file names it to the tag or the
 * element call that takes it: an import from 'react' or a JSX runtime under
 * any name, React's namespace (a default or namespace import,
 * `require('react')`, `await import('react')`) by member or literal key, a
 * same-file alias, destructuring, prop, parameter, conditional or return, and
 * what `memo` wraps. A clone's type is its element's (React's `cloneElement`
 * keeps `element.type`), and its element is a value the kind reading follows
 * the same way, so a clone of a fragment, written in place, held, handed
 * through a parameter or picked by Children's methods, is a fragment; it
 * renders the children it is handed (its arguments, or else its props'
 * `children`), or else its element's. `Children.only` gives back the element
 * it is given, and `Children.toArray` and `Children.map` keep an element whole
 * (they do not enter a fragment) with its type, so each is read through. A
 * component named Fragment that the file declares is its own and stays an
 * element.
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
 * arrow and sr-only labels); an array held in a name or returned by a call,
 * rendered as children (the reading keeps what an array's elements hold, not
 * how many there are); a context's Consumer, whose function child's return
 * renders into its parent; `createFactory`, which React 19 removed, so a call
 * of it throws before anything renders; an element call whose arguments are
 * spread in; a lazy type, which a promise resolves; a call's value wrapped in
 * another call or a method (`String(f(n))`, `f(n).trim()`); a token or a type
 * that crosses modules (an export read in another file, an imported
 * formatter's fallback, a component named Fragment or a context imported from
 * another module, which may be React's re-exported); React state; a class's
 * field read through `this`; a promise's `then`; and a generator's `yield`.
 * One over-read fails closed: a clone handed children keeps its element's own
 * in this reading.
 *
 * If you're writing copy and want a dash: restructure the sentence (split it,
 * use a colon, or a middot separator for compact labels). En-dashes (–) in
 * genuine ranges (Q1–Q4, 30–60s) are allowed and not checked here.
 */

const FRONTEND_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCANNED_DIRS = ['app', 'components', 'features', 'lib', 'hooks']
const EM_DASH = '—'
/** The modules that export React's types: 'react', and its JSX runtimes, which export its Fragment. */
const REACT_MODULES = new Set(['react', 'react/jsx-runtime', 'react/jsx-dev-runtime'])
/** React's types that render their children into their parent, with no element of their own; Suspense is one too, and
    renders its fallback in their place while they wait. Activity and ViewTransition are React 19's (the App Router
    renders with it), which the app's React 18 types do not declare yet. */
const FRAGMENT_TYPES = new Set(['Fragment', 'StrictMode', 'Profiler', 'Activity', 'ViewTransition'])

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

/** Whether a JSX child is the only meaningful child of its element (whitespace-only text, and an expression that holds
    nothing or only a comment, aside). A fragment is no element: it renders its children into its own parent, so a child
    alone in a fragment written among siblings is not alone. `fragment` says which parents are fragments: `<>`, and an
    element of a fragment type. */
function soleChild(child: ts.JsxChild, fragment: (parent: ts.JsxElement | ts.JsxFragment) => boolean): boolean {
  const parent = child.parent
  if (!ts.isJsxElement(parent) && !ts.isJsxFragment(parent)) return false
  const meaningful = parent.children.filter(writtenChild)
  if (meaningful.length !== 1 || meaningful[0] !== child) return false
  return fragment(parent) && (ts.isJsxElement(parent.parent) || ts.isJsxFragment(parent.parent)) ? soleChild(parent, fragment) : true
}

/** The module an import binding (default, namespace or named) is imported from. */
function moduleOf(binding: ts.Node): string | undefined {
  let n: ts.Node | undefined = binding
  while (n && !ts.isImportDeclaration(n)) n = n.parent
  return n && ts.isStringLiteral(n.moduleSpecifier) ? n.moduleSpecifier.text : undefined
}

/** Whether a file may name one of React's types: an import from REACT_MODULES of React's namespace or default, of a
    type, Suspense or createContext by name, or React loaded by `require` or `import()`. A file without one names none,
    and its type reading is skipped. */
function namesReact(source: ts.SourceFile, text: string): boolean {
  const named = new Set([...FRAGMENT_TYPES, 'Suspense', 'createContext', 'default'])
  return (
    /\b(?:require|import)\(\s*['"]react['"/]/.test(text) ||
    source.statements.some((s) => {
      const clause = ts.isImportDeclaration(s) && ts.isStringLiteral(s.moduleSpecifier) && REACT_MODULES.has(s.moduleSpecifier.text) ? s.importClause : undefined
      if (!clause || clause.isTypeOnly) return false
      const bindings = clause.namedBindings
      return !!clause.name || (!!bindings && (ts.isNamespaceImport(bindings) || bindings.elements.some((el) => !el.isTypeOnly && named.has((el.propertyName ?? el.name).text))))
    })
  )
}

/** What the type reading holds: React's namespace (a default or namespace import of one of REACT_MODULES, or the module
    `require` or `import()` loads), a same-file context (`createContext`'s), a fragment type, and Suspense. */
type TypeLeaf = 'react' | 'context' | 'fragmentType' | 'suspense'
/** What React's namespace holds under a key: its fragment types, Suspense, and itself as `default`; a key the scan
    cannot read may be any of them. */
const reactMember = (key: string | undefined): TypeLeaf[] | undefined =>
  key === undefined ? ['fragmentType', 'suspense'] : key === 'Suspense' ? ['suspense'] : FRAGMENT_TYPES.has(key) ? ['fragmentType'] : key === 'default' ? ['react'] : undefined
/** What the kind reading holds: an element's kind (a fragment, or an element of its own), and what a clone's props and
    children are to it (`inert`: a clone is its element's kind). */
type Kind = 'fragment' | 'element' | 'inert'
/** What the token reading holds as a leaf: the token, and an element, a value of its own (a fragment is no element: the
    shared reading holds its children). */
type Leaf = 'token' | 'element'
/** A value a node joins into copy: an expression, or the member a spread gives by its key (`[spread, 'fallback']`). */
type Joined = ts.Expression | [ts.Expression, string] | undefined

/** Every em-dash in `text` outside the sanctioned token, as `file:line text`. */
function violationsIn(text: string, file: string): string[] {
  if (!text.includes(EM_DASH)) return []
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const declarationOf = scopeResolver(source)
  const knownAs = knownAsIn(declarationOf)
  const calleeName = (call: ts.CallExpression) => knownAs(call.expression)?.name ?? ''
  /** The React element call a call is (one of ELEMENT_MAKERS, or cloneElement), by the name its callee is known by; a
      same-file function of that name is the file's own, as the shared reading holds it. */
  const elementCall = (call: ts.CallExpression): string | undefined => {
    const name = calleeName(call)
    if (!ELEMENT_MAKERS.has(name) && name !== 'cloneElement') return undefined
    const callee = unwrapHeld(call.expression)
    const declaration = ts.isIdentifier(callee) ? declarationOf(callee) : undefined
    const init = declaration && ts.isVariableDeclaration(declaration) && declaration.initializer ? unwrapHeld(declaration.initializer) : undefined
    const own = !!declaration && (ts.isFunctionDeclaration(declaration) || (!!init && (ts.isArrowFunction(init) || ts.isFunctionExpression(init))))
    return own ? undefined : name
  }
  const isToken = (n: ts.Node) => (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) && n.text === EM_DASH

  // React's types are values, read by the shared reading from where the file names them to where an element takes one
  // (a tag, an element call's first argument): under any import name, a member of React's namespace by name or literal
  // key, a same-file alias, destructuring, prop, parameter, conditional or return, and what `memo` wraps. A component
  // named Fragment that the file declares is its own; one imported from another module is out of reach (the module gap).
  /** Whether a call loads one of REACT_MODULES: the global `require`, or `import()`. */
  const loadsReact = (call: ts.CallExpression) => {
    const loader = call.expression.kind === ts.SyntaxKind.ImportKeyword || (ts.isIdentifier(call.expression) && call.expression.text === 'require' && !declarationOf(call.expression))
    const loaded = call.arguments[0]
    return loader && !!loaded && ts.isStringLiteralLike(loaded) && REACT_MODULES.has(loaded.text)
  }
  const typeLeafOf = (e: ts.Expression): TypeLeaf[] | undefined => {
    if (ts.isIdentifier(e)) {
      const declaration = declarationOf(e)
      if (!declaration || !REACT_MODULES.has(moduleOf(declaration) ?? '')) return undefined
      if (ts.isImportClause(declaration) || ts.isNamespaceImport(declaration)) return ['react']
      return ts.isImportSpecifier(declaration) ? reactMember((declaration.propertyName ?? declaration.name).text) : undefined
    }
    if (!ts.isCallExpression(e)) return undefined
    if (calleeName(e) === 'createContext') return ['context']
    return loadsReact(e) ? ['react'] : undefined
  }
  let typesRead: HeldValues<TypeLeaf> | undefined
  const types = () =>
    (typesRead ??= heldValues<TypeLeaf>(source, typeLeafOf, {
      memberLeaf: (leaf, key) => (leaf === 'react' ? reactMember(key) : leaf === 'context' && (key === 'Provider' || key === undefined) ? ['fragmentType'] : undefined),
    }))
  const readsTypes = namesReact(source, text)
  const typeLeaves = (type: ts.Expression | undefined) => (type && readsTypes ? leavesOf(types().valueOf(type)) : new Map<TypeLeaf, number>())
  /** Whether an element of this type renders its children into its parent: one of React's FRAGMENT_TYPES or its
      Suspense, or a same-file context's Provider. */
  const isFragmentType = (type: ts.Expression | undefined) => {
    const leaves = typeLeaves(type)
    return leaves.has('fragmentType') || leaves.has('suspense')
  }
  const isSuspense = (type: ts.Expression) => typeLeaves(type).has('suspense')
  /** The type a JSX tag names: none for an intrinsic element (`<span>`, `<my-chart>`) or a namespaced one. */
  const tagType = (opening: ts.JsxOpeningLikeElement): ts.Expression | undefined => {
    const tag = opening.tagName
    return ts.isJsxNamespacedName(tag) || (ts.isIdentifier(tag) && /^[a-z]|-/.test(tag.text)) ? undefined : tag
  }
  const openingOf = (e: ts.JsxElement | ts.JsxSelfClosingElement) => (ts.isJsxElement(e) ? e.openingElement : e)
  /** The type an element call is given: its first argument, unless it is spread in (a gap). */
  const typeArgument = (call: ts.CallExpression) => (call.arguments[0] && !ts.isSpreadElement(call.arguments[0]) ? call.arguments[0] : undefined)

  // A clone's type is its element's (React's cloneElement keeps `element.type`), and its element is a value: written in
  // place, held, handed through a parameter or a prop, returned, or picked by Children's methods. The kind reading
  // follows it there; a clone's props and children do not change its kind.
  /** Whether an expression is a clone's argument after its first (its props or a child). */
  const cloneArgument = (e: ts.Expression): boolean => {
    let n: ts.Node = e
    while (ts.isParenthesizedExpression(n.parent) || ts.isAsExpression(n.parent) || ts.isSatisfiesExpression(n.parent) || ts.isNonNullExpression(n.parent) || ts.isTypeAssertionExpression(n.parent)) n = n.parent
    return ts.isCallExpression(n.parent) && n.parent.arguments.indexOf(n as ts.Expression) > 0 && elementCall(n.parent) === 'cloneElement'
  }
  const kindLeafOf = (e: ts.Expression): Kind[] | undefined => {
    if (cloneArgument(e)) return ['inert']
    if (ts.isJsxFragment(e)) return ['fragment']
    if (ts.isJsxElement(e) || ts.isJsxSelfClosingElement(e)) return isFragmentType(tagType(openingOf(e))) ? ['fragment'] : ['element']
    if (ts.isCallExpression(e) && ELEMENT_MAKERS.has(elementCall(e) ?? '')) return isFragmentType(typeArgument(e)) ? ['fragment'] : ['element']
    return undefined
  }
  let kindsRead: HeldValues<Kind> | undefined
  const kinds = () => (kindsRead ??= heldValues<Kind>(source, kindLeafOf))
  /** Whether a clone may be a fragment: its element may be one. */
  const clonesFragment = (call: ts.CallExpression) => {
    const element = typeArgument(call)
    return !!element && leavesOf(kinds().valueOf(element)).has('fragment')
  }

  /** The parents that render their children into their own parent: `<>`, and an element of a fragment type. */
  const fragment = (parent: ts.JsxElement | ts.JsxFragment) => ts.isJsxFragment(parent) || isFragmentType(tagType(parent.openingElement))
  const values = heldValues<Leaf>(
    source,
    (e) => {
      if (isToken(e)) return ['token']
      // An element is a value of its own; a fragment, `<>` or an element of a fragment type made by JSX, React's element
      // calls or a clone of one, is its children (the shared reading holds them).
      if (ts.isJsxElement(e) || ts.isJsxSelfClosingElement(e)) return isFragmentType(tagType(openingOf(e))) ? undefined : ['element']
      if (!ts.isCallExpression(e)) return undefined
      const name = elementCall(e)
      if (!name) return undefined
      if (name === 'cloneElement') return clonesFragment(e) ? undefined : ['element']
      return isFragmentType(typeArgument(e)) ? undefined : ['element']
    },
    // The shared reading follows each same-file call into what the function returns (E76), so a formatter's fallback
    // fails where its call is joined into copy; the self-check's E76 plants (88 to 97) fail if it stops.
    { textLeaf: (jsxText) => (jsxText.text.trim() === EM_DASH ? ['token'] : undefined), suspends: isSuspense },
  )
  const holdsToken = (joined: Joined) => {
    if (!joined) return false
    const [e, key] = Array.isArray(joined) ? joined : [joined, undefined]
    const value = values.valueOf(ts.isSpreadElement(e) ? e.expression : e)
    return leavesOf(key === undefined ? value : propertyOf(value, key)).has('token')
  }

  /** The children an element renders beside each other, as written: an array among them is its elements, which React
      renders as siblings (`{['—', ' sh']}`, the runtime's `children: […]`), and a spread is several. Each is joined
      when there are two or more. */
  const besideEachOther = (children: readonly ts.Expression[]): ts.Expression[] => {
    const items: ts.Expression[] = []
    let several = false
    const add = (e: ts.Expression): void => {
      const x = unwrapHeld(e)
      if (ts.isSpreadElement(x)) {
        several = true
        items.push(x.expression)
      } else if (ts.isArrayLiteralExpression(x)) {
        for (const element of x.elements) if (!ts.isOmittedExpression(element)) add(element)
      } else items.push(e)
    }
    children.forEach(add)
    return several || items.length > 1 ? items : []
  }
  /** The children an element call hands the element it makes, as written: createElement's and cloneElement's arguments
      from the third on, or else (and always for the runtime's jsx, jsxs and jsxDEV) the `children` its props literal
      sets. */
  const handedChildren = (call: ts.CallExpression): ts.Expression[] => {
    const name = elementCall(call)
    if ((name === 'createElement' || name === 'cloneElement') && call.arguments.length > 2) return [...call.arguments.slice(2)]
    const props = call.arguments[1] && unwrapHeld(call.arguments[1])
    if (!props || !ts.isObjectLiteralExpression(props)) return []
    let given: ts.Expression[] = []
    for (const p of props.properties) {
      if (ts.isPropertyAssignment(p) && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) && p.name.text === 'children') given = [p.initializer]
      else if (ts.isShorthandPropertyAssignment(p) && p.name.text === 'children') given = [p.name]
    }
    return given
  }
  /** The values a JSX element's attributes give one prop: each attribute of that name, and what each spread gives under
      it. */
  const attributeValues = (opening: ts.JsxOpeningLikeElement, name: string): Joined[] =>
    opening.attributes.properties.flatMap((attribute): Joined[] => {
      if (ts.isJsxSpreadAttribute(attribute)) return [[attribute.expression, name]]
      if (!ts.isIdentifier(attribute.name) || attribute.name.text !== name) return []
      const init = attribute.initializer
      return [!init ? undefined : ts.isJsxExpression(init) ? init.expression : init]
    })

  /** The values a node joins into copy (see the header). */
  const joinedAt = (node: ts.Node): Joined[] => {
    if (ts.isBinaryExpression(node) && (node.operatorToken.kind === ts.SyntaxKind.PlusToken || node.operatorToken.kind === ts.SyntaxKind.PlusEqualsToken)) {
      return [node.left, node.right]
    }
    if (ts.isTemplateSpan(node)) return [node.expression]
    if (ts.isJsxExpression(node) && !ts.isJsxAttribute(node.parent)) {
      if (!node.expression) return []
      // Beside siblings it is joined; alone, an array's elements (or a spread child's) are beside each other.
      if (!soleChild(node, fragment) || node.dotDotDotToken) return [node.expression]
      return besideEachOther([node.expression])
    }
    // An element of a fragment type written among siblings renders into its parent what its props give it: its
    // `children` when none are written inside it, and a Suspense's fallback.
    if ((ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) && (ts.isJsxElement(node.parent) || ts.isJsxFragment(node.parent))) {
      const opening = openingOf(node)
      const type = tagType(opening)
      if (!type || !isFragmentType(type)) return []
      const written = ts.isJsxElement(node) && node.children.some(writtenChild)
      if (soleChild(node, fragment)) {
        return written ? [] : besideEachOther(attributeValues(opening, 'children').filter((v): v is ts.Expression => !!v && !Array.isArray(v)))
      }
      return [...(written ? [] : [node]), ...(written && isSuspense(type) ? attributeValues(opening, 'fallback') : [])]
    }
    if (!ts.isCallExpression(node)) return []
    const name = calleeName(node)
    const args = node.arguments
    const callee = unwrapHeld(node.expression)
    const receiver = ts.isPropertyAccessExpression(callee) ? callee.expression : undefined
    if (elementCall(node)) return besideEachOther(handedChildren(node))
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
    for (const joined of joinedAt(node)) if (holdsToken(joined)) report(Array.isArray(joined) ? joined[0] : joined!, EM_DASH)
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
      "import { cloneElement, cloneElement as copyOf, Children, StrictMode, Profiler, Suspense, Activity, createContext, createFactory, memo, lazy } from 'react'",
      "import { jsx as make, jsxs, Fragment as RuntimeFragment } from 'react/jsx-runtime'",
      "import { jsxDEV } from 'react/jsx-dev-runtime'",
      'const f = cloneElement(<Fragment>—</Fragment>)',
      'export const CV = () => <p>{f} shares</p>',
      'export const CW = () => <p>{cloneElement(<>—</>)} shares</p>',
      'export const CX = () => <p>{React.cloneElement(FRAG)} shares</p>',
      "export const CY = () => <p>{copyOf(HELD_FRAGMENT, { key: 'k' })} shares</p>",
      "export const CZ = () => <p>{ReactNs['cloneElement'](createElement(Fragment, null, '—'))} shares</p>",
      'const { cloneElement: dup } = React',
      'export const DA = () => <p>{dup(cloneElement(<>—</>))} shares</p>',
      'const cloned = (el: ReactElement) => cloneElement(el)',
      'export const DB = () => <p>{cloned(<>—</>)} shares</p>',
      'export const DC = () => <p>{cloneElement(<span />, null, <>—</>)} shares</p>',
      "export const DD = () => <p>{cloneElement(cloneElement(<span />, null, <>x</>), null, '—')} shares</p>",
      "export const DE = () => <p>{cloneElement(<>x</>, null, '—')} shares</p>",
      "export const DF = () => <p>{cloneElement(<>x</>, { children: '—' })} shares</p>",
      "export const DG = () => cloneElement(<>x</>, null, '—', ' shares')",
      'export const DH = () => <td>{cloneElement(FRAG)}</td>',
      'export const DI = () => <p>{Children.only(<>—</>)} shares</p>',
      'export const DJ = () => <p>{Children.toArray(FRAG)} shares</p>',
      'export const DK = () => <p>{Children.map(FRAG, (c) => c)} shares</p>',
      'export const DL = () => <p>{React.Children.map(HELD_FRAGMENT, (c) => cloneElement(c))} shares</p>',
      'export const DM = () => <td>{Children.only(FRAG)}</td>',
      "export const DN = () => <p>{make(Fragment, { children: '—' })} shares</p>",
      "export const DO = () => jsxs('p', { children: ['—', ' shares'] })",
      "export const DP = () => <p>{jsxDEV(RuntimeFragment, { children: '—' }, undefined, false, undefined, undefined)} shares</p>",
      "export const DQ = () => jsx('td', { children: '—' })",
      'export const DR = () => <p><Fragment children="—" /> shares</p>',
      "export const DS = () => <p>{createElement(Fragment, { children: '—' })} shares</p>",
      "export const DT = () => <td><Fragment children={['—', ' sh']} /></td>",
      'export const DU = () => <p><StrictMode>—</StrictMode> shares</p>',
      'export const DV = () => <p><Profiler id="p" onRender={() => {}}>—</Profiler> shares</p>',
      'export const DW = () => <p><Suspense fallback="—"><b>x</b></Suspense> shares</p>',
      'export const DX = () => <p><Activity>—</Activity> shares</p>',
      "const Ctx = createContext('')",
      'export const DY = () => <p><Ctx.Provider value="x">—</Ctx.Provider> shares</p>',
      'const Passes = memo(Fragment)',
      'export const DZ = () => <p><Passes>—</Passes> shares</p>',
      'export const EA = () => <td><Suspense fallback="—"><b>x</b></Suspense></td>',
      "const WAITING = <Suspense fallback={'—'}><b>x</b></Suspense>",
      'export const EB = () => <p>{WAITING} shares</p>',
      'const Shell = ({ As }: { As: ElementType }) => { const shown = <As fallback="—"><b>x</b></As>; return <p>{shown} shares</p> }',
      'export const EC = () => <Shell As={Suspense} />',
      "const Required = require('react')",
      'export const ED = () => <p><Required.Fragment>—</Required.Fragment> shares</p>',
      "export async function EE() { const Loaded = await import('react'); return <p><Loaded.Fragment>—</Loaded.Fragment> shares</p> }",
      "export const EF = () => <p>{['—', ' shares']}</p>",
      "export const EG = () => createElement('p', null, ['—', ' shares'])",
      "export const EH = () => <td>{['—']}</td>",
      "const PARTS = ['—', ' shares']",
      'export const EI = () => <td>{PARTS}</td>',
      "export const EJ = () => <p><Ctx.Consumer>{() => '—'}</Ctx.Consumer> shares</p>",
      "export const EK = () => <p>{createFactory(Fragment)(null, '—')} shares</p>",
      "export const EL = () => <p>{createElement(...([Fragment, null, '—'] as const))} shares</p>",
      'const Later = lazy(async () => ({ default: memo(Fragment) }))',
      'export const EM = () => <p><Later>—</Later> shares</p>',
      "export const EN = () => <p>{cloneElement(FRAG, null, 'x')} shares</p>",
      "export function EO(v?: string) { const jsx = (x?: string) => x ?? '—'; return <p>{jsx(v)} sh</p> }",
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
    // Fragment that the file declares (141) stays an element and passes beside a unit, and so does one imported from
    // another module (142: the module gap, since it may be React's re-exported). React's types are values: a fragment
    // written as a JSX runtime call (143) and React's Fragment handed in through a prop (Wrap's `<As>`, 144, given at
    // 145) fail.
    // React's element API (147 to 149 import it). Codex's clone of a fragment, held (150, read at 151), fails, and so
    // do a clone written in place (152), one of a held fragment under `React.cloneElement` (153), under a renamed import
    // with props (154), under a namespace's literal key of a created fragment (155), under a destructured name of
    // another clone (156, at 157), and one of a parameter given a fragment (158, at 159). A clone's type is its
    // element's, so a span's clone handed a fragment (160), and the clone of such a clone (161), stay elements. A
    // fragment's clone renders what it is handed, by argument (162) or by props (163), and the children it is handed
    // sit beside each other (164); alone in a cell it passes (165). Children.only (166), toArray (167) and map, whose
    // callback is handed the fragment whole and may clone it (168, 169), keep it a fragment; alone, it passes (170). The
    // JSX runtime's jsx under a renamed import (171), jsxs's children array (172) and jsxDEV with the runtime's own
    // Fragment (173) fail; jsx's sole child passes (174). Children given by props fail: a Fragment's `children`
    // attribute (175), createElement's props (176), and an array there, whose elements sit beside each other (177).
    // React's other types that render their children into their parent: StrictMode (178), Profiler (179), Suspense's
    // fallback (180), Activity (181), a same-file context's Provider (182, at 183) and memo(Fragment) (184, at 185) fail;
    // a Suspense alone in a cell passes (186); a held Suspense's fallback (187, at 188) and that of a Suspense handed in
    // through a prop (189, given at 190) fail. React read by `require` (191, at 192) and by `await import()` (193). An
    // array written as children renders its elements beside each other (194, 195); one alone passes (196). Planted
    // gaps: an array held in a name (197, read at 198), a context's Consumer (199), createFactory (200), arguments spread
    // into createElement (201) and a lazy type (202, at 203). A clone handed children keeps its element's own in this
    // reading, an over-read that fails closed (204). A same-file function of a maker's name is the file's own: its
    // fallback fails where its call is joined (205).
    expect(violationsIn(src, file)).toEqual(
      [8, 9, 10, 11, 14, 15, 16, 17, 21, 22, 26, 28, 31, 39, 42, 43, 46, 51, 51, 51, 52, 53, 56, 58, 60, 61, 63, 69, 71, 72, 73, 74, 74, 75, 75, 76, 78, 82, 83, 84, 85, 86, 89, 90, 91, 92, 92, 94, 95, 96, 97, 103, 104, 105, 122, 123, 124, 125, 126, 128, 131, 132, 133, 134, 135, 143, 144, 146, 151, 152, 153, 154, 155, 157, 159, 162, 163, 164, 166, 167, 168, 169, 171, 172, 173, 175, 176, 177, 178, 179, 180, 181, 183, 185, 188, 189, 192, 193, 194, 195, 204, 205].map(
        (line) => `features/zzprobe/Probe.tsx:${line} —`,
      ),
    )
  })

  // Every source file under SCANNED_DIRS through the shared reader, React's types and kinds read as values: about
  // four seconds alone, past vitest's five under a loaded runner, so the scan carries its own time limit.
  it('finds no em-dash in any string literal, template literal, or JSX text', () => {
    const violations = SCANNED_DIRS.flatMap((dir) => sourceFiles(path.join(FRONTEND_ROOT, dir))).flatMap(
      emDashViolations,
    )
    expect(
      violations,
      `Em-dash found in copy. Restructure the sentence instead (docs/voice-and-style.md): ` +
        `split it, use a colon, or a middot for compact labels.\n${violations.join('\n')}`,
    ).toEqual([])
  }, 30_000)
})
