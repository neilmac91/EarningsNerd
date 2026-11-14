// @vitest-environment node
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { afterEach, describe, expect, it, vi } from 'vitest'

/**
 * lib/sentryOnWorkers.ts changes Sentry.init for the Next server on Cloudflare Workers and must change nothing on
 * Vercel. Each case imports the module afresh under the runtime it names, since the module reads the runtime once.
 */
const integrations = [{ name: 'ConsoleLogs' }] as never[]

async function load(runtime: { nextRuntime?: string; userAgent?: string }) {
  vi.resetModules()
  vi.stubEnv('NEXT_RUNTIME', runtime.nextRuntime ?? '')
  vi.stubGlobal('navigator', runtime.userAgent ? { userAgent: runtime.userAgent } : undefined)
  return import('@/lib/sentryOnWorkers')
}

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
})

describe('Sentry options for the Next server on Cloudflare Workers', () => {
  it('are what instrumentation.ts passes to Sentry.init, with no integrations or transport of its own', () => {
    // Nothing else notices if instrumentation.ts stops using them: the hook still loads, Vercel is unchanged, and
    // the server Worker goes back to reporting nothing.
    const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
    const source = readFileSync(path.join(frontend, 'instrumentation.ts'), 'utf8')
    const init = source.slice(source.indexOf('Sentry.init({'), source.indexOf('export const onRequestError'))
    expect(init).toContain('...sentryOptionsOnWorkers([')
    expect(init).not.toMatch(/^\s*(integrations|transport):/m)
  })

  it('passes the integrations through untouched on Vercel (Node) and in the edge runtime', async () => {
    for (const runtime of [
      { nextRuntime: 'nodejs', userAgent: 'Node.js/22' },
      { nextRuntime: 'nodejs' },
      { nextRuntime: 'edge', userAgent: 'Cloudflare-Workers' },
    ]) {
      const { sentryOptionsOnWorkers } = await load(runtime)
      expect(sentryOptionsOnWorkers(integrations), JSON.stringify(runtime)).toEqual({ integrations })
    }
  })

  it('on Workers, sends with fetch and drops ContextLines from the defaults, keeping the rest and our own', async () => {
    const { sentryOptionsOnWorkers, sentryFetchTransport } = await load({ nextRuntime: 'nodejs', userAgent: 'Cloudflare-Workers' })
    const options = sentryOptionsOnWorkers(integrations)
    expect(options.transport).toBe(sentryFetchTransport)
    const defaults = [{ name: 'Dedupe' }, { name: 'ContextLines' }, { name: 'Http' }] as never[]
    const chosen = (options.integrations as (defaults: never[]) => Array<{ name: string }>)(defaults)
    expect(chosen.map((integration) => integration.name)).toEqual(['Dedupe', 'Http', 'ConsoleLogs'])
  })

  it('posts an envelope to the address Sentry gives it and reports the status and rate-limit headers', async () => {
    const { sentryFetchTransport } = await load({ nextRuntime: 'nodejs', userAgent: 'Cloudflare-Workers' })
    const fetchMock = vi.fn(async () => new Response('{}', { status: 429, headers: { 'Retry-After': '60', 'X-Sentry-Rate-Limits': '60:error' } }))
    vi.stubGlobal('fetch', fetchMock)
    const transport = sentryFetchTransport({
      url: 'https://sentry.invalid/api/1/envelope/',
      headers: { 'x-test': '1' },
      recordDroppedEvent: () => {},
    } as never)
    const result = await transport.send([{ event_id: 'abc' }, [[{ type: 'event' }, { message: 'boom' }]]] as never)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('https://sentry.invalid/api/1/envelope/')
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual({ 'x-test': '1' })
    expect(String(init.body)).toContain('"message":"boom"')
    expect(result).toMatchObject({ statusCode: 429, headers: { 'retry-after': '60', 'x-sentry-rate-limits': '60:error' } })
  })
})
