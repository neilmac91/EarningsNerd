import path from 'node:path'
import fs from 'node:fs'
import { HERE, launchChromium } from './browser.mjs'
const EVID = process.env.CRITIQUE_EVIDENCE_DIR || path.join(HERE, 'evidence')
fs.mkdirSync(EVID, { recursive: true })
const { browser } = await launchChromium()
const ctx = async (vw, vh, scenario, mobile=false) => {
  const c = await browser.newContext({ viewport: { width: vw, height: vh }, isMobile: mobile, hasTouch: mobile })
  await c.addCookies([{ name: 'en_scenario', value: scenario, domain: 'localhost', path: '/', sameSite: 'Lax' }])
  await c.addInitScript(() => { try { localStorage.setItem('theme', 'light'); localStorage.setItem('en:copilot-coachmark-v1', '1'); localStorage.setItem('cookie-consent', JSON.stringify({ analytics: false, functional: true, version: 1 })) } catch {} })
  return c
}
const culprits = `(() => { const cw = document.documentElement.clientWidth; const out = []; document.querySelectorAll('body *').forEach((el) => { const r = el.getBoundingClientRect(); if (r.right > cw + 1 && r.width > 0 && r.height > 0) out.push({ tag: el.tagName, cls: String(el.className || '').slice(0, 90), right: Math.round(r.right), w: Math.round(r.width), h: Math.round(r.height) }) }); return { cw, sw: document.documentElement.scrollWidth, n: out.length, top: out.slice(0, 10) } })()`
const out = {}
for (const w of [720, 640, 600, 480]) {
  const c = await ctx(w, 900, 'anon'); const p = await c.newPage()
  await p.goto('http://localhost:3000/filing/3', { waitUntil: 'networkidle' }); await p.waitForTimeout(600)
  out[`reflow-${w}`] = await p.evaluate(culprits); await c.close()
}
// keyboard popover: Tab from "Copy filing link" into the first chip, count popovers, screenshot
{
  const c = await ctx(1440, 900, 'pro'); const p = await c.newPage()
  await p.goto('http://localhost:3000/filing/3', { waitUntil: 'networkidle' }); await p.waitForTimeout(600)
  await p.getByRole('button', { name: 'Copy filing link' }).focus()
  await p.keyboard.press('Tab'); await p.waitForTimeout(500)
  const a = await p.evaluate(() => ({ active: document.activeElement?.getAttribute('aria-label'), expanded: document.activeElement?.getAttribute('aria-expanded'), groups: document.querySelectorAll('[role=group][aria-label="Source detail"]').length, scrollY: window.scrollY }))
  await p.screenshot({ path: EVID + '/V-kbd-popover-tab1.png' })
  await p.keyboard.press('Tab'); await p.waitForTimeout(500)
  const b = await p.evaluate(() => ({ active: document.activeElement?.getAttribute('aria-label'), expanded: document.activeElement?.getAttribute('aria-expanded'), groups: document.querySelectorAll('[role=group][aria-label="Source detail"]').length, groupHasLink: !!document.querySelector('[role=group][aria-label="Source detail"] a'), scrollY: window.scrollY }))
  await p.screenshot({ path: EVID + '/V-kbd-popover-tab2.png' })
  // can Tab ever land inside the popover?
  const trail = []
  for (let i = 0; i < 4; i++) { await p.keyboard.press('Tab'); await p.waitForTimeout(250); trail.push(await p.evaluate(() => ({ tag: document.activeElement?.tagName, label: document.activeElement?.getAttribute('aria-label') || document.activeElement?.textContent?.trim().slice(0, 30), inPopover: !!document.activeElement?.closest('[role=group][aria-label="Source detail"]'), groups: document.querySelectorAll('[role=group][aria-label="Source detail"]').length }))) }
  out['kbd-popover'] = { afterTab1: a, afterTab2: b, trail }
  // Enter on a chip with pane closed: what changes?
  await p.getByRole('button', { name: 'Source: Verified in filing' }).first().focus(); await p.keyboard.press('Enter'); await p.waitForTimeout(1200)
  out['enter-on-chip'] = await p.evaluate(() => { const d = document.querySelector('[role=dialog][aria-label="Ask this Filing"]'); return { ariaHidden: d?.getAttribute('aria-hidden'), display: d ? getComputedStyle(d).display : null, selectedTab: document.querySelector('[role=tab][aria-selected="true"]')?.textContent?.trim(), scrollY: window.scrollY, active: document.activeElement?.getAttribute('aria-label') } })
  await c.close()
}
// company page: row CTAs
{
  const c = await ctx(1440, 900, 'anon'); const p = await c.newPage()
  await p.goto('http://localhost:3000/company/AAPL', { waitUntil: 'networkidle' }); await p.waitForTimeout(600)
  out['company-rows'] = await p.evaluate(() => [...document.querySelectorAll('a[href^="/filing/"]')].slice(0, 8).map((x) => x.textContent.trim().slice(0, 50) + ' -> ' + x.getAttribute('href')))
  await c.close()
}
// analysis ?ticker=
{
  const c = await ctx(1440, 900, 'pro'); const p = await c.newPage()
  await p.goto('http://localhost:3000/analysis?ticker=AAPL', { waitUntil: 'networkidle' }); await p.waitForTimeout(2500)
  out['analysis'] = await p.evaluate(() => ({ h1: document.querySelector('h1')?.textContent, hasChart: !!document.querySelector('.recharts-wrapper'), text: document.body.innerText.slice(0, 600) }))
  await c.close()
}
console.log(JSON.stringify(out, null, 1))
await browser.close()
