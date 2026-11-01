import { test, expect, type Locator, type Page } from '@playwright/test'
import { CHART_TOKENS } from '../../features/analysis/lib/charts/theme'
import { expectInks, expectSound, hexOf, measurePlots, type Paint } from './fixtures/chartChecks'
import { MARKERS, servedHolding } from './fixtures/companyBuild'
import { openCompany, PEERS, type Theme } from './fixtures/companyPeersApi'

/**
 * The Sector peers panel mounts on the company page and draws through the trend charts' engine (E251). It shows itself
 * only once the peers endpoint answers a cohort, as production has since the SIC backfill of 2026-10-31, and renders
 * nothing otherwise, so no render test can see it go missing from the page; a fixture answers its fetcher here, so this
 * browser gate can (lessons/frontend-route-redesign-needs-a-mount-gate.md). Production builds the panel (the flag is on
 * in production's build, as for the filing page's Financial trends) and so does CI's e2e job, so on a build without the
 * flag, or without the mount, the cases that draw it fail.
 *
 * On /company/SUBX, answered by fixtures/companyPeersApi.ts with the fixture's spread (eleven companies from $416.0B to
 * $5.1B, the subject sixth, all of which the panel's eleven slots draw; tests/unit/fixtures/peers-cohorts.json, which the
 * backend's contract test holds to the service), in both themes at 390 and 1280px: the heading and the SVG of the role
 * img named "Revenue chart" mount; the subject's bar computes chart-1's token and every other bar the context token; a
 * bar a company, TNYX, the eleventh, among them; every printed value is one of the
 * fixture's, to the digit it prints; the values stop opens at the subject, and the spec's DOM checks for one card hold
 * (fixtures/chartChecks.ts: D1, D2, D3, D5, D6 at each paint's floor on the card's computed ground, none faded, the
 * context ink among the marks, D8 at full hinting, D10 under reduced motion, D14 and M6, the values stop and the open
 * column held to the subject's index in the fixture); at 390px the plot scrolls inside its card, a region named "Revenue
 * chart. Scroll horizontally to view all companies."; and the page does not scroll sideways. The start in a browser
 * (E251's PR 1 rule, TrendChartPlot): at 300 and 390px a subject's column opens centred as far as the scroll goes, the
 * spread's first company at the scroll's start on the plot's own axis with no sticky gutter, its sixth scrolled with the
 * gutter shown, its tenth at the scroll's end, and near-equal's fourth at the scroll's start at 390px and scrolled at
 * 300px, whose plot's view is 230px; at 1280px each fits its card. A broken run (E258), at 390 and 1280px: where the chart leaves
 * out a company ranked above the subject it draws after the top ('cap', 'cap, tie at the tenth'), the step to the subject's
 * tick is three quarters of a slot wider than every other; where it leaves out none ranked above it, a tie included ('cap, subject
 * eleventh', 'cap, all tied'), every step is a slot; the DOM checks hold over each; and at 1280px the subject's column as
 * the checks read it is the one its hover wash paints. The widest slot (E266): every case's slot is no wider than 104 px,
 * and at 390 and 1280px the pair's two bars stand 104 px apart in a plot narrower than its card, at its left, with the
 * subject's tooltip at 1280px past the plot's right edge, inside the card. On a phone under 200% text at 390 and 320px
 * (E267), the subject's tooltip stands taller than its plot and covers the next company's bar; a tap there closes it,
 * and the next tap pins that company's tooltip. Under 200% text at 390, 360 and 320px, the page does not scroll sideways and
 * the heading, the rank line and the picker stay inside the card. While a metric picked loads, and once its answer
 * draws no chart, the heading row keeps its height, at 390 and 1280px. With production's own answer, a company ranked
 * alone (peer_count 1, JPM's on 2026-10-31), the panel never asks for the card's chunk: once the page has handled that
 * answer (markPeersSettled below, a mark the read's own end leaves), no script holding the card is in the document or was
 * requested, the panel shows nothing and the filings render; the spread, at the same mark, has asked for it, so the
 * mark comes after the gate's decision. CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md).
 */

const VIEWPORTS = [
  { width: 390, height: 844, isMobile: true, hasTouch: true },
  { width: 1280, height: 900, isMobile: false, hasTouch: false },
]
const THEMES: Theme[] = ['light', 'dark']
const SPREAD = PEERS.cases.spread.response
const SUBJECT = SPREAD.subject.ticker
/** The widest a company's slot gets (E266, chief design on #1879), written out so the checks hold the plot to the ruling
 *  rather than to the panel's own constant: every case here passes it to expectSound. */
const MAX_SLOT = 104

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
        // Every company of the eleven, each a slot of its own: the answer's own list, not the panel's rule for it.
        const companies = SPREAD.peers
        expect(companies, 'eleven companies, each with a value').toHaveLength(11)
        expect(drawing.bars.map((bar) => bar.period), 'a bar a company, all eleven, in the answer’s order').toEqual(companies.map((entry) => entry.ticker))
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
        expectSound({ ...report, name }, { start: SPREAD.peers.findIndex((entry) => entry.is_subject), maxSlot: MAX_SLOT })
        if (width < 768) {
          expect(report.scrolls, `${name}: the spread's eleven bars scroll inside the card on a phone`).toBe(true)
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

/** Where each start opens on a phone, by PR 1's rule (TrendChartPlot): its column's centre, less half the plot's own
 *  gutter, less half the view, clamped to the scroll's range. "start" is the scroll's start, on the plot's own axis
 *  with no sticky gutter; "end" the scroll's end; "scrolled" between, the gutter shown. A start the fixture names, by the
 *  subject's index in its answer, never read off the page under test. */
type Opens = 'start' | 'scrolled' | 'end'
const STARTS: { name: string; opens: Record<300 | 390, Opens> }[] = [
  // A sector's largest company: its centred scroll falls before 0.
  { name: 'spread, subject first', opens: { 300: 'start', 390: 'start' } },
  // Near-equal's fourth: before 0 in the 390px page's 309px view (−10.5 px, as PR 1 measured −6 px in a 300px view), so
  // at the scroll's start; the 300px page's view is 230px, where it falls after 0 (+29 px) and opens scrolled.
  { name: 'near-equal', opens: { 300: 'scrolled', 390: 'start' } },
  // The spread's sixth: its column fits the first view, yet it opens centred, scrolled.
  { name: 'spread', opens: { 300: 'scrolled', 390: 'scrolled' } },
  // The spread's tenth: its centred scroll runs past the scroll's end.
  { name: 'spread, subject tenth', opens: { 300: 'end', 390: 'end' } },
]

for (const width of [300, 390, 1280] as const) {
  test.describe(`Sector peers' start at ${width}px`, () => {
    test.use({ viewport: { width, height: 900 }, isMobile: width < 768, hasTouch: width < 768, reducedMotion: 'reduce' })

    for (const { name, opens } of STARTS) {
      const start = PEERS.cases[name].response.peers.findIndex((entry) => entry.is_subject)
      const where = width === 1280 ? 'fits its card' : { start: 'opens at the scroll’s start, no sticky gutter', scrolled: 'opens scrolled, its column centred, the sticky gutter shown', end: 'opens at the scroll’s end' }[opens[width]]
      test(`${name}: the values stop and the open column are the subject's, company ${start + 1}; it ${where}`, async ({ page, baseURL }) => {
        await openCompany(page, baseURL!, name, 'light')
        const card = sectorPeers(page)
        const plot = card.getByTestId('peers-chart')
        await expect(plot.getByRole('img', { name: 'Revenue chart', exact: true })).toBeVisible()
        await expect(plot).not.toHaveAttribute('aria-busy')
        await page.evaluate(() => document.fonts.ready)
        await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
        const [report] = await measurePlots(card)
        const label = `${name} at ${width}px`
        expectSound({ ...report, name: label }, { start, maxSlot: MAX_SLOT })
        if (width === 1280) {
          expect(report.scrolls, `${label}: fits its card`).toBe(false)
          return
        }
        expect(report.scrolls, `${label}: scrolls inside its card`).toBe(true)
        // The rule, from the plot's own geometry: the column's centre in the scroll's coordinates, the plot's own gutter
        // (its plot rect's left, data-plot), the view and the scroll's range.
        const plotLeft = await plot.locator('[data-plot]').first().evaluate((group) => Number(group.getAttribute('data-plot')!.split(' ')[0]))
        const column = report.columns[start]
        const range = report.scrollLeft + report.fromNewest
        const centred = (column.left + column.right) / 2 + report.scrollLeft - plotLeft / 2 - report.viewportWidth / 2
        const rule = Math.max(0, Math.min(range, centred))
        expect(Math.abs(report.scrollLeft - rule), `${label}: opens at ${report.scrollLeft}px, the rule's ${rule.toFixed(1)} (centred ${centred.toFixed(1)}, range ${range})`).toBeLessThanOrEqual(1)
        const opened: Opens = report.scrollLeft <= 0 ? 'start' : report.fromNewest <= 1 ? 'end' : 'scrolled'
        expect(opened, `${label}: where it opens`).toBe(opens[width])
        expect(report.gutter != null, `${label}: the sticky gutter exactly when scrolled`).toBe(opened !== 'start')
      })
    }
  })
}

// E258: where the chart leaves out a company ranked above the subject it draws after the top, a gap of three quarters of
// a slot stands before the subject, so the bars never read it as next in rank; a cut that leaves out no company ranked above it, a tie
// included, draws its bars a slot apart. The companies each case draws are written out, so the check reads the plot's
// own ticks against them rather than the panel's own logic.
const BREAKS: { name: string; drawn: string; gap: boolean }[] = [
  { name: 'cap', drawn: 'ABCDEFGHIJM', gap: true },
  { name: 'cap, tie at the tenth', drawn: 'ABCDEFGHIM', gap: true },
  { name: 'cap, subject eleventh', drawn: 'ABCDEFGHIJK', gap: false },
  { name: 'cap, all tied', drawn: 'ABCDEFGHIJL', gap: false },
]

for (const width of [390, 1280] as const) {
  test.describe(`Sector peers' run at ${width}px`, () => {
    test.use({ viewport: { width, height: 900 }, isMobile: width < 768, hasTouch: width < 768, reducedMotion: 'reduce' })

    for (const { name, drawn, gap } of BREAKS) {
      const tickers = [...drawn].map((letter) => `CAP${letter}`)
      const subject = PEERS.cases[name].response.subject.ticker
      test(`${name}: ${gap ? `three quarters of a slot more before ${subject}, drawn after the top` : 'its bars a slot apart'}, and the plot sound`, async ({ page, baseURL }) => {
        await openCompany(page, baseURL!, name, 'light')
        const card = sectorPeers(page)
        const plot = card.getByTestId('peers-chart')
        await expect(plot.getByRole('img', { name: 'Revenue chart', exact: true })).toBeVisible()
        await expect(plot).not.toHaveAttribute('aria-busy')
        await page.evaluate(() => document.fonts.ready)
        await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
        const label = `${name} at ${width}px`
        const [report] = await measurePlots(card)
        expectSound({ ...report, name: label }, { start: tickers.indexOf(subject), maxSlot: MAX_SLOT })
        const ticks = await plot.getByRole('img', { name: 'Revenue chart', exact: true }).locator('text[data-text="x"]').evaluateAll((nodes) =>
          nodes.map((node) => ({ ticker: node.textContent, x: Number(node.getAttribute('x')) })))
        expect(ticks.map((tick) => tick.ticker), `${label}: a tick a company drawn`).toEqual(tickers)
        const steps = ticks.slice(1).map((tick, i) => tick.x - ticks[i].x)
        const slot = Math.min(...steps)
        expect(steps.map((step) => Math.round((step / slot) * 100) / 100), `${label}: each step between neighbouring ticks, in slots`)
          .toEqual(steps.map((_, i) => (gap && i === steps.length - 1 ? 1.75 : 1)))
        // The subject's column as the checks read it (fixtures/chartChecks.ts: a slot is the narrowest step between ticks)
        // is the one its hover wash paints; the plot's width over its ticks would miss it on each side across a seam. A
        // hover needs a pointer, so the desktop width alone runs it, where the plot fits its card.
        if (width === 1280) {
          const svg = plot.getByRole('img', { name: 'Revenue chart', exact: true })
          await svg.scrollIntoViewIfNeeded()
          const box = (await svg.boundingBox())!
          const at = tickers.indexOf(subject)
          await page.mouse.move(box.x + ticks[at].x, box.y + box.height / 2)
          const wash = plot.locator('[data-chart-wash]')
          await expect(wash).toBeVisible()
          const [hovered] = await measurePlots(card)
          const viewport = (await plot.locator('[data-analysis-chart-scroll]').boundingBox())!
          const painted = (await wash.boundingBox())!
          expect(Math.abs(hovered.columns[at].left - (painted.x - viewport.x)), `${label}: the subject's column starts where its wash does`).toBeLessThanOrEqual(0.5)
          expect(Math.abs(hovered.columns[at].right - (painted.x + painted.width - viewport.x)), `${label}: and ends where it does`).toBeLessThanOrEqual(0.5)
        }
      })
    }
  })
}

// E266: a small cohort's bars stand MAX_SLOT apart, the plot at the card's left, where filling the card set a pair's two
// bars about 560 px apart at 1280px; the tooltip still places itself within the card's width, past the plot's right edge.
for (const width of [390, 1280] as const) {
  test.describe(`Sector peers' widest slot at ${width}px`, () => {
    test.use({ viewport: { width, height: 900 }, isMobile: width < 768, hasTouch: width < 768, reducedMotion: 'reduce' })

    test(`pair: its two bars ${MAX_SLOT}px apart, the plot narrower than its card at the card's left, and sound`, async ({ page, baseURL }) => {
      await openCompany(page, baseURL!, 'pair', 'light')
      const card = sectorPeers(page)
      const plot = card.getByTestId('peers-chart')
      // Two commercial banks, which rank on net interest income (F69).
      const svg = plot.getByRole('img', { name: 'Net interest income chart', exact: true })
      await expect(svg).toBeVisible()
      await expect(plot).not.toHaveAttribute('aria-busy')
      await page.evaluate(() => document.fonts.ready)
      await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
      const label = `pair at ${width}px`
      const [report] = await measurePlots(card)
      expectSound({ ...report, name: label }, { start: 0, maxSlot: MAX_SLOT })
      const ticks = await svg.locator('text[data-text="x"]').evaluateAll((nodes) => nodes.map((node) => ({ ticker: node.textContent, x: Number(node.getAttribute('x')) })))
      expect(ticks.map((tick) => tick.ticker), `${label}: a tick a company drawn`).toEqual(['JPM', 'BAC'])
      expect(ticks[1].x - ticks[0].x, `${label}: the step between the bars`).toBe(MAX_SLOT)
      // The plot: its own gutter, two slots and the 8 px right pad, short of its card, so it neither scrolls nor stops.
      expect(report.svgWidth, `${label}: the plot is its gutter, two slots and its right pad`).toBe(report.cover + 2 * MAX_SLOT + 8)
      expect(report.svgWidth, `${label}: narrower than its card`).toBeLessThan(report.viewportWidth)
      expect([report.scrolls, report.keyboardStop], `${label}: no scroll and no keyboard stop`).toEqual([false, false])
      // A hover needs a pointer, so the desktop width alone runs it: the subject's tooltip sits flush right of its column,
      // past the plot's right edge and inside the card.
      if (width === 1280) {
        await svg.scrollIntoViewIfNeeded()
        const box = (await svg.boundingBox())!
        await page.mouse.move(box.x + ticks[0].x, box.y + box.height / 2)
        const tip = plot.locator('[data-chart-tooltip]')
        await expect(tip).toBeVisible()
        const viewport = (await plot.locator('[data-analysis-chart-scroll]').boundingBox())!
        const placed = (await tip.boundingBox())!
        expect(Math.abs(placed.x - (box.x + report.columns[0].right)), `${label}: the tooltip flush right of the subject's column`).toBeLessThanOrEqual(1)
        expect(placed.x + placed.width, `${label}: past the plot's right edge`).toBeGreaterThan(box.x + box.width)
        expect(placed.x + placed.width, `${label}: inside the card`).toBeLessThanOrEqual(viewport.x + viewport.width + 0.5)
      }
    })
  })
}

// E267 (chief design's check of #1868): on a phone under 200% text the tooltip stands taller than its plot and spans the
// view, so it covers the other bars, and a tap meant for a covered bar lands on the tooltip. That tap closes it, and the
// next tap on the bar pins the bar's own tooltip.
for (const width of [390, 320]) {
  test.describe(`Sector peers' tooltip on a phone at ${width}px under 200% text`, () => {
    test.use({ viewport: { width, height: 844 }, isMobile: true, hasTouch: true, reducedMotion: 'reduce' })

    test('a tap on the tooltip over a bar it covers closes it, and the next tap pins that bar (E267)', async ({ page, baseURL }) => {
      await openCompany(page, baseURL!, 'spread', 'light', { doubled: true })
      await expect
        .poll(() => page.evaluate(() => getComputedStyle(document.documentElement).fontSize), { message: 'the 200% text setting took: the root computes to 32px' })
        .toBe('32px')
      const plot = sectorPeers(page).getByTestId('peers-chart')
      const svg = plot.getByRole('img', { name: 'Revenue chart', exact: true })
      await expect(svg).toBeVisible()
      await page.evaluate(() => document.fonts.ready)
      const viewport = plot.locator('[data-analysis-chart-scroll]')
      await viewport.scrollIntoViewIfNeeded()
      await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
      const frame = (await viewport.boundingBox())!
      const box = (await svg.boundingBox())!
      // Each company's tick, at its centre on the page, among those the view shows.
      const ticks = (await svg.locator('text[data-text="x"]').evaluateAll((nodes) => nodes.map((node) => {
        const r = node.getBoundingClientRect()
        return { ticker: node.textContent ?? '', x: r.x + r.width / 2 }
      }))).filter((tick) => tick.x > frame.x && tick.x < frame.x + frame.width).sort((a, b) => a.x - b.x)
      // The plot opens at the subject, its column centred; the company ranked after it stands right of it, in view.
      const subject = ticks.find((tick) => tick.ticker === SUBJECT)!
      const next = ticks[ticks.indexOf(subject) + 1]
      expect(next, `${width}px: a company in view right of the subject`).toBeDefined()
      await page.touchscreen.tap(subject.x, box.y + box.height / 2)
      const tip = plot.locator('[data-chart-tooltip]')
      await expect(tip.locator('p')).toHaveText(new RegExp(`^${SUBJECT} · `))
      const placed = (await tip.boundingBox())!
      // The case the row names: the tooltip taller than its plot, over the next company's bar.
      expect(placed.height, `${width}px: the tooltip stands taller than its plot`).toBeGreaterThan(box.height)
      expect(next.x > placed.x && next.x < placed.x + placed.width, `${width}px: the tooltip covers ${next.ticker}'s bar`).toBe(true)
      const y = Math.max(placed.y, box.y) + 24
      await page.touchscreen.tap(next.x, y)
      await expect(tip, `${width}px: a tap on the tooltip closes it`).toHaveCount(0)
      await page.touchscreen.tap(next.x, y)
      await expect(tip.locator('p'), `${width}px: the next tap pins ${next.ticker}'s tooltip`).toHaveText(new RegExp(`^${next.ticker} · `))
    })
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

/** Marks, on the page's window, the moment the page has handled its peers read's answer: the client's handler is the
 *  XHR's `onloadend`, set before `send` (axios), so a listener added at `send` runs after it, once the microtasks it
 *  starts have put the answer in the query's cache and queued the query's notify, a zero timeout; a zero timeout this
 *  listener queues runs after that notify and the render it starts, in which the gate decides and, for a cohort, asks
 *  for the card's chunk (the runtime appends its script there and then). */
function markPeersSettled() {
  const open = XMLHttpRequest.prototype.open
  const send = XMLHttpRequest.prototype.send
  const peers = new WeakSet<XMLHttpRequest>()
  XMLHttpRequest.prototype.open = function (this: XMLHttpRequest, ...args: unknown[]) {
    if (/\/api\/companies\/[^/]+\/peers(?:\?|$)/.test(String(args[1]))) peers.add(this)
    return (open as (...rest: unknown[]) => void).apply(this, args)
  }
  XMLHttpRequest.prototype.send = function (this: XMLHttpRequest, ...args: unknown[]) {
    if (peers.has(this)) this.addEventListener('loadend', () => setTimeout(() => { (window as { peersSettled?: boolean }).peersSettled = true }, 0))
    return (send as (...rest: unknown[]) => void).apply(this, args)
  }
}

/** The card's chunk, by the build's own scripts: those holding its string, which the browser would ask for. */
function cardChunks() {
  const chunks = servedHolding(MARKERS.card)
  expect(chunks.length, 'the build holds the Sector peers card in a script of its own').toBeGreaterThan(0)
  return chunks
}

/** Every script the page asked for and every script element in it, once the page has handled its peers answer. */
async function scriptsWhenSettled(page: Page, asked: string[]) {
  await page.waitForFunction(() => (window as { peersSettled?: boolean }).peersSettled === true)
  const present = await page.evaluate(() => [...document.querySelectorAll<HTMLScriptElement>('script[src]')].map((script) => new URL(script.src).pathname))
  return { present, asked: [...asked] }
}

test.describe('Sector peers with production’s own answer, a company ranked alone', () => {
  test.use({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' })

  test('once the page has handled the answer, the card’s chunk was never asked for, the panel shows nothing and the filings render', async ({ page, baseURL }) => {
    const answer = PEERS.cases['production single'].response
    expect([answer.sic, answer.peer_count], 'production’s answer: no SIC code, the subject alone').toEqual([null, 1])
    const card = cardChunks()
    const asked: string[] = []
    page.on('request', (request) => asked.push(new URL(request.url()).pathname))
    await page.addInitScript(markPeersSettled)
    const landed = page.waitForResponse((response) => new URL(response.url()).pathname === `/api/companies/${answer.ticker}/peers`)
    await openCompany(page, baseURL!, 'production single', 'light')
    expect((await landed).status()).toBe(200)
    const settled = await scriptsWhenSettled(page, asked)
    expect(settled.present.filter((script) => card.includes(script)), 'a script of the card’s in the document').toEqual([])
    expect(settled.asked.filter((script) => card.includes(script)), 'a request for the card’s chunk').toEqual([])
    await expect(page.getByRole('heading', { level: 2, name: 'SEC filings', exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { level: 2, name: 'Sector peers', exact: true })).toHaveCount(0)
    await expect(page.getByText('This chart could not be drawn.')).toHaveCount(0)
  })

  test('the mark is after the gate’s decision: at it, the spread’s card has asked for its chunk', async ({ page, baseURL }) => {
    const card = cardChunks()
    const asked: string[] = []
    page.on('request', (request) => asked.push(new URL(request.url()).pathname))
    await page.addInitScript(markPeersSettled)
    await openCompany(page, baseURL!, 'spread', 'light')
    const settled = await scriptsWhenSettled(page, asked)
    expect(settled.present.filter((script) => card.includes(script)).sort(), 'the card’s scripts in the document at the mark').toEqual([...card].sort())
    await expect(sectorPeers(page)).toBeVisible()
  })
})

test.describe('Sector peers while a metric picked loads', () => {
  for (const { width, isMobile } of [{ width: 390, isMobile: true }, { width: 1280, isMobile: false }]) {
    test.describe(`at ${width}px`, () => {
      test.use({ viewport: { width, height: 900 }, isMobile, hasTouch: isMobile, reducedMotion: 'reduce' })

      test('the heading row keeps its height while the answer loads and once it draws no chart', async ({ page, baseURL }) => {
        let release!: () => void
        const held = new Promise<void>((resolve) => { release = resolve })
        const withheld = held.then(() => PEERS.cases['withheld peer'].response)
        await openCompany(page, baseURL!, 'spread', 'light', { more: { eps_diluted: withheld } })
        const card = sectorPeers(page)
        await expect(card.getByTestId('peers-chart').getByRole('img', { name: 'Revenue chart', exact: true })).toBeVisible()
        await page.evaluate(() => document.fonts.ready)
        // The heading row: the heading and the rank line (or its held room) beside, or above, the picker.
        const row = () => card.evaluate((section) => {
          const box = section.querySelector('h2')!.parentElement!.parentElement!.getBoundingClientRect()
          const next = section.querySelector('h2')!.parentElement!.parentElement!.nextElementSibling!.getBoundingClientRect()
          return { height: box.height, below: next.top - box.top }
        })
        const opened = await row()
        await card.getByRole('combobox', { name: /^Metric\b/ }).selectOption('eps_diluted')
        await expect(card.getByRole('status', { name: 'Loading sector peers', exact: true })).toBeVisible()
        await expect(card.locator('[data-held-rank]')).toHaveCount(1)
        const loading = await row()
        release()
        await expect(card.getByText('Too few sector peers have EPS (diluted) figures to compare.', { exact: true })).toBeVisible()
        const none = await row()
        for (const [state, measured] of [['loading', loading], ['no chart', none]] as const) {
          expect(Math.abs(measured.height - opened.height), `${state}: the row's ${measured.height}px against ${opened.height}px`).toBeLessThanOrEqual(0.5)
          expect(Math.abs(measured.below - opened.below), `${state}: what follows the row starts ${measured.below}px below its top, against ${opened.below}px`).toBeLessThanOrEqual(0.5)
        }
      })
    })
  }
})
