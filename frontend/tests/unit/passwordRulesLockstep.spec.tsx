import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { ESLint } from 'eslint'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import PasswordField from '@/features/auth/components/PasswordField'
import { PASSWORD_MIN_LENGTH, PASSWORD_RULE } from '@/lib/passwordRules'
import { bindingEscape, bindingReferences, bindingResolver, containerEscape, writtenAs, type Binding } from './astBindings'

/**
 * The password rule the UI states moves in lockstep with the server (CLAUDE.md rule 12; the
 * planLimitsLockstep pattern). The reset page once told users "with upper- and lowercase letters and a
 * number", a rule the server never had (2026-10 audit, UA-35), and the strength meter called an
 * 11-character password "Good" though the server rejects it (UA-43).
 *
 *  - lib/passwordRules.ts mirrors the minimum the server enforces (backend/app/config.py
 *    PASSWORD_MIN_LENGTH, read by password_utils.validate_password_strength). Every statement of that
 *    validator's body is pinned (a helper call is a statement too), and every password field of the auth
 *    schemas (backend/app/routers/auth.py) is a bare `str` whose validator only calls it, so PASSWORD_RULE
 *    states the whole rule. A check written into a route handler's own body is not read here.
 *  - PASSWORD_RULE's "We check new passwords against known data breaches" stands only while the
 *    HaveIBeenPwned check defaults on (backend/app/config.py PWNED_PASSWORD_CHECK_ENABLED,
 *    backend/app/services/pwned_passwords.py) and the two routes behind the pages that state it (register
 *    and reset_password) call it. It names the check, never a refusal: the lookup fails open (an outage or
 *    an error lets the password through), so a sentence saying breached passwords are rejected, refused or
 *    blocked would be false whenever it does.
 *  - A file that handles a password (renders a password field or reads lib/passwordRules) never writes a
 *    length by hand: no length in copy ("12 characters", "12-character", "12+", "12 or more", "twelve"),
 *    on one line, composed across JSX text and its expressions (`At least {12}` then `characters` on the
 *    next line), or composed in a template literal or a `+` chain (its literal parts and the number each
 *    slot holds, a literal or a numeric constant of any name: `Use at least ${MIN_CHARS} characters.`; an
 *    element's text is read composed and with each template or chain in its braces a gap, a count either
 *    reading states failing, so composing never hides one), no `minLength` or `min_length` number, no local
 *    constant whose name says min and len, no `.length` compared against a number or a numeric constant of
 *    any name, no `.min(n)` call or `.{n,}` pattern, and no number equal to the floor anywhere in its code.
 *    Beside those readings, every value a slot, an operand or a braced expression can render is read, as the
 *    field reader below reads an autoComplete (a ternary's either branch, `&&`, `||`, `??`, a const of any
 *    kind, a name destructured at any depth, an object's entry or a member path, a same-file function's
 *    return), one branching value at a time with the others
 *    gaps, in copy, a comparison, a minimum call, a pattern composed in a template or a chain, and a
 *    `minLength` held in a value. Any other file that mentions a password never types the floor itself, in
 *    any of those forms or in a constant named for a minimum, a length, a floor or a password. Not read, each
 *    planted as a gap: a count computed at runtime or worked out by arithmetic (`${8 + 4}`), and one only two
 *    branching values state together (`{a ? 1 : 9}{b ? 2 : 9} characters`); a value with more readings than
 *    the evaluator takes fails loudly, and so does one nested past the 24 steps it follows (a cycle of consts) or
 *    read through a container, a parameter or props that can change (as the field reader below reads them), where
 *    a gap would hide what the page renders. The two pages that state PASSWORD_RULE render it word for word,
 *    whatever their source looks like (authPagesCopy.spec.tsx for /reset-password, RegisterForm.spec.tsx for
 *    /register).
 *  - Every new-password field carries `minLength={PASSWORD_MIN_LENGTH}`, or its form checks
 *    `.length < PASSWORD_MIN_LENGTH` in its code (CODE_CHECKED, read on the syntax tree, so a comment or a
 *    string does not count). A field's `autoComplete` is read in every value it can render: a literal,
 *    braced or not; a template or a `+` chain, each part's every value; each branch of a condition, nested;
 *    `&&`, `||` and `??` as the language takes them; a same-file const; a name destructured at any depth out
 *    of an object or an array (a key, renamed or not, an index, a rest without the keys taken beside it, each
 *    step's default); a same-file object's or array's entry or a member path (`CONFIG.inputs.ac`), or every
 *    entry for a key the reader cannot name (`MODES[kind]`); a same-file function's every return (one called
 *    where it stands and `useMemo`'s factory among them; undefined where its body can end without one: an if
 *    with an else, a switch with a default and a try with a catch that return in every arm end in none, and a
 *    loop is read as able to end, so a function whose loop returns fails closed), its parameters bound to the
 *    call's arguments; and a prop the component forwards (a key of its first parameter, destructured, `props.x`
 *    or taken by a const; a spread of its props, or of a rest without the key), with the default it renders. A
 *    container (an object or an array, nested or not) is read through a binding or a member path only while
 *    nothing can change it after its initializer: a const binding stops a reassignment of the name, not a write
 *    into what it holds, so every use of the container, of an alias or of a part of it must read it (a const or
 *    a `let` that holds it, a pattern, a rest read as it without the keys taken, another object it is stored in,
 *    a spread copy that holds a part, a same-file function's parameter and an array method's callback are
 *    followed; astBindings' containerEscape reads each use). An entry assigned (`=`, a compound or a logical
 *    assignment), incremented, deleted, or assigned by destructuring or a loop; a method that may write it
 *    (`push`, `pop`, `shift`, `unshift`, `splice`, `sort`, `reverse`, `fill`, `copyWithin`, one that reads
 *    `this`); the container or a part of it handed to a call (`Object.assign`, `defineProperty`,
 *    `defineProperties` and `setPrototypeOf`, `Reflect.set`, `deleteProperty` and `defineProperty`, a function
 *    of another module, a same-file one that writes it), to a component or to React as a ref; stored by an
 *    assignment or into a `var`; returned; or exported, which another module may write: each makes every value
 *    read through the container fail loudly, with the use and its line. `as const` is types only, so its
 *    container is read like any other; `Object.freeze` is read through (it hands back what it is handed) and
 *    the container still checked, since a freeze is shallow and a write before it lands. A parameter assigned
 *    in its function, and props written in the component (through them or a rest of them; calling a prop is a
 *    read), fail the same way. A field is a new-password field when one of those values names
 *    new-password, and it fails when any value names neither new- nor current-password ("off", a falsy `&&`,
 *    undefined, null or void, in any branch: `reset ? 'new-password' : 'off'` fails). A form the reader
 *    cannot evaluate fails loudly, with the form: a name from another module, a `let`, a call, an object or
 *    a spread it cannot follow, a class's `this.props`, a value destructured from inside a prop, a computed
 *    key or an array's rest destructured, a forwarded value composed into text, a prop of a parameter after
 *    the first, more than 64 composed values, a value nested past the 24 steps the evaluator follows (a cycle
 *    of consts). Every password field (a `type` that can be
 *    password, a PasswordField, or a component that forwards one, rendered, called as a function or created
 *    with `createElement`) names its autoComplete so. A forwarding component (FORWARDERS, found to a fixed
 *    point) is read at each caller, under every name the caller renders it by: its declared name; a const
 *    that holds it, through any call that wraps it (forwardRef, memo, a `lazy` or `dynamic` loader), a
 *    condition's either branch or a logical operator; an entry of the objects a const holds, at any depth
 *    (`Fields.Secret`, `Kit.inputs.Secret`), dotted, by a literal key, or every entry for any other key
 *    (`PICK[which]`); a name destructured out of any of these (renamed, nested, with a default, both read, an
 *    array's element); an import under any name (default, `{ A as B }`, a namespace, an object imported under
 *    an alias, through re-exports); and a prop of a same-file component that its callers hand it
 *    (`<Page Field={Secret} />` read where Page renders `<Field>`, an `as` prop among them), run to a fixed
 *    point however many components hand it down. The follower takes eight steps from where a name is rendered
 *    (each const, key, pattern, module, branch of a condition or a logical operator and wrapping call is one),
 *    and a prop is handed names of at most eight member steps: a chain longer than that, or a cycle (a const
 *    that holds itself, an `export *` that re-exports itself, a component that hands a member of its own prop
 *    back to itself), names a component it cannot follow, and a tag, a `createElement` or a call named as a
 *    component that renders one fails loudly, with where it stopped. A component is named
 *    through a container (an entry, an element, a pattern over one) only while nothing in its module can change
 *    the container, each use read as above: a tag, a `createElement` or a call named as a component (a capital,
 *    as JSX requires) through one that can fails loudly. One forwarded
 *    from a function the reader cannot name (a callback, a render prop) fails loudly, every forwarding
 *    component is rendered by a file the scan reads, and the scan must find the app's new-password fields,
 *    so a field it cannot read fails instead of passing unseen. Not read, each planted as a gap: an element
 *    built by a factory, which lint refuses (eslint.designRules.mjs's elements-built-with-jsx refuses React's
 *    element factories in app code under any name, so the scan reads `createElement`, `jsx`, `jsxs` and
 *    `jsxDEV` called by those names and follows no other: `h('input', …)` with `createElement as h`, and a
 *    clone's override, `cloneElement`, are lint's, planted with the rule's finding), an `as` prop of a
 *    component no file the scan reads declares, a component
 *    loaded by a `.then`, destructured by a computed key, out of a `let`, out of a call or out of an array's
 *    rest, a `type` forwarded under another prop's name or carried only by a spread the reader cannot
 *    follow, a value written to the DOM, a write into a container another module declares (an import is named
 *    by its declaration, so an export is followed rather than refused), and a component written into a
 *    container, or reached past the follower's reach, and called under a lowercase name.
 *  - Every file under SOURCE_ROOTS is read (scripts, Markdown, MDX) or listed in NOT_READ with why it can
 *    hold no password rule.
 *  - The strength meter says "Too short" under the minimum and scores length past it.
 */
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const backend = (rel: string) => readFileSync(path.resolve(frontendDir, '../backend', rel), 'utf8')

const SOURCE_ROOTS = ['app', 'features', 'components', 'lib', 'hooks']
/** Renders a password field or reads the rule. */
const HANDLES_PASSWORD = /type=\{?\s*["'`]password["'`]|<PasswordField\b|["'`](?:new|current)-password["'`]|@\/lib\/passwordRules/

/** The counts copy spells out, to twenty. */
const NUMBER_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty']
/** A length in copy: "12 characters", "12-character", "12+ characters", "12 or more characters", "twelve chars". */
const lengthInCopy = (count: string) =>
  new RegExp(String.raw`\b${count}\+?(?:\s+or\s+(?:more|longer))?[\s‐-―-]+(?:characters?|chars?)\b`, 'i')
const ANY_COUNT = String.raw`(?:\d+|${NUMBER_WORDS.join('|')})`
const FLOOR_COUNT = String.raw`(?:${PASSWORD_MIN_LENGTH}|${NUMBER_WORDS[PASSWORD_MIN_LENGTH] ?? PASSWORD_MIN_LENGTH})`
/** `minLength={12}`, `minLength: 12`, `minlength="12"`, `min_length=12`. */
const MIN_LENGTH_NUMBER = /\bmin_?length\b\s*(?:=\s*\{?\s*|:\s*)["'`]?\d+/i
/** A constant whose name says min and len, in either order and any case, set to a number. */
const MIN_CONSTANT = /\b\w*(?:min\w*len|len\w*min)\w*\s*(?::\s*[\w.]+\s*)?=\s*\d+/i

type Pattern = { label: string; pattern: RegExp }
/** Written by hand in a file that handles a password. */
const HAND_TYPED: Pattern[] = [
  { label: 'a minLength literal', pattern: MIN_LENGTH_NUMBER },
  { label: 'a length in copy', pattern: lengthInCopy(ANY_COUNT) },
  { label: 'a local minimum constant', pattern: MIN_CONSTANT },
  { label: 'a length compared against a number', pattern: /\.length\s*[<>]=?\s*[1-9]\d*|\b[1-9]\d*\s*[<>]=?\s*[\w.]*\.length\b/ },
]
/** In any other file that mentions a password: the floor itself, typed. */
const FLOOR_TYPED: Pattern[] = [
  { label: 'a minLength literal', pattern: MIN_LENGTH_NUMBER },
  { label: 'the floor in copy', pattern: lengthInCopy(FLOOR_COUNT) },
  {
    label: 'the floor in a constant',
    pattern: new RegExp(String.raw`\b\w*(?:min|len|floor|password)\w*\s*(?::\s*[\w.]+\s*)?=\s*${PASSWORD_MIN_LENGTH}\b`, 'i'),
  },
  {
    label: 'the floor compared against a length',
    pattern: new RegExp(String.raw`\.length\s*[<>]=?\s*${PASSWORD_MIN_LENGTH}\b|\b${PASSWORD_MIN_LENGTH}\s*[<>]=?\s*[\w.]*\.length\b`),
  },
]
/** The pages that state or enforce the rule, and the meter that scores against it. */
const RULE_SITES = [
  'app/reset-password/page.tsx',
  'features/auth/components/RegisterForm.tsx',
  'features/auth/components/PasswordField.tsx',
  'features/settings/components/ChangePasswordForm.tsx',
]
/** Forms whose new-password inputs check the floor in code instead of through `minLength`. */
const CODE_CHECKED: Record<string, string> = {
  'features/settings/components/ChangePasswordForm.tsx': 'shows its own sentence for a short password before the request',
}

/** Scripts (TS or JS, JSX or not) and prose (Markdown, MDX) are read. */
const READ = /\.(?:[cm]?[jt]sx?|mdx?)$/
/** Every other extension under SOURCE_ROOTS, with why it can hold no password rule. */
const NOT_READ: Record<string, string> = {
  '.json': 'data (the analysis demo), never copy, a field or a check',
  '.css': 'styles, never copy, a field or a check',
}
const isScript = (rel: string) => /\.[cm]?[jt]sx?$/.test(rel)
const scriptKind = (rel: string) =>
  rel.endsWith('.tsx') ? ts.ScriptKind.TSX : rel.endsWith('.jsx') ? ts.ScriptKind.JSX : /\.[cm]?js$/.test(rel) ? ts.ScriptKind.JS : ts.ScriptKind.TS
const parse = (source: string, rel: string) => ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, scriptKind(rel))
/** Each source parsed once for the field scans, which read every file more than once (FORWARDERS' fixed point). */
const PARSED = new Map<string, { source: string; sf: ts.SourceFile }>()
const parsed = (source: string, rel: string) => {
  const hit = PARSED.get(rel)
  if (hit?.source === source) return hit.sf
  const sf = parse(source, rel)
  PARSED.set(rel, { source, sf })
  return sf
}
const lineOf = (sf: ts.SourceFile, node: ts.Node) => sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
const squash = (text: string) => text.replace(/\s+/g, ' ').trim()

function walk(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === 'node_modules' ? [] : walk(full)
    return [full]
  })
}

function handTyped(source: string, rel: string): string[] {
  const patterns = HANDLES_PASSWORD.test(source) ? HAND_TYPED : /password/i.test(source) ? FLOOR_TYPED : []
  const offenders: string[] = []
  source.split('\n').forEach((line, index) => {
    for (const { label, pattern } of patterns) {
      if (pattern.test(line)) offenders.push(`${rel}:${index + 1} (${label}): ${line.trim()}`)
    }
  })
  return offenders
}

/** In a file that handles a password, the floor typed as a number anywhere in its code, whatever it is named. */
function floorNumbers(source: string, rel: string): string[] {
  if (!isScript(rel) || !HANDLES_PASSWORD.test(source)) return []
  const sf = parse(source, rel)
  const out: string[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isNumericLiteral(node) && Number(node.text.replace(/_/g, '')) === PASSWORD_MIN_LENGTH) {
      out.push(`${rel}:${lineOf(sf, node)} (the floor as a number): ${node.parent.getText(sf).trim()}`)
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

const unwrap = (node: ts.Expression): ts.Expression =>
  ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isSatisfiesExpression(node) || ts.isTypeAssertionExpression(node)
    ? unwrap(node.expression)
    : node
const COMPARISONS = new Set([ts.SyntaxKind.LessThanToken, ts.SyntaxKind.LessThanEqualsToken, ts.SyntaxKind.GreaterThanToken, ts.SyntaxKind.GreaterThanEqualsToken])

/**
 * In a script, the lengths a line scan cannot see: copy composed across JSX text and its expressions (a
 * number in braces, a sentence split over lines), a `.length` compared against a numeric constant of any
 * name, a `.min(n)` call, a `.{n,}` pattern and a `minLength` held in a constant, each read in every value
 * its parts can render. Where the file handles a password, any count; where it only mentions one, the floor.
 */
function codeForms(source: string, rel: string): string[] {
  const handles = HANDLES_PASSWORD.test(source)
  if (!isScript(rel) || (!handles && !/password/i.test(source))) return []
  const counts = (n: number | undefined) => n !== undefined && (handles ? n >= 1 : n === PASSWORD_MIN_LENGTH)
  const copy = lengthInCopy(handles ? ANY_COUNT : FLOOR_COUNT)
  const sf = parse(source, rel)
  const out: string[] = []
  // The file's numeric constants, whatever their names: `const FLOOR = 12`, `const n = 12 as const`.
  const constants = new Map<string, number>()
  const collect = (node: ts.Node): void => {
    if (ts.isVariableDeclarationList(node) && node.flags & ts.NodeFlags.Const) {
      for (const decl of node.declarations) {
        const init = decl.initializer && unwrap(decl.initializer)
        if (ts.isIdentifier(decl.name) && init && ts.isNumericLiteral(init)) constants.set(decl.name.text, Number(init.text.replace(/_/g, '')))
      }
    }
    ts.forEachChild(node, collect)
  }
  collect(sf)
  const valueOf = (node: ts.Expression): number | undefined => {
    const inner = unwrap(node)
    if (ts.isNumericLiteral(inner)) return Number(inner.text.replace(/_/g, ''))
    return ts.isIdentifier(inner) ? constants.get(inner.text) : undefined
  }
  const isLength = (node: ts.Expression) => {
    const inner = unwrap(node)
    return ts.isPropertyAccessExpression(inner) && inner.name.text === 'length'
  }
  // What a piece of copy renders as text: a literal's own, a template's parts with what each slot holds, a `+` chain
  // joined; a number from a literal or a numeric constant of any name, and any other value a gap no count spans.
  const composed = (node: ts.Expression): string => {
    const inner = unwrap(node)
    if (ts.isStringLiteral(inner) || ts.isNoSubstitutionTemplateLiteral(inner)) return inner.text
    if (ts.isTemplateExpression(inner)) return inner.head.text + inner.templateSpans.map((span) => composed(span.expression) + span.literal.text).join('')
    if (isPlus(inner)) return composed(inner.left) + composed(inner.right)
    return String(valueOf(inner) ?? ' … ')
  }
  /** Whether a `+` chain carries a string: an operand, through nested chains and parentheses, that is a string or a template. */
  const carriesText = (node: ts.Expression): boolean => {
    const inner = unwrap(node)
    return isPlus(inner) ? carriesText(inner.left) || carriesText(inner.right) : ts.isStringLiteral(inner) || ts.isNoSubstitutionTemplateLiteral(inner) || ts.isTemplateExpression(inner)
  }
  /** Whether a template or a `+` chain is read as part of a larger one: a chain's operand, a slot, or a JSX child an element composes. */
  const composedByParent = (node: ts.Node): boolean => {
    let parent = node.parent
    while (parent && (ts.isParenthesizedExpression(parent) || ts.isAsExpression(parent) || ts.isSatisfiesExpression(parent))) parent = parent.parent
    return !!parent && (isPlus(parent) || ts.isTemplateSpan(parent) || (ts.isJsxExpression(parent) && (ts.isJsxElement(parent.parent) || ts.isJsxFragment(parent.parent))))
  }
  // What an element renders as text: its text, each expression composed as copy, its children's text. Read again with
  // each template or `+` chain in braces a gap (`composing` false), any other value as before, so composing never hides
  // a count that reading states (a slot's text run into the count: `{`Use at ${'least'}`}8 characters`).
  const rendered = (node: ts.Node, composing = true): string => {
    if (ts.isJsxText(node)) return node.text
    if (ts.isJsxExpression(node)) {
      const inner = node.expression && unwrap(node.expression)
      if (!inner) return ''
      return composing || ts.isStringLiteral(inner) || ts.isNoSubstitutionTemplateLiteral(inner) ? composed(inner) : String(valueOf(inner) ?? ' … ')
    }
    return ts.isJsxElement(node) || ts.isJsxFragment(node) ? node.children.map((child) => rendered(child, composing)).join('') : ' '
  }
  // Every value a slot, an operand or a braced expression can render, read beside the readings above (which stay): a
  // ternary's either branch, `&&`, `||` and `??`, a const of any kind, an object's entry, a same-file function's return
  // (the field reader's evaluator, a value it cannot know a gap). One branching value varies at a time, the others gaps,
  // so the readings grow with the values and not with their product; a value with more readings than the evaluator
  // takes fails loudly.
  const evaluate = evaluator(sf, bindingResolver(sf), true)
  const ALTERNATIVES = new Map<ts.Node, Alternative[]>()
  const alternatives = (node: ts.Expression): Alternative[] => {
    let values = ALTERNATIVES.get(node)
    if (!values) {
      ALTERNATIVES.set(node, (values = evaluate.of(node)))
      const capped = values.find((value) => value.kind === 'unreadable' && value.cap)
      if (capped?.kind === 'unreadable') out.push(`${rel}:${lineOf(sf, node)} (a value with more readings than this reader takes): ${capped.form}`)
      const loud = values.find((value) => value.kind === 'unreadable' && value.loud)
      if (loud?.kind === 'unreadable') out.push(`${rel}:${lineOf(sf, node)} (a value this reader cannot read): ${loud.form}`)
    }
    return values
  }
  const texts = (node: ts.Expression, jsx: boolean) => [...new Set(alternatives(node).map((value) => textOf(value, jsx)))]
  const numbers = (node: ts.Expression) => texts(node, false).filter((text) => /^\d+$/.test(text)).map(Number)
  /** A piece of copy as its parts, each every text it can render: a template's or a chain's literal parts and values, and an
      element's text, braced expressions (a template or a chain in braces by its own parts) and children. */
  const parts = (node: ts.Node, jsx: boolean): string[][] => {
    if (ts.isJsxText(node)) return [[node.text]]
    if (ts.isJsxElement(node) || ts.isJsxFragment(node)) return node.children.flatMap((child) => parts(child, true))
    if (ts.isJsxExpression(node)) return node.expression ? parts(node.expression, true) : []
    if (ts.isJsxSelfClosingElement(node) || !ts.isExpression(node)) return [[' ']]
    const inner = unwrap(node)
    if (ts.isTemplateExpression(inner)) return [[inner.head.text], ...inner.templateSpans.flatMap((span) => [...parts(span.expression, false), [span.literal.text]])]
    if (isPlus(inner)) return [...parts(inner.left, false), ...parts(inner.right, false)]
    return [texts(inner, jsx)]
  }
  const READINGS = new Map<ts.Node, string[]>()
  /** A piece's readings: every branching part a gap, then each branching part's every text in turn, the others gaps. */
  const readings = (node: ts.Node): string[] => {
    let hit = READINGS.get(node)
    if (!hit) {
      const all = parts(node, false)
      const base = all.map((options) => (options.length === 1 ? options[0] : ' … '))
      const varied = all.flatMap((options, i) => (options.length > 1 ? options.map((text) => [...base.slice(0, i), text, ...base.slice(i + 1)].join('')) : []))
      READINGS.set(node, (hit = [base.join(''), ...varied].map(squash)))
    }
    return hit
  }
  const STATED = new Map<ts.Node, string | undefined>()
  /** The text in which an element states a count, composed, with its templates as gaps, or in any reading; undefined
      where none does. */
  const stated = (node: ts.Node): string | undefined => {
    if (!ts.isJsxElement(node) && !ts.isJsxFragment(node)) return undefined
    if (!STATED.has(node)) STATED.set(node, [rendered(node), rendered(node, false)].map(squash).concat(readings(node)).find((text) => copy.test(text)))
    return STATED.get(node)
  }
  const patternIn = (text: string) => {
    const min = text.match(/(?<!\\)\.\{(\d+),\d*\}/)
    return !!min && counts(Number(min[1]))
  }
  /** Whether a string or a pattern literal inside a node holds a counting pattern by itself. */
  const literalPattern = (node: ts.Node): boolean =>
    ((ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isRegularExpressionLiteral(node)) && patternIn(node.text)) ||
    (ts.forEachChild(node, (child) => literalPattern(child) || undefined) ?? false)
  const statesCount = (node: ts.Node) => stated(node) !== undefined
  const visit = (node: ts.Node): void => {
    // The innermost element whose text states a count, so one sentence is one finding.
    if (statesCount(node) && !(node as ts.JsxElement | ts.JsxFragment).children.some(statesCount)) {
      out.push(`${rel}:${lineOf(sf, node)} (copy composed across JSX): ${stated(node)}`)
    }
    // A template or a `+` chain is copy too, read at its outermost node; a string on one line is the line scan's.
    const piece = ts.isTemplateExpression(node) || (ts.isNoSubstitutionTemplateLiteral(node) && node.text.includes('\n')) || (isPlus(node) && carriesText(node))
    if (piece && !composedByParent(node)) {
      const text = [squash(composed(node as ts.Expression)), ...readings(node)].find((reading) => copy.test(reading))
      if (text !== undefined) out.push(`${rel}:${lineOf(sf, node)} (copy composed in a template or a + chain): ${text}`)
      // A pattern composed in a template or a chain (`new RegExp(`^.{${MIN},}$`)`), where no literal in it holds one alone.
      const pattern = literalPattern(node) ? undefined : readings(node).find(patternIn)
      if (pattern !== undefined) out.push(`${rel}:${lineOf(sf, node)} (a pattern minimum): ${pattern}`)
    }
    if (ts.isBinaryExpression(node) && COMPARISONS.has(node.operatorToken.kind)) {
      const other = isLength(node.left) ? node.right : isLength(node.right) ? node.left : undefined
      if (other && (counts(valueOf(other)) || numbers(other).some(counts))) out.push(`${rel}:${lineOf(sf, node)} (a length compared against a number): ${squash(node.getText(sf))}`)
    }
    if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) && node.expression.name.text === 'min') {
      const receiver = node.expression.expression
      const math = ts.isIdentifier(receiver) && receiver.text === 'Math'
      if (!math && node.arguments.length > 0 && (counts(valueOf(node.arguments[0])) || numbers(node.arguments[0]).some(counts))) {
        out.push(`${rel}:${lineOf(sf, node)} (a minimum call): ${squash(node.getText(sf))}`)
      }
    }
    if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isRegularExpressionLiteral(node)) {
      if (patternIn(node.text)) out.push(`${rel}:${lineOf(sf, node)} (a pattern minimum): ${node.getText(sf)}`)
    }
    // A minLength the line scan cannot see (a literal is its), in any value the evaluator reads: `minLength={GAP}`.
    if ((ts.isJsxAttribute(node) || ts.isPropertyAssignment(node)) && /^min_?length$/i.test(node.name.getText(sf))) {
      const value = ts.isPropertyAssignment(node) ? node.initializer : node.initializer && ts.isJsxExpression(node.initializer) ? node.initializer.expression : undefined
      const inner = value && unwrap(value)
      if (inner && !ts.isNumericLiteral(inner) && !ts.isStringLiteralLike(inner) && numbers(inner).some(counts)) {
        out.push(`${rel}:${lineOf(sf, node)} (a minLength held in a value): ${squash(node.getText(sf))}`)
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return [...new Set(out)]
}

/** A password field: where it renders, what its autoComplete is (named in every value it can take, or not), whether one
    of those values is new-password (the floor applies), and each prop it forwards its autoComplete through, with the
    component that forwards it under the name its callers render it by. */
type Field = {
  line: number
  tag: string
  id: string
  kind: 'new' | 'current' | 'forwarded' | 'unnamed' | 'unreadable'
  isNew: boolean
  floor: boolean
  forwards: Array<{ component: string; prop: string }>
  renders: string[]
  unreadable?: string
}
/** The components each component's props are handed by the callers that render it, keyed `Component#prop`
    (`<Page Field={Secret} />` hands Page's `Field` what Secret names). */
type Passes = ReadonlyMap<string, readonly string[]>
const NO_PASSES: Passes = new Map()
/** The components that forward a password field's autoComplete, each with the props it forwards it through, and the
    components the callers in the same sources hand as props. */
type Forwarders = ReadonlyMap<string, ReadonlySet<string>> & { readonly passes?: Passes }

/** Whether a value carries a string that passes `test`: a literal, braced or not, or one inside an expression. */
function carries(value: ts.Node | undefined, test: (text: string) => boolean): boolean {
  if (!value) return false
  const text =
    ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value) || ts.isTemplateHead(value) || ts.isTemplateMiddle(value) || ts.isTemplateTail(value)
      ? value.text
      : undefined
  if (text !== undefined && test(text)) return true
  return ts.forEachChild(value, (child) => carries(child, test) || undefined) ?? false
}
const namesNew = (text: string) => /\bnew-password\b/i.test(text)
const namesCurrent = (text: string) => /\bcurrent-password\b/i.test(text)

/** One value an expression can render: its text; nothing (undefined, null or false); a prop the function it renders in
    forwards from its caller; or a form this reader cannot evaluate, which fails loudly (one with more values than it
    takes, `cap`, and one read through a container or a binding that can change or nested past what it follows, `loud`,
    fail even where the length reader reads a gap). */
type Alternative =
  | { kind: 'text'; text: string }
  | { kind: 'nothing'; value: 'undefined' | 'null' | 'false' }
  | { kind: 'forwarded'; prop: string; from: ts.SignatureDeclaration }
  | { kind: 'unreadable'; form: string; cap?: true; loud?: true }
type Resolve = (ref: ts.Identifier) => Binding | undefined
/** A same-file function's parameters, each bound to the argument a call passes it, read where the call is. */
type Env = ReadonlyMap<ts.Node, { value: ts.Expression | undefined; env: Env }>
/** What an expression holds: a same-file object or array literal (with where its entries are read), or a function's props;
    a rest of an object or of the props without the keys taken out beside it; or one this reader cannot follow, through
    which every value read is unreadable, loudly: one of those that can change after this reader's source for it (a
    container written or handed on after its initializer, a parameter assigned, props written), or one nested past what
    it follows. */
type Holder =
  | { object: ts.ObjectLiteralExpression; env: Env; without?: readonly string[] }
  | { array: ts.ArrayLiteralExpression; env: Env }
  | { props: ts.ParameterDeclaration; without?: readonly string[] }
  | { unfollowed: ts.Node; why: string }
/** One step a pattern takes into what it destructures: an object's key, an array's index, or an object's rest. */
type Step = { key: string } | { index: number } | { rest: string[] }
/** Where a destructured name sits: its pattern's root (a declaration or a parameter) and each step from it, with the
    default each step renders where its entry is undefined. Undefined for a computed key or an array's rest, which no
    reader here follows. */
function bindingSteps(decl: ts.BindingElement): { root: ts.VariableDeclaration | ts.ParameterDeclaration; steps: Array<{ step: Step; fallback?: ts.Expression }> } | undefined {
  const steps: Array<{ step: Step; fallback?: ts.Expression }> = []
  let node: ts.Node = decl
  while (ts.isBindingElement(node)) {
    const element: ts.BindingElement = node
    const pattern = element.parent
    if (ts.isArrayBindingPattern(pattern)) {
      if (element.dotDotDotToken) return undefined
      steps.unshift({ step: { index: pattern.elements.indexOf(element) }, fallback: element.initializer })
    } else {
      const key = element.propertyName ?? element.name
      const taken = pattern.elements.filter((other) => other !== element).map((other) => other.propertyName ?? other.name)
      if (ts.isComputedPropertyName(key) || (element.dotDotDotToken && taken.some((other) => ts.isComputedPropertyName(other)))) return undefined
      steps.unshift({ step: element.dotDotDotToken ? { rest: taken.map(keyText) } : { key: keyText(key) }, fallback: element.initializer })
    }
    node = pattern.parent
  }
  return ts.isVariableDeclaration(node) || ts.isParameter(node) ? { root: node, steps } : undefined
}
/** Why each container (or props parameter) the evaluator reaches can change after this reader's source for it, cached. */
const CHANGES = new WeakMap<ts.Node, string | undefined>()
/** The most values a template or a `+` chain is read in; one with more fails loudly rather than be read in part. */
const MAX_ALTERNATIVES = 64
const UNDEFINED: Alternative = { kind: 'nothing', value: 'undefined' }
const FALSE: Alternative = { kind: 'nothing', value: 'false' }
const BOOLEANS: Alternative[] = [{ kind: 'text', text: 'true' }, FALSE]
const COMPARING = new Set([
  ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken,
  ts.SyntaxKind.LessThanToken, ts.SyntaxKind.LessThanEqualsToken, ts.SyntaxKind.GreaterThanToken, ts.SyntaxKind.GreaterThanEqualsToken,
  ts.SyntaxKind.InstanceOfKeyword, ts.SyntaxKind.InKeyword,
])
const isPlus = (node: ts.Node): node is ts.BinaryExpression => ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken
const bareExpression = (node: ts.Expression): ts.Expression => {
  let inner = node
  while (ts.isParenthesizedExpression(inner) || ts.isAsExpression(inner) || ts.isSatisfiesExpression(inner) || ts.isNonNullExpression(inner) || ts.isTypeAssertionExpression(inner)) inner = inner.expression
  return inner
}
/** A property's key as text: `autoComplete`, `'auto-complete'`, `0`. */
const keyText = (name: ts.Node) => name.getText().replace(/^["'`]|["'`]$/g, '')
/** What a value renders as: its text; nothing as its own name in a template, and as nothing at all in JSX; a value this
    reader cannot know, a gap. */
const textOf = (value: Alternative, jsx = false) => (value.kind === 'text' ? value.text : value.kind === 'nothing' ? (jsx ? '' : value.value) : ' … ')
const isUndefined = (value: Alternative) => value.kind === 'nothing' && value.value === 'undefined'
/** Truthiness as `&&`, `||` and `??` take it: "0" may be the number 0, and a value this reader cannot know may be either. */
const mayBeFalsy = (value: Alternative) => value.kind !== 'text' || value.text === '' || value.text === '0'
const mayBeTruthy = (value: Alternative) => value.kind !== 'nothing' && !(value.kind === 'text' && value.text === '')
const isNullish = (value: Alternative) => value.kind === 'nothing' && value.value !== 'false'
const mayBeNullish = (value: Alternative) => isNullish(value) || value.kind === 'forwarded' || value.kind === 'unreadable'

/** Whether a `break` can leave a switch: one not inside a loop or a switch within it, or any labelled one. */
function breaksOut(statement: ts.SwitchStatement): boolean {
  const within = (node: ts.Node, nested: boolean): boolean => {
    if (ts.isFunctionLike(node)) return false
    if (ts.isBreakStatement(node)) return !nested || !!node.label
    const inner = nested || ts.isIterationStatement(node, false) || (ts.isSwitchStatement(node) && node !== statement)
    return ts.forEachChild(node, (child) => within(child, inner) || undefined) ?? false
  }
  return statement.caseBlock.clauses.some((clause) => clause.statements.some((child) => within(child, false)))
}
/** Whether a statement can finish and let the code after it run. A return, a throw, a break or a continue cannot (a loop,
    a switch or a label a break leaves is read as able to end); a block cannot once one of its statements cannot; an if
    with an else cannot when neither branch can; a try cannot when its finally cannot, or when neither its block nor its
    catch can; a switch with a default cannot when no break leaves it and its last clause cannot. Anything else, a loop
    among them, can: reading too many ends only adds an undefined. */
function canEnd(statement: ts.Statement): boolean {
  if (ts.isReturnStatement(statement) || ts.isThrowStatement(statement) || ts.isBreakStatement(statement) || ts.isContinueStatement(statement)) return false
  if (ts.isBlock(statement)) return statement.statements.every(canEnd)
  if (ts.isIfStatement(statement)) return !statement.elseStatement || canEnd(statement.thenStatement) || canEnd(statement.elseStatement)
  if (ts.isTryStatement(statement)) {
    return (!statement.finallyBlock || canEnd(statement.finallyBlock)) && (canEnd(statement.tryBlock) || (!!statement.catchClause && canEnd(statement.catchClause.block)))
  }
  if (ts.isSwitchStatement(statement)) {
    const clauses = statement.caseBlock.clauses
    const last = clauses[clauses.length - 1]
    return !clauses.some(ts.isDefaultClause) || breaksOut(statement) || !last || last.statements.every(canEnd)
  }
  return true
}
/** What a same-file function hands back: its concise body, or each `return` of its own, with undefined for a bare `return`
    and for a body that can end without one. */
function returnsOf(fn: ts.SignatureDeclaration): Array<ts.Expression | undefined> {
  const body = (fn as ts.FunctionLikeDeclarationBase).body
  if (!body) return [undefined]
  if (!ts.isBlock(body)) return [body]
  const out: Array<ts.Expression | undefined> = []
  const walk = (node: ts.Node): void => {
    if (node !== body && ts.isFunctionLike(node)) return
    if (ts.isReturnStatement(node)) out.push(node.expression)
    ts.forEachChild(node, walk)
  }
  walk(body)
  if (canEnd(body)) out.push(undefined)
  return out
}
/** A function written in place: an arrow or a function expression (called where it stands, or `useMemo`'s factory). */
const functionIn = (node: ts.Node | undefined) => {
  const inner = node && bareExpression(node as ts.Expression)
  return inner && (ts.isArrowFunction(inner) || ts.isFunctionExpression(inner)) ? inner : undefined
}
/** The same-file function a name binds to: a declaration, or a const holding an arrow or a function expression. */
function functionOf(binding: Binding | undefined): ts.SignatureDeclaration | undefined {
  if (!binding) return undefined
  if (ts.isFunctionDeclaration(binding.decl)) return binding.decl
  return ts.isVariableDeclaration(binding.decl) && binding.decl.parent.flags & ts.NodeFlags.Const ? functionIn(binding.init) : undefined
}

/**
 * Every value an expression can render, read in its file: a literal; a template or a `+` chain, each part's every value;
 * each branch of a condition, nested; `&&`, `||` and `??` as the language takes them; a same-file const; a same-file
 * object's entry, or every entry for a key the reader cannot name (`MODES[kind]`); a same-file function's every return
 * (an arrow or a function called in place, and `useMemo`'s factory, among them), its parameters bound to the call's
 * arguments and their defaults; a name destructured at any depth, out of an object or an array (a key, renamed or not, an
 * index, a rest without the keys taken out beside it, each step's default); and a prop the function it renders in
 * forwards from its caller (a key of its first parameter, the props: destructured, `props.x`, a const that takes it),
 * with the default it renders when none is passed. A container reached through a binding or an entry is read only while
 * nothing can change it after its initializer (astBindings' containerEscape), a parameter only while its function does
 * not assign it, and props only while the component does not write them. Anything else is unreadable: a name from
 * another module, a `let`, a call or an object this reader cannot follow, a class's `this.props`, a value destructured
 * from inside a prop, a computed key or an array's rest destructured, a forwarded value composed into text, more than
 * MAX_ALTERNATIVES values, a value read through what can change, and one nested past the 24 steps this reader follows (a
 * cycle of consts). With `gaps` (the length reader), a value it cannot know composes into text as a gap instead of making
 * the whole unreadable, except the last three, which stay loud.
 */
function evaluator(sf: ts.SourceFile, resolve: Resolve, gaps = false) {
  const show = (node: ts.Node) => squash(node.getText(sf))
  const unreadable = (node: ts.Node, why: string): Alternative[] => [{ kind: 'unreadable', form: `${show(node)} (${why})` }]
  const loudly = (node: ts.Node, why: string): Alternative[] => [{ kind: 'unreadable', form: `${show(node)} (${why})`, loud: true }]
  const references = bindingReferences(sf, resolve)
  /** Whether a parameter, or a name destructured from one, is assigned in its function (a const cannot be). */
  const reassigned = (decl: Binding['decl']) => references(decl).some((ref) => writtenAs(ref) !== undefined)
  const REASSIGNED = 'a parameter assigned in its function'
  /** Past the 24 steps this reader follows (a cycle of consts): loud, like a value read through what can change. */
  const NESTED = 'nested past what this reader follows'
  /** Why a container this reader reaches through a binding or an entry can change after its initializer, or undefined. */
  const changes = (literal: ts.ObjectLiteralExpression | ts.ArrayLiteralExpression): string | undefined => {
    if (!CHANGES.has(literal)) {
      const escaped = containerEscape(literal, sf, resolve)
      CHANGES.set(literal, escaped ? `a container that can change after its initializer: ${escaped.how}, line ${lineOf(sf, escaped.at)}` : undefined)
    }
    return CHANGES.get(literal)
  }
  /** Why a component's props can change in it (a use of them, or of a rest taken out of them, that is not a read), or undefined. */
  const propsChange = (param: ts.ParameterDeclaration): string | undefined => {
    if (!CHANGES.has(param)) {
      const holders: Binding['decl'][] = ts.isIdentifier(param.name) ? [param] : ts.isObjectBindingPattern(param.name) ? param.name.elements.filter((e) => e.dotDotDotToken) : []
      const escaped = holders.map((decl) => bindingEscape(decl, sf, resolve)).find((found) => found !== undefined)
      CHANGES.set(param, escaped ? `props that can change in the component: ${escaped.how}, line ${lineOf(sf, escaped.at)}` : undefined)
    }
    return CHANGES.get(param)
  }
  /** `Object.freeze(x)`: it hands back what it is handed, and writes nothing. */
  const freezes = (call: ts.CallExpression) => {
    const callee = bareExpression(call.expression)
    return ts.isPropertyAccessExpression(callee) && ts.isIdentifier(callee.expression) && callee.expression.text === 'Object' && !resolve(callee.expression) &&
      callee.name.text === 'freeze' && call.arguments.length === 1 && !ts.isSpreadElement(call.arguments[0])
  }
  /** A prop a function forwards from its caller: a key of its first parameter, which holds the props. */
  const forwarded = (param: ts.ParameterDeclaration, prop: string, at: ts.Node): Alternative[] =>
    param.parent.parameters[0] === param ? [{ kind: 'forwarded', prop, from: param.parent }] : unreadable(at, 'a parameter after the first, which holds no props')
  const paramHolder = (param: ts.ParameterDeclaration, env: Env, depth: number): Holder | undefined => {
    if (reassigned(param)) return { unfollowed: param, why: REASSIGNED }
    const bound = env.get(param)
    if (bound) return holderOf(bound.value ?? param.initializer, bound.value ? bound.env : env, depth + 1, true)
    const why = propsChange(param)
    return why ? { unfollowed: param, why } : { props: param }
  }
  /** What an expression holds. A container is read where it is written in place; reached through a binding or an entry
      (`bound`), only while nothing can change it after its initializer. */
  const holderOf = (expr: ts.Expression | undefined, env: Env, depth = 0, bound = false): Holder | undefined => {
    const inner = expr && bareExpression(expr)
    if (!inner) return undefined
    if (depth > 24) return { unfollowed: inner, why: NESTED }
    if (ts.isObjectLiteralExpression(inner) || ts.isArrayLiteralExpression(inner)) {
      const why = bound ? changes(inner) : undefined
      return why ? { unfollowed: inner, why } : ts.isObjectLiteralExpression(inner) ? { object: inner, env } : { array: inner, env }
    }
    if (ts.isCallExpression(inner) && freezes(inner)) return holderOf(inner.arguments[0] as ts.Expression, env, depth + 1, bound)
    // A member is the holder its entry holds (`KIT.inputs`, `KIT['inputs']`).
    if (ts.isPropertyAccessExpression(inner)) return holderAt(holderOf(inner.expression, env, depth + 1), inner.name.text, undefined, env, depth)
    if (ts.isElementAccessExpression(inner) && (ts.isStringLiteralLike(inner.argumentExpression) || ts.isNumericLiteral(inner.argumentExpression))) {
      return holderAt(holderOf(inner.expression, env, depth + 1), inner.argumentExpression.text, undefined, env, depth)
    }
    const decl = ts.isIdentifier(inner) ? resolve(inner)?.decl : undefined
    if (decl && ts.isParameter(decl)) return paramHolder(decl, env, depth)
    if (decl && ts.isBindingElement(decl)) {
      const path = bindingSteps(decl)
      if (path && ts.isParameter(path.root) && reassigned(decl)) return { unfollowed: decl, why: REASSIGNED }
      return path && path.steps.reduce<Holder | undefined>((holder, step) => stepInto(holder, step, env, depth), rootHolder(path.root, env, depth))
    }
    return decl && ts.isVariableDeclaration(decl) && decl.parent.flags & ts.NodeFlags.Const ? holderOf(decl.initializer, env, depth + 1, true) : undefined
  }
  /** An entry's node: an object's by its key, an array's by its index; 'missing' where it has none, undefined where this
      reader cannot tell (a spread before it, a computed key, a method). */
  const nodeAt = (holder: Exclude<Holder, { props: ts.ParameterDeclaration } | { unfollowed: ts.Node }>, key: string): { node: ts.Expression; env: Env } | 'missing' | undefined => {
    if ('array' in holder) {
      const index = Number(key)
      const elements = holder.array.elements
      if (!Number.isInteger(index) || index < 0 || elements.slice(0, index + 1).some(ts.isSpreadElement)) return undefined
      const element = elements[index]
      return !element || ts.isOmittedExpression(element) ? 'missing' : { node: element, env: holder.env }
    }
    if (holder.without?.includes(key)) return 'missing'
    if (holder.object.properties.some((p) => ts.isSpreadAssignment(p) || (p.name && ts.isComputedPropertyName(p.name)))) return undefined
    const entry = holder.object.properties.find((p) => p.name && keyText(p.name) === key)
    if (!entry) return 'missing'
    if (ts.isPropertyAssignment(entry)) return { node: entry.initializer, env: holder.env }
    return ts.isShorthandPropertyAssignment(entry) ? { node: entry.name, env: holder.env } : undefined
  }
  /** The holder an entry holds, or its step's default where the entry is missing; none past the props. */
  const holderAt = (holder: Holder | undefined, key: string, fallback: ts.Expression | undefined, env: Env, depth: number): Holder | undefined => {
    if (!holder || 'props' in holder) return undefined
    if ('unfollowed' in holder) return holder
    const found = nodeAt(holder, key)
    if (found === 'missing') return fallback ? holderOf(fallback, env, depth + 1, true) : undefined
    return found ? holderOf(found.node, found.env, depth + 1, true) : undefined
  }
  /** What a pattern's root holds: a parameter's props (or the argument a call binds), or a const's initializer. */
  const rootHolder = (root: ts.VariableDeclaration | ts.ParameterDeclaration, env: Env, depth: number): Holder | undefined =>
    ts.isParameter(root) ? paramHolder(root, env, depth) : root.parent.flags & ts.NodeFlags.Const ? holderOf(root.initializer, env, depth + 1, true) : undefined
  /** One step into a holder: an entry's holder, or a rest of an object or of the props without the keys taken. */
  const stepInto = (holder: Holder | undefined, { step, fallback }: { step: Step; fallback?: ts.Expression }, env: Env, depth: number): Holder | undefined => {
    if (holder && 'unfollowed' in holder) return holder
    if ('rest' in step) return holder && !('array' in holder) ? { ...holder, without: [...(holder.without ?? []), ...step.rest] } : undefined
    return holderAt(holder, 'key' in step ? step.key : String(step.index), fallback, env, depth)
  }
  /** A holder's entry by its key, its every value (undefined where it has none), or the prop where it holds the props. */
  const entryIn = (holder: Holder | undefined, key: string, at: ts.Node, depth: number): Alternative[] => {
    if (!holder) return unreadable(at, 'an object this reader cannot follow')
    if ('unfollowed' in holder) return loudly(at, holder.why)
    if ('props' in holder) return holder.without?.includes(key) ? [UNDEFINED] : forwarded(holder.props, key, at)
    const found = nodeAt(holder, key)
    if (found === 'missing') return [UNDEFINED]
    return found ? of(found.node, found.env, depth) : unreadable(at, 'an entry this reader cannot read: a spread before it, a computed key or a method')
  }
  /** Every entry a holder holds, for a key the reader cannot name. */
  const everyEntryIn = (holder: Holder | undefined, at: ts.Node, depth: number): Alternative[] => {
    if (holder && 'unfollowed' in holder) return loudly(at, holder.why)
    if (!holder || 'props' in holder) return unreadable(at, 'an object this reader cannot follow, by a key it cannot name')
    if ('array' in holder) {
      return holder.array.elements.flatMap((element) =>
        ts.isSpreadElement(element) ? unreadable(element, 'a spread this reader cannot follow') : ts.isOmittedExpression(element) ? [UNDEFINED] : of(element, holder.env, depth),
      )
    }
    return holder.object.properties
      .filter((p) => !(p.name && !ts.isComputedPropertyName(p.name) && holder.without?.includes(keyText(p.name))))
      .flatMap((p) =>
        ts.isPropertyAssignment(p) ? of(p.initializer, holder.env, depth) : ts.isShorthandPropertyAssignment(p) ? of(p.name, holder.env, depth) : unreadable(p, 'an entry this reader cannot read'),
      )
  }
  /** A value with the default a parameter or a destructured key renders where it may be undefined. */
  const withDefault = (values: Alternative[], fallback: ts.Expression | undefined, env: Env, depth: number) =>
    fallback && values.some((value) => isUndefined(value) || value.kind === 'forwarded' || value.kind === 'unreadable')
      ? [...values.filter((value) => !isUndefined(value)), ...of(fallback, env, depth)]
      : values
  const named = (e: ts.Identifier, env: Env, depth: number): Alternative[] => {
    if (e.text === 'undefined') return [UNDEFINED]
    const decl = resolve(e)?.decl
    if (!decl) return unreadable(e, 'a name from another module, or a global')
    if (ts.isParameter(decl)) {
      if (reassigned(decl)) return loudly(e, REASSIGNED)
      const bound = env.get(decl)
      return bound ? withDefault(bound.value ? of(bound.value, bound.env, depth) : [UNDEFINED], decl.initializer, env, depth) : unreadable(e, 'a parameter that is not a prop')
    }
    if (ts.isBindingElement(decl)) {
      // A destructured name: its pattern's root taken apart step by step, at any depth, each step's default beside.
      const path = bindingSteps(decl)
      if (!path) return unreadable(e, "a computed key or an array's rest, destructured")
      if (ts.isVariableDeclaration(path.root) && !(path.root.parent.flags & ts.NodeFlags.Const)) return unreadable(e, 'a let or a var, which can change')
      if (ts.isParameter(path.root) && reassigned(decl)) return loudly(e, REASSIGNED)
      const last = path.steps[path.steps.length - 1]
      if ('rest' in last.step) return unreadable(e, 'a rest, destructured')
      let holder = rootHolder(path.root, env, depth)
      for (const step of path.steps.slice(0, -1)) {
        if (holder && 'props' in holder && !('rest' in step.step)) return unreadable(e, 'a value destructured from inside a prop')
        holder = stepInto(holder, step, env, depth)
      }
      return withDefault(entryIn(holder, 'key' in last.step ? last.step.key : String(last.step.index), e, depth), last.fallback, env, depth)
    }
    if (ts.isVariableDeclaration(decl)) return decl.parent.flags & ts.NodeFlags.Const && decl.initializer ? of(decl.initializer, env, depth) : unreadable(e, 'a let or a var, which can change')
    return unreadable(e, 'a function, not a value')
  }
  /** A template or a `+` chain: each part's every value, joined; `${x}` alone is x's own value. */
  const composed = (e: ts.TemplateExpression | ts.BinaryExpression, env: Env, depth: number): Alternative[] => {
    if (ts.isTemplateExpression(e) && !e.head.text && e.templateSpans.length === 1 && !e.templateSpans[0].literal.text) return of(e.templateSpans[0].expression, env, depth)
    const parts: Alternative[][] = ts.isTemplateExpression(e)
      ? [[{ kind: 'text', text: e.head.text }], ...e.templateSpans.flatMap((span): Alternative[][] => [of(span.expression, env, depth), [{ kind: 'text', text: span.literal.text }]])]
      : [of(e.left, env, depth), of(e.right, env, depth)]
    let texts = ['']
    for (const options of parts) {
      const blocked = options.find((o) => o.kind === 'unreadable' && (o.cap || o.loud || !gaps)) ?? (gaps ? undefined : options.find((o) => o.kind === 'forwarded'))
      if (blocked) return blocked.kind === 'unreadable' ? [blocked] : unreadable(e, 'a forwarded value composed into text')
      texts = [...new Set(texts.flatMap((head) => options.map((o) => head + textOf(o))))]
      if (texts.length > MAX_ALTERNATIVES) return [{ kind: 'unreadable', form: `${show(e)} (more than ${MAX_ALTERNATIVES} values)`, cap: true }]
    }
    return texts.map((text) => ({ kind: 'text', text }))
  }
  const called = (e: ts.CallExpression, env: Env, depth: number): Alternative[] => {
    const callee = bareExpression(e.expression)
    const binding = ts.isIdentifier(callee) ? resolve(callee) : undefined
    // `useMemo(() => value, deps)` renders its factory's value; an arrow or a function called where it stands, its own.
    const memo = !binding && /^(?:React\.)?useMemo$/.test(callee.getText(sf))
    const fn = memo ? functionIn(e.arguments[0]) : binding ? functionOf(binding) : functionIn(callee)
    if (!fn || e.arguments.some(ts.isSpreadElement)) return unreadable(e, 'a call this reader cannot follow')
    const scope = new Map(env)
    fn.parameters.forEach((parameter, index) => scope.set(parameter, { value: memo ? undefined : e.arguments[index], env }))
    return returnsOf(fn).flatMap((value) => (value ? of(value, scope, depth) : [UNDEFINED]))
  }
  const read = (node: ts.Node, env: Env, depth: number): Alternative[] => {
    if (ts.isJsxExpression(node)) return node.expression ? of(node.expression, env, depth) : [UNDEFINED]
    const e = bareExpression(node as ts.Expression)
    if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) return [{ kind: 'text', text: e.text }]
    if (ts.isNumericLiteral(e)) return [{ kind: 'text', text: String(Number(e.text.replace(/_/g, ''))) }]
    if (e.kind === ts.SyntaxKind.TrueKeyword) return [{ kind: 'text', text: 'true' }]
    if (e.kind === ts.SyntaxKind.FalseKeyword) return [FALSE]
    if (e.kind === ts.SyntaxKind.NullKeyword) return [{ kind: 'nothing', value: 'null' }]
    if (ts.isVoidExpression(e)) return [UNDEFINED]
    if (ts.isTemplateExpression(e) || isPlus(e)) return composed(e, env, depth)
    if (ts.isConditionalExpression(e)) return [...of(e.whenTrue, env, depth), ...of(e.whenFalse, env, depth)]
    if (ts.isPrefixUnaryExpression(e) && e.operator === ts.SyntaxKind.ExclamationToken) return BOOLEANS
    if (ts.isBinaryExpression(e)) {
      const op = e.operatorToken.kind
      if (COMPARING.has(op)) return BOOLEANS
      const left = of(e.left, env, depth)
      const right = () => of(e.right, env, depth)
      // `&&` renders a falsy left as itself and otherwise the right; `||` a truthy left and otherwise the right; `??` a
      // left that is neither null nor undefined and otherwise the right.
      if (op === ts.SyntaxKind.AmpersandAmpersandToken) return [...left.filter(mayBeFalsy).map((o) => (o.kind === 'text' || o.kind === 'nothing' ? o : FALSE)), ...(left.some(mayBeTruthy) ? right() : [])]
      if (op === ts.SyntaxKind.BarBarToken) return [...left.filter(mayBeTruthy), ...(left.some(mayBeFalsy) ? right() : [])]
      if (op === ts.SyntaxKind.QuestionQuestionToken) return [...left.filter((o) => !isNullish(o)), ...(left.some(mayBeNullish) ? right() : [])]
      return unreadable(e, 'an operator this reader does not evaluate')
    }
    if (ts.isIdentifier(e)) return named(e, env, depth)
    if (ts.isPropertyAccessExpression(e)) return entryIn(holderOf(e.expression, env, depth), e.name.text, e, depth)
    if (ts.isElementAccessExpression(e)) {
      const keys = of(e.argumentExpression, env, depth)
      return keys.every((key) => key.kind === 'text')
        ? keys.flatMap((key) => entryIn(holderOf(e.expression, env, depth), textOf(key), e, depth))
        : everyEntryIn(holderOf(e.expression, env, depth), e, depth)
    }
    if (ts.isCallExpression(e)) return called(e, env, depth)
    return unreadable(e, 'a form this reader does not evaluate')
  }
  const of = (node: ts.Node, env: Env, depth: number): Alternative[] => {
    if (depth > 24) return loudly(node, NESTED)
    const out = read(node, env, depth + 1)
    // An object read by every entry and holding none, or a function with no value, renders undefined.
    return out.length ? out : [UNDEFINED]
  }
  return {
    of: (node: ts.Node) => of(node, new Map(), 0),
    holderOf: (expr: ts.Expression) => holderOf(expr, new Map()),
    forwarded,
  }
}

/** Each file's binding resolver, made once. */
const RESOLVERS = new WeakMap<ts.SourceFile, Resolve>()
const resolverOf = (sf: ts.SourceFile) => {
  let resolve = RESOLVERS.get(sf)
  if (!resolve) RESOLVERS.set(sf, (resolve = bindingResolver(sf)))
  return resolve
}
/** A module by its path from the frontend root: one parsed here (a planted source among them), or a file on disk. */
const moduleAt = (rel: string): ts.SourceFile | undefined => {
  const hit = PARSED.get(rel)
  if (hit) return hit.sf
  const file = path.join(frontendDir, rel)
  return existsSync(file) && statSync(file).isFile() ? parsed(readFileSync(file, 'utf8'), rel) : undefined
}
/** The module a specifier names (`@/` is the frontend root); undefined for a package. */
const moduleRel = (importer: string, specifier: string): string | undefined => {
  const base = specifier.startsWith('@/') ? specifier.slice(2) : specifier.startsWith('.') ? path.posix.join(path.posix.dirname(importer), specifier) : undefined
  return base === undefined ? undefined : ['', '.tsx', '.ts', '.jsx', '.js', '/index.tsx', '/index.ts'].map((suffix) => base + suffix).find((rel) => isScript(rel) && !!moduleAt(rel))
}
/** A file's imports: each local name with the names its module declares the import under, and each namespace's module. */
const IMPORTS = new WeakMap<ts.SourceFile, { names: Map<string, string[]>; namespaces: Map<string, string> }>()
function importsOf(sf: ts.SourceFile) {
  let hit = IMPORTS.get(sf)
  if (hit) return hit
  hit = { names: new Map<string, string[]>(), namespaces: new Map<string, string>() }
  IMPORTS.set(sf, hit)
  for (const statement of sf.statements) {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier) || !statement.importClause) continue
    const from = moduleRel(sf.fileName, statement.moduleSpecifier.text)
    const { name, namedBindings } = statement.importClause
    if (!from) continue
    if (name) hit.names.set(name.text, declaredNames(from, 'default'))
    if (namedBindings && ts.isNamespaceImport(namedBindings)) hit.namespaces.set(namedBindings.name.text, from)
    if (namedBindings && ts.isNamedImports(namedBindings)) {
      for (const element of namedBindings.elements) hit.names.set(element.name.text, declaredNames(from, (element.propertyName ?? element.name).text))
    }
  }
  return hit
}
/** The names a module declares an export under: through `export { A as B }`, a re-export from another module or
    `export *`, and `export default` (what it exports by name, or `default@file` for a function with none). A chain of
    re-exports past the follower's reach, a cycle of `export *` among them, is a name it cannot follow. */
function declaredNames(rel: string | undefined, name: string, depth = 0): string[] {
  const sf = rel === undefined ? undefined : moduleAt(rel)
  if (!sf || rel === undefined) return []
  if (depth > FOLLOW_STEPS) return [pastReach(rel)]
  const out: string[] = []
  for (const statement of sf.statements) {
    const from = ts.isExportDeclaration(statement) && statement.moduleSpecifier && ts.isStringLiteral(statement.moduleSpecifier) ? moduleRel(rel, statement.moduleSpecifier.text) : undefined
    if (name === 'default' && ts.isExportAssignment(statement) && !statement.isExportEquals) {
      const names = heldNames(statement.expression, sf, depth + 1)
      out.push(...(names.length ? names : [`default@${rel}`]))
    } else if (name === 'default' && (ts.isFunctionDeclaration(statement) || ts.isClassDeclaration(statement)) && ts.getCombinedModifierFlags(statement) & ts.ModifierFlags.Default) {
      out.push(statement.name?.text ?? `default@${rel}`)
    } else if (ts.isExportDeclaration(statement) && statement.exportClause && ts.isNamedExports(statement.exportClause)) {
      for (const element of statement.exportClause.elements) {
        if (element.name.text !== name) continue
        const local = (element.propertyName ?? element.name).text
        out.push(...(statement.moduleSpecifier ? declaredNames(from, local, depth + 1) : namedNames(sf, local, moduleConst(sf, local), depth + 1, NO_PASSES)))
      }
    } else if (ts.isExportDeclaration(statement) && !statement.exportClause && from && name !== 'default') out.push(...declaredNames(from, name, depth + 1))
  }
  return out.length ? out : [name === 'default' ? `default@${rel}` : name]
}
const LOGICAL = new Set([ts.SyntaxKind.QuestionQuestionToken, ts.SyntaxKind.BarBarToken, ts.SyntaxKind.AmpersandAmpersandToken])
/** The components a value names: an identifier (with what a same-file const it names holds, what a destructured name
    holds, or what it imports), a member (with what its object holds at the key), through parentheses and any call that
    wraps one (`memo(PasswordField)`), either branch of a condition or a logical operator, and the default export of a
    module a loader imports (`lazy(() => import('./Secret'))`). Past the follower's reach (a cycle of consts), a name it
    cannot follow. */
function heldNames(value: ts.Expression, sf: ts.SourceFile, depth = 0, passes: Passes = NO_PASSES): string[] {
  const inner = bareExpression(value)
  if (depth > FOLLOW_STEPS) return [pastReach(placeOf(sf, inner))]
  if (ts.isIdentifier(inner)) return namedNames(sf, inner.text, resolverOf(sf)(inner)?.decl, depth, passes)
  if (ts.isPropertyAccessExpression(inner)) return [inner.getText(sf), ...namesAt(inner.expression, [inner.name.text], sf, depth + 1, passes)]
  // An element of an object of components: by a literal key, that entry; by any other, every entry of the object it holds.
  if (ts.isElementAccessExpression(inner)) {
    const key = ts.isStringLiteralLike(inner.argumentExpression) || ts.isNumericLiteral(inner.argumentExpression) ? inner.argumentExpression.text : undefined
    const keys = key !== undefined ? [key] : objectKeys(inner.expression, sf)
    return keys.flatMap((each) => (isUnfollowed(each) ? [each] : namesAt(inner.expression, [each], sf, depth + 1, passes)))
  }
  if (ts.isConditionalExpression(inner)) return [...heldNames(inner.whenTrue, sf, depth + 1, passes), ...heldNames(inner.whenFalse, sf, depth + 1, passes)]
  if (ts.isBinaryExpression(inner) && LOGICAL.has(inner.operatorToken.kind)) return [...heldNames(inner.left, sf, depth + 1, passes), ...heldNames(inner.right, sf, depth + 1, passes)]
  if (ts.isCallExpression(inner)) {
    const loaded = inner.expression.kind === ts.SyntaxKind.ImportKeyword ? inner : functionIn(inner.arguments[0])?.body
    if (loaded && ts.isCallExpression(loaded) && loaded.expression.kind === ts.SyntaxKind.ImportKeyword) {
      const specifier = loaded.arguments[0]
      return specifier && ts.isStringLiteral(specifier) ? declaredNames(moduleRel(sf.fileName, specifier.text), 'default', depth + 1) : []
    }
    return inner.arguments[0] && !ts.isSpreadElement(inner.arguments[0]) ? heldNames(inner.arguments[0], sf, depth + 1, passes) : []
  }
  return []
}
/** The keys of the same-file object literal a value holds, written in place or held by a const; past the follower's reach
    (a cycle of consts), a name it cannot follow in their place. */
function objectKeys(value: ts.Expression, sf: ts.SourceFile, depth = 0): string[] {
  const inner = bareExpression(value)
  if (ts.isObjectLiteralExpression(inner)) return inner.properties.flatMap((p) => (p.name && !ts.isComputedPropertyName(p.name) ? [keyText(p.name)] : []))
  const decl = ts.isIdentifier(inner) ? resolverOf(sf)(inner)?.decl : undefined
  if (!decl || !ts.isVariableDeclaration(decl) || !(decl.parent.flags & ts.NodeFlags.Const) || !decl.initializer) return []
  return depth < FOLLOW_STEPS ? objectKeys(decl.initializer, sf, depth + 1) : [pastReach(placeOf(sf, inner))]
}
/** A name, with what the same-file const it binds to holds, what the pattern that destructures it holds there, or the
    names its import declares. */
const namedNames = (sf: ts.SourceFile, name: string, decl: Binding['decl'] | undefined, depth: number, passes: Passes): string[] => [
  name,
  ...(decl && ts.isVariableDeclaration(decl) && decl.parent.flags & ts.NodeFlags.Const && decl.initializer ? heldNames(decl.initializer, sf, depth + 1, passes) : []),
  ...(decl && ts.isBindingElement(decl) ? patternNames(decl, sf, depth + 1, passes) : []),
  ...(decl ? [] : (importsOf(sf).names.get(name) ?? [])),
]
/** The components a value holds at a path of keys (an object's entry, an array's element): its own names with the keys
    after them (`Fields`, then `Secret`, names `Fields.Secret`, an entry written in place), and what it holds there,
    followed through an object or an array written in place, a const, a destructured name, a namespace import, either
    branch of a condition or a logical operator, and a component's prop (what its callers hand it). Past the follower's
    reach, a name it cannot follow. */
function namesAt(value: ts.Expression, keys: readonly string[], sf: ts.SourceFile, depth: number, passes: Passes): string[] {
  if (!keys.length) return heldNames(value, sf, depth, passes)
  const inner = bareExpression(value)
  if (depth > FOLLOW_STEPS) return [pastReach(placeOf(sf, inner))]
  const at = (child: ts.Expression, rest: readonly string[] = keys.slice(1)) => namesAt(child, rest, sf, depth + 1, passes)
  // An entry is named by the container's initializer only while nothing in its module can change it after.
  const why = ts.isObjectLiteralExpression(inner) || (ts.isArrayLiteralExpression(inner) && Number.isInteger(Number(keys[0]))) ? componentsChange(inner, sf) : undefined
  if (why) return [`${UNFOLLOWED}${why}`]
  if (ts.isObjectLiteralExpression(inner)) {
    const entry = inner.properties.find((p) => p.name && !ts.isComputedPropertyName(p.name) && keyText(p.name) === keys[0])
    return entry && ts.isPropertyAssignment(entry) ? at(entry.initializer) : entry && ts.isShorthandPropertyAssignment(entry) ? at(entry.name) : []
  }
  if (ts.isArrayLiteralExpression(inner)) {
    const index = Number(keys[0])
    const element = inner.elements[index]
    return Number.isInteger(index) && element && !ts.isOmittedExpression(element) && !inner.elements.slice(0, index + 1).some(ts.isSpreadElement) ? at(element) : []
  }
  if (ts.isConditionalExpression(inner)) return [...at(inner.whenTrue, keys), ...at(inner.whenFalse, keys)]
  if (ts.isBinaryExpression(inner) && LOGICAL.has(inner.operatorToken.kind)) return [...at(inner.left, keys), ...at(inner.right, keys)]
  if (!ts.isIdentifier(inner) && !ts.isPropertyAccessExpression(inner)) return []
  const own = heldNames(inner, sf, depth + 1, passes).map((name) => withKeys(name, keys))
  if (ts.isPropertyAccessExpression(inner)) return [...own, ...at(inner.expression, [inner.name.text, ...keys])]
  const decl = resolverOf(sf)(inner)?.decl
  if (decl && ts.isVariableDeclaration(decl)) return [...own, ...(decl.parent.flags & ts.NodeFlags.Const && decl.initializer ? at(decl.initializer, keys) : [])]
  if (decl && ts.isBindingElement(decl)) return [...own, ...patternNames(decl, sf, depth + 1, passes, keys)]
  if (decl && ts.isParameter(decl)) return [...own, ...propNames(decl, keys, sf, passes)]
  const namespace = decl ? undefined : importsOf(sf).namespaces.get(inner.text)
  return [...own, ...(namespace ? declaredNames(namespace, keys[0], depth + 1).map((name) => withKeys(name, keys.slice(1))) : [])]
}
/** A name for a component this reader cannot follow: one read through a container that can change after its initializer,
    or one past the follower's reach. A tag, a `createElement` or a call named as a component that renders it fails
    loudly, with why. */
const UNFOLLOWED = '\u0000unfollowed: '
const isUnfollowed = (name: string) => name.startsWith(UNFOLLOWED)
/** The follower's reach: the steps it takes from where a name is rendered (each const, key, pattern, module, branch of a
    condition or a logical operator and wrapping call is one) before a chain, or a cycle, is one it cannot follow; and the
    member steps a name a prop is handed may take, which keeps the props callers hand finite. */
const FOLLOW_STEPS = 8
/** A name past the follower's reach, with where it stopped: a file's line, or the module whose exports it was reading. */
const pastReach = (where: string) => `${UNFOLLOWED}more steps than this reader follows, at ${where}`
const placeOf = (sf: ts.SourceFile, node: ts.Node) => `${sf.fileName}:${lineOf(sf, node)}`
/** A name with keys after it (`Fields`, then `Secret`, names `Fields.Secret`); a name this reader cannot follow stays as it is. */
const withKeys = (name: string, keys: readonly string[]) => (isUnfollowed(name) || !keys.length ? name : [name, ...keys].join('.'))
/** Why a container the follower names components through can change after its initializer in its own module (another
    module's write is a stated limit: the follower reads an import by its declaration), or undefined. */
const FOLLOWED = new WeakMap<ts.Node, string | undefined>()
function componentsChange(literal: ts.ObjectLiteralExpression | ts.ArrayLiteralExpression, sf: ts.SourceFile): string | undefined {
  if (!FOLLOWED.has(literal)) {
    const escaped = containerEscape(literal, sf, resolverOf(sf), { exports: false })
    FOLLOWED.set(literal, escaped ? `a container that can change after its initializer: ${escaped.how}, line ${lineOf(sf, escaped.at)}` : undefined)
  }
  return FOLLOWED.get(literal)
}
/** The components a destructured name holds: its pattern's root taken apart by its keys (with `extra` after them), each
    step's default beside; a rest keeps the keys it is taken at. A component's prop holds what its callers hand it. Past
    the follower's reach, a name it cannot follow. */
function patternNames(decl: ts.BindingElement, sf: ts.SourceFile, depth: number, passes: Passes, extra: readonly string[] = []): string[] {
  const path = bindingSteps(decl)
  if (!path) return []
  if (depth > FOLLOW_STEPS) return [pastReach(placeOf(sf, decl))]
  const keys = [...path.steps.flatMap(({ step }) => ('key' in step ? [step.key] : 'index' in step ? [String(step.index)] : [])), ...extra]
  let taken = 0
  const defaults = path.steps.flatMap(({ step, fallback }) => {
    if (!('rest' in step)) taken++
    return fallback ? namesAt(fallback, keys.slice(taken), sf, depth + 1, passes) : []
  })
  const { root } = path
  const held = ts.isParameter(root) ? propNames(root, keys, sf, passes)
    : root.parent.flags & ts.NodeFlags.Const && root.initializer ? namesAt(root.initializer, keys, sf, depth + 1, passes) : []
  return [...held, ...defaults]
}
/** What a component's callers hand its prop (the first key, of its first parameter), with the keys after it. */
function propNames(param: ts.ParameterDeclaration, keys: readonly string[], sf: ts.SourceFile, passes: Passes): string[] {
  const component = param.parent.parameters[0] === param ? componentName(param.parent, sf.fileName) : undefined
  return component && keys.length ? (passes.get(`${component}#${keys[0]}`) ?? []).map((name) => withKeys(name, keys.slice(1))) : []
}
/**
 * The components each component's props are handed by the callers that render it, over `sources`, to a fixed point (a
 * prop handed on as another's, down any number of components): `<Page Field={Secret} />` hands Page's `Field` what Secret
 * names. Only a value naming a component (a capital, as JSX requires) is kept. The loop ends: the passes only grow, inside
 * a finite set. Each name is made of the sources' own names, keys and modules, and one handed with more than FOLLOW_STEPS
 * member steps is a name this reader cannot follow, which stops the one name that would grow forever: a component that
 * hands a member of its own prop back to itself adds a step to it each round.
 */
function componentPasses(sources: ReadonlyArray<{ rel: string; source: string }>): Map<string, string[]> {
  const passes = new Map<string, string[]>()
  for (let grew = true; grew; ) {
    grew = false
    for (const { rel, source } of sources) {
      if (!isScript(rel)) continue
      const sf = parsed(source, rel)
      const visit = (node: ts.Node): void => {
        if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && !/^[a-z][^.]*$/.test(node.tagName.getText(sf))) {
          const callees = heldNames(node.tagName as ts.Expression, sf, 0, passes)
          for (const attribute of node.attributes.properties) {
            if (!ts.isJsxAttribute(attribute) || !attribute.initializer || !ts.isJsxExpression(attribute.initializer) || !attribute.initializer.expression) continue
            const handed = heldNames(attribute.initializer.expression, sf, 0, passes)
              .filter((name) => /^[A-Z]/.test(name) || name.startsWith('default@') || isUnfollowed(name))
              .map((name) => (isUnfollowed(name) || name.split('.').length - 1 <= FOLLOW_STEPS ? name : pastReach(placeOf(sf, attribute))))
            for (const callee of handed.length ? callees : []) {
              const key = `${callee}#${attribute.name.getText(sf)}`
              const known = passes.get(key) ?? []
              const added = [...new Set(handed)].filter((name) => !known.includes(name))
              if (!added.length) continue
              passes.set(key, [...known, ...added])
              grew = true
            }
          }
        }
        ts.forEachChild(node, visit)
      }
      visit(sf)
    }
  }
  return passes
}
/** A module's own top-level const or function by its name (for a name a module exports, read from outside it). */
function moduleConst(sf: ts.SourceFile, name: string): ts.VariableDeclaration | ts.FunctionDeclaration | undefined {
  for (const statement of sf.statements) {
    if (ts.isFunctionDeclaration(statement) && statement.name?.text === name) return statement
    if (ts.isVariableStatement(statement)) {
      const decl = statement.declarationList.declarations.find((d) => ts.isIdentifier(d.name) && d.name.text === name)
      if (decl) return decl
    }
  }
  return undefined
}

/** The name a function is rendered or called under: its own declared name; a const that holds it, in place or through any
    call that wraps it (forwardRef, memo, any other; a wrapped one named with a capital, as JSX requires); an entry of
    the objects a const holds, at any depth (`Fields.Secret`, `Kit.inputs.Secret`); or a default export (`default@file`). Undefined for any other function (a callback, a render
    prop), whose callers this reader cannot find. */
function componentName(fn: ts.SignatureDeclaration, rel: string): string | undefined {
  if (ts.isFunctionDeclaration(fn)) return fn.name?.text ?? (ts.getCombinedModifierFlags(fn) & ts.ModifierFlags.Default ? `default@${rel}` : undefined)
  let node: ts.Node = fn
  let wrapped = false
  for (;;) {
    const parent = node.parent
    if (ts.isParenthesizedExpression(parent) || ts.isAsExpression(parent) || ts.isSatisfiesExpression(parent)) node = parent
    else if (ts.isCallExpression(parent) && parent.arguments.some((argument) => argument === node)) {
      node = parent
      wrapped = true
    } else break
  }
  const holder = node.parent
  if (ts.isVariableDeclaration(holder) && ts.isIdentifier(holder.name)) return !wrapped || /^[A-Z]/.test(holder.name.text) ? holder.name.text : undefined
  if (ts.isExportAssignment(holder)) return `default@${rel}`
  // An object's entry, at any depth of the objects a const holds (`Fields.Secret`, `Kit.inputs.Secret`).
  const keys: string[] = []
  let entry: ts.Node = ts.isMethodDeclaration(fn) ? fn : holder
  while ((ts.isPropertyAssignment(entry) || ts.isMethodDeclaration(entry)) && ts.isObjectLiteralExpression(entry.parent) && !ts.isComputedPropertyName(entry.name)) {
    keys.unshift(keyText(entry.name))
    let object: ts.Node = entry.parent.parent
    while (ts.isParenthesizedExpression(object) || ts.isAsExpression(object) || ts.isSatisfiesExpression(object)) object = object.parent
    if (ts.isVariableDeclaration(object) && ts.isIdentifier(object.name)) return `${object.name.text}.${keys.join('.')}`
    entry = object
  }
  return undefined
}

/** The password fields (a `type` that can be password, a PasswordField, a forwarding component rendered, called or
    created) and new-password fields a file renders. */
function passwordFields(source: string, rel: string, forwarders: Forwarders = FORWARDERS): Field[] {
  if (!isScript(rel)) return []
  const sf = parsed(source, rel)
  const evaluate = evaluator(sf, resolverOf(sf))
  const out: Field[] = []
  /** Each attribute a tag reads: as written (undefined for a bare one), or the values a spread gives it. */
  type Attrs = Map<string, ts.Node | undefined | Alternative[]>
  const valuesOf = (value: ts.Node | undefined | Alternative[]): Alternative[] =>
    Array.isArray(value) ? value : value === undefined ? [{ kind: 'text', text: 'true' }] : evaluate.of(value)
  /** The names a tag renders a component under (an intrinsic element, lowercase, its own); the props each forwarder among
      them forwards a field's autoComplete through. */
  const passes = forwarders.passes ?? NO_PASSES
  const namesOf = (tag: ts.Expression) => (/^[a-z][^.]*$/.test(tag.getText(sf)) ? [tag.getText(sf)] : heldNames(tag, sf, 0, passes))
  const forwardedBy = (names: string[]) => (names.some((name) => forwarders.has(name)) ? [...new Set(names.flatMap((name) => [...(forwarders.get(name) ?? [])]))] : undefined)
  const keysOf = (names: string[]) => [...new Set([...(forwardedBy(names) ?? ['autoComplete']), 'type', 'minLength', 'id'])]
  /** Spreads an object into a tag's attributes as React does, a later attribute winning: the entries of an object the
      evaluator holds (written in place, held, destructured or a member; a rest without the keys taken out beside it); the
      props a function forwards, all of them or a rest without those keys; and for any other value, every attribute this
      reader reads, unreadable. */
  const spreadInto = (attrs: Attrs, value: ts.Expression, keys: readonly string[]) => {
    const holder = evaluate.holderOf(value)
    if (holder && 'unfollowed' in holder) {
      const spread: Alternative[] = [{ kind: 'unreadable', form: `{...${squash(value.getText(sf))}} (${holder.why})`, loud: true }]
      for (const key of keys) attrs.set(key, attrs.has(key) ? [...spread, ...valuesOf(attrs.get(key))] : spread)
      return
    }
    if (holder && 'object' in holder) {
      for (const entry of holder.object.properties) {
        const key = entry.name && !ts.isComputedPropertyName(entry.name) ? keyText(entry.name) : undefined
        if (key !== undefined && holder.without?.includes(key)) continue
        if (ts.isSpreadAssignment(entry)) spreadInto(attrs, entry.expression, keys)
        else if (ts.isPropertyAssignment(entry) && key !== undefined) attrs.set(key, entry.initializer)
        else if (ts.isShorthandPropertyAssignment(entry)) attrs.set(entry.name.text, entry.name)
        else for (const read of keys) attrs.set(read, [{ kind: 'unreadable', form: `${squash(entry.getText(sf))} (an entry this reader cannot read)` }])
      }
      return
    }
    const props = holder && 'props' in holder ? holder : undefined
    for (const key of keys) {
      if (props?.without?.includes(key)) continue
      const spread: Alternative[] = props ? evaluate.forwarded(props.props, key, value) : [{ kind: 'unreadable', form: `{...${squash(value.getText(sf))}} (a spread this reader cannot follow)` }]
      attrs.set(key, attrs.has(key) ? [...spread, ...valuesOf(attrs.get(key))] : spread)
    }
  }
  /** One field from its attributes (written on a tag, or the object a forwarding component is called or created with). */
  const field = (at: ts.Node, tag: string, names: string[], attrs: Attrs) => {
    const reached = names.find(isUnfollowed)
    if (reached) {
      const id = attrs.get('id')
      out.push({
        line: lineOf(sf, at), tag, id: id && !Array.isArray(id) && ts.isStringLiteral(id) ? id.text : '', kind: 'unreadable', isNew: false, floor: false,
        forwards: [], renders: names.filter((name) => forwarders.has(name)), unreadable: `${tag} (a component read through ${reached.slice(UNFOLLOWED.length)})`,
      })
      return
    }
    const own = forwardedBy(names)
    // A forwarding component's autoComplete is the props it forwards it through; any other field's, its own attribute.
    const props = (own ?? ['autoComplete']).filter((name) => attrs.has(name))
    const values = props.flatMap((name) => valuesOf(attrs.get(name)))
    const node = (name: string) => {
      const value = attrs.get(name)
      return Array.isArray(value) ? undefined : value
    }
    const isNew = props.some((name) => carries(node(name), namesNew)) || values.some((v) => v.kind === 'text' && namesNew(v.text))
    const typed = attrs.has('type') && (carries(node('type'), (text) => text === 'password') || valuesOf(attrs.get('type')).some((v) => v.kind === 'text' && v.text === 'password'))
    if (!isNew && !names.includes('PasswordField') && !own && !typed) return
    const forwards: Field['forwards'] = []
    let unnamable: string | undefined
    for (const value of values) {
      if (value.kind !== 'forwarded') continue
      const component = componentName(value.from, rel)
      if (component) forwards.push({ component, prop: value.prop })
      else unnamable ??= `${value.prop} (forwarded from a function this reader cannot name, a callback or a render prop, so no caller of it is read)`
    }
    const unreadable = values.find((v): v is Extract<Alternative, { kind: 'unreadable' }> => v.kind === 'unreadable')?.form ?? unnamable
    const namesKind = (v: Alternative) => v.kind === 'forwarded' || (v.kind === 'text' && (namesNew(v.text) || namesCurrent(v.text)))
    const kind: Field['kind'] = !props.length ? 'unnamed' : unreadable ? 'unreadable' : !values.every(namesKind) ? 'unnamed' : forwards.length ? 'forwarded' : isNew ? 'new' : 'current'
    const min = node('minLength')
    const minExpression = min && ts.isJsxExpression(min) ? min.expression : (min as ts.Expression | undefined)
    const id = node('id')
    out.push({
      line: lineOf(sf, at),
      tag,
      id: id && ts.isStringLiteral(id) ? id.text : '',
      kind,
      isNew,
      floor: !!minExpression && minExpression.getText(sf) === 'PASSWORD_MIN_LENGTH',
      forwards,
      renders: names.filter((name) => forwarders.has(name)),
      unreadable,
    })
  }
  const visit = (node: ts.Node): void => {
    if (ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) {
      const names = namesOf(node.tagName as ts.Expression)
      const attrs: Attrs = new Map()
      for (const prop of node.attributes.properties) {
        if (ts.isJsxAttribute(prop)) attrs.set(prop.name.getText(sf), prop.initializer)
        else spreadInto(attrs, prop.expression, keysOf(names))
      }
      field(node, node.tagName.getText(sf), names, attrs)
    }
    // A forwarding component called as a function (`Secret({ autoComplete: … })`), or any element created without JSX
    // (`createElement(Secret, { … })`, `jsx('input', { … })`): the object it is handed is its attributes.
    if (ts.isCallExpression(node)) {
      const create = /^(?:React\.)?(?:createElement|jsxs?|jsxDEV)$/.test(node.expression.getText(sf))
      const tag = create ? node.arguments[0] : node.expression
      const object = create ? node.arguments[1] : node.arguments[0]
      const names = !tag || ts.isSpreadElement(tag) ? [] : ts.isStringLiteralLike(tag) ? [tag.text] : namesOf(tag)
      // A call through a container that can change is a component's (loud) only where it is named as one: a capital, as JSX requires.
      const callee = bareExpression(node.expression)
      const calledName = ts.isIdentifier(callee) ? callee.text : ts.isPropertyAccessExpression(callee) ? callee.name.text : undefined
      if (create || forwardedBy(names) || names.includes('PasswordField') || (names.some(isUnfollowed) && (calledName === undefined || /^[A-Z]/.test(calledName)))) {
        const attrs: Attrs = new Map()
        if (object && !ts.isSpreadElement(object)) spreadInto(attrs, object, keysOf(names))
        field(node, tag ? tag.getText(sf) : '', names, attrs)
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}
const describeField = (rel: string, field: Field) => `${rel}:${field.line} <${field.tag}>`

/**
 * The components that forward a password field's autoComplete from their own props, with the props they forward it
 * through, found over `sources` to a fixed point: a caller of one renders a password field itself, read where it writes
 * those props (or forwards them on).
 */
function forwardingComponents(sources: ReadonlyArray<{ rel: string; source: string }>): Map<string, Set<string>> & { passes: Passes } {
  // Parse every source first, so one imports another by its path whichever is read first.
  for (const { rel, source } of sources) if (isScript(rel)) parsed(source, rel)
  const found = Object.assign(new Map<string, Set<string>>(), { passes: componentPasses(sources) })
  // To a fixed point, which the loop reaches: the forwarders only grow, each a component the sources declare (by the name
  // componentName gives it) with a prop it forwards, a key written in the sources.
  for (let grew = true; grew; ) {
    grew = false
    for (const { rel, source } of sources) {
      for (const { component, prop } of passwordFields(source, rel, found).flatMap((field) => field.forwards)) {
        const props = found.get(component) ?? new Set<string>()
        found.set(component, props)
        if (props.has(prop)) continue
        props.add(prop)
        grew = true
      }
    }
  }
  return found
}
/** The app's and planted sources' own forwarding components (the app's files are FORWARDERS' already). */
const forwardersOf = (sources: ReadonlyArray<{ rel: string; source: string }>): Forwarders => {
  const own = forwardingComponents(sources)
  const merged = Object.assign(new Map<string, Set<string>>([...FORWARDERS].map(([name, props]) => [name, new Set(props)])), { passes: own.passes })
  for (const [name, props] of own) merged.set(name, new Set([...(merged.get(name) ?? []), ...props]))
  return merged
}
const forwardersFor = (source: string, rel: string) => forwardersOf([{ rel, source }])

/** New-password JSX fields whose `minLength` is not the shared constant. */
const fieldsWithoutFloor = (source: string, rel: string, forwarders: Forwarders = forwardersFor(source, rel)) =>
  passwordFields(source, rel, forwarders)
    .filter((field) => field.isNew && !field.floor)
    .map((field) => describeField(rel, field))
/** Password fields whose autoComplete does not name new- or current-password in every value it can take. */
const unnamedFields = (source: string, rel: string, forwarders: Forwarders = forwardersFor(source, rel)) =>
  passwordFields(source, rel, forwarders)
    .filter((field) => field.kind === 'unnamed')
    .map((field) => describeField(rel, field))
/** Password fields whose autoComplete holds a form this reader cannot evaluate: each fails loudly, with the form. */
const unreadableFields = (source: string, rel: string, forwarders: Forwarders = forwardersFor(source, rel)) =>
  passwordFields(source, rel, forwarders)
    .filter((field) => field.kind === 'unreadable')
    .map((field) => `${describeField(rel, field)} autoComplete is a form this reader cannot evaluate: ${field.unreadable}`)
/** Forwarding components no source renders (a route's entry, which the framework renders, or a component nothing uses):
    no caller's value reaches their field. */
const unrenderedForwarders = (sources: ReadonlyArray<{ rel: string; source: string }>, forwarders: Forwarders) => {
  const rendered = new Set(sources.flatMap(({ rel, source }) => passwordFields(source, rel, forwarders).flatMap((field) => field.renders)))
  return [...forwarders.keys()].filter((name) => !rendered.has(name)).sort()
}

/** Whether a form checks `….length < PASSWORD_MIN_LENGTH` in its code; a comment or a string does not count. */
function checksFloorInCode(source: string, rel: string): boolean {
  const visit = (node: ts.Node): boolean =>
    (ts.isBinaryExpression(node) &&
      node.operatorToken.kind === ts.SyntaxKind.LessThanToken &&
      ts.isPropertyAccessExpression(node.left) &&
      node.left.name.text === 'length' &&
      ts.isIdentifier(node.right) &&
      node.right.text === 'PASSWORD_MIN_LENGTH') ||
    (ts.forEachChild(node, (child) => visit(child) || undefined) ?? false)
  return visit(parse(source, rel))
}

/** The statements a Python `def` at `start` runs: its body without the docstring, comments or blank lines. */
function pythonBlock(lines: string[], start: number): string[] {
  const indent = (line: string) => line.length - line.trimStart().length
  // The signature may span lines; the body starts after the line that closes it.
  let open = start
  while (open < lines.length && !/\)\s*(?:->\s*[^:]+)?:\s*(?:#.*)?$/.test(lines[open])) open++
  const code: string[] = []
  for (let i = open + 1; i < lines.length && (!lines[i].trim() || indent(lines[i]) > indent(lines[start])); i++) {
    const line = lines[i].trim()
    if (line && !line.startsWith('#')) code.push(line)
  }
  const quote = code[0]?.match(/^(?:"""|''')/)?.[0]
  if (quote) {
    const closes = code.findIndex((line, k) => (k === 0 ? line.length > 3 && line.endsWith(quote) : line.endsWith(quote)))
    code.splice(0, closes + 1)
  }
  return code
}
const pythonBody = (source: string, def: RegExp): string[] | undefined => {
  const lines = source.split('\n')
  const start = lines.findIndex((line) => def.test(line))
  return start < 0 ? undefined : pythonBlock(lines, start)
}

/** Every validator in a schema module that names a password field or reads one, as `(args) statement / …`. */
function passwordValidators(source: string): string[] {
  const lines = source.split('\n')
  return lines.flatMap((line, index) => {
    const decorator = line.match(/^\s*@(?:field_validator|model_validator|validator|root_validator)\b(.*)$/)
    if (!decorator) return []
    const def = lines.findIndex((l, k) => k > index && /^\s*(?:async\s+)?def\s/.test(l))
    const body = def < 0 ? [] : pythonBlock(lines, def)
    return /password/.test(decorator[1]) || body.some((statement) => /password/.test(statement)) ? [`${decorator[1].trim()} ${body.join(' / ')}`] : []
  })
}

const ALL_FILES = SOURCE_ROOTS.flatMap((root) => walk(path.join(frontendDir, root)))
const FILES = ALL_FILES.filter((file) => READ.test(file))
const rel = (file: string) => path.relative(frontendDir, file).split(path.sep).join('/')
/** The app's forwarding components, PasswordField among them. */
const FORWARDERS = forwardingComponents(FILES.filter((file) => isScript(rel(file))).map((file) => ({ rel: rel(file), source: readFileSync(file, 'utf8') })))
const RULE_FILE = 'lib/passwordRules.ts'

describe('the password rule moves in lockstep with the backend', () => {
  it('mirrors PASSWORD_MIN_LENGTH, the minimum validate_password_strength enforces', () => {
    const match = backend('app/config.py').match(/^\s*PASSWORD_MIN_LENGTH:\s*int\s*=\s*(\d+)/m)
    if (!match) throw new Error('PASSWORD_MIN_LENGTH not found in backend/app/config.py')
    expect(PASSWORD_MIN_LENGTH).toBe(Number(match[1]))
  })

  it('the validator checks length only, so PASSWORD_RULE states the whole rule', () => {
    const body = pythonBody(backend('app/services/password_utils.py'), /^def validate_password_strength\b/)
    if (!body) throw new Error('validate_password_strength not found in backend/app/services/password_utils.py')
    expect(body, 'a new password rule on the server: state it in PASSWORD_RULE, then update this list').toEqual([
      'if len(value) < settings.PASSWORD_MIN_LENGTH:',
      'raise ValueError(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters.")',
      'if len(value) > PASSWORD_MAX_LENGTH:',
      'raise ValueError(f"Password must be at most {PASSWORD_MAX_LENGTH} characters.")',
      'return value',
    ])
  })

  it('every password field of the auth schemas is a bare str whose validator only calls validate_password_strength', () => {
    const router = backend('app/routers/auth.py')
    // A constraint on the field itself (Field(min_length=…), a pattern) would be a rule too.
    const fields = router.split('\n').flatMap((line) => line.match(/^ {4}(\w*password\w*)\s*:\s*(.+?)\s*$/)?.slice(1, 3).join(': ') ?? [])
    expect(fields, 'a password field changed in backend/app/routers/auth.py: state any new rule in PASSWORD_RULE, then update this list').toEqual([
      'password: str',
      'password: str',
      'new_password: str',
      'current_password: Optional[str] = None',
      'new_password: str',
    ])
    expect(passwordValidators(router), 'a new password rule in a schema: state it in PASSWORD_RULE, then update this list').toEqual([
      '("password") return validate_password_strength(value)',
      '("new_password") return validate_password_strength(value)',
      '("new_password") return validate_password_strength(value)',
    ])
  })

  it('names the breach check only while it defaults on and the routes behind the sentence call it, and never a refusal the fail-open lookup cannot keep', () => {
    expect(PASSWORD_RULE).toContain('We check new passwords against known data breaches.')
    expect(PASSWORD_RULE, 'is_password_pwned fails open, so a breached password can get through: name the check, not a refusal').not.toMatch(
      /\b(?:reject|refus|block|den(?:y|ied)|not allowed|never accept|can(?:no|['\u2019])t use)/i,
    )
    expect(backend('app/config.py')).toMatch(/^\s*PWNED_PASSWORD_CHECK_ENABLED:\s*bool\s*=\s*True\b/m)
    // /register and /reset-password state PASSWORD_RULE; these are the routes their forms post to.
    const router = backend('app/routers/auth.py')
    for (const [route, password] of [['register', 'user_data.password'], ['reset_password', 'payload.new_password']]) {
      const body = pythonBody(router, new RegExp(String.raw`^async def ${route}\(`))
      expect(body, `${route} must refuse a breached password with is_password_pwned`).toContain(`if await is_password_pwned(${password}):`)
    }
  })

  it('reads every file that handles a password (a scan that finds none must not pass)', () => {
    expect(
      ALL_FILES.filter((file) => !READ.test(file) && !(path.extname(file) in NOT_READ)).map(rel),
      'a file the scan does not read: read its extension (READ), or list it in NOT_READ with why it holds no password rule',
    ).toEqual([])
    const handling = FILES.filter((file) => HANDLES_PASSWORD.test(readFileSync(file, 'utf8'))).map(rel)
    expect(handling).toEqual(expect.arrayContaining([...RULE_SITES, 'app/login/page.tsx']))
  })

  it('no file that handles a password writes a length by hand', () => {
    const offenders = FILES.filter((file) => rel(file) !== RULE_FILE).flatMap((file) => {
      const source = readFileSync(file, 'utf8')
      return [...handTyped(source, rel(file)), ...floorNumbers(source, rel(file)), ...codeForms(source, rel(file))]
    })
    expect(offenders, "use PASSWORD_MIN_LENGTH / PASSWORD_RULE from '@/lib/passwordRules'").toEqual([])
  })

  it('every new-password field carries minLength={PASSWORD_MIN_LENGTH}, or its form checks the floor in code', () => {
    const sources = FILES.map((file) => ({ rel: rel(file), source: readFileSync(file, 'utf8') }))
    // The scan finds the app's new-password fields: a check that reads none must not pass.
    expect([...FORWARDERS.keys()], 'the scan finds the component the app forwards a password field through').toContain('PasswordField')
    const found = sources.flatMap(({ rel, source }) => passwordFields(source, rel).filter((f) => f.kind === 'new').map((f) => `${rel} <${f.tag} id="${f.id}">`))
    expect(found).toEqual(
      expect.arrayContaining([
        'app/reset-password/page.tsx <PasswordField id="password">',
        'app/reset-password/page.tsx <PasswordField id="confirm">',
        'features/auth/components/RegisterForm.tsx <PasswordField id="password">',
        'features/settings/components/ChangePasswordForm.tsx <Input id="new_pw">',
        'features/settings/components/ChangePasswordForm.tsx <Input id="confirm_pw">',
      ]),
    )
    expect(
      sources.flatMap(({ rel, source }) => unnamedFields(source, rel, FORWARDERS)),
      "name the field's autoComplete (new-password or current-password) in every value it can take, so this check can tell which it is",
    ).toEqual([])
    expect(sources.flatMap(({ rel, source }) => unreadableFields(source, rel, FORWARDERS)), 'write the autoComplete in a form this reader evaluates').toEqual([])
    expect(unrenderedForwarders(sources, FORWARDERS), 'a component forwards a password field\'s autoComplete, but no file the scan reads renders it').toEqual([])
    const missing = sources.filter(({ rel }) => !(rel in CODE_CHECKED)).flatMap(({ rel, source }) => fieldsWithoutFloor(source, rel, FORWARDERS))
    expect(missing, 'give the field minLength={PASSWORD_MIN_LENGTH}').toEqual([])
    for (const file of Object.keys(CODE_CHECKED)) {
      expect(checksFloorInCode(readFileSync(path.join(frontendDir, file), 'utf8'), file), `${file} must check .length < PASSWORD_MIN_LENGTH in its code`).toBe(true)
    }
  })

  it('the pages that state or enforce the rule read it from lib/passwordRules', () => {
    for (const site of RULE_SITES) {
      expect(readFileSync(path.join(frontendDir, site), 'utf8'), `${site} must import from '@/lib/passwordRules'`).toMatch(
        /from '@\/lib\/passwordRules'/,
      )
    }
  })

  it('the scans catch what they are for (a self-check on fixed sources)', () => {
    const form = "import { PASSWORD_MIN_LENGTH } from '@/lib/passwordRules'\n"
    expect(handTyped(`${form}if (next.length < 12) {`, 'probe.tsx')).toEqual(['probe.tsx:2 (a length compared against a number): if (next.length < 12) {'])
    expect(handTyped(`${form}const hint = 'Use 12 or more characters.'`, 'probe.tsx')).toEqual([
      "probe.tsx:2 (a length in copy): const hint = 'Use 12 or more characters.'",
    ])
    // The rest of the copy family: hyphenated, a plus, spelled out, and the short form.
    for (const copy of ['Use a 12-character passphrase.', 'Use 12+ characters.', 'Use twelve characters or more.', 'At least 8 chars.']) {
      expect(handTyped(`${form}const hint = '${copy}'`, 'probe.tsx'), copy).toHaveLength(1)
    }
    // A renamed constant is read by its name and by its value; the value alone, under any name.
    expect(handTyped(`${form}const MIN_PASSWORD_LENGTH = 12`, 'probe.tsx')).toEqual([
      'probe.tsx:2 (a local minimum constant): const MIN_PASSWORD_LENGTH = 12',
    ])
    expect(floorNumbers(`${form}const MIN_PASSWORD_LENGTH = 12\nconst FLOOR = 12\nconst gap = 4`, 'probe.tsx')).toEqual([
      'probe.tsx:2 (the floor as a number): MIN_PASSWORD_LENGTH = 12',
      'probe.tsx:3 (the floor as a number): FLOOR = 12',
    ])
    expect(handTyped(`${form}const field = { minLength: 12 }`, 'probe.tsx')).toEqual(['probe.tsx:2 (a minLength literal): const field = { minLength: 12 }'])
    expect(handTyped(`${form}if (value.length > 0 && next.length < PASSWORD_MIN_LENGTH) {}`, 'probe.tsx')).toEqual([])
    expect(floorNumbers(`${form}if (value.length > 0 && next.length < PASSWORD_MIN_LENGTH + 4) {}`, 'probe.tsx')).toEqual([])
    // A file that only mentions a password is held to the floor, not to every number.
    expect(handTyped(`// password note\nconst cap = 'at most 400 characters'\nif (s.length > 120) {}`, 'note.ts')).toEqual([])
    for (const floor of [
      `const copy = 'at least ${PASSWORD_MIN_LENGTH} characters'`,
      `const copy = 'a ${PASSWORD_MIN_LENGTH}-character passphrase'`,
      `const copy = '${NUMBER_WORDS[PASSWORD_MIN_LENGTH]} characters'`,
      `export const PASSWORD_FLOOR = ${PASSWORD_MIN_LENGTH}`,
      `if (value.length < ${PASSWORD_MIN_LENGTH}) {}`,
      `const rule = { minLength: ${PASSWORD_MIN_LENGTH} }`,
    ]) {
      expect(handTyped(`// password note\n${floor}`, 'note.ts'), floor).toHaveLength(1)
    }
    // What a line scan cannot see (the principal review's forms), at any count where a file handles a
    // password: copy composed across JSX, a comparison through a constant of any name, a minimum call, a pattern.
    expect(
      codeForms(
        [
          form.trimEnd(),
          'const a = <p>At least {8} characters.</p>',
          'const b = (',
          '  <p>',
          '    At least 8',
          '    characters.',
          '  </p>',
          ')',
          'const GAP = 8',
          'if (pw.length < GAP) {}',
          'const schema = z.string().min(8)',
          'const c = <input type="password" pattern=".{8,}" />',
          // The shared constant, a count computed at runtime and Math.min are not a hand-typed length.
          'const d = <p>At least {PASSWORD_MIN_LENGTH} characters, {Math.min(a, 8)} left.</p>',
          'if (items.length > 0 && pw.length < PASSWORD_MIN_LENGTH) {}',
          // The review of #1310's forms: a length in a template literal or a `+` chain, its slot a constant of any
          // name or a literal; and inside a JSX child, read with the element's text.
          'const e = `Use at least ${GAP} characters.`',
          "const f = 'At least ' + GAP + ' characters.'",
          "const g = 'At least 8 ' + 'characters.'",
          'const h = <PasswordField hint={`At least ${8} characters.`} />',
          'const i = <p>{`At least ${GAP}`} characters.</p>',
          // The shared constant in a template, and a template with no count, are not a hand-typed length.
          'const j = `At least ${PASSWORD_MIN_LENGTH} characters.`',
          'const k = `Use ${words} characters you can remember.`',
          // A slot's text run into the count: composed it reads "least8"; with the template a gap, the count stands.
          "const l = <p>{`Use at ${'least'}`}8 characters.</p>",
        ].join('\n'),
        'probe.tsx',
      ),
    ).toEqual([
      'probe.tsx:2 (copy composed across JSX): At least 8 characters.',
      'probe.tsx:4 (copy composed across JSX): At least 8 characters.',
      'probe.tsx:10 (a length compared against a number): pw.length < GAP',
      'probe.tsx:11 (a minimum call): z.string().min(8)',
      'probe.tsx:12 (a pattern minimum): ".{8,}"',
      'probe.tsx:15 (copy composed in a template or a + chain): Use at least 8 characters.',
      'probe.tsx:16 (copy composed in a template or a + chain): At least 8 characters.',
      'probe.tsx:17 (copy composed in a template or a + chain): At least 8 characters.',
      'probe.tsx:18 (copy composed in a template or a + chain): At least 8 characters.',
      'probe.tsx:19 (copy composed across JSX): At least 8 characters.',
      'probe.tsx:22 (copy composed across JSX): … 8 characters.',
    ])
    // Where a file only mentions a password: the floor in those forms, and no other count.
    expect(
      codeForms(
        [
          '// password note',
          `const a = <p>At least {${PASSWORD_MIN_LENGTH}} characters.</p>`,
          `const n = ${PASSWORD_MIN_LENGTH}`,
          'if (pw.length < n) {}',
          `const schema = z.string().min(${PASSWORD_MIN_LENGTH})`,
          `const re = /^.{${PASSWORD_MIN_LENGTH},}$/`,
          'const b = <p>At most {400} characters.</p>',
          'const LIMIT = 400',
          'if (note.length > LIMIT) {}',
          `const t = \`at least \${${PASSWORD_MIN_LENGTH}} characters\``,
          'const u = `at most ${400} characters`',
        ].join('\n'),
        'note.tsx',
      ),
    ).toEqual([
      `note.tsx:2 (copy composed across JSX): At least ${PASSWORD_MIN_LENGTH} characters.`,
      'note.tsx:4 (a length compared against a number): pw.length < n',
      `note.tsx:5 (a minimum call): z.string().min(${PASSWORD_MIN_LENGTH})`,
      `note.tsx:6 (a pattern minimum): /^.{${PASSWORD_MIN_LENGTH},}$/`,
      `note.tsx:10 (copy composed in a template or a + chain): at least ${PASSWORD_MIN_LENGTH} characters`,
    ])
    // Every value a slot, an operand or a braced expression can render (#1370's fifth round, beside the readings above):
    // a ternary's either branch, `&&`, `??`, a string const, an object's entry, a same-file function's return, and a
    // comparison, a minimum call, a composed pattern and a minLength through them.
    expect(
      codeForms(
        [
          form.trimEnd(),
          'const GAP = 8',
          "const UNIT = 'characters'",
          'const LIMITS = { password: 8 }',
          "const minFor = (plan: string) => (plan === 'pro' ? 12 : 8)",
          'const a = `At least ${strict ? 12 : 8} characters.`',
          'const b = <p>At least {strict ? 12 : 8} characters.</p>',
          'const c = `Use ${GAP} ${UNIT}.`',
          'const d = <p>At least {strict && 8} characters.</p>',
          'const e = `At least ${limit ?? 8} characters.`',
          'const f = `At least ${LIMITS.password} characters.`',
          "const g = `At least ${minFor('pro')} characters.`",
          'const h = <p>At least <b>{strict ? 12 : 8}</b> characters.</p>',
          'if (pw.length < (strict ? 12 : GAP)) {}',
          'const schema = z.string().min(strict ? 12 : GAP)',
          'const re = new RegExp(`^.{${GAP},}$`)',
          'const i = <input type="password" minLength={GAP} />',
          // A count worked out at runtime stays unread; one beside a value the evaluator cannot know is read past it.
          'const j = `${remaining} characters left`',
          "const k = <p>{strict ? `${unknown} 8 characters.` : null}</p>",
          // A count destructured, at any depth, out of an object or an array, or reached through members.
          'const POLICY = { limits: { min: 8 } }',
          'const { password: fromPattern } = LIMITS',
          'const [fromArray] = [8]',
          'const { limits: { min: nestedMin } } = POLICY',
          'const l = `At least ${fromPattern} characters.`',
          'const m = <p>At least {fromArray} characters.</p>',
          'const n = `At least ${nestedMin} characters.`',
          'const o = `At least ${POLICY.limits.min} characters.`',
          // A count read through a container that can change after its initializer fails loudly (#1370's seventh round): read
          // from the initializer it would be stale, read as a gap it would hide the 9 the page renders.
          'const WRITTEN_LIMITS = { min: 8 }',
          'WRITTEN_LIMITS.min = 9',
          'const p = `At least ${WRITTEN_LIMITS.min} characters.`',
          'const SENTENCE = `At least ${WRITTEN_LIMITS.min}`',
          'const q = <p>{SENTENCE} characters.</p>',
          // Nested past what the evaluator follows, a cycle of consts read as a value and as a holder (#1370's eighth round):
          // loud, where a gap would read the template as no count without the reader having finished it.
          'const LOOP_A = LOOP_B',
          'const LOOP_B = LOOP_A',
          'const r = `At least ${LOOP_A} characters.`',
          'const HOLD_A = HOLD_B',
          'const HOLD_B = HOLD_A',
          'const s = `At least ${HOLD_A.min} characters.`',
        ].join('\n'),
        'probe.tsx',
      ),
    ).toEqual([
      'probe.tsx:6 (copy composed in a template or a + chain): At least 12 characters.',
      'probe.tsx:7 (copy composed across JSX): At least 12 characters.',
      'probe.tsx:8 (copy composed in a template or a + chain): Use 8 characters.',
      'probe.tsx:9 (copy composed across JSX): At least 8 characters.',
      'probe.tsx:10 (copy composed in a template or a + chain): At least 8 characters.',
      'probe.tsx:11 (copy composed in a template or a + chain): At least 8 characters.',
      'probe.tsx:12 (copy composed in a template or a + chain): At least 12 characters.',
      'probe.tsx:13 (copy composed across JSX): At least 12 characters.',
      'probe.tsx:14 (a length compared against a number): pw.length < (strict ? 12 : GAP)',
      'probe.tsx:15 (a minimum call): z.string().min(strict ? 12 : GAP)',
      'probe.tsx:16 (a pattern minimum): ^.{8,}$',
      'probe.tsx:17 (a minLength held in a value): minLength={GAP}',
      'probe.tsx:19 (copy composed across JSX): … 8 characters.',
      'probe.tsx:19 (copy composed in a template or a + chain): … 8 characters.',
      'probe.tsx:24 (copy composed in a template or a + chain): At least 8 characters.',
      'probe.tsx:25 (copy composed across JSX): At least 8 characters.',
      'probe.tsx:26 (copy composed in a template or a + chain): At least 8 characters.',
      'probe.tsx:27 (copy composed in a template or a + chain): At least 8 characters.',
      'probe.tsx:30 (a value this reader cannot read): WRITTEN_LIMITS.min (a container that can change after its initializer: an entry assigned, line 29)',
      'probe.tsx:31 (a value this reader cannot read): WRITTEN_LIMITS.min (a container that can change after its initializer: an entry assigned, line 29)',
      // Read through a const's template: the template stays loud where a gap would hide the count.
      'probe.tsx:32 (a value this reader cannot read): WRITTEN_LIMITS.min (a container that can change after its initializer: an entry assigned, line 29)',
      // The cycle stops on the const its twenty-fifth step reaches, as a value; as a holder, at the member read through it.
      'probe.tsx:35 (a value this reader cannot read): LOOP_B (nested past what this reader follows)',
      'probe.tsx:38 (a value this reader cannot read): HOLD_A.min (nested past what this reader follows)',
    ])
    // The length reader's limits, each a gap: a floor only two branching values state together, and one worked out by
    // arithmetic, are not read; the floor in one branch is. A value with more readings than the evaluator takes is loud.
    const [tens, ones] = [String(PASSWORD_MIN_LENGTH).slice(0, -1) || '0', String(PASSWORD_MIN_LENGTH).slice(-1)]
    const slots = ['a', 'b', 'c', 'd', 'e', 'f', 'g'].map((name) => `\${${name} ? 1 : 2}`).join('')
    expect(
      codeForms(
        [
          '// password note',
          `const a = <p>{x ? ${tens} : 9}{y ? ${ones} : 9} characters</p>`,
          `const b = \`at least \${${PASSWORD_MIN_LENGTH - 4} + 4} characters\``,
          `const c = \`at least \${big ? ${PASSWORD_MIN_LENGTH} : 0} characters\``,
          `const d = \`\${flag ? \`${slots}\` : ''} characters\``,
        ].join('\n'),
        'note.tsx',
      ),
    ).toEqual([
      `note.tsx:4 (copy composed in a template or a + chain): at least ${PASSWORD_MIN_LENGTH} characters`,
      expect.stringMatching(/^note\.tsx:5 \(a value with more readings than this reader takes\): `.*` \(more than 64 values\)$/),
    ])
    expect(
      fieldsWithoutFloor(
        [
          '<PasswordField id="a" autoComplete="new-password" minLength={PASSWORD_MIN_LENGTH} />',
          '<PasswordField id="b" autoComplete="new-password" showStrength />',
          '<Input id="c" type="password" autoComplete="new-password" minLength={12} />',
          '<PasswordField id="d" autoComplete="current-password" />',
          // Braced, a template, or one branch of an expression: still a new-password field.
          "<Input id=\"e\" type=\"password\" autoComplete={'new-password'} />",
          '<Input id="f" type="password" autoComplete={`new-password`} minLength={PASSWORD_MIN_LENGTH} />',
          "<Input id=\"g\" type=\"password\" autoComplete={setting ? 'new-password' : 'current-password'} />",
          // A forwarded prop is read where its caller writes the literal.
          '<input id="h" autoComplete={autoComplete} minLength={minLength} />',
        ].join('\n'),
        'probe.tsx',
      ),
    ).toEqual(['probe.tsx:2 <PasswordField>', 'probe.tsx:3 <Input>', 'probe.tsx:5 <Input>', 'probe.tsx:7 <Input>'])
    const spreads = [
      // A spread object is read like attributes written out.
      "<PasswordField id=\"i\" {...{ autoComplete: 'new-password' }} />",
      "<PasswordField id=\"j\" {...{ autoComplete: 'new-password', minLength: PASSWORD_MIN_LENGTH }} />",
      // A password field names its autoComplete or forwards one (a spread of props); a field it cannot read fails.
      '<Input id="k" type="password" name="new_password" />',
      '<Input id="l" type="password" {...rest} />',
      "<input id=\"m\" type={show ? 'text' : 'password'} autoComplete={autoComplete} />",
    ].join('\n')
    expect(fieldsWithoutFloor(spreads, 'probe.tsx')).toEqual(['probe.tsx:1 <PasswordField>'])
    expect(unnamedFields(spreads, 'probe.tsx')).toEqual(['probe.tsx:3 <Input>'])
    // The review of #1310's forms: a literal autoComplete must name new- or current-password ("off", "password", a typo
    // or a bare attribute names neither), and a forwarding component's caller is a field, whatever the component is called.
    const named = [
      '<Input id="n" type="password" autoComplete="off" />',
      "<Input id=\"o\" type=\"password\" autoComplete={'password'} />",
      '<PasswordField id="p" autoComplete="off" showStrength />',
      '<input id="q" type="password" autoComplete="new_password" />',
      "<input id=\"r\" type=\"password\" autoComplete={on ? 'off' : 'username'} />",
      '<input id="s" type="password" autoComplete />',
      'export function SecretInput(props: { id: string; autoComplete?: string }) { return <Input id={props.id} type="password" autoComplete={props.autoComplete} /> }',
      'const t = <SecretInput id="t" />',
      'const u = <SecretInput id="u" autoComplete="new-password" minLength={PASSWORD_MIN_LENGTH} />',
      'export const Shown = forwardRef(function Shown(props: Props, ref: Ref) { return <input ref={ref} type="password" {...props} /> })',
      'const v = <Shown id="v" />',
    ].join('\n')
    expect(unnamedFields(named, 'probe.tsx')).toEqual([
      'probe.tsx:1 <Input>', 'probe.tsx:2 <Input>', 'probe.tsx:3 <PasswordField>', 'probe.tsx:4 <input>', 'probe.tsx:5 <input>', 'probe.tsx:6 <input>',
      'probe.tsx:8 <SecretInput>', 'probe.tsx:11 <Shown>',
    ])
    expect(fieldsWithoutFloor(named, 'probe.tsx')).toEqual([])
    expect([...forwardingComponents([{ rel: 'probe.tsx', source: named }]).keys()].sort()).toEqual(['SecretInput', 'Shown'])
    // Undefined, null and void name nothing (the review of 3a1368ec): the field is unnamed and its component forwards
    // nothing. A PasswordField is a field with no forwarders handed in at all.
    const nothing = [
      'export function LoginPage() { return <form><input id="a" type="password" autoComplete={undefined} /></form> }',
      'export function ResetPage() { return <form><input id="b" type="password" autoComplete={null} /></form> }',
      'export function JoinPage() { return <form><input id="c" type="password" autoComplete={void 0} /></form> }',
    ].join('\n')
    expect([unnamedFields(nothing, 'probe.tsx'), [...forwardingComponents([{ rel: 'probe.tsx', source: nothing }]).keys()]]).toEqual([
      ['probe.tsx:1 <input>', 'probe.tsx:2 <input>', 'probe.tsx:3 <input>'],
      [],
    ])
    expect(passwordFields('export const F = () => <PasswordField id="w" />', 'probe.tsx', new Map()).map((field) => field.kind)).toEqual(['unnamed'])
    // CODE_CHECKED's check is read on the syntax tree: a comment or a string does not count.
    expect(checksFloorInCode('// if (next.length < PASSWORD_MIN_LENGTH) {}\nconst s = "next.length < PASSWORD_MIN_LENGTH"', 'probe.tsx')).toBe(false)
    expect(checksFloorInCode('if (next.length < PASSWORD_MIN_LENGTH) {}', 'probe.tsx')).toBe(true)
    const python = [
      'def validate(value: str) -> str:',
      '    """Doc.',
      '',
      '    More doc."""',
      '    # a note',
      '    _reject_letters_only(value)',
      '    return value',
      '',
      'class UserCreate(BaseModel):',
      '    @field_validator("password")',
      '    @classmethod',
      '    def check(cls, value: str) -> str:',
      '        if value.isalpha():',
      '            raise ValueError("Add a digit.")',
      '        return validate_password_strength(value)',
      '',
      '    @field_validator("email")',
      '    @classmethod',
      '    def normalize(cls, value: str) -> str:',
      '        return value.strip()',
    ].join('\n')
    // A helper call is a statement of the body; the docstring and the comment are not.
    expect(pythonBody(python, /^def validate\b/)).toEqual(['_reject_letters_only(value)', 'return value'])
    expect(passwordValidators(python)).toEqual(['("password") if value.isalpha(): / raise ValueError("Add a digit.") / return validate_password_strength(value)'])
  })

  it('reads every value an autoComplete can render, flags a field one value leaves unnamed, and fails loudly on a form it cannot evaluate', () => {
    // Each form with its own field (Codex on 77b306f6: a mixed ternary passed, because one valid branch classed it new).
    const family = [
      "import { useContext, useMemo, useState } from 'react'",
      "import { SHARED_MODE } from '@/lib/elsewhere'",
      "const NEW = 'new-password'",
      "const BLANK = ''",
      "const MODES = { reset: 'new-password', login: 'current-password' } as const",
      "const MIXED = { reset: 'new-password', off: 'off' } as const",
      "const pick = (reset: boolean) => (reset ? 'new-password' : 'current-password')",
      "const pickOff = (reset: boolean) => (reset ? 'new-password' : 'off')",
      'function echo(value: string) { return value }',
      "function maybe(reset: boolean) { if (reset) return 'new-password' }",
      `const many = (n: number) => \`${['1', '3', '5', '7', '1', '3', '5'].map((digit) => `\${n ? ${digit} : ${Number(digit) + 1}}`).join('')}\``,
      "let later = 'current-password'",
      "export function Form({ reset, kind, mode = 'current-password', fallback = 'off' }: { reset: boolean; kind: 'reset' | 'login'; mode?: string; fallback?: string }) {",
      "  const local = reset ? NEW : 'current-password'",
      "  const [state] = useState('current-password')",
      '  const { mode: shared } = useContext(Settings)',
      '  return (',
      '    <form>',
      '      <input id="literal" type="password" autoComplete="current-password" />',
      "      <input id=\"braced\" type=\"password\" autoComplete={'current-password'} />",
      '      <input id="template" type="password" autoComplete={`current-password`} />',
      "      <input id=\"slot\" type=\"password\" autoComplete={`${'new'}-password`} />",
      "      <input id=\"ternary\" type=\"password\" autoComplete={reset ? 'new-password' : 'current-password'} />",
      "      <input id=\"nested\" type=\"password\" autoComplete={reset ? (kind === 'reset' ? NEW : 'current-password') : 'current-password'} />",
      "      <input id=\"or\" type=\"password\" autoComplete={BLANK || 'current-password'} />",
      "      <input id=\"nullish\" type=\"password\" autoComplete={(kind === 'reset' ? NEW : undefined) ?? 'current-password'} />",
      '      <input id="const" type="password" autoComplete={NEW} />',
      '      <input id="local" type="password" autoComplete={local} />',
      '      <input id="lookup" type="password" autoComplete={MODES[kind]} />',
      '      <input id="entry" type="password" autoComplete={MODES.login} />',
      "      <input id=\"key\" type=\"password\" autoComplete={MODES['login']} />",
      '      <input id="call" type="password" autoComplete={pick(reset)} />',
      "      <input id=\"echo\" type=\"password\" autoComplete={echo('current-password')} />",
      "      <input id=\"memo\" type=\"password\" autoComplete={useMemo(() => (reset ? NEW : 'current-password'), [reset])} />",
      "      <input id=\"inPlace\" type=\"password\" autoComplete={(() => 'current-password')()} />",
      '      <input id="prop" type="password" autoComplete={mode} />',
      "      <input id=\"codex\" type=\"password\" autoComplete={reset ? 'new-password' : 'off'} />",
      "      <input id=\"and\" type=\"password\" autoComplete={reset && 'new-password'} />",
      "      <input id=\"nestedOff\" type=\"password\" autoComplete={reset ? NEW : kind === 'login' ? 'current-password' : 'off'} />",
      "      <input id=\"orOff\" type=\"password\" autoComplete={(kind === 'reset' && NEW) || 'off'} />",
      "      <input id=\"nullishOff\" type=\"password\" autoComplete={MIXED.off ?? 'current-password'} />",
      '      <input id="lookupOff" type="password" autoComplete={MIXED[kind]} />',
      '      <input id="callOff" type="password" autoComplete={pickOff(reset)} />',
      '      <input id="fallsOff" type="password" autoComplete={maybe(reset)} />',
      "      <input id=\"templateOff\" type=\"password\" autoComplete={`${reset ? 'new' : 'no'}-password`} />",
      "      <input id=\"undefinedBranch\" type=\"password\" autoComplete={reset ? undefined : 'current-password'} />",
      "      <input id=\"nullishFalls\" type=\"password\" autoComplete={(kind === 'reset' ? NEW : undefined) ?? 'off'} />",
      '      <input id="defaultOff" type="password" autoComplete={fallback} />',
      '      <input id="imported" type="password" autoComplete={SHARED_MODE} />',
      '      <input id="let" type="password" autoComplete={later} />',
      '      <input id="unknownCall" type="password" autoComplete={String(reset)} />',
      '      <input id="method" type="password" autoComplete={NEW.trim()} />',
      '      <input id="state" type="password" autoComplete={state} />',
      '      <input id="context" type="password" autoComplete={shared} />',
      '      <input id="composedProp" type="password" autoComplete={`${kind}-password`} />',
      '      <input id="many" type="password" autoComplete={many(1)} />',
      '    </form>',
      '  )',
      '}',
      'export class Legacy extends Component<{ mode: string }> {',
      '  render() { return <input id="class" type="password" autoComplete={this.props.mode} /> }',
      '}',
      // A name destructured at any depth, out of an object or an array (#1370's sixth round), and a body that ends in every
      // path (the re-review of 6a39e259: an if/else that returns in both branches gained a phantom undefined).
      "const CONFIG = { inputs: { ac: 'new-password' }, ac: 'current-password' } as const",
      "const PAIR = ['new-password', 'off'] as const",
      "function pickEvery(r: boolean) { if (r) { return 'new-password' } else { return 'current-password' } }",
      "function pickSwitch(k: string) { switch (k) { case 'reset': return 'new-password'; default: return 'current-password' } }",
      "function pickTry() { try { return 'current-password' } catch { return 'current-password' } }",
      "function pickLoop() { for (;;) { return 'current-password' } }",
      'export function Patterns({ reset, kind }: { reset: boolean; kind: string }) {',
      '  const { inputs: { ac: nestedAc } } = CONFIG',
      "  const [arrayAc] = ['current-password']",
      "  const { missing: defaultedAc = 'current-password' } = CONFIG",
      '  const { inputs: _inputs, ...restConfig } = CONFIG',
      '  const [, second] = PAIR',
      '  const { [kind]: computedAc } = CONFIG',
      '  let { ac: letAc } = CONFIG',
      '  const [, ...tail] = PAIR',
      '  const { ac: importedAc } = SHARED_CONFIG',
      '  return (',
      '    <form>',
      '      <input id="nestedPattern" type="password" autoComplete={nestedAc} />',
      '      <input id="arrayPattern" type="password" autoComplete={arrayAc} />',
      '      <input id="patternDefault" type="password" autoComplete={defaultedAc} />',
      '      <input id="memberPath" type="password" autoComplete={CONFIG.inputs.ac} />',
      '      <input id="objectRest" type="password" autoComplete={restConfig.ac} />',
      '      <input id="takenFromRest" type="password" autoComplete={restConfig.inputs} />',
      '      <input id="arrayOff" type="password" autoComplete={second} />',
      '      <input id="everyBranch" type="password" autoComplete={pickEvery(reset)} />',
      '      <input id="switchDefault" type="password" autoComplete={pickSwitch(kind)} />',
      '      <input id="tryCatch" type="password" autoComplete={pickTry()} />',
      '      <input id="loopReturns" type="password" autoComplete={pickLoop()} />',
      '      <input id="computedPattern" type="password" autoComplete={computedAc} />',
      '      <input id="letPattern" type="password" autoComplete={letAc} />',
      '      <input id="arrayRestValue" type="password" autoComplete={tail[0]} />',
      '      <input id="importedPattern" type="password" autoComplete={importedAc} />',
      '    </form>',
      '  )',
      '}',
      'export function Nested({ input: { ac } }: { input: { ac?: string } }) { return <input id="fromPropNested" type="password" autoComplete={ac} /> }',
    ].join('\n')
    expect(passwordFields(family, 'family.tsx', new Map()).map((field) => `${field.id} ${field.kind}`)).toEqual([
      // Read: every value names new- or current-password, or forwards the caller's.
      'literal current', 'braced current', 'template current', 'slot new', 'ternary new', 'nested new', 'or current', 'nullish new',
      'const new', 'local new', 'lookup new', 'entry current', 'key current', 'call new', 'echo current', 'memo new', 'inPlace current',
      'prop forwarded',
      // Flagged: one value names neither, in any branch.
      'codex unnamed', 'and unnamed', 'nestedOff unnamed', 'orOff unnamed', 'nullishOff unnamed', 'lookupOff unnamed', 'callOff unnamed',
      'fallsOff unnamed', 'templateOff unnamed', 'undefinedBranch unnamed', 'nullishFalls unnamed', 'defaultOff unnamed',
      // Loud: a form the evaluator cannot read.
      'imported unreadable', 'let unreadable', 'unknownCall unreadable', 'method unreadable', 'state unreadable', 'context unreadable',
      'composedProp unreadable', 'many unreadable', 'class unreadable',
      // Destructured at any depth: read, flagged (an array's 'off', a key the rest leaves out), or loud; and every path's end.
      'nestedPattern new', 'arrayPattern current', 'patternDefault current', 'memberPath new', 'objectRest current', 'takenFromRest unnamed',
      'arrayOff unnamed', 'everyBranch new', 'switchDefault new', 'tryCatch current',
      // A loop is read as able to end, so a function whose loop returns gains an undefined: it fails closed, a stated limit.
      'loopReturns unnamed',
      'computedPattern unreadable', 'letPattern unreadable', 'arrayRestValue unreadable', 'importedPattern unreadable', 'fromPropNested unreadable',
    ])
    expect(unnamedFields(family, 'family.tsx', new Map())[0]).toBe('family.tsx:37 <input>')
    expect(unreadableFields(family, 'family.tsx', new Map())).toEqual([
      'family.tsx:49 <input> autoComplete is a form this reader cannot evaluate: SHARED_MODE (a name from another module, or a global)',
      'family.tsx:50 <input> autoComplete is a form this reader cannot evaluate: later (a let or a var, which can change)',
      'family.tsx:51 <input> autoComplete is a form this reader cannot evaluate: String(reset) (a call this reader cannot follow)',
      'family.tsx:52 <input> autoComplete is a form this reader cannot evaluate: NEW.trim() (a call this reader cannot follow)',
      'family.tsx:53 <input> autoComplete is a form this reader cannot evaluate: state (an object this reader cannot follow)',
      'family.tsx:54 <input> autoComplete is a form this reader cannot evaluate: shared (an object this reader cannot follow)',
      'family.tsx:55 <input> autoComplete is a form this reader cannot evaluate: `${kind}-password` (a forwarded value composed into text)',
      expect.stringMatching(/^family\.tsx:56 <input> autoComplete is a form this reader cannot evaluate: `.*` \(more than 64 values\)$/),
      'family.tsx:61 <input> autoComplete is a form this reader cannot evaluate: this.props.mode (an object this reader cannot follow)',
      "family.tsx:92 <input> autoComplete is a form this reader cannot evaluate: computedAc (a computed key or an array's rest, destructured)",
      'family.tsx:93 <input> autoComplete is a form this reader cannot evaluate: letAc (a let or a var, which can change)',
      'family.tsx:94 <input> autoComplete is a form this reader cannot evaluate: tail[0] (an object this reader cannot follow)',
      'family.tsx:95 <input> autoComplete is a form this reader cannot evaluate: importedAc (an object this reader cannot follow)',
      'family.tsx:99 <input> autoComplete is a form this reader cannot evaluate: ac (a value destructured from inside a prop)',
    ])
    // The floor follows a new-password value in any branch, a mixed one included.
    expect(fieldsWithoutFloor(family, 'family.tsx', new Map())).toContain('family.tsx:37 <input>')
  })

  it('follows a forwarded autoComplete to every caller, under every name a caller renders its component by', () => {
    const secret = [
      "export default function Secret({ mode = 'current-password' }: { mode?: string }) { return <input id=\"secretInput\" type=\"password\" autoComplete={mode} /> }",
      "export const Plain = (props: { ac?: string }) => <input id=\"plainInput\" type=\"password\" autoComplete={props.ac ?? 'current-password'} />",
      'export const Wrapped = withTheme((props: { ac?: string }) => <input id="wrappedInput" type="password" autoComplete={props.ac} />)',
      'export const Fields = { Hidden: (props: { ac?: string }) => <input id="hiddenInput" type="password" autoComplete={props.ac} /> }',
      'export function Spread(props: { autoComplete?: string }) { return <input {...props} id="spreadInput" type="password" /> }',
      'export function Renamed({ which }: { which?: string }) { return <Secret id="renamedSecret" mode={which} /> }',
      // Read where they render: a rest without the key, an invalid fallback, a const object spread in, a spread unread.
      'export function Swallow({ autoComplete, ...rest }: { autoComplete?: string }) { return <input {...rest} id="swallow" type="password" /> }',
      "export const BadFallback = (props: { ac?: string }) => <input id=\"badFallback\" type=\"password\" autoComplete={props.ac ?? 'off'} />",
      "const NEW_ATTRS = { autoComplete: 'new-password' } as const",
      'export function FromConst() { return <input {...NEW_ATTRS} id="fromConst" type="password" /> }',
      "export function FromCall() { return <input {...register('password')} id=\"fromCall\" type=\"password\" /> }",
      // Loud: a prop of a parameter after the first, and one forwarded from a function no caller can name.
      'export function Second(label: string, props: { ac?: string }) { return <input id="second" type="password" autoComplete={props.ac} /> }',
      'export function Rows({ items }: { items: Array<{ ac: string }> }) { return <>{items.map((item) => <input id="callback" type="password" autoComplete={item.ac} />)}</> }',
    ].join('\n')
    const barrel = ["export { default as Hidden2 } from './secret'", "export { Plain as Bare } from './secret'"].join('\n')
    const page = [
      "import Pw from '@/features/auth/components/PasswordField'",
      "import Shh, { Plain as Simple, Wrapped, Fields, Spread, Renamed } from './secret'",
      "import * as All from './secret'",
      "import { Hidden2, Bare } from './index'",
      'const Alias = Simple',
      'const Memo = memo(Shh)',
      "const Lazy = dynamic(() => import('./secret'))",
      'const Either = flag ? Shh : Simple',
      'export function Page() {',
      '  return (',
      '    <>',
      '      <Pw id="pw" autoComplete="off" />',
      '      <Shh id="shh" mode="off" />',
      '      <Simple id="simple" ac="off" />',
      '      <All.Plain id="all" ac="off" />',
      '      <Hidden2 id="hidden2" mode="off" />',
      '      <Bare id="bare" ac="off" />',
      '      <Alias id="alias" ac="off" />',
      '      <Memo id="memo" mode="off" />',
      '      <Lazy id="lazy" mode="off" />',
      '      <Either id="either" ac="current-password" />',
      '      <Wrapped id="wrapped" ac="off" />',
      '      <Fields.Hidden id="entry" ac="off" />',
      '      <Spread id="spread" autoComplete="off" />',
      '      <Renamed id="renamed" which="off" />',
      "      {Shh({ id: 'called', mode: 'off' })}",
      "      {createElement(Simple, { id: 'created', ac: 'off' })}",
      "      {createElement('input', { id: 'createdInput', type: 'password', autoComplete: 'off' })}",
      '      <Shh id="good" mode="new-password" />',
      '      <Simple id="current" ac="current-password" />',
      '    </>',
      '  )',
      '}',
    ].join('\n')
    // Not read, each a limit the header states: a clone's override (lint's: elements-built-with-jsx refuses
    // cloneElement outside its one allowlisted file), an `as` prop of a component no file read declares, a component
    // loaded by a `.then`, a `type` forwarded under another prop's name or carried only by a spread the reader cannot
    // follow, and a value written to the DOM.
    const gaps = [
      "import { cloneElement } from 'react'",
      "import { Plain } from './secret'",
      "const Then = dynamic(() => import('./secret').then((m) => m.Plain))",
      "function TypeKind({ kind }: { kind: string }) { return <input type={kind} autoComplete=\"off\" /> }",
      'export function Gaps() {',
      "  ref.current?.setAttribute('autocomplete', 'off')",
      '  return (',
      '    <>',
      "      {cloneElement(<Plain id=\"cloned\" ac=\"current-password\" />, { ac: 'off' })}",
      '      <Box as={Plain} id="as" ac="off" />',
      '      <Then id="then" ac="off" />',
      '      <TypeKind kind="password" />',
      "      <input {...register('password')} id=\"registered\" />",
      '    </>',
      '  )',
      '}',
    ].join('\n')
    const sources = [
      { rel: 'plants/secret.tsx', source: secret },
      { rel: 'plants/index.ts', source: barrel },
      { rel: 'plants/page.tsx', source: page },
      { rel: 'plants/gaps.tsx', source: gaps },
    ]
    const forwarders = forwardersOf(sources)
    const kinds = (rel: string, source: string) => passwordFields(source, rel, forwarders).map((field) => `${field.id} ${field.kind}`)
    expect(kinds('plants/page.tsx', page)).toEqual([
      'pw unnamed', 'shh unnamed', 'simple unnamed', 'all unnamed', 'hidden2 unnamed', 'bare unnamed', 'alias unnamed', 'memo unnamed',
      'lazy unnamed', 'either current', 'wrapped unnamed', 'entry unnamed', 'spread unnamed', 'renamed unnamed', 'called unnamed',
      'created unnamed', 'createdInput unnamed', 'good new', 'current current',
    ])
    expect(kinds('plants/secret.tsx', secret)).toEqual([
      'secretInput forwarded', 'plainInput forwarded', 'wrappedInput forwarded', 'hiddenInput forwarded', 'spreadInput forwarded',
      'renamedSecret forwarded', 'swallow unnamed', 'badFallback unnamed', 'fromConst new', 'fromCall unreadable', 'second unreadable',
      'callback unreadable',
    ])
    expect(kinds('plants/gaps.tsx', gaps)).toEqual(['cloned current'])
    expect(Object.fromEntries([...forwardingComponents(sources)].map(([name, props]) => [name, [...props]]))).toEqual({
      Secret: ['mode'], Plain: ['ac'], Wrapped: ['ac'], 'Fields.Hidden': ['ac'], Spread: ['autoComplete'], Renamed: ['which'], BadFallback: ['ac'],
    })
    // A forwarding component nothing renders is a field no caller's value reaches: it fails (the plants' own, so a
    // component the app adds never reads as unrendered here).
    expect(unrenderedForwarders(sources, forwardingComponents(sources))).toEqual(['BadFallback'])
  })

  it('leaves an element built by a factory to lint, which refuses it: elements-built-with-jsx (Codex on 44229515)', { timeout: 30_000 }, async () => {
    // Codex's form: createElement imported under another name builds a password input with no JSX. The scan reads JSX,
    // and createElement or jsx called by those names; it follows no other name of a factory, since the lint rule
    // elements-built-with-jsx (eslint.designRules.mjs) refuses every one in app code, this one included.
    const factory = [
      "import { createElement as h } from 'react'",
      'export default function FactoryField() {',
      "  return h('input', { id: 'factory', type: 'password', autoComplete: 'off' })",
      '}',
      '',
    ].join('\n')
    const rel = 'app/factory-field.tsx'
    expect(passwordFields(factory, rel, forwardersFor(factory, rel)), 'not reached by the scan').toEqual([])
    const [linted] = await new ESLint({ cwd: frontendDir }).lintText(factory, { filePath: path.join(frontendDir, rel) })
    expect(linted.messages.filter((m) => m.ruleId === 'earningsnerd/elements-built-with-jsx').map((m) => `${m.line} ${m.message.split(':')[0]}`), 'refused by lint').toEqual([
      '1 createElement, imported from react',
    ])
  })

  it('follows a component reached through a binding pattern, a lookup or a prop its callers hand it', () => {
    // Codex on 6a39e259: a forwarder destructured out of an object (`const { Secret } = Fields`) passed `mode="off"`; and the
    // re-review of 6a39e259: an object of components imported under an alias (`<F.Hidden>`). Each form with its own field.
    const kit = [
      "export const Plain = (props: { ac?: string }) => <input id=\"plainInput\" type=\"password\" autoComplete={props.ac ?? 'current-password'} />",
      'export const Fields = { Hidden: (props: { ac?: string }) => <input id="hiddenInput" type="password" autoComplete={props.ac} /> }',
      'export const Kit = { inputs: { Deep: (props: { ac?: string }) => <input id="deepInput" type="password" autoComplete={props.ac} /> } }',
      'const Local = { Inner: (props: { ac?: string }) => <input id="innerInput" type="password" autoComplete={props.ac} /> }',
      'const { Inner } = Local',
      'export const UseInner = () => <Inner id="sameFile" ac="off" />',
      'export const ByName = () => <Local.Inner id="innerByName" ac="current-password" />',
    ].join('\n')
    const barrel = "export { Fields as Kit2 } from './kit'"
    const page = [
      "import { Plain, Fields, Kit, Fields as F } from './kit'",
      "import * as All from './kit'",
      "import { Kit2 } from './index'",
      'const { Hidden } = Fields',
      'const { Hidden: Renamed } = Fields',
      'const { inputs: { Deep } } = Kit',
      'const { Missing = Plain } = Fields',
      'const [First] = [Plain]',
      'const { Plain: FromNamespace } = All',
      'const { Hidden: FromReexport } = Kit2',
      'const PICK = { plain: Plain }',
      'function Frame({ Field, ac }: { Field: Comp; ac?: string }) { return <Field id="framedInner" ac={ac} /> }',
      'function FrameLiteral({ Field }: { Field: Comp }) { return <Field id="framedLiteral" ac="off" /> }',
      'function Box({ as: As, ...rest }: { as: Comp; ac?: string }) { return <As {...rest} id="boxedInner" /> }',
      "export function Page({ which }: { which: 'plain' }) {",
      '  const Picked = PICK[which]',
      '  return (',
      '    <>',
      '      <Hidden id="destructured" ac="off" />',
      '      <Renamed id="renamedKey" ac="off" />',
      '      <Deep id="nested" ac="off" />',
      '      <Missing id="defaulted" ac="off" />',
      '      <First id="arrayed" ac="off" />',
      '      <FromNamespace id="fromNamespace" ac="off" />',
      '      <FromReexport id="fromReexport" ac="off" />',
      '      <F.Hidden id="aliasObject" ac="off" />',
      '      <Picked id="picked" ac="off" />',
      '      <Frame id="framed" Field={Plain} ac="off" />',
      '      <FrameLiteral Field={Plain} />',
      '      <Box id="boxed" as={Plain} ac="off" />',
      '      <Hidden id="destructuredValid" ac="current-password" />',
      '    </>',
      '  )',
      '}',
    ].join('\n')
    // Not read, each a limit the header states: a computed key, a `let`, a component out of a call, an array's rest.
    const gaps = [
      "import { Fields } from './kit'",
      "export function Gaps({ key }: { key: 'Hidden' }) {",
      '  const { [key]: Computed } = Fields',
      '  let { Hidden: Changing } = Fields',
      '  const { Hidden: FromHook } = useFields()',
      '  const [, ...others] = [Fields.Hidden]',
      '  const [Rested] = others',
      '  return (',
      '    <>',
      '      <Computed id="computedKey" ac="off" />',
      '      <Changing id="letPattern" ac="off" />',
      '      <FromHook id="fromHook" ac="off" />',
      '      <Rested id="arrayRest" ac="off" />',
      '    </>',
      '  )',
      '}',
    ].join('\n')
    const sources = [
      { rel: 'patterns/kit.tsx', source: kit },
      { rel: 'patterns/index.ts', source: barrel },
      { rel: 'patterns/page.tsx', source: page },
      { rel: 'patterns/gaps.tsx', source: gaps },
    ]
    const forwarders = forwardersOf(sources)
    const kinds = (rel: string, source: string) => passwordFields(source, rel, forwarders).map((field) => `${field.id} ${field.kind}`)
    expect(kinds('patterns/kit.tsx', kit)).toEqual([
      'plainInput forwarded', 'hiddenInput forwarded', 'deepInput forwarded', 'innerInput forwarded', 'sameFile unnamed', 'innerByName current',
    ])
    expect(kinds('patterns/page.tsx', page)).toEqual([
      'framedInner forwarded', 'framedLiteral unnamed', 'boxedInner forwarded',
      'destructured unnamed', 'renamedKey unnamed', 'nested unnamed', 'defaulted unnamed', 'arrayed unnamed', 'fromNamespace unnamed',
      'fromReexport unnamed', 'aliasObject unnamed', 'picked unnamed', 'framed unnamed', 'boxed unnamed', 'destructuredValid current',
    ])
    expect(kinds('patterns/gaps.tsx', gaps)).toEqual([])
    expect(Object.fromEntries([...forwardingComponents(sources)].map(([name, props]) => [name, [...props]]))).toEqual({
      Plain: ['ac'], 'Fields.Hidden': ['ac'], 'Kit.inputs.Deep': ['ac'], 'Local.Inner': ['ac'], Frame: ['ac'], Box: ['ac'],
    })
    expect(forwardingComponents(sources).passes.get('Frame#Field')).toEqual(['Plain'])
    expect(unrenderedForwarders(sources, forwardingComponents(sources))).toEqual([])
  })

  it('follows a prop handed down any number of components, and fails loudly where a chain runs past what it follows', () => {
    // Codex on 3ebe222b: `Plain` handed from F9 down to F0, which renders `<Field ac="off" />`, took ten rounds to reach F0,
    // and the propagation stopped after eight without a word, so the invalid field was never read; Plain's separate valid
    // render kept the unrendered-forwarder check quiet. It now runs to its fixed point; F0 is declared first, so each round
    // hands Plain one component further down.
    const kit = "export const Plain = (props: { ac?: string }) => <input id=\"plainInput\" type=\"password\" autoComplete={props.ac ?? 'current-password'} />"
    const handDown = [
      "import { Plain } from './kit'",
      'function F0({ Field }: { Field: Comp }) { return <Field id="handedDown" ac="off" /> }',
      ...Array.from({ length: 9 }, (_, i) => `function F${i + 1}({ Field }: { Field: Comp }) { return <F${i} Field={Field} /> }`),
      'export const Top = () => <><F9 Field={Plain} /><Plain id="plainValid" ac="current-password" /></>',
    ].join('\n')
    // Each cap the follower keeps against a cycle (of consts, keys, patterns or modules) fails loudly where it is reached,
    // with its own component and field, through each way a name reaches a field: a tag, `createElement`, a call named as a
    // component, and a prop its callers hand. The props a component is handed stay finite: a name it hands a member of
    // its own prop back to itself grows a step a round, and past eight steps it is one the follower cannot follow.
    const reach = [
      "import { Plain } from './kit'",
      "import { Ghost } from './loopA'",
      'const Kit = { field: Plain }',
      'const LoopA = LoopB',
      'const LoopB = LoopA',
      'const KeysA = KeysB',
      'const KeysB = KeysA',
      ...Array.from({ length: 7 }, (_, i) => `const Member${i} = Member${i + 1}`),
      'const Member7 = Kit.field',
      'const { field: Destructured } = Kit',
      ...Array.from({ length: 7 }, (_, i) => `const Pattern${i} = Pattern${i + 1}`),
      'const Pattern7 = Destructured',
      'function Frame({ Field }: { Field: Comp }) { return <Field id="patternChain" ac="off" /> }',
      'function Grow({ Node }: { Node: Comp }) { return <><Node id="grown" ac="off" /><Grow Node={Node.Inner} /></> }',
      // The limit: a component reached past the follower's reach and called under a lowercase name reads as no field.
      ...Array.from({ length: 8 }, (_, i) => `const lowered${i} = lowered${i + 1}`),
      'const lowered8 = Plain',
      "export function Reach({ which }: { which: 'field' }) {",
      '  const ByKey = KeysA[which]',
      '  return (',
      '    <>',
      '      <LoopA id="constCycle" ac="off" />',
      "      {createElement(Ghost, { id: 'exportCycle', ac: 'off' })}",
      "      {ByKey({ id: 'keyCycle', ac: 'off' })}",
      '      <Member0 id="memberChain" ac="off" />',
      '      <Frame Field={Pattern0} />',
      '      <Grow Node={Plain} />',
      "      {lowered0({ id: 'loweredChain', ac: 'off' })}",
      '    </>',
      '  )',
      '}',
    ].join('\n')
    const sources = [
      { rel: 'reach/kit.tsx', source: kit },
      { rel: 'reach/handdown.tsx', source: handDown },
      { rel: 'reach/loopA.ts', source: "export * from './loopB'" },
      { rel: 'reach/loopB.ts', source: "export * from './loopA'" },
      { rel: 'reach/page.tsx', source: reach },
    ]
    const forwarders = forwardersOf(sources)
    const kinds = (rel: string, source: string) => passwordFields(source, rel, forwarders).map((field) => `${field.id} ${field.kind}`)
    expect(kinds('reach/handdown.tsx', handDown)).toEqual(['handedDown unnamed', 'plainValid current'])
    expect(forwardingComponents(sources).passes.get('F0#Field')).toContain('Plain')
    expect(kinds('reach/page.tsx', reach)).toEqual(['patternChain unreadable', 'grown unreadable', 'constCycle unreadable', 'exportCycle unreadable', 'keyCycle unreadable', 'memberChain unreadable'])
    const lineWith = (needle: string) => reach.split('\n').findIndex((line) => line.includes(needle)) + 1
    const stopped = (field: string, tag: string, where: string) =>
      `reach/page.tsx:${lineWith(field)} <${tag}> autoComplete is a form this reader cannot evaluate: ${tag} (a component read through more steps than this reader follows, at ${where})`
    expect(unreadableFields(reach, 'reach/page.tsx', forwarders)).toEqual([
      // A prop its callers hand (patternNames: the destructured name eight consts in).
      stopped('id="patternChain"', 'Field', `reach/page.tsx:${lineWith('const { field: Destructured }')}`),
      // The name a component hands a member of its own prop back to itself, past eight member steps.
      stopped('id="grown"', 'Node', `reach/page.tsx:${lineWith('<Grow Node={Node.Inner} />')}`),
      // A tag (heldNames: the cycle of consts stops on the const its ninth step reaches).
      stopped('id="constCycle"', 'LoopA', `reach/page.tsx:${lineWith('const LoopA = LoopB')}`),
      // createElement (declaredNames: the cycle of `export *` stops in the module its ninth step reaches).
      stopped("id: 'exportCycle'", 'Ghost', 'reach/loopB.ts'),
      // A call named as a component (objectKeys: a key the follower cannot name, read through the cycle of consts).
      stopped("id: 'keyCycle'", 'ByKey', `reach/page.tsx:${lineWith('const KeysB = KeysA')}`),
      // A tag again (namesAt: the member eight consts in).
      stopped('id="memberChain"', 'Member0', `reach/page.tsx:${lineWith('const Member7 = Kit.field')}`),
    ])
    expect(Object.fromEntries([...forwardingComponents(sources)].map(([name, props]) => [name, [...props]]))).toEqual({ Plain: ['ac'] })
    expect(unrenderedForwarders(sources, forwardingComponents(sources))).toEqual([])
  })

  it('reads a container only while nothing can change it after its initializer, and a parameter or props only while its function cannot', () => {
    // Codex on 28b69145: `const modes = ['new-password']; modes[0] = 'off'` passed, read from its initializer. A const binding stops
    // a reassignment of the name, not a write into what it holds. Each form with its own container and its own field: read (every
    // use of the container, an alias or a part of it reads), or loud (one does not), with what that use does and its line.
    type Verdict = 'new' | 'current' | 'forwarded' | { how: string; at: string; props?: true } | 'reassigned'
    // [field id, the module-level code, the autoComplete read (a spread where it starts `{...`; none where the code renders the field)]
    const rows: Array<[id: string, code: string, value: string | undefined, verdict: Verdict]> = [
      // Read: `as const` is types only; the freeze is read (it hands back what it is handed); a method of its array that only
      // reads it and a callback that reads each element; a same-file function that only reads its parameter; another object
      // that holds it and is only read; a `let` whose every use reads; a spread copy (written, it is the copy); an entry that
      // cannot reach it as `this`; a spread onto an intrinsic element; a prop called (a caller's function).
      ['sealed', "const SEALED = ['new-password'] as const", 'SEALED[0]', 'new'],
      ['frozen', "const FROZEN = Object.freeze({ ac: 'current-password' })", 'FROZEN.ac', 'current'],
      ['scanned', "const SCANNED = ['current-password']; export const scanned = SCANNED.includes('off') || SCANNED.map((mode) => mode.length)", 'SCANNED[0]', 'current'],
      ['handed', "const HANDED = { ac: 'current-password' }; function readAc(o: { ac: string }) { return o.ac }", 'readAc(HANDED)', 'current'],
      ['outer', "const INNER = { ac: 'current-password' }; const OUTER = { inner: INNER }", 'OUTER.inner.ac', 'current'],
      ['peeked', "const PEEKED = { ac: 'current-password' }; let peek = PEEKED; export const peekAc = peek.ac", 'PEEKED.ac', 'current'],
      ['shallow', "const SHALLOW = { ac: 'current-password' }; const shallowCopy = { ...SHALLOW }; shallowCopy.ac = 'off'", 'SHALLOW.ac', 'current'],
      ['arrows', "const ARROWS = { ac: 'current-password', bump: () => 1 }; ARROWS.bump()", 'ARROWS.ac', 'current'],
      ['spreadRead', "const SPREAD_READ = { autoComplete: 'current-password' }", '{...SPREAD_READ}', 'current'],
      ['readProps', "export const ReadProps = (props: { ac?: string; onPick: () => void }) => { props.onPick(); return <input id=\"readProps\" type=\"password\" autoComplete={props.ac} /> }", undefined, 'forwarded'],
      // Written after its initializer: an entry assigned (`=`, compound, logical), incremented, deleted, or assigned by
      // destructuring or a loop.
      ['codex', "const modes = ['new-password']; modes[0] = 'off'", 'modes[0]', { how: 'an entry assigned', at: "modes[0] = 'off'" }],
      ['compound', "const COMPOUND = { ac: 'current' }; COMPOUND.ac += '-password'", 'COMPOUND.ac', { how: 'an entry assigned', at: 'COMPOUND.ac +=' }],
      ['logical', "const LOGICAL = { ac: '' }; LOGICAL.ac ||= 'off'", 'LOGICAL.ac', { how: 'an entry assigned', at: 'LOGICAL.ac ||=' }],
      ['counted', "const COUNTED = { ac: 'current-password', n: 0 }; COUNTED.n++", 'COUNTED.ac', { how: 'an entry incremented or decremented', at: 'COUNTED.n++' }],
      ['deleted', "const DELETED = { ac: 'current-password' }; delete DELETED.ac", 'DELETED.ac', { how: 'an entry deleted', at: 'delete DELETED.ac' }],
      ['destructured', "const DESTRUCTURED = ['current-password']; ;[DESTRUCTURED[0]] = ['off']", 'DESTRUCTURED[0]', { how: 'an entry assigned by destructuring', at: '[DESTRUCTURED[0]] =' }],
      ['looped', "const LOOPED = ['current-password']; for (LOOPED[0] of ['off']) {}", 'LOOPED[0]', { how: 'an entry assigned by a loop', at: 'for (LOOPED[0]' }],
      // A method of its own that may write it: each an array has that writes, and an object's method that reads `this`.
      ...['push', 'pop', 'shift', 'unshift', 'splice', 'sort', 'reverse', 'fill', 'copyWithin'].map((method): [string, string, string, Verdict] => [
        method, `const M_${method.toUpperCase()} = ['current-password', 'new-password']; M_${method.toUpperCase()}.${method}(${method === 'push' || method === 'unshift' || method === 'fill' ? "'off'" : method === 'splice' || method === 'copyWithin' ? '0, 1' : ''})`,
        `M_${method.toUpperCase()}[0]`, { how: 'a method called on it', at: `M_${method.toUpperCase()}.${method}(` },
      ]),
      ['self', "const SELF = { ac: 'current-password', reset() { this.ac = 'off' } }; SELF.reset()", 'SELF.ac', { how: 'a method called on it', at: 'SELF.reset()' }],
      // Handed to a call that may write it: Object's and Reflect's writers, a function of another module, a part of it, and a
      // same-file function that writes its parameter; and a freeze, which is shallow.
      ...[
        ['assign', 'Object.assign(X, { ac: "off" })'], ['defineProperty', 'Object.defineProperty(X, "ac", { value: "off" })'],
        ['defineProperties', 'Object.defineProperties(X, { ac: { value: "off" } })'], ['setPrototypeOf', 'Object.setPrototypeOf(X, null)'],
        ['reflectSet', 'Reflect.set(X, "ac", "off")'], ['reflectDelete', 'Reflect.deleteProperty(X, "ac")'],
        ['reflectDefine', 'Reflect.defineProperty(X, "ac", { value: "off" })'], ['registered', 'register(X)'],
      ].map(([id, call]): [string, string, string, Verdict] => {
        const name = `C_${id.toUpperCase()}`
        return [id, `const ${name} = { ac: 'current-password' }; ${call.replace('X', name)}`, `${name}.ac`, { how: 'handed to a call', at: call.replace('X', name) }]
      }),
      ['part', "const PART = { inputs: { ac: 'current-password' } }; register(PART.inputs)", 'PART.inputs.ac', { how: 'handed to a call', at: 'register(PART.inputs)' }],
      ['clobbered', "function clobber(o: { ac: string }) { o.ac = 'off' }; const CLOBBERED = { ac: 'current-password' }; clobber(CLOBBERED)", 'CLOBBERED.ac', { how: 'an entry assigned', at: 'function clobber' }],
      ['frozenDeep', "const FROZEN_DEEP = Object.freeze({ inputs: { ac: 'current-password' } }); FROZEN_DEEP.inputs.ac = 'off'", 'FROZEN_DEEP.inputs.ac', { how: 'an entry assigned', at: 'FROZEN_DEEP.inputs.ac =' }],
      // Written through an alias, a destructured part, a copy that holds a part, a rest (read as it without the keys taken), a
      // `let`, or another object it is stored in.
      ['aliased', "const ALIASED = ['current-password']; const alias = ALIASED; alias[0] = 'off'", 'ALIASED[0]', { how: 'an entry assigned', at: 'alias[0] =' }],
      ['nested', "const NESTED = { inputs: { ac: 'current-password' } }; const { inputs } = NESTED; inputs.ac = 'off'", 'NESTED.inputs.ac', { how: 'an entry assigned', at: "; inputs.ac = 'off'" }],
      ['spreadPart', "const SPREAD_PART = { inputs: { ac: 'current-password' } }; const partCopy = { ...SPREAD_PART }; partCopy.inputs.ac = 'off'", 'SPREAD_PART.inputs.ac', { how: 'an entry assigned', at: 'partCopy.inputs.ac =' }],
      ['restOf', "const REST_SOURCE = { ac: 'current-password', other: 1 }; const { other, ...restOf } = REST_SOURCE; restOf.ac = 'off'", 'REST_SOURCE.ac', { how: 'an entry assigned', at: 'restOf.ac =' }],
      ['viaLet', "const VIA_LET = { ac: 'current-password' }; let held = VIA_LET; held.ac = 'off'", 'VIA_LET.ac', { how: 'an entry assigned', at: 'held.ac =' }],
      // A `var` is not followed: it is seen past the block the resolver reads it in.
      ['varred', "const VARRED = { ac: 'current-password' }; if (VARRED) { var varAlias = VARRED }; varAlias.ac = 'off'", 'VARRED.ac', { how: 'stored into a var', at: 'var varAlias' }],
      ['stored', "const STORED = { ac: 'current-password' }; const BAG = { stored: STORED }; BAG.stored.ac = 'off'", 'STORED.ac', { how: 'an entry assigned', at: 'BAG.stored.ac =' }],
      ['listed', "const LISTED = { ac: 'current-password' }; const LIST = [LISTED]; LIST[0].ac = 'off'", 'LISTED.ac', { how: 'an entry assigned', at: 'LIST[0].ac =' }],
      // Written by the callback an array method of its own hands it to: each element, or the array itself.
      ['mapped', "const MAPPED = [{ ac: 'current-password' }]; MAPPED.forEach((entry) => { entry.ac = 'off' })", 'MAPPED[0].ac', { how: 'an entry assigned', at: 'entry.ac =' }],
      ['mappedAll', "const MAPPED_ALL = ['current-password']; MAPPED_ALL.map((mode, index, all) => (all[index] = 'off'))", 'MAPPED_ALL[0]', { how: 'an entry assigned', at: 'all[index] =' }],
      // Handed where this reader cannot follow it: stored by an assignment, returned, exported, a component's prop, a part spread
      // into a component, React's ref.
      ['slotted', "const SLOTTED = { ac: 'current-password' }; let slot: object = {}; slot = SLOTTED", 'SLOTTED.ac', { how: 'stored by an assignment', at: 'slot = SLOTTED' }],
      ['returned', "const RETURNED = { ac: 'current-password' }; export function leak() { return RETURNED }", 'RETURNED.ac', { how: 'returned from a function', at: 'return RETURNED' }],
      ['exported', "export const EXPORTED = { ac: 'current-password' }", 'EXPORTED.ac', { how: 'exported, so another module may write it', at: 'export const EXPORTED' }],
      ['propped', "const PROPPED = { ac: 'current-password' }; export const propped = <Widget config={PROPPED} />", 'PROPPED.ac', { how: 'handed to a component', at: 'config={PROPPED}' }],
      ['partSpread', "const PART_SPREAD = { inputs: { ac: 'current-password' } }; export const partSpread = <Widget {...PART_SPREAD} />", 'PART_SPREAD.inputs.ac', { how: 'what it holds handed to a component', at: '<Widget {...PART_SPREAD}' }],
      ['reffed', "const REFFED = { current: null, ac: 'current-password' }; export const reffed = <div ref={REFFED} />", 'REFFED.ac', { how: 'handed to React as a ref, which writes it', at: 'ref={REFFED}' }],
      // A parameter assigned in its function, one a call binds included, and props written (through them or a rest of them).
      ['reassigned', "export function Reassigned({ mode = 'current-password' }: { mode?: string }) { mode = 'off'; return <input id=\"reassigned\" type=\"password\" autoComplete={mode} /> }", undefined, 'reassigned'],
      ['rebound', "const REBOUND = { ac: 'current-password' }; function rebind(m: { ac: string }) { m = { ac: 'off' }; return m.ac }", 'rebind(REBOUND)', 'reassigned'],
      ['reboundPart', "const REBOUND_PART = { cfg: { ac: 'current-password' } }; function rebindPart({ cfg }: { cfg: { ac: string } }) { cfg = { ac: 'off' }; return cfg.ac }", 'rebindPart(REBOUND_PART)', 'reassigned'],
      ['writtenProps', "export const WrittenProps = (props: { ac?: string }) => { props.ac = 'off'; return <input id=\"writtenProps\" type=\"password\" autoComplete={props.ac} /> }", undefined, { how: 'an entry assigned', at: "props.ac = 'off'", props: true }],
      ['restWritten', "export function RestWritten({ id, ...rest }: { id: string; autoComplete?: string }) { rest.autoComplete = 'off'; return <input {...rest} id=\"restWritten\" type=\"password\" /> }", undefined, { how: 'an entry assigned', at: "rest.autoComplete = 'off'", props: true }],
    ]
    const source = [
      ...rows.map(([, code]) => code),
      'export function Containers() {',
      '  return (',
      '    <form>',
      ...rows.flatMap(([id, , value]) =>
        value === undefined ? [] : value.startsWith('{...') ? [`      <input ${value} id="${id}" type="password" />`] : [`      <input id="${id}" type="password" autoComplete={${value}} />`]),
      '    </form>',
      '  )',
      '}',
    ]
    /** The one line that holds `needle`. */
    const lineOf = (needle: string) => {
      const hits = source.flatMap((line, index) => (line.includes(needle) ? [index + 1] : []))
      expect(hits, needle).toHaveLength(1)
      return hits[0]
    }
    const kindOf = (verdict: Verdict) => (typeof verdict === 'string' && verdict !== 'reassigned' ? verdict : 'unreadable')
    const ordered = [...rows.filter(([, , value]) => value === undefined), ...rows.filter(([, , value]) => value !== undefined)]
    const fields = passwordFields(source.join('\n'), 'containers.tsx', new Map())
    expect(fields.map((field) => `${field.id} ${field.kind}`)).toEqual(ordered.map(([id, , , verdict]) => `${id} ${kindOf(verdict)}`))
    expect(unreadableFields(source.join('\n'), 'containers.tsx', new Map())).toEqual(
      ordered.flatMap(([id, code, value, verdict]) => {
        if (typeof verdict === 'string' && verdict !== 'reassigned') return []
        const at = value === undefined ? lineOf(code) : lineOf(`id="${id}"`)
        const read = value ?? (code.includes('{...rest}') ? '{...rest}' : code.includes('props.ac') ? 'props.ac' : 'mode')
        const why = verdict === 'reassigned' ? 'a parameter assigned in its function'
          : `${verdict.props ? 'props that can change in the component' : 'a container that can change after its initializer'}: ${verdict.how}, line ${lineOf(verdict.at)}`
        const shown = id === 'rebound' ? 'm.ac' : id === 'reboundPart' ? 'cfg.ac' : read
        return [`containers.tsx:${at} <input> autoComplete is a form this reader cannot evaluate: ${shown} (${why})`]
      }),
    )
    // The follower names a component through a container the same way, and a tag, a createElement or a call named as a
    // component (a capital) through one that can change fails loudly. An export is followed (it reads an import by its
    // declaration), so a write in the importing module is a limit, planted last.
    const kit = [
      "export const Secret = ({ mode }: { mode?: string }) => <input id=\"secretInput\" type=\"password\" autoComplete={mode} />",
      'export const Quiet = (props: { mode?: string }) => <span>{props.mode}</span>',
      'const SEALED_KIT = { field: Secret }',
      'const SWAPPED = { field: Quiet }; SWAPPED.field = Secret; export const label = SWAPPED.toString()',
      'const STACK = [Quiet]; STACK.push(Secret)',
      'const LENT = { field: Quiet }; lend(LENT)',
      'const CALLS = { Field: Quiet }; CALLS.Field = Secret',
      // The limit: a component written into a container and called under a lowercase name reads as no field.
      "const lower = { field: Quiet }; lower.field = Secret; export const viaCall = lower.field({ id: 'lowerCall', mode: 'off' })",
      'function Frame({ Field }: { Field: typeof Quiet }) { return <Field id="framed" mode="off" /> }',
      'export const SHARED = { field: Quiet }',
      'export function Page() {',
      '  const [Stacked] = STACK',
      '  return (',
      '    <>',
      '      <SEALED_KIT.field id="sealedKit" mode="off" />',
      '      <SWAPPED.field id="swapped" mode="off" />',
      '      <Stacked id="stacked" mode="off" />',
      '      <LENT.field id="lent" mode="off" />',
      "      {createElement(SWAPPED.field, { id: 'created', mode: 'off' })}",
      "      {CALLS.Field({ id: 'called', mode: 'off' })}",
      '      <Frame Field={SWAPPED.field} />',
      '    </>',
      '  )',
      '}',
    ]
    const importer = ["import { SHARED, Secret } from './kit'", 'SHARED.field = Secret', 'export const Other = () => <SHARED.field id="importerWrite" mode="off" />']
    const sources = [{ rel: 'containers/kit.tsx', source: kit.join('\n') }, { rel: 'containers/importer.tsx', source: importer.join('\n') }]
    const forwarders = forwardersOf(sources)
    const kitLine = (needle: string) => kit.findIndex((line) => line.includes(needle)) + 1
    expect(passwordFields(sources[0].source, sources[0].rel, forwarders).map((field) => `${field.id} ${field.kind}`)).toEqual([
      'secretInput forwarded', 'framed unreadable', 'sealedKit unnamed', 'swapped unreadable', 'stacked unreadable', 'lent unreadable', 'created unreadable',
      'called unreadable',
    ])
    const through = (tag: string, field: string, how: string, at: string) =>
      `containers/kit.tsx:${kitLine(field)} <${tag}> autoComplete is a form this reader cannot evaluate: ${tag} (a component read through a container that can change after its initializer: ${how}, line ${kitLine(at)})`
    expect(unreadableFields(sources[0].source, sources[0].rel, forwarders)).toEqual([
      // A prop its callers hand a component read through such a container.
      through('Field', 'id="framed"', 'an entry assigned', 'SWAPPED.field = Secret'),
      through('SWAPPED.field', 'id="swapped"', 'an entry assigned', 'SWAPPED.field = Secret'),
      through('Stacked', 'id="stacked"', 'a method called on it', 'STACK.push'),
      through('LENT.field', 'id="lent"', 'handed to a call', 'lend(LENT)'),
      through('SWAPPED.field', "id: 'created'", 'an entry assigned', 'SWAPPED.field = Secret'),
      through('CALLS.Field', "id: 'called'", 'an entry assigned', 'CALLS.Field = Secret'),
    ])
    // The limit: a write in a module that imports the container is not read, so `<SHARED.field>` reads as Quiet, no field.
    expect(passwordFields(sources[1].source, sources[1].rel, forwarders)).toEqual([])
  })

  it('the strength meter says "Too short" under the minimum and scores length past it', () => {
    const field = (value: string, minLength?: number) => (
      <PasswordField id="pw" label="Password" value={value} onChange={() => {}} minLength={minLength} showStrength />
    )
    const almost = 'Ab1!'.padEnd(PASSWORD_MIN_LENGTH - 1, 'x')
    const { rerender } = render(field(almost, PASSWORD_MIN_LENGTH))
    expect(screen.getByText('Too short')).toBeInTheDocument()
    // Clearing the floor alone is one bar.
    rerender(field('a'.repeat(PASSWORD_MIN_LENGTH), PASSWORD_MIN_LENGTH))
    expect(screen.getByText('Weak')).toBeInTheDocument()
    rerender(field(`${almost}x`, PASSWORD_MIN_LENGTH))
    expect(screen.getByText('Good')).toBeInTheDocument()
    rerender(field(`${almost}xxxxx`, PASSWORD_MIN_LENGTH))
    expect(screen.getByText('Strong')).toBeInTheDocument()
    // Without the prop the meter still scores against the server's floor.
    rerender(field(almost))
    expect(screen.getByText('Too short')).toBeInTheDocument()
  })
})
