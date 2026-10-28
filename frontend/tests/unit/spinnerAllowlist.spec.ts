/* =============================================================================
   spinnerAllowlist.spec.ts — a turning glyph marks two waits
   -----------------------------------------------------------------------------
   Outside Button (<Button loading>, Steady loading) and Input (FieldSpinner,
   Search field), a spinner marks one of two waits (DESIGN_SYSTEM.md §4 ›
   Spinner): a control's own request, where the glyph takes the place of the
   control's icon, sits before its label or in a select's trailing inset, and
   the control carries aria-busy; or a page's one read, in a region that names
   the wait. A run in progress shown in words is the Activity line, a loading
   layout is Skeleton bones. Each site is pinned here, by file, with the wait
   it marks, so a new spinner fails until its author names which of the two it
   is; the two lines that still pair their words with a spinner are pinned as
   they stand.

   Sites: the scan reads class lists as tests/unit/classListScan.ts states,
   and a site is the innermost list holding `animate-spin`, behind any variant
   prefix and with Tailwind's `!` before or after, counted once.
   Hidden: every spinner the scan finds in a JSX element's class attribute is
   aria-hidden (bare, "true", {true} or {'true'}), on the element itself (an
   icon passes it to its svg) or on an HTML element enclosing it, as Button's
   and Input's spinners are. The control's aria-busy, the region's name or the
   words beside it say what waits; the glyph says nothing.
   One token is enough here, so a token held in a const, passed to another
   helper or concatenated counts where its string is written. Missed, stated
   as gaps and planted where a source can hold them (a stylesheet cannot): a
   spin by another name (an arbitrary animate-[…] value, a keyframe of the
   app's own) and an animation in a stylesheet or an inline style; and, for
   the hidden rule, a spinner whose class list is built outside the element (a
   const, a helper's return). Read strictly, and planted: aria-hidden set by
   any other expression ({quiet}) or by a spread, or on a component enclosing
   the glyph, which may not pass it to the DOM, does not count.
============================================================================= */

import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'
import { CLASS_ATTRIBUTE, classListSites, literalTexts, parse, sourceFiles, tokensOf } from './classListScan'

const ROOT = path.join(__dirname, '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
// Equal to the list (lessons/test-allowlist-caps-are-equalities.md): lower it when an entry goes; a new entry raises
// it in the same change, its reason naming the wait it marks.
const MAX_ALLOWLIST_SIZE = 14
const CONTROL = "a control's own request:"
const PAGE = "a page's one read:"
const WORDS = 'words beside a spinner, waiting on the pass that decides whether such a line takes the Activity line (tasks/todo.md E233):'
const ALLOW: Record<string, { sites: number; reason: string }> = {
  'components/ui/Button.tsx': { sites: 1, reason: "the busy Button's spinner, <Button loading> (Steady loading)" },
  'components/ui/Input.tsx': { sites: 1, reason: "FieldSpinner, a busy field's spinner in its trailing inset (Search field)" },
  'app/check-email/page.tsx': { sites: 1, reason: `${CONTROL} the resend link's glyph before its label, the link aria-busy` },
  'features/auth/components/VerificationBanner.tsx': {
    sites: 1,
    reason: `${CONTROL} the banner's resend link, its glyph before its label, the link aria-busy`,
  },
  'features/admin/components/InviteRow.tsx': { sites: 1, reason: `${CONTROL} the resend's glyph in place of its paper plane, the button aria-busy` },
  'features/admin/components/FeedbackRow.tsx': { sites: 1, reason: `${CONTROL} the status select's glyph in its trailing inset, the select aria-busy` },
  'features/watchlist/components/PopularTickerChips.tsx': { sites: 1, reason: `${CONTROL} an adding chip's glyph in place of its plus, the chip aria-busy` },
  'features/settings/components/NotificationPreferencesForm.tsx': {
    sites: 1,
    reason: `${CONTROL} beside the alerts heading while a switch saves, the switches aria-busy`,
  },
  'app/company/[ticker]/page-client.tsx': {
    sites: 1,
    reason: `${PAGE} the company loader, a status region named for the wait (fullPageSpinnerGate pins it until bones replace it)`,
  },
  'app/filing/[id]/page-client.tsx': {
    sites: 2,
    reason:
      `${PAGE} the filing loader (fullPageSpinnerGate pins it) and the summary's while its generation is decided, ` +
      'each a status region named for the wait',
  },
  'features/filings/components/TickerFilingsView.tsx': {
    sites: 1,
    reason: `${PAGE} the /filing/<TICKER> loader, a status region named for the wait (fullPageSpinnerGate pins it until bones replace it)`,
  },
  'app/verify-email/page.tsx': { sites: 1, reason: `${PAGE} over the heading "Verifying your email…", which names the wait` },
  'features/analysis/components/NarrativePane.tsx': {
    sites: 1,
    reason: `${WORDS} "Assembling the numbers…" and "Writing…" as the trend analysis streams`,
  },
  'app/delete-account/page.tsx': { sites: 1, reason: `${WORDS} "Checking whether you are logged in…"` },
}

const SPIN = /(?:^|:)!?animate-spin!?$/
const spins = (tokens: string[]) => tokens.some((t) => SPIN.test(t))
const spinnerSites = (source: string, fileName: string) => classListSites(source, fileName, spins)

/** Whether `attributes` set aria-hidden to true: bare, "true", {true} or {'true'}. */
function hidden(attributes: ts.JsxAttributes, sourceFile: ts.SourceFile): boolean {
  return attributes.properties.some((a) => {
    if (!ts.isJsxAttribute(a) || a.name.getText(sourceFile) !== 'aria-hidden') return false
    const value = a.initializer
    if (!value) return true
    if (ts.isStringLiteral(value)) return value.text === 'true'
    const expression = ts.isJsxExpression(value) ? value.expression : undefined
    return !!expression && (expression.kind === ts.SyntaxKind.TrueKeyword || (ts.isStringLiteral(expression) && expression.text === 'true'))
  })
}

/** Whether a JSX tag is an HTML element (a lowercase name), which hands its aria-hidden to the DOM; a component may not. */
const intrinsic = (tag: ts.JsxTagNameExpression) => ts.isIdentifier(tag) && /^[a-z]/.test(tag.text)

/** The lines of each element whose class attribute spins while neither it nor an HTML element around it is aria-hidden. */
function unhiddenSpinners(source: string, fileName: string): number[] {
  const sourceFile = parse(source, fileName)
  const lines: number[] = []
  const visit = (node: ts.Node): void => {
    if (ts.isJsxSelfClosingElement(node) || ts.isJsxOpeningElement(node)) {
      const spinning = node.attributes.properties.some(
        (a) => ts.isJsxAttribute(a) && !!a.initializer && CLASS_ATTRIBUTE.test(a.name.getText(sourceFile)) && spins(literalTexts(a).flatMap(tokensOf)),
      )
      let covered = hidden(node.attributes, sourceFile)
      for (let up: ts.Node | undefined = node.parent; spinning && !covered && up; up = up.parent) {
        if (ts.isJsxElement(up) && intrinsic(up.openingElement.tagName)) covered = hidden(up.openingElement.attributes, sourceFile)
      }
      if (spinning && !covered) lines.push(sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1)
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return lines
}

describe('a spinner marks a control’s own request or a page’s one read, each site pinned, the glyph hidden', () => {
  it('counts the planted sites: the spinners it must find, the lines it must pass, and its stated gaps', () => {
    const planted: [string, number][] = [
      // Found: a string site, behind a variant, with Tailwind's `!`; a const; any string.
      ['export const A = () => <CircleNotchIcon aria-hidden="true" className="h-4 w-4 animate-spin motion-reduce:animate-none" />', 1],
      ['export const B = () => <svg className="motion-safe:animate-spin" />', 1],
      ['export const C = () => <svg className="!animate-spin" />', 1],
      ["export const SPIN = 'h-3 w-3 animate-spin'", 1],
      // Found: a class site, wherever its list sits; a ternary's arms count together.
      ["export const D = (busy: boolean) => <svg className={cx('h-4 w-4', busy && 'animate-spin')} />", 1],
      ['export const E = (tone: string) => <svg className={`${tone} animate-spin`} />', 1],
      ["export const F = (busy: boolean) => ['h-4 w-4', busy && 'animate-spin'].filter(Boolean).join(' ')", 1],
      ["export const G = (busy: boolean) => <Icon iconClassName={busy ? 'animate-spin' : 'h-4'} />", 1],
      // Counted per list: nested lists count once; two spinners count two.
      ["export const H = (busy: boolean) => <svg className={cx('h-4', cx('w-4', busy && 'animate-spin'))} />", 1],
      ['export const I = () => <><svg className="animate-spin" /><svg className="animate-spin" /></>', 2],
      // Passed: a still glyph; a comment; another animation's name; a pulse.
      ['export const J = () => <CircleNotchIcon className="h-4 w-4" />', 0],
      ['// <svg className="animate-spin" />, in a comment\nexport const K = 1', 0],
      ['export const L = () => <svg className="animate-spin-slow" />', 0],
      ['export const M = () => <span className="animate-pulse" />', 0],
      // Found where its string is written: a token held in a const, passed to another helper or concatenated.
      ["const SPINNING = 'animate-spin'\nexport const N = () => <svg className={cx('h-4', SPINNING)} />", 1],
      ["export const O = (on: boolean) => <svg className={merge('h-4', on ? 'animate-spin' : '')} />", 1],
      ["export const P = (on: boolean) => 'h-4 ' + (on ? 'animate-spin' : '')", 1],
      // Gaps, as stated: a spin by another name, an arbitrary value or a keyframe of the app's own.
      ["export const Q = (on: boolean) => 'h-4 ' + (on ? 'animate-[spin_1s_linear_infinite]' : '')", 0],
      ['export const R = () => <svg className="animate-[spin_1s_linear_infinite]" />', 0],
      ['export const S = () => <svg className="animate-turn" />', 0],
      // Gaps, as stated: an animation in an inline style.
      ["export const T = () => <svg style={{ animation: 'spin 1s linear infinite' }} />", 0],
    ]
    expect(planted.map(([source]) => spinnerSites(source, 'planted.tsx'))).toEqual(planted.map(([, sites]) => sites))
  })

  it('reads the planted glyphs: hidden on the element or around it, or not', () => {
    const planted: [string, number[]][] = [
      ['export const A = () => <CircleNotchIcon className="h-4 w-4 animate-spin" />', [1]],
      ['export const B = () => <CircleNotchIcon aria-hidden="true" className="h-4 w-4 animate-spin" />', []],
      ['export const C = () => <CircleNotchIcon aria-hidden className="animate-spin" />', []],
      ['export const D = () => <svg aria-hidden={true} className="animate-spin" />', []],
      ["export const E = () => <svg aria-hidden={'true'} className=\"animate-spin\" />", []],
      ['export const F = () => <span aria-hidden="true">\n  <CircleNotchIcon className="animate-spin" />\n</span>', []],
      ['export const G = () => <svg aria-hidden="false" className="animate-spin" />', [1]],
      ['export const H = (quiet: boolean) => <svg aria-hidden={quiet} className="animate-spin" />', [1]],
      ["export const I = (busy: boolean) => <svg className={cx('h-4', busy && 'animate-spin')} />", [1]],
      ['export const J = () => <div role="status">\n  <svg className="animate-spin" />\n</div>', [2]],
      // Read strictly: aria-hidden on a component around the glyph, or in a spread.
      ['export const K = () => <Wrapper aria-hidden="true">\n  <svg className="animate-spin" />\n</Wrapper>', [2]],
      ['export const L = (props: object) => <svg {...props} className="animate-spin" />', [1]],
      // Passed: a still glyph needs nothing; gaps, as stated: a list built outside the element, a const or a helper's return.
      ['export const M = () => <CircleNotchIcon className="h-4 w-4" />', []],
      ["const TURNING = 'h-4 w-4 animate-spin'\nexport const N = () => <svg className={TURNING} />", []],
      ["const turning = () => 'h-4 w-4 animate-spin'\nexport const O = () => <svg className={turning()} />", []],
    ]
    expect(planted.map(([source]) => unhiddenSpinners(source, 'planted.tsx'))).toEqual(planted.map(([, lines]) => lines))
  })

  it('every spinner is allowlisted, at its count', () => {
    const problems: string[] = []
    const found = new Map<string, number>()
    for (const file of sourceFiles(ROOT, SCAN_DIRS)) {
      const sites = spinnerSites(fs.readFileSync(path.join(ROOT, file), 'utf8'), file)
      if (sites > 0) found.set(file, sites)
    }
    for (const file of [...new Set([...found.keys(), ...Object.keys(ALLOW)])].sort()) {
      const actual = found.get(file) ?? 0
      const allowed = ALLOW[file]?.sites ?? 0
      if (actual > allowed) problems.push(`${file}: ${actual} spinners, ${allowed} allowed`)
      else if (actual < allowed) problems.push(`${file}: ${actual} spinners, ${allowed} allowed: lower its count or delete its entry (stale)`)
    }
    expect(
      problems,
      "A spinner outside Button and Input marks a control's own request (in place of its icon, the control aria-busy) " +
        "or a page's one read (in a region that names the wait): DESIGN_SYSTEM.md §4 › Spinner. A run in progress " +
        'shown in words is <ActivityLine>, a loading layout is <Skeleton> bones, a busy Button is <Button loading>.',
    ).toEqual([])
  })

  it('every spinner glyph is aria-hidden', () => {
    const unhidden = sourceFiles(ROOT, SCAN_DIRS).flatMap((file) =>
      unhiddenSpinners(fs.readFileSync(path.join(ROOT, file), 'utf8'), file).map((line) => `${file}:${line}`),
    )
    expect(
      unhidden,
      "A spinner says nothing: the control's aria-busy, the region's name or the words beside it say what waits. " +
        'Set aria-hidden="true" on the glyph (DESIGN_SYSTEM.md §4 › Spinner).',
    ).toEqual([])
  })

  it('the allowlist is held to its cap and gives each entry its reason', () => {
    expect(Object.keys(ALLOW).length, 'a new spinner names the wait it marks in a new entry, and raises the cap with it').toBe(MAX_ALLOWLIST_SIZE)
    for (const [file, entry] of Object.entries(ALLOW)) {
      expect(entry.reason.length, `${file}: give the entry its reason`).toBeGreaterThan(20)
    }
  })
})
