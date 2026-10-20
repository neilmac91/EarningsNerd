import { test, expect, type Page } from '@playwright/test'
import { API_ORIGIN, answerApi, type Who } from './fixtures/filing3Api'

/**
 * E27 / PR B: the Item 1A wording block of the change report, in a real Chromium. An anonymous
 * visitor gets the teaser: the counts, the first changes, how many more there are, the Upgrade to
 * Pro button (which opens the upgrade dialog and hands focus back on Escape) and a sign-in link. A
 * Pro user gets every change, no prompt, and the review: pressed-state toggles on each change, the
 * j/k and 1/2 keys, the progress line, and the receipt once the queue is complete, which copies as
 * text. The redline reads as one paragraph: inserted words underlined, removed words struck
 * through, each named for assistive tech.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API is answered in
 * the browser (fixtures/filing3Api.ts; the server render's own read of the report fails, so the
 * client reads it once /me has settled, which is the path this spec covers). The report is this
 * spec's own synthetic fixture: nothing in it is filing text.
 */

const PRIOR = { filing_id: 2, filing_type: '10-K', filing_date: '2024-11-01T00:00:00+00:00', period_end_date: '2024-09-28T00:00:00+00:00', accession_number: 'prior-annual-report' }
const SIDE = { status: 'ok', extracted_at: '2026-10-12T00:00:00+00:00', reference_only: false, char_count: 2400, paragraph_count: 9 }
const ITEMS = [
  { id: 'w1', kind: 'modified', index: 1, prior_index: 1, similarity: 0.8, moved: false, ops: [['equal', 'Demand for our products depends on'], ['delete', 'a few'], ['insert', 'several large'], ['equal', 'customers.']] },
  { id: 'w2', kind: 'added', index: 4, after: 'New export controls could limit sales in some regions.' },
  { id: 'w3', kind: 'removed', prior_index: 5, before: 'Supply constraints eased during the year.' },
  { id: 'w4', kind: 'moved', index: 7, prior_index: 3, after: 'Cybersecurity incidents could disrupt our operations.' },
  { id: 'w5', kind: 'modified', index: 8, prior_index: 8, similarity: 0.9, moved: false, ops: [['equal', 'Interest rates may'], ['insert', 'continue to'], ['equal', 'rise.']] },
]
const report = (who: Who) => ({
  has_prior: true,
  comparison_basis: 'Year over year',
  prior_filing: PRIOR,
  metrics: {
    headline: 'Revenue up 6.4%',
    items: [{ metric: 'revenue', label: 'Revenue', direction: 'up', pct: 6.4, current: 416e9, prior: 391e9, display: '+6.4%', tone: 'gain' }],
    data_quality: 'ok',
  },
  reporting_currency: 'USD',
  risks: null,
  key_changes: null,
  has_changes: true,
  section_changes: {
    section: 'item_1a',
    section_label: 'Risk factors',
    access: who === 'pro' ? 'full' : 'teaser',
    engine_version: 1,
    prior_filing: PRIOR,
    status: 'ok',
    reason: null,
    current: SIDE,
    prior: SIDE,
    paragraphs: { prior: 9, later: 9, prior_excluded: 0, later_excluded: 0 },
    counts: { unchanged: 4, modified: 2, added: 1, removed: 1, moved: 1 },
    words: { later_total: 620, inserted: 11, deleted: 6, changed_ratio: 0.03 },
    has_changes: true,
    items: who === 'pro' ? ITEMS : ITEMS.slice(0, 3),
    items_total: 5,
    truncated: who !== 'pro',
  },
})

type Label = 'reviewed' | 'follow_up'

/** The review endpoints answered in the browser like the server would: labels accumulate per
 *  change id, the fifth completes the review and freezes a receipt. Returns the labels seen. */
async function answerReview(page: Page, cors: Record<string, string>) {
  const labels: Record<string, Label> = {}
  let wasComplete = false
  const state = (answering = false) => {
    const values = Object.values(labels)
    const reviewed = values.filter((label) => label === 'reviewed').length
    const complete = values.length === ITEMS.length
    const completedNow = complete && !wasComplete
    if (answering) wasComplete = complete
    const followUps = Object.entries(labels).filter(([, label]) => label === 'follow_up').map(([id]) => id)
    return {
      filing_id: 3,
      section: 'item_1a',
      section_label: 'Item 1A. Risk Factors',
      status: 'ok',
      engine_version: 1,
      items_total: ITEMS.length,
      labels,
      counts: { reviewed, follow_up: values.length - reviewed, unlabeled: ITEMS.length - values.length },
      completed_at: complete ? '2026-10-13T12:00:00Z' : null,
      // The server names the transition on a label's answer; a read never carries it.
      ...(answering ? { completed_now: completedNow } : {}),
      receipt: complete
        ? {
            version: 1,
            completed_at: '2026-10-13T12:00:00Z',
            section: 'item_1a',
            section_label: 'Item 1A. Risk Factors',
            filing: { filing_id: 3, filing_type: '10-K', filing_date: '2025-10-31T00:00:00+00:00', period_end_date: '2025-09-27T00:00:00+00:00', accession_number: 'current-annual-report' },
            prior_filing: PRIOR,
            texts: {
              current: { sha256: 'c'.repeat(64), extractor_version: 1, extracted_at: '2026-10-12T00:00:00Z' },
              prior: { sha256: 'p'.repeat(64), extractor_version: 1, extracted_at: '2026-10-12T00:00:00Z' },
            },
            engine_version: 1,
            app_version: '1.1.0',
            paragraphs: { prior: 9, later: 9, prior_excluded: 0, later_excluded: 0 },
            counts: { unchanged: 4, modified: 2, added: 1, removed: 1, moved: 1 },
            words: { later_total: 620, inserted: 11, deleted: 6, changed_ratio: 0.03 },
            items_total: ITEMS.length,
            labels: { reviewed, follow_up: followUps.length },
            follow_up_ids: followUps,
          }
        : null,
    }
  }
  await page.route(`${API_ORIGIN}/api/summaries/filing/3/wording-review`, (route) => route.fulfill({ status: 200, headers: cors, json: state() }))
  await page.route(`${API_ORIGIN}/api/summaries/filing/3/wording-review/labels`, (route) => {
    // Only the PUT reaches the route (Chromium's preflight is answered by Playwright itself).
    expect(route.request().method()).toBe('PUT')
    const body = route.request().postDataJSON() as { item_id: string; label: Label | null }
    if (body.label === null) delete labels[body.item_id]
    else labels[body.item_id] = body.label
    return route.fulfill({ status: 200, headers: cors, json: state(true) })
  })
  return labels
}

async function openReport(page: Page, baseURL: string, who: Who) {
  await answerApi(page, baseURL, who)
  // Registered after answerApi, so it is tried first: Playwright matches the newest route first.
  const cors = { 'access-control-allow-origin': new URL(baseURL).origin, 'access-control-allow-credentials': 'true' }
  await page.route(`${API_ORIGIN}/api/summaries/filing/3/what-changed`, (route) => route.fulfill({ status: 200, headers: cors, json: report(who) }))
  if (who === 'pro') await answerReview(page, cors)
  // Consent answered and the first-run coachmark seen, so nothing covers the report.
  await page.addInitScript(() => {
    try {
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  })
  await page.goto('/filing/3')
  const block = page.getByRole('region', { name: 'What changed' }).locator('[data-wording-access]')
  await expect(block).toBeVisible()
  await block.scrollIntoViewIfNeeded()
  return block
}

test.describe('the risk factor wording block of the change report', () => {
  test.use({ viewport: { width: 1280, height: 900 } })

  test('an anonymous visitor gets the teaser: the first changes, the count of the rest, and the Pro prompt with a sign-in', async ({ page, baseURL }) => {
    const block = await openReport(page, baseURL!, 'anon')
    await expect(block).toHaveAttribute('data-wording-access', 'teaser')
    await expect(block.getByRole('heading', { name: /Risk factor wording/ })).toBeVisible()
    await expect(block.getByText(/5 paragraphs changed: 2 modified, 1 added, 1 removed and 1 moved; 4 unchanged/)).toBeVisible()
    await expect(block.getByRole('listitem')).toHaveCount(3)
    await expect(block.getByText('2 more changes in this section. Pro shows every change.')).toBeVisible()
    await expect(block.getByRole('link', { name: 'Already Pro? Log in' })).toHaveAttribute('href', '/login')

    // The redline: the later text with the removed words beside it, both named for assistive tech,
    // underlined and struck through in the rendered CSS.
    const first = block.getByRole('listitem').first()
    await expect(first.locator('ins')).toHaveText('added: several large')
    await expect(first.locator('del')).toHaveText('removed: a few')
    expect(await first.locator('ins').evaluate((el) => getComputedStyle(el).textDecorationLine)).toContain('underline')
    expect(await first.locator('del').evaluate((el) => getComputedStyle(el).textDecorationLine)).toContain('line-through')

    // The prompt opens the upgrade dialog, which names the feature; Escape closes it and hands
    // focus back to the button that opened it.
    const upgrade = block.getByRole('button', { name: 'Upgrade to Pro' })
    await upgrade.click()
    const dialog = page.getByRole('dialog', { name: 'Upgrade to Pro' })
    await expect(dialog).toBeVisible()
    await expect(dialog.getByText(/Risk factor wording review is a Pro feature/)).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await expect(upgrade).toBeFocused()
  })

  test('a Pro user gets every change and no prompt', async ({ page, baseURL }) => {
    const block = await openReport(page, baseURL!, 'pro')
    await expect(block).toHaveAttribute('data-wording-access', 'full')
    await expect(block.getByRole('listitem')).toHaveCount(5)
    await expect(block.getByText(/more change/)).toHaveCount(0)
    await expect(block.getByRole('button', { name: 'Upgrade to Pro' })).toHaveCount(0)
    await expect(block.getByRole('link', { name: 'Already Pro? Log in' })).toHaveCount(0)
  })

  test('a Pro user reviews the changes: toggles and keys mark them, the progress counts, and the end of the queue is a receipt that copies', async ({ page, baseURL, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write'])
    const block = await openReport(page, baseURL!, 'pro')
    const progress = block.getByTestId('wording-progress')
    await expect(progress).toHaveText('0 of 5 changes marked.')
    const rows = block.getByRole('listitem')

    // A press marks the change and flips its toggle; the other toggle on the row stays up.
    const firstReviewed = rows.nth(0).getByRole('button', { name: 'Reviewed: change 1 of 5' })
    await firstReviewed.click()
    await expect(firstReviewed).toHaveAttribute('aria-pressed', 'true')
    await expect(rows.nth(0).getByRole('button', { name: 'Follow up: change 1 of 5' })).toHaveAttribute('aria-pressed', 'false')
    await expect(progress).toHaveText('1 of 5 changes marked.')

    // From a toggle, j moves focus to the next change; 2 flags the focused change; k moves back.
    await firstReviewed.focus()
    await page.keyboard.press('j')
    await expect(rows.nth(1)).toBeFocused()
    await page.keyboard.press('2')
    await expect(rows.nth(1).getByRole('button', { name: 'Follow up: change 2 of 5' })).toHaveAttribute('aria-pressed', 'true')
    await expect(progress).toHaveText('2 of 5 changes marked, 1 to follow up.')
    await page.keyboard.press('j')
    await page.keyboard.press('1')
    await page.keyboard.press('j')
    await page.keyboard.press('1')
    await page.keyboard.press('j')
    await expect(rows.nth(4)).toBeFocused()
    await expect(progress).toHaveText('4 of 5 changes marked, 1 to follow up.')
    await expect(block.getByTestId('wording-receipt')).toHaveCount(0)

    // The last label completes the review: the receipt names the two texts and copies as text.
    await page.keyboard.press('1')
    await expect(progress).toHaveText('All 5 changes marked, 1 to follow up. Receipt below.')
    const receipt = block.getByTestId('wording-receipt')
    await expect(receipt).toContainText('10-K current-annual-report')
    await expect(receipt).toContainText('cccccccccccc… / pppppppppppp…')
    await receipt.getByRole('button', { name: 'Copy receipt' }).click()
    await expect(receipt.getByRole('status')).toHaveText('Receipt copied.')
    const copied = await page.evaluate(() => navigator.clipboard.readText())
    expect(copied.split('\n')[0]).toBe('EarningsNerd review receipt')
    expect(copied).toContain(`Text SHA-256: current ${'c'.repeat(64)}; prior ${'p'.repeat(64)}`)
    expect(copied).toContain('Follow-up change ids: w2')

    // Clearing a label reopens the queue and takes the receipt with it.
    await rows.nth(1).getByRole('button', { name: 'Follow up: change 2 of 5' }).click()
    await expect(progress).toHaveText('4 of 5 changes marked.')
    await expect(block.getByTestId('wording-receipt')).toHaveCount(0)
  })
})
