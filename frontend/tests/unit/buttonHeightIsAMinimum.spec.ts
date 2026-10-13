import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * A taller Button is set with min-h, never a fixed h-, and through the factory's own className
 * option. Below a 24rem viewport the Button's narrow state sets h-auto so a label can wrap
 * (components/ui/Button.tsx, wrapWhenNarrow), and that rule sits after every base utility in the
 * stylesheet, so a caller's `h-11` becomes 40px on a 360px phone while its `min-h-11` is kept; the
 * narrow state keeps a caller's min-h or py only when it can see them, which is the className option
 * of buttonVariants() (<Button> and the wrappers pass theirs through it), never a token beside the
 * factory's output in cx() or a template (frontend/DESIGN_SYSTEM.md, Button size).
 *
 * This gate reads every file under app, components, features, hooks and lib, twice. The first pass
 * finds the Button-like components: Button itself, and every component that forwards its caller's
 * props into buttonVariants()'s className option or onto a <Button>: a prop of the component's own
 * parameters, named directly (`className`), through `props.className`, declared in the body from
 * one (`const { className } = props`, `const classes = cx('w-full', className)`), inside an
 * expression (`cx('w-full', className)`) or as a spread of the props (`{...rest}`); a spread of
 * something else (a mapped module const) is not a caller's class (RetryButton, MarketingCta, and any
 * wrapper written later). A body const that mentions a prop anywhere in its initializer, even as a
 * guard (`const cls = cx('w-full', label === 'x' && 'italic')`), also makes a wrapper, so a caller's
 * h-<n> aimed at the component's outer element is then named: the rule fails loud there.
 *
 * The second pass fails on two things. First, a bare `h-<n>` token in the className of a Button-like
 * element or in a buttonVariants() className option (a literal, a same-file const, a shorthand
 * property, a conditional's branches, a template's text, an array's elements, a class composer's
 * arguments, a same-file helper's returned expression and a method call's receiver, such as
 * `['h-10', 'w-full'].join(' ')`; icon-sm is exempt); this rule reads what it can, and a call it
 * cannot resolve (an imported helper) gives it nothing. Second, in any class expression that composes
 * buttonVariants() (under its import name or an alias; in the attribute, or in a same-file const or
 * helper the attribute names anywhere in it, such as `cx(ROW, 'mt-2')`, `${ROW} mt-2` or `cls()`), a
 * literal `h-<n>`, `min-h-` or `py-` token outside the call, or a forwarded binding (a parameter such
 * as `className`, also as `props.className`, `className as string`, `className!`, or either side of
 * `||` and `??`) outside the call, which would carry a caller's min-h or py where the narrow state
 * cannot see it; the condition of `cond && 'class'`, `undefined`, `null` and a boolean are not
 * classes. The beside walk reads an array's elements, a spread's operand, the receiver of `.join`,
 * `.filter` and `.trim`, `.concat` with its arguments, and `.join`'s literal separator, which is set
 * between the classes (`[buttonVariants(), className].join(' ')`, `[…].filter(Boolean).join(' ')`); a
 * predicate is not a class. A call's arguments are read only when the callee is a class composer: cx
 * (components/ui/cx.ts, imported from there or through components/ui) or clsx (the tree has no cn).
 * Any other plain-name call is resolved to the same-file function of that name (an arrow or function
 * expression held by a const, or a function declaration) and its returned expression is walked (an
 * expression body, or a body whose only statement is a return; a conditional's branches count). A
 * binding the file does not resolve (a parameter, an import, a module object's member) is reported as
 * forwarded, and what the walk does not read (an imported helper, a helper with a longer body, a member
 * whose root is not a plain name such as `S[size].pad`, `get().big`, `this.x` or `(a ?? b).pad`, a
 * separator that is not a literal, an element access, an object, any other method) or one too deep to
 * read is reported as unreadable rather than skipped, so the beside rule fails closed. A name resolves
 * by scope: to the declaration in the nearest enclosing block or function body, then the module, so a
 * parameter, a destructured prop or a same-named const in another component never stands in.
 *
 * Known limits, both pinned in the self-check: a component that forwards its className into
 * RetryButton or MarketingCta, rather than into the factory or a <Button>, is not discovered (the
 * first pass reads only a factory call and a <Button>), and a function declaration in the component body
 * (`function cls() { return cx('w-full', className) }`) does not make a wrapper (a body binding is
 * read from a variable declaration only). The codebase has neither shape; class helpers are written
 * as arrow consts, which are read.
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const FIXED_HEIGHT = /(?:^|\s)!?h-(?:\d+(?:\.\d+)?|px|\[[^\]]+\])(?=\s|$)/
const HEIGHT_OR_PADDING = /(?:^|\s)!?(?:min-h-[^\s]+|py-[^\s]+|h-(?:\d+(?:\.\d+)?|px|\[[^\]]+\]))(?=\s|$)/

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

/** The local names buttonVariants is imported under in this file (`buttonVariants`, or an alias). */
function factoryNames(sf: ts.SourceFile): Set<string> {
  const names = new Set<string>()
  for (const stmt of sf.statements) {
    if (!ts.isImportDeclaration(stmt) || !stmt.importClause?.namedBindings || !ts.isNamedImports(stmt.importClause.namedBindings)) continue
    for (const el of stmt.importClause.namedBindings.elements) {
      if ((el.propertyName ?? el.name).text === 'buttonVariants') names.add(el.name.text)
    }
  }
  return names
}

const isFactoryCall = (n: ts.Node, names: Set<string>): n is ts.CallExpression =>
  ts.isCallExpression(n) && ts.isIdentifier(n.expression) && names.has(n.expression.text)

/** An expression without its parentheses, `as`, `satisfies` or non-null wrappers. */
const unwrapExpression = (e: ts.Expression): ts.Expression =>
  ts.isParenthesizedExpression(e) || ts.isAsExpression(e) || ts.isSatisfiesExpression(e) || ts.isNonNullExpression(e) ? unwrapExpression(e.expression) : e

const bindsName = (name: ts.BindingName, text: string): boolean =>
  ts.isIdentifier(name) ? name.text === text : name.elements.some((el) => !ts.isOmittedExpression(el) && bindsName(el.name, text))

/** The nearest enclosing function named as a component (its own name, or the const holding it, capitalised). */
function componentFunction(node: ts.Node): ts.SignatureDeclaration | undefined {
  for (let n: ts.Node | undefined = node.parent; n; n = n.parent) {
    if (ts.isFunctionLike(n) && /^[A-Z]/.test(functionName(n) ?? '')) return n
  }
  return undefined
}

function functionName(fn: ts.SignatureDeclaration): string | undefined {
  if ((ts.isFunctionDeclaration(fn) || ts.isFunctionExpression(fn)) && fn.name) return fn.name.text
  let holder: ts.Node = fn.parent
  while (ts.isCallExpression(holder)) holder = holder.parent
  return ts.isVariableDeclaration(holder) && ts.isIdentifier(holder.name) ? holder.name.text : undefined
}

/** Whether an expression reaches the component's own props: a parameter name (also destructured in the
    body from a parameter) or a `props.x` access on one, anywhere inside it. Callback parameters between
    the expression and the component (a `.map` arrow) do not count. */
function reachesProps(e: ts.Expression): boolean {
  const component = componentFunction(e)
  if (!component) return false
  const param = (text: string) => component.parameters.some((p) => bindsName(p.name, text))
  /** Whether a node holds an identifier that is a parameter or a body binding from one (a property's name is not one). */
  const holdsProp = (node: ts.Node, depth: number): boolean => {
    let found = false
    const look = (n: ts.Node) => {
      if (found) return
      if (ts.isIdentifier(n) && !(ts.isPropertyAccessExpression(n.parent) && n.parent.name === n) && (param(n.text) || bodyBound(n.text, depth))) found = true
      else ts.forEachChild(n, look)
    }
    look(node)
    return found
  }
  /** Whether a name is declared in the component's body from its props, directly or through another such declaration. */
  const bodyBound = (text: string, depth = 0): boolean => {
    if (depth > 3) return false
    let found = false
    const look = (n: ts.Node) => {
      if (found) return
      if (ts.isVariableDeclaration(n) && bindsName(n.name, text) && n.initializer && holdsProp(n.initializer, depth + 1)) found = true
      else ts.forEachChild(n, look)
    }
    look(component)
    return found
  }
  return holdsProp(e, 0)
}

type Declaration = ts.VariableDeclaration | ts.FunctionDeclaration

const declaresIn = (list: ts.VariableDeclarationList, text: string): ts.VariableDeclaration | undefined =>
  list.declarations.find((d) => bindsName(d.name, text))

/** The declaration a name refers to, by scope: the nearest enclosing block, function body or module that
    declares it, so a same-named const in another component never stands in. Undefined when the nearest
    binding is a parameter, a loop or catch variable, a destructuring or an import, or nothing binds it. */
function declarationOf(id: ts.Identifier): Declaration | undefined {
  const text = id.text
  for (let node: ts.Node | undefined = id.parent; node; node = node.parent) {
    if (ts.isFunctionLike(node) && node.parameters.some((p) => bindsName(p.name, text))) return undefined
    if (ts.isCatchClause(node) && node.variableDeclaration && bindsName(node.variableDeclaration.name, text)) return undefined
    if ((ts.isForStatement(node) || ts.isForOfStatement(node) || ts.isForInStatement(node)) && node.initializer
      && ts.isVariableDeclarationList(node.initializer) && declaresIn(node.initializer, text)) return undefined
    if (ts.isBlock(node) || ts.isSourceFile(node) || ts.isModuleBlock(node) || ts.isCaseClause(node) || ts.isDefaultClause(node)) {
      for (const stmt of node.statements) {
        if (ts.isFunctionDeclaration(stmt) && stmt.name?.text === text) return stmt
        const d = ts.isVariableStatement(stmt) ? declaresIn(stmt.declarationList, text) : undefined
        if (d) return ts.isIdentifier(d.name) ? d : undefined
      }
    }
  }
  return undefined
}

/** The initializer of the same-file const an identifier names, resolved by scope. */
function localInitializer(id: ts.Identifier): ts.Expression | undefined {
  const d = declarationOf(id)
  return d && ts.isVariableDeclaration(d) ? d.initializer : undefined
}

/** What the same-file function a name declares returns (a function declaration, or a const holding an arrow
    or function expression): its expression body, or the expression of a body whose only statement is a
    return. Undefined for anything else (an import, a longer body). */
function localReturn(id: ts.Identifier): ts.Expression | undefined {
  const d = declarationOf(id)
  const init = d && ts.isVariableDeclaration(d) && d.initializer ? unwrapExpression(d.initializer) : undefined
  const fn = d && ts.isFunctionDeclaration(d) ? d : init && (ts.isArrowFunction(init) || ts.isFunctionExpression(init)) ? init : undefined
  if (!fn?.body) return undefined
  if (!ts.isBlock(fn.body)) return fn.body
  const [only] = fn.body.statements
  return fn.body.statements.length === 1 && ts.isReturnStatement(only) ? only.expression : undefined
}

/** The local names the class composers are imported under: cx (components/ui/cx.ts, also through
    components/ui) and clsx (the tree has no cn). Only a composer's arguments are read as classes. */
const composerCache = new WeakMap<ts.SourceFile, Set<string>>()
function composerNames(sf: ts.SourceFile): Set<string> {
  const cached = composerCache.get(sf)
  if (cached) return cached
  const names = new Set<string>()
  composerCache.set(sf, names)
  for (const stmt of sf.statements) {
    if (!ts.isImportDeclaration(stmt) || !ts.isStringLiteral(stmt.moduleSpecifier) || !stmt.importClause) continue
    const from = stmt.moduleSpecifier.text
    const wanted = /^(?:@\/components\/ui(?:\/cx)?|\.\/cx)$/.test(from) ? 'cx' : from === 'clsx' ? 'clsx' : undefined
    if (!wanted) continue
    if (wanted === 'clsx' && stmt.importClause.name) names.add(stmt.importClause.name.text)
    const bindings = stmt.importClause.namedBindings
    if (bindings && ts.isNamedImports(bindings)) {
      for (const el of bindings.elements) if ((el.propertyName ?? el.name).text === wanted) names.add(el.name.text)
    }
  }
  return names
}

/** The literal strings an expression can be: a literal, a same-file const, a conditional's branches, a
    template's text, an array's elements, a composer's arguments, a same-file helper's returned expression
    and, for a method call (`[…].join(' ')`), its receiver and arguments. Another call (an imported helper)
    gives nothing: this rule reads what it can, and only the beside rule fails closed. */
function literals(e: ts.Expression, sf: ts.SourceFile, depth = 0): string[] {
  if (depth > 6) return []
  if (ts.isParenthesizedExpression(e)) return literals(e.expression, sf, depth + 1)
  if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) return [e.text]
  if (ts.isTemplateExpression(e)) return [[e.head.text, ...e.templateSpans.map((s) => s.literal.text)].join(' ')]
  if (ts.isConditionalExpression(e)) return [...literals(e.whenTrue, sf, depth + 1), ...literals(e.whenFalse, sf, depth + 1)]
  if (ts.isBinaryExpression(e)) return [...literals(e.left, sf, depth + 1), ...literals(e.right, sf, depth + 1)]
  if (ts.isArrayLiteralExpression(e)) return e.elements.flatMap((el) => literals(el, sf, depth + 1))
  if (ts.isSpreadElement(e)) return literals(e.expression, sf, depth + 1)
  if (ts.isCallExpression(e)) {
    const args = () => e.arguments.flatMap((a) => literals(a, sf, depth + 1))
    if (ts.isPropertyAccessExpression(e.expression)) return [...literals(e.expression.expression, sf, depth + 1), ...args()]
    const callee = unwrapExpression(e.expression)
    if (!ts.isIdentifier(callee)) return []
    if (composerNames(sf).has(callee.text)) return args()
    const returned = localReturn(callee)
    return returned ? literals(returned, sf, depth + 1) : []
  }
  if (ts.isIdentifier(e)) {
    const init = localInitializer(e)
    return init ? literals(init, sf, depth + 1) : []
  }
  return []
}

/** The methods a class list is composed with, and what their arguments are: concat's are classes, join's
    separator is text set between the classes, filter's predicate and trim take none. The receiver is read. */
const CLASS_METHODS = new Map<string, 'classes' | 'separator' | 'none'>([['concat', 'classes'], ['join', 'separator'], ['filter', 'none'], ['trim', 'none']])
const NOT_A_CLASS = new Set([ts.SyntaxKind.NullKeyword, ts.SyntaxKind.TrueKeyword, ts.SyntaxKind.FalseKeyword])

/** What an expression carries outside any factory call inside it: literal strings, and the names of
    forwarded bindings (identifiers the file does not resolve to a const) and of what it cannot read. */
function beside(e: ts.Expression, sf: ts.SourceFile, names: Set<string>): { literals: string[]; forwarded: string[] } {
  const out = { literals: [] as string[], forwarded: [] as string[] }
  const composers = composerNames(sf)
  const go = (raw: ts.Expression, depth: number): void => {
    const x = unwrapExpression(raw)
    if (isFactoryCall(x, names)) return
    const unreadable = (why: string, n: ts.Node = x) => { out.forwarded.push(`${n.getText(sf).slice(0, 40)} (${why})`) }
    if (depth > 6) { unreadable('too deep to read'); return }
    if (ts.isStringLiteral(x) || ts.isNoSubstitutionTemplateLiteral(x)) { out.literals.push(x.text); return }
    if (NOT_A_CLASS.has(x.kind)) return
    if (ts.isSpreadElement(x)) { go(x.expression, depth + 1); return }
    if (ts.isArrayLiteralExpression(x)) { x.elements.forEach((el) => go(el, depth + 1)); return }
    if (ts.isConditionalExpression(x)) { go(x.whenTrue, depth + 1); go(x.whenFalse, depth + 1); return }
    if (ts.isBinaryExpression(x)) {
      // The left of `&&` is a condition, never a class; either side of `||`, `??` or `+` can be the value.
      if (x.operatorToken.kind !== ts.SyntaxKind.AmpersandAmpersandToken) go(x.left, depth + 1)
      go(x.right, depth + 1)
      return
    }
    if (ts.isCallExpression(x)) {
      const callee = unwrapExpression(x.expression)
      if (ts.isIdentifier(callee)) {
        // A composer's arguments are its classes; a same-file helper's are not, its returned expression is.
        if (composers.has(callee.text)) { x.arguments.forEach((a) => go(a, depth + 1)); return }
        const returned = localReturn(callee)
        if (returned) go(returned, depth + 1)
        else unreadable('unreadable')
        return
      }
      const method = ts.isPropertyAccessExpression(callee) ? CLASS_METHODS.get(callee.name.text) : undefined
      if (method === undefined || !ts.isPropertyAccessExpression(callee)) { unreadable('unreadable'); return }
      go(callee.expression, depth + 1)
      if (method === 'classes') x.arguments.forEach((a) => go(a, depth + 1))
      if (method === 'separator' && x.arguments[0]) {
        const sep = unwrapExpression(x.arguments[0])
        if (ts.isStringLiteral(sep) || ts.isNoSubstitutionTemplateLiteral(sep)) out.literals.push(sep.text)
        else unreadable('unreadable', sep)
      }
      return
    }
    if (ts.isTemplateExpression(x)) {
      out.literals.push(x.head.text, ...x.templateSpans.map((s) => s.literal.text))
      x.templateSpans.forEach((s) => go(s.expression, depth + 1))
      return
    }
    if (ts.isPropertyAccessExpression(x)) {
      let root: ts.Expression = x
      while (ts.isPropertyAccessExpression(root)) root = unwrapExpression(root.expression)
      // A member of a plain name is a binding the file does not resolve; any other root (an element
      // access, a call's result, `this`, a parenthesised `??`) is not read.
      if (!ts.isIdentifier(root)) unreadable('unreadable')
      else if (root.text !== 'undefined') out.forwarded.push(x.getText(sf))
      return
    }
    if (ts.isIdentifier(x)) {
      if (x.text === 'undefined') return
      const init = localInitializer(x)
      if (init) go(init, depth + 1)
      else out.forwarded.push(x.text)
      return
    }
    unreadable('unreadable')
  }
  go(e, 0)
  return out
}

/** Whether an identifier is a reference to a binding (not a property's name or a declaration's own name). */
const isReference = (n: ts.Identifier): boolean => {
  const p = n.parent
  return !((ts.isPropertyAccessExpression(p) || ts.isPropertyAssignment(p) || ts.isJsxAttribute(p) || ts.isVariableDeclaration(p)
    || ts.isFunctionDeclaration(p) || ts.isParameter(p) || ts.isBindingElement(p) || ts.isPropertySignature(p)) && p.name === n)
}

/** Whether an expression composes the factory: a call in it, or in a same-file const or helper it names. */
const containsFactory = (e: ts.Node, names: Set<string>): boolean => {
  let found = false
  const seen = new Set<ts.Node>()
  const look = (n: ts.Node) => {
    if (found) return
    if (isFactoryCall(n, names)) { found = true; return }
    if (ts.isIdentifier(n) && isReference(n)) {
      const d = declarationOf(n)
      const target = d && (ts.isFunctionDeclaration(d) ? d.body : d.initializer)
      if (target && !seen.has(target)) { seen.add(target); look(target) }
      return
    }
    ts.forEachChild(n, look)
  }
  look(e)
  return found
}

const stringOf = (e: ts.Expression | undefined): string | null => {
  const x = e && ts.isJsxExpression(e) ? e.expression : e
  return x && (ts.isStringLiteral(x) || ts.isNoSubstitutionTemplateLiteral(x)) ? x.text : null
}

/** The component a JSX element sits in. */
function componentName(node: ts.Node): string | undefined {
  const fn = componentFunction(node)
  return fn ? functionName(fn) : undefined
}

function parseText(file: string, text: string): ts.SourceFile {
  return ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
}

const parse = (file: string): ts.SourceFile => parseText(file, readFileSync(file, 'utf8'))

type Sources = Map<string, ts.SourceFile>

/** Button, plus every component that forwards a caller's className into the factory's option or onto a <Button>. */
function buttonLikeTags(sources: Sources): Set<string> {
  const tags = new Set(['Button'])
  for (const [, sf] of sources) {
    const names = factoryNames(sf)
    const visit = (node: ts.Node) => {
      if (isFactoryCall(node, names) && node.arguments[0] && ts.isObjectLiteralExpression(node.arguments[0])) {
        const option = node.arguments[0].properties.find((p) => (ts.isPropertyAssignment(p) || ts.isShorthandPropertyAssignment(p)) && p.name.getText() === 'className')
        const value = option && ts.isShorthandPropertyAssignment(option) ? option.name : option && ts.isPropertyAssignment(option) ? option.initializer : undefined
        const owner = value && reachesProps(value) ? componentName(node) : undefined
        if (owner) tags.add(owner)
      }
      if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText() === 'Button') {
        const forwards = node.attributes.properties.some((p) => (ts.isJsxSpreadAttribute(p) && reachesProps(p.expression))
          || (ts.isJsxAttribute(p) && p.name.getText() === 'className' && !!p.initializer && ts.isJsxExpression(p.initializer) && !!p.initializer.expression && reachesProps(p.initializer.expression)))
        const owner = forwards ? componentName(node) : undefined
        if (owner) tags.add(owner)
      }
      ts.forEachChild(node, visit)
    }
    visit(sf)
  }
  return tags
}

/** Every bare h-<n> on a Button-like className or a factory option, and everything beside the factory. */
function offenders(sources: Sources, tags: Set<string>): string[] {
  const out: string[] = []
  for (const [file, sf] of sources) {
    const rel = path.relative(ROOT, file)
    const names = factoryNames(sf)
    const at = (n: ts.Node) => `${rel}:${sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1}`
    const reportFixed = (n: ts.Node, className: ts.Expression, size: string | null) => {
      if (size === 'icon-sm') return
      for (const value of literals(className, sf)) {
        const hit = FIXED_HEIGHT.exec(value)
        if (hit) out.push(`${at(n)} "${hit[0].trim()}" (use min-h)`)
      }
    }
    const reportBeside = (n: ts.Node, expression: ts.Expression) => {
      if (!containsFactory(expression, names)) return
      const found = beside(expression, sf, names)
      for (const value of found.literals) {
        const hit = HEIGHT_OR_PADDING.exec(value)
        if (hit) out.push(`${at(n)} "${hit[0].trim()}" beside buttonVariants() (pass it through the factory's className option)`)
      }
      for (const name of found.forwarded) out.push(`${at(n)} "${name}" forwarded beside buttonVariants() (pass it through the factory's className option)`)
    }
    const visit = (node: ts.Node) => {
      if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
        const attr = (name: string) => node.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText() === name)
        const init = attr('className')?.initializer
        const className = init && ts.isJsxExpression(init) ? init.expression : init
        if (className) {
          if (tags.has(node.tagName.getText())) reportFixed(node, className, stringOf(attr('size')?.initializer))
          reportBeside(node, className)
        }
      }
      if (isFactoryCall(node, names) && node.arguments[0] && ts.isObjectLiteralExpression(node.arguments[0])) {
        const options = node.arguments[0]
        const prop = (name: string) => {
          const p = options.properties.find((p) => (ts.isPropertyAssignment(p) || ts.isShorthandPropertyAssignment(p)) && p.name.getText() === name)
          return p && ts.isPropertyAssignment(p) ? p.initializer : p && ts.isShorthandPropertyAssignment(p) ? p.name : undefined
        }
        const className = prop('className')
        if (className) reportFixed(node, className, stringOf(prop('size')))
      }
      ts.forEachChild(node, visit)
    }
    visit(sf)
  }
  return out
}

const files = SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))
const sources: Sources = new Map(files.map((file) => [file, parse(file)] as const))

describe('a taller Button is set with min-h, never a fixed h-, through the factory', () => {
  it('the Button-like components are discovered', () => {
    const tags = buttonLikeTags(sources)
    expect([...tags]).toEqual(expect.arrayContaining(['Button', 'RetryButton', 'MarketingCta']))
  })

  it('no Button-like className or buttonVariants() option carries a bare h-<n>, and nothing sits beside the factory', () => {
    expect(offenders(sources, buttonLikeTags(sources)), 'below 24rem the narrow state sets h-auto and keeps only the min-h and py it can see, the factory\'s className option').toEqual([])
  })

  it('the scan catches what it is for (a self-check on fixed sources)', () => {
    const file = path.join(ROOT, 'features/zzfixture/Probe.tsx')
    const src = `import { Button, buttonVariants, cx } from '@/components/ui'
import { sourceTraceChipClass } from '@/features/filings/lib/sourceTraceChip'
const BIG = ['h-10', 'w-full'].join(' ')
const ROW = [buttonVariants({ variant: 'ghost' }), 'min-h-11', 'mt-2'].filter(Boolean).join(' ')
export function Joined({ className }: { className?: string }) {
  return <a href="/" className={[buttonVariants({ variant: 'primary' }), className].join(' ')}>x</a>
}
export function Padded() {
  return <a href="/" className={[buttonVariants({ variant: 'primary' }), 'py-3'].join(' ')}>x</a>
}
export function Big() {
  return <Button className={BIG}>x</Button>
}
export function Row() {
  return <a href="/" className={ROW}>x</a>
}
export function Concat({ className }: { className?: string }) {
  return <a href="/" className={buttonVariants().concat(' ', className ?? '')}>x</a>
}
export function Spread({ extra }: { extra: string[] }) {
  return <a href="/" className={[buttonVariants(), ...extra].join(' ')}>x</a>
}
export function Unknown({ open }: { open: boolean }) {
  return <a href="/" className={cx(buttonVariants(), styles['big'], { 'ring-2': open })}>x</a>
}
export function Mapped({ className }: { className?: string }) {
  return <a href="/" className={[buttonVariants(), className].map(String).join(' ')}>x</a>
}
export function Fine({ open }: { open: boolean }) {
  return <a href="/" className={[buttonVariants(), 'mt-3', open && 'ring-2', null, false].filter(Boolean).join(' ')}>x</a>
}
export function LabeledCls({ title, className }: { title?: string; className?: string }) {
  const label = title ?? 'x'
  const cls = cx('w-full', label === 'x' && 'italic')
  return <div className={className}><Button className={cls}>{label}</Button></div>
}
export function MarketingCta({ className, href }: { className?: string; href: string }) {
  return <a href={href} className={buttonVariants({ className })}>x</a>
}
export function Outer({ className }: { className?: string }) {
  return <MarketingCta href="/" className={className} />
}
export function FnDecl({ className }: { className?: string }) {
  function cls() { return cx('w-full', className) }
  return <Button className={cls()}>x</Button>
}
export function Callers() {
  return (
    <>
      <LabeledCls title="t" className="h-10" />
      <Outer className="h-10" />
      <FnDecl className="h-10" />
    </>
  )
}
const tall = () => 'min-h-12 py-3'
const chipClasses = (kind: 'a' | 'b') => kind === 'a' ? 'py-3 min-h-11' : 'py-2'
const tallCls = () => 'h-10 w-full'
function twoSteps() { const base = 'mt-2'; return base }
export function Helpers({ className }: { className?: string }) {
  return (
    <>
      <a href="/" className={cx(buttonVariants(), tall())}>x</a>
      <a href="/" className={cx(buttonVariants(), chipClasses('a'))}>x</a>
      <a href="/" className={cx(buttonVariants({ variant: 'secondary' }), sourceTraceChipClass(false))}>x</a>
      <a href="/" className={cx(buttonVariants(), className)}>x</a>
      <Button className={tallCls()}>x</Button>
      <a href="/" className={cx(buttonVariants(), twoSteps())}>x</a>
    </>
  )
}
const S = { lg: { pad: 'py-3' } }
const get = () => ({ big: 'py-3' })
export function Roots({ size, a, b }: { size: 'lg'; a?: { pad: string }; b: { pad: string } }) {
  return (
    <>
      <a href="/" className={cx(buttonVariants(), S[size].pad)}>x</a>
      <a href="/" className={cx(buttonVariants(), get().big)}>x</a>
      <a href="/" className={cx(buttonVariants(), (a ?? b).pad)}>x</a>
    </>
  )
}
export class Legacy {
  x = 'py-3'
  render() { return <a href="/" className={cx(buttonVariants(), this.x)}>x</a> }
}
export function Separators({ sep, label }: { sep: string; label: string }) {
  return (
    <>
      <a href="/" className={[buttonVariants(), 'mt-2'].join(' py-3 ')}>x</a>
      <a href="/" className={[buttonVariants(), 'mt-2'].join(sep)}>x</a>
      <a href="/" className={cx(buttonVariants(), label.trim())}>x</a>
    </>
  )
}
const COMPOSED = cx(buttonVariants(), 'py-3')
const BASE = buttonVariants()
const cls = () => cx(buttonVariants(), 'py-3')
export function Composed() {
  return (
    <>
      <a href="/" className={cx(COMPOSED, 'mt-2')}>x</a>
      <a href="/" className={\`\${BASE} py-3\`}>x</a>
      <a href="/" className={cls()}>x</a>
    </>
  )
}
export function SameNameA() {
  const pick = cx('mt-2')
  return <div className={pick}>x</div>
}
export function SameNameB() {
  const pick = cx(buttonVariants(), 'min-h-11')
  return <a href="/" className={pick}>x</a>
}
`
    const fixture: Sources = new Map([[file, parseText(file, src)]])
    const tags = buttonLikeTags(fixture)
    expect([...tags].sort()).toEqual(['Button', 'LabeledCls', 'MarketingCta'])
    // Discovered: LabeledCls (its cls mentions the title prop as a guard: fail-loud) and MarketingCta. Not
    // discovered, the two known limits: Outer (forwards into MarketingCta) and FnDecl (a function declaration).
    const via = "beside buttonVariants() (pass it through the factory's className option)"
    expect(offenders(fixture, tags)).toEqual([
      `features/zzfixture/Probe.tsx:6 "className" forwarded ${via}`,
      `features/zzfixture/Probe.tsx:9 "py-3" ${via}`,
      'features/zzfixture/Probe.tsx:12 "h-10" (use min-h)',
      `features/zzfixture/Probe.tsx:15 "min-h-11" ${via}`,
      `features/zzfixture/Probe.tsx:18 "className" forwarded ${via}`,
      `features/zzfixture/Probe.tsx:21 "extra" forwarded ${via}`,
      `features/zzfixture/Probe.tsx:24 "styles['big'] (unreadable)" forwarded ${via}`,
      `features/zzfixture/Probe.tsx:24 "{ 'ring-2': open } (unreadable)" forwarded ${via}`,
      `features/zzfixture/Probe.tsx:27 "[buttonVariants(), className].map(String (unreadable)" forwarded ${via}`,
      'features/zzfixture/Probe.tsx:50 "h-10" (use min-h)',
      // A same-file helper's returned expression is read, a conditional's branches included; an imported
      // helper or a longer body is unreadable; a composer's argument is still forwarded.
      `features/zzfixture/Probe.tsx:63 "min-h-12" ${via}`,
      `features/zzfixture/Probe.tsx:64 "py-3" ${via}`,
      `features/zzfixture/Probe.tsx:64 "py-2" ${via}`,
      `features/zzfixture/Probe.tsx:65 "sourceTraceChipClass(false) (unreadable)" forwarded ${via}`,
      `features/zzfixture/Probe.tsx:66 "className" forwarded ${via}`,
      'features/zzfixture/Probe.tsx:67 "h-10" (use min-h)',
      `features/zzfixture/Probe.tsx:68 "twoSteps() (unreadable)" forwarded ${via}`,
      // A member whose root is not a plain name is unreadable.
      `features/zzfixture/Probe.tsx:77 "S[size].pad (unreadable)" forwarded ${via}`,
      `features/zzfixture/Probe.tsx:78 "get().big (unreadable)" forwarded ${via}`,
      `features/zzfixture/Probe.tsx:79 "(a ?? b).pad (unreadable)" forwarded ${via}`,
      `features/zzfixture/Probe.tsx:85 "this.x (unreadable)" forwarded ${via}`,
      // A literal separator's text is read, any other separator is unreadable; label.trim() reads its receiver.
      `features/zzfixture/Probe.tsx:90 "py-3" ${via}`,
      `features/zzfixture/Probe.tsx:91 "sep (unreadable)" forwarded ${via}`,
      `features/zzfixture/Probe.tsx:92 "label" forwarded ${via}`,
      // A const or helper that composes the factory is checked inside a larger expression.
      `features/zzfixture/Probe.tsx:102 "py-3" ${via}`,
      `features/zzfixture/Probe.tsx:103 "py-3" ${via}`,
      `features/zzfixture/Probe.tsx:104 "py-3" ${via}`,
      // A name resolves by scope: SameNameA's pick is its own, not SameNameB's.
      `features/zzfixture/Probe.tsx:114 "min-h-11" ${via}`,
    ])
  })
})
