import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Section headings in settings and on the dashboard carry no icon (DESIGN.md › Icons; the "Settings and
 * subscription" line in docs/brand/08-applications.md §3). An icon element (a `…Icon` component from
 * lib/icons) fails here when it renders inside an <h2>/<h3>, or as the element directly before one among
 * the same parent's children, the flex-row shape the eight removed heading icons had (DSW-13, DSW-19).
 */
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const ROOTS = ['app/dashboard', 'features/settings', 'features/subscriptions', 'features/dashboard']
const HEADINGS = new Set(['h2', 'h3'])

type JsxNode = ts.JsxElement | ts.JsxSelfClosingElement
const isJsxNode = (node: ts.Node): node is JsxNode => ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)
const tagOf = (node: JsxNode, source: ts.SourceFile) =>
  (ts.isJsxElement(node) ? node.openingElement.tagName : node.tagName).getText(source)
const isIcon = (node: JsxNode, source: ts.SourceFile) => /Icon$/.test(tagOf(node, source))

/** Every icon rendered inside, or directly before, a section heading, as `file:line <Icon> where <hN>`. */
function headingIcons(file: string, text: string): string[] {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const found: string[] = []
  const at = (node: ts.Node) => source.getLineAndCharacterOfPosition(node.getStart()).line + 1
  const visit = (node: ts.Node): void => {
    if (ts.isJsxElement(node)) {
      const tag = tagOf(node, source)
      if (HEADINGS.has(tag)) {
        const inside = (child: ts.Node): void => {
          if (isJsxNode(child) && isIcon(child, source)) found.push(`${file}:${at(child)} <${tagOf(child, source)}> inside <${tag}>`)
          ts.forEachChild(child, inside)
        }
        node.children.forEach(inside)
      }
      // Siblings: the element before a heading, skipping whitespace-only text.
      const siblings = node.children.filter((child) => !(ts.isJsxText(child) && child.containsOnlyTriviaWhiteSpaces))
      siblings.forEach((child, i) => {
        const before = siblings[i - 1]
        if (i > 0 && isJsxNode(child) && HEADINGS.has(tagOf(child, source)) && isJsxNode(before) && isIcon(before, source)) {
          found.push(`${file}:${at(before)} <${tagOf(before, source)}> before <${tagOf(child, source)}>`)
        }
      })
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return found
}

const walk = (dir: string): string[] =>
  readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name)
    if (statSync(full).isDirectory()) return walk(full)
    return name.endsWith('.tsx') ? [full] : []
  })

describe('Section headings in settings and on the dashboard carry no icon', () => {
  it('sees an icon inside a heading and one directly before it, and nothing else (self-check)', () => {
    const fixture = [
      'const a = <h2><BellIcon className="h-5 w-5" /> Filing alerts</h2>',
      'const b = <div className="flex items-center gap-3"><CreditCardIcon className="h-5 w-5" />',
      '  <h2>Billing</h2></div>',
      'const c = <div><h3>Plan</h3><LightningIcon /></div>',
      'const d = <div><LinkIcon /><p>Not a heading</p><h3>Accounts</h3></div>',
      'const e = <Badge icon={<LightningIcon />}>Pro</Badge>',
    ].join('\n')
    expect(headingIcons('fixture.tsx', fixture)).toEqual([
      'fixture.tsx:1 <BellIcon> inside <h2>',
      'fixture.tsx:2 <CreditCardIcon> before <h2>',
    ])
  })

  it('no settings, subscription or dashboard source puts an icon on a section heading', () => {
    const files = ROOTS.flatMap((root) => walk(path.join(frontendDir, root)))
    // Not vacuous: the settings sources this rule came from are scanned.
    const rels = files.map((file) => path.relative(frontendDir, file).split(path.sep).join('/'))
    expect(rels).toEqual(expect.arrayContaining([
      'features/settings/components/BillingPanel.tsx',
      'features/settings/components/NotificationPreferencesForm.tsx',
      'app/dashboard/settings/page.tsx',
      'features/dashboard/components/FilingFeed.tsx',
    ]))
    expect(files.flatMap((file, i) => headingIcons(rels[i], readFileSync(file, 'utf8')))).toEqual([])
  })
})
