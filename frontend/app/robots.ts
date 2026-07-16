import type { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        // Keep crawl budget on the content surface: API proxies, authed app chrome, and the
        // auth/utility flows (which carry no indexable content and would otherwise surface as
        // duplicate generic titles). NOT listed: /company, /filing, /pricing, legal pages.
        disallow: [
          '/api/',
          '/dashboard',
          '/admin',
          '/profile',
          '/settings',
          '/login',
          '/register',
          '/check-email',
          '/verify-email',
          '/forgot-password',
          '/reset-password',
          '/delete-account',
        ],
      },
    ],
    sitemap: 'https://www.earningsnerd.io/sitemap.xml',
  }
}
