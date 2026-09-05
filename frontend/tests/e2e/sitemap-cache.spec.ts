import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
import path from 'node:path'

test('serves the complete sitemap from the hourly route cache with no backend', async ({ request }) => {
  // Metadata route handlers set their own browser Cache-Control header. The prerender manifest
  // records Next's server-side ISR lifetime; the HTTP cache hit below proves that cache is used.
  const manifest = JSON.parse(readFileSync(path.resolve(__dirname, '../../.next/prerender-manifest.json'), 'utf8'))
  expect(manifest.routes['/sitemap.xml']).toMatchObject({ initialRevalidateSeconds: 3600 })
  const first = await request.get('/sitemap.xml')
  expect(first.status()).toBe(200)
  expect(first.headers()['content-type']).toContain('application/xml')
  expect(await first.text()).toContain('<loc>https://www.earningsnerd.io/terms</loc>')

  const second = await request.get('/sitemap.xml')
  expect(second.headers()['x-nextjs-cache']).toBe('HIT')
  expect(await second.text()).toBe(await first.text())
})
