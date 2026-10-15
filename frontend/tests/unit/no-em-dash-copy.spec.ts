import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Copy-voice structural guard: no em-dashes in user-facing copy
 * (docs/voice-and-style.md). The 2026-07 copy pass removed every em-dash from
 * string literals, template literals, and JSX text across the app source;
 * this spec keeps them out. Comments are naturally exempt (the AST walk never
 * sees them), and the ONE sanctioned use — the bare '—' missing-value token
 * rendered in tables and detail rows (lib/format.ts MISSING_TOKENS) — is
 * exempted as an exact-match literal that stands alone: a JSX text node whose
 * trim is '—' as the sole child of its element (`<td>—</td>`), or a string or
 * no-substitution template literal whose text is exactly '—' where the value
 * it gives stands alone. As a JSX child (the literal itself, or a branch of a
 * conditional, of `??` or `||`, or the right of `&&` around it) it is held to
 * the same test as the text: exempt only as its element's sole meaningful
 * child (`<td>{'—'}</td>`, `<td>{v ?? '—'}</td>`). Beside sibling children it
 * is copy and fails, and so it does as an operand of `+`, the right of `+=` or
 * a template's substitution; a template's head, middle or tail is never
 * exempt, since the template joins it to what its substitutions render. So a
 * spaced dash beside an expression fails in each spelling: `— {speaker}`,
 * `{'—'} {speaker}`, `'—' + ' ' + speaker` (BG-02). A token held in a name,
 * handed to a function (a formatter's fallback) or returned is read where it
 * is written, and exempt there; what the code does with it afterwards (a
 * `concat`, an array's `join`, a sibling the name is rendered beside) is out
 * of a literal scan's reach and review-checked. The self-check below plants
 * each form.
 *
 * If you're writing copy and want a dash: restructure the sentence (split it,
 * use a colon, or a middot separator for compact labels). En-dashes (–) in
 * genuine ranges (Q1–Q4, 30–60s) are allowed and not checked here.
 */

const FRONTEND_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCANNED_DIRS = ['app', 'components', 'features', 'lib', 'hooks']
const EM_DASH = '—'

function sourceFiles(dir: string): string[] {
  if (!existsSync(dir)) return []
  const out: string[] = []
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry)
    if (statSync(full).isDirectory()) {
      out.push(...sourceFiles(full))
    } else if (/\.(ts|tsx)$/.test(entry) && !/\.(spec|test)\.(ts|tsx)$/.test(entry)) {
      out.push(full)
    }
  }
  return out
}

/** Whether a JSX child is the only meaningful child of its element (whitespace-only text, and an
    expression that holds nothing or only a comment, aside). */
function soleChild(child: ts.JsxText | ts.JsxExpression): boolean {
  const parent = child.parent
  if (!ts.isJsxElement(parent) && !ts.isJsxFragment(parent)) return false
  const meaningful = parent.children.filter(
    (c) => !(ts.isJsxText(c) && c.containsOnlyTriviaWhiteSpaces) && !(ts.isJsxExpression(c) && !c.expression),
  )
  return meaningful.length === 1 && meaningful[0] === child
}

/** The bare missing-value token is the one sanctioned em-dash: a JSX text node trimming to '—' that is the
    only child of its element, or a string or no-substitution template literal that is exactly '—' where the
    value it gives stands alone (see the header). */
function isBareMissingToken(node: ts.Node, literalText: string): boolean {
  if (ts.isJsxText(node)) return literalText.trim() === EM_DASH && soleChild(node)
  // A template's head, middle or tail is joined to what its substitutions render: never the whole value.
  if (!ts.isStringLiteral(node) && !ts.isNoSubstitutionTemplateLiteral(node)) return false
  if (literalText !== EM_DASH) return false
  // Follow the value up to where it is used, through what passes it on unchanged as React renders it:
  // parentheses, a type assertion, a conditional's branch, either side of `??` or `||` and the right of `&&`.
  let value: ts.Node = node
  for (;;) {
    const up: ts.Node = value.parent
    const op = ts.isBinaryExpression(up) ? up.operatorToken.kind : undefined
    if (ts.isParenthesizedExpression(up) || ts.isAsExpression(up) || ts.isSatisfiesExpression(up) || ts.isNonNullExpression(up)) value = up
    else if (ts.isConditionalExpression(up) && up.condition !== value) value = up
    else if (op === ts.SyntaxKind.QuestionQuestionToken || op === ts.SyntaxKind.BarBarToken) value = up
    else if (op === ts.SyntaxKind.AmpersandAmpersandToken && (up as ts.BinaryExpression).right === value) value = up
    else break
  }
  const use = value.parent
  // Joined into copy: an operand of `+`, the right of `+=`, a template's substitution.
  if (ts.isBinaryExpression(use)) {
    const op = use.operatorToken.kind
    if (op === ts.SyntaxKind.PlusToken || (op === ts.SyntaxKind.PlusEqualsToken && use.right === value)) return false
  }
  if (ts.isTemplateSpan(use)) return false
  // A JSX child: the token only as its element's sole meaningful child, as JSX text is (an attribute's value stands alone).
  if (ts.isJsxExpression(use) && !ts.isJsxAttribute(use.parent)) return soleChild(use)
  return true
}

/** Every em-dash in `text` outside the sanctioned token, as `file:line text`. */
function violationsIn(text: string, file: string): string[] {
  if (!text.includes(EM_DASH)) return []
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const violations: string[] = []

  const record = (node: ts.Node, literalText: string) => {
    if (!literalText.includes(EM_DASH) || isBareMissingToken(node, literalText)) return
    const { line } = source.getLineAndCharacterOfPosition(node.getStart())
    violations.push(`${path.relative(FRONTEND_ROOT, file)}:${line + 1} ${literalText.trim().slice(0, 80)}`)
  }

  const visit = (node: ts.Node) => {
    if (
      ts.isStringLiteral(node) ||
      ts.isNoSubstitutionTemplateLiteral(node) ||
      ts.isTemplateHead(node) ||
      ts.isTemplateMiddle(node) ||
      ts.isTemplateTail(node) ||
      ts.isJsxText(node)
    ) {
      record(node, node.text)
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return violations
}

const emDashViolations = (file: string): string[] => violationsIn(readFileSync(file, 'utf8'), file)

describe('no em-dashes in user-facing copy (voice guard)', () => {
  it('reads every form of the missing-value token (a self-check on fixed sources)', () => {
    const file = path.join(FRONTEND_ROOT, 'features/zzprobe/Probe.tsx')
    const src = [
      'export const A = ({ speaker, v }: { speaker: string; v?: string }) => (',
      '  <>',
      '    <td>—</td>',
      "    <td>{'—'}</td>",
      "    <td>{v ?? '—'}</td>",
      '    <td>{/* empty */}{`—`}</td>',
      "    <span title={'—'}>{speaker}</span>",
      '    <cite>— {speaker}</cite>',
      "    <cite>{'—'} {speaker}</cite>",
      "    <cite>{v ? '—' : ''} {speaker}</cite>",
      "    <cite>{speaker} {v || ('—')}</cite>",
      '  </>',
      ')',
      "export const B = (speaker: string) => '—' + ' ' + speaker",
      "export const C = (speaker: string) => `${'—'} ${speaker}`",
      'export const D = (speaker: string) => `—${speaker}`',
      "export const E = (speaker: string) => { let s = speaker; s += '—'; return s }",
      "export const MISSING = '—'",
      "export const F = (x?: string) => (x !== '—' ? x : null) ?? `—`",
    ].join('\n')
    // Lines 3 to 7 stand alone (the text, the literal, a fallback, a template beside an empty expression, an
    // attribute's value) and 18 to 19 are read where they are written (a name, a comparison, a fallback returned).
    // Lines 8 to 11 sit beside sibling children (as text, a literal, a conditional's branch, the right of `||`
    // in parentheses), 14 is a `+` operand, 15 a template's substitution, 16 a template's head and 17 the
    // right of `+=`.
    expect(violationsIn(src, file)).toEqual([8, 9, 10, 11, 14, 15, 16, 17].map((line) => `features/zzprobe/Probe.tsx:${line} —`))
  })

  it('finds no em-dash in any string literal, template literal, or JSX text', () => {
    const violations = SCANNED_DIRS.flatMap((dir) => sourceFiles(path.join(FRONTEND_ROOT, dir))).flatMap(
      emDashViolations,
    )
    expect(
      violations,
      `Em-dash found in copy. Restructure the sentence instead (docs/voice-and-style.md): ` +
        `split it, use a colon, or a middot for compact labels.\n${violations.join('\n')}`,
    ).toEqual([])
  })
})
