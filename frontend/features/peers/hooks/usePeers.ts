import { useQuery } from '@tanstack/react-query'
import { getPeers, type PeerComparisonResponse } from '@/features/peers/api/peers-api'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/queryKeys'

/** A company's sector cohort on one metric, the one read the panel's gate and its card share: the gate reads the default
 *  metric to decide whether the panel shows, and the card reads it again, from the cache, and any metric picked. Facts
 *  change only with new filings, so an answer stays fresh an hour; only a retryable failure is tried again. */
export function usePeers(ticker: string, metric: string) {
  return useQuery<PeerComparisonResponse>({
    queryKey: queryKeys.peers(ticker, metric),
    queryFn: () => getPeers(ticker, metric),
    enabled: ticker !== '',
    retry: (failureCount, err) => (err instanceof ApiError && err.isRetryable ? failureCount < 2 : false),
    staleTime: 60 * 60 * 1000,
    gcTime: 2 * 60 * 60 * 1000,
  })
}
