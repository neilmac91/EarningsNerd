/** Real browser/API/GCS exercise. No API responses, auth cookies or submission receipts are mocked. */
import { createRequire } from 'node:module'
import { createHash, randomUUID } from 'node:crypto'
import path from 'node:path'
import { LOCAL_ORIGIN, check } from './live_proxy.mjs'

export const ASSERTIONS = ['upload', 'clipboard', 'private_reads', 'other_user_denied', 'admin_view',
  'safe_links', 'retry', 'export', 'account_deleted', 'cleanup', 'memory_boundary']
const LINK = 'https://evidence.example.invalid/feedback-verification?quarter=1#chart'
const COOKIE_NAMES = ['earningsnerd_access_token', 'earningsnerd_refresh_token', 'en_session']
const success = status => status >= 200 && status < 300
// A preceding UI action can fail before its event is awaited. Keep shutdown rejections handled and out of process logs.
function pending(promise) { promise.catch(() => {}); return promise }

export function validateFixtures(fixtures, runId) {
  check(fixtures?.schema === 1 && fixtures.run_id === runId, 'fixture-run')
  const accounts = fixtures.accounts
  check(accounts && Object.keys(accounts).sort().join('|') === 'admin|other|owner', 'fixture-accounts')
  const ids = new Set()
  for (const [role, account] of Object.entries(accounts)) {
    check(Number.isSafeInteger(account.id) && account.id > 0
      && typeof account.email === 'string' && account.email.length < 254
      && account.email === `feedback-verify+${runId}-${role}@example.com`
      && typeof account.password === 'string' && account.password.length >= 12 && account.password.length < 200, 'fixture-account')
    ids.add(account.id)
  }
  check(ids.size === 3, 'fixture-identities')
  return accounts
}

async function login(browser, account, theme, contexts) {
  const context = await browser.newContext({ baseURL: LOCAL_ORIGIN, ignoreHTTPSErrors: true,
    viewport: { width: 1440, height: 1000 }, acceptDownloads: true, serviceWorkers: 'block' })
  contexts.push(context)
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: LOCAL_ORIGIN })
  await context.addInitScript(theme => {
    localStorage.setItem('theme', theme)
    localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false,
      sessionRecording: false, timestamp: new Date().toISOString() }))
  }, theme)
  // Stop telemetry/external navigation. Requests to the local application always reach the real proxy/backend.
  await context.route(url => /^https?:/.test(url.protocol) && url.origin !== LOCAL_ORIGIN,
    route => route.abort('blockedbyclient'))
  const page = await context.newPage()
  page.setDefaultTimeout(15_000)
  await page.goto('/login?redirect=/terms')
  await page.getByRole('button', { name: 'Continue with email' }).click()
  await page.locator('input[type="email"]').fill(account.email)
  await page.locator('input[type="password"]').fill(account.password)
  await page.locator('button[type="submit"]').click()
  await page.waitForURL(LOCAL_ORIGIN + '/terms')
  await page.getByRole('button', { name: 'Send feedback', exact: true }).waitFor()
  const cookies = await context.cookies([LOCAL_ORIGIN, LOCAL_ORIGIN + '/api/auth/refresh'])
  for (const name of COOKIE_NAMES) {
    const cookie = cookies.find(value => value.name === name)
    check(cookie?.secure && cookie.httpOnly && cookie.domain === 'localhost'
      && cookie.path === (name === 'earningsnerd_refresh_token' ? '/api/auth' : '/'), 'real-cookie-semantics')
  }
  const exposed = await page.evaluate(() => document.cookie)
  check(COOKIE_NAMES.every(name => !exposed.includes(name + '=')), 'http-only-cookie')
  return { context, page }
}

async function screenshot(page, output, name) {
  // Only fixed names and post-login synthetic content are saved; never a trace, video or browser state.
  await page.screenshot({ path: path.join(output, name + '.png'), animations: 'disabled' })
}

async function submitThroughComposer(page, png, theme, output, lost = false) {
  await page.getByRole('button', { name: 'Send feedback', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Send feedback' })
  const message = `Synthetic live feedback ${theme}${lost ? ' recovery' : ''}.\n${LINK}`
  await dialog.getByRole('textbox').fill(message)
  const choosing = pending(page.waitForEvent('filechooser'))
  await dialog.getByRole('button', { name: 'Add screenshots' }).click()
  await (await choosing).setFiles([1, 2].map(index => ({ name: `synthetic-${index}.png`, mimeType: 'image/png', buffer: png })))
  await page.evaluate(async base64 => {
    const bytes = Uint8Array.from(atob(base64), char => char.charCodeAt(0))
    await navigator.clipboard.write([new ClipboardItem({ 'image/png': new Blob([bytes], { type: 'image/png' }) })])
  }, png.toString('base64'))
  await dialog.getByRole('textbox').focus()
  await page.keyboard.press('Control+V')
  await page.waitForFunction(() => document.querySelectorAll('img[alt^="Selected screenshot"]').length === 3)
  await screenshot(page, output, `composer-${theme}${lost ? '-recovery' : ''}`)
  const outgoing = pending(page.waitForRequest(request => request.method() === 'POST'
    && new URL(request.url()).pathname === '/api/feedback/with-attachments'))
  const answered = lost ? null : pending(page.waitForResponse(response => response.request().method() === 'POST'
    && new URL(response.url()).pathname === '/api/feedback/with-attachments'))
  await dialog.getByRole('button', { name: 'Send feedback', exact: true }).click()
  const sent = await outgoing
  // Retain only the actual synthetic multipart bytes and non-credential replay headers in memory.
  const headers = sent.headers()
  const replay = { body: sent.postDataBuffer(), key: headers['idempotency-key'],
    reader: headers['x-feedback-user-id'], contentType: headers['content-type'] }
  check(replay.body && replay.body.length <= 16 * 1024 * 1024 && /^[a-f0-9-]{36}$/.test(replay.key), 'submission-capture')
  let id
  if (answered) {
    const response = await answered
    check(success(response.status()), 'upload-response')
    id = (await response.json()).id
    check(Number.isSafeInteger(id), 'upload-receipt')
  }
  await dialog.waitFor({ state: 'detached', timeout: 90_000 })
  check(await page.evaluate(() => sessionStorage.getItem('en_feedback_pending') === null), 'receipt-cleared')
  return { id, replay, message }
}

async function replaySubmission(page, replay, replacement) {
  const body = replacement || replay.body
  return page.evaluate(async ({ base64, key, reader, contentType }) => {
    const response = await fetch('/api/feedback/with-attachments', { method: 'POST', credentials: 'include',
      headers: { 'content-type': contentType, 'idempotency-key': key, 'x-feedback-user-id': reader,
        'x-requested-with': 'XMLHttpRequest' },
      body: Uint8Array.from(atob(base64), char => char.charCodeAt(0)) })
    return { status: response.status, body: await response.json() }
  }, { base64: body.toString('base64'), key: replay.key, reader: replay.reader, contentType: replay.contentType })
}

async function authenticatedRead(context, relative) {
  check(/^\/api\/[A-Za-z0-9_/?=&.-]+$/.test(relative), 'authenticated-path')
  return context.request.get(LOCAL_ORIGIN + relative, { maxRedirects: 0, timeout: 90_000 })
}

async function imageBytes(context, metadata, sharp) {
  check(metadata.download_path === `/api/feedback/attachments/${metadata.id}`, 'manifest-download-path')
  const response = await authenticatedRead(context, metadata.download_path)
  check(response.status() === 200 && response.headers()['content-type']?.startsWith('image/png')
    && response.headers()['cache-control']?.includes('no-store')
    && response.headers()['x-content-type-options'] === 'nosniff', 'private-image-response')
  const bytes = await response.body()
  check(bytes.length > 0 && bytes.length <= 8 * 1024 * 1024, 'private-image-size')
  const info = await sharp(bytes).metadata()
  check(info.format === 'png' && !info.exif && !info.xmp && !info.iptc, 'normalized-private-image')
  if (metadata.sha256) check(createHash('sha256').update(bytes).digest('hex') === metadata.sha256, 'private-image-integrity')
}

/** Self-contained so Playwright executes this same workload in the real browser; injectable I/O is offline-test-only. */
export async function boundaryUploadWorkload({ base64, keys, readerId }, io = {
  fetch: globalThis.fetch.bind(globalThis), delay: milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds)),
}) {
  const ensure = (condition, code) => { if (!condition) throw new Error(code) }
  const source = Uint8Array.from(atob(base64), char => char.charCodeAt(0))
  const padded = new Uint8Array(5 * 1024 * 1024)
  padded.set(source)
  const jobs = await Promise.all(keys.map(async (key, index) => {
    const form = new FormData()
    form.append('type', 'general')
    form.append('message', 'Synthetic live maximum-size verification ' + index)
    form.append('page_url', '/terms')
    for (let image = 0; image < 3; image++) form.append('files', new Blob([padded], { type: 'image/png' }), `boundary-${image}.png`)
    // Encode once: retries preserve both the UUID and the exact multipart bytes/boundary.
    const encoded = new Response(form)
    return { key, body: await encoded.arrayBuffer(), contentType: encoded.headers.get('content-type'), posts: 0 }
  }))
  const send = async job => {
    job.posts++
    const response = await io.fetch('/api/feedback/with-attachments', { method: 'POST', credentials: 'include',
      headers: { 'content-type': job.contentType, 'idempotency-key': job.key,
        'x-feedback-user-id': String(readerId), 'x-requested-with': 'XMLHttpRequest' }, body: job.body })
    await response.arrayBuffer()
    ensure((response.status >= 200 && response.status < 300)
      || (response.status === 503 && response.headers.get('retry-after') === '5'), 'boundary-upload-response')
  }
  // The production decoder intentionally has one slot. A concurrent request may receive documented busy/503.
  await Promise.all(jobs.map(send))
  const ids = []
  for (const job of jobs) {
    let id
    for (let poll = 0; poll < 12; poll++) {
      const response = await io.fetch('/api/feedback/submissions/' + job.key, { credentials: 'include',
        headers: { 'x-feedback-user-id': String(readerId) } })
      ensure(response.status === 200 || response.status === 404, 'boundary-receipt-response')
      const receipt = await response.json()
      if (response.status === 200) {
        ensure(receipt.submission_id === job.key && ['submitted', 'processing', 'retryable'].includes(receipt.state), 'boundary-receipt-identity')
        if (receipt.state === 'submitted') {
          ensure(Number.isSafeInteger(receipt.feedback?.id) && receipt.feedback.id > 0, 'boundary-receipt-id')
          id = receipt.feedback.id
          break
        }
      }
      // Honor Retry-After:5 after the initial concurrent requests have both finished. Never rotate an uncertain UUID.
      await io.delay(5000)
      if (response.status === 404 || receipt.state === 'retryable') {
        ensure(job.posts < 3, 'boundary-retry-limit')
        await send(job)
      }
    }
    ensure(id !== undefined, 'boundary-receipt-deadline')
    ids.push(id)
  }
  ensure(ids.length === 2 && new Set(ids).size === 2, 'boundary-distinct-receipts')
  return ids
}

async function memoryBurst(page, png, readerId) {
  return page.evaluate(boundaryUploadWorkload, { base64: png.toString('base64'), keys: [randomUUID(), randomUUID()], readerId })
}

/** The runner owns cleanup/completion; the browser owns only user-visible assertions and real application calls. */
export async function runBrowser(config, fixtures, proxy, frontend, signal) {
  const accounts = validateFixtures(fixtures, config.run_id)
  const require = createRequire(path.join(frontend, 'package.json'))
  const { chromium } = require('playwright')
  const sharp = require('sharp')
  const png = await sharp({ create: { width: 800, height: 450, channels: 4, background: '#24445b' } })
    .png().withMetadata({ exif: { IFD0: { Artist: 'Synthetic feedback verification' } } }).toBuffer()
  const browser = await chromium.launch({ headless: true, env: {
    PATH: process.env.PATH || '', HOME: process.env.HOME || '', TMPDIR: process.env.TMPDIR || '/tmp',
  } })
  const abort = () => { void browser.close().catch(() => {}) }
  signal?.addEventListener('abort', abort, { once: true })
  if (signal?.aborted) abort()
  const contexts = []
  const assertions = Object.fromEntries(ASSERTIONS.map(name => [name, false]))
  try {
    let owner
    let admin
    let initial
    for (const theme of ['light', 'dark']) {
      owner = await login(browser, accounts.owner, theme, contexts)
      const submitted = await submitThroughComposer(owner.page, png, theme, config.output_dir)
      initial ||= submitted
      admin = await login(browser, accounts.admin, theme, contexts)
      await admin.page.goto('/admin/feedback')
      const opener = admin.page.getByRole('button', { name: `View details for feedback ${submitted.id}` })
      await opener.focus()
      await opener.press('Enter')
      const detail = admin.page.getByRole('dialog', { name: 'Feedback details' })
      await admin.page.waitForFunction(() => [...document.querySelectorAll('img[alt^="Screenshot "]')]
        .filter(image => image.complete && image.naturalWidth > 0).length === 3)
      const link = detail.getByRole('link', { name: LINK, exact: true })
      check(await link.getAttribute('href') === LINK && await link.getAttribute('rel') === 'noopener noreferrer', 'admin-safe-link')
      await screenshot(admin.page, config.output_dir, 'admin-' + theme)
      await admin.page.setViewportSize({ width: 390, height: 400 })
      await admin.page.evaluate(() => { document.documentElement.style.fontSize = '32px' })
      await detail.getByRole('button', { name: 'Download screenshot 3', exact: true }).focus()
      await screenshot(admin.page, config.output_dir, 'admin-narrow-' + theme)
      await admin.page.keyboard.press('Escape')
      check(await opener.evaluate(element => element === document.activeElement), 'admin-focus-return')
    }
    assertions.upload = assertions.clipboard = assertions.admin_view = assertions.safe_links = true

    const repeated = await replaySubmission(owner.page, initial.replay)
    check(success(repeated.status) && repeated.body.id === initial.id, 'same-key-replay')
    const offset = initial.replay.body.indexOf(Buffer.from('Synthetic live feedback'))
    check(offset >= 0, 'conflict-fixture-offset')
    const conflicted = Buffer.from(initial.replay.body)
    conflicted[offset] = 'X'.charCodeAt(0)
    check((await replaySubmission(owner.page, initial.replay, conflicted)).status === 409, 'same-key-conflict')
    proxy.fault.armed = true
    const recovered = await submitThroughComposer(owner.page, png, 'dark', config.output_dir, true)
    check(proxy.fault.saved && proxy.events.some(event => event.dropped && event.key === recovered.replay.key), 'real-lost-response')
    const recovery = await authenticatedRead(owner.context, '/api/feedback/submissions/' + recovered.replay.key)
    check(recovery.status() === 200 && (await recovery.json()).state === 'submitted', 'lost-response-receipt')
    assertions.retry = true

    // Exercise both accepted source-byte and decoded-pixel ceilings concurrently, not merely tiny padded images.
    const maximumPixels = await sharp({ create: { width: 4000, height: 4000, channels: 4, background: '#24445b' } }).png().toBuffer()
    check(maximumPixels.length < 5 * 1024 * 1024, 'boundary-fixture-size')
    const boundaryIds = await memoryBurst(owner.page, maximumPixels, accounts.owner.id)
    const listed = await authenticatedRead(admin.context, '/api/admin/feedback')
    check(listed.status() === 200, 'admin-manifest')
    const ownReports = (await listed.json()).feedback.filter(report => report.user_id === accounts.owner.id)
    const images = ownReports.flatMap(report => report.attachments || [])
    check(ownReports.length === 5 && images.length === 15
      && boundaryIds.every(id => ownReports.find(report => report.id === id)?.attachments.length === 3), 'published-counts')
    const other = await login(browser, accounts.other, 'light', contexts)
    for (const context of [owner.context, admin.context]) await imageBytes(context, images[0], sharp)
    const denied = await authenticatedRead(other.context, images[0].download_path)
    check([403, 404].includes(denied.status()), 'other-user-private-denial')
    assertions.private_reads = assertions.other_user_denied = true

    await owner.page.goto('/dashboard/settings')
    const exported = pending(owner.page.waitForResponse(response => new URL(response.url()).pathname === '/api/users/export'))
    const download = pending(owner.page.waitForEvent('download'))
    await owner.page.getByRole('button', { name: 'Download my data', exact: true }).click()
    const exportResponse = await exported
    check(exportResponse.status() === 200, 'export-response')
    const exportedData = await exportResponse.json()
    await download
    const exportedImages = exportedData.feedback.flatMap(report => report.attachments)
    check(exportedData.feedback.length === ownReports.length && exportedImages.length === images.length
      && exportedImages.every(image => !('object_key' in image) && !('data' in image)), 'export-manifest')
    await imageBytes(owner.context, exportedImages[0], sharp)
    assertions.export = true

    await owner.page.getByRole('button', { name: 'Delete my account', exact: true }).click()
    await owner.page.getByPlaceholder('delete my account', { exact: true }).fill('delete my account')
    const deleted = pending(owner.page.waitForResponse(response => response.request().method() === 'DELETE'
      && new URL(response.url()).pathname === '/api/users/me'))
    await owner.page.getByRole('button', { name: 'Delete my account', exact: true }).click()
    check(success((await deleted).status()), 'owner-delete-response')
    const gone = await authenticatedRead(admin.context, images[0].download_path)
    check(gone.status() === 410, 'deleted-image-denied')
    assertions.account_deleted = true
    return { assertions }
  } finally {
    signal?.removeEventListener('abort', abort)
    await Promise.allSettled(contexts.map(context => context.close()))
    await browser.close()
  }
}
