// Design gates from the 2026-10 design critique (docs: frontend/DESIGN_SYSTEM.md §4 "Callout" and
// "Filing identity"), each pinned by tests/unit/designRules.spec.ts:
//
//   no-side-stripe      (P-08) A thick left border on a rounded container is the side-tab stripe
//                       card, the strongest generic tell the critique found. Callouts are inset wells
//                       (features/summaries/components/Callout.tsx) whose tone lives in the label
//                       word; a quotation keeps its 2px bar, but never with rounded corners. The rule
//                       evaluates whole class strings the way responsive-grid-base-track does (every
//                       helper argument and template chunk together, each conditional branch with the
//                       text that is always there around it), so `border-l-4 ${tone} … rounded-xl`
//                       is caught although no single literal holds both classes. A primitive that
//                       always rounds itself (Card) needs no rounded-* beside the stripe.
//   no-form-code-badge  (P-04) A form code (the form families EDGAR writes, 10-K, 10-Q, 8-K, SC 13D,
//                       S-1, DEF 14A and their kin, FORM_CODES, and the insider forms the product
//                       writes as words, Form 3, Form 4 and Form 5) is text in the data face, never a
//                       Badge: a blue chip on 10-Q spent the status colour on a category, and a
//                       neutral one still reads as a status. The rule flags a <Badge> (or ui.Badge)
//                       that reads a filing-type field, or holds a literal form code (string,
//                       template or text), in its children or in a prop that styles it. Descriptive
//                       props (title, alt, aria-*) may name the form: they describe, not display; and
//                       a prop that neither displays nor styles (key, ref, an event handler, data-*,
//                       id) is not read.
//                       It flags a hand-rolled chip by the same reading: an HTML element whose class
//                       text sets uppercase and tracking-eyebrow, written inline or held in a binding
//                       declared in the same file (`const EYEBROW = 'uppercase tracking-eyebrow'`
//                       read as `className={EYEBROW}`; the initializer a string, a template or a
//                       cx()/clsx() call), and whose content, read through its HTML wrappers since
//                       uppercase and letter-spacing inherit (`<span>{form}</span>`, or sibling spans
//                       `<span>{form}</span><span> · Filed {ago}</span>`), opens with text or an
//                       expression that reads a form field anywhere in it (`{hit.form ?? fallback}`,
//                       `{filing.form.toUpperCase()}`) or holds a code, or text opening with one
//                       before a separator (a middot, bullet or pipe, a comma, colon or semicolon,
//                       or a dash set off by a space: `{'10-Q · Filed'}`, `10-Q - Filed`), as in
//                       `{form} • Filed {ago}`. A component, a Badge or an element that resets the
//                       face before the lead ends the reading (it is judged by its own rule or sets
//                       its own face); nothing after the lead takes the chip's face off it. A class
//                       a fixed truthiness rules out never counts (`cx({ uppercase: false })`,
//                       `cx(false && 'uppercase')`), and one it guarantees always does
//                       (`cx({ 'normal-case': 1 })`); any other string in the class counts.
//   no-unguarded-animation (P-09) Every Tailwind animation utility stops under reduced motion
//                       (WCAG 2.3.3): `motion-safe:animate-x`, or `animate-x` beside a
//                       `motion-reduce:animate-none` with the same variants in the class text that
//                       always renders with it. Same variants, because a variant can raise the
//                       animation's specificity (`dark:`, `group-hover:`) or move it later in the
//                       stylesheet (`md:`), and then a bare guard loses: `[&>:last-child]:after:
//                       animate-pulse` needs `motion-reduce:[&>:last-child]:after:animate-none`. A
//                       spinner becomes its static glyph, a skeleton a static bone, an entrance
//                       shows at once. The globals.css classes that stop themselves in a
//                       reduced-motion block (SELF_GUARDED_ANIMATIONS) need no guard; the spec holds
//                       each of them, and every other animation globals.css declares, to that block.
//   locale-pinned-numbers  A number or a time reads in one locale (en-US) whatever the viewer's browser
//                       says, so `x.toLocaleString()`, `x.toLocaleTimeString()` and
//                       `Intl.NumberFormat()`, with `new` or without it (both return the formatter),
//                       with no locale, with `undefined` for it or with an empty list (`[]`), each the
//                       browser's own locale, are banned everywhere, lib/format.ts included: it owns the
//                       formatters and pins 'en-US' itself (getFormatter), so the rule reads it as it reads
//                       the app, and a bare call added there fails too.
//                       `x.toLocaleDateString()` is not read here: eslint.config.mjs's date rule
//                       (no-restricted-syntax) bans every call of it, pinned or not, and names
//                       formatLocalDate, so reading it here too would report one call twice. The receiver's type is not read, so a Date's
//                       toLocaleString() is caught too: the message names lib/format generally (fmtCount
//                       and fmtDecimal for a number, a date helper for a date), or pass 'en-US'. A
//                       locale other than the literal 'en-US' (or a list of it) is reported too: another
//                       locale ('de-DE'), or one the scan cannot read (a variable, which may be the
//                       browser's), since the product formats numbers and times in en-US alone.
//                       `Intl.NumberFormat` reached under another name (`const { NumberFormat } = Intl`,
//                       `globalThis.Intl`) passes, which no file writes today, and so does a computed
//                       member (`n['toLocaleString']()`, `Intl['NumberFormat']`): no one writes it by
//                       accident, and a deliberate way round the rule belongs in review (an eslint-disable
//                       with its reason), not in the rule. `Intl.DateTimeFormat` is not
//                       read (its one call site, features/calendar/lib/dates.ts, pins 'en-CA').
//   no-hand-rolled-toggle-group (CO-15, CO-22, CO-25) One single-choice toggle group app-wide: the
//                       SegmentedControl (components/ui). The rule reads an element whose role is the literal
//                       "group" (role="group" or role={'group'}) and walks the children written inside it, a
//                       .map callback and a conditional included, for a <button>, <Button> or <x.Button> tag
//                       with aria-pressed written on it; one found is that control rebuilt by hand, and three
//                       such rows on the company page had drifted from it (no focus ring, a hover that darkens).
//                       Two shapes are read beyond the group's own markup. A child tag that names a component
//                       declared in the same file (a function declaration, or a const bound to an arrow or a
//                       function expression, also inside memo or forwardRef) is read through what it renders:
//                       an arrow's expression body and every return statement's argument, conditionals and
//                       logical expressions included; the name resolves through ESLint's scopes, so a prop or
//                       a parameter of that name is not the same-file component. And the DS Button imported
//                       under another name (`import { Button as X }` from @/components/ui or
//                       @/components/ui/Button) is a <Button>. The reading is one level deep and follows
//                       syntax, not data: a wrapper imported from another file, a wrapper that renders yet
//                       another wrapper, a class component, aria-pressed reaching the button through spread
//                       props, and a row without role="group" stay unread (review-checked). The primitive's
//                       own file is exempt. The one site the wider reading finds is WordingChanges.tsx's review
//                       row (LabelToggle, features/filings): its toggle clears a label that is already set, so
//                       "pressed nowhere" is a valid state, which the SegmentedControl (always one selected
//                       value) cannot hold, and the group's line carries the disable with that reason; E62
//                       (tasks/todo.md) holds the decision. A group of independent toggles (a multi-select
//                       filter row) is not this control either: disable the rule on that line with the reason.
//
// Out of scope, as for every class-string rule here: a class name assembled from fragments at
// runtime, a form code reaching a Badge through a renamed variable (data-flow, not syntax), a
// Badge imported under another name, and an animation set outside a class utility (an arbitrary
// `[animation:…]` property, an inline style). The chip check resolves a class binding declared in
// the same file only: an imported constant, a class passed in as a prop, an object of recipes
// (`styles.eyebrow`), a function's return value and a later assignment to the binding stay unread.

import { branchTexts, classUnitVisitors, parseClassToken, splitClassToken } from './eslint.gridBaseTrack.mjs'

const STRIPE_WIDTH = /^border-[ls]-(2|4|8|\[[^\]]+\])$/
const ROUNDED = /^rounded(-|$)/
const NOT_ROUNDED = /(^|-)none$/

/** Primitives that always round themselves (Card's recipe sets its radius): a stripe class on one
 *  is the stripe card with no rounded-* in sight. */
const ROUNDED_PRIMITIVES = new Set(['Card'])

/** The JSX element a class attribute sits on ("Card" for <Card> and <ui.Card>), else null. */
function elementName(node) {
  const name = node.type === 'JSXAttribute' ? node.parent?.name : null
  if (name?.type === 'JSXIdentifier') return name.name
  if (name?.type === 'JSXMemberExpression') return name.property.name
  return null
}

/** The stripe token in `classText` when it also rounds the container, else null. */
export function sideStripe(classText) {
  const tokens = classText.split(/\s+/).filter(Boolean)
  const parsed = tokens.map((raw) => ({ raw, token: parseClassToken(raw) })).filter((t) => t.token)
  const stripe = parsed.find((t) => STRIPE_WIDTH.test(t.token.utility))
  const rounded = parsed.some((t) => ROUNDED.test(t.token.utility) && !NOT_ROUNDED.test(t.token.utility))
  return stripe && rounded ? stripe.raw : null
}

export const noSideStripe = {
  meta: {
    type: 'problem',
    docs: { description: 'No side-tab stripe: a thick left border on a rounded container.' },
    schema: [],
    messages: {
      stripe:
        '{{token}} on a rounded container is the side-tab stripe card. Use the Callout inset well ' +
        '(tone in the label word) or a hairline section; a quotation keeps a 2px bar without rounding.',
    },
  },
  create(context) {
    return classUnitVisitors((node, pieces) => {
      const rounds = ROUNDED_PRIMITIVES.has(elementName(node))
      for (const text of branchTexts(pieces)) {
        const token = sideStripe(rounds ? `${text} rounded` : text)
        if (token !== null) {
          context.report({ node, messageId: 'stripe', data: { token } })
          return
        }
      }
    })
  },
}

const FORM_FIELD = /^(filing_type|filingType|form_type|formType|form)$/
// Props that describe an element rather than display it: a tooltip, alt text, an accessible name. They may name the form.
const DESCRIPTIVE_PROP = /^(title|alt|aria-[a-z]+)$/
// Props that neither display nor style anything: React's key and ref, an event handler, a data attribute, an id. A form
// field read there puts no form on the badge (`<Badge key={filing.form}>Current</Badge>`); every other prop is read,
// so a prop the Badge renders or styles by (children, icon, variant, className, style) counts and the gate fails closed.
const UNRENDERED_PROP = /^(key|ref|id|on[A-Z]\w*|data-[\w-]+)$/
const isBadge = (name) =>
  (name?.type === 'JSXIdentifier' && name.name === 'Badge') ||
  (name?.type === 'JSXMemberExpression' && name.property.name === 'Badge')
// The form families the product renders, written as EDGAR writes them: the periodic and current reports
// (10-K and 10-Q with their transition forms 10-KT and 10-QT, 20-F, 40-F, 11-K and 11-KT, 8-K, 6-K, 1-A, 1-K,
// 1-U), the registration statements (S-1 to
// S-11 and S-20, SF-1 and SF-3, F-1 to F-10 and F-80, read as ranges, so a number EDGAR retired, S-2 or
// F-5, counts as a code too; the 424B prospectuses), the ownership and tender families (SC 13D, SC 13G,
// SC TO, SC 14D9, 13F-HR, 13F-NT), the proxy family (DEF 14A, DEFA14A, DEFM14A, PRE 14A), the fund reports
// (N-CSR, N-Q, N-PX, N-1A, N-2) and the insider forms written as words (the search's chip labels the
// code 4 "Form 4"). The letters after a dash are each family's own, so "10-year", "Top 10" and "F-150" are
// not forms, and neither is a pairing EDGAR does not write (40-K, 20-Q, 11-F).
const FORM_CODES = String.raw`10-[KQ]T?|[24]0-F|11-KT?|[86]-K|1-[AKU]|13F-(?:HR|NT)|SC 13[DG]|SC TO-[ICT]|SC 14D9|(?:DEF|DEFA|DEFM|PRE) ?14A|S-(?:[1-9]|1[01]|20)|SF-[13]|F-(?:[1-9]|10|80)|424B\d|N-(?:CSR|Q|PX|1A|2)|Form\s[345]`
const FORM_CODE = new RegExp(String.raw`^\s*(${FORM_CODES})(\/A)?\s*$`, 'i')
// A text child that opens with a form code and then only a separator: a middot, bullet or pipe, a comma, colon or
// semicolon, or a dash set off by a space (`10-Q · Filed `, `8-K, filed`, `10-Q - Filed`); never prose (`10-K filings`,
// `10-K's cover page`), and a hyphen joined to the code is a word (`S-1-style`).
const FORM_CODE_LEAD = new RegExp(String.raw`^\s*(${FORM_CODES})(\/A)?(?:\s*(?:$|[·•|,:;–—])|\s+-)`, 'i')
const CHIP_CLASS = /^(class|className)$/
// The eyebrow recipe, under a variant or not, with Tailwind 3's important modifier or not (`!uppercase`, `sm:!uppercase`:
// the same declarations, marked !important).
const EYEBROW_CHIP = [/(^|:)!?uppercase$/, /(^|:)!?tracking-eyebrow$/]
// The helpers a class binding may call: `const EYEBROW = cx('uppercase', 'tracking-eyebrow')`.
const CLASS_HELPER = /^(cx|clsx)$/

// Values whose truthiness their text fixes: an array, object, function or class expression is truthy.
const TRUTHY_SHAPE = /^(?:ArrayExpression|ObjectExpression|FunctionExpression|ArrowFunctionExpression|ClassExpression)$/

/** An expression's truthiness whatever runs: true or false, or undefined when it depends on what runs. A literal by its
 *  value (a regex is truthy); a template truthy once a chunk has text, falsy when empty with no substitution; an array,
 *  object, function or class expression truthy; the globals `undefined` and `NaN` falsy, `Infinity` truthy; `void x`
 *  falsy, `typeof x` truthy, `!x` the opposite of x; `&&`, `||`, `??` (a truthy left is never null or undefined), a
 *  conditional and a comma sequence by JavaScript's rules over their parts. Anything else is undefined. */
function staticTruth(raw) {
  const node = unwrapTs(raw)
  if (!node) return undefined
  if (node.type === 'Literal') return node.regex ? true : node.value === null && node.bigint !== undefined ? undefined : !!node.value
  if (node.type === 'TemplateLiteral') {
    if (node.quasis.some((q) => (q.value.cooked ?? q.value.raw) !== '')) return true
    return node.expressions.length === 0 ? false : undefined
  }
  if (TRUTHY_SHAPE.test(node.type)) return true
  if (node.type === 'Identifier') return node.name === 'undefined' || node.name === 'NaN' ? false : node.name === 'Infinity' ? true : undefined
  if (node.type === 'UnaryExpression') {
    if (node.operator === 'void') return false
    if (node.operator === 'typeof') return true
    const argument = node.operator === '!' ? staticTruth(node.argument) : undefined
    return argument === undefined ? undefined : !argument
  }
  if (node.type === 'LogicalExpression') {
    const left = staticTruth(node.left)
    const right = staticTruth(node.right)
    if (node.operator === '&&') return left === false ? false : left === true ? right : right === false ? false : undefined
    if (node.operator === '||') return left === true ? true : left === false ? right : right === true ? true : undefined
    return left === true ? true : left === false && right === false ? false : undefined
  }
  if (node.type === 'ConditionalExpression') {
    const test = staticTruth(node.test)
    const [yes, no] = [staticTruth(node.consequent), staticTruth(node.alternate)]
    return test === true ? yes : test === false ? no : yes === no ? yes : undefined
  }
  if (node.type === 'SequenceExpression') return staticTruth(node.expressions[node.expressions.length - 1])
  return undefined
}

/** The operand of a logical or conditional expression that never renders because its truthiness is fixed: the right of
 *  `&&` after a falsy left, of `||` or `??` after a truthy one, the arm a fixed test never takes; else null. */
function untaken(node) {
  if (node.type === 'LogicalExpression') {
    const left = staticTruth(node.left)
    return (node.operator === '&&' ? left === false : left === true) ? node.right : null
  }
  if (node.type === 'ConditionalExpression') {
    const test = staticTruth(node.test)
    return test === undefined ? null : test ? node.alternate : node.consequent
  }
  return null
}

/** Every string an attribute's value can contribute (literals and template chunks), joined. An identifier
 *  contributes what `binding` reads for it: the class text of a binding declared in the same file. A class helper's
 *  object form names its classes by key (`cx({ uppercase: active })`), so a bare key contributes its name, as a quoted
 *  key contributes its text. A part that never renders contributes nothing: an entry whose value is falsy whatever runs
 *  (`cx({ uppercase: false })`), and an operand a fixed truthiness leaves untaken (`cx(false && 'uppercase')`). Every
 *  other string counts wherever it stands, a condition's included, so the reading fails closed. */
function attributeText(node, keys, binding, out = []) {
  if (!node || typeof node.type !== 'string') return out
  if (node.type === 'Property' && staticTruth(node.value) === false) return out
  if (node.type === 'Literal' && typeof node.value === 'string') out.push(node.value)
  if (node.type === 'Property' && !node.computed && node.key.type === 'Identifier') out.push(node.key.name)
  if (node.type === 'TemplateElement') out.push(node.value.cooked ?? node.value.raw)
  if (node.type === 'Identifier') out.push(...binding(node))
  const skipped = untaken(node)
  for (const key of keys[node.type] ?? []) {
    for (const child of [node[key]].flat()) if (child !== skipped) attributeText(child, keys, binding, out)
  }
  return out
}

/** The expression under TypeScript's wrappers, which change its type and not its text: `as const`,
 *  `satisfies`, a non-null `!` and the angle-bracket assertion. */
const unwrapTs = (node) => {
  while (node && /^TS(?:As|Satisfies|NonNull|TypeAssertion)Expression$|^TSTypeAssertion$/.test(node.type)) node = node.expression
  return node
}
/** A binding initializer read as class text: a string, a template, or a cx()/clsx() call, under TypeScript's
 *  wrappers or not (`'uppercase tracking-eyebrow' as const`). An object of recipes, a function or any other
 *  expression is not, so `styles.data` never reads `styles.chip`. */
const isClassShaped = (raw) => {
  const init = unwrapTs(raw)
  return (
    (init?.type === 'Literal' && typeof init.value === 'string') ||
    init?.type === 'TemplateLiteral' ||
    (init?.type === 'CallExpression' && init.callee.type === 'Identifier' && CLASS_HELPER.test(init.callee.name))
  )
}

/** The variable an identifier reads, from ESLint's scope analysis; null for a name that is not a
 *  reference (a property key) and for a global. */
function resolvedVariable(sourceCode, identifier) {
  for (let scope = sourceCode.getScope(identifier); scope; scope = scope.upper) {
    const reference = scope.references.find((r) => r.identifier === identifier)
    if (reference) return reference.resolved
  }
  return null
}

/** The first node in `node` that names or spells a form, else null: a form field wherever it sits (`form`,
 *  `hit.form ?? fallback`, `filing.form.toUpperCase()`, `hit['form']`), or text (JSX text, a string, a template chunk) that
 *  `code` matches. A descriptive prop and one that neither displays nor styles are skipped, and a nested Badge is
 *  checked on its own visit. */
/** A computed member key's text when it is written out: a string, or a template with no substitution. */
const staticKey = (key) =>
  key?.type === 'Literal' && typeof key.value === 'string'
    ? key.value
    : key?.type === 'TemplateLiteral' && key.expressions.length === 0
      ? key.quasis[0].value.cooked
      : undefined

function formNode(node, keys, code = FORM_CODE) {
  if (!node || typeof node.type !== 'string') return null
  if (node.type === 'JSXAttribute' && (DESCRIPTIVE_PROP.test(node.name?.name ?? '') || UNRENDERED_PROP.test(node.name?.name ?? ''))) return null
  if (node.type === 'JSXElement' && isBadge(node.openingElement.name)) return null
  if (node.type === 'Identifier' && FORM_FIELD.test(node.name)) return node
  // A form field read by bracket notation (`hit['form']`, `filing?.[\`filing_type\`]`) is the field too.
  if (node.type === 'MemberExpression' && node.computed && FORM_FIELD.test(staticKey(node.property) ?? '')) return node
  if (node.type === 'JSXText' && code.test(node.value)) return node
  if (node.type === 'Literal' && typeof node.value === 'string' && code.test(node.value)) return node
  if (node.type === 'TemplateElement' && code.test(node.value.cooked ?? '')) return node
  for (const key of keys[node.type] ?? []) {
    for (const child of [node[key]].flat()) {
      const found = formNode(child, keys, code)
      if (found) return found
    }
  }
  return null
}

const meaningfulChildren = (node) =>
  node.children.filter(
    (c) =>
      !(c.type === 'JSXText' && c.value.trim() === '') &&
      !(c.type === 'JSXExpressionContainer' && c.expression.type === 'JSXEmptyExpression'),
  )
const classTokens = (node, keys, binding) => {
  const classAttr = node.openingElement.attributes.find((a) => a.type === 'JSXAttribute' && CHIP_CLASS.test(a.name?.name ?? ''))
  return classAttr ? attributeText(classAttr.value, keys, binding).join(' ').split(/\s+/) : []
}
// An inner element that resets the recipe is a face of its own, when it resets it unconditionally. Either half resets
// it: a text-transform other than uppercase (`normal-case`, `lowercase`, `capitalize`, `[text-transform:none]`) or a
// letter-spacing of its own (another tracking utility, an arbitrary one such as `tracking-[0.02em]`,
// `[letter-spacing:0]`). A reset under a variant (`sm:normal-case`, `dark:tracking-normal`) leaves the chip's face on
// in the other branches (a phone, the light theme), and so does one on a single path of its class value
// (`plain ? 'normal-case' : ''`, `cx(plain && 'normal-case')`), so neither ends the reading. An important reset
// (`!normal-case`) is a reset. A face set by an inline style is not read, so a wrapper that resets it that way is
// reported: the gate fails closed there.
const RESETS_EYEBROW = /^!?(?:normal-case|lowercase|capitalize|tracking-(?!eyebrow$)\S+|\[text-transform:(?!uppercase\])[^\]]+\]|\[letter-spacing:[^\]]+\])$/
/** Whether a class value resets the eyebrow face on every path it can take. Each path needs a reset, not the same one
 *  (`plain ? 'normal-case' : 'tracking-normal'` cancels one half of the recipe on each path): a string's tokens, a
 *  template's whole static tokens, both arms of a conditional, both sides of `||` and `??`, any argument of a cx()/clsx()
 *  call (an object's key only when its value is truthy whatever runs), and a same-file binding by its class-shaped
 *  initializer (`init`). A fixed truthiness picks the path (staticTruth): the arm a fixed test takes, the right of `&&`
 *  after a truthy left, the side of `||` or `??` a fixed left decides. `a && b` otherwise, and anything else, resets
 *  nothing; `seen` holds the bindings on the current path, so it stops a binding that reads itself while a sibling
 *  branch reads the same binding in full. */
function resetsOnEveryPath(raw, init, seen = new Set()) {
  const node = unwrapTs(raw)
  const resets = (tokens) => tokens.some((token) => RESETS_EYEBROW.test(token))
  const words = (text) => text.split(/\s+/).filter(Boolean)
  if (!node) return false
  if (node.type === 'JSXExpressionContainer') return resetsOnEveryPath(node.expression, init, seen)
  if (node.type === 'Literal') return typeof node.value === 'string' && resets(words(node.value))
  if (node.type === 'TemplateLiteral') {
    return node.quasis.some((quasi, i) => {
      const text = quasi.value.cooked ?? quasi.value.raw
      const parts = words(text)
      // A token that touches a substitution is not whole.
      if (i > 0 && !/^\s/.test(text)) parts.shift()
      if (i < node.quasis.length - 1 && !/\s$/.test(text)) parts.pop()
      return resets(parts)
    })
  }
  if (node.type === 'ConditionalExpression') {
    const test = staticTruth(node.test)
    if (test !== undefined) return resetsOnEveryPath(test ? node.consequent : node.alternate, init, seen)
    return resetsOnEveryPath(node.consequent, init, seen) && resetsOnEveryPath(node.alternate, init, seen)
  }
  if (node.type === 'LogicalExpression') {
    const left = staticTruth(node.left)
    if (node.operator === '&&') return left === true && resetsOnEveryPath(node.right, init, seen)
    if (left === true) return resetsOnEveryPath(node.left, init, seen)
    if (left === false && node.operator === '||') return resetsOnEveryPath(node.right, init, seen)
    return resetsOnEveryPath(node.left, init, seen) && resetsOnEveryPath(node.right, init, seen)
  }
  if (node.type === 'CallExpression' && node.callee.type === 'Identifier' && CLASS_HELPER.test(node.callee.name)) {
    return node.arguments.some((arg) => {
      const value = unwrapTs(arg)
      // An object argument resets on every path only by a key whose value is truthy whatever runs.
      if (value?.type === 'ObjectExpression') {
        return value.properties.some((p) => p.type === 'Property' && !p.computed && staticTruth(p.value) === true
          && resets(words(p.key.type === 'Identifier' ? p.key.name : String(p.key.value))))
      }
      return resetsOnEveryPath(arg, init, seen)
    })
  }
  if (node.type === 'Identifier') {
    const target = init(node)
    if (!target || seen.has(target)) return false
    // The bindings on this path alone: a sibling branch that reads the same binding reads it in full.
    return resetsOnEveryPath(target, init, new Set([...seen, target]))
  }
  return false
}
/** Whether an element's class resets the eyebrow face on every path (resetsOnEveryPath). */
const resetsFace = (element, init) => {
  const classAttr = element.openingElement.attributes.find((a) => a.type === 'JSXAttribute' && CHIP_CLASS.test(a.name?.name ?? ''))
  return !!classAttr && resetsOnEveryPath(classAttr.value, init)
}
/** An expression that renders only whitespace (`{' '}`): passed over in looking for the lead. */
const isBlank = (expression) => {
  const node = unwrapTs(expression)
  return (
    (node?.type === 'Literal' && typeof node.value === 'string' && node.value.trim() === '') ||
    (node?.type === 'TemplateLiteral' && node.expressions.length === 0 && (node.quasis[0].value.cooked ?? '').trim() === '')
  )
}
/** An expression that renders nothing on one of its paths: `cond && x`, a conditional with an empty arm (`cond ?
 *  'New · ' : null`), a fallback that may be empty (`label || null`, `note ?? ''`: `||` renders its right side when
 *  the left is empty, `??` only when the left is null or undefined, so a left of `''` or `false` renders nothing,
 *  as in `(isNew && 'New') ?? 'Latest'`; a value the scan cannot read is taken to render, so `label ?? 'Latest'` with
 *  `label` unread passes, as `{label}` does, a gap the spec plants), or an empty value itself (null, a boolean,
 *  undefined, a blank string). */
const mayRenderNothing = (expression) => {
  const node = unwrapTs(expression)
  if (!node || isBlank(node)) return true
  if (node.type === 'Literal' && (node.value === null || typeof node.value === 'boolean')) return true
  if (node.type === 'Identifier' && node.name === 'undefined') return true
  if (node.type === 'LogicalExpression' && node.operator === '&&') return true
  if (node.type === 'LogicalExpression' && node.operator === '??') return mayBeKeptBlank(node.left) || mayRenderNothing(node.right)
  if (node.type === 'LogicalExpression') return mayRenderNothing(node.right)
  if (node.type === 'ConditionalExpression') return mayRenderNothing(node.consequent) || mayRenderNothing(node.alternate)
  return false
}
/** Whether a value may be blank without being null or undefined (a blank string, a boolean, a falsy `&&`): what `??`
 *  keeps and renders as nothing, where `||` would take its right side. A value the scan cannot read is taken to render. */
const mayBeKeptBlank = (expression) => {
  const node = unwrapTs(expression)
  if (!node) return false
  if (isBlank(node) || (node.type === 'Literal' && typeof node.value === 'boolean')) return true
  if (node.type === 'LogicalExpression' && node.operator === '&&') return true
  if (node.type === 'LogicalExpression' && node.operator === '||') return mayBeKeptBlank(node.right)
  if (node.type === 'LogicalExpression') return mayBeKeptBlank(node.left) || mayBeKeptBlank(node.right)
  if (node.type === 'ConditionalExpression') return mayBeKeptBlank(node.consequent) || mayBeKeptBlank(node.alternate)
  return false
}

/** The lead of an element's content: its first text or expression in document order, read through its HTML
 *  wrappers and fragments at any depth, siblings included, since uppercase and letter-spacing inherit (`<span>{form}</span><span>
 *  · Filed {ago}</span>` inside the chip renders in its face; an empty wrapper, an icon's <i>, is passed over).
 *  A blank expression (`{' '}`) is passed over too, and so is one that renders nothing on one path (mayRenderNothing:
 *  `{isNew && 'New · '}`) unless it can render a form itself. Null when a component or a Badge (judged by its own rule) or an
 *  element that resets the recipe on every path (resetsFace: a face of its own) comes first; undefined when the
 *  content holds no text at all. What follows the lead does not change the face the lead is set in. */
function leadChild(node, keys, init) {
  for (const child of meaningfulChildren(node)) {
    if (child.type === 'JSXExpressionContainer' && isBlank(child.expression)) continue
    // An expression that renders nothing on one path (`{isNew && 'New · '}`) leads only on its other paths, so unless
    // it can render a form itself the reading goes on to what leads when it renders nothing.
    if (child.type === 'JSXExpressionContainer' && mayRenderNothing(child.expression) && !formNode(child.expression, keys, FORM_CODE_LEAD)) continue
    if (child.type === 'JSXText' || child.type === 'JSXExpressionContainer') return child
    // A fragment renders its children in place: read through it as through a plain wrapper.
    if (child.type === 'JSXFragment') {
      const lead = leadChild(child, keys, init)
      if (lead !== undefined) return lead
      continue
    }
    if (child.type !== 'JSXElement') return null
    const name = child.openingElement.name
    if (name.type !== 'JSXIdentifier' || !/^[a-z]/.test(name.name)) return null
    if (resetsFace(child, init)) return null
    const lead = leadChild(child, keys, init)
    if (lead !== undefined) return lead
  }
  return undefined
}

/** A hand-rolled chip around a form: an HTML element set in eyebrow type (uppercase, tracking-eyebrow, in
 *  its class text or a same-file binding it reads) whose lead (leadChild: the first text or expression of its
 *  content, read through its HTML wrappers, siblings included) shows a form by formNode's reading (its strings
 *  tested with FORM_CODE_LEAD, so `{'10-Q · Filed'}` counts), as the codebase's `{form} • Filed {ago}` meta line
 *  does. A Badge by another hand. A sentence that names a form later (`Latest {filing.filing_type}`) or opens
 *  with one as prose (`10-K filings`) is copy; a component, a Badge or a face-resetting element before the lead
 *  ends the reading, and nothing after it does. The children are read first, so a class binding is resolved
 *  only around a form. */
function isEyebrowFormChip(node, keys, binding, init) {
  const name = node.openingElement.name
  if (name.type !== 'JSXIdentifier' || !/^[a-z]/.test(name.name)) return false
  const lead = leadChild(node, keys, init)
  if (!lead || !formNode(lead, keys, FORM_CODE_LEAD)) return false
  const tokens = classTokens(node, keys, binding)
  return EYEBROW_CHIP.every((pattern) => tokens.some((token) => pattern.test(token)))
}

export const noFormCodeBadge = {
  meta: {
    type: 'problem',
    docs: { description: 'Form codes are text in the data face, never a Badge.' },
    schema: [],
    messages: {
      badge:
        'A form code inside <Badge> — set it as text in the data face (font-data font-semibold), as ' +
        'the filing identity strip does. Badges are for states, not document categories.',
      chip:
        'A form code in a hand-rolled eyebrow chip (uppercase, tracking-eyebrow): set it as text in the ' +
        'data face (font-data), as the filing identity strip does. Eyebrow type is for metric labels.',
    },
  },
  create(context) {
    const { sourceCode } = context
    const keys = sourceCode.visitorKeys
    // The class text of the binding an identifier in a class attribute names (`className={EYEBROW}`,
    // `cx(EYEBROW, 'mt-1')`): a same-file declaration whose initializer is class-shaped, read as an inline
    // class is. An import, a parameter or prop and a destructured name give nothing; `seen` stops a binding
    // that reads itself.
    const bindingClassText = (identifier, seen = new Set()) => {
      const def = resolvedVariable(sourceCode, identifier)?.defs[0]
      const init = def?.type === 'Variable' && def.node.id.type === 'Identifier' ? def.node.init : null
      if (!isClassShaped(init) || seen.has(init)) return []
      seen.add(init)
      return attributeText(init, keys, (inner) => bindingClassText(inner, seen))
    }
    // The same binding's class-shaped initializer itself, for the reading of what a class sets on every path.
    const bindingInit = (identifier) => {
      const def = resolvedVariable(sourceCode, identifier)?.defs[0]
      const init = def?.type === 'Variable' && def.node.id.type === 'Identifier' ? def.node.init : null
      return isClassShaped(init) ? init : null
    }
    return {
      JSXElement(node) {
        if (isEyebrowFormChip(node, keys, bindingClassText, bindingInit)) {
          return context.report({ node: node.openingElement, messageId: 'chip' })
        }
        if (!isBadge(node.openingElement.name)) return
        for (const part of [...node.openingElement.attributes, ...node.children]) {
          const found = formNode(part, keys)
          if (found) return context.report({ node: found, messageId: 'badge' })
        }
      },
    }
  },
}

/** globals.css classes that stop themselves in a `prefers-reduced-motion: reduce` block, so a use
 *  site needs no guard. tests/unit/designRules.spec.ts reads globals.css to hold each one to it. */
export const SELF_GUARDED_ANIMATIONS = new Set(['animate-fadeIn', 'animate-check-pop', 'animate-on-scroll'])

const MOTION_REDUCE = 'motion-reduce'
const isAnimation = (utility) =>
  utility.startsWith('animate-') && utility !== 'animate-none' && !SELF_GUARDED_ANIMATIONS.has(utility)
// In order: stacked selector variants compose the selector in sequence (`group-hover:peer-focus:`
// and `peer-focus:group-hover:` select different elements), so only the same sequence is the same.
const sameVariants = (a, b) => a.length === b.length && a.every((v, i) => v === b[i])

/** The first animation in `classText` that keeps moving under reduced motion, with the guard that
 *  stops it and its motion-safe spelling (`{ token, guard, safe }`), else null. A guard stops an
 *  animation when it carries the same variants in the same order (`motion-reduce` anywhere among
 *  them) and is at least as important: an `!important` animation beats a plain guard. */
export function unguardedAnimation(classText) {
  const tokens = classText.split(/\s+/).filter(Boolean).map((raw) => ({ raw, ...splitClassToken(raw) }))
  const guards = tokens
    .filter((t) => t.utility === 'animate-none' && t.variants.includes(MOTION_REDUCE))
    .map((t) => ({ variants: t.variants.filter((v) => v !== MOTION_REDUCE), important: t.important }))
  for (const t of tokens) {
    if (!isAnimation(t.utility) || t.variants.includes('motion-safe')) continue
    if (guards.some((g) => sameVariants(g.variants, t.variants) && (g.important || !t.important))) continue
    const variants = t.variants.filter((v) => v !== MOTION_REDUCE)
    const bang = t.important ? '!' : ''
    return {
      token: t.raw,
      guard: [MOTION_REDUCE, ...variants, `${bang}animate-none`].join(':'),
      safe: ['motion-safe', ...variants, `${bang}${t.utility}`].join(':'),
    }
  }
  return null
}

export const noUnguardedAnimation = {
  meta: {
    type: 'problem',
    docs: { description: 'Every animation utility stops under reduced motion.' },
    schema: [],
    messages: {
      unguarded:
        '{{token}} keeps moving under reduced motion (WCAG 2.3.3). Add {{guard}} in the class text that ' +
        'always renders with it, or write {{safe}}: a spinner becomes its static glyph, a skeleton a ' +
        'static bone, an entrance shows at once.',
    },
  },
  create(context) {
    return classUnitVisitors((node, pieces) => {
      for (const text of branchTexts(pieces)) {
        const found = unguardedAnimation(text)
        if (found) {
          context.report({ node, messageId: 'unguarded', data: found })
          return
        }
      }
    })
  },
}

/** The methods that format in the browser's locale when given none. */
const LOCALE_METHODS = new Set(['toLocaleString', 'toLocaleTimeString'])

/** Whether a call's locale argument is missing, the literal `undefined` or an empty list (`[]`): each is the browser's
    own locale. */
const unpinnedLocale = (args) =>
  args.length === 0 ||
  (args[0].type === 'Identifier' && args[0].name === 'undefined') ||
  (args[0].type === 'ArrayExpression' && args[0].elements.length === 0)

/** The one locale the product formats numbers and times in; lib/format.ts pins it for every helper. */
const PINNED_LOCALE = 'en-US'
const isPinnedLiteral = (node) => node.type === 'Literal' && node.value === PINNED_LOCALE
/** Whether a call's locale argument is present but not 'en-US' (or a list of it): another locale, or one the rule
    cannot read (a variable, a call), which may be the browser's. */
const otherLocale = (args) =>
  !unpinnedLocale(args) &&
  !isPinnedLiteral(args[0]) &&
  !(args[0].type === 'ArrayExpression' && args[0].elements.every((element) => element && isPinnedLiteral(element)))

/** Whether a callee is `Intl.NumberFormat`, which returns the same formatter called with `new` or without it. */
const isIntlNumberFormat = (callee) =>
  callee.type === 'MemberExpression' &&
  !callee.computed &&
  callee.object.type === 'Identifier' &&
  callee.object.name === 'Intl' &&
  callee.property.name === 'NumberFormat'

export const localePinnedNumbers = {
  meta: {
    type: 'problem',
    docs: { description: 'Numbers are formatted in a pinned locale, through lib/format.' },
    schema: [],
    messages: {
      unpinned:
        '{{call}} with no locale renders in the viewer\'s browser locale. Format the value through the ' +
        "lib/format.ts helper made for it (fmtCount or fmtDecimal for a number, a date helper for a date), " +
        "or pass 'en-US'.",
      other:
        "{{call}} pins {{locale}}, not 'en-US', the one locale the product formats numbers and times in " +
        "(lib/format.ts). Format the value through the lib/format.ts helper made for it, or pass 'en-US'.",
    },
  },
  create(context) {
    const report = (node, args, call) => {
      if (unpinnedLocale(args)) context.report({ node, messageId: 'unpinned', data: { call } })
      else if (otherLocale(args)) context.report({ node, messageId: 'other', data: { call, locale: context.sourceCode.getText(args[0]) } })
    }
    return {
      CallExpression(node) {
        const callee = node.callee
        if (isIntlNumberFormat(callee)) {
          report(node, node.arguments, 'Intl.NumberFormat()')
          return
        }
        if (callee.type !== 'MemberExpression' || callee.computed || !LOCALE_METHODS.has(callee.property.name)) return
        report(node, node.arguments, `${callee.property.name}()`)
      },
      NewExpression(node) {
        if (isIntlNumberFormat(node.callee)) report(node, node.arguments, 'new Intl.NumberFormat()')
      },
    }
  },
}

const isGroupRole = (attr) =>
  attr.type === 'JSXAttribute' &&
  attr.name?.name === 'role' &&
  ((attr.value?.type === 'Literal' && attr.value.value === 'group') ||
    (attr.value?.type === 'JSXExpressionContainer' &&
      attr.value.expression.type === 'Literal' &&
      attr.value.expression.value === 'group'))
const isButtonName = (name) =>
  (name?.type === 'JSXIdentifier' && (name.name === 'button' || name.name === 'Button')) ||
  (name?.type === 'JSXMemberExpression' && name.property.name === 'Button')
const hasPressed = (opening) =>
  opening.attributes.some((attr) => attr.type === 'JSXAttribute' && attr.name?.name === 'aria-pressed')
/** The SegmentedControl's own file: the one place a group of pressed buttons is built. */
const TOGGLE_GROUP_HOME = /(^|[\\/])components[\\/]ui[\\/]SegmentedControl\.tsx$/
/** The modules the DS Button is imported from: a local name bound to their `Button` export is a <Button>. */
const DS_BUTTON_SOURCES = new Set(['@/components/ui', '@/components/ui/Button'])
/** React's component wrappers: `memo(fn)` and `forwardRef(fn)`, bare or as `React.x`, render `fn`. */
const COMPONENT_WRAPPERS = new Set(['memo', 'forwardRef'])
const FUNCTION_TYPES = new Set(['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression'])

/** The local names a file binds to the DS Button's `Button` export, `Button` itself included. */
function dsButtonNames(program) {
  const names = new Set()
  for (const statement of program.body) {
    if (statement.type !== 'ImportDeclaration' || !DS_BUTTON_SOURCES.has(statement.source.value)) continue
    for (const spec of statement.specifiers) {
      if (spec.type === 'ImportSpecifier' && (spec.imported.name ?? spec.imported.value) === 'Button') names.add(spec.local.name)
    }
  }
  return names
}

const calleeName = (callee) =>
  callee.type === 'Identifier' ? callee.name : callee.type === 'MemberExpression' && !callee.computed ? callee.property.name : null

/** The function a same-file binding declares as a component: a function declaration, or a const bound to an
 *  arrow or a function expression (through memo, forwardRef, `as` and `satisfies`); else null. */
function componentFunction(variable) {
  for (const def of variable.defs) {
    if (def.type === 'FunctionName' && def.node.body) return def.node
    if (def.type !== 'Variable' || def.parent?.kind !== 'const') continue
    let init = def.node.init
    while (init) {
      if (init.type === 'TSAsExpression' || init.type === 'TSSatisfiesExpression') init = init.expression
      else if (init.type === 'CallExpression' && COMPONENT_WRAPPERS.has(calleeName(init.callee))) init = init.arguments[0]
      else break
    }
    if (init?.type === 'ArrowFunctionExpression' || init?.type === 'FunctionExpression') return init
  }
  return null
}

/** What a component function renders: an arrow's expression body, or the argument of every return statement in
 *  its own body (a nested function's returns are that function's). */
function renderedBy(fn, keys) {
  if (fn.body.type !== 'BlockStatement') return [fn.body]
  const rendered = []
  const visit = (node) => {
    if (!node || typeof node.type !== 'string' || FUNCTION_TYPES.has(node.type)) return
    if (node.type === 'ReturnStatement') {
      if (node.argument) rendered.push(node.argument)
      return
    }
    for (const key of keys[node.type] ?? []) for (const child of [node[key]].flat()) visit(child)
  }
  for (const statement of fn.body.body) visit(statement)
  return rendered
}

export const noHandRolledToggleGroup = {
  meta: {
    type: 'problem',
    docs: { description: 'A single-choice toggle group is the SegmentedControl, never a hand-rolled row.' },
    schema: [],
    messages: {
      handRolled:
        'A role="group" of aria-pressed buttons is a single-choice toggle group: compose <SegmentedControl ' +
        'label options value onChange> from @/components/ui (the ring, the pressed colorway and the wrapping ' +
        'come with it). A group of independent toggles is not this control: disable the rule with the reason.',
    },
  },
  create(context) {
    if (TOGGLE_GROUP_HOME.test(context.filename ?? '')) return {}
    const { sourceCode } = context
    const keys = sourceCode.visitorKeys
    const buttonNames = dsButtonNames(sourceCode.ast)
    const isButton = (name) => isButtonName(name) || (name?.type === 'JSXIdentifier' && buttonNames.has(name.name))
    // The same-file component a capitalised tag names, resolved from the tag's own scope outwards, else null.
    const componentOf = (opening) => {
      const { name } = opening
      if (name.type !== 'JSXIdentifier' || !/^[A-Z]/.test(name.name)) return null
      for (let scope = sourceCode.getScope(opening); scope; scope = scope.upper) {
        const variable = scope.set.get(name.name)
        if (variable) return componentFunction(variable)
      }
      return null
    }
    // The first <button>/<Button> with aria-pressed under `node`, else null. With `follow`, a tag naming a
    // same-file component is read through what that component renders, one level deep (no further `follow`).
    const pressedButton = (node, follow) => {
      if (!node || typeof node.type !== 'string') return null
      if (node.type === 'JSXOpeningElement') {
        if (isButton(node.name)) {
          if (hasPressed(node)) return node
        } else if (follow) {
          const component = componentOf(node)
          if (component && renderedBy(component, keys).some((rendered) => pressedButton(rendered, false))) return node
        }
      }
      for (const key of keys[node.type] ?? []) {
        for (const child of [node[key]].flat()) {
          const found = pressedButton(child, follow)
          if (found) return found
        }
      }
      return null
    }
    return {
      JSXElement(node) {
        if (!node.openingElement.attributes.some(isGroupRole)) return
        for (const child of node.children) {
          if (pressedButton(child, true)) return context.report({ node: node.openingElement, messageId: 'handRolled' })
        }
      },
    }
  },
}

const plugin = {
  rules: {
    'no-side-stripe': noSideStripe,
    'no-form-code-badge': noFormCodeBadge,
    'no-unguarded-animation': noUnguardedAnimation,
    'locale-pinned-numbers': localePinnedNumbers,
    'no-hand-rolled-toggle-group': noHandRolledToggleGroup,
  },
}
export default plugin
