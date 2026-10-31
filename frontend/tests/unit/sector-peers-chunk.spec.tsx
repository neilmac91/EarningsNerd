/* =============================================================================
   sector-peers-chunk.spec.tsx: the Sector peers card's chunk, failed and asked for again (E251)
   -----------------------------------------------------------------------------
   The gate (features/peers/components/SectorPeers.tsx) loads the card in a chunk of its own. React.lazy keeps a
   rejected import for good, so a lazy made once for the module would put the boundary's card on every company after one
   failed chunk, until a reload: the page's ChartErrorBoundary is keyed by ticker and starts afresh, but a module's lazy
   would throw its first rejection again. The gate makes its lazy as it mounts, so the next company asks for the chunk
   again. Here the card's module fails its first import, as a chunk lost to the network would, and loads on the next
   (Vitest evaluates a mocked module again after its factory throws).
============================================================================= */
import { readFileSync } from 'node:fs'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const chunk = vi.hoisted(() => ({ failures: 0, imports: 0 }))
vi.mock('@/features/peers/components/SectorPeersCard', async (importOriginal) => {
  chunk.imports += 1
  if (chunk.failures > 0) {
    chunk.failures -= 1
    throw new Error('Failed to load chunk')
  }
  return importOriginal()
})
const getPeers = vi.fn()
vi.mock('@/features/peers/api/peers-api', () => ({ getPeers: (...args: unknown[]) => getPeers(...args) }))

import { ChartErrorBoundary } from '@/components/ChartErrorBoundary'
import SectorPeers from '@/features/peers/components/SectorPeers'
import type { PeerFixture } from './chartPlan'

const FIXTURE = JSON.parse(readFileSync('tests/unit/fixtures/peers-cohorts.json', 'utf8')) as PeerFixture

afterEach(() => {
  getPeers.mockReset()
})

/** The panel as the page mounts it: inside its boundary, keyed by the ticker. */
const panel = (client: QueryClient, ticker: string) => (
  <QueryClientProvider client={client}>
    <ChartErrorBoundary key={ticker}>
      <SectorPeers ticker={ticker} />
    </ChartErrorBoundary>
  </QueryClientProvider>
)

describe('the Sector peers card’s chunk (E251)', () => {
  it('asks again on the next company for a chunk that failed: the boundary stands in for the first, and the next draws', async () => {
    getPeers.mockImplementation(() => Promise.resolve(structuredClone(FIXTURE.cases.spread.response)))
    chunk.failures = 1
    // React logs what the boundary catches, and rethrows it through a window error event that jsdom reports unless it is
    // handled; keep the output quiet.
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const handled = (event: ErrorEvent) => event.preventDefault()
    window.addEventListener('error', handled)
    try {
      const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
      const { rerender } = render(panel(client, 'AAA'))
      expect(await screen.findByText('This chart could not be drawn.', undefined, { timeout: 4000 })).toBeInTheDocument()
      expect(chunk.imports, 'the chunk asked for once').toBe(1)

      rerender(panel(client, 'BBB'))
      // The next company's gate makes a lazy of its own, which asks for the chunk again, and draws.
      await waitFor(() => expect(chunk.imports, 'the chunk asked for again on the next company').toBe(2), { timeout: 3000 })
      expect(await screen.findByRole('heading', { level: 2, name: 'Sector peers' }, { timeout: 8000 })).toBeInTheDocument()
      expect(screen.queryByText('This chart could not be drawn.')).toBeNull()
    } finally {
      window.removeEventListener('error', handled)
      consoleError.mockRestore()
    }
  }, 20_000)
})
