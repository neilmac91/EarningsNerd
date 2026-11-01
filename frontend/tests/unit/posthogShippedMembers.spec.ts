import { execFileSync } from 'node:child_process'
import { readdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * Rule-12 gate for lessons/frontend-reach-sdk-internals-by-shape-and-test-the-shipped-build.md and, by its identity
 * check, lessons/frontend-an-sdk-that-captures-nothing-can-still-store.md: no code reaches a
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
 * Three more checks run here. The manifest has no field a bundler reads before `module`. No string names another copy
 * of the client, in any of its tokens (a path segment, a URL before its query or hash, markup held as text):
 * - a core build other than the manifest's entries, by its file name, or by a dotted name without its extension where
 *   the package ships that file (`module.no-external`);
 * - the `no-external` sub-package, or the compiled source (`posthog-core`);
 * - a package subpath other than `package.json`, `react` and the entries' own paths.
 * Which builds keep the names the entries rename changes between releases: in 1.440.0 every `no-external` build and
 * the ES5 build keep them. And app code (outside tests/) ties an account to PostHog only through lib/analytics.ts,
 * which waits for consent, since posthog-js stores an identity even while it captures nothing. The check fails:
 * - an `identify`, `alias` or `setIdentity` read off anything but a name bound to that module's import (called, passed
 *   or bound), or destructured;
 * - a key that sets the person (`bootstrap.distinctID`, `identity_distinct_id`, `register({ distinct_id })`) in an object
 *   literal or written by assignment;
 * - either kind named by a bare string, or another declaration of a name bound to the facade;
 * - any of these in code held in a string.
 *
 * Out of reach, as the planted gaps below record:
 * - a name, a build path or an identify assembled at run time;
 * - a core build named by a bare, dotless path segment (`array`, `module`), the `full` sub-package, or a compiled
 *   source file other than `posthog-core`, named by a bare path segment;
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
const CORE_BUILD = /^(?:array|module|main)(?:\.[\w-]+)*\.(?:m?js|cjs)$/
// A dotted core build name without its extension counts where the package ships that file (`module.no-external`), so
// `module.exports` passes. A bare `array` or `module` segment would match too much code and prose, so it is out of
// reach (planted below).
const CORE_BUILD_STEM = /^(?:array|module|main)(?:\.[\w-]+)+$/
const DIST = new Set(readdirSync(path.join(packageRoot, 'dist')))
const OTHER_COPIES = new Set(['no-external', 'posthog-core', 'posthog-core.js'])
const TOKEN_BREAK = /[^\w.@-]+/
const ENTRIES = new Set([path.basename(manifest.module), path.basename(manifest.main)])
const namesOtherCopy = (token: string) => (CORE_BUILD.test(token) && !ENTRIES.has(token))
  || (CORE_BUILD_STEM.test(token) && ['.js', '.mjs', '.cjs'].some(ext => DIST.has(token + ext) && !ENTRIES.has(token + ext)))
  || OTHER_COPIES.has(token)
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
  // A computed key written as a string literal (`{ ['_retryQueue']: queue }`) names the member all the same.
  if (ts.isComputedPropertyName(name) && ts.isStringLiteralLike(name.expression)) return name.expression.text
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
 * Every string that names another copy of the client than the manifest's entries. Only files that name posthog-js are
 * read, so a build's name counts as any token of a string, as a path segment does in `path.join(packageRoot, 'dist',
 * name)` or a file name does before a URL's query.
 */
function otherBuilds(source: string, fileName: string): string[] {
  const named: string[] = []
  stringsOf(parse(source, fileName), (text) => {
    const copies = text.split(TOKEN_BREAK).filter(namesOtherCopy)
    const subpaths = Array.from(text.matchAll(SUBPATH), match => match[1]).filter(subpath => !SUBPATHS_ALLOWED.has(subpath))
    if (copies.length || subpaths.length) named.push(`${fileName}: ${text}`)
  })
  return named
}

// posthog-js 1.440.0's ways to tie an account by call: setIdentity aliases the id it is given.
const IDENTITY_MEMBERS = new Set(['identify', 'alias', 'setIdentity'])
// Keys that set the person posthog-js reports as: `bootstrap: { distinctID }` and `identity_distinct_id` at init or in
// set_config, `register({ distinct_id })`.
const IDENTITY_KEYS = new Set(['distinctID', 'distinct_id', 'identity_distinct_id'])
const IDENTITY_HOME = 'lib/analytics.ts'

/** Whether an import names lib/analytics.ts: `@/lib/analytics`, or a relative path that resolves to it from this file. */
function namesFacade(specifier: string, fileName: string): boolean {
  if (specifier === '@/lib/analytics') return true
  if (!specifier.startsWith('.')) return false
  return path.posix.normalize(path.posix.join(path.posix.dirname(fileName), specifier)) === IDENTITY_HOME.replace(/\.ts$/, '')
}

/** The local names this file binds to lib/analytics.ts's exports, the default import and `analytics` included. */
function facadeNames(file: ts.SourceFile): Set<string> {
  const names = new Set<string>()
  for (const statement of file.statements) {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) continue
    if (!namesFacade(statement.moduleSpecifier.text, file.fileName)) continue
    const clause = statement.importClause
    if (clause?.name) names.add(clause.name.text)
    if (clause?.namedBindings && ts.isNamedImports(clause.namedBindings)) {
      for (const element of clause.namedBindings.elements) names.add(element.name.text)
    }
  }
  return names
}

/**
 * Whether this identifier is the name a declaration binds: a variable, a parameter, a destructured name, a function, a
 * class or an enum. An import is left out, since a second import of a name already bound fails to compile.
 */
function declares(node: ts.Identifier): boolean {
  const parent = node.parent
  return (ts.isVariableDeclaration(parent) || ts.isParameter(parent) || ts.isBindingElement(parent) || ts.isFunctionDeclaration(parent)
    || ts.isFunctionExpression(parent) || ts.isClassDeclaration(parent) || ts.isClassExpression(parent) || ts.isEnumDeclaration(parent))
    && parent.name === node
}

const IDENTITY_NAMES = new Set([...IDENTITY_MEMBERS, ...IDENTITY_KEYS])
const ASSIGNS = (kind: ts.SyntaxKind) => kind >= ts.SyntaxKind.FirstAssignment && kind <= ts.SyntaxKind.LastAssignment

/**
 * Each way this source ties an account to a PostHog client other than through lib/analytics.ts's facade, with its line:
 * - an identity member read off anything but a name bound to the facade's import (called, passed or bound), or
 *   destructured;
 * - a key that sets the person, in an object literal (computed keys written as strings included) or written by
 *   assignment;
 * - an identity member or key named by a bare string (`Reflect.get(posthog, 'identify')`, `const key = 'distinct_id'`);
 * - another declaration of a name bound to the facade, which could hold a client in its scope
 *   (`const analytics = usePostHog()`);
 * - any of these in code held in a string, two strings deep at most.
 */
function identityTies(source: string, fileName: string, depth = 0): Array<{ name: string; line: number }> {
  const file = parse(source, fileName)
  const facade = facadeNames(file)
  const found = new Map<string, { name: string; line: number }>()
  const flag = (name: string, node: ts.Node) => {
    const line = file.getLineAndCharacterOfPosition(node.getStart(file)).line + 1
    found.set(`${name}:${line}`, { name, line })
  }
  const viaFacade = (receiver: ts.Expression) => ts.isIdentifier(receiver) && facade.has(receiver.text)
  const keyed = (target: ts.Expression) => ts.isPropertyAccessExpression(target) ? target.name.text
    : ts.isElementAccessExpression(target) && ts.isStringLiteralLike(target.argumentExpression) ? target.argumentExpression.text : undefined
  const visit = (node: ts.Node) => {
    if (ts.isIdentifier(node) && facade.has(node.text) && declares(node)) {
      flag(`${node.text} declared again`, node)
    } else if ((ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node)) && IDENTITY_MEMBERS.has(keyed(node) ?? '')
      && !viaFacade(node.expression)) {
      flag(keyed(node)!, node)
    } else if (ts.isBindingElement(node) && ts.isObjectBindingPattern(node.parent)) {
      const name = nameOf(node.propertyName ?? node.name)
      if (name && IDENTITY_MEMBERS.has(name)) flag(name, node)
    } else if ((ts.isPropertyAssignment(node) || ts.isShorthandPropertyAssignment(node)) && IDENTITY_KEYS.has(nameOf(node.name) ?? '')) {
      flag(nameOf(node.name)!, node)
    } else if (ts.isBinaryExpression(node) && ASSIGNS(node.operatorToken.kind) && IDENTITY_KEYS.has(keyed(node.left) ?? '')) {
      flag(keyed(node.left)!, node)
    }
    ts.forEachChild(node, visit)
  }
  visit(file)
  stringsOf(file, (text, node) => {
    const parent = node.parent
    // An element access, a key and a destructured name are read above, by their place in the code.
    const placed = ts.isElementAccessExpression(parent) || ts.isComputedPropertyName(parent)
      || ((isMember(parent) || ts.isBindingElement(parent)) && ((parent as ts.BindingElement).propertyName === node || (parent as ts.NamedDeclaration).name === node))
    if (IDENTITY_NAMES.has(text)) {
      if (!placed && !inType(node)) flag(text, node)
    } else if (depth < 2 && /[.[{]/.test(text) && [...IDENTITY_NAMES].some(name => text.includes(name))) {
      for (const { name } of identityTies(text, 'held.ts', depth + 1)) flag(name, node)
    }
  })
  return [...found.values()]
}

const identityCalls = (source: string, fileName: string) => identityTies(source, fileName).map(({ name, line }) => `${fileName}:${line}: ${name}`)

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
    ['code held two strings deep', 'page.evaluate("new Function(\'return client._retryQueue\')")'],
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
    ['a build by its extensionless path segment', "require(path.join(POSTHOG_PACKAGE, 'dist', 'module.no-external'))"],
    ['a build URL with a version query', "page.addScriptTag({ url: `${INGEST}/static/array.full.no-external.js?v=1.440.0` })"],
    ['a build URL with an interpolated query', 'page.addScriptTag({ url: `${INGEST}/static/array.full.no-external.js?v=${version}` })'],
    ['a build URL with a hash', "fetch('/static/array.full.no-external.js#build')"],
    ['a build in markup held as text', 'route.fulfill({ body: \'<script src="/static/array.full.no-external.js"></script>\' })'],
    ['a build in page code held in a string', "page.addScriptTag({ content: `document.head.append(Object.assign(document.createElement('script'), { src: '/static/array.full.no-external.js' }))` })"],
    ['the no-external sub-package by its directory', "require(path.join(packageRoot, 'no-external'))"],
    ['the nested no-external sub-package by its directories', "require(path.join(packageRoot, 'full', 'no-external'))"],
    ['the compiled source of the client', "require(path.join(packageRoot, 'lib', 'src', 'posthog-core.js'))"],
    ['the compiled source of the client without its extension', "require(path.join(packageRoot, 'lib', 'src', 'posthog-core'))"],
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
    ['a module script', "page.addScriptTag({ type: 'module', content: script })"],
    ['a dotted word the package does not ship', "const target = 'module.exports'"],
  ])('passes %s', (_build, planted) => {
    expect(otherBuilds(planted, 'planted.ts')).toEqual([])
  })

  // Planted gaps, out of the gate's reach by design (header).
  it('does not see a name, a build path or an identify assembled at run time (a stated gap)', () => {
    expect(unknownToBuild('client[`_${part}Queue`]', 'planted.ts')).toEqual([])
    expect(otherBuilds("path.join(POSTHOG_PACKAGE, 'dist', `array.${flavour}.js`)", 'planted.ts')).toEqual([])
    expect(identityCalls('posthog[`ident${suffix}`](id)', 'planted.ts')).toEqual([])
  })
  it('does not see a dotless core build, the full sub-package or another compiled source file by a bare path segment (a stated gap)', () => {
    expect(otherBuilds("require(path.join(packageRoot, 'dist', 'array'))", 'planted.ts')).toEqual([])
    expect(otherBuilds("require(path.join(packageRoot, 'full'))", 'planted.ts')).toEqual([])
    expect(otherBuilds("require(path.join(packageRoot, 'lib', 'src', 'remote-config.js'))", 'planted.ts')).toEqual([])
  })
  it('does not read code held more than two strings deep (a stated gap)', () => {
    expect(unknownToBuild('page.evaluate(\'eval("Function(`return client._retryQueue`)")\')', 'planted.ts')).toEqual([])
    expect(identityCalls('page.evaluate(\'eval("Function(`return posthog.identify(id)`)")\')', 'planted.ts')).toEqual([])
  })
  it('does not read a file that handles a client without naming posthog-js (a stated gap)', () => {
    expect(scansFile('export const stand = { _send_retriable_request() {} }')).toBe(false)
  })
  it('passes a kept name read off the wrong object (a stated gap)', () => {
    expect(unknownToBuild('client._instance', 'planted.ts')).toEqual([])
  })
})

describe('an account reaches PostHog only through lib/analytics.ts', () => {
  const appCode = code.filter(file => !file.startsWith('tests/') && file !== IDENTITY_HOME)

  it('no app code that names posthog-js identifies an account outside lib/analytics.ts', () => {
    expect(appCode).toEqual(expect.arrayContaining(['app/posthog-provider.tsx', 'lib/posthogConsent.ts']))
    expect(appCode.flatMap(file => identityCalls(source(file), file))).toEqual([])
    // The facade's own call, which waits for consent, is the one the check sees there.
    expect(identityCalls(source(IDENTITY_HOME), IDENTITY_HOME)).toHaveLength(1)
  })

  it.each<[string, string, string?]>([
    ['a direct identify', 'posthog.identify(String(user.id), { plan })'],
    ['an identify through the React hook', 'usePostHog().identify(id)'],
    ['an optional identify', 'posthog?.identify(id)'],
    ['an identify by element access', "posthog['identify'](id)"],
    ['an alias', 'posthog.alias(id)'],
    ['an identify called through call', 'posthog.identify.call(posthog, id)'],
    ['an identify bound for later', 'const tie = posthog.identify.bind(posthog)'],
    ['an identify passed as a value', '[id].forEach(posthog.identify, posthog)'],
    ['a destructured identify', 'const { identify } = posthog'],
    ['a client imported under the facade\'s name', "import analytics from 'posthog-js'\nanalytics.identify(id)"],
    ['a client held under the facade\'s name', 'const analytics = usePostHog()\nanalytics.identify(id)'],
    ['a setIdentity, which aliases', 'posthog.setIdentity(id, hash)'],
    ['an identity bootstrapped at init', 'posthog.init(key, { bootstrap: { distinctID: id } })'],
    ['an identity given at init', 'posthog.init(key, { identity_distinct_id: id })'],
    ['an identity given by set_config', 'posthog.set_config({ identity_distinct_id: id })'],
    ['an identity registered by hand', 'posthog.register({ distinct_id: id })'],
    ['an identity registered by a computed key', "posthog.register({ ['distinct_id']: id })"],
    ['a client held in a scope under the facade\'s imported name', "import analytics from '@/lib/analytics'\nfunction tie(id: string) { const analytics = usePostHog(); analytics.identify(id) }"],
    ['a client passed under the facade\'s imported name', "import { analytics } from '@/lib/analytics'\nexport const tie = (analytics: PostHog, id: string) => analytics.identify(id)"],
    ['a client destructured under the facade\'s imported name', "import analytics from '@/lib/analytics'\nexport function tie({ analytics }: Props) { analytics.identify(id) }"],
    ['another module called analytics', "import { analytics } from './analytics'\nanalytics.identify(id)", 'app/planted.ts'],
    ['a method reached by its bare name', "Reflect.get(posthog, 'identify').call(posthog, id)"],
    ['a method name held in a variable', "const method = 'identify'\nposthog[method](id)"],
    ['a key written by assignment', 'props.distinct_id = id\nposthog.register(props)'],
    ['a key written by element access', "props['distinct_id'] ??= id"],
    ['an identify held as code in a page script', "const tie = <Script id=\"tie\">{'window.posthog.identify(id)'}</Script>", 'planted.tsx'],
    ['an identify held two strings deep', 'page.evaluate("new Function(\'return posthog.identify(id)\')")'],
  ])('flags %s', (_form, planted, fileName = 'planted.ts') => {
    expect(identityCalls(planted, fileName)).toHaveLength(1)
  })
  it.each<[string, string, string?]>([
    ['the consent-gated facade', "import analytics from '@/lib/analytics'\nanalytics.identify(String(user.id), { plan })"],
    ['the facade by its named export', "import { analytics } from '@/lib/analytics'\nanalytics.identify(id)"],
    ['the facade from a sibling under lib/', "import { analytics } from './analytics'\nanalytics.identify(id)", 'lib/planted.ts'],
    ['the facade by a relative path from another directory', "import analytics from '../lib/analytics'\nanalytics.identify(id)", 'hooks/planted.ts'],
    ['a key by the facade\'s name in an object', "import analytics from '@/lib/analytics'\nconst tools = { analytics, log: { analytics: true } }"],
    ['the facade by element access', "import analytics from '@/lib/analytics'\nanalytics['identify'](id)"],
    ['a read of the person\'s id', 'const id = posthog.get_distinct_id() ?? event.properties.distinct_id'],
    ['a type position', "type Identify = PostHog['identify']"],
    ['a sentence in a string', "const note = 'we identify a reader only after an allow.'"],
    ['another call', "posthog.capture('event')"],
  ])('passes %s', (_form, planted, fileName = 'planted.ts') => {
    expect(identityCalls(planted, fileName)).toEqual([])
  })
})
