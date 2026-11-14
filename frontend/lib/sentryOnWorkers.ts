import * as Sentry from '@sentry/nextjs'

type InitOptions = NonNullable<Parameters<typeof Sentry.init>[0]>
type TransportOptions = Parameters<NonNullable<InitOptions['transport']>>[0]
type Integration = Extract<InitOptions['integrations'], unknown[]>[number]

/**
 * True for the Next server (the Node build of the SDK) when it runs in the Cloudflare Workers runtime, which names
 * itself in `navigator.userAgent`. Node names itself "Node.js/<major>", so this is false on Vercel and in tests; the
 * middleware's edge build of the SDK needs none of this.
 */
export const NODE_SDK_ON_WORKERS =
  process.env.NEXT_RUNTIME === 'nodejs' &&
  typeof navigator !== 'undefined' &&
  navigator.userAgent === 'Cloudflare-Workers'

/**
 * Sends Sentry's envelopes with `fetch`. The Node SDK's own transport uses `node:https`, and on Workers a send
 * through it never completes.
 */
export function sentryFetchTransport(options: TransportOptions) {
  return Sentry.createTransport(options, async (request) => {
    const response = await fetch(options.url, {
      method: 'POST',
      body: request.body as BodyInit,
      headers: options.headers,
    })
    return {
      statusCode: response.status,
      headers: {
        'x-sentry-rate-limits': response.headers.get('X-Sentry-Rate-Limits'),
        'retry-after': response.headers.get('Retry-After'),
      },
    }
  })
}

/**
 * The SDK's default integrations without ContextLines, which reads each stack frame's source file from disk to
 * quote the lines around it. A Worker has no such files, and there the read never returns, so no error event is
 * ever sent.
 */
export const withoutContextLines = (defaults: Integration[]): Integration[] =>
  defaults.filter((integration) => integration.name !== 'ContextLines')

/**
 * What instrumentation.ts adds to Sentry.init for the Next server on Workers, and nothing anywhere else. Measured on
 * a deployed Worker: with the SDK's defaults, none of the server's errors reached Sentry; with these two, all did
 * (docs/DEPLOYMENT.md, "Frontend on Cloudflare Workers (staging)").
 */
export function sentryOptionsOnWorkers(integrations: Integration[]): Pick<InitOptions, 'integrations' | 'transport'> {
  if (!NODE_SDK_ON_WORKERS) return { integrations }
  return {
    transport: sentryFetchTransport,
    integrations: (defaults) => [...withoutContextLines(defaults), ...integrations],
  }
}
