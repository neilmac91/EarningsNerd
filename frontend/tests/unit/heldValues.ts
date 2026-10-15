import ts from 'typescript'

/**
 * What a same-file binding holds, read by its name to a fixed point, for the gates that follow a value from where
 * it is written to where it is used: brandVoiceRules.spec.ts's heading icons and reservedGlyphs.spec.ts's glyph
 * counts. One reading for both, so a shape one gate follows the other follows too.
 *
 * A value is the leaves it may be (the gate says what a leaf is: an icon's import, a glyph's root), each with how
 * many times it renders, and, for an object, what each of its properties holds. Counts add where a value renders its
 * parts together (an element's tag and children: `<><QuotesIcon /><QuotesIcon /></>` renders the glyph twice) and
 * take the larger where it renders one or the other (a conditional's arms, `||`, `??`, a member read by a key the
 * scan cannot read). It is read through:
 *  - a binding's name, whatever it holds and with its shape kept (an alias of an object is that object; a const,
 *    let or var, by its initializer), resolved by scope: a name reads the nearest enclosing declaration of it, so a
 *    name two functions each declare reads its own function's binding, and a parameter or a function of that name
 *    shadows an outer holder;
 *  - a member read by name or literal key (`MARK.alert`, `MARK['alert']`, a nested `A.b.c`), and one read by a key
 *    the scan cannot read (`MARK[kind]`), which may be any property;
 *  - a member destructured from an object or an array, nested patterns included (`const { alert: Alert } = MARK`,
 *    `const [Mark] = MARKS`, `const [{ alert }] = LIST`), with its default, which renders when the member is missing
 *    (`const { mark: Mark = QuotesIcon } = PROPS`); a parameter holds what its caller passes, which the scan cannot
 *    read, or its default, so a component's default prop (`({ icon: Mark = BellIcon })`) is read too;
 *  - an object literal's properties and spreads, in source order, so a later property overrides a spread's;
 *  - an array literal's elements by index (`const marks = [QuotesIcon]` read as `marks[0]`); past a spread the indices
 *    are unknown, so a literal index there may read any element from the spread on;
 *  - a conditional's two arms, both sides of `||` and `??`, the right of `&&`;
 *  - a JSX element's tag and its children (`<BellIcon />` holds what BellIcon holds, `<span><BellIcon /></span>` and
 *    the fragment `<><BellIcon /></>` hold it too, as do `{expressions}` among the children);
 *  - parentheses, `as`, `satisfies`, `<T>` and `!`.
 * Out of its reach, for each gate to name: a binding assigned after its declaration, a value built by a call
 * (`Object.assign`, a function's return, an array's methods) and what a function or a component renders.
 */
export interface Held<L> {
  /** Each leaf the value may be, with how many times it renders. */
  leaves: Map<L, number>
  props: Map<string, Held<L>> | null
}

export interface HeldValues<L> {
  /** What an expression holds. */
  valueOf(e: ts.Expression): Held<L>
  /** What the binding an identifier reads holds, when it holds a leaf; the binding is resolved by scope. */
  holderOf(id: ts.Identifier): Held<L> | undefined
  /** The nodes a holder's initializer reads a leaf or another holder through: a hold, not a use. */
  held: Set<ts.Node>
}

const empty = <L>(): Held<L> => ({ leaves: new Map(), props: null })

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

/** Either value (a conditional's arms, `||`, `??`): the leaves of both, each at the larger count, and each property
    either side holds. */
export function union<L>(a: Held<L>, b: Held<L>): Held<L> {
  return { leaves: joined(a.leaves, b.leaves, Math.max), props: joinedProps(a, b) }
}

/** Both values, rendered together (an element's tag and its children): each leaf as many times as the two render it. */
const both = <L>(a: Held<L>, b: Held<L>): Held<L> => ({ leaves: joined(a.leaves, b.leaves, add), props: joinedProps(a, b) })

/** Every leaf a value holds, its properties' included, with how many times it renders: a value read whole reads
    each of its properties. */
export function leavesOf<L>(value: Held<L>): Map<L, number> {
  let out = new Map(value.leaves)
  for (const prop of value.props?.values() ?? []) out = joined(out, leavesOf(prop), add)
  return out
}

/** The key prefix of an array's elements from a spread on, whose indices the scan cannot know. */
const REST = '…'

/** A member of a value by its key: undefined for a key the scan cannot read, which may be any property; a literal index
    an array's known elements do not reach may read any element from its spread on. */
function memberOf<L>(base: Held<L>, key: string | undefined): Held<L> {
  if (!base.props) return empty()
  if (key === undefined) return [...base.props.values()].reduce(union, empty<L>())
  const rest = () => [...base.props!].filter(([k]) => k.startsWith(REST)).map(([, v]) => v).reduce(union, empty<L>())
  return base.props.get(key) ?? (/^\d+$/.test(key) ? rest() : empty<L>())
}

const size = <L>(value: Held<L>): number =>
  [...value.leaves.values()].reduce(add, 0) + [...(value.props?.entries() ?? [])].reduce((n, [key, prop]) => n + key.length + size(prop), 0)

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

/**
 * The values of one source. `leafOf` names the leaves an expression is by itself (an import of an icon, a
 * namespace's member), or returns undefined.
 */
export function heldValues<L>(sf: ts.SourceFile, leafOf: (e: ts.Expression) => L[] | undefined): HeldValues<L> {
  // Keyed by the declaration (scopeResolver), never by the bare name.
  const holders = new Map<ts.Node, Held<L>>()
  const declarationOf = scopeResolver(sf)

  const valueOf = (e: ts.Expression, record?: Set<ts.Node>): Held<L> => {
    const x = unwrapHeld(e)
    const own = leafOf(x)
    if (own?.length) {
      record?.add(x)
      const leaves = new Map<L, number>()
      for (const leaf of own) leaves.set(leaf, (leaves.get(leaf) ?? 0) + 1)
      return { leaves, props: null }
    }
    if (ts.isIdentifier(x)) {
      const declaration = declarationOf(x)
      const holder = declaration && holders.get(declaration)
      if (!holder) return empty()
      record?.add(x)
      return holder
    }
    if (ts.isPropertyAccessExpression(x) || ts.isElementAccessExpression(x)) {
      const base = valueOf(x.expression)
      if (!base.props) return empty()
      const value = memberOf(base, memberKey(x))
      if (leavesOf(value).size > 0) record?.add(x)
      return value
    }
    if (ts.isConditionalExpression(x)) return union(valueOf(x.whenTrue, record), valueOf(x.whenFalse, record))
    if (ts.isBinaryExpression(x)) {
      const op = x.operatorToken.kind
      if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken) return union(valueOf(x.left, record), valueOf(x.right, record))
      if (op === ts.SyntaxKind.AmpersandAmpersandToken) return valueOf(x.right, record)
      return empty()
    }
    if (ts.isJsxSelfClosingElement(x) || ts.isJsxElement(x) || ts.isJsxFragment(x)) {
      const tag = ts.isJsxFragment(x) ? undefined : (ts.isJsxElement(x) ? x.openingElement : x).tagName
      let value = tag && (ts.isIdentifier(tag) || ts.isPropertyAccessExpression(tag)) ? valueOf(tag, record) : empty<L>()
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
        if (leavesOf(value).size > 0) props.set(index < 0 ? `${REST}${rest++}` : String(index), value)
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
      return { leaves: new Map(), props }
    }
    if (ts.isObjectLiteralExpression(x)) {
      const props = new Map<string, Held<L>>()
      for (const p of x.properties) {
        if (ts.isSpreadAssignment(p)) {
          for (const [key, value] of valueOf(p.expression, record).props ?? []) props.set(key, value)
          continue
        }
        if (!ts.isPropertyAssignment(p) && !ts.isShorthandPropertyAssignment(p)) continue
        const key = propertyKey(p.name)
        if (key === undefined) continue
        const value = valueOf(ts.isPropertyAssignment(p) ? p.initializer : p.name, record)
        if (leavesOf(value).size > 0) props.set(key, value)
        else props.delete(key)
      }
      return { leaves: new Map(), props }
    }
    return empty()
  }

  const bindings: Array<ts.VariableDeclaration | ts.ParameterDeclaration> = []
  const collect = (node: ts.Node): void => {
    if (ts.isVariableDeclaration(node) && node.initializer) bindings.push(node)
    if (ts.isParameter(node) && (node.initializer || !ts.isIdentifier(node.name))) bindings.push(node)
    ts.forEachChild(node, collect)
  }
  collect(sf)

  /** What a declaration binds, by the node that declares each name (scopeResolver's): its initializer's value, or what
      each element of an object or array pattern destructures from it, nested patterns included. A rest element is not
      followed. */
  const bound = (d: ts.VariableDeclaration | ts.ParameterDeclaration, record?: Set<ts.Node>): Array<[ts.Node, Held<L>]> => {
    const out: Array<[ts.Node, Held<L>]> = []
    const bind = (name: ts.BindingName, value: Held<L>, node: ts.Node): void => {
      if (ts.isIdentifier(name)) {
        out.push([node, value])
        return
      }
      name.elements.forEach((el, index) => {
        if (ts.isOmittedExpression(el) || el.dotDotDotToken) return
        const key = ts.isArrayBindingPattern(name) ? String(index) : propertyKey(el.propertyName ?? el.name)
        if (key === undefined) return
        // A default renders when the member is missing, so the element may hold either.
        const member = memberOf(value, key)
        bind(el.name, el.initializer ? union(member, valueOf(el.initializer, record)) : member, el)
      })
    }
    // A parameter's caller passes what the scan cannot read: it holds its default, if it has one.
    bind(d.name, d.initializer ? valueOf(d.initializer, record) : empty<L>(), d)
    return out
  }

  // To a fixed point: each pass reads every declaration with what the passes before it found. In code that runs, a
  // value stops growing within a pass per binding. A declaration that reads itself (`const a = <>{a}</>`, which no
  // runtime allows) would count without end: the scan throws instead of settling on an arbitrary count.
  const total = () => [...holders.values()].reduce((n, value) => n + size(value), 0)
  let settled = false
  for (let pass = 0; !settled && pass <= bindings.length + 1; pass++) {
    const before = total()
    for (const d of bindings) {
      for (const [declaration, value] of bound(d)) if (leavesOf(value).size > 0) holders.set(declaration, value)
    }
    settled = total() === before
  }
  if (!settled) throw new Error(`${sf.fileName}: what a same-file binding holds reads itself, so its count never settles`)

  const held = new Set<ts.Node>()
  for (const d of bindings) {
    const elementsOf = (name: ts.BindingName): ts.Node[] =>
      ts.isIdentifier(name) ? [] : name.elements.flatMap((el) => (ts.isOmittedExpression(el) ? [] : ts.isIdentifier(el.name) ? [el] : elementsOf(el.name)))
    const declarations: ts.Node[] = ts.isIdentifier(d.name) ? [d] : elementsOf(d.name)
    if (declarations.some((declaration) => holders.has(declaration))) bound(d, held)
  }
  const holderOf = (id: ts.Identifier) => {
    const declaration = declarationOf(id)
    return declaration ? holders.get(declaration) : undefined
  }
  return { valueOf: (e) => valueOf(e), holderOf, held }
}
