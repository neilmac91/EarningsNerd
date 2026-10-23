import { readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { componentTag, heldValues, leavesOf, propertyOf, renderedLeavesOf, scopeResolver, unwrapHeld, writtenChild, type Fn, type Held } from './heldValues'

/**
 * A served company name prints through formatCompanyName (E146, CLAUDE.md rule 12). EDGAR serves an issuer's name as
 * its conformed name, often in capitals ("NVIDIA CORP"); lib/formatCompanyName.ts gives it its display casing, and the
 * raw name stays the data value (a key, a URL, a search query, an analytics property, an API payload, a CSV, a title
 * attribute that quotes the filing). So the same company never reads "NVIDIA Corp" in one row and "NVIDIA CORP" in
 * the next.
 *
 * What reads as a served company name is taken from the types, in one program over the scanned files and the planted
 * forms, so the checker says which declaration a read reaches, through imports, destructuring and the type a
 * callback is given. A company-name field is a property of an interface, a type literal or a class (a constructor's
 * parameter property among a class's) that holds a string and is named `company_name`, `companyName` or `company`
 * (NAME_KEYS), or `name` in a type that also declares `ticker` (a company: the filing's, the summary's, the
 * watchlist's and the dashboard's, Reporting this week's, CompanyLogo's props). A field declared in an API module
 * (API_MODULES: a feature's api/ directory, lib/serverApi.ts, lib/api/ and the payload types in types/) is served:
 * it holds the name as the backend sends it. A field declared anywhere else is the app's own (a view model such as
 * the redlines' RedlineSource, a component's props such as CompanyLogo's `name`): the app fills it, the gate checks
 * every fill it can place, and a read of it is the display form. The census below fails a field of the app's own
 * that nothing the gate can see fills, since its value would then come from somewhere the gate cannot check (a value
 * handed whole fills one when its member there is another company-name field, not the same field handed on). A field
 * the app keeps the served name in on purpose, as data (SERVED_KEYS: the evidence pack's and the redlines'
 * `conformedName`, which their JSON downloads write), is served wherever it is declared: a fill of it is data and
 * never checked, and a read of it is the served name, so printing it fails.
 *
 * Values are followed through each file by the shared reader (tests/unit/heldValues.ts) with `passThrough` and
 * `state` on, so a name held in a const, a destructuring, a parameter a same-file call fills, a same-file function's
 * return, a callback, React's state (useState with what its setter is handed, useReducer with what its dispatcher is
 * handed, useActionState and react-dom's useFormState as a reducer, useOptimistic with what its setter is handed or
 * what its update function returns, a reducer the reader does not hold (another module's) giving back what React
 * hands it, as a call the reader cannot follow does; the setter and the dispatcher followed as values: destructured,
 * read by index from the hook's pair, held by another name, put in an object, handed to a same-file component or
 * function, handed back by a custom hook, handed as the callback of an array's methods, of `Array.from` or of React's
 * `Children.map` and `Children.forEach` (each element), called through Function.prototype's `call`, `apply` or `bind`
 * or through `Reflect.apply`; useRef, useDeferredValue, useSyncExternalStore), a template literal, `+`, an array or a
 * call the reader cannot follow (`String()`, `trim()`, `join()`) is still the name. So is a name an object literal's
 * getter hands back (what the literal's methods and accessors put on `this` and read from it included), one a
 * property holds that Object.defineProperty, Object.defineProperties, Object.create or Reflect.defineProperty
 * defines, or Reflect.set puts, and one a built-in collection is made with or given (`new Map` and `new WeakMap`
 * under each entry's key, read by `get`; Object.fromEntries; `new Set` and a Set's `add`, read by iterating it; a
 * Map's or a Set's `values()` and `entries()`; `new Array`, `Array()`, `Array.of`). Across modules, another module's
 * function that hands back a served name as text (or in an array or a Set it returns) gives the name wherever the
 * reader reads a call of it: called here (through `call` or `apply` too), or handed on as a value and called by React
 * (a reducer, an initializer), an array's method or a same-file function, through any chain of modules
 * (SERVED_RETURNS, a fixed point over the program), and reached through an import's alias, a re-export or a const
 * that holds it (both arms of a conditional, either side of `||` or `??`), by every declaration it has, an overloaded
 * function's body among them. A getter that hands back a served name, an object literal's or a class's, gives the
 * name wherever the checker places a read of it, in any module, since a read calls it. A call of formatCompanyName
 * (imported under any name, read from the module's namespace, or held in a same-file const) gives the display form;
 * so does a read of a field of the app's own, and a string literal is written by hand in its display form. An element
 * is a value of its own, read where it is written.
 *
 * It fails (findingsIn):
 *  A. a served name printed raw: an expression child of an intrinsic element, a fragment or a component the scan
 *     cannot read (an import, React's Fragment); the text an intrinsic element shows from a prop (HOST_TEXT_PROPS:
 *     its children and inner HTML, a field's value, default value and placeholder, an option's label, an iframe's
 *     document); every prop of a component the scan cannot read but the attribute ones (ATTRIBUTE_PROPS), since it
 *     may print any other (a Notice's title, the Ask callout's `subjectLabel`), and what a function such a prop
 *     holds returns (a column's `render`), another module's function that hands back a served name included; what a
 *     component returns as text, or in an array or a Set it returns (React renders an iterable's items), nested, a
 *     component being a function its module renders as a tag or names for one (PascalCase), one another module
 *     renders (RENDERED_IN: through an import's alias, a re-export, a default export, an object's member or a
 *     wrapper such as memo), one its module exports as its default (a page Next renders, or one a module loads
 *     lazily), whatever its name, and a class component's `render`, a method or a field whose value is a function
 *     (a class that extends React's Component or PureComponent, through any chain of classes); and the words Next
 *     prints from a page's metadata (METADATA_TEXT: the tab's title, the description, a social card's), by the keys
 *     Next's metadata types declare. A same-file component's props and children bind its parameters, so a name handed
 *     to one fails where the component prints it.
 *  B. a field of the app's own filled with a served name: an object literal's property (a getter by what it
 *     returns), placed by the type the literal is given (a declared type, a return type, a parameter's type, read
 *     through Object.freeze, parentheses, `as`, `satisfies` and `!`), a spread of a served object into such a
 *     literal, a JSX attribute or a spread of a served object into a component's props (so CompanyLogo's `name`
 *     takes the display form), an assignment to the field (`=`, `||=`, `&&=`, `??=`), and an argument a `new` or a
 *     `super` call hands a constructor's parameter property. A served object handed whole to a type that holds such
 *     a field (a view of the app's own) fills it too, wherever the checker gives the place a type (handedAt): a
 *     declaration's or a default's initializer, a class's field among them, an assignment, a return, an arrow's
 *     body, a yield, a call's argument (a spread one by its elements, a generic's parameter by its constraint,
 *     whatever the call infers), Object.assign's sources, an object literal's member, an array's element or spread,
 *     a JSX attribute's value, a spread's member and an assertion's operand; the type's other fields, an array's
 *     elements, a record's values, a generic's type arguments and a function's return hold the field the same way
 *     (slotsOf). A mapper that stops formatting fails here, at the line that fills its field. An object literal the
 *     checker cannot place that holds a company-name key (a NAME_KEYS key, or `name` beside `ticker`) filled with a
 *     served name fails too, unless the type it is given has an index signature (a data payload, as analytics'
 *     properties).
 *
 * Over-reads that fail closed: a prop of a component the scan cannot read that never prints (a table's row key, a
 * link's tooltip `title`), a value an imported function is handed but never gives back (a length), and an object
 * literal the checker cannot place that is data, which a declared type then places. False positives of the reading,
 * which pass: a field named for a company that holds no name (the refresh review's `company` slug) is read as the
 * app's own, filled by hand. Out of scope by design, clean: an attribute that is not printed text (a key, an href,
 * an id, a data attribute, a title attribute, an aria-label, an alt), an analytics call, an API payload or a cache
 * row typed as the API's own type, a CSV, a comparison, an object a function named like a component returns (a
 * mapper's), which is no text, and text drawn outside React (the chart export paints its header on a canvas from
 * ChartExportHeader's `company`, a field of the app's own, which rule B holds). Out of reach, each planted as a gap
 * in tests/unit/fixtures/companyNameForms.tsx or companyNameRendered/ and review-checked: text a call puts on the
 * screen outside JSX (a toast's message, `document.title`), since a call's arguments are data to the gate; a name
 * served under another field of an object a component the scan cannot read prints by key (a DataTable column with no
 * `render`, which prints `row[key]`); a name that crosses modules in a prop typed as a plain string (`label:
 * string`, or an indexed access type such as `CalendarEvent['company_name']`), or inside an object another module's
 * function hands back; what a child hands its parent's ref through useImperativeHandle; a state's setter or a
 * reducer's dispatcher handed to another module's code (a function or a component it imports) and called there,
 * where the reader does not look; a name served under another field (the census fails a string field of an API type
 * named for a company, an issuer, a filer, a registrant or an entity until it joins the reading or NOT_NAMES); a
 * read by a key the scan cannot read (`ev[key]`) or from a type that declares no field for it (an index signature,
 * `any`), and a served object handed whole to a view of the app's own through such a type (cast through `unknown`,
 * or JSON.parse's `any`); a piece of the name read by index from what a call hands back (`n.split(' ')[0]`); a
 * display form shouted again (`formatCompanyName(n).toUpperCase()`); a utility known by its name (an array's method)
 * called through Function.prototype's `call` or `apply`, which the reader reads as a call of the method; a served
 * name copied into a class component's field or its state and printed through `this` (`label =
 * this.props.ev.company_name`, then `{this.label}`), since the shared reader follows no class's fields and no
 * class's `this` (a served field read through `this.props` is still read by its type, as a class's getter is, above,
 * and so is a field declared as a view of the app's own, by rule B; the app's class components, two error
 * boundaries, print no name); a getter read through a type that declares its property (another module's object held
 * under a declared type, or a class's getter read through an interface it implements), since the checker places the
 * read on the declared property; an object literal's `this` handed on whole (a getter that hands back its own
 * object, then a member of what it gives); what an assignment through a `set` accessor hands the accessor, kept for
 * a getter of another name; a property descriptor's `get` that reads `this`, which the reader binds to the
 * descriptor; a Proxy's traps; a Map's entries iterated as `[key, value]` pairs, since the reader holds a Map's
 * values as its elements (`get`, `forEach`, `values()` and `entries()` read them), and a served name a Map holds as
 * a key (a Map a component returns, which React renders as such pairs, among them); a promise's `then` and a
 * generator's yields (a component another module loads lazily through a `then` among them); and React's element
 * calls, which app code may not write (earningsnerd/elements-built-with-jsx).
 */

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCANNED_DIRS = ['app', 'components', 'features', 'lib', 'hooks']
/** The planted forms: one exported function per form, marked in the comment before it, scored by the self-check. In the
    program beside the app, so the checker reads the app's types there; outside the scan. */
const FORMS = path.join(ROOT, 'tests/unit/fixtures/companyNameForms.tsx')
/** The forms that need a module of their own (a module's default export, a component another module renders), scored
    with FORMS. */
const RENDERED_FORMS = path.join(ROOT, 'tests/unit/fixtures/companyNameRendered')
const FORM_MODULES = [FORMS, ...sourceFiles(RENDERED_FORMS).sort()]
const FORMATTER_FILE = path.join(ROOT, 'lib/formatCompanyName.ts')
/** Where the types of what the backend serves are declared: a feature's api/ modules, the server-side fetch layer
    (lib/serverApi.ts, whose hero data the landing prints), the HTTP client's types and the payload types in types/. */
const API_MODULES = [/^features\/[^/]+\/api\//, /^lib\/serverApi\.ts$/, /^lib\/api\//, /^types\//]
/** The keys a company's name is served under, beside a company's `name`. */
const NAME_KEYS = new Set(['company_name', 'companyName', 'company'])
/** The keys the app keeps a served name under on purpose, as data: served wherever they are declared (the header). */
const SERVED_KEYS = new Set(['conformedName'])
/** A string field of an API type named for a company, an issuer, a filer, a registrant or an entity: the census reads
    each as a company-name field or as one of NOT_NAMES. */
const NAMED_LIKE_A_COMPANY = /compan|issuer|filer|registrant|entity/i
/** String fields of the API types named like a company that hold no company's name (none today). */
const NOT_NAMES: string[] = []
/** The props of a component the scan cannot read that never print: they reach an attribute, a handler or React. A
    `title` is not one of them: a Notice's and a card's print. Nor is a `name`: a chart series' prints in its tooltip. */
const ATTRIBUTE_PROPS = /^(?:key|ref|className|style|id|role|tabIndex|htmlFor|href|src|type|alt|aria-.+|data-.+|on[A-Z].*)$/
/** The props an intrinsic element shows as text. Its other attributes (a title, an aria-label, an alt) are not printed. */
const HOST_TEXT_PROPS = ['children', 'dangerouslySetInnerHTML', 'value', 'defaultValue', 'placeholder', 'label', 'srcDoc']
/** React's calls that make an element: a value of its own, as JSX is. */
const ELEMENT_CALLS = new Set(['createElement', 'cloneElement', 'jsx', 'jsxs', 'jsxDEV'])
/** The words Next prints from a page's metadata (the tab's title, the description, a social card's), by the key Next's
    metadata types declare them under; a title's `default` and `absolute` are its text, its `template` a pattern. */
const METADATA_TEXT = new Set(['title', 'description', 'default', 'absolute'])
const isNextDeclaration = (d: ts.Node) => /[\\/]node_modules[\\/]next[\\/]/.test(d.getSourceFile().fileName)

/** All JS and TS modules, including JSX and explicit ES/CommonJS suffixes; declarations and tests are not app code. */
function sourceFiles(dir: string): string[] {
  const out: string[] = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) out.push(...sourceFiles(full))
    else if (/\.(?:[cm]?[jt]s|[jt]sx)$/.test(entry.name) && !/\.(spec|test)\.(?:[cm]?[jt]s|[jt]sx)$|\.d\.[cm]?ts$/.test(entry.name)) out.push(full)
  }
  return out
}

const FILES = SCANNED_DIRS.flatMap((dir) => sourceFiles(path.join(ROOT, dir)))
/** One program over the scanned files and the forms, built once at import, outside any test's timeout: the price of
    asking the checker which declaration a read reaches, which no source scan can see across modules. */
const TSCONFIG = ts.readConfigFile(path.join(ROOT, 'tsconfig.json'), ts.sys.readFile)
const PARSED = ts.parseJsonConfigFileContent(TSCONFIG.config, ts.sys, ROOT)
const PROGRAM = ts.createProgram([...FILES, ...FORM_MODULES], { ...PARSED.options, noEmit: true, skipLibCheck: true })
const CHECKER = PROGRAM.getTypeChecker()
const relative = (file: string) => path.relative(ROOT, file).split(path.sep).join('/')
const isApiModule = (file: string) => API_MODULES.some((re) => re.test(relative(file)))

const keyText = (name: ts.Node | undefined): string | undefined =>
  name && (ts.isIdentifier(name) || ts.isStringLiteral(name) || ts.isNoSubstitutionTemplateLiteral(name) || ts.isNumericLiteral(name)) ? name.text : undefined
const stringLike = (type: ts.Type): boolean => {
  const t = CHECKER.getNonNullableType(type)
  return t.isUnion() ? t.types.every(stringLike) : (t.flags & ts.TypeFlags.StringLike) !== 0
}
/** Each member of a type (each side of a union) under a key. */
const propertiesNamed = (type: ts.Type | undefined, key: string): ts.Symbol[] => {
  if (!type) return []
  const t = CHECKER.getNonNullableType(type)
  return (t.isUnion() ? t.types : [t]).flatMap((part) => part.getProperty(key) ?? [])
}

/** A field: a property of an interface or a type literal, a class's property, or a constructor's parameter property
    (`constructor(public company_name: string)`), which declares a property of its class. */
type Field = ts.PropertySignature | ts.PropertyDeclaration | ts.ParameterPropertyDeclaration
const isFieldDeclaration = (d: ts.Node): d is Field =>
  ts.isPropertySignature(d) || ts.isPropertyDeclaration(d) || (ts.isParameter(d) && ts.isParameterPropertyDeclaration(d, d.parent))
/** The interface, type literal or class a field belongs to. */
const holderOf = (d: Field): ts.Node => (ts.isParameter(d) ? d.parent.parent : d.parent)
const fieldCache = new Map<ts.Node, boolean>()
/** Whether a declaration is a company-name field (the header's reading). */
function isNameField(d: ts.Node): d is Field {
  if (!isFieldDeclaration(d)) return false
  const cached = fieldCache.get(d)
  if (cached !== undefined) return cached
  const key = keyText(d.name)
  const result =
    !!key &&
    stringLike(CHECKER.getTypeAtLocation(d)) &&
    (NAME_KEYS.has(key) || SERVED_KEYS.has(key) || (key === 'name' && propertiesNamed(CHECKER.getTypeAtLocation(holderOf(d)), 'ticker').length > 0))
  fieldCache.set(d, result)
  return result
}
const isServed = (d: Field) => isApiModule(d.getSourceFile().fileName) || SERVED_KEYS.has(keyText(d.name) ?? '')
/** The company-name fields a symbol declares (a union's or a mapped type's member declares each of its sources). */
const fieldsOf = (symbol: ts.Symbol | undefined): Field[] => (symbol?.declarations ?? []).filter(isNameField)
const fieldName = (d: Field) => {
  const holder = holderOf(d)
  const owner = ts.isInterfaceDeclaration(holder) || ts.isClassDeclaration(holder) ? holder.name?.text : undefined
  const { line } = d.getSourceFile().getLineAndCharacterOfPosition(d.getStart())
  return `${owner ?? `{…}@${relative(d.getSourceFile().fileName)}:${line + 1}`}.${keyText(d.name)}`
}

/** How deep a value handed whole to a type is read (rule B): its fields, an array's elements, a record's values, a
    generic's type arguments and a function's return, nested. */
const HANDED_DEPTH = 6
const isLibDeclared = (symbol: ts.Symbol) =>
  !!symbol.declarations?.length && symbol.declarations.every((d) => /[\\/]node_modules[\\/]/.test(d.getSourceFile().fileName))
/** Each side of a type a value may take: a union's members, null and undefined dropped, and a type parameter read as
    its constraint, which is what a generic's body reads it as. */
const sidesOf = (type: ts.Type, seen = new Set<ts.Type>()): ts.Type[] => {
  const t = CHECKER.getNonNullableType(type)
  if (seen.has(t)) return []
  seen.add(t)
  if (t.isUnion()) return t.types.flatMap((part) => sidesOf(part, seen))
  if (t.flags & ts.TypeFlags.TypeParameter) {
    const constraint = CHECKER.getBaseConstraintOfType(t)
    return constraint && constraint !== t ? sidesOf(constraint, seen) : []
  }
  return [t]
}
/** A generic's type arguments by its type parameters' names, so a Map's `V` meets a ReadonlyMap's (a tuple's, which
    have no names, by their places). */
const typeArgumentsOf = (t: ts.Type): Map<string, ts.Type> => {
  if (!(t.flags & ts.TypeFlags.Object) || !((t as ts.ObjectType).objectFlags & ts.ObjectFlags.Reference)) return new Map()
  const reference = t as ts.TypeReference
  const args = CHECKER.getTypeArguments(reference)
  return new Map((reference.target.typeParameters ?? []).flatMap((p, i) => (args[i] ? [[p.symbol?.name ?? `${i}`, args[i]] as const] : [])))
}
/** What a spread hands on from a value: an array's or a tuple's elements, an iterable's items. */
const elementsOf = (type: ts.Type): ts.Type[] =>
  sidesOf(type).flatMap((side) => [CHECKER.getIndexInfoOfType(side, ts.IndexKind.Number)?.type ?? typeArgumentsOf(side).get('T') ?? []].flat())
/** A step from a type to a value it holds: a property by its key, an index signature's value (`number` or `string`),
    a generic's type argument by its parameter's name, a function's return. */
interface Step {
  by: 'prop' | 'index' | 'arg' | 'return'
  key: string
}
/** A field of the app's own a type holds, and the steps that reach it from the type (the field's own key last). */
interface Slot {
  own: Field[]
  path: Step[]
}
const SLOTS = new Map<ts.Type, Slot[]>()
/** The fields of the app's own a type holds, for a value handed to it whole (rule B): its own, and those its other
    fields, an array's elements, a record's values, a generic's type arguments and a function's return hold, to
    HANDED_DEPTH levels. A library's members are no field of the app's, though its type arguments may hold one. Read once
    per type. */
const slotsOf = (type: ts.Type, depth = 0, open = new Set<ts.Type>()): Slot[] => {
  const cached = SLOTS.get(type)
  if (cached) return cached
  if (depth > HANDED_DEPTH || open.has(type)) return []
  open.add(type)
  const out: Slot[] = []
  const under = (step: Step, inner: ts.Type) => {
    for (const slot of slotsOf(inner, depth + 1, open)) out.push({ own: slot.own, path: [step, ...slot.path] })
  }
  for (const t of sidesOf(type)) {
    for (const p of t.getProperties()) {
      const own = fieldsOf(p).filter((f) => !isServed(f))
      if (own.length > 0) out.push({ own, path: [{ by: 'prop', key: p.name }] })
      else if (!isLibDeclared(p)) under({ by: 'prop', key: p.name }, CHECKER.getTypeOfSymbol(p))
    }
    for (const [key, kind] of [['number', ts.IndexKind.Number], ['string', ts.IndexKind.String]] as const) {
      const value = CHECKER.getIndexInfoOfType(t, kind)?.type
      if (value) under({ by: 'index', key }, value)
    }
    for (const [key, arg] of typeArgumentsOf(t)) under({ by: 'arg', key }, arg)
    for (const signature of t.getCallSignatures()) under({ by: 'return', key: '' }, signature.getReturnType())
  }
  open.delete(type)
  if (depth === 0) SLOTS.set(type, out)
  return out
}
/** The members a type holds at the end of a slot's path (each side of a union along it). */
const membersAlong = (source: ts.Type, path: Step[]): ts.Symbol[] => {
  let types = [source]
  for (const step of path.slice(0, -1)) {
    types = types.flatMap((type) => sidesOf(type)).flatMap((side): ts.Type[] => {
      if (step.by === 'prop') {
        const member = side.getProperty(step.key)
        return member ? [CHECKER.getTypeOfSymbol(member)] : []
      }
      if (step.by === 'index') return [CHECKER.getIndexInfoOfType(side, step.key === 'number' ? ts.IndexKind.Number : ts.IndexKind.String)?.type ?? []].flat()
      if (step.by === 'arg') return [typeArgumentsOf(side).get(step.key) ?? []].flat()
      return side.getCallSignatures().map((signature) => signature.getReturnType())
    })
  }
  const last = path[path.length - 1]
  return last ? types.flatMap((type) => sidesOf(type)).flatMap((side) => side.getProperty(last.key) ?? []) : []
}

/** Whether a class is a React class component: it extends React's Component or PureComponent, through any chain of
    classes. */
const isClassComponent = (cls: ts.ClassLikeDeclaration): boolean => {
  const seen = new Set<ts.Type>()
  const extendsReact = (type: ts.Type): boolean => {
    const t = type.flags & ts.TypeFlags.Object && (type as ts.ObjectType).objectFlags & ts.ObjectFlags.Reference ? (type as ts.TypeReference).target : type
    if (seen.has(t)) return false
    seen.add(t)
    const symbol = t.getSymbol()
    const react = (symbol?.declarations ?? []).some((d) => /[\\/]node_modules[\\/]@types[\\/]react[\\/]/.test(d.getSourceFile().fileName))
    if (react && (symbol?.name === 'Component' || symbol?.name === 'PureComponent')) return true
    return t.isClassOrInterface() && CHECKER.getBaseTypes(t).some(extendsReact)
  }
  return extendsReact(CHECKER.getTypeAtLocation(cls))
}
/** A class component's render, which React calls on the instance and prints what it returns: a method, or a field
    whose value is a function (`render = () => …`). A static member is the class's own, which React never calls. */
const renderOf = (cls: ts.ClassLikeDeclaration): Fn | undefined => {
  for (const m of cls.members) {
    if (!(ts.isMethodDeclaration(m) || ts.isPropertyDeclaration(m)) || keyText(m.name) !== 'render') continue
    if (m.modifiers?.some((x) => x.kind === ts.SyntaxKind.StaticKeyword)) continue
    if (ts.isMethodDeclaration(m) && m.body) return m
    const fn = ts.isPropertyDeclaration(m) && m.initializer ? unwrapHeld(m.initializer) : undefined
    if (fn && (ts.isArrowFunction(fn) || ts.isFunctionExpression(fn))) return fn
  }
  return undefined
}

const resolved = (symbol: ts.Symbol | undefined) => (symbol && symbol.flags & ts.SymbolFlags.Alias ? CHECKER.getAliasedSymbol(symbol) : symbol)
const FORMATTER = (() => {
  const fn = PROGRAM.getSourceFile(FORMATTER_FILE)?.statements.find(
    (s): s is ts.FunctionDeclaration => ts.isFunctionDeclaration(s) && s.name?.text === 'formatCompanyName',
  )
  if (!fn) throw new Error(`${relative(FORMATTER_FILE)} declares no formatCompanyName: the gate cannot tell the display form`)
  return fn
})()
/** The declaration a callee reaches, through an import's alias and a namespace's member. */
const calleeTarget = (callee: ts.Expression) => {
  const e = unwrapHeld(callee)
  const at = ts.isPropertyAccessExpression(e) ? e.name : ts.isIdentifier(e) ? e : undefined
  return resolved(at && CHECKER.getSymbolAtLocation(at))
}

/** How a value reads: a served name, the display form, an element, which is a value of its own (its children are
    read where they are written, so an element held in a name or returned is never read twice), or another module's
    function that hands back a served name, held as a value: a call of it, wherever the reader reads one, is served. */
type Leaf = 'served' | 'shown' | 'element' | 'serving'
interface Finding {
  node: ts.Node
  line: number
  rule: 'A' | 'B'
  shown: string
}
/** A fill of a field of the app's own, for the census of what fills each. */
interface Fill {
  field: Field
  node: ts.Node
}

const isFnNode = (n: ts.Node | undefined): n is Fn =>
  !!n && (ts.isFunctionDeclaration(n) || ts.isArrowFunction(n) || ts.isFunctionExpression(n) || ts.isMethodDeclaration(n))
/** What hands back what it returns: a function, or a getter (an object literal's or a class's), which a read of its
    property calls. */
type Returner = Fn | ts.GetAccessorDeclaration
const isReturner = (n: ts.Node | undefined): n is Returner => isFnNode(n) || (!!n && ts.isGetAccessorDeclaration(n))
/** What a function or a getter returns: an arrow's expression body, and each `return` in its body outside the functions
    nested in it. */
const returnsOf = (fn: Returner): ts.Expression[] => {
  if (!fn.body) return []
  if (!ts.isBlock(fn.body)) return [fn.body]
  const out: ts.Expression[] = []
  const walk = (n: ts.Node): void => {
    if (ts.isFunctionLike(n)) return
    if (ts.isReturnStatement(n) && n.expression) out.push(n.expression)
    ts.forEachChild(n, walk)
  }
  ts.forEachChild(fn.body, walk)
  return out
}
/** The functions a declaration holds: itself, or what a const or a property is given, read as a value is read:
    through parentheses, `as`, `satisfies` and `!`, both arms of a conditional, both sides of `||` and `??` and the right
    of `&&`, and a name or a member that holds one, by every declaration it has (an overloaded function's signatures
    and its body, so the body that returns is never missed). */
const functionsOf = (d: ts.Node | undefined, seen = new Set<ts.Node>()): Fn[] => {
  if (!d || seen.has(d)) return []
  seen.add(d)
  if (isFnNode(d)) return [d]
  const declared = (symbol: ts.Symbol | undefined): Fn[] => (symbol?.declarations ?? []).flatMap((x) => functionsOf(x, seen))
  const held = (expression: ts.Expression): Fn[] => {
    const e = unwrapHeld(expression)
    if (isFnNode(e)) return [e]
    if (ts.isConditionalExpression(e)) return [...held(e.whenTrue), ...held(e.whenFalse)]
    if (ts.isBinaryExpression(e)) {
      const op = e.operatorToken.kind
      if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken) return [...held(e.left), ...held(e.right)]
      return op === ts.SyntaxKind.AmpersandAmpersandToken ? held(e.right) : []
    }
    return ts.isIdentifier(e) || ts.isPropertyAccessExpression(e) ? declared(calleeTarget(e)) : []
  }
  if (ts.isShorthandPropertyAssignment(d)) return declared(resolved(CHECKER.getShorthandAssignmentValueSymbol(d)))
  const init = ts.isVariableDeclaration(d) || ts.isPropertyAssignment(d) ? d.initializer : undefined
  return init ? held(init) : []
}
/** The functions of the app's other modules an expression names (a call's callee, or a function handed on as a
    value), through an import's alias, a namespace's member, a re-export, an object's method and a const that holds
    one (functionsOf; a library's are no app code, and the formatter gives the display form). */
const crossTargets = (expression: ts.Expression, sf: ts.SourceFile): Fn[] =>
  (calleeTarget(expression)?.declarations ?? [])
    .flatMap((d) => functionsOf(d))
    .filter((fn) => fn.getSourceFile() !== sf && !/[\\/]node_modules[\\/]/.test(fn.getSourceFile().fileName) && fn !== FORMATTER)

/**
 * One source's reading (the header's): its values followed by the shared reader with `passThrough` and React's state
 * on, a call of another module's function that hands back a served name as text (servedReturns) holding the name.
 */
function readerOf(sf: ts.SourceFile, servedReturns: ReadonlySet<Returner>) {
  const declarationOf = scopeResolver(sf)

  /** Whether a callee is formatCompanyName: an import under any name, the module's namespace, or a same-file const. */
  const isFormatter = (callee: ts.Expression, seen = new Set<ts.Node>()): boolean => {
    if (calleeTarget(callee)?.declarations?.includes(FORMATTER)) return true
    const e = unwrapHeld(callee)
    const declaration = ts.isIdentifier(e) ? declarationOf(e) : undefined
    if (!declaration || seen.has(declaration) || !ts.isVariableDeclaration(declaration) || !declaration.initializer) return false
    seen.add(declaration)
    return isFormatter(declaration.initializer, seen)
  }
  /** Whether a call is one of React's element calls (by the declaration its callee reaches in React's types). */
  const isElementCall = (call: ts.CallExpression) => {
    const target = calleeTarget(call.expression)
    return !!target && ELEMENT_CALLS.has(target.name) && !!target.declarations?.some((d) => /[\\/]node_modules[\\/]@types[\\/]react[\\/]/.test(d.getSourceFile().fileName))
  }
  /** The members a binding takes from the object it destructures. */
  const bindingMembers = (element: ts.BindingElement): ts.Symbol[] => {
    if (!ts.isObjectBindingPattern(element.parent)) return []
    const key = keyText(element.propertyName ?? element.name)
    return key ? propertiesNamed(CHECKER.getTypeAtLocation(element.parent), key) : []
  }
  const leafOfFields = (fields: Field[]): Leaf[] | undefined => (fields.length === 0 ? undefined : [fields.some(isServed) ? 'served' : 'shown'])
  /** A read of a getter that hands back a served name (servedReturns), an object literal's or a class's, in any module:
      the read calls the getter, so it is served. */
  const gotten = (members: Array<ts.Symbol | undefined>): Leaf[] | undefined =>
    members.some((m) => (m?.declarations ?? []).some((d) => ts.isGetAccessorDeclaration(d) && servedReturns.has(d))) ? ['served'] : undefined
  /** A member read: a company-name field by its type, or a getter that hands back a served name. */
  const leafOfMembers = (members: Array<ts.Symbol | undefined>): Leaf[] | undefined =>
    leafOfFields(members.flatMap(fieldsOf)) ?? gotten(members)
  const leafOf = (e: ts.Expression): Leaf[] | undefined => {
    if (ts.isJsxElement(e) || ts.isJsxSelfClosingElement(e) || ts.isJsxFragment(e)) return ['element']
    if (ts.isCallExpression(e)) {
      if (isFormatter(e.expression)) return ['shown']
      if (isElementCall(e)) return ['element']
      // Another module's function that hands back a served name as text, however many modules it is handed through.
      if (crossTargets(e.expression, sf).some((fn) => servedReturns.has(fn))) return ['served']
      return undefined
    }
    if (ts.isPropertyAccessExpression(e)) return leafOfMembers([CHECKER.getSymbolAtLocation(e.name)]) ?? serving(e)
    if (ts.isElementAccessExpression(e)) return leafOfMembers([CHECKER.getSymbolAtLocation(e.argumentExpression)])
    if (ts.isIdentifier(e)) {
      const declaration = declarationOf(e)
      if (declaration && ts.isBindingElement(declaration)) return leafOfMembers(bindingMembers(declaration))
      if (declaration && (ts.isImportSpecifier(declaration) || ts.isImportClause(declaration))) return serving(e)
    }
    return undefined
  }
  /** Another module's function that hands back a served name, named but not called here: the reader calls it where the
      code does (a callback, a reducer, an initializer, a parameter a same-file function calls). */
  const serving = (e: ts.Expression): Leaf[] | undefined => (crossTargets(e, sf).some((fn) => servedReturns.has(fn)) ? ['serving'] : undefined)
  const calls = (leaf: Leaf): Leaf[] | undefined => (leaf === 'serving' ? ['served'] : undefined)
  return { declarationOf, values: heldValues<Leaf>(sf, leafOf, { passThrough: true, state: true, calls }) }
}
type Reader = ReturnType<typeof readerOf>

/** The sources the program holds outside node_modules: the scanned app, what it imports from the rest of the app, and
    the planted forms with the modules they import. */
const PROGRAM_SOURCES = PROGRAM.getSourceFiles().filter((sf) => !sf.isDeclarationFile && !/[\\/]node_modules[\\/]/.test(sf.fileName))
/**
 * The functions and getters that hand back a served name as text, to a fixed point over the program: each pass reads
 * every source with what the pass before it found, so a call of one from another module holds the name, as a same-file
 * call does, and so does a read of such a getter wherever the checker places it, through any chain of modules (a cycle
 * of them included). The set only grows, so it settles; the readings of its last pass, made with the settled set, are
 * the ones the scan uses.
 */
const { SERVED_RETURNS, READERS } = (() => {
  let served = new Set<Returner>()
  for (let pass = 0; pass <= PROGRAM_SOURCES.length; pass++) {
    const next = new Set<Returner>()
    const readers = new Map<ts.SourceFile, Reader>()
    for (const sf of PROGRAM_SOURCES) {
      const reader = readerOf(sf, served)
      readers.set(sf, reader)
      const walk = (node: ts.Node): void => {
        if (isReturner(node) && returnsOf(node).some((r) => renderedLeavesOf(reader.values.valueOf(r)).has('served'))) next.add(node)
        ts.forEachChild(node, walk)
      }
      walk(sf)
    }
    if (next.size === served.size) return { SERVED_RETURNS: next as ReadonlySet<Returner>, READERS: readers }
    served = next
  }
  throw new Error('the functions that hand back a served name never settle')
})()

/**
 * The functions some module renders as an element of a function another module declares: each tag in the program that
 * reaches one through an import's alias, a re-export, a module's default export, an object's member or a wrapper such as
 * memo (what the declaring module's reader holds there). Each is a component in the module that declares it, whatever
 * its name.
 */
const RENDERED_IN = (() => {
  const out = new Map<ts.SourceFile, Set<Fn>>()
  const held = (e: ts.Expression): Fn[] => [...(READERS.get(e.getSourceFile())?.values.valueOf(e).fns ?? [])]
  const declared = (d: ts.Node): Fn[] => {
    if (isFnNode(d)) return [d]
    if (ts.isExportAssignment(d)) return held(d.expression)
    if ((ts.isVariableDeclaration(d) || ts.isPropertyAssignment(d)) && d.initializer) return held(d.initializer)
    if (ts.isShorthandPropertyAssignment(d)) return (CHECKER.getShorthandAssignmentValueSymbol(d)?.declarations ?? []).flatMap(declared)
    return []
  }
  for (const sf of PROGRAM_SOURCES) {
    const walk = (node: ts.Node): void => {
      if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
        for (const d of calleeTarget(node.tagName as ts.Expression)?.declarations ?? []) {
          const home = d.getSourceFile()
          if (home === sf || !READERS.has(home)) continue
          for (const fn of declared(d)) out.set(home, (out.get(home) ?? new Set<Fn>()).add(fn))
        }
      }
      ts.forEachChild(node, walk)
    }
    walk(sf)
  }
  return out
})()

/** Every served name printed raw (A) and every field of the app's own filled with one (B) in one source. */
function findingsIn(sf: ts.SourceFile): { findings: Finding[]; fills: Fill[] } {
  const { declarationOf, values } = READERS.get(sf) ?? readerOf(sf, SERVED_RETURNS)
  const SERVED: Held<Leaf> = { leaves: new Map([['served', 1]]), props: null, fns: null }
  const servedIn = (value: Held<Leaf>) => leavesOf(value).has('served')
  const holds = (e: ts.Expression | undefined) => !!e && servedIn(values.valueOf(e))

  const findings: Finding[] = []
  const fills: Fill[] = []
  const seen = new Set<ts.Node>()
  const flag = (node: ts.Node, rule: Finding['rule']) => {
    if (seen.has(node)) return
    seen.add(node)
    const { line } = sf.getLineAndCharacterOfPosition(node.getStart(sf))
    findings.push({ node, line: line + 1, rule, shown: node.getText(sf).replace(/\s+/g, ' ').trim().slice(0, 90) })
  }
  /** A fill of fields: counted for the census where a field is the app's own, and failed when it holds a served name. */
  const fill = (fields: Field[], served: boolean, at: ts.Node) => {
    const own = fields.filter((f) => !isServed(f))
    if (own.length === 0) return
    for (const field of own) fills.push({ field, node: at })
    if (served) flag(at, 'B')
  }

  const fnsIn =(value: Held<Leaf>, out = new Set<Fn>(), visited = new Set<Held<Leaf>>()): Set<Fn> => {
    if (visited.has(value)) return out
    visited.add(value)
    for (const fn of value.fns ?? []) out.add(fn)
    for (const prop of value.props?.values() ?? []) fnsIn(prop, out, visited)
    return out
  }
  /** A function whose return prints (a component's, a column's render): its returns that are the name as text, or an
      array or a Set holding it, whose items React renders (renderedLeavesOf; an object it returns is no text). */
  const returnsServed = (fn: Fn) => {
    for (const r of returnsOf(fn)) if (renderedLeavesOf(values.valueOf(r)).has('served')) flag(r, 'A')
  }

  type Kind = 'host' | 'own' | 'unread'
  const kindOf = (opening: ts.JsxOpeningLikeElement): Kind => {
    const tag = componentTag(opening)
    if (!tag) return 'host'
    return values.valueOf(tag).fns?.size ? 'own' : 'unread'
  }
  /** The company-name fields a component's props declare under a key. */
  const propFields = (opening: ts.JsxOpeningLikeElement, key: string): Field[] =>
    propertiesNamed(CHECKER.getContextualType(opening.attributes), key).flatMap(fieldsOf)
  /** What a spread hands on under a key: a served object's own company-name field is the served name. */
  const spreadMember = (expression: ts.Expression, key: string): Held<Leaf> =>
    propertiesNamed(CHECKER.getTypeAtLocation(expression), key).flatMap(fieldsOf).some(isServed) ? SERVED : propertyOf(values.valueOf(expression), key)
  const spreadKeys = (expression: ts.Expression): string[] => [
    ...new Set([...(values.valueOf(expression).props?.keys() ?? []), ...CHECKER.getNonNullableType(CHECKER.getTypeAtLocation(expression)).getProperties().map((p) => p.name)]),
  ]

  const element = (el: ts.JsxElement | ts.JsxSelfClosingElement) => {
    const opening = ts.isJsxElement(el) ? el.openingElement : el
    const kind = kindOf(opening)
    const written = ts.isJsxElement(el) && el.children.some(writtenChild)
    const prints = (prop: string) => (prop === 'children' ? !written : kind === 'host' ? HOST_TEXT_PROPS.includes(prop) : kind === 'unread' && !ATTRIBUTE_PROPS.test(prop))
    const prop = (name: string, value: Held<Leaf>, at: ts.Node) => {
      const fields = kind === 'host' ? [] : propFields(opening, name)
      if (fields.length > 0) return fill(fields, servedIn(value), at)
      if (!prints(name)) return
      if (servedIn(value)) flag(at, 'A')
      if (kind !== 'unread') return
      fnsIn(value).forEach(returnsServed)
      // Another module's function that hands back a served name, which the component may call and print (a column's render).
      if (leavesOf(value).has('serving')) flag(at, 'A')
    }
    const attributes = opening.attributes.properties
    attributes.forEach((attr, i) => {
      if (ts.isJsxSpreadAttribute(attr)) {
        // A later attribute of the same name overrides what the spread hands on.
        const later = new Set(attributes.slice(i + 1).flatMap((a) => (ts.isJsxAttribute(a) ? [a.name.getText(sf)] : [])))
        const keys = kind === 'host' ? HOST_TEXT_PROPS : spreadKeys(attr.expression)
        for (const key of keys) {
          if (later.has(key)) continue
          prop(key, spreadMember(attr.expression, key), attr)
          // A member handed on whole, under a prop that is no company-name field (a view under `view`).
          if (kind !== 'host' && propFields(opening, key).length === 0) {
            handedMember(propertiesNamed(CHECKER.getContextualType(opening.attributes), key), attr.expression, key, attr)
          }
        }
        return
      }
      const init = attr.initializer
      const expression = !init ? undefined : ts.isJsxExpression(init) ? init.expression : init
      if (expression) prop(attr.name.getText(sf), values.valueOf(expression), attr)
    })
  }
  const rendersChildren = (parent: ts.Node) => ts.isJsxFragment(parent) || (ts.isJsxElement(parent) && kindOf(parent.openingElement) !== 'own')

  /** A call of Object's own method of that name (Object not shadowed in the file). */
  const isObjectMethod = (callee: ts.Expression, name: string) => {
    const e = unwrapHeld(callee)
    return ts.isPropertyAccessExpression(e) && e.name.text === name && ts.isIdentifier(e.expression) && e.expression.text === 'Object' && !declarationOf(e.expression)
  }
  const isObjectFreeze = (callee: ts.Expression) => isObjectMethod(callee, 'freeze')
  const isWithin = (inner: ts.Node, outer: ts.Node) => inner.getSourceFile() === outer.getSourceFile() && inner.pos >= outer.pos && inner.end <= outer.end
  /** The type an object literal is given: its context, read through the wrappers that hand it on whole (parentheses,
      `as`, `satisfies`, `!`, Object.freeze) while that context is only the literal's own type. */
  const givenType = (literal: ts.ObjectLiteralExpression): ts.Type | undefined => {
    let node: ts.Expression = literal
    for (;;) {
      const type = CHECKER.getContextualType(node)
      const own = !type || CHECKER.getNonNullableType(type).getProperties().every((p) => (p.declarations ?? []).every((d) => isWithin(d, literal)))
      if (!own) return type
      const parent: ts.Node = node.parent
      if (ts.isParenthesizedExpression(parent) || ts.isAsExpression(parent) || ts.isSatisfiesExpression(parent) || ts.isNonNullExpression(parent)) node = parent
      else if (ts.isCallExpression(parent) && parent.arguments[0] === node && isObjectFreeze(parent.expression)) node = parent
      else return type
    }
  }
  const hasIndex = (type: ts.Type | undefined) => !!type && !!CHECKER.getNonNullableType(type).getStringIndexType()
  const objectLiteral = (literal: ts.ObjectLiteralExpression) => {
    const type = givenType(literal)
    const placed = (key: string) => propertiesNamed(type, key).flatMap(fieldsOf).filter((f) => !isWithin(f, literal))
    const keys = literal.properties.map((p) => keyText(p.name))
    literal.properties.forEach((p, i) => {
      if (ts.isSpreadAssignment(p)) {
        // A spread fills each field the given type declares that no later property sets.
        const later = new Set(keys.slice(i + 1))
        for (const key of spreadKeys(p.expression)) {
          if (later.has(key)) continue
          const fields = placed(key)
          if (fields.length > 0) fill(fields, servedIn(spreadMember(p.expression, key)), p)
          // A member handed on whole, under a key the given type declares outside the literal (a view under `view`).
          else handedMember(propertiesNamed(type, key).filter((m) => !(m.declarations ?? []).every((d) => isWithin(d, literal))), p.expression, key, p)
        }
        return
      }
      // A property's value, or what its getter returns: a getter fills its key as a value does.
      const getter = ts.isGetAccessorDeclaration(p)
      if (!getter && !ts.isPropertyAssignment(p) && !ts.isShorthandPropertyAssignment(p)) return
      const key = keyText(p.name)
      if (!key) return
      const served = getter ? returnsOf(p).some(holds) : holds(ts.isPropertyAssignment(p) ? p.initializer : p.name)
      // The words Next prints from a page's metadata.
      if (METADATA_TEXT.has(key) && propertiesNamed(type, key).some((m) => m.declarations?.some(isNextDeclaration)) && served) return flag(p, 'A')
      const fields = placed(key)
      if (fields.length > 0) return fill(fields, served, p)
      // A literal the checker cannot place, holding a company-name key: read as a field of the app's own, unless the
      // type it is given has an index signature (a data payload) or declares the key (then the field is not a name).
      const nameKey = NAME_KEYS.has(key) || (key === 'name' && keys.includes('ticker'))
      if (nameKey && !hasIndex(type) && propertiesNamed(type, key).length === 0 && served) flag(p, 'B')
    })
  }
  const ASSIGNMENTS = new Set([ts.SyntaxKind.EqualsToken, ts.SyntaxKind.BarBarEqualsToken, ts.SyntaxKind.QuestionQuestionEqualsToken, ts.SyntaxKind.AmpersandAmpersandEqualsToken])
  const assignment = (node: ts.BinaryExpression) => {
    const target = unwrapHeld(node.left)
    const symbol = ts.isPropertyAccessExpression(target)
      ? CHECKER.getSymbolAtLocation(target.name)
      : ts.isElementAccessExpression(target)
        ? CHECKER.getSymbolAtLocation(target.argumentExpression)
        : undefined
    const fields = fieldsOf(symbol)
    if (fields.length > 0) fill(fields, holds(node.right), node)
  }

  /** A member read of a getter that hands back a served name (SERVED_RETURNS), an object literal's or a class's. */
  const servedGetter = (members: ts.Symbol[]) =>
    members.some((m) => (m.declarations ?? []).some((d) => ts.isGetAccessorDeclaration(d) && SERVED_RETURNS.has(d)))
  /**
   * A value handed whole to a type the place it reaches is given: each field of the app's own the type holds (slotsOf) is
   * filled with the value's member along the same steps, a served name when the value's type serves one there (a field
   * of an API type, or a getter that hands one back) or, along fields alone, the reader holds one there. A member that is
   * the same field (a view handed on as itself) is no fill for the census.
   */
  const handedInto = (target: ts.Type, source: ts.Type, held: () => Held<Leaf>, at: ts.Node) => {
    for (const { own, path } of slotsOf(target)) {
      const members = membersAlong(source, path)
      const from = members.flatMap(fieldsOf)
      const kept = () => path.every((step) => step.by === 'prop') && servedIn(path.reduce((value, step) => propertyOf(value, step.key), held()))
      const served = from.some(isServed) || servedGetter(members) || kept()
      if (served || from.some((f) => !own.includes(f))) fill(own, served, at)
    }
  }
  /** A spread's member under a key, handed on whole to each member the place declares there. */
  const handedMember = (into: ts.Symbol[], from: ts.Expression, key: string, at: ts.Node) => {
    const targets = into.map((m) => CHECKER.getTypeOfSymbol(m)).filter((type) => slotsOf(type).length > 0)
    if (targets.length === 0) return
    const members = propertiesNamed(CHECKER.getTypeAtLocation(from), key)
    for (const target of targets) {
      for (const m of members) handedInto(target, CHECKER.getTypeOfSymbol(m), () => propertyOf(values.valueOf(from), key), at)
    }
  }
  /** The type a generic's parameter declares, read through its constraint: what a value handed to it fills, whatever
      the checker infers for the call (an argument, or a JSX attribute's value, of a generic function or component). */
  const declaredFor = (value: ts.Expression): ts.Type | undefined => {
    const parent = value.parent
    if ((ts.isCallExpression(parent) || ts.isNewExpression(parent)) && parent.arguments?.includes(value)) {
      const declaration = CHECKER.getResolvedSignature(parent)?.getDeclaration()
      if (!declaration?.typeParameters?.length) return undefined
      const i = parent.arguments.indexOf(value)
      const params = declaration.parameters
      const param = params[Math.min(i, params.length - 1)]
      if (!param || (i >= params.length && !param.dotDotDotToken)) return undefined
      const type = CHECKER.getTypeAtLocation(param)
      return param.dotDotDotToken ? CHECKER.getIndexInfoOfType(type, ts.IndexKind.Number)?.type : type
    }
    const attribute = ts.isJsxExpression(parent) ? parent.parent : undefined
    if (!attribute || !ts.isJsxAttribute(attribute)) return undefined
    const declaration = CHECKER.getResolvedSignature(attribute.parent.parent)?.getDeclaration()
    const props = declaration?.typeParameters?.length ? declaration.parameters[0] : undefined
    const member = props && CHECKER.getTypeAtLocation(props).getProperty(attribute.name.getText(sf))
    return member && CHECKER.getTypeOfSymbol(member)
  }
  interface Handed {
    value: ts.Expression
    into: Array<ts.Type | undefined>
    /** A spread argument, which hands on its elements. */
    spread?: boolean
  }
  const placedBy = (value: ts.Expression): Handed[] => [{ value, into: [CHECKER.getContextualType(value), declaredFor(value)] }]
  /** Where a value is handed whole to a type, with that type: a declaration's or a default's initializer, an
      assignment's right side, a return, an arrow's body and a yield (the function's return type, declared or given),
      a call's argument (a spread one's elements, and a generic's parameter by its constraint), Object.assign's
      sources (its target's type), an object literal's member, an array's element or spread, a JSX attribute's value,
      and an assertion's operand (`as`, `<T>`, `satisfies`). A spread's members are handed where the literal or the
      props read the spread. */
  const handedAt = (node: ts.Node): Handed[] => {
    if (ts.isVariableDeclaration(node) || ts.isParameter(node) || ts.isBindingElement(node) || ts.isPropertyDeclaration(node)) {
      return node.initializer ? placedBy(node.initializer) : []
    }
    if (ts.isBinaryExpression(node)) return ASSIGNMENTS.has(node.operatorToken.kind) ? placedBy(node.right) : []
    if (ts.isReturnStatement(node) || ts.isYieldExpression(node)) return node.expression ? placedBy(node.expression) : []
    if (ts.isArrowFunction(node)) return ts.isBlock(node.body) ? [] : placedBy(node.body)
    if (ts.isCallExpression(node) && isObjectMethod(node.expression, 'assign') && node.arguments.length > 1) {
      const target = CHECKER.getTypeAtLocation(node.arguments[0])
      return node.arguments.slice(1).flatMap((value) => (ts.isSpreadElement(value) ? [] : [{ value, into: [target] }]))
    }
    if (ts.isCallExpression(node) || ts.isNewExpression(node)) {
      return (node.arguments ?? []).flatMap((a) => (ts.isSpreadElement(a) ? [{ value: a.expression, into: [CHECKER.getContextualType(a)], spread: true }] : placedBy(a)))
    }
    if (ts.isPropertyAssignment(node)) return placedBy(node.initializer)
    if (ts.isShorthandPropertyAssignment(node)) return placedBy(node.name)
    if (ts.isArrayLiteralExpression(node)) {
      return node.elements.flatMap((e) =>
        ts.isSpreadElement(e) ? [{ value: e.expression, into: [CHECKER.getContextualType(node)] }] : ts.isOmittedExpression(e) ? [] : placedBy(e),
      )
    }
    if (ts.isJsxAttribute(node)) return node.initializer && ts.isJsxExpression(node.initializer) && node.initializer.expression ? placedBy(node.initializer.expression) : []
    if (ts.isAsExpression(node) || ts.isTypeAssertionExpression(node) || ts.isSatisfiesExpression(node)) return placedBy(node.expression)
    return []
  }
  /** The values a handed expression may be: through parentheses and `!`, both arms of a conditional, both sides of `||`
      and `??`, and the right of `&&` and of a comma. An object or array literal, a function and an element are no value
      here: each member, element, return and child of theirs is a place of its own. */
  const handedValues = (e: ts.Expression): ts.Expression[] => {
    if (ts.isParenthesizedExpression(e) || ts.isNonNullExpression(e)) return handedValues(e.expression)
    if (ts.isConditionalExpression(e)) return [...handedValues(e.whenTrue), ...handedValues(e.whenFalse)]
    if (ts.isBinaryExpression(e)) {
      const op = e.operatorToken.kind
      if (op === ts.SyntaxKind.BarBarToken || op === ts.SyntaxKind.QuestionQuestionToken) return [...handedValues(e.left), ...handedValues(e.right)]
      if (op === ts.SyntaxKind.AmpersandAmpersandToken || op === ts.SyntaxKind.CommaToken) return handedValues(e.right)
    }
    const literal = ts.isObjectLiteralExpression(e) || ts.isArrayLiteralExpression(e) || ts.isClassExpression(e) || ts.isFunctionLike(e)
    return literal || ts.isJsxElement(e) || ts.isJsxSelfClosingElement(e) || ts.isJsxFragment(e) ? [] : [e]
  }
  const NO_VALUE: Held<Leaf> = { leaves: new Map(), props: null, fns: null }
  /** A constructor's parameter property that is a field of the app's own: what a `new` or a `super` call hands it
      fills the field. */
  const constructed = (node: ts.NewExpression | ts.CallExpression) => {
    const declaration = CHECKER.getResolvedSignature(node)?.getDeclaration()
    if (!declaration || !ts.isConstructorDeclaration(declaration)) return
    ;(node.arguments ?? []).forEach((arg, i) => {
      const param = declaration.parameters[i]
      if (param && !ts.isSpreadElement(arg) && isNameField(param)) fill([param], holds(arg), arg)
    })
  }
  const handed = ({ value, into, spread }: Handed) => {
    const targets = into.filter((t): t is ts.Type => !!t)
    if (targets.length === 0) return
    for (const leaf of handedValues(value)) {
      const type = CHECKER.getTypeAtLocation(leaf)
      const sources = spread ? elementsOf(type) : [type]
      for (const target of targets) for (const source of sources) handedInto(target, source, spread ? () => NO_VALUE : () => values.valueOf(leaf), leaf)
    }
  }

  // The same-file components: each rendered here as a tag, rendered by another module (RENDERED_IN), exported as the
  // module's default (a page Next renders, or one a module renders through its default import, lazily or not), named
  // for one (PascalCase), or a class component's render.
  const components = new Set<Fn>(RENDERED_IN.get(sf))
  const heldHere = (d: ts.Node): Fn[] => (isFnNode(d) ? [d] : ts.isVariableDeclaration(d) && d.initializer ? [...(values.valueOf(d.initializer).fns ?? [])] : [])
  const collect = (node: ts.Node): void => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const tag = componentTag(node)
      for (const fn of (tag && values.valueOf(tag).fns) || []) components.add(fn)
    }
    if (ts.isFunctionDeclaration(node) && node.name && /^[A-Z]/.test(node.name.text)) components.add(node)
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && /^[A-Z]/.test(node.name.text) && node.initializer) {
      for (const fn of values.valueOf(node.initializer).fns ?? []) components.add(fn)
    }
    if (ts.isFunctionDeclaration(node) && node.modifiers?.some((m) => m.kind === ts.SyntaxKind.DefaultKeyword)) components.add(node)
    if (ts.isExportAssignment(node) && !node.isExportEquals) for (const fn of values.valueOf(node.expression).fns ?? []) components.add(fn)
    if (ts.isExportSpecifier(node) && node.name.text === 'default') {
      for (const d of CHECKER.getExportSpecifierLocalTargetSymbol(node)?.declarations ?? []) for (const fn of heldHere(d)) components.add(fn)
    }
    // A class component: React calls its render.
    const render = ts.isClassLike(node) && isClassComponent(node) ? renderOf(node) : undefined
    if (render) components.add(render)
    ts.forEachChild(node, collect)
  }
  collect(sf)

  const visit = (node: ts.Node): void => {
    if (ts.isJsxExpression(node) && node.expression && rendersChildren(node.parent) && holds(node.expression)) flag(node, 'A')
    if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) element(node)
    if (ts.isObjectLiteralExpression(node)) objectLiteral(node)
    if (ts.isBinaryExpression(node) && ASSIGNMENTS.has(node.operatorToken.kind)) assignment(node)
    handedAt(node).forEach(handed)
    if (ts.isNewExpression(node) || (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.SuperKeyword)) constructed(node)
    ts.forEachChild(node, visit)
  }
  visit(sf)
  components.forEach(returnsServed)
  return { findings: findings.sort((a, b) => a.line - b.line), fills }
}

const sourceOf = (file: string) => {
  const sf = PROGRAM.getSourceFile(file)
  if (!sf) throw new Error(`${relative(file)} is not in the program`)
  return sf
}
const SCANS = FILES.map((file) => ({ file, ...findingsIn(sourceOf(file)) }))

/** Every app source the program holds (the scanned files and what they import from elsewhere in the app, types/
    included), outside node_modules and the tests. */
const APP_SOURCES = PROGRAM.getSourceFiles().filter((sf) => {
  const rel = relative(sf.fileName)
  return !rel.startsWith('..') && !rel.includes('node_modules/') && !rel.startsWith('tests/')
})
/** Every company-name field the app declares. */
const DECLARED: Field[] = APP_SOURCES.flatMap((sf) => {
  const out: Field[] = []
  const walk = (node: ts.Node): void => {
    if (isNameField(node)) out.push(node)
    ts.forEachChild(node, walk)
  }
  walk(sf)
  return out
})

describe('a served company name prints through formatCompanyName (E146)', () => {
  it('scores every planted form in tests/unit/fixtures/companyNameForms.tsx and companyNameRendered/ as its mark says', () => {
    // A form is a top-level statement its comment marks: in companyNameForms.tsx a function or a class (a class
    // component's) named for its mark, and in a module of companyNameRendered/ whatever statement holds the form (a
    // default export, a const). A top-level helper named for a form (N23Line) is that form's.
    const forms = new Map<string, string>()
    const named = new Set<string>()
    const strays: string[] = []
    for (const file of FORM_MODULES) {
      const sf = sourceOf(file)
      const markOf = (stmt: ts.Statement) =>
        ts.getLeadingCommentRanges(sf.text, stmt.pos)?.map((r) => /^\/\*\*\s*(N\d+) (flag|clean|gap):/.exec(sf.text.slice(r.pos, r.end))).find(Boolean)
      const nameOf = (stmt: ts.Statement) => (ts.isFunctionDeclaration(stmt) || ts.isClassDeclaration(stmt) ? stmt.name?.text : undefined)
      const marks = new Map<ts.Statement, string>()
      for (const stmt of sf.statements) {
        const mark = markOf(stmt)
        if (!mark || (file === FORMS && mark[1] !== nameOf(stmt))) continue
        forms.set(mark[1], mark[2])
        marks.set(stmt, mark[1])
      }
      const formOf = (node: ts.Node): string | undefined => {
        const top = sf.statements.find((s) => node.pos >= s.pos && node.end <= s.end)
        if (!top) return undefined
        return marks.get(top) ?? /^N\d+/.exec(nameOf(top) ?? '')?.[0]
      }
      for (const f of findingsIn(sf).findings) {
        const form = formOf(f.node)
        if (form && forms.has(form)) named.add(form)
        else strays.push(`${relative(file)} line ${f.line}: ${f.shown}`)
      }
    }
    const count = (mark: string) => [...forms.values()].filter((m) => m === mark).length
    expect([count('flag'), count('clean'), count('gap')], 'the forms planted: flagged, clean and gaps').toEqual([168, 54, 32])
    const misread = [...forms].filter(([name, mark]) => named.has(name) !== (mark === 'flag')).map(([name, mark]) => `${name} (${mark})`)
    expect(misread, 'the gate reads these forms against their marks: fix the gate, or flip the mark with its record').toEqual([])
    expect(strays, 'the gate named a node outside a planted form').toEqual([])
  })

  it('reads the API types: the served fields it knows, and every string field named like a company', () => {
    const served = DECLARED.filter(isServed).map(fieldName)
    expect(served, 'the reading finds the served names the app prints').toEqual(
      expect.arrayContaining([
        'CalendarEvent.company_name',
        'NotificationItem.company_name',
        'AnalysisCoverage.company_name',
        'Company.name',
        'FullTextSearchHit.company',
        'NotableFiling.company_name',
        'ReportingCompany.name',
        'ExampleData.companyName',
      ]),
    )
    // A name served under another field would pass unread: each string field of an API type named for a company, an
    // issuer, a filer, a registrant or an entity is read as a name or listed as none.
    const unread: string[] = []
    const apiSources = APP_SOURCES.filter((sf) => isApiModule(sf.fileName))
    expect(apiSources.length, 'the census reads the API modules').toBeGreaterThan(20)
    for (const sf of apiSources) {
      const walk = (node: ts.Node): void => {
        if (isFieldDeclaration(node) && NAMED_LIKE_A_COMPANY.test(keyText(node.name) ?? '')) {
          if (stringLike(CHECKER.getTypeAtLocation(node)) && !isNameField(node) && !NOT_NAMES.includes(fieldName(node))) unread.push(fieldName(node))
        }
        ts.forEachChild(node, walk)
      }
      walk(sf)
    }
    expect(unread, 'an API field named like a company: add its key to NAME_KEYS, or to NOT_NAMES with the reason').toEqual([])
  })

  it('sees a fill of every field of the app’s own', () => {
    const filled = new Set(SCANS.flatMap(({ fills }) => fills.map((f) => f.field)))
    const own = DECLARED.filter((field) => !isServed(field))
    expect(own.map(fieldName), 'the app’s own fields include CompanyLogo’s name and the redlines’ source').toEqual(
      expect.arrayContaining(['CompanyLogoProps.name', 'RedlineSource.companyName', 'SourceIdentity.companyName', 'ChartExportHeader.company']),
    )
    expect(
      own.filter((field) => !filled.has(field)).map(fieldName),
      'nothing the gate can see fills these fields of the app’s own, so their values come from where it cannot check them: ' +
        'declare a type the API serves in an API module, or give the object that fills the field its type',
    ).toEqual([])
  })

  it('finds no served company name printed raw, and no field of the app’s own filled with one', () => {
    // A floor, so a walk that reads nothing cannot pass.
    expect(FILES.length, 'the scan reads the app').toBeGreaterThan(300)
    expect(SCANS.reduce((n, { fills }) => n + fills.length, 0), 'the scan sees the fills of the app’s own fields').toBeGreaterThan(10)
    const violations = SCANS.flatMap(({ file, findings }) => findings.map((f) => `${relative(file)}:${f.line} (${f.rule}) ${f.shown}`))
    expect(
      violations,
      'A served company name prints through formatCompanyName (lib/formatCompanyName.ts), so a company reads the same ' +
        'everywhere: format it once where it enters a feature (a mapper, or a component before it prints the line and the ' +
        'mark) and print that. Keep the raw name where it is data: a key, a URL, a query, an analytics property, a payload.\n' +
        violations.join('\n'),
    ).toEqual([])
  })
})
