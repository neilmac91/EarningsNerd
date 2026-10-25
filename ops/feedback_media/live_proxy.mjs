/** Test-only HTTPS bridge for the founder-approved disposable feedback verification service. */
import fs from 'node:fs'
import http from 'node:http'
import https from 'node:https'
import { Transform } from 'node:stream'

export const LOCAL_ORIGIN = 'https://localhost:8443'
export const FRONTEND_PORT = 3141
export const MAX_BODY_BYTES = 16 * 1024 * 1024
export const MAX_RESPONSE_BYTES = 32 * 1024 * 1024
export const DEADLINE_MS = 90_000
const PRIVATE_HEADERS = /^(?:x-serverless-authorization|x-feedback-verify-|proxy-|forwarded$|x-forwarded-)/i
const HOP_HEADERS = new Set(['connection', 'keep-alive', 'transfer-encoding', 'te', 'trailer', 'upgrade', 'proxy-authenticate', 'proxy-authorization'])
const DIGEST = /^[a-f0-9]{64}$/
const MANIFEST_KEYS = ['version', 'run_id', 'service_origin', 'service_audience', 'expected_project', 'expected_service',
  'runtime_source_sha256', 'verification_suite_sha256', 'frontend_tree', 'image_digest', 'id_token_file',
  'control_token_file', 'cert_file', 'key_file', 'output_dir']

export class VerificationError extends Error {
  constructor(code) { super(code); this.name = 'VerificationError' }
}
export function check(condition, code) { if (!condition) throw new VerificationError(code) }

/** O_NOFOLLOW + fstat keep privileged inputs from becoming symlink or non-private file reads. */
export function privateFile(file, maxBytes = 32_768) {
  check(typeof file === 'string' && file.startsWith('/'), 'private-file-path')
  let descriptor
  try {
    descriptor = fs.openSync(file, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW)
    const stat = fs.fstatSync(descriptor)
    check(stat.isFile() && (stat.mode & 0o777) === 0o600
      && stat.uid === process.getuid() && stat.size > 0 && stat.size <= maxBytes, 'private-file-permissions')
    return fs.readFileSync(descriptor)
  } catch (error) {
    if (error instanceof VerificationError) throw error
    throw new VerificationError('private-file-unavailable')
  } finally { if (descriptor !== undefined) fs.closeSync(descriptor) }
}

export function validateManifest(value) {
  check(value && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join('|') === [...MANIFEST_KEYS].sort().join('|'), 'manifest-fields')
  check(value.version === 1 && /^\d+-1$/.test(value.run_id), 'manifest-run')
  check(value.expected_project === 'earnings-nerd' && value.expected_service === 'earningsnerd-feedback-verify', 'manifest-resource')
  check(typeof value.service_origin === 'string'
    && /^https:\/\/earningsnerd-feedback-verify-[a-z0-9-]+(?:\.[a-z0-9-]+)*\.run\.app$/.test(value.service_origin)
    && value.service_audience === value.service_origin, 'manifest-origin')
  check(DIGEST.test(value.runtime_source_sha256) && DIGEST.test(value.verification_suite_sha256)
    && /^[a-f0-9]{40}$/.test(value.frontend_tree) && /^sha256:[a-f0-9]{64}$/.test(value.image_digest), 'manifest-digests')
  for (const key of ['id_token_file', 'control_token_file', 'cert_file', 'key_file', 'output_dir']) {
    check(typeof value[key] === 'string' && value[key].startsWith('/') && !/[\r\n\0]/.test(value[key]), 'manifest-path')
  }
  return Object.freeze({ ...value })
}

export function readManifest(file) {
  try { return validateManifest(JSON.parse(privateFile(file).toString('utf8'))) }
  catch (error) { if (error instanceof VerificationError) throw error; throw new VerificationError('manifest-json') }
}

/** Cloud Run verifies the signature; this local check rejects a stale or wrong-audience credential before use. */
export function audienceToken(token, audience, now = Date.now()) {
  check(typeof token === 'string' && token.length <= 16_384 && /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(token), 'service-token-format')
  let claims
  try { claims = JSON.parse(Buffer.from(token.split('.')[1], 'base64url').toString('utf8')) }
  catch { throw new VerificationError('service-token-claims') }
  check(claims.aud === audience && Number.isFinite(claims.exp) && claims.exp * 1000 > now + 60_000, 'service-token-scope')
  return token
}
export function serviceToken(config) {
  return audienceToken(privateFile(config.id_token_file, 16_384).toString('utf8').trim(), config.service_audience)
}

export function browserRoute(rawPath, method, headers) {
  check(headers.host === 'localhost:8443', 'browser-host')
  check(!headers.origin || headers.origin === LOCAL_ORIGIN, 'browser-origin')
  check(typeof rawPath === 'string' && rawPath.length <= 8192 && rawPath.startsWith('/')
    && !rawPath.startsWith('//') && !/[\\\x00-\x20\x7f]/.test(rawPath), 'browser-path')
  const rawName = rawPath.split('?')[0]
  let decoded
  try { decoded = decodeURIComponent(rawName) } catch { throw new VerificationError('browser-path') }
  check(!/%(?:2f|5c|25)/i.test(rawName) && !/[\\\x00-\x20\x7f]/.test(decoded)
    && !/(?:^|\/)\.{1,2}(?:\/|$)/.test(decoded) && !decoded.startsWith('/__feedback_verify'), 'browser-path')
  const api = decoded.startsWith('/api/')
  check(api || method === 'GET' || method === 'HEAD', 'frontend-method')
  check(!api || ['GET', 'HEAD', 'OPTIONS', 'POST', 'PATCH', 'DELETE'].includes(method), 'api-method')
  check(!api || ['GET', 'HEAD', 'OPTIONS'].includes(method) || headers.origin === LOCAL_ORIGIN, 'write-origin')
  return api ? 'api' : 'frontend'
}

export function forwardedHeaders(headers, destination, token) {
  const nominated = new Set(String(headers.connection || '').toLowerCase().split(',').map(x => x.trim()))
  const result = {}
  for (const [key, value] of Object.entries(headers)) {
    const name = key.toLowerCase()
    if (value !== undefined && !HOP_HEADERS.has(name) && !nominated.has(name) && !PRIVATE_HEADERS.test(name) && name !== 'host') result[name] = value
  }
  if (destination === 'api') {
    result['x-serverless-authorization'] = `Bearer ${token}`
  } else if (destination === 'frontend') {
    result.host = 'localhost:8443'
    result['x-forwarded-host'] = 'localhost:8443'
    result['x-forwarded-proto'] = 'https'
  }
  return result
}

export function responseHeaders(headers, status, destination) {
  // No API redirect is followed or relayed: an IAM-bearing request never follows Location.
  if (status >= 300 && status < 400 && status !== 304) {
    check(destination === 'frontend' && typeof headers.location === 'string', 'upstream-redirect')
    let location
    try { location = new URL(headers.location, LOCAL_ORIGIN) } catch { throw new VerificationError('upstream-redirect') }
    check(location.origin === LOCAL_ORIGIN && !headers.location.startsWith('//'), 'upstream-redirect')
  }
  const result = forwardedHeaders(headers, 'response')
  delete result.host
  delete result['x-forwarded-host']
  delete result['x-forwarded-proto']
  // Do not weaken or rewrite cookie attributes. Cookie arrays remain distinct Set-Cookie headers.
  if (headers['set-cookie']) {
    check(Array.isArray(headers['set-cookie']) && headers['set-cookie'].every(cookie =>
      !/;\s*domain=/i.test(cookie)), 'upstream-cookie-domain')
    result['set-cookie'] = headers['set-cookie']
  }
  return result
}

export function byteLimit(maxBytes, code) {
  let received = 0
  return new Transform({ transform(chunk, encoding, done) {
    received += chunk.length
    done(received > maxBytes ? new VerificationError(code) : null, received > maxBytes ? undefined : chunk)
  } })
}

/** Dependencies are injectable only for offline boundary tests; callers cannot choose an upstream in a URL. */
export function proxyHandler(config, { cloudRequest = https.request, frontendRequest = http.request,
  tokenReader = serviceToken, fault = { armed: false }, onResponse = () => {} } = {}) {
  const service = new URL(config.service_origin)
  return (request, response) => {
    let upstream
    let upstreamResponse
    let input
    let timer
    let finished = false
    const end = (code = 'proxy-unavailable', status = 502) => {
      if (finished) return
      finished = true
      clearTimeout(timer)
      request.unpipe(input)
      input?.destroy()
      request.resume()
      upstream?.destroy()
      upstreamResponse?.destroy()
      if (!response.headersSent) response.writeHead(status, { 'content-type': 'text/plain', 'cache-control': 'no-store' })
      response.end(code)
    }
    try {
      const destination = browserRoute(request.url, request.method, request.headers)
      const length = request.headers['content-length']
      check(length === undefined || (/^\d+$/.test(length) && Number(length) <= MAX_BODY_BYTES), 'request-size')
      const headers = forwardedHeaders(request.headers, destination, destination === 'api' ? tokenReader(config) : undefined)
      const options = { hostname: destination === 'api' ? service.hostname : '127.0.0.1',
        port: destination === 'api' ? 443 : FRONTEND_PORT, path: request.url, method: request.method, headers }
      const transport = destination === 'api' ? cloudRequest : frontendRequest
      const loseResponse = destination === 'api' && request.method === 'POST'
        && request.url === '/api/feedback/with-attachments' && fault.armed
      if (loseResponse) fault.armed = false
      upstream = transport(options, (answer) => {
        upstreamResponse = answer
        try {
          const cleaned = responseHeaders(answer.headers, answer.statusCode, destination)
          const output = byteLimit(MAX_RESPONSE_BYTES, 'response-size')
          output.on('error', () => end('response-size'))
          answer.on('error', () => end())
          if (loseResponse) {
            check(answer.statusCode >= 200 && answer.statusCode < 300, 'lost-response-not-saved')
            output.resume()
            output.on('end', () => {
              finished = true
              clearTimeout(timer)
              fault.saved = true
              onResponse({ path: request.url, method: request.method, status: answer.statusCode,
                key: request.headers['idempotency-key'], dropped: true })
              response.destroy()
            })
          } else {
            response.writeHead(answer.statusCode, cleaned)
            output.pipe(response)
            output.on('end', () => {
              finished = true
              clearTimeout(timer)
              onResponse({ path: request.url, method: request.method, status: answer.statusCode,
                key: request.headers['idempotency-key'], dropped: false })
            })
          }
          answer.pipe(output)
        } catch { end() }
      })
      upstream.on('error', () => end())
      timer = setTimeout(() => end('proxy-deadline', 504), DEADLINE_MS)
      input = byteLimit(MAX_BODY_BYTES, 'request-size')
      input.on('error', () => end('request-size', 413))
      request.on('aborted', () => end('client-disconnected'))
      request.on('error', () => end('client-disconnected'))
      response.on('close', () => { if (!finished) end('client-disconnected') })
      request.pipe(input).pipe(upstream)
    } catch (error) { end(error instanceof VerificationError ? error.message : 'proxy-unavailable', 400) }
  }
}

export async function startProxy(config) {
  const fault = { armed: false, saved: false }
  const events = []
  const server = https.createServer({ cert: privateFile(config.cert_file), key: privateFile(config.key_file) },
    proxyHandler(config, { fault, onResponse: event => { if (events.length < 1000) events.push(event) } }))
  server.headersTimeout = 15_000
  server.requestTimeout = DEADLINE_MS
  server.on('clientError', (_error, socket) => socket.destroy())
  server.on('upgrade', (_request, socket) => socket.destroy())
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(8443, '127.0.0.1', resolve) })
  return { events, fault, async close() {
    server.closeAllConnections()
    await new Promise(resolve => server.close(resolve))
  } }
}

/** Server-only control calls; deliberately not exposed by the HTTPS browser proxy. */
export function controlRequest(config, action, body) {
  check(['fixtures', 'receipt', 'cleanup', 'complete'].includes(action), 'control-action')
  const data = body === undefined ? undefined : Buffer.from(JSON.stringify(body))
  check(!data || data.length <= 8192, 'control-size')
  const control = privateFile(config.control_token_file, 1024).toString('utf8').trim()
  check(/^[a-f0-9]{64}$/.test(control), 'control-token-format')
  return new Promise((resolve, reject) => {
    const request = https.request({ hostname: new URL(config.service_origin).hostname, port: 443,
      path: '/__feedback_verify/' + action, method: data ? 'POST' : 'GET',
      headers: { 'x-serverless-authorization': `Bearer ${serviceToken(config)}`,
        'x-feedback-verify-control': control, 'x-feedback-verify-run': config.run_id,
        ...(data ? { 'content-type': 'application/json', 'content-length': data.length } : {}) } }, (answer) => {
      if (answer.statusCode !== 200) { answer.destroy(); reject(new VerificationError('control-rejected')); return }
      const chunks = []
      const limited = byteLimit(128 * 1024, 'control-response-size')
      limited.on('data', chunk => chunks.push(chunk))
      limited.on('error', () => { answer.destroy(); reject(new VerificationError('control-response-size')) })
      answer.on('error', () => reject(new VerificationError('control-unavailable')))
      limited.on('end', () => {
        try { resolve(JSON.parse(Buffer.concat(chunks).toString('utf8'))) }
        catch { reject(new VerificationError('control-json')) }
      })
      answer.pipe(limited)
    })
    const deadline = setTimeout(() => request.destroy(new VerificationError('control-deadline')), DEADLINE_MS)
    request.once('close', () => clearTimeout(deadline))
    request.on('error', () => reject(new VerificationError('control-unavailable')))
    request.end(data)
  })
}
