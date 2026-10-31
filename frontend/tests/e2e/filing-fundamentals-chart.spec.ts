import { test, expect, type Locator, type Page } from '@playwright/test'
import { CHART_TOKENS } from '../../features/analysis/lib/charts/theme'
import { expectInks, expectSound, hexOf, measurePlots, type Paint } from './fixtures/chartChecks'
import { answerApi, API_ORIGIN, FUNDAMENTALS, type Theme } from './fixtures/filing3Api'

/**
 * Financial trends mounts on the filing page and draws through the trend charts' engine (E195 D, D-067). Production
 * builds the card (the flag is on in production's build: its filing pages draw it, read 2026-10-30) and so does CI's
 * e2e job, so on a build without the flag every case here fails: the card never mounts. It renders nothing on an error
 * and for a filing with no featured series, so no render test can see it go missing from the page; a fixture answers
 * its fetcher here, so this browser gate can (lessons/frontend-route-redesign-needs-a-mount-gate.md).
 *
 * On /filing/3, answered by fixtures/filing3Api.ts (production's payload for the filing, four series kept), in both
 * themes at 390 and 1280px: the card's heading and its plot mount, the picker opens on revenue and offers every series
 * the fixture holds, and for each one, chosen in turn, the plot prints what only that series' plot prints, counted from
 * the fixture (lessons/test-probes-assert-what-only-success-renders.md): its fiscal years as its year labels, each once,
 * and its unit's sign, with a minus where its values are negative; the card shows its "Source check needed" badge only
 * on the series that need a check; and the page does not scroll sideways. Consecutive series share their years
 * (revenue and net margin, working capital and the current ratio), so the unit is what tells a redrawn plot from the
 * one before. The heading also stands over the loading state; every point of the fixture holds a value, so each year
 * prints. Each series is drawn by the engine: an SVG with the
 * role img named "{metric} chart", every bar in chart-1 with its value printed on it, a values stop whose value text
 * opens at the newest fiscal year with its end date, net margin redrawn on a percent axis, and the spec's DOM checks
 * that hold for one card (fixtures/chartChecks.ts: D1, D2, D3, D5, D6 on the computed colours, D8 at full hinting, D10
 * under reduced motion, D14 and M6).
 *
 * Under 200% text (Chromium's own text setting, as reflow-200.spec.ts doubles it) at 390, 360 and 320px, for every
 * series, the page does not scroll sideways and the heading row keeps its badge inside the card: beside the heading, or
 * wholly beneath it, its label breaking only where the badge does not fit on a line of its own. Before, the row did not
 * wrap and the one-line badge took the page to 511 to 516px on a calculated series. Those cases read no renderer's DOM,
 * so they hold the card's chrome whichever draws the plot.
 *
 * The card lands where its bones stood (DESIGN_SYSTEM.md §11), at 1280, 390 and 320px in both themes: the fixture's
 * answer to the card's fetch is held until the loading card, its status shown, is measured, and the card that lands on
 * revenue, the default series, which needs no source check, is that height within 0.5px. Before, its bones held the
 * plot alone, and the card grew 56px at 1280px and 128px at 390 and 320px, where the picker takes a row of its own and
 * the footnote two lines. CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md).
 */

const VIEWPORTS = [
  { width: 390, height: 844, isMobile: true, hasTouch: true },
  { width: 1280, height: 900, isMobile: false, hasTouch: false },
]
const THEMES: Theme[] = ['light', 'dark']
const SERIES = FUNDAMENTALS.concepts

/** The card: the nearest section around its heading. */
const financialTrends = (page: Page) =>
  page.getByRole('heading', { level: 2, name: 'Financial trends', exact: true }).locator('xpath=ancestor::section[1]')

/** Each series' unit as the engine prints it in its tick and value labels: an amount's currency sign, a margin's %, a
 *  multiple's ×. */
const UNIT_SIGN: Record<string, string> = { revenue: '$', net_margin: '%', working_capital: '$', current_ratio: '×' }
/** The series the fixture marks for a source check (calculated, `needs_review`), which the card badges. */
const BADGED = new Set(['net_margin', 'working_capital', 'current_ratio'])

/** What the plot's SVG prints: every label that is a year alone ("2023" or "FY2023"), each counted, in order; whether
 *  a label carries the series' unit sign; and whether such a label also carries a minus. */
const drawn = (plot: Locator, sign: string) =>
  plot.evaluate((root, unit) => {
    const texts = [...root.querySelectorAll('svg text')].map((text) => (text.textContent ?? '').replace(/\s+/g, ' ').trim())
    const years = texts.flatMap((text) => {
      const year = /^(?:FY)?((?:19|20)\d{2})$/.exec(text)
      return year ? [Number(year[1])] : []
    }).sort((a, b) => a - b)
    const signed = texts.filter((text) => text.includes(unit))
    return { years, unit: signed.length > 0, minus: signed.some((text) => /[−-]/.test(text)) }
  }, sign)

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

/** Consent answered and the first-run coachmark seen (neither belongs to this card), the theme chosen, then the page.
 *  Given `held`, the card's fetch waits for it before the fixture answers. */
async function openFiling(page: Page, baseURL: string, theme: Theme, held?: Promise<void>) {
  await answerApi(page, baseURL, 'anon')
  // Registered after answerApi, so it runs first, then hands the request on to the fixture's answer.
  if (held) {
    await page.route((url) => url.origin === API_ORIGIN && url.pathname === '/api/filings/3/fundamentals', async (route) => {
      await held
      await route.fallback()
    })
  }
  await page.addInitScript((chosen: Theme) => {
    try {
      localStorage.setItem('theme', chosen)
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  }, theme)
  await page.goto('/filing/3')
  const card = financialTrends(page)
  await expect(card).toBeVisible()
  return card
}

/** Chooses a series and waits until the plot prints what only that series' plot prints, and the card its badge. */
async function choose(card: Locator, concept: string) {
  await card.getByRole('combobox', { name: /^Metric\b/ }).selectOption(concept)
  const points = SERIES.find((series) => series.concept === concept)!.points
  const expected = {
    years: points.map((point) => point.fiscal_year).sort((a, b) => a - b),
    unit: true,
    minus: points.some((point) => point.value < 0),
  }
  const plot = card.getByTestId('fundamentals-chart')
  await expect(plot, `${concept}: the plot mounts`).toBeVisible()
  await expect.poll(() => drawn(plot, UNIT_SIGN[concept]), { message: `${concept}: the plot prints this series' years, its unit's sign and its sign` }).toEqual(expected)
  const badge = card.getByText('Source check needed', { exact: true })
  if (BADGED.has(concept)) await expect(badge, `${concept}: the card badges a series that needs a source check`).toBeVisible()
  else await expect(badge, `${concept}: the card badges no series that needs no check`).toHaveCount(0)
  return plot
}

/** A printed value's number and half a step of its last printed digit: "−$23.4B" is −23.4e9 within 0.05e9, "25.3%"
 *  25.3 within 0.05, "0.87×" 0.87 within 0.005. */
const SCALE: Record<string, number> = { K: 1e3, M: 1e6, B: 1e9, T: 1e12 }
function printedNumber(text: string) {
  const match = /^([−-])?[^\d−-]*([\d,]+)(?:\.(\d+))?([KMBT])?[%×]?$/.exec(text.trim())
  if (!match) throw new Error(`a printed value this check cannot read: "${text}"`)
  const scale = match[4] ? SCALE[match[4]] : 1
  const digits = match[3] ?? ''
  const value = Number(`${match[2].replace(/,/g, '')}.${digits || '0'}`) * scale * (match[1] ? -1 : 1)
  return { text, value, within: 0.5 * 10 ** -digits.length * scale }
}

/** The engine's drawing of the chosen series, held to what the full /analysis look promises (D-067). */
async function expectEngineDrawing(card: Locator, plot: Locator, concept: string, theme: Theme) {
  const label = (await card.getByRole('combobox', { name: /^Metric\b/ }).locator('option:checked').textContent())!.trim()
  const points = SERIES.find((series) => series.concept === concept)!.points
  const newest = Math.max(...points.map((point) => point.fiscal_year))
  const svg = plot.getByRole('img', { name: `${label} chart`, exact: true })
  await expect(svg, `${concept}: a named SVG of the role img`).toBeVisible()
  const drawing = await svg.evaluate((root) => ({
    fills: [...root.querySelectorAll('rect[data-series]')].map((bar) => bar.getAttribute('fill')),
    labels: [...root.querySelectorAll('text[data-text="label"]')].map((text) => text.textContent ?? ''),
    ticks: [...root.querySelectorAll('text[data-text="tick"]')].map((text) => text.textContent ?? ''),
  }))
  expect(drawing.fills, `${concept}: every bar in chart-1`).toEqual(points.map(() => CHART_TOKENS[theme].series[0]))
  expect(drawing.labels, `${concept}: every value printed on its bar`).toHaveLength(points.length)
  if (concept === 'net_margin') {
    expect(drawing.ticks, 'net margin redraws on a percent axis, from its zero').toContain('0%')
    expect(drawing.ticks.every((tick) => tick.endsWith('%')), `net margin redraws on a percent axis: ${drawing.ticks.join(', ')}`).toBe(true)
    expect(drawing.labels.every((value) => value.endsWith('%')), `net margin prints percents: ${drawing.labels.join(', ')}`).toBe(true)
  }
  // Each printed value is one of this series' own, to the digit it prints: a plot that kept the series before in this
  // series' format (revenue's amounts as percents, the same years) prints numbers none of these round to.
  const printed = drawing.labels.map(printedNumber).sort((a, b) => a.value - b.value)
  const filed = points.map((point) => point.value).sort((a, b) => a - b)
  printed.forEach(({ text, value, within }, i) => {
    expect(Math.abs(value - filed[i]), `${concept}: "${text}" prints the filed ${filed[i]}`).toBeLessThanOrEqual(within + 1e-9 * Math.abs(filed[i]))
  })
  const stop = card.getByRole('slider', { name: `${label} chart values`, exact: true })
  await expect(stop, `${concept}: the values stop opens at the newest fiscal year, with its end date`).toHaveAttribute('aria-valuetext', new RegExp(`^FY${newest}, year ended [A-Z][a-z]+ \\d{1,2}, \\d{4}\\. ${label}: `))

  // The spec's DOM checks for one card: its text, its marks and its inks on the card's computed ground.
  const [report] = await measurePlots(card)
  const name = `${label} (${theme})`
  expectSound({ ...report, name })
  const ground = await card.evaluate((section) => getComputedStyle(section).backgroundColor)
  expect(hexOf(ground), `${name}: the card is the chart surface`).toBe(CHART_TOKENS[theme].surface)
  const html = await card.locator('[data-chart-text]').evaluateAll((nodes) => nodes.map((node) => ({
    what: `${node.getAttribute('data-chart-text')} "${node.textContent}"`, floor: 'text' as const, colour: getComputedStyle(node).color,
  })))
  expectInks(name, [...report.paints, ...html] as Paint[], ground)
}

/** Chromium's own text setting doubled (standard 32, fixed 26), as reflow-200.spec.ts doubles it, confirmed taken. */
async function doubleText(page: Page) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
  await expect
    .poll(() => page.evaluate(() => getComputedStyle(document.documentElement).fontSize), { message: 'the 200% text setting took: the root computes to 32px' })
    .toBe('32px')
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
}

/** The heading row: the heading's box, the source-check badge's (none when the series needs no check) against the card's
 *  content box, and the badge's width on one line, measured on a hidden copy, against the row's. */
const headingRow = (card: Locator) =>
  card.evaluate((section) => {
    const heading = section.querySelector('h2')!
    const row = heading.parentElement!
    const badge = [...row.children].find((child) => child !== heading) as HTMLElement | undefined
    const box = (el: Element) => { const r = el.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, height: r.height } }
    const style = getComputedStyle(section)
    const bounds = section.getBoundingClientRect()
    const content = { left: bounds.left + parseFloat(style.paddingLeft), right: bounds.right - parseFloat(style.paddingRight) }
    if (!badge) return { heading: box(heading), content, badge: null }
    const probe = badge.cloneNode(true) as HTMLElement
    probe.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap;width:max-content'
    row.appendChild(probe)
    const oneLine = probe.getBoundingClientRect()
    probe.remove()
    return { heading: box(heading), content, badge: { ...box(badge), text: badge.textContent, oneLineWidth: oneLine.width, oneLineHeight: oneLine.height, room: row.clientWidth } }
  })

/** The card's height, unrounded, once the fonts are in and two frames have painted. */
async function settledHeight(page: Page, card: Locator) {
  await page.evaluate(() => document.fonts.ready)
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
  return card.evaluate((section) => section.getBoundingClientRect().height)
}

test.describe.configure({ mode: 'parallel' })
// Full font hinting, headless Chrome's default (CI's): D1 and D8 run in the case that can break them.
test.use({ launchOptions: { args: ['--font-render-hinting=full'] } })

for (const { width, height, isMobile, hasTouch } of VIEWPORTS) {
  test.describe(`Financial trends on /filing/3 at ${width}px`, () => {
    test.use({ viewport: { width, height }, isMobile, hasTouch, reducedMotion: 'reduce' })

    for (const theme of THEMES) {
      test(`${theme}: the card and its plot mount, each series draws through the engine and prints its years, and the page does not scroll sideways`, async ({ page, baseURL }) => {
        const card = await openFiling(page, baseURL!, theme)
        expect(await page.evaluate(() => document.documentElement.classList.contains('dark')), `the ${theme} theme took`).toBe(theme === 'dark')
        const picker = card.getByRole('combobox', { name: /^Metric\b/ })
        await expect(picker).toHaveValue('revenue')
        const offered = await picker.locator('option').evaluateAll((options) => options.map((option) => (option as HTMLOptionElement).value))
        expect([...offered].sort(), 'the picker offers every series the fixture holds').toEqual(SERIES.map((series) => series.concept).sort())

        for (const concept of offered) {
          const plot = await choose(card, concept)
          await page.evaluate(() => document.fonts.ready)
          await expectEngineDrawing(card, plot, concept, theme)
          const { scrollWidth, clientWidth, past } = await widths(page)
          expect(scrollWidth, `${concept}: scrollWidth ${scrollWidth}px against clientWidth ${clientWidth}px; past the edge: ${past.join('; ') || 'nothing'}`).toBeLessThanOrEqual(clientWidth)
        }
      })
    }
  })
}

for (const { width, height, isMobile, hasTouch } of [...VIEWPORTS, { width: 320, height: 844, isMobile: true, hasTouch: true }]) {
  test.describe(`Financial trends on /filing/3 at ${width}px, its fetch held`, () => {
    test.use({ viewport: { width, height }, isMobile, hasTouch, reducedMotion: 'reduce' })

    for (const theme of THEMES) {
      test(`${theme}: the card lands where its bones stood`, async ({ page, baseURL }) => {
        let release!: () => void
        const held = new Promise<void>((resolve) => { release = resolve })
        const card = await openFiling(page, baseURL!, theme, held)
        await expect(card.getByRole('status', { name: 'Loading financial trends', exact: true })).toBeVisible()
        const loading = await settledHeight(page, card)

        release()
        await expect(card.getByRole('combobox', { name: /^Metric\b/ })).toHaveValue('revenue')
        const plot = card.getByTestId('fundamentals-chart')
        await expect(plot.getByRole('img', { name: 'Revenue chart', exact: true })).toBeVisible()
        await expect(plot).not.toHaveAttribute('aria-busy')
        await expect(card.getByText('Source check needed', { exact: true }), 'revenue needs no source check').toHaveCount(0)
        await expect(card.getByText('Sources & checks', { exact: true })).toBeVisible()
        const loaded = await settledHeight(page, card)
        expect(Math.abs(loaded - loading), `the card is ${loading}px loading and ${loaded}px loaded`).toBeLessThanOrEqual(0.5)
      })
    }
  })
}

for (const width of [390, 360, 320]) {
  test.describe(`Financial trends on /filing/3 at ${width}px under 200% text`, () => {
    test.use({ viewport: { width, height: 844 }, isMobile: true, hasTouch: true })

    test('every series keeps the page from scrolling sideways, and the heading row its badge inside the card', async ({ page, baseURL }) => {
      const card = await openFiling(page, baseURL!, 'light')
      await choose(card, 'revenue')
      await doubleText(page)
      for (const { concept } of SERIES) {
        await choose(card, concept)
        await page.evaluate(() => document.fonts.ready)
        const { scrollWidth, clientWidth, past } = await widths(page)
        expect(scrollWidth, `${concept}: scrollWidth ${scrollWidth}px against clientWidth ${clientWidth}px; past the edge: ${past.join('; ') || 'nothing'}`).toBeLessThanOrEqual(clientWidth)

        const row = await headingRow(card)
        expect(row.badge != null, `${concept}: the badge shows exactly when a value needs a source check`).toBe(BADGED.has(concept))
        if (!row.badge) continue
        const { badge, heading, content } = row
        const where = `badge ${badge.left.toFixed(1)}..${badge.right.toFixed(1)}, ${badge.top.toFixed(1)}..${badge.bottom.toFixed(1)}; heading ${heading.left.toFixed(1)}..${heading.right.toFixed(1)}, ${heading.top.toFixed(1)}..${heading.bottom.toFixed(1)}; content ${content.left.toFixed(1)}..${content.right.toFixed(1)}`
        expect(badge.left >= content.left - 0.5 && badge.right <= content.right + 0.5, `${concept}: the badge lies inside the card's content box (${where})`).toBe(true)
        const beside = badge.left >= heading.right - 0.5 && badge.top < heading.bottom && badge.bottom > heading.top
        const beneath = badge.top >= heading.bottom - 0.5
        expect(beside || beneath, `${concept}: the badge is beside the heading or wholly beneath it (${where})`).toBe(true)
        const wraps = badge.height > badge.oneLineHeight + 1
        expect(!wraps || badge.oneLineWidth > badge.room - 0.5, `${concept}: "${badge.text}" breaks only where it does not fit a line (${badge.oneLineWidth.toFixed(1)}px on one line, ${badge.room}px of row)`).toBe(true)
      }
    })
  })
}
