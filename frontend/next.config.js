/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['recharts'],
  env: {
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL || 
      (process.env.NODE_ENV === 'production' ? 'https://api.earningsnerd.io' : 'http://localhost:8000'),
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

module.exports = nextConfig