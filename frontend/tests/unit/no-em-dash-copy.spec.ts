import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { scopeResolver } from './heldValues'

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
 * `{'—'} {speaker}`, `'—' + ' ' + speaker` (BG-02). A token held in a `const`
 * or `let` is followed to each reference of the name in its file, one name at
 * a time (a name holding the name is followed too), and each reference is held
 * to the same test, so `const DASH = '—'` rendered as `{DASH} {speaker}` fails
 * at the reference, and a token held in an object's property under such a
 * name (`const BOX = { token: '—' }`, or the shorthand `{ DASH }` of a name
 * holding it) is followed to each `BOX.token` read the same way. A reference
 * is the name's by scope (scopeResolver in heldValues.ts), so a same-named
 * binding in a nested scope, a parameter of that name, and an object a nested
 * scope declares under the holder's name are their own values, never the
 * token's, and a token a nested scope declares is followed to its own reads
 * only. A reference the scan cannot see (an export read
 * in another file, a destructured read such as `const { token } = BOX`, an
 * object or array passed on whole), an array's element and what a function or
 * an array does with the token afterwards (a formatter's fallback, a `concat`,
 * a `join`) are out of a literal scan's reach and review-checked, as is a token
 * handed to a function or returned, which is read where it is written. The
 * self-check below plants each form.
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

/** Where a value (the token, or a name holding it) is used, following what passes it on unchanged as React
    renders it: parentheses, a type assertion, a conditional's branch, either side of `??` or `||` and the right
    of `&&`. */
function usageOf(token: ts.Node): { value: ts.Node; use: ts.Node } {
  let value: ts.Node = token
  for (;;) {
    const up: ts.Node = value.parent
    const op = ts.isBinaryExpression(up) ? up.operatorToken.kind : undefined
    if (ts.isParenthesizedExpression(up) || ts.isAsExpression(up) || ts.isSatisfiesExpression(up) || ts.isNonNullExpression(up)) value = up
    else if (ts.isConditionalExpression(up) && up.condition !== value) value = up
    else if (op === ts.SyntaxKind.QuestionQuestionToken || op === ts.SyntaxKind.BarBarToken) value = up
    else if (op === ts.SyntaxKind.AmpersandAmpersandToken && (up as ts.BinaryExpression).right === value) value = up
    else break
  }
  return { value, use: value.parent }
}

type Declared = ts.VariableDeclaration & { name: ts.Identifier }
type Resolve = (id: ts.Identifier) => ts.Node | undefined

/** Every reference in the file that reads a declaration's value: an identifier that scope resolves to it (so a
    same-named binding in a nested scope, or a parameter of that name, is its own) and that is not the `name` of its
    parent (the declaration itself, a property or attribute of that name, another binding of it, an export of it,
    which another file reads), except a shorthand property's (`{ DASH }`), which is both the key and a read of the
    name. */
function referencesTo(declared: Declared, source: ts.SourceFile, resolve: Resolve): ts.Identifier[] {
  const refs: ts.Identifier[] = []
  const visit = (node: ts.Node) => {
    const parent = node.parent as ts.Node & { name?: ts.Node }
    if (
      ts.isIdentifier(node) &&
      node.text === declared.name.text &&
      (parent.name !== node || ts.isShorthandPropertyAssignment(parent)) &&
      resolve(node) === declared
    ) {
      refs.push(node)
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return refs
}

/** The `const` or `let` an object literal initializes, through parentheses or `as const`, else null. */
function holderOf(node: ts.Node): Declared | null {
  let value: ts.Node = node
  while (ts.isParenthesizedExpression(value.parent) || ts.isAsExpression(value.parent) || ts.isSatisfiesExpression(value.parent)) value = value.parent
  const decl = value.parent
  return ts.isVariableDeclaration(decl) && decl.initializer === value && ts.isIdentifier(decl.name) ? (decl as Declared) : null
}

/** The nodes where a bare token, or a name holding one, is joined into copy: none when every use stands alone
    (see the header). A `const` or `let` holding the token is followed to each reference that scope resolves to it,
    one declaration at a time, and a property of an object such a declaration holds (`const BOX = { token: '—' }`)
    to each `BOX.token` read of that declaration. */
function joinedUses(token: ts.Node, source: ts.SourceFile, resolve: Resolve, seen = new Set<ts.Node | string>()): ts.Node[] {
  const { value, use } = usageOf(token)
  // Joined into copy: an operand of `+`, the right of `+=`, a template's substitution.
  if (ts.isBinaryExpression(use)) {
    const op = use.operatorToken.kind
    if (op === ts.SyntaxKind.PlusToken || (op === ts.SyntaxKind.PlusEqualsToken && use.right === value)) return [token]
  }
  if (ts.isTemplateSpan(use)) return [token]
  // A JSX child: the token only as its element's sole meaningful child, as JSX text is (an attribute's value stands alone).
  if (ts.isJsxExpression(use) && !ts.isJsxAttribute(use.parent)) return soleChild(use) ? [] : [token]
  // Held in a name: each reference of the name is held to the same test.
  if (ts.isVariableDeclaration(use) && use.initializer === value && ts.isIdentifier(use.name) && !seen.has(use)) {
    seen.add(use)
    return referencesTo(use as Declared, source, resolve).flatMap((ref) => joinedUses(ref, source, resolve, seen))
  }
  // Held in an object's property under a name, written out or as the shorthand of a name holding it (`{ DASH }`):
  // each `NAME.prop` read in the file is held to the same test. A destructured read, an element of an array and an
  // object passed on whole stay review-checked (the header).
  const property = ts.isPropertyAssignment(use) && use.initializer === value ? use : ts.isShorthandPropertyAssignment(use) && use.name === value ? use : null
  if (property && ts.isObjectLiteralExpression(property.parent)) {
    const holder = holderOf(property.parent)
    const prop = ts.isIdentifier(property.name) || ts.isStringLiteral(property.name) ? property.name.text : null
    const key = holder && prop !== null ? `${holder.getStart(source)}.${prop}` : null
    if (holder && key !== null && !seen.has(key)) {
      seen.add(key)
      return referencesTo(holder, source, resolve)
        .map((ref) => ref.parent)
        .filter((read): read is ts.PropertyAccessExpression => ts.isPropertyAccessExpression(read) && read.name.text === prop)
        .flatMap((read) => joinedUses(read, source, resolve, seen))
    }
  }
  return []
}

/** The bare missing-value token is the one sanctioned em-dash: a JSX text node trimming to '—' that is the
    only child of its element, or a string or no-substitution template literal that is exactly '—' where the
    value it gives stands alone (see the header). Returns the nodes where the literal is copy instead: the
    literal itself, or each reference of a name holding the token that is joined into copy. */
function tokenViolations(node: ts.Node, literalText: string, source: ts.SourceFile, resolve: Resolve): ts.Node[] {
  if (ts.isJsxText(node)) return literalText.trim() === EM_DASH && soleChild(node) ? [] : [node]
  // A template's head, middle or tail is joined to what its substitutions render: never the whole value.
  if (!ts.isStringLiteral(node) && !ts.isNoSubstitutionTemplateLiteral(node)) return [node]
  if (literalText !== EM_DASH) return [node]
  return joinedUses(node, source, resolve)
}

/** Every em-dash in `text` outside the sanctioned token, as `file:line text`. */
function violationsIn(text: string, file: string): string[] {
  if (!text.includes(EM_DASH)) return []
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const resolve = scopeResolver(source)
  const violations: string[] = []

  const record = (node: ts.Node, literalText: string) => {
    if (!literalText.includes(EM_DASH)) return
    for (const at of tokenViolations(node, literalText, source, resolve)) {
      const { line } = source.getLineAndCharacterOfPosition(at.getStart())
      violations.push(`${path.relative(FRONTEND_ROOT, file)}:${line + 1} ${literalText.trim().slice(0, 80)}`)
    }
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
      "const DASH = '—'",
      'export const G = ({ speaker }: { speaker: string }) => <cite>{DASH} {speaker}</cite>',
      "export const H = (speaker: string) => DASH + ' ' + speaker",
      "const NONE = '—'",
      'export const I = ({ v }: { v?: string }) => <td>{v ?? NONE}</td>',
      'const HELD = NONE',
      'export const J = (x: string) => `${HELD}${x}`',
      "const BOX = { token: '—' } as const",
      'export const K = ({ speaker }: { speaker: string }) => <cite>{BOX.token} {speaker}</cite>',
      'export const L = ({ v }: { v?: string }) => <td>{v ?? BOX.token}</td>',
      'const SHORT = { DASH } as const',
      'export const M = ({ speaker }: { speaker: string }) => <cite>{SHORT.DASH} {speaker}</cite>',
      'export const N = ({ v }: { v?: string }) => <td>{v ?? SHORT.DASH}</td>',
      "const TOKEN = '—'",
      "export function O({ speaker }: { speaker: string }) { const TOKEN = 'none'; return <cite>{TOKEN} {speaker}</cite> }",
      "export const P = (TOKEN: string) => TOKEN + ' ' + TOKEN",
      "const CELL = { token: '—' } as const",
      "export function Q({ speaker }: { speaker: string }) { const CELL = { token: 'none' }; return <cite>{CELL.token} {speaker}</cite> }",
      "const MARK = 'x'",
      "export function R({ speaker }: { speaker: string }) { const MARK = '—'; return <cite>{MARK} {speaker}</cite> }",
      'export const S = ({ speaker }: { speaker: string }) => <cite>{MARK} {speaker}</cite>',
      "const ROOT = '—'",
      'export function T({ speaker }: { speaker: string }) { const ALIAS = ROOT; return <cite>{ALIAS} {speaker}</cite> }',
      'export function U({ speaker }: { speaker: string }) { const ALIAS = ROOT; return <cite>{ALIAS} {speaker}</cite> }',
    ].join('\n')
    // Lines 3 to 7 stand alone (the text, the literal, a fallback, a template beside an empty expression, an
    // attribute's value) and 18 to 19 are read where they are written (a name no line reads, a comparison, a
    // fallback returned). Lines 8 to 11 sit beside sibling children (as text, a literal, a conditional's branch,
    // the right of `||` in parentheses), 14 is a `+` operand, 15 a template's substitution, 16 a template's head
    // and 17 the right of `+=`. A name holding the token is followed to its references: DASH (20) is rendered
    // beside a sibling at 21 and is a `+` operand at 22; NONE (23) stands alone as a fallback at 24, and HELD
    // (25), which holds NONE, is a template's substitution at 26. BOX (27) holds the token in a property: its
    // `BOX.token` read sits beside a sibling at 28 and stands alone as a fallback at 29. SHORT (30) holds DASH by its
    // shorthand: its `SHORT.DASH` read sits beside a sibling at 31 (found while DASH's references are followed, so it
    // comes after 22) and stands alone as a fallback at 32. A reference is the name's by scope (the review's case):
    // TOKEN (33) is read by no line, since O's TOKEN (34) and P's parameter (35) are their own values; CELL (36) is read
    // by no line, since Q declares its own CELL (37); and R's MARK (39), a token a nested scope declares, is followed to
    // its own read beside a sibling at 39, not to S's read of the outer MARK (40). Each declaration is followed once, so
    // T's and U's ALIAS, two declarations of one name that both hold ROOT (41), are each followed to their own read
    // beside a sibling (42, 43).
    expect(violationsIn(src, file)).toEqual([8, 9, 10, 11, 14, 15, 16, 17, 21, 22, 31, 26, 28, 39, 42, 43].map((line) => `features/zzprobe/Probe.tsx:${line} —`))
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
