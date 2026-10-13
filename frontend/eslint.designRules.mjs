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
//   direction-text-tokens (D-030, DESIGN.md "Separate Signals") A delta or a direction chip is text, so
//                       its ink is the 700-level direction token (text-gain-text / text-loss-text, the
//                       -dark pair in dark: lib/financialTone's directionText and directionChip), never
//                       the 600 level and never sage. The rule bans text-gain, text-gain-light, text-loss
//                       and text-loss-light under any variant (the 600s are graphic tones: 3.0:1 and
//                       3.9:1 as text on their tints), and a text-brand-* class where it colours a
//                       direction glyph: on a TrendUpIcon or TrendDownIcon, on the element that renders
//                       one as its child, or in an object that pairs one with its classes (a direction
//                       map such as { Icon: TrendUpIcon, cls: '…' }). A glyph reached through a variable
//                       rendered elsewhere (`<Icon />`) is data-flow, out of scope as below.
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
//
// Out of scope, as for every class-string rule here: a class name assembled from fragments at
// runtime, a form code reaching a Badge through a renamed variable (data-flow, not syntax), a
// Badge imported under another name, and an animation set outside a class utility (an arbitrary
// `[animation:…]` property, an inline style).

import { branchTexts, classUnitVisitors, collectStaticText, parseClassToken, splitClassToken } from './eslint.gridBaseTrack.mjs'

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

const DIRECTION_600_TEXT = /^text-(gain|loss)(-light)?(\/\S+)?$/
const BRAND_TEXT = /^text-brand(-|\/|$)/
const TREND_ICON = /^Trend(Up|Down)Icon$/
const CLASS_ATTR = /^(class|className|\w+ClassName)$/

/** The first token of `classText` whose utility matches `pattern`, under any variant, else null. */
const firstToken = (classText, pattern) =>
  classText.split(/\s+/).find((raw) => raw && pattern.test(splitClassToken(raw).utility)) ?? null

/** The first 600-level direction colour used as text in `classText`, else null. */
export const direction600Text = (classText) => firstToken(classText, DIRECTION_600_TEXT)
/** The first sage text class in `classText`, else null. */
export const brandText = (classText) => firstToken(classText, BRAND_TEXT)

const isTrendIcon = (name) =>
  (name?.type === 'JSXIdentifier' && TREND_ICON.test(name.name)) ||
  (name?.type === 'JSXMemberExpression' && TREND_ICON.test(name.property.name))

/** Every class text an expression can render, one per branch (see branchTexts). */
const textsOf = (node) => branchTexts(collectStaticText(node, new WeakSet()))

export const directionTextTokens = {
  meta: {
    type: 'problem',
    docs: { description: 'Direction text uses the 700-level gain/loss tokens, never the 600 level or sage.' },
    schema: [],
    messages: {
      light:
        '{{token}} is the 600-level direction colour, a graphic tone that fails as text. Use the 700 level ' +
        '(text-gain-text / text-loss-text, dark:text-gain-dark / dark:text-loss-dark), or directionText / ' +
        'directionChip from lib/financialTone.',
      brand:
        '{{token}} colours a direction in sage, and sage never marks a gain, a loss or a figure (D-030). Use ' +
        'directionText / directionChip from lib/financialTone, or the neutral ink with the glyph carrying it.',
    },
  },
  create(context) {
    const reportBrand = (node, texts) => {
      for (const text of texts) {
        const token = brandText(text)
        if (token !== null) return context.report({ node, messageId: 'brand', data: { token } })
      }
    }
    const classAttrs = (opening) =>
      opening.attributes.filter((a) => a.type === 'JSXAttribute' && a.name.type === 'JSXIdentifier' && CLASS_ATTR.test(a.name.name))
    return {
      ...classUnitVisitors((node, pieces) => {
        for (const text of branchTexts(pieces)) {
          const token = direction600Text(text)
          if (token !== null) return context.report({ node, messageId: 'light', data: { token } })
        }
      }),
      // A glyph and the element that renders it as a child: the ink it inherits is the parent's.
      JSXElement(node) {
        if (!isTrendIcon(node.openingElement.name)) return
        const holders = [node.openingElement]
        if (node.parent?.type === 'JSXElement') holders.push(node.parent.openingElement)
        for (const opening of holders) {
          for (const attr of classAttrs(opening)) reportBrand(attr, textsOf(attr.value))
        }
      },
      // A direction map: an object that holds a trend glyph beside the classes it is drawn with.
      ObjectExpression(node) {
        const props = node.properties.filter((p) => p.type === 'Property')
        if (!props.some((p) => p.value.type === 'Identifier' && TREND_ICON.test(p.value.name))) return
        for (const p of props) {
          if (p.value.type === 'Literal' || p.value.type === 'TemplateLiteral') reportBrand(p.value, textsOf(p.value))
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

const plugin = {
  rules: {
    'direction-text-tokens': directionTextTokens,
    'no-side-stripe': noSideStripe,
    'no-form-code-badge': noFormCodeBadge,
    'no-unguarded-animation': noUnguardedAnimation,
  },
}
export default plugin
