import * as Sentry from '@sentry/nextjs'
import { SENTRY_CONSOLE_LOG_LEVELS, SENTRY_DATA_COLLECTION, SENTRY_TELEMETRY_PRIVACY } from './lib/sentryConfig'
import { sentryOptionsOnWorkers } from './lib/sentryOnWorkers'

export async function register() {
    if (process.env.NEXT_RUNTIME === 'nodejs' || process.env.NEXT_RUNTIME === 'edge') {
        Sentry.init({
            dsn: process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN,
            // Release/environment mirror the client (deployed git SHA + deploy target) so server and
            // client errors group under one release.
            release: process.env.NEXT_PUBLIC_SENTRY_RELEASE || process.env.VERCEL_GIT_COMMIT_SHA || undefined,
            environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || process.env.VERCEL_ENV || undefined,
            dataCollection: SENTRY_DATA_COLLECTION,
            ...SENTRY_TELEMETRY_PRIVACY,
            // On Vercel this is the integrations list alone. On Cloudflare Workers the Next server also needs a
            // transport and one default integration removed, or it reports nothing (lib/sentryOnWorkers.ts).
            ...sentryOptionsOnWorkers([
                // v11 removed enableLogs. Calling this integration is now the log opt-in.
                Sentry.consoleLoggingIntegration({ levels: [...SENTRY_CONSOLE_LOG_LEVELS] }),
            ]),
        })
    }
}

export const onRequestError = Sentry.captureRequestError
