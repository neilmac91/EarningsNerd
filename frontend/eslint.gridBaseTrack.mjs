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
// md:grid-cols-3`. This rule parses each class token's variants and evaluates everything that lands
// on one element together: a class attribute (`className`, `*ClassName`) and a class-helper call
// (cx/clsx/…) with all their literal, template and branch text. A string in there that is a grid on
// its own (it has `grid`) must also pass on its own, so one branch of a conditional can't borrow
// another branch's base. Any other string or template literal is evaluated on its own, so a class
// constant or map is gated too, and a function (`className={() => cx(…)}`) starts afresh. Pinned by
// tests/unit/gridBaseTrackRule.spec.ts.
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
 *  chunks joined): both arms of a conditional or logical, helper-call arguments, array elements,
 *  object keys and values. */
function collectStaticText(node, out) {
  if (!node) return out
  switch (node.type) {
    case 'Literal':
      if (typeof node.value === 'string') out.push(node.value)
      break
    case 'TemplateLiteral':
      out.push(node.quasis.map((q) => q.value.cooked ?? q.value.raw).join(' '))
      for (const e of node.expressions) collectStaticText(e, out)
      break
    case 'JSXExpressionContainer':
    case 'TSAsExpression':
    case 'TSSatisfiesExpression':
    case 'TSNonNullExpression':
    case 'ChainExpression':
      collectStaticText(node.expression, out)
      break
    case 'ConditionalExpression':
      collectStaticText(node.consequent, out)
      collectStaticText(node.alternate, out)
      break
    case 'LogicalExpression':
      collectStaticText(node.left, out)
      collectStaticText(node.right, out)
      break
    case 'BinaryExpression':
      if (node.operator === '+') {
        collectStaticText(node.left, out)
        collectStaticText(node.right, out)
      }
      break
    case 'CallExpression':
      if (node.callee.type === 'MemberExpression') collectStaticText(node.callee.object, out)
      for (const a of node.arguments) collectStaticText(a, out)
      break
    case 'ArrayExpression':
      for (const el of node.elements) collectStaticText(el, out)
      break
    case 'ObjectExpression':
      for (const p of node.properties) {
        if (p.type !== 'Property') continue
        if (p.key.type === 'Literal') collectStaticText(p.key, out)
        collectStaticText(p.value, out)
      }
      break
  }
  return out
}

const isClassAttribute = (node) =>
  node.type === 'JSXAttribute' && node.name.type === 'JSXIdentifier' && CLASS_ATTRIBUTE.test(node.name.name)
const isHelperCall = (node) =>
  node.type === 'CallExpression' && node.callee.type === 'Identifier' && CLASS_HELPERS.has(node.callee.name)
/** A node inside one of these is evaluated as part of it, not on its own; a function between them
 *  ends the unit, since its return value is a class string of its own. */
const isUnit = (node) => isClassAttribute(node) || isHelperCall(node) || node.type === 'TemplateLiteral'
const isFunction = (node) => /^(ArrowFunctionExpression|FunctionExpression|FunctionDeclaration)$/.test(node.type)
function insideUnit(node) {
  for (let p = node.parent; p && !isFunction(p); p = p.parent) if (isUnit(p)) return true
  return false
}
const isGridPiece = (text) =>
  text.split(/\s+/).some((token) => {
    const t = parseClassToken(token)
    return t !== null && isGridDisplay(t)
  })

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
    // The whole unit must pass, and so must each piece that is a grid by itself.
    const check = (node, pieces) => {
      for (const text of [pieces.join(' '), ...pieces.filter(isGridPiece)]) {
        const prefix = gridBaseTrackProblem(text)
        if (prefix !== null) {
          context.report({ node, messageId: 'missing', data: { fix: `${prefix}grid-cols-1` } })
          return
        }
      }
    }
    return {
      JSXAttribute(node) {
        if (isClassAttribute(node) && !insideUnit(node)) check(node, collectStaticText(node.value, []))
      },
      CallExpression(node) {
        if (isHelperCall(node) && !insideUnit(node)) check(node, collectStaticText(node, []))
      },
      TemplateLiteral(node) {
        if (!insideUnit(node)) check(node, collectStaticText(node, []))
      },
      Literal(node) {
        if (typeof node.value === 'string' && !insideUnit(node)) check(node, [node.value])
      },
    }
  },
}

const plugin = { rules: { 'responsive-grid-base-track': responsiveGridBaseTrack } }
export default plugin
