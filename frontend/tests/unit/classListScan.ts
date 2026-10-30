/* =============================================================================
   classListScan.ts — the class lists the design gates read
   -----------------------------------------------------------------------------
   Shared by tests/unit/pulsingMarkAllowlist.spec.ts and
   tests/unit/spinnerAllowlist.spec.ts, whose headers state what each one looks
   for and whose planted forms hold this reader. A gate passes a test over a
   list's tokens; a site is the innermost list that passes it, counted once (a
   list, not an element: an element whose ternary picks between two such lists
   counts two):
     string — any string literal or template chunk whose tokens pass, wherever
              it sits (the reader cannot tell a class string from any other);
     class  — a list whose parts together pass: a cx() or clsx() call, a
              template, an array literal joined into one string (through any
              filter or map, cast or parenthesis on the way), or a class
              attribute (className, iconClassName and the like) whatever builds
              it. A list bound to a const counts where it is written; a
              ternary's arms count together.
   Comments never count: the reader walks each file's TypeScript AST. Out of
   reach: a token held in a binding (a const, an import, a parameter) and split
   from the rest of its list, a helper other than cx() or clsx() outside any
   class list, and a `+` concatenation.
============================================================================= */

import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'

export const CLASS_ATTRIBUTE = /^\w*[cC]lassName$/
// The app's two class joiners: components/ui/cx and the clsx package.
const CLASS_JOINERS = new Set(['cx', 'clsx'])

export const tokensOf = (text: string) => text.split(/\s+/).filter(Boolean)

/** The expression under any parentheses, `as`, `satisfies`, `!` or angle-bracket cast. */
function unwrapped(expr: ts.Expression): ts.Expression {
  while (
    ts.isParenthesizedExpression(expr) ||
    ts.isAsExpression(expr) ||
    ts.isSatisfiesExpression(expr) ||
    ts.isNonNullExpression(expr) ||
    ts.isTypeAssertionExpression(expr)
  ) {
    expr = expr.expression
  }
  return expr
}

/** An array literal joined into one string, through any filter, map or cast on the way: [a, b && c].filter(Boolean).join(' '). */
function joinedArray(node: ts.Node): boolean {
  if (!ts.isCallExpression(node) || !ts.isPropertyAccessExpression(node.expression) || node.expression.name.text !== 'join') return false
  let receiver = unwrapped(node.expression.expression)
  while (ts.isCallExpression(receiver) && ts.isPropertyAccessExpression(receiver.expression)) receiver = unwrapped(receiver.expression.expression)
  return ts.isArrayLiteralExpression(receiver)
}

const isLiteralChunk = (n: ts.Node): n is ts.StringLiteralLike | ts.TemplateHead | ts.TemplateMiddle | ts.TemplateTail =>
  ts.isStringLiteralLike(n) || ts.isTemplateHead(n) || ts.isTemplateMiddle(n) || ts.isTemplateTail(n)

/** Every string or template chunk under `node`. */
export function literalTexts(node: ts.Node): string[] {
  const out: string[] = []
  const visit = (n: ts.Node): void => {
    if (isLiteralChunk(n)) out.push(n.text)
    ts.forEachChild(n, visit)
  }
  visit(node)
  return out
}

export function parse(source: string, fileName: string): ts.SourceFile {
  return ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, fileName.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
}

/** How many class lists in `source` pass `passes`, each the innermost list that does, counted once. */
export function classListSites(source: string, fileName: string, passes: (tokens: string[]) => boolean): number {
  const sourceFile = parse(source, fileName)
  // A class list beyond one string: a class attribute (whatever builds it), a joiner's call, a template, or an array
  // literal joined into one string.
  const isClassList = (node: ts.Node) =>
    (ts.isJsxAttribute(node) && !!node.initializer && CLASS_ATTRIBUTE.test(node.name.getText(sourceFile))) ||
    (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && CLASS_JOINERS.has(node.expression.text)) ||
    ts.isTemplateExpression(node) ||
    joinedArray(node)
  let sites = 0
  // Whether a site was counted at or under `node`: a class list counts only when nothing inside it did.
  const visit = (node: ts.Node): boolean => {
    if (isLiteralChunk(node)) {
      if (!passes(tokensOf(node.text))) return false
      sites++
      return true
    }
    let inner = false
    ts.forEachChild(node, (child) => {
      if (visit(child)) inner = true
    })
    if (inner || !isClassList(node) || !passes(literalTexts(node).flatMap(tokensOf))) return inner
    sites++
    return true
  }
  visit(sourceFile)
  return sites
}

/** Every .ts and .tsx file under `root`'s `dirs`, as a path relative to `root` with forward slashes. */
export function sourceFiles(root: string, dirs: readonly string[]): string[] {
  const out: string[] = []
  const walk = (dir: string): void => {
    if (!fs.existsSync(dir)) return
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, entry.name)
      if (entry.isDirectory()) walk(p)
      else if (/\.tsx?$/.test(entry.name)) out.push(path.relative(root, p).split(path.sep).join('/'))
    }
  }
  for (const dir of dirs) walk(path.join(root, dir))
  return out
}
