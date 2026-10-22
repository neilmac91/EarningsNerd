// Node re-reads process.env.TZ on assignment (filing-date-local-day.spec.tsx measured it), so the zone set
// here holds for every render below, imports included. New York: a reader's zone behind UTC.
process.env.TZ = 'America/New_York'

import { describe, expect, it } from 'vitest'
import { act, render } from '@testing-library/react'
import { renderToString } from 'react-dom/server'
import { hydrateRoot } from 'react-dom/client'
import DataNotes from '@/features/analysis/components/DataNotes'
import { SAMPLE_ANALYSIS_DATASET } from '@/features/marketing/lib/landing-samples'
import { formatInstant } from '@/lib/format'

/**
 * Data notes' source date (chief design on #1457, 6309710108): `data_as_of` is an instant, the source data's sync
 * time (`iso_z(facts_synced_at)`), and it prints as the day it falls on in the reader's zone, "October 20, 2026",
 * never as the instant itself, which read as a bug one click into the landing's demo. The landing renders the demo
 * on the server, so its paragraph also hydrates where the reader's zone puts the instant on another day.
 */
const asOf = (data_as_of: string | null) => ({ ...SAMPLE_ANALYSIS_DATASET, data_as_of })

describe('the source date in Data notes', () => {
  it("prints the saved run's sync time as its day, not the instant", () => {
    expect(SAMPLE_ANALYSIS_DATASET.data_as_of, 'the run this case reads').toBe('2026-10-20T18:38:47.008084Z')
    const { container } = render(<DataNotes dataset={SAMPLE_ANALYSIS_DATASET} sample />)
    expect(container).toHaveTextContent('Source data as of October 20, 2026.')
    expect(container.textContent).not.toContain('2026-10-20T')
  })

  it("takes the day the instant falls on in the reader's zone", () => {
    // 01:05 UTC on October 21 is 21:05 on October 20 in New York, so a read of the instant's UTC day would fail here.
    const { container } = render(<DataNotes dataset={asOf('2026-10-21T01:05:33Z')} />)
    expect(container).toHaveTextContent('Source data as of October 20, 2026.')
  })

  it.each([null, 'not a date'])('says the refresh time is unavailable for %s', (value) => {
    const { container } = render(<DataNotes dataset={asOf(value)} />)
    expect(container).toHaveTextContent('Source refresh time is unavailable.')
    expect(container).not.toHaveTextContent('Source data as of')
  })

  it("hydrates the landing's server markup where the reader's zone puts the instant on another day", async () => {
    const element = <DataNotes dataset={SAMPLE_ANALYSIS_DATASET} sample />
    const container = document.createElement('div')
    const errors: unknown[] = []
    try {
      // The server renders in UTC, where the run's 18:38 falls on October 20.
      process.env.TZ = 'UTC'
      const html = renderToString(element)
      expect(html).toContain('Source data as of October 20, 2026.')
      container.innerHTML = html
      document.body.appendChild(container)
      // In Tokyo the same instant is 03:38 on October 21, so the browser's text differs from the server's.
      process.env.TZ = 'Asia/Tokyo'
      expect(formatInstant(SAMPLE_ANALYSIS_DATASET.data_as_of, 'MMMM d, yyyy'), 'the control: the zones disagree').toBe('October 21, 2026')
      await act(async () => {
        hydrateRoot(container, element, { onRecoverableError: (error) => { errors.push(error) } })
      })
      // A mismatch outside suppressHydrationWarning reports here, and React renders the root again on the client.
      expect(errors).toEqual([])
      expect(container).toHaveTextContent(/Source data as of October 2[01], 2026\./)
    } finally {
      process.env.TZ = 'America/New_York'
      container.remove()
    }
  })
})
