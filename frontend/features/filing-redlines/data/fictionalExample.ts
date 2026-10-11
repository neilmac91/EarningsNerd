import type { RedlinePair } from '../lib/filingPair'

/** Written for this prototype; no real issuer, accession, or SEC source is represented. */
export const fictionalPair: RedlinePair = {
  fictional: true,
  earlier: {
    filingId: null,
    companyName: 'Harbor Vale Industries', ticker: 'Fictional company',
    reportDate: '2024-12-31', filingDate: '2025-02-21', accession: 'Fictional earlier filing', originalUrl: null,
  },
  current: {
    filingId: null,
    companyName: 'Harbor Vale Industries', ticker: 'Fictional company',
    reportDate: '2025-12-31', filingDate: '2026-02-20', accession: 'Fictional later filing', originalUrl: null,
  },
}

export const fictionalEarlierText = `We manufacture industrial sensors for customers in North America.

Our largest customer accounted for 18% of revenue in the year ended December 31, 2024.

We rely on a single supplier for a component used in our primary product line.

We evaluate the recoverability of long-lived assets when events indicate that their carrying value may not be recoverable.`

export const fictionalCurrentText = `We manufacture industrial sensors for customers in North America.

Our largest customer accounted for 27% of revenue in the year ended December 31, 2025.

We qualified a second supplier for a component used in our primary product line. Both suppliers operate in the same region.

We evaluate the recoverability of long-lived assets when events indicate that their carrying value may not be recoverable.

We recorded an impairment charge of $8 million related to equipment at our closed facility.`
