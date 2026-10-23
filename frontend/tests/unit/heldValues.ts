import ts from 'typescript'

/**
 * What a same-file value holds, followed from where it is written to where it is used, for the gates that read a
 * value rather than its syntax: brandVoiceRules.spec.ts's heading icons, reservedGlyphs.spec.ts's glyph counts,
 * no-em-dash-copy.spec.ts's missing-value token joined into copy, missingValueToken.spec.ts's token rendered outside
 * its element and checkboxRecipe.spec.tsx's input type. One reading for all five, so a shape one gate follows the
 * others follow too (lessons/test-gates-must-be-as-wide-as-their-rule.md: the family is taken from the language, not
 * from the forms a review names).
 *
 * A value is the leaves it may be (the gate says what a leaf is: an icon's import, a glyph's root), each with how
 * many times it renders; for an object or an array, what each property or element holds; and the same-file functions
 * it may be. A leaf may have members (a namespace import: the gate's `memberLeaf` names the leaf its member is by key),
 * so a namespace held by another name, assigned, destructured or passed on is followed like any other value. Counts add where a value renders its parts together (an element's tag and children:
 * `<><QuotesIcon /><QuotesIcon /></>` renders the glyph twice) and take the larger where it renders one or the other (a
 * conditional's arms, `||`, `??`, a member read by a key the scan cannot read, the values one name is given in turn).
 *
 * A name holds every value it is given, resolved by scope (the nearest enclosing declaration, so a name two functions
 * each declare reads its own function's binding, and a parameter or a function of that name shadows an outer one; a
 * name declared again in its scope, by `var` or over a parameter, is one binding, and an overload's signature declares
 * nothing, so a call reads the implementation):
 *  - its declaration's initializer, a destructuring of it (object and array patterns, nested, each element with its
 *    default, which renders when the member is missing, and a rest element the rest: an array's elements from its
 *    place on, re-indexed, or the properties the pattern does not name) and each later assignment (`=`, `||=`, `&&=`,
 *    `??=`, and a destructuring assignment with its defaults and its rest);
 *  - as a loop's variable, each element of what it iterates (`for (const Mark of MARKS)`, a pattern or a name assigned);
 *  - as a parameter, its default and what each same-file call passes it: a direct call (`render(QuotesIcon)`, a spread
 *    argument any element, a rest parameter the arguments from its place on, by position), a JSX element of a same-file component (its props object: each attribute, each spread's
 *    properties, the children as `children`), React's `createElement` of one (or the JSX runtime's `jsx`, `jsxs` or
 *    `jsxDEV`, whose props hold its children), a callback handed to an array's methods
 *    (`MARKS.map((Mark) => …)`: each element; `reduce`'s accumulator its initial value and each return; `sort`'s two
 *    elements), to `Array.from`, to React's `Children.map` and `Children.forEach` (each child), and a function handed on
 *    by a name, a property, an argument or a return, however it reached the call (`each((Mark) => …)` where `each`
 *    calls its parameter);
 *  - what the code puts in an object or an array after making it: a property assigned (`BOX.mark = QuotesIcon`, nested,
 *    or under a key the scan cannot read, which any read may reach), an element pushed, unshifted or spliced in, a
 *    `Set`'s `add`, a `Map`'s `set`, `Object.assign` and `Reflect.set` onto it, and a property `Object.defineProperty`,
 *    `Object.defineProperties` or `Reflect.defineProperty` defines on it (its descriptor's `value`, or what its `get`
 *    returns).
 * An expression holds:
 *  - a member read by name or literal key (`MARK.alert`, `MARK['alert']`, a nested `A.b.c`, a `Map`'s `get`,
 *    `Reflect.get`), and one read by a key the scan cannot read (`MARK[kind]`), which may be any property;
 *  - an object literal's properties, spreads, methods and getters (a getter's property is what it returns), in source
 *    order, so a later property overrides a spread's. In the literal's methods and accessors (and a function expression
 *    given as one of its properties), a member of `this` is the literal's member, what the code puts on `this` there
 *    included (`this.raw = name`, read back as `this.raw` or from the literal); `this` handed on whole holds nothing,
 *    so an object that hands back its own `this` never nests itself;
 *  - an array literal's elements by index (`[QuotesIcon]` read as `marks[0]`); past a spread the indices are unknown,
 *    so a literal index there may read any element from the spread on;
 *  - a built-in collection's constructor (a global, under any local name): `new Map` and `new WeakMap` hold each
 *    entry's value under its key, as `set` puts it (a pair written out under its key when the scan can read it, else
 *    under any key; a pair from an iterable the scan cannot see written, under any key; a copied Map's values under
 *    theirs), and `new Set`, `new Array`, `Array()` and `Array.of` hold their items, unplaced, as `add` and `push` put
 *    them; a WeakSet gives nothing back to read, and any other constructor (a class's, a Proxy's) holds nothing;
 *  - a conditional's two arms, both sides of `||` and `??`, the right of `&&`, an assignment's value, an `await`;
 *  - a JSX element's tag and its children (`<span><BellIcon /></span>` and `<><BellIcon /></>` hold it, as do
 *    `{expressions}` among the children, and JSX text for a gate that reads it, `textLeaf`), and the same for React's
 *    `createElement` (its type and children), the JSX runtime's `jsx`, `jsxs` and `jsxDEV` (its type and its props'
 *    `children`) and `cloneElement` (its element and children). An element given no children of its own takes the
 *    `children` its props give it (`<span children={<BellIcon />} />`, `createElement('span', { children })`, a clone's
 *    props), as React does; a clone handed children keeps its element's own in this reading too, an over-read. React's
 *    Suspense renders its `fallback` in its children's place while they wait, so it holds either (`suspends` says
 *    which types suspend: by default one known by the name Suspense). A same-file component's element, by JSX,
 *    `createElement` or the runtime's calls, also
 *    holds what the component returns, each time it is rendered (`<AlertMark />` where `AlertMark` returns
 *    `<BellIcon />`), so a glyph or an icon a component draws is read where the component is rendered. A gate that
 *    reads an element as what renders in its place (`rendered`, the em-dash gate's) has it hold what the component
 *    returns and nothing else, asked before its own leaves. A tag that names an intrinsic element (`<span>`,
 *    `<my-chart>`) is a string to React, never the binding of that name a file may declare;
 *  - a call: a same-file function's returns (an arrow's expression, each `return` outside nested functions); an
 *    array's `find`, `findLast`, `at`, `pop` and `shift` (an element), `filter`, `slice`, `splice`, `concat`, `sort`,
 *    `reverse`, `flat` and their copying forms (its elements), `map` and `flatMap` (what the callback returns) and
 *    `reduce` (its accumulator), and `values()` (its elements) and `entries()` (each element at index 1) of a value
 *    without a same-file method of that name; `Object.values`, `Object.entries` (each value at index 1),
 *    `Object.assign` (its target, with every source's properties), `Object.fromEntries` (each entry's value under its
 *    key, as `new Map` holds it), `Object.defineProperty` and `Object.defineProperties` (their target, with what they
 *    define), `Object.create` (its prototype's properties, with what it defines), `Object.freeze`,
 *    `Object.seal` and `Object.preventExtensions` (what they are given), `Array.from`; React's `Children.map` (what the
 *    callback returns), `Children.toArray` and
 *    `Children.only`, `useMemo` (what its callback returns), `useCallback` (its callback), and `memo` and
 *    `forwardRef` (the component they wrap); and, for a gate that reads React's state (`state`), `useState`,
 *    `useReducer`, `useActionState` (and react-dom's `useFormState`), `useOptimistic`, `useRef`, `useDeferredValue`
 *    and `useSyncExternalStore` (what each keeps, HeldOptions.state).
 *    Wherever the reading calls a value (a callee, a callback, a hook's initializer, reducer, updater or snapshot), a
 *    leaf the gate says is a function gives back what the gate names (HeldOptions.calls: another module's function).
 *    A function value called through Function.prototype's `call` or `apply`, or `Reflect.apply`, is called with the
 *    arguments after `thisArg` (`apply`'s from its list), and `bind` gives back the function, its bound arguments
 *    handed to it there and a later call's arguments after them (a call of a function ever bound may be through the
 *    bound one, so its arguments reach both places);
 *  - parentheses, `as`, `satisfies`, `<T>` and `!`.
 * A call is known by the name its callee is known by (knownAs), so React's utilities and the globals are read under
 * any local name: an import renamed (`Children as Kids`), a member destructured under another name, a same-file
 * alias (`const h = createElement`).
 * A gate that fails closed on code the reading cannot see (`passThrough`, the missing-value gate's) also has a call of
 * a function it does not hold (an import's, a global's, a method of a value it does not hold) hold what it is handed,
 * each argument and a method's receiver, since a formatter may give back its fallback (`formatLocalDate(value, pattern,
 * '—')`) and `String()` or `trim()` the value it is given (React's call of a reducer it does not hold among them, for a
 * gate that reads state: the state may be what the reducer is handed); a template literal, tagged or not, hold its
 * substitutions, `+` both sides and a comma expression its last; and `+=` give its target what it adds. Without it each
 * holds nothing.
 * Out of its reach, for each gate to name and plant as a gap: a value that crosses modules (an app module's export or a
 * context's, or a setter handed to another module's code), what React state holds after its setter or a reducer runs
 * unless the gate reads state (HeldOptions.state), what a child hands its parent's ref through useImperativeHandle, a
 * class's members and its `this` (a field, a getter, a method), `this` handed on whole (returned, passed or held by
 * another name), what an assignment through a `set` accessor hands the accessor, a property descriptor's `get` that
 * reads `this` (the reading binds it to the descriptor, where it runs on the object), a Proxy's traps, a Map's entries
 * iterated as `[key, value]` pairs (a Map holds its values as its elements, so `forEach`, `values()` and `entries()`
 * hand on a value, and a pair destructured from the Map itself holds nothing), a Map's keys (it holds a value under a
 * key the scan can read, never the key), a promise's `then`, a generator's yields, and a utility known by its name (an
 * array's method, React's Children) called through Function.prototype's `call` or `apply`, which reads as a call of the
 * method. One over-count, which fails closed: a parameter is not told apart by call, so it holds what every same-file
 * call passes it, and a function called with different values reads all of them at each call (a component rendered once
 * with each of two glyphs counts both at each render).
 * The reading settles on code that runs: an array's elements past a spread are keyed by where they are written, so an
 * array that appends to itself (`setNames((prev) => [...prev, name])`) holds the same keys on every pass, and a value
 * nests at most DEPTH levels, past which it is what it holds anywhere below, so a value that nests itself (a getter
 * that hands back an object holding its own object) stops deepening. A value whose counts grow through its own reads
 * (`const a = <>{a}</>`, which no runtime allows, or a component that passes its own children back to itself with more
 * added) never settles: the scan throws instead of settling on an arbitrary count.
 */
export interface Held<L> {
  /** Each leaf the value may be, with how many times it renders. */
  leaves: Map<L, number>
  props: Map<string, Held<L>> | null
  /** The same-file functions the value may be: a call through it binds their parameters and reads their returns. */
  fns: Set<Fn> | null
  /** The React hooks (useState, useReducer) whose setter or dispatcher the value may be (HeldOptions.state): a call
      through it hands the hook what it is passed. */
  setters?: Set<ts.CallExpression> | null
}

/** A function the scan follows: a declaration, an arrow, a function expression or an object literal's method. */
export type Fn = ts.FunctionDeclaration | ts.ArrowFunction | ts.FunctionExpression | ts.MethodDeclaration
/** What the scan reads the returns of: a function, or an object literal's getter, whose returns its property holds. */
type Body = Fn | ts.GetAccessorDeclaration

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
const joinedSetters = <L>(a: Held<L>, b: Held<L>): Set<ts.CallExpression> | null =>
  a.setters?.size || b.setters?.size ? new Set([...(a.setters ?? []), ...(b.setters ?? [])]) : null

/** Either value (a conditional's arms, `||`, `??`, a name's values in turn): the leaves of both, each at the larger
    count, each property either side holds, and the functions and setters of both. */
export function union<L>(a: Held<L>, b: Held<L>): Held<L> {
  return { leaves: joined(a.leaves, b.leaves, Math.max), props: joinedProps(a, b), fns: joinedFns(a, b), setters: joinedSetters(a, b) }
}

/** Both values, rendered together (an element's tag and its children): each leaf as many times as the two render it. */
const both = <L>(a: Held<L>, b: Held<L>): Held<L> => ({
  leaves: joined(a.leaves, b.leaves, add),
  props: joinedProps(a, b),
  fns: joinedFns(a, b),
  setters: joinedSetters(a, b),
})

/** Every leaf a value holds, its properties' included, with how many times it renders: a value read whole reads
    each of its properties. */
export function leavesOf<L>(value: Held<L>): Map<L, number> {
  let out = new Map(value.leaves)
  for (const prop of value.props?.values() ?? []) out = joined(out, leavesOf(prop), add)
  return out
}

/** The leaves React renders from a value as a child or a component's return: its own, and those of its elements (an
    array's by index, an element placed past a spread or built by a call, a Set's, one written under a key the scan
    cannot read), nested; an object's fields are no child of it. */
export function renderedLeavesOf<L>(value: Held<L>): Map<L, number> {
  let out = new Map(value.leaves)
  for (const [key, prop] of value.props ?? []) {
    if (/^\d+$/.test(key) || key.startsWith(REST) || key === ANY) out = joined(out, renderedLeavesOf(prop), add)
  }
  return out
}

/** A value as text, what a call the reading cannot follow, a template literal or `+` gives back under `passThrough`:
    every leaf it holds, its properties' included, with no properties or functions of its own, so a string a recursion
    builds from what it returns settles instead of nesting deeper on every pass. */
const asText = <L>(value: Held<L>): Held<L> => ({ leaves: leavesOf(value), props: null, fns: null })

/** Whether a value holds nothing to follow: no leaf, no function and no setter, here or in a property. */
const vacant = <L>(value: Held<L>): boolean =>
  value.leaves.size === 0 && !value.fns?.size && !value.setters?.size && [...(value.props?.values() ?? [])].every(vacant)

/** The key prefix of an array's elements whose indices the scan cannot know (past a spread, pushed, built by a call). */
const REST = '…'
/** The key a property is written under when the scan cannot read the key (`BOX[key] = …`): any read may reach it. */
const ANY = '*'

/** A property of a value by its key: undefined for a key the scan cannot read, which may be any property; a literal index
    an array's known elements do not reach may read any element past them; a property written under a key the scan
    cannot read may be any member. */
export function propertyOf<L>(base: Held<L>, key: string | undefined): Held<L> {
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

/** How deep a held value nests: past it, a value is what it holds anywhere below, each leaf at its largest count, with
    no properties of its own, so a value that nests itself on every pass (a getter or a function that hands back an
    object holding its own object, an array put inside itself) settles instead of growing without end. */
const DEPTH = 16
/** Everything a value holds, at any depth, in one value: its leaves (each at its largest count), functions and
    setters. */
const flattened = <L>(value: Held<L>): Held<L> =>
  [...(value.props?.values() ?? [])].reduce(
    (out, prop) => union(out, flattened(prop)),
    { leaves: value.leaves, props: null, fns: value.fns, setters: value.setters } as Held<L>,
  )
/** A value nested at most DEPTH levels: each property past the bound is flattened. */
const bounded = <L>(value: Held<L>, depth = 0): Held<L> => {
  if (!value.props?.size) return value
  if (depth >= DEPTH) return flattened(value)
  let changed = false
  const props = new Map<string, Held<L>>()
  for (const [key, prop] of value.props) {
    const next = bounded(prop, depth + 1)
    if (next !== prop) changed = true
    props.set(key, next)
  }
  return changed ? { ...value, props } : value
}

const size = <L>(value: Held<L>): number =>
  [...value.leaves.values()].reduce(add, 0) +
  (value.fns?.size ?? 0) +
  (value.setters?.size ?? 0) +
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

/** Whether a JSX element's attributes may give it a prop: an attribute of that name, or a spread. */
const gives = (opening: ts.JsxOpeningLikeElement, name: string): boolean =>
  opening.attributes.properties.some((a) => ts.isJsxSpreadAttribute(a) || (ts.isIdentifier(a.name) && a.name.text === name))

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

/** How scope reads a file's names (scopeResolver). */
export interface ScopeResolver {
  /** The declaration a name reads: its binding's first declaration. Undefined for a global. */
  (id: ts.Identifier): ts.Node | undefined
  /** Every declaration of the binding a name reads, in source order (none for a global). */
  all(id: ts.Identifier): ts.Node[]
}

/**
 * The declaration a name reads where it is written: the nearest enclosing scope that declares it. A block declares
 * its `const`, `let`, functions and classes; a function its parameters and every `var` inside it; the file its
 * imports; a `for` statement and a `catch` clause their own bindings; a named function expression its own name, which
 * its parameters and its `var`s shadow. The node returned is the declaration of a bare name and the element of a
 * destructured one. A name declared again in its scope is one binding: `var` declared twice (`var Mark; var Mark =
 * QuotesIcon`), or a parameter's name declared again by `var`, reads its first declaration, and `all` gives every
 * declaration of it. An overload's signature declares nothing, since only the implementation runs.
 */
export function scopeResolver(sf: ts.SourceFile): ScopeResolver {
  const declared = new Map<ts.Node, Map<string, ts.Node[]>>()
  const declare = (scope: ts.Node | undefined, name: string, node: ts.Node) => {
    if (!scope) return
    const names = declared.get(scope) ?? new Map<string, ts.Node[]>()
    declared.set(scope, names)
    names.set(name, [...(names.get(name) ?? []), node])
  }
  // A named function expression's own name, read where nothing in the function declares it.
  const ownName = new Map<ts.Node, string>()
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
    else if (ts.isFunctionDeclaration(n) && n.name && n.body) declare(enclosing(n, blockScope), n.name.text, n)
    else if (ts.isClassDeclaration(n) && n.name) declare(enclosing(n, blockScope), n.name.text, n)
    else if (ts.isFunctionExpression(n) && n.name) ownName.set(n, n.name.text)
    else if (ts.isImportClause(n) && n.name) declare(sf, n.name.text, n)
    else if (ts.isImportSpecifier(n) || ts.isNamespaceImport(n)) declare(sf, n.name.text, n)
    ts.forEachChild(n, visit)
  }
  visit(sf)
  const all = (id: ts.Identifier): ts.Node[] => {
    // A function's own name is read from outside its parameters and body: an expression's is the function, and a
    // declaration's is found from the scope that declares it.
    const fn = id.parent
    if (ts.isFunctionExpression(fn) && fn.name === id) return [fn]
    const from = ts.isFunctionDeclaration(fn) && fn.name === id ? fn.parent : fn
    for (let n: ts.Node | undefined = from; n; n = n.parent) {
      const found = declared.get(n)?.get(id.text)
      if (found) return found
      if (ownName.get(n) === id.text) return [n]
    }
    return []
  }
  return Object.assign((id: ts.Identifier) => all(id)[0], { all })
}

/**
 * The name an expression is known by, through what renames it: an import under another name (`Children as Kids`) and a
 * member destructured under another name (`const { Children: Kids } = React`) by the name they take, a same-file alias
 * (`const h = createElement`, by any declaration of its binding) by its initializer's, a member by its own name or
 * literal key (`React['cloneElement']`). `global` is true only for a name nothing in the file declares (`Object`,
 * `Array`).
 */
export function knownAsIn(declarationOf: ScopeResolver) {
  const knownAs = (raw: ts.Expression, seen = new Set<ts.Node>()): { name: string; global: boolean } | undefined => {
    const e = unwrapHeld(raw)
    if (ts.isPropertyAccessExpression(e)) return { name: e.name.text, global: false }
    if (ts.isElementAccessExpression(e)) return ts.isStringLiteralLike(e.argumentExpression) ? { name: e.argumentExpression.text, global: false } : undefined
    if (!ts.isIdentifier(e)) return undefined
    const declaration = declarationOf(e)
    if (!declaration) return { name: e.text, global: true }
    if (ts.isImportSpecifier(declaration)) return { name: (declaration.propertyName ?? declaration.name).text, global: false }
    if (ts.isBindingElement(declaration) && ts.isObjectBindingPattern(declaration.parent)) {
      const key = declaration.propertyName ?? declaration.name
      if (ts.isIdentifier(key)) return { name: key.text, global: false }
    }
    for (const d of declarationOf.all(e)) {
      if (!ts.isVariableDeclaration(d) || !d.initializer || seen.has(d)) continue
      seen.add(d)
      const aliased = knownAs(d.initializer, seen)
      if (aliased) return aliased
    }
    return { name: e.text, global: false }
  }
  return knownAs
}

/** Array methods whose first argument is called with each element. */
const ELEMENT_CALLBACKS = new Set(['map', 'flatMap', 'forEach', 'filter', 'find', 'findLast', 'findIndex', 'findLastIndex', 'some', 'every'])
/** Array methods that return one of the elements. */
const ELEMENT_RESULTS = new Set(['find', 'findLast', 'at', 'pop', 'shift'])
/** Array methods that return an array of the elements (and, for `concat` and the splices, what they add). */
const ARRAY_RESULTS = new Set(['filter', 'slice', 'splice', 'toSpliced', 'concat', 'sort', 'toSorted', 'reverse', 'toReversed', 'flat', 'with'])

/** What a gate tells the shared reading beyond its leaves. */
export interface HeldOptions<L> {
  /** The leaves a leaf with members has under a key (a namespace's member), placed at `node`, the read or the binding. */
  memberLeaf?: (leaf: L, key: string | undefined, node: ts.Node) => L[] | undefined
  /** The leaves a JSX text child is, for a gate that reads text (the em-dash gate's token). */
  textLeaf?: (text: ts.JsxText) => L[] | undefined
  /** Whether an element of this type renders its `fallback` prop in its children's place (React's Suspense, while they
      wait). By default, a type known by the name Suspense that is not a same-file component; a gate that reads React's
      types as values (the em-dash gate) says it of a type however the type reaches the element. */
  suspends?: (type: ts.Expression) => boolean
  /** Whether a same-file component's element (by JSX, createElement or the runtime's calls) is what the component
      returns and nothing else, asked before `leafOf`: for a gate that reads an element as what renders in its place
      (the em-dash gate), so an element of a component that returns an element of its own is that element, and one of a
      component that passes its children or a prop through, or returns a fragment or text, is what it renders into the
      element's parent. By default the element is `leafOf`'s, or else holds what the component returns and the children
      it is handed. */
  rendered?: boolean
  /** Whether a value built by code the reading cannot follow holds what it is built from (the header's last
      paragraph): a call of a function the reading does not hold, a template literal, `+` and a comma expression, and
      `+=` gives its target what it adds. For a gate that asks whether a leaf may render, not how often
      (missingValueToken.spec.ts): each part counts once, so a string a loop or a recursion builds settles. By default
      each holds nothing. */
  passThrough?: boolean
  /** Whether React's state keeps what it is handed and gives it back (companyNameDisplay.spec.ts). A setter or a
      dispatcher is a value, the hook it came from (Held.setters), followed as any other value is: destructured, read by
      index from the hook's pair, held by another name, put in an object, handed to a same-file function or component,
      handed back by a custom hook. useState's first element holds its initial value, what its initializer returns and
      what each call through its setter hands it (a value, or what an updater returns, the updater called with the
      state); useReducer's, its initial argument and what its init and its reducer return, the reducer called with the
      state and each action a call through its dispatcher hands it, and useActionState's (react-dom's useFormState
      before it) the same, its action the reducer; useOptimistic's, its passthrough value and what each call through
      its setter hands it, or what its update function returns, called with the state and each value; useRef's
      `current`, its initial value (what the code puts there later is an assignment, read as any other);
      useDeferredValue, what it defers; useSyncExternalStore, what the snapshot returns. A setter handed to code the
      reading does not hold (another module's function or component) is called where the reading cannot see, and what
      a child hands its parent's ref through useImperativeHandle reaches no binding the parent reads. A reducer the reading does not hold (another module's) is, to
      a gate that reads with `passThrough`, a call it cannot follow, so the state may be what React hands it: the state
      and each action. By default each hook is a call the reading cannot follow. */
  state?: boolean
  /** What a call of a leaf gives back, for a gate whose leaves include functions the reading does not hold (another
      module's function that hands back a served name, companyNameDisplay.spec.ts): wherever the reading calls a value
      (a callee, a callback an array's methods or React's Children call, a hook's initializer, reducer, updater or
      snapshot), each leaf it holds gives back what this names, beside the returns of its same-file functions. By
      default a leaf gives back nothing. */
  calls?: (leaf: L) => L[] | undefined
}

/** React's calls that make an element of the type they are given: createElement, and the JSX runtime's jsx, jsxs and
    jsxDEV, whose props hold the children. */
export const ELEMENT_MAKERS = new Set(['createElement', 'jsx', 'jsxs', 'jsxDEV'])
const RUNTIME_MAKERS = new Set(['jsx', 'jsxs', 'jsxDEV'])

/** A JSX child as it renders: whitespace-only text and an expression that holds nothing or only a comment render
    nothing. */
export const writtenChild = (c: ts.JsxChild): boolean =>
  !(ts.isJsxText(c) && c.containsOnlyTriviaWhiteSpaces) && !(ts.isJsxExpression(c) && !c.expression)

/** The type a JSX tag names when it may be a component: an identifier or a member. A tag that names an intrinsic element
    (an identifier that starts lower case or holds a dash: `<span>`, `<my-chart>`) or a namespaced one is a string to
    React, never a binding, whatever the file declares by that name. */
export const componentTag = (opening: ts.JsxOpeningLikeElement): ts.Identifier | ts.PropertyAccessExpression | undefined => {
  const tag = opening.tagName
  if (ts.isIdentifier(tag)) return /^[a-z]|-/.test(tag.text) ? undefined : tag
  return ts.isPropertyAccessExpression(tag) ? tag : undefined
}

/**
 * The values of one source. `leafOf` names the leaves an expression is by itself (an import of an icon, a
 * namespace's member), or returns undefined.
 */
export function heldValues<L>(
  sf: ts.SourceFile,
  leafOf: (e: ts.Expression) => L[] | undefined,
  { memberLeaf, textLeaf, suspends, rendered, passThrough, state, calls }: HeldOptions<L> = {},
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
  const knownAs = knownAsIn(declarationOf)
  /** A call's callee by the name it is known by (knownAs): `render` in `render()`, `map` in `MARKS.map()`,
      `createElement` in `React.createElement()` and in `h()` after `import { createElement as h }`. */
  const calleeName = (call: ts.CallExpression): string => knownAs(call.expression)?.name ?? ''
  /** Whether an element of this type renders its fallback in its children's place (HeldOptions.suspends). */
  const suspendsAs = suspends ?? ((type: ts.Expression) => knownAs(type)?.name === 'Suspense')
  /** What a call's callee is read from: `MARKS` in `MARKS.map()`, `React.Children` in `React.Children.map()`. */
  const receiverOf = (call: ts.CallExpression): ts.Expression | undefined => {
    const callee = unwrapHeld(call.expression)
    return ts.isPropertyAccessExpression(callee) ? callee.expression : undefined
  }
  /** Whether a call's receiver is this global (`Object`, `Array`: no declaration in the file, under any alias) or
      React's `Children` (imported, renamed, destructured or read as `React.Children`), by the name it is known by. */
  const receiverNamed = (call: ts.CallExpression, name: string): boolean => {
    const recv = receiverOf(call)
    const known = recv && knownAs(recv)
    return !!known && known.name === name && (name === 'Children' || known.global)
  }
  /** Whether an assignment's target, or the object a member is put in, is a same-file binding the scan holds: a name
      declared in the file (not an import or a function), read through any members. */
  const holdsTarget = (target: ts.Expression): boolean => {
    let t = unwrapHeld(target)
    while (ts.isPropertyAccessExpression(t) || ts.isElementAccessExpression(t)) t = unwrapHeld(t.expression)
    if (ts.isObjectLiteralExpression(t) || ts.isArrayLiteralExpression(t)) return true
    if (t.kind === ts.SyntaxKind.ThisKeyword) return !!thisLiteral(t)
    if (!ts.isIdentifier(t)) return false
    const declaration = declarationOf(t)
    return !!declaration && (ts.isVariableDeclaration(declaration) || ts.isBindingElement(declaration) || ts.isParameter(declaration))
  }
  /** The object literal a `this` is: the nearest function that binds `this` (an arrow does not), when that function is
      one of the literal's methods or accessors, or a function expression given as one of its properties. Undefined for
      any other `this` (a class's, a plain function's), which the reading does not follow. */
  const thisLiteral = (node: ts.Node): ts.ObjectLiteralExpression | undefined => {
    let fn = node.parent
    while (fn && !ts.isSourceFile(fn) && !ts.isClassLike(fn) && !(ts.isFunctionLike(fn) && !ts.isArrowFunction(fn))) fn = fn.parent
    if (!fn || !(ts.isMethodDeclaration(fn) || ts.isGetAccessorDeclaration(fn) || ts.isSetAccessorDeclaration(fn) || ts.isFunctionExpression(fn))) {
      return undefined
    }
    const owner = ts.isFunctionExpression(fn) ? (ts.isPropertyAssignment(fn.parent) ? fn.parent.parent : undefined) : fn.parent
    return owner && ts.isObjectLiteralExpression(owner) ? owner : undefined
  }
  /** The object literals a `this` in the file is, read or written: each holds its own value and what the code puts on
      `this` (sources). */
  const thisLiterals = new Set<ts.ObjectLiteralExpression>()
  const findThis = (n: ts.Node): void => {
    if (n.kind === ts.SyntaxKind.ThisKeyword) {
      const literal = thisLiteral(n)
      if (literal) thisLiterals.add(literal)
    }
    ts.forEachChild(n, findThis)
  }
  findThis(sf)

  // A function or a getter being read for its returns: a call of it inside its own returns (recursion) adds nothing
  // more.
  const evaluating = new Set<Body>()
  /** What a function or a getter returns: an arrow's expression body, and each `return` in its body outside the
      functions nested in it. */
  const returnsOf = (fn: Body): ts.Expression[] => {
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
  const returned = (fns: Iterable<Body> | null | undefined, record?: Set<ts.Node>): Held<L> => {
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
  /** What calling a value gives back: what its same-file functions return, and what each of its leaves gives back
      when called (HeldOptions.calls). */
  const called = (value: Held<L>, record?: Set<ts.Node>): Held<L> => {
    const back = returned(value.fns, record)
    if (!calls || value.leaves.size === 0) return back
    const leaves = new Map<L, number>()
    for (const leaf of value.leaves.keys()) for (const own of calls(leaf) ?? []) leaves.set(own, (leaves.get(own) ?? 0) + 1)
    return leaves.size ? union(back, { leaves, props: null, fns: null }) : back
  }
  /** A hook's setter or dispatcher as a value: the hook it came from (HeldOptions.state). */
  const setterOf = (hook: ts.CallExpression): Held<L> => ({ leaves: new Map(), props: null, fns: null, setters: new Set([hook]) })
  /** What the calls through a hook's setter or dispatcher hand it, however each reached the setter: useState's values
      and updaters, useReducer's actions (HeldOptions.state). */
  const handedTo = (hook: ts.CallExpression): Held<L> => holders.get(hook) ?? empty()
  /** What a property descriptor gives its property: its `value`, and what its `get` returns. */
  const described = (descriptor: Held<L>, record?: Set<ts.Node>): Held<L> =>
    union(propertyOf(descriptor, 'value'), called(propertyOf(descriptor, 'get'), record))
  /** The properties a definition call defines, each what its descriptor gives it: Object.defineProperty's and
      Reflect.defineProperty's one, under its key, or those of the map Object.defineProperties and Object.create are
      given. */
  const definedBy = (x: ts.CallExpression, record?: Set<ts.Node>): Map<string, Held<L>> => {
    const props = new Map<string, Held<L>>()
    const [, second, third] = x.arguments
    if (calleeName(x) === 'defineProperty') {
      const value = third && !ts.isSpreadElement(third) ? described(valueOf(third, record), record) : empty<L>()
      if (!vacant(value)) props.set(literalKey(second) ?? ANY, value)
      return props
    }
    const map = second && !ts.isSpreadElement(second) ? valueOf(second, record) : empty<L>()
    for (const [key, descriptor] of map.props ?? []) {
      const value = described(descriptor, record)
      if (!vacant(value)) props.set(key, value)
    }
    return props
  }
  /** The entries a Map, a WeakMap or Object.fromEntries is given, each value under its key, as a Map's `set` puts it: a
      pair written out under its key when the scan can read it (else under any key), and from what the scan cannot see
      written (an array of pairs held by a name, Object.entries, a Map copied) each pair's value under any key and a
      copied Map's values under theirs. */
  const entriesOf = (given: ts.Expression | undefined, record?: Set<ts.Node>): Map<string, Held<L>> => {
    const props = new Map<string, Held<L>>()
    const put = (key: string | undefined, value: Held<L>) => {
      if (vacant(value)) return
      const at = key ?? ANY
      props.set(at, props.has(at) ? union(props.get(at)!, value) : value)
    }
    if (!given || ts.isSpreadElement(given)) return props
    const e = unwrapHeld(given)
    if (ts.isArrayLiteralExpression(e)) {
      for (const el of e.elements) {
        if (ts.isOmittedExpression(el)) continue
        const pair = ts.isSpreadElement(el) ? undefined : unwrapHeld(el)
        if (pair && ts.isArrayLiteralExpression(pair) && pair.elements.length >= 2 && !pair.elements.slice(0, 2).some(ts.isSpreadElement)) {
          const [key, value] = pair.elements
          if (!ts.isOmittedExpression(value)) put(literalKey(key), valueOf(value, record))
          continue
        }
        put(undefined, propertyOf(ts.isSpreadElement(el) ? elementOf(valueOf(el.expression, record)) : valueOf(el, record), '1'))
      }
      return props
    }
    const value = valueOf(e, record)
    put(undefined, propertyOf(elementOf(value), '1'))
    for (const [key, held] of value.props ?? []) put(key, held)
    return props
  }
  /** What a built-in collection's constructor holds (knownAs: a global, under any local name): a Map's and a WeakMap's
      entries under their keys (entriesOf), and a Set's items and an Array's elements, unplaced, as `add` and `push`
      put them. A WeakSet gives nothing back to read, and any other constructor (a class's, a Proxy's) is no value the
      reading follows. */
  const newValue = (x: ts.NewExpression, record?: Set<ts.Node>): Held<L> => {
    const known = knownAs(x.expression)
    if (!known?.global) return empty()
    const args = x.arguments ?? []
    if (known.name === 'Map' || known.name === 'WeakMap') return { leaves: new Map(), props: entriesOf(args[0], record), fns: null }
    if (known.name === 'Set') return args[0] && !ts.isSpreadElement(args[0]) ? arrayOf(elementOf(valueOf(args[0], record))) : empty()
    if (known.name === 'Array') return elementsOf(args, record)
    return empty()
  }
  /** An array of what a call is handed, unplaced (Array's constructor and call, Array.of): a spread argument's
      elements. A lone count gives a length, which holds nothing to follow. */
  const elementsOf = (args: readonly ts.Expression[], record?: Set<ts.Node>): Held<L> =>
    arrayOf(args.reduce((value, a) => union(value, ts.isSpreadElement(a) ? elementOf(valueOf(a.expression, record)) : valueOf(a, record)), empty<L>()))
  /** What same-file components render where their element is: what they return, the components themselves aside. */
  const renders = (fns: Set<Fn>, element: ts.Node, record?: Set<ts.Node>): Held<L> => {
    const value = returned(fns, record)
    if (leavesOf(value).size > 0) record?.add(element)
    return { ...value, fns: null }
  }
  /** Whether a call is one of React's ELEMENT_MAKERS (a same-file function of that name is the file's own). */
  const maker = (call: ts.CallExpression) => ELEMENT_MAKERS.has(calleeName(call)) && !valueOf(call.expression).fns?.size
  /** The same-file components an element is of: its JSX tag's, or the type a maker call is given; null for any other
      expression. */
  const componentsOf = (x: ts.Expression): Set<Fn> | null => {
    if (ts.isJsxElement(x) || ts.isJsxSelfClosingElement(x)) {
      const type = componentTag(ts.isJsxElement(x) ? x.openingElement : x)
      return type ? valueOf(type).fns : null
    }
    const type = ts.isCallExpression(x) && maker(x) ? x.arguments[0] : undefined
    return type && !ts.isSpreadElement(type) ? valueOf(type).fns : null
  }

  const leavesAre = (own: L[]): Held<L> => {
    const leaves = new Map<L, number>()
    for (const leaf of own) leaves.set(leaf, (leaves.get(leaf) ?? 0) + 1)
    return { leaves, props: null, fns: null }
  }
  /** What a JSX child holds: an element or an expression by its value, JSX text by `textLeaf`. */
  const childValue = (child: ts.JsxChild, record?: Set<ts.Node>): Held<L> =>
    ts.isJsxElement(child) || ts.isJsxSelfClosingElement(child) || ts.isJsxFragment(child)
      ? valueOf(child, record)
      : ts.isJsxExpression(child)
        ? child.expression
          ? valueOf(child.expression, record)
          : empty<L>()
        : ts.isJsxText(child) && textLeaf
          ? leavesAre(textLeaf(child) ?? [])
          : empty<L>()

  /** The props a JSX element's attributes give it: each attribute's value and each spread's properties, a later one
      overriding. */
  const jsxProps = (opening: ts.JsxOpeningLikeElement, record?: Set<ts.Node>): Map<string, Held<L>> => {
    const props = new Map<string, Held<L>>()
    for (const attr of opening.attributes.properties) {
      if (ts.isJsxSpreadAttribute(attr)) {
        for (const [key, value] of valueOf(attr.expression, record).props ?? []) props.set(key, value)
        continue
      }
      const init = attr.initializer
      const expression = !init ? undefined : ts.isJsxExpression(init) ? init.expression : init
      const value = expression ? valueOf(expression, record) : empty<L>()
      if (!vacant(value)) props.set(attr.name.getText(), value)
      else props.delete(attr.name.getText())
    }
    return props
  }

  const valueOf = (e: ts.Expression, record?: Set<ts.Node>): Held<L> => {
    const x = unwrapHeld(e)
    // A same-file component's element is what the component renders, for a gate that reads it so (`rendered`).
    const components = rendered ? componentsOf(x) : null
    if (components?.size) return renders(components, x, record)
    const own = leafOf(x)
    if (own?.length) {
      record?.add(x)
      return leavesAre(own)
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
      // A member of `this` in an object literal's method or accessor is the literal's member (thisLiteral); `this`
      // read whole is no value the reading holds.
      const base = unwrapHeld(x.expression)
      const literal = base.kind === ts.SyntaxKind.ThisKeyword ? thisLiteral(base) : undefined
      const value = memberOf(literal ? (holders.get(literal) ?? empty<L>()) : valueOf(x.expression), memberKey(x), x)
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
      // A string built by `+` holds both sides, each once, so a string a loop or a recursion builds settles; a comma
      // expression is its last (passThrough).
      if (passThrough && op === ts.SyntaxKind.PlusToken) return asText(union(valueOf(x.left, record), valueOf(x.right, record)))
      if (passThrough && op === ts.SyntaxKind.CommaToken) return valueOf(x.right, record)
      return empty()
    }
    // A template literal holds its substitutions, each once, as `+` does; a tagged one is a call of its tag that the
    // reading cannot follow, so it may give back what it is handed (passThrough).
    if (passThrough && ts.isTemplateExpression(x)) return asText(x.templateSpans.reduce((value, span) => union(value, valueOf(span.expression, record)), empty<L>()))
    if (passThrough && ts.isTaggedTemplateExpression(x)) return asText(valueOf(x.template, record))
    if (ts.isCallExpression(x)) return callValue(x, record)
    if (ts.isNewExpression(x)) return newValue(x, record)
    if (ts.isJsxSelfClosingElement(x) || ts.isJsxElement(x) || ts.isJsxFragment(x)) {
      const opening = ts.isJsxFragment(x) ? undefined : ts.isJsxElement(x) ? x.openingElement : x
      const type = opening && componentTag(opening)
      let value = type ? valueOf(type, record) : empty<L>()
      const component = !!value.fns?.size
      // A same-file component's element holds what the component renders, not the component.
      if (component && value.fns) value = renders(value.fns, x, record)
      // Its children: those written inside it, or else the `children` its props give it; and a Suspense's fallback,
      // which renders in their place while they wait (one or the other renders).
      const written = ts.isJsxSelfClosingElement(x) ? [] : x.children.filter(writtenChild)
      let children = empty<L>()
      for (const child of written) children = both(children, childValue(child, record))
      const fallback = !!opening && !component && !!type && gives(opening, 'fallback') && suspendsAs(type)
      if (opening && ((!written.length && gives(opening, 'children')) || fallback)) {
        const props: Held<L> = { leaves: new Map(), props: jsxProps(opening, record), fns: null }
        if (!written.length) children = memberOf(props, 'children', x)
        if (fallback) children = union(children, memberOf(props, 'fallback', x))
      }
      return both(value, children)
    }
    if (ts.isArrayLiteralExpression(x)) {
      const props = new Map<string, Held<L>>()
      let index = 0
      // Past a spread the indices are unknown, so an element is keyed by where it is written (unplaced): one after a
      // spread by its own place, and a spread's by the spread and the key it had. A key this literal gave on an earlier
      // pass, and a key read as any element, are kept as they are, so an array that appends to itself (`[...prev, x]`,
      // in a state's updater or a `let`) holds the same keys on every pass and settles.
      const places = new Set(x.elements.map((el) => el.pos))
      const unplaced = (key: string, spread: ts.SpreadElement): string => {
        if (key === ANY) return key
        const at = key.startsWith(REST) ? /^\d+/.exec(key.slice(REST.length))?.[0] : undefined
        return at !== undefined && places.has(Number(at)) ? key : `${REST}${spread.pos}.${key}`
      }
      const put = (key: string, value: Held<L>) => {
        if (vacant(value)) return
        props.set(key, props.has(key) ? union(props.get(key)!, value) : value)
      }
      for (const el of x.elements) {
        if (ts.isSpreadElement(el)) {
          index = -1
          for (const [key, value] of valueOf(el.expression, record).props ?? []) put(unplaced(key, el), value)
          continue
        }
        if (!ts.isOmittedExpression(el)) put(index < 0 ? `${REST}${el.pos}` : String(index), valueOf(el, record))
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
        // A getter's property is what the getter returns; a setter alone gives the property no value to follow.
        const getter = ts.isGetAccessorDeclaration(p)
        if (!getter && !ts.isPropertyAssignment(p) && !ts.isShorthandPropertyAssignment(p)) continue
        const key = propertyKey(p.name)
        if (key === undefined) continue
        const value = getter ? returned([p], record) : valueOf(ts.isPropertyAssignment(p) ? p.initializer : p.name, record)
        if (!vacant(value)) props.set(key, value)
        else props.delete(key)
      }
      const made: Held<L> = { leaves: new Map(), props, fns: null }
      // A literal a `this` is: also what the code puts on `this` in its methods and accessors (sources).
      const kept = holders.get(x)
      return kept ? union(made, kept) : made
    }
    return empty()
  }

  /** What a call holds (see the header's list); empty for a call the scan cannot follow. */
  const callValue = (x: ts.CallExpression, record?: Set<ts.Node>): Held<L> => {
    const name = calleeName(x)
    const args = x.arguments
    const arg = (i: number) => (args[i] ? valueOf(args[i], record) : empty<L>())
    const fnsOf = (i: number) => (args[i] ? valueOf(args[i]).fns : null)
    /** What the function a call is handed at this position gives back when it is called. */
    const calledAt = (i: number) => (args[i] ? called(valueOf(args[i]), record) : empty<L>())
    // React's element calls hold what JSX would: the type and the children; a clone holds its element and children. A
    // same-file function of one of their names is the file's own (a call of it holds what it returns, below).
    if ((ELEMENT_MAKERS.has(name) || name === 'cloneElement') && !valueOf(x.expression).fns?.size) {
      let value = arg(0)
      const component = name !== 'cloneElement' && !!value.fns?.size
      if (component && value.fns) value = renders(value.fns, x, record)
      // The children it hands the element: createElement's and cloneElement's arguments from the third on, rendered
      // together, or else (and always for the runtime's calls) its props' `children`; and a Suspense's fallback.
      let children = empty<L>()
      const props = () => arg(1)
      if (RUNTIME_MAKERS.has(name) || args.length <= 2) children = memberOf(props(), 'children', x)
      else for (let i = 2; i < args.length; i++) children = both(children, arg(i))
      if (name !== 'cloneElement' && !component && args[0] && args[1] && !ts.isSpreadElement(args[0]) && suspendsAs(args[0])) {
        children = union(children, memberOf(props(), 'fallback', x))
      }
      return both(value, children)
    }
    if (receiverNamed(x, 'Children')) {
      if (name === 'map') return arrayOf(calledAt(1))
      if (name === 'toArray' || name === 'only') return union(arg(0), elementOf(arg(0)))
      return empty()
    }
    if (receiverNamed(x, 'Object')) {
      if (name === 'values') return arrayOf(elementOf(arg(0)))
      // Object.fromEntries gives back an object with each entry's value under its key (entriesOf).
      if (name === 'fromEntries') return { leaves: new Map(), props: entriesOf(args[0], record), fns: null }
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
      // defineProperty and defineProperties give back their target with what they define on it; create gives back a
      // new object, which reads its prototype's properties and those it defines.
      if (name === 'defineProperty' || name === 'defineProperties' || name === 'create') {
        const base = arg(0)
        const props = new Map<string, Held<L>>(base.props ?? [])
        for (const [key, value] of definedBy(x, record)) props.set(key, value)
        return name === 'create' ? { leaves: new Map(), props, fns: null } : { leaves: base.leaves, props, fns: base.fns }
      }
      return empty()
    }
    // Reflect.get reads a member as `.` and `[]` do.
    if (receiverNamed(x, 'Reflect') && name === 'get' && args[0] && !ts.isSpreadElement(args[0])) {
      const value = memberOf(valueOf(args[0]), literalKey(args[1]), x)
      if (leavesOf(value).size > 0) record?.add(x)
      return value
    }
    if (receiverNamed(x, 'Array') && name === 'from') return args[1] ? arrayOf(calledAt(1)) : arrayOf(elementOf(arg(0)))
    // Array.of and Array called without `new` give back an array of what they are handed, as its constructor does.
    if (receiverNamed(x, 'Array') && name === 'of') return elementsOf(args, record)
    const bare = knownAs(x.expression)
    if (bare?.global && bare.name === 'Array' && ts.isIdentifier(unwrapHeld(x.expression))) return elementsOf(args, record)
    if (name === 'useMemo') return calledAt(0)
    if (name === 'useCallback') return arg(0)
    // React's state, for a gate that reads it (HeldOptions.state): what each hook keeps, where it gives it back.
    if (state) {
      if (name === 'useState') {
        // React calls a function its setter is handed (an updater) and keeps what it returns.
        const handed = handedTo(x)
        const kept = union({ leaves: handed.leaves, props: handed.props, fns: null }, called(handed, record))
        return withProps([
          ['0', union(union(arg(0), calledAt(0)), kept)],
          ['1', setterOf(x)],
        ])
      }
      // useActionState (react-dom's useFormState before it) is a reducer: its action is called with the state and each
      // payload its dispatcher is handed, and its state is what the action returns.
      if (name === 'useReducer' || name === 'useActionState' || name === 'useFormState') {
        // A reducer the reading does not hold gives back, to a gate that reads with passThrough, what React hands it:
        // the state and each action its dispatcher is handed.
        const unheld = passThrough && !fnsOf(0)?.size ? handedTo(x) : empty<L>()
        return withProps([
          ['0', union(union(arg(1), unheld), union(calledAt(2), calledAt(0)))],
          ['1', setterOf(x)],
        ])
      }
      if (name === 'useOptimistic') {
        // React's optimistic state: its passthrough value, and what each call through its setter hands it, or, given an
        // update function, what that returns, called with the state and each value handed (one the reading does not
        // hold gives back, to a gate that reads with passThrough, what it is handed).
        const handed = handedTo(x)
        const kept = !args[1]
          ? { leaves: handed.leaves, props: handed.props, fns: null }
          : union(calledAt(1), passThrough && !fnsOf(1)?.size ? handed : empty<L>())
        return withProps([
          ['0', union(arg(0), kept)],
          ['1', setterOf(x)],
        ])
      }
      if (name === 'useRef') return withProps([['current', arg(0)]])
      if (name === 'useDeferredValue') return union(arg(0), arg(1))
      if (name === 'useSyncExternalStore') return union(calledAt(1), calledAt(2))
    }
    // Function.prototype's `call` and `apply` give back what the function they are read from gives back, and `bind`
    // gives back the function itself.
    const through = throughMethod(x, record)
    if (through) return through.method === 'bind' ? through.target : called(through.target, record)
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
      if (name === 'map' || name === 'flatMap') return arrayOf(calledAt(0))
      // `values()` iterates the elements (a Map's values, a Set's items), and `entries()` pairs each at index 1, unless
      // the receiver's own method of that name is a same-file function.
      if ((name === 'values' || name === 'entries') && args.length === 0 && !valueOf(x.expression).fns?.size) {
        const element = elementOf(valueOf(recv, record))
        return arrayOf(name === 'entries' ? withProps([['1', element]]) : element)
      }
      if (name === 'reduce' || name === 'reduceRight') return union(arg(1), calledAt(0))
      if (name === 'get' && args.length === 1) {
        const base = valueOf(recv)
        if (base.props) {
          const value = memberOf(base, literalKey(args[0]), x)
          if (leavesOf(value).size > 0) record?.add(x)
          return value
        }
      }
    }
    // A call of a same-file function holds what it returns, and a call of a leaf what the gate says it gives back.
    const callee = valueOf(x.expression)
    if (callee.fns?.size || !passThrough) return called(callee, record)
    // A call the reading cannot follow may give back what it is handed, as text: each argument, a spread one's
    // elements, and a method's receiver (passThrough); and what its callee's leaves give back (HeldOptions.calls).
    let handed = recv ? valueOf(recv, record) : empty<L>()
    for (const a of args) handed = union(handed, ts.isSpreadElement(a) ? elementOf(valueOf(a.expression, record)) : valueOf(a, record))
    return union(asText(handed), called(callee, record))
  }

  /** Gives a holder a value it may hold, beside those it holds already, nested at most DEPTH levels (bounded). */
  const give = (key: ts.Node, value: Held<L>) => {
    if (vacant(value)) return
    const before = holders.get(key)
    holders.set(key, bounded(before ? union(before, value) : value))
  }
  /** Gives a declared name its part of a value: a bare name the whole, each element of an object or array pattern its
      member, nested patterns included, with its default (which renders when the member is missing), and a rest element
      the rest: an array's elements from its place on (restOf), an object's properties the pattern does not name
      (othersOf; a key the scan cannot read names none). */
  const bindName = (name: ts.BindingName, value: Held<L>, node: ts.Node, record?: Set<ts.Node>): void => {
    // A name declared again in its scope (`var Mark; var Mark = QuotesIcon`) gives the binding its first declaration reads.
    if (ts.isIdentifier(name)) return give(declarationOf(name) ?? node, value)
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
    // What the code puts on `this` in an object literal's method or accessor, it puts on the literal (thisLiteral).
    if (t.kind === ts.SyntaxKind.ThisKeyword) {
      const literal = thisLiteral(t)
      if (literal) give(literal, value)
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
  /** How many arguments each same-file function is bound with (Function.prototype.bind): a later call of the bound
      function hands its arguments to the parameters after them. A bound list the scan cannot count (a spread) is
      ANY_SHIFT: a later argument may land on any parameter. */
  const boundShifts = new Map<Fn, Set<number>>()
  const ANY_SHIFT = -1
  /** Binds each parameter of a function to what a call passes it, by position: a rest parameter takes the arguments
      from its place on, each at its position (restOf), and past a spread argument each parameter may take any of its
      elements. A parameter's default is bound where it is declared. */
  const bindParams = (fn: Fn, passed: Array<Held<L>>, tail?: Held<L>) => {
    const args = argumentsOf(passed, tail)
    fn.parameters.forEach((p, i) => bindName(p.name, p.dotDotDotToken ? restOf(args, i) : (passed[i] ?? tail ?? empty<L>()), p))
  }
  /** Binds the parameters of these functions to what a call passes them (bindParams). A call of a function ever bound
      may be a call of the bound one, so its arguments also land after the bound arguments (boundShifts). */
  const pass = (fns: Set<Fn> | null | undefined, passed: Array<Held<L>>, tail?: Held<L>) => {
    for (const fn of fns ?? []) {
      bindParams(fn, passed, tail)
      for (const k of boundShifts.get(fn) ?? []) {
        if (k === ANY_SHIFT) bindParams(fn, [], [...passed, tail ?? empty<L>()].reduce(union, empty<L>()))
        else bindParams(fn, [...Array.from({ length: k }, () => empty<L>()), ...passed], tail)
      }
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
  /** Whether a value may be called: a same-file function, a hook's setter or dispatcher, or a leaf the gate calls. */
  const callable = (value: Held<L>): boolean =>
    !!value.fns?.size || !!value.setters?.size || (!!calls && [...value.leaves.keys()].some((leaf) => !!calls(leaf)?.length))
  /** A call of Function.prototype's `call`, `apply` or `bind` on a value the reading may call (an object's own member of
      that name is read as any member is), or of `Reflect.apply(f, thisArg, list)`: the method, the function value, and
      the arguments it hands the function, after `thisArg` (`apply`'s from its list: each element at its place, one the
      scan cannot place at any). A utility known by its name (an array's method, React's Children) is no value the
      reading may call, so its call through these is read as a call of the method. */
  const throughMethod = (x: ts.CallExpression, record?: Set<ts.Node>) => {
    const method = calleeName(x)
    const reflected = method === 'apply' && receiverNamed(x, 'Reflect')
    const recv = reflected ? x.arguments[0] : receiverOf(x)
    if (!recv || ts.isSpreadElement(recv) || (method !== 'call' && method !== 'apply' && method !== 'bind')) return undefined
    const target = valueOf(recv)
    if (!callable(target) || (!reflected && target.props?.has(method))) return undefined
    if (method !== 'apply') {
      const [passed, tail] = passedBy(x.arguments.slice(1), record)
      return { method, target, passed, tail }
    }
    const listArg = x.arguments[reflected ? 2 : 1]
    const list = listArg && !ts.isSpreadElement(listArg) ? valueOf(listArg, record) : empty<L>()
    const placed: Array<Held<L>> = []
    let tail: Held<L> | undefined
    for (const [key, value] of list.props ?? []) {
      if (/^\d+$/.test(key)) placed[Number(key)] = value
      else tail = union(tail ?? empty<L>(), value)
    }
    return { method, target, passed: Array.from(placed, (value) => value ?? empty<L>()), tail }
  }
  /** A call through a value, however the value reached the callee: a same-file function's parameters take what it is
      passed, and a hook's setter or dispatcher hands the hook its first argument (HeldOptions.state); React calls an
      updater a setter is handed with the state. */
  const callThrough = (callee: Held<L>, passed: Array<Held<L>>, tail?: Held<L>) => {
    if (callee.fns?.size) pass(callee.fns, passed, tail)
    const handed = passed[0] ?? tail ?? empty<L>()
    for (const hook of callee.setters ?? []) {
      give(hook, handed)
      if (handed.fns?.size && calleeName(hook) === 'useState') pass(handed.fns, [propertyOf(valueOf(hook), '0')])
    }
  }
  /** What a call gives a holder: a same-file function's parameters, a callback's, or an array or a `Map` it puts in. */
  const call = (x: ts.CallExpression, record?: Set<ts.Node>) => {
    const name = calleeName(x)
    const args = x.arguments
    const recv = receiverOf(x)
    const fnsAt = (i: number) => (args[i] ? valueOf(args[i]).fns : null)
    // React calls a reducer with the state and each action its dispatcher is handed in the file, and its initializer
    // with the initial argument (HeldOptions.state).
    if (state && (name === 'useReducer' || name === 'useActionState' || name === 'useFormState')) {
      const reducer = fnsAt(0)
      if (reducer?.size) pass(reducer, [propertyOf(valueOf(x, record), '0'), handedTo(x)])
      const init = name === 'useReducer' ? fnsAt(2) : null
      if (init?.size && args[1]) pass(init, [valueOf(args[1], record)])
    }
    // React calls useOptimistic's update function with the optimistic state and each value its setter is handed.
    if (state && name === 'useOptimistic') {
      const update = fnsAt(1)
      if (update?.size) pass(update, [propertyOf(valueOf(x, record), '0'), handedTo(x)])
    }
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
    // What a definition puts on a held object (Object.defineProperty, Object.defineProperties, Reflect.defineProperty:
    // what each descriptor gives), and what Reflect.set puts there, as an assignment does.
    const defines = (receiverNamed(x, 'Object') && (name === 'defineProperty' || name === 'defineProperties')) || (receiverNamed(x, 'Reflect') && name === 'defineProperty')
    if (defines || (receiverNamed(x, 'Reflect') && name === 'set')) {
      if (!args[0] || !holdsTarget(args[0])) return
      const props = defines ? definedBy(x, record) : new Map<string, Held<L>>()
      const put = !defines && args[2] ? valueOf(args[2], record) : empty<L>()
      if (!vacant(put)) props.set(literalKey(args[1]) ?? ANY, put)
      if (props.size) assign(args[0], { leaves: new Map(), props, fns: null }, record)
      return
    }
    // React's element call of a same-file component calls it with its props (a same-file function of a maker's name is
    // the file's own, called below).
    const component = ELEMENT_MAKERS.has(name) && args[0] && !valueOf(x.expression).fns?.size ? valueOf(args[0]).fns : null
    if (component?.size) {
      const props = args[1] ? valueOf(args[1], record) : empty<L>()
      // createElement's children arguments join its props; the runtime's calls hold theirs in their props.
      let children = empty<L>()
      if (name === 'createElement') for (const a of args.slice(2)) children = both(children, valueOf(a, record))
      pass(component, [vacant(children) ? props : union(props, withProps([['children', children]]))])
      // What the component returns renders here, not where it is written.
      returned(component, record)
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
      } else if ((name === 'push' || name === 'unshift' || name === 'splice' || (name === 'add' && args.length === 1)) && holdsTarget(recv)) {
        // What the code puts in an array after making it, or a Set's `add`, at indices the scan cannot know.
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
    // Function.prototype's methods: `call` and `apply` call the function they are read from, and `bind` hands it its
    // bound arguments now and puts a later call's after them.
    const through = throughMethod(x, record)
    if (through) {
      callThrough(through.target, through.passed, through.tail)
      const bound = args.slice(1)
      const k = bound.some(ts.isSpreadElement) ? ANY_SHIFT : bound.length
      if (through.method === 'bind' && k !== 0) {
        for (const fn of through.target.fns ?? []) boundShifts.set(fn, new Set([...(boundShifts.get(fn) ?? []), k]))
      }
      return
    }
    // A call through a value, however the value reached the callee (callThrough).
    const callee = valueOf(x.expression)
    if (!callee.fns?.size && !callee.setters?.size) return
    callThrough(callee, ...passedBy(args, record))
  }
  /** A JSX element of a same-file component calls it with a props object: each attribute's value, each spread's
      properties (a later attribute overriding), and its children as `children`. */
  const render = (x: ts.JsxElement | ts.JsxSelfClosingElement, record?: Set<ts.Node>) => {
    const opening = ts.isJsxElement(x) ? x.openingElement : x
    const tag = componentTag(opening)
    if (!tag) return
    const fns = valueOf(tag).fns
    if (!fns?.size) return
    const props = jsxProps(opening, record)
    if (ts.isJsxElement(x)) {
      let children = empty<L>()
      for (const child of x.children) children = both(children, childValue(child, record))
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
      } else if (passThrough && ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusEqualsToken) {
        // `+=` joins what it adds to what its target held (passThrough); either, not both, so the holder settles.
        const rec = holdsTarget(node.left) ? record : undefined
        assign(node.left, asText(union(valueOf(node.left), valueOf(node.right, rec))), rec)
      }
      else if (ts.isCallExpression(node)) call(node, record)
      else if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) render(node, record)
      // A literal a `this` is holds its own value, for the members of `this` its methods and accessors read (a hold of
      // nothing: where the literal is handed on records it).
      else if (ts.isObjectLiteralExpression(node) && thisLiterals.has(node)) give(node, valueOf(node))
      ts.forEachChild(node, visit)
    }
    visit(sf)
  }
  let sites = 0
  const count = (node: ts.Node): void => {
    if (ts.isVariableDeclaration(node) || ts.isParameter(node) || ts.isForOfStatement(node) || ts.isBinaryExpression(node) || ts.isCallExpression(node) || ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) sites++
    else if (ts.isObjectLiteralExpression(node) && thisLiterals.has(node)) sites++
    ts.forEachChild(node, count)
  }
  count(sf)

  // To a fixed point: each pass reads every source with what the passes before it found, and a holder only gains. In
  // code that runs, a value stops growing within a pass per source, or within DEPTH passes for a value that nests
  // itself (bounded). A value whose counts grow through its own reads (`const a = <>{a}</>`, which no runtime allows,
  // or a component handing its own children back to itself with more added) would count without end: the scan throws
  // instead of settling on an arbitrary count.
  const total = () =>
    [...holders.values()].reduce((n, value) => n + size(value), 0) + [...boundShifts.values()].reduce((n, shifts) => n + shifts.size, 0)
  let settled = false
  for (let pass = 0; !settled && pass <= sites + DEPTH + 1; pass++) {
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
    const type = ts.isCallExpression(element) ? (maker(element) ? element.arguments[0] : undefined) : componentTag(element)
    if (!type || !(ts.isIdentifier(type) || ts.isPropertyAccessExpression(type))) return empty()
    const fns = valueOf(type).fns
    return fns?.size ? renders(fns, element) : empty()
  }
  return { valueOf: (e) => valueOf(e), holderOf, renderOf, held }
}
