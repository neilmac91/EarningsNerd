import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { bindingResolver } from './astBindings'

/**
 * No dead preference ships (DSW-01). Every alert preference the settings form renders or saves, and every
 * value it offers for one, must be read by the code that sends alerts: the three job services below, read as
 * text (the planLimitsLockstep pattern) and split into their top-level `def` and `class` blocks (decorators
 * included). A block counts only when the alert jobs reach it: the entry points JOB_ENTRIES and every block one
 * of them names, followed through the three files. A field counts as read when such a block reads
 * `prefs.<field>` (an assignment does not count); an option value counts when such a block has it as a string
 * literal. So the preferences write path (apply_preference_update and the defaults and coercion only it
 * reaches), a helper only the write path calls (a `_normalize_digest` sanitizer), a GET serializer and a
 * module constant cannot stand in for a job honouring the field. Comments and docstrings are ignored.
 *
 * The form's fields are read off the prefs value (a binding named prefs, in any scope) wherever the form reads it:
 * a member in any attribute, child or expression of any element or component (`checked={prefs.digest === 'weekly'}`,
 * `selected={prefs.x}`, `{prefs.x ? … : …}`, `disabled={!prefs.x}`), written `?.`, `!` or bracketed with a literal key,
 * and a key taken out of it at any depth (a nested pattern, an array's element). The value is followed through the
 * form's own file, a name to the declaration it binds to (astBindings), to: a const that holds it, or one that may (either
 * side of `??`, `||` or `&&`, either branch of a condition) or holds a copy of it (an object that spreads it in,
 * `Object.assign`, `structuredClone`, useMemo's value); a key named prefs taken out of any object; a same-file component's prop
 * it is handed under any name or spread into (`<Rows source={prefs} />`, `<Rows {...prefs} />`, read as `{ source }`,
 * `props.source`, a rest, or each key taken out of the spread); a same-file function's parameter it is handed at a
 * call; what a same-file hook returns; and a context the file provides it through (`<C.Provider value={prefs}>` or
 * React 19's `<C value={prefs}>`, read with `useContext(C)` or `use(C)`). A component or a function is any the file
 * declares: a function declaration, an arrow or a function expression, one a call wraps (useCallback, useMemo's
 * factory, memo, forwardRef or any wrapper, nested), an object's method or arrow property (`actions.persist`,
 * `<Parts.Row>`), one a same-file hook returns, and one handed on as a prop or an argument. The fields a save writes
 * are read the same way: a call of `save`, any `.mutate` or `.mutateAsync`, the function a mutation runs (its
 * `mutationFn`) called directly, or any such function that calls one, its update written in place, held in a const or
 * spread from one; and each name handed to `setBool` or any such function that saves `{ [name]: … }` keyed by its own
 * parameter. Out of reach, each planted as a gap the self-check asserts unread: a value or a function from another
 * module, a class component, the value kept in React state or a ref (`useState`, `useRef`), a copy made another way (a
 * JSON round trip), an array's rest, a field named by a computed key or enumerated (`prefs[key]`,
 * `Object.entries(prefs)`), a function called through call, apply or bind or held in an array, and a save sent by hand
 * (`fetch`). A field the API fills from the account's entitlements
 * (`_prefs_response` in backend/app/routers/users.py assigns it from `ent.`, and the update model does not take it) is
 * gating the user cannot set, not a preference, so a read of it there is not held to the jobs; read directly as a
 * control's state (`checked={prefs.x}`), as main read it, any field is.
 *
 * The values the form offers are read where they are written, in each form a choice takes: any element's
 * `value="…"` or `value={'…'}` (an <option>, a radio input, a custom item; `value={prefs.x}` is the control's
 * state, a field, and on an <option>, whose value is what it offers, a value the scan cannot read), each
 * entry's `value` in an `options` prop (SegmentedControl, the design system's single choice, or any select
 * wrapper), and a literal a save or mutate call writes into a field (`save({ digest: 'weekly' })`, each
 * branch of a condition over literals). A value or an `options` entry may also be the element,
 * or one of its fields, of the array a `.map` takes (`DIGESTS.map((d) => <option value={d}>)`,
 * `CHOICES.map((c) => ({ value: c.value }))`), the array written in place or as a const in the form. A `value`
 * or an `options` written any other way fails the scan, so a choice it cannot read never ships unread.
 *
 * Limits: a block is reached by name (a same-named function in another module is not told apart, and a call
 * made through a variable or getattr is not followed, which only narrows), and a reached block counts as a
 * whole, so a read whose value the job then drops still counts; review reads what the job does with it.
 *
 * The digest frequency select failed this: users.py stored `digest` and no job read it, so a "Weekly" choice
 * still mailed daily. It comes back only with a reader here.
 */
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const FORM = 'features/settings/components/NotificationPreferencesForm.tsx'
const CONSUMERS = [
  'backend/app/services/notification_service.py',
  'backend/app/services/filing_scan_service.py',
  'backend/app/services/notification_delivery_service.py',
]

/** Where the alert jobs start: the hourly scan, the daily digest, the delivery drain, and the per-filing decision they share. */
const JOB_ENTRIES = ['run_filing_scan', 'run_daily_digest', 'drain', 'evaluate_delivery']

/**
 * A Python source's top-level `def`/`class` blocks by name (decorators included), with `#` comments and
 * triple-quoted strings dropped. Module-level statements go: a constant there is a value list, not a job
 * reading it. (A `#` or triple quote inside a string literal is rare here and only narrows.)
 */
function blocks(python: string): Map<string, string> {
  const lines = python
    .replace(/"""[\s\S]*?"""|'''[\s\S]*?'''/g, '')
    .split('\n')
    .map((line) => line.replace(/(^|\s)#.*$/, ''))
  const out = new Map<string, string[]>()
  let current: string[] | null = null
  let decorators: string[] = []
  for (const line of lines) {
    // A column-0 closing bracket (`) -> Tuple[bool, bool]:`) still belongs to the signature above it.
    if (/^[^\s)\]}]/.test(line)) {
      if (line.startsWith('@')) {
        decorators.push(line)
        continue
      }
      const block = /^(?:async\s+)?def\s+(\w+)|^class\s+(\w+)/.exec(line)
      current = null
      if (block) {
        const name = block[1] ?? block[2]
        current = out.get(name) ?? []
        out.set(name, current)
        current.push(...decorators)
      }
      decorators = []
    }
    if (current) current.push(line)
  }
  return new Map([...out].map(([name, code]) => [name, code.join('\n')]))
}

/** The code the alert jobs run: every block named from JOB_ENTRIES on, through the given sources. */
function jobCode(sources: string[], entries: string[] = JOB_ENTRIES): string {
  const all = new Map<string, string>()
  for (const python of sources) for (const [name, code] of blocks(python)) all.set(name, `${all.get(name) ?? ''}\n${code}`)
  const reached = new Set<string>()
  const queue = entries.filter((name) => all.has(name))
  while (queue.length) {
    const name = queue.pop()!
    if (reached.has(name)) continue
    reached.add(name)
    for (const other of all.keys()) {
      if (!reached.has(other) && new RegExp(`\\b${other}\\b`).test(all.get(name)!)) queue.push(other)
    }
  }
  return [...reached].map((name) => all.get(name)).join('\n')
}

/** The form's preferences: the fields it renders or saves, the option values it offers, and the option values it writes in
    a form the scan cannot read. `derived` names the fields the API fills from entitlements, set aside from the reads. */
function formPreferences(file: string, text: string, derived: ReadonlySet<string> = new Set()) {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const line = (node: ts.Node) => source.getLineAndCharacterOfPosition(node.getStart()).line + 1
  const fields = new Map<string, number>()
  const options = new Map<string, number>()
  const unreadable: string[] = []

  const unwrap = (node: ts.Expression): ts.Expression =>
    ts.isAsExpression(node) || ts.isSatisfiesExpression(node) || ts.isParenthesizedExpression(node) ? unwrap(node.expression) : node
  const literal = (node: ts.Expression | undefined): string | null => {
    if (!node) return null
    const inner = unwrap(node)
    return ts.isStringLiteral(inner) || ts.isNoSubstitutionTemplateLiteral(inner) ? inner.text : null
  }
  /** The array literal an expression names: written in place, or a const in this file. */
  const arrayOf = (node: ts.Expression): ts.ArrayLiteralExpression | null => {
    const inner = unwrap(node)
    if (ts.isArrayLiteralExpression(inner)) return inner
    if (!ts.isIdentifier(inner)) return null
    let found: ts.ArrayLiteralExpression | null = null
    const find = (n: ts.Node): void => {
      if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === inner.text && n.initializer) {
        const init = unwrap(n.initializer)
        if (ts.isArrayLiteralExpression(init)) found = init
      }
      ts.forEachChild(n, find)
    }
    find(source)
    return found
  }
  /** The values a `value={…}` takes: a literal, or the elements (or one field of each) of the array a `.map` callback walks. */
  const optionValues = (expression: ts.Expression): string[] | null => {
    const direct = literal(expression)
    if (direct !== null) return [direct]
    const field = ts.isPropertyAccessExpression(expression) ? expression.name.text : null
    const root = ts.isPropertyAccessExpression(expression) ? expression.expression : expression
    if (!ts.isIdentifier(root)) return null
    for (let node: ts.Node | undefined = expression.parent; node; node = node.parent) {
      if (!(ts.isArrowFunction(node) || ts.isFunctionExpression(node))) continue
      const [element] = node.parameters
      if (!element || !ts.isIdentifier(element.name) || element.name.text !== root.text) continue
      const call = node.parent
      if (!ts.isCallExpression(call) || call.arguments[0] !== node || !ts.isPropertyAccessExpression(call.expression)
        || call.expression.name.text !== 'map') return null
      const array = arrayOf(call.expression.expression)
      if (!array) return null
      const values = array.elements.map((item) => {
        if (!field) return literal(item as ts.Expression)
        const object = unwrap(item as ts.Expression)
        if (!ts.isObjectLiteralExpression(object)) return null
        const prop = object.properties.find(
          (p): p is ts.PropertyAssignment => ts.isPropertyAssignment(p) && !!p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) && p.name.text === field,
        )
        return literal(prop?.initializer)
      })
      return values.every((value): value is string => value !== null) ? values : null
    }
    return null
  }

  /** The values an `options` prop offers: each entry's `value`, the array written in place or a const in this file, or a
      `.map` whose callback returns `{ value: … }` over one. */
  const optionsValues = (expression: ts.Expression): string[] | null => {
    const valueOf = (object: ts.Expression) => {
      const inner = unwrap(object)
      if (!ts.isObjectLiteralExpression(inner)) return undefined
      return inner.properties.find(
        (p): p is ts.PropertyAssignment => ts.isPropertyAssignment(p) && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) && p.name.text === 'value',
      )?.initializer
    }
    const array = arrayOf(expression)
    if (array) {
      const values = array.elements.map((item) => literal(valueOf(item as ts.Expression)))
      return values.every((value): value is string => value !== null) ? values : null
    }
    const call = unwrap(expression)
    const callback = ts.isCallExpression(call) && ts.isPropertyAccessExpression(call.expression) && call.expression.name.text === 'map' ? call.arguments[0] : undefined
    if (!callback || !(ts.isArrowFunction(callback) || ts.isFunctionExpression(callback))) return null
    const body = ts.isBlock(callback.body)
      ? callback.body.statements.find((statement): statement is ts.ReturnStatement => ts.isReturnStatement(statement))?.expression
      : callback.body
    const value = body && valueOf(body)
    return value ? optionValues(value) : null
  }
  /** The string literals an expression can be: a literal, each branch of a condition, each side of `||` or `??`. */
  const literalsOf = (expression: ts.Expression): string[] => {
    const inner = unwrap(expression)
    const direct = literal(inner)
    if (direct !== null) return [direct]
    if (ts.isConditionalExpression(inner)) return [...literalsOf(inner.whenTrue), ...literalsOf(inner.whenFalse)]
    const op = ts.isBinaryExpression(inner) ? inner.operatorToken.kind : undefined
    if (ts.isBinaryExpression(inner) && (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken)) return [...literalsOf(inner.left), ...literalsOf(inner.right)]
    return []
  }

  // ── What the form hands where: its functions and the prefs value, followed through the file ─────────────────────────
  // A name is the declaration an identifier binds to in the file (astBindings, so two components' `props` stay apart; an
  // unbound name, an import or a global, is its text), or a member path from one (`actions.persist`, `props.source`). A
  // function is reached by the name its call or its tag spells, and each of its parameters takes what every call and tag
  // in the file hands it there. Run to a fixed point.
  const resolve = bindingResolver(source)
  const ids = new Map<ts.Node, string>()
  const keyOf = (id: ts.Identifier): string => {
    const decl = resolve(id)?.decl
    if (!decl) return id.text
    let key = ids.get(decl)
    if (!key) ids.set(decl, (key = `${id.text}#${ids.size}`))
    return key
  }
  const bare = (node: ts.Expression): ts.Expression => {
    let inner = node
    while (ts.isParenthesizedExpression(inner) || ts.isAsExpression(inner) || ts.isSatisfiesExpression(inner) ||
      ts.isNonNullExpression(inner) || ts.isTypeAssertionExpression(inner)) inner = inner.expression
    return inner
  }
  const nameOf = (node: ts.Expression): string | undefined => {
    const inner = bare(node)
    if (ts.isIdentifier(inner)) return keyOf(inner)
    const key = ts.isPropertyAccessExpression(inner) ? inner.name.text
      : ts.isElementAccessExpression(inner) && ts.isStringLiteralLike(inner.argumentExpression) ? inner.argumentExpression.text : undefined
    if (key === undefined) return undefined
    const head = nameOf((inner as ts.PropertyAccessExpression | ts.ElementAccessExpression).expression)
    return head === undefined ? undefined : `${head}.${key}`
  }
  const LOGICAL = new Set([ts.SyntaxKind.QuestionQuestionToken, ts.SyntaxKind.BarBarToken, ts.SyntaxKind.AmpersandAmpersandToken])
  /** A property's or a key's own name, as written. */
  const propertyKey = (name: ts.Node | undefined): string | undefined =>
    name && (ts.isIdentifier(name) || ts.isStringLiteral(name) || ts.isNumericLiteral(name)) ? name.text : undefined
  type Fn = ts.SignatureDeclaration
  const consts = new Map<string, ts.Expression>()
  const functions = new Map<string, Set<Fn>>()
  /** A name and every declaration in the file that binds it (the seeds are names: `prefs`, `save`, `setBool`). */
  const seeds = (...names: string[]): Set<string> => {
    const out = new Set(names)
    const walk = (node: ts.Node): void => {
      if (ts.isIdentifier(node) && names.includes(node.text)) out.add(keyOf(node))
      ts.forEachChild(node, walk)
    }
    walk(source)
    return out
  }
  const holders = seeds('prefs')
  const contexts = new Set<string>()
  const reads = new Map<string, number>()
  let grew = true
  const addFunction = (name: string, fn: Fn) => {
    const known = functions.get(name) ?? new Set<Fn>()
    if (known.has(fn)) return
    functions.set(name, known.add(fn))
    grew = true
  }
  const addHolder = (name: string) => {
    if (holders.has(name)) return
    holders.add(name)
    grew = true
  }
  const read = (field: string, at: ts.Node) => {
    if (!reads.has(field)) reads.set(field, line(at))
  }
  const named = (name: string | undefined): Fn[] => (name === undefined ? [] : [...(functions.get(name) ?? [])])

  /** What a function hands back: its concise body, or each `return` of its own (a nested function's are its own). */
  const returnsOf = (fn: Fn): ts.Expression[] => {
    if (ts.isArrowFunction(fn) && !ts.isBlock(fn.body)) return [fn.body]
    const body = (fn as ts.FunctionLikeDeclarationBase).body
    const out: ts.Expression[] = []
    const walk = (node: ts.Node): void => {
      if (node !== body && ts.isFunctionLike(node)) return
      if (ts.isReturnStatement(node) && node.expression) out.push(node.expression)
      ts.forEachChild(node, walk)
    }
    if (body) walk(body)
    return out
  }
  /** The functions a value is: an arrow or a function expression; a named one; the one a call wraps as its first argument
      (useCallback, memo, forwardRef or any wrapper, nested), useMemo's factory's result; what a same-file hook returns. */
  const functionsIn = (value: ts.Expression | undefined, depth = 0): Fn[] => {
    if (!value || depth > 8) return []
    const inner = bare(value)
    if (ts.isArrowFunction(inner) || ts.isFunctionExpression(inner)) return [inner]
    const name = nameOf(inner)
    if (name !== undefined) return named(name)
    if (!ts.isCallExpression(inner)) return []
    if (/(?:^|\.)useMemo$/.test(nameOf(inner.expression) ?? '')) {
      return functionsIn(inner.arguments[0], depth + 1).flatMap((factory) => returnsOf(factory).flatMap((value) => functionsIn(value, depth + 1)))
    }
    const wrapped = functionsIn(inner.arguments[0], depth + 1)
    if (wrapped.length) return wrapped
    return named(nameOf(inner.expression)).flatMap((hook) => returnsOf(hook).flatMap((value) => functionsIn(value, depth + 1)))
  }
  /** The object literals a value is: written in place, held in a const, or what a same-file hook returns. */
  const objectsIn = (value: ts.Expression | undefined, depth = 0): ts.ObjectLiteralExpression[] => {
    if (!value || depth > 8) return []
    const inner = bare(value)
    if (ts.isObjectLiteralExpression(inner)) return [inner]
    const name = nameOf(inner)
    if (name !== undefined) return objectsIn(consts.get(name), depth + 1)
    if (!ts.isCallExpression(inner)) return []
    return named(nameOf(inner.expression)).flatMap((hook) => returnsOf(hook).flatMap((value) => objectsIn(value, depth + 1)))
  }
  /** A tag that provides a context: `<C.Provider>`, or `<C>` where C is a same-file `createContext(…)` (React 19). */
  const contextOf = (tag: string | undefined): string | undefined => {
    if (tag === undefined) return undefined
    if (tag.endsWith('.Provider')) return tag.slice(0, -'.Provider'.length)
    const init = consts.get(tag)
    const call = init && bare(init)
    return call && ts.isCallExpression(call) && /(?:^|\.)createContext$/.test(nameOf(call.expression) ?? '') ? tag : undefined
  }
  /** Whether a value is the prefs value, or may be: a name holding it; either side of `??`, `||` or `&&` and either branch of a
      condition; a copy of it (an object that spreads it in, `Object.assign` or `structuredClone` of it); useMemo's value;
      `useContext(C)` or `use(C)` of a context the file provides it through; or what a same-file function that returns it
      hands back. */
  const isHolder = (value: ts.Expression, seen = new Set<Fn>()): boolean => {
    const inner = bare(value)
    const name = nameOf(inner)
    if (name !== undefined) return holders.has(name)
    if (ts.isBinaryExpression(inner) && LOGICAL.has(inner.operatorToken.kind)) return isHolder(inner.left, seen) || isHolder(inner.right, seen)
    if (ts.isConditionalExpression(inner)) return isHolder(inner.whenTrue, seen) || isHolder(inner.whenFalse, seen)
    if (ts.isObjectLiteralExpression(inner)) return inner.properties.some((p) => ts.isSpreadAssignment(p) && isHolder(p.expression, seen))
    if (!ts.isCallExpression(inner)) return false
    const callee = nameOf(inner.expression) ?? ''
    if (/^(?:Object\.assign|structuredClone)$/.test(callee)) return inner.arguments.some((arg) => !ts.isSpreadElement(arg) && isHolder(arg, seen))
    if (/(?:^|\.)useMemo$/.test(callee)) {
      return functionsIn(inner.arguments[0]).some((factory) => !seen.has(factory) && (seen.add(factory), returnsOf(factory).some((returned) => isHolder(returned, seen))))
    }
    if (/^(?:React\.)?(?:useContext|use)$/.test(callee)) {
      const context = inner.arguments[0] && nameOf(inner.arguments[0])
      return context !== undefined && contexts.has(context)
    }
    return named(callee).some((fn) => {
      if (seen.has(fn)) return false
      seen.add(fn)
      return returnsOf(fn).some((returned) => isHolder(returned, seen))
    })
  }
  /** Hand a value to a name: the prefs value, the functions it is, and an object's functions as `name.key`. */
  const bindName = (name: string, value: ts.Expression) => {
    if (isHolder(value)) addHolder(name)
    for (const fn of functionsIn(value)) addFunction(name, fn)
    for (const object of objectsIn(value)) {
      for (const property of object.properties) {
        const key = propertyKey(property.name)
        if (key === undefined) continue
        if (ts.isMethodDeclaration(property)) addFunction(`${name}.${key}`, property)
        else if (ts.isPropertyAssignment(property)) for (const fn of functionsIn(property.initializer)) addFunction(`${name}.${key}`, fn)
        else if (ts.isShorthandPropertyAssignment(property)) for (const fn of named(nameOf(property.name))) addFunction(`${name}.${key}`, fn)
      }
    }
  }
  /** The array literals a value is: written in place, or held in a const. */
  const arraysIn = (value: ts.Expression | undefined, depth = 0): ts.ArrayLiteralExpression[] => {
    if (!value || depth > 8) return []
    const inner = bare(value)
    if (ts.isArrayLiteralExpression(inner)) return [inner]
    const name = nameOf(inner)
    return name !== undefined ? arraysIn(consts.get(name), depth + 1) : []
  }
  /** Hand a value to a binding: a name; an array pattern, each element the array's element at its index; or an object
      pattern, whose keys taken out of the prefs value are fields read, whose rest holds the rest of it, and each of whose
      nested patterns takes apart the value at its key (an object's entry, or a member of a name: `props.prefs`); a key
      taken out of an object of functions names that function. */
  const bindPattern = (target: ts.BindingName, value: ts.Expression) => {
    if (ts.isIdentifier(target)) return bindName(keyOf(target), value)
    if (ts.isArrayBindingPattern(target)) {
      target.elements.forEach((element, index) => {
        if (ts.isOmittedExpression(element) || element.dotDotDotToken) return
        for (const array of arraysIn(value)) {
          const item = array.elements[index]
          if (item && !ts.isOmittedExpression(item) && !array.elements.slice(0, index + 1).some(ts.isSpreadElement)) bindPattern(element.name, item)
        }
      })
      return
    }
    const holder = isHolder(value)
    for (const element of target.elements) {
      const key = propertyKey(element.propertyName ?? element.name)
      if (element.dotDotDotToken) {
        if (ts.isIdentifier(element.name)) bindName(keyOf(element.name), value)
        continue
      }
      if (key === undefined) continue
      if (holder) read(key, element)
      if (!ts.isIdentifier(element.name)) {
        for (const object of objectsIn(value)) {
          for (const property of object.properties) {
            if (propertyKey(property.name) !== key) continue
            if (ts.isPropertyAssignment(property)) bindPattern(element.name, property.initializer)
            else if (ts.isShorthandPropertyAssignment(property)) bindPattern(element.name, property.name)
          }
        }
        const inner = bare(value)
        if (nameOf(inner) !== undefined) bindPattern(element.name, ts.factory.createPropertyAccessExpression(inner as ts.LeftHandSideExpression, key))
        continue
      }
      for (const object of objectsIn(value)) {
        for (const property of object.properties) {
          if (propertyKey(property.name) !== key) continue
          const local = keyOf(element.name)
          if (ts.isMethodDeclaration(property)) addFunction(local, property)
          else if (ts.isPropertyAssignment(property)) bindName(local, property.initializer)
          else if (ts.isShorthandPropertyAssignment(property)) for (const fn of named(nameOf(property.name))) addFunction(local, fn)
        }
      }
    }
  }
  /** Hand a tag's attribute (or a spread of its props, `prop` undefined) to the first parameter of the component it names. */
  const bindProp = (component: Fn, prop: string | undefined, value: ts.Expression) => {
    const param = component.parameters[0]?.name
    if (!param) return
    if (ts.isIdentifier(param)) return bindName(prop === undefined ? keyOf(param) : `${keyOf(param)}.${prop}`, value)
    if (!ts.isObjectBindingPattern(param)) return
    if (prop === undefined) return bindPattern(param, value)
    const element = param.elements.find((e) => !e.dotDotDotToken && propertyKey(e.propertyName ?? e.name) === prop)
    if (element) return bindPattern(element.name, value)
    const rest = param.elements.find((e) => e.dotDotDotToken && ts.isIdentifier(e.name))
    if (rest && ts.isIdentifier(rest.name)) bindName(`${keyOf(rest.name)}.${prop}`, value)
  }

  // The calls that save a preference: `save`, any `.mutate`, and each function in the file that calls one; and those that
  // take the field's name, `setBool('notify_10k')` and any function that saves `{ [name]: … }` keyed by its own parameter.
  const savers = seeds('save')
  const keySavers = seeds('setBool')
  const calleeText = (call: ts.CallExpression) => nameOf(call.expression) ?? call.expression.getText(source)
  const savesHere = (call: ts.CallExpression) => {
    const callee = calleeText(call)
    return savers.has(callee) || /\.(?:mutate|mutateAsync)$/.test(callee)
  }
  const within = (node: ts.Node, test: (node: ts.Node) => boolean): boolean =>
    test(node) || (ts.forEachChild(node, (child) => within(child, test) || undefined) ?? false)
  const savesByKey = (fn: Fn): boolean => {
    const params = new Set(fn.parameters.flatMap((p) => (ts.isIdentifier(p.name) ? [p.name.text] : [])))
    return within(fn, (node) => ts.isCallExpression(node) && savesHere(node) && node.arguments.some((arg) => objectsIn(arg).some((object) =>
      object.properties.some((p) => !!p.name && ts.isComputedPropertyName(p.name) && ts.isIdentifier(p.name.expression) && params.has(p.name.expression.text)))))
  }

  const walkFile = (step: (node: ts.Node) => void) => {
    const walk = (node: ts.Node): void => {
      if (ts.isTypeNode(node)) return
      step(node)
      ts.forEachChild(node, walk)
    }
    walk(source)
  }
  while (grew) {
    grew = false
    walkFile((node) => {
      if (ts.isFunctionDeclaration(node) && node.name) addFunction(keyOf(node.name), node)
      // The function a mutation runs (`useMutation({ mutationFn: updatePrefs })`) saves when it is called directly too.
      if ((ts.isPropertyAssignment(node) || ts.isShorthandPropertyAssignment(node)) && propertyKey(node.name) === 'mutationFn') {
        const fn = nameOf(ts.isPropertyAssignment(node) ? node.initializer : node.name)
        if (fn !== undefined && !savers.has(fn)) {
          savers.add(fn)
          grew = true
        }
      }
      // A key named prefs taken out of an object, whatever it is taken out of (`const { prefs: settings } = props`).
      if (ts.isBindingElement(node) && !node.dotDotDotToken && propertyKey(node.propertyName ?? node.name) === 'prefs') {
        if (ts.isIdentifier(node.name)) addHolder(keyOf(node.name))
        else if (ts.isObjectBindingPattern(node.name)) {
          for (const element of node.name.elements) {
            const key = element.dotDotDotToken ? undefined : propertyKey(element.propertyName ?? element.name)
            if (key !== undefined) read(key, element)
          }
        }
      }
      if (ts.isVariableDeclaration(node) && node.initializer) {
        if (ts.isIdentifier(node.name)) consts.set(keyOf(node.name), node.initializer)
        bindPattern(node.name, node.initializer)
      }
      if (ts.isCallExpression(node)) {
        for (const fn of named(nameOf(node.expression))) {
          node.arguments.forEach((arg, index) => {
            const param = fn.parameters[index]
            if (param && !param.dotDotDotToken && !ts.isSpreadElement(arg)) bindPattern(param.name, arg)
          })
        }
      }
      if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
        const tag = nameOf(node.tagName as ts.Expression)
        const context = contextOf(tag)
        for (const attribute of node.attributes.properties) {
          const value = ts.isJsxSpreadAttribute(attribute) ? attribute.expression
            : attribute.initializer && ts.isJsxExpression(attribute.initializer) ? attribute.initializer.expression : undefined
          if (!value) continue
          const prop = ts.isJsxAttribute(attribute) ? attribute.name.getText(source) : undefined
          if (context !== undefined && prop === 'value' && isHolder(value) && !contexts.has(context)) {
            contexts.add(context)
            grew = true
          }
          for (const component of named(tag)) bindProp(component, prop, value)
        }
      }
    })
    for (const [name, fns] of functions) {
      for (const fn of fns) {
        if (!savers.has(name) && within(fn, (node) => ts.isCallExpression(node) && savesHere(node))) {
          savers.add(name)
          grew = true
        }
        if (!keySavers.has(name) && savesByKey(fn)) {
          keySavers.add(name)
          grew = true
        }
      }
    }
  }
  // Each field read off the prefs value: a member (`prefs.x`, `prefs?.x`, `prefs!.x`, `prefs['x']`); the keys taken out
  // of it were read on the way.
  walkFile((node) => {
    if (ts.isPropertyAccessExpression(node) && isHolder(node.expression)) read(node.name.text, node)
    if (ts.isElementAccessExpression(node) && isHolder(node.expression) && ts.isStringLiteralLike(node.argumentExpression)) read(node.argumentExpression.text, node)
  })

  const visit = (node: ts.Node): void => {
    // type BoolPref = 'notify_10k' | … : every member is a field the form can save.
    if (ts.isTypeAliasDeclaration(node) && ts.isUnionTypeNode(node.type)) {
      for (const member of node.type.types) {
        if (ts.isLiteralTypeNode(member) && ts.isStringLiteral(member.literal)) fields.set(member.literal.text, line(member))
      }
    }
    if (ts.isCallExpression(node)) {
      // setBool('notify_10k'), and any function that saves `{ [name]: … }` keyed by its parameter: each name handed to it.
      if (keySavers.has(calleeText(node))) {
        for (const arg of node.arguments) if (ts.isStringLiteral(arg)) fields.set(arg.text, line(arg))
      }
      // save({ digest: … }) / mutation.mutate({ … }) / any saver: each field its update writes (written in place, held in a
      // const, or spread into it from one), and each literal it writes into one.
      if (savesHere(node)) {
        const update = (object: ts.ObjectLiteralExpression, depth = 0): void => {
          for (const prop of object.properties) {
            if (ts.isSpreadAssignment(prop)) {
              if (depth < 8) for (const inner of objectsIn(prop.expression)) update(inner, depth + 1)
              continue
            }
            const key = propertyKey(prop.name)
            if (key !== undefined) fields.set(key, line(prop))
            if (ts.isPropertyAssignment(prop)) for (const value of literalsOf(prop.initializer)) options.set(value, line(prop))
          }
        }
        for (const arg of node.arguments) for (const object of objectsIn(arg)) update(object)
      }
    }
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node))) {
      const tag = node.tagName.getText(source)
      for (const attr of node.attributes.properties) {
        if (!ts.isJsxAttribute(attr) || !attr.initializer) continue
        const name = attr.name.getText(source)
        const init = attr.initializer
        const expression = ts.isJsxExpression(init) ? init.expression : undefined
        // checked={prefs.x} / value={prefs.x}: a preference the form renders as a control's state. An <option>'s value is
        // what it offers, so there it is read as an offered value too, and no literal can be read from it.
        if ((name === 'checked' || name === 'value') && expression && ts.isPropertyAccessExpression(expression) && expression.expression.getText(source) === 'prefs') {
          fields.set(expression.name.text, line(init))
          if (tag !== 'option') continue
        }
        // value="weekly", value={'weekly'}, a value a .map writes (an <option>, a radio, any item); options={[{ value: … }]}.
        // A context provider's value is what it provides, not a choice.
        if (name === 'value' && contextOf(nameOf(node.tagName as ts.Expression)) !== undefined) continue
        const values = name === 'value'
          ? ts.isStringLiteral(init) ? [init.text] : expression ? optionValues(expression) : null
          : name === 'options'
            ? expression ? optionsValues(expression) : null
            : undefined
        if (values === undefined) continue
        if (values) for (const value of values) options.set(value, line(attr))
        else unreadable.push(`${file}:${line(attr)} <${tag} ${attr.getText(source)}>`)
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  // The reads beside main's: a field the API fills from entitlements is gating, not a preference, unless read as a state above.
  for (const [field, at] of reads) if (!derived.has(field) && !fields.has(field)) fields.set(field, at)
  return { fields, options, unreadable }
}

/**
 * The fields the API fills from the account's entitlements (`realtime_available=ent.realtime_alerts` in
 * backend/app/routers/users.py's `_prefs_response`): gating the form shows, not preferences the user sets.
 */
const USERS = readFileSync(path.resolve(frontendDir, '../backend/app/routers/users.py'), 'utf8')
const DERIVED = new Set([...(blocks(USERS).get('_prefs_response') ?? '').matchAll(/\b(\w+)\s*=\s*ent\.\w+/g)].map((match) => match[1]))
/** The fields a user can set: the update model's. */
const SETTABLE = new Set([...(blocks(USERS).get('NotificationPreferencesUpdate') ?? '').matchAll(/^\s+(\w+)\s*:/gm)].map((match) => match[1]))

const form = formPreferences(FORM, readFileSync(path.join(frontendDir, FORM), 'utf8'), DERIVED)
const consumerCode = jobCode(CONSUMERS.map((rel) => readFileSync(path.resolve(frontendDir, '..', rel), 'utf8')))

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const readsField = (code: string, field: string) => new RegExp(`\\bprefs\\.${escape(field)}\\b(?!\\s*=(?!=))`).test(code)
const hasLiteral = (code: string, value: string) => new RegExp(`['"]${escape(value)}['"]`).test(code)

describe('Notification preferences the form offers are read by the alert jobs', () => {
  it('finds the form\'s preferences and the jobs\' code (the scan is not vacuous)', () => {
    expect([...form.fields.keys()]).toEqual(expect.arrayContaining(['notify_10k', 'notify_10q', 'notify_8k', 'realtime']))
    for (const entry of JOB_ENTRIES) expect(consumerCode, entry).toMatch(new RegExp(`def ${entry}\\(`))
  })

  it('counts a read only in code the jobs reach, never the write path, a helper only it calls, a serializer, a constant or a docstring (self-check)', () => {
    const service = [
      '"""Helpers. prefs.weekly_note is only mentioned here."""',
      'VALID_DIGESTS = ("immediate", "daily", "weekly")',
      'def apply_preference_update(db, prefs, data):',
      '    prefs.digest = _normalize_digest(prefs)',
      '',
      'def _normalize_digest(prefs):',
      '    return prefs.digest if prefs.digest in ("daily", "weekly") else "daily"',
      '',
      'def serialize_preferences(prefs):',
      '    return {"notify_10q": prefs.notify_10q}',
      '',
      '@cached',
      'def evaluate_delivery(',
      '    prefs, ent, filing_type,',
      ') -> tuple:',
      '    # prefs.notify_10k in a comment is no read',
      '    prefs.realtime = False',
      '    return _enabled(prefs, filing_type), filing_type == "8-K"',
      '',
      'def _enabled(prefs, filing_type):',
      '    return bool(prefs.notify_8k)',
    ].join('\n')
    const job = ['async def run_daily_digest(db):', '    eligible, _ = evaluate_delivery(prefs, ent, "10-K")'].join('\n')
    const code = jobCode([service, job])
    expect(readsField(code, 'notify_8k')).toBe(true)
    expect(hasLiteral(code, '8-K')).toBe(true)
    expect(code).toContain('@cached')
    expect(readsField(code, 'digest')).toBe(false)
    expect(readsField(code, 'notify_10q')).toBe(false)
    expect(readsField(code, 'realtime')).toBe(false)
    expect(readsField(code, 'notify_10k')).toBe(false)
    expect(readsField(code, 'weekly_note')).toBe(false)
    expect(hasLiteral(code, 'weekly')).toBe(false)
    // A job that calls the helper itself makes it a reader.
    expect(readsField(jobCode([service, `${job}\n    _normalize_digest(prefs)`]), 'digest')).toBe(true)
  })

  it('reads the values every kind of choice offers, in place and through a .map, and refuses any other (self-check)', () => {
    const fixture = [
      "const DIGESTS = ['daily', 'weekly'] as const",
      "const CHOICES = [{ value: 'immediate', label: 'Now' }]",
      'export const A = () => <select>{DIGESTS.map((d) => <option key={d} value={d}>{d}</option>)}</select>',
      'export const B = () => <select>{CHOICES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}</select>',
      "export const C = () => <select><option value=\"monthly\">Monthly</option><option value={'hourly'}>Hourly</option></select>",
      "export const D = () => <select>{['quarterly'].map((q) => <option key={q} value={q}>{q}</option>)}</select>",
      'export const E = ({ v }: { v: string }) => <option value={v} />',
      'export const F = () => <select>{load().map((x) => <option key={x} value={x}>{x}</option>)}</select>',
      // The choices the review of #1291 found unread (DSW-01's "Weekly still mails daily" through another control):
      // a SegmentedControl's options, in place, as a const and through a .map; a radio input; a literal a save writes.
      "export const G = () => <SegmentedControl label=\"Digest\" options={[{ value: 'fortnightly', label: 'Fortnightly' }]} value={prefs.digest} onChange={(digest) => save({ digest })} />",
      "const PERIODS = [{ value: 'yearly', label: 'Yearly' }] as const",
      'export const H = () => <SegmentedControl label="Period" options={PERIODS} value={prefs.period} onChange={() => {}} />',
      "const KINDS = ['annual', 'interim'] as const",
      'export const I = () => <SegmentedControl label="Kind" options={KINDS.map((k) => ({ value: k, label: k }))} value={prefs.kind} onChange={() => {}} />',
      'export const J = () => <input type="radio" name="digest" value="biweekly" checked={prefs.digest === \'biweekly\'} readOnly />',
      "export const K = () => <button type=\"button\" onClick={() => save({ digest: on ? 'never' : 'hourly' })}>Never</button>",
      'export const L = () => <SegmentedControl label="x" options={load()} value={prefs.l} onChange={() => {}} />',
      "export const M = () => <SegmentedControl label=\"x\" options={[{ value: v, label: 'V' }]} value={prefs.m} onChange={() => {}} />",
      // A select's value is its state; an <option>'s is what it offers, and the current preference offers no literal.
      'export const N = () => <select value={prefs.digest}><option value={prefs.digest}>Current</option></select>',
    ].join('\n')
    const { options, unreadable } = formPreferences('fixture.tsx', fixture)
    expect([...options.keys()].sort()).toEqual([
      'annual', 'biweekly', 'daily', 'fortnightly', 'hourly', 'immediate', 'interim', 'monthly', 'never', 'quarterly', 'weekly', 'yearly',
    ])
    expect(unreadable).toEqual([
      'fixture.tsx:7 <option value={v}>',
      'fixture.tsx:8 <option value={x}>',
      'fixture.tsx:16 <SegmentedControl options={load()}>',
      "fixture.tsx:17 <SegmentedControl options={[{ value: v, label: 'V' }]}>",
      'fixture.tsx:18 <option value={prefs.digest}>',
    ])
  })

  it('reads a field wherever the form reads the prefs value, and a save through any helper, but not gating the API derives (self-check)', () => {
    // Each form with a field used nowhere else in the fixture (Codex on 8fb22fbe: another line could mask a miss), tagged
    // with the fields it reads, or with those it breaks the rule with out of the scan's reach (the header's limits).
    const FORMS: Array<[code: string, read?: string[], gap?: string[]]> = [
      ['export function Form() {'],
      ['  const { data: prefs } = useQuery(q)'],
      ['  const held = prefs'],
      ['  const { f_destructured, f_renamed: renamed } = prefs', ['f_destructured', 'f_renamed']],
      ['  const persist = (update: Update) => mutation.mutate(update)'],
      // A saver in each function form (the re-review of 77b306f6 found one in useCallback unfollowed).
      ['  const persistCb = useCallback((u: Update) => mutation.mutate(u), [mutation])'],
      ['  const persistMemo = useMemo(() => (u: Update) => save(u), [])'],
      ['  const actions = { store(u: Update) { save(u) }, reset: (u: Update) => save(u) }'],
      ['  const viaHook = usePersist()'],
      ['  const { keep } = useActions()'],
      ['  const flip = (field: string) => save({ [field]: true })'],
      ["  const update = { f_const_update: 'monthly' }", ['f_const_update']],
      ['  const base = { f_spread_update: true }', ['f_spread_update']],
      ['  const handlers = [persist]'],
      ['  const MemoizedRow = useMemo(() => ({ source }: P) => <Toggle checked={source.f_usememo_component} />, [])', ['f_usememo_component']],
      ['  const { prefs: fromBag } = bag'],
      ['  const fromHook = usePrefsValue()'],
      ['  const hookLabel = useLabel(prefs)'],
      ['  const [local] = useState(prefs)'],
      ['  const ref = useRef(prefs)'],
      // The prefs value or a copy of it through any operator or call that hands it on (the re-review of 6a39e259 found
      // `??`, a ternary, a spread copy and useMemo unread), and taken apart by a nested or an array pattern.
      ['  const viaNullish = prefs ?? DEFAULTS'],
      ['  const viaTernary = ok ? prefs : DEFAULTS'],
      ['  const viaSpread = { ...prefs }'],
      ['  const viaMemo = useMemo(() => prefs, [prefs])'],
      ['  const viaAssign = Object.assign({}, prefs)'],
      ['  const viaClone = structuredClone(prefs)'],
      ['  const viaJson = JSON.parse(JSON.stringify(prefs))'],
      ['  const bag2 = { prefs }'],
      ['  const { prefs: { f_nested_prefs } } = bag2', ['f_nested_prefs']],
      ['  const { settings: { f_nested_object } } = { settings: prefs }', ['f_nested_object']],
      ['  const { f_with_default = false } = prefs', ['f_with_default']],
      ['  const [first] = [prefs]'],
      ['  const PAIR = [other, prefs]'],
      ['  const [, second] = PAIR'],
      ['  const [, ...restPair] = [other, prefs]'],
      // A save through any trigger a mutation offers, and the function it runs called directly (the re-review: mutateAsync).
      ['  const mutation2 = useMutation({ mutationFn: updatePrefs })'],
      ['  return ('],
      ['    <PrefsContext.Provider value={prefs}>'],
      ['    <Prefs19 value={prefs}>'],
      // The prefs value read in place.
      ["      <input type=\"radio\" checked={prefs.f_compared === 'biweekly'} readOnly />", ['f_compared']],
      ['      <Picker selected={prefs.f_wrapper} />', ['f_wrapper']],
      ["      <p>{prefs.f_child ? 'On' : 'Off'} {hookLabel}</p>", ['f_child']],
      ['      <Toggle disabled={!prefs.f_negated} />', ['f_negated']],
      ["      <Picker selected={prefs.f_fallback ?? 'daily'} />", ['f_fallback']],
      ['      <Row label={`Every ${prefs.f_template}`} />', ['f_template']],
      ['      <Toggle checked={prefs?.f_optional} />', ['f_optional']],
      ["      <Toggle checked={prefs['f_bracket']} />", ['f_bracket']],
      ['      <Toggle checked={prefs!.f_asserted} />', ['f_asserted']],
      ['      <Toggle checked={held.f_alias} />', ['f_alias']],
      ['      <Toggle checked={fromHook.f_hook_value} />', ['f_hook_value']],
      ['      <Toggle checked={fromBag.f_key_prefs} />', ['f_key_prefs']],
      ['      <Toggle checked={prefs.f_direct} />', ['f_direct']],
      ['      <Toggle checked={viaNullish.f_nullish} />', ['f_nullish']],
      ['      <Toggle checked={viaTernary.f_ternary} />', ['f_ternary']],
      ['      <Toggle checked={viaSpread.f_spread_copy} />', ['f_spread_copy']],
      ['      <Toggle checked={viaMemo.f_memo_value} />', ['f_memo_value']],
      ['      <Toggle checked={viaAssign.f_assign} />', ['f_assign']],
      ['      <Toggle checked={viaClone.f_clone} />', ['f_clone']],
      ['      <Toggle checked={(prefs || DEFAULTS).f_or_inline} />', ['f_or_inline']],
      ['      <Toggle checked={first.f_array_pattern} />', ['f_array_pattern']],
      ['      <Toggle checked={second.f_array_const} />', ['f_array_const']],
      ['      <Deep settings={prefs} />'],
      ['      <select><option value={prefs.f_option}>Current</option></select>', ['f_option']],
      ['      <Toggle disabled={!prefs.f_available} />'],
      ['      <Toggle checked={other.f_other} />'],
      ['      <Toggle checked={prefsLabel.f_label} />'],
      // A save through each form of saver.
      ["      <button onClick={() => persist({ f_saved: on ? 'never' : 'hourly' })}>Reset</button>", ['f_saved']],
      ["      <button onClick={() => persistCb({ f_cb: 'weekly' })}>Weekly</button>", ['f_cb']],
      ['      <button onClick={() => persistMemo({ f_memo_saved: true })}>Memo</button>', ['f_memo_saved']],
      ['      <button onClick={() => actions.store({ f_method: true })}>Store</button>', ['f_method']],
      ['      <button onClick={() => actions.reset({ f_method_arrow: true })}>Reset</button>', ['f_method_arrow']],
      ['      <button onClick={() => viaHook({ f_hook_saved: true })}>Hook</button>', ['f_hook_saved']],
      ['      <button onClick={() => keep({ f_hook_object: true })}>Keep</button>', ['f_hook_object']],
      ['      <button onClick={() => persistDecl({ f_decl_saved: true })}>Declared</button>', ['f_decl_saved']],
      ["      <button onClick={() => flip('f_key_saved')}>Flip</button>", ['f_key_saved']],
      ['      <button onClick={() => mutation.mutateAsync({ f_mutate_async: true })}>Async</button>', ['f_mutate_async']],
      ['      <button onClick={() => updatePrefs({ f_mutation_fn: true })}>Direct</button>', ['f_mutation_fn']],
      ['      <button onClick={() => persist(update)}>Held</button>'],
      ['      <button onClick={() => persist({ ...base })}>Spread</button>'],
      ['      <button onClick={() => run(persist)}>Run</button>'],
      ['      <Panel onSave={persist} />'],
      // The prefs value handed on: a prop, a spread, a wrapped or an object's component, a rest, a context, a hook.
      ['      <Rows source={prefs} />'],
      ['      <Cells source={prefs} />'],
      ['      <Spread {...prefs} />'],
      ['      <SpreadAll {...prefs} />'],
      ['      <MemoRows source={prefs} />'],
      ['      <FwdRows source={prefs} />'],
      ['      <MemoFwd source={prefs} />'],
      ['      <RestRows other={prefs} />'],
      ['      <Parts.Row source={prefs} />'],
      ['      <MemoizedRow source={prefs} />'],
      ['      <Leaf />'],
      ['      <Leaf19 />'],
      // Out of reach, the header's limits: React state or a ref, a computed key, a class, another module, call/apply/bind,
      // an array of functions.
      ['      <Toggle checked={local.f_gap_state} />', [], ['f_gap_state']],
      ['      <Toggle checked={ref.current.f_gap_ref} />', [], ['f_gap_ref']],
      ['      <Toggle checked={prefs[dynamicKey]} />', [], ['dynamicKey']],
      ['      {Object.entries(prefs).map(([entryKey, on]) => <Toggle key={entryKey} checked={on} />)}', [], ['entryKey']],
      ['      <Legacy source={prefs} />'],
      ['      <ExternalRows source={prefs} />'],
      ["      <button onClick={() => persistElsewhere({ f_gap_import: 'gap_import' })}>Import</button>", [], ['f_gap_import']],
      ["      <button onClick={() => persist.call(null, { f_gap_call: 'gap_call' })}>Call</button>", [], ['f_gap_call']],
      ["      <button onClick={() => handlers[0]({ f_gap_array: 'gap_array' })}>Array</button>", [], ['f_gap_array']],
      // Out of reach too: a copy made another way (a JSON round trip), an array's rest, and a save sent by hand (`fetch`).
      ['      <Toggle checked={viaJson.f_gap_json} />', [], ['f_gap_json']],
      ['      <Toggle checked={restPair[0].f_gap_array_rest} />', [], ['f_gap_array_rest']],
      ["      <button onClick={() => fetch('/api/prefs', { method: 'PUT', body: JSON.stringify({ f_gap_fetch: true }) })}>Fetch</button>", [], ['f_gap_fetch']],
      ['    </Prefs19>'],
      ['    </PrefsContext.Provider>'],
      ['  )'],
      ['}'],
      ['function persistDecl(u: Update) { mutation.mutate(u) }'],
      ['function usePersist() { return (u: Update) => save(u) }'],
      ['function useActions() { return { keep: (u: Update) => save(u) } }'],
      ['function usePrefsValue() { const { data: prefs } = useQuery(q); return prefs }'],
      ["function useLabel(p: Prefs) { return p.f_hook_arg ? 'On' : 'Off' }", ['f_hook_arg']],
      ['function run(fn: (u: Update) => void) { fn({ f_arg_saved: true }) }', ['f_arg_saved']],
      ['function Panel({ onSave }: PanelProps) { return <button onClick={() => onSave({ f_prop_saved: true })}>Save</button> }', ['f_prop_saved']],
      ['function Rows({ source }: { source: { f_typed: boolean } }) { return <Toggle checked={source.f_prop} /> }', ['f_prop']],
      ['function Deep({ settings: { f_prop_nested } }: P) { return <Toggle checked={f_prop_nested} /> }', ['f_prop_nested']],
      ['function KeyedRows(props: P) { const { prefs: { f_keyed_nested } } = props; return <Toggle checked={!!f_keyed_nested} /> }', ['f_keyed_nested']],
      ['function Cells(props: Props) { return <Toggle checked={props.source.f_props} /> }', ['f_props']],
      ['function Spread({ f_spread }: Prefs) { return <Toggle checked={f_spread} /> }', ['f_spread']],
      ['function SpreadAll(props: Prefs) { return <Toggle checked={props.f_spread_props} /> }', ['f_spread_props']],
      ['const MemoRows = memo(function MemoRows({ source }: P) { return <Toggle checked={source.f_memo} /> })', ['f_memo']],
      ['const FwdRows = forwardRef((props: P, ref: R) => <Toggle ref={ref} checked={props.source.f_forward} />)', ['f_forward']],
      ['const MemoFwd = memo(forwardRef(({ source }: P, ref: R) => <Toggle ref={ref} checked={source.f_memo_forward} />))', ['f_memo_forward']],
      ['function RestRows({ source, ...rest }: P) { return <Toggle checked={rest.other.f_rest} /> }', ['f_rest']],
      ['const Parts = { Row: ({ source }: P) => <Toggle checked={source.f_object_component} /> }', ['f_object_component']],
      ['const PrefsContext = createContext<Prefs | null>(null)'],
      ['const Prefs19 = createContext<Prefs | null>(null)'],
      ['function Leaf() { const fromContext = useContext(PrefsContext); return <Toggle checked={fromContext.f_context} /> }', ['f_context']],
      ['function Leaf19() { const fromUse = use(Prefs19); return <Toggle checked={fromUse.f_context19} /> }', ['f_context19']],
      ['class Legacy extends Component<P> { render() { return <Toggle checked={this.props.source.f_gap_class} /> } }', [], ['f_gap_class']],
    ]
    const { fields, options, unreadable } = formPreferences('fixture.tsx', FORMS.map(([code]) => code).join('\n'), new Set(['f_available']))
    expect([...fields.keys()].sort()).toEqual(FORMS.flatMap(([, read = []]) => read).sort())
    expect(FORMS.flatMap(([, , gap = []]) => gap).filter((name) => fields.has(name)), 'a limit the header states is read after all: move it to the read forms').toEqual([])
    expect([...options.keys()].sort()).toEqual(['hourly', 'monthly', 'never', 'weekly'])
    // The current preference as an option's value still offers no literal (0662fdcf); a context provider's value is no choice.
    const optionLine = FORMS.findIndex(([code]) => code.includes('<option value={prefs.f_option}>')) + 1
    expect(unreadable).toEqual([`fixture.tsx:${optionLine} <option value={prefs.f_option}>`])
    // The gating the response fills from the entitlements is no setting: the update model takes none of it.
    expect([...DERIVED], 'the response fills the two gates from the entitlements').toEqual(expect.arrayContaining(['eightk_available', 'realtime_available']))
    expect([...DERIVED].filter((field) => SETTABLE.has(field)), 'a field the user can set is a preference, never gating').toEqual([])
    expect(SETTABLE.has('digest'), 'the update model is read').toBe(true)
  })

  it('every field the form renders or saves is read as prefs.<field> by the jobs', () => {
    const unread = [...form.fields].filter(([field]) => !readsField(consumerCode, field))
    expect(unread.map(([field, at]) => `${FORM}:${at} ${field} has no reader the jobs reach in ${CONSUMERS.join(', ')}`)).toEqual([])
  })

  it('every value the form offers is a literal the jobs act on, and the scan reads each one', () => {
    expect(form.unreadable, 'write the value as a literal or through a .map over a literal array').toEqual([])
    const unread = [...form.options].filter(([value]) => !hasLiteral(consumerCode, value))
    expect(unread.map(([value, at]) => `${FORM}:${at} option "${value}" has no reader the jobs reach in ${CONSUMERS.join(', ')}`)).toEqual([])
  })
})
