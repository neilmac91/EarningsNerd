import { expect, test } from '@playwright/test'

test('serves the complete sitemap from the hourly route cache with no backend', async ({ request }) => {
  const first = await request.get('/sitemap.xml')
  expect(first.status()).toBe(200)
  expect(first.headers()['content-type']).toContain('application/xml')
  expect(first.headers()['cache-control']).toContain('s-maxage=3600')
  expect(await first.text()).toContain('<loc>https://www.earningsnerd.io/terms</loc>')

  const second = await request.get('/sitemap.xml')
  expect(second.headers()['x-nextjs-cache']).toBe('HIT')
  expect(second.headers()['cache-control']).toContain('s-maxage=3600')
  expect(await second.text()).toBe(await first.text())
})
