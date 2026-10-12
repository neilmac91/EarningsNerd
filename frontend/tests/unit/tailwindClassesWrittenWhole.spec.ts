import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Tailwind generates only the class names its extractor finds whole in the source
 * (lessons/frontend-tailwind-classes-are-written-whole.md). A class assembled from an interpolated
 * prefix (`${NARROW}h-auto`), a suffix (`text-${tone}`), a concatenation (`NARROW + 'h-auto'`) or a
 * map over fragments (`['h-auto'].map((c) => `${NARROW}${c}`)`) looks right in a class string, passes
 * every test that reads the string, and emits no CSS. This gate fails, anywhere under app,
 * components, features or lib, on: a template interpolation or a `+` operand that resolves to a
 * variant prefix (a string ending in ":", read through a same-file const, a conditional or a
 * concatenation); an interpolation or a non-literal `+` operand that runs straight into a utility
 * token (hyphenated, or one of the single-word utilities); and a utility stem (`text-`, `bg-`, …)
 * that runs straight into an interpolation or a non-literal operand. Identifiers, URLs and
 * measurements (`${id}-row`, `${base}/api`, `${n}px`, `base + ' h-auto'`) do not match: the token after
 * the join must begin with a letter and be a utility, and the stem before it must be a known family
 * followed by its hyphen. An interpolation that can only yield whole tokens, a conditional between
 * string literals that end in a space or are empty (`${hint ? 'mt-1.5 ' : ''}inline-flex`), leaves
 * the next token whole.
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'lib']
const UTILITY_AFTER = /^[a-z][a-z0-9]*(?:-[a-z0-9.[\]/%]+)+(?=\s|$)/
const STEM_BEFORE =
  /(?:^|\s)-?(?:[a-z0-9[\]().:@-]+:)?(?:h|w|min-h|min-w|max-w|max-h|p[xytblr]?|m[xytblr]?|gap|space-[xy]|text|bg|border|rounded|ring|shadow|font|leading|tracking|whitespace|opacity|z|inset|top|left|right|bottom|translate-[xy]|scale|rotate|grid-cols|grid-rows|col|row|order|basis|flex|justify|items|self|place|content|duration|delay|ease|fill|stroke|outline|decoration|underline-offset|aspect|object|overflow|cursor|select|pointer-events|transition|animate|divide|from|via|to|line-clamp|indent|columns|size)-\[?$/

const SINGLE_UTILITIES = new Set([
  'hidden', 'flex', 'grid', 'block', 'inline', 'contents', 'relative', 'absolute', 'fixed', 'sticky', 'static', 'visible',
  'invisible', 'truncate', 'uppercase', 'lowercase', 'capitalize', 'italic', 'underline', 'overline', 'antialiased',
  'isolate', 'container', 'rounded', 'border', 'shadow', 'ring', 'outline', 'transition', 'resize', 'table', 'grow',
  'shrink', 'collapse', 'tabular-nums', 'sr-only',
])
/** Whether text begins with a utility token: a hyphenated one, a single-word one followed by a space or
    the end, or either behind a ":" (an interpolated variant name, `${bp}:flex`). */
function utilityHead(text: string): string | null {
  const rest = text.startsWith(':') ? text.slice(1) : text
  const hyphenated = UTILITY_AFTER.exec(rest)
  if (hyphenated) return (text.startsWith(':') ? ':' : '') + hyphenated[0]
  const word = /^[a-z][a-z0-9-]*(?=\s|$)/.exec(rest)
  return word && SINGLE_UTILITIES.has(word[0]) ? (text.startsWith(':') ? ':' : '') + word[0] : null
}

/** Whether an interpolation can only end in a space or nothing, so the literal after it stays a whole token. */
function endsClean(e: ts.Expression): boolean {
  if (ts.isParenthesizedExpression(e)) return endsClean(e.expression)
  if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) return e.text === '' || /\s$/.test(e.text)
  if (ts.isConditionalExpression(e)) return endsClean(e.whenTrue) && endsClean(e.whenFalse)
  if (ts.isBinaryExpression(e) && (e.operatorToken.kind === ts.SyntaxKind.BarBarToken || e.operatorToken.kind === ts.SyntaxKind.QuestionQuestionToken)) return endsClean(e.left) && endsClean(e.right)
  return false
}

/** The string an expression is known to end with: a literal's text, a same-file const's, a conditional's branches. */
function knownEndings(e: ts.Expression, sf: ts.SourceFile, depth = 0): string[] {
  if (depth > 4) return []
  if (ts.isParenthesizedExpression(e)) return knownEndings(e.expression, sf, depth + 1)
  if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) return [e.text]
  if (ts.isTemplateExpression(e)) return [e.templateSpans[e.templateSpans.length - 1].literal.text]
  if (ts.isConditionalExpression(e)) return [...knownEndings(e.whenTrue, sf, depth + 1), ...knownEndings(e.whenFalse, sf, depth + 1)]
  if (ts.isBinaryExpression(e) && e.operatorToken.kind === ts.SyntaxKind.PlusToken) return knownEndings(e.right, sf, depth + 1)
  if (ts.isIdentifier(e)) {
    let init: ts.Expression | undefined
    const find = (n: ts.Node) => {
      if (!init && ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === e.text && n.initializer) init = n.initializer
      ts.forEachChild(n, find)
    }
    find(sf)
    return init ? knownEndings(init, sf, depth + 1) : []
  }
  return []
}
/** Whether an expression resolves to a variant prefix, a chain of `token:` segments with no space (`sm:`,
    `dark:hover:`, `[@media(max-width:24rem)]:`), the surest sign of a composed class. Prose that ends in a
    colon has spaces in it and is not one. */
const variantPrefix = (e: ts.Expression, sf: ts.SourceFile) => knownEndings(e, sf).some((text) => /^(?:[a-z0-9[\]().:@=/-]+:)+$/.test(text))
const isStringy = (e: ts.Expression) => ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

describe('every Tailwind class is written whole', () => {
  it('nothing under app, components, features or lib composes a class from an interpolation or a concatenation', () => {
    const offenders: string[] = []
    for (const file of SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))) {
      const rel = path.relative(ROOT, file)
      const sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
      const at = (n: ts.Node) => `${rel}:${sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1}`
      const visit = (node: ts.Node) => {
        if (ts.isTemplateExpression(node)) {
          let before = node.head.text
          for (const span of node.templateSpans) {
            const after = span.literal.text
            const head = utilityHead(after)
            if (variantPrefix(span.expression, sf)) offenders.push(`${at(span)} "\${…}" is a variant prefix`)
            else if (head && !endsClean(span.expression)) offenders.push(`${at(span)} "\${…}${head}"`)
            if (STEM_BEFORE.test(before)) offenders.push(`${at(span)} "${before.trim().split(/\s+/).pop()}\${…}"`)
            before = after
          }
        }
        if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
          const { left, right } = node
          if (variantPrefix(left, sf) && !(isStringy(right) && /^\s/.test(right.text))) offenders.push(`${at(node)} "${left.getText(sf)} + …" is a variant prefix`)
          else if (isStringy(right) && utilityHead(right.text) && !isStringy(left)) offenders.push(`${at(node)} "… + '${utilityHead(right.text)}'"`)
          if (isStringy(left) && STEM_BEFORE.test(left.text) && !isStringy(right)) offenders.push(`${at(node)} "'${left.text.trim().split(/\s+/).pop()}' + …"`)
        }
        ts.forEachChild(node, visit)
      }
      visit(sf)
    }
    expect(offenders, 'write the whole class per case and let a map choose between whole strings').toEqual([])
  })
})
