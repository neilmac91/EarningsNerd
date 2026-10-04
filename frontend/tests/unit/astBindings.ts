import ts from 'typescript'

/**
 * Lexical name resolution for the AST gates (busyControlsStayFocusable.spec.ts, spinnerGateHoldsFailure.spec.ts):
 * a reference resolves to the binding of its name visible from it, so two components in one file may each
 * declare their own `cannotSubmit`, and a parameter shadows an outer const. A function declaration binds its name
 * to its body, so a handler written `function reload() { … }` is followed like `const reload = () => …`. Not a spec:
 * a module the gates share.
 */

/** A name binding: where it is visible, its declaration, and what it aliases (if anything). */
export interface Binding {
  scope: ts.Node
  decl: ts.VariableDeclaration | ts.ParameterDeclaration | ts.BindingElement | ts.FunctionDeclaration
  /**
   * The initializer, for `{ isPending: x }` the property it renames, or a function declaration's body; none for a
   * plain parameter.
   */
  alias?: ts.Node
  /** A variable declaration's initializer only (what a same-file const holds). */
  init?: ts.Expression
}

/** The node whose extent bounds a binding's visibility: the enclosing block, or a parameter's function. */
export function scopeOf(node: ts.Node): ts.Node {
  if (ts.isParameter(node)) return node.parent
  for (let p = node.parent; ; p = p.parent) {
    if (ts.isParameter(p)) return p.parent
    if (
      ts.isBlock(p) || ts.isSourceFile(p) || ts.isModuleBlock(p) || ts.isCaseClause(p) || ts.isDefaultClause(p) ||
      ts.isCatchClause(p) || ts.isForStatement(p) || ts.isForInStatement(p) || ts.isForOfStatement(p)
    ) {
      return p
    }
  }
}

/** Resolves a reference to the innermost binding of its name whose scope contains the reference. */
export function bindingResolver(sf: ts.SourceFile): (ref: ts.Identifier) => Binding | undefined {
  const bindings = new Map<string, Binding[]>()
  const bind = (name: ts.Identifier, decl: Binding['decl'], alias?: ts.Node, init?: ts.Expression): void => {
    bindings.set(name.text, [...(bindings.get(name.text) ?? []), { scope: scopeOf(decl), decl, alias, init }])
  }
  const collect = (node: ts.Node): void => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
      bind(node.name, node, node.initializer, node.initializer)
    } else if (ts.isParameter(node) && ts.isIdentifier(node.name)) bind(node.name, node)
    else if (ts.isBindingElement(node) && ts.isIdentifier(node.name)) bind(node.name, node, node.propertyName)
    else if (ts.isFunctionDeclaration(node) && node.name && node.body) bind(node.name, node, node.body)
    ts.forEachChild(node, collect)
  }
  collect(sf)
  return (ref) => {
    let best: Binding | undefined
    for (const b of bindings.get(ref.text) ?? []) {
      if (b.scope.pos > ref.pos || ref.end > b.scope.end) continue
      if (!best || b.scope.end - b.scope.pos < best.scope.end - best.scope.pos) best = b
    }
    return best
  }
}
