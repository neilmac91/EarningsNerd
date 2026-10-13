import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * A Badge is a label, never a control (brand sweep filing/F27; DESIGN_SYSTEM.md: passive Card and Badge
 * primitives do not implement the control-state set). The ticker route once wrapped a brand Badge in a
 * link, so the row's one action looked like a status chip and had no hover, focus or pressed state of
 * its own. A Badge may sit inside a control beside the control's own text (a form chip on a filing
 * card), but it is never the control's whole face, and it never takes a handler or a control role.
 */

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const ROOTS = ['app', 'components', 'features']
const CONTROLS = new Set(['a', 'button', 'Link', 'Button'])
const CONTROL_ROLES = new Set(['button', 'link', 'menuitem', 'tab', 'checkbox', 'switch', 'option'])

const tagOf = (node: ts.Node): string | null =>
  ts.isJsxElement(node) ? node.openingElement.tagName.getText() : ts.isJsxSelfClosingElement(node) ? node.tagName.getText() : null

const attributesOf = (node: ts.JsxElement | ts.JsxSelfClosingElement) =>
  (ts.isJsxElement(node) ? node.openingElement : node).attributes.properties.filter(ts.isJsxAttribute)

/** The Badges in one source that are a control's whole face, or a control themselves. */
export function badgeControls(source: string, file = 'probe.tsx'): string[] {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const out: string[] = []
  const at = (node: ts.Node) => `${file}:${sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1}`
  const visit = (node: ts.Node) => {
    if (ts.isJsxElement(node) && CONTROLS.has(node.openingElement.tagName.getText())) {
      const children = node.children.filter((child) => !(ts.isJsxText(child) && child.containsOnlyTriviaWhiteSpaces))
      if (children.length === 1 && tagOf(children[0]) === 'Badge') out.push(`${at(children[0])} a Badge is the whole face of a <${node.openingElement.tagName.getText()}>`)
    }
    if ((ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) && tagOf(node) === 'Badge') {
      for (const attr of attributesOf(node)) {
        const name = attr.name.getText()
        const role = name === 'role' && attr.initializer && ts.isStringLiteral(attr.initializer) ? attr.initializer.text : null
        if (/^on[A-Z]/.test(name) || name === 'href' || name === 'tabIndex' || (role && CONTROL_ROLES.has(role))) {
          out.push(`${at(node)} a Badge takes ${name}${role ? `="${role}"` : ''}`)
        }
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return out
}

function sources(): string[] {
  const out: string[] = []
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) {
        if (entry.name !== 'node_modules') walk(full)
      } else if (entry.name.endsWith('.tsx')) out.push(full)
    }
  }
  for (const root of ROOTS) walk(path.join(FRONTEND, root))
  return out
}

describe('a Badge is a label, never a control', () => {
  it('sees a Badge used as a control (a check that finds nothing must not pass)', () => {
    expect(badgeControls('const a = <Link href="/x">\n  <Badge variant="brand">Generate</Badge>\n</Link>')).toEqual([
      'probe.tsx:2 a Badge is the whole face of a <Link>',
    ])
    expect(badgeControls('const a = <button type="button"><Badge>Go</Badge></button>')).toHaveLength(1)
    expect(badgeControls('const a = <Badge onClick={go}>Go</Badge>')).toEqual(['probe.tsx:1 a Badge takes onClick'])
    expect(badgeControls('const a = <Badge role="button">Go</Badge>')).toEqual(['probe.tsx:1 a Badge takes role="button"'])
    // A Badge beside the control's own text is a label inside it, which is allowed.
    expect(badgeControls('const a = <Link href="/x"><Badge>10-K</Badge> <span>Apple annual report</span></Link>')).toEqual([])
  })

  it('no source file uses a Badge as a control', () => {
    const files = sources()
    expect(files.length, 'the source walk found the app').toBeGreaterThan(100)
    const offenders = files.flatMap((file) => badgeControls(readFileSync(file, 'utf8'), path.relative(FRONTEND, file)))
    expect(offenders, 'use a Button, a text link or IDENTITY_LINK for the action, and keep the Badge as its label').toEqual([])
  })
})
