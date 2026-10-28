/* =============================================================================
   pulsingMarkAllowlist.spec.ts — a run in progress has one shape
   -----------------------------------------------------------------------------
   A pulsing round mark is the activity line's dot: the Copilot's "Reading the
   filing…" and the analysis page's history fetch show their words beside it
   (DESIGN_SYSTEM.md §4 › Activity line); a run that reports how far it has got
   shows a bar instead, as the summary's generating card does. The dot ships
   only through ui/ActivityLine, plus Badge's live dot on the `new` chip. The
   analysis page and the Copilot wrote the line by hand, and one drifted from
   the other (#1755, #1756), so a hand-rolled copy fails here.

   The scan reads each file's TypeScript AST (comments never count). A mark is
   a pulse (`animate-pulse` or `animate-ping`, Tailwind's two pulsing
   animations) and a full round (`rounded-full`) in one class list, behind any
   variant prefix (motion-safe:, dark:, group-hover:) and with Tailwind's `!`
   before or after. A site is the innermost list that holds both, counted once
   (a list, not an element: an element whose ternary picks between two such
   lists counts two):
     string — any string literal or template chunk that holds both tokens,
              wherever it sits (the scan cannot tell a class string from any
              other, so a title naming both counts too);
     class  — a list whose parts together hold both: a cx() or clsx() call, a
              template, an array literal joined into one string (through any
              filter or map, cast or parenthesis on the way), or a class
              attribute (className, iconClassName and the like) whatever builds
              it. A list bound to a const counts where it is written. A
              ternary's arms count together, so a mark that pulses in one state
              and is round in the other fails too.
   Out of reach, stated and planted as gaps: a token held in a binding (a
   const, an import, a parameter) and split from the other; a helper other than
   cx() or clsx() outside any class list, and a `+` concatenation; a pulse on an
   element whose round mark is a child; a round by another name (an arbitrary
   rounded-[…] value, which the design lint refuses as an off-scale radius); a
   pulse by another name (an arbitrary animate-[…] value, a keyframe of the
   app's own); an animation in a stylesheet or an inline style.
   Each allowlisted file is pinned, with its reason, to its number of sites: a
   new hand-rolled mark, an extra one in a sanctioned file and a stale entry all
   fail.
============================================================================= */

import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

const ROOT = path.join(__dirname, '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
// Equal to the list (lessons/test-allowlist-caps-are-equalities.md): lower it when an entry goes; never raise it to
// fit a new hand-rolled mark.
const MAX_ALLOWLIST_SIZE = 2
const ALLOW: Record<string, { sites: number; reason: string }> = {
  'components/ui/ActivityLine.tsx': { sites: 1, reason: 'the activity line: one pulse dot beside the words of a run in progress' },
  'components/ui/Badge.tsx': { sites: 1, reason: "the `new` chip's live dot, in the chip's own sage ink (Solid chip, Status chip)" },
}

const PULSE = /(?:^|:)!?animate-(?:pulse|ping)!?$/
const ROUND = /(?:^|:)!?rounded-full!?$/
const CLASS_ATTRIBUTE = /^\w*[cC]lassName$/
// The app's two class joiners: components/ui/cx and the clsx package.
const CLASS_JOINERS = new Set(['cx', 'clsx'])
const tokensOf = (text: string) => text.split(/\s+/).filter(Boolean)
const holds = (tokens: string[], token: RegExp) => tokens.some((t) => token.test(t))
const holdsBoth = (tokens: string[]) => holds(tokens, PULSE) && holds(tokens, ROUND)

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
function literalTexts(node: ts.Node): string[] {
  const out: string[] = []
  const visit = (n: ts.Node): void => {
    if (isLiteralChunk(n)) out.push(n.text)
    ts.forEachChild(n, visit)
  }
  visit(node)
  return out
}

function pulsingMarkSites(source: string, fileName: string): number {
  const sourceFile = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    fileName.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  )
  // A class list beyond one string: a class attribute (whatever builds it), a joiner's call, a template, or an array
  // literal joined into one string.
  const isClassList = (node: ts.Node) =>
    (ts.isJsxAttribute(node) && !!node.initializer && CLASS_ATTRIBUTE.test(node.name.getText(sourceFile))) ||
    (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && CLASS_JOINERS.has(node.expression.text)) ||
    ts.isTemplateExpression(node) ||
    joinedArray(node)
  let sites = 0
  // Whether a mark was counted at or under `node`: a class list counts only when nothing inside it did.
  const visit = (node: ts.Node): boolean => {
    if (isLiteralChunk(node)) {
      if (!holdsBoth(tokensOf(node.text))) return false
      sites++
      return true
    }
    let inner = false
    ts.forEachChild(node, (child) => {
      if (visit(child)) inner = true
    })
    if (inner || !isClassList(node) || !holdsBoth(literalTexts(node).flatMap(tokensOf))) return inner
    sites++
    return true
  }
  visit(sourceFile)
  return sites
}

function walk(dir: string, out: string[] = []): string[] {
  if (!fs.existsSync(dir)) return out
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name)) out.push(p)
  }
  return out
}

function scan(): Map<string, number> {
  const found = new Map<string, number>()
  for (const dir of SCAN_DIRS) {
    for (const file of walk(path.join(ROOT, dir))) {
      const sites = pulsingMarkSites(fs.readFileSync(file, 'utf8'), file)
      if (sites > 0) found.set(path.relative(ROOT, file).split(path.sep).join('/'), sites)
    }
  }
  return found
}

describe('a pulsing round mark ships only through ActivityLine and Badge’s live dot', () => {
  it('reads the planted forms: the marks it must find, the lines it must pass, and its stated gaps', () => {
    const planted: [string, number][] = [
      // Found: a string site.
      ['export const A = () => <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-strong" />', 1],
      ['export const B = () => <span className="dark:!animate-pulse rounded-full" />', 1],
      ['export const C = () => <span className="group-hover:animate-pulse rounded-full!" />', 1],
      ['export const D = (busy: boolean) => <span className={busy ? "rounded-full motion-safe:animate-pulse" : "rounded-full"} />', 1],
      ["export const DOT = 'animate-pulse rounded-full bg-current'", 1],
      ['export const E = () => <span className="h-2 w-2 animate-ping rounded-full bg-brand-strong" />', 1],
      // Found, as stated: any string counts, not only a class list.
      ['export const F = () => <abbr title="animate-pulse rounded-full" />', 1],
      // Found: a class site, the two tokens split across one list's parts, wherever the list sits.
      ["export const G = (busy: boolean) => <span className={cx('h-1.5 w-1.5 rounded-full', busy && 'animate-pulse')} />", 1],
      ['export const H = (tone: string) => <i className={`rounded-full ${tone} animate-pulse`} />', 1],
      ["const MARK = cx('h-1.5 w-1.5 rounded-full', 'animate-pulse')\nexport const I = () => <span className={MARK} />", 1],
      ["export const dotClass = (on: boolean) => clsx('h-1.5 w-1.5 rounded-full', on && 'animate-pulse')", 1],
      ["export const dotTemplate = (on: boolean) => `h-1.5 w-1.5 rounded-full ${on ? 'animate-pulse' : ''}`", 1],
      ["export const dotJoined = (on: boolean) => ['h-1.5 w-1.5 rounded-full', on && 'animate-pulse'].join(' ')", 1],
      ["export const dotFiltered = (on: boolean) => ['h-1.5 w-1.5 rounded-full', on && 'animate-pulse'].filter(Boolean).join(' ')", 1],
      ["export const dotCast = (on: boolean) => (['rounded-full', on && 'animate-pulse'] as string[]).filter(Boolean)!.join(' ')", 1],
      ["export const K = (on: boolean) => <Dot iconClassName={merge('rounded-full', on && 'animate-pulse')} />", 1],
      // Found, as stated: a ternary's arms count together.
      ["export const L = (busy: boolean) => <span className={busy ? 'animate-pulse h-2' : 'rounded-full'} />", 1],
      // Counted per list: nested lists count once; two marks, or an element picking between two lists, count two.
      ["export const M = (on: boolean) => <span className={cx('h-2', cx('rounded-full', on && 'animate-pulse'))} />", 1],
      ['export const W = () => <><span className="animate-pulse rounded-full" /><span className="animate-pulse rounded-full" /></>', 2],
      ["export const X = (on: boolean) => <span className={on ? cx('rounded-full', 'animate-pulse') : cx('rounded-full', 'animate-ping')} />", 2],
      // Passed: the summary stream's caret is a pulsing bar; a still dot; a spinner; a comment; another animation's name.
      ['export const N = () => <span className="ml-1 inline-block h-5 w-0.5 bg-brand-strong animate-pulse motion-reduce:animate-none" />', 0],
      ['export const O = () => <span className="h-1.5 w-1.5 rounded-full bg-brand-strong" />', 0],
      ['export const P = () => <span className="h-4 w-4 animate-spin rounded-full border-2 border-current" />', 0],
      ['// h-1.5 w-1.5 animate-pulse rounded-full, in a comment\nexport const Q = 1', 0],
      ['export const R = () => <span className="animate-pulse-slow rounded-full" />', 0],
      // Gaps, as stated: a token held in a binding and split from the other; a helper outside any class list; a
      // concatenation; a pulse whose round mark is a child; a round by another name; a pulse by another name.
      ["const ROUND = 'rounded-full'\nexport const S = () => <i className={cx(ROUND, 'animate-pulse')} />", 0],
      ["export const Y = merge('rounded-full', 'animate-pulse')", 0],
      ["export const Z = (on: boolean) => 'rounded-full ' + (on ? 'animate-pulse' : '')", 0],
      ['export const T = () => <span className="animate-pulse"><span className="h-1.5 w-1.5 rounded-full" /></span>', 0],
      ['export const U = () => <span className="animate-pulse rounded-[50%]" />', 0],
      ['export const V = () => <span className="animate-[pulse_2s_infinite] rounded-full" />', 0],
    ]
    expect(planted.map(([source]) => pulsingMarkSites(source, 'planted.tsx'))).toEqual(planted.map(([, sites]) => sites))
  })

  it('every pulsing round mark is allowlisted, at its count', () => {
    const found = scan()
    const problems: string[] = []
    for (const file of [...new Set([...found.keys(), ...Object.keys(ALLOW)])].sort()) {
      const actual = found.get(file) ?? 0
      const allowed = ALLOW[file]?.sites ?? 0
      if (actual > allowed) problems.push(`${file}: ${actual} pulsing round marks, ${allowed} allowed`)
      else if (actual < allowed) problems.push(`${file}: ${actual} pulsing round marks, ${allowed} allowed: lower its count or delete its entry (stale)`)
    }
    expect(
      problems,
      'A run in progress shown in words beside a pulse dot is <ActivityLine> (components/ui), the one dot ' +
        '(DESIGN_SYSTEM.md §4 › Activity line); a loading bone is <Skeleton>. Never hand-roll the dot.',
    ).toEqual([])
  })

  it('the allowlist is shrink-only and gives each entry its reason', () => {
    expect(Object.keys(ALLOW).length, 'compose <ActivityLine> instead of adding an entry').toBe(MAX_ALLOWLIST_SIZE)
    for (const [file, entry] of Object.entries(ALLOW)) {
      expect(file.startsWith('components/ui/'), `${file}: a pulsing round mark belongs to a primitive`).toBe(true)
      expect(entry.reason.length).toBeGreaterThan(20)
    }
  })
})
