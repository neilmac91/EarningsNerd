import * as Sentry from '@sentry/nextjs'

export async function register() {
    if (process.env.NEXT_RUNTIME === 'nodejs') {
        Sentry.init({
            dsn: process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN,
            enableLogs: true,
            integrations: [
                Sentry.consoleLoggingIntegration({ levels: ["warn", "error"] }),
            ],
        })
    }

    if (process.env.NEXT_RUNTIME === 'edge') {
        Sentry.init({
            dsn: process.env.SENTRY_DSN || process.env.NEXT_PUBLIC_SENTRY_DSN,
            enableLogs: true,
            integrations: [
                Sentry.consoleLoggingIntegration({ levels: ["warn", "error"] }),
            ],
        })
    }
}

export const onRequestError = Sentry.captureRequestError
