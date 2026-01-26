/** @type {import('next').NextConfig} */
const { withSentryConfig } = require('@sentry/nextjs')

const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['recharts'],
  env: {
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL ||
      (process.env.NODE_ENV === 'production' ? 'https://api.earningsnerd.io' : 'http://localhost:8000'),
    NEXT_PUBLIC_SENTRY_DSN:
      process.env.NEXT_PUBLIC_SENTRY_DSN ||
      'https://ece733dc1e5aa4e794d80f2bcc498e24@o4510744719851520.ingest.de.sentry.io/4510744722276432',
    SENTRY_DSN:
      process.env.SENTRY_DSN ||
      'https://ece733dc1e5aa4e794d80f2bcc498e24@o4510744719851520.ingest.de.sentry.io/4510744722276432',
    // Feature flags for UI simplification
    // Set to 'true' to enable legacy tabbed UI, 'false' for simplified single-view
    NEXT_PUBLIC_ENABLE_SECTION_TABS: process.env.NEXT_PUBLIC_ENABLE_SECTION_TABS || 'false',
    // Set to 'true' to show financial charts, 'false' to hide them
    NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS: process.env.NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS || 'false',
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