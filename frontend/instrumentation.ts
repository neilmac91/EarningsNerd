import * as Sentry from '@sentry/nextjs'
import { SENTRY_CONSOLE_LOG_LEVELS, SENTRY_DATA_COLLECTION } from './lib/sentryConfig'

export async function register() {
    if (process.env.NEXT_RUNTIME === 'nodejs' || process.env.NEXT_RUNTIME === 'edge') {
        Sentry.init({
            dsn: process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN,
            // Release/environment mirror the client (deployed git SHA + deploy target) so server and
            // client errors group under one release.
            release: process.env.NEXT_PUBLIC_SENTRY_RELEASE || process.env.VERCEL_GIT_COMMIT_SHA || undefined,
            environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || process.env.VERCEL_ENV || undefined,
            dataCollection: SENTRY_DATA_COLLECTION,
            integrations: [
                // v11 removed enableLogs. Calling this integration is now the log opt-in.
                Sentry.consoleLoggingIntegration({ levels: [...SENTRY_CONSOLE_LOG_LEVELS] }),
            ],
        })
    }
}

export const onRequestError = Sentry.captureRequestError
