/* =============================================================================
   wordmarkSingleSource.spec.ts — guardrail (v3, Q1; backend reach, BG-27)
   -----------------------------------------------------------------------------
   components/EarningsNerdLogo.tsx is the ONE source of the two-tone wordmark
   (variant="full" | "wordmark"). Header and AuthShell hand-composed
   `Earnings<em>Nerd</em>` before v3 and drifted in size and tracking; this spec
   fails if any other file renders the italic "Nerd" half by hand.

   Outside React the wordmark has to be composed by hand, since nothing renders
   a mail or a PDF through the component: those renditions are named in
   SANCTIONED_BACKEND, and the scan of backend/app holds the list to an equality
   (D-040), so a new hand-composed rendition fails until it is named here with
   its reason, and a removed one fails until its entry goes. The PDF rendition's
   colours ("Earnings" in the ink, "Nerd" italic in brand-strong) are read from
   its rendered stylesheet by backend/tests/unit/test_export_palette_parity.py;
   the mail's are review-checked until its header port (E54). The brand
   templates (docs/brand/templates, scripts/brand/og-template.html) are artwork,
   outside this scan, as before.
============================================================================= */

import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

const ROOT = path.join(__dirname, '../..')
const REPO = path.join(ROOT, '..')
const SCAN_DIRS = ['app', 'components', 'features', 'hooks', 'lib']
const SOURCE = 'components/EarningsNerdLogo.tsx'
const HAND_ROLLED = /<em\b[^>]*>\s*Nerd\s*<\/em>/
const BACKEND = path.join(REPO, 'backend/app')
/** The renditions no React component can render, each with its reason. */
const SANCTIONED_BACKEND = [
  'backend/app/services/email_service.py', // the transactional mail's header
  'backend/app/services/pdf_branding.py', // the PDF masthead of both exports
]

function walk(dir: string, test: (name: string) => boolean, out: string[] = []): string[] {
  if (!fs.existsSync(dir)) return out
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name !== '__pycache__') walk(p, test, out)
    } else if (test(entry.name)) out.push(p)
  }
  return out
}

const handRolled = (file: string) => HAND_ROLLED.test(fs.readFileSync(file, 'utf8'))

describe('the wordmark has one source: EarningsNerdLogo', () => {
  it('no other file hand-composes the italic "Nerd"', () => {
    const offenders: string[] = []
    for (const dir of SCAN_DIRS) {
      for (const file of walk(path.join(ROOT, dir), (name) => /\.tsx?$/.test(name))) {
        const rel = path.relative(ROOT, file).split(path.sep).join('/')
        if (rel !== SOURCE && handRolled(file)) offenders.push(rel)
      }
    }
    expect(offenders, 'render <EarningsNerdLogo variant="wordmark" | "full"> instead').toEqual([])
  })

  it('the source still renders it (the pattern above stays meaningful)', () => {
    expect(fs.readFileSync(path.join(ROOT, SOURCE), 'utf8')).toMatch(HAND_ROLLED)
  })

  it('outside React, only the sanctioned backend renditions compose it', () => {
    const found = walk(BACKEND, (name) => name.endsWith('.py'))
      .filter(handRolled)
      .map((file) => path.relative(REPO, file).split(path.sep).join('/'))
      .sort()
    expect(found, 'compose the wordmark in a sanctioned rendition, or name this one in SANCTIONED_BACKEND with its reason')
      .toEqual(SANCTIONED_BACKEND)
  })

  it('the pattern reads the forms Python writes (planted probe)', () => {
    const forms = [
      '<span class="wordmark">Earnings<em>Nerd</em></span>', // the PDF masthead's markup
      '<td style="color:#1A1A17;">Earnings<em style="color:#3C6650;font-style:italic;">Nerd</em></td>', // inline styles
      'f"<td>Earnings<em class=\\"accent\\">Nerd</em></td>"', // a quoted attribute escaped in a Python string
      '"Earnings<em>\\n  Nerd\\n</em>"'.replace(/\\n/g, '\n'), // the half split across lines
    ]
    expect(forms.filter((form) => !HAND_ROLLED.test(form))).toEqual([])
    expect(HAND_ROLLED.test('<span>EarningsNerd</span>')).toBe(false) // the plain name is not the wordmark
  })
})
