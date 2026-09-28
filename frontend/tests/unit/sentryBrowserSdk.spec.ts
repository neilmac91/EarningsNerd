import { afterEach, expect, it } from 'vitest'
import * as Sentry from '@sentry/nextjs'
import { SENTRY_BROWSER_SESSION_LIFECYCLE, SENTRY_CONSOLE_LOG_LEVELS, SENTRY_DATA_COLLECTION, SENTRY_REPLAY_SAMPLE_RATES } from '@/lib/sentryConfig'

afterEach(async () => {
  Sentry.setUser(null)
  await Sentry.close(2000)
})

it('loads the real browser SDK and captures an exception with user context', async () => {
  const envelopes: unknown[] = []
  Sentry.init({
    dsn: 'https://public@example.invalid/1',
    defaultIntegrations: false,
    autoSessionTracking: false,
    dataCollection: SENTRY_DATA_COLLECTION,
    ...SENTRY_REPLAY_SAMPLE_RATES,
    integrations: [
      Sentry.browserSessionIntegration({ lifecycle: SENTRY_BROWSER_SESSION_LIFECYCLE }),
      Sentry.consoleLoggingIntegration({ levels: [...SENTRY_CONSOLE_LOG_LEVELS] }),
    ],
    transport: () => ({
      send: async (envelope) => {
        envelopes.push(envelope)
        return { statusCode: 200 }
      },
      flush: async () => true,
    }),
  })
  const client = Sentry.getClient()
  expect(client).toBeInstanceOf(Sentry.BrowserClient)
  expect(client?.getOptions()).toMatchObject({
    dataCollection: SENTRY_DATA_COLLECTION,
    ...SENTRY_REPLAY_SAMPLE_RATES,
  })
  expect(client?.getIntegrationByName('BrowserSession')).toBeDefined()
  expect(client?.getIntegrationByName('ConsoleLogs')).toBeDefined()
  Sentry.setUser({ id: 'browser-sdk-regression' })
  const eventId = Sentry.captureException(new Error('browser-sdk-capture-sentinel'))
  expect(await Sentry.flush(2000)).toBe(true)

  // Only transport is replaced; SDK event construction, capture, and context remain real.
  const sent = JSON.stringify(envelopes)
  expect(envelopes).toHaveLength(1)
  expect(sent).toContain(eventId)
  expect(sent).toContain('browser-sdk-capture-sentinel')
  expect(sent).toContain('browser-sdk-regression')
})
