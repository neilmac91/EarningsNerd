import { readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Config } from 'tailwindcss'
import resolveConfig from 'tailwindcss/resolveConfig'
import ts from 'typescript'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { Badge, buttonVariants, countControlClass, type BadgeVariant, type ButtonVariant, type CountControlKind } from '@/components/ui'
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
 *    own bindings: a variable (its initializer, every value the file assigns it, destructured or not,
 *    and every value it puts in it: a push, an unshift, a splice's inserts, a fill's value or a Set's
 *    add, an index or a field it sets, a compound assignment's included, or the fields Object.assign
 *    copies, from a spread of sources too, along a chain of fields), a field, an index, a
 *    destructured name and its default (a rest element read as the whole it is taken from, so it
 *    fails closed on what comes before it), a loop's variable, and a function's parameter, which
 *    takes its default and what the file's own calls hand it (an argument in its place, or the
 *    members an array method hands its callback, written inline or held in a name); a call holds and
 *    renders what its callbacks, its own same-file function or a useMemo returns, and Object.assign
 *    its target with the fields it copies. Arrays and objects are read through a spread, an object's
 *    values, keys and entries, a call that keeps its members or returns one (each array method that
 *    returns a list of them, slice, filter, concat and flat among them, with the values toSpliced,
 *    with and fill add; a Set, Array.from, Children.toArray; at, find, pop, shift), a map's returns
 *    and a join, and one rendered whole renders every member. React's child utilities are named
 *    through the checker, however a call reaches them (an aliased import, a destructured, held or
 *    bound method, a field or a key that holds one, a function that returns one, a name that may be
 *    undefined), and a callee typed over (`const one: (c: ReactNode) => ReactNode = Children.only`)
 *    is read through the one walk, so every binding above carries one:
 *    Children.toArray keeps the children it is given (one that is no array is a member), Children.map
 *    and forEach hand their callback each, Children.only and cloneElement render the element they are
 *    given, and the children a clone or createElement hands an element (from the third argument on,
 *    or the props written in the call) render in its place, a clone's unless the element it clones
 *    sets an ink of its own. A key the scan cannot read may land on any member, so every member is
 *    read; a parameter bound at several calls takes every call's value, so a function that renders it
 *    in sage fails on any call that hands it a digit; and a binding the walk meets again (a function
 *    that hands a parameter to itself) ends there.
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
 *    from an app component followed through the checker: one that renders its children in sage (the
 *    walk carries them from its props through every binding above and React's child utilities; a
 *    field of that name read off anything else is no child of its) is a sage element, and one that
 *    renders a number in the ink it inherits (what a same-file helper returns included) fails inside
 *    a sage parent, or given sage where it is used when it hands that className to the element it
 *    returns. A value is read through the type checker (one program from tsconfig.json): a number- or
 *    bigint-typed expression or an array of them (rendered whole or joined, any member that renders
 *    one counting), a template or a call fed one (a formatter, and so also a lookup such as
 *    labelFor(i) or a helper that builds a label), a number's own method, a same-file variable
 *    holding one, a parameter the file's calls hand one (by the type of what each call gives it,
 *    whatever the parameter's own type), or what a callback or a same-file function returns, through
 *    conditionals, `||`, `??`, the right of `&&` (and its left when that can be a number, which
 *    renders a 0) and JSX branches; a comparison is a boolean and renders nothing. A citation whose
 *    bracket is its whole text ("[{n}]") and a link that renders its own address are text. The count
 *    control (frontend/DESIGN_SYSTEM.md) is the second check: a control that rests in sage never
 *    holds its count in a span of its own ink, written inline, held in a same-file variable, or
 *    returned by a same-file function its label calls or maps with (its props are not its label); a
 *    component that renders its children inside a control is one where it is used, its children the
 *    label. Its sage is its own or the element's around it where it is rendered: where it is written,
 *    where the file's bindings carry it when it is held elsewhere (reported there), and, for a
 *    control a component renders in the ink it inherits, where the component is used or the sage
 *    className the component hands to the element it returns. The count control has one source,
 *    countControlClass (components/ui/countControl.ts), read as the classes it returns for the kind
 *    named, and the third check fails a control whose label carries a count and that classes written
 *    in its file turn sage under the pointer, a sage text colour behind a pointer state (a sage fill
 *    recolours an icon, not the label): a hand-built copy of the recipe, on the control, on the
 *    element holding the count (a label span, under the control's group too) or on the control a
 *    same-file wrapper renders its children in, a class helper's return (a function declaration's
 *    too) and a className default counting as written. The label is read through the file's bindings
 *    (a same-file variable, a same-file function's return) and inside an app component in it that
 *    turns its children or a count of its own sage. A count control that never turns sage, and a
 *    countdown on a control that waits, rest in the ink outside the helper, review-checked. The
 *    planted forms in tests/unit/fixtures/brandRule2Forms.tsx, one per way the rule can be broken,
 *    per look-alike that must pass and per known gap, are scored on every run, so the gate's reach
 *    is held as well as its verdict on the app; and a walk the gate asks of a callee that outruns
 *    its step budget fails it, naming the call, rather than hang the suite. Out of a source scan's
 *    reach, and so review-checked (the fixture marks each as a gap): a value held in a string (a
 *    date or an index name computed as text, or any value the server or the model sends as text) or
 *    written in words; a value bound outside the file's own calls (a component's prop, which JSX
 *    binds and the component check reads only for its children and className, a count control handed
 *    as one included, a hook's state, a callback handed through another function's parameter); a
 *    count a component renders in its own ink inside a sage control, sage handed to a component
 *    through a prop other than className, a className given where a component is used that the
 *    component joins with its own ink (cx joins without merging, so CSS order decides), hands to an
 *    element below the one it returns, or never applies (its ink then masks the one the component
 *    inherits), a conditional written in a literal's field, read as written since the scan cannot
 *    tie it to the element's other fields, a clone's or a created element's own ink (a created
 *    component's, any className cloneElement's or createElement's props give it, the Slot pattern
 *    among them, or sage the element it clones sets on the children it is handed), props either is
 *    given held in a name or spread into the ones written in the call (read as none, so the children
 *    they hand are unread and a className they give fails closed), a value put in an array or an
 *    object through another name for it (an alias, or a parameter it is handed to), a value held in
 *    a Map, a method the scan names by what follows the dot (an array's, Object's, a push) called
 *    through a key instead (`labels['slice'](0)`), read as a call it does not know, a React utility
 *    called through call, apply or Reflect.apply, whose callee is lib's, or held under a type of its
 *    own in another file or a class's field, and the count control's recipe rebuilt in another
 *    file's helper; beyond the fixture, a literal another file holds, a colour set by an inline
 *    style or on a pseudo-element, a library component's internals, a component created inside
 *    another's render, reading that one's children through a closure (the lint's
 *    react-hooks/static-components forbids one), and SVG text coloured by attribute (the chart
 *    theme, which carries no sage). A forwarded className is read under the name the props give it,
 *    through a same-file variable or helper holding it and through an object's `className` key, the
 *    arguments of a same-file call at the places a spread among them could leave them, a spread laid
 *    out by the length the checker knows and its own members unread, a rest parameter's member by an
 *    index the checker reads as one number, counted
 *    from the end as `at()` and `length - N` count, or taken by a destructuring of the rest. Neither
 *    check reads one a component forwards through a spread or a conditional return. The one-source
 *    check reads one the component joins with its
 *    own ink, which the ink check leaves to review, and reads an ink a label sets in one state only
 *    (`dark:text-…`) as its own. The waitlist counter's own spec covers the count on the public
 *    pages.
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

/** The array methods that return some of their receiver's own members, so a map over one walks the receiver's
    members; some add members of their own (ADDS_MEMBERS). */
const KEEPS_MEMBERS = new Set(['slice', 'filter', 'toSorted', 'toReversed', 'sort', 'reverse', 'concat', 'toSpliced', 'with', 'splice', 'fill', 'copyWithin'])
/** The arguments a KEEPS_MEMBERS call adds as members, by place (from, up to): toSpliced's inserts, the value `with`
    puts at its index and the one `fill` fills with, never an index or a count. concat adds every argument, a list's
    members or the value itself. */
const ADDS_MEMBERS = new Map<string, readonly [number, number?]>([['toSpliced', [2]], ['with', [1, 2]], ['fill', [0, 1]]])
/** A call that returns its receiver's members with the lists among them opened, to any depth, as React renders a
    nested list's members and a join prints them. */
const FLATTENS = new Set(['flat'])
/** Calls that return one of their receiver's members, read as an index: `at(0)` by its index, the others (`pop` and
    `shift` among them) as a key the scan cannot read. */
const ONE_MEMBER = new Set(['at', 'find', 'findLast', 'pop', 'shift'])
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

/** A call of a method in `names` (`rows.slice(…)`), and `Object.<name>(x)`. */
const method = (v: ts.Expression, names: ReadonlySet<string>): v is ts.CallExpression & { expression: ts.PropertyAccessExpression } =>
  ts.isCallExpression(v) && ts.isPropertyAccessExpression(v.expression) && names.has(v.expression.name.text)
const objectCall = (v: ts.Expression, name: string): v is ts.CallExpression =>
  ts.isCallExpression(v) && ts.isPropertyAccessExpression(v.expression) && ts.isIdentifier(v.expression.expression)
  && v.expression.expression.text === 'Object' && v.expression.name.text === name && v.arguments.length > 0
/** A call or a `new` that keeps what it is given: `Array.from(x)` without a mapper, `new Set(x)`. */
const keepsArgument = (v: ts.Expression): v is ts.CallExpression | ts.NewExpression =>
  (ts.isNewExpression(v) && ts.isIdentifier(v.expression) && v.expression.text === 'Set' && !!v.arguments?.length)
  || (ts.isCallExpression(v) && ts.isPropertyAccessExpression(v.expression) && ts.isIdentifier(v.expression.expression)
    && v.expression.expression.text === 'Array' && v.expression.name.text === 'from' && v.arguments.length === 1)

/** React's child utilities, which hand JSX through: Children's methods, cloneElement and createElement. A call names one
    when what it calls is React's own declaration, however the call reaches it. The checker types it so through an
    aliased import, `React.Children`, a destructured, held or bound method, a field or a key that holds one, a function
    that returns one or a name that may be undefined; and a callee whose type is written over (`const one: (c:
    ReactNode) => ReactNode = Children.only`, a cast, a typed field, member, parameter or return)
    is read through the one walk (`walkLiterals`), which ends at the first value it reaches that is one, so any binding
    the walk follows carries a utility, however it is typed. An array's `map`, the DOM's createElement or a same-file
    `toArray` is not one, unless it is typed as React's, which fails closed. One called through `call`, `apply` or
    `Reflect.apply` is a gap, since what is called is lib's, and so is one held under a type of its own in another
    file or in a class's field, which the walk does not follow. Every call's callee is asked, once: keeping the checker
    to callees under a utility's name saved about a tenth of a second and left a key and a held name unread. */
const REACT_UTILITIES = new Set(['toArray', 'only', 'map', 'forEach', 'cloneElement', 'createElement'])
const REACT_TYPES = /[\\/]node_modules[\\/]@types[\\/]react[\\/]/
/** The React utility a type's call signature is declared as, or undefined. */
function utilityOf(type: ts.Type): string | undefined {
  const declaration = CHECKER.getNonNullableType(type).getCallSignatures()[0]?.declaration
  const name = declaration && !ts.isJSDocSignature(declaration) && declaration.name && ts.isIdentifier(declaration.name) ? declaration.name.text : undefined
  return name && REACT_UTILITIES.has(name) && REACT_TYPES.test(declaration!.getSourceFile().fileName) ? name : undefined
}
/** The React utility a value is once the steps a walk has taken into it are read off its type (`Children` at
    `only`); a node the walk builds has no type, and an index or a key the scan cannot read names none. */
function utilityAlong(at: ts.Expression, path: Step[]): string | undefined {
  if (at.pos < 0) return undefined
  let type = CHECKER.getTypeAtLocation(at)
  for (const step of path) {
    if (typeof step !== 'string') return undefined
    const property = CHECKER.getPropertyOfType(CHECKER.getNonNullableType(type), step)
    if (!property) return undefined
    type = CHECKER.getTypeOfSymbolAtLocation(property, at)
  }
  return utilityOf(type)
}
const UTILITIES = new Map<ts.Node, string | undefined>()
/** The steps one ask of reactUtility may walk, nested asks included. A binding graph that branches out of all
    proportion then fails rule 2 and names its call, instead of hanging the suite: vitest cannot stop a synchronous
    walk. Measured on 2026-10-14, the app's and the fixture's costliest ask took 54 steps (of 698 asks). */
const WALK_BUDGET = 500_000
let walkSteps: number | undefined
class WalkBudgetSpent extends Error {}
const OVER_BUDGET: string[] = []
function reactUtility(v: ts.Expression): string | undefined {
  if (!ts.isCallExpression(v)) return undefined
  if (!UTILITIES.has(v)) {
    // A call met again while its callee is read (a helper that calls itself) names no utility.
    UTILITIES.set(v, undefined)
    const callee = unwrap(v.expression)
    const outermost = walkSteps === undefined
    if (outermost) walkSteps = WALK_BUDGET
    try {
      let name = utilityAlong(callee, [])
      if (!name) walkLiterals(callee, callee.getSourceFile(), [], (at, path) => !!(name ??= utilityAlong(at, path)))
      UTILITIES.set(v, name)
    } catch (error) {
      // A nested ask's spent budget ends the outermost one, which names its call and reads as no utility.
      if (!(error instanceof WalkBudgetSpent) || !outermost) throw error
      const sf = v.getSourceFile()
      OVER_BUDGET.push(`${path.relative(ROOT, sf.fileName)}:${sf.getLineAndCharacterOfPosition(v.getStart()).line + 1} ${v.getText().slice(0, 60)}`)
    } finally {
      if (outermost) walkSteps = undefined
    }
  }
  return UTILITIES.get(v)
}
/** A call that returns a list of members it keeps: a method in KEEPS_MEMBERS or FLATTENS, a Set or Array.from, an
    object's values, keys or entries, and Children.toArray. A map's members are what its callback returns. */
const listCall = (v: ts.Expression): v is ts.CallExpression | ts.NewExpression =>
  method(v, KEEPS_MEMBERS) || method(v, FLATTENS) || keepsArgument(v) || ['values', 'keys', 'entries'].some((name) => objectCall(v, name))
  || reactUtility(v) === 'toArray'
/** The property a props literal sets under a name (`{ className: … }`), or undefined. */
const propOf = (props: ts.Expression | undefined, name: string) => {
  const x = props && unwrap(props)
  return x && ts.isObjectLiteralExpression(x) ? x.properties.find((p) => p.name !== undefined && keyOf(p.name) === name) : undefined
}
/** Whether a cloneElement or createElement call's props give the element a className of its own, which the scan does
    not read (a gap): on a clone it replaces the cloned element's, so that element's ink no longer holds. */
const setsClassName = (props: ts.Expression | undefined) => propOf(props, 'className') !== undefined
/** The children a cloneElement or createElement call hands the element it makes: its arguments from the third on (a
    spread read through), or else the `children` its props set; undefined when it hands none, and a clone keeps its
    element's own. */
function handedChildren(call: ts.CallExpression): ts.Expression[] | undefined {
  if (call.arguments.length > 2) return call.arguments.slice(2).map((a) => (ts.isSpreadElement(a) ? a.expression : a))
  const children = propOf(call.arguments[1], 'children')
  return children && ts.isPropertyAssignment(children) ? [children.initializer]
    : children && ts.isShorthandPropertyAssignment(children) ? [children.name] : undefined
}
/** Whether a cloneElement call renders the element it clones as that element: its props give the clone no className,
    and it hands the clone no children of its own. */
const clonesAsIs = (call: ts.CallExpression) => reactUtility(call) === 'cloneElement' && !handedChildren(call) && !setsClassName(call.arguments[1])

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
    hands the parameter at `at` (read `loose`, a child that is no array being one, for React's Children). A site that
    holds only `when` its call is Children.map's or forEach's, or `unless` it is, is asked when it is read. */
interface Site { args?: ts.NodeArray<ts.Expression>; members?: ts.Expression; at?: number; loose?: boolean; when?: ts.CallExpression; unless?: ts.CallExpression }
const SITES = new Map<ts.SourceFile, Map<ts.Node, Site[]>>()
const handsChildren = (call: ts.CallExpression) => ['map', 'forEach'].includes(reactUtility(call) ?? '')
/** Where a function's parameters take their values, indexed once per file: every call that names it, every array
    method it is handed to (`rows.map(render)`, its callback written inline or named, the members landing where
    HANDS_MEMBERS says), Array.from's mapper (its source's members), and Children.map's and forEach's callback (the
    children's). Which calls are Children's is asked when a site is read, not while the index is built, since
    reactUtility's walk reads parameters through this index. A component's props come from JSX, which the component
    check reads (its children and className), so a tag is no call here. */
function sitesOf(fn: ts.Node): Site[] {
  const sf = fn.getSourceFile()
  let sites = SITES.get(sf)
  if (!sites) {
    const index = new Map<ts.Node, Site[]>()
    const add = (f: ts.Node, site: Site) => index.set(f, [...(index.get(f) ?? []), site])
    visit(sf, (n) => {
      if (!ts.isCallExpression(n)) return
      const callee = unwrap(n.expression)
      if (n.arguments[1]) for (const f of functionsOf(n.arguments[1])) add(f, { members: n.arguments[0], at: 0, loose: true, when: n })
      if (ts.isPropertyAccessExpression(callee)) {
        const at = HANDS_MEMBERS.get(callee.name.text)
        if (at !== undefined && n.arguments[0]) for (const f of functionsOf(n.arguments[0])) add(f, { members: callee.expression, at, unless: n })
        if (callee.name.text === 'from' && ts.isIdentifier(callee.expression) && callee.expression.text === 'Array' && n.arguments[1]) {
          for (const f of functionsOf(n.arguments[1])) add(f, { members: n.arguments[0], at: 0 })
        }
      }
      for (const f of functionsOf(callee)) add(f, { args: n.arguments })
    })
    SITES.set(sf, sites = index)
  }
  return (sites.get(fn) ?? []).filter((site) => (!site.when || handsChildren(site.when)) && (!site.unless || !handsChildren(site.unless)))
}

/** A value a name holds, and the steps from it to the name's place (`[label] = LABELS` holds LABELS at index 0). */
interface Held { value: ts.Expression; steps: Step[] }
/** The array a push, an unshift, a splice or an index assignment leaves its values in: they are members, at a place
    that depends on what the array held before, so the spread first makes any index read every member. */
const placed = (values: readonly ts.Expression[]) =>
  ts.factory.createArrayLiteralExpression([ts.factory.createSpreadElement(ts.factory.createArrayLiteralExpression()), ...values])
/** The methods that put their arguments in an array (or a Set: `add`), by place (from, up to): `fill` puts its value,
    not its range. `add` is matched on any receiver: on one that is no Set (a classList, a date) it leaves a value where
    nothing renders it as a list. */
const PUTS_MEMBERS = new Map<string, readonly [number, number?]>([['push', [0]], ['unshift', [0]], ['splice', [2]], ['add', [0]], ['fill', [0, 1]]])
/** What a value put at a place can be, read as code (a literal's own fields are read as written): either side of a
    conditional, `??` or `||`. */
const branches = (v: ts.Expression): ts.Expression[] => {
  const x = unwrap(v)
  if (ts.isConditionalExpression(x)) return [x.whenTrue, x.whenFalse].flatMap(branches)
  if (ts.isBinaryExpression(x) && [ts.SyntaxKind.QuestionQuestionToken, ts.SyntaxKind.BarBarToken].includes(x.operatorToken.kind)) {
    return [x.left, x.right].flatMap(branches)
  }
  return [v]
}
/** The variable a place is read off and the steps to it (`groups[k].items` is `groups` at [null, 'items']). */
function placeOf(target: ts.Expression): { root: ts.Identifier; path: Step[] } | undefined {
  const path: Step[] = []
  let x = unwrap(target)
  while (ts.isPropertyAccessExpression(x) || ts.isElementAccessExpression(x)) {
    path.unshift(ts.isPropertyAccessExpression(x) ? x.name.text : accessStep(x.argumentExpression))
    x = unwrap(x.expression)
  }
  return ts.isIdentifier(x) ? { root: x, path } : undefined
}
/** What a variable holds once the file puts a value at a place in it: the value in an object at each field on the
    way, among an array's members at an index (`placed`), and either for a key the scan cannot read (built as
    `[true]`, a computed key `keyOf` cannot read either, and no identifier a reader could take for a name). */
const placeAt = (path: Step[], value: ts.Expression): ts.Expression[] =>
  path.reduceRight<ts.Expression[]>((inner, step) => inner.flatMap((v) => [
    ...(typeof step === 'number' ? [] : [ts.factory.createObjectLiteralExpression([ts.factory.createPropertyAssignment(
      step === null ? ts.factory.createComputedPropertyName(ts.factory.createTrue()) : ts.factory.createStringLiteral(step), v)])]),
    ...(typeof step === 'string' ? [] : [placed([v])]),
  ]), [value])
const ASSIGNED = new Map<ts.SourceFile, Map<ts.Symbol, Held[]>>()
/** What a same-file variable holds: its initializer and every value the file assigns it (`label = 'Ready'` in a
    switch, `label += …`, or `[label] = …` and `({ label } = …)` destructured, a default in the pattern and a rest
    target included) or
    puts in it (`labels.push(…)`, an unshift, a splice or a Set's add, `labels[i] = …`, `row.label = …` or `??=`,
    `||=`, `+=`, and each source's fields `Object.assign(row, …)` copies), the assignments indexed once per file. */
function variableValues(declaration: ts.VariableDeclaration): Held[] {
  const sf = declaration.getSourceFile()
  let index = ASSIGNED.get(sf)
  if (!index) {
    const found = new Map<ts.Symbol, Held[]>()
    const add = (symbol: ts.Symbol | undefined, held: Held) => { if (symbol) found.set(symbol, [...(found.get(symbol) ?? []), held]) }
    // A value put at a place in a variable (`placeAt`): a field or an index it sets, or an array a method fills.
    const put = (target: ts.Expression, value: ts.Expression) => {
      const place = placeOf(target)
      if (!place) return
      for (const held of branches(value).flatMap((v) => placeAt(place.path, v))) add(CHECKER.getSymbolAtLocation(place.root), { value: held, steps: [] })
    }
    const assign = (target: ts.Expression, value: ts.Expression, steps: Step[]): void => {
      const t = unwrap(target)
      if (ts.isIdentifier(t)) add(CHECKER.getSymbolAtLocation(t), { value, steps })
      else if (!steps.length && (ts.isPropertyAccessExpression(t) || ts.isElementAccessExpression(t))) put(t, value)
      else if (ts.isBinaryExpression(t) && t.operatorToken.kind === ts.SyntaxKind.EqualsToken) {
        assign(t.left, value, steps)
        assign(t.left, t.right, [])
      } else if (ts.isArrayLiteralExpression(t)) {
        // A rest target holds what the others leave, read as the whole it is taken from: an array's members, any of which
        // an index into it may land on (a spread of the value), or the object with every key, as `bindingOf` reads one.
        t.elements.forEach((element, i) => {
          if (ts.isSpreadElement(element)) assign(element.expression, ts.factory.createArrayLiteralExpression([ts.factory.createSpreadElement(value)]), steps)
          else if (!ts.isOmittedExpression(element)) assign(element, value, [...steps, i])
        })
      } else if (ts.isObjectLiteralExpression(t)) {
        for (const property of t.properties) {
          if (ts.isSpreadAssignment(property)) assign(property.expression, value, steps)
          else if (ts.isPropertyAssignment(property)) assign(property.initializer, value, [...steps, keyOf(property.name)])
          else if (ts.isShorthandPropertyAssignment(property)) {
            const symbol = CHECKER.getShorthandAssignmentValueSymbol(property)
            add(symbol, { value, steps: [...steps, property.name.text] })
            if (property.objectAssignmentInitializer) add(symbol, { value: property.objectAssignmentInitializer, steps: [] })
          }
        }
      }
    }
    visit(sf, (n) => {
      if (ts.isCallExpression(n) && ts.isPropertyAccessExpression(n.expression) && PUTS_MEMBERS.has(n.expression.name.text)) {
        put(n.expression.expression, placed(n.arguments.slice(...PUTS_MEMBERS.get(n.expression.name.text)!).flatMap(branches)))
        return
      }
      // Object.assign copies each source's fields into its target; a spread hands it a list of sources, any member of
      // which may be one (read through a key the scan cannot read, `[true]`, as `placeAt` builds one).
      if (ts.isCallExpression(n) && objectCall(n, 'assign')) {
        const [target, ...sources] = n.arguments
        for (const source of sources) {
          put(target, ts.isSpreadElement(source) ? ts.factory.createElementAccessExpression(source.expression, ts.factory.createTrue()) : source)
        }
        return
      }
      if (!ts.isBinaryExpression(n)) return
      const operator = n.operatorToken.kind
      if (operator < ts.SyntaxKind.FirstAssignment || operator > ts.SyntaxKind.LastAssignment) return
      // A compound assignment (`+=`, `??=`) adds its right side, to a variable or at a place in one; only `=`
      // destructures.
      const left = unwrap(n.left)
      if (ts.isIdentifier(left)) add(CHECKER.getSymbolAtLocation(left), { value: n.right, steps: [] })
      else if (operator === ts.SyntaxKind.EqualsToken) assign(n.left, n.right, [])
      else if (ts.isPropertyAccessExpression(left) || ts.isElementAccessExpression(left)) put(left, n.right)
    })
    ASSIGNED.set(sf, index = found)
  }
  const symbol = CHECKER.getSymbolAtLocation(declaration.name)
  return [...(declaration.initializer ? [{ value: declaration.initializer, steps: [] }] : []), ...((symbol && index.get(symbol)) ?? [])]
}

/** Where a name is bound: the variable or parameter its destructuring climbs to, the steps from that declaration's
    value to the name's place, and each default met on the way with the steps below it (a parameter's own default
    last). A rest element holds what the others leave and is read as the whole it is taken from: an object by the key
    asked for, one the others took included, and an array's members, any of which an index into it may land on, so
    it fails closed on what the others took. */
interface Binding { declaration: ts.Node | undefined; steps: Step[]; defaults: Held[] }
function bindingOf(symbol: ts.Symbol | undefined, path: Step[]): Binding {
  const steps = [...path]
  const defaults: Held[] = []
  let declaration: ts.Node | undefined = symbol?.valueDeclaration
  while (declaration && ts.isBindingElement(declaration)) {
    const pattern = declaration.parent
    if (declaration.dotDotDotToken) {
      if (ts.isArrayBindingPattern(pattern) && steps.length) steps[0] = null
    } else {
      if (declaration.initializer) defaults.push({ value: declaration.initializer, steps: [...steps] })
      steps.unshift(ts.isObjectBindingPattern(pattern) ? keyOf(declaration.propertyName ?? declaration.name) : pattern.elements.indexOf(declaration))
    }
    declaration = pattern.parent
  }
  if (declaration && ts.isParameter(declaration) && declaration.initializer) defaults.push({ value: declaration.initializer, steps: [...steps] })
  return { declaration, steps, defaults }
}

/** The mark a function's first parameter holds at its `children`: a component's props are bound by JSX where it is
    used, not by the file's calls, so what reads their children holds this instead, through every binding the walk
    follows (`literalExpressions`), and the component summary can tell what reaches them. One per parameter, it
    renders nothing and names nothing. */
const CHILDREN_MARKS = new Map<ts.ParameterDeclaration, ts.Expression>()
const MARKS = new Set<ts.Node>()
function childrenMark(props: ts.ParameterDeclaration): ts.Expression {
  let mark = CHILDREN_MARKS.get(props)
  if (!mark) {
    CHILDREN_MARKS.set(props, (mark = ts.factory.createObjectLiteralExpression()))
    MARKS.add(mark)
  }
  return mark
}

/** The literals an expression holds when it reads a same-file literal, through the file's own bindings: a
    variable's initializer and every value the file assigns it or puts in it (`CONFIG.step`, `STEPS[0]`, `const
    first = STEPS[0]`, `let label` set in a switch or destructured into, `labels.push(…)`), a call's return (a
    same-file function's, or a useMemo's callback's), a destructured name with its default (`const { cls } = TONES[tone]
    ?? TONES.flat`, `({ step = 'Step 1' })`, `({ step: s })`, `([q])`), a for…of variable (the array's members) or
    a for…in one (the object's keys), and a parameter: its default, and whatever the file binds it to at
    `sitesOf`'s calls (an argument in its place, or the members of the array a method hands it, its callback
    written inline or named: `ARRAY.map((item) => …)`, `ARRAY.map(render)`, a nested map over an element's field
    included), whose children, when it is a function's first parameter, are held as their mark (`childrenMark`).
    Arrays and objects are read through a spread, a shorthand property through the name it holds, an object
    through Object.values, keys and entries, an array through a call that keeps its members (`slice`, `filter`,
    `concat`, `flat` …), a Set, Array.from or Children.toArray, and a map through what its callback returns; a member
    through `at`, `find` and `findLast`, a join through every member it joins, the element Children.only or a clone
    renders, and the chain through `??`, `||` and conditionals.
    A value written in a literal is read as written: a conditional there is not split, since the scan cannot tie it
    to the element's other fields (the pricing cards' call to action takes its button's variant and its label
    from the same plan). A key the scan cannot read (`LABELS[i]`, a computed key, `find`), or an index into an
    array with a spread or through such a call, may land on any member, so every member is read; a parameter the
    file binds at several calls takes every call's value, so a function that renders it in sage fails on any call
    that hands it a digit, and a binding met again on the way reads only its defaults, so a function that hands a
    parameter to itself ends in time. Names resolve through the checker, so an index, a shadowing binding, a prop
    or an import is never taken for a literal. */
const LITERALS = new Map<ts.Node, ts.Expression[]>()
/** The same read as a list (`[null]`: every member it may hold), which the walks ask of what a list renders. */
const LIST_LITERALS = new Map<ts.Node, ts.Expression[]>()
function literalExpressions(e: ts.Expression, sf: ts.SourceFile, path: Step[] = []): ts.Expression[] {
  const cache = !path.length ? LITERALS : path.length === 1 && path[0] === null ? LIST_LITERALS : undefined
  if (!cache) return walkLiterals(e, sf, path)
  let found = cache.get(e)
  if (!found) cache.set(e, (found = walkLiterals(e, sf, path)))
  return found
}
function walkLiterals(e: ts.Expression, sf: ts.SourceFile, path: Step[], stop?: (at: ts.Expression, path: Step[]) => boolean): ts.Expression[] {
  // What an expression holds once the path is walked into it; `inLiteral` marks a value written in a literal.
  const held = (x: ts.Expression, path: Step[], depth: number, inLiteral = false): ts.Expression[] => {
    if (depth > 24) return []
    if (walkSteps !== undefined && --walkSteps < 0) throw new WalkBudgetSpent()
    const at = unwrap(x)
    // Any part of a component's children is its children.
    if (MARKS.has(at)) return [at]
    // A walk that looks for a value (reactUtility's, for a callee's utility) ends where it finds one.
    if (stop?.(at, path)) return []
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
    // Object.assign returns its target, with its sources' fields: any of them may hold the field asked for.
    if (objectCall(at, 'assign')) return at.arguments.flatMap((a) => (ts.isSpreadElement(a) ? held(a.expression, [null, ...path], depth + 1) : held(a, path, depth + 1)))
    // A call holds what its same-file function returns (`build()`), and useMemo what its callback returns; a function
    // met again on the way (one that returns a call of itself) holds nothing more. Children.only holds the element it is
    // given, and so does cloneElement while it gives the clone no children or className of its own.
    if (ts.isCallExpression(at)) {
      if ((reactUtility(at) === 'only' || clonesAsIs(at)) && at.arguments[0]) return held(at.arguments[0], path, depth + 1)
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
    // A shorthand property's name (`{ children }`, handed to a clone) holds what the name it repeats holds.
    if (ts.isIdentifier(at)) {
      const parent = at.parent
      const shorthand = !!parent && ts.isShorthandPropertyAssignment(parent) && parent.name === at
      return bound(shorthand ? CHECKER.getShorthandAssignmentValueSymbol(parent) : CHECKER.getSymbolAtLocation(at), path, depth + 1)
    }
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
      // A first parameter read at its children, or by a key the scan cannot read, may be a component's children.
      const children = at === 0 && (steps[0] === 'children' || steps[0] === null) ? [childrenMark(declaration)] : []
      return [...defaults, ...children, ...sitesOf(declaration.parent).flatMap((site) => {
        if (site.members) {
          return site.at === at && !declaration.dotDotDotToken ? members(site.members, depth + 1, site.loose).flatMap((member) => held(member, steps, depth + 1, true)) : []
        }
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
  // The members of the arrays an expression holds: an array literal's, through a spread; a call's that keeps them
  // (concat's arguments' too, and flat's with the lists among them opened), or keeps what it is given; an object's
  // values, keys or entries (each a [key, value] pair); a map's returns; a component's children, whose members are its
  // children. A `loose` read takes a value that is no list as its one member, as React reads children:
  // Children.toArray's, what Children.map and forEach hand their callback, what concat is given, and the receiver of a
  // call that keeps its members, so a string's slice or concat keeps its text.
  const members = (x: ts.Expression, depth: number, loose = false): ts.Expression[] =>
    held(x, [], depth + 1).flatMap((v) => {
      if (MARKS.has(v)) return [v]
      if (method(v, KEEPS_MEMBERS)) {
        const name = v.expression.name.text
        const added = name === 'concat'
          ? v.arguments.flatMap((a) => members(ts.isSpreadElement(a) ? a.expression : a, depth + 1, !ts.isSpreadElement(a)))
          : v.arguments.slice(...(ADDS_MEMBERS.get(name) ?? [0, 0])).flatMap((a) => (ts.isSpreadElement(a) ? members(a.expression, depth + 1) : [a]))
        return [...members(v.expression.expression, depth + 1, true), ...added]
      }
      if (method(v, FLATTENS)) return members(v.expression.expression, depth + 1).flatMap((m) => opened(m, depth + 1))
      if (keepsArgument(v)) return members(v.arguments![0], depth + 1)
      if (reactUtility(v) === 'toArray') return ts.isCallExpression(v) && v.arguments[0] ? members(v.arguments[0], depth + 1, true) : []
      if (objectCall(v, 'values')) return held(v.arguments[0], [null], depth + 1)
      if (objectCall(v, 'keys')) return pairs(v.arguments[0], depth + 1).map(([key]) => key).filter((key) => !ts.isOmittedExpression(key))
      if (objectCall(v, 'entries')) {
        return pairs(v.arguments[0], depth + 1).flatMap(([key, values]) => values.map((value) => ts.factory.createArrayLiteralExpression([key, value])))
      }
      if (method(v, MAPS)) return mapped(v, depth + 1)
      if (!ts.isArrayLiteralExpression(v)) return loose ? [v] : []
      return v.elements.flatMap((m) => (ts.isSpreadElement(m) ? members(m.expression, depth + 1) : ts.isOmittedExpression(m) ? [] : [m]))
    })
  // A member `flat` opens: the members of a list it holds, each opened in turn; anything else, itself.
  const opened = (m: ts.Expression, depth: number): ts.Expression[] =>
    held(m, [], depth + 1).flatMap((v) => (!MARKS.has(v) && (ts.isArrayLiteralExpression(v) || listCall(v)) ? members(v, depth + 1).flatMap((inner) => opened(inner, depth + 1)) : [v]))
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
    const lists = listCall(v) || method(v, MAPS)
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
      // A call reads what the same-file function it calls returns (`className={quiet()}`, a function declaration's
      // included); the count control's helper is read by its kind instead (`countControlTokens`).
      if (ts.isCallExpression(n) && !countControlCall(n)) {
        for (const r of functionsOf(n.expression).flatMap(returnedExpressions)) {
          if (nodes.includes(r)) continue
          nodes.push(r)
          follow(r)
        }
      }
      // A node the scan builds has no parent; none is an identifier (`placeAt`'s unreadable key is `[true]`), and this
      // keeps one from crashing the reader if it ever is.
      if (!ts.isIdentifier(n) || !n.parent || (ts.isPropertyAccessExpression(n.parent) && n.parent.name === n)) return
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

/** Every string a className attribute can produce, split into tokens, with the count control's recipe wherever a
    call composes it (`countControlTokens`); `written` reads the classes written in the file alone. */
function classTokens(opening: ts.JsxOpeningLikeElement, written = false): string[] {
  const parts: string[] = []
  const read = (n: ts.Node): void => {
    if (countControlCall(n)) {
      if (!written) parts.push(...countControlTokens(n))
      return
    }
    const text = ts.isJsxText(n) ? null : literalText(n)
    if (text !== null) parts.push(text)
    ts.forEachChild(n, read)
  }
  for (const node of classNameNodes(opening)) read(node)
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

/** The count control's recipe (components/ui/countControl.ts): a call to it in a className is read as the classes the
    helper returns for the kind it names, or for every kind when the scan cannot read the kind, so a site that composes
    it is read as if the recipe were written there. The kinds are asked of the helper's own type. */
const COUNT_CONTROL = declaredFunction('components/ui/countControl.ts', 'countControlClass')
const COUNT_KINDS = unionMembers('components/ui/countControl.ts', 'CountControlKind') as CountControlKind[]
function countControlCall(n: ts.Node): n is ts.CallExpression {
  if (!ts.isCallExpression(n)) return false
  const declaration = declarationOf(unwrap(n.expression))
  return !!declaration && functionOf(declaration) === COUNT_CONTROL
}
function countControlTokens(call: ts.CallExpression): string[] {
  const named = call.arguments[0] ? variantLiterals(call.arguments[0]) : []
  const kinds = named.length && named.every((kind) => (COUNT_KINDS as string[]).includes(kind)) ? (named as CountControlKind[]) : COUNT_KINDS
  return kinds.flatMap((kind) => countControlClass(kind).split(/\s+/))
}

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

/** A cached read that can meet itself while it runs: a component that renders itself, two that render each other, an
    element whose ink is its component's. Met again while in progress, it gives `placeholder`, and its result is kept
    only when it read nothing still in progress below it: a read inside a cycle depends on the unfinished value of the
    cycle's outermost member, so it is read again once that member is done, and no verdict hangs on the order the scan
    meets the members in. */
const IN_PROGRESS: ts.Node[] = []
let outermostRead = Infinity
function memo<V>(cache: Map<ts.Node, V>, key: ts.Node, placeholder: V, compute: () => V): V {
  const known = cache.get(key)
  if (known !== undefined) return known
  const at = IN_PROGRESS.indexOf(key)
  if (at !== -1) {
    outermostRead = Math.min(outermostRead, at)
    return placeholder
  }
  const outer = outermostRead
  outermostRead = Infinity
  IN_PROGRESS.push(key)
  try {
    const value = compute()
    if (outermostRead >= IN_PROGRESS.length - 1) cache.set(key, value)
    return value
  } finally {
    IN_PROGRESS.pop()
    outermostRead = Math.min(outer, outermostRead)
  }
}

const COLOURS = new Map<ts.Node, Ink>()
/** The ink an element gives its children: 'sage' or 'other' when it sets a resting text colour, null when
    they inherit its parent's. The call site's ink first; then, for a component the app declares, the ink it
    renders its children in, so a component that wraps its children in sage is a sage element. */
function textColour(opening: ts.JsxOpeningLikeElement): Ink {
  return memo(COLOURS, opening, null, () => {
    const ink = siteInk(opening)
    if (ink !== null) return ink
    const fn = componentFunction(opening)
    return fn ? summary(fn).childrenInk : null
  })
}

/** Whether a node holds JSX anywhere in it. */
function containsJsx(node: ts.Node): boolean {
  let found = false
  visit(node, (n) => { if (ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n) || ts.isJsxFragment(n)) found = true })
  return found
}

/** The JSX a name or a call holds through the file's bindings (`const body = <span>{children}</span>`, each JSX value a
    `let` is assigned, a helper's parameter handed a label, the element Children.only renders), once per walk; none for
    one that holds no JSX, which the value reading takes instead. A call the walk reads no further holds itself, which
    is no JSX held elsewhere: the caller walks it where it stands. */
function heldJsx(e: ts.Expression, sf: ts.SourceFile, followed: Set<ts.Node>): ts.Expression[] {
  return literalExpressions(e, sf).filter((v) => {
    if (v === unwrap(e) || followed.has(v) || !containsJsx(v)) return false
    followed.add(v)
    return true
  })
}

/** A cloneElement or createElement call: one that makes an element. */
const makesElement = (call: ts.CallExpression) => ['cloneElement', 'createElement'].includes(reactUtility(call) ?? '')
/** The children a cloneElement or createElement call hands the element it makes (`handedChildren`), which render in
    its place, in that element's ink: none when its props set a className, which the scan does not read, or when a
    clone renders them in an ink of the cloned element's own, since every element it can clone sets one (one the scan
    cannot read inherits). A created element's own ink, its type's or its props', is not read: its children render in
    the ink it inherits. */
function elementChildren(call: ts.CallExpression, sf: ts.SourceFile): ts.Expression[] {
  const handed = handedChildren(call)
  if (!handed || setsClassName(call.arguments[1])) return []
  if (reactUtility(call) === 'cloneElement') {
    const elements = call.arguments[0] ? literalExpressions(call.arguments[0], sf).filter((v) => ts.isJsxElement(v) || ts.isJsxSelfClosingElement(v)) : []
    if (elements.length && elements.every((el) => textColour(ts.isJsxElement(el) ? el.openingElement : el) !== null)) return []
  }
  return handed
}

/** What a component does with the ink it inherits: the ink its children render in (null when they inherit
    it too), whether it renders a number of its own in that inherited ink, which a sage parent colours, whether
    it renders a control in it that holds its count in an ink of its own (the count control's form), and whether it
    renders its children inside a control, which makes it one where it is used (they are that control's label). And
    what the one-source check reads of it: whether classes written in its file turn its children sage under the
    pointer, inside its control (`childrenInHoverSage`) or anywhere (`childrenTurnSage`, a label component), whether
    they turn a count of its own so (`countTurnsSage`), and whether it hands its className to the element it returns
    and renders a count in that element's ink (`rootCount`), which classes given where it is used reach. */
interface Summary {
  childrenInk: Ink
  inheritsValue: boolean
  inheritsControl: boolean
  childrenInControl: boolean
  childrenInHoverSage: boolean
  childrenTurnSage: boolean
  countTurnsSage: boolean
  rootCount: boolean
}
const SUMMARIES = new Map<ts.Node, Summary>()
/** A component met again mid-walk (one that renders itself) reads as one that passes its ink through and carries
    nothing (`memo`). */
const NO_SUMMARY: Summary = {
  childrenInk: null, inheritsValue: false, inheritsControl: false, childrenInControl: false, childrenInHoverSage: false,
  childrenTurnSage: false, countTurnsSage: false, rootCount: false,
}
function summary(fn: ts.FunctionLikeDeclaration): Summary {
  return memo(SUMMARIES, fn, NO_SUMMARY, () => summarize(fn))
}
function summarize(fn: ts.FunctionLikeDeclaration): Summary {
  const sf = fn.getSourceFile()
  const childInks = new Set<'sage' | 'other' | 'inherit'>()
  let carries = false
  let controls = false
  // How many controls the walk is inside, and whether it has met the children inside one.
  let inControl = 0
  let childrenInControl = false
  // The elements the walk is inside, outermost first, each with what the walk read of it where it met it: whether it
  // is a control, the ink it sets (textColour) and whether classes written in its file turn what it renders in that
  // ink sage under the pointer (turnsSageUnderPointer). Whether the control its children render in, or an element
  // between them, turns them sage under the pointer is a wrapper holding the recipe.
  const inside: { opening: ts.JsxOpeningLikeElement; control: boolean; own: Ink; turns: boolean }[] = []
  let childrenInHoverSage = false
  // Whether what renders at the walk's place turns sage under the pointer: the nearest element around it that turns
  // sage under the pointer comes before any that sets an ink of its own, as a label span holds its count in its own
  // ink (`labelTurnsSage`).
  let childrenTurnSage = false
  let countTurnsSage = false
  const underPointerSage = () => {
    for (let i = inside.length - 1; i >= 0; i--) {
      if (inside[i].turns) return true
      if (inside[i].own !== null) return false
    }
    return false
  }
  // Whether a count rendered here takes the ink of the element the component returns, which a className it forwards
  // reaches: the root it sits in takes the className, and no element between them sets an ink of its own. Read only
  // for a component that forwards it, so a return whose root does not take it holds no such count.
  const forwards = forwardsClassName(fn)
  let rootCount = false
  const inRootInk = () => forwards && inside.length > 0 && takesClassName(inside[0].opening)
    && inside.slice(1).every((entry) => entry.own === null)
  // A count rendered here: one in the inherited ink, one an element around it turns sage under the pointer, and one in
  // the forwarded className's reach. The value is read only when one of them can hold.
  const counted = (ink: 'sage' | 'other' | 'inherit', counts: () => boolean) => {
    const pointer = underPointerSage()
    const root = inRootInk()
    if ((ink !== 'inherit' && !pointer && !root) || !counts()) return
    if (ink === 'inherit') carries = true
    if (pointer) countTurnsSage = true
    if (root) rootCount = true
  }
  const props = fn.parameters[0]
  const takesChildren = !!props && !!CHECKER.getTypeAtLocation(props).getProperty('children')
  // The children, however the component reaches them from its props: the walk carries their mark (`childrenMark`)
  // through every binding it follows, so `props.children`, `{ children: content }`, `const items =
  // Children.toArray(children)`, `[first] = …`, a helper's parameter handed them, the callback Children.map or a map
  // hands their members, what a same-file function, a map's callback or a useMemo returns, a member or a list of them,
  // and the one child Children.only or a clone renders all reach them, and a field of that name read off anything else
  // (a row's `item.children`) does not. A list renders its members, so one that holds them reaches them too.
  const mark = props && childrenMark(props)
  // JSX written here and literal text are the component's own; anything else may hold its children, whole or as a list.
  const isChildren = (x: ts.Expression) => !!mark && !ts.isJsxElement(x) && !ts.isJsxSelfClosingElement(x) && !ts.isJsxFragment(x)
    && literalText(x) === null && (literalExpressions(x, sf).includes(mark) || literalExpressions(x, sf, [null]).includes(mark))
  const followed = new Set<ts.Node>()
  const element = (el: ts.JsxElement | ts.JsxSelfClosingElement, ink: 'sage' | 'other' | 'inherit') => {
    const opening = ts.isJsxElement(el) ? el.openingElement : el
    // An app component's summary, read once for every fact below: inside a cycle of components a summary is read
    // afresh each time it is asked for (`memo`), so a second read per element would multiply the walk. A control's
    // own-ink check (`ownInkCounts`) still reads the components inside it again.
    const fn = componentFunction(opening)
    const s = fn ? summary(fn) : undefined
    const site = siteInk(opening)
    const own = site ?? (s ? s.childrenInk : null)
    const next = own ?? ink
    // A spread can carry the children through (`<span {...rest} />`).
    if (takesChildren && opening.attributes.properties.some((p) => ts.isJsxSpreadAttribute(p))) childInks.add(next)
    // A component that renders a number in the ink it inherits (`inheritsValue`): the ink here, an element around it
    // that turns sage under the pointer, or the forwarded className's reach colours it.
    if (site === null && s?.inheritsValue) {
      if (ink === 'inherit') carries = true
      if (underPointerSage()) countTurnsSage = true
      if (inRootInk()) rootCount = true
    }
    // A root that hands the forwarded className on to a component that forwards it to its count
    // (`<Inner n={n} className={className} />`) reaches that count too.
    if (forwards && !inside.length && s?.rootCount && takesClassName(opening)) rootCount = true
    // A component that turns a count it renders sage under the pointer itself (`countUnderPointer`).
    const written = classTokens(opening, true).some(sageUnderPointer)
    if (s && (s.countTurnsSage || (written && s.rootCount))) countTurnsSage = true
    const control = isControl(opening, s)
    if (next === 'inherit' && ((ts.isJsxElement(el) && control && ownInkCounts(el, sf).length) || (site === null && s?.inheritsControl))) controls = true
    if (!ts.isJsxElement(el)) return
    inside.push({ opening, control, own, turns: written || !!s?.childrenTurnSage })
    if (control) inControl++
    children(el.children, next)
    if (control) inControl--
    inside.pop()
  }
  const children = (list: ts.NodeArray<ts.JsxChild>, ink: 'sage' | 'other' | 'inherit') => {
    list.forEach((child, i) => {
      if (ts.isJsxText(child)) { if (carriesDigit(child.text)) counted(ink, () => true) }
      else if (ts.isJsxExpression(child) && child.expression) { if (!citationBracket(list, i) && !bracketTemplate(child.expression)) expression(child.expression, ink) }
      else if (ts.isJsxElement(child) || ts.isJsxSelfClosingElement(child)) element(child, ink)
      else if (ts.isJsxFragment(child)) children(child.children, ink)
    })
  }
  const expression = (e: ts.Expression, ink: 'sage' | 'other' | 'inherit') => {
    const x = unwrap(e)
    if (ts.isConditionalExpression(x)) { expression(x.whenTrue, ink); expression(x.whenFalse, ink); return }
    if (ts.isBinaryExpression(x)) { valueOperands(x).forEach((operand) => expression(operand, ink)); return }
    // The children render here, in this ink; what else the expression holds is read on (a default the props give
    // them, an element held beside them).
    if (isChildren(x)) {
      childInks.add(ink)
      if (inControl) {
        childrenInControl = true
        // The control a wrapper renders follows a control's own rule: an element of it that turns sage under the
        // pointer copies the recipe whatever ink its children rest in (`handRolledCountControls`).
        const at = inside.map((entry) => entry.control).lastIndexOf(true)
        if (inside.slice(at).some((entry) => entry.turns)) childrenInHoverSage = true
      }
      if (underPointerSage()) childrenTurnSage = true
    }
    if (ts.isJsxElement(x) || ts.isJsxSelfClosingElement(x)) element(x, ink)
    else if (ts.isJsxFragment(x)) children(x.children, ink)
    // An array renders every member, and so does a list (`rows.slice(0, 2)`, Children.toArray), each read once; a
    // clone or a created element renders the children it is handed in its place (`elementChildren`).
    else if (ts.isArrayLiteralExpression(x)) x.elements.forEach((m) => { if (!ts.isOmittedExpression(m)) expression(ts.isSpreadElement(m) ? m.expression : m, ink) })
    else if (listCall(x)) literalExpressions(x, sf, [null]).forEach((m) => { if (!followed.has(m)) { followed.add(m); expression(m, ink) } })
    else if (ts.isCallExpression(x) && makesElement(x) && handedChildren(x)) elementChildren(x, sf).forEach((child) => expression(child, ink))
    else if (ts.isCallExpression(x) && renderedFunctions(x).some((fn) => returnedExpressions(fn).length)) {
      // What its callbacks and its own same-file function return renders here, each function walked once, so one
      // that renders itself ends; a call with no callbacks counts its own value too (a helper fed a number).
      const fns = renderedFunctions(x).filter((fn) => !followed.has(fn))
      fns.forEach((fn) => followed.add(fn))
      fns.flatMap(returnedExpressions).forEach((r) => expression(r, ink))
      if (!callbacksOf(x).length) counted(ink, () => rendersValue(x, sf))
    } else {
      const jsx = ts.isIdentifier(x) || ts.isCallExpression(x) ? heldJsx(x, sf, followed) : []
      jsx.forEach((h) => expression(h, ink))
      if (!jsx.length) {
        const text = literalText(x)
        counted(ink, () => (text !== null ? carriesDigit(text) : literalValues(x, sf).some(carriesDigit) || rendersValue(x, sf)))
      }
    }
  }
  for (const r of returnedExpressions(fn)) expression(r, 'inherit')
  return {
    // No path to the children found (a clone given a className, a callback handed through another function) reads as
    // one that passes its ink through, so a number given to it inside a sage parent is still read.
    childrenInk: childInks.has('sage') ? 'sage' : childInks.has('inherit') || childInks.size === 0 ? null : 'other',
    inheritsValue: carries,
    inheritsControl: controls,
    childrenInControl,
    childrenInHoverSage,
    childrenTurnSage,
    countTurnsSage,
    rootCount,
  }
}

/** Whether a component element renders a number in the ink it inherits, which a sage parent would colour. */
function inheritsValue(opening: ts.JsxOpeningLikeElement): boolean {
  if (siteInk(opening) !== null) return false
  const fn = componentFunction(opening)
  return !!fn && summary(fn).inheritsValue
}

/** Whether a component element renders, in the ink it inherits, a control that holds its count in an ink of its own. */
function inheritsControl(opening: ts.JsxOpeningLikeElement): boolean {
  if (siteInk(opening) !== null) return false
  const fn = componentFunction(opening)
  return !!fn && summary(fn).inheritsControl
}

/** What an element renders in its own ink (stops at a child that sets its own colour), through the file's
    bindings: each literal text, and each element that inherits the ink (a control, a component). What is held
    elsewhere (a variable's value, what a function returns, JSX handed to a helper) is reported at `site`, the
    expression that renders it here: the variable's name, or the call. */
interface InInk { node: ts.Node; text?: string; element?: ts.JsxElement | ts.JsxSelfClosingElement }
function inInk(children: ts.NodeArray<ts.JsxChild>, sf: ts.SourceFile, out: InInk[] = [], seen = new Set<ts.Node>(), site?: ts.Node): InInk[] {
  const element = (el: ts.JsxElement | ts.JsxSelfClosingElement, at: ts.Node | undefined) => {
    if (textColour(ts.isJsxElement(el) ? el.openingElement : el) !== null) return
    out.push({ node: at ?? el, element: el })
    if (ts.isJsxElement(el)) inInk(el.children, sf, out, seen, at)
  }
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
    else if (ts.isJsxFragment(x)) inInk(x.children, sf, out, seen, at)
    else if (ts.isJsxElement(x) || ts.isJsxSelfClosingElement(x)) element(x, at)
    else if (ts.isCallExpression(x) || ts.isNewExpression(x)) {
      // What the call holds (a member through `at` or `find`, the members a join renders, the element Children.only or
      // a clone renders, what its same-file function or useMemo returns), every member of a list (`{rows.slice(0, 2)}`,
      // `{Children.toArray(items)}`), the children a clone or a created element is handed, in its place
      // (`elementChildren`), and what its callbacks return, each callback read once.
      literalExpressions(x, sf).forEach(read)
      if (listCall(x)) literalExpressions(x, sf, [null]).forEach(read)
      if (!ts.isCallExpression(x)) return
      if (makesElement(x)) elementChildren(x, sf).forEach((child) => expr(child, at))
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
    else if (ts.isJsxFragment(child)) inInk(child.children, sf, out, seen, site)
    else if (ts.isJsxElement(child) || ts.isJsxSelfClosingElement(child)) element(child, site)
  }
  return out
}

/** The literal texts an element renders in its own ink (`inInk`). */
const inkTexts = (children: ts.NodeArray<ts.JsxChild>, sf: ts.SourceFile) =>
  inInk(children, sf).filter((r): r is InInk & { text: string } => r.text !== undefined)

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
  const declaration = binding.declaration
  if (!declaration || !ts.isParameter(declaration) || declaration.dotDotDotToken || declaration.getSourceFile() !== sf) return false
  if (binding.defaults.some((d) => valueType(CHECKER.getTypeAtLocation(d.value), d.steps, d.value))) return true
  const at = declaration.parent.parameters.indexOf(declaration)
  return sitesOf(declaration.parent).some((site) => {
    if (site.members) {
      const type = CHECKER.getTypeAtLocation(site.members)
      const member = CHECKER.getIndexTypeOfType(type, ts.IndexKind.Number) ?? (site.loose ? type : undefined)
      return site.at === at && valueType(member, binding.steps, site.members)
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
  // An array renders every member (`{[<b key="a">{n}</b>]}`), and so does a list (`{Children.toArray(items)}`).
  if (ts.isArrayLiteralExpression(x) && x.elements.some((m) => !ts.isOmittedExpression(m) && rendersValue(ts.isSpreadElement(m) ? m.expression : m, sf, depth + 1))) return true
  if (listCall(x) && literalExpressions(x, sf, [null]).some((v) => !asWritten(v) && rendersValue(v, sf, depth + 1))) return true
  if (ts.isCallExpression(x)) {
    // A clone or a created element given children renders them in its place (`elementChildren`).
    if (makesElement(x) && handedChildren(x)) return elementChildren(x, sf).some((child) => rendersValue(child, sf, depth + 1))
    // A number's own method ("n.toLocaleString()"), a join of what renders one (every member it joins), a call that
    // returns one, a formatter fed one (a literal argument such as "slice(0, 20)" is not a value), what a callback or
    // the same-file function it calls returns, or what it holds (the element Children.only or a clone renders, a
    // member through `at` or `find`).
    if (isNumberTyped(x)) return true
    if (ts.isPropertyAccessExpression(x.expression) && isNumberTyped(x.expression.expression)) return true
    if (method(x, JOINS) && rendersValue(x.expression.expression, sf, depth + 1)) return true
    if (renderedFunctions(x).some((fn) => returnedExpressions(fn).some((r) => rendersValue(r, sf, depth + 1)))) return true
    if (literalExpressions(x, sf).some((v) => v !== x && !asWritten(v) && rendersValue(v, sf, depth + 1))) return true
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
    return !!opening && takesClassName(opening)
  })
}
/** Whether an element's className reads the `className` its component is handed (`readsClassName`). */
function takesClassName(opening: ts.JsxOpeningLikeElement): boolean {
  const attr = opening.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText() === 'className')
  return !!attr?.initializer && readsClassName(attr.initializer, opening, new Map(), new Set())
}
/** Whether an expression reads the `className` the component around `at` is handed: the `className` field of what holds
    the props (`props.className`, `props['className']`, `props[KEY]`, the key read by a string or a same-file constant),
    the name a destructuring of the props gives it (`({ className: cls })`, `const { className: cls } = props`,
    `({ className: cls } = props)` assigned later: a binding keyed `className` in what holds the props, `holdsProps`), a
    same-file variable holding either, by its initializer or any value the file assigns it (`const cls = className`,
    `cls = props.className`), or a same-file helper returning one (`pick(props)`), its parameters bound at that call,
    each identifier resolved through the checker, a shorthand property's (`{ className }`) to the value it repeats. A
    field of some other object (`THEME.className`) is no read of it. `calls` carries the arguments of the same-file
    calls on the way, so a helper's parameter is read at the call being read, not at every call in the file
    (`pick(props)` beside `className={pick(THEME)}`); `seen` the declarations read on the way, afresh at each helper's
    call, so a variable's cycle ends and a helper called twice is read at each call; `holding` what `holdsProps` has
    read on the way in, so an object whose `className` reads its own ends. */
function readsClassName(node: ts.Node, at: ts.Node, calls: Calls, seen: Set<ts.Node>, holding: ReadonlySet<ts.Node> = new Set()): boolean {
  const sf = at.getSourceFile()
  let found = false
  const scan = (m: ts.Node): void => {
    if (found) return
    // The `className` field of what holds the props.
    if ((ts.isPropertyAccessExpression(m) && m.name.text === 'className') || (ts.isElementAccessExpression(m) && isClassNameKey(m.argumentExpression, sf))) {
      if (holdsProps(m.expression, at, new Set(holding), calls)) found = true
      return
    }
    // A member of a rest parameter read by an index (`parts[0]`, `parts.at(-1)`) is the argument at that place alone, or
    // the arguments a spread among them could leave there.
    const members = restMembers(m, calls)
    if (members) {
      if (members.some((arg) => readsClassName(arg, at, calls, seen, holding))) found = true
      return
    }
    // A same-file helper's call reads what the helper returns, its parameters bound at this call
    // (`className={pick(props)}`), and not an argument the helper does not return (`fixed(props.className)`). A call
    // the scan cannot read into (`cx`, a library's), and a helper's call to itself, pass their arguments through, so
    // they are read.
    if (ts.isCallExpression(m)) {
      const fns = functionsOf(m.expression).filter((fn) => !calls.has(fn))
      if (fns.length) {
        for (const fn of fns) if (returnedExpressions(fn).some((r) => readsClassName(r, at, new Map([...calls, [fn, m.arguments]]), new Set(), holding))) found = true
        return
      }
    }
    if (!ts.isIdentifier(m)) return void ts.forEachChild(m, scan)
    const shorthand = ts.isShorthandPropertyAssignment(m.parent) && m.parent.name === m ? m.parent : undefined
    const symbol = shorthand ? CHECKER.getShorthandAssignmentValueSymbol(shorthand) : CHECKER.getSymbolAtLocation(m)
    const declaration = symbol?.valueDeclaration
    if (!declaration || seen.has(declaration)) return
    seen.add(declaration)
    const reads = (values: ts.Expression[]): boolean => values.some((v) => readsClassName(v, at, calls, seen, holding))
    const holds = (values: ts.Expression[]): boolean => values.some((h) => holdsProps(h, at, new Set(holding), calls))
    if (ts.isBindingElement(declaration)) {
      // A name a destructuring gives (`bindingOf`: the parameter or variable it climbs to, and the steps to its place).
      // Keyed `className`, it is the className of what holds the props at the steps before it (`({ className: cls })`,
      // `const { className: cls } = props`, `const [{ className: cls }] = [props]`); at a rest parameter's own pattern
      // (`(...[head])`) or a destructuring of one (`const [head] = parts`), it is the argument at its place, a rest
      // element the arguments from its place on; at any other steps, what the value holds there (`const [cls] =
      // [props.className]`), a parameter read at the call on the way; and its default is read as written.
      const { declaration: root, steps, defaults } = bindingOf(symbol, [])
      if (reads(defaults.map(({ value }) => value))) found = true
      const pattern = declaration.parent
      const named = namesClassName(declaration.propertyName ?? declaration.name)
      const rest = root && (ts.isParameter(root) || ts.isVariableDeclaration(root)) && root.name === pattern && ts.isArrayBindingPattern(pattern) ? restParameterBehind(root) : undefined
      if (rest) {
        const args = calls.get(rest.parent) ?? []
        const from = rest.parent.parameters.indexOf(rest)
        const position = (pattern as ts.ArrayBindingPattern).elements.indexOf(declaration)
        if (reads(declaration.dotDotDotToken ? argumentsFrom(args, from + position) : argumentsAt(args, from, position))) found = true
      } else if (root && ts.isParameter(root)) {
        if (named ? holdsProps(root, at, new Set(holding), calls) : reads(parameterValues(root, steps, sf, calls))) found = true
      } else if (root && ts.isVariableDeclaration(root)) {
        for (const { value, steps: held } of variableValues(root)) {
          if (reads(valuesAt(value, [...held, ...steps], sf, calls))) found = true
          if (named && holds(valuesAt(value, [...held, ...steps.slice(0, -1)], sf, calls))) found = true
        }
      }
    } else if (ts.isVariableDeclaration(declaration)) {
      // What the name holds (`variableValues`): the value at its place, walked into by the steps a destructuring
      // assignment leaves (`[cls] = [props.className]` holds the array at 0), read as the initializer is; or the
      // `className` field of what holds the props, taken by one (`({ className: cls } = props)`, `[{ className: cls }]
      // = [props]`), the steps before the field walked first.
      for (const { value, steps } of variableValues(declaration)) {
        if (reads(valuesAt(value, steps, sf, calls))) found = true
        if (steps[steps.length - 1] === 'className' && holds(valuesAt(value, steps.slice(0, -1), sf, calls))) found = true
      }
    } else if (ts.isParameter(declaration)) {
      // A helper's parameter holds what the call on the way hands it (`pass(props.className)`), a rest parameter the
      // arguments from its place on (a same-file joiner), each read at the places a spread among the arguments could
      // leave it (`argumentsAt`).
      if (reads(parameterValues(declaration, [], sf, calls))) found = true
    }
  }
  scan(node)
  return found
}
/** Where an object's `className` comes from, the last write winning: 'props' when what holds the props is spread in or
    merged last, or a `className` key reads theirs (`{ ...props }`, `Object.assign({}, THEME, props)`, `{ className:
    props.className }`, the key written as is, by a string or by a same-file constant, its value read as a className
    attribute's is, `readsClassName`); 'own' when a `className` key of its own or an object known to set one comes last
    (`{ ...props, className: 'x' }`, `Object.assign({}, props, THEME)`); null when the scan cannot tell. Object.assign's
    sources are read in order, a spread of an array literal opened; a source the scan cannot read is passed over. */
function classNameFrom(e: ts.Expression, at: ts.Node, seen: Set<ts.Node>, calls: Calls): 'props' | 'own' | null {
  const x = unwrap(e)
  const sources: ts.Expression[] = []
  if (ts.isCallExpression(x) && objectCall(x, 'assign')) {
    for (const a of layOut(x.arguments)) if ('node' in a && !ts.isOmittedExpression(a.node)) sources.push(a.node)
  } else if (ts.isObjectLiteralExpression(x)) {
    for (const m of [...x.properties].reverse()) {
      if (ts.isSpreadAssignment(m)) {
        const from = classNameFrom(m.expression, at, new Set(seen), calls)
        if (from) return from
      } else if ((ts.isPropertyAssignment(m) || ts.isShorthandPropertyAssignment(m)) && namesClassName(m.name)) {
        return readsClassName(ts.isPropertyAssignment(m) ? m.initializer : m.name, at, calls, new Set(), seen) ? 'props' : 'own'
      }
    }
    return null
  } else {
    if (holdsProps(x, at, new Set(seen), calls)) return 'props'
    return setsOwnClassName(x) ? 'own' : null
  }
  for (const source of sources.reverse()) {
    const from = classNameFrom(source, at, new Set(seen), calls)
    if (from) return from
  }
  return null
}
/** Whether an expression is known to set a `className` of its own: an object literal with the key, through a spread of
    one, or a same-file variable holding one. */
function setsOwnClassName(e: ts.Expression, seen = new Set<ts.Node>()): boolean {
  const x = unwrap(e)
  if (seen.has(x)) return false
  seen.add(x)
  if (ts.isObjectLiteralExpression(x)) {
    return x.properties.some((m) => ts.isSpreadAssignment(m) ? setsOwnClassName(m.expression, seen)
      : (ts.isPropertyAssignment(m) || ts.isShorthandPropertyAssignment(m)) && namesClassName(m.name))
  }
  const declaration = ts.isIdentifier(x) ? CHECKER.getSymbolAtLocation(x)?.valueDeclaration : undefined
  return !!declaration && ts.isVariableDeclaration(declaration) && variableValues(declaration).some(({ value, steps }) => !steps.length && setsOwnClassName(value, seen))
}
/** The arguments of the same-file calls a read is inside, by the function called. */
type Calls = ReadonlyMap<ts.Node, ts.NodeArray<ts.Expression>>
/** A call's arguments laid out by place: each argument as written; a spread of an array literal, or of a same-file
    const typed as a tuple and holding one (`const PREFIX: readonly [string] = ['x']`), opened into its elements
    (`f(...[a, b], c)` hands `a`, `b`, `c`); any other spread as the least and most members its type gives it
    (`spreadLength`). A const typed as an array is not opened, since the file may push to it. */
type Laid = { node: ts.Expression } | { min: number; max: number }
function layOut(args: readonly ts.Expression[]): Laid[] {
  return args.flatMap((a): Laid[] => {
    if (!ts.isSpreadElement(a)) return [{ node: a }]
    const inner = unwrap(a.expression)
    if (ts.isArrayLiteralExpression(inner)) return layOut(inner.elements)
    const type = CHECKER.getTypeAtLocation(inner)
    const declaration = ts.isIdentifier(inner) ? CHECKER.getSymbolAtLocation(inner)?.valueDeclaration : undefined
    const held = declaration && ts.isVariableDeclaration(declaration) && (ts.getCombinedNodeFlags(declaration) & ts.NodeFlags.Const) && declaration.initializer ? unwrap(declaration.initializer) : undefined
    if (held && ts.isArrayLiteralExpression(held) && tupleMembers(type).every((t) => CHECKER.isTupleType(t))) return layOut(held.elements)
    return [spreadLength(type)]
  })
}
/** A type's members: a union's, or the type itself. */
const tupleMembers = (type: ts.Type): ts.Type[] => (type.isUnion() ? type.types : [type])
/** The least and most members a spread of a value of this type hands: a tuple's fixed length (`readonly [string]`),
    one with optional or rest elements by its bounds, a union of tuples by the least and most over them
    (`[] | [string]`); none and any for an array or anything else. */
function spreadLength(type: ts.Type): { min: number; max: number } {
  const bounds = tupleMembers(type).map((t) => {
    if (!CHECKER.isTupleType(t)) return { min: 0, max: Infinity }
    const target = (t as ts.TypeReference).target as ts.TupleType
    return { min: target.minLength, max: target.hasRestElement ? Infinity : target.fixedLength }
  })
  return { min: Math.min(...bounds.map((b) => b.min)), max: Math.max(...bounds.map((b) => b.max)) }
}
/** The least and most arguments a run of laid-out entries puts before (or after) a place. */
function extent(entries: Laid[]): { min: number; max: number } {
  return entries.reduce((acc, e) => ('node' in e ? { min: acc.min + 1, max: acc.max + 1 } : { min: acc.min + e.min, max: acc.max + e.max }), { min: 0, max: 0 })
}
/** The arguments a call could hand to the parameter at `from` when `index` is 0, or to the member at `index` of the
    rest parameter starting at `from` (`fromEnd`: that member counted from the arguments' end): each argument, laid
    out by place (`layOut`), that the lengths of the spreads before it (after it, from the end) could put there
    (`first(...xs, a, b)` could hand `a` first, never `b`, and never `a` either when `xs` is a tuple of one;
    `last(h, ...xs)` handed `c` alone holds no member). A spread's own members are not read. */
function argumentsAt(args: readonly ts.Expression[], from: number, index: number, fromEnd = false): ts.Expression[] {
  const laid = layOut(args)
  return laid.flatMap((e, j) => {
    if (!('node' in e)) return []
    const before = extent(laid.slice(0, j))
    if (!fromEnd) return before.min <= from + index && from + index <= before.max ? [e.node] : []
    const after = extent(laid.slice(j + 1))
    return before.max >= from && after.min <= index && index <= after.max ? [e.node] : []
  })
}
/** The arguments a call could hand to the rest parameter starting at `from`, used whole: each argument the lengths of
    the spreads before it could put at or past that place. A spread's own members are not read. */
function argumentsFrom(args: readonly ts.Expression[], from: number): ts.Expression[] {
  const laid = layOut(args)
  return laid.flatMap((e, j) => ('node' in e && extent(laid.slice(0, j)).max >= from ? [e.node] : []))
}
/** What a parameter holds at `steps`, in the calls' context: the arguments the call on the way hands it (`argumentsAt`;
    a rest parameter's member by the first step when it is an index, the whole of them when no step picks one), the
    remaining steps walked in (`atSteps`). Nothing for a parameter no call on the way binds. */
function parameterValues(parameter: ts.ParameterDeclaration, steps: Step[], sf: ts.SourceFile, calls: Calls): ts.Expression[] {
  const args = calls.get(parameter.parent) ?? []
  const index = parameter.parent.parameters.indexOf(parameter)
  if (!parameter.dotDotDotToken) return argumentsAt(args, index, 0).flatMap((arg) => atSteps(arg, steps, sf))
  const [first, ...rest] = steps
  const handed = typeof first === 'number' ? argumentsAt(args, index, first) : first === undefined || first === null ? argumentsFrom(args, index) : []
  return handed.flatMap((arg) => atSteps(arg, rest, sf))
}
/** What a value holds at `steps`: a parameter a call on the way binds, what that call hands it there
    (`parameterValues`); anything else, the parameter of a function around the element included, the expressions the
    binding walk meets there (`atSteps`). */
function valuesAt(value: ts.Expression, steps: Step[], sf: ts.SourceFile, calls: Calls): ts.Expression[] {
  const x = unwrap(value)
  const declaration = ts.isIdentifier(x) ? CHECKER.getSymbolAtLocation(x)?.valueDeclaration : undefined
  return declaration && ts.isParameter(declaration) && calls.has(declaration.parent) ? parameterValues(declaration, steps, sf, calls) : atSteps(value, steps, sf)
}
/** The rest parameter a pattern takes apart: the parameter itself when the pattern is its name (`(...[head])`), or the
    one a declaration's initializer names (`const [head] = parts`); undefined for any other root. */
function restParameterBehind(root: ts.ParameterDeclaration | ts.VariableDeclaration): ts.ParameterDeclaration | undefined {
  if (ts.isParameter(root)) return root.dotDotDotToken ? root : undefined
  const value = root.initializer ? unwrap(root.initializer) : undefined
  const declaration = value && ts.isIdentifier(value) ? CHECKER.getSymbolAtLocation(value)?.valueDeclaration : undefined
  return declaration && ts.isParameter(declaration) && declaration.dotDotDotToken ? declaration : undefined
}
/** The members of a rest parameter an index could read (`parts[0]`, `parts.at(0)`; `parts.at(-1)` and
    `parts[parts.length - 1]` counted from the end), bound at the call being read: the arguments that place could hold
    (`argumentsAt`), none when the index is past the arguments handed. `at()` truncates its index as the runtime does
    (`at(0.5)` is `at(0)`) and counts a negative one from the end; brackets name a member by an integer at or past 0
    alone (`parts[-1]`, `parts[0.5]`, `parts[parts.length]` name none), and an infinite index names none either way.
    Undefined for any other node, and for an index the scan cannot read, so the rest is read whole. */
function restMembers(node: ts.Node, calls: Calls): ts.Expression[] | undefined {
  const byAt = ts.isCallExpression(node)
  let receiver: ts.Expression | undefined
  let key: ts.Expression | undefined
  if (ts.isElementAccessExpression(node)) { receiver = node.expression; key = node.argumentExpression }
  else if (byAt && ts.isPropertyAccessExpression(node.expression) && node.expression.name.text === 'at' && node.arguments[0]) {
    receiver = node.expression.expression
    key = node.arguments[0]
  }
  if (!receiver || !key) return undefined
  const id = unwrap(receiver)
  const declaration = ts.isIdentifier(id) ? CHECKER.getSymbolAtLocation(id)?.valueDeclaration : undefined
  if (!declaration || !ts.isParameter(declaration) || !declaration.dotDotDotToken) return undefined
  const args = calls.get(declaration.parent)
  if (!args) return undefined
  const from = declaration.parent.parameters.indexOf(declaration)
  const back = lengthBack(key, id)
  if (back !== null) {
    if (Number.isInteger(back) && back >= 1) return argumentsAt(args, from, back - 1, true)
    return byAt && !Number.isInteger(back) ? undefined : []
  }
  let step = numericIndex(key)
  if (step === null) return undefined
  if (!Number.isFinite(step)) return []
  if (byAt) step = Math.trunc(step)
  else if (step < 0 || !Number.isInteger(step)) return []
  return step < 0 ? argumentsAt(args, from, -step - 1, true) : argumentsAt(args, from, step)
}
/** A numeric index: a literal, a negative one (`-1`) or a fraction included, or any expression the checker types as
    one number (`const LAST = -1`); null for any other key. */
function numericIndex(key: ts.Expression): number | null {
  const k = unwrap(key)
  if (ts.isPrefixUnaryExpression(k) && k.operator === ts.SyntaxKind.MinusToken && ts.isNumericLiteral(k.operand)) return -Number(k.operand.text.replace(/_/g, ''))
  if (ts.isNumericLiteral(k)) return Number(k.text.replace(/_/g, ''))
  const type = CHECKER.getTypeAtLocation(k)
  return type.isNumberLiteral() ? type.value : null
}
/** `N` when a key reads `parts.length - N` of the receiver `parts` (`numericIndex` for `N`); null for any other key. */
function lengthBack(key: ts.Expression, receiver: ts.Expression): number | null {
  const k = unwrap(key)
  if (!ts.isBinaryExpression(k) || k.operatorToken.kind !== ts.SyntaxKind.MinusToken) return null
  const left = unwrap(k.left)
  if (!ts.isPropertyAccessExpression(left) || left.name.text !== 'length') return null
  const owner = unwrap(left.expression)
  if (!ts.isIdentifier(owner) || !ts.isIdentifier(receiver) || CHECKER.getSymbolAtLocation(owner) !== CHECKER.getSymbolAtLocation(receiver)) return null
  return numericIndex(k.right)
}
/** Whether a key expression names `className`: a string, or a same-file constant holding one (`literalValues`). */
const isClassNameKey = (key: ts.Expression, sf: ts.SourceFile): boolean =>
  accessStep(key) === 'className' || (ts.isIdentifier(unwrap(key)) && literalValues(key, sf).includes('className'))
/** Whether a property's or a binding's name is `className`, written as is, by a string, or by a same-file constant
    (`{ [KEY]: … }`, `const { [KEY]: cls } = props`). */
const namesClassName = (name: ts.PropertyName | ts.BindingName): boolean =>
  keyOf(name) === 'className' || (ts.isComputedPropertyName(name) && isClassNameKey(name.expression, name.getSourceFile()))
/** What a value holds at the steps a destructuring assignment leaves (`[cls] = [props.className]` holds the array at 0,
    `[{ className: cls }] = [props]` the array at 0 then `className`): the expressions the binding walk meets once the
    steps are walked in (`walkLiterals`, stopped there), each read as written; the value itself when there are none. */
function atSteps(value: ts.Expression, steps: Step[], sf: ts.SourceFile): ts.Expression[] {
  if (!steps.length) return [value]
  const found: ts.Expression[] = []
  walkLiterals(value, sf, steps, (at, path) => { if (!path.length) found.push(at); return !path.length })
  return found
}
/** The declaration a binding element's destructuring climbs to: a parameter or a variable. */
function bindingRoot(binding: ts.Node): ts.Node {
  let root: ts.Node = binding
  while (ts.isBindingElement(root) || ts.isObjectBindingPattern(root) || ts.isArrayBindingPattern(root)) root = root.parent
  return root
}
/** Whether a declaration or an expression holds the props a function around `at` is handed (the component's, or a
    render callback's): the parameter itself (`({ className: cls })`), a helper's parameter the call on the way hands them
    (`pick(props)`, read at that call alone), a rest of it (`({ n, ...rest })`), a variable the file gives one of these,
    by its initializer or an assignment, destructured or not (`const p = props`, `const [p] = [props]`, `[p] = [props]`),
    an object spreading one (`{ ...props }`, `Object.assign({}, props)`) or a same-file function returning one (`get()`);
    not some other object (`const { className: cls } = theme`). */
function holdsProps(node: ts.Node, at: ts.Node, seen = new Set<ts.Node>(), calls: Calls = new Map()): boolean {
  if (seen.has(node)) return false
  seen.add(node)
  if (ts.isParameter(node)) {
    for (let p: ts.Node | undefined = at; p; p = p.parent) if (p === node.parent) return true
    return !node.dotDotDotToken && argumentsAt(calls.get(node.parent) ?? [], node.parent.parameters.indexOf(node), 0).some((arg) => holdsProps(arg, at, seen, calls))
  }
  if (ts.isBindingElement(node)) {
    if (node.dotDotDotToken) return holdsProps(bindingRoot(node), at, seen, calls)
    // A name a declaration's destructuring gives (`const [p] = [props]`): what the variable holds at the name's steps.
    const { declaration, steps } = bindingOf(ts.isIdentifier(node.name) ? CHECKER.getSymbolAtLocation(node.name) : undefined, [])
    return !!declaration && ts.isVariableDeclaration(declaration)
      && variableValues(declaration).some(({ value, steps: held }) => atSteps(value, [...held, ...steps], declaration.getSourceFile()).some((v) => holdsProps(v, at, seen, calls)))
  }
  if (ts.isVariableDeclaration(node)) {
    return variableValues(node).some(({ value, steps }) => atSteps(value, steps, node.getSourceFile()).some((v) => holdsProps(v, at, seen, calls)))
  }
  if (ts.isObjectLiteralExpression(node)) return classNameFrom(node, at, seen, calls) === 'props'
  const value = unwrap(node as ts.Expression)
  if (value !== node) return holdsProps(value, at, seen, calls)
  // A call holds what its same-file function returns (`get()`), its parameters bound at the call, useMemo what its
  // callback returns, and Object.assign its target with its sources' fields, the last source that sets a `className`
  // winning (`classNameFrom`).
  if (ts.isCallExpression(value)) {
    if (objectCall(value, 'assign')) return classNameFrom(value, at, seen, calls) === 'props'
    const fns = [...functionsOf(value.expression), ...(isUseMemo(value) && value.arguments[0] ? functionsOf(value.arguments[0]) : [])]
    return fns.some((fn) => returnedExpressions(fn).some((r) => holdsProps(r, at, seen, new Map([...calls, [fn, value.arguments]]))))
  }
  const declaration = ts.isIdentifier(value) ? CHECKER.getSymbolAtLocation(value)?.valueDeclaration : undefined
  return !!declaration && holdsProps(declaration, at, seen, calls)
}

/** The ink an element inherits from the elements around it in its own file: the nearest one that sets an ink. One
    written in a prop or a handler (`content={<button>…</button>}`) renders where the component puts it, or not at
    all, so it inherits nothing the scan can see (the prop gap). */
function inheritedInk(node: ts.Node): Ink {
  for (let p = node.parent; p; p = p.parent) {
    if (ts.isJsxAttribute(p)) return null
    if (ts.isJsxElement(p)) {
      const ink = textColour(p.openingElement)
      if (ink !== null) return ink
    }
  }
  return null
}

/** A control the user activates: a link, a button, a disclosure's summary, any element given an href or an
    onClick, the ui Button family, and an app component that renders its children inside a control (its children
    are that control's label). */
function isControl(opening: ts.JsxOpeningLikeElement, read?: Summary): boolean {
  if (['a', 'button', 'summary'].includes(opening.tagName.getText())) return true
  if (opening.attributes.properties.some((p) => ts.isJsxAttribute(p) && ['href', 'onClick'].includes(p.name.getText()))) return true
  const fn = componentFunction(opening)
  return !!fn && (VARIANT_COMPONENTS.get(fn)?.inks === BUTTON_INK || (read ?? summary(fn)).childrenInControl)
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

/** What a control's label holds in an ink of its own that carries a digit or a value: in its markup, in the same-file
    variable its label is held in (`{overflowLabel}`), or in what a same-file function it calls or maps with returns
    (`{renderLabel(n)}`). A count held elsewhere is reported at the expression that renders it in the control, and all
    of it at `site`, where the control is rendered, when the control itself is held elsewhere. */
function ownInkCounts(control: ts.JsxElement, sf: ts.SourceFile, out: Offence[] = [], site?: ts.Node): Offence[] {
  const followed = new Set<ts.Node>()
  const holders = (node: ts.Node, at?: ts.Node): void => {
    // A prop is not the label: a handler's body, a tooltip's content.
    if (ts.isJsxAttributes(node)) return
    const jsx = ts.isJsxExpression(node) && node.expression && ts.isIdentifier(unwrap(node.expression))
      ? heldJsx(unwrap(node.expression) as ts.Identifier, sf, followed)
      : []
    jsx.forEach((h) => holders(h, at ?? node))
    // A function written inside the label is walked where it stands; one held elsewhere, once.
    if (ts.isCallExpression(node)) {
      for (const fn of renderedFunctions(node)) {
        if (followed.has(fn) || (fn.pos >= node.pos && fn.end <= node.end)) continue
        followed.add(fn)
        returnedExpressions(fn).forEach((r) => holders(r, at ?? node))
      }
    }
    if (node !== control && ts.isJsxElement(node) && textColour(node.openingElement) === 'other') {
      for (const { node: hit, text } of inkTexts(node.children, sf)) if (carriesDigit(text)) out.push({ node: at ?? hit, text })
      for (const hit of inkValues(node.children, sf, [], node.openingElement)) out.push({ node: at ?? hit, text: `{${hit.getText(sf)}}` })
    }
    ts.forEachChild(node, (child) => holders(child, at))
  }
  holders(control, site)
  return out
}

/** Rule 2's second check over one file, the count control's: what a control resting in sage holds in an ink of
    its own that carries a digit or a value (`ownInkCounts`). The sage is the control's own, or inherited from the
    elements around it: where the control is written, where it is rendered when it is held elsewhere (a variable,
    a helper's return, JSX handed to a helper: `inInk`, reported there), or where a component that renders it in
    the ink it inherits is used, or is given sage that it hands to the element it returns (reported at that use). */
function heldValues(sf: ts.SourceFile): Offence[] {
  const out: Offence[] = []
  const inSage = (el: ts.JsxElement | ts.JsxSelfClosingElement, site?: ts.Node) => {
    const opening = ts.isJsxElement(el) ? el.openingElement : el
    if (ts.isJsxElement(el) && isControl(opening)) ownInkCounts(el, sf, out, site)
    if (inheritsControl(opening)) out.push({ node: site ?? el, text: `<${opening.tagName.getText(sf)}>` })
  }
  visit(sf, (n) => {
    if (!ts.isJsxElement(n) && !ts.isJsxSelfClosingElement(n)) return
    const opening = ts.isJsxElement(n) ? n.openingElement : n
    const own = textColour(opening)
    if ((own ?? inheritedInk(n)) === 'sage') inSage(n)
    if (own === 'sage' && ts.isJsxElement(n)) for (const r of inInk(n.children, sf)) if (r.element && r.node !== r.element) inSage(r.element, r.node)
    const fn = componentFunction(opening)
    if (fn && siteInk(opening) === 'sage' && forwardsClassName(fn) && summary(fn).inheritsControl) {
      out.push({ node: n, text: `<${opening.tagName.getText(sf)}>` })
    }
  })
  return out
}

/** A class token that turns the text sage under the pointer: a sage text colour behind hover: or active: (a group- or
    peer- form included). A sage fill (`hover:fill-brand-strong`) recolours an icon, never the label, so it is not one. */
function sageUnderPointer(token: string): boolean {
  const parts = splitVariants(token)
  const utility = parts.pop()!.replace(/^!/, '')
  return utility.startsWith('text-') && SAGE.test(utility) && parts.some((variant) => ACTIVITY.test(variant))
}

/** Whether an element's classes written in its file turn what it renders in its own ink sage under the pointer, or,
    for an app component, whether it renders its children so (`childrenTurnSage`). */
function turnsSageUnderPointer(opening: ts.JsxOpeningLikeElement): boolean {
  if (classTokens(opening, true).some(sageUnderPointer)) return true
  const fn = componentFunction(opening)
  return !!fn && summary(fn).childrenTurnSage
}

/** Whether an app component element turns a count it renders sage under the pointer: one of its own, by classes written
    in its file (`countTurnsSage`), or one in the ink of the element it returns, when the call site gives it classes
    that do and it hands its className to that element (`rootCount`), whatever ink that element rests in. */
function countUnderPointer(opening: ts.JsxOpeningLikeElement): boolean {
  const fn = componentFunction(opening)
  if (!fn) return false
  const s = summary(fn)
  return s.countTurnsSage || (s.rootCount && classTokens(opening, true).some(sageUnderPointer))
}

/** Whether a control's label turns its count sage under the pointer, by classes written in a file the scan reads: an
    element of it that holds the count in its own ink and turns sage under the pointer, the recipe moved onto the label
    (`<button className="group"><span className="… group-hover:text-brand-strong">{n} more</span></button>`), or an app
    component in it that renders the count so, the children it is handed (`<a><CountLabel>See all {n}</CountLabel></a>`)
    or a count of its own (`<a><CountLabel n={n} /></a>`, `countUnderPointer`). The label is read written in place or
    held in a name and rendered here (`const label = <CountLabel>…`, read through the file's bindings, a call's return
    included), through a conditional, `&&`, `||`, `??` and an array on the way. An icon that turns sage holds no count.
    A component's className given where it is used is read as reaching the children it is handed, as textColour reads
    it, so a component that hands it to an icon beside them reads as turning them sage: give the icon its class inside
    the component. */
function labelTurnsSage(control: ts.JsxElement, sf: ts.SourceFile): boolean {
  const holds = (el: ts.JsxElement) =>
    inkTexts(el.children, sf).some(({ text }) => carriesDigit(text)) || inkValues(el.children, sf, [], el.openingElement).length > 0
  const followed = new Set<ts.Node>()
  const element = (el: ts.Expression): boolean => {
    if (ts.isJsxFragment(el)) return inside(el.children)
    if (!ts.isJsxElement(el) && !ts.isJsxSelfClosingElement(el)) return false
    const opening = ts.isJsxElement(el) ? el.openingElement : el
    if (countUnderPointer(opening)) return true
    return ts.isJsxElement(el) && ((turnsSageUnderPointer(opening) && holds(el)) || inside(el.children))
  }
  // What an expression among the control's children renders: JSX written there, through a conditional, `&&`, `||`,
  // `??` or an array, the JSX a name or a call holds through the file's bindings, and what a callback returns, each
  // value once.
  const expression = (e: ts.Expression): boolean => {
    const x = unwrap(e)
    if (ts.isJsxElement(x) || ts.isJsxSelfClosingElement(x) || ts.isJsxFragment(x)) return element(x)
    if (ts.isConditionalExpression(x)) return expression(x.whenTrue) || expression(x.whenFalse)
    if (ts.isBinaryExpression(x)) return valueOperands(x).some(expression)
    if (ts.isArrayLiteralExpression(x)) return x.elements.some((m) => !ts.isOmittedExpression(m) && expression(ts.isSpreadElement(m) ? m.expression : m))
    if (heldJsx(x, sf, followed).some(expression)) return true
    // What a callback the call is handed returns renders here too (`{items.map((i) => <span>…</span>)}`), each once.
    return ts.isCallExpression(x) && renderedFunctions(x).some((fn) => {
      if (followed.has(fn)) return false
      followed.add(fn)
      return returnedExpressions(fn).some(expression)
    })
  }
  const inside = (list: ts.NodeArray<ts.JsxChild>): boolean => list.some((child) => {
    if (ts.isJsxExpression(child)) return !!child.expression && expression(child.expression)
    return element(child as ts.Expression)
  })
  return inside(control.children)
}

/** Rule 2's third check over one file, the count control's one source: a control whose label carries a count (a
    digit in its text, or a value, in any ink) and whose classes written in the file turn it sage under the pointer has
    rebuilt the count control by hand. It composes countControlClass (components/ui/countControl.ts) instead, so a change
    to the recipe reaches every count at once. */
function handRolledCountControls(sf: ts.SourceFile): Offence[] {
  const out: Offence[] = []
  visit(sf, (n) => {
    if (!ts.isJsxElement(n) || !isControl(n.openingElement)) return
    const offence = { node: n, text: `<${n.openingElement.tagName.getText(sf)}>` }
    // The label turns its count sage under the pointer.
    if (labelTurnsSage(n, sf)) return void out.push(offence)
    // Or its own classes, or those of the control a wrapper renders its children in (`<MoreButton>Show
    // {n}</MoreButton>`), turn it sage under the pointer, and its label carries a count in any ink.
    const wrapper = componentFunction(n.openingElement)
    if (!classTokens(n.openingElement, true).some(sageUnderPointer) && !(wrapper && summary(wrapper).childrenInHoverSage)) return
    const counts = inkTexts(n.children, sf).some(({ text }) => carriesDigit(text))
      || inkValues(n.children, sf, [], n.openingElement).length > 0 || ownInkCounts(n, sf).length > 0
    if (counts) out.push(offence)
  })
  return out
}

describe('brand rule 2: sage never colours a number', () => {
  // Each offence once: a text reached two ways (a helper's return read as a value and walked as JSX) is one.
  const inApp = (check: (sf: ts.SourceFile) => Offence[]) =>
    [...new Set(SOURCES.flatMap(({ rel, sf }) => check(sf).map(({ node, text }) => where(rel, sf, node, text))))]

  // The app scan asks the checker for the types of what it reads in every file, about 2.5 s; the budget leaves room
  // for a loaded CI runner.
  it('nothing the app renders in sage ink at rest carries a digit or a value', () => {
    expect(inApp(sageValues), 'set the number in the ink (text-text-primary / secondary); sage signals brand and activity').toEqual([])
  }, 20_000)

  it('no control that rests in sage holds its count in an ink of its own (the count control)', () => {
    expect(inApp(heldValues), 'rest the whole label in the ink, sage under the pointer (the count control, frontend/DESIGN_SYSTEM.md)').toEqual([])
  })

  it('a control whose label carries a count and turns sage under the pointer composes the count control, its one source', () => {
    expect(inApp(handRolledCountControls), 'compose countControlClass (components/ui/countControl.ts) beside the shape; never rebuild the recipe by hand').toEqual([])
  })

  it('scores every planted form in tests/unit/fixtures/brandRule2Forms.tsx as its mark says', () => {
    const sf = PROGRAM.getSourceFile(FORMS)
    if (!sf) throw new Error(`${FORMS} is not in the program`)
    const lineOf = (node: ts.Node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
    const named = new Set([...sageValues(sf), ...heldValues(sf), ...handRolledCountControls(sf)].map(({ node }) => lineOf(node)))
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

  // Last, so it reads every walk the checks above asked for.
  it('every walk the gate asks of a callee ends within its budget', () => {
    expect(OVER_BUDGET, 'a binding graph reactUtility cannot walk within WALK_BUDGET: simplify its bindings, or raise the budget with a measure').toEqual([])
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
