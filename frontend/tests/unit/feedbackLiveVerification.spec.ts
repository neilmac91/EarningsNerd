// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import https from 'node:https'
import { PassThrough, Writable } from 'node:stream'
import { finished } from 'node:stream/promises'
import {
  audienceToken, browserRoute, forwardedHeaders, responseHeaders, privateFile,
  validateManifest, proxyHandler, MAX_BODY_BYTES, DEADLINE_MS, LOCAL_ORIGIN,
} from '../../../ops/feedback_media/live_proxy.mjs'
import { ASSERTIONS, validateFixtures, boundaryUploadWorkload } from '../../../ops/feedback_media/live_browser.mjs'
import { run, receiptEnvelope, safeFailure } from '../../../ops/feedback_media/live_runner.mjs'

const temporary: string[] = []
function directory() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'feedback-verify-unit-'))
  temporary.push(dir)
  return dir
}
function manifest(dir = '/tmp/private-verification') {
  return {
    version: 1, run_id: '123-1', expected_project: 'earnings-nerd', expected_service: 'earningsnerd-feedback-verify',
    service_origin: 'https://earningsnerd-feedback-verify-123.us-west1.run.app',
    service_audience: 'https://earningsnerd-feedback-verify-123.us-west1.run.app',
    runtime_source_sha256: 'a'.repeat(64), verification_suite_sha256: 'b'.repeat(64), frontend_tree: 'c'.repeat(40),
    image_digest: 'sha256:' + 'd'.repeat(64), id_token_file: dir + '/token', control_token_file: dir + '/control',
    cert_file: dir + '/cert', key_file: dir + '/key', output_dir: dir + '/output',
  }
}
function receipt(config = manifest()) {
  return { signature: 'e'.repeat(64), payload: {
    schema: 1, purpose: 'feedback-media-verification', run_id: config.run_id, completed_at: '2026-10-25T12:00:00Z',
    image_digest: config.image_digest, runtime_source_sha256: config.runtime_source_sha256,
    verification_suite_sha256: config.verification_suite_sha256, frontend_tree: config.frontend_tree,
    browser_assertions: Object.fromEntries(ASSERTIONS.map(key => [key, true])),
    observed: {
      database: { feedback: 5, submitted: 5, attachments: 15, fixture_users: 0, published_attachments: 15,
        confirmed_generation_deletions: 15, normalized_metadata_valid: true, available: 0, deleted: 15, pending: 0 },
      notifications: { accepted: 5, rejected: 0, attachment_counts: [3, 3, 3, 3, 3], admin_link_valid: true, no_image_payload: true },
      cleanup: { dry_run: false, eligible: 15, deleted: 15, errors: 0, overdue: 0, pending_verification: 0 },
      resources: { sample_count: 6, rss_peak_bytes: 100, cgroup_sample_peak_bytes: 100,
        cgroup_kernel_peak_bytes: null, cgroup_memory_limit_bytes: null, configured_memory_limit_bytes: 1073741824,
        self_high_water_rss_bytes: 100, reaped_child_high_water_rss_bytes: 100,
        worker_limits: { feedback_image_service: 1, feedback_storage_worker_service: 2 }, unexplained_children: false,
        last_process_count: 1, sample_age_seconds: 0.05, acceptance_passed: true, conservative_process_bound_bytes: 400,
        evidence_basis: 'kernel peak unavailable; conservative process-bound evidence',
        method: 'kernel peak when exposed; otherwise conservative process bound plus sampled cgroup; representative workload only' },
    },
  } }
}
class Response extends Writable {
  headersSent = false
  status = 0
  headers: Record<string, unknown> = {}
  chunks: Buffer[] = []
  writeHead(status: number, headers: Record<string, unknown>) { this.status = status; this.headers = headers; this.headersSent = true }
  _write(chunk: Buffer, _encoding: string, next: () => void) { this.chunks.push(Buffer.from(chunk)); next() }
}
function exchange({ fault = { armed: false }, answerBody = Buffer.from('accepted'), hold = false } = {}) {
  const request = Object.assign(new PassThrough(), { url: '/api/feedback/with-attachments', method: 'POST',
    headers: { host: 'localhost:8443', origin: LOCAL_ORIGIN, 'content-type': 'multipart/form-data; boundary=exact',
      cookie: 'real=browser-cookie', authorization: 'Bearer application-jwt', 'idempotency-key': 'synthetic-key',
      'x-serverless-authorization': 'browser-supplied', 'x-feedback-verify-control': 'browser-control' } })
  const response = new Response()
  const bytes: Buffer[] = []
  let answer: PassThrough
  const transport = vi.fn((_options, callback) => {
    const upstream = new Writable({ write(chunk, _encoding, next) { bytes.push(Buffer.from(chunk)); next() } })
    if (!hold) upstream.once('finish', () => {
      answer = Object.assign(new PassThrough(), { statusCode: 200, headers: { 'content-type': 'image/png',
        'set-cookie': ['access=a; Secure; HttpOnly; Path=/', 'refresh=b; Secure; HttpOnly; Path=/api/auth'] } })
      callback(answer)
      answer.end(answerBody)
    })
    return upstream
  })
  const events: unknown[] = []
  proxyHandler(manifest(), { cloudRequest: transport, tokenReader: () => 'server-only-token', fault,
    onResponse: event => events.push(event) })(request, response)
  return { request, response, transport, bytes, events, upstream: transport.mock.results[0].value }
}

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  vi.unstubAllEnvs()
  for (const dir of temporary.splice(0)) fs.rmSync(dir, { recursive: true, force: true })
})

describe('disposable feedback verification trust boundaries', () => {
  it('accepts only private regular inputs and a fresh token for the fixed service', () => {
    const dir = directory(), file = path.join(dir, 'input')
    fs.writeFileSync(file, 'private', { mode: 0o600 })
    expect(privateFile(file).toString()).toBe('private')
    fs.chmodSync(file, 0o644)
    expect(() => privateFile(file)).toThrow('private-file-permissions')
    fs.chmodSync(file, 0o600)
    fs.symlinkSync(file, path.join(dir, 'link'))
    expect(() => privateFile(path.join(dir, 'link'))).toThrow('private-file-unavailable')
    expect(() => privateFile(file, 3)).toThrow('private-file-permissions')
    const config = manifest(dir)
    expect(validateManifest(config)).toEqual(config)
    for (const change of [{ expected_project: 'production-other' }, { service_origin: 'https://attacker.example' },
      { service_audience: 'https://different.run.app' }, { extra: 'secret' }]) {
      expect(() => validateManifest({ ...config, ...change })).toThrow()
    }
    const token = (aud: string, exp: number) => 'e30.' + Buffer.from(JSON.stringify({ aud, exp })).toString('base64url') + '.c2ln'
    expect(audienceToken(token(config.service_origin, 200), config.service_origin, 100_000)).toContain('.c2ln')
    expect(() => audienceToken(token('elsewhere', 200), config.service_origin, 100_000)).toThrow('service-token-scope')
    expect(() => audienceToken(token(config.service_origin, 150), config.service_origin, 100_000)).toThrow('service-token-scope')
  })

  it('keeps browser requests on the local app and never exposes control routes', () => {
    const headers = { host: 'localhost:8443', origin: LOCAL_ORIGIN }
    expect(browserRoute('/api/feedback?status=new', 'GET', headers)).toBe('api')
    expect(browserRoute('/terms', 'GET', headers)).toBe('frontend')
    for (const url of ['https://attacker.example/api/feedback', '//attacker.example/api', '/__feedback_verify/receipt',
      '/%5f_feedback_verify/fixtures', '/api/../__feedback_verify/receipt', '/api/%2e%2e/receipt',
      '/api%2ffeedback', '/api/%255f_feedback_verify', '/api/\\host']) {
      expect(() => browserRoute(url, 'GET', headers)).toThrow()
    }
    expect(() => browserRoute('/api/feedback', 'POST', { host: headers.host })).toThrow('write-origin')
    expect(() => browserRoute('/api/feedback', 'GET', { ...headers, origin: 'https://evil.example' })).toThrow('browser-origin')
    expect(() => browserRoute('/api/feedback', 'GET', { ...headers, host: 'evil.example' })).toThrow('browser-host')
    expect(() => browserRoute('/terms', 'POST', headers)).toThrow('frontend-method')
  })

  it('isolates IAM credentials, rejects redirects and preserves binary bodies plus real cookie attributes', async () => {
    const clean = forwardedHeaders({ connection: 'x-remove', 'x-remove': 'secret', 'x-feedback-verify-run': '123-1',
      'x-serverless-authorization': 'spoofed', 'x-forwarded-host': 'evil', authorization: 'Bearer app', cookie: 'a=b' }, 'api', 'iam')
    expect(clean).toEqual({ authorization: 'Bearer app', cookie: 'a=b', 'x-serverless-authorization': 'Bearer iam' })
    expect(forwardedHeaders({ 'x-serverless-authorization': 'spoofed' }, 'frontend')).not.toHaveProperty('x-serverless-authorization')
    expect(() => responseHeaders({ location: 'https://elsewhere.example' }, 302, 'api')).toThrow('upstream-redirect')
    expect(() => responseHeaders({ location: '//elsewhere.example' }, 302, 'frontend')).toThrow('upstream-redirect')
    expect(() => responseHeaders({ 'set-cookie': ['auth=x; Domain=.earningsnerd.io'] }, 200, 'api')).toThrow('upstream-cookie-domain')
    expect(responseHeaders({ location: '/login' }, 307, 'frontend').location).toBe('/login')
    const body = Buffer.from([0, 255, 13, 10, 1, 128]), x = exchange({ answerBody: body })
    const done = finished(x.response)
    x.request.end(body)
    await done
    expect(Buffer.concat(x.bytes)).toEqual(body)
    expect(Buffer.concat(x.response.chunks)).toEqual(body)
    expect(x.transport.mock.calls[0][0]).toMatchObject({ hostname: 'earningsnerd-feedback-verify-123.us-west1.run.app',
      port: 443, path: '/api/feedback/with-attachments', headers: { 'content-type': 'multipart/form-data; boundary=exact',
        cookie: 'real=browser-cookie', authorization: 'Bearer application-jwt', 'x-serverless-authorization': 'Bearer server-only-token' } })
    expect(x.transport.mock.calls[0][0].headers).not.toHaveProperty('x-feedback-verify-control')
    expect(x.response.headers['set-cookie']).toEqual(['access=a; Secure; HttpOnly; Path=/', 'refresh=b; Secure; HttpOnly; Path=/api/auth'])
  })

  it('bounds streamed bodies and cancels upstream work on disconnect or deadline', async () => {
    const oversized = exchange({ hold: true })
    const done = finished(oversized.response)
    oversized.request.end(Buffer.alloc(MAX_BODY_BYTES + 1))
    await done
    expect(oversized.response.status).toBe(413)
    expect(oversized.upstream.destroyed).toBe(true)
    const disconnected = exchange({ hold: true })
    disconnected.request.emit('aborted')
    expect(disconnected.upstream.destroyed).toBe(true)
    vi.useFakeTimers()
    const stalled = exchange({ hold: true })
    await vi.advanceTimersByTimeAsync(DEADLINE_MS)
    expect(stalled.response.status).toBe(504)
    expect(stalled.upstream.destroyed).toBe(true)
  })

  it('drops a response only after the real upstream has accepted the complete submission', async () => {
    const fault = { armed: true, saved: false }, x = exchange({ fault })
    expect(fault.saved).toBe(false)
    const closed = new Promise(resolve => x.response.once('close', resolve))
    x.request.end(Buffer.from('real-multipart-body'))
    await closed
    expect(fault).toEqual({ armed: false, saved: true })
    expect(Buffer.concat(x.bytes).toString()).toBe('real-multipart-body')
    expect(x.response.chunks).toEqual([])
    expect(x.events).toEqual([{ path: '/api/feedback/with-attachments', method: 'POST', status: 200, key: 'synthetic-key', dropped: true }])
  })

  it('starts concurrent boundary uploads and recovers documented busy responses with the same bytes and UUID under a retry bound', async () => {
    const keys = ['00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000002']
    const uploads = []
    let releaseFirst
    const initial = new Promise(resolve => { releaseFirst = resolve })
    const delay = vi.fn(async () => {})
    const fetch = vi.fn(async (url, options) => {
      if (options.method === 'POST') {
        uploads.push(options)
        const key = options.headers['idempotency-key']
        if (uploads.length === 1) await initial
        if (uploads.length === 2 && key === keys[1]) { releaseFirst(); return new globalThis.Response('{}', { status: 503, headers: { 'retry-after': '5' } }) }
        return new globalThis.Response('{}', { status: 201 })
      }
      const key = url.split('/').at(-1)
      const retried = uploads.filter(upload => upload.headers['idempotency-key'] === key).length > 1
      return globalThis.Response.json({ submission_id: key, state: key === keys[0] || retried ? 'submitted' : 'retryable',
        feedback: { id: key === keys[0] ? 4 : 5 } })
    })
    const input = { base64: Buffer.from('synthetic-image').toString('base64'), keys, readerId: 1 }
    expect(await boundaryUploadWorkload(input, { fetch, delay })).toEqual([4, 5])
    expect(uploads).toHaveLength(3)
    expect(uploads[2].body).toBe(uploads[1].body)
    expect(uploads[2].headers).toEqual(uploads[1].headers)
    expect(delay).toHaveBeenCalledExactlyOnceWith(5000)
    // A permanent busy service must stop after the allowed attempts without minting another key.
    const busy = vi.fn(async (_url, options) => options.method === 'POST'
      ? new globalThis.Response('{}', { status: 503, headers: { 'retry-after': '5' } })
      : globalThis.Response.json({ submission_id: keys[0], state: 'retryable' }))
    await expect(boundaryUploadWorkload(input, { fetch: busy, delay })).rejects.toThrow('boundary-retry-limit')
    expect(busy.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(4)
  })

  it('does not make even a cleanup call when protected Ops invocation is absent', async () => {
    const dir = directory(), file = path.join(dir, 'manifest.json')
    const config = manifest(dir)
    fs.writeFileSync(file, JSON.stringify(config), { mode: 0o600 })
    const claims = Buffer.from(JSON.stringify({ aud: config.service_audience, exp: Math.floor(Date.now() / 1000) + 3600 })).toString('base64url')
    fs.writeFileSync(config.id_token_file, 'e30.' + claims + '.c2ln', { mode: 0o600 })
    fs.writeFileSync(config.control_token_file, 'a'.repeat(64), { mode: 0o600 })
    const remote = vi.spyOn(https, 'request').mockImplementation(() => { throw new Error('unexpected remote action') })
    vi.stubEnv('GITHUB_ACTIONS', 'false')
    expect(await run(file)).toEqual({ status: 'failed', stage: 'manifest', reason: 'approved-ops-invocation' })
    expect(remote).not.toHaveBeenCalled()
  })

  it('saves only a fully bound counts-only receipt and fixture identities for this run', () => {
    const config = manifest(), valid = receipt(config)
    expect(receiptEnvelope(valid, config)).toBe(valid)
    for (const change of [value => { value.payload.frontend_tree = 'f'.repeat(40) },
      value => { value.payload.observed.database.pending = 1 },
      value => { value.payload.observed.database.confirmed_generation_deletions = 14 },
      value => { value.payload.observed.resources.acceptance_passed = false },
      value => { value.payload.observed.resources.conservative_process_bound_bytes = 'private' },
      value => { value.payload.observed.resources.evidence_basis = 'unsupported' },
      value => { value.payload.observed.notifications.secret = 'credential' },
      value => { value.payload.observed.notifications.attachment_counts[0] = 'credential' },
      value => { value.payload.observed.resources.method = 'credential' },
      value => { value.payload.extra = 'credential' }]) {
      const invalid = structuredClone(valid); change(invalid)
      expect(() => receiptEnvelope(invalid, config)).toThrow()
    }
    expect(safeFailure('browser', new Error('password=private'))).toEqual({ status: 'failed', stage: 'browser', reason: 'verification-unavailable' })
    const fixtures = { schema: 1, run_id: config.run_id, accounts: Object.fromEntries(['owner', 'other', 'admin'].map((role, i) =>
      [role, { id: i + 1, email: `feedback-verify+${config.run_id}-${role}@example.com`, password: 'private-synthetic-password' }])) }
    expect(validateFixtures(fixtures, config.run_id)).toBe(fixtures.accounts)
    expect(() => validateFixtures(fixtures, '999-1')).toThrow('fixture-run')
    fixtures.accounts.owner.email = 'real-user@example.com'
    expect(() => validateFixtures(fixtures, config.run_id)).toThrow('fixture-account')
  })
})
