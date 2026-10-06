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
   whose class tokens include `fixed` (behind any variant prefix) as a fixed site. Its rank is the first `z-*`
   token — unprefixed first, then any variant: a number, a zIndex ladder name,
   or 0 when absent / auto (a fixed element at z-auto outranks nothing and is
   not counted).
     exempt   z-overlay / z-modal / z-toast ride the documented transient layers
              above the workspace — popovers, dialogs + the source and viewer
              sheets, the skip link; a real modal may legitimately make the page
              beneath it inert, and it is gone on dismissal.
     pinned   the workspace layers and the feedback launcher, each file pinned
              to its exact z counts with a reason (the dialogAllowlist idiom).
              A pinned site that moves up OR down fails: lowering the sheet to
              the consent layer would put it under the bar again.
     other    every other fixed site must rank at or below z-consent: no fixed
              chrome outranks the workspace layers at the launcher corner.
     sticky   every sticky site ranks below z-consent, so in-page sticky chrome
              passing through the bar's region never paints over a consent
              choice; the top-anchored site and page headers are pinned (they
              stick at the top of the viewport, away from the bar).
   A lower z alone would let the launcher cover a consent choice (the finding's
   addendum), so a second check keeps the fix honest: the pinned sheets anchor
   on `bottom-[var(--consent-inset,0px)]` and subtract the inset from their vh
   cap, the files that place launchers with inline styles import
   BOTTOM_CHROME_OFFSET, the bar itself rides z-consent and publishes the
   inset, and globals.css reserves the inset as the document's bottom scroll
   padding (a focus never lands a control behind the bar). Inline
   `position: 'fixed'` style objects are anchored popovers placed
   at their trigger, never bottom chrome; they are pinned by count so a new one
   is reviewed here rather than slipping past the class-token scan.

   Mutation recorded in the PR: `z-consent` → `z-50` on the bar in
   components/CookieConsent.tsx fails the ladder check, naming the file
   (`z-sticky` → `z-40` on SummaryBlocks' section nav fails the sticky clause).
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
/** The documented transient layers above the workspace (popovers, dialogs + sheets, toasts / skip link). */
const TRANSIENT_LAYERS = new Set(['overlay', 'modal', 'toast'])

// Shrink-only: lower a count or drop an entry when a site goes; never raise one to fit new fixed chrome.
const MAX_PINNED_FILES = 4
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
/** Fixed chrome positioned with an inline style takes the consent inset through the shared offset. */
const OFFSET_IMPORTERS = [
  'features/filings/components/copilot/FilingWorkspace.tsx',
  'features/filings/components/copilot/AskCopilotRail.tsx',
  'features/feedback/components/FeedbackWidget.tsx',
]
const CONSENT_BAR = 'components/CookieConsent.tsx'
/** Sticky chrome that outranks the bar: top-anchored headers only, pinned to their exact z counts. */
const STICKY_ABOVE_CONSENT: Record<string, { z: Record<string, number>; reason: string }> = {
  'components/Header.tsx': { z: { '50': 1 }, reason: 'the site header sticks at the top of the viewport' },
  'components/SecondaryHeader.tsx': { z: { '40': 1 }, reason: 'the page header (dashboard, watchlist, pricing, admin) sticks at the top' },
}
/** Inline `position: 'fixed'` style objects — anchored popovers at their trigger, never bottom chrome. */
const INLINE_FIXED: Record<string, number> = {
  'features/filings/components/copilot/AskAboutSelection.tsx': 1,
  'features/filings/components/copilot/CitationChip.tsx': 1,
  'features/filings/components/SourceTrace.tsx': 1,
}

type Rank = number | 'transient'
interface FixedSite {
  text: string
  rank: Rank
}
interface FileScan {
  fixed: FixedSite[]
  sticky: FixedSite[]
  inlineFixed: number
  /** Named imports from lib/consentLayer. */
  consentImports: Set<string>
}

const utility = (token: string) => (token.split(':').pop() as string).replace(/^!/, '')
const classTokens = (text: string) => text.split(/\s+/).filter(Boolean)
const isFixedClassList = (text: string) => classTokens(text).some((token) => utility(token) === 'fixed')
const isStickyClassList = (text: string) => classTokens(text).some((token) => utility(token) === 'sticky')

/** The z rank of a fixed class list: the unprefixed z token, else the first variant one, else 0. */
function rankOf(text: string): Rank {
  const zs = classTokens(text).filter((token) => /^z-/.test(utility(token)))
  const pick = zs.find((token) => !token.includes(':')) ?? zs[0]
  if (!pick) return 0
  const name = utility(pick).slice(2)
  if (TRANSIENT_LAYERS.has(name)) return 'transient'
  if (name === 'auto') return 0
  if (/^\d+$/.test(name)) return Number(name)
  if (name in Z_INDEX) return Number(Z_INDEX[name])
  throw new Error(`cannot rank "${pick}": use a zIndex ladder token (DESIGN_SYSTEM §4), never z-[N]`)
}

function scanSource(source: string, fileName: string): FileScan {
  const sourceFile = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    fileName.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  )
  const out: FileScan = { fixed: [], sticky: [], inlineFixed: 0, consentImports: new Set() }
  const visit = (node: ts.Node): void => {
    // A template's static chunks form one class list (`fixed ${pos} z-40` ranks 40); the string
    // literals inside its ${…} spans are visited as their own sites below.
    const text = ts.isStringLiteralLike(node)
      ? node.text
      : ts.isTemplateExpression(node)
        ? [node.head.text, ...node.templateSpans.map((span) => span.literal.text)].join(' ')
        : null
    if (text !== null && isFixedClassList(text)) {
      out.fixed.push({ text, rank: rankOf(text) })
    } else if (text !== null && isStickyClassList(text)) {
      out.sticky.push({ text, rank: rankOf(text) })
    } else if (
      ts.isPropertyAssignment(node) &&
      (ts.isIdentifier(node.name) || ts.isStringLiteral(node.name)) &&
      node.name.text === 'position' &&
      ts.isStringLiteralLike(node.initializer) &&
      node.initializer.text === 'fixed'
    ) {
      out.inlineFixed += 1
      return // the 'fixed' value is a style keyword, not a class list
    } else if (
      ts.isImportDeclaration(node) &&
      ts.isStringLiteral(node.moduleSpecifier) &&
      node.moduleSpecifier.text === CONSENT_LAYER_MODULE &&
      node.importClause?.namedBindings &&
      ts.isNamedImports(node.importClause.namedBindings)
    ) {
      for (const el of node.importClause.namedBindings.elements) out.consentImports.add((el.propertyName ?? el.name).text)
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
      const result = scanSource(fs.readFileSync(file, 'utf8'), file)
      if (result.fixed.length || result.sticky.length || result.inlineFixed || result.consentImports.size) {
        found.set(path.relative(ROOT, file).split(path.sep).join('/'), result)
      }
    }
  }
  scanned = found
  return found
}

/** Numeric ranks above auto, counted per value — what the pins describe. */
const rankedCounts = (sites: FixedSite[]) => {
  const counts: Record<string, number> = {}
  for (const site of sites) {
    if (site.rank === 'transient' || site.rank === 0) continue
    counts[String(site.rank)] = (counts[String(site.rank)] ?? 0) + 1
  }
  return counts
}

describe('no fixed bottom chrome outranks the workspace layers at the launcher corner', () => {
  it('the detector reads fixed class lists, their rank, inline fixed styles and the consent imports', () => {
    expect(rankOf('fixed bottom-0 z-50 bg-panel-light')).toBe(50)
    expect(rankOf('fixed bottom-0 z-consent')).toBe(CONSENT_Z)
    expect(rankOf('lg:hidden fixed inset-0 z-30 bg-overlay')).toBe(30)
    expect(rankOf('fixed inset-x-0 bottom-0 z-40 lg:static lg:z-auto')).toBe(40) // the unprefixed token wins
    expect(rankOf('sr-only focus:not-sr-only focus:fixed focus:z-toast')).toBe('transient')
    expect(rankOf('fixed inset-0 z-modal')).toBe('transient')
    expect(rankOf('fixed inset-0 z-overlay')).toBe('transient')
    expect(rankOf('fixed rounded-lg shadow-e4')).toBe(0)
    expect(rankOf('fixed z-auto')).toBe(0)
    expect(() => rankOf('fixed z-[55]')).toThrow(/ladder token/)
    expect(isFixedClassList('focus:fixed')).toBe(true)
    expect(isFixedClassList('fixed-width')).toBe(false)
    expect(isFixedClassList('fixedness')).toBe(false)

    const kinds = (code: string) => {
      const r = scanSource(code, 'fixture.tsx')
      return { fixed: r.fixed.map((s) => s.rank), sticky: r.sticky.map((s) => s.rank), inline: r.inlineFixed, imports: [...r.consentImports] }
    }
    const none = { fixed: [], sticky: [], inline: 0, imports: [] }
    expect(kinds('const a = <div className="fixed bottom-0 z-50" />')).toEqual({ ...none, fixed: [50] })
    expect(kinds('const a = `fixed ${pos} z-40`')).toEqual({ ...none, fixed: [40] })
    expect(kinds("const a = `${open ? 'fixed z-50' : ''} w-full`")).toEqual({ ...none, fixed: [50] })
    expect(kinds('const a = `${SHELL} ${open ? "lg:border-l" : "hidden"}`')).toEqual(none)
    expect(kinds("const s = { position: 'fixed', top: 1 }")).toEqual({ ...none, inline: 1 })
    expect(kinds("const s = { 'position': 'fixed' }")).toEqual({ ...none, inline: 1 })
    expect(kinds('const n = <nav className="sticky top-16 z-sticky -mx-4" />')).toEqual({ ...none, sticky: [30] })
    expect(kinds('const n = <header className="sticky top-0 z-40" />')).toEqual({ ...none, sticky: [40] })
    expect(kinds('const c = "relative min-w-0 lg:sticky lg:top-16"')).toEqual({ ...none, sticky: [0] })
    expect(kinds("import { BOTTOM_CHROME_OFFSET as o, CONSENT_INSET } from '@/lib/consentLayer'")).toEqual({
      ...none,
      imports: ['BOTTOM_CHROME_OFFSET', 'CONSENT_INSET'],
    })
    // comments never count; prose with the word is harmless (rank 0 is not counted)
    expect(kinds('// fixed bottom-0 z-50\n/* position: "fixed" */ const a = 1')).toEqual(none)
    expect(rankedCounts(scanSource('const t = "a fixed income table"', 'f.ts').fixed)).toEqual({})
    expect(rankedCounts([{ text: '', rank: 40 }, { text: '', rank: 40 }, { text: '', rank: 30 }, { text: '', rank: 'transient' }])).toEqual({
      '40': 2,
      '30': 1,
    })
  })

  it('every fixed site that is not pinned ranks at or below z-consent (transient layers exempt)', () => {
    const offenders = [...scan()]
      .filter(([file]) => !(file in PINNED))
      .flatMap(([file, { fixed }]) =>
        fixed
          .filter((site) => site.rank !== 'transient' && site.rank > CONSENT_Z)
          .map((site) => `${file}: fixed chrome at z-${site.rank} (max z-consent = ${CONSENT_Z}) — "${site.text.slice(0, 60)}"`),
      )
    expect(
      offenders,
      'Fixed chrome above z-consent covers the workspace launcher / sheets / coachmark at the launcher corner. ' +
        'Put it on z-consent and take the --consent-inset (lib/consentLayer), ride a transient layer ' +
        '(z-overlay / z-modal / z-toast) for a popover or dialog, or, for a new workspace layer, pin it here with its reason.',
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
      'Sticky chrome at or above z-consent paints over the consent bar wherever it passes through the bar\'s region ' +
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
      for (const site of scan().get(file)?.fixed ?? []) {
        if (site.rank !== 40) continue
        const tokens = classTokens(site.text).filter((token) => !token.includes(':'))
        const bottom = tokens.filter((token) => /^bottom-/.test(token))
        const vhCaps = tokens.filter((token) => /^max-h-\[.*vh/.test(token))
        for (const token of bottom) if (!token.includes(INSET_VAR)) problems.push(`${file}: "${token}" ignores ${INSET_VAR}`)
        for (const token of vhCaps) if (!token.includes(INSET_VAR)) problems.push(`${file}: "${token}" can exceed the viewport over the bar`)
        if (bottom.length === 0 && site.text.includes('inset-x-0')) problems.push(`${file}: a sheet without a bottom-[…] anchor`)
      }
    }
    for (const file of OFFSET_IMPORTERS) {
      if (!scan().get(file)?.consentImports.has('BOTTOM_CHROME_OFFSET')) {
        problems.push(`${file}: inline-positioned launcher must import BOTTOM_CHROME_OFFSET from ${CONSENT_LAYER_MODULE}`)
      }
    }
    const bar = scan().get(CONSENT_BAR)
    if (bar?.fixed.map((s) => s.rank).join() !== String(CONSENT_Z)) {
      problems.push(`${CONSENT_BAR}: expected exactly one fixed site on z-consent, found ${JSON.stringify(bar?.fixed.map((s) => s.rank) ?? [])}`)
    }
    if (!bar?.consentImports.has('publishConsentLayer')) problems.push(`${CONSENT_BAR}: must publish the consent layer`)
    // The scrollport reserves the inset too: a focus or scrollIntoView must never land behind the bar.
    const globalsCss = fs.readFileSync(path.join(ROOT, 'app/globals.css'), 'utf8')
    if (!/scroll-padding-bottom:\s*var\(--consent-inset,\s*0px\)/.test(globalsCss)) {
      problems.push(`app/globals.css: html must set scroll-padding-bottom: var(${INSET_VAR}, 0px)`)
    }
    expect(
      problems,
      'A lower z alone is not enough: the launcher would cover a consent choice. The sheets anchor on ' +
        `bottom-[var(${INSET_VAR},0px)] and subtract it from their vh cap; inline-positioned launchers use BOTTOM_CHROME_OFFSET.`,
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

  it('the pin lists are shrink-only', () => {
    expect(Object.keys(PINNED).length, 'ride an existing layer instead of pinning a new file').toBeLessThanOrEqual(MAX_PINNED_FILES)
  })
})
