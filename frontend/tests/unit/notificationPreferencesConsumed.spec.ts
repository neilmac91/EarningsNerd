import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { ESLint } from 'eslint'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { bindingResolver, containerEscape } from './astBindings'

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
 * parameter. A container the scan reads through a name (an update a save sends, an object of savers, an options array
 * and the objects in it) is read only while nothing can change it after its initializer, each use read as astBindings'
 * containerEscape reads it, a save that sends it (followed into a same-file saver's parameter) and an `options` prop
 * counting as reads: a write, a method that may write it, a call or a component it is handed to, or an export fails
 * the scan with the use and its line. Out of reach, each planted as a gap the self-check asserts unread: a value or a
 * function from another module, a class component, the value kept in React state or a ref (`useState`, `useRef`), a
 * copy made another way (a JSON round trip), an array's rest, a field named by a computed key or enumerated
 * (`prefs[key]`, `Object.entries(prefs)`), a function called through call, apply or bind or held in an array, a save
 * sent by hand (`fetch`), and an object a same-file hook returns, written after the call (read as the hook writes it);
 * a component that writes the options array it is handed is not read either. Nor is an element built by a factory,
 * which lint refuses (eslint.designRules.mjs's elements-built-with-jsx): `React.createElement(Rows, { source: prefs })`
 * hands the prefs value to no prop the scan follows (planted with the rule's finding). A field the API fills from the
 * account's entitlements (`_prefs_response` in backend/app/routers/users.py assigns it from `ent.`, and the update
 * model does not take it) is gating the user cannot set, not a preference, so a read of it there is not held to the
 * jobs; read directly as a control's state (`checked={prefs.x}`), as main read it, any field is.
 *
 * The values the form offers are read where they are written, in each form a choice takes: any element's
 * `value="…"` or `value={'…'}` (an <option>, a radio input, a custom item; `value={prefs.x}` is the control's
 * state, a field, and on an <option>, whose value is what it offers, a value the scan cannot read), each
 * entry's `value` in an `options` prop (SegmentedControl, the design system's single choice, or any select
 * wrapper), and each value a save or mutate call writes into a field: a literal (`save({ digest: 'weekly' })`),
 * each branch of a condition and each side of `||`, `??` or `&&`, what a same-file const holds (`const WEEKLY =
 * 'weekly'`, through a const that names another), and a function's own parameter, read as its default and as what
 * each call of the function in the file hands it (`choose('weekly')`); a control's callback's own parameter
 * (`onChange={(v) => save({ digest: v })}`) also takes what the control offers, read where that is written (its
 * options, or a switch's true or false). A boolean, a number, null or undefined offers no choice, and neither does a
 * value an operator makes a boolean (`!x`, a comparison). A value or an `options` entry may also be the element,
 * or one of its fields, of the array a `.map` takes (`DIGESTS.map((d) => <option value={d}>)`,
 * `CHOICES.map((c) => ({ value: c.value }))`), the array written in place or as a const in the form. A `value`,
 * an `options` entry or a saved value written any other way fails the scan with its place: a `let`, a value kept in
 * React state, an import, a member (`e.target.value` is not the callback's own parameter), a call, a template with a
 * substitution, a method, and a parameter of a function that no call in the file and no control hands a value. So a
 * choice it cannot read never ships unread.
 *
 * Limits: a block is reached by name (a same-named function in another module is not told apart, and a call
 * made through a variable or getattr is not followed, which only narrows), and a reached block counts as a
 * whole, so a read whose value the job then drops still counts; review reads what the job does with it. In the
 * form, each walk follows a value eight steps (a wrapping call, a hook's return, a const, a spread into an update):
 * a chain longer than that, or a cycle of them (a hook that returns its own call, a const that holds itself), fails
 * the scan loudly with the place it stopped, so it never reads as no saver or no field.
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
  /** The containers the scan reads through a name (and the objects of an options array it reads each entry's value of),
      each checked once the scan is done: nothing may change one after its initializer. */
  const followed = new Map<ts.ObjectLiteralExpression | ts.ArrayLiteralExpression, string>()
  const lexical = bindingResolver(source)
  /** The array literal an expression names: written in place, or the declaration its name binds to (astBindings, so a
      same-named const in another component is that component's own; Codex on 74fe2f53). */
  const arrayOf = (node: ts.Expression): ts.ArrayLiteralExpression | null => {
    const inner = unwrap(node)
    if (ts.isArrayLiteralExpression(inner)) return inner
    if (!ts.isIdentifier(inner)) return null
    const decl = lexical(inner)?.decl
    const init = decl && ts.isVariableDeclaration(decl) && decl.initializer ? unwrap(decl.initializer) : undefined
    if (!init || !ts.isArrayLiteralExpression(init)) return null
    followed.set(init, inner.text)
    return init
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
      const values = array.elements.map((item, index) => {
        if (!field) return literal(item as ts.Expression)
        const object = unwrap(item as ts.Expression)
        if (!ts.isObjectLiteralExpression(object)) return null
        if (followed.has(array)) followed.set(object, `${followed.get(array)}[${index}]`)
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
      array.elements.forEach((item, index) => {
        const object = unwrap(item as ts.Expression)
        if (followed.has(array) && ts.isObjectLiteralExpression(object)) followed.set(object, `${followed.get(array)}[${index}]`)
      })
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
  // ── What the form hands where: its functions and the prefs value, followed through the file ─────────────────────────
  // A name is the declaration an identifier binds to in the file (astBindings, so two components' `props` stay apart; an
  // unbound name, an import or a global, is its text), or a member path from one (`actions.persist`, `props.source`). A
  // function is reached by the name its call or its tag spells, and each of its parameters takes what every call and tag
  // in the file hands it there. Run to a fixed point, which the loop reaches: it only adds (a function to a name, a holder,
  // a saver, a context), and every name it adds is a declaration of the file, a member path written in it, or a declaration
  // with at most two of the file's keys after it, so what it can add is finite. Each walk inside it stops at eight steps
  // and says so (pastReach).
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
  /** A value a walk here reaches past its eight steps (a chain of wrapping calls, hook returns, consts or spreads, or a cycle
      of them: a hook that returns its own call, a const that holds itself): what it holds goes unread, so the scan fails
      loudly, once per place, with where it stopped and what it was following. */
  const pastReach = <T>(node: ts.Node, what: string): T[] => {
    const entry = `${file}:${line(node)} ${node.getText(source).replace(/\s+/g, ' ')} (${what} through more steps than this reader follows)`
    if (!unreadable.includes(entry)) unreadable.push(entry)
    return []
  }
  /** The functions a value is: an arrow or a function expression; a named one; the one a call wraps as its first argument
      (useCallback, memo, forwardRef or any wrapper, nested), useMemo's factory's result; what a same-file hook returns. */
  const functionsIn = (value: ts.Expression | undefined, depth = 0): Fn[] => {
    if (!value) return []
    if (depth > 8) return pastReach(value, 'a function held')
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
    if (!value) return []
    if (depth > 8) return pastReach(value, 'an object held')
    const inner = bare(value)
    if (ts.isObjectLiteralExpression(inner)) return [inner]
    const name = nameOf(inner)
    if (name !== undefined) return objectsIn(follow(name), depth + 1)
    if (!ts.isCallExpression(inner)) return []
    return named(nameOf(inner.expression)).flatMap((hook) => returnsOf(hook).flatMap((value) => objectsIn(value, depth + 1)))
  }
  /** What a name holds, a container recorded as followed. */
  const follow = (name: string): ts.Expression | undefined => {
    const init = consts.get(name)
    const inner = init && bare(init)
    if (inner && (ts.isObjectLiteralExpression(inner) || ts.isArrayLiteralExpression(inner))) followed.set(inner, name.replace(/#\d+$/, ''))
    return init
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
      const fns = object.properties.flatMap((property) => {
        const key = propertyKey(property.name)
        if (key === undefined) return []
        const held = ts.isMethodDeclaration(property) ? [property] : ts.isPropertyAssignment(property) ? functionsIn(property.initializer)
          : ts.isShorthandPropertyAssignment(property) ? named(nameOf(property.name)) : []
        return held.map((fn) => [`${name}.${key}`, fn] as const)
      })
      for (const [key, fn] of fns) addFunction(key, fn)
      // An object of functions a const holds, read at its declaration: checked like a container read by its name.
      let top: ts.Node = object
      while (ts.isParenthesizedExpression(top.parent) || ts.isAsExpression(top.parent) || ts.isSatisfiesExpression(top.parent)) top = top.parent
      if (fns.length && ts.isVariableDeclaration(top.parent) && top.parent.initializer === top) followed.set(object, top.parent.name.getText(source))
    }
  }
  /** The array literals a value is: written in place, or held in a const. */
  const arraysIn = (value: ts.Expression | undefined, depth = 0): ts.ArrayLiteralExpression[] => {
    if (!value) return []
    if (depth > 8) return pastReach(value, 'an array held')
    const inner = bare(value)
    if (ts.isArrayLiteralExpression(inner)) return [inner]
    const name = nameOf(inner)
    return name !== undefined ? arraysIn(follow(name), depth + 1) : []
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

  // ── What a save writes into a field ─────────────────────────────────────────────────────────────────────────────────
  // A control's callbacks: each function an attribute hands an element or a component (`onChange={(v) => …}`,
  // `onChange={setBool('x')}`, `onChange={pick}`). The control calls it with the values it offers, read where they are
  // written (its options), or a switch's true or false. And every call the file makes of each function, under any name.
  const callbacks = new Set<Fn>()
  const callsOf = new Map<Fn, ts.CallExpression[]>()
  walkFile((node) => {
    if (ts.isJsxAttribute(node) && node.initializer && ts.isJsxExpression(node.initializer) && node.initializer.expression) {
      for (const fn of functionsIn(node.initializer.expression)) callbacks.add(fn)
    }
    if (ts.isCallExpression(node)) for (const fn of functionsIn(node.expression)) callsOf.set(fn, [...(callsOf.get(fn) ?? []), node])
  })
  const BOOLEAN = new Set([
    ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken, ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken,
    ts.SyntaxKind.LessThanToken, ts.SyntaxKind.GreaterThanToken, ts.SyntaxKind.LessThanEqualsToken, ts.SyntaxKind.GreaterThanEqualsToken,
    ts.SyntaxKind.InstanceOfKeyword, ts.SyntaxKind.InKeyword,
  ])
  /** The strings a save can write into a field, each with where it is written: a string literal; each branch of a
      condition and each side of `||`, `??` or `&&`; what a same-file const holds; and a function's own parameter, read
      as its default, as what each call of the function in the file hands it, and, for a control's callback, as the
      values the control offers. A boolean, a number, null or undefined offers none, and neither does a value whose
      operator makes it a boolean (`!x`, a comparison). Anything else fails the scan, with its place: a `let`, a value
      kept in React state, an import, a member (`e.target.value` is not the callback's own parameter), a call, a
      template with a substitution, and a parameter of a function no call in the file and no control hands a value.
      `seen` stops a const or a parameter read twice, a cycle among them included. */
  const refuseValue = (node: ts.Node): [] => {
    const entry = `${file}:${line(node)} ${node.getText(source).replace(/\s+/g, ' ')} (a value a save writes that this scan cannot read)`
    if (!unreadable.includes(entry)) unreadable.push(entry)
    return []
  }
  const savedValues = (value: ts.Expression, seen = new Set<ts.Node>()): Array<[text: string, at: ts.Node]> => {
    const inner = bare(value)
    const unread = (node: ts.Node = inner) => refuseValue(node)
    if (ts.isStringLiteral(inner) || ts.isNoSubstitutionTemplateLiteral(inner)) return [[inner.text, inner]]
    const kind = inner.kind
    if (kind === ts.SyntaxKind.TrueKeyword || kind === ts.SyntaxKind.FalseKeyword || kind === ts.SyntaxKind.NullKeyword || ts.isNumericLiteral(inner) || ts.isBigIntLiteral(inner) || ts.isVoidExpression(inner)) return []
    if (ts.isPrefixUnaryExpression(inner)) {
      const signed = (inner.operator === ts.SyntaxKind.MinusToken || inner.operator === ts.SyntaxKind.PlusToken) && ts.isNumericLiteral(bare(inner.operand))
      return inner.operator === ts.SyntaxKind.ExclamationToken || signed ? [] : unread()
    }
    if (ts.isConditionalExpression(inner)) return [...savedValues(inner.whenTrue, seen), ...savedValues(inner.whenFalse, seen)]
    if (ts.isBinaryExpression(inner)) {
      const op = inner.operatorToken.kind
      if (BOOLEAN.has(op)) return []
      if (LOGICAL.has(op)) return [...savedValues(inner.left, seen), ...savedValues(inner.right, seen)]
      return op === ts.SyntaxKind.CommaToken ? savedValues(inner.right, seen) : unread()
    }
    if (!ts.isIdentifier(inner)) return unread()
    const decl = resolve(inner)?.decl
    if (!decl) return inner.text === 'undefined' ? [] : unread()
    if (seen.has(decl)) return []
    seen.add(decl)
    if (ts.isVariableDeclaration(decl) && ts.isIdentifier(decl.name) && decl.initializer && decl.parent.flags & ts.NodeFlags.Const) {
      return savedValues(decl.initializer, seen)
    }
    if (!ts.isParameter(decl) || !ts.isIdentifier(decl.name) || decl.dotDotDotToken) return unread()
    const fn = decl.parent
    const index = fn.parameters.indexOf(decl)
    const calls = callsOf.get(fn) ?? []
    if (!calls.length && !callbacks.has(fn)) return unread()
    const values = decl.initializer ? savedValues(decl.initializer, seen) : []
    for (const call of calls) {
      const arg = call.arguments[index]
      if (call.arguments.slice(0, index + 1).some(ts.isSpreadElement)) unread(call)
      else if (arg) values.push(...savedValues(arg, seen))
    }
    return values
  }

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
              const spread = objectsIn(prop.expression)
              if (depth < 8) for (const inner of spread) update(inner, depth + 1)
              else if (spread.length) pastReach(prop, 'an update spread')
              continue
            }
            const key = propertyKey(prop.name)
            if (key !== undefined) fields.set(key, line(prop))
            // Each value it writes there, read where it is written (savedValues); a method or an accessor computes one.
            const value = ts.isPropertyAssignment(prop) ? prop.initializer : ts.isShorthandPropertyAssignment(prop) ? prop.name : undefined
            for (const [text, at] of value ? savedValues(value) : refuseValue(prop)) options.set(text, line(at))
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
  // Every container the scan read through a name: nothing may change it after its initializer (a write would save a field or
  // offer a value the scan never saw). Its read sites are reads: an update a save sends (a same-file function it is handed to
  // is followed into its parameter) and an options prop.
  const sends = (use: ts.Expression) => {
    const call = use.parent
    if (!ts.isCallExpression(call) || !call.arguments.includes(use) || !savesHere(call)) return false
    const callee = bare(call.expression)
    return !(ts.isIdentifier(callee) && resolve(callee))
  }
  const offers = (use: ts.Expression) => ts.isJsxExpression(use.parent) && ts.isJsxAttribute(use.parent.parent) && use.parent.parent.name.getText(source) === 'options'
  for (const [container, name] of followed) {
    const escaped = containerEscape(container, source, resolve, { reads: (use) => sends(use) || offers(use) })
    if (escaped) unreadable.push(`${file}:${line(container)} ${name} (a container that can change after its initializer: ${escaped.how}, line ${line(escaped.at)})`)
  }
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
      // An entry of an options array written after its initializer (#1370's seventh round): loud, through a .map or a prop.
      "const CHOICES2 = [{ value: 'choice_written' }]",
      "CHOICES2[0].value = 'choice_extra'",
      'export const O = () => <select>{CHOICES2.map((c) => <option key={c.value} value={c.value}>{c.value}</option>)}</select>',
      "const PERIODS2 = [{ value: 'period_written', label: 'W' }]",
      "PERIODS2[0].value = 'period_extra'",
      'export const P = () => <SegmentedControl label="p" options={PERIODS2} value={prefs.p} onChange={() => {}} />',
      // A name binds to its own declaration (Codex on 74fe2f53): Q reads the module's SHADOWED, R its own.
      "const SHADOWED = [{ value: 'shadow_outer', label: 'Outer' }]",
      'export const Q = () => <SegmentedControl label="q" options={SHADOWED} value={prefs.q} onChange={() => {}} />',
      "export const R = () => { const SHADOWED = [{ value: 'shadow_inner', label: 'Inner' }]; return <SegmentedControl label=\"r\" options={SHADOWED} value={prefs.r} onChange={() => {}} /> }",
    ].join('\n')
    const { options, unreadable } = formPreferences('fixture.tsx', fixture)
    expect([...options.keys()].sort()).toEqual([
      'annual', 'biweekly', 'choice_written', 'daily', 'fortnightly', 'hourly', 'immediate', 'interim', 'monthly', 'never', 'period_written', 'quarterly',
      'shadow_inner', 'shadow_outer', 'weekly', 'yearly',
    ])
    expect(unreadable).toEqual([
      'fixture.tsx:7 <option value={v}>',
      'fixture.tsx:8 <option value={x}>',
      'fixture.tsx:16 <SegmentedControl options={load()}>',
      "fixture.tsx:17 <SegmentedControl options={[{ value: v, label: 'V' }]}>",
      'fixture.tsx:18 <option value={prefs.digest}>',
      'fixture.tsx:19 CHOICES2[0] (a container that can change after its initializer: an entry assigned, line 20)',
      'fixture.tsx:22 PERIODS2[0] (a container that can change after its initializer: an entry assigned, line 23)',
    ])
  })

  it('reads every value a save writes into a field, and refuses one it cannot read (self-check)', () => {
    // The value half of the review of 8fb22fbe, re-run on 28b69145 and 3ebe222b: a same-file const, a value kept in
    // React state, a `let` and an import each offered a value the scan neither read nor refused. Each form saves into
    // a field of its own, tagged with the values it offers, or with the form the scan must refuse.
    const VALUES: Array<[code: string, offers?: string[], refused?: string]> = [
      ["import { CHOICE } from './choices'"],
      ["const WEEKLY = 'zz_weekly'"],
      ["const BASE = 'zz_alias'"],
      ['const ALIAS = BASE'],
      ['export function Form({ on }: { on: boolean }) {'],
      ["  const [v_state, setState] = useState('zz_state_initial')"],
      ["  let pick = 'zz_let'"],
      // A saver's own parameter takes what each call hands it; a control's callback, also what the control offers.
      ['  const choose = (v: string) => save({ v_param: v })'],
      ['  const onPick = (v: string) => save({ v_both: v })'],
      ['  const orphan = (v: string) => save({ v_orphan: v })', [], 'v'],
      ['  return ('],
      ['    <>'],
      // Chief design's probes: a same-file const (and a const holding one), React state, a `let`, an import.
      ['      <button onClick={() => save({ v_const: WEEKLY })}>Weekly</button>', ['zz_weekly']],
      ['      <button onClick={() => save({ v_alias: ALIAS })}>Alias</button>', ['zz_alias']],
      ["      <button onClick={() => { setState('zz_state'); save({ v_state }) }}>State</button>", [], 'v_state'],
      ['      <button onClick={() => save({ v_let: pick })}>Let</button>', [], 'pick'],
      ['      <button onClick={() => save({ v_import: CHOICE })}>Import</button>', [], 'CHOICE'],
      // A control callback's own parameter: the control's options carry its values.
      ["      <SegmentedControl label=\"Seg\" options={[{ value: 'zz_seg', label: 'Seg' }]} value={prefs.v_callback} onChange={(v) => save({ v_callback: v })} />", ['zz_seg']],
      ["      <button onClick={() => choose('zz_param')}>Param</button>", ['zz_param']],
      ["      <SegmentedControl label=\"Both\" options={[{ value: 'zz_both_option', label: 'B' }]} value={prefs.v_both} onChange={onPick} />", ['zz_both_option']],
      ["      <button onClick={() => onPick('zz_both_direct')}>Direct</button>", ['zz_both_direct']],
      // A member of the callback's parameter is not the parameter; a template with a substitution; a branch the scan
      // cannot read beside one it can.
      ['      <select onChange={(e) => save({ v_member: e.target.value })}><option value="zz_member">M</option></select>', ['zz_member'], 'e.target.value'],
      ['      <button onClick={() => save({ v_template: `${WEEKLY}ly` })}>Template</button>', [], '`${WEEKLY}ly`'],
      ["      <button onClick={() => save({ v_branch: on ? 'zz_branch' : pick })}>Branch</button>", ['zz_branch'], 'pick'],
      // A boolean, a number or null offers no choice, and neither does a value an operator makes a boolean.
      ["      <button onClick={() => save({ v_not: !on, v_compared: pick === 'x', v_true: true, v_null: null, v_number: -1 })}>Flags</button>"],
      ['    </>'],
      ['  )'],
      ['}'],
    ]
    const { fields, options, unreadable } = formPreferences('fixture.tsx', VALUES.map(([code]) => code).join('\n'))
    expect([...fields.keys()].sort()).toEqual([
      'v_alias', 'v_both', 'v_branch', 'v_callback', 'v_compared', 'v_const', 'v_import', 'v_let', 'v_member', 'v_not', 'v_null', 'v_number', 'v_orphan',
      'v_param', 'v_state', 'v_template', 'v_true',
    ])
    expect([...options.keys()].sort()).toEqual(VALUES.flatMap(([, offers = []]) => offers).sort())
    expect(unreadable).toEqual(
      VALUES.flatMap(([, , refused], index) => (refused === undefined ? [] : [`fixture.tsx:${index + 1} ${refused} (a value a save writes that this scan cannot read)`])),
    )
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
      // A container the scan reads through a name, written after its initializer (#1370's seventh round): an update a save
      // sends, an options array, an object of savers. Each fails loudly; the scan still reads what the initializer holds.
      ['  const update3 = { f_written_update: true }', ['f_written_update']],
      ['  update3.f_written_extra = true'],
      ["  const OFFERED = ['offered_written']"],
      ["  OFFERED.push('offered_extra')"],
      ['  const acts = { send: (u: Update) => save(u) }'],
      ['  acts.extra = true'],
      ['  const hooked = useNoop()'],
      ['  const update4 = { f_rebound_update: true }', ['f_rebound_update']],
      ['  hooked.keep = (u: Update) => save(u)'],
      // Past a walk's eight steps (#1370's eighth round), each loud with the place it stopped: Codex's saver nine wrappers
      // deep on 3ebe222b, a cycle of consts read as an object (a save sends it) and as an array (a pattern takes it apart),
      // and an update that spreads itself.
      ['  const persistDeep = w1(w2(w3(w4(w5(w6(w7(w8(w9((u: Update) => save(u))))))))))'],
      ['  const loopA = loopB'],
      ['  const loopB = loopA'],
      ['  const [fromLoop] = loopA'],
      ['  const spreadLoop = { f_spread_loop: true, ...spreadLoop }', ['f_spread_loop']],
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
      ['      <button onClick={() => persist(update3)}>Written</button>'],
      ['      <select>{OFFERED.map((o) => <option key={o} value={o}>{o}</option>)}</select>'],
      ['      <button onClick={() => acts.send({ f_acts_saved: true })}>Acts</button>', ['f_acts_saved']],
      ['      <button onClick={() => persistOther(update4)}>Rebound</button>'],
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
      // Out of reach too: an object a same-file hook returns, written after the call (its returned object is read as the hook
      // writes it).
      ['      <button onClick={() => hooked.keep({ f_gap_hook_write: true })}>Hooked</button>', [], ['f_gap_hook_write']],
      // Past a walk's reach: the saver nine wrappers deep is never found, so its field stays unread, loudly.
      ['      <button onClick={() => persistDeep({ f_gap_deep_wrapper: true })}>Deep</button>', [], ['f_gap_deep_wrapper']],
      ['      <button onClick={() => persist(loopA)}>Loop</button>'],
      ['      <button onClick={() => persist(spreadLoop)}>Spread loop</button>'],
      ['    </Prefs19>'],
      ['    </PrefsContext.Provider>'],
      ['  )'],
      ['}'],
      ['function persistDecl(u: Update) { mutation.mutate(u) }'],
      ['function usePersist() { return (u: Update) => save(u) }'],
      ['function useActions() { return { keep: (u: Update) => save(u) } }'],
      ['function useNoop() { return { keep: (u: Update) => u } }'],
      ['function persistOther(u: Update) { u = { f_rebound_extra: true }; save(u) }'],
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
    expect([...options.keys()].sort()).toEqual(['hourly', 'monthly', 'never', 'offered_written', 'weekly'])
    // The current preference as an option's value still offers no literal (0662fdcf); a context provider's value is no choice.
    // Each written container is loud, with what its write does and where.
    const lineWith = (needle: string) => FORMS.findIndex(([code]) => code.includes(needle)) + 1
    const written = (name: string, how: string, at: string) =>
      `fixture.tsx:${lineWith(`const ${name} =`)} ${name} (a container that can change after its initializer: ${how}, line ${lineWith(at)})`
    // A walk past its eight steps is loud where it stopped: the saver's arrow, the ninth value the wrappers hold; the cycle's
    // const the ninth step lands on, from each const's own value (as an object) and from the pattern (as an array), the save
    // of loopA stopping where loopB's value does; and the spread the update walk reaches ninth.
    const past = (needle: string, form: string, what: string) => `fixture.tsx:${lineWith(needle)} ${form} (${what} through more steps than this reader follows)`
    expect(unreadable).toEqual([
      past('const persistDeep =', '(u: Update) => save(u)', 'a function held'),
      past('const loopA =', 'loopB', 'an object held'),
      past('const loopA =', 'loopB', 'an array held'),
      past('const loopB =', 'loopA', 'an object held'),
      `fixture.tsx:${lineWith('<option value={prefs.f_option}>')} <option value={prefs.f_option}>`,
      past('const spreadLoop =', '...spreadLoop', 'an update spread'),
      written('acts', 'an entry assigned', 'acts.extra'),
      written('update3', 'an entry assigned', 'update3.f_written_extra'),
      // A same-file saver that sends another object than the one it is handed (its parameter reassigned).
      written('update4', 'the name that holds it assigned', 'function persistOther'),
      written('OFFERED', 'a method called on it', 'OFFERED.push'),
    ])
    // The gating the response fills from the entitlements is no setting: the update model takes none of it.
    expect([...DERIVED], 'the response fills the two gates from the entitlements').toEqual(expect.arrayContaining(['eightk_available', 'realtime_available']))
    expect([...DERIVED].filter((field) => SETTABLE.has(field)), 'a field the user can set is a preference, never gating').toEqual([])
    expect(SETTABLE.has('digest'), 'the update model is read').toBe(true)
  })

  it('leaves a prop an element factory hands to lint, which refuses the factory: elements-built-with-jsx (Codex on 44229515)', { timeout: 30_000 }, async () => {
    // Codex's form: React.createElement hands the prefs value to a same-file component, whose field the scan never
    // reads. The scan follows a prop a tag hands (`<Rows source={prefs} />`); it does not read a factory, since the
    // lint rule elements-built-with-jsx (eslint.designRules.mjs) refuses every factory in app code, this one included.
    const factory = [
      "import React from 'react'",
      'export default function Form() {',
      '  const { data: prefs } = useQuery(q)',
      '  return <div>{React.createElement(Reader, { source: prefs })}</div>',
      '}',
      'function Reader({ source }: { source: { f_factory: boolean } }) { return <Toggle checked={source.f_factory} /> }',
      '',
    ].join('\n')
    expect([...formPreferences('fixture.tsx', factory).fields.keys()], 'not reached by the scan').toEqual([])
    const [linted] = await new ESLint({ cwd: frontendDir }).lintText(factory, { filePath: path.join(frontendDir, FORM) })
    expect(linted.messages.filter((m) => m.ruleId === 'earningsnerd/elements-built-with-jsx').map((m) => `${m.line} ${m.message.split(':')[0]}`), 'refused by lint').toEqual([
      '4 React.createElement',
    ])
  })

  it('every field the form renders or saves is read as prefs.<field> by the jobs', () => {
    const unread = [...form.fields].filter(([field]) => !readsField(consumerCode, field))
    expect(unread.map(([field, at]) => `${FORM}:${at} ${field} has no reader the jobs reach in ${CONSUMERS.join(', ')}`)).toEqual([])
  })

  it('every value the form offers is a literal the jobs act on, and the scan reads each one', () => {
    expect(
      form.unreadable,
      'write each value as a literal or through a .map over a literal array, save a literal, a same-file const or what a control hands its callback, keep what the scan reads through (an update, an object of savers, an options array) unchanged after its initializer, and within eight steps of where it is used',
    ).toEqual([])
    const unread = [...form.options].filter(([value]) => !hasLiteral(consumerCode, value))
    expect(unread.map(([value, at]) => `${FORM}:${at} option "${value}" has no reader the jobs reach in ${CONSUMERS.join(', ')}`)).toEqual([])
  })
})
