import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * A Notice or GuidanceCard title is one phrase, never two clauses joined by a semicolon: the second clause
 * belongs in the description ("Checkout finished", then "Your plan updates in a moment."; D-033). Every
 * string literal, template piece and JSX text inside a `title` given to either component (under any import
 * alias) in app, components and features fails here when it holds a semicolon, both arms of a conditional
 * included. A title passed in as a variable is not read. JSX decodes HTML entities in its text and attribute
 * strings, so `&apos;` reads as an apostrophe, not as a semicolon, and `&#59;` reads as one.
 */
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const ROOTS = ['app', 'components', 'features']
const COMPONENTS = new Set(['Notice', 'GuidanceCard'])

/** A JSX text or attribute string as it renders: numeric entities decoded, the common named ones decoded and
 *  any other named one dropped (none renders a semicolon). A JS string inside braces is not decoded by JSX. */
const NAMED_ENTITIES: Record<string, string> = { amp: '&', apos: "'", quot: '"', lt: '<', gt: '>', nbsp: ' ' }
const decodeJsxEntities = (text: string): string =>
  text.replace(/&(#\d+|#x[\da-f]+|\w+);/gi, (_entity, body: string) =>
    body[0] !== '#'
      ? NAMED_ENTITIES[body] ?? ''
      : String.fromCodePoint(/^#x/i.test(body) ? Number.parseInt(body.slice(2), 16) : Number(body.slice(1))),
  )

/** Every text piece of every Notice or GuidanceCard title in a source, as `file:line text`. */
function titleTexts(file: string, text: string): string[] {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const names = new Set(COMPONENTS)
  for (const statement of source.statements) {
    const bindings = ts.isImportDeclaration(statement) ? statement.importClause?.namedBindings : undefined
    if (bindings && ts.isNamedImports(bindings)) {
      for (const element of bindings.elements) {
        if (COMPONENTS.has((element.propertyName ?? element.name).text)) names.add(element.name.text)
      }
    }
  }
  const found: string[] = []
  const pieces = (node: ts.Node): void => {
    // A nested element's own attributes (a span's className) are not title text.
    if (ts.isJsxAttribute(node)) return
    if (
      ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node) || ts.isTemplateHead(node)
      || ts.isTemplateMiddle(node) || ts.isTemplateTail(node) || ts.isJsxText(node)
    ) {
      const jsx = ts.isJsxText(node) || (ts.isStringLiteral(node) && ts.isJsxAttribute(node.parent))
      const words = (jsx ? decodeJsxEntities(node.text) : node.text).replace(/\s+/g, ' ').trim()
      if (words) found.push(`${file}:${source.getLineAndCharacterOfPosition(node.getStart()).line + 1} ${words}`)
    }
    ts.forEachChild(node, pieces)
  }
  const visit = (node: ts.Node): void => {
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && names.has(node.tagName.getText(source))) {
      for (const attribute of node.attributes.properties) {
        if (ts.isJsxAttribute(attribute) && attribute.name.getText(source) === 'title' && attribute.initializer) {
          pieces(attribute.initializer)
        }
      }
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

describe('A Notice or GuidanceCard title is one phrase', () => {
  it('reads each piece of a title, under an alias and in both arms, and nothing else (self-check)', () => {
    const fixture = [
      "import { Notice as Banner } from '@/components/ui'",
      'const a = <Notice title="Checkout finished; your plan updates in a moment" />',
      "const b = <GuidanceCard title={week ? 'A quiet week' : 'Loading; please wait'} description=\"x\" />",
      'const c = <Banner title={`${n} filings; more soon`} />',
      'const d = <Notice title={<span className="a;b">Two; clauses</span>} />',
      'const e = <Notice title="Pro is active" description="Your plan updates; reload" />',
      'const f = <Badge title="a; b" />',
      'const g = <Notice title={message} />',
      'const h = <Notice title="You&apos;re on Pro" /> // an entity is one character, not a semicolon',
      'const i = <Notice title={<>Tom &amp; Jerry; a pair &#59; two</>} />',
    ].join('\n')
    expect(titleTexts('fixture.tsx', fixture)).toEqual([
      'fixture.tsx:2 Checkout finished; your plan updates in a moment',
      'fixture.tsx:3 A quiet week',
      'fixture.tsx:3 Loading; please wait',
      'fixture.tsx:4 filings; more soon',
      'fixture.tsx:5 Two; clauses',
      'fixture.tsx:6 Pro is active',
      "fixture.tsx:9 You're on Pro",
      'fixture.tsx:10 Tom & Jerry; a pair ; two',
    ])
    // The rule's own test on the decoded text: the entity passes, the real semicolon fails.
    expect(titleTexts('fixture.tsx', fixture).slice(-2).map((title) => title.includes(';'))).toEqual([false, true])
  })

  it('no title in the app joins two clauses with a semicolon', () => {
    const files = ROOTS.flatMap((root) => walk(path.join(frontendDir, root)))
    const titles = files.flatMap((file) =>
      titleTexts(path.relative(frontendDir, file).split(path.sep).join('/'), readFileSync(file, 'utf8')),
    )
    expect(titles.filter((title) => title.includes(';')), 'move the second clause into the description').toEqual([])
    // Not vacuous: the post-checkout notices this rule came from are read.
    expect(titles.map((title) => title.slice(title.indexOf(' ') + 1))).toEqual(
      expect.arrayContaining(['Pro is active', 'Checkout finished', 'You returned from checkout']),
    )
  })
})
