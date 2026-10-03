/* =============================================================================
   designExportRetired.spec.ts — guardrail (v3, Q2 / MIGRATION-v3 §d)
   -----------------------------------------------------------------------------
   The Claude Design landing export (mocks, support.js, a vendored `_ds/`
   design-system snapshot, verification screenshots) left the app tree; it is
   archived in git history at 02628e5 until the upstream design-system sync
   publishes it. Only RATIONALE.md stays, because app code cites it. Never
   re-vendor a design export or `_ds` snapshot under frontend/design — link the
   published package instead.
============================================================================= */

import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

const ROOT = path.join(__dirname, '../..')
const DESIGN_DIR = path.join(ROOT, 'design')

function walk(dir: string, out: string[] = []): string[] {
  if (!fs.existsSync(dir)) return out
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === '.DS_Store') continue // Finder metadata on a local checkout, never committed
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(p, out)
    else out.push(path.relative(ROOT, p).split(path.sep).join('/'))
  }
  return out
}

describe('the design export stays out of the app tree', () => {
  it('frontend/design holds only the cited RATIONALE.md', () => {
    expect(walk(DESIGN_DIR), 'archive design exports outside the app (see RATIONALE.md)').toEqual([
      'design/landing-redesign/RATIONALE.md',
    ])
  })
})
