import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * A control that writes to the clipboard keeps its words and says a press where a screen reader hears it (rule 12;
 * chief design on #1789, #1791 and #1793). Copy link flashed its words to "Copied" under a pinned aria-label, so its
 * name lacked the word shown (WCAG 2.5.3) and a press said nothing a screen reader hears (4.1.3). Words that change
 * rename the control, and inside a live region (the bulk invite summary's) are heard on top of any confirmation. And
 * inside a modal dialog the page's toast region lies outside the dialog, which aria-modal hides from VoiceOver, so a
 * toast from in there is never heard.
 *
 * The scan reads each source file under app, components, features, hooks and lib as TypeScript, so a comment or a
 * string that only looks like code counts for nothing. Each clipboard write (`writeText` or `write` on any
 * `….clipboard`, optional chains included) is said on its own path: after it, in the function that writes, and outside
 * a catch clause or a rejection handler, it calls
 * - `toast.success(…)`, the toast region;
 * - the setter of a `useState` whose value a `role="status"` element of the file reads, as Copy filing link and Copy
 *   receipt do (Codex on #1793: a status line the copy never updates says nothing);
 * - or `onStatus(…)`, the status line of the dialog the control sits in.
 * A toast is never all: a write said in the toast region also calls `onStatus`, so a dialog can take its press. A
 * dialog (a file that renders ui/Modal) passes `onStatus` to each component it renders that takes one, and an `onStatus`
 * passed anywhere is the setter of a state a `role="status"` element of the passing file reads. No words in a file that
 * writes read "Copied", with or without a stop, as a label would (a state named 'copied' is no words). Any other reach
 * for the clipboard (an alias, a destructured `clipboard`) fails until the scan learns it, so no write hides from it.
 * PRESSED_BY names the spec that presses each writer and reads the words it says. The waitlist's referral Copy still
 * flips and is said nowhere; RESIDUE holds it to E244.
 */

const ROOT = join(__dirname, '..', '..')
const DIRS = ['app', 'components', 'features', 'hooks', 'lib']

function sourcesUnder(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === 'node_modules' ? [] : sourcesUnder(path)
    return /\.tsx?$/.test(entry.name) ? [path] : []
  })
}

const NO_CONFIRMATION = 'a clipboard write said nowhere a screen reader hears'
const TOAST_ONLY = 'a clipboard write said in the toast region alone, which a dialog hides'
const FLIPS = 'a label flips to "Copied"'
const UNREAD = 'a reach for the clipboard the scan cannot follow'
const DIALOG_TOAST = 'a dialog renders a control that takes onStatus without it'
const STATUS_NOWHERE = 'an onStatus that no status line reads'

const parse = (fileName: string, source: string) =>
  ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)

/** Each clipboard write in a source, and whether it reaches the clipboard any other way the scan cannot follow. */
function clipboardReach(sf: ts.SourceFile): { writes: ts.CallExpression[]; unread: boolean } {
  const writes: ts.CallExpression[] = []
  let unread = false
  const visit = (node: ts.Node) => {
    // `….clipboard` read straight into a call of one of its methods; anything else is a reach the scan cannot follow.
    if (ts.isPropertyAccessExpression(node) && node.name.text === 'clipboard') {
      const member = node.parent
      const call = ts.isPropertyAccessExpression(member) && member.expression === node ? member.parent : undefined
      if (!call || !ts.isCallExpression(call) || call.expression !== member || !/^(write|read)(Text)?$/.test(member.name.text)) unread = true
      else if (member.name.text.startsWith('write')) writes.push(call)
    }
    if (ts.isBindingElement(node) && (node.propertyName ?? node.name).getText() === 'clipboard') unread = true
    ts.forEachChild(node, visit)
  }
  visit(sf)
  return { writes, unread }
}

/** The innermost function around a node: the handler a clipboard write runs in. */
function enclosingFunction(node: ts.Node): ts.Node {
  for (let at = node.parent; at; at = at.parent) if (ts.isFunctionLike(at)) return at
  return node.getSourceFile()
}

/** On the failure's path between a node and the function that writes: in a catch clause, or in a rejection handler
 *  (`.catch(fn)`, or `.then(ok, fn)`'s second). */
function onFailurePath(node: ts.Node, fn: ts.Node): boolean {
  for (let at = node.parent; at && at !== fn; at = at.parent) {
    if (ts.isCatchClause(at)) return true
    const call = at.parent
    if (ts.isFunctionLike(at) && call && ts.isCallExpression(call) && ts.isPropertyAccessExpression(call.expression)) {
      const handler = call.arguments.indexOf(at as ts.Expression)
      if ((call.expression.name.text === 'catch' && handler === 0) || (call.expression.name.text === 'then' && handler === 1)) return true
    }
  }
  return false
}

const hasStatusRole = (attributes: ts.JsxAttributes) =>
  attributes.properties.some(
    (a) => ts.isJsxAttribute(a) && a.name.getText() === 'role' && !!a.initializer && ts.isStringLiteral(a.initializer) && a.initializer.text === 'status',
  )

/** Each name a source imports, with the file it resolves to under the frontend root and the name it exports there. */
function importsOf(sf: ts.SourceFile, fileName: string): Map<string, { file?: string; exported: string }> {
  const names = new Map<string, { file?: string; exported: string }>()
  for (const statement of sf.statements) {
    if (!ts.isImportDeclaration(statement) || !statement.importClause || !ts.isStringLiteral(statement.moduleSpecifier)) continue
    const spec = statement.moduleSpecifier.text
    const base = spec.startsWith('@/') ? join(ROOT, spec.slice(2)) : spec.startsWith('.') ? join(dirname(fileName), spec) : undefined
    const file = base && [`${base}.tsx`, `${base}.ts`, join(base, 'index.tsx'), join(base, 'index.ts')].find((path) => existsSync(path))
    const { name, namedBindings } = statement.importClause
    if (name) names.set(name.text, { file, exported: 'default' })
    if (namedBindings && ts.isNamedImports(namedBindings)) {
      for (const element of namedBindings.elements) names.set(element.name.text, { file, exported: (element.propertyName ?? element.name).text })
    }
  }
  return names
}

const takesOnStatusCache = new Map<string, boolean>()
/** Whether a component's file declares an `onStatus` prop: a control that says its press in the dialog it sits in. */
function takesOnStatus(file: string): boolean {
  if (!takesOnStatusCache.has(file)) {
    const sf = parse(file, readFileSync(file, 'utf8'))
    takesOnStatusCache.set(file, contains(sf, (n) => ts.isPropertySignature(n) && n.name.getText() === 'onStatus'))
  }
  return takesOnStatusCache.get(file)!
}

const isUiModal = (imported: { file?: string; exported: string } | undefined) =>
  !!imported?.file && imported.exported === 'Modal' && /components\/ui\/(index\.ts|Modal\.tsx)$/.test(imported.file)

function contains(root: ts.Node, test: (node: ts.Node) => boolean): boolean {
  let found = false
  const visit = (node: ts.Node) => {
    if (found) return
    if (test(node)) found = true
    else ts.forEachChild(node, visit)
  }
  visit(root)
  return found
}

/** What a source lacks: a write said where a screen reader hears it, a dialog's status line, words that stay. */
function copyFaults(source: string, fileName = join(ROOT, 'features', 'source.tsx')): string[] {
  const sf = parse(fileName, source)
  const { writes, unread } = clipboardReach(sf)
  const imports = importsOf(sf, fileName)
  const setters = new Map<string, string>()
  const spoken = new Set<string>()
  const elements: (ts.JsxOpeningElement | ts.JsxSelfClosingElement)[] = []
  let flips = false
  const visit = (node: ts.Node) => {
    // const [value, setValue] = useState(…)
    if (ts.isVariableDeclaration(node) && ts.isArrayBindingPattern(node.name) && node.initializer && ts.isCallExpression(node.initializer)
      && /(^|\.)useState$/.test(node.initializer.expression.getText())) {
      const [value, setter] = node.name.elements
      if (value && setter && ts.isBindingElement(value) && ts.isBindingElement(setter) && ts.isIdentifier(value.name) && ts.isIdentifier(setter.name)) {
        setters.set(setter.name.text, value.name.text)
      }
    }
    const element = ts.isJsxElement(node) ? node.openingElement : ts.isJsxSelfClosingElement(node) ? node : null
    if (element) elements.push(element)
    // Every name a status line reads.
    if (element && hasStatusRole(element.attributes)) {
      const read = (n: ts.Node) => {
        if (ts.isIdentifier(n)) spoken.add(n.text)
        ts.forEachChild(n, read)
      }
      read(node)
    }
    if ((ts.isStringLiteralLike(node) || ts.isJsxText(node)) && /^Copied[.!]?$/.test(node.text.trim())) flips = true
    ts.forEachChild(node, visit)
  }
  visit(sf)

  /** How a write is said on its own path: in the toast region, in a status line of the file, or through onStatus. */
  const said = (write: ts.CallExpression) => {
    const fn = enclosingFunction(write)
    const ways = new Set<'toast' | 'status' | 'onStatus'>()
    const look = (n: ts.Node) => {
      if (ts.isCallExpression(n) && n.getStart() >= write.getEnd() && !onFailurePath(n, fn)) {
        const callee = n.expression.getText()
        if (callee === 'toast.success') ways.add('toast')
        else if (callee === 'onStatus' || callee === 'props.onStatus') ways.add('onStatus')
        else if (spoken.has(setters.get(callee) ?? '')) ways.add('status')
      }
      ts.forEachChild(n, look)
    }
    look(fn)
    return ways
  }
  const ways = writes.map(said)
  const tag = (element: ts.JsxOpeningElement | ts.JsxSelfClosingElement) =>
    ts.isIdentifier(element.tagName) ? imports.get(element.tagName.text) : undefined
  const attribute = (element: ts.JsxOpeningElement | ts.JsxSelfClosingElement, name: string) =>
    element.attributes.properties.find((a): a is ts.JsxAttribute => ts.isJsxAttribute(a) && a.name.getText() === name)
  const dialog = elements.some((element) => isUiModal(tag(element)))
  const passed = elements.map((element) => attribute(element, 'onStatus')).filter((a) => a !== undefined)
  const reachesStatus = (a: ts.JsxAttribute) =>
    !!a.initializer && ts.isJsxExpression(a.initializer) && !!a.initializer.expression && ts.isIdentifier(a.initializer.expression)
    && spoken.has(setters.get(a.initializer.expression.text) ?? '')

  return [
    ...(ways.every((w) => w.size > 0) ? [] : [NO_CONFIRMATION]),
    ...(ways.some((w) => w.has('toast') && !w.has('onStatus')) ? [TOAST_ONLY] : []),
    ...(writes.length && flips ? [FLIPS] : []),
    ...(unread ? [UNREAD] : []),
    ...(dialog && elements.some((element) => {
      const file = tag(element)?.file
      return !!file && takesOnStatus(file) && !attribute(element, 'onStatus')
    }) ? [DIALOG_TOAST] : []),
    ...(passed.every(reachesStatus) ? [] : [STATUS_NOWHERE]),
  ]
}

/** The files the rule still finds at fault, each with its row. Equal, not a cap: a fix takes its entry out. */
const RESIDUE: Record<string, string[]> = {
  // E244: the waitlist success card's referral Copy flips to "Copied" and is said nowhere a screen reader hears.
  'features/waitlist/components/WaitlistForm.tsx': [NO_CONFIRMATION, FLIPS],
}

/**
 * The spec that presses each writer and reads the words it says (chief design on #1793): the scan reads where a press
 * is said, and these read what. Each word is in the writer and in its spec. A writer with no entry fails, so a new
 * copy control comes with a spec of its own; null is a writer whose fix brings its spec, held by RESIDUE.
 */
const PRESSED_BY: Record<string, { spec: string; words: string[] } | null> = {
  'features/admin/components/CopyLinkButton.tsx': {
    spec: 'tests/unit/inviteCopyConfirmations.spec.tsx',
    words: ['Invite link copied', 'Invite link copied.', 'Could not copy the link.'],
  },
  'features/admin/components/ShareInvite.tsx': {
    spec: 'tests/unit/inviteCopyConfirmations.spec.tsx',
    words: ['Invite message copied.', 'Could not copy the message.'],
  },
  'features/filings/components/WordingChanges.tsx': { spec: 'tests/unit/wording-changes.spec.tsx', words: ['Receipt copied.'] },
  'features/summaries/components/SummaryActionsBar.tsx': {
    spec: 'tests/unit/filing-link-copy.spec.tsx',
    words: ['Filing link copied.', 'Could not copy the link.'],
  },
  'features/waitlist/components/WaitlistForm.tsx': null,
}

const files = DIRS.flatMap((dir) => sourcesUnder(join(ROOT, dir)))

describe('a clipboard write is said where a screen reader hears it, and its control keeps its words', () => {
  it('holds every source file, the residue named exactly', () => {
    const found = Object.fromEntries(
      files
        .map((file) => [relative(ROOT, file), copyFaults(readFileSync(file, 'utf8'), file)] as const)
        .filter(([, faults]) => faults.length),
    )
    expect(found).toEqual(RESIDUE)
  })

  it('names the spec that presses each writer and reads the words it says', () => {
    const writers = files
      .filter((file) => clipboardReach(parse(file, readFileSync(file, 'utf8'))).writes.length > 0)
      .map((file) => relative(ROOT, file))
    expect(writers.sort(), 'each writer, and only a writer, has an entry').toEqual(Object.keys(PRESSED_BY).sort())
    for (const [writer, entry] of Object.entries(PRESSED_BY)) {
      if (!entry) {
        expect(RESIDUE[writer], `${writer} has no spec and no row`).toBeDefined()
        continue
      }
      const source = readFileSync(join(ROOT, writer), 'utf8')
      const spec = readFileSync(join(ROOT, entry.spec), 'utf8')
      for (const word of entry.words) {
        expect(source, `${writer} says "${word}"`).toContain(word)
        expect(spec, `${entry.spec} reads "${word}"`).toContain(word)
      }
    }
  })

  it('finds each fault in planted sources, write by write, and passes over comments and strings', () => {
    const copy = (body: string, head = '') => `${head}export function C({ onStatus }: { onStatus?: (m: string) => void }) {
  const copy = async () => {
    ${body}
  }
  return <button onClick={copy}>Copy link</button>
}`
    // The flash: its words flip and nothing is heard.
    expect(copyFaults(copy("await navigator.clipboard.writeText(link); setCopied(true)")
      .replace('>Copy link<', ">{copied ? 'Copied' : 'Copy link'}<"))).toEqual([NO_CONFIRMATION, FLIPS])
    expect(copyFaults(copy('await navigator.clipboard.writeText(link)').replace('>Copy link<', ">{copied ? 'Copied!' : 'Copy link'}<"))).toEqual([
      NO_CONFIRMATION,
      FLIPS,
    ])
    expect(copyFaults(copy('await navigator.clipboard.writeText(link)').replace('>Copy link<', '>{copied ? <>Copied</> : <>Copy link</>}<'))).toEqual([
      NO_CONFIRMATION,
      FLIPS,
    ])
    // A write the scan reads however it is spelled: an optional chain, the window's navigator.
    expect(copyFaults(copy('await navigator.clipboard?.writeText(link)'))).toEqual([NO_CONFIRMATION])
    expect(copyFaults(copy('await window.navigator?.clipboard.write([item])'))).toEqual([NO_CONFIRMATION])
    // A reach it cannot follow fails until it learns it: an alias, a destructured clipboard. A read is no write.
    expect(copyFaults(copy('const board = navigator.clipboard; await board.writeText(link)'))).toEqual([UNREAD])
    expect(copyFaults(copy('const { clipboard } = navigator; await clipboard.writeText(link)'))).toEqual([UNREAD])
    expect(copyFaults(copy('setText(await navigator.clipboard.readText())'))).toEqual([])
    // Said in the toast region and through onStatus, the dialog's line: heard outside a dialog and in one.
    expect(copyFaults(copy("await navigator.clipboard.writeText(link); if (onStatus) onStatus('Invite link copied.'); else toast.success('Invite link copied')"))).toEqual([])
    expect(copyFaults(copy("navigator.clipboard.writeText(link).then(() => onStatus ? onStatus('Copied the link.') : toast.success('Invite link copied'))"))).toEqual([])
    // A toast alone, which a dialog hides, though a state named 'copied' is no words.
    expect(copyFaults(copy("await navigator.clipboard.writeText(link); setCopyState('copied'); toast.success('Invite link copied')"))).toEqual([TOAST_ONLY])
    const status = (handler: string, line = "<p role=\"status\">{copyState === 'copied' ? 'Receipt copied.' : ''}</p>") => `export function C() {
  const [copyState, setCopyState] = useState('idle')
  const [other, setOther] = useState(false)
  const copy = async () => {
    try { ${handler} } catch { setCopyState('failed') }
  }
  return <><button onClick={copy}>Copy receipt</button>${line}</>
}`
    expect(copyFaults(status("await navigator.clipboard.writeText(text); setCopyState('copied')"))).toEqual([])
    // A status line the copy never updates: the success's setter gone (the failure's alone sets it), another state set,
    // or an empty line.
    expect(copyFaults(status('await navigator.clipboard.writeText(text)'))).toEqual([NO_CONFIRMATION])
    expect(copyFaults(status('await navigator.clipboard.writeText(text); setOther(true)'))).toEqual([NO_CONFIRMATION])
    expect(copyFaults(status("await navigator.clipboard.writeText(text); setCopyState('copied')", '<p role="status" />'))).toEqual([NO_CONFIRMATION])
    // A setter or a toast before the write says nothing of it; on the failure's path, a catch clause or a rejection
    // handler, it is not the copy's.
    expect(copyFaults(status("setCopyState('copied'); await navigator.clipboard.writeText(text)"))).toEqual([NO_CONFIRMATION])
    expect(copyFaults(copy("try { await navigator.clipboard.writeText(link) } catch { onStatus('Invite link copied.') }"))).toEqual([NO_CONFIRMATION])
    expect(copyFaults(copy("navigator.clipboard.writeText(link).catch(() => onStatus('Invite link copied.'))"))).toEqual([NO_CONFIRMATION])
    expect(copyFaults(copy("navigator.clipboard.writeText(link).then(undefined, () => onStatus('Invite link copied.'))"))).toEqual([NO_CONFIRMATION])
    // A second write whose own handler is said nowhere, though another handler in the file is.
    const two = `export function C() {
  const [state, setState] = useState('idle')
  const copyMessage = async () => { await navigator.clipboard.writeText(message); setState('copied') }
  const copyLink = async () => { await navigator.clipboard.writeText(link) }
  return <><button onClick={copyMessage}>Copy message</button><button onClick={copyLink}>Copy link</button><p role="status">{state}</p></>
}`
    expect(copyFaults(two)).toEqual([NO_CONFIRMATION])
    // A confirmation in a comment confirms nothing; a write in a comment or a string is no write.
    expect(copyFaults(copy("await navigator.clipboard.writeText(link) /* onStatus('Invite link copied.') */"))).toEqual([NO_CONFIRMATION])
    expect(copyFaults("// await navigator.clipboard.writeText(link)\nconst note = 'navigator.clipboard.writeText(link)'")).toEqual([])
    // A /* inside a string opens no comment, so the write after it is read.
    expect(copyFaults(copy('await navigator.clipboard.writeText(link)', "const accept = 'image/*'\n"))).toEqual([NO_CONFIRMATION])
  })

  it("holds a dialog to its controls' onStatus, and an onStatus to a status line", () => {
    const dialog = (row: string, line = '<p role="status">{status}</p>') => `import { Modal } from '@/components/ui'
import CopyLinkButton from '@/features/admin/components/CopyLinkButton'
export function D() {
  const [status, setStatus] = useState('')
  const [other, setOther] = useState('')
  return <><Modal open onClose={close}>${row}${line}</Modal></>
}`
    expect(copyFaults(dialog('<CopyLinkButton link={link} onStatus={setStatus} />'))).toEqual([])
    // Without it the press goes to the toast region, which the dialog hides.
    expect(copyFaults(dialog('<CopyLinkButton link={link} />'))).toEqual([DIALOG_TOAST])
    // An onStatus no status line reads: another state's setter, or the line gone.
    expect(copyFaults(dialog('<CopyLinkButton link={link} onStatus={setOther} />'))).toEqual([STATUS_NOWHERE])
    expect(copyFaults(dialog('<CopyLinkButton link={link} onStatus={setStatus} />', ''))).toEqual([STATUS_NOWHERE])
    // Outside a dialog the control says its press in the toast region.
    expect(copyFaults(dialog('<CopyLinkButton link={link} />').replace(/<\/?Modal[^>]*>/g, ''))).toEqual([])
  })
})
