/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['recharts'],
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'https://api.earningsnerd.io',
  },
  webpack: (config, { isServer }) => {
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

