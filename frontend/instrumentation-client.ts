import * as Sentry from "@sentry/nextjs";
import {
  SENTRY_BROWSER_SESSION_LIFECYCLE,
  SENTRY_CONSOLE_LOG_LEVELS,
  SENTRY_DATA_COLLECTION,
  SENTRY_REPLAY_SAMPLE_RATES,
  SENTRY_TELEMETRY_PRIVACY,
} from "./lib/sentryConfig";
import { installTelemetryNavigationGuard, protectTelemetryRoute, sanitizeTelemetryUrl } from './lib/telemetryPrivacy'

installTelemetryNavigationGuard()

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  // Release = deployed git SHA (Vercel build), environment = deploy target — so client errors are
  // attributable to an exact build + env. Empty string → undefined so Sentry falls back to defaults.
  release: process.env.NEXT_PUBLIC_SENTRY_RELEASE || undefined,
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || undefined,
  dataCollection: SENTRY_DATA_COLLECTION,
  ...SENTRY_REPLAY_SAMPLE_RATES,
  ...SENTRY_TELEMETRY_PRIVACY,
  integrations: [
    // v11 defaults to one browser session per page load; retain v10's route lifecycle.
    Sentry.browserSessionIntegration({ lifecycle: SENTRY_BROWSER_SESSION_LIFECYCLE }),
    // v11 removed enableLogs. Calling this integration is now the log opt-in.
    Sentry.consoleLoggingIntegration({ levels: [...SENTRY_CONSOLE_LOG_LEVELS] }),
  ],
});

export const onRouterTransitionStart: typeof Sentry.captureRouterTransitionStart = (url, ...args) => {
  // Runs before the router changes the address or renders the sensitive page.
  protectTelemetryRoute(url)
  Sentry.captureRouterTransitionStart(sanitizeTelemetryUrl(url), ...args)
}
