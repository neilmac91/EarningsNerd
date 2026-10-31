import ts from 'typescript'

/**
 * Lexical name resolution for the AST gates (busyControlsStayFocusable.spec.ts, spinnerGateHoldsFailure.spec.ts):
 * a reference resolves to the binding of its name visible from it, so two components in one file may each
 * declare their own `cannotSubmit`, and a parameter shadows an outer const. A function declaration binds its name
 * to its body, so a handler written `function reload() { … }` is followed like `const reload = () => …`. Not a spec:
 * a module the gates share. It also finds every reference to a binding (bindingReferences), how an expression is
 * written where it stands (writtenAs), and where a container can change after its initializer (containerEscape, and
 * bindingEscape from a binding's references): the gates that read a const's object or array
 * (passwordRulesLockstep.spec.tsx, notificationPreferencesConsumed.spec.ts) trust one only while every use of it reads.
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

type Resolver = (ref: ts.Identifier) => Binding | undefined

/** The wrappers a value passes through unchanged: parentheses, `as`, `satisfies`, `!` and `<T>`. */
const passesThrough = (node: ts.Node) =>
  ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isSatisfiesExpression(node) || ts.isNonNullExpression(node) || ts.isTypeAssertionExpression(node)
/** The outermost node a value reaches through those wrappers. */
const outermost = (node: ts.Node): ts.Node => {
  let at = node
  while (passesThrough(at.parent)) at = at.parent
  return at
}
/** A value without those wrappers. */
const bare = (node: ts.Expression): ts.Expression => (passesThrough(node) ? bare((node as ts.ParenthesizedExpression).expression) : node)
/** A property's key as written: `ac`, `'auto-complete'`, `0`. */
const keyText = (name: ts.PropertyName) => (ts.isIdentifier(name) || ts.isStringLiteralLike(name) || ts.isNumericLiteral(name) || ts.isPrivateIdentifier(name) ? name.text : name.getText())

/** Whether an identifier names a binding where a value is read or written: not a declaration's own name, a property's name
    or key, a JSX attribute's name, a label, or an import. */
function isReference(id: ts.Identifier): boolean {
  const parent = id.parent
  if (ts.isPropertyAccessExpression(parent)) return parent.expression === id
  if (ts.isBindingElement(parent)) return parent.initializer === id
  if (ts.isQualifiedName(parent) || ts.isLabeledStatement(parent) || ts.isBreakOrContinueStatement(parent) || ts.isMetaProperty(parent) || ts.isJsxAttribute(parent)) return false
  if (ts.isImportSpecifier(parent) || ts.isImportClause(parent) || ts.isNamespaceImport(parent) || ts.isImportEqualsDeclaration(parent) || ts.isNamespaceExport(parent)) return false
  if (ts.isExportSpecifier(parent)) return (parent.propertyName ?? parent.name) === id && !parent.parent.parent.moduleSpecifier
  if (
    ts.isPropertyAssignment(parent) || ts.isPropertyDeclaration(parent) || ts.isMethodDeclaration(parent) || ts.isGetAccessorDeclaration(parent) ||
    ts.isSetAccessorDeclaration(parent) || ts.isEnumMember(parent) || ts.isVariableDeclaration(parent) || ts.isParameter(parent) ||
    ts.isFunctionDeclaration(parent) || ts.isFunctionExpression(parent) || ts.isClassDeclaration(parent) || ts.isClassExpression(parent)
  ) {
    return parent.name !== id
  }
  return true
}

const REFERENCES = new WeakMap<ts.SourceFile, Map<ts.Node, ts.Identifier[]>>()
/** Every reference to each binding of a file: the identifiers that resolve to it where a value is read or written (never its
    own name, a key, a JSX attribute's name or a type). */
export function bindingReferences(sf: ts.SourceFile, resolve: Resolver = bindingResolver(sf)): (decl: Binding['decl']) => readonly ts.Identifier[] {
  let index = REFERENCES.get(sf)
  if (!index) {
    const found = new Map<ts.Node, ts.Identifier[]>()
    const visit = (node: ts.Node): void => {
      if (ts.isTypeNode(node)) return
      const decl = ts.isIdentifier(node) && isReference(node) ? resolve(node)?.decl : undefined
      if (decl) found.set(decl, found.get(decl) ?? []).get(decl)!.push(node as ts.Identifier)
      ts.forEachChild(node, visit)
    }
    visit(sf)
    REFERENCES.set(sf, (index = found))
  }
  const references = index
  return (decl) => references.get(decl) ?? []
}

const ASSIGNS = (kind: ts.SyntaxKind) => kind >= ts.SyntaxKind.FirstAssignment && kind <= ts.SyntaxKind.LastAssignment
/** How an expression is written where it stands: assigned (`=`, `+=`, `||=`), incremented or decremented, deleted, or
    assigned by destructuring (`[x] = …`, `({ k: x } = …)`) or by a loop (`for (x of …)`); undefined where it is not. */
export function writtenAs(expr: ts.Expression): string | undefined {
  const at = outermost(expr)
  const parent = at.parent
  if (ts.isBinaryExpression(parent) && parent.left === at && ASSIGNS(parent.operatorToken.kind)) return 'assigned'
  if ((ts.isPrefixUnaryExpression(parent) || ts.isPostfixUnaryExpression(parent)) && (parent.operator === ts.SyntaxKind.PlusPlusToken || parent.operator === ts.SyntaxKind.MinusMinusToken)) {
    return 'incremented or decremented'
  }
  if (ts.isDeleteExpression(parent)) return 'deleted'
  let target: ts.Node = at
  for (;;) {
    const up = target.parent
    const element = ts.isArrayLiteralExpression(up) || ts.isObjectLiteralExpression(up) || ts.isSpreadElement(up) || ts.isSpreadAssignment(up) || passesThrough(up)
    if (!element && !(ts.isPropertyAssignment(up) && up.initializer === target) && !(ts.isShorthandPropertyAssignment(up) && up.name === target)) break
    target = up
  }
  const top = target.parent
  if (target !== at && ts.isBinaryExpression(top) && top.left === target && top.operatorToken.kind === ts.SyntaxKind.EqualsToken) return 'assigned by destructuring'
  if ((ts.isForOfStatement(top) || ts.isForInStatement(top)) && top.initializer === target) return 'assigned by a loop'
  return undefined
}

/** Whether a function's own body holds a node that passes `test`: an arrow's body is its own, a nested function's is not. */
const ownBodyHas = (fn: ts.SignatureDeclaration, test: (node: ts.Node) => boolean): boolean => {
  const visit = (node: ts.Node): boolean => test(node) || (!(ts.isFunctionLike(node) && !ts.isArrowFunction(node)) && !!ts.forEachChild(node, visit))
  const body = (fn as ts.FunctionLikeDeclarationBase).body
  return !!body && visit(body)
}
const STORES = new Set([ts.SyntaxKind.EqualsToken, ts.SyntaxKind.BarBarEqualsToken, ts.SyntaxKind.AmpersandAmpersandEqualsToken, ts.SyntaxKind.QuestionQuestionEqualsToken])

/** An array's methods that only read it; those that call a callback with each element (and the array last); and those
    whose result holds its elements. Any other method (push, sort, splice, fill) may write it. */
const ITERATES = new Set(['map', 'forEach', 'filter', 'find', 'findIndex', 'findLast', 'findLastIndex', 'some', 'every', 'flatMap', 'reduce', 'reduceRight'])
const HANDS_OUT = new Set(['filter', 'find', 'findLast', 'slice', 'at', 'concat', 'flat', 'entries', 'values', 'toSorted', 'toReversed', 'toSpliced', 'with'])
const ARRAY_READS = new Set([...ITERATES, ...HANDS_OUT, 'includes', 'indexOf', 'lastIndexOf', 'join', 'keys', 'toString', 'toLocaleString'])
/** The global functions that only read what they are handed; those whose result holds its parts; Object.freeze returns it. */
const READS_ONLY = new Set(['Object.keys', 'Object.isFrozen', 'Object.isSealed', 'Object.isExtensible', 'Array.isArray', 'JSON.stringify', 'structuredClone', 'String', 'Number', 'Boolean'])
const HANDS_OUT_CALLS = new Set(['Object.values', 'Object.entries', 'Array.from'])

type Container = ts.ObjectLiteralExpression | ts.ArrayLiteralExpression
/** One step from a value into the container it holds: an entry's key (null for any entry) and the container one step in. */
type Step = { key: string | null; inner: Container | undefined }
/** Where a container can change after it is made: the use, and what it does there. */
export interface ContainerEscape {
  at: ts.Node
  how: string
}

/**
 * Where an object or an array literal can change after it is made, or undefined where nothing can change it: the first use
 * of it, of an alias of it or of a part of it, that is not a read. A const binding stops a reassignment of the name, not a
 * write into what it holds, so every use is followed: a const or a `let` that holds it (each reference; a `var` is not
 * read), a pattern that takes it apart (a key, an index, a rest that keeps its other keys), a default, an entry of another
 * literal it is stored in (that literal's uses at the key), a branch of a condition or a logical operator, a same-file
 * function's parameter it is handed to, and the callback an array method of its own hands it to. A read is a member read,
 * a comparison, a template slot, a spread copy (whose parts it still holds), a JSX child, an attribute of an intrinsic
 * element, a call of an entry that cannot reach it as `this` (an arrow, or a function that never reads `this`), a method
 * of its array that only reads it, and a global that only reads (`Object.keys`, `JSON.stringify`, `Object.freeze`, which
 * returns it). Anything else is not: an entry assigned (`=`, `+=`, `||=`), incremented, deleted or assigned by
 * destructuring or a loop; any other method called on it (`push`, `sort`, a method that reads `this`); handed to a call
 * (`Object.assign(it, …)`, `Reflect.set(it, …)`, any function a same-file one is not), to a component (a prop, or a
 * spread of what it holds) or to React as a ref; stored by an assignment, into a `var` or a class; returned, thrown or
 * yielded; its name reassigned; and exported (another module may write it) unless `exports` is false. `reads` names a
 * reader's own read sites (a save call it reads an update at).
 */
export const containerEscape = (literal: Container, sf: ts.SourceFile, resolve: Resolver, options: EscapeOptions = {}): ContainerEscape | undefined =>
  escapeReader(sf, resolve, options).container(literal)
/** Where what a binding holds can change through it, read as containerEscape reads a container's uses, from each reference
    to the binding (a component's props, a parameter no call binds: a call of one of its entries calls what a caller
    handed, so it counts as a read). */
export const bindingEscape = (decl: Binding['decl'], sf: ts.SourceFile, resolve: Resolver, options: EscapeOptions = {}): ContainerEscape | undefined =>
  escapeReader(sf, resolve, options).binding(decl)
type EscapeOptions = { exports?: boolean; reads?: (use: ts.Expression) => boolean }

function escapeReader(sf: ts.SourceFile, resolve: Resolver, { exports = true, reads = () => false }: EscapeOptions) {
  const references = bindingReferences(sf, resolve)
  const seen = new Map<ts.Node, Set<string>>()
  let budget = 4000
  const escape = (at: ts.Node, how: string): ContainerEscape => ({ at, how })
  /** The same-file function an expression is: one written in place, or a name bound to a declaration or a const holding one. */
  const functionAt = (expr: ts.Expression): ts.SignatureDeclaration | undefined => {
    const inner = bare(expr)
    if (ts.isArrowFunction(inner) || ts.isFunctionExpression(inner)) return inner
    const decl = ts.isIdentifier(inner) ? resolve(inner)?.decl : undefined
    if (decl && ts.isFunctionDeclaration(decl)) return decl
    const init = decl && ts.isVariableDeclaration(decl) && decl.parent.flags & ts.NodeFlags.Const && decl.initializer ? bare(decl.initializer) : undefined
    return init && (ts.isArrowFunction(init) || ts.isFunctionExpression(init)) ? init : undefined
  }
  /** A global's dotted name (`Object.freeze`, `JSON.stringify`, `structuredClone`) where no binding of the file shadows it. */
  const globalName = (expr: ts.Expression): string | undefined => {
    const inner = bare(expr)
    const root = ts.isPropertyAccessExpression(inner) ? inner.expression : inner
    return ts.isIdentifier(root) && !resolve(root) && (inner === root || ts.isIdentifier((inner as ts.PropertyAccessExpression).name)) ? inner.getText(sf) : undefined
  }
  /** Whether calling an entry hands it no `this` to write through: an arrow, or a function or method that never reads `this`
      (for a key it cannot name, every entry). A method it does not hold (a built-in: push, sort) may write it. */
  const callsWithoutThis = (holder: Container | undefined, key: string | undefined): boolean => {
    if (!holder) return true
    const entries: ts.Node[] = ts.isObjectLiteralExpression(holder)
      ? holder.properties.filter((p) => key === undefined || (!!p.name && !ts.isComputedPropertyName(p.name) && keyText(p.name) === key))
      : holder.elements.filter((_, index) => key === undefined || String(index) === key)
    return entries.length > 0 && entries.every((entry) => {
      const value = ts.isPropertyAssignment(entry) ? bare(entry.initializer) : ts.isMethodDeclaration(entry) ? entry : ts.isExpression(entry) ? bare(entry) : undefined
      const fn = value && (ts.isArrowFunction(value) || ts.isFunctionExpression(value) || ts.isMethodDeclaration(value)) ? value : undefined
      return !!fn && (ts.isArrowFunction(fn) || !ownBodyHas(fn, (node) => node.kind === ts.SyntaxKind.ThisKeyword))
    })
  }
  /** A value bound to a declaration (a variable's initializer, a parameter or its default, a pattern's default): every
      reference to the name, or each part a pattern takes. */
  const bound = (decl: ts.VariableDeclaration | ts.ParameterDeclaration | ts.BindingElement, path: readonly Step[], holder: Container | undefined): ContainerEscape | undefined => {
    let root: ts.Node = decl
    while (ts.isBindingElement(root)) root = root.parent.parent
    const list = ts.isVariableDeclaration(root) && ts.isVariableDeclarationList(root.parent) ? root.parent : undefined
    if (list && !(list.flags & (ts.NodeFlags.Const | ts.NodeFlags.Let))) return escape(decl, 'stored into a var')
    if (exports && list && ts.getCombinedModifierFlags(root as ts.VariableDeclaration) & ts.ModifierFlags.Export) return escape(decl, 'exported, so another module may write it')
    return ts.isIdentifier(decl.name) ? firstOf(references(decl), (ref) => flows(ref, path, holder)) : pattern(decl.name, path, holder)
  }
  /** Each part a pattern takes of a value that is the container (path empty) or holds it: a key, an index or a rest of
      what holds it, followed one step in; an object's rest, a copy the readers read as the value without the keys taken
      beside it, at the same level. */
  const pattern = (name: ts.BindingPattern, path: readonly Step[], holder: Container | undefined): ContainerEscape | undefined => {
    for (const [index, element] of name.elements.entries()) {
      if (ts.isOmittedExpression(element)) continue
      const [step, ...rest] = path
      let into: { path: readonly Step[]; holder: Container | undefined } | undefined
      if (ts.isArrayBindingPattern(name)) {
        if (element.dotDotDotToken) into = step ? { path: [{ key: null, inner: step.inner }, ...rest], holder } : undefined
        else into = step && (step.key === null || step.key === String(index)) ? { path: rest, holder: step.inner } : undefined
      } else if (element.dotDotDotToken) {
        const keys = name.elements.filter((other) => other !== element).map((other) => other.propertyName ?? (other.name as ts.Identifier))
          .map((key) => (ts.isComputedPropertyName(key) ? null : keyText(key)))
        into = step && step.key !== null && keys.includes(step.key) ? undefined : { path, holder }
      } else {
        const key = element.propertyName ?? element.name
        const text = ts.isComputedPropertyName(key) ? null : keyText(key as ts.PropertyName)
        into = step && (step.key === null || text === null || step.key === text) ? { path: rest, holder: step.inner } : undefined
      }
      if (!into) continue
      const found = ts.isIdentifier(element.name) ? firstOf(references(element), (ref) => flows(ref, into.path, into.holder)) : pattern(element.name, into.path, into.holder)
      if (found) return found
    }
    return undefined
  }
  /** An array read by a method of its own: a callback (written in place or a same-file function) takes each element (the
      part, where the array holds it) and the array itself last; one this reader cannot read hands them out. */
  const iterated = (call: ts.Node, method: string, path: readonly Step[], holder: Container | undefined): ContainerEscape | undefined => {
    if (!ITERATES.has(method)) return undefined
    const callback = ts.isCallExpression(call) ? call.arguments[0] : undefined
    const fn = callback && !ts.isSpreadElement(callback) ? functionAt(callback) : undefined
    if (!fn || fn.parameters.some((p) => p.dotDotDotToken)) return escape(call, 'handed to a callback this reader cannot read')
    const reduce = method === 'reduce' || method === 'reduceRight'
    const array = fn.parameters[reduce ? 3 : 2]
    const found = array ? bound(array, path, holder) : undefined
    const [step, ...rest] = path
    const element = fn.parameters[reduce ? 1 : 0]
    return found ?? (step && element && (step.key === null || /^\d+$/.test(step.key)) ? bound(element, rest, step.inner) : undefined)
  }
  /** Where a value that is the container (path empty) or holds it along `path` goes from `value`. */
  const flows = (value: ts.Expression, path: readonly Step[], holder: Container | undefined): ContainerEscape | undefined => {
    const visit = path.map((step) => step.key ?? '\u0000').join('\u0001')
    const visits = seen.get(value) ?? new Set<string>()
    if (visits.has(visit)) return undefined
    seen.set(value, visits.add(visit))
    if (--budget < 0 || path.length > 8) return escape(value, 'held through more steps than this reader follows')
    const at = outermost(value) as ts.Expression
    const parent = at.parent
    if (reads(at)) return undefined
    const rebound = ts.isIdentifier(value) ? writtenAs(value) : undefined
    if (rebound) return escape(value, `the name that holds it ${rebound}`)
    // A member: an entry read (the container is not the entry), written, or called with the container as `this`.
    if ((ts.isPropertyAccessExpression(parent) || ts.isElementAccessExpression(parent)) && parent.expression === at) {
      const argument = ts.isElementAccessExpression(parent) ? bare(parent.argumentExpression) : undefined
      const key = ts.isPropertyAccessExpression(parent) ? parent.name.text : argument && (ts.isStringLiteralLike(argument) || ts.isNumericLiteral(argument)) ? argument.text : undefined
      const member = outermost(parent).parent
      const call = (ts.isCallExpression(member) || ts.isNewExpression(member)) && member.expression === outermost(parent) ? member : ts.isTaggedTemplateExpression(member) && member.tag === outermost(parent) ? member : undefined
      const reading = call && !!holder && ts.isArrayLiteralExpression(holder) && key !== undefined && ARRAY_READS.has(key)
      if (!path.length) {
        const written = writtenAs(parent)
        if (written) return escape(parent, `an entry ${written}`)
        if (!call || callsWithoutThis(holder, key)) return undefined
        return reading ? iterated(call, key!, path, holder) : escape(call, 'a method called on it')
      }
      const [step, ...rest] = path
      if (call) {
        if (reading) return HANDS_OUT.has(key!) ? escape(call, 'a method that hands out what it holds') : iterated(call, key!, path, holder)
        return callsWithoutThis(holder, key) ? undefined : escape(call, 'a method called on what holds it')
      }
      if (key !== undefined && step.key !== null && key !== step.key) return undefined
      return writtenAs(parent) ? undefined : flows(parent, rest, step.inner)
    }
    if ((ts.isVariableDeclaration(parent) || ts.isParameter(parent) || ts.isBindingElement(parent)) && parent.initializer === at) return bound(parent, path, holder)
    // Stored into another literal: that literal holds it at the key (any key where computed, any index after a spread).
    if ((ts.isPropertyAssignment(parent) && parent.initializer === at) || (ts.isShorthandPropertyAssignment(parent) && parent.name === at)) {
      const key = ts.isComputedPropertyName(parent.name) ? null : keyText(parent.name)
      return flows(parent.parent, [{ key, inner: holder }, ...path], parent.parent)
    }
    if (ts.isArrayLiteralExpression(parent)) {
      const index = parent.elements.indexOf(at)
      const key = parent.elements.slice(0, index).some(ts.isSpreadElement) ? null : String(index)
      return flows(parent, [{ key, inner: holder }, ...path], parent)
    }
    // A spread copies its entries: the copy holds its parts, never it.
    if (ts.isSpreadAssignment(parent)) return path.length ? flows(parent.parent, path, parent.parent) : undefined
    if (ts.isSpreadElement(parent)) {
      const outer = parent.parent
      if (!path.length) return undefined
      return ts.isArrayLiteralExpression(outer) ? flows(outer, [{ key: null, inner: path[0].inner }, ...path.slice(1)], outer) : escape(outer, 'what it holds handed to a call')
    }
    const intrinsic = (element: ts.Node) =>
      (ts.isJsxOpeningElement(element) || ts.isJsxSelfClosingElement(element)) && /^[a-z][^.]*$/.test(element.tagName.getText(sf))
    if (ts.isJsxSpreadAttribute(parent)) return path.length && !intrinsic(parent.parent.parent) ? escape(parent, 'what it holds handed to a component') : undefined
    if (ts.isJsxExpression(parent)) {
      const attribute = parent.parent
      if (!ts.isJsxAttribute(attribute)) return undefined
      if (attribute.name.getText(sf) === 'ref') return escape(attribute, 'handed to React as a ref, which writes it')
      return intrinsic(attribute.parent.parent) ? undefined : escape(attribute, 'handed to a component')
    }
    if ((ts.isCallExpression(parent) || ts.isNewExpression(parent)) && parent.expression !== at) {
      const name = globalName(parent.expression)
      if (name === 'Object.freeze') return flows(parent, path, holder)
      if (name && READS_ONLY.has(name)) return undefined
      if (name && HANDS_OUT_CALLS.has(name)) return path.length ? escape(parent, 'what it holds handed out by a call') : undefined
      // A same-file function takes it as the parameter at its place; any other call may write it.
      const args: readonly ts.Expression[] = parent.arguments ?? []
      const index = args.indexOf(at)
      const fn = ts.isCallExpression(parent) ? functionAt(parent.expression) : undefined
      const rest = fn?.parameters.findIndex((p) => p.dotDotDotToken) ?? -1
      if (!fn || args.slice(0, index).some(ts.isSpreadElement) || (rest >= 0 && rest <= index) || ownBodyHas(fn, (node) => ts.isIdentifier(node) && node.text === 'arguments')) {
        return escape(parent, 'handed to a call')
      }
      return fn.parameters[index] ? bound(fn.parameters[index], path, holder) : undefined
    }
    if (ts.isCallExpression(parent) || ts.isNewExpression(parent) || ts.isTaggedTemplateExpression(parent) || ts.isDecorator(parent)) return escape(parent, 'called')
    if (ts.isReturnStatement(parent) || (ts.isArrowFunction(parent) && parent.body === at)) return escape(parent, 'returned from a function')
    if (ts.isThrowStatement(parent) || ts.isYieldExpression(parent)) return escape(parent, 'handed out')
    if (ts.isPropertyDeclaration(parent)) return escape(parent, 'stored into a class')
    if (ts.isExportAssignment(parent) || ts.isExportSpecifier(parent)) return exports ? escape(parent, 'exported, so another module may write it') : undefined
    if (ts.isBinaryExpression(parent)) {
      const op = parent.operatorToken.kind
      if (ASSIGNS(op)) return parent.right === at && STORES.has(op) ? escape(parent, 'stored by an assignment') : undefined
      if (op === ts.SyntaxKind.AmpersandAmpersandToken || op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken) return flows(parent, path, holder)
      return op === ts.SyntaxKind.CommaToken && parent.right === at ? flows(parent, path, holder) : undefined
    }
    if (ts.isConditionalExpression(parent)) return parent.condition === at ? undefined : flows(parent, path, holder)
    if (ts.isAwaitExpression(parent)) return flows(parent, path, holder)
    if (ts.isTemplateSpan(parent)) return ts.isTaggedTemplateExpression(parent.parent.parent) ? escape(parent.parent.parent, 'handed to a call') : undefined
    if (ts.isForOfStatement(parent) && parent.expression === at) {
      const [step, ...rest] = path
      const decl = ts.isVariableDeclarationList(parent.initializer) ? parent.initializer.declarations[0] : undefined
      if (!step) return undefined
      return decl && (step.key === null || /^\d+$/.test(step.key)) ? bound(decl, rest, step.inner) : escape(parent, 'what it holds handed to a loop this reader cannot read')
    }
    const reading =
      ts.isPrefixUnaryExpression(parent) || ts.isPostfixUnaryExpression(parent) || ts.isTypeOfExpression(parent) || ts.isVoidExpression(parent) ||
      ts.isExpressionStatement(parent) || ts.isIfStatement(parent) || ts.isWhileStatement(parent) || ts.isDoStatement(parent) || ts.isForStatement(parent) ||
      ts.isForInStatement(parent) || ts.isSwitchStatement(parent) || ts.isCaseClause(parent) || ts.isComputedPropertyName(parent) ||
      (ts.isElementAccessExpression(parent) && parent.argumentExpression === at) ||
      ts.isJsxOpeningElement(parent) || ts.isJsxSelfClosingElement(parent) || ts.isJsxClosingElement(parent)
    return reading ? undefined : escape(parent, 'used where this reader cannot tell it is only read')
  }
  return {
    container: (literal: Container) => flows(literal, [], literal),
    binding: (decl: Binding['decl']) => firstOf(references(decl), (ref) => flows(ref, [], undefined)),
  }
}

/** The first value `each` returns for the items, or undefined. */
function firstOf<T, R>(items: readonly T[], each: (item: T) => R | undefined): R | undefined {
  for (const item of items) {
    const found = each(item)
    if (found !== undefined) return found
  }
  return undefined
}
