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
//   no-form-code-badge  (P-04) A form code (10-K, 10-Q, 6-K …) is text in the data face, never a
//                       Badge: a blue chip on 10-Q spent the status colour on a category, and a
//                       neutral one still reads as a status. The rule flags a <Badge> (or ui.Badge)
//                       that reads a filing-type field, or holds a literal form code (string,
//                       template or text), in its children or in a prop that styles it. Descriptive
//                       props (title, alt, aria-*) may name the form: they describe, not display.
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
//                       locale the scan cannot read (a variable) passes, and so does `Intl.NumberFormat`
//                       reached under another name (`const { NumberFormat } = Intl`, `globalThis.Intl`),
//                       which no file writes today. `Intl.DateTimeFormat` is not
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
// `[animation:…]` property, an inline style).

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
const DESCRIPTIVE_PROP = /^(title|alt|aria-[a-z]+)$/
const isBadge = (name) =>
  (name?.type === 'JSXIdentifier' && name.name === 'Badge') ||
  (name?.type === 'JSXMemberExpression' && name.property.name === 'Badge')
const FORM_CODE = /^\s*(10-K|10-Q|8-K|20-F|40-F|6-K|S-1|S-4|DEF 14A)(\/A)?\s*$/i

export const noFormCodeBadge = {
  meta: {
    type: 'problem',
    docs: { description: 'Form codes are text in the data face, never a Badge.' },
    schema: [],
    messages: {
      badge:
        'A form code inside <Badge> — set it as text in the data face (font-data font-semibold), as ' +
        'the filing identity strip does. Badges are for states, not document categories.',
    },
  },
  create(context) {
    const keys = context.sourceCode.visitorKeys
    // The first node in a Badge's props or children that names or spells a form, else null. A
    // nested Badge is checked on its own visit.
    const formNode = (node) => {
      if (!node || typeof node.type !== 'string') return null
      if (node.type === 'JSXAttribute' && DESCRIPTIVE_PROP.test(node.name?.name ?? '')) return null
      if (node.type === 'JSXElement' && isBadge(node.openingElement.name)) return null
      if (node.type === 'Identifier' && FORM_FIELD.test(node.name)) return node
      if (node.type === 'JSXText' && FORM_CODE.test(node.value)) return node
      if (node.type === 'Literal' && typeof node.value === 'string' && FORM_CODE.test(node.value)) return node
      if (node.type === 'TemplateElement' && FORM_CODE.test(node.value.cooked ?? '')) return node
      for (const key of keys[node.type] ?? []) {
        for (const child of [node[key]].flat()) {
          const found = formNode(child)
          if (found) return found
        }
      }
      return null
    }
    return {
      JSXElement(node) {
        if (!isBadge(node.openingElement.name)) return
        for (const part of [...node.openingElement.attributes, ...node.children]) {
          const found = formNode(part)
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
    },
  },
  create(context) {
    return {
      CallExpression(node) {
        const callee = node.callee
        if (isIntlNumberFormat(callee)) {
          if (unpinnedLocale(node.arguments)) context.report({ node, messageId: 'unpinned', data: { call: 'Intl.NumberFormat()' } })
          return
        }
        if (callee.type !== 'MemberExpression' || callee.computed || !LOCALE_METHODS.has(callee.property.name)) return
        if (unpinnedLocale(node.arguments)) context.report({ node, messageId: 'unpinned', data: { call: `${callee.property.name}()` } })
      },
      NewExpression(node) {
        if (isIntlNumberFormat(node.callee) && unpinnedLocale(node.arguments)) {
          context.report({ node, messageId: 'unpinned', data: { call: 'new Intl.NumberFormat()' } })
        }
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
