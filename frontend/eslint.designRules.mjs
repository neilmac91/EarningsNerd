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
//   no-form-code-badge  (P-04) A form code (10-K, 10-Q, 6-K …, and the insider forms the product
//                       writes as words, Form 3, Form 4 and Form 5) is text in the data face, never a
//                       Badge: a blue chip on 10-Q spent the status colour on a category, and a
//                       neutral one still reads as a status. The rule flags a <Badge> (or ui.Badge)
//                       that reads a filing-type field, or holds a literal form code (string,
//                       template or text), in its children or in a prop that styles it. Descriptive
//                       props (title, alt, aria-*) may name the form: they describe, not display.
//                       It flags a hand-rolled chip by the same reading: an HTML element whose class
//                       text sets uppercase and tracking-eyebrow, written inline or held in a binding
//                       declared in the same file (`const EYEBROW = 'uppercase tracking-eyebrow'`
//                       read as `className={EYEBROW}`; the initializer a string, a template or a
//                       cx()/clsx() call), and whose first non-blank child, text or an expression,
//                       reads a form field anywhere in it (`{hit.form ?? fallback}`,
//                       `{filing.form.toUpperCase()}`) or holds a code, or text opening with one
//                       before a separator (`{'10-Q · Filed'}`), followed only by text or
//                       expressions, as in `{form} • Filed {ago}`.
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
const DESCRIPTIVE_PROP = /^(title|alt|aria-[a-z]+)$/
const isBadge = (name) =>
  (name?.type === 'JSXIdentifier' && name.name === 'Badge') ||
  (name?.type === 'JSXMemberExpression' && name.property.name === 'Badge')
// The numbered codes, and the insider forms written as words: the search's chip labels the code 4 "Form 4".
const FORM_CODE = /^\s*(10-K|10-Q|8-K|20-F|40-F|6-K|S-1|S-4|DEF 14A|Form\s[345])(\/A)?\s*$/i
// A text child that opens with a form code and then only a separator (`10-Q · Filed `), never prose (`10-K filings`).
const FORM_CODE_LEAD = /^\s*(10-K|10-Q|8-K|20-F|40-F|6-K|S-1|S-4|DEF 14A|Form\s[345])(\/A)?\s*($|[·•|])/i
const CHIP_CLASS = /^(class|className)$/
const EYEBROW_CHIP = [/(^|:)uppercase$/, /(^|:)tracking-eyebrow$/]
// The helpers a class binding may call: `const EYEBROW = cx('uppercase', 'tracking-eyebrow')`.
const CLASS_HELPER = /^(cx|clsx)$/

/** Every string an attribute's value can contribute (literals and template chunks), joined. An identifier
 *  contributes what `binding` reads for it: the class text of a binding declared in the same file. */
function attributeText(node, keys, binding, out = []) {
  if (!node || typeof node.type !== 'string') return out
  if (node.type === 'Literal' && typeof node.value === 'string') out.push(node.value)
  if (node.type === 'TemplateElement') out.push(node.value.cooked ?? node.value.raw)
  if (node.type === 'Identifier') out.push(...binding(node))
  for (const key of keys[node.type] ?? []) {
    for (const child of [node[key]].flat()) attributeText(child, keys, binding, out)
  }
  return out
}

/** A binding initializer read as class text: a string, a template, or a cx()/clsx() call. An object of
 *  recipes, a function or any other expression is not, so `styles.data` never reads `styles.chip`. */
const isClassShaped = (init) =>
  (init?.type === 'Literal' && typeof init.value === 'string') ||
  init?.type === 'TemplateLiteral' ||
  (init?.type === 'CallExpression' && init.callee.type === 'Identifier' && CLASS_HELPER.test(init.callee.name))

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
 *  `hit.form ?? fallback`, `filing.form.toUpperCase()`), or text (JSX text, a string, a template chunk) that
 *  `code` matches. A descriptive prop is skipped, and a nested Badge is checked on its own visit. */
function formNode(node, keys, code = FORM_CODE) {
  if (!node || typeof node.type !== 'string') return null
  if (node.type === 'JSXAttribute' && DESCRIPTIVE_PROP.test(node.name?.name ?? '')) return null
  if (node.type === 'JSXElement' && isBadge(node.openingElement.name)) return null
  if (node.type === 'Identifier' && FORM_FIELD.test(node.name)) return node
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

/** A hand-rolled chip around a form: an HTML element set in eyebrow type (uppercase, tracking-eyebrow, in
 *  its class text or a same-file binding it reads) whose first non-blank child, text or an expression, shows
 *  a form by formNode's reading (its strings tested with FORM_CODE_LEAD, so `{'10-Q · Filed'}` counts),
 *  followed only by text or expressions (the codebase's `{form} • Filed {ago}` meta line). A Badge by
 *  another hand. A sentence that names a form later (`Latest {filing.filing_type}`) or opens with one as
 *  prose (`10-K filings`) is copy, and an element child ends the match. The children are read first, so a
 *  class binding is resolved only around a form. */
function isEyebrowFormChip(node, keys, binding) {
  const name = node.openingElement.name
  if (name.type !== 'JSXIdentifier' || !/^[a-z]/.test(name.name)) return false
  const children = node.children.filter(
    (c) =>
      !(c.type === 'JSXText' && c.value.trim() === '') &&
      !(c.type === 'JSXExpressionContainer' && c.expression.type === 'JSXEmptyExpression'),
  )
  if (children.length === 0) return false
  if (!children.every((c) => c.type === 'JSXText' || c.type === 'JSXExpressionContainer')) return false
  if (!formNode(children[0], keys, FORM_CODE_LEAD)) return false
  const classAttr = node.openingElement.attributes.find((a) => a.type === 'JSXAttribute' && CHIP_CLASS.test(a.name?.name ?? ''))
  const tokens = classAttr ? attributeText(classAttr.value, keys, binding).join(' ').split(/\s+/) : []
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
    return {
      JSXElement(node) {
        if (isEyebrowFormChip(node, keys, bindingClassText)) {
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
    'no-hand-rolled-toggle-group': noHandRolledToggleGroup,
  },
}
export default plugin
