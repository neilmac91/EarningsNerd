import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * The sage mark raster is one buffer written to two places by scripts/generate-brand-assets.mjs:
 * public/assets/earningsnerd-mark-sage.png, served at a fixed URL for transactional email (mail
 * clients drop inline SVG), and backend/app/assets/brand/earningsnerd-mark.png, which the Excel
 * export embeds. Regenerating one without the other would let the mail lockup and the workbook
 * drift apart, and the mark is protected (lessons/brand-the-mark-is-protected.md), so this spec
 * fails when the two files differ by a byte.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SERVED = path.join(FRONTEND, 'public/assets/earningsnerd-mark-sage.png')
const EMBEDDED = path.resolve(FRONTEND, '../backend/app/assets/brand/earningsnerd-mark.png')
const sha = (file: string) => createHash('sha256').update(readFileSync(file)).digest('hex')

describe('the served mark raster is the backend raster, byte for byte', () => {
  it('public/assets/earningsnerd-mark-sage.png equals backend/app/assets/brand/earningsnerd-mark.png', () => {
    expect(readFileSync(SERVED).length).toBeGreaterThan(0)
    expect(sha(SERVED)).toBe(sha(EMBEDDED))
  })
})
