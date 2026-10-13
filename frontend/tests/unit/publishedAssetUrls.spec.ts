import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { NextRequest } from 'next/server'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { middleware } from '@/middleware'

/**
 * A published asset URL stays where it was published (CLAUDE.md rule 12;
 * frontend/public/assets/LOGO_README.md › Rules). Transactional email shows its images by
 * address, a sent message keeps those addresses for as long as it is kept, and nobody can edit it
 * after sending, so renaming, moving or removing one of these files, or redirecting its path,
 * breaks the image in every message already delivered. This list is the register of published
 * paths: a change that puts a new asset path in mail adds it here in the same PR. Each path must
 * be a file in frontend/public (a PNG where it is one) and pass middleware.ts in both waitlist
 * modes; a redirect or rewrite in next.config.js or vercel.json, and the image itself, are
 * review-checked.
 */
const PUBLISHED = [
  // The mark in the transactional mail header (docs/brand/templates/email-header.html) once its
  // port into backend/app/services/email_service.py ships; the Excel export's raster, same bytes.
  '/assets/earningsnerd-mark-sage.png',
]

const PUBLIC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../public')
const PNG_SIGNATURE = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
// middleware.ts gates every path outside its allow-lists unless WAITLIST_MODE is 'false'.
const WAITLIST_MODES = ['true', 'false']
const SENT = 'is referenced by sent email'

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('published asset URLs', () => {
  for (const url of PUBLISHED) {
    it(`${url} is still a file in frontend/public`, () => {
      const file = path.join(PUBLIC, url)
      expect(existsSync(file), `${url} ${SENT}: keep the file at this path`).toBe(true)
      if (url.endsWith('.png')) {
        const signature = readFileSync(file).subarray(0, 8)
        expect(signature.equals(PNG_SIGNATURE), `${url} is no longer a PNG`).toBe(true)
      }
    })

    it.each(WAITLIST_MODES)(`${url} passes the middleware with WAITLIST_MODE=%s`, (mode) => {
      vi.stubEnv('WAITLIST_MODE', mode)
      const res = middleware(new NextRequest(new URL(url, 'https://www.earningsnerd.io')))
      expect(res.headers.get('location'), `${url} ${SENT}: never redirect it`).toBeNull()
      expect(res.headers.get('x-middleware-next'), `${url} ${SENT}: pass it through`).toBe('1')
    })
  }
})
