import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * A published asset URL stays where it was published (CLAUDE.md rule 12; frontend/public/assets/
 * LOGO_README.md › Rules). Transactional email shows its images by address, a sent message keeps those
 * addresses for as long as it is kept, and nobody can edit it after sending, so renaming, moving or
 * removing one of these files breaks the image in every message already delivered. This list is the
 * register of published paths; each is served from frontend/public at the same path.
 */
const PUBLISHED = [
  // The mark in the transactional mail header (docs/brand/templates/email-header.html, ported into
  // backend/app/services/email_service.py), the same bytes as the Excel export's raster.
  '/assets/earningsnerd-mark-sage.png',
]

const PUBLIC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../public')
const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])

describe('published asset URLs', () => {
  for (const url of PUBLISHED) {
    it(`${url} is still served from frontend/public`, () => {
      const file = path.join(PUBLIC, url)
      expect(existsSync(file), `${url} is referenced by sent email: keep the file at this path`).toBe(true)
      if (url.endsWith('.png')) expect(readFileSync(file).subarray(0, 8).equals(PNG_SIGNATURE), `${url} is no longer a PNG`).toBe(true)
    })
  }
})
