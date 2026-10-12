import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * A taller Button is set with min-h, never a fixed h-. Below a 24rem viewport the Button's narrow
 * state sets h-auto so a label can wrap (components/ui/Button.tsx, wrapWhenNarrow), and that rule sits
 * after every base utility in the stylesheet, so a caller's `h-11` becomes 40px on a 360px phone while
 * its `min-h-11` is kept (frontend/DESIGN_SYSTEM.md, Button size). This gate reads every <Button> and
 * every buttonVariants() call under app, components, features, hooks and lib and fails when the
 * className it is given, a literal or a same-file const, carries a bare `h-<n>` token; icon-sm, whose
 * square never wraps, is exempt.
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const FIXED_HEIGHT = /(?:^|\s)!?h-(?:\d+(?:\.\d+)?|px|\[[^\]]+\])(?=\s|$)/

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

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

const text = (e: ts.Expression | undefined): string | null => (e && (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) ? e.text : null)

describe('a taller Button is set with min-h, never a fixed h-', () => {
  it('no <Button> or buttonVariants() call under the app passes a bare h-<n> in its className', () => {
    const offenders: string[] = []
    for (const file of SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))) {
      const rel = path.relative(ROOT, file)
      const sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
      const report = (n: ts.Node, className: ts.Expression, size: string | null) => {
        if (size === 'icon-sm') return
        for (const value of literals(className, sf)) {
          const hit = FIXED_HEIGHT.exec(value)
          if (hit) offenders.push(`${rel}:${sf.getLineAndCharacterOfPosition(n.getStart(sf)).line + 1} "${hit[0].trim()}" (use min-h)`)
        }
      }
      const visit = (node: ts.Node) => {
        if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText() === 'Button') {
          const attr = (name: string) => node.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText() === name)
          const className = attr('className')?.initializer
          const sizeAttr = attr('size')?.initializer
          const size = sizeAttr && ts.isStringLiteral(sizeAttr) ? sizeAttr.text : null
          if (className) report(node, ts.isJsxExpression(className) ? className.expression ?? className : className, size)
        }
        if (ts.isCallExpression(node) && node.expression.getText() === 'buttonVariants' && node.arguments[0] && ts.isObjectLiteralExpression(node.arguments[0])) {
          const prop = (name: string) => node.arguments[0] && ts.isObjectLiteralExpression(node.arguments[0])
            ? node.arguments[0].properties.find((p): p is ts.PropertyAssignment => ts.isPropertyAssignment(p) && p.name.getText() === name)
            : undefined
          const className = prop('className')?.initializer
          if (className) report(node, className, text(prop('size')?.initializer))
        }
        ts.forEachChild(node, visit)
      }
      visit(sf)
    }
    expect(offenders, 'below 24rem the narrow state sets h-auto; a caller keeps its min-h, never its h-').toEqual([])
  })
})
