import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Rule-12 gate for lessons/frontend-reach-sdk-internals-by-shape-and-test-the-shipped-build.md: no code reaches a
 * posthog-js member that the build Next bundles does not have. The npm builds rename some private members while the
 * typings keep them, so `tsc` passes `client._retryQueue` and the shipped code reads undefined: #1552's consent guard
 * threw before `posthog.init` on every page that way.
 *
 * It reads every file under frontend/ that names posthog-js (git's list, this gate left out). A JavaScript or
 * TypeScript file is parsed. Each underscore name it does any of the following with must appear as an identifier in
 * the package's `module` build, read from its manifest as a bundler reads it:
 * - reads, writes, destructures or tests for (`in`, Reflect, defineProperty);
 * - defines on a stand-in, as an object literal, a class or a constructor's parameter property;
 * - sets as a JSX attribute;
 * - passes as a bare string;
 * - holds as code in a string that another context runs (a page script, a Function body).
 * Type positions (indexed types, interfaces, ambient declarations and fields, .d.ts files) and comments are not code. A
 * JSON file runs no code; any other kind of file that names posthog-js fails here until the gate learns to read it.
 * Prose in a string that names a member by its dotted path (`'client._retryQueue is renamed'`) reads as held code and
 * fails: reword it, never exempt the name. NOT_POSTHOG_MEMBERS lists the underscore names such files use that are not
 * posthog-js members, each with its reason.
 *
 * Two more checks run here. The manifest has no field a bundler reads before `module`. And no string names a posthog-js
 * build other than the manifest's own entries, by its file name (alone or in a path) or by a package subpath other
 * than `package.json` and `react`. Which builds keep the names the entries rename changes between releases: in 1.440.0
 * every `no-external` build and the ES5 build keep them.
 *
 * Out of reach, as the planted gaps below record:
 * - a name or a build path assembled at run time;
 * - code held more than two strings deep;
 * - a file that handles a PostHog client without naming posthog-js;
 * - a kept name read off the wrong object, since a name passes when the build has it anywhere (`client._instance`
 *   passes, though the client's helpers carry `_instance` and the client does not).
 */

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SELF = path.relative(frontendRoot, fileURLToPath(import.meta.url)).split(path.sep).join('/')
const packageRoot = path.dirname(createRequire(import.meta.url).resolve('posthog-js/package.json'))
const manifest = JSON.parse(readFileSync(path.join(packageRoot, 'package.json'), 'utf8')) as Record<string, unknown> & { module: string; main: string }
const shipped = readFileSync(path.join(packageRoot, manifest.module), 'utf8')

/** Underscore names that files naming posthog-js use and that are not posthog-js members, each with its reason. */
const NOT_POSTHOG_MEMBERS: Record<string, string> = {
  __earningsnerdConsentGeneration: 'lib/posthogConsent.ts tags request options with the consent generation',
  __esModule: 'module interop: the transport e2e page shim marks the posthog-js module it hands to compiled code',
}

const CODE = /\.(?:[mc]?[jt]sx?)$/
const TYPES_ONLY = /\.d\.[mc]?ts$/
const NOT_CODE = /\.json$/
const UNDERSCORE = /^_[\w$]*$/
const BUILD_FILE = /(?:^|[/\\])((?:array|module|main)(?:\.[\w-]+)*\.(?:m?js|cjs))(?:\?[\w=&-]*)?$/
const ENTRIES = new Set([path.basename(manifest.module), path.basename(manifest.main)])
// A package subpath, such as `posthog-js/no-external` (its own build) or `posthog-js/dist/...`. The manifest, the React
// wrapper (which imports the package entry) and the entries' own paths are allowed.
const SUBPATH = /(?<![\w@.-])posthog-js\/([\w.-]+(?:\/[\w.-]+)*)/g
const SUBPATHS_ALLOWED = new Set(['package.json', 'react', ...[manifest.module, manifest.main].map(entry => path.posix.normalize(entry))])
const escape = (name: string) => name.replace(/[$]/g, '\\$&')
const inBuild = (name: string) => new RegExp(`(?<![\\w$])${escape(name)}(?![\\w$])`).test(shipped)
const scansFile = (source: string) => source.includes('posthog-js')
const PROPERTY_MODIFIERS = new Set([ts.SyntaxKind.PublicKeyword, ts.SyntaxKind.PrivateKeyword, ts.SyntaxKind.ProtectedKeyword, ts.SyntaxKind.ReadonlyKeyword])

const ambient = (node: ts.Node) => ts.canHaveModifiers(node) && Boolean(ts.getModifiers(node)?.some(m => m.kind === ts.SyntaxKind.DeclareKeyword))

function inType(node: ts.Node): boolean {
  for (let current: ts.Node | undefined = node; current; current = current.parent) {
    // A class's `extends` clause holds an expression the class runs, though TypeScript files it as a type node.
    if (ts.isExpressionWithTypeArguments(current) && ts.isHeritageClause(current.parent)
      && current.parent.token === ts.SyntaxKind.ExtendsKeyword && ts.isClassLike(current.parent.parent)) return false
    if (ts.isTypeNode(current) || ts.isInterfaceDeclaration(current) || ts.isTypeAliasDeclaration(current) || ambient(current)) return true
  }
  return false
}

function nameOf(name: ts.Node | undefined): string | undefined {
  if (!name) return undefined
  if (ts.isIdentifier(name) || ts.isPrivateIdentifier(name) || ts.isStringLiteralLike(name)) return name.text
  if (ts.isJsxNamespacedName(name)) return name.name.text
  return undefined
}

const isMember = (node: ts.Node) => ts.isPropertyAssignment(node) || ts.isShorthandPropertyAssignment(node) || ts.isMethodDeclaration(node)
  || ts.isPropertyDeclaration(node) || ts.isGetAccessorDeclaration(node) || ts.isSetAccessorDeclaration(node) || ts.isJsxAttribute(node)

/** The text of every string-like node: a string, a plain template, or a template's literal parts with a stand-in value. */
function stringsOf(file: ts.SourceFile, visit: (text: string, node: ts.Node) => void) {
  const walk = (node: ts.Node) => {
    if (ts.isStringLiteralLike(node)) visit(node.text, node)
    else if (ts.isTemplateExpression(node)) visit(node.head.text + node.templateSpans.map(span => ` 0 ${span.literal.text}`).join(''), node)
    ts.forEachChild(node, walk)
  }
  walk(file)
}

function parse(source: string, fileName: string) {
  const kind = /\.[jt]sx$/.test(fileName) ? ts.ScriptKind.TSX : /\.[mc]?js$/.test(fileName) ? ts.ScriptKind.JS : ts.ScriptKind.TS
  return ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, kind)
}

/** Every underscore name the source uses as a member, with its line; code held in a string is read as code too. */
function underscoreMembers(source: string, fileName: string, depth = 0): Array<{ name: string; line: number }> {
  const file = parse(source, fileName)
  const found = new Map<string, { name: string; line: number }>()
  const lineOf = (node: ts.Node) => file.getLineAndCharacterOfPosition(node.getStart(file)).line + 1
  const add = (name: string | undefined, node: ts.Node) => {
    if (name && UNDERSCORE.test(name) && !inType(node)) found.set(`${name}:${lineOf(node)}`, { name, line: lineOf(node) })
  }
  const visit = (node: ts.Node) => {
    if (ts.isPropertyAccessExpression(node)) add(nameOf(node.name), node)
    else if (ts.isElementAccessExpression(node) && ts.isStringLiteralLike(node.argumentExpression)) add(node.argumentExpression.text, node)
    else if (ts.isBindingElement(node) && ts.isObjectBindingPattern(node.parent)) add(nameOf(node.propertyName ?? node.name), node)
    else if (isMember(node)) add(nameOf((node as ts.NamedDeclaration).name), node)
    else if (ts.isParameter(node) && ts.isConstructorDeclaration(node.parent) && ts.getModifiers(node)?.some(m => PROPERTY_MODIFIERS.has(m.kind))) {
      add(nameOf(node.name), node)
    }
    ts.forEachChild(node, visit)
  }
  visit(file)
  stringsOf(file, (text, node) => {
    const parent = node.parent
    if (ts.isImportDeclaration(parent) || ts.isExportDeclaration(parent) || ts.isElementAccessExpression(parent)) return
    if (isMember(parent) && (parent as ts.NamedDeclaration).name === node) return
    if (UNDERSCORE.test(text)) add(text, node)
    // A string can hold code another context runs: a page script, a Function body, a JSON stand-in.
    else if (depth < 2 && text.includes('_') && /[.[{]/.test(text)) {
      for (const { name } of underscoreMembers(text, 'held.ts', depth + 1)) add(name, node)
    }
  })
  return [...found.values()]
}

const unknownToBuild = (source: string, fileName: string) =>
  underscoreMembers(source, fileName)
    .filter(({ name }) => !(name in NOT_POSTHOG_MEMBERS) && !inBuild(name))
    .map(({ name, line }) => `${fileName}:${line}: ${name}`)

/**
 * Every posthog-js build a string names, other than the manifest's own entries. Only files that name posthog-js are
 * read, so a build's file name counts on its own, as a path segment does in `path.join(packageRoot, 'dist', name)`.
 */
function otherBuilds(source: string, fileName: string): string[] {
  const named: string[] = []
  stringsOf(parse(source, fileName), (text) => {
    const build = BUILD_FILE.exec(text)?.[1]
    const subpaths = Array.from(text.matchAll(SUBPATH), match => match[1]).filter(subpath => !SUBPATHS_ALLOWED.has(subpath))
    if ((build && !ENTRIES.has(build)) || subpaths.length) named.push(`${fileName}: ${text}`)
  })
  return named
}

const staleNames = (names: Record<string, string>, used: Set<string>) => Object.keys(names).filter(name => !used.has(name))

const listed = execFileSync('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z', '--', '.'], { cwd: frontendRoot, encoding: 'utf8' })
  .split('\0').filter(Boolean)
const targets = listed.filter(file => file !== SELF && scansFile(readFileSync(path.join(frontendRoot, file), 'utf8')))
const code = targets.filter(file => CODE.test(file) && !TYPES_ONLY.test(file))
const source = (file: string) => readFileSync(path.join(frontendRoot, file), 'utf8')

describe('posthog-js members the shipped build has', () => {
  it('reads the build Next bundles, which keeps every member the guard reaches by name', () => {
    // A bundler reads `exports` and `browser` before `module`. Should posthog-js add either, this gate, the guard's
    // unit gate and the transport e2e could all read a build Next no longer bundles, so that fails here first.
    expect(Object.keys(manifest).filter(field => field === 'exports' || field === 'browser')).toEqual([])
    // The queues' own method names (enqueue, unload, enable, resume) are common words in the build; the guard's
    // real-build unit gate decides those by finding the queues.
    for (const kept of ['_send_request', '__loaded', '__request_queue', '_instance', 'retriableRequest', 'is_capturing']) {
      expect(inBuild(kept), kept).toBe(true)
    }
  })

  it('reads every file kind it meets that names posthog-js, and not itself', () => {
    expect(listed).toContain(SELF)
    expect(targets).not.toContain(SELF)
    expect(code).toEqual(expect.arrayContaining(['lib/posthogConsent.ts', 'app/posthog-provider.tsx', 'tests/e2e/telemetry-network.spec.ts']))
    expect(targets.filter(file => !CODE.test(file) && !NOT_CODE.test(file))).toEqual([])
  })

  it('no code under frontend/ that names posthog-js reaches a member the shipped build does not have', () => {
    expect(code.flatMap(file => unknownToBuild(source(file), file))).toEqual([])
  })

  it('no code under frontend/ that names posthog-js loads a posthog-js build other than the manifest\'s entries', () => {
    expect(code.flatMap(file => otherBuilds(source(file), file))).toEqual([])
  })

  it('each name NOT_POSTHOG_MEMBERS lists is still used, so the list keeps no stale exemption', () => {
    const used = new Set(code.flatMap(file => underscoreMembers(source(file), file).map(({ name }) => name)))
    expect(staleNames(NOT_POSTHOG_MEMBERS, used)).toEqual([])
    expect(staleNames({ ...NOT_POSTHOG_MEMBERS, __plantedStaleName: 'planted' }, used)).toEqual(['__plantedStaleName'])
  })

  // The gate's fixture: each way the rule can be broken, and each look-alike that must pass.
  const PLANTED_BREAKS: Array<[string, string, string?]> = [
    ['an optional read', 'client._retryQueue?.unload()'],
    ['a call', 'client._send_retriable_request.bind(client)'],
    ['a write', 'client._requestQueue = queue'],
    ['an element access', "client['_requestQueue'].unload()"],
    ['an optional element access', "client?.['_requestQueue']"],
    ['a destructured read', 'const { _retryQueue: queue } = client'],
    ['a shorthand destructure', 'const { _retryQueue } = client'],
    ['an `in` test', "if ('_retryQueue' in client) {}"],
    ['a Reflect read', "Reflect.get(client, '_retryQueue')"],
    ['a stand-in field', 'const stand = { _send_retriable_request: vi.fn() }'],
    ['a stand-in method', 'const stand = { _send_retriable_request() {} }'],
    ['a class stand-in method', 'class Stand { _send_retriable_request() { return undefined } }'],
    ['a class stand-in field', 'class Stand { _retryQueue = { unload() {} } }'],
    ['a class stand-in getter', 'class Stand { get _retryQueue() { return queue } }'],
    ['a subclass override', 'class Mine extends PostHog { _send_retriable_request(options: unknown) { return options } }'],
    ['a class expression stand-in', 'const stand = new (class { _retryQueue = queue })()'],
    ['a parameter property', 'class Stand { constructor(public _retryQueue: object) {} }'],
    ['a read inside `extends`', 'class Probe extends (client._retryQueue as unknown as { new (): object }) {}'],
    ['a stand-in inside `extends`', 'class Probe extends mixin({ _send_retriable_request() {} }) {}'],
    ['a JSX attribute', 'const probe = <Probe _retryQueue={queue} />', 'planted.tsx'],
    ['a spy by name', "vi.spyOn(client, '_send_retriable_request')"],
    ['a property defined by name', "Object.defineProperty(client, '_retryQueue', { value: undefined })"],
    ['a page script in a string', "await page.addScriptTag({ content: 'window.posthog._retryQueue.unload()' })"],
    ['a page script in a template', 'await page.addScriptTag({ content: `window.posthog._retryQueue.unload(${delay})` })'],
    ['a Function body', "new Function('client', 'return client._retryQueue')"],
    ['a JSON stand-in', 'JSON.parse(\'{"_retryQueue": {}}\')'],
    ['prose naming a member by its dotted path, read as held code', "throw new Error('client._retryQueue is renamed by the build')"],
  ]
  it.each(PLANTED_BREAKS)('flags %s', (_form, planted, fileName = 'planted.ts') => {
    expect(unknownToBuild(planted, fileName)).toHaveLength(1)
  })

  const PLANTED_CLEAN: Array<[string, string]> = [
    ['a kept private name', 'client._send_request(options)'],
    ['a kept double-underscore name', 'if (client.__loaded) client.__request_queue = []'],
    ['an own name', 'options.__earningsnerdConsentGeneration ??= generation'],
    ['the interop marker', "vi.mock('posthog-js', () => ({ __esModule: true, default: client }))"],
    ['a type position', "type Retry = PostHog['_retryQueue']"],
    ['an interface key', "interface Hidden { '_retryQueue': unknown }"],
    ['an ambient class', "declare class Hidden { '_retryQueue': unknown }"],
    ['an ambient field', 'class Stand { declare _retryQueue: unknown }'],
    ['a comment', '// client._retryQueue is renamed by the build'],
    ['a sentence in a string', "const note = 'the build renames _retryQueue, so the guard finds it by shape'"],
    ['a public name', 'client.capture("event")'],
  ]
  it.each(PLANTED_CLEAN)('passes %s', (_form, planted) => {
    expect(unknownToBuild(planted, 'planted.ts')).toEqual([])
  })

  it.each([
    ['#1552\'s CDN build, which keeps the names', "readFileSync('node_modules/posthog-js/dist/array.full.no-external.js')"],
    ['a build named in its own path segment', "page.addScriptTag({ path: path.join(POSTHOG_PACKAGE, 'dist', 'array.full.no-external.js') })"],
    ['a CommonJS build', "require(path.join(packageRoot, 'dist', 'module.no-external.cjs'))"],
    ['a build read raw, by a query', "path.join(POSTHOG_PACKAGE, 'dist', 'array.full.no-external.js?raw')"],
    ['a build in a template on the package path', 'readFileSync(`${POSTHOG_PACKAGE}/dist/array.full.no-external.js`)'],
    ['a build that renames the names, but is not an entry', "import(pathToFileURL('node_modules/posthog-js/dist/module.full.js').href)"],
    ['a subpath entry', "await import('posthog-js/no-external')"],
    ['a nested subpath entry', "await import('posthog-js/full/no-external')"],
    ['a build by its extensionless subpath', "await import('posthog-js/dist/module.no-external')"],
  ])('flags a test that loads %s', (_build, planted) => {
    expect(otherBuilds(planted, 'planted.ts')).toHaveLength(1)
  })
  it.each([
    ['the manifest module entry', "path.join(packageRoot, 'dist/module.mjs')"],
    ['the module entry by subpath', "require.resolve('posthog-js/dist/module.mjs')"],
    ['an extension script', "path.join(POSTHOG_PACKAGE, 'dist', 'lazy-recorder.js')"],
    ['the package entry', "import posthog from 'posthog-js'"],
    ['the manifest', "require.resolve('posthog-js/package.json')"],
    ['the React wrapper', "import { PostHogProvider } from 'posthog-js/react'"],
  ])('passes %s', (_build, planted) => {
    expect(otherBuilds(planted, 'planted.ts')).toEqual([])
  })

  // Planted gaps, out of the gate's reach by design (header).
  it('does not see a name or a build path assembled at run time (a stated gap)', () => {
    expect(unknownToBuild('client[`_${part}Queue`]', 'planted.ts')).toEqual([])
    expect(otherBuilds("path.join(POSTHOG_PACKAGE, 'dist', `array.${flavour}.js`)", 'planted.ts')).toEqual([])
  })
  it('does not read code held more than two strings deep (a stated gap)', () => {
    expect(unknownToBuild('page.evaluate(\'eval("Function(`return client._retryQueue`)")\')', 'planted.ts')).toEqual([])
  })
  it('does not read a file that handles a client without naming posthog-js (a stated gap)', () => {
    expect(scansFile('export const stand = { _send_retriable_request() {} }')).toBe(false)
  })
  it('passes a kept name read off the wrong object (a stated gap)', () => {
    expect(unknownToBuild('client._instance', 'planted.ts')).toEqual([])
  })
})
