import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Tailwind generates only the class names its extractor finds whole in the source
 * (lessons/frontend-tailwind-classes-are-written-whole.md). A class assembled from an interpolated
 * prefix (`${NARROW}h-auto`) or suffix (`text-${tone}`) looks right in a class string, passes every
 * test that reads the string, and emits no CSS. This gate fails on a template literal, anywhere under
 * app, components, features or lib, whose interpolation runs straight into a hyphenated utility token
 * with no separator between them, or whose literal text ends in a hyphenated utility stem that runs
 * straight into an interpolation. Identifiers, URLs and measurements (`${id}-row`, `${base}/api`,
 * `${n}px`) do not match: the token after the interpolation must begin with a letter and carry a
 * hyphen, and the stem before it must be a known utility family followed by its hyphen. An
 * interpolation that can only yield whole tokens, a conditional between string literals that end
 * in a space or are empty (`${hint ? 'mt-1.5 ' : ''}inline-flex`), leaves the next token whole.
 */
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'lib']
const UTILITY_AFTER = /^[a-z][a-z0-9]*(?:-[a-z0-9.[\]/%]+)+(?=\s|$)/
const STEM_BEFORE =
  /(?:^|\s)(?:[a-z0-9[\]().:@-]+:)?(?:h|w|min-h|min-w|max-w|max-h|p[xytblr]?|m[xytblr]?|gap|space-[xy]|text|bg|border|rounded|ring|shadow|font|leading|tracking|whitespace|opacity|z|inset|top|left|right|bottom|translate-[xy]|scale|rotate|grid-cols|grid-rows|col|row|order|basis|flex|justify|items|self|place|content|duration|delay|ease|fill|stroke|outline|decoration|underline-offset|aspect|object|overflow|cursor|select|pointer-events|transition|animate|divide|from|via|to|line-clamp|indent|columns|size)-$/

/** Whether an interpolation can only end in a space or nothing, so the literal after it stays a whole token. */
function endsClean(e: ts.Expression): boolean {
  if (ts.isParenthesizedExpression(e)) return endsClean(e.expression)
  if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) return e.text === '' || /\s$/.test(e.text)
  if (ts.isConditionalExpression(e)) return endsClean(e.whenTrue) && endsClean(e.whenFalse)
  if (ts.isBinaryExpression(e) && (e.operatorToken.kind === ts.SyntaxKind.BarBarToken || e.operatorToken.kind === ts.SyntaxKind.QuestionQuestionToken)) return endsClean(e.left) && endsClean(e.right)
  return false
}

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

describe('every Tailwind class is written whole', () => {
  it('no template literal under app, components, features or lib composes a class from an interpolation', () => {
    const offenders: string[] = []
    for (const file of SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))) {
      const rel = path.relative(ROOT, file)
      const sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)
      const visit = (node: ts.Node) => {
        if (ts.isTemplateExpression(node)) {
          let before = node.head.text
          for (const span of node.templateSpans) {
            const after = span.literal.text
            const afterMatch = UTILITY_AFTER.exec(after)
            const line = sf.getLineAndCharacterOfPosition(span.getStart(sf)).line + 1
            if (afterMatch && !endsClean(span.expression)) offenders.push(`${rel}:${line} "\${…}${afterMatch[0]}"`)
            if (STEM_BEFORE.test(before)) offenders.push(`${rel}:${line} "${before.trim().split(/\s+/).pop()}\${…}"`)
            before = after
          }
        }
        ts.forEachChild(node, visit)
      }
      visit(sf)
    }
    expect(offenders, 'write the whole class per case and let a map choose between whole strings').toEqual([])
  })
})
