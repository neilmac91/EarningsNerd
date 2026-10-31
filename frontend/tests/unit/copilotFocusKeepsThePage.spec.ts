/* =============================================================================
   copilotFocusKeepsThePage.spec.ts — a focus the pane's code moves keeps the page
   -----------------------------------------------------------------------------
   The filing page's pane (features/filings/components/copilot/) can run below
   the fold: the desktop pane's height follows its top a frame late. A focus's
   own scroll moves every scrolling ancestor, the page included, so the press on
   Source that focused the composer moved the page under the reader (E248; chief
   design on #1813: "A press on Source should never move the page under the
   reader"). A focus the pane's code moves passes `{ preventScroll: true }`;
   the composer then brings its shell into view inside its column, never the
   page (CopilotComposer's revealInScrollBox;
   lessons/frontend-programmatic-focus-never-moves-the-page.md). This gate reads
   the preventScroll half.

   Sites: every call of a member named `focus` in the folder and in the pane's
   launcher hand-off (hooks/useFocusHandoff.ts), `?.` included, and every
   `autoFocus` attribute, which React focuses with the browser's own scroll. A
   call passes when its first argument is an object literal holding
   `preventScroll: true` and no spread. The rail's calls on `composerRef.current` are the
   composer's handle, whose field takes focus that way; each file that calls it
   holds composerRef as a `useRef<CopilotComposerHandle>`. Any other site is
   pinned here by file, with why its focus keeps the browser's scroll: a focus
   the user moves (Tab, Shift+Tab, the arrow keys, Escape's return), which the
   browser brings into view as a native Tab would, or the phone's sheet, a
   modal, whose focus stays inside it (fixed, so no page scroll moves it) until
   its close returns focus to the control that opened it.
   And no code in the folder names scrollIntoView or scrollIntoViewIfNeeded,
   which scroll every ancestor; a comment may. The page moves from one site:
   CopilotComposer's revealOnPage, the move a press makes once its pane has
   settled and the composer is still out of view (E252; chief design on #1845:
   "Move it once per press or ⌘K. Never move it from a resize or the follow").
   A page move is a call of scroll, scrollTo or scrollBy on the window
   (`window`, `globalThis`, `self`, or bare) or on the document's scrolling
   element (`document.documentElement`, `document.scrollingElement`,
   `document.body`), or a write to that element's scrollTop or scrollLeft; a
   box's own scroll (highlightInDom's reader) is not one.
   Read strictly, and planted: options held in a variable or spread in (a spread
   after `preventScroll: true` can undo it), a shorthand `preventScroll`, and
   `preventScroll: false` do not count as passing.
   Missed, stated: a focus passed as a value (`requestAnimationFrame(el.focus)`),
   a focus moved from outside the folder (ui/Modal's, the reader's), and a page
   move through an alias (`const page = document.scrollingElement`).
============================================================================= */

import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { parse, sourceFiles } from './classListScan'

const ROOT = path.join(__dirname, '../..')
const PANE = 'features/filings/components/copilot'
const HANDOFF = 'hooks/useFocusHandoff.ts'
const HANDLE = 'composerRef.current'
const ANCESTOR_SCROLLS = new Set(['scrollIntoView', 'scrollIntoViewIfNeeded'])
const PAGE_SCROLLS = new Set(['scroll', 'scrollTo', 'scrollBy'])
const PAGE_OFFSETS = new Set(['scrollTop', 'scrollLeft'])
const WINDOW = new Set(['window', 'globalThis', 'self'])
const PAGE_ELEMENT = new Set(['document.documentElement', 'document.scrollingElement', 'document.body'])
/** The one page move, the composer's reveal after a press (E252). */
const PAGE_MOVES = { [`${PANE}/CopilotComposer.tsx`]: ['window.scrollBy'] }
const USER = 'a focus the user moves, which the browser brings into view as a native Tab would:'
// Equal to the sites found (lessons/test-allowlist-caps-are-equalities.md): a new site raises its count in the same
// change, its reason naming why that focus keeps the browser's scroll.
const ALLOW: Record<string, { sites: number; reason: string }> = {
  [`${PANE}/useEvidencePopoverKeys.ts`]: {
    sites: 4,
    reason: `${USER} Tab from a citation's chip into its popover, Shift+Tab back, Tab past it, and Escape's return to the chip`,
  },
  [`${PANE}/SecondaryPaneTabs.tsx`]: { sites: 1, reason: `${USER} the arrow keys, Home and End between the pane's tabs` },
  [`${PANE}/useSheetFocusTrap.ts`]: {
    sites: 6,
    reason:
      "the phone's sheet, a modal: its open focus and Tab's wrap stay inside it, fixed, so no page scroll moves them, " +
      'and its close returns focus to the control that opened it, as a dialog does',
  },
}

interface Sites {
  /** Focus calls with `{ preventScroll: true }`. */
  prevented: number
  /** Focus calls without it, the handle's aside. */
  unprevented: number
  /** Calls of the composer's handle (`composerRef.current?.focus()`). */
  handle: number
  /** Each name in the code that scrolls every ancestor. */
  ancestorScrolls: string[]
  /** Each call or write that moves the page, as `receiver.member`. */
  pageMoves: string[]
}

const propertyName = (name: ts.PropertyName) =>
  ts.isIdentifier(name) || ts.isStringLiteralLike(name) || ts.isNumericLiteral(name) ? name.text : null

function sitesIn(source: string, fileName: string): Sites {
  const sourceFile = parse(source, fileName)
  const sites: Sites = { prevented: 0, unprevented: 0, handle: 0, ancestorScrolls: [], pageMoves: [] }
  const member = (callee: ts.Expression): { name: string; receiver: ts.Expression } | null => {
    if (ts.isPropertyAccessExpression(callee)) return { name: callee.name.text, receiver: callee.expression }
    if (ts.isElementAccessExpression(callee) && ts.isStringLiteralLike(callee.argumentExpression)) {
      return { name: callee.argumentExpression.text, receiver: callee.expression }
    }
    return null
  }
  // The receiver as written, past parentheses, `as`, `satisfies` and `!`, and with `?.` read as `.`.
  const receiverText = (receiver: ts.Expression): string =>
    ts.isParenthesizedExpression(receiver) ||
    ts.isAsExpression(receiver) ||
    ts.isSatisfiesExpression(receiver) ||
    ts.isNonNullExpression(receiver) ||
    ts.isTypeAssertionExpression(receiver)
      ? receiverText(receiver.expression)
      : receiver.getText(sourceFile).replace(/\?\./g, '.')
  const pageOffset = (target: ts.Expression) => {
    const access = member(target)
    return access && PAGE_OFFSETS.has(access.name) && PAGE_ELEMENT.has(receiverText(access.receiver))
      ? `${receiverText(access.receiver)}.${access.name}`
      : null
  }
  const preventsScroll = (call: ts.CallExpression) => {
    const [options] = call.arguments
    return (
      !!options &&
      ts.isObjectLiteralExpression(options) &&
      !options.properties.some(ts.isSpreadAssignment) &&
      options.properties.some(
        (p) =>
          ts.isPropertyAssignment(p) &&
          propertyName(p.name) === 'preventScroll' &&
          p.initializer.kind === ts.SyntaxKind.TrueKeyword,
      )
    )
  }
  const visit = (node: ts.Node): void => {
    if (ts.isCallExpression(node)) {
      const callee = member(node.expression)
      if (callee?.name === 'focus') {
        if (callee.receiver.getText(sourceFile) === HANDLE) sites.handle += 1
        else if (preventsScroll(node)) sites.prevented += 1
        else sites.unprevented += 1
      }
      if (callee && PAGE_SCROLLS.has(callee.name)) {
        const receiver = receiverText(callee.receiver)
        if (WINDOW.has(receiver) || PAGE_ELEMENT.has(receiver)) sites.pageMoves.push(`${receiver}.${callee.name}`)
      }
      if (ts.isIdentifier(node.expression) && PAGE_SCROLLS.has(node.expression.text)) {
        sites.pageMoves.push(node.expression.text)
      }
    }
    if (ts.isBinaryExpression(node) && node.operatorToken.kind >= ts.SyntaxKind.FirstAssignment && node.operatorToken.kind <= ts.SyntaxKind.LastAssignment) {
      const offset = pageOffset(node.left)
      if (offset) sites.pageMoves.push(offset)
    }
    if (
      (ts.isPrefixUnaryExpression(node) || ts.isPostfixUnaryExpression(node)) &&
      (node.operator === ts.SyntaxKind.PlusPlusToken || node.operator === ts.SyntaxKind.MinusMinusToken)
    ) {
      const offset = pageOffset(node.operand)
      if (offset) sites.pageMoves.push(offset)
    }
    if (ts.isJsxAttribute(node) && node.name.getText(sourceFile) === 'autoFocus') sites.unprevented += 1
    if ((ts.isIdentifier(node) || ts.isStringLiteralLike(node)) && ANCESTOR_SCROLLS.has(node.text)) {
      sites.ancestorScrolls.push(node.text)
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return sites
}

const files = [...sourceFiles(ROOT, [PANE]), HANDOFF]
const scanned = Object.fromEntries(
  files.map((file) => [file, { source: fs.readFileSync(path.join(ROOT, file), 'utf8'), sites: sitesIn(fs.readFileSync(path.join(ROOT, file), 'utf8'), file) }]),
)

describe('a focus the pane moves keeps the page (E248)', () => {
  it('reads the pane', () => {
    expect(files.length).toBeGreaterThan(10)
    expect(files).toContain(`${PANE}/CopilotComposer.tsx`)
    expect(files).toContain(`${PANE}/AskCopilotRail.tsx`)
    expect(scanned[HANDOFF].sites).toMatchObject({ unprevented: 0, prevented: 2 })
  })

  it("every focus the pane's code moves passes preventScroll, or is pinned with why it keeps the browser's scroll", () => {
    const unprevented = Object.fromEntries(
      Object.entries(scanned).flatMap(([file, { sites }]) => (sites.unprevented ? [[file, sites.unprevented]] : [])),
    )
    expect(unprevented).toEqual(Object.fromEntries(Object.entries(ALLOW).map(([file, { sites }]) => [file, sites])))
    // Each reason names its own focus beyond the shared opening.
    for (const { reason } of Object.values(ALLOW)) expect(reason.replace(USER, '').trim().length).toBeGreaterThan(40)
  })

  it("the rail's focus goes through the composer's handle, whose field takes focus with preventScroll", () => {
    const composer = scanned[`${PANE}/CopilotComposer.tsx`].sites
    expect(composer).toMatchObject({ unprevented: 0, handle: 0 })
    expect(composer.prevented).toBeGreaterThan(0)
    const callers = Object.entries(scanned).filter(([, { sites }]) => sites.handle > 0)
    expect(callers.map(([file]) => file)).toEqual([`${PANE}/AskCopilotRail.tsx`])
    for (const [, { source }] of callers) expect(source).toMatch(/\bcomposerRef = useRef<CopilotComposerHandle>\(null\)/)
  })

  it('no code in the pane scrolls every ancestor', () => {
    const found = Object.entries(scanned).flatMap(([file, { sites }]) => sites.ancestorScrolls.map((name) => `${file}: ${name}`))
    expect(found).toEqual([])
  })

  it("the page moves from one site: the composer's reveal a press makes once its pane settles (E252)", () => {
    const found = Object.fromEntries(
      Object.entries(scanned).flatMap(([file, { sites }]) => (sites.pageMoves.length ? [[file, sites.pageMoves]] : [])),
    )
    expect(found).toEqual(PAGE_MOVES)
  })

  it('reads what it states, planted', () => {
    const planted = (code: string) => sitesIn(code, 'planted.tsx')
    expect(planted('el.focus({ preventScroll: true })')).toMatchObject({ prevented: 1, unprevented: 0 })
    expect(planted("el?.focus({ focusVisible: true, 'preventScroll': true })")).toMatchObject({ prevented: 1, unprevented: 0 })
    for (const strict of [
      'el.focus()',
      'el?.focus()',
      'el.focus?.()',
      "el['focus']()",
      'el.focus({ preventScroll: false })',
      'el.focus(options)',
      'el.focus({ ...options })',
      'el.focus({ preventScroll: true, ...options })',
      'el.focus({ preventScroll })',
      'other.current?.focus()',
      'const field = <textarea autoFocus />',
      'const field = <input autoFocus={open} />',
    ]) {
      expect(planted(strict), strict).toMatchObject({ prevented: 0, unprevented: 1 })
    }
    expect(planted('composerRef.current?.focus()')).toMatchObject({ handle: 1, unprevented: 0 })
    for (const scroll of ['el.scrollIntoView()', "el.scrollIntoViewIfNeeded?.()", "el['scrollIntoView']({ block: 'nearest' })"]) {
      expect(planted(scroll).ancestorScrolls, scroll).toHaveLength(1)
    }
    for (const move of [
      'window.scrollBy({ top: 1 })',
      'window.scrollTo(0, 0)',
      'window.scroll(0, 0)',
      'scrollBy(0, 1)',
      'globalThis.scrollTo({ top: 0 })',
      'self.scrollBy(0, 1)',
      "window['scrollBy'](0, 1)",
      'window.scrollBy?.(0, 1)',
      'document.scrollingElement?.scrollTo(0, 0)',
      'document.documentElement.scrollTop = 0',
      'document.scrollingElement!.scrollTop += 10',
      '(document.scrollingElement as HTMLElement).scrollTop = 0',
      'document.body.scrollTop -= 1',
      'document.documentElement.scrollLeft = 0',
      'document.documentElement.scrollTop++',
    ]) {
      expect(planted(move).pageMoves, move).toHaveLength(1)
    }
    for (const box of [
      'box.scrollTo({ top: 0 })',
      'box.scrollBy(0, 1)',
      'box.scrollTop = 0',
      'el.scrollTop += by',
      'const y = window.scrollY',
      'const t = document.documentElement.scrollTop',
    ]) {
      expect(planted(box).pageMoves, box).toEqual([])
    }
    expect(planted('// el.scrollIntoView() moved the page\n/* el.focus() */ const a = 1')).toEqual({
      prevented: 0,
      unprevented: 0,
      handle: 0,
      ancestorScrolls: [],
      pageMoves: [],
    })
  })
})
