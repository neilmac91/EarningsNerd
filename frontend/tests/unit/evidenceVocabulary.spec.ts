import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * The evidence vocabulary as a gate (D-058, the founder's review of 2026-10-22; docs/voice-and-style.md rule 2 and its
 * vocabulary; CLAUDE.md rule 12). Two rules, read from the source:
 *
 * 1. A retired evidence label never ships: "SEC XBRL", "Verified in filing" and "Source match found" anywhere, and as a
 *    whole label the "Cited", "Located in the filing" and bare "Verified" badges used to read and a bare "SEC EDGAR" (the sign-in page's
 *    trust signal read as if the SEC vouched for the figures; chief design on #1530). The labels the product shows
 *    live in one module, features/filings/lib/evidenceLabels.ts; "located in the filing" stays in prose.
 * 2. A link to the source names SEC.gov, not EDGAR: no link's text (its own and its children's), aria-label or title
 *    names EDGAR. A link is an <a> or <Link>, or any element given an href.
 *
 * Copy is what the TypeScript syntax tree holds as text: string literals, template text and JSX text, and, inside a
 * link, a same-file constant it renders by name. Comments, identifiers and URLs (edgarCompanyUrl, an href) are not
 * copy. An attribution outside a link ("Data sourced from SEC EDGAR" in the footer and AiDisclaimer) is not a label,
 * and the plan's R9 leaves it, as it leaves the legal pages (LEGAL, whose links keep their published words). The scan cannot follow copy another module hands a link (sourceLinkLabel(url) reads
 * evidenceLabels.ts, which rule 1 reads whole); that stays review-checked. The OG card's template is read as text
 * for rule 1. The planted forms below hold the scan's reach: each way to break a rule fails, each look-alike passes.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SCANNED = ['app', 'components', 'features', 'lib']
const LEGAL = ['app/terms/', 'app/privacy/']
const OG_TEMPLATE = 'scripts/brand/og-template.html'

// The server's own reason string, compared to pick the badge's words and never shown (SummaryDisplay reasonWords).
const RETIRED_ALLOWED = new Set(['features/summaries/components/SummaryDisplay.tsx: financial figures not grounded in SEC XBRL data'])

const WHOLE_LABELS = new Set(['Cited', 'Located in the filing', 'Verified'])
const retired = (node: ts.Node, text: string) =>
  /SEC XBRL|Verified in filing|Source match found/.test(text) ||
  WHOLE_LABELS.has(text.trim()) ||
  (ts.isJsxText(node) && text.trim() === 'SEC EDGAR')

const NOT_COPY_ATTRIBUTES = new Set(['href', 'src', 'className', 'rel', 'target', 'id', 'key', 'prefetch'])
const isLinkTag = (tag: string) => tag === 'a' || tag === 'Link'

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(path.join(FRONTEND, dir), { withFileTypes: true })) {
    const rel = `${dir}/${entry.name}`
    if (entry.isDirectory()) sourceFiles(rel, out)
    else if (/\.tsx?$/.test(entry.name) && !entry.name.endsWith('.d.ts')) out.push(rel)
  }
  return out
}

function textOf(node: ts.Node): string | null {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text
  if (ts.isTemplateHead(node) || ts.isTemplateMiddle(node) || ts.isTemplateTail(node)) return node.text
  if (ts.isJsxText(node)) return node.text
  return null
}

function visit(node: ts.Node, fn: (n: ts.Node) => void) {
  fn(node)
  node.forEachChild((child) => visit(child, fn))
}

/** The same file's `const NAME = '…'` (or a template without substitutions), by name. */
function fileConstants(sf: ts.SourceFile): Map<string, string> {
  const out = new Map<string, string>()
  visit(sf, (node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      const text = textOf(node.initializer)
      if (text !== null) out.set(node.name.text, text)
    }
  })
  return out
}

/** Every piece of copy inside a link element: its text, its children's, and its attributes' but for addresses. */
function linkCopy(element: ts.JsxElement | ts.JsxSelfClosingElement, constants: Map<string, string>): string[] {
  const out: string[] = []
  const read = (node: ts.Node) => {
    if (ts.isJsxAttribute(node) && NOT_COPY_ATTRIBUTES.has(node.name.getText())) return
    const text = textOf(node)
    if (text !== null) out.push(text)
    else if (ts.isIdentifier(node) && constants.has(node.text) && !ts.isPropertyAccessExpression(node.parent)) {
      out.push(constants.get(node.text)!)
    }
    node.forEachChild(read)
  }
  read(element)
  return out
}

export interface Breach {
  rule: 'retired label' | 'link names EDGAR'
  at: string
  text: string
}

export function scan(rel: string, source: string): Breach[] {
  const sf = ts.createSourceFile(rel, source, ts.ScriptTarget.Latest, true, rel.endsWith('.ts') ? ts.ScriptKind.TS : ts.ScriptKind.TSX)
  const at = (node: ts.Node) => `${rel}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1}`
  const constants = fileConstants(sf)
  const breaches: Breach[] = []
  visit(sf, (node) => {
    const text = textOf(node)
    if (text !== null && retired(node, text) && !RETIRED_ALLOWED.has(`${rel}: ${text}`) && !LEGAL.some((dir) => rel.startsWith(dir))) {
      breaches.push({ rule: 'retired label', at: at(node), text: text.trim() })
    }
    if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
      const opening = ts.isJsxElement(node) ? node.openingElement : node
      const hasHref = opening.attributes.properties.some((p) => ts.isJsxAttribute(p) && p.name.getText() === 'href')
      if ((isLinkTag(opening.tagName.getText()) || hasHref) && !LEGAL.some((dir) => rel.startsWith(dir))) {
        for (const copy of linkCopy(node, constants)) {
          if (/EDGAR/.test(copy)) breaches.push({ rule: 'link names EDGAR', at: at(node), text: copy.trim() })
        }
      }
    }
  })
  return breaches
}

/** The OG card's visible text: the template with its comments, style and script blocks and tags taken out. */
const visibleHtml = (html: string) =>
  html.replace(/<!--[\s\S]*?-->/g, ' ').replace(/<(style|script)\b[\s\S]*?<\/\1>/gi, ' ').replace(/<[^>]+>/g, ' ')

describe('the evidence vocabulary (D-058)', () => {
  const files = SCANNED.flatMap((dir) => sourceFiles(dir))

  it('reads the app', () => {
    expect(files).toEqual(expect.arrayContaining([
      'features/filings/lib/evidenceLabels.ts',
      'features/filings/components/SourceTrace.tsx',
      'features/filings/components/FilingIndex.tsx',
      'app/waitlist/page.tsx',
    ]))
  })

  it('ships no retired evidence label, and every link to the source names SEC.gov', () => {
    const breaches = files.flatMap((rel) => scan(rel, readFileSync(path.join(FRONTEND, rel), 'utf8')))
    expect(breaches).toEqual([])
  })

  it('keeps its one allowed literal only while the badge still compares it', () => {
    const display = readFileSync(path.join(FRONTEND, 'features/summaries/components/SummaryDisplay.tsx'), 'utf8')
    for (const entry of RETIRED_ALLOWED) expect(display).toContain(`'${entry.split(': ')[1]}'`)
  })

  it('the OG card shows no retired label', () => {
    const visible = visibleHtml(readFileSync(path.join(FRONTEND, OG_TEMPLATE), 'utf8'))
    expect(visible).toContain('Apple Inc.')
    expect(visible).not.toMatch(/SEC XBRL|Verified in filing/)
  })
})

describe('the vocabulary scan holds its reach', () => {
  const breaches = (source: string) => scan('features/x/Planted.tsx', source).map((b) => b.rule)

  it.each([
    ['a link that names EDGAR', `export const A = () => <a href="https://www.sec.gov">Full history on SEC EDGAR</a>`],
    ['a link whose name names EDGAR', 'export const A = ({ u }: { u: string }) => <a href={u} aria-label={`View the 10-K on SEC EDGAR (opens in a new tab)`}>10-K</a>'],
    ['a link whose hidden text names EDGAR', `export const A = ({ u }: { u: string }) => <a href={u}><span aria-hidden="true">EDGAR</span></a>`],
    ['a Link that renders a same-file constant naming EDGAR', `const LABEL = 'Original on SEC EDGAR'\nexport const A = () => <Link href="/f">{LABEL}</Link>`],
    ['any element given an href', `export const A = () => <Button href="https://www.sec.gov">Open on EDGAR</Button>`],
  ])('fails %s', (_, source) => {
    expect(breaches(source)).toContain('link names EDGAR')
  })

  it.each([
    ['the old figure label', `export const B = () => <Badge>SEC XBRL</Badge>`],
    ['the old passage label', `export const L = 'Verified in filing'`],
    ['the old chip label', `export const L = cond ? 'Cited' : 'Matches filing'`],
    ['the old label in a template', 'export const L = (n: number) => `${n} SEC XBRL figures`'],
    ['the old hero chip', `export const C = () => <a href="https://www.sec.gov">Located in the filing</a>`],
    ['a bare source name as a label', `export const T = () => <span><ShieldCheckIcon />SEC EDGAR</span>`],
    ['the old match phrase', `export const S = 'Source match found'`],
    ['a bare verified badge', `export const V = () => <span><CheckCircleIcon />Verified</span>`],
  ])('fails %s', (_, source) => {
    expect(breaches(source)).toContain('retired label')
  })

  it.each([
    ['an attribution outside a link', `export const F = () => <p>Data sourced from SEC EDGAR</p>`],
    ['a comment inside a link', `export const A = ({ u }: { u: string }) => <a href={u}>{/* the EDGAR document */}Open the filing on SEC.gov</a>`],
    ['an address built from an EDGAR helper', `export const A = ({ cik }: { cik: string }) => <a href={edgarCompanyUrl(cik)}>Full history on SEC.gov</a>`],
    ['a sentence that cites', `export const P = () => <p>Official filings, cited and traceable to the source.</p>`],
    ['an acronym behind a plain word', `export const H = () => <details><summary>How we check</summary>We compare it with the XBRL data.</details>`],
    ['the product word in prose', `export const P = () => <p>Excerpts located in the filing’s own text, or withheld.</p>`],
    ['a source name in a keyword list', `export const K = ['SEC filings', 'SEC EDGAR']`],
  ])('passes %s', (_, source) => {
    expect(breaches(source)).toEqual([])
  })
})
