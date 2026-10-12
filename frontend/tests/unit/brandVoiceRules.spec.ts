import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * The voice rules of docs/brand/07-voice.md as one gate (CLAUDE.md rule 12; docs/brand/decisions-log.md
 * D-031). Until this spec they were prose, and the 2026-10 audit found each of them broken somewhere.
 * It reads the TypeScript AST of every shipped module under app, components, features, hooks and lib:
 *
 *  - sentenceCase: headings (h1 to h3), the title of a GuidanceCard, Notice or Modal, a button's
 *    label (<Button> or <button>) and a page's metadata title are in sentence case: after the first
 *    word of a phrase, a capitalised word must be a proper noun (PROPER_NOUNS). The check is a
 *    heuristic, so a false positive goes to the residue with its reason, never to a weaker regex.
 *  - exclamation: no exclamation mark in copy.
 *  - emoji: no emoji in copy: a character that presents as an emoji by default, or any pictograph
 *    forced to one with U+FE0F. Typographic glyphs (the ▲ ▼ direction marks, ↗ for an external link,
 *    © ® ™) are text, not emoji.
 *  - buzzword: none of the banned words (BUZZWORDS).
 *  - headingIcon: no icon element inside a heading (a section heading carries no icon; DESIGN.md).
 *  - developerWording: copy in lib/ and hooks/ (the fallback errors a user reads) never names the
 *    backend, an API path, a "reader" or an HTTP status number.
 *
 * Copy is a JSX text node, or a string or template literal outside the places code keeps its own
 * strings (imports, class lists, comparisons, identifiers such as hrefs and keys; see isCodeString).
 *
 * VOICE_RESIDUE holds what the audit found on the day the gate landed, counted per file and clause.
 * It only shrinks: each surface PR that fixes a file lowers or deletes its line, a new violation fails
 * (an unlisted file, or a listed count that rises), a fixed one fails until its count is lowered, and
 * the list's size is capped at the seed (VOICE_RESIDUE_MAX). A PR that must add an entry says why in
 * its body.
 */

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']

type Clause = 'sentenceCase' | 'exclamation' | 'emoji' | 'buzzword' | 'headingIcon' | 'developerWording'

/** Names that keep their capitals mid-phrase: the product's names, the regulator and its systems, the
    nine parts of the summary outline (backend/app/services/summary_schema.py SECTION_META), months and
    the third parties a page names. Longest first, so a phrase wins over its words. */
const PROPER_NOUNS = [
  'Earnings Quality & Cash Conversion', 'Value Drivers & Capital Allocation', 'Balance Sheet & Liquidity',
  'Results That Matter', 'Multi-Period Analysis', 'Notable Footnotes', 'Forward Signals', 'Ask this Filing',
  'Trace to Source', 'The Print', 'Segments', 'Risks',
  'EarningsNerd', 'Pro', 'SEC', 'EDGAR', 'XBRL', 'U.S.',
  'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December',
  'Jan', 'Feb', 'Mar', 'Apr', 'Jun', 'Jul', 'Aug', 'Sep', 'Sept', 'Oct', 'Nov', 'Dec',
  'Google', 'Apple', 'Stripe', 'GitHub', 'LinkedIn', 'WhatsApp',
].sort((a, b) => b.length - a.length)

const BUZZWORDS: Array<[string, RegExp]> = [
  ['unlock', /\bunlock(?:s|ed|ing)?\b/i],
  ['seamless', /\bseamless(?:ly)?\b/i],
  ['effortless', /\beffortless(?:ly)?\b/i],
  ['empower', /\bempower(?:s|ed|ing|ment)?\b/i],
  ['supercharge', /\bsupercharg(?:e|es|ed|ing)\b/i],
  ['transform', /\btransform(?:s|ed|ing|ative)?\b/i],
  ['actionable', /\bactionable\b/i],
  ['decision-ready', /\bdecision-ready\b/i],
  ['game-changing', /\bgame-chang(?:ing|er)\b/i],
  ['clarity', /\bclarity\b/i],
  ['edge', /\b(?:an?|the|your|our) edge\b/i],
  ['markets move fast', /\bmarkets move fast\b/i],
]

const EMOJI = /\p{Emoji_Presentation}|\p{Extended_Pictographic}\uFE0F/u
const EXCLAMATION = /[\p{L}\p{N})'"’”.]!(?=\s|$|['"’”)])/u
const DEVELOPER_WORDING = /\bbackend\b|\/api\/|\breader\b|\b[45]\d\d\b/i
const HEADINGS = new Set(['h1', 'h2', 'h3'])
const TITLED = new Set(['GuidanceCard', 'Notice', 'Modal', 'ModalHeader'])
const BUTTONS = new Set(['Button', 'button'])
const CONTROLS = new Set(['Button', 'button', 'a', 'Link'])
/** Attributes that hold code, not copy. */
const CODE_ATTRS = /^(?:className|class|href|src|srcSet|id|key|type|role|name|rel|target|variant|size|as|method|action|htmlFor|autoComplete|inputMode|enterKeyHint|lang|viewBox|d|fill|stroke|strokeWidth|strokeLinecap|strokeLinejoin|xmlns|mode|side|align|tone|tabIndex|pattern|form|scope|dateTime|sizes|crossOrigin|referrerPolicy|layout|data-[\w-]+|aria-(?:controls|labelledby|describedby|haspopup|live|current|expanded|hidden|selected|pressed|checked|disabled|modal|orientation|sort|atomic|relevant|busy|invalid|required|owns|activedescendant))$/
/** Calls whose string arguments are class lists or keys. */
const CODE_CALLS = new Set(['cx', 'clsx', 'cn', 'buttonVariants', 'inputClasses', 'require', 'querySelector', 'querySelectorAll', 'getItem', 'setItem', 'removeItem', 'addEventListener', 'removeEventListener', 'getElementById', 'matchMedia', 'startsWith', 'endsWith', 'includes', 'replace', 'split', 'test', 'match', 'capture', 'track', 'identify', 'register', 'useQuery', 'setAttribute', 'getAttribute', 'createElement'])

interface Finding {
  rel: string
  line: number
  clause: Clause
  text: string
}

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name) && !/\.(spec|test)\.tsx?$|\.d\.ts$/.test(entry.name)) out.push(p)
  }
  return out
}

const parse = (source: string, fileName: string) =>
  ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, fileName.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS)

/** A literal's text, a template's `${…}` read as `{x}`. */
function literalText(node: ts.Node): string | null {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text
  if (ts.isJsxText(node)) return node.containsOnlyTriviaWhiteSpaces ? null : node.text
  if (ts.isTemplateExpression(node)) return [node.head.text, ...node.templateSpans.map((span) => `{x}${span.literal.text}`)].join('')
  return null
}

const looksLikeClasses = (text: string) => {
  const tokens = text.trim().split(/\s+/).filter(Boolean)
  return tokens.length > 0 && tokens.every((t) => /^[!a-z0-9:_\-[\]/.%#&>()=,*@~+{}'"]+$/.test(t)) && tokens.some((t) => /[-:[]/.test(t))
}

const callName = (call: ts.CallExpression) =>
  ts.isIdentifier(call.expression) ? call.expression.text : ts.isPropertyAccessExpression(call.expression) ? call.expression.name.text : ''

/** Whether a string literal is code's own string, not copy: an import, a key, a class list, a comparison, a code attribute or argument. */
function isCodeString(node: ts.Node, text: string): boolean {
  if (ts.isJsxText(node)) return false
  if (looksLikeClasses(text) || !/\p{L}/u.test(text)) return true
  // Markup a module builds (an SVG for an export) is code.
  if (/<\/?[a-z][\w-]*[\s>/]/.test(text)) return true
  const parent = node.parent
  if (!parent) return true
  if (ts.isImportDeclaration(parent) || ts.isExportDeclaration(parent) || ts.isExternalModuleReference(parent) || ts.isLiteralTypeNode(parent)) return true
  if ((ts.isPropertyAssignment(parent) || ts.isPropertyDeclaration(parent) || ts.isMethodDeclaration(parent)) && parent.name === node) return true
  if (ts.isElementAccessExpression(parent) || ts.isCaseClause(parent)) return true
  if (ts.isBinaryExpression(parent) && [ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken, ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken, ts.SyntaxKind.InKeyword].includes(parent.operatorToken.kind)) return true
  for (let n: ts.Node | undefined = parent; n; n = n.parent) {
    if (ts.isJsxAttribute(n)) return CODE_ATTRS.test(n.name.getText())
    if (ts.isPropertyAssignment(n) && /^(?:className|classNames|href|key|queryKey|id|type|variant)$/.test(n.name.getText())) return true
    if (ts.isCallExpression(n) && CODE_CALLS.has(callName(n))) return true
    if (ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n) || ts.isBlock(n) || ts.isSourceFile(n)) break
  }
  return false
}

/** Capitalised words after a phrase's first word that are not proper nouns. */
export function titleCaseWords(text: string): string[] {
  let t = ` ${text} `
  for (const noun of PROPER_NOUNS) t = t.split(noun).join(' {n} ')
  const out: string[] = []
  // A phrase starts again after a sentence stop, a separator, a bracket or quote, or an expression
  // (`{x}`: an icon or a value before a label).
  for (const segment of t.split(/[.?!|·:;–—]\s+|\s[-–—]\s|\n|\(|\)|["“”]|\{x\}/)) {
    const words = segment.trim().split(/\s+/).filter(Boolean)
    words.slice(1).forEach((raw) => {
      const word = raw.replace(/^['‘’]+|[,'‘’]+$/g, '')
      if (/^[A-Z][a-z]+(?:['’]s)?$/.test(word)) out.push(word)
    })
  }
  return out
}

/** The text an element renders, its expressions read as `{x}`. */
function elementText(element: ts.JsxElement): string {
  const parts: string[] = []
  const visit = (node: ts.Node) => {
    if (ts.isJsxText(node)) parts.push(node.text)
    else if (ts.isJsxExpression(node)) {
      const e = node.expression
      const text = e ? literalText(e) : null
      parts.push(text ?? '{x}')
      return
    }
    ts.forEachChild(node, visit)
  }
  element.children.forEach(visit)
  return parts.join('').replace(/\s+/g, ' ').trim()
}

const tagOf = (node: ts.JsxOpeningLikeElement) => node.tagName.getText()

/** Every violation in one source. */
export function voiceFindings(source: string, rel: string): Finding[] {
  const sf = parse(source, rel)
  const findings: Finding[] = []
  const add = (node: ts.Node, clause: Clause, text: string) =>
    findings.push({ rel, line: sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1, clause, text: text.replace(/\s+/g, ' ').trim().slice(0, 80) })
  const devScope = rel.startsWith('lib/') || rel.startsWith('hooks/')

  const visit = (node: ts.Node, inMetadata: boolean): void => {
    // Copy: every literal outside code's own strings.
    const text = literalText(node)
    if (text !== null && !isCodeString(node, text)) {
      if (EXCLAMATION.test(text)) add(node, 'exclamation', text)
      if (EMOJI.test(text)) add(node, 'emoji', text)
      for (const [word, re] of BUZZWORDS) if (re.test(text)) add(node, 'buzzword', `${word}: ${text}`)
      if (devScope && /\s/.test(text.trim()) && DEVELOPER_WORDING.test(text)) add(node, 'developerWording', text)
    }
    // Headings, buttons: their rendered text; headings: no icon inside.
    if (ts.isJsxElement(node)) {
      const tag = tagOf(node.openingElement)
      if (HEADINGS.has(tag) || BUTTONS.has(tag)) {
        const rendered = elementText(node)
        if (titleCaseWords(rendered).length) add(node, 'sentenceCase', rendered)
      }
      if (HEADINGS.has(tag)) {
        const icons: ts.Node[] = []
        // An icon inside a control the heading wraps (a disclosure button's caret) is the control's
        // affordance, not the heading's icon.
        const find = (n: ts.Node) => {
          if (ts.isJsxElement(n) && CONTROLS.has(tagOf(n.openingElement))) return
          if ((ts.isJsxSelfClosingElement(n) || ts.isJsxOpeningElement(n)) && /Icon$/.test(tagOf(n))) icons.push(n)
          ts.forEachChild(n, find)
        }
        node.children.forEach(find)
        for (const icon of icons) add(icon, 'headingIcon', `<${tagOf(icon as ts.JsxOpeningLikeElement)}> in <${tag}>`)
      }
    }
    // A GuidanceCard, Notice or Modal title.
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && TITLED.has(tagOf(node))) {
      const title = node.attributes.properties.find((p): p is ts.JsxAttribute => ts.isJsxAttribute(p) && p.name.getText() === 'title')
      const init = title?.initializer
      const expr = init && ts.isJsxExpression(init) ? init.expression : init
      const value = expr ? literalText(expr) : null
      if (value !== null && titleCaseWords(value).length) add(expr!, 'sentenceCase', value)
    }
    // A page's metadata title (`export const metadata`, generateMetadata), its default and template included.
    if (inMetadata && ts.isPropertyAssignment(node) && /^(?:title|default|template)$/.test(node.name.getText())) {
      const value = literalText(node.initializer)
      if (value !== null && titleCaseWords(value).length) add(node.initializer, 'sentenceCase', value)
    }
    const metadataScope =
      inMetadata ||
      (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.name.text === 'metadata') ||
      (ts.isFunctionDeclaration(node) && node.name?.text === 'generateMetadata')
    ts.forEachChild(node, (child) => visit(child, metadataScope))
  }
  visit(sf, false)
  return findings
}

const FILES = SCAN_DIRS.flatMap((dir) => walk(path.join(ROOT, dir)))
const rel = (file: string) => path.relative(ROOT, file).split(path.sep).join('/')

/**
 * The violations found on 2026-10-12, per file and clause. Each line names the sweep PR that owns the
 * file, or why the text stays.
 */
const VOICE_RESIDUE: Record<string, Partial<Record<Clause, number>>> = {
  'app/admin/feedback/page.tsx': { sentenceCase: 1 }, // brand-admin
  'app/admin/invites/page.tsx': { sentenceCase: 1 }, // brand-admin
  'app/contact/page.tsx': { sentenceCase: 3 }, // brand-contact-security-presentation
  'app/dashboard/error.tsx': { sentenceCase: 4 }, // brand-dashboard-watchlist (DSW-12)
  'app/dashboard/settings/page.tsx': { sentenceCase: 1 }, // brand-settings-subscriptions
  'app/error.tsx': { sentenceCase: 1 }, // brand-chrome-primitives (the development-only details panel)
  'app/filing/[id]/page.tsx': { sentenceCase: 2 }, // brand-metadata-social (meta titles)
  'app/privacy/page.tsx': { sentenceCase: 16 }, // legal page: its headings wait on the founder (legalDates bump)
  'app/search/page.tsx': { sentenceCase: 1 }, // brand-metadata-social (meta title)
  'app/security/page.tsx': { sentenceCase: 11 }, // founder-gated: the /security recase lands with its claims (UA ids)
  'app/terms/page.tsx': { sentenceCase: 4 }, // legal page: its headings wait on the founder (legalDates bump)
  'app/waitlist/page.tsx': { buzzword: 1 }, // brand-public-pages (BG-23, "clarity")
  'components/CookieConsent.tsx': { sentenceCase: 6 }, // brand-chrome-primitives
  'features/analysis/components/MetricsTable.tsx': { sentenceCase: 1 }, // brand-analysis
  'features/contact/components/ContactForm.tsx': { sentenceCase: 1 }, // brand-contact-security-presentation
  'features/feedback/components/FeedbackWidget.tsx': { emoji: 3 }, // brand-chrome-primitives
  'features/fundamentals/components/FundamentalsTrendChart.tsx': { sentenceCase: 1 }, // brand-company-page
  'features/insiders/components/InsiderActivityPanel.tsx': { sentenceCase: 2 }, // brand-company-page
  'features/peers/components/PeerComparisonPanel.tsx': { sentenceCase: 1 }, // brand-company-page
  'features/settings/components/NotificationPreferencesForm.tsx': { sentenceCase: 1, headingIcon: 1 }, // brand-settings-subscriptions (DSW-13)
  'features/subscriptions/components/PeekLocked.tsx': { buzzword: 1 }, // brand-settings-subscriptions (DSW-11, "unlock")
  'features/summaries/components/SummaryActionsBar.tsx': { sentenceCase: 1 }, // brand-filing-page
  'lib/api/client.ts': { developerWording: 1 }, // brand-chrome-primitives (CAL-12, "backend API")
}
const VOICE_RESIDUE_MAX = { entries: 24, violations: 66 }

describe('brand voice rules (docs/brand/07-voice.md)', () => {
  const findings = FILES.flatMap((file) => voiceFindings(readFileSync(file, 'utf8'), rel(file)))

  it('reads the app (a scan that finds no copy must not pass)', () => {
    expect(FILES.length).toBeGreaterThan(300)
    expect(FILES.map(rel)).toEqual(expect.arrayContaining(['app/page.tsx', 'lib/api/client.ts', 'hooks/useCountUp.ts']))
  })

  it('every violation is in the residue, and every residue count is current', () => {
    const counts = new Map<string, Finding[]>()
    for (const f of findings) {
      const key = `${f.rel} ${f.clause}`
      counts.set(key, [...(counts.get(key) ?? []), f])
    }
    const problems: string[] = []
    for (const [key, list] of counts) {
      const [file, clause] = key.split(' ') as [string, Clause]
      const allowed = VOICE_RESIDUE[file]?.[clause] ?? 0
      const lines = list.map((f) => `${f.rel}:${f.line} [${f.clause}] ${JSON.stringify(f.text)}`)
      if (list.length > allowed) problems.push(`${key}: ${list.length} found, ${allowed} in VOICE_RESIDUE\n  ${lines.join('\n  ')}`)
      else if (list.length < allowed) problems.push(`${key}: ${list.length} found, ${allowed} in VOICE_RESIDUE: lower the count`)
    }
    for (const [file, clauses] of Object.entries(VOICE_RESIDUE)) {
      for (const clause of Object.keys(clauses) as Clause[]) {
        if (!counts.has(`${file} ${clause}`)) problems.push(`${file} ${clause}: none left, delete it from VOICE_RESIDUE`)
      }
    }
    expect(problems, 'fix the copy (docs/brand/07-voice.md); the residue only shrinks').toEqual([])
  })

  it('the residue only shrinks', () => {
    const entries = Object.values(VOICE_RESIDUE).flatMap((clauses) => Object.values(clauses))
    expect(entries.length, 'VOICE_RESIDUE gained an entry').toBeLessThanOrEqual(VOICE_RESIDUE_MAX.entries)
    expect(entries.reduce((sum, n) => sum + (n ?? 0), 0), 'VOICE_RESIDUE gained a violation').toBeLessThanOrEqual(VOICE_RESIDUE_MAX.violations)
  })

  it('the scan catches what it is for (a self-check on a fixed source)', () => {
    const src = [
      "import { BellIcon } from '@/lib/icons'",
      "export const metadata = { title: 'Filing Alerts | EarningsNerd' }",
      'export function Probe() {',
      '  return (',
      '    <div className="flex items-center">',
      '      <h2><BellIcon />Filing Alerts</h2>',
      '      <Button>Go to Login</Button>',
      '      <GuidanceCard title="Authentication Required" />',
      "      <p>{'Great news!'}</p>",
      '      <span>Upgrade to unlock ✨</span>',
      '      <h3>Results That Matter</h3>',
      '      <h3>Ask this Filing about Apple’s 10-K for Q3 · SEC EDGAR</h3>',
      '      <Button>Wow!</Button>',
      "      <a className=\"md:!block focus-visible:outline-none\" href=\"/pricing\">See Pro plans</a>",
      '    </div>',
      '  )',
      '}',
    ].join('\n')
    expect(voiceFindings(src, 'features/probe/Probe.tsx').map((f) => `${f.line} ${f.clause}`)).toEqual([
      '2 sentenceCase',
      '6 sentenceCase',
      '6 headingIcon',
      '7 sentenceCase',
      '8 sentenceCase',
      '9 exclamation',
      '10 emoji',
      '10 buzzword',
      '13 exclamation',
    ])
    expect(voiceFindings("export const msg = 'The backend returned 503. Try again.'", 'lib/api/probe.ts').map((f) => f.clause)).toEqual(['developerWording'])
    expect(voiceFindings("export const msg = 'The backend returned 503. Try again.'", 'features/probe/msg.ts')).toEqual([])
  })
})
