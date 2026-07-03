import type { MetadataRoute } from 'next'

/* PWA manifest — served at /manifest.webmanifest by the App Router.
   Icons come from scripts/generate-brand-assets.mjs: the "any" pair is the
   appicon tile as drawn; the "maskable" pair is full-bleed with the mark at
   0.62 so it survives the r=40% safe-zone crop on Android launchers. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'EarningsNerd',
    short_name: 'EarningsNerd',
    description:
      'AI-powered SEC filing analysis — 10-K and 10-Q summaries with every number traced to the source.',
    start_url: '/',
    display: 'standalone',
    background_color: '#F4F3EE',
    theme_color: '#4F7A63',
    icons: [
      { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
      { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
      { src: '/icons/icon-maskable-192.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
      { src: '/icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  }
}
