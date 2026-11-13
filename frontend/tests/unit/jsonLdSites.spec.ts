// @vitest-environment node
/* =============================================================================
   jsonLdSites.spec.ts — guardrail
   -----------------------------------------------------------------------------
   Every <script type="application/ld+json"> writes its payload through
   lib/jsonLd's jsonLdHtml, which escapes `<`. JSON.stringify leaves `<` alone, so
   a `</script>` inside a value (a company name or a form type from SEC data)
   would end the element and the rest of the value would be parsed as markup.

   The scan reads each file's TypeScript AST (comments never count). A site is a
   JSX element whose `type` attribute is the literal "application/ld+json". It
   passes only in this form, with jsonLdHtml imported from '@/lib/jsonLd':

     <script type="application/ld+json"
             dangerouslySetInnerHTML={{ __html: jsonLdHtml(data) }} />

   and fails when the payload is anything else (JSON.stringify, a call wrapped in
   another expression, a helper of the same name defined elsewhere), when the
   element has children (a text child is not escaped) or when it spreads props
   (a spread can replace the payload). The type named anywhere but a JSX `type`
   attribute fails too (createElement props, a constant): the scan cannot read
   that element, so write it in JSX with the literal inline.
============================================================================= */

import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

const ROOT = path.join(__dirname, '../..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const LD_TYPE = 'application/ld+json'
const HELPER = 'jsonLdHtml'
const HELPER_MODULE = '@/lib/jsonLd'

type TextLiteral = ts.StringLiteral | ts.NoSubstitutionTemplateLiteral

const isTextLiteral = (node: ts.Node): node is TextLiteral =>
  ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)

function unwrap(node: ts.Node | undefined): ts.Node | undefined {
  let current = node
  while (current && (ts.isJsxExpression(current) || ts.isParenthesizedExpression(current))) current = current.expression
  return current
}

function attribute(attributes: ts.JsxAttributes, name: string, source: ts.SourceFile): ts.JsxAttribute | undefined {
  return attributes.properties.find(
    (property): property is ts.JsxAttribute => ts.isJsxAttribute(property) && property.name.getText(source) === name,
  )
}

function importsHelper(source: ts.SourceFile): boolean {
  return source.statements.some((statement) => {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) return false
    if (statement.moduleSpecifier.text !== HELPER_MODULE) return false
    const bindings = statement.importClause?.namedBindings
    if (!bindings || !ts.isNamedImports(bindings)) return false
    return bindings.elements.some(
      (element) => element.name.text === HELPER && (element.propertyName === undefined || element.propertyName.text === HELPER),
    )
  })
}

function payloadProblem(attributes: ts.JsxAttributes, source: ts.SourceFile): string | undefined {
  const html = attribute(attributes, 'dangerouslySetInnerHTML', source)
  if (!html) return `has no dangerouslySetInnerHTML; write its payload as { __html: ${HELPER}(data) }`
  const value = unwrap(html.initializer)
  const property =
    value && ts.isObjectLiteralExpression(value)
      ? value.properties.find(
          (candidate): candidate is ts.PropertyAssignment =>
            ts.isPropertyAssignment(candidate) && candidate.name.getText(source) === '__html',
        )
      : undefined
  const payload = unwrap(property?.initializer)
  const direct = payload && ts.isCallExpression(payload) && ts.isIdentifier(payload.expression) && payload.expression.text === HELPER
  if (!direct) return `writes its payload without ${HELPER}; write it as { __html: ${HELPER}(data) }`
  if (!importsHelper(source)) return `calls a ${HELPER} that is not imported from '${HELPER_MODULE}'`
  return undefined
}

function scanJsonLd(file: string, text: string): { sites: number; problems: string[] } {
  const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const problems: string[] = []
  const read = new Set<ts.Node>()
  let sites = 0
  const at = (node: ts.Node) => `${file}:${source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1}`

  const visitElements = (node: ts.Node): void => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      const type = unwrap(attribute(node.attributes, 'type', source)?.initializer)
      if (type && isTextLiteral(type) && type.text === LD_TYPE) {
        sites += 1
        read.add(type)
        const problem = payloadProblem(node.attributes, source)
        if (problem) problems.push(`${at(node)} ${problem}`)
        if (node.attributes.properties.some(ts.isJsxSpreadAttribute)) {
          problems.push(`${at(node)} spreads props onto the element, which can replace its payload`)
        }
        const children = ts.isJsxOpeningElement(node) ? node.parent.children : []
        if (children.some((child) => !ts.isJsxText(child) || child.text.trim() !== '')) {
          problems.push(`${at(node)} has children; a text child is not escaped, so the payload goes in dangerouslySetInnerHTML`)
        }
      }
    }
    ts.forEachChild(node, visitElements)
  }
  visitElements(source)

  const visitLiterals = (node: ts.Node): void => {
    if (isTextLiteral(node) && node.text === LD_TYPE && !read.has(node)) {
      problems.push(`${at(node)} names the JSON-LD type outside a JSX type attribute, where this scan cannot read the element`)
    }
    ts.forEachChild(node, visitLiterals)
  }
  visitLiterals(source)

  return { sites, problems }
}

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) sourceFiles(full, out)
    else if (/\.tsx?$/.test(entry.name)) out.push(full)
  }
  return out
}

const IMPORT = `import { ${HELPER} } from '${HELPER_MODULE}'\n`
const element = (rest: string) => `${IMPORT}export const node = <script type="${LD_TYPE}" ${rest}`

// Each planted case is one way past the rule, and the words the scan must answer it with.
const PLANTED: Array<[name: string, source: string, expected: string]> = [
  ['JSON.stringify as the payload', element('dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />'), `without ${HELPER}`],
  ['the helper inside a larger expression', element(`dangerouslySetInnerHTML={{ __html: ${HELPER}(data) + tail }} />`), `without ${HELPER}`],
  ['a payload object built elsewhere', element('dangerouslySetInnerHTML={payload} />'), `without ${HELPER}`],
  ['no payload attribute', element('/>'), 'has no dangerouslySetInnerHTML'],
  ['a text child', element(`>{JSON.stringify(data)}</script>`), 'has children'],
  ['spread props', element(`dangerouslySetInnerHTML={{ __html: ${HELPER}(data) }} {...rest} />`), 'spreads props'],
  [
    'a helper of the same name defined in the file',
    `const ${HELPER} = (data: unknown) => JSON.stringify(data)\nexport const node = <script type="${LD_TYPE}" dangerouslySetInnerHTML={{ __html: ${HELPER}(data) }} />`,
    `not imported from '${HELPER_MODULE}'`,
  ],
  [
    'the helper imported under another name beside a local one',
    `import { ${HELPER} as safe } from '${HELPER_MODULE}'\nconst ${HELPER} = JSON.stringify\nexport const node = <script type="${LD_TYPE}" dangerouslySetInnerHTML={{ __html: ${HELPER}(data) }} />`,
    `not imported from '${HELPER_MODULE}'`,
  ],
  [
    'the type as an expression, with JSON.stringify',
    `${IMPORT}export const node = <script type={'${LD_TYPE}'} dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />`,
    `without ${HELPER}`,
  ],
  [
    'createElement props',
    `${IMPORT}export const node = createElement('script', { type: '${LD_TYPE}', dangerouslySetInnerHTML: { __html: JSON.stringify(data) } })`,
    'outside a JSX type attribute',
  ],
  [
    'the type held in a constant',
    `${IMPORT}const TYPE = '${LD_TYPE}'\nexport const node = <script type={TYPE} dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />`,
    'outside a JSX type attribute',
  ],
]

describe('JSON-LD script elements', () => {
  it('every site in the app writes its payload through jsonLdHtml', () => {
    let sites = 0
    const problems: string[] = []
    for (const dir of SCAN_DIRS) {
      for (const file of sourceFiles(path.join(ROOT, dir))) {
        const result = scanJsonLd(path.relative(ROOT, file), fs.readFileSync(file, 'utf8'))
        sites += result.sites
        problems.push(...result.problems)
      }
    }
    expect(problems).toEqual([])
    // The scan is reading the app: the homepage, company, filing and pricing pages each carry one.
    expect(sites).toBeGreaterThanOrEqual(4)
  })

  it('accepts the one sanctioned form, as a self-closing element or an empty pair', () => {
    const payload = `dangerouslySetInnerHTML={{ __html: ${HELPER}(build(data)) }}`
    expect(scanJsonLd('planted.tsx', element(`${payload} />`))).toEqual({ sites: 1, problems: [] })
    expect(scanJsonLd('planted.tsx', element(`${payload}>\n  </script>`))).toEqual({ sites: 1, problems: [] })
    expect(scanJsonLd('planted.tsx', `${IMPORT}export const node = <Script id="ld" type={\`${LD_TYPE}\`} ${payload} />`)).toEqual({
      sites: 1,
      problems: [],
    })
  })

  it.each(PLANTED)('reports a planted bypass: %s', (_name, source, expected) => {
    const { problems } = scanJsonLd('planted.tsx', source)
    expect(problems.join('\n')).toContain(expected)
  })

  it('leaves a file that only mentions the type in a comment alone', () => {
    expect(scanJsonLd('planted.ts', `// <script type="${LD_TYPE}">\nexport const answer = 42\n`)).toEqual({ sites: 0, problems: [] })
  })
})
