import type * as Sentry from '@sentry/nextjs'

type SentryDataCollection = NonNullable<Parameters<typeof Sentry.init>[0]['dataCollection']>

// Sentry 11 broadens collection when dataCollection is omitted. Keep the v10 baseline explicit:
// no user/IP inference, cookies, bodies, GraphQL payloads, GenAI content, DB values, or queue args.
export const SENTRY_DATA_COLLECTION = {
  userInfo: false,
  cookies: false,
  httpHeaders: {
    request: { deny: ['forwarded', '-ip', 'remote-', 'via', '-user'] },
    response: { deny: ['forwarded', '-ip', 'remote-', 'via', '-user'] },
  },
  httpBodies: [],
  urlQueryParams: { deny: ['forwarded', '-ip', 'remote-', 'via', '-user'] },
  genAI: { inputs: false, outputs: false },
  databaseQueryData: false,
  queues: false,
  graphQL: { document: false, variables: false },
} satisfies SentryDataCollection

// Keep the browser behavior explicit across SDK majors.
export const SENTRY_BROWSER_SESSION_LIFECYCLE = 'route' as const
export const SENTRY_CONSOLE_LOG_LEVELS = ['warn', 'error'] as const
export const SENTRY_REPLAY_SAMPLE_RATES = {
  replaysSessionSampleRate: 0,
  replaysOnErrorSampleRate: 0,
} as const
