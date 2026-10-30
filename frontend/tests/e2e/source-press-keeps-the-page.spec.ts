import { test, expect } from '@playwright/test'
import { PANE, answerApi } from './fixtures/filing3Api'

/**
 * A press on Source never moves the page under the reader (chief design on #1813; E248). Opening the pane on Ask
 * focuses the rail's composer a frame later, or once the plan or usage loads, and a focus's own scroll moves every
 * scrolling ancestor, the page included. While the desktop pane's lower part sat below the fold, as it can for a frame
 * before the pane measures its top, that scroll brought the composer up: in #1813's e2e run 41053542799 the page sat
 * at 495px after the press. The composer now takes focus with preventScroll and is brought into view inside the rail's
 * column only (CopilotComposer's revealInScrollBox).
 *
 * Here the pane's cell is held taller than the screen, so the composer stays below the fold whatever the timing: the
 * press opens the pane, the composer takes focus there, and the page stays at 0. With the page scrolled, ⌘K's focus
 * keeps it where it was too.
 */
test.describe('a press on Source keeps the page / 1100x800, a Pro reader on /filing/3', () => {
  test.use({ viewport: { width: 1100, height: 800 }, reducedMotion: 'reduce', serviceWorkers: 'block', colorScheme: 'light' })

  test('the composer takes focus below the fold and the page stays where it was', async ({ page, baseURL }) => {
    await page.addInitScript(() => {
      localStorage.setItem('theme', 'light')
      localStorage.setItem('en_session_active', '1')
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-10T00:00:00Z', version: 2 }))
    })
    await answerApi(page, baseURL!, 'pro')
    await page.goto('/filing/3')
    const source = page.getByRole('button', { name: 'Source', exact: true })
    await expect(source).toBeVisible()
    // The pane's cell (the shell's parent, mounted while the pane is closed), held at three screens tall.
    await page.locator(PANE).evaluate((shell) => {
      shell.parentElement!.style.height = '2400px'
    })
    await page.evaluate(() => window.scrollTo(0, 0))
    expect(await page.evaluate(() => window.scrollY), 'the page starts at its top').toBe(0)

    await source.click()
    const composer = page.locator(PANE).getByRole('textbox', { name: 'Ask about this filing' })
    await expect(composer, 'the composer takes focus as the pane opens on Ask').toBeFocused()
    // Two frames after the focus, for any scroll it brought to land.
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))))
    expect(await page.evaluate(() => window.scrollY), 'a press on Source leaves the page at its top').toBe(0)
    const box = (await composer.boundingBox())!
    expect(box.y, 'the composer is below the fold, where a focus with its own scroll would have moved the page').toBeGreaterThan(800)

    // ⌘K with the page scrolled: the open rail's composer takes focus again, and the page stays where the reader put it.
    await page.evaluate(() => window.scrollTo(0, 300))
    await composer.evaluate((el: HTMLElement) => el.blur())
    await page.keyboard.press('ControlOrMeta+k')
    await expect(composer, '⌘K focuses the open rail\'s composer').toBeFocused()
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))))
    expect(await page.evaluate(() => window.scrollY), '⌘K leaves the page where it was').toBe(300)
  })
})
