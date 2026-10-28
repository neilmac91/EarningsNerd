import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Status colour is for status (lessons/frontend-status-colors-for-status-only.md; DESIGN_SYSTEM.md §4 › Inline
 * notice, §12): the info, success, warning and error tints paint a state (a result, an error, a limit, a mode of the
 * account) and nothing else, and the primitives under components/ui (Notice, Badge, GuidanceCard, Input's error
 * tone) own them. A hand-rolled tint outside that folder is residue, and a Notice says which state it is at every
 * call site: Notice.variant has had no default since 2026-10-24, when the generating card's whimsy line was found
 * sitting in the blue `info` Notice it had kept for three months. Two gates, one file:
 *
 *  1. STATUS TINT CENSUS. Every .ts/.tsx source under app, components, features, hooks and lib except components/ui
 *     is read through the TypeScript AST (a .css file is not read: app/globals.css holds no status tint and @apply is
 *     not a class string), and every status-TINT class token (a ground, a border or a side border, a ring or a ring
 *     offset, a gradient stop, a divide, an outline or a shadow: `bg|border(-[trblxyse])?|ring(-offset)?|from|to|via|
 *     divide|outline|shadow` - `info|success|warning|error` - `light|dark|text|emphasis`) in a string literal or a
 *     template chunk counts, each match once, so a light/dark pair is two. A comment is not read. Status INK is not a tint and is not counted: a
 *     sentence in `text-error-light`, a glyph in `fill-success-light`, a stroke, are the status colour on a state the
 *     system sanctions (§9), and a token inside another (`shadow-ring-error-dark`, the focus ring the primitives own)
 *     is not read. The gain/loss tones (lib/financialTone.ts) and the brand's tints are not status. RESIDUE lists what
 *     the census found on 2026-10-24, per file at its count, with the surface and the open item that retires it
 *     (tasks/todo.md E196: its clause (2) the guidance and warning containers, (3) and (4) the error and other clones of
 *     Notice and Badge; its clause (1), the pricing usage box, took the shared UsageMeter on 2026-10-27, and the
 *     dashboard's meter with it); a line under "a status tint on a state, no item" is held at its count until a
 *     primitive takes the surface. Shrink-only: a fixed surface fails until its count is lowered, a new tint fails,
 *     and the totals equal RESIDUE_MAX, lowered in the same commit as each shrink
 *     (lessons/test-allowlist-caps-are-equalities.md).
 *
 *  2. NOTICE VARIANT WRITTEN. Every `<Notice …>` under app, components and features, read under its name, a
 *     named-import alias (`Notice as Banner`), a namespace import (`UI.Notice`) and a same-file const alias
 *     (`const N = Notice`), carries a variant written as a string literal: `variant="info"`, `variant={'info'}`, or a
 *     spread object literal with a string-literal variant (`{...{ variant: 'info' }}`). Where one element writes it
 *     twice the last wins, as React reads it. A variant given as anything else (a variable, a call, a shorthand
 *     property, a bare `variant`), a missing variant, and a spread of anything but an object literal (`{...props}`,
 *     at the element or inside the literal) fail: a variable spread is unknowable, so it fails rather than being
 *     skipped, even beside a written variant. tsc requires the prop; this catches the spread and dynamic forms it
 *     cannot. Not read: a Notice reached through another module's re-export.
 */

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const TINT_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
/** The primitives own the tints: the census leaves this folder alone. */
const PRIMITIVES = 'components/ui/'
const NOTICE_DIRS = ['app', 'components', 'features']
const COMPONENT = 'Notice'
const STATUS_TINT = /(?<![\w-])(?:bg|border(?:-[trblxyse])?|ring(?:-offset)?|from|to|via|divide|outline|shadow)-(?:info|success|warning|error)-(?:light|dark|text|emphasis)\b/g

const RESIDUE: Record<string, number> = {
  // E196 (2): hand-rolled warning containers, which wait on a `warning` Notice variant.
  'app/dashboard/page.tsx': 6, // the usage banner's warning tint; also the delete button's hover tint (the meter is UsageMeter's)
  'components/Header.tsx': 4, // the phone menu's verify-email row
  'features/admin/components/ShareInvite.tsx': 4, // the invite-sharing warning well
  'features/auth/components/UserMenu.tsx': 6, // the unverified dot and the verify-email row
  'features/auth/components/VerificationBanner.tsx': 6, // the banner's warning ground and hover
  // E196 (3) and (4): clones of Notice, GuidanceCard or Badge that take the primitive.
  'features/search/components/FullTextSearch.tsx': 4, // an error Notice clone (2026-10-18)
  'features/filings/components/copilot/CopilotMessage.tsx': 4, // the error bubble, Notice's error recipe verbatim
  'features/calendar/components/DayDetailDialog.tsx': 4, // the "Market closed" info Notice clone
  'features/companies/components/CompanySearch.tsx': 3, // the error dropdown's light and dark hairline and its dark ground
  'features/calendar/components/AlertBell.tsx': 4, // the error icon well, GuidanceCard's recipe
  'features/admin/components/BulkResultSummary.tsx': 2, // the error rows' tint
  'features/summaries/components/SummaryActionsBar.tsx': 2, // the hand-rolled success chip (Badge has `success`)
  // A status tint on a genuine state, no open item: held at its count until a primitive takes the surface.
  'app/delete-account/page.tsx': 2, // the deletion card's error ring
  'app/global-error.tsx': 2, // the error boundary's stack well
  'features/admin/components/EmailChipsInput.tsx': 4, // an invalid address chip
  'features/admin/components/InviteRow.tsx': 2, // the revoke button's hover tint
  'features/auth/components/PasswordField.tsx': 10, // the strength meter's five rungs
  'features/contact/components/ContactForm.tsx': 2, // the sent confirmation's icon well
  'features/dashboard/components/YourCompanies.tsx': 2, // the remove button's hover tint
  'features/filings/components/copilot/FilingViewer.tsx': 4, // the viewer's warning strip
}
/** Equal to the table, never above it: lower both with the table in the same commit. */
const RESIDUE_MAX = { files: 20, uses: 77 }

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

const rel = (file: string) => path.relative(ROOT, file).split(path.sep).join('/')

const parse = (source: string, fileName: string) =>
  ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, fileName.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)

/** A string literal, a template with no substitution, or one chunk of a template around its substitutions. */
const isStringChunk = (node: ts.Node): node is ts.StringLiteralLike | ts.TemplateLiteralLikeNode =>
  ts.isStringLiteralLike(node) || ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)

/** The status-tint class tokens in one source: every match in every string literal and template chunk. */
export function statusTintUses(source: string, fileName: string): number {
  let uses = 0
  const visit = (node: ts.Node): void => {
    if (isStringChunk(node)) uses += node.text.match(STATUS_TINT)?.length ?? 0
    ts.forEachChild(node, visit)
  }
  visit(parse(source, fileName))
  return uses
}

/** The names a source renders the component under: its own, a named-import alias, a namespace import's member and
    a same-file const alias of any of those, followed until no new alias appears (noticeTitlesAreOnePhrase.spec.ts). */
function componentNames(sf: ts.SourceFile): Set<string> {
  const names = new Set([COMPONENT])
  for (const statement of sf.statements) {
    const bindings = ts.isImportDeclaration(statement) ? statement.importClause?.namedBindings : undefined
    if (bindings && ts.isNamedImports(bindings)) {
      for (const element of bindings.elements) if ((element.propertyName ?? element.name).text === COMPONENT) names.add(element.name.text)
    }
    if (bindings && ts.isNamespaceImport(bindings)) names.add(`${bindings.name.text}.${COMPONENT}`)
  }
  const aliases: Array<[string, string]> = []
  const collect = (node: ts.Node): void => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer && (ts.isIdentifier(node.initializer) || ts.isPropertyAccessExpression(node.initializer))) {
      aliases.push([node.name.text, node.initializer.getText(sf)])
    }
    ts.forEachChild(node, collect)
  }
  collect(sf)
  for (let grew = true; grew; ) {
    grew = false
    for (const [alias, target] of aliases) {
      if (names.has(target) && !names.has(alias)) {
        names.add(alias)
        grew = true
      }
    }
  }
  return names
}

/** Every `<Notice>` in one source (`notices`), and each whose variant is not written as a string literal, as
    `file:line <Tag> why` (`unwritten`). */
export function noticeVariants(source: string, fileName: string): { notices: number; info: number; unwritten: string[] } {
  const sf = parse(source, fileName)
  const names = componentNames(sf)
  const written = (e: ts.Expression | undefined) => e !== undefined && ts.isStringLiteralLike(e)
  const literal = (e: ts.Expression | undefined) => (e !== undefined && ts.isStringLiteralLike(e) ? e.text : undefined)
  const key = (name: ts.PropertyName) => name.getText(sf).replace(/['"]/g, '')
  let notices = 0
  let info = 0
  const unwritten: string[] = []
  const visit = (node: ts.Node): void => {
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && names.has(node.tagName.getText(sf))) {
      notices += 1
      // The variant the element ends with, in source order (the last write wins), or undefined with none; a spread of
      // anything but an object literal makes every prop unknowable.
      let variant: boolean | undefined
      let value: string | undefined
      let unknowable = false
      for (const attribute of node.attributes.properties) {
        if (ts.isJsxAttribute(attribute)) {
          if (attribute.name.getText(sf) !== 'variant') continue
          const init = attribute.initializer
          variant = init !== undefined && (ts.isStringLiteral(init) || (ts.isJsxExpression(init) && written(init.expression)))
          value = init === undefined ? undefined : ts.isStringLiteral(init) ? init.text : ts.isJsxExpression(init) ? literal(init.expression) : undefined
        } else if (ts.isObjectLiteralExpression(attribute.expression)) {
          for (const property of attribute.expression.properties) {
            if (ts.isSpreadAssignment(property)) unknowable = true
            else if (ts.isPropertyAssignment(property) && key(property.name) === 'variant') {
              variant = written(property.initializer)
              value = literal(property.initializer)
            } else if (ts.isShorthandPropertyAssignment(property) && property.name.text === 'variant') {
              variant = false
              value = undefined
            }
          }
        } else unknowable = true
      }
      const why = unknowable ? 'spreads a variable: its props are unknowable' : variant === undefined ? 'has no variant' : variant ? null : 'variant is not a string literal'
      if (why) unwritten.push(`${fileName}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1} <${node.tagName.getText(sf)}> ${why}`)
      else if (value === 'info') info += 1
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return { notices, info, unwritten }
}

/** The `info` Notices on 2026-10-24, per file at their count: each a state (a result, a limit, a mode) or an item
    that retires it. A new info Notice is added here on purpose, reviewed for state against activity (DESIGN_SYSTEM.md
    §4 › Inline notice: a run in progress is never a Notice), and the table only shrinks. */
const INFO_NOTICES: Record<string, number> = {
  'app/dashboard/page.tsx': 1, // "Checkout finished": a result
  'app/pricing/page.tsx': 2, // "You returned from checkout": a result; "New subscriptions are currently unavailable": a mode
  'features/legal/components/CollectionGate.tsx': 1, // collection unavailable: a mode
  'features/analysis/components/NarrativePane.tsx': 2, // source references that need attention, not enough history: results
  'features/analysis/components/AnalysisPageClient.tsx': 4, // an unsupported filer (a state); the signed-out guidance, the Pro upsell and the history fetch (activity) wait on E196 (2)
  'features/auth/components/RegisterForm.tsx': 1, // the private-beta guidance waits on E196 (2)
}
const INFO_NOTICES_MAX = { files: 6, uses: 11 }

describe('status tints are a census (DESIGN_SYSTEM.md §4 › Inline notice, §12)', () => {
  const uses = new Map<string, number>()
  for (const file of TINT_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))) {
    const r = rel(file)
    if (r.startsWith(PRIMITIVES)) continue
    const n = statusTintUses(readFileSync(file, 'utf8'), r)
    if (n > 0) uses.set(r, n)
  }

  it('every status tint outside components/ui is listed residue, at its current count', () => {
    const problems: string[] = []
    for (const file of [...new Set([...uses.keys(), ...Object.keys(RESIDUE)])].sort()) {
      const actual = uses.get(file) ?? 0
      const listed = RESIDUE[file] ?? 0
      if (actual === 0) problems.push(`${file}: no status tint left: delete its RESIDUE line and lower RESIDUE_MAX.files and .uses`)
      else if (actual > listed) problems.push(`${file}: ${actual} status tint classes, ${listed} listed`)
      else if (actual < listed) problems.push(`${file}: ${actual} status tint classes, ${listed} listed: lower its RESIDUE count and RESIDUE_MAX.uses (stale)`)
    }
    expect(
      problems,
      'A status tint belongs to a primitive: <Notice variant="…"> for a state in a card or a form, <Badge> for a chip, GuidanceCard for an empty state. A hand-rolled one is added to RESIDUE on purpose, under the item that retires it, or not at all.',
    ).toEqual([])
  })

  it('the residue only shrinks', () => {
    // Equality, not a ceiling: a PR that shrinks the table lowers the cap in the same commit.
    expect(Object.keys(RESIDUE).length, 'RESIDUE changed its files: move RESIDUE_MAX.files with it in the same commit').toBe(RESIDUE_MAX.files)
    expect(Object.values(RESIDUE).reduce((sum, n) => sum + n, 0), 'RESIDUE changed its uses: move RESIDUE_MAX.uses with it in the same commit').toBe(RESIDUE_MAX.uses)
  })

  it('leaves the primitives alone because they are excluded, not because the reader misses them', () => {
    // Notice and Badge carry the tints the census is for: the reader counts them there, and the census skips the folder.
    for (const primitive of ['Notice.tsx', 'Badge.tsx']) {
      expect(statusTintUses(readFileSync(path.join(ROOT, PRIMITIVES, primitive), 'utf8'), `${PRIMITIVES}${primitive}`), primitive).toBeGreaterThan(0)
    }
    expect([...uses.keys()].filter((file) => file.startsWith(PRIMITIVES))).toEqual([])
  })
})

describe('every Notice writes its variant', () => {
  it('no <Notice> under app, components or features takes its variant from anything but a string literal', () => {
    const read: string[] = []
    const unwritten: string[] = []
    for (const file of NOTICE_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))) {
      const r = rel(file)
      const found = noticeVariants(readFileSync(file, 'utf8'), r)
      if (found.notices > 0) read.push(r)
      unwritten.push(...found.unwritten)
    }
    expect(unwritten, 'write variant="error|info|success" at the call site: a Notice says which state it is (DESIGN_SYSTEM.md §4 › Inline notice)').toEqual([])
    // Not vacuous: the Notices E196 (2) names and one imported by its own path (components/ui/Notice) are read.
    expect(read).toEqual(
      expect.arrayContaining(['features/auth/components/RegisterForm.tsx', 'features/analysis/components/AnalysisPageClient.tsx', 'features/settings/components/BillingPanel.tsx']),
    )
  })

  it('every info Notice is listed, at its count: a new one is a deliberate addition, reviewed for state against activity', () => {
    const found = new Map<string, number>()
    for (const file of NOTICE_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))) {
      const r = rel(file)
      const n = noticeVariants(readFileSync(file, 'utf8'), r).info
      if (n > 0) found.set(r, n)
    }
    const problems: string[] = []
    for (const file of [...new Set([...found.keys(), ...Object.keys(INFO_NOTICES)])].sort()) {
      const actual = found.get(file) ?? 0
      const listed = INFO_NOTICES[file] ?? 0
      if (actual === 0) problems.push(`${file}: no info Notice left: delete its INFO_NOTICES line and lower INFO_NOTICES_MAX`)
      else if (actual > listed) problems.push(`${file}: ${actual} info Notices, ${listed} listed`)
      else if (actual < listed) problems.push(`${file}: ${actual} info Notices, ${listed} listed: lower its count and INFO_NOTICES_MAX.uses (stale)`)
    }
    expect(
      problems,
      'An info Notice is an advisory state (a result, a limit, a mode of the account), never activity: a run in progress is the progress indicator with its words in the ink (DESIGN_SYSTEM.md §4 › Inline notice). Add a genuine state to INFO_NOTICES on purpose, with its reason, and move INFO_NOTICES_MAX with it.',
    ).toEqual([])
    // Equality, not a ceiling (lessons/test-allowlist-caps-are-equalities.md).
    expect(Object.keys(INFO_NOTICES).length, 'INFO_NOTICES changed its files: move INFO_NOTICES_MAX.files with it in the same commit').toBe(INFO_NOTICES_MAX.files)
    expect(Object.values(INFO_NOTICES).reduce((sum, n) => sum + n, 0), 'INFO_NOTICES changed its uses: move INFO_NOTICES_MAX.uses with it in the same commit').toBe(INFO_NOTICES_MAX.uses)
  })
})

describe('the scans catch what they are for (a self-check on fixed sources)', () => {
  it('counts a tint in a string, a JSX attribute, a template chunk and a conditional arm, and nothing else', () => {
    const tinted = [
      '// bg-error-light in a comment is no use',
      // Three: a tint's background, border and dark background in one class string.
      "const a = 'bg-info-light/10 border-info-light/40 dark:bg-info-dark/15'",
      // Two: a light/dark pair of borders in a JSX attribute.
      'const b = <p className="rounded border border-warning-light/30 dark:border-warning-dark/30">x</p>',
      // Three: each arm of a conditional inside a template, and the chunk after it.
      'const c = `h-2 ${ok ? "bg-success-light" : "bg-error-light"} dark:bg-success-dark`',
      // Two: a tint under a variant, and the destructive hover's emphasis shade.
      "const d = 'hover:bg-info-light/10 hover:bg-error-emphasis'",
      // None: the focus ring token holds a status token inside another word (the ring the primitives own).
      "const e = 'focus-visible:shadow-ring-error dark:focus-visible:shadow-ring-error-dark'",
      // None: the gain/loss tones, the brand's tints, a shade with no status, and a word that only contains a token.
      "const f = 'bg-gain-soft border-loss-light bg-brand-weak text-text-secondary-light bg-info-lighter'",
      // None: status INK on a sentence or a glyph is the status colour on a state, not a tint.
      "const g = 'text-error-light dark:text-error-dark fill-success-light stroke-warning-dark text-info-text'",
      // Two: a side border (the side-tab stripe's form) and a ring offset are tints too.
      "const h = 'border-l-4 border-l-warning-light ring-offset-error-dark'",
    ].join('\n')
    expect(statusTintUses(tinted, 'probe.tsx')).toBe(12)
    expect(statusTintUses("export const tone = 'text-gain-text dark:text-gain-dark'", 'lib/probe.ts')).toBe(0)
  })

  it('reads each Notice under every alias and fails the unwritten, the dynamic and the spread forms', () => {
    const fixture = [
      "import { Notice as Banner } from '@/components/ui'; import * as UI from '@/components/ui/Notice'",
      'const N = UI.Notice',
      'const a = <Notice variant="info" title="t" />',
      "const b = <Banner variant={'error'} title=\"t\" />",
      'const c = <UI.Notice variant={`success`} title="t" />',
      "const d = <N {...{ variant: 'info', title: 't' }} />",
      'const e = <Notice title="t" />',
      'const f = <Notice variant={kind} title="t" />',
      'const g = <Notice {...props} />',
      'const h = <Notice variant="info" {...props} />',
      "const i = <Notice {...{ ...rest, variant: 'info' }} />",
      'const j = <Notice {...{ variant }} />',
      'const k = <Notice variant />',
      "const l = <Notice {...{ variant: 'info' }} variant={kind} />",
      'const m = <Badge variant={kind} />',
      "const n = <Notice variant={kind} {...{ variant: 'info' }}>t</Notice>",
    ].join('\n')
    // info: a, d and n (the spread literal's 'info' is n's last write).
    expect(noticeVariants(fixture, 'probe.tsx')).toEqual({
      notices: 13,
      info: 3,
      unwritten: [
        'probe.tsx:7 <Notice> has no variant',
        'probe.tsx:8 <Notice> variant is not a string literal',
        'probe.tsx:9 <Notice> spreads a variable: its props are unknowable',
        'probe.tsx:10 <Notice> spreads a variable: its props are unknowable',
        'probe.tsx:11 <Notice> spreads a variable: its props are unknowable',
        'probe.tsx:12 <Notice> variant is not a string literal',
        'probe.tsx:13 <Notice> variant is not a string literal',
        'probe.tsx:14 <Notice> variant is not a string literal',
      ],
    })
  })
})
