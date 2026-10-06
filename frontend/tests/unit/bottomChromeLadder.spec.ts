/* =============================================================================
   bottomChromeLadder.spec.ts — guardrail (EN-02, CLAUDE.md rule 12)
   -----------------------------------------------------------------------------
   The research chrome on the filing page is fixed bottom chrome: the "Ask this
   Filing" launcher and the first-run coachmark (z-40), the workspace / copilot
   bottom sheets (z-40) over their scrims (z-30), and the feedback launcher
   (z-30, bottom-left). The cookie-consent bar used to sit over all of it at
   z-50: elementFromPoint at the launcher's centre returned "Accept All", the
   coachmark pointed at a covered launcher and the mobile sheet's composer was
   behind the bar. DESIGN_SYSTEM §4 Stacking now gives the bar its own layer,
   z-consent (35), BENEATH that chrome, and the chrome adds the bar's height
   (--consent-inset, published by CookieConsent through lib/consentLayer) to
   its bottom offset while the bar is mounted, so both control sets stay usable.
   The layer also sits ABOVE the page's own sticky chrome (z-sticky 30): a first
   cut at 20 let the mobile section nav, in its unscrolled position on a short
   phone, paint over "Accept All" (320x568).

   The scan reads each file's TypeScript AST (comments never count) and takes
   every string literal, and every template literal's static chunks joined,
   whose class tokens include `fixed` (behind any variant prefix) as a fixed site. Its rank is the HIGHEST z
   token in the list — unprefixed or behind any variant (`z-30 lg:z-50` ranks
   50): a number, a zIndex ladder name, or 0 when absent / auto (a fixed element
   at z-auto outranks nothing and is not counted).
     exempt   z-overlay / z-modal / z-toast ride the documented transient layers
              above the workspace — popovers, dialogs + the source and viewer
              sheets, the skip link; a real modal may legitimately make the page
              beneath it inert, and it is gone on dismissal.
     pinned   the workspace layers and the feedback launcher, each file pinned
              to its exact z counts with a reason (the dialogAllowlist idiom).
              A pinned site that moves up OR down fails: lowering the sheet to
              the consent layer would put it under the bar again.
     other    every other fixed site must rank below z-consent: no fixed chrome
              outranks the workspace layers at the launcher corner, and nothing
              ties with the bar (equal z is DOM order).
     sticky   every sticky site ranks below z-consent, so in-page sticky chrome
              passing through the bar's region never paints over a consent
              choice; the top-anchored site and page headers are pinned (they
              stick at the top of the viewport, away from the bar).
   Because a z can be written apart from its `fixed` (`clsx('fixed', 'z-50')`,
   `const z = 'z-50'`, `style={{ zIndex: 60 }}`), a file that has any fixed site
   is also held to its highest z token in ANY string literal and its highest
   inline `zIndex:` — below z-consent unless the file is pinned (then at most
   its pinned z, and no inline zIndex at all).
   A lower z alone would let the launcher cover a consent choice (the finding's
   addendum), so a second check keeps the fix honest: the pinned sheets anchor
   on `bottom-[var(--consent-inset,0px)]` and subtract the inset from their vh
   cap, no pinned file carries a `bottom-0` anchor behind any variant (the lg+
   docked overlay once did), the launcher / coachmark offset objects take their
   `bottom` from BOTTOM_CHROME_OFFSET (not merely importing it), the bar itself
   rides z-consent and calls publishConsentLayer inside a layout effect, and
   globals.css reserves the inset as the document's bottom scroll padding (a
   focus never lands a control behind the bar). Inline `position: 'fixed'`
   style objects (`as const` and parentheses included) are anchored popovers
   placed at their trigger, never bottom chrome; they are pinned by count so a
   new one is reviewed here rather than slipping past the class-token scan.
   Every pin list is shrink-only in files, in sites and in z.

   Mutations recorded in the PR: `z-consent` → `z-50` on the bar in
   components/CookieConsent.tsx fails the ladder check, naming the file;
   `z-sticky` → `z-40` on SummaryBlocks' section nav fails the sticky clause;
   dropping the scroll padding from globals.css fails the inset clause.
============================================================================= */

import fs from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

const ROOT = path.join(__dirname, '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const Z_INDEX: Record<string, string> = createRequire(import.meta.url)('../../tailwind.config.js').theme.extend.zIndex
const CONSENT_Z = Number(Z_INDEX.consent)
const CONSENT_LAYER_MODULE = '@/lib/consentLayer'
const INSET_VAR = '--consent-inset'
const INSET_ANCHOR = `bottom-[var(${INSET_VAR},0px)]`
/** The documented transient layers above the workspace (popovers, dialogs + sheets, toasts / skip link). */
const TRANSIENT_LAYERS = new Set(['overlay', 'modal', 'toast'])

// Shrink-only: lower a count or drop an entry when a site goes; never raise one to fit new fixed chrome.
const PINNED: Record<string, { z: Record<string, number>; reason: string }> = {
  'features/filings/components/copilot/FilingWorkspace.tsx': {
    z: { '40': 2, '30': 1 },
    reason: 'the workspace sheet and the "Ask this Filing" launcher (z-40) over the mobile scrim (z-30)',
  },
  'features/filings/components/copilot/AskCopilotRail.tsx': {
    z: { '40': 2, '30': 1 },
    reason: 'the standalone copilot sheet and launcher (z-40) over their scrim (z-30)',
  },
  'features/filings/components/copilot/CopilotCoachmark.tsx': {
    z: { '40': 1 },
    reason: 'the first-run coachmark floats with the launcher',
  },
  'features/feedback/components/FeedbackWidget.tsx': {
    z: { '30': 1 },
    reason: 'the feedback launcher, bottom-left at scrim level, beneath the Ask chrome',
  },
}
/** The pins' frozen totals: files, sites and the highest z any pinned site may use. */
const PINNED_LIMITS = { files: 4, sites: 8, maxZ: 40 }
/** Inline-style offset objects of fixed chrome: their `bottom` must come from BOTTOM_CHROME_OFFSET. */
const OFFSET_OBJECTS: Record<string, string[]> = {
  'features/filings/components/copilot/FilingWorkspace.tsx': ['LAUNCHER_OFFSET', 'COACHMARK_OFFSET'],
  'features/filings/components/copilot/AskCopilotRail.tsx': ['LAUNCHER_OFFSET'],
  'features/feedback/components/FeedbackWidget.tsx': ['LAUNCHER_OFFSET'],
}
const CONSENT_BAR = 'components/CookieConsent.tsx'
/** Sticky chrome that outranks the bar: top-anchored headers only, pinned to their exact z counts. */
const STICKY_ABOVE_CONSENT: Record<string, { z: Record<string, number>; reason: string }> = {
  'components/Header.tsx': { z: { '50': 1 }, reason: 'the site header sticks at the top of the viewport' },
  'components/SecondaryHeader.tsx': { z: { '40': 1 }, reason: 'the page header (dashboard, watchlist, pricing, admin) sticks at the top' },
}
const STICKY_LIMITS = { files: 2, maxZ: 50 }
/** Inline `position: 'fixed'` style objects — anchored popovers at their trigger, never bottom chrome. */
const INLINE_FIXED: Record<string, number> = {
  'features/filings/components/copilot/AskAboutSelection.tsx': 1,
  'features/filings/components/copilot/CitationChip.tsx': 1,
  'features/filings/components/SourceTrace.tsx': 1,
}
const INLINE_FIXED_TOTAL = 3

type Rank = number | 'transient'
interface FixedSite {
  text: string
  rank: Rank
}
interface FileScan {
  fixed: FixedSite[]
  sticky: FixedSite[]
  inlineFixed: number
  /** The highest numeric z token in ANY string literal of the file (a z written apart from its `fixed`). */
  maxZ: number
  /** The highest numeric inline `zIndex:` style property in the file. */
  maxInlineZ: number
  /** `bottom-0` anchors, behind any variant, found in class lists. */
  bottomZeroAnchors: string[]
  /** Named imports from lib/consentLayer. */
  consentImports: Set<string>
  /** Offset object literals by name: does their `bottom` take BOTTOM_CHROME_OFFSET? */
  offsetObjects: Record<string, boolean>
  /** publishConsentLayer(…) is called inside a useLayoutEffect callback. */
  publishesInLayoutEffect: boolean
}

const utility = (token: string) => (token.split(':').pop() as string).replace(/^!/, '')
const classTokens = (text: string) => text.split(/\s+/).filter(Boolean)
const isFixedClassList = (text: string) => classTokens(text).some((token) => utility(token) === 'fixed')
const isStickyClassList = (text: string) => classTokens(text).some((token) => utility(token) === 'sticky')

/** Numeric value of one z token name (a number or a ladder name); null for auto / transient / none. */
function zValue(name: string, token: string): number | null {
  if (TRANSIENT_LAYERS.has(name) || name === 'auto') return null
  if (/^\d+$/.test(name)) return Number(name)
  if (name in Z_INDEX) return Number(Z_INDEX[name])
  // z-[N] is the design lint's business (DataTable's internal z-[5] is its one exemption); here it ranks as N.
  const arbitrary = /^\[(\d+)\]$/.exec(name)
  if (arbitrary) return Number(arbitrary[1])
  throw new Error(`cannot rank "${token}": use a zIndex ladder token (DESIGN_SYSTEM §4)`)
}

/** The highest numeric z token in a class list, behind any variant; 0 when none. */
function maxZOf(text: string): number {
  let max = 0
  for (const token of classTokens(text)) {
    const u = utility(token)
    if (!/^z-/.test(u)) continue
    max = Math.max(max, zValue(u.slice(2), token) ?? 0)
  }
  return max
}

/** The z rank of a fixed / sticky class list: its highest numeric z; else 'transient' if it rides one; else 0. */
function rankOf(text: string): Rank {
  const numeric = maxZOf(text)
  if (numeric > 0) return numeric
  const transient = classTokens(text).some((token) => TRANSIENT_LAYERS.has(utility(token).replace(/^z-/, '')) && /^z-/.test(utility(token)))
  return transient ? 'transient' : 0
}

const bottomZeroTokens = (text: string) => classTokens(text).filter((token) => utility(token) === 'bottom-0')

/** Unwrap `as const`, `satisfies`, `<T>x` and parentheses around an initializer. */
function unwrap(node: ts.Expression): ts.Expression {
  let current = node
  for (;;) {
    if (ts.isAsExpression(current) || ts.isSatisfiesExpression(current) || ts.isTypeAssertionExpression(current) || ts.isParenthesizedExpression(current)) {
      current = current.expression
    } else {
      return current
    }
  }
}

const numericOf = (node: ts.Expression): number | null => {
  const inner = unwrap(node)
  if (ts.isNumericLiteral(inner)) return Number(inner.text)
  if (ts.isStringLiteralLike(inner) && /^\d+$/.test(inner.text)) return Number(inner.text)
  return null
}

const propertyName = (node: ts.PropertyAssignment) =>
  ts.isIdentifier(node.name) || ts.isStringLiteral(node.name) ? node.name.text : null

/** `bottom: BOTTOM_CHROME_OFFSET` or `bottom: \`calc(${BOTTOM_CHROME_OFFSET} + …)\``. */
function usesChromeOffset(node: ts.Expression): boolean {
  const inner = unwrap(node)
  if (ts.isIdentifier(inner)) return inner.text === 'BOTTOM_CHROME_OFFSET'
  if (ts.isTemplateExpression(inner)) return inner.templateSpans.some((span) => usesChromeOffset(span.expression))
  return false
}

function containsCall(node: ts.Node, callee: string): boolean {
  let found = false
  const look = (n: ts.Node): void => {
    if (found) return
    if (ts.isCallExpression(n) && ts.isIdentifier(n.expression) && n.expression.text === callee) {
      found = true
      return
    }
    ts.forEachChild(n, look)
  }
  look(node)
  return found
}

function scanSource(source: string, fileName: string, offsetObjects: string[] = []): FileScan {
  const sourceFile = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    fileName.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  )
  const out: FileScan = {
    fixed: [],
    sticky: [],
    inlineFixed: 0,
    maxZ: 0,
    maxInlineZ: 0,
    bottomZeroAnchors: [],
    consentImports: new Set(),
    offsetObjects: {},
    publishesInLayoutEffect: false,
  }
  const visit = (node: ts.Node): void => {
    // A template's static chunks form one class list (`fixed ${pos} z-40` ranks 40); the string
    // literals inside its ${…} spans are visited as their own sites below.
    const text = ts.isStringLiteralLike(node)
      ? node.text
      : ts.isTemplateExpression(node)
        ? [node.head.text, ...node.templateSpans.map((span) => span.literal.text)].join(' ')
        : null
    if (text !== null) {
      out.maxZ = Math.max(out.maxZ, maxZOf(text))
      out.bottomZeroAnchors.push(...bottomZeroTokens(text))
      if (isFixedClassList(text)) out.fixed.push({ text, rank: rankOf(text) })
      else if (isStickyClassList(text)) out.sticky.push({ text, rank: rankOf(text) })
    }
    if (ts.isPropertyAssignment(node)) {
      const name = propertyName(node)
      if (name === 'position') {
        const inner = unwrap(node.initializer)
        if (ts.isStringLiteralLike(inner) && inner.text === 'fixed') {
          out.inlineFixed += 1
          return // the 'fixed' value is a style keyword, not a class list
        }
      } else if (name === 'zIndex') {
        out.maxInlineZ = Math.max(out.maxInlineZ, numericOf(node.initializer) ?? 0)
      }
    }
    if (
      ts.isImportDeclaration(node) &&
      ts.isStringLiteral(node.moduleSpecifier) &&
      node.moduleSpecifier.text === CONSENT_LAYER_MODULE &&
      node.importClause?.namedBindings &&
      ts.isNamedImports(node.importClause.namedBindings)
    ) {
      for (const el of node.importClause.namedBindings.elements) out.consentImports.add((el.propertyName ?? el.name).text)
    }
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && offsetObjects.includes(node.name.text) && node.initializer) {
      const init = unwrap(node.initializer)
      const bottom = ts.isObjectLiteralExpression(init)
        ? init.properties.find((p): p is ts.PropertyAssignment => ts.isPropertyAssignment(p) && propertyName(p) === 'bottom')
        : undefined
      out.offsetObjects[node.name.text] = bottom ? usesChromeOffset(bottom.initializer) : false
    }
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'useLayoutEffect') {
      if (containsCall(node, 'publishConsentLayer')) out.publishesInLayoutEffect = true
    }
    ts.forEachChild(node, visit)
  }
  visit(sourceFile)
  return out
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

let scanned: Map<string, FileScan> | undefined
function scan(): Map<string, FileScan> {
  if (scanned) return scanned
  const found = new Map<string, FileScan>()
  for (const dir of SCAN_DIRS) {
    for (const file of walk(path.join(ROOT, dir))) {
      const rel = path.relative(ROOT, file).split(path.sep).join('/')
      const result = scanSource(fs.readFileSync(file, 'utf8'), file, OFFSET_OBJECTS[rel] ?? [])
      if (result.fixed.length || result.sticky.length || result.inlineFixed || result.consentImports.size) {
        found.set(rel, result)
      }
    }
  }
  scanned = found
  return found
}

// Any fixed site counts, transient ones included: a split literal could hand a z-50 to a z-toast element too.
const hasFixedChrome = (r: FileScan) => r.inlineFixed > 0 || r.fixed.length > 0

/** Numeric ranks above auto, counted per value — what the pins describe. */
const rankedCounts = (sites: FixedSite[]) => {
  const counts: Record<string, number> = {}
  for (const site of sites) {
    if (site.rank === 'transient' || site.rank === 0) continue
    counts[String(site.rank)] = (counts[String(site.rank)] ?? 0) + 1
  }
  return counts
}
const maxPinnedZ = (z: Record<string, number>) => Math.max(0, ...Object.keys(z).map(Number))

describe('no fixed bottom chrome outranks the workspace layers at the launcher corner', () => {
  it('the detector reads fixed class lists, their rank, inline fixed styles and the consent imports', () => {
    expect(rankOf('fixed bottom-0 z-50 bg-panel-light')).toBe(50)
    expect(rankOf('fixed bottom-0 z-consent')).toBe(CONSENT_Z)
    expect(rankOf('lg:hidden fixed inset-0 z-30 bg-overlay')).toBe(30)
    expect(rankOf('fixed inset-x-0 bottom-0 z-40 lg:static lg:z-auto')).toBe(40)
    expect(rankOf('fixed bottom-0 z-30 lg:z-50')).toBe(50) // the highest token, behind any variant
    expect(rankOf('sr-only focus:not-sr-only focus:fixed focus:z-toast')).toBe('transient')
    expect(rankOf('fixed inset-0 z-modal')).toBe('transient')
    expect(rankOf('fixed inset-0 z-overlay')).toBe('transient')
    expect(rankOf('fixed z-overlay md:z-50')).toBe(50) // a numeric beside a transient counts
    expect(rankOf('fixed rounded-lg shadow-e4')).toBe(0)
    expect(rankOf('fixed z-auto')).toBe(0)
    expect(rankOf('fixed z-[55]')).toBe(55) // an arbitrary value ranks as its number (the design lint bans it)
    expect(() => rankOf('fixed z-nope')).toThrow(/ladder token/)
    expect(isFixedClassList('focus:fixed')).toBe(true)
    expect(isFixedClassList('fixed-width')).toBe(false)
    expect(isFixedClassList('fixedness')).toBe(false)

    const kinds = (code: string, offsets: string[] = []) => {
      const r = scanSource(code, 'fixture.tsx', offsets)
      return {
        fixed: r.fixed.map((s) => s.rank),
        sticky: r.sticky.map((s) => s.rank),
        inline: r.inlineFixed,
        maxZ: r.maxZ,
        maxInlineZ: r.maxInlineZ,
        anchors: r.bottomZeroAnchors,
        imports: [...r.consentImports],
        offsets: r.offsetObjects,
        layoutPublish: r.publishesInLayoutEffect,
      }
    }
    const none = { fixed: [], sticky: [], inline: 0, maxZ: 0, maxInlineZ: 0, anchors: [], imports: [], offsets: {}, layoutPublish: false }
    expect(kinds('const a = <div className="fixed bottom-0 z-50" />')).toEqual({ ...none, fixed: [50], maxZ: 50, anchors: ['bottom-0'] })
    expect(kinds('const a = `fixed ${pos} z-40`')).toEqual({ ...none, fixed: [40], maxZ: 40 })
    expect(kinds("const a = `${open ? 'fixed z-50' : ''} w-full`")).toEqual({ ...none, fixed: [50], maxZ: 50 })
    expect(kinds('const a = `${SHELL} ${open ? "lg:border-l" : "hidden"}`')).toEqual(none)
    // a z written apart from its fixed is still the file's z
    expect(kinds("const a = clsx('fixed bottom-0 right-0', 'z-50')")).toEqual({ ...none, fixed: [0], maxZ: 50, anchors: ['bottom-0'] })
    expect(kinds("const z = 'z-50'; const a = `fixed ${z}`")).toEqual({ ...none, fixed: [0], maxZ: 50 })
    expect(kinds('const a = <div className="fixed bottom-0" style={{ zIndex: 60 }} />')).toEqual({ ...none, fixed: [0], maxInlineZ: 60, anchors: ['bottom-0'] })
    expect(kinds("const s = { zIndex: '55' }")).toEqual({ ...none, maxInlineZ: 55 })
    expect(kinds('const a = "fixed inset-x-0 bottom-0 lg:bottom-0 z-40"')).toEqual({ ...none, fixed: [40], maxZ: 40, anchors: ['bottom-0', 'lg:bottom-0'] })
    expect(kinds("const s = { position: 'fixed', top: 1 }")).toEqual({ ...none, inline: 1 })
    expect(kinds("const s = { 'position': 'fixed' }")).toEqual({ ...none, inline: 1 })
    expect(kinds("const s = { position: 'fixed' as const }")).toEqual({ ...none, inline: 1 })
    expect(kinds("const s = { position: ('fixed') }")).toEqual({ ...none, inline: 1 })
    expect(kinds("const p = 'fixed'; const s = { position: p }")).toEqual({ ...none, fixed: [0] }) // the bare literal is a fixed site
    expect(kinds('const n = <nav className="sticky top-16 z-sticky -mx-4" />')).toEqual({ ...none, sticky: [30], maxZ: 30 })
    expect(kinds('const n = <header className="sticky top-0 z-40" />')).toEqual({ ...none, sticky: [40], maxZ: 40 })
    expect(kinds('const c = "relative min-w-0 lg:sticky lg:top-16"')).toEqual({ ...none, sticky: [0] })
    expect(kinds("import { BOTTOM_CHROME_OFFSET as o, CONSENT_INSET } from '@/lib/consentLayer'")).toEqual({
      ...none,
      imports: ['BOTTOM_CHROME_OFFSET', 'CONSENT_INSET'],
    })
    // offset objects: the bottom must come from BOTTOM_CHROME_OFFSET, directly or inside a template
    expect(kinds("const LAUNCHER_OFFSET = { bottom: BOTTOM_CHROME_OFFSET, right: '1rem' }", ['LAUNCHER_OFFSET']).offsets).toEqual({ LAUNCHER_OFFSET: true })
    expect(kinds('const COACHMARK_OFFSET: CSSProperties = { bottom: `calc(${BOTTOM_CHROME_OFFSET} + 4rem)` }', ['COACHMARK_OFFSET']).offsets).toEqual({ COACHMARK_OFFSET: true })
    expect(kinds("const LAUNCHER_OFFSET = { bottom: '1.25rem' }", ['LAUNCHER_OFFSET']).offsets).toEqual({ LAUNCHER_OFFSET: false })
    expect(kinds("const LAUNCHER_OFFSET = { right: '1rem' }", ['LAUNCHER_OFFSET']).offsets).toEqual({ LAUNCHER_OFFSET: false })
    // the bar publishes from a layout effect, not from anywhere
    expect(kinds('useLayoutEffect(() => { const m = () => publishConsentLayer(1); m() }, [])').layoutPublish).toBe(true)
    expect(kinds('useEffect(() => { publishConsentLayer(1) }, [])').layoutPublish).toBe(false)
    // comments never count; prose with the word is harmless (rank 0 is not counted)
    expect(kinds('// fixed bottom-0 z-50\n/* position: "fixed" */ const a = 1')).toEqual(none)
    expect(rankedCounts(scanSource('const t = "a fixed income table"', 'f.ts').fixed)).toEqual({})
    expect(rankedCounts([{ text: '', rank: 40 }, { text: '', rank: 40 }, { text: '', rank: 30 }, { text: '', rank: 'transient' }])).toEqual({
      '40': 2,
      '30': 1,
    })
  })

  it('every fixed site that is not pinned ranks below z-consent; only the bar sits on it (transient layers exempt)', () => {
    const offenders = [...scan()]
      .filter(([file]) => !(file in PINNED) && file !== CONSENT_BAR)
      .flatMap(([file, { fixed }]) =>
        fixed
          .filter((site) => site.rank !== 'transient' && site.rank >= CONSENT_Z)
          .map((site) => `${file}: fixed chrome at z-${site.rank} (must be below z-consent = ${CONSENT_Z}) — "${site.text.slice(0, 60)}"`),
      )
    expect(
      offenders,
      'Fixed chrome at or above z-consent covers the workspace launcher / sheets / coachmark at the launcher corner, or ties ' +
        'with the bar (equal z is DOM order). Rank it below z-consent and let the bar paint over it, ride a transient layer ' +
        '(z-overlay / z-modal / z-toast) for a popover or dialog, or, for a new workspace layer, pin it here with its reason.',
    ).toEqual([])
  })

  it('a file with fixed chrome carries no z token or inline zIndex at or above z-consent anywhere (a z written apart from its fixed)', () => {
    const problems: string[] = []
    for (const [file, r] of scan()) {
      if (!hasFixedChrome(r)) continue
      const ceiling = file in PINNED ? maxPinnedZ(PINNED[file].z) : file === CONSENT_BAR ? CONSENT_Z : CONSENT_Z - 1
      if (r.maxZ > ceiling) problems.push(`${file}: a z-${r.maxZ} token in a file with fixed chrome (ceiling z-${ceiling})`)
      if (r.maxInlineZ > 0 && (file in PINNED || file === CONSENT_BAR || r.maxInlineZ >= CONSENT_Z)) {
        problems.push(`${file}: inline zIndex ${r.maxInlineZ} in a file with fixed chrome`)
      }
    }
    expect(
      problems,
      'A z that is not in the same class list as its `fixed` (clsx(…, "z-50"), a const, an inline style) still paints the fixed ' +
        'element there. Keep every z in a file with fixed chrome below z-consent (pinned files: at their pinned z, never an inline zIndex).',
    ).toEqual([])
  })

  it('no in-page sticky chrome ranks at or above z-consent (the top-anchored headers are pinned)', () => {
    const offenders = [...scan()]
      .filter(([file]) => !(file in STICKY_ABOVE_CONSENT))
      .flatMap(([file, { sticky }]) =>
        sticky
          .filter((site) => site.rank !== 'transient' && site.rank >= CONSENT_Z)
          .map((site) => `${file}: sticky chrome at z-${site.rank} (must be below z-consent = ${CONSENT_Z}) — "${site.text.slice(0, 60)}"`),
      )
    expect(
      offenders,
      "Sticky chrome at or above z-consent paints over the consent bar wherever it passes through the bar's region " +
        '(a section nav in its unscrolled position on a short phone). Use z-sticky for in-page sticky chrome; a header ' +
        'that sticks at the top of the viewport is pinned here with its reason.',
    ).toEqual([])
    for (const [file, { z, reason }] of Object.entries(STICKY_ABOVE_CONSENT)) {
      expect(fs.existsSync(path.join(ROOT, file)), `${file} is pinned but does not exist`).toBe(true)
      expect(reason.trim().length, `${file} needs a reason`).toBeGreaterThan(0)
      expect(rankedCounts(scan().get(file)?.sticky ?? []), `${file} drifted from its sticky pin`).toEqual(z)
    }
  })

  it.each(Object.entries(PINNED))('%s still declares exactly its pinned fixed sites', (file, { z, reason }) => {
    expect(fs.existsSync(path.join(ROOT, file)), `${file} is pinned but does not exist`).toBe(true)
    expect(reason.trim().length, `${file} needs a reason`).toBeGreaterThan(0)
    expect(
      rankedCounts(scan().get(file)?.fixed ?? []),
      `${file} drifted from its pin. A workspace layer moved up (it would cover the launcher corner) or down ` +
        '(it would sit under the consent bar), or a fixed site was added or removed: update the pin only for a documented ladder change.',
    ).toEqual(z)
  })

  it('the pinned bottom chrome takes the consent inset, and the bar publishes it from z-consent', () => {
    const problems: string[] = []
    for (const file of Object.keys(PINNED)) {
      const r = scan().get(file)
      for (const site of r?.fixed ?? []) {
        if (site.rank !== 40) continue
        const tokens = classTokens(site.text).filter((token) => !token.includes(':'))
        const bottom = tokens.filter((token) => /^bottom-/.test(token))
        const vhCaps = tokens.filter((token) => /^max-h-\[.*vh/.test(token))
        for (const token of bottom) if (token !== INSET_ANCHOR) problems.push(`${file}: "${token}" is not ${INSET_ANCHOR}`)
        for (const token of vhCaps) if (!token.includes(INSET_VAR)) problems.push(`${file}: "${token}" can exceed the viewport over the bar`)
        if (bottom.length === 0 && site.text.includes('inset-x-0')) problems.push(`${file}: a sheet without a bottom-[…] anchor`)
      }
      // No `bottom-0` behind any variant in a pinned file: the lg+ docked overlay once re-anchored itself under the bar that way.
      for (const token of r?.bottomZeroAnchors ?? []) problems.push(`${file}: "${token}" anchors fixed chrome under the bar (use ${INSET_ANCHOR})`)
    }
    for (const [file, names] of Object.entries(OFFSET_OBJECTS)) {
      const r = scan().get(file)
      if (!r?.consentImports.has('BOTTOM_CHROME_OFFSET')) {
        problems.push(`${file}: inline-positioned launcher must import BOTTOM_CHROME_OFFSET from ${CONSENT_LAYER_MODULE}`)
      }
      for (const name of names) {
        if (r?.offsetObjects[name] !== true) problems.push(`${file}: ${name}.bottom must be BOTTOM_CHROME_OFFSET (or a calc() around it)`)
      }
    }
    const bar = scan().get(CONSENT_BAR)
    if (bar?.fixed.map((s) => s.rank).join() !== String(CONSENT_Z)) {
      problems.push(`${CONSENT_BAR}: expected exactly one fixed site on z-consent, found ${JSON.stringify(bar?.fixed.map((s) => s.rank) ?? [])}`)
    }
    if (!bar?.publishesInLayoutEffect) problems.push(`${CONSENT_BAR}: must call publishConsentLayer inside a useLayoutEffect`)
    // The scrollport reserves the inset too: a focus or scrollIntoView must never land behind the bar.
    const globalsCss = fs.readFileSync(path.join(ROOT, 'app/globals.css'), 'utf8')
    if (!/scroll-padding-bottom:\s*var\(--consent-inset,\s*0px\)/.test(globalsCss)) {
      problems.push(`app/globals.css: html must set scroll-padding-bottom: var(${INSET_VAR}, 0px)`)
    }
    expect(
      problems,
      'A lower z alone is not enough: the launcher would cover a consent choice. The sheets anchor on ' +
        `${INSET_ANCHOR} and subtract it from their vh cap; inline-positioned launchers take their bottom from BOTTOM_CHROME_OFFSET.`,
    ).toEqual([])
  })

  it('inline position:fixed styles are the pinned anchored popovers only', () => {
    const found = Object.fromEntries([...scan()].filter(([, r]) => r.inlineFixed > 0).map(([file, r]) => [file, r.inlineFixed]))
    expect(
      found,
      'A new inline position:fixed site: position bottom chrome with the ladder tokens (and the consent inset), ' +
        'or pin an anchored popover here with the others.',
    ).toEqual(INLINE_FIXED)
  })

  it('the pin lists are shrink-only: files, sites and z', () => {
    expect(Object.keys(PINNED).length, 'ride an existing layer instead of pinning a new file').toBeLessThanOrEqual(PINNED_LIMITS.files)
    const sites = Object.values(PINNED).reduce((n, { z }) => n + Object.values(z).reduce((a, b) => a + b, 0), 0)
    expect(sites, 'a new fixed site in a pinned file needs a documented ladder change, not a raised count').toBeLessThanOrEqual(PINNED_LIMITS.sites)
    for (const [file, { z }] of Object.entries(PINNED)) expect(maxPinnedZ(z), `${file} pinned above the workspace layers`).toBeLessThanOrEqual(PINNED_LIMITS.maxZ)
    expect(Object.keys(STICKY_ABOVE_CONSENT).length).toBeLessThanOrEqual(STICKY_LIMITS.files)
    for (const [file, { z }] of Object.entries(STICKY_ABOVE_CONSENT)) expect(maxPinnedZ(z), `${file} pinned above the header`).toBeLessThanOrEqual(STICKY_LIMITS.maxZ)
    expect(Object.values(INLINE_FIXED).reduce((a, b) => a + b, 0)).toBeLessThanOrEqual(INLINE_FIXED_TOTAL)
  })
})
