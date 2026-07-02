/** @type {import('next').NextConfig} */
const { withSentryConfig } = require('@sentry/nextjs')

const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['recharts'],
  images: {
    // Logo.dev's ticker-keyed logo CDN (see CompanyLogo.tsx). Hotlinked directly —
    // no proxy needed since its token is a publishable, client-safe identifier.
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'img.logo.dev',
        pathname: '/ticker/**',
      },
    ],
  },
  env: {
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL ||
      (process.env.NODE_ENV === 'production' ? 'https://api.earningsnerd.io' : 'http://localhost:8000'),
    // Sentry DSN should be configured via environment variables only (no hardcoded fallback)
    NEXT_PUBLIC_SENTRY_DSN: process.env.NEXT_PUBLIC_SENTRY_DSN || '',
    SENTRY_DSN: process.env.SENTRY_DSN || '',
    // Sentry release = deployed git SHA, so frontend errors are attributable to an exact build.
    // Vercel injects VERCEL_GIT_COMMIT_SHA at build time; fall back to an explicit override or ''.
    NEXT_PUBLIC_SENTRY_RELEASE:
      process.env.NEXT_PUBLIC_SENTRY_RELEASE || process.env.VERCEL_GIT_COMMIT_SHA || '',
    // Deploy target (production/preview/development) for Sentry environment tagging.
    NEXT_PUBLIC_SENTRY_ENVIRONMENT:
      process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || process.env.VERCEL_ENV || process.env.NODE_ENV || 'development',
    // Feature flags for UI simplification
    // Set to 'true' to enable legacy tabbed UI, 'false' for simplified single-view
    NEXT_PUBLIC_ENABLE_SECTION_TABS: process.env.NEXT_PUBLIC_ENABLE_SECTION_TABS || 'false',
    // Set to 'true' to show financial charts, 'false' to hide them
    NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS: process.env.NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS || 'false',
  },
  async headers() {
    // Site-wide security headers (the API sets its own; these cover the Vercel-served app pages).
    // Clickjacking is blocked two ways: X-Frame-Options for older browsers and CSP frame-ancestors
    // for modern ones. A full resource CSP (default-src/script-src/…) is deliberately deferred to a
    // follow-up so it can roll out report-only first without risking breakage — frame-ancestors
    // alone only governs who may frame the page, so it is safe to enforce now.
    // Referrer-Policy strict-origin-when-cross-origin sends only the origin cross-origin, so a
    // single-use token in a URL (invite / reset / verify) can't leak to a third party via Referer;
    // this one site-wide policy supersedes the former /register-only no-referrer (kept unambiguous
    // to avoid Next.js emitting duplicate Referrer-Policy headers when rules overlap).
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'Content-Security-Policy', value: "frame-ancestors 'none'" },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        ],
      },
    ]
  },
  webpack: (config, { isServer }) => {
    // TODO: Revisit this webpack configuration when Next.js or recharts has better support for lodash.
    // This is a workaround for a known issue with recharts and lodash compatibility.
    // See: https://github.com/recharts/recharts/issues/2372
    // Fix for Recharts/lodash compatibility issue
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
      }
    }
    
    // Ensure lodash and its submodules are resolved correctly
    const path = require('path')
    const lodashPath = path.dirname(require.resolve('lodash/package.json'))
    
    config.resolve.alias = {
      ...config.resolve.alias,
      'lodash$': lodashPath,
      'lodash/isEqual': path.join(lodashPath, 'isEqual.js'),
      'lodash/throttle': path.join(lodashPath, 'throttle.js'),
      'lodash/merge': path.join(lodashPath, 'merge.js'),
    }
    
    // Also ensure modules can resolve lodash submodules
    config.resolve.modules = [
      ...(config.resolve.modules || []),
      path.join(__dirname, 'node_modules'),
    ]
    
    return config
  },
}

const sentryOptions = {
  // Avoid Sentry CLI noise during local builds.
  silent: true,
}

module.exports = withSentryConfig(nextConfig, sentryOptions)