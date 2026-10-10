import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { bindingResolver, type Binding } from './astBindings'

/**
 * Rule-12 gate for lessons/frontend-busy-controls-stay-focusable.md (e) and DESIGN_SYSTEM §4: no element
 * opacity on an aria-disabled control. A control that is busy or unavailable stays focusable
 * (`aria-disabled` plus an early return, never native `disabled`), so it can still show its focus ring,
 * and an element `opacity` fades that ring with everything else the element paints: under `opacity-50`
 * the brand ring on panel fell from 1.97:1 to 1.37:1 in light and from 2.87:1 to 1.68:1 in dark
 * (PopularTickerChips, Chromium 141). The unavailable look fades what the control draws in (its label's
 * ink, its hairline, a switch track's fill) or a child (`group-aria-disabled:opacity-50` on the
 * content), never the element.
 *
 * The scan reads the TypeScript AST of every .ts and .tsx under app/, components/, features/, hooks/ and
 * lib/. Comments never count. Two clauses, no allowlist:
 *
 *  1. No class token, in any string or template chunk of any of those files (a className, a `cx(…)`
 *     argument, a class list held in a module const), puts an `opacity-*` utility behind a variant that
 *     matches the element's own aria-disabled state: `aria-disabled:`, `aria-[disabled=true]:`, or an
 *     arbitrary variant naming `aria-disabled`, under any other variants (`dark:aria-disabled:hover:`).
 *     `group-aria-disabled:` and `peer-aria-disabled:` style another element, whose opacity does not
 *     reach the control's ring, so they pass.
 *  2. An aria-disabled control holds no `opacity-*` class at all, except behind `disabled:` (a natively
 *     disabled control cannot hold focus, so it shows no ring). This is the pending-opacity shape, a fade
 *     a busy flag picks in JS: AlertBell's `pending || checking ? 'cursor-progress opacity-60' : ''`.
 *     A control is a JSX element that carries an `aria-disabled` attribute, or a use of a shared control:
 *     a component that renders such an element and hands it the caller's className (its `className`
 *     prop, or its rest props). The DS Button renders `loading` as aria-disabled, so
 *     `<Button loading={busy} className={busy ? 'opacity-50' : ''}>` fails; a Button that is never given
 *     `loading` is no control. Which uses count is read from the component's own `aria-disabled`
 *     expression. When it is falsy unless a prop is passed (props with no default or a falsy one, joined
 *     by `||`, `&&` or `??`: Button's `loading || undefined`), a use is a control when it passes one of
 *     those props. Any other expression can be truthy at a use that passes nothing (a negation, a truthy
 *     default, a call, state), so every use is a control (RetryButton, AlertBell). A wrapper that
 *     forwards to a shared control is one too, and a use under an alias (`const BusyButton = Button`,
 *     `memo(Button)`) is a use of it.
 *     The scan reads every string and template chunk of the control's className and of what its
 *     identifiers name: a const's initializer (one property of a class map, for `LOOKS.busy` or a name
 *     destructured from it) or a function declaration's body, resolved in lexical
 *     scope, followed transitively and across modules, through an import (`@/…` or relative, named or
 *     default) and a barrel's re-exports (`export { a as b } from`, `export * from`). So a shared class
 *     list such as `fieldUnavailableClass` is read at each control that takes it, whatever variant it is
 *     written behind.
 *
 * What it cannot see: a component that takes its props undestructured (`props.className`), is used
 * under a member tag (`ui.Button`) or is loaded lazily (`dynamic(() => import(…))`); two components that
 * render each other; a class list built up by reassignment (`let cls = ''; cls += …`); a trigger prop or a
 * className that reaches a use through a props
 * spread; a class list reached through a namespace import (`import * as`; the app has none) or held in
 * a package; an `opacity` set by a `style` prop or by a rule in globals.css (it has none keyed to
 * aria-disabled); an ancestor's opacity.
 */

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const ROOTS = ['app', 'components', 'features', 'hooks', 'lib']

function walk(dir: string, out: string[]): string[] {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name)
    if (statSync(p).isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(p) && !p.endsWith('.d.ts')) out.push(p)
  }
  return out
}

/** `dark:aria-disabled:hover:!opacity-50` is variants dark, aria-disabled, hover and the utility
    `!opacity-50`. A colon inside brackets (`[&:hover]:`, `aria-[disabled=true]:`) does not split. */
function parseToken(token: string): { variants: string[]; utility: string } {
  const parts: string[] = []
  let depth = 0
  let start = 0
  for (let i = 0; i < token.length; i += 1) {
    const c = token[i]
    if (c === '[' || c === '(') depth += 1
    else if (c === ']' || c === ')') depth -= 1
    else if (c === ':' && depth === 0) {
      parts.push(token.slice(start, i))
      start = i + 1
    }
  }
  return { variants: parts, utility: token.slice(start) }
}

/** The element-opacity utility, with `!`, an arbitrary value or as an arbitrary property (`[opacity:0.5]`):
    not `bg-opacity-*` or `transition-opacity`, and not full strength (`opacity-100`), which fades nothing. */
const fadesElement = (utility: string) =>
  /^!?(opacity-|\[opacity:)/.test(utility) && !/^!?(opacity-100|opacity-\[1\]|\[opacity:1\])$/.test(utility)
/** A variant that matches the element's own aria-disabled state. */
const ownAriaDisabled = (variant: string) =>
  variant === 'aria-disabled' || /^aria-\[disabled\b/.test(variant) || (variant.startsWith('[') && variant.includes('aria-disabled'))

const isChunk = (n: ts.Node): n is ts.StringLiteralLike | ts.TemplateHead | ts.TemplateMiddle | ts.TemplateTail =>
  ts.isStringLiteralLike(n) || ts.isTemplateHead(n) || ts.isTemplateMiddle(n) || ts.isTemplateTail(n)
const tokensOf = (text: string) => text.split(/\s+/).filter(Boolean)

interface Offender {
  line: number
  token: string
  /** `variant`: clause 1. `element`: clause 2. */
  clause: 'variant' | 'element'
  /** Clause 2: where the class is written, when that is not the control's own line. */
  writtenAt?: string
}

/** A name that is a member's or an object key's (`styles.chip`, `{ className: … }`), not a reference. */
const isMemberName = (n: ts.Identifier) =>
  (ts.isPropertyAccessExpression(n.parent) && n.parent.name === n) || (ts.isPropertyAssignment(n.parent) && n.parent.name === n)

/** A source file's text, or undefined when there is no such file. */
type Read = (file: string) => string | undefined

interface Module {
  file: string
  sf: ts.SourceFile
  visible: (ref: ts.Identifier) => Binding | undefined
  /** Local name to the app module and the exported name an import brings in. */
  imports: Map<string, { file: string; name: string }>
}

/** What a name holds, and the module whose names it is written in. */
interface Held {
  node: ts.Node
  mod: Module
}

type Component = ts.FunctionDeclaration | ts.FunctionExpression | ts.ArrowFunction
const isFunction = (n: ts.Node): n is Component => ts.isFunctionDeclaration(n) || ts.isFunctionExpression(n) || ts.isArrowFunction(n)
/** The props that make a shared control aria-disabled, or 'always' when any use can be. */
type Triggers = Set<string> | 'always'
type JsxTag = ts.JsxOpeningElement | ts.JsxSelfClosingElement
const isJsxTag = (n: ts.Node): n is JsxTag => ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)

const hasModifier = (n: ts.Node, kind: ts.SyntaxKind) =>
  ts.canHaveModifiers(n) && (ts.getModifiers(n)?.some((m) => m.kind === kind) ?? false)

/**
 * The scan over one set of files (`read`), with `@/` resolved against `root`. Returns, for a file, every
 * offending class token in it, how many elements in it carry `aria-disabled` (`controls`) and how many are
 * controls as uses of a shared control (`uses`).
 */
function fadeScanner(read: Read, root: string): (file: string) => { offenders: Offender[]; controls: number; uses: number } {
  const modules = new Map<string, Module | undefined>()

  /** The app file an import specifier names; undefined for a package. */
  const resolve = (from: string, specifier: string): string | undefined => {
    const base = specifier.startsWith('@/')
      ? path.join(root, specifier.slice(2))
      : specifier.startsWith('.')
        ? path.resolve(path.dirname(from), specifier)
        : undefined
    if (!base) return undefined
    return [base, `${base}.ts`, `${base}.tsx`, path.join(base, 'index.ts'), path.join(base, 'index.tsx')].find(
      (file) => /\.tsx?$/.test(file) && read(file) !== undefined,
    )
  }

  const load = (file: string): Module | undefined => {
    if (modules.has(file)) return modules.get(file)
    const source = read(file)
    let mod: Module | undefined
    if (source !== undefined) {
      const kind = file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
      const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, kind)
      const imports: Module['imports'] = new Map()
      for (const s of sf.statements) {
        if (!ts.isImportDeclaration(s) || !ts.isStringLiteral(s.moduleSpecifier) || !s.importClause) continue
        const target = resolve(file, s.moduleSpecifier.text)
        if (!target) continue
        const { name, namedBindings } = s.importClause
        if (name) imports.set(name.text, { file: target, name: 'default' })
        if (namedBindings && ts.isNamedImports(namedBindings)) {
          for (const el of namedBindings.elements) imports.set(el.name.text, { file: target, name: (el.propertyName ?? el.name).text })
        }
      }
      mod = { file, sf, visible: bindingResolver(sf), imports }
    }
    modules.set(file, mod)
    return mod
  }

  /** What `name` exported from `mod` holds, through a barrel's re-exports. */
  const exported = (mod: Module, name: string, seen: Set<string>): Held | undefined => {
    if (seen.has(mod.file)) return undefined
    seen.add(mod.file)
    const stars: Module[] = []
    for (const s of mod.sf.statements) {
      if (ts.isVariableStatement(s) && hasModifier(s, ts.SyntaxKind.ExportKeyword)) {
        for (const d of s.declarationList.declarations) {
          if (ts.isIdentifier(d.name) && d.name.text === name && d.initializer) return { node: d.initializer, mod }
        }
      } else if (ts.isFunctionDeclaration(s) && s.body && hasModifier(s, ts.SyntaxKind.ExportKeyword)) {
        const exportedAs = hasModifier(s, ts.SyntaxKind.DefaultKeyword) ? 'default' : s.name?.text
        if (exportedAs === name) return { node: s.body, mod }
      } else if (ts.isExportAssignment(s) && !s.isExportEquals && name === 'default') {
        return { node: s.expression, mod }
      } else if (ts.isExportDeclaration(s)) {
        const from = s.moduleSpecifier && ts.isStringLiteral(s.moduleSpecifier) ? resolve(mod.file, s.moduleSpecifier.text) : undefined
        const target = from ? load(from) : undefined
        if (!s.exportClause) {
          if (target) stars.push(target)
        } else if (ts.isNamedExports(s.exportClause)) {
          const el = s.exportClause.elements.find((e) => e.name.text === name)
          if (!el) continue
          const local = el.propertyName ?? el.name
          if (s.moduleSpecifier) return target ? exported(target, local.text, seen) : undefined
          return ts.isIdentifier(local) ? held(local, mod) : undefined
        }
      }
    }
    for (const star of stars) {
      const found = exported(star, name, seen)
      if (found) return found
    }
    return undefined
  }

  /**
   * What the name at `ref` holds: a const's initializer (for a name destructured from a const, the whole of
   * what that const holds) or a function declaration's body, in this module or in the one it is imported from.
   * A parameter or a destructured prop holds what the caller passes, which no file shows, and it shadows an
   * import of the same name.
   */
  const held = (ref: ts.Identifier, mod: Module): Held | undefined => {
    const binding = mod.visible(ref)
    if (binding) {
      let node = binding.init ?? (ts.isFunctionDeclaration(binding.decl) ? binding.alias : undefined)
      // `const { busy: busyClass } = LOOKS`: a name destructured from a const holds that const's `busy`, or all
      // the const holds when its one property cannot be told apart (a nested pattern, an object built at runtime).
      if (!node && ts.isBindingElement(binding.decl)) {
        const { decl } = binding
        let from: ts.Node = decl
        while (ts.isBindingElement(from) || ts.isObjectBindingPattern(from) || ts.isArrayBindingPattern(from)) from = from.parent
        if (ts.isVariableDeclaration(from) && from.initializer) {
          const key = decl.propertyName ?? decl.name
          const direct = ts.isObjectBindingPattern(decl.parent) && decl.parent.parent === from && !decl.dotDotDotToken
          const picked = direct && (ts.isIdentifier(key) || ts.isStringLiteral(key)) ? member(from.initializer, mod, key.text) : 'whole'
          if (picked !== 'whole') return picked
          node = from.initializer
        }
      }
      return node ? { node, mod } : undefined
    }
    const imported = mod.imports.get(ref.text)
    const from = imported && load(imported.file)
    return from ? exported(from, imported.name, new Set()) : undefined
  }

  const bare = (n: ts.Node): ts.Node =>
    ts.isParenthesizedExpression(n) || ts.isAsExpression(n) || ts.isSatisfiesExpression(n) ? bare(n.expression) : n

  /**
   * What the property `key` of an object holds, when the object is a literal or a name that holds one: the
   * property's value, nothing when the literal has no such key or the name holds nothing this scan can read, or
   * 'whole' when one property cannot be told apart (a spread, a computed key, an object built at runtime).
   */
  const member = (object: ts.Node, mod: Module, key: string): Held | undefined | 'whole' => {
    let target: Held | undefined = { node: bare(object), mod }
    if (ts.isIdentifier(target.node)) {
      target = held(target.node, mod)
      if (!target) return undefined
      target = { node: bare(target.node), mod: target.mod }
    }
    if (!ts.isObjectLiteralExpression(target.node)) return 'whole'
    let unknown = false
    for (const property of target.node.properties) {
      const name = property.name
      if (!name || ts.isComputedPropertyName(name)) unknown = true
      else if (name.text !== key) continue
      else if (ts.isPropertyAssignment(property)) return { node: property.initializer, mod: target.mod }
      else if (ts.isShorthandPropertyAssignment(property)) return { node: property.name, mod: target.mod }
      else unknown = true
    }
    return unknown ? 'whole' : undefined
  }

  /**
   * The class text a className expression can hold: its own chunks, and those the names in it reach. Only what
   * can become the class: never a condition (a ternary's test, the left of `&&`), whose value picks a class
   * without being one, and never another element's classes (JSX inside a callback or a component a name leads to).
   */
  const classChunks = (expr: ts.Node, mod: Module, seen: Set<ts.Node>, out: { text: string; node: ts.Node; mod: Module }[]) => {
    const visit = (n: ts.Node): void => {
      if (ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n) || ts.isJsxFragment(n)) return
      if (ts.isConditionalExpression(n)) {
        visit(n.whenTrue)
        visit(n.whenFalse)
        return
      }
      if (ts.isBinaryExpression(n) && n.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken) {
        visit(n.right)
        return
      }
      // `LOOKS.busy` holds that one property of a class map, not its siblings.
      if (ts.isPropertyAccessExpression(n) && ts.isIdentifier(n.expression)) {
        const picked = member(n.expression, mod, n.name.text)
        if (picked !== 'whole') {
          if (picked && !seen.has(picked.node)) {
            seen.add(picked.node)
            classChunks(picked.node, picked.mod, seen, out)
          }
          return
        }
      }
      if (isChunk(n)) out.push({ text: n.text, node: n, mod })
      else if (ts.isIdentifier(n)) {
        if (isMemberName(n)) return
        const target = held(n, mod)
        if (!target || seen.has(target.node)) return
        seen.add(target.node)
        classChunks(target.node, target.mod, seen, out)
      }
      ts.forEachChild(n, visit)
    }
    visit(expr)
    return out
  }

  /**
   * The component a value is, and its module: the function itself, a declaration held by its body, an alias of
   * one (`const BusyButton = Button`), or the one a wrapper is given (`forwardRef(function Button…)`, `memo(Button)`).
   */
  const componentOf = (node: ts.Node, mod: Module, seen = new Set<ts.Node>()): { fn: Component; mod: Module } | undefined => {
    if (seen.has(node)) return undefined
    seen.add(node)
    if (isFunction(node)) return { fn: node, mod }
    if (ts.isBlock(node) && isFunction(node.parent)) return { fn: node.parent, mod }
    if (ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isSatisfiesExpression(node)) return componentOf(node.expression, mod, seen)
    if (ts.isIdentifier(node)) {
      const target = held(node, mod)
      return target && componentOf(target.node, target.mod, seen)
    }
    if (ts.isCallExpression(node)) {
      for (const arg of node.arguments) {
        const found = componentOf(arg, mod, seen)
        if (found) return found
      }
    }
    return undefined
  }

  const attributeOf = (tag: JsxTag, name: string) =>
    tag.attributes.properties.find((a): a is ts.JsxAttribute => ts.isJsxAttribute(a) && a.name.getText() === name)

  /** The prop of `fn` a name stands for: its name, '...' for its rest props, undefined when it is no prop of `fn`. */
  const propNamed = (ref: ts.Identifier, fn: Component, mod: Module): string | undefined => {
    const decl = mod.visible(ref)?.decl
    if (!decl || !ts.isBindingElement(decl) || decl.parent !== fn.parameters[0]?.name) return undefined
    if (decl.dotDotDotToken) return '...'
    const name = decl.propertyName ?? decl.name
    return ts.isIdentifier(name) || ts.isStringLiteral(name) ? name.text : undefined
  }

  /** Every identifier an expression reads, through the same-file consts it names; never a member's or a key's name. */
  const reads = (expr: ts.Node, mod: Module, each: (ref: ts.Identifier) => void, seen = new Set<Binding>()): void => {
    const visit = (n: ts.Node): void => {
      if (ts.isIdentifier(n)) {
        if (isMemberName(n)) return
        each(n)
        const binding = mod.visible(n)
        if (binding?.init && !seen.has(binding)) {
          seen.add(binding)
          reads(binding.init, mod, each, seen)
        }
      }
      ts.forEachChild(n, visit)
    }
    visit(expr)
  }

  /** `false`, `null`, `undefined`, `0` or `''`: a value that never makes a control aria-disabled. */
  const isFalsy = (n: ts.Node): boolean =>
    n.kind === ts.SyntaxKind.FalseKeyword ||
    n.kind === ts.SyntaxKind.NullKeyword ||
    (ts.isIdentifier(n) && n.text === 'undefined') ||
    (ts.isNumericLiteral(n) && Number(n.text) === 0) ||
    (ts.isStringLiteralLike(n) && n.text === '')

  /**
   * The props of `fn` one of which a use must pass for `expr` to be truthy: an expression built from its props
   * (each with no default, or a falsy one), falsy literals, `||`, `&&` and `??` is falsy when none is passed
   * (`loading || undefined`). Any other shape can be truthy at a use that passes nothing (a negation, a truthy
   * default, a call, state), so it is 'always'.
   */
  const builtFrom = (expr: ts.Node | undefined, fn: Component, mod: Module, seen = new Set<Binding>()): Triggers => {
    if (!expr) return 'always'
    if (ts.isParenthesizedExpression(expr)) return builtFrom(expr.expression, fn, mod, seen)
    if (isFalsy(expr)) return new Set()
    if (ts.isBinaryExpression(expr)) {
      const op = expr.operatorToken.kind
      if (op !== ts.SyntaxKind.BarBarToken && op !== ts.SyntaxKind.AmpersandAmpersandToken && op !== ts.SyntaxKind.QuestionQuestionToken) return 'always'
      const left = builtFrom(expr.left, fn, mod, seen)
      const right = builtFrom(expr.right, fn, mod, seen)
      return left === 'always' || right === 'always' ? 'always' : new Set([...left, ...right])
    }
    if (ts.isIdentifier(expr)) {
      const binding = mod.visible(expr)
      const prop = propNamed(expr, fn, mod)
      if (binding && prop && prop !== '...' && ts.isBindingElement(binding.decl)) {
        const fallback = binding.decl.initializer
        return !fallback || isFalsy(fallback) ? new Set([prop]) : 'always'
      }
      if (binding?.init && !seen.has(binding)) {
        seen.add(binding)
        return builtFrom(binding.init, fn, mod, seen)
      }
    }
    return 'always'
  }

  /**
   * What makes this element aria-disabled: its own `aria-disabled`, or the trigger props it passes to a shared
   * control (null where the control needs none). Undefined when the element is no control.
   */
  const fedBy = (tag: JsxTag, mod: Module): (ts.Node | undefined)[] | null | undefined => {
    const own = attributeOf(tag, 'aria-disabled')
    if (own) return [own.initializer]
    if (!ts.isIdentifier(tag.tagName) || !/^[A-Z]/.test(tag.tagName.text)) return undefined
    const component = componentOf(tag.tagName, mod)
    const triggers = component && sharedControl(component.fn, component.mod)
    if (!triggers) return undefined
    if (triggers === 'always') return null
    const passed = [...triggers].map((prop) => attributeOf(tag, prop)).filter((a) => a !== undefined)
    return passed.length ? passed.map((a) => a.initializer) : undefined
  }

  const shared = new Map<Component, Triggers | undefined>()
  /** The triggers of a component that renders a control and hands it the caller's className; undefined for any other. */
  const sharedControl = (fn: Component, mod: Module): Triggers | undefined => {
    if (shared.has(fn)) return shared.get(fn)
    shared.set(fn, undefined) // components that render each other in a cycle are not followed round it
    const pattern = fn.parameters[0]?.name
    let triggers: Triggers | undefined
    const takesCallersClassName = (tag: JsxTag): boolean => {
      let takes = false
      const className = attributeOf(tag, 'className')?.initializer
      if (className) reads(className, mod, (ref) => (takes ||= propNamed(ref, fn, mod) === 'className'))
      // Rest props carry className unless the component took it out of them, or a className written after the
      // spread overrides it.
      const keepsClassName = pattern && ts.isObjectBindingPattern(pattern) && pattern.elements.some((e) => (e.propertyName ?? e.name).getText() === 'className')
      const attributes = tag.attributes.properties
      attributes.forEach((a, i) => {
        if (!ts.isJsxSpreadAttribute(a) || !ts.isIdentifier(a.expression) || propNamed(a.expression, fn, mod) !== '...' || keepsClassName) return
        const overridden = attributes.slice(i + 1).some((later) => ts.isJsxAttribute(later) && later.name.getText() === 'className')
        if (!overridden) takes = true
      })
      return takes
    }
    const visit = (n: ts.Node): void => {
      if (isJsxTag(n) && triggers !== 'always') {
        const feeding = fedBy(n, mod)
        if (feeding !== undefined && takesCallersClassName(n)) {
          for (const expr of feeding ?? [undefined]) {
            const from = feeding === null ? 'always' : builtFrom(expr && ts.isJsxExpression(expr) ? expr.expression : undefined, fn, mod)
            if (from === 'always') triggers = 'always'
            else if (triggers !== 'always') triggers = new Set([...(triggers ?? []), ...from])
          }
        }
      }
      ts.forEachChild(n, visit)
    }
    if (pattern && ts.isObjectBindingPattern(pattern) && fn.body) visit(fn.body)
    shared.set(fn, triggers)
    return triggers
  }

  return (file) => {
    const mod = load(file)
    const offenders: Offender[] = []
    let controls = 0
    let uses = 0
    if (!mod) return { offenders, controls, uses }
    const { sf } = mod
    const lineOf = (n: ts.Node) => sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1

    const visit = (n: ts.Node): void => {
      if (isChunk(n)) {
        for (const token of tokensOf(n.text)) {
          const { variants, utility } = parseToken(token)
          if (fadesElement(utility) && variants.some(ownAriaDisabled)) offenders.push({ line: lineOf(n), token, clause: 'variant' })
        }
      }
      if (isJsxTag(n) && fedBy(n, mod) !== undefined) {
        if (attributeOf(n, 'aria-disabled')) controls += 1
        else uses += 1
        const className = attributeOf(n, 'className')?.initializer
        for (const chunk of className ? classChunks(className, mod, new Set(), []) : []) {
          for (const token of tokensOf(chunk.text)) {
            const { variants, utility } = parseToken(token)
            // Clause 1 already reports a fade behind the element's own aria-disabled variant, where it is written.
            if (!fadesElement(utility) || variants.includes('disabled') || variants.some(ownAriaDisabled)) continue
            const at = chunk.mod.sf.getLineAndCharacterOfPosition(chunk.node.getStart(chunk.mod.sf)).line + 1
            const elsewhere = chunk.mod !== mod || chunk.node.pos < n.pos || chunk.node.end > n.end
            const writtenAt = elsewhere ? `${path.relative(root, chunk.mod.file)}:${at}` : undefined
            offenders.push({ line: lineOf(n), token, clause: 'element', writtenAt })
          }
        }
      }
      ts.forEachChild(n, visit)
    }
    visit(sf)
    return { offenders, controls, uses }
  }
}

/** The offenders of `file` among in-memory `files`, keyed by path under a root of `/app`. */
const tokensAmong = (files: Record<string, string>, file: string) =>
  fadeScanner((f) => files[f], '/app')(file).offenders.map((o) => `${o.clause} ${o.token}`)
const tokensIn = (source: string) => tokensAmong({ '/app/Fixture.tsx': source }, '/app/Fixture.tsx')

describe('no element opacity on an aria-disabled control (rule-12 gate)', () => {
  it('sees an opacity behind the element’s own aria-disabled variant wherever a class list is written, and nothing else', () => {
    expect(
      tokensIn(`
        const CHIP = ['inline-flex rounded-full', 'focus-visible:shadow-ring-brand aria-disabled:opacity-50'].join(' ')
        export const fieldUnavailable = cx('aria-disabled:bg-background-light', 'dark:aria-disabled:hover:!opacity-[.6]')
        const arbitrary = \`rounded \${wide ? 'w-full' : ''} aria-[disabled=true]:opacity-40 [&[aria-disabled=true]]:opacity-30\`
        const property = 'aria-disabled:[opacity:0.5]'
        export const Row = () => <button className="text-sm aria-disabled:opacity-50" />
      `),
    ).toEqual([
      'variant aria-disabled:opacity-50',
      'variant dark:aria-disabled:hover:!opacity-[.6]',
      'variant aria-[disabled=true]:opacity-40',
      'variant [&[aria-disabled=true]]:opacity-30',
      'variant aria-disabled:[opacity:0.5]',
      'variant aria-disabled:opacity-50',
    ])
    expect(
      tokensIn(`
        // aria-disabled:opacity-50 would fade the ring too.
        const LOOK = cx(
          'aria-disabled:cursor-not-allowed aria-disabled:text-brand-strong/50 aria-disabled:border-brand-border/50',
          'aria-disabled:bg-opacity-50 aria-disabled:transition-opacity aria-disabled:opacity-100 disabled:opacity-50 opacity-70',
        )
        export const Row = () => (
          <button className="group aria-disabled:text-error-light/50">
            <span className="group-aria-disabled:opacity-50 peer-aria-disabled:opacity-50" />
          </button>
        )
      `),
    ).toEqual([])
  })

  it('sees any other opacity class on an element that carries aria-disabled, through same-file names, and nothing else', () => {
    // AlertBell's shape before this gate: the busy flag picks the fade in JS.
    expect(
      tokensIn(`
        export const Bell = ({ pending, checking }) => (
          <button
            disabled={checking}
            aria-disabled={pending || undefined}
            className={cx('h-7 w-7 rounded-lg', pending || checking ? 'cursor-progress opacity-60' : '', className)}
          />
        )
      `),
    ).toEqual(['element opacity-60'])
    expect(
      tokensIn(`
        const CHIP = ['rounded-full', 'hover:opacity-80'].join(' ')
        const LOOKS = { busy: 'opacity-35', idle: 'px-2' }
        const { busy: busyLook } = LOOKS
        const dim = (busy) => (busy ? 'opacity-50' : '')
        function look(busy) {
          return cx(CHIP, dim(busy))
        }
        export const Chip = ({ busy }) => {
          const faded = \`\${busy ? 'opacity-40' : ''} px-3\`
          return (
            <>
              <button aria-disabled={busy || undefined} className={look(busy)} />
              <Button aria-disabled={busy || undefined} className={faded} />
              <a aria-disabled={busy || undefined} className={busyLook} />
              <b aria-disabled={busy || undefined} className={LOOKS.busy} />
              <i aria-disabled={busy || undefined} className={LOOKS[kind]} />
            </>
          )
        }
      `),
    ).toEqual(['element hover:opacity-80', 'element opacity-50', 'element opacity-40', 'element opacity-35', 'element opacity-35', 'element opacity-35'])
    expect(
      tokensIn(`
        const dim = 'opacity-50'
        export const Row = ({ busy, dim }) => (
          <li className="opacity-70">
            <button disabled={busy} className="opacity-60" />
            <button aria-disabled={busy || undefined} className={cx('group disabled:opacity-60 disabled:hover:opacity-60', dim, styles.dim)}>
              <span className="opacity-50 group-aria-disabled:opacity-50" />
            </button>
          </li>
        )
        // One property of a class map is not its siblings.
        const SHADES = { calm: 'text-sm', decorative: 'opacity-50' }
        const { calm } = SHADES
        export const Calm = ({ busy }) => <button aria-disabled={busy || undefined} className={cx(calm, SHADES.calm, SHADES.missing)} />
        // A condition picks a class without being one, and another element's classes are not this control's.
        const Icon = () => <svg className="opacity-60" />
        export const Save = () => {
          const mutation = useMutation({ onError: () => toast(<div className="opacity-90">Failed</div>) })
          const pending = mutation.isPending
          return (
            <button
              aria-disabled={pending || undefined}
              className={cx(pending ? 'cursor-progress' : '', Icon ? 'pl-9' : 'pl-3', pending && 'px-2', look({ opacity: 'w-full' }))}
            />
          )
        }
      `),
    ).toEqual([])
  })

  it('follows a class list across modules: an import, a barrel’s re-exports and a default export, and nothing a package or a parameter holds', () => {
    const files = {
      '/app/components/ui/Input.tsx': `
        const FIELD = 'w-full rounded-lg disabled:opacity-60'
        export function inputClasses() {
          return cx(FIELD)
        }
        export const fieldUnavailableClass = cx('aria-disabled:cursor-not-allowed', 'opacity-60')
      `,
      '/app/components/ui/Look.ts': `
        const dim = 'hover:opacity-80'
        export { dim as busyLook }
        export default 'opacity-30'
      `,
      '/app/components/ui/index.ts': `
        export { fieldUnavailableClass as unavailable, inputClasses } from './Input'
        export * from './Look'
      `,
      '/app/features/Row.tsx': `
        import { clsx } from 'clsx'
        import { unavailable, inputClasses, busyLook } from '@/components/ui'
        import fade from '../components/ui/Look'
        export const Row = ({ busy }) => (
          <>
            <select aria-disabled={busy || undefined} className={clsx(inputClasses(), unavailable)} />
            <button aria-disabled={busy || undefined} className={busy ? busyLook : fade} />
          </>
        )
      `,
      '/app/features/Quiet.tsx': `
        import { clsx } from 'clsx'
        import { unavailable, busyLook } from '@/components/ui'
        import { missing } from '@/components/ui/Nowhere'
        export const Quiet = ({ busy, unavailable: passed }) => (
          <>
            <select className={clsx(unavailable, busyLook)} />
            <button aria-disabled={busy || undefined} className={clsx(passed, missing, clsx)} />
          </>
        )
        export const Shadowed = ({ busy, busyLook }) => <button aria-disabled={busy || undefined} className={busyLook} />
      `,
    }
    // Each is reported at the control that takes it: its own module holds no aria-disabled variant to report.
    expect(tokensAmong(files, '/app/features/Row.tsx')).toEqual(['element opacity-60', 'element hover:opacity-80', 'element opacity-30'])
    expect(tokensAmong(files, '/app/components/ui/Input.tsx')).toEqual([])
    expect(tokensAmong(files, '/app/features/Quiet.tsx')).toEqual([])
  })

  it('holds a use of a shared control to the rule: by the props that can make it aria-disabled, through a wrapper or an alias, and nothing else', () => {
    const files = {
      '/app/components/ui/Button.tsx': `
        export const Button = forwardRef(function Button({ loading = false, className, children, ...rest }, ref) {
          return (
            <button ref={ref} aria-disabled={loading || undefined} className={cx('rounded-lg disabled:opacity-50', className)} {...rest}>
              {children}
            </button>
          )
        })
        export function Chip({ className, children }) {
          return <span className={className}>{children}</span>
        }
        export function Fixed({ loading, label }) {
          return <button aria-disabled={loading || undefined} className="rounded-lg">{label}</button>
        }
        export function DefaultBusy({ busy = true, className }) {
          return <button aria-disabled={busy || undefined} className={className} />
        }
        export function Ready({ ready, className }) {
          return <button aria-disabled={!ready} className={className} />
        }
        export function Never({ className }) {
          return <button aria-disabled={false} className={className} />
        }
        export function KeyOnly({ busy, className }) {
          return (
            <div className={className}>
              <button aria-disabled={busy || undefined} className={variants({ className: 'w-full' })} />
            </div>
          )
        }
        export function Pinned({ busy, ...rest }) {
          return <button {...rest} aria-disabled={busy || undefined} className="rounded-lg" />
        }
      `,
      '/app/hooks/Retry.tsx': `
        import { Button } from '@/components/ui/Button'
        export function RetryButton({ failures, ...rest }) {
          const busy = failures.some((f) => f.busy)
          return <Button {...rest} loading={busy}>Retry</Button>
        }
      `,
      '/app/features/Bell.tsx': `
        export function Bell({ alerts, ticker, className }) {
          const pending = alerts.isPending(ticker)
          const look = cx('h-7 w-7', className)
          return <button aria-disabled={pending || undefined} className={look} />
        }
      `,
      '/app/features/Page.tsx': `
        import { Button as DsButton, Chip, DefaultBusy, Fixed, KeyOnly, Never, Pinned, Ready } from '@/components/ui/Button'
        import { RetryButton } from '@/hooks/Retry'
        import { Bell } from './Bell'
        import Link from 'next/link'
        const FADED = 'hover:opacity-80'
        const BusyButton = DsButton
        const MemoButton = memo(BusyButton)
        export const Page = ({ busy, alerts }) => (
          <>
            <DsButton loading={busy} className={busy ? 'opacity-50' : ''}>Save</DsButton>
            <RetryButton failures={[]} className={FADED} />
            <Bell alerts={alerts} ticker="AAPL" className="opacity-40" />
            <DsButton loading className="opacity-30">Sending</DsButton>
            <BusyButton loading={busy} className="opacity-20">Aliased</BusyButton>
            <MemoButton loading={busy} className="opacity-10">Wrapped</MemoButton>
            <MemoButton className="opacity-10">Never loading</MemoButton>
            <DefaultBusy className="opacity-25" />
            <Ready className="opacity-15" />
            <Never className="opacity-70" />
            <KeyOnly busy={busy} className="opacity-70" />
            <Pinned busy={busy} className="opacity-70" />
            <DsButton loading={busy} className="opacity-100">Full strength</DsButton>
            <DsButton className="opacity-0 group-hover:opacity-100">Copy</DsButton>
            <DsButton loading={busy} className="w-full disabled:opacity-60">Send</DsButton>
            <Chip className="opacity-70">New</Chip>
            <Fixed loading={busy} label="Go" className="opacity-70" />
            <Link href="/" className="opacity-70">Home</Link>
            <img loading="lazy" className="opacity-0" />
          </>
        )
      `,
    }
    expect(tokensAmong(files, '/app/features/Page.tsx')).toEqual([
      'element opacity-50',
      'element hover:opacity-80',
      'element opacity-40',
      'element opacity-30',
      'element opacity-20',
      'element opacity-10',
      'element opacity-25',
      'element opacity-15',
    ])
    for (const file of ['/app/components/ui/Button.tsx', '/app/hooks/Retry.tsx', '/app/features/Bell.tsx']) {
      expect(tokensAmong(files, file)).toEqual([])
    }
  })

  it('no class fades an aria-disabled control as a whole', () => {
    const offenders: string[] = []
    let controls = 0
    let uses = 0
    const scan = fadeScanner((file) => (existsSync(file) && statSync(file).isFile() ? readFileSync(file, 'utf8') : undefined), frontendRoot)
    for (const file of ROOTS.flatMap((root) => walk(path.join(frontendRoot, root), []))) {
      const found = scan(file)
      controls += found.controls
      uses += found.uses
      for (const o of found.offenders) {
        offenders.push(`${path.relative(frontendRoot, file)}:${o.line} ${o.token}${o.writtenAt ? ` (written at ${o.writtenAt})` : ''}`)
      }
    }
    // The scan reached the app: its aria-disabled elements and its `<Button loading>` uses are in what it read.
    expect(controls).toBeGreaterThan(0)
    expect(uses).toBeGreaterThan(0)
    expect(
      offenders,
      'An element opacity on an aria-disabled control fades its focus ring: the control stays focusable. Fade what ' +
        'it draws in instead (label ink and hairline at /50 on the tokens it already uses, both themes), or a child ' +
        '(`group-aria-disabled:opacity-50`); a natively disabled state keeps `disabled:opacity-*`. ' +
        'DESIGN_SYSTEM §4, lessons/frontend-busy-controls-stay-focusable.md (e).',
    ).toEqual([])
  })
})
