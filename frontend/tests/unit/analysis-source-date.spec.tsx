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
 * time (`iso_z(facts_synced_at)`), and it prints as the day it falls on in the reader's zone, "October 22, 2026",
 * never as the instant itself, which read as a bug one click into the landing's demo. The landing renders the demo
 * on the server, which cannot know the reader's zone: the server and the hydrating render print the run's UTC day in
 * any zone, so the markup matches with no mismatch suppressed, and the browser then prints the reader's day (Codex on
 * #1457, 4351326588: suppressing the mismatch kept the server's day under the App Router's React 19).
 */
const asOf = (data_as_of: string | null) => ({ ...SAMPLE_ANALYSIS_DATASET, data_as_of })

describe('the source date in Data notes', () => {
  it("prints the saved run's sync time as its day, not the instant", () => {
    expect(SAMPLE_ANALYSIS_DATASET.data_as_of, 'the run this case reads').toBe('2026-10-22T16:42:27.234940Z')
    const { container } = render(<DataNotes dataset={SAMPLE_ANALYSIS_DATASET} sample />)
    expect(container).toHaveTextContent('Source data as of October 22, 2026.')
    expect(container.textContent).not.toContain('2026-10-22T')
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

  it("hydrates the landing's server markup in any zone, then prints the reader's day", async () => {
    const element = <DataNotes dataset={SAMPLE_ANALYSIS_DATASET} sample />
    const container = document.createElement('div')
    const errors: unknown[] = []
    try {
      // In Tokyo the run's 16:42 UTC on October 22 is 01:42 on October 23, so the reader's day is not the UTC day.
      process.env.TZ = 'Asia/Tokyo'
      expect(formatInstant(SAMPLE_ANALYSIS_DATASET.data_as_of, 'MMMM d, yyyy'), 'the control: the zones disagree').toBe('October 23, 2026')
      // The server prints the UTC day whatever its own zone, Tokyo's here, as the hydrating render does in the reader's.
      const html = renderToString(element)
      expect(html).toContain('Source data as of October 22, 2026.')
      container.innerHTML = html
      document.body.appendChild(container)
      await act(async () => {
        hydrateRoot(container, element, { onRecoverableError: (error) => { errors.push(error) } })
      })
      // A mismatch reports here (the paragraph suppresses none), and React would render the root again on the client.
      expect(errors).toEqual([])
      // React renders again right after hydrating, in the browser, with the reader's day: in React 18.3.1, this
      // harness's, and in the App Router's React 19 alike, since neither has a mismatch to resolve.
      expect(container).toHaveTextContent('Source data as of October 23, 2026.')
    } finally {
      process.env.TZ = 'America/New_York'
      container.remove()
    }
  })
})
