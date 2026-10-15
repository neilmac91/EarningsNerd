import ts from 'typescript'

/**
 * What a same-file binding holds, read by its name to a fixed point, for the gates that follow a value from where
 * it is written to where it is used: brandVoiceRules.spec.ts's heading icons and reservedGlyphs.spec.ts's glyph
 * counts. One reading for both, so a shape one gate follows the other follows too.
 *
 * A value is the set of leaves it may be (the gate says what a leaf is: an icon's import, a glyph's root) and, for
 * an object, what each of its properties holds. It is read through:
 *  - a binding's name, whatever it holds and with its shape kept (an alias of an object is that object; a const,
 *    let or var, by its initializer);
 *  - a member read by name or literal key (`MARK.alert`, `MARK['alert']`, a nested `A.b.c`), and one read by a key
 *    the scan cannot read (`MARK[kind]`), which may be any property;
 *  - a member destructured from an object (`const { alert: Alert } = MARK`);
 *  - an object literal's properties and spreads, in source order, so a later property overrides a spread's;
 *  - a conditional's two arms, both sides of `||` and `??`, the right of `&&`;
 *  - a JSX element's tag and its children (`<BellIcon />` holds what BellIcon holds, `<span><BellIcon /></span>` and
 *    the fragment `<><BellIcon /></>` hold it too, as do `{expressions}` among the children);
 *  - parentheses, `as`, `satisfies`, `<T>` and `!`.
 * Out of its reach, for each gate to name: a binding assigned after its declaration, a value built by a call
 * (`Object.assign`, a function's return, an array's methods) and what a function or a component renders.
 */
export interface Held<L> {
  leaves: Set<L>
  props: Map<string, Held<L>> | null
}

export interface HeldValues<L> {
  /** What an expression holds. */
  valueOf(e: ts.Expression): Held<L>
  /** The bindings that hold a leaf, by name. */
  holders: Map<string, Held<L>>
  /** The nodes a holder's initializer reads a leaf or another holder through: a hold, not a use. */
  held: Set<ts.Node>
}

const empty = <L>(): Held<L> => ({ leaves: new Set(), props: null })

/** Either value: the leaves of both, and each property either side holds. */
export function union<L>(a: Held<L>, b: Held<L>): Held<L> {
  let props: Map<string, Held<L>> | null = null
  if (a.props || b.props) {
    props = new Map(a.props ?? [])
    for (const [key, value] of b.props ?? []) props.set(key, props.has(key) ? union(props.get(key)!, value) : value)
  }
  return { leaves: new Set([...a.leaves, ...b.leaves]), props }
}

/** Every leaf a value holds, its properties' included. */
export function leavesOf<L>(value: Held<L>): Set<L> {
  const out = new Set(value.leaves)
  for (const prop of value.props?.values() ?? []) for (const leaf of leavesOf(prop)) out.add(leaf)
  return out
}

const size = <L>(value: Held<L>): number =>
  value.leaves.size + [...(value.props?.entries() ?? [])].reduce((n, [key, prop]) => n + key.length + size(prop), 0)

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
 * The values of one source. `leafOf` names the leaves an expression is by itself (an import of an icon, a
 * namespace's member), or returns undefined.
 */
export function heldValues<L>(sf: ts.SourceFile, leafOf: (e: ts.Expression) => L[] | undefined): HeldValues<L> {
  const holders = new Map<string, Held<L>>()

  const valueOf = (e: ts.Expression, record?: Set<ts.Node>): Held<L> => {
    const x = unwrapHeld(e)
    const own = leafOf(x)
    if (own?.length) {
      record?.add(x)
      return { leaves: new Set(own), props: null }
    }
    if (ts.isIdentifier(x)) {
      const holder = holders.get(x.text)
      if (!holder) return empty()
      record?.add(x)
      return holder
    }
    if (ts.isPropertyAccessExpression(x) || ts.isElementAccessExpression(x)) {
      const base = valueOf(x.expression)
      if (!base.props) return empty()
      const key = memberKey(x)
      const value = key === undefined ? [...base.props.values()].reduce(union, empty<L>()) : base.props.get(key) ?? empty<L>()
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
        if (ts.isJsxElement(child) || ts.isJsxSelfClosingElement(child) || ts.isJsxFragment(child)) value = union(value, valueOf(child, record))
        else if (ts.isJsxExpression(child) && child.expression) value = union(value, valueOf(child.expression, record))
      }
      return value
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
      return { leaves: new Set(), props }
    }
    return empty()
  }

  const bindings: ts.VariableDeclaration[] = []
  const collect = (node: ts.Node): void => {
    if (ts.isVariableDeclaration(node) && node.initializer) bindings.push(node)
    ts.forEachChild(node, collect)
  }
  collect(sf)

  /** What a declaration binds, by name: its initializer's value, or the members it destructures. */
  const bound = (d: ts.VariableDeclaration, record?: Set<ts.Node>): Array<[string, Held<L>]> => {
    if (ts.isIdentifier(d.name)) return [[d.name.text, valueOf(d.initializer!, record)]]
    if (!ts.isObjectBindingPattern(d.name)) return []
    const value = valueOf(d.initializer!, record)
    if (!value.props) return []
    const out: Array<[string, Held<L>]> = []
    for (const el of d.name.elements) {
      if (el.dotDotDotToken || !ts.isIdentifier(el.name)) continue
      const key = propertyKey(el.propertyName ?? el.name)
      const prop = key === undefined ? undefined : value.props.get(key)
      if (prop) out.push([el.name.text, prop])
    }
    return out
  }

  // To a fixed point: each pass reads every declaration with what the passes before it found. A value only
  // grows, so the passes stop; the bound covers a declaration that reads itself, which no runtime allows.
  const total = () => [...holders.values()].reduce((n, value) => n + size(value), 0)
  for (let pass = 0, before = -1; before !== total() && pass <= bindings.length + 1; pass++) {
    before = total()
    for (const d of bindings) {
      for (const [name, value] of bound(d)) if (leavesOf(value).size > 0) holders.set(name, value)
    }
  }

  const held = new Set<ts.Node>()
  for (const d of bindings) {
    const names = ts.isIdentifier(d.name) ? [d.name.text] : ts.isObjectBindingPattern(d.name) ? d.name.elements.map((el) => el.name.getText(sf)) : []
    if (names.some((name) => holders.has(name))) bound(d, held)
  }
  return { valueOf: (e) => valueOf(e), holders, held }
}
