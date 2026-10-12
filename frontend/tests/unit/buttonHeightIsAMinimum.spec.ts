import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * A taller Button is set with min-h, never a fixed h-, and through the factory's own className
 * option. Below a 24rem viewport the Button's narrow state sets h-auto so a label can wrap
 * (components/ui/Button.tsx, wrapWhenNarrow), and that rule sits after every base utility in the
 * stylesheet, so a caller's `h-11` becomes 40px on a 360px phone while its `min-h-11` is kept; the
 * narrow state keeps a caller's min-h or py only when it can see them, which is the className option
 * of buttonVariants() (<Button> and the wrappers pass theirs through it), never a token beside the
 * factory's output in cx() or a template (frontend/DESIGN_SYSTEM.md, Button size). This gate reads,
 * under app, components, features, hooks and lib, every <Button>, <RetryButton> and <MarketingCta>
 * className and every buttonVariants() className option (a literal, a same-file const, a shorthand
 * property, a conditional's branches, a template's text) and fails on a bare `h-<n>` token; and every
 * className expression that composes buttonVariants() with a literal `h-`, `min-h-` or `py-` token
 * outside the call. icon-sm, whose square never wraps, is exempt from the first; a const imported from
 * another file is not read.
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
/** The components that forward a className into buttonVariants(). */
const BUTTON_TAGS = new Set(['Button', 'RetryButton', 'MarketingCta'])
const FIXED_HEIGHT = /(?:^|\s)!?h-(?:\d+(?:\.\d+)?|px|\[[^\]]+\])(?=\s|$)/
const HEIGHT_OR_PADDING = /(?:^|\s)!?(?:min-h-[^\s]+|py-[^\s]+|h-(?:\d+(?:\.\d+)?|px|\[[^\]]+\]))(?=\s|$)/

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

const isFactoryCall = (n: ts.Node): n is ts.CallExpression => ts.isCallExpression(n) && n.expression.getText() === 'buttonVariants'

/** The literal strings an expression can be: a literal, a same-file const, a conditional's branches, a template's text. */
function literals(e: ts.Expression, sf: ts.SourceFile, depth = 0): string[] {
  if (depth > 4) return []
  if (ts.isParenthesizedExpression(e)) return literals(e.expression, sf, depth + 1)
  if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) return [e.text]
  if (ts.isTemplateExpression(e)) return [[e.head.text, ...e.templateSpans.map((s) => s.literal.text)].join(' ')]
  if (ts.isConditionalExpression(e)) return [...literals(e.whenTrue, sf, depth + 1), ...literals(e.whenFalse, sf, depth + 1)]
  if (ts.isBinaryExpression(e)) return [...literals(e.left, sf, depth + 1), ...literals(e.right, sf, depth + 1)]
  if (ts.isCallExpression(e)) return e.arguments.flatMap((a) => literals(a, sf, depth + 1))
  if (ts.isIdentifier(e)) {
    let init: ts.Expression | undefined
    const find = (n: ts.Node) => {
      if (!init && ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === e.text && n.initializer) init = n.initializer
      ts.forEachChild(n, find)
    }
    find(sf)
    return init ? literals(init, sf, depth + 1) : []
  }
  return []
}

/** The literal strings an expression carries outside any buttonVariants() call inside it. */
function literalsBeside(e: ts.Expression, sf: ts.SourceFile): string[] {
  if (isFactoryCall(e)) return []
  if (ts.isParenthesizedExpression(e)) return literalsBeside(e.expression, sf)
  if (ts.isConditionalExpression(e)) return [...literalsBeside(e.whenTrue, sf), ...literalsBeside(e.whenFalse, sf)]
  if (ts.isBinaryExpression(e)) return [...literalsBeside(e.left, sf), ...literalsBeside(e.right, sf)]
  if (ts.isCallExpression(e)) return e.arguments.flatMap((a) => literalsBeside(a, sf))
  if (ts.isTemplateExpression(e)) {
    return [e.head.text, ...e.templateSpans.map((s) => s.literal.text), ...e.templateSpans.flatMap((s) => literalsBeside(s.expression, sf))]
  }
  return literals(e, sf)
}

const stringOf = (e: ts.Expression | undefined): string | null => {
  const x = e && ts.isJsxExpression(e) ? e.expression : e
  return x && (ts.isStringLiteral(x) || ts.isNoSubstitutionTemplateLiteral(x)) ? x.text : null
}

describe('a taller Button is set with min-h, never a fixed h-, through the factory', () => {
  it('no Button-like className or buttonVariants() option carries a bare h-<n>, and no height or padding sits beside the factory', () => {
    const offenders: string[] = []
    for (const file of SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))) {
      const rel = path.relative(ROOT, file)
      const sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
      const at = (n: ts.Node) => `${rel}:${sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1}`
      const reportFixed = (n: ts.Node, className: ts.Expression, size: string | null) => {
        if (size === 'icon-sm') return
        for (const value of literals(className, sf)) {
          const hit = FIXED_HEIGHT.exec(value)
          if (hit) offenders.push(`${at(n)} "${hit[0].trim()}" (use min-h)`)
        }
      }
      const visit = (node: ts.Node) => {
        if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
          const attr = (name: string) => node.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText() === name)
          const init = attr('className')?.initializer
          const className = init && ts.isJsxExpression(init) ? init.expression : init
          if (className) {
            if (BUTTON_TAGS.has(node.tagName.getText())) reportFixed(node, className, stringOf(attr('size')?.initializer))
            let composesFactory = false
            const look = (n: ts.Node) => { if (isFactoryCall(n)) composesFactory = true; else ts.forEachChild(n, look) }
            look(className)
            if (composesFactory) {
              for (const value of literalsBeside(className, sf)) {
                const hit = HEIGHT_OR_PADDING.exec(value)
                if (hit) offenders.push(`${at(node)} "${hit[0].trim()}" beside buttonVariants() (pass it through the factory's className option)`)
              }
            }
          }
        }
        if (isFactoryCall(node) && node.arguments[0] && ts.isObjectLiteralExpression(node.arguments[0])) {
          const options = node.arguments[0]
          const prop = (name: string) => {
            const p = options.properties.find((p) => (ts.isPropertyAssignment(p) || ts.isShorthandPropertyAssignment(p)) && p.name.getText() === name)
            return p && ts.isPropertyAssignment(p) ? p.initializer : p && ts.isShorthandPropertyAssignment(p) ? p.name : undefined
          }
          const className = prop('className')
          if (className) reportFixed(node, className, stringOf(prop('size')))
        }
        ts.forEachChild(node, visit)
      }
      visit(sf)
    }
    expect(offenders, 'below 24rem the narrow state sets h-auto and keeps only the min-h and py it can see, the factory\'s className option').toEqual([])
  })
})
