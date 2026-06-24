import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  // Release = deployed git SHA (Vercel build), environment = deploy target — so client errors are
  // attributable to an exact build + env. Empty string → undefined so Sentry falls back to defaults.
  release: process.env.NEXT_PUBLIC_SENTRY_RELEASE || undefined,
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || undefined,
  enableLogs: true,
  integrations: [
    Sentry.consoleLoggingIntegration({ levels: ["log", "warn", "error"] }),
  ],
});

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
