import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import ts from 'typescript'
import { describe, expect, it } from 'vitest'

/**
 * A control that writes to the clipboard keeps its words and confirms where a screen reader hears it (rule 12; chief
 * design on #1789 and #1791). Copy link flashed its words to "Copied" under a pinned aria-label, so its name lacked the
 * word shown (WCAG 2.5.3) and a press said nothing a screen reader hears (4.1.3), while Copy message beside it put
 * "Invite message copied" in the toast region. Words that change rename the control, and inside a live region (the
 * bulk invite summary's) are heard on top of any confirmation.
 *
 * The scan reads each source file under app, components, features and lib as TypeScript, so a comment or a string
 * that only looks like code counts for nothing. Each clipboard write (`navigator.clipboard.writeText` or `.write`)
 * confirms where it is heard, on its own path: after the write, in the function that writes and outside a catch
 * clause, it calls `toast.success(…)`, the toast region, or the setter of a `useState` whose value a `role="status"`
 * element of the file reads, as Copy filing link and Copy receipt confirm theirs (Codex on #1793: a status line the
 * copy never updates says nothing). And no words in a file that writes to the clipboard read "Copied", with or
 * without its stop, as a label would (a state named 'copied' is no words): a label that flips to them renames its
 * control. The waitlist's referral Copy still flips and confirms nowhere a screen reader hears; RESIDUE holds it to
 * E244.
 */

const ROOT = join(__dirname, '..', '..')
const DIRS = ['app', 'components', 'features', 'lib']

function sourcesUnder(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) return entry.name === 'node_modules' ? [] : sourcesUnder(path)
    return /\.tsx?$/.test(entry.name) ? [path] : []
  })
}

const NO_CONFIRMATION = 'a clipboard write with no confirmation a screen reader hears'
const FLIPS = 'a label flips to "Copied"'

const isWrite = (node: ts.Node): node is ts.CallExpression =>
  ts.isCallExpression(node) && /(^|\.)navigator\.clipboard\.write(Text)?$/.test(node.expression.getText())

/** The innermost function around a node: the handler a clipboard write runs in. */
function enclosingFunction(node: ts.Node): ts.Node {
  for (let at = node.parent; at; at = at.parent) if (ts.isFunctionLike(at)) return at
  return node.getSourceFile()
}

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

/** Inside a catch clause between the node and the function that holds it: the failure's path, not the copy's. */
function inCatch(node: ts.Node, fn: ts.Node): boolean {
  for (let at = node.parent; at && at !== fn; at = at.parent) if (ts.isCatchClause(at)) return true
  return false
}

const hasStatusRole = (attributes: ts.JsxAttributes) =>
  attributes.properties.some(
    (a) => ts.isJsxAttribute(a) && a.name.getText() === 'role' && !!a.initializer && ts.isStringLiteral(a.initializer) && a.initializer.text === 'status',
  )

/**
 * What a source that writes to the clipboard lacks: a confirmation each write's reader hears, and words that stay.
 * A write is heard when, after it in the function that writes and outside a catch clause (so on the copy's own path,
 * not the failure's), it calls `toast.success(…)` or the setter of a `useState` whose value a `role="status"` element
 * of the file reads: a status line with nothing the handler sets says nothing.
 */
function copyFaults(source: string, fileName = 'source.tsx'): string[] {
  const sf = ts.createSourceFile(fileName, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const writes: ts.CallExpression[] = []
  const setters = new Map<string, string>()
  const spoken = new Set<string>()
  let flips = false
  const visit = (node: ts.Node) => {
    if (isWrite(node)) writes.push(node)
    // const [value, setValue] = useState(…)
    if (ts.isVariableDeclaration(node) && ts.isArrayBindingPattern(node.name) && node.initializer && ts.isCallExpression(node.initializer)
      && /(^|\.)useState$/.test(node.initializer.expression.getText())) {
      const [value, setter] = node.name.elements
      if (value && setter && ts.isBindingElement(value) && ts.isBindingElement(setter) && ts.isIdentifier(value.name) && ts.isIdentifier(setter.name)) {
        setters.set(setter.name.text, value.name.text)
      }
    }
    // Every name a status line reads.
    const element = ts.isJsxElement(node) ? node.openingElement : ts.isJsxSelfClosingElement(node) ? node : null
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
  if (writes.length === 0) return []
  const confirms = (write: ts.CallExpression) => {
    const fn = enclosingFunction(write)
    return contains(fn, (n) => {
      if (!ts.isCallExpression(n) || n.getStart() < write.getEnd() || inCatch(n, fn)) return false
      const callee = n.expression.getText()
      if (callee === 'toast.success') return true
      const value = setters.get(callee)
      return value !== undefined && spoken.has(value)
    })
  }
  return [...(writes.every(confirms) ? [] : [NO_CONFIRMATION]), ...(flips ? [FLIPS] : [])]
}

/** The files the rule still finds at fault, each with its row. Equal, not a cap: a fix takes its entry out. */
const RESIDUE: Record<string, string[]> = {
  // E244: the waitlist success card's referral Copy flips to "Copied" and confirms nowhere a screen reader hears.
  'features/waitlist/components/WaitlistForm.tsx': [NO_CONFIRMATION, FLIPS],
}

const files = DIRS.flatMap((dir) => sourcesUnder(join(ROOT, dir)))

describe('a clipboard write confirms where a screen reader hears it, and its control keeps its words', () => {
  it('holds every source file that writes to the clipboard, the residue named exactly', () => {
    const found = Object.fromEntries(
      files
        .map((file) => [relative(ROOT, file), copyFaults(readFileSync(file, 'utf8'), file)] as const)
        .filter(([, faults]) => faults.length),
    )
    expect(found).toEqual(RESIDUE)
  })

  it('reads the writers it holds', () => {
    const writers = files
      .filter((file) => {
        const sf = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
        return contains(sf, isWrite)
      })
      .map((file) => relative(ROOT, file))
    expect(writers).toEqual(
      expect.arrayContaining([
        'features/admin/components/CopyLinkButton.tsx',
        'features/admin/components/ShareInvite.tsx',
        'features/filings/components/WordingChanges.tsx',
        'features/summaries/components/SummaryActionsBar.tsx',
        'features/waitlist/components/WaitlistForm.tsx',
      ]),
    )
  })

  it('finds each fault in planted sources, write by write, and passes over comments and strings', () => {
    const copy = (body: string) => `export function C() {\n  const copy = async () => {\n    ${body}\n  }\n  return <button onClick={copy}>Copy link</button>\n}`
    // The flash: its words flip and nothing is heard.
    expect(copyFaults(copy("await navigator.clipboard.writeText(link); setCopied(true)")
      .replace('>Copy link<', ">{copied ? 'Copied' : 'Copy link'}<"))).toEqual([NO_CONFIRMATION, FLIPS])
    expect(copyFaults(copy("await navigator.clipboard.writeText(link)").replace('>Copy link<', ">{copied ? 'Copied!' : 'Copy link'}<"))).toEqual([
      NO_CONFIRMATION,
      FLIPS,
    ])
    expect(copyFaults(copy('await navigator.clipboard.writeText(link)').replace('>Copy link<', '>{copied ? <>Copied</> : <>Copy link</>}<'))).toEqual([
      NO_CONFIRMATION,
      FLIPS,
    ])
    // Heard: a success toast after the write, or the setter of the state a status line reads.
    expect(copyFaults(copy("await navigator.clipboard.writeText(link); toast.success('Invite link copied')"))).toEqual([])
    expect(copyFaults(copy("navigator.clipboard.writeText(link).then(() => toast.success('Invite link copied'))"))).toEqual([])
    // A state named 'copied' is no words.
    expect(copyFaults(copy("await navigator.clipboard.writeText(link); setCopyState('copied'); toast.success('Invite link copied')"))).toEqual([])
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
    // A setter or a toast before the write says nothing of it; a toast on the failure's path is not the copy's.
    expect(copyFaults(status("setCopyState('copied'); await navigator.clipboard.writeText(text)"))).toEqual([NO_CONFIRMATION])
    expect(copyFaults(copy("try { await navigator.clipboard.writeText(link) } catch { toast.success('Invite link copied') }"))).toEqual([NO_CONFIRMATION])
    // A second write whose own handler confirms nothing, though another handler in the file toasts.
    const two = `export function C() {
  const copyMessage = async () => { await navigator.clipboard.writeText(message); toast.success('Invite message copied') }
  const copyLink = async () => { await navigator.clipboard.writeText(link) }
  return <><button onClick={copyMessage}>Copy message</button><button onClick={copyLink}>Copy link</button></>
}`
    expect(copyFaults(two)).toEqual([NO_CONFIRMATION])
    // A toast in a comment confirms nothing; a write in a comment or a string is no write.
    expect(copyFaults(copy("await navigator.clipboard.writeText(link) /* toast.success('Invite link copied') */"))).toEqual([NO_CONFIRMATION])
    expect(copyFaults("// await navigator.clipboard.writeText(link)\nconst note = 'navigator.clipboard.writeText(link)'")).toEqual([])
    // A /* inside a string opens no comment, so the write after it is read.
    expect(copyFaults(`const accept = 'image/*'\n${copy('await navigator.clipboard.writeText(link)')}`)).toEqual([NO_CONFIRMATION])
  })
})
