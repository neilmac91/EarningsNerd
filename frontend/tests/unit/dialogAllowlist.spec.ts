/* =============================================================================
   dialogAllowlist.spec.ts — guardrail (v3, DS-04)
   -----------------------------------------------------------------------------
   role="dialog" ships ONLY through ui/Modal plus the documented bespoke sheets
   (the copilot rail / filing viewer / workspace sheet own focus traps via
   useSheetFocusTrap; SourceTrace's mobile source-detail sheet likewise).
   Everything else composes <Modal>. This spec IS the Batch-2 done-gate: it
   fails until UpgradeModal, EmailVerificationModal, Resend/RevokeShareModal,
   FeedbackWidget and DayDetailDialog are migrated.
============================================================================= */

import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

const ROOT = path.join(__dirname, '../..')
const SCAN_DIRS = ['app', 'components', 'features']
const ALLOW = new Set([
  'components/ui/Modal.tsx',
  'features/filings/components/copilot/AskCopilotRail.tsx',
  'features/filings/components/copilot/FilingViewer.tsx',
  'features/filings/components/copilot/FilingWorkspace.tsx',
  'features/filings/components/SourceTrace.tsx',
])

function walk(dir: string, out: string[] = []): string[] {
  if (!fs.existsSync(dir)) return out
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else if (/\.tsx?$/.test(entry.name)) out.push(p)
  }
  return out
}

describe('dialogs ship only through ui/Modal (or the documented sheets)', () => {
  it('role="dialog" appears only in the allowlist', () => {
    const offenders: string[] = []
    for (const dir of SCAN_DIRS) {
      for (const file of walk(path.join(ROOT, dir))) {
        if (!fs.readFileSync(file, 'utf8').includes('role="dialog"')) continue
        const rel = path.relative(ROOT, file).split(path.sep).join('/')
        if (!ALLOW.has(rel)) offenders.push(rel)
      }
    }
    expect(offenders).toEqual([])
  })
})
