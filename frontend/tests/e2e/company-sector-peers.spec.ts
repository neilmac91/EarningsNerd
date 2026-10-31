import { test, expect, type Locator, type Page } from '@playwright/test'
import { CHART_TOKENS } from '../../features/analysis/lib/charts/theme'
import { drawn } from '../../features/peers/lib/cohort'
import { expectInks, expectSound, hexOf, measurePlots, type Paint } from './fixtures/chartChecks'
import { openCompany, PEERS, type Theme } from './fixtures/companyPeersApi'

/**
 * The Sector peers panel mounts on the company page and draws through the trend charts' engine (E251). It shows itself
 * only once the peers endpoint answers a cohort, which production cannot until the SIC backfill runs, and renders
 * nothing otherwise, so no render test can see it go missing from the page; a fixture answers its fetcher here, so this
 * browser gate can (lessons/frontend-route-redesign-needs-a-mount-gate.md). Production builds the panel (the flag is on
 * in production's build, as for the filing page's Financial trends) and so does CI's e2e job, so on a build without the
 * flag, or without the mount, the cases that draw it fail.
 *
 * On /company/SUBX, answered by fixtures/companyPeersApi.ts with the fixture's spread (eleven companies from $416.0B to
 * $5.1B, the subject sixth, so the panel draws the top ten; tests/unit/fixtures/peers-cohorts.json, which the backend's
 * contract test holds to the service), in both themes at 390 and 1280px: the heading and the SVG of the role img named
 * "Revenue chart" mount; the
 * subject's bar computes chart-1's token and every other bar the context token; every printed value is one of the
 * fixture's, to the digit it prints; the values stop opens at the subject, and the spec's DOM checks for one card hold
 * (fixtures/chartChecks.ts: D1, D2, D3, D5, D6 at each paint's floor on the card's computed ground, the context ink among
 * the marks, D8 at full hinting, D10 under reduced motion, D14 and M6, opening with the subject's column in view); at
 * 390px the plot scrolls inside its card, a region named "Revenue chart. Scroll horizontally to view all companies.";
 * and the page does not scroll sideways. Under 200% text at 390, 360 and 320px, the page does not scroll sideways and
 * the heading, the rank line and the picker stay inside the card. With production's own answer, a company ranked alone
 * (peer_count 1, JPM's on 2026-10-31), once that answer has landed, the panel shows nothing and the filings render.
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md).
 */

const VIEWPORTS = [
  { width: 390, height: 844, isMobile: true, hasTouch: true },
  { width: 1280, height: 900, isMobile: false, hasTouch: false },
]
const THEMES: Theme[] = ['light', 'dark']
const SPREAD = PEERS.cases.spread.response
const SUBJECT = SPREAD.subject.ticker

/** The panel: the nearest section around its heading. */
const sectorPeers = (page: Page) =>
  page.getByRole('heading', { level: 2, name: 'Sector peers', exact: true }).locator('xpath=ancestor::section[1]')

/** A printed value's number and half a step of its last printed digit: "$416B" is 416e9 within 0.5e9, "$5.10B" 5.1e9
 *  within 0.005e9. */
const SCALE: Record<string, number> = { K: 1e3, M: 1e6, B: 1e9, T: 1e12 }
function printedNumber(text: string) {
  const match = /^([−-])?[^\d−-]*([\d,]+)(?:\.(\d+))?([KMBT])?[%×]?$/.exec(text.trim())
  if (!match) throw new Error(`a printed value this check cannot read: "${text}"`)
  const scale = match[4] ? SCALE[match[4]] : 1
  const digits = match[3] ?? ''
  const value = Number(`${match[2].replace(/,/g, '')}.${digits || '0'}`) * scale * (match[1] ? -1 : 1)
  return { text, value, within: 0.5 * 10 ** -digits.length * scale }
}

/** The document's widths and, for a failure message, the widest boxes past the viewport's right edge. */
const widths = (page: Page) =>
  page.evaluate(() => {
    const root = document.documentElement
    const past = [...document.querySelectorAll('body *')]
      .map((el) => ({ el, right: el.getBoundingClientRect().right }))
      .filter(({ right }) => right > root.clientWidth + 0.5)
      .sort((a, b) => b.right - a.right)
      .slice(0, 6)
      .map(({ el, right }) => `${Math.round(right)}px ${el.tagName.toLowerCase()} "${(el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 40)}"`)
    return { scrollWidth: root.scrollWidth, clientWidth: root.clientWidth, past }
  })

/** The heading row's boxes (the heading, the rank line, the picker's label and its select) against the card's content
 *  box. */
const headingRow = (card: Locator) =>
  card.evaluate((section) => {
    const style = getComputedStyle(section)
    const bounds = section.getBoundingClientRect()
    const content = { left: bounds.left + parseFloat(style.paddingLeft), right: bounds.right - parseFloat(style.paddingRight) }
    const heading = section.querySelector('h2')!
    const rank = heading.nextElementSibling
    const select = section.querySelector('select')!
    return {
      content,
      boxes: [heading, rank, select.closest('label'), select].filter((el): el is Element => el != null).map((el) => {
        const r = el.getBoundingClientRect()
        return { what: `${el.tagName.toLowerCase()} "${(el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 40)}"`, left: r.left, right: r.right }
      }),
    }
  })

test.describe.configure({ mode: 'parallel' })
// Full font hinting, headless Chrome's default (CI's): D1 and D8 run in the case that can break them.
test.use({ launchOptions: { args: ['--font-render-hinting=full'] } })

for (const { width, height, isMobile, hasTouch } of VIEWPORTS) {
  test.describe(`Sector peers on /company/${SUBJECT} at ${width}px`, () => {
    test.use({ viewport: { width, height }, isMobile, hasTouch, reducedMotion: 'reduce' })

    for (const theme of THEMES) {
      test(`${theme}: the panel mounts once its cohort lands and draws it through the engine, the subject in chart-1 and every other company in the context ink, each value the fixture's, opening at the subject`, async ({ page, baseURL }) => {
        await openCompany(page, baseURL!, 'spread', theme)
        expect(await page.evaluate(() => document.documentElement.classList.contains('dark')), `the ${theme} theme took`).toBe(theme === 'dark')
        const card = sectorPeers(page)
        await expect(card).toBeVisible()
        await expect(card.getByRole('combobox', { name: /^Metric\b/ })).toHaveValue('revenue')
        await expect(card.getByText(`${SUBJECT} ranks #6 of 11 on revenue`, { exact: true })).toBeVisible()
        const plot = card.getByTestId('peers-chart')
        const svg = plot.getByRole('img', { name: 'Revenue chart', exact: true })
        await expect(svg).toBeVisible()
        await expect(plot).not.toHaveAttribute('aria-busy')
        await page.evaluate(() => document.fonts.ready)

        // The bars, their computed paint by role: the subject chart-1, every other company the context ink.
        const tokens = CHART_TOKENS[theme]
        const drawing = await svg.evaluate((root) => ({
          bars: [...root.querySelectorAll('rect[data-series]')].map((bar) => ({ period: bar.getAttribute('data-period'), fill: getComputedStyle(bar).fill })),
          labels: [...root.querySelectorAll('text[data-text="label"]')].map((text) => text.textContent ?? ''),
        }))
        const companies = drawn(SPREAD)
        expect(drawing.bars.map((bar) => bar.period), 'a bar a company, in the answer’s order').toEqual(companies.map((entry) => entry.ticker))
        for (const bar of drawing.bars) {
          expect(hexOf(bar.fill), `${bar.period}'s computed fill`).toBe(bar.period === SUBJECT ? tokens.series[0] : tokens.context)
        }
        // Each printed value is one of the cohort's own, to the digit it prints.
        expect(drawing.labels, 'every value printed on its bar').toHaveLength(companies.length)
        const printed = drawing.labels.map(printedNumber).sort((a, b) => a.value - b.value)
        const values = companies.map((entry) => entry.value!).sort((a, b) => a - b)
        printed.forEach(({ text, value, within }, i) => {
          expect(Math.abs(value - values[i]), `"${text}" prints the fixture's ${values[i]}`).toBeLessThanOrEqual(within + 1e-9 * Math.abs(values[i]))
        })
        // The values stop opens at the subject and says who it is.
        const stop = card.getByRole('slider', { name: 'Revenue chart values', exact: true })
        await expect(stop).toHaveAttribute('aria-valuenow', '5')
        await expect(stop).toHaveAttribute('aria-valuetext', /^Synthetic Subject Corp, SUBX, this company, rank 6 of 11, FY2025, year ended December 31, 2025\. Revenue: /)

        // The spec's DOM checks for one card: its text, its marks (the context ink among them) and its inks on the card's
        // computed ground.
        const [report] = await measurePlots(card)
        const name = `Sector peers (${theme}, ${width}px)`
        expectSound({ ...report, name })
        expect(report.start, `${name}: the values stop opens at the subject`).toBe(5)
        if (width < 768) {
          expect(report.scrolls, `${name}: the spread's ten bars, the top ten of eleven, scroll inside the card on a phone`).toBe(true)
          await expect(card.getByRole('region', { name: 'Revenue chart. Scroll horizontally to view all companies.', exact: true })).toBeVisible()
        }
        const ground = await card.evaluate((section) => getComputedStyle(section).backgroundColor)
        expect(hexOf(ground), `${name}: the card is the chart surface`).toBe(tokens.surface)
        const html = await card.locator('[data-chart-text]').evaluateAll((nodes) => nodes.map((node) => ({
          what: `${node.getAttribute('data-chart-text')} "${node.textContent}"`, floor: 'text' as const, colour: getComputedStyle(node).color,
        })))
        expectInks(name, [...report.paints, ...html] as Paint[], ground)
        expect(report.paints.some((paint) => paint.floor === 'marks' && hexOf(paint.colour) === tokens.context), `${name}: D6 read the context ink`).toBe(true)

        const { scrollWidth, clientWidth, past } = await widths(page)
        expect(scrollWidth, `scrollWidth ${scrollWidth}px against clientWidth ${clientWidth}px; past the edge: ${past.join('; ') || 'nothing'}`).toBeLessThanOrEqual(clientWidth)
      })
    }
  })
}

for (const width of [390, 360, 320]) {
  test.describe(`Sector peers on /company/${SUBJECT} at ${width}px under 200% text`, () => {
    test.use({ viewport: { width, height: 844 }, isMobile: true, hasTouch: true, reducedMotion: 'reduce' })

    test('the page does not scroll sideways, and the heading, the rank line and the picker stay inside the card', async ({ page, baseURL }) => {
      await openCompany(page, baseURL!, 'spread', 'light', { doubled: true })
      await expect
        .poll(() => page.evaluate(() => getComputedStyle(document.documentElement).fontSize), { message: 'the 200% text setting took: the root computes to 32px' })
        .toBe('32px')
      const card = sectorPeers(page)
      await expect(card.getByTestId('peers-chart').getByRole('img', { name: 'Revenue chart', exact: true })).toBeVisible()
      await page.evaluate(() => document.fonts.ready)
      await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))

      const { scrollWidth, clientWidth, past } = await widths(page)
      expect(scrollWidth, `scrollWidth ${scrollWidth}px against clientWidth ${clientWidth}px; past the edge: ${past.join('; ') || 'nothing'}`).toBeLessThanOrEqual(clientWidth)
      const { content, boxes } = await headingRow(card)
      expect(boxes.map((box) => box.what).join(' | '), 'the heading row: the heading, the rank line, the picker').toMatch(/^h2 "Sector peers" \| p "SUBX ranks #6 of 11 on revenue" \| label "Metric/)
      const outside = boxes.filter((box) => box.left < content.left - 0.5 || box.right > content.right + 0.5)
        .map((box) => `${box.what} ${box.left.toFixed(1)}..${box.right.toFixed(1)}`)
      expect(outside, `inside the card's content box ${content.left.toFixed(1)}..${content.right.toFixed(1)}`).toEqual([])
    })
  })
}

test.describe('Sector peers with production’s own answer, a company ranked alone', () => {
  test.use({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' })

  test('once the answer has landed, the panel shows nothing and the filings render', async ({ page, baseURL }) => {
    const answer = PEERS.cases['production single'].response
    expect([answer.sic, answer.peer_count], 'production’s answer: no SIC code, the subject alone').toEqual([null, 1])
    const landed = page.waitForResponse((response) => new URL(response.url()).pathname === `/api/companies/${answer.ticker}/peers`)
    await openCompany(page, baseURL!, 'production single', 'light')
    expect((await landed).status()).toBe(200)
    await expect(page.getByRole('heading', { level: 2, name: 'SEC filings', exact: true })).toBeVisible()
    await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
    await expect(page.getByRole('heading', { level: 2, name: 'Sector peers', exact: true })).toHaveCount(0)
    await expect(page.getByText('This chart could not be drawn.')).toHaveCount(0)
  })
})
