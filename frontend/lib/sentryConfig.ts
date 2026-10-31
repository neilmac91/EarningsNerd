import type * as Sentry from '@sentry/nextjs'
import { sanitizeTelemetry } from './telemetryPrivacy'

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
  urlQueryParams: false,
  genAI: { inputs: false, outputs: false },
  databaseQueryData: false,
  queues: false,
  graphQL: { document: false, variables: false },
} satisfies SentryDataCollection

// Query filtering does not cover fragments, nested extras, messages or structured logs.
export const SENTRY_TELEMETRY_PRIVACY = {
  beforeSend: (event) => sanitizeTelemetry(event),
  beforeBreadcrumb: (breadcrumb) => sanitizeTelemetry(breadcrumb),
  beforeSendLog: (log) => sanitizeTelemetry(log),
  beforeSendSpan: (span) => sanitizeTelemetry(span),
} satisfies Pick<NonNullable<Parameters<typeof Sentry.init>[0]>, 'beforeSend' | 'beforeBreadcrumb' | 'beforeSendLog' | 'beforeSendSpan'>

// Keep the browser behavior explicit across SDK majors.
export const SENTRY_BROWSER_SESSION_LIFECYCLE = 'route' as const
export const SENTRY_CONSOLE_LOG_LEVELS = ['warn', 'error'] as const
export const SENTRY_REPLAY_SAMPLE_RATES = {
  replaysSessionSampleRate: 0,
  replaysOnErrorSampleRate: 0,
} as const
