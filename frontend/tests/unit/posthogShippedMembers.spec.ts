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
 * In every file under frontend/ that names posthog-js (an import, a type import, a vi.mock), each underscore name the
 * code reads, writes, destructures, defines on an object literal or passes as a string (vi.spyOn, defineProperty)
 * must appear as an identifier in the package's `module` build, read from its package.json as a bundler reads it.
 * Type positions (`PostHog['_retryQueue']`) and comments are not code, so they are not read. Our own underscore names
 * are listed in OWN_NAMES with their reason. Out of reach, as the planted gaps below record: a name assembled at run
 * time, and a file that handles a PostHog client without naming posthog-js. A public name a build renamed would break
 * the SDK's own API, so only underscore names are read.
 */

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const packageRoot = path.dirname(createRequire(import.meta.url).resolve('posthog-js/package.json'))
const manifest = JSON.parse(readFileSync(path.join(packageRoot, 'package.json'), 'utf8')) as Record<string, unknown> & { module: string }
const shipped = readFileSync(path.join(packageRoot, manifest.module), 'utf8')

/** Our own underscore names on PostHog objects, never posthog-js members. */
const OWN_NAMES: Record<string, string> = {
  __earningsnerdConsentGeneration: 'lib/posthogConsent.ts tags request options with the consent generation',
}

const UNDERSCORE = /^_[\w$]*$/
const escape = (name: string) => name.replace(/[$]/g, '\\$&')
const inBuild = (name: string) => new RegExp(`(?<![\\w$])${escape(name)}(?![\\w$])`).test(shipped)

function inType(node: ts.Node): boolean {
  for (let current: ts.Node | undefined = node.parent; current; current = current.parent) {
    if (ts.isTypeNode(current)) return true
  }
  return false
}

function nameOf(name: ts.Node | undefined): string | undefined {
  if (!name) return undefined
  if (ts.isIdentifier(name) || ts.isPrivateIdentifier(name) || ts.isStringLiteralLike(name)) return name.text
  return undefined
}

/** Every underscore name the source uses as a member, with its line. */
export function underscoreMembers(source: string, fileName: string): Array<{ name: string; line: number }> {
  const kind = /\.tsx$|\.jsx$/.test(fileName) ? ts.ScriptKind.TSX : /\.[mc]?js$/.test(fileName) ? ts.ScriptKind.JS : ts.ScriptKind.TS
  const file = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, kind)
  const found: Array<{ name: string; line: number }> = []
  const add = (name: string | undefined, node: ts.Node) => {
    if (name && UNDERSCORE.test(name) && !inType(node)) {
      found.push({ name, line: file.getLineAndCharacterOfPosition(node.getStart(file)).line + 1 })
    }
  }
  const visit = (node: ts.Node) => {
    if (ts.isPropertyAccessExpression(node)) add(nameOf(node.name), node)
    else if (ts.isElementAccessExpression(node) && ts.isStringLiteralLike(node.argumentExpression)) add(node.argumentExpression.text, node)
    else if (ts.isBindingElement(node) && ts.isObjectBindingPattern(node.parent)) add(nameOf(node.propertyName ?? node.name), node)
    else if ((ts.isPropertyAssignment(node) || ts.isShorthandPropertyAssignment(node) || ts.isMethodDeclaration(node)
      || ts.isGetAccessorDeclaration(node) || ts.isSetAccessorDeclaration(node)) && ts.isObjectLiteralExpression(node.parent)) {
      add(nameOf(node.name), node)
    } else if (ts.isStringLiteralLike(node) && !ts.isElementAccessExpression(node.parent) && !ts.isImportDeclaration(node.parent)
      && !ts.isExportDeclaration(node.parent) && !ts.isExternalModuleReference(node.parent)) {
      add(node.text, node)
    }
    ts.forEachChild(node, visit)
  }
  visit(file)
  return found
}

const unknownToBuild = (source: string, fileName: string) =>
  underscoreMembers(source, fileName)
    .filter(({ name }) => !(name in OWN_NAMES) && !inBuild(name))
    .map(({ name, line }) => `${fileName}:${line}: ${name}`)

const files = execFileSync('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z', '--', '.'], { cwd: frontendRoot, encoding: 'utf8' })
  .split('\0')
  .filter(file => /\.(?:[mc]?[jt]sx?)$/.test(file))

describe('posthog-js members the shipped build has', () => {
  it('reads the build Next bundles, which keeps every member the guard reaches by name', () => {
    // A bundler reads `exports` and `browser` before `module`. Should posthog-js add either, this gate, the guard's
    // unit gate and the transport e2e could all read a build Next no longer bundles, so that fails here first.
    expect(Object.keys(manifest).filter(field => field === 'exports' || field === 'browser')).toEqual([])
    for (const kept of ['_send_request', '__loaded', '__request_queue', '_instance', 'retriableRequest', 'enqueue', 'unload', 'resume', 'enable']) {
      expect(inBuild(kept), kept).toBe(true)
    }
  })

  it('no code under frontend/ that names posthog-js reaches a member the shipped build does not have', () => {
    const scanned = files.filter(file => readFileSync(path.join(frontendRoot, file), 'utf8').includes('posthog-js'))
    // The guard and the provider name posthog-js: a scan that misses them proves nothing.
    expect(scanned).toEqual(expect.arrayContaining(['lib/posthogConsent.ts', 'app/posthog-provider.tsx']))
    const unknown = scanned.flatMap(file => unknownToBuild(readFileSync(path.join(frontendRoot, file), 'utf8'), file))
    expect(unknown).toEqual([])
  })

  it('each own name is still used, so the list cannot keep a stale exemption', () => {
    const used = new Set(files
      .filter(file => readFileSync(path.join(frontendRoot, file), 'utf8').includes('posthog-js'))
      .flatMap(file => underscoreMembers(readFileSync(path.join(frontendRoot, file), 'utf8'), file).map(({ name }) => name)))
    expect(Object.keys(OWN_NAMES).filter(name => !used.has(name))).toEqual([])
  })

  // The gate's fixture: each way the rule can be broken, and each look-alike that must pass.
  const PLANTED_BREAKS: Array<[string, string]> = [
    ['an optional read', 'client._retryQueue?.unload()'],
    ['a call', 'client._send_retriable_request.bind(client)'],
    ['a write', 'client._requestQueue = queue'],
    ['an element access', "client['_requestQueue'].unload()"],
    ['a destructured read', 'const { _retryQueue: queue } = client'],
    ['a shorthand destructure', 'const { _retryQueue } = client'],
    ['a stand-in field', 'const stand = { _send_retriable_request: vi.fn() }'],
    ['a stand-in method', 'const stand = { _send_retriable_request() {} }'],
    ['a spy by name', "vi.spyOn(client, '_send_retriable_request')"],
    ['a property defined by name', "Object.defineProperty(client, '_retryQueue', { value: undefined })"],
  ]
  it.each(PLANTED_BREAKS)('flags %s', (_form, code) => {
    expect(unknownToBuild(code, 'planted.ts')).toHaveLength(1)
  })

  const PLANTED_CLEAN: Array<[string, string]> = [
    ['a kept private name', 'client._send_request(options)'],
    ['a kept double-underscore name', 'if (client.__loaded) client.__request_queue = []'],
    ['an own name', 'options.__earningsnerdConsentGeneration ??= generation'],
    ['a type position', "type Retry = PostHog['_retryQueue']"],
    ['a comment', '// client._retryQueue is renamed by the build'],
    ['a sentence in a string', "const note = 'the build renames _retryQueue'"],
    ['a public name', 'client.capture("event")'],
  ]
  it.each(PLANTED_CLEAN)('passes %s', (_form, code) => {
    expect(unknownToBuild(code, 'planted.ts')).toEqual([])
  })

  // Planted gaps, out of the gate's reach by design (header).
  const PLANTED_GAPS: Array<[string, string]> = [
    ['a name assembled at run time', 'client[`_${part}Queue`]'],
  ]
  it.each(PLANTED_GAPS)('does not see %s (a stated gap)', (_form, code) => {
    expect(unknownToBuild(code, 'planted.ts')).toEqual([])
  })
})
