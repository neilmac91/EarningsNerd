import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * A control that writes to the clipboard keeps its words and confirms where a screen reader hears it (rule 12; chief
 * design on #1789 and #1791). Copy link flashed its words to "Copied" under a pinned aria-label, so its name lacked the
 * word shown (WCAG 2.5.3) and a press said nothing a screen reader hears (4.1.3), while Copy message beside it put
 * "Invite message copied" in the toast region. Words that change rename the control, and inside a live region (the
 * bulk invite summary's) are heard on top of any confirmation. So each source file that writes to the clipboard
 * confirms through the toast region (`toast.success`) or a role="status" line beside its control, as Copy filing link
 * and Copy receipt do, and no label in it flips to "Copied". The waitlist's referral Copy still flips and confirms
 * nowhere a screen reader hears; RESIDUE holds it to E244.
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

/** The code without its comments, so a comment that names a pattern neither writes nor confirms. */
const stripComments = (code: string) => code.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|\s)\/\/.*$/gm, '$1')

const WRITES = /navigator\.clipboard\.write/
const HEARD = /\btoast\.success\(|role="status"/
const FLIPS = /(["'`])Copied\1|>\s*Copied\s*</

/** What a source that writes to the clipboard lacks: a confirmation that is heard, and words that stay. */
function copyFaults(source: string): string[] {
  const code = stripComments(source)
  if (!WRITES.test(code)) return []
  return [
    ...(HEARD.test(code) ? [] : ['no confirmation a screen reader hears']),
    ...(FLIPS.test(code) ? ['a label flips to "Copied"'] : []),
  ]
}

/** The files the rule still finds at fault, each with its row. Equal, not a cap: a fix takes its entry out. */
const RESIDUE: Record<string, string[]> = {
  // E244: the waitlist success card's referral Copy flips to "Copied" and confirms nowhere a screen reader hears.
  'features/waitlist/components/WaitlistForm.tsx': ['no confirmation a screen reader hears', 'a label flips to "Copied"'],
}

const files = DIRS.flatMap((dir) => sourcesUnder(join(ROOT, dir)))

describe('a clipboard write confirms where a screen reader hears it, and its control keeps its words', () => {
  it('holds every source file that writes to the clipboard, the residue named exactly', () => {
    const found = Object.fromEntries(
      files.map((file) => [relative(ROOT, file), copyFaults(readFileSync(file, 'utf8'))] as const).filter(([, faults]) => faults.length),
    )
    expect(found).toEqual(RESIDUE)
  })

  it('reads the writers it holds', () => {
    const writers = files.filter((file) => WRITES.test(stripComments(readFileSync(file, 'utf8')))).map((file) => relative(ROOT, file))
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

  it('finds each fault in planted sources, and passes over a comment', () => {
    const flash = "await navigator.clipboard.writeText(link); setCopied(true)\nreturn <button>{copied ? 'Copied' : 'Copy link'}</button>"
    expect(copyFaults(flash)).toEqual(['no confirmation a screen reader hears', 'a label flips to "Copied"'])
    expect(copyFaults('await navigator.clipboard.writeText(link)\nreturn <p role="status" />{copied ? <>Copied</> : <>Copy link</>}')).toEqual([
      'a label flips to "Copied"',
    ])
    expect(copyFaults("await navigator.clipboard.writeText(link)\ntoast.success('Invite link copied')")).toEqual([])
    expect(copyFaults('await navigator.clipboard.writeText(text)\nreturn <p role="status">{copied ? \'Receipt copied.\' : \'\'}</p>')).toEqual([])
    expect(copyFaults("await navigator.clipboard.writeText(link) /* toast.success('Invite link copied') */")).toEqual([
      'no confirmation a screen reader hears',
    ])
    expect(copyFaults('// await navigator.clipboard.writeText(link)')).toEqual([])
  })
})
