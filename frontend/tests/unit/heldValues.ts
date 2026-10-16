import ts from 'typescript'

/**
 * What a same-file value holds, followed from where it is written to where it is used, for the gates that read a
 * value rather than its syntax: brandVoiceRules.spec.ts's heading icons and reservedGlyphs.spec.ts's glyph counts. One
 * reading for both, so a shape one gate follows the other follows too (lessons/test-gates-must-be-as-wide-as-their-rule.md:
 * the family is taken from the language, not from the forms a review names).
 *
 * A value is the leaves it may be (the gate says what a leaf is: an icon's import, a glyph's root), each with how
 * many times it renders; for an object or an array, what each property or element holds; and the same-file functions
 * it may be. A leaf may have members (a namespace import: the gate's `memberLeaf` names the leaf its member is by key),
 * so a namespace held by another name, assigned, destructured or passed on is followed like any other value. Counts add where a value renders its parts together (an element's tag and children:
 * `<><QuotesIcon /><QuotesIcon /></>` renders the glyph twice) and take the larger where it renders one or the other (a
 * conditional's arms, `||`, `??`, a member read by a key the scan cannot read, the values one name is given in turn).
 *
 * A name holds every value it is given, resolved by scope (the nearest enclosing declaration, so a name two functions
 * each declare reads its own function's binding, and a parameter or a function of that name shadows an outer one):
 *  - its declaration's initializer, a destructuring of it (object and array patterns, nested, each element with its
 *    default, which renders when the member is missing, and a rest element the rest: an array's elements from its
 *    place on, re-indexed, or the properties the pattern does not name) and each later assignment (`=`, `||=`, `&&=`,
 *    `??=`, and a destructuring assignment with its defaults and its rest);
 *  - as a loop's variable, each element of what it iterates (`for (const Mark of MARKS)`, a pattern or a name assigned);
 *  - as a parameter, its default and what each same-file call passes it: a direct call (`render(QuotesIcon)`, a spread
 *    argument any element, a rest parameter the arguments from its place on, by position), a JSX element of a same-file component (its props object: each attribute, each spread's
 *    properties, the children as `children`), React's `createElement` of one, a callback handed to an array's methods
 *    (`MARKS.map((Mark) => …)`: each element; `reduce`'s accumulator its initial value and each return; `sort`'s two
 *    elements), to `Array.from`, to React's `Children.map` and `Children.forEach` (each child), and a function handed on
 *    by a name, a property, an argument or a return, however it reached the call (`each((Mark) => …)` where `each`
 *    calls its parameter);
 *  - what the code puts in an object or an array after making it: a property assigned (`BOX.mark = QuotesIcon`, nested,
 *    or under a key the scan cannot read, which any read may reach), an element pushed, unshifted or spliced in, a
 *    `Map`'s `set`, and `Object.assign` onto it.
 * An expression holds:
 *  - a member read by name or literal key (`MARK.alert`, `MARK['alert']`, a nested `A.b.c`, a `Map`'s `get`), and one
 *    read by a key the scan cannot read (`MARK[kind]`), which may be any property;
 *  - an object literal's properties, spreads and methods, in source order, so a later property overrides a spread's;
 *  - an array literal's elements by index (`[QuotesIcon]` read as `marks[0]`); past a spread the indices are unknown,
 *    so a literal index there may read any element from the spread on;
 *  - a conditional's two arms, both sides of `||` and `??`, the right of `&&`, an assignment's value, an `await`;
 *  - a JSX element's tag and its children (`<span><BellIcon /></span>` and `<><BellIcon /></>` hold it, as do
 *    `{expressions}` among the children), and the same for React's `createElement` (its type and children) and
 *    `cloneElement` (its element and children); a same-file component's element, by JSX or `createElement`, also
 *    holds what the component returns, each time it is rendered (`<AlertMark />` where `AlertMark` returns
 *    `<BellIcon />`), so a glyph or an icon a component draws is read where the component is rendered;
 *  - a call: a same-file function's returns (an arrow's expression, each `return` outside nested functions); an
 *    array's `find`, `findLast`, `at`, `pop` and `shift` (an element), `filter`, `slice`, `splice`, `concat`, `sort`,
 *    `reverse`, `flat` and their copying forms (its elements), `map` and `flatMap` (what the callback returns) and
 *    `reduce` (its accumulator); `Object.values`, `Object.entries` (each value at index 1), `Object.assign` (its
 *    target, with every source's properties), `Object.freeze`, `Object.seal` and `Object.preventExtensions` (what
 *    they are given), `Array.from`; React's `Children.map` (what the callback returns), `Children.toArray` and
 *    `Children.only`, `useMemo` (what its callback returns), `useCallback` (its callback), and `memo` and
 *    `forwardRef` (the component they wrap);
 *  - parentheses, `as`, `satisfies`, `<T>` and `!`.
 * Out of its reach, for each gate to name and plant as a gap: a value that crosses modules (an app module's export or a
 * context's), what React state holds after its setter or a reducer runs, a class's fields and `this`, a promise's
 * `then` and a generator's yields. One over-count, which fails closed: a parameter is not told apart by call, so it
 * holds what every same-file call passes it, and a function called with different values reads all of them at each
 * call (a component rendered once with each of two glyphs counts both at each render). A value that grows through its own reads (`const a = <>{a}</>`, or a
 * component that passes its own children back to itself with more added) never settles: the scan throws instead of
 * settling on an arbitrary count.
 */
export interface Held<L> {
  /** Each leaf the value may be, with how many times it renders. */
  leaves: Map<L, number>
  props: Map<string, Held<L>> | null
  /** The same-file functions the value may be: a call through it binds their parameters and reads their returns. */
  fns: Set<Fn> | null
}

/** A function the scan follows: a declaration, an arrow, a function expression or an object literal's method. */
export type Fn = ts.FunctionDeclaration | ts.ArrowFunction | ts.FunctionExpression | ts.MethodDeclaration

export interface HeldValues<L> {
  /** What an expression holds. */
  valueOf(e: ts.Expression): Held<L>
  /** What the binding an identifier reads holds, when it holds a leaf or a function; the binding is resolved by scope. */
  holderOf(id: ts.Identifier): Held<L> | undefined
  /** What a same-file component renders where this element (a JSX tag or a `createElement` call) renders it: its
      returns; empty for any other element. */
  renderOf(element: ts.JsxOpeningLikeElement | ts.CallExpression): Held<L>
  /** The nodes a value is handed on through (an initializer, an assignment, an argument or a prop to a same-file
      function, what a loop or a callback iterates, what is put in an object): a hold, not a use. */
  held: Set<ts.Node>
}

const empty = <L>(): Held<L> => ({ leaves: new Map(), props: null, fns: null })
const fnValue = <L>(fn: Fn): Held<L> => ({ leaves: new Map(), props: null, fns: new Set([fn]) })
const withProps = <L>(entries: Array<[string, Held<L>]>): Held<L> => ({ leaves: new Map(), props: new Map(entries), fns: null })

const add = (x: number, y: number) => x + y
/** Two counts of leaves joined leaf by leaf: added, or the larger. */
const joined = <L>(a: Map<L, number>, b: Map<L, number>, join: (x: number, y: number) => number): Map<L, number> => {
  const out = new Map(a)
  for (const [leaf, n] of b) out.set(leaf, out.has(leaf) ? join(out.get(leaf)!, n) : n)
  return out
}
const joinedProps = <L>(a: Held<L>, b: Held<L>): Map<string, Held<L>> | null => {
  if (!a.props && !b.props) return null
  const props = new Map(a.props ?? [])
  for (const [key, value] of b.props ?? []) props.set(key, props.has(key) ? union(props.get(key)!, value) : value)
  return props
}
const joinedFns = <L>(a: Held<L>, b: Held<L>): Set<Fn> | null => (a.fns || b.fns ? new Set([...(a.fns ?? []), ...(b.fns ?? [])]) : null)

/** Either value (a conditional's arms, `||`, `??`, a name's values in turn): the leaves of both, each at the larger
    count, each property either side holds, and the functions of both. */
export function union<L>(a: Held<L>, b: Held<L>): Held<L> {
  return { leaves: joined(a.leaves, b.leaves, Math.max), props: joinedProps(a, b), fns: joinedFns(a, b) }
}

/** Both values, rendered together (an element's tag and its children): each leaf as many times as the two render it. */
const both = <L>(a: Held<L>, b: Held<L>): Held<L> => ({ leaves: joined(a.leaves, b.leaves, add), props: joinedProps(a, b), fns: joinedFns(a, b) })

/** Every leaf a value holds, its properties' included, with how many times it renders: a value read whole reads
    each of its properties. */
export function leavesOf<L>(value: Held<L>): Map<L, number> {
  let out = new Map(value.leaves)
  for (const prop of value.props?.values() ?? []) out = joined(out, leavesOf(prop), add)
  return out
}

/** Whether a value holds nothing to follow: no leaf and no function, here or in a property. */
const vacant = <L>(value: Held<L>): boolean =>
  value.leaves.size === 0 && !value.fns?.size && [...(value.props?.values() ?? [])].every(vacant)

/** The key prefix of an array's elements whose indices the scan cannot know (past a spread, pushed, built by a call). */
const REST = '…'
/** The key a property is written under when the scan cannot read the key (`BOX[key] = …`): any read may reach it. */
const ANY = '*'

/** A property of a value by its key: undefined for a key the scan cannot read, which may be any property; a literal index
    an array's known elements do not reach may read any element past them; a property written under a key the scan
    cannot read may be any member. */
function propertyOf<L>(base: Held<L>, key: string | undefined): Held<L> {
  if (!base.props) return empty()
  if (key === undefined) return [...base.props.values()].reduce(union, empty<L>())
  const rest = () => [...base.props!].filter(([k]) => k.startsWith(REST)).map(([, v]) => v).reduce(union, empty<L>())
  const named = base.props.get(key) ?? (/^\d+$/.test(key) ? rest() : empty<L>())
  const any = base.props.get(ANY)
  return any ? union(named, any) : named
}
/** An array whose elements the scan cannot place: each may be this. */
const arrayOf = <L>(element: Held<L>): Held<L> => (vacant(element) ? empty<L>() : withProps([[`${REST}0`, element]]))
/** What an array rest element takes (`const [first, ...rest] = …`, a rest parameter of the arguments): the elements from
    `from` on, re-indexed from 0; an element whose index the scan cannot know stays unplaced, and one written under a key
    the scan cannot read may be any of them. */
const restOf = <L>(value: Held<L>, from: number): Held<L> => {
  const props = new Map<string, Held<L>>()
  for (const [key, prop] of value.props ?? []) {
    if (!/^\d+$/.test(key)) props.set(key, prop)
    else if (Number(key) >= from) props.set(String(Number(key) - from), prop)
  }
  return { leaves: new Map(), props, fns: null }
}
/** What an object rest element takes (`const { a, ...rest } = …`): the properties the pattern does not name, and its
    leaves, so a leaf with members (a namespace) still names its other members. */
const othersOf = <L>(value: Held<L>, named: ReadonlySet<string>): Held<L> => ({
  leaves: value.leaves,
  props: value.props && new Map([...value.props].filter(([key]) => !named.has(key))),
  fns: null,
})
/** A call's arguments as an array: each at its position, and from a spread argument on, unplaced. */
const argumentsOf = <L>(passed: Array<Held<L>>, tail?: Held<L>): Held<L> => {
  const props = new Map<string, Held<L>>()
  passed.forEach((value, i) => {
    if (!vacant(value)) props.set(String(i), value)
  })
  if (tail && !vacant(tail)) props.set(`${REST}0`, tail)
  return { leaves: new Map(), props, fns: null }
}

const size = <L>(value: Held<L>): number =>
  [...value.leaves.values()].reduce(add, 0) +
  (value.fns?.size ?? 0) +
  [...(value.props?.entries() ?? [])].reduce((n, [key, prop]) => n + key.length + size(prop), 0)

export const unwrapHeld = (e: ts.Expression): ts.Expression =>
  ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isSatisfiesExpression(e) || ts.isNonNullExpression(e) || ts.isTypeAssertionExpression(e)
    ? unwrapHeld(e.expression)
    : e

/** A member's key read by name or literal key, or undefined for a key the scan cannot read. */
export const memberKey = (n: ts.PropertyAccessExpression | ts.ElementAccessExpression): string | undefined =>
  ts.isPropertyAccessExpression(n)
    ? n.name.text
    : ts.isStringLiteralLike(n.argumentExpression) || ts.isNumericLiteral(n.argumentExpression)
      ? n.argumentExpression.text
      : undefined

const propertyKey = (name: ts.PropertyName | ts.BindingName): string | undefined =>
  ts.isIdentifier(name) || ts.isStringLiteral(name) || ts.isNumericLiteral(name) ? name.text : undefined

const literalKey = (e: ts.Expression | undefined): string | undefined =>
  e && (ts.isStringLiteralLike(e) || ts.isNumericLiteral(e)) ? e.text : undefined

const ASSIGNMENTS = new Set<ts.SyntaxKind>([
  ts.SyntaxKind.EqualsToken,
  ts.SyntaxKind.BarBarEqualsToken,
  ts.SyntaxKind.AmpersandAmpersandEqualsToken,
  ts.SyntaxKind.QuestionQuestionEqualsToken,
])

/** Whether an expression is written, not read: an assignment's target (each target of a destructuring assignment
    included) or a `for … of` or `for … in` loop's target. */
export function isWrite(node: ts.Node): boolean {
  let n = node
  for (let p = n.parent; p; n = p, p = p.parent) {
    if (ts.isBinaryExpression(p) && ASSIGNMENTS.has(p.operatorToken.kind)) return p.left === n
    if (ts.isForOfStatement(p) || ts.isForInStatement(p)) return p.initializer === n
    // Climb through a destructuring assignment's pattern: its literals, a property's target and a default's target.
    const inPattern =
      ts.isObjectLiteralExpression(p) ||
      ts.isArrayLiteralExpression(p) ||
      ts.isParenthesizedExpression(p) ||
      ts.isShorthandPropertyAssignment(p) ||
      ts.isSpreadElement(p) ||
      ts.isSpreadAssignment(p) ||
      (ts.isPropertyAssignment(p) && p.initializer === n)
    if (!inPattern) return false
  }
  return false
}

/**
 * The declaration a name reads where it is written: the nearest enclosing scope that declares it. A block declares
 * its `const`, `let`, functions and classes; a function its parameters and every `var` inside it; the file its
 * imports; a `for` statement and a `catch` clause their own bindings. The node returned is the declaration of a bare
 * name and the element of a destructured one. Undefined for a global.
 */
export function scopeResolver(sf: ts.SourceFile): (id: ts.Identifier) => ts.Node | undefined {
  const declared = new Map<ts.Node, Map<string, ts.Node>>()
  const declare = (scope: ts.Node | undefined, name: string, node: ts.Node) => {
    if (!scope) return
    const names = declared.get(scope) ?? new Map<string, ts.Node>()
    declared.set(scope, names)
    if (!names.has(name)) names.set(name, node)
  }
  const functionScope = (n: ts.Node) => ts.isSourceFile(n) || ts.isFunctionLike(n) || ts.isModuleBlock(n)
  const blockScope = (n: ts.Node) =>
    functionScope(n) || ts.isBlock(n) || ts.isCaseBlock(n) || ts.isCatchClause(n) || ts.isForStatement(n) || ts.isForInStatement(n) || ts.isForOfStatement(n)
  const enclosing = (n: ts.Node, isScope: (n: ts.Node) => boolean) => {
    let up = n.parent
    while (up && !isScope(up)) up = up.parent
    return up
  }
  const bind = (name: ts.BindingName, node: ts.Node, scope: ts.Node | undefined): void => {
    if (ts.isIdentifier(name)) declare(scope, name.text, node)
    else for (const el of name.elements) if (!ts.isOmittedExpression(el)) bind(el.name, el, scope)
  }
  const visit = (n: ts.Node): void => {
    if (ts.isVariableDeclaration(n)) {
      const list = n.parent
      const blockScoped = ts.isVariableDeclarationList(list) && (list.flags & ts.NodeFlags.BlockScoped) !== 0
      bind(n.name, n, ts.isCatchClause(list) ? list : enclosing(n, blockScoped ? blockScope : functionScope))
    } else if (ts.isParameter(n)) bind(n.name, n, n.parent)
    else if ((ts.isFunctionDeclaration(n) || ts.isClassDeclaration(n)) && n.name) declare(enclosing(n, blockScope), n.name.text, n)
    else if (ts.isFunctionExpression(n) && n.name) declare(n, n.name.text, n)
    else if (ts.isImportClause(n) && n.name) declare(sf, n.name.text, n)
    else if (ts.isImportSpecifier(n) || ts.isNamespaceImport(n)) declare(sf, n.name.text, n)
    ts.forEachChild(n, visit)
  }
  visit(sf)
  return (id) => {
    for (let n: ts.Node | undefined = id.parent; n; n = n.parent) {
      const found = declared.get(n)?.get(id.text)
      if (found) return found
    }
    return undefined
  }
}

/** Array methods whose first argument is called with each element. */
const ELEMENT_CALLBACKS = new Set(['map', 'flatMap', 'forEach', 'filter', 'find', 'findLast', 'findIndex', 'findLastIndex', 'some', 'every'])
/** Array methods that return one of the elements. */
const ELEMENT_RESULTS = new Set(['find', 'findLast', 'at', 'pop', 'shift'])
/** Array methods that return an array of the elements (and, for `concat` and the splices, what they add). */
const ARRAY_RESULTS = new Set(['filter', 'slice', 'splice', 'toSpliced', 'concat', 'sort', 'toSorted', 'reverse', 'toReversed', 'flat', 'with'])

/**
 * The values of one source. `leafOf` names the leaves an expression is by itself (an import of an icon, a
 * namespace's member), or returns undefined.
 */
export function heldValues<L>(
  sf: ts.SourceFile,
  leafOf: (e: ts.Expression) => L[] | undefined,
  memberLeaf?: (leaf: L, key: string | undefined, node: ts.Node) => L[] | undefined,
): HeldValues<L> {
  // Keyed by the declaration (scopeResolver), never by the bare name.
  const holders = new Map<ts.Node, Held<L>>()
  /** A member of a value by its key: its property, and what a leaf with members is under the key (a namespace's
      member, by `memberLeaf`, placed at `node`, the read or the binding that takes it). */
  const memberOf = (base: Held<L>, key: string | undefined, node: ts.Node = sf): Held<L> => {
    const value = propertyOf(base, key)
    if (!memberLeaf || base.leaves.size === 0) return value
    const leaves = new Map<L, number>()
    for (const leaf of base.leaves.keys()) for (const own of memberLeaf(leaf, key, node) ?? []) leaves.set(own, (leaves.get(own) ?? 0) + 1)
    return leaves.size ? union(value, { leaves, props: null, fns: null }) : value
  }
  /** Any element of an array, any property of an object, or any member of a leaf with members. */
  const elementOf = (value: Held<L>): Held<L> => memberOf(value, undefined)
  const declarationOf = scopeResolver(sf)
  const isFn = (n: ts.Node | undefined): n is Fn =>
    !!n && (ts.isFunctionDeclaration(n) || ts.isArrowFunction(n) || ts.isFunctionExpression(n) || ts.isMethodDeclaration(n))
  /** A call's callee by its last name: `render` in `render()`, `map` in `MARKS.map()`, `createElement` in
      `React.createElement()`. */
  const calleeName = (call: ts.CallExpression): string => {
    const callee = unwrapHeld(call.expression)
    return ts.isIdentifier(callee) ? callee.text : ts.isPropertyAccessExpression(callee) ? callee.name.text : ''
  }
  /** What a call's callee is read from: `MARKS` in `MARKS.map()`, `React.Children` in `React.Children.map()`. */
  const receiverOf = (call: ts.CallExpression): ts.Expression | undefined => {
    const callee = unwrapHeld(call.expression)
    return ts.isPropertyAccessExpression(callee) ? callee.expression : undefined
  }
  /** Whether a call's receiver is this global (`Object`, `Array`: no declaration in the file) or React's `Children`
      (imported, or read as `React.Children`). */
  const receiverNamed = (call: ts.CallExpression, name: string): boolean => {
    const recv = receiverOf(call)
    const r = recv && unwrapHeld(recv)
    if (!r) return false
    if (ts.isPropertyAccessExpression(r)) return r.name.text === name
    return ts.isIdentifier(r) && r.text === name && (name === 'Children' || !declarationOf(r))
  }
  /** Whether an assignment's target, or the object a member is put in, is a same-file binding the scan holds: a name
      declared in the file (not an import or a function), read through any members. */
  const holdsTarget = (target: ts.Expression): boolean => {
    let t = unwrapHeld(target)
    while (ts.isPropertyAccessExpression(t) || ts.isElementAccessExpression(t)) t = unwrapHeld(t.expression)
    if (ts.isObjectLiteralExpression(t) || ts.isArrayLiteralExpression(t)) return true
    if (!ts.isIdentifier(t)) return false
    const declaration = declarationOf(t)
    return !!declaration && (ts.isVariableDeclaration(declaration) || ts.isBindingElement(declaration) || ts.isParameter(declaration))
  }

  // A function being read for its returns: a call of it inside its own returns (recursion) adds nothing more.
  const evaluating = new Set<Fn>()
  /** What a function returns: an arrow's expression body, and each `return` in its body outside the functions nested in it. */
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
  const returned = (fns: Iterable<Fn> | null | undefined, record?: Set<ts.Node>): Held<L> => {
    let value = empty<L>()
    for (const fn of fns ?? []) {
      if (evaluating.has(fn)) continue
      evaluating.add(fn)
      try {
        for (const r of returnsOf(fn)) value = union(value, valueOf(r, record))
      } finally {
        evaluating.delete(fn)
      }
    }
    return value
  }

  const valueOf = (e: ts.Expression, record?: Set<ts.Node>): Held<L> => {
    const x = unwrapHeld(e)
    const own = leafOf(x)
    if (own?.length) {
      record?.add(x)
      const leaves = new Map<L, number>()
      for (const leaf of own) leaves.set(leaf, (leaves.get(leaf) ?? 0) + 1)
      return { leaves, props: null, fns: null }
    }
    if (ts.isIdentifier(x)) {
      const declaration = declarationOf(x)
      if (isFn(declaration)) return fnValue(declaration)
      const holder = declaration && holders.get(declaration)
      if (!holder) return empty()
      record?.add(x)
      return holder
    }
    if (ts.isArrowFunction(x) || ts.isFunctionExpression(x)) return fnValue(x)
    if (ts.isAwaitExpression(x)) return valueOf(x.expression, record)
    if (ts.isPropertyAccessExpression(x) || ts.isElementAccessExpression(x)) {
      const value = memberOf(valueOf(x.expression), memberKey(x), x)
      if (leavesOf(value).size > 0) record?.add(x)
      return value
    }
    if (ts.isConditionalExpression(x)) return union(valueOf(x.whenTrue, record), valueOf(x.whenFalse, record))
    if (ts.isBinaryExpression(x)) {
      const op = x.operatorToken.kind
      if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken) return union(valueOf(x.left, record), valueOf(x.right, record))
      if (op === ts.SyntaxKind.AmpersandAmpersandToken) return valueOf(x.right, record)
      // An assignment is its value: the right side, or for `||=`, `&&=` and `??=` the old value or the right side.
      if (op === ts.SyntaxKind.EqualsToken) return valueOf(x.right, record)
      if (ASSIGNMENTS.has(op)) return union(valueOf(x.left), valueOf(x.right, record))
      return empty()
    }
    if (ts.isCallExpression(x)) return callValue(x, record)
    if (ts.isJsxSelfClosingElement(x) || ts.isJsxElement(x) || ts.isJsxFragment(x)) {
      const tag = ts.isJsxFragment(x) ? undefined : (ts.isJsxElement(x) ? x.openingElement : x).tagName
      let value = tag && (ts.isIdentifier(tag) || ts.isPropertyAccessExpression(tag)) ? valueOf(tag, record) : empty<L>()
      // A same-file component's element holds what the component renders, not the component.
      if (value.fns?.size) {
        const rendered = returned(value.fns, record)
        if (leavesOf(rendered).size > 0) record?.add(x)
        value = { ...rendered, fns: null }
      }
      for (const child of ts.isJsxSelfClosingElement(x) ? [] : x.children) {
        if (ts.isJsxElement(child) || ts.isJsxSelfClosingElement(child) || ts.isJsxFragment(child)) value = both(value, valueOf(child, record))
        else if (ts.isJsxExpression(child) && child.expression) value = both(value, valueOf(child.expression, record))
      }
      return value
    }
    if (ts.isArrayLiteralExpression(x)) {
      const props = new Map<string, Held<L>>()
      let index = 0
      let rest = 0
      const place = (value: Held<L>) => {
        if (!vacant(value)) props.set(index < 0 ? `${REST}${rest++}` : String(index), value)
      }
      for (const el of x.elements) {
        if (ts.isSpreadElement(el)) {
          index = -1
          for (const value of valueOf(el.expression, record).props?.values() ?? []) place(value)
          continue
        }
        if (!ts.isOmittedExpression(el)) place(valueOf(el, record))
        if (index >= 0) index++
      }
      return { leaves: new Map(), props, fns: null }
    }
    if (ts.isObjectLiteralExpression(x)) {
      const props = new Map<string, Held<L>>()
      for (const p of x.properties) {
        if (ts.isSpreadAssignment(p)) {
          for (const [key, value] of valueOf(p.expression, record).props ?? []) props.set(key, value)
          continue
        }
        if (ts.isMethodDeclaration(p)) {
          const key = propertyKey(p.name)
          if (key !== undefined) props.set(key, fnValue(p))
          continue
        }
        if (!ts.isPropertyAssignment(p) && !ts.isShorthandPropertyAssignment(p)) continue
        const key = propertyKey(p.name)
        if (key === undefined) continue
        const value = valueOf(ts.isPropertyAssignment(p) ? p.initializer : p.name, record)
        if (!vacant(value)) props.set(key, value)
        else props.delete(key)
      }
      return { leaves: new Map(), props, fns: null }
    }
    return empty()
  }

  /** What a call holds (see the header's list); empty for a call the scan cannot follow. */
  const callValue = (x: ts.CallExpression, record?: Set<ts.Node>): Held<L> => {
    const name = calleeName(x)
    const args = x.arguments
    const arg = (i: number) => (args[i] ? valueOf(args[i], record) : empty<L>())
    const fnsOf = (i: number) => (args[i] ? valueOf(args[i]).fns : null)
    // React's element calls hold what JSX would: the type and the children; a clone holds its element and children.
    if (name === 'createElement' || name === 'cloneElement') {
      let value = arg(0)
      if (name === 'createElement' && value.fns?.size) {
        const rendered = returned(value.fns, record)
        if (leavesOf(rendered).size > 0) record?.add(x)
        value = { ...rendered, fns: null }
      }
      for (let i = 2; i < args.length; i++) value = both(value, arg(i))
      return value
    }
    if (receiverNamed(x, 'Children')) {
      if (name === 'map') return arrayOf(returned(fnsOf(1), record))
      if (name === 'toArray' || name === 'only') return union(arg(0), elementOf(arg(0)))
      return empty()
    }
    if (receiverNamed(x, 'Object')) {
      if (name === 'values') return arrayOf(elementOf(arg(0)))
      if (name === 'entries') return arrayOf(withProps([['1', elementOf(arg(0))]]))
      // Object.assign gives back its target with every source's properties on it, so a compound component
      // (`Object.assign(Root, { Part })`) is still Root; freeze, seal and preventExtensions give back what they are given.
      if (name === 'assign') {
        const target = arg(0)
        const props = new Map<string, Held<L>>(target.props ?? [])
        for (let i = 1; i < args.length; i++) for (const [key, value] of arg(i).props ?? []) props.set(key, value)
        return { leaves: target.leaves, props, fns: target.fns }
      }
      if (name === 'freeze' || name === 'seal' || name === 'preventExtensions') return arg(0)
      return empty()
    }
    if (receiverNamed(x, 'Array') && name === 'from') return args[1] ? arrayOf(returned(fnsOf(1), record)) : arrayOf(elementOf(arg(0)))
    if (name === 'useMemo') return returned(fnsOf(0), record)
    if (name === 'useCallback') return arg(0)
    // React's component wrappers give back the component they wrap: `memo(Mark)`, `forwardRef((props, ref) => …)`.
    if (name === 'memo' || name === 'forwardRef') return arg(0)
    const recv = receiverOf(x)
    if (recv) {
      if (ELEMENT_RESULTS.has(name)) return elementOf(valueOf(recv, record))
      if (ARRAY_RESULTS.has(name)) {
        let element = elementOf(valueOf(recv, record))
        // What `concat`, `splice` and `with` add: an array's elements, or a value itself.
        const added = name === 'concat' ? args : name === 'splice' || name === 'toSpliced' ? args.slice(2) : name === 'with' ? args.slice(1) : []
        for (const a of added) {
          const v = valueOf(a, record)
          element = union(element, union(elementOf(v), { ...v, props: null }))
        }
        return arrayOf(element)
      }
      if (name === 'map' || name === 'flatMap') return arrayOf(returned(fnsOf(0), record))
      if (name === 'reduce' || name === 'reduceRight') return union(arg(1), returned(fnsOf(0), record))
      if (name === 'get' && args.length === 1) {
        const base = valueOf(recv)
        if (base.props) {
          const value = memberOf(base, literalKey(args[0]), x)
          if (leavesOf(value).size > 0) record?.add(x)
          return value
        }
      }
    }
    // A call of a same-file function holds what it returns.
    return returned(valueOf(x.expression).fns, record)
  }

  /** Gives a holder a value it may hold, beside those it holds already. */
  const give = (key: ts.Node, value: Held<L>) => {
    if (vacant(value)) return
    const before = holders.get(key)
    holders.set(key, before ? union(before, value) : value)
  }
  /** Gives a declared name its part of a value: a bare name the whole, each element of an object or array pattern its
      member, nested patterns included, with its default (which renders when the member is missing), and a rest element
      the rest: an array's elements from its place on (restOf), an object's properties the pattern does not name
      (othersOf; a key the scan cannot read names none). */
  const bindName = (name: ts.BindingName, value: Held<L>, node: ts.Node, record?: Set<ts.Node>): void => {
    if (ts.isIdentifier(name)) return give(node, value)
    const named = new Set<string>()
    name.elements.forEach((el, index) => {
      if (ts.isOmittedExpression(el)) return
      if (el.dotDotDotToken) return bindName(el.name, ts.isArrayBindingPattern(name) ? restOf(value, index) : othersOf(value, named), el, record)
      const key = ts.isArrayBindingPattern(name) ? String(index) : propertyKey(el.propertyName ?? el.name)
      if (key === undefined) return
      named.add(key)
      const member = memberOf(value, key, el)
      bindName(el.name, el.initializer ? union(member, valueOf(el.initializer, record)) : member, el, record)
    })
  }
  /** A destructuring assignment's element and its default (`[Mark = QuotesIcon] = …`). */
  const defaulted = (e: ts.Expression): [ts.Expression, ts.Expression | undefined] =>
    ts.isBinaryExpression(e) && e.operatorToken.kind === ts.SyntaxKind.EqualsToken ? [e.left, e.right] : [e, undefined]
  /** Gives an assignment's target a value: a name (its declaration's holder), a member of a same-file binding (what the
      code puts in an object after making it, nested, or under a key the scan cannot read), or each target of a
      destructuring pattern with its default, its rest taking the rest (restOf, othersOf). */
  const assign = (target: ts.Expression, value: Held<L>, record?: Set<ts.Node>): void => {
    const t = unwrapHeld(target)
    if (ts.isIdentifier(t)) {
      const declaration = declarationOf(t)
      if (declaration && !isFn(declaration)) give(declaration, value)
      return
    }
    if (ts.isPropertyAccessExpression(t) || ts.isElementAccessExpression(t)) {
      if (!vacant(value)) assign(t.expression, withProps([[memberKey(t) ?? ANY, value]]), record)
      return
    }
    if (ts.isObjectLiteralExpression(t)) {
      const named = new Set<string>()
      for (const p of t.properties) {
        if (ts.isSpreadAssignment(p)) assign(p.expression, othersOf(value, named), record)
        else if (ts.isPropertyAssignment(p)) {
          const key = propertyKey(p.name)
          if (key === undefined) continue
          named.add(key)
          const [inner, fallback] = defaulted(p.initializer)
          const member = memberOf(value, key, p)
          assign(inner, fallback ? union(member, valueOf(fallback, record)) : member, record)
        } else if (ts.isShorthandPropertyAssignment(p)) {
          named.add(p.name.text)
          const member = memberOf(value, p.name.text, p)
          assign(p.name, p.objectAssignmentInitializer ? union(member, valueOf(p.objectAssignmentInitializer, record)) : member, record)
        }
      }
      return
    }
    if (ts.isArrayLiteralExpression(t)) {
      t.elements.forEach((el, index) => {
        if (ts.isOmittedExpression(el)) return
        if (ts.isSpreadElement(el)) return assign(el.expression, restOf(value, index), record)
        const [inner, fallback] = defaulted(el)
        const member = memberOf(value, String(index), el)
        assign(inner, fallback ? union(member, valueOf(fallback, record)) : member, record)
      })
    }
  }
  /** Binds each parameter of these functions to what a call passes it, by position: a rest parameter takes the arguments
      from its place on, each at its position (restOf), and past a spread argument each parameter may take any of its
      elements. A parameter's default is bound where it is declared. */
  const pass = (fns: Set<Fn> | null | undefined, passed: Array<Held<L>>, tail?: Held<L>) => {
    const args = argumentsOf(passed, tail)
    for (const fn of fns ?? []) {
      fn.parameters.forEach((p, i) => bindName(p.name, p.dotDotDotToken ? restOf(args, i) : (passed[i] ?? tail ?? empty<L>()), p))
    }
  }
  /** A call's arguments by position, and from a spread argument on what any later position may take: any of its
      elements or any argument after it. */
  const passedBy = (args: readonly ts.Expression[], record?: Set<ts.Node>): [Array<Held<L>>, Held<L> | undefined] => {
    const passed: Array<Held<L>> = []
    let tail: Held<L> | undefined
    for (const a of args) {
      const v = ts.isSpreadElement(a) ? elementOf(valueOf(a.expression, record)) : valueOf(a, record)
      if (ts.isSpreadElement(a) || tail) tail = union(tail ?? empty<L>(), v)
      else passed.push(v)
    }
    return [passed, tail]
  }
  /** What a call gives a holder: a same-file function's parameters, a callback's, or an array or a `Map` it puts in. */
  const call = (x: ts.CallExpression, record?: Set<ts.Node>) => {
    const name = calleeName(x)
    const args = x.arguments
    const recv = receiverOf(x)
    const fnsAt = (i: number) => (args[i] ? valueOf(args[i]).fns : null)
    if (receiverNamed(x, 'Children') && (name === 'map' || name === 'forEach')) {
      const fns = fnsAt(1)
      if (fns?.size && args[0]) {
        const children = valueOf(args[0], record)
        pass(fns, [union(children, elementOf(children))])
      }
      return
    }
    if (receiverNamed(x, 'Array') && name === 'from') {
      const fns = fnsAt(1)
      if (fns?.size && args[0]) pass(fns, [elementOf(valueOf(args[0], record))])
      return
    }
    if (receiverNamed(x, 'Object') && name === 'assign') {
      if (!args[0] || !holdsTarget(args[0])) return
      const props = new Map<string, Held<L>>()
      for (const a of args.slice(1)) for (const [key, value] of valueOf(a, record).props ?? []) props.set(key, value)
      assign(args[0], { leaves: new Map(), props, fns: null }, record)
      return
    }
    if (name === 'createElement' && args[0]) {
      const fns = valueOf(args[0]).fns
      if (!fns?.size) return
      const props = args[1] ? valueOf(args[1], record) : empty<L>()
      let children = empty<L>()
      for (const a of args.slice(2)) children = both(children, valueOf(a, record))
      pass(fns, [vacant(children) ? props : union(props, withProps([['children', children]]))])
      // What the component returns renders here, not where it is written.
      returned(fns, record)
      return
    }
    if (recv) {
      if (ELEMENT_CALLBACKS.has(name)) {
        const fns = fnsAt(0)
        if (fns?.size) pass(fns, [elementOf(valueOf(recv, record))])
      } else if (name === 'reduce' || name === 'reduceRight') {
        const fns = fnsAt(0)
        // The accumulator is the initial value, then each return; the current value is each element.
        if (fns?.size) pass(fns, [union(args[1] ? valueOf(args[1], record) : empty<L>(), returned(fns)), elementOf(valueOf(recv, record))])
      } else if (name === 'sort' || name === 'toSorted') {
        const fns = fnsAt(0)
        if (fns?.size) {
          const element = elementOf(valueOf(recv, record))
          pass(fns, [element, element])
        }
      } else if ((name === 'push' || name === 'unshift' || name === 'splice') && holdsTarget(recv)) {
        // What the code puts in an array after making it, at indices the scan cannot know.
        const added = name === 'splice' ? args.slice(2) : [...args]
        const entries: Array<[string, Held<L>]> = []
        for (const a of added) {
          const v = ts.isSpreadElement(a) ? elementOf(valueOf(a.expression, record)) : valueOf(a, record)
          if (!vacant(v)) entries.push([`${REST}${a.pos}`, v])
        }
        if (entries.length) assign(recv, withProps(entries), record)
      } else if (name === 'set' && args.length === 2 && holdsTarget(recv)) {
        const v = valueOf(args[1], record)
        if (!vacant(v)) assign(recv, withProps([[literalKey(args[0]) ?? ANY, v]]), record)
      }
    }
    // A call of a same-file function, however the function reached the callee: each parameter takes what it is passed.
    const fns = valueOf(x.expression).fns
    if (fns?.size) pass(fns, ...passedBy(args, record))
  }
  /** A JSX element of a same-file component calls it with a props object: each attribute's value, each spread's
      properties (a later attribute overriding), and its children as `children`. */
  const render = (x: ts.JsxElement | ts.JsxSelfClosingElement, record?: Set<ts.Node>) => {
    const opening = ts.isJsxElement(x) ? x.openingElement : x
    const tag = opening.tagName
    if (!ts.isIdentifier(tag) && !ts.isPropertyAccessExpression(tag)) return
    const fns = valueOf(tag).fns
    if (!fns?.size) return
    const props = new Map<string, Held<L>>()
    for (const attr of opening.attributes.properties) {
      if (ts.isJsxSpreadAttribute(attr)) {
        for (const [key, value] of valueOf(attr.expression, record).props ?? []) props.set(key, value)
        continue
      }
      const init = attr.initializer
      const expression = !init || ts.isStringLiteral(init) ? undefined : ts.isJsxExpression(init) ? init.expression : init
      const value = expression ? valueOf(expression, record) : empty<L>()
      if (!vacant(value)) props.set(attr.name.getText(), value)
      else props.delete(attr.name.getText())
    }
    if (ts.isJsxElement(x)) {
      let children = empty<L>()
      for (const child of x.children) {
        if (ts.isJsxElement(child) || ts.isJsxSelfClosingElement(child) || ts.isJsxFragment(child)) children = both(children, valueOf(child, record))
        else if (ts.isJsxExpression(child) && child.expression) children = both(children, valueOf(child.expression, record))
      }
      if (!vacant(children)) props.set('children', children)
    }
    pass(fns, [{ leaves: new Map(), props, fns: null }])
    // What the component returns renders here, not where it is written.
    returned(fns, record)
  }
  /** A loop's variable takes each element of what it iterates. */
  const loop = (x: ts.ForOfStatement, record?: Set<ts.Node>) => {
    const declared = ts.isVariableDeclarationList(x.initializer)
    const rec = declared || holdsTarget(x.initializer as ts.Expression) ? record : undefined
    const element = elementOf(valueOf(x.expression, rec))
    if (ts.isVariableDeclarationList(x.initializer)) for (const d of x.initializer.declarations) bindName(d.name, element, d, rec)
    else assign(x.initializer, element, rec)
  }

  /** Every place a name is given a value, read once with what the reads before it found. */
  const sources = (record?: Set<ts.Node>) => {
    const visit = (node: ts.Node): void => {
      if (ts.isVariableDeclaration(node) && node.initializer) bindName(node.name, valueOf(node.initializer, record), node, record)
      else if (ts.isParameter(node) && (node.initializer || !ts.isIdentifier(node.name))) {
        // A parameter's default, which renders when the caller passes nothing.
        bindName(node.name, node.initializer ? valueOf(node.initializer, record) : empty<L>(), node, record)
      } else if (ts.isForOfStatement(node)) loop(node, record)
      else if (ts.isBinaryExpression(node) && ASSIGNMENTS.has(node.operatorToken.kind)) {
        const rec = holdsTarget(node.left) ? record : undefined
        assign(node.left, valueOf(node.right, rec), rec)
      }
      else if (ts.isCallExpression(node)) call(node, record)
      else if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) render(node, record)
      ts.forEachChild(node, visit)
    }
    visit(sf)
  }
  let sites = 0
  const count = (node: ts.Node): void => {
    if (ts.isVariableDeclaration(node) || ts.isParameter(node) || ts.isForOfStatement(node) || ts.isBinaryExpression(node) || ts.isCallExpression(node) || ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) sites++
    ts.forEachChild(node, count)
  }
  count(sf)

  // To a fixed point: each pass reads every source with what the passes before it found, and a holder only gains. In
  // code that runs, a value stops growing within a pass per source. A value that reads itself (`const a = <>{a}</>`,
  // which no runtime allows, or a component handing its own children back to itself with more added) would count
  // without end: the scan throws instead of settling on an arbitrary count.
  const total = () => [...holders.values()].reduce((n, value) => n + size(value), 0)
  let settled = false
  for (let pass = 0; !settled && pass <= sites + 1; pass++) {
    const before = total()
    sources()
    settled = total() === before
  }
  if (!settled) throw new Error(`${sf.fileName}: what a same-file binding holds reads itself, so its count never settles`)

  const held = new Set<ts.Node>()
  sources(held)
  const holderOf = (id: ts.Identifier) => {
    const declaration = declarationOf(id)
    return declaration ? holders.get(declaration) : undefined
  }
  const renderOf = (element: ts.JsxOpeningLikeElement | ts.CallExpression): Held<L> => {
    const type = ts.isCallExpression(element) ? (calleeName(element) === 'createElement' ? element.arguments[0] : undefined) : element.tagName
    if (!type || !(ts.isIdentifier(type) || ts.isPropertyAccessExpression(type))) return empty()
    const fns = valueOf(type).fns
    return fns?.size ? { ...returned(fns), fns: null } : empty()
  }
  return { valueOf: (e) => valueOf(e), holderOf, renderOf, held }
}
