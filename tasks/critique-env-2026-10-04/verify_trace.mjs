import path from 'node:path'
import { pathToFileURL } from 'node:url'
const HERE = path.dirname(new URL(import.meta.url).pathname)
const EVID = process.env.CRITIQUE_EVIDENCE_DIR || path.join(HERE, 'evidence')
const { chromium } = await import(pathToFileURL(path.join(HERE, '..', '..', 'frontend/node_modules/@playwright/test/index.mjs')).href)
const browser = await chromium.launch({ headless: true, executablePath: '/opt/pw-browsers/chromium' })
const run = async (name, { consent, mobile, method }) => {
  const c = await browser.newContext({ viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 }, isMobile: !!mobile, hasTouch: !!mobile })
  await c.addCookies([{ name: 'en_scenario', value: 'pro', domain: 'localhost', path: '/', sameSite: 'Lax' }])
  await c.addInitScript((consent) => { try { localStorage.setItem('theme', 'light'); localStorage.setItem('en:copilot-coachmark-v1', '1'); if (consent) localStorage.setItem('cookie-consent', JSON.stringify({ analytics: false, functional: true, version: 1 })) } catch {} }, consent)
  const p = await c.newPage(); await p.goto('http://localhost:3000/filing/3', { waitUntil: 'networkidle' }); await p.waitForTimeout(700)
  const chip = p.getByRole('button', { name: 'Source: Verified in filing' }).first()
  await chip.scrollIntoViewIfNeeded(); await p.waitForTimeout(300)
  const state = () => p.evaluate(() => { const d = document.querySelector('[role=dialog][aria-label="Ask this Filing"]'); const r = d?.getBoundingClientRect(); return { ariaHidden: d?.getAttribute('aria-hidden'), display: d ? getComputedStyle(d).display : null, rect: r ? { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) } : null, selectedTab: document.querySelector('[role=tab][aria-selected="true"]')?.textContent?.trim(), emptyState: !!document.body.innerText.includes('not available to view in-app'), sourceSheet: document.querySelectorAll('[role=dialog][aria-label="Source detail"]').length } })
  const before = await state()
  if (method === 'click') await chip.click(); else if (method === 'tap') await chip.tap(); else { await chip.focus(); await p.keyboard.press('Enter') }
  await p.waitForTimeout(2500)
  const after = await state()
  await p.screenshot({ path: `${EVID}/V-trace-${name}.png` })
  await c.close(); return { name, before, after }
}
const out = []
out.push(await run('desktop-consented-click', { consent: true, method: 'click' }))
out.push(await run('desktop-noconsent-click', { consent: false, method: 'click' }))
out.push(await run('desktop-consented-enter', { consent: true, method: 'enter' }))
out.push(await run('mobile-consented-tap', { consent: true, mobile: true, method: 'tap' }))
out.push(await run('mobile-noconsent-tap', { consent: false, mobile: true, method: 'tap' }))
console.log(JSON.stringify(out, null, 1)); await browser.close()
