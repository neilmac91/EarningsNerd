import { readFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Config } from 'tailwindcss'
import resolveConfig from 'tailwindcss/resolveConfig'
import ts from 'typescript'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { Badge, buttonVariants, type BadgeVariant, type ButtonVariant } from '@/components/ui'
import { HEADLINES } from '@/features/marketing/lib/headline'

/**
 * Three brand rules as gates (CLAUDE.md rule 12; docs/brand/06-system.md §6; docs/voice-and-style.md
 * › Claims), read from the source the way landing-sections-mounted.spec.ts reads app/page.tsx:
 *
 * 1. Scope stays on matching claims. The server checks only some figures (a mapped concept of at
 *    least $1M: backend/app/services/provenance_service.py, build_metric_source), so shipped copy
 *    never says "each figure" or "every figure" without the scope beside it ("checkable", "where
 *    they can be", "the server can check"). The 2026-10-11 review caught a voice pass that had
 *    deleted that scope in nine places. Two siblings keep the other scopes: 1b, the outline is "up
 *    to nine parts"; 1c, only risk excerpts are promised as located or withheld.
 * 2. Sage never colours a number, anywhere in the app (DESIGN.md › the Separate Signals Rule;
 *    docs/brand/decisions-log.md D-030, the founder's call of 2026-10-11: the strict reading holds
 *    inside the product as on the public surfaces). Nothing an element renders in sage ink at rest
 *    may carry a digit or a value (SEC form codes such as "10-K" are names, and the device's citation
 *    brackets, "[1]" and "[F1]", are not numbers). A digit counts written inline (a template's
 *    substitutions included) or held in a same-file literal or JSX and reached through the file's
 *    own bindings: a variable (its initializer and every value the file assigns it, destructured or
 *    not), a field, an index, a destructured name and its default, a loop's variable, and a
 *    function's parameter, which takes its default and what the file's own calls hand it (an
 *    argument in its place, or the members an array method hands its callback, written inline or
 *    held in a name); a call holds and renders what its callbacks, its own same-file function or a
 *    useMemo returns. Arrays and objects are read through a spread, an object's values, keys and
 *    entries, a call that keeps its members or returns one (slice, filter, a Set, Array.from; at,
 *    find), a map's returns and a join. A key the scan cannot read may land on any member, so every
 *    member is read; a parameter bound at several calls takes every call's value, so a function that
 *    renders it in sage fails on any call that hands it a digit; and a binding the walk meets again
 *    (a function that hands a parameter to itself) ends there.
 *    Sage ink is any brand-family colour token, with or without an opacity modifier, in a state the
 *    element can rest in (dark:, a breakpoint, aria-*, data-*, disabled:, visited:, focus:); hover:
 *    and active: and their group- and peer- forms are activity under the pointer, sage's other job,
 *    so a control may turn sage under the pointer while its count rests in the ink, and keyboard
 *    focus draws the sage ring, not a sage count. The ink comes from the className at the call site
 *    (inline, or a same-file variable wherever it stands in the expression, through the variables it
 *    is built from, and a helper's parameter through the file's calls; a variable read by a key or
 *    called is read whole, any class it holds counting), from a variant component (Button,
 *    RetryButton, MarketingCta and Badge, each variant's colour asked of the component itself, and
 *    buttonVariants() in a className likewise; a variant the scan cannot read counts as sage), or
 *    from an app component followed through the checker: one that renders its children in sage is a
 *    sage element, and one that renders a number in the ink it inherits (what a same-file helper
 *    returns included) fails inside a sage parent, or given sage where it is used when it hands that
 *    className to the element it returns. A value is read through the type checker (one program from
 *    tsconfig.json): a number- or bigint-typed expression or an array of them (whole or joined), a
 *    template or a call fed one (a formatter, and so also a lookup such as labelFor(i) or a helper
 *    that builds a label), a number's own method, a same-file variable holding one, a parameter the
 *    file's calls hand one (by the type of what each call gives it, whatever the parameter's own
 *    type), or what a callback or a same-file function returns, through conditionals, `||`, `??`,
 *    the right of `&&` (and its left when that can be a number, which renders a 0) and JSX
 *    branches; a comparison is a boolean and renders nothing. A citation
 *    whose bracket is its whole text ("[{n}]") and a link that renders its own address are text. The
 *    count control (frontend/DESIGN_SYSTEM.md) is the second check: a control that rests in sage, its
 *    own or the element's around it, never holds its count in a span of its own ink, written inline,
 *    held in a same-file variable, or returned by a same-file function its label calls or maps with
 *    (its props are not its label). The planted forms in tests/unit/fixtures/brandRule2Forms.tsx, one
 *    per way the rule can be broken, per look-alike that must pass and per known gap, are scored on
 *    every run, so the gate's reach is held as well as its verdict on the app. Out of a source scan's
 *    reach, and so review-checked (the fixture marks each as a gap): a value held in a string (a date
 *    or an index name computed as text, or any value the server or the model sends as text) or
 *    written in words; a value bound outside the file's own calls (a component's prop, which JSX
 *    binds and the component check reads only for its children and className, a hook's state, a
 *    callback handed through another function's parameter); a count a component renders in its own
 *    ink inside a sage control, sage handed to a component through a prop other than className, a
 *    component's own ink that a call-site className joins (cx joins without merging, so CSS order
 *    decides), and a conditional written in a literal's field, read as written since the scan cannot
 *    tie it to the element's other fields; beyond the fixture, a literal another file holds, a colour
 *    set by an inline style or on a pseudo-element, a library component's internals, and SVG text
 *    coloured by attribute (the chart theme, which carries no sage). The waitlist counter's own spec
 *    covers the count on the public pages.
 * 3. The Marked Copy Rule (DESIGN.md › Graphic device): the highlight (`en-mark`) never sits on a
 *    figure or a price, the hero's accent phrases included; the margin (`en-margin`) exists only
 *    inside MarkedCopy, and every MarkedCopy carries at least one marker (`EnRef`).
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

const FILES = SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))
/** Rule 2's planted forms: one component per way the rule can be broken or a look-alike must pass, each
 *  marked flag, clean or gap. Read in the same program as the app and scored by the last rule 2 test, so a
 *  change to the gate that loses a form, or catches a look-alike, fails here. Outside the scan roots. */
const FORMS = path.join(ROOT, 'tests/unit/fixtures/brandRule2Forms.tsx')
/** One program over the scanned files, so rule 2 can ask the checker what an expression renders (a
 *  number, a template with a number in it, a formatter fed a number), not only what its literals say.
 *  This build is the suite's slowest import (about 11 s on a laptop, outside any test's timeout): the
 *  price of seeing a runtime count a source scan cannot; skipLibCheck is set, and nothing else trims
 *  it without losing the checker, so do not fold it back into a regex. */
const TSCONFIG = ts.readConfigFile(path.join(ROOT, 'tsconfig.json'), ts.sys.readFile)
const PARSED = ts.parseJsonConfigFileContent(TSCONFIG.config, ts.sys, ROOT)
const PROGRAM = ts.createProgram([...FILES, FORMS], { ...PARSED.options, noEmit: true, skipLibCheck: true })
const CHECKER = PROGRAM.getTypeChecker()
/** The surfaces a stranger meets before signing in, where the brand brief's strict reading holds. */
const PUBLIC_SURFACES = [
  'app/page.tsx', 'app/not-found.tsx', 'app/waitlist/', 'app/pricing/', 'app/login/', 'app/register/', 'app/forgot-password/',
  'features/marketing/', 'features/waitlist/', 'features/auth/components/',
  'components/Header.tsx', 'components/Footer.tsx', 'components/CookieConsent.tsx',
]
const isPublic = (rel: string) => PUBLIC_SURFACES.some((prefix) => (prefix.endsWith('/') ? rel.startsWith(prefix) : rel === prefix))
const SOURCES = FILES.map((file) => {
  const sf = PROGRAM.getSourceFile(file)
  if (!sf) throw new Error(`${file} is not in the program`)
  return { rel: path.relative(ROOT, file).split(path.sep).join('/'), sf }
})

const where = (rel: string, sf: ts.SourceFile, node: ts.Node, text: string) =>
  `${rel}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1} ${JSON.stringify(text.trim().slice(0, 80))}`

function visit(node: ts.Node, fn: (n: ts.Node) => void) {
  fn(node)
  ts.forEachChild(node, (child) => visit(child, fn))
}

/** The literal text a node carries, or null. */
function literalText(node: ts.Node): string | null {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isJsxText(node)) return node.text
  if (ts.isTemplateExpression(node)) return [node.head.text, ...node.templateSpans.map((span) => span.literal.text)].join(' ')
  if (ts.isNumericLiteral(node)) return node.text
  return null
}

const unwrap = (e: ts.Expression): ts.Expression =>
  ts.isAsExpression(e) || ts.isSatisfiesExpression(e) || ts.isParenthesizedExpression(e) || ts.isNonNullExpression(e) ? unwrap(e.expression) : e

/** Calls that return some of their receiver's own members, so a map over one walks the receiver's members. */
const KEEPS_MEMBERS = new Set(['slice', 'filter', 'toSorted', 'toReversed', 'sort', 'reverse'])
/** Calls that return one of their receiver's members, read as an index: `at(0)` by its index, the others as a key
    the scan cannot read. */
const ONE_MEMBER = new Set(['at', 'find', 'findLast'])
/** Calls whose members are what their callback returns, and the call that renders every member as text. */
const MAPS = new Set(['map', 'flatMap'])
const JOINS = new Set(['join'])
/** The array methods that hand a callback the array's members, and the parameter each member lands in. */
const HANDS_MEMBERS = new Map<string, number>([
  ...['map', 'flatMap', 'forEach', 'filter', 'find', 'findLast', 'findIndex', 'findLastIndex', 'some', 'every'].map((m) => [m, 0] as const),
  ['reduce', 1], ['reduceRight', 1],
])

/** A useMemo call (`useMemo(…)`, `React.useMemo(…)`), which holds what its callback returns. */
const isUseMemo = (call: ts.CallExpression) =>
  (ts.isIdentifier(call.expression) ? call.expression : ts.isPropertyAccessExpression(call.expression) ? call.expression.name : undefined)?.text === 'useMemo'

/** A step into a literal: a property's name, a member's index, or null for a key the scan cannot read. */
type Step = string | number | null

/** The same-file functions an expression names: one written inline, or the one a name, a field or a method holds,
    through the checker (every function a variable is given, its initializer and each assignment, or the one a
    wrapper such as useCallback or memo is given), on either branch of a conditional, `??` or `||`. Each
    expression is read once. */
const FUNCTIONS = new Map<ts.Node, ts.FunctionLikeDeclaration[]>()
function functionsOf(e: ts.Expression): ts.FunctionLikeDeclaration[] {
  let found = FUNCTIONS.get(e)
  if (!found) FUNCTIONS.set(e, (found = functionsNamed(e, new Set())))
  return found
}
function functionsNamed(e: ts.Expression, seen: Set<ts.Node>): ts.FunctionLikeDeclaration[] {
  const x = unwrap(e)
  if (ts.isArrowFunction(x) || ts.isFunctionExpression(x)) return [x]
  if (ts.isConditionalExpression(x)) return [x.whenTrue, x.whenFalse].flatMap((branch) => functionsNamed(branch, seen))
  if (ts.isBinaryExpression(x) && [ts.SyntaxKind.QuestionQuestionToken, ts.SyntaxKind.BarBarToken].includes(x.operatorToken.kind)) {
    return [x.left, x.right].flatMap((side) => functionsNamed(side, seen))
  }
  // A field or a method is a same-file function only on a same-file object, so the checker is asked for the field
  // only then: asking it of `rows.map` would type `rows`, at every call in the file. A field read by a literal key
  // (`R['chip']`) names that field; any other key names nothing the scan can read.
  if (ts.isPropertyAccessExpression(x) || ts.isElementAccessExpression(x)) {
    let root = unwrap(x.expression)
    while (ts.isPropertyAccessExpression(root) || ts.isElementAccessExpression(root)) root = unwrap(root.expression)
    const object = ts.isIdentifier(root) ? CHECKER.getSymbolAtLocation(root)?.valueDeclaration : undefined
    if (!object || !ts.isVariableDeclaration(object) || object.getSourceFile() !== x.getSourceFile()) return []
  }
  const name = ts.isIdentifier(x) ? x : ts.isPropertyAccessExpression(x) ? x.name
    : ts.isElementAccessExpression(x) && ts.isStringLiteralLike(x.argumentExpression) ? x.argumentExpression : undefined
  const declaration = name && CHECKER.getSymbolAtLocation(name)?.valueDeclaration
  if (!declaration || declaration.getSourceFile() !== x.getSourceFile() || seen.has(declaration)) return []
  seen.add(declaration)
  if (ts.isFunctionDeclaration(declaration) || ts.isMethodDeclaration(declaration)) return [declaration]
  if (ts.isPropertyAssignment(declaration)) return functionsNamed(declaration.initializer, seen)
  if (!ts.isVariableDeclaration(declaration)) return []
  return variableValues(declaration).flatMap((v) => {
    if (v.steps.length) return []
    const value = unwrap(v.value)
    return functionsNamed(ts.isCallExpression(value) && value.arguments[0] ? value.arguments[0] : value, seen)
  })
}

/** A call that binds a same-file function's parameters: its arguments, by position, or the array whose members it
    hands the parameter at `at`. */
interface Site { args?: ts.NodeArray<ts.Expression>; members?: ts.Expression; at?: number }
const SITES = new Map<ts.SourceFile, Map<ts.Node, Site[]>>()
/** Where a function's parameters take their values, indexed once per file: every call that names it, every array
    method it is handed to (`rows.map(render)`, its callback written inline or named, the members landing where
    HANDS_MEMBERS says), and Array.from's mapper (its source's members). A component's props come from JSX, which
    the component check reads (its children and className), so a tag is no call here. */
function sitesOf(fn: ts.Node): Site[] {
  const sf = fn.getSourceFile()
  let sites = SITES.get(sf)
  if (!sites) {
    const index = new Map<ts.Node, Site[]>()
    const add = (f: ts.Node, site: Site) => index.set(f, [...(index.get(f) ?? []), site])
    visit(sf, (n) => {
      if (!ts.isCallExpression(n)) return
      const callee = unwrap(n.expression)
      if (ts.isPropertyAccessExpression(callee)) {
        const at = HANDS_MEMBERS.get(callee.name.text)
        if (at !== undefined && n.arguments[0]) for (const f of functionsOf(n.arguments[0])) add(f, { members: callee.expression, at })
        if (callee.name.text === 'from' && ts.isIdentifier(callee.expression) && callee.expression.text === 'Array' && n.arguments[1]) {
          for (const f of functionsOf(n.arguments[1])) add(f, { members: n.arguments[0], at: 0 })
        }
      }
      for (const f of functionsOf(callee)) add(f, { args: n.arguments })
    })
    SITES.set(sf, sites = index)
  }
  return sites.get(fn) ?? []
}

/** A value a name holds, and the steps from it to the name's place (`[label] = LABELS` holds LABELS at index 0). */
interface Held { value: ts.Expression; steps: Step[] }
const ASSIGNED = new Map<ts.SourceFile, Map<ts.Symbol, Held[]>>()
/** What a same-file variable holds: its initializer and every value the file assigns it (`label = 'Ready'` in a
    switch, `label += …`, or `[label] = …` and `({ label } = …)` destructured, a default in the pattern included),
    the assignments indexed once per file. */
function variableValues(declaration: ts.VariableDeclaration): Held[] {
  const sf = declaration.getSourceFile()
  let index = ASSIGNED.get(sf)
  if (!index) {
    const found = new Map<ts.Symbol, Held[]>()
    const add = (symbol: ts.Symbol | undefined, held: Held) => { if (symbol) found.set(symbol, [...(found.get(symbol) ?? []), held]) }
    const assign = (target: ts.Expression, value: ts.Expression, steps: Step[]): void => {
      const t = unwrap(target)
      if (ts.isIdentifier(t)) add(CHECKER.getSymbolAtLocation(t), { value, steps })
      else if (ts.isBinaryExpression(t) && t.operatorToken.kind === ts.SyntaxKind.EqualsToken) {
        assign(t.left, value, steps)
        assign(t.left, t.right, [])
      } else if (ts.isArrayLiteralExpression(t)) {
        t.elements.forEach((element, i) => { if (!ts.isSpreadElement(element) && !ts.isOmittedExpression(element)) assign(element, value, [...steps, i]) })
      } else if (ts.isObjectLiteralExpression(t)) {
        for (const property of t.properties) {
          if (ts.isPropertyAssignment(property)) assign(property.initializer, value, [...steps, keyOf(property.name)])
          else if (ts.isShorthandPropertyAssignment(property)) {
            const symbol = CHECKER.getShorthandAssignmentValueSymbol(property)
            add(symbol, { value, steps: [...steps, property.name.text] })
            if (property.objectAssignmentInitializer) add(symbol, { value: property.objectAssignmentInitializer, steps: [] })
          }
        }
      }
    }
    visit(sf, (n) => {
      if (!ts.isBinaryExpression(n)) return
      const operator = n.operatorToken.kind
      if (operator < ts.SyntaxKind.FirstAssignment || operator > ts.SyntaxKind.LastAssignment) return
      // A compound assignment (`+=`, `??=`) adds its right side; only `=` destructures.
      if (ts.isIdentifier(n.left)) add(CHECKER.getSymbolAtLocation(n.left), { value: n.right, steps: [] })
      else if (operator === ts.SyntaxKind.EqualsToken) assign(n.left, n.right, [])
    })
    ASSIGNED.set(sf, index = found)
  }
  const symbol = CHECKER.getSymbolAtLocation(declaration.name)
  return [...(declaration.initializer ? [{ value: declaration.initializer, steps: [] }] : []), ...((symbol && index.get(symbol)) ?? [])]
}

/** Where a name is bound: the variable or parameter its destructuring climbs to, the steps from that declaration's
    value to the name's place, and each default met on the way with the steps below it (a parameter's own default
    last); null for a rest element, which holds what the others leave. */
interface Binding { declaration: ts.Node | undefined; steps: Step[]; defaults: Held[] }
function bindingOf(symbol: ts.Symbol | undefined, path: Step[]): Binding | null {
  const steps = [...path]
  const defaults: Held[] = []
  let declaration: ts.Node | undefined = symbol?.valueDeclaration
  while (declaration && ts.isBindingElement(declaration)) {
    if (declaration.dotDotDotToken) return null
    if (declaration.initializer) defaults.push({ value: declaration.initializer, steps: [...steps] })
    const pattern = declaration.parent
    steps.unshift(ts.isObjectBindingPattern(pattern) ? keyOf(declaration.propertyName ?? declaration.name) : pattern.elements.indexOf(declaration))
    declaration = pattern.parent
  }
  if (declaration && ts.isParameter(declaration) && declaration.initializer) defaults.push({ value: declaration.initializer, steps: [...steps] })
  return { declaration, steps, defaults }
}

/** The literals an expression holds when it reads a same-file literal, through the file's own bindings: a
    variable's initializer and every value the file assigns it (`CONFIG.step`, `STEPS[0]`, `const first =
    STEPS[0]`, `let label` set in a switch or destructured into), a call's return (a same-file function's, or a
    useMemo's callback's), a destructured name with its default (`const { cls } = TONES[tone]
    ?? TONES.flat`, `({ step = 'Step 1' })`, `({ step: s })`, `([q])`), a for…of variable (the array's members) or
    a for…in one (the object's keys), and a parameter: its default, and whatever the file binds it to at
    `sitesOf`'s calls (an argument in its place, or the members of the array a method hands it, its callback
    written inline or named: `ARRAY.map((item) => …)`, `ARRAY.map(render)`, a nested map over an element's field
    included). Arrays and objects are read through a spread, a shorthand property through the name it holds, an
    object through Object.values, keys and entries, an array through a call that keeps its members (`slice`,
    `filter` …), a Set or Array.from, and a map through what its callback returns; a member through `at`, `find`
    and `findLast`, a join through every member it joins, and the chain through `??`, `||` and conditionals. A
    value written in a literal is read as written: a conditional there is not split, since the scan cannot tie it
    to the element's other fields (the pricing cards' call to action takes its button's variant and its label
    from the same plan). A key the scan cannot read (`LABELS[i]`, a computed key, `find`), or an index into an
    array with a spread or through such a call, may land on any member, so every member is read; a parameter the
    file binds at several calls takes every call's value, so a function that renders it in sage fails on any call
    that hands it a digit, and a binding met again on the way reads only its defaults, so a function that hands a
    parameter to itself ends in time. Names resolve through the checker, so an index, a shadowing binding, a prop
    or an import is never taken for a literal. */
const LITERALS = new Map<ts.Node, ts.Expression[]>()
function literalExpressions(e: ts.Expression, sf: ts.SourceFile, path: Step[] = []): ts.Expression[] {
  if (path.length) return walkLiterals(e, sf, path)
  let found = LITERALS.get(e)
  if (!found) LITERALS.set(e, (found = walkLiterals(e, sf, path)))
  return found
}
function walkLiterals(e: ts.Expression, sf: ts.SourceFile, path: Step[]): ts.Expression[] {
  const method = (v: ts.Expression, names: ReadonlySet<string>): v is ts.CallExpression & { expression: ts.PropertyAccessExpression } =>
    ts.isCallExpression(v) && ts.isPropertyAccessExpression(v.expression) && names.has(v.expression.name.text)
  const objectCall = (v: ts.Expression, name: string): v is ts.CallExpression =>
    ts.isCallExpression(v) && ts.isPropertyAccessExpression(v.expression) && ts.isIdentifier(v.expression.expression)
    && v.expression.expression.text === 'Object' && v.expression.name.text === name && v.arguments.length > 0
  // A call or a `new` that keeps what it is given: `Array.from(x)` without a mapper, `new Set(x)`.
  const keepsArgument = (v: ts.Expression): v is ts.CallExpression | ts.NewExpression =>
    (ts.isNewExpression(v) && ts.isIdentifier(v.expression) && v.expression.text === 'Set' && !!v.arguments?.length)
    || (ts.isCallExpression(v) && ts.isPropertyAccessExpression(v.expression) && ts.isIdentifier(v.expression.expression)
      && v.expression.expression.text === 'Array' && v.expression.name.text === 'from' && v.arguments.length === 1)
  // What an expression holds once the path is walked into it; `inLiteral` marks a value written in a literal.
  const held = (x: ts.Expression, path: Step[], depth: number, inLiteral = false): ts.Expression[] => {
    if (depth > 24) return []
    const at = unwrap(x)
    if (!inLiteral && ts.isConditionalExpression(at)) return [at.whenTrue, at.whenFalse].flatMap((branch) => held(branch, path, depth + 1))
    if (!inLiteral && ts.isBinaryExpression(at) && [ts.SyntaxKind.QuestionQuestionToken, ts.SyntaxKind.BarBarToken].includes(at.operatorToken.kind)) {
      return [at.left, at.right].flatMap((side) => held(side, path, depth + 1))
    }
    if (ts.isPropertyAccessExpression(at)) return held(at.expression, [at.name.text, ...path], depth + 1)
    if (ts.isElementAccessExpression(at)) return held(at.expression, [accessStep(at.argumentExpression), ...path], depth + 1)
    if (method(at, ONE_MEMBER)) {
      const index = at.arguments[0] && unwrap(at.arguments[0])
      const step = at.expression.name.text === 'at' && index && ts.isNumericLiteral(index) ? Number(index.text) : null
      return held(at.expression.expression, [step, ...path], depth + 1)
    }
    if (method(at, JOINS)) return path.length ? [] : held(at.expression.expression, [null], depth + 1)
    // A call holds what its same-file function returns (`build()`), and useMemo what its callback returns; a function
    // met again on the way (one that returns a call of itself) holds nothing more.
    if (ts.isCallExpression(at)) {
      const fns = [...functionsOf(at.expression), ...(isUseMemo(at) && at.arguments[0] ? functionsOf(at.arguments[0]) : [])]
      if (fns.length) {
        return fns.flatMap((fn) => {
          const key = `call:${fn.pos}:${JSON.stringify(path)}`
          if (reading.has(key)) return []
          reading.add(key)
          try {
            return returnedExpressions(fn).flatMap((r) => held(r, path, depth + 1))
          } finally {
            reading.delete(key)
          }
        })
      }
    }
    if (ts.isIdentifier(at)) return bound(CHECKER.getSymbolAtLocation(at), path, depth + 1)
    if (path.length === 0) return [at]
    const [step, ...rest] = path
    return into(at, step, depth + 1).flatMap((value) => held(value, rest, depth + 1, true))
  }
  // The bindings being read, by declaration and steps: one met again (a function that hands a parameter to itself,
  // a variable built from itself) reads only its defaults, so the walk ends in time linear in its calls.
  const reading = new Set<string>()
  // What a name holds: its defaults (`bindingOf`), then a variable's values, a loop's members or keys, or the values
  // the file binds a parameter to.
  const bound = (symbol: ts.Symbol | undefined, path: Step[], depth: number): ts.Expression[] => {
    const binding = bindingOf(symbol, path)
    if (!binding) return []
    const { declaration, steps } = binding
    const defaults = binding.defaults.flatMap((d) => held(d.value, d.steps, depth + 1))
    if (!declaration || declaration.getSourceFile() !== sf) return defaults
    const key = `${declaration.pos}:${JSON.stringify(steps)}`
    if (reading.has(key)) return defaults
    reading.add(key)
    try {
      if (ts.isVariableDeclaration(declaration)) {
        const loop = declaration.parent.parent
        if (ts.isForOfStatement(loop)) return [...defaults, ...members(loop.expression, depth + 1).flatMap((member) => held(member, steps, depth + 1, true))]
        if (ts.isForInStatement(loop)) {
          return [...defaults, ...(steps.length ? [] : pairs(loop.expression, depth + 1).map(([k]) => k).filter((k) => !ts.isOmittedExpression(k)))]
        }
        return [...defaults, ...variableValues(declaration).flatMap((v) => held(v.value, [...v.steps, ...steps], depth + 1))]
      }
      if (!ts.isParameter(declaration)) return defaults
      const at = declaration.parent.parameters.indexOf(declaration)
      return [...defaults, ...sitesOf(declaration.parent).flatMap((site) => {
        if (site.members) return site.at === at && !declaration.dotDotDotToken ? members(site.members, depth + 1).flatMap((member) => held(member, steps, depth + 1, true)) : []
        const args = site.args ?? []
        // A rest parameter holds the arguments from its place on, as an array.
        if (declaration.dotDotDotToken) return held(ts.factory.createArrayLiteralExpression(args.slice(at)), steps, depth + 1)
        // From a spread argument on, a place may hold any of what follows.
        const spread = args.findIndex(ts.isSpreadElement)
        if (spread !== -1 && at >= spread) {
          return args.slice(spread).flatMap((a) => (ts.isSpreadElement(a) ? held(a.expression, [null, ...steps], depth + 1) : held(a, steps, depth + 1)))
        }
        return args[at] ? held(args[at], steps, depth + 1) : []
      })]
    } finally {
      reading.delete(key)
    }
  }
  // The members of the arrays an expression holds: an array literal's, through a spread; a call's that keeps them,
  // or keeps what it is given; an object's values, keys or entries (each a [key, value] pair); a map's returns.
  const members = (x: ts.Expression, depth: number): ts.Expression[] =>
    held(x, [], depth + 1).flatMap((v) => {
      if (method(v, KEEPS_MEMBERS)) return members(v.expression.expression, depth + 1)
      if (keepsArgument(v)) return members(v.arguments![0], depth + 1)
      if (objectCall(v, 'values')) return held(v.arguments[0], [null], depth + 1)
      if (objectCall(v, 'keys')) return pairs(v.arguments[0], depth + 1).map(([key]) => key).filter((key) => !ts.isOmittedExpression(key))
      if (objectCall(v, 'entries')) {
        return pairs(v.arguments[0], depth + 1).flatMap(([key, values]) => values.map((value) => ts.factory.createArrayLiteralExpression([key, value])))
      }
      if (method(v, MAPS)) return mapped(v, depth + 1)
      if (!ts.isArrayLiteralExpression(v)) return []
      return v.elements.flatMap((m) => (ts.isSpreadElement(m) ? members(m.expression, depth + 1) : ts.isOmittedExpression(m) ? [] : [m]))
    })
  // What a map's callback returns, each a member, read as code (a conditional there is split); a flatMap's
  // returned arrays give their members.
  const mapped = (call: ts.CallExpression & { expression: ts.PropertyAccessExpression }, depth: number): ts.Expression[] =>
    callbackReturns(call).flatMap((r) => held(r, [], depth + 1)).flatMap((v) =>
      call.expression.name.text === 'flatMap' && ts.isArrayLiteralExpression(v) ? members(v, depth + 1) : [v])
  // An object's own keys, through a spread, each with the values it holds (`Object.keys`, `entries`, for…in); a
  // name written as an identifier becomes its text.
  const pairs = (x: ts.Expression, depth: number): [ts.Expression, ts.Expression[]][] =>
    held(x, [], depth + 1).filter(ts.isObjectLiteralExpression).flatMap((o) => o.properties.flatMap((property): [ts.Expression, ts.Expression[]][] => {
      if (ts.isSpreadAssignment(property)) return pairs(property.expression, depth + 1)
      const key = property.name ? keyOf(property.name) : null
      // A computed name the scan cannot read has no text to render; its value still counts.
      const text = key === null ? ts.factory.createOmittedExpression() : ts.factory.createStringLiteral(String(key))
      const values = ts.isPropertyAssignment(property) ? [property.initializer]
        : ts.isShorthandPropertyAssignment(property) ? bound(CHECKER.getShorthandAssignmentValueSymbol(property), [], depth + 1) : []
      return [[text, values]]
    }))
  // One step into a literal: an object's property, an array's member, or every property or member for a key the
  // scan cannot read or an index that may land on any member.
  const into = (v: ts.Expression, step: Step, depth: number): ts.Expression[] => {
    const lists = method(v, KEEPS_MEMBERS) || keepsArgument(v) || method(v, MAPS) || ['values', 'keys', 'entries'].some((name) => objectCall(v, name))
    if (lists) return step === null || typeof step === 'number' ? members(v, depth + 1) : []
    if (ts.isArrayLiteralExpression(v)) {
      if (step === null || v.elements.some(ts.isSpreadElement)) return typeof step === 'string' ? [] : members(v, depth + 1)
      const member = typeof step === 'number' ? v.elements[step] : undefined
      return member && !ts.isOmittedExpression(member) ? [member] : []
    }
    if (!ts.isObjectLiteralExpression(v)) return []
    // A computed name the scan cannot read may be the key asked for.
    const matches = (name: ts.PropertyName) => step === null || keyOf(name) === null || String(keyOf(name)) === String(step)
    return v.properties.flatMap((property) => {
      if (ts.isSpreadAssignment(property)) return held(property.expression, [step], depth + 1)
      if (ts.isPropertyAssignment(property) && matches(property.name)) return [property.initializer]
      if (ts.isShorthandPropertyAssignment(property) && matches(property.name)) {
        return bound(CHECKER.getShorthandAssignmentValueSymbol(property), [], depth + 1)
      }
      return []
    })
  }
  return held(e, path, 0)
}

/** The step a property or binding name reads: its text, a numeric name's index, a computed name's literal, or null
    for a computed name the scan cannot read. */
function keyOf(name: ts.PropertyName | ts.BindingName): Step {
  if (ts.isIdentifier(name) || ts.isStringLiteral(name) || ts.isPrivateIdentifier(name)) return name.text
  if (ts.isNumericLiteral(name)) return Number(name.text)
  if (ts.isComputedPropertyName(name)) {
    const key = unwrap(name.expression)
    return ts.isStringLiteral(key) || ts.isNoSubstitutionTemplateLiteral(key) ? key.text : ts.isNumericLiteral(key) ? Number(key.text) : null
  }
  return null
}

/** The literal texts `literalExpressions` finds, for an expression rendered in JSX: an array renders every member it
    holds (`{['Q1', 'Q2']}`, `{labels}`). */
function literalValues(e: ts.Expression, sf: ts.SourceFile, depth = 0): string[] {
  if (depth > 8) return []
  return literalExpressions(e, sf).flatMap((v) => {
    if (ts.isArrayLiteralExpression(v)) {
      return v.elements.flatMap((m) => (ts.isOmittedExpression(m) ? [] : literalValues(ts.isSpreadElement(m) ? m.expression : m, sf, depth + 1)))
    }
    const text = literalText(v)
    return text === null ? [] : [text]
  })
}

/** The nodes a className attribute is read from: its initializer, and the same-file variable behind every
    identifier in it, wherever the identifier stands (`className={cls}`, `className={cx(cls, on && hot)}`,
    `className={on ? SAGE : QUIET}`), each value it holds (its initializer and every assignment) followed
    through the variables it is built from, so a class string held in a const is read as if written inline. A
    variable read by a key or called (`TONE[tone]`, `cls(on)`) is read whole, so any class it holds counts: the
    scan cannot know the key, and fails closed. Any other name is read for the literals it holds
    (`literalExpressions`): one destructured from a const (`const { cls } = TONES[tone] ?? TONES.flat`), a map
    callback's element over a literal array (`TONES.map((t) => <span className={t.cls}>…)`), or a helper's
    parameter bound at the file's calls, with the fields read off it; a whole object or array it holds is not
    read as a class. The checker resolves each identifier, so a prop, a property name or an import is never
    taken for either. */
const CLASS_NODES = new Map<ts.Node, ts.Node[]>()
function classNameNodes(opening: ts.JsxOpeningLikeElement): ts.Node[] {
  let found = CLASS_NODES.get(opening)
  if (!found) CLASS_NODES.set(opening, (found = readClassName(opening)))
  return found
}
function readClassName(opening: ts.JsxOpeningLikeElement): ts.Node[] {
  const attr = opening.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText() === 'className')
  if (!attr?.initializer) return []
  const sf = opening.getSourceFile()
  const nodes: ts.Node[] = [attr.initializer]
  const follow = (node: ts.Node) =>
    visit(node, (n) => {
      if (!ts.isIdentifier(n) || (ts.isPropertyAccessExpression(n.parent) && n.parent.name === n)) return
      // The fields and keys read off the name (`t.cls`, `t.tone.cls`), so the literals are the ones it reads.
      let chain: ts.Expression = n
      while ((ts.isPropertyAccessExpression(chain.parent) || ts.isElementAccessExpression(chain.parent)) && chain.parent.expression === chain) chain = chain.parent
      const values = localValues(n, sf)
      // A whole object or array the name holds is no class; its fields are read where the className reads them.
      const literals = values.length ? values : literalExpressions(chain, sf).filter((v) => !ts.isObjectLiteralExpression(v) && !ts.isArrayLiteralExpression(v))
      for (const found of literals) {
        if (nodes.includes(found)) continue
        nodes.push(found)
        follow(found)
      }
    })
  follow(attr.initializer)
  return nodes
}

/** Every string a className attribute can produce, split into tokens. */
function classTokens(opening: ts.JsxOpeningLikeElement): string[] {
  const parts: string[] = []
  for (const node of classNameNodes(opening)) {
    visit(node, (n) => {
      const text = ts.isJsxText(n) ? null : literalText(n)
      if (text !== null) parts.push(text)
    })
  }
  return parts.join(' ').split(/\s+/).filter(Boolean)
}

type Ink = 'sage' | 'other' | null

/** A sage colour token: any colour of the brand family (`text-brand`, `-strong`, `-strong-dark`, …), with or
    without an opacity modifier (`text-brand-strong/70`), or the legacy accent-strong alias. `fill-` counts on
    SVG text, whose glyphs it paints. */
const SAGE = /^(?:text|fill)-(?:brand(?:-[a-z]+)*|accent-strong)(?:\/(?:\d+|\[[^\]]+\]))?$/
/** Utilities that share a colour's prefix and set no ink of their own: the theme's type sizes (read from
    tailwind.config.js, so a size added there is never read as a colour), an arbitrary length, alignment,
    overflow and wrapping, and the parent's own colour (`text-inherit`, `text-current`). */
const SIZES = Object.keys(resolveConfig(createRequire(import.meta.url)(path.join(ROOT, 'tailwind.config.js')) as Config).theme.fontSize)
const escapeRegExp = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const NOT_COLOUR = new RegExp(
  `^text-(?:${SIZES.map(escapeRegExp).join('|')})(?:/[\\w.[\\]-]+)?$`
    + '|^text-(?:left|center|right|justify|start|end|ellipsis|clip|wrap|nowrap|balance|pretty|inherit|current)$'
    + String.raw`|^text-\[(?:length:|[\d.]|(?:calc|clamp|min|max)\()|^fill-(?:none|current|inherit)$`,
)
/** Variants that apply only under the pointer (hover: and active:, and their group- and peer- forms: activity,
    sage's other job), and those that colour a pseudo-element rather than the element's own text. Every other
    variant is a state an element can rest in, so its colour counts: dark:, a breakpoint, aria-*, data-*,
    disabled:, open:, visited: (a link stays visited), target: (a section stays the fragment's target), and
    focus: in all its forms, since keyboard focus draws the sage ring and a focused control stays focused while
    it is read. A selected tab's sage count is a sage count. */
const ACTIVITY = /^(?:(?:group|peer)-)?(?:hover|active)(?:\/[\w-]+)?$|^\[.*:(?:hover|active)\b.*\]$/
const PSEUDO = /^(?:placeholder|file|marker|selection|before|after|first-letter|first-line|backdrop)$/
const SVG_TEXT = new Set(['text', 'tspan', 'textPath'])
const CITATION = /^\[F?\d+\]$/
/** SEC form codes are names, not values ("Open the 10-K", "10-Ks and 10-Qs"), as a form code read from a variable
    already is. A form whose code is a bare number is read as a form code only with its name before it
    ("Form 4"): a bare "4" is a count. */
const FORM_CODE = /\b(?:10-K|10-Q|8-K|20-F|40-F|6-K|11-K|S-1|S-3|S-4|S-8|F-1|F-3|DEF 14A|13F|Form [345])(?:\/A)?(?:s|['’]s)?\b/g
const carriesDigit = (text: string) => {
  const trimmed = text.trim()
  return !CITATION.test(trimmed) && /\d/.test(trimmed.replace(FORM_CODE, ''))
}

/** A class token's variants and utility, split on the colons outside brackets (`data-[state=open]:…`). */
function splitVariants(token: string): string[] {
  const parts: string[] = []
  let depth = 0
  let start = 0
  for (let i = 0; i < token.length; i++) {
    if (token[i] === '[') depth++
    else if (token[i] === ']') depth--
    else if (token[i] === ':' && depth === 0) { parts.push(token.slice(start, i)); start = i + 1 }
  }
  parts.push(token.slice(start))
  return parts
}

/** The resting text colour class tokens give an element: 'sage', 'other', or null when they set none. */
function tokenInk(tokens: string[], svgText = false): Ink {
  let ink: Ink = null
  for (const token of tokens) {
    const parts = splitVariants(token)
    const utility = parts.pop()!.replace(/^!/, '')
    if (!(utility.startsWith('text-') || (svgText && utility.startsWith('fill-'))) || NOT_COLOUR.test(utility)) continue
    if (parts.some((variant) => ACTIVITY.test(variant) || PSEUDO.test(variant))) continue
    if (SAGE.test(utility)) return 'sage'
    ink = 'other'
  }
  return ink
}

/** The scanned files and the planted forms, so a component is followed only into code the scan owns, never into a
    library. */
const SCANNED = new Set([...FILES, FORMS].map((file) => path.normalize(file)))

/** The declaration behind an identifier or a component tag, followed through imports and re-exports. */
function declarationOf(name: ts.Node): ts.Declaration | undefined {
  let symbol = CHECKER.getSymbolAtLocation(ts.isPropertyAccessExpression(name) ? name.name : name)
  if (symbol && symbol.flags & ts.SymbolFlags.Alias) symbol = CHECKER.getAliasedSymbol(symbol)
  const declaration = symbol?.valueDeclaration ?? symbol?.declarations?.[0]
  return declaration && SCANNED.has(path.normalize(declaration.getSourceFile().fileName)) ? declaration : undefined
}

/** The function a component declaration renders through: itself, the function a const holds, or the one
    passed to forwardRef() or memo(). */
function functionOf(node: ts.Node): ts.FunctionLikeDeclaration | undefined {
  if (ts.isFunctionDeclaration(node) || ts.isArrowFunction(node) || ts.isFunctionExpression(node)) return node
  const init = ts.isVariableDeclaration(node) ? node.initializer : ts.isExportAssignment(node) ? node.expression : undefined
  if (!init) return undefined
  const x = unwrap(init)
  if (ts.isArrowFunction(x) || ts.isFunctionExpression(x)) return x
  const target = ts.isCallExpression(x) && x.arguments[0] ? unwrap(x.arguments[0]) : x
  if (ts.isArrowFunction(target) || ts.isFunctionExpression(target)) return target
  if (ts.isIdentifier(target)) {
    const declaration = declarationOf(target)
    return declaration && declaration !== node ? functionOf(declaration) : undefined
  }
  return undefined
}

/** The app component a JSX tag renders, or undefined for an element or a library component. */
function componentFunction(opening: ts.JsxOpeningLikeElement): ts.FunctionLikeDeclaration | undefined {
  const tag = opening.tagName
  if (ts.isIdentifier(tag) && /^[a-z]/.test(tag.text)) return undefined
  const declaration = declarationOf(tag)
  return declaration && functionOf(declaration)
}

/** The expressions a function returns (its body when it is one), skipping nested functions. */
function returnedExpressions(fn: ts.FunctionLikeDeclaration): ts.Expression[] {
  if (!fn.body) return []
  if (!ts.isBlock(fn.body)) return [fn.body]
  const out: ts.Expression[] = []
  const collect = (n: ts.Node) => {
    if (ts.isFunctionLike(n)) return
    if (ts.isReturnStatement(n) && n.expression) out.push(n.expression)
    ts.forEachChild(n, collect)
  }
  ts.forEachChild(fn.body, collect)
  return out
}

/** The same-file functions a call is handed, written inline or named (`rows.map((r) => …)`, `rows.map(renderRow)`). */
const callbacksOf = (call: ts.CallExpression) => call.arguments.flatMap((a) => functionsOf(a))
/** What a call renders: what its callbacks return, with or without a block body. */
const callbackReturns = (call: ts.CallExpression) => callbacksOf(call).flatMap(returnedExpressions)
/** The functions whose returns a call renders: its callbacks', and, for a call to a same-file function, that
    function's own (`{label('Q3')}`, `{renderRow(row)}`). */
const renderedFunctions = (call: ts.CallExpression) => [...callbacksOf(call), ...functionsOf(call.expression)]

/** The string members of a union type alias (`ButtonVariant`), read through the checker. */
function unionMembers(rel: string, name: string): string[] {
  const sf = PROGRAM.getSourceFile(path.join(ROOT, rel))
  let alias: ts.TypeAliasDeclaration | undefined
  if (sf) visit(sf, (n) => { if (!alias && ts.isTypeAliasDeclaration(n) && n.name.text === name) alias = n })
  if (!alias) throw new Error(`${rel} declares no ${name}`)
  const type = CHECKER.getTypeAtLocation(alias.name)
  return (type.isUnion() ? type.types : [type]).filter((t): t is ts.StringLiteralType => t.isStringLiteral()).map((t) => t.value)
}

/** The function a file declares under a name, for the variant components below. */
function declaredFunction(rel: string, name: string): ts.FunctionLikeDeclaration {
  const sf = PROGRAM.getSourceFile(path.join(ROOT, rel))
  let fn: ts.FunctionLikeDeclaration | undefined
  if (sf) visit(sf, (n) => {
    if (fn) return
    if (ts.isFunctionDeclaration(n) && n.name?.text === name) fn = n
    else if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === name) fn = functionOf(n)
  })
  if (!fn) throw new Error(`${rel} declares no component ${name}`)
  return fn
}

/** The variant a component takes when the call site names none, from its own destructuring default. */
function defaultVariant(fn: ts.FunctionLikeDeclaration, name: string): string {
  const binding = fn.parameters[0]?.name
  const element = binding && ts.isObjectBindingPattern(binding)
    ? binding.elements.find((e) => ts.isIdentifier(e.name) && e.name.text === 'variant')
    : undefined
  if (!element?.initializer || !ts.isStringLiteral(element.initializer)) throw new Error(`${name} declares no literal default variant`)
  return element.initializer.text
}

/** Each variant's resting ink, asked of the component itself (buttonVariants() for the Button family, a static
    render for Badge), so a variant that turns sage is read the day it does. */
const BUTTON_INK = new Map<string, Ink>(unionMembers('components/ui/Button.tsx', 'ButtonVariant')
  .map((v) => [v, tokenInk(buttonVariants({ variant: v as ButtonVariant }).split(/\s+/))]))
const BADGE_INK = new Map<string, Ink>(unionMembers('components/ui/Badge.tsx', 'BadgeVariant').map((v) => {
  const html = renderToStaticMarkup(createElement(Badge, { variant: v as BadgeVariant }, 'x'))
  return [v, tokenInk((html.match(/^<[a-z]+[^>]*?\bclass="([^"]*)"/)?.[1] ?? '').split(/\s+/))]
}))
/** The components whose colour is their `variant` prop, with the variant each takes by default. RetryButton
    (hooks/useRetainedFailure.tsx) and MarketingCta render a ui Button's treatment. */
const VARIANT_COMPONENTS = new Map(([
  ['components/ui/Button.tsx', 'Button', BUTTON_INK],
  ['hooks/useRetainedFailure.tsx', 'RetryButton', BUTTON_INK],
  ['features/marketing/components/MarketingCta.tsx', 'MarketingCta', BUTTON_INK],
  ['components/ui/Badge.tsx', 'Badge', BADGE_INK],
] as const).map(([rel, name, inks]) => {
  const fn = declaredFunction(rel, name)
  return [fn as ts.Node, { inks, fallback: defaultVariant(fn, name) }] as const
}))

const COMPARISONS = new Set([
  ts.SyntaxKind.LessThanToken, ts.SyntaxKind.GreaterThanToken, ts.SyntaxKind.LessThanEqualsToken, ts.SyntaxKind.GreaterThanEqualsToken,
  ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken, ts.SyntaxKind.EqualsEqualsEqualsToken,
  ts.SyntaxKind.ExclamationEqualsEqualsToken, ts.SyntaxKind.InKeyword, ts.SyntaxKind.InstanceOfKeyword,
])
/** The operands a binary expression can evaluate to: none of a comparison (its boolean renders nothing), the
    right of `&&`, and its left only when that can be a number (`{count && …}` renders a 0, and so does a chain
    such as `{count && open && …}`, whose left is typed `0 | boolean`), and both of `||`, `??` and arithmetic. */
function valueOperands(x: ts.BinaryExpression): ts.Expression[] {
  const operator = x.operatorToken.kind
  if (COMPARISONS.has(operator)) return []
  if (operator === ts.SyntaxKind.AmpersandAmpersandToken) return mayBeNumber(x.left) ? [x.left, x.right] : [x.right]
  return [x.left, x.right]
}

/** The variants an expression can name: its literals through conditionals and `??`/`||`, the component's default
    for `undefined` or `null`, and 'unknown' for anything else (an identifier, a call, a member), which may be any
    variant (`variant={v ?? 'neutral'}` may be brand). */
function variantLiterals(e: ts.Expression): string[] {
  const x = unwrap(e)
  const text = literalText(x)
  if (text !== null) return [text]
  if (x.kind === ts.SyntaxKind.NullKeyword || (ts.isIdentifier(x) && x.text === 'undefined')) return ['default']
  if (ts.isConditionalExpression(x)) return [...variantLiterals(x.whenTrue), ...variantLiterals(x.whenFalse)]
  if (ts.isBinaryExpression(x)) return valueOperands(x).flatMap(variantLiterals)
  return ['unknown']
}

/** The inks a variant component, or a `buttonVariants()` call in an element's className, can give its
    children, or null when the element is neither. A variant the scan cannot read (an identifier, a spread,
    a shorthand `variant`) counts as sage, since it may be. */
function variantInks(opening: ts.JsxOpeningLikeElement): Ink[] | null {
  const ink = (inks: Map<string, Ink>) => (v: string): Ink => (inks.has(v) ? inks.get(v)! : 'sage')
  const fn = componentFunction(opening)
  const component = fn && VARIANT_COMPONENTS.get(fn)
  if (component) {
    const attr = opening.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText() === 'variant')
    let variants: string[]
    if (opening.attributes.properties.some((p) => ts.isJsxSpreadAttribute(p))) variants = ['unknown']
    else if (!attr) variants = [component.fallback]
    else if (attr.initializer && ts.isStringLiteral(attr.initializer)) variants = [attr.initializer.text]
    else if (attr.initializer && ts.isJsxExpression(attr.initializer) && attr.initializer.expression) {
      variants = variantLiterals(attr.initializer.expression).map((v) => (v === 'default' ? component.fallback : v))
      if (variants.length === 0) variants = ['unknown']
    } else variants = ['unknown']
    return variants.map(ink(component.inks))
  }
  const variants: string[] = []
  for (const node of classNameNodes(opening)) {
    visit(node, (n) => {
      if (!ts.isCallExpression(n) || n.expression.getText() !== 'buttonVariants') return
      const options = n.arguments[0]
      // No options: the factory's default, primary.
      if (!options) { variants.push('primary'); return }
      const opaque = !ts.isObjectLiteralExpression(options)
        || options.properties.some((p) => ts.isSpreadAssignment(p) || (ts.isShorthandPropertyAssignment(p) && p.name.text === 'variant'))
      if (opaque) { variants.push('unknown'); return }
      const variant = options.properties.find((p): p is ts.PropertyAssignment => ts.isPropertyAssignment(p) && p.name.getText() === 'variant')
      const read = variant ? variantLiterals(variant.initializer).map((v) => (v === 'default' ? 'primary' : v)) : ['primary']
      variants.push(...(read.length ? read : ['unknown']))
    })
  }
  return variants.length ? variants.map(ink(BUTTON_INK)) : null
}

/** The resting ink the call site gives an element: a variant component's variant, or the className written
    there (inline, a same-file const, or buttonVariants() in it). */
function siteInk(opening: ts.JsxOpeningLikeElement): Ink {
  const classes = tokenInk(classTokens(opening), SVG_TEXT.has(opening.tagName.getText()))
  const variants = variantInks(opening)
  if (!variants) return classes
  return variants.includes('sage') || classes === 'sage' ? 'sage' : variants.includes(null) ? classes : 'other'
}

const COLOURS = new Map<ts.Node, Ink>()
/** The ink an element gives its children: 'sage' or 'other' when it sets a resting text colour, null when
    they inherit its parent's. The call site's ink first; then, for a component the app declares, the ink it
    renders its children in, so a component that wraps its children in sage is a sage element. */
function textColour(opening: ts.JsxOpeningLikeElement): Ink {
  const known = COLOURS.get(opening)
  if (known !== undefined) return known
  COLOURS.set(opening, null)
  let ink = siteInk(opening)
  if (ink === null) {
    const fn = componentFunction(opening)
    if (fn) ink = summary(fn).childrenInk
  }
  COLOURS.set(opening, ink)
  return ink
}

/** Whether a node holds JSX anywhere in it. */
function containsJsx(node: ts.Node): boolean {
  let found = false
  visit(node, (n) => { if (ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n) || ts.isJsxFragment(n)) found = true })
  return found
}

/** The JSX a name holds through the file's bindings (`const body = <span>{children}</span>`, each JSX value a `let` is
    assigned, a helper's parameter handed a label), once per walk; none for one that holds no JSX, which the value
    reading takes instead. */
function heldJsx(id: ts.Identifier, sf: ts.SourceFile, followed: Set<ts.Node>): ts.Expression[] {
  return literalExpressions(id, sf).filter((v) => {
    if (followed.has(v) || !containsJsx(v)) return false
    followed.add(v)
    return true
  })
}

/** What a component does with the ink it inherits: the ink its children render in (null when they inherit
    it too), and whether it renders a number of its own in that inherited ink, which a sage parent colours. */
interface Summary { childrenInk: Ink; inheritsValue: boolean }
const SUMMARIES = new Map<ts.Node, Summary>()
function summary(fn: ts.FunctionLikeDeclaration): Summary {
  const known = SUMMARIES.get(fn)
  if (known) return known
  // A component that renders itself reads, mid-walk, as one that passes its ink through and carries nothing.
  SUMMARIES.set(fn, { childrenInk: null, inheritsValue: false })
  const sf = fn.getSourceFile()
  const childInks = new Set<'sage' | 'other' | 'inherit'>()
  let carries = false
  const props = fn.parameters[0]
  const takesChildren = !!props && !!CHECKER.getTypeAtLocation(props).getProperty('children')
  // The names the children go by: `children`, a renamed binding (`{ children: content }`), and the parameter of a
  // callback they are handed to (`Children.map(children, (child) => …)`, `children.map(…)`), added as the walk
  // meets it.
  const aliases = new Set(['children'])
  if (props && ts.isObjectBindingPattern(props.name)) {
    for (const binding of props.name.elements) {
      if (binding.propertyName && ts.isIdentifier(binding.propertyName) && binding.propertyName.text === 'children' && ts.isIdentifier(binding.name)) aliases.add(binding.name.text)
    }
  }
  const isChildren = (e: ts.Expression) => {
    const x = unwrap(e)
    return (ts.isIdentifier(x) && aliases.has(x.text)) || (ts.isPropertyAccessExpression(x) && x.name.text === 'children')
  }
  const followed = new Set<ts.Node>()
  const element = (el: ts.JsxElement | ts.JsxSelfClosingElement, ink: 'sage' | 'other' | 'inherit') => {
    const opening = ts.isJsxElement(el) ? el.openingElement : el
    const next = textColour(opening) ?? ink
    // A spread can carry the children through (`<span {...rest} />`).
    if (takesChildren && opening.attributes.properties.some((p) => ts.isJsxSpreadAttribute(p))) childInks.add(next)
    if (ink === 'inherit' && inheritsValue(opening)) carries = true
    if (ts.isJsxElement(el)) children(el.children, next)
  }
  const children = (list: ts.NodeArray<ts.JsxChild>, ink: 'sage' | 'other' | 'inherit') => {
    list.forEach((child, i) => {
      if (ts.isJsxText(child)) { if (ink === 'inherit' && carriesDigit(child.text)) carries = true }
      else if (ts.isJsxExpression(child) && child.expression) { if (!citationBracket(list, i) && !bracketTemplate(child.expression)) expression(child.expression, ink) }
      else if (ts.isJsxElement(child) || ts.isJsxSelfClosingElement(child)) element(child, ink)
      else if (ts.isJsxFragment(child)) children(child.children, ink)
    })
  }
  const expression = (e: ts.Expression, ink: 'sage' | 'other' | 'inherit') => {
    const x = unwrap(e)
    if (isChildren(x)) childInks.add(ink)
    else if (ts.isJsxElement(x) || ts.isJsxSelfClosingElement(x)) element(x, ink)
    else if (ts.isJsxFragment(x)) children(x.children, ink)
    else if (ts.isConditionalExpression(x)) { expression(x.whenTrue, ink); expression(x.whenFalse, ink) }
    else if (ts.isBinaryExpression(x)) valueOperands(x).forEach((operand) => expression(operand, ink))
    else if (ts.isCallExpression(x) && renderedFunctions(x).some((fn) => returnedExpressions(fn).length)) {
      const callee = x.expression
      if (x.arguments.some(isChildren) || (ts.isPropertyAccessExpression(callee) && isChildren(callee.expression))) {
        for (const fn of callbacksOf(x)) if (fn.parameters[0] && ts.isIdentifier(fn.parameters[0].name)) aliases.add(fn.parameters[0].name.text)
      }
      // What its callbacks and its own same-file function return renders here, each function walked once, so one
      // that renders itself ends; a call with no callbacks counts its own value too (a helper fed a number).
      const fns = renderedFunctions(x).filter((fn) => !followed.has(fn))
      fns.forEach((fn) => followed.add(fn))
      fns.flatMap(returnedExpressions).forEach((r) => expression(r, ink))
      if (ink === 'inherit' && !callbacksOf(x).length && rendersValue(x, sf)) carries = true
    } else {
      const jsx = ts.isIdentifier(x) ? heldJsx(x, sf, followed) : []
      jsx.forEach((h) => expression(h, ink))
      if (!jsx.length && ink === 'inherit') {
        const text = literalText(x)
        if (text !== null ? carriesDigit(text) : literalValues(x, sf).some(carriesDigit) || rendersValue(x, sf)) carries = true
      }
    }
  }
  for (const r of returnedExpressions(fn)) expression(r, 'inherit')
  const result: Summary = {
    // No path to the children found (cloned, handed to a helper) reads as one that passes its ink through, so a
    // number given to it inside a sage parent is still read.
    childrenInk: childInks.has('sage') ? 'sage' : childInks.has('inherit') || childInks.size === 0 ? null : 'other',
    inheritsValue: carries,
  }
  SUMMARIES.set(fn, result)
  return result
}

/** Whether a component element renders a number in the ink it inherits, which a sage parent would colour. */
function inheritsValue(opening: ts.JsxOpeningLikeElement): boolean {
  if (siteInk(opening) !== null) return false
  const fn = componentFunction(opening)
  return !!fn && summary(fn).inheritsValue
}

/** The literal texts an element renders in its own ink (stops at a child that sets its own colour). Text held
    elsewhere (a variable's value, what a function returns) is reported at `site`, the expression that renders it
    here: the variable's name, or the call. */
function inkTexts(children: ts.NodeArray<ts.JsxChild>, sf: ts.SourceFile, out: { node: ts.Node; text: string }[] = [], seen = new Set<ts.Node>(), site?: ts.Node) {
  const expr = (e: ts.Expression, at = site) => {
    const x = unwrap(e)
    const push = (text: string) => out.push({ node: at ?? x, text })
    // What the file binds a name, a field read or a call to (`literalExpressions`), read once where it is rendered:
    // a literal's text, a template with its substitutions, an array's members, the JSX it holds. A value a literal's
    // field writes as a conditional stays as written.
    const read = (v: ts.Expression) => {
      if (v === x || seen.has(v) || asWritten(v)) return
      seen.add(v)
      expr(v, at ?? x)
    }
    const text = literalText(x)
    if (text !== null) {
      push(text)
      // A template's substitutions render with it (`{`Go to ${label}`}`): each is read as an expression of its own.
      if (ts.isTemplateExpression(x)) x.templateSpans.forEach((span) => expr(span.expression, at))
    } else if (ts.isConditionalExpression(x)) [x.whenTrue, x.whenFalse].forEach((branch) => expr(branch, at))
    else if (ts.isBinaryExpression(x)) valueOperands(x).forEach((operand) => expr(operand, at))
    // An array renders every member (`{['Q1', 'Q2']}`), a spread's included.
    else if (ts.isArrayLiteralExpression(x)) x.elements.forEach((m) => { if (!ts.isOmittedExpression(m)) expr(ts.isSpreadElement(m) ? m.expression : m, at) })
    else if (ts.isJsxFragment(x)) inkTexts(x.children, sf, out, seen, at)
    else if (ts.isJsxElement(x) && textColour(x.openingElement) === null) inkTexts(x.children, sf, out, seen, at)
    else if (ts.isCallExpression(x)) {
      // What the call holds (a member through `at` or `find`, the members a join renders, what its same-file function
      // or useMemo returns) and what its callbacks return, each callback read once.
      literalExpressions(x, sf).forEach(read)
      for (const fn of callbacksOf(x)) {
        if (seen.has(fn)) continue
        seen.add(fn)
        returnedExpressions(fn).forEach((r) => expr(r, at ?? x))
      }
    } else if (ts.isIdentifier(x) || ts.isPropertyAccessExpression(x) || ts.isElementAccessExpression(x)) literalExpressions(x, sf).forEach(read)
  }
  for (const child of children) {
    if (ts.isJsxText(child)) out.push({ node: site ?? child, text: child.text })
    else if (ts.isJsxExpression(child) && child.expression) expr(child.expression)
    else if (ts.isJsxFragment(child)) inkTexts(child.children, sf, out, seen, site)
    else if (ts.isJsxElement(child) && textColour(child.openingElement) === null) inkTexts(child.children, sf, out, seen, site)
  }
  return out
}

/** A number or a bigint: either renders as digits. */
const NUMBER_LIKE = ts.TypeFlags.NumberLike | ts.TypeFlags.BigIntLike
/** Whether an expression's type can be a number: any member of a union. */
function mayBeNumber(e: ts.Expression): boolean {
  const t = CHECKER.getTypeAtLocation(e)
  return (t.isUnion() ? t.types : [t]).some((u) => (u.flags & NUMBER_LIKE) !== 0)
}
function numberType(t: ts.Type): boolean {
  if (t.flags & NUMBER_LIKE) return true
  // A union is a number when every member that is not null or undefined is one (`number | null`);
  // ReactNode and `string | number` carry other things and are not read as values.
  if (!t.isUnion()) return false
  const members = t.types.filter((u) => !(u.flags & (ts.TypeFlags.Null | ts.TypeFlags.Undefined)))
  return members.length > 0 && members.every((u) => (u.flags & NUMBER_LIKE) !== 0)
}
const isNumberTyped = (e: ts.Expression) => numberType(CHECKER.getTypeAtLocation(e))
/** Whether a type is an array or a tuple of numbers, which renders each one's digits (`{counts}`). */
function numberArrayType(t: ts.Type): boolean {
  const member = CHECKER.isArrayType(t) || CHECKER.isTupleType(t) ? CHECKER.getIndexTypeOfType(t, ts.IndexKind.Number) : undefined
  return !!member && numberType(member)
}
const isNumberArray = (e: ts.Expression) => numberArrayType(CHECKER.getTypeAtLocation(e))

/** What the variable an identifier names holds, when this file declares it: its initializer and every value the
    file assigns it (one level). Resolved through the checker, so a parameter, or a name another function in the
    file declares, is never mistaken for it. */
function localValues(id: ts.Identifier, sf: ts.SourceFile): ts.Expression[] {
  const declaration = CHECKER.getSymbolAtLocation(id)?.valueDeclaration
  if (!declaration || !ts.isVariableDeclaration(declaration) || declaration.getSourceFile() !== sf) return []
  // A value destructured into the variable (`[label] = LABELS`) is read at its place.
  return variableValues(declaration).flatMap((v) => (v.steps.length ? literalExpressions(v.value, sf, v.steps) : [v.value]))
}

/** A value a literal's field writes and the scan reads as written (`literalExpressions`): a conditional, `??`, `||`. */
const asWritten = (v: ts.Expression) =>
  ts.isConditionalExpression(v) || (ts.isBinaryExpression(v) && [ts.SyntaxKind.QuestionQuestionToken, ts.SyntaxKind.BarBarToken].includes(v.operatorToken.kind))

/** The step an element access reads: a literal key, or null for one the scan cannot read. */
function accessStep(key: ts.Expression): Step {
  const k = unwrap(key)
  return ts.isNumericLiteral(k) ? Number(k.text) : ts.isStringLiteral(k) || ts.isNoSubstitutionTemplateLiteral(k) ? k.text : null
}

/** Whether a type, walked through the steps of a destructuring or a field read, is a number or an array of them. */
function valueType(t: ts.Type | undefined, steps: Step[], at: ts.Node): boolean {
  let type = t
  for (const step of steps) {
    if (!type) return false
    if (typeof step === 'string') {
      const property = type.getProperty(step)
      type = property && CHECKER.getTypeOfSymbolAtLocation(property, at)
    } else type = CHECKER.getIndexTypeOfType(type, ts.IndexKind.Number)
  }
  return !!type && (numberType(type) || numberArrayType(type))
}

/** Whether the file hands a parameter a value, by the type of what it is given: a number passed to a parameter typed
    wider (`(v: ReactNode) => …` called with a count), mapped from an array of numbers, or given as its default,
    through the fields the parameter is destructured or read by (`({ n }) => …` given `{ n: count }`). */
function boundToValue(e: ts.Expression, sf: ts.SourceFile): boolean {
  const path: Step[] = []
  let x = unwrap(e)
  while (ts.isPropertyAccessExpression(x) || ts.isElementAccessExpression(x)) {
    path.unshift(ts.isPropertyAccessExpression(x) ? x.name.text : accessStep(x.argumentExpression))
    x = unwrap(x.expression)
  }
  if (!ts.isIdentifier(x)) return false
  const binding = bindingOf(CHECKER.getSymbolAtLocation(x), path)
  const declaration = binding?.declaration
  if (!binding || !declaration || !ts.isParameter(declaration) || declaration.dotDotDotToken || declaration.getSourceFile() !== sf) return false
  if (binding.defaults.some((d) => valueType(CHECKER.getTypeAtLocation(d.value), d.steps, d.value))) return true
  const at = declaration.parent.parameters.indexOf(declaration)
  return sitesOf(declaration.parent).some((site) => {
    if (site.members) {
      return site.at === at && valueType(CHECKER.getIndexTypeOfType(CHECKER.getTypeAtLocation(site.members), ts.IndexKind.Number), binding.steps, site.members)
    }
    const arg = site.args?.[at]
    return !!arg && !ts.isSpreadElement(arg) && valueType(CHECKER.getTypeAtLocation(arg), binding.steps, arg)
  })
}

/** Whether a JSX expression renders a value: a number-typed expression or an array of them (rendered whole or
 *  joined), a template or concatenation with a number in it, a string-returning call fed a number (a formatter,
 *  and so also a lookup such as `labelFor(i)`: give that label its own ink or pass it a string), what a callback
 *  or a same-file function returns, a conditional with such a branch, a same-file variable holding one of those,
 *  or a component that renders a number in the ink it inherits. */
function rendersValue(e: ts.Expression, sf: ts.SourceFile, depth = 0): boolean {
  const x = unwrap(e)
  if (depth > 6) return false
  if (ts.isJsxSelfClosingElement(x)) return inheritsValue(x)
  if (ts.isJsxFragment(x)) return inkValues(x.children, sf).length > 0
  if (ts.isJsxElement(x)) return inheritsValue(x.openingElement) || (textColour(x.openingElement) === null && inkValues(x.children, sf).length > 0)
  if (ts.isTemplateExpression(x)) return x.templateSpans.some((span) => rendersValue(span.expression, sf, depth + 1))
  if (literalText(x) !== null) return false
  if (ts.isConditionalExpression(x)) return rendersValue(x.whenTrue, sf, depth + 1) || rendersValue(x.whenFalse, sf, depth + 1)
  if (ts.isBinaryExpression(x)) return valueOperands(x).some((operand) => rendersValue(operand, sf, depth + 1))
  if (ts.isCallExpression(x)) {
    // A number's own method ("n.toLocaleString()"), a join of numbers, a call that returns one, a formatter fed
    // one (a literal argument such as "slice(0, 20)" is not a value), or what a callback or the same-file
    // function it calls returns.
    if (isNumberTyped(x)) return true
    if (ts.isPropertyAccessExpression(x.expression) && isNumberTyped(x.expression.expression)) return true
    if (ts.isPropertyAccessExpression(x.expression) && JOINS.has(x.expression.name.text) && isNumberArray(x.expression.expression)) return true
    if (renderedFunctions(x).some((fn) => returnedExpressions(fn).some((r) => rendersValue(r, sf, depth + 1)))) return true
    return x.arguments.some((a) => !ts.isArrowFunction(unwrap(a)) && !ts.isFunctionExpression(unwrap(a)) && literalText(unwrap(a)) === null && isNumberTyped(a))
  }
  if (ts.isIdentifier(x)) {
    const values = localValues(x, sf)
    if (values.length) return values.some((value) => rendersValue(value, sf, depth + 1)) || isNumberTyped(x) || isNumberArray(x)
  }
  if (ts.isIdentifier(x) || ts.isPropertyAccessExpression(x) || ts.isElementAccessExpression(x)) {
    // A parameter the file hands a number, whatever its own type; and what a name or a field read holds through the
    // file's bindings that renders one (a template or JSX handed to a helper).
    if (boundToValue(x, sf)) return true
    if (literalExpressions(x, sf).some((v) => !asWritten(v) && rendersValue(v, sf, depth + 1))) return true
  }
  return isNumberTyped(x) || isNumberArray(x)
}

/** The device's citation marker: an expression whose bracket is the whole of the text around it ("[{n}]"). */
function citationBracket(children: ts.NodeArray<ts.JsxChild>, i: number): boolean {
  const before = children[i - 1]
  const after = children[i + 1]
  return !!before && !!after && ts.isJsxText(before) && ts.isJsxText(after) && /^\s*\[\s*$/.test(before.text) && /^\s*\]\s*$/.test(after.text)
}

/** A template whose brackets are its whole text (`{`[${n}]`}`): the citation marker written as one string. */
function bracketTemplate(e: ts.Expression): boolean {
  const x = unwrap(e)
  return ts.isTemplateExpression(x) && /^\s*\[\s*$/.test(x.head.text) && x.templateSpans.length === 1 && /^\s*\]\s*$/.test(x.templateSpans[0].literal.text)
}

/** The expression a link renders as its own address (`<a href={url}>{url}</a>`): text, not a value. */
function ownAddress(opening: ts.JsxOpeningLikeElement | undefined, e: ts.Expression): boolean {
  const href = opening?.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText() === 'href')
  return !!href?.initializer && ts.isJsxExpression(href.initializer) && !!href.initializer.expression && href.initializer.expression.getText() === e.getText()
}

/** The expressions and component elements an element renders in its own ink that carry a value (stops at a
    child with its own colour). */
function inkValues(children: ts.NodeArray<ts.JsxChild>, sf: ts.SourceFile, out: ts.Node[] = [], opening?: ts.JsxOpeningLikeElement) {
  const element = (el: ts.JsxElement | ts.JsxSelfClosingElement | ts.JsxFragment) => {
    if (ts.isJsxFragment(el)) return void inkValues(el.children, sf, out)
    const own = ts.isJsxElement(el) ? el.openingElement : el
    if (inheritsValue(own)) out.push(el)
    if (ts.isJsxElement(el) && textColour(own) === null) inkValues(el.children, sf, out)
  }
  children.forEach((child, i) => {
    if (ts.isJsxExpression(child) && child.expression) {
      if (citationBracket(children, i) || ownAddress(opening, child.expression)) return
      if (bracketTemplate(child.expression)) return
      const x = unwrap(child.expression)
      if (ts.isJsxElement(x) || ts.isJsxSelfClosingElement(x) || ts.isJsxFragment(x)) return element(x)
      if (rendersValue(child.expression, sf)) out.push(child.expression)
    } else if (ts.isJsxElement(child) || ts.isJsxSelfClosingElement(child) || ts.isJsxFragment(child)) element(child)
  })
  return out
}

/** All literal text under an element, whatever its colour (for the highlight rule). A field read inside an
    attribute (`className={STYLES.chip}`, `key={item.id}`) is no text the element renders, so it is not resolved. */
function allTexts(node: ts.Node, sf: ts.SourceFile): { node: ts.Node; text: string }[] {
  const out: { node: ts.Node; text: string }[] = []
  const inAttribute = (m: ts.Node) => {
    for (let p = m.parent; p && p !== node; p = p.parent) if (ts.isJsxAttribute(p)) return true
    return false
  }
  visit(node, (n) => {
    if (ts.isJsxAttribute(n.parent ?? n) && n !== node) return
    const text = ts.isJsxText(n) || ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n) || ts.isTemplateExpression(n) || ts.isNumericLiteral(n) ? literalText(n) : null
    if (text !== null && !(n.parent && ts.isJsxAttribute(n.parent))) out.push({ node: n, text })
    if (ts.isPropertyAccessExpression(n) && !inAttribute(n)) literalValues(n, sf).forEach((value) => out.push({ node: n, text: value }))
  })
  return out
}

describe('brand rule 1: matching claims keep their scope', () => {
  const UNSCOPED = /\b(?:each|every|all)\s+(?:figure|number)s?\b/i
  const SCOPE = /checkable|can be checked|can check|where (?:they|it) can be/i

  it('no shipped string or JSX text says "each figure" or "every figure" without the scope beside it', () => {
    const offenders: string[] = []
    for (const { rel, sf } of SOURCES) {
      visit(sf, (n) => {
        if (ts.isImportDeclaration(n.parent ?? n) || ts.isExportDeclaration(n.parent ?? n)) return
        const text = literalText(n)
        if (text !== null && !ts.isNumericLiteral(n) && UNSCOPED.test(text) && !SCOPE.test(text)) offenders.push(where(rel, sf, n, text))
      })
    }
    expect(offenders, 'say what the server checks: "where they can be checked", "checkable figures"').toEqual([])
  })
})

describe('brand rule 1b: the nine-part outline keeps its scope', () => {
  // The schema's nine sections are all optional (backend/app/services/summary_schema.py,
  // SummaryDocSections) and the render builders drop an empty one, so a filing without segment
  // disclosure has eight. Shipped copy may name the nine-part outline, never promise nine parts
  // per filing (Codex review of PR #1226).
  const PROMISE = /\bnine parts,? (?:per|for every|in every|every)\b|\bevery (?:filing|summary|10-K)\b[^.]*\bnine parts\b/i
  it('no shipped text promises nine parts for every filing unless it says "up to"', () => {
    const offenders: string[] = []
    for (const { rel, sf } of SOURCES) {
      visit(sf, (n) => {
        const text = literalText(n)
        if (text !== null && !ts.isNumericLiteral(n) && PROMISE.test(text) && !/\bup to nine parts\b/i.test(text)) offenders.push(where(rel, sf, n, text))
      })
    }
    expect(offenders, 'say "up to nine parts", or name the outline').toEqual([])
  })
})

describe('brand rule 1c: the withholding promise names risk excerpts', () => {
  // Of a summary's quotes, only risk excerpts are withheld when the filing's text does not match:
  // the server projects a risk only from a whitespace-exact span and counts the rest
  // (backend/app/services/provenance_service.py). A Forward Signals quote stays on the page,
  // labelled Cited, while AI_FORWARD_QUOTE_GATE is off (backend/app/services/ai/
  // forward_quote_gate.py). So a public surface may promise that risk excerpts are located or
  // withheld, or are the filing's own words, never that quotes in general are (the founder's
  // review of PR #1226). An object literal is read as one statement, so a claims row's subject
  // and label are judged together.
  const PROMISE = /\bwithheld\b|\bown words\b|\bpassage (?:it|they) came from\b/i
  const QUOTES = /\bquot(?:e|es|ed|ation|ations)\b|\bexcerpts?\b/i
  const SCOPE = /\brisks?\b/i

  /** The statement a literal belongs to: every literal value of its object literal, or itself. */
  function statement(n: ts.Node, text: string): string {
    const assignment = n.parent
    if (!assignment || !ts.isPropertyAssignment(assignment) || !ts.isObjectLiteralExpression(assignment.parent)) return text
    return assignment.parent.properties
      .map((p) => (ts.isPropertyAssignment(p) ? literalText(unwrap(p.initializer)) : null))
      .filter((t): t is string => t !== null)
      .join(' · ')
  }

  it('no text on a public surface promises that quotes are withheld or are the filing’s own words unless it names risk excerpts', () => {
    const offenders: string[] = []
    for (const { rel, sf } of SOURCES.filter((s) => isPublic(s.rel))) {
      visit(sf, (n) => {
        const text = literalText(n)
        if (text === null || ts.isNumericLiteral(n)) return
        const whole = statement(n, text)
        if (PROMISE.test(text) && QUOTES.test(whole) && !SCOPE.test(whole)) offenders.push(where(rel, sf, n, whole))
      })
    }
    expect(offenders, 'name what is enforced: "risk excerpts … or withheld"').toEqual([])
  })
})

/** Whether a component hands its `className` prop to the element it returns, so sage given where it is used
    colours all it renders in inherited ink. One that puts the className on an inner element (a label beside its
    number) is not read this way. */
function forwardsClassName(fn: ts.FunctionLikeDeclaration): boolean {
  return returnedExpressions(fn).some((r) => {
    const x = unwrap(r)
    const opening = ts.isJsxElement(x) ? x.openingElement : ts.isJsxSelfClosingElement(x) ? x : undefined
    const attr = opening?.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText() === 'className')
    let forwards = false
    if (attr?.initializer) visit(attr.initializer, (m) => { if (ts.isIdentifier(m) && m.text === 'className') forwards = true })
    return forwards
  })
}

/** The ink an element inherits from the elements around it in its own file: the nearest one that sets an ink. */
function inheritedInk(node: ts.Node): Ink {
  for (let p = node.parent; p; p = p.parent) {
    if (ts.isJsxElement(p)) {
      const ink = textColour(p.openingElement)
      if (ink !== null) return ink
    }
  }
  return null
}

/** A control the user activates: a link, a button, a disclosure's summary, any element given an href or an
    onClick, and the ui Button family. */
function isControl(opening: ts.JsxOpeningLikeElement): boolean {
  if (['a', 'button', 'summary'].includes(opening.tagName.getText())) return true
  if (opening.attributes.properties.some((p) => ts.isJsxAttribute(p) && ['href', 'onClick'].includes(p.name.getText()))) return true
  const fn = componentFunction(opening)
  return !!fn && VARIANT_COMPONENTS.get(fn)?.inks === BUTTON_INK
}

interface Offence { node: ts.Node; text: string }

/** Rule 2's first check over one file: what it renders in sage ink at rest that carries a digit or a value. */
function sageValues(sf: ts.SourceFile): Offence[] {
  const out: Offence[] = []
  visit(sf, (n) => {
    if (!ts.isJsxElement(n) && !ts.isJsxSelfClosingElement(n)) return
    const opening = ts.isJsxElement(n) ? n.openingElement : n
    if (textColour(opening) !== 'sage') return
    if (ts.isJsxElement(n)) {
      for (const { node, text } of inkTexts(n.children, sf)) if (carriesDigit(text)) out.push({ node, text })
      for (const node of inkValues(n.children, sf, [], opening)) out.push({ node, text: `{${node.getText(sf)}}` })
    }
    // Sage given where a component is used reaches the number it renders in the ink it inherits, when the
    // component hands that className to the element it returns. A variant component's own ink is read above.
    const fn = componentFunction(opening)
    if (fn && !VARIANT_COMPONENTS.has(fn) && siteInk(opening) === 'sage' && forwardsClassName(fn) && summary(fn).inheritsValue) {
      out.push({ node: n, text: `<${opening.tagName.getText(sf)}>` })
    }
  })
  return out
}

/** Rule 2's second check over one file, the count control's: what a control resting in sage holds in an ink of
    its own that carries a digit or a value, in its markup, in the same-file variable its label is held in
    (`{overflowLabel}`), or in what a same-file function it calls or maps with returns (`{renderLabel(n)}`), a
    count held elsewhere reported at the expression that renders it in the control. */
function heldValues(sf: ts.SourceFile): Offence[] {
  const out: Offence[] = []
  visit(sf, (n) => {
    if (!ts.isJsxElement(n) || !isControl(n.openingElement) || (textColour(n.openingElement) ?? inheritedInk(n)) !== 'sage') return
    const followed = new Set<ts.Node>()
    const holders = (node: ts.Node, site?: ts.Node): void => {
      // A prop is not the label: a handler's body, a tooltip's content.
      if (ts.isJsxAttributes(node)) return
      const jsx = ts.isJsxExpression(node) && node.expression && ts.isIdentifier(unwrap(node.expression))
        ? heldJsx(unwrap(node.expression) as ts.Identifier, sf, followed)
        : []
      jsx.forEach((h) => holders(h, site ?? node))
      // A function written inside the label is walked where it stands; one held elsewhere, once.
      if (ts.isCallExpression(node)) {
        for (const fn of renderedFunctions(node)) {
          if (followed.has(fn) || (fn.pos >= node.pos && fn.end <= node.end)) continue
          followed.add(fn)
          returnedExpressions(fn).forEach((r) => holders(r, site ?? node))
        }
      }
      if (node !== n && ts.isJsxElement(node) && textColour(node.openingElement) === 'other') {
        for (const { node: hit, text } of inkTexts(node.children, sf)) if (carriesDigit(text)) out.push({ node: site ?? hit, text })
        for (const hit of inkValues(node.children, sf, [], node.openingElement)) out.push({ node: site ?? hit, text: `{${hit.getText(sf)}}` })
      }
      ts.forEachChild(node, (child) => holders(child, site))
    }
    holders(n)
  })
  return out
}

describe('brand rule 2: sage never colours a number', () => {
  // Each offence once: a text reached two ways (a helper's return read as a value and walked as JSX) is one.
  const inApp = (check: (sf: ts.SourceFile) => Offence[]) =>
    [...new Set(SOURCES.flatMap(({ rel, sf }) => check(sf).map(({ node, text }) => where(rel, sf, node, text))))]

  // The app scan asks the checker for the types of what it reads in every file, about 2 s on a laptop; the budget
  // leaves room for a loaded CI runner.
  it('nothing the app renders in sage ink at rest carries a digit or a value', () => {
    expect(inApp(sageValues), 'set the number in the ink (text-text-primary / secondary); sage signals brand and activity').toEqual([])
  }, 20_000)

  it('no control that rests in sage holds its count in an ink of its own (the count control)', () => {
    expect(inApp(heldValues), 'rest the whole label in the ink, sage under the pointer (the count control, frontend/DESIGN_SYSTEM.md)').toEqual([])
  })

  it('scores every planted form in tests/unit/fixtures/brandRule2Forms.tsx as its mark says', () => {
    const sf = PROGRAM.getSourceFile(FORMS)
    if (!sf) throw new Error(`${FORMS} is not in the program`)
    const lineOf = (node: ts.Node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
    const named = new Set([...sageValues(sf), ...heldValues(sf)].map(({ node }) => lineOf(node)))
    const forms = sf.text.split('\n').flatMap((text, i) => {
      const mark = /^export function (P\d+)\b.*\/\/ (flag|clean|gap)$/.exec(text)
      return mark ? [{ name: mark[1], line: i + 1, mark: mark[2] }] : []
    })
    expect(forms.filter((form) => form.mark === 'flag').length, 'the fixture plants forms that break the rule').toBeGreaterThan(0)
    expect(forms.filter((form) => form.mark === 'clean').length, 'the fixture plants look-alikes').toBeGreaterThan(0)
    const misread = forms.filter((form) => named.has(form.line) !== (form.mark === 'flag')).map((form) => `${form.name} (${form.mark})`)
    const strays = [...named].filter((line) => !forms.some((form) => form.line === line)).map((line) => `line ${line}`)
    expect(misread, 'rule 2 reads these forms against their marks: fix the gate, or flip the mark with its record (D-030)').toEqual([])
    expect(strays, 'rule 2 named a line that is not a planted form').toEqual([])
  })
})

describe('brand rule 3: the Marked Copy Rule', () => {
  it('the highlight (en-mark) never sits on a figure or a price', () => {
    const offenders: string[] = []
    for (const { rel, sf } of SOURCES) {
      visit(sf, (n) => {
        if (!ts.isJsxElement(n) || !classTokens(n.openingElement).includes('en-mark')) return
        for (const { node, text } of allTexts(n, sf)) if (/[\d$%]/.test(text)) offenders.push(where(rel, sf, node, text))
      })
    }
    expect(offenders).toEqual([])
  })

  it("the hero's accent phrases (rendered inside the highlight) carry no figure or price", () => {
    for (const [variant, headline] of Object.entries(HEADLINES)) expect(headline.accent, variant).not.toMatch(/[\d$%]/)
  })

  it('the margin exists only inside MarkedCopy, and every MarkedCopy carries a marker', () => {
    const marginOutside: string[] = []
    const withoutMarker: string[] = []
    for (const { rel, sf } of SOURCES) {
      visit(sf, (n) => {
        if ((ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n)) && rel !== 'features/marketing/components/MarkedCopy.tsx') {
          const opening = ts.isJsxElement(n) ? n.openingElement : n
          if (classTokens(opening).includes('en-margin')) marginOutside.push(where(rel, sf, n, 'en-margin'))
        }
        if (ts.isJsxElement(n) && n.openingElement.tagName.getText() === 'MarkedCopy') {
          let marker = false
          visit(n, (m) => {
            if ((ts.isJsxElement(m) && m.openingElement.tagName.getText() === 'EnRef') || (ts.isJsxSelfClosingElement(m) && m.tagName.getText() === 'EnRef')) marker = true
          })
          if (!marker) withoutMarker.push(where(rel, sf, n, '<MarkedCopy> without <EnRef>'))
        }
      })
    }
    expect(marginOutside, 'render <MarkedCopy> instead of a bare gutter').toEqual([])
    expect(withoutMarker, 'a margin appears only beside text that carries a marker').toEqual([])
  })

  it('the scan sees the surfaces it guards (the rules above stay meaningful)', () => {
    expect(PUBLIC_SURFACES.every((prefix) => SOURCES.some((s) => (prefix.endsWith('/') ? s.rel.startsWith(prefix) : s.rel === prefix))), 'every public surface prefix matches a file').toBe(true)
    const rels = new Set(SOURCES.map((s) => s.rel))
    for (const rel of ['features/marketing/components/HeroHeadline.tsx', 'features/marketing/components/HeroExample.tsx', 'app/waitlist/page.tsx', 'app/pricing/page.tsx', 'features/auth/components/AuthShell.tsx', 'features/calendar/components/EarningsCalendarPage.tsx', 'features/calendar/components/MonthView.tsx', 'features/calendar/components/WeekView.tsx']) {
      expect(rels.has(rel), rel).toBe(true)
    }
    const marked = SOURCES.filter(({ sf }) => {
      let found = false
      visit(sf, (n) => {
        if (ts.isJsxElement(n) && classTokens(n.openingElement).includes('en-mark')) found = true
      })
      return found
    }).map((s) => s.rel)
    expect(marked).toEqual(expect.arrayContaining(['features/marketing/components/HeroHeadline.tsx', 'app/waitlist/page.tsx', 'features/auth/components/AuthShell.tsx']))
  })
})
