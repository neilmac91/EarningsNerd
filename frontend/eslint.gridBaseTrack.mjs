// Gate for lessons/frontend-variable-text-must-not-size-a-wrapping-row.md: every grid that sets its
// columns under a variant also sets its base track in the same class string —
// `grid grid-cols-1 md:grid-cols-3`, not `grid md:grid-cols-3`. Without the base, the phone layout
// is one implicit `auto` track whose minimum is the widest child's min-content, so one long
// company name scrolls the whole page sideways (/dashboard #1058, /dashboard/watchlist #1077).
//
// A custom rule rather than a no-restricted-syntax regex, because the rule is about a whole class
// string and a regex selector sees one literal at a time. The regex flagged `cx('grid
// grid-cols-1', c && 'md:grid-cols-2')` because the base is in a different argument, and missed
// `grid md:!grid-cols-3`, `grid group-hover/card:grid-cols-2` and `grid grid-cols-none
// md:grid-cols-3`. This rule parses each class token's variants and evaluates what lands on one
// element: a class attribute (`className`, `*ClassName`) or a class-helper call (cx/clsx/…), with
// all its literal and template text. Text that is always there (a plain string, every helper
// argument, array element and template chunk) is checked together. Text that is there only on some
// renders (a ternary arm, an `&&`/`||`/`??` operand, an object key or value) is a branch, checked
// together with the text that is always there around it and nothing else. So a base track satisfies
// variant columns only where it is sure to render with them: in the same branch, or in text that is
// always there. `cx('grid grid-cols-1', wide && 'md:grid-cols-2')` and `cx('grid md:grid-cols-2',
// 'grid-cols-1')` pass; `cx('grid', wide ? 'md:grid-cols-2' : 'grid-cols-1')` (a branch borrows the
// other arm's base) and `cx('grid md:grid-cols-2', narrow && 'grid-cols-1')` (the base is only
// sometimes there) fail. A branch inside a branch also sees the text that is always there in its
// enclosing branch, and a spread (`cx('grid', ...parts)`) counts as written in place. Any string or
// template literal the unit does not reach this way is evaluated on its own, never skipped: a class
// constant or map, a member lookup on an inline map (`cx('grid', { 2: 'md:grid-cols-2' }[n])`), a
// sequence or tagged template, or the body of a function (`className={() => cx(…)}`), which starts
// afresh. Pinned by tests/unit/gridBaseTrackRule.spec.ts.
//
// Out of scope, as for every class-string rule here: a class name assembled from fragments at
// runtime, and a component whose own root is the grid while the caller passes only
// `md:grid-cols-*` (that call is flagged; adding a base there could override the component's own
// base, so decide it in review and disable the line with a reason).

const CLASS_ATTRIBUTE = /^(class|className|\w+ClassName)$/
const CLASS_HELPERS = new Set(['cx', 'clsx', 'cn', 'classNames', 'classnames', 'twMerge', 'twJoin'])

/** Split a class token into variants and utility: `md:hover:!grid-cols-3` →
 *  { variants: ['md', 'hover'], utility: 'grid-cols-3' }. Colons inside `[…]`/`(…)` (arbitrary
 *  variants and values) do not split. Returns null for a token whose variant styles other elements
 *  (`*:`, `[&>div]:`, `[&_p]:`), because those classes do not size this element's tracks. */
export function parseClassToken(token) {
  const parts = []
  let depth = 0
  let start = 0
  for (let i = 0; i < token.length; i++) {
    const ch = token[i]
    if (ch === '[' || ch === '(') depth++
    else if ((ch === ']' || ch === ')') && depth > 0) depth--
    else if (ch === ':' && depth === 0) {
      parts.push(token.slice(start, i))
      start = i + 1
    }
  }
  parts.push(token.slice(start))
  // Important modifier: `!utility` (Tailwind 3), `utility!` (Tailwind 4), or a leading `!` on the
  // whole token.
  const utility = parts.pop().replace(/^!|!$/g, '')
  const variants = parts.map((v, i) => (i === 0 ? v.replace(/^!/, '') : v))
  const targetsOthers = (v) => v === '*' || v === '**' || (v.startsWith('[') && /&.*[>_+~]/.test(v))
  if (variants.some(targetsOthers)) return null
  return { variants, utility }
}

const isGridDisplay = (t) => t.utility === 'grid' || t.utility === 'inline-grid'
const isCols = (t) => t.utility.startsWith('grid-cols-')

/** Returns null when the class text is fine, else the variant prefix whose base track is missing
 *  (`''` for the unprefixed base, `'sm:'` for `hidden sm:grid lg:grid-cols-4`). */
export function gridBaseTrackProblem(classText) {
  const tokens = classText.split(/\s+/).filter(Boolean).map(parseClassToken).filter(Boolean)
  if (!tokens.some((t) => isCols(t) && t.variants.length > 0)) return null
  // A base track has to apply whenever the grid display does: no variant it lacks, and not
  // `grid-cols-none`, which leaves the tracks implicit again.
  const covers = (display) =>
    tokens.some(
      (t) =>
        isCols(t) &&
        t.utility !== 'grid-cols-none' &&
        t.variants.every((v) => display.variants.includes(v)),
    )
  const displays = tokens.filter(isGridDisplay)
  // No display token at all: a fragment (a constant, a caller's className) that will be joined to
  // a grid elsewhere. It must carry its own unprefixed base.
  const unprefixed = { variants: [] }
  if (displays.length === 0 || displays.some((d) => d.variants.length === 0)) {
    return covers(unprefixed) ? null : ''
  }
  const missing = displays.find((d) => !covers(d))
  return missing ? `${missing.variants.join(':')}:` : null
}

/** All literal text that can reach the class list, one piece per string literal or template (its
 *  chunks joined), each tagged with its branch: a ternary arm, a logical operand, an object key or
 *  value opens a branch inside the current one; everything else (helper-call arguments, array
 *  elements, spreads, template expressions, `+` operands) stays in it. Every node it walks is added
 *  to `reached`, so the rule evaluates on its own only what no unit reached. */
function collectStaticText(node, reached, out = [], branch = { parent: null }) {
  if (!node) return out
  reached.add(node)
  const sub = (child) => collectStaticText(child, reached, out, branch)
  const optional = (child) => collectStaticText(child, reached, out, { parent: branch })
  switch (node.type) {
    case 'Literal':
      if (typeof node.value === 'string') out.push({ text: node.value, branch })
      break
    case 'TemplateLiteral':
      out.push({ text: node.quasis.map((q) => q.value.cooked ?? q.value.raw).join(' '), branch })
      for (const e of node.expressions) sub(e)
      break
    case 'JSXExpressionContainer':
    case 'TSAsExpression':
    case 'TSSatisfiesExpression':
    case 'TSNonNullExpression':
    case 'ChainExpression':
      sub(node.expression)
      break
    case 'SpreadElement':
      sub(node.argument)
      break
    case 'ConditionalExpression':
      optional(node.consequent)
      optional(node.alternate)
      break
    case 'LogicalExpression':
      optional(node.left)
      optional(node.right)
      break
    case 'BinaryExpression':
      if (node.operator === '+') {
        sub(node.left)
        sub(node.right)
      }
      break
    case 'CallExpression':
      if (node.callee.type === 'MemberExpression') sub(node.callee.object)
      for (const a of node.arguments) sub(a)
      break
    case 'ArrayExpression':
      for (const el of node.elements) sub(el)
      break
    case 'ObjectExpression':
      for (const p of node.properties) {
        if (p.type !== 'Property') {
          sub(p)
          continue
        }
        if (p.computed || p.key.type === 'Literal') optional(p.key)
        optional(p.value)
      }
      break
  }
  return out
}

const isClassAttribute = (node) =>
  node.type === 'JSXAttribute' && node.name.type === 'JSXIdentifier' && CLASS_ATTRIBUTE.test(node.name.name)
const isHelperCall = (node) =>
  node.type === 'CallExpression' && node.callee.type === 'Identifier' && CLASS_HELPERS.has(node.callee.name)
export const responsiveGridBaseTrack = {
  meta: {
    type: 'problem',
    docs: { description: 'A grid that sets its columns under a variant also sets its base track.' },
    schema: [],
    messages: {
      missing:
        'Responsive grid without a base track — add {{fix}} (minmax(0, 1fr); grid-cols-[auto] if a ' +
        'content-sized track is intended) beside the variant grid-cols-*, or the narrow layout sizes ' +
        'to its widest content and can scroll the page sideways.',
    },
  },
  create(context) {
    // Each branch must pass with the text that renders whenever it does: its own, and that of every
    // branch enclosing it up to the always-there text. Siblings never count.
    const check = (node, pieces) => {
      for (const branch of new Set(pieces.map((p) => p.branch))) {
        const present = new Set()
        for (let b = branch; b; b = b.parent) present.add(b)
        const text = pieces
          .filter((p) => present.has(p.branch))
          .map((p) => p.text)
          .join(' ')
        const prefix = gridBaseTrackProblem(text)
        if (prefix !== null) {
          context.report({ node, messageId: 'missing', data: { fix: `${prefix}grid-cols-1` } })
          return
        }
      }
    }
    // ESLint enters a node before its descendants, so a unit (class attribute, helper call,
    // template) has marked everything it evaluates before any of it is visited on its own. A node it
    // did not reach (a function body, a member lookup, a sequence) falls through and is checked
    // alone, so an unmodelled shape is gated, never skipped.
    const reached = new WeakSet()
    const evaluate = (node, value) => {
      if (!reached.has(node)) check(node, collectStaticText(value, reached))
    }
    return {
      JSXAttribute(node) {
        if (isClassAttribute(node)) evaluate(node, node.value)
      },
      CallExpression(node) {
        if (isHelperCall(node)) evaluate(node, node)
      },
      TemplateLiteral(node) {
        evaluate(node, node)
      },
      Literal(node) {
        if (typeof node.value === 'string') evaluate(node, node)
      },
    }
  },
}

const plugin = { rules: { 'responsive-grid-base-track': responsiveGridBaseTrack } }
export default plugin
