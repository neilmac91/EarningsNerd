import { WarningIcon } from '@/lib/icons'

/**
 * Honest data-quality flag for machine-extracted financials that failed the backend's
 * local-invariant reconciliation gate (strategy §3.5 — e.g. an implausible period-over-period
 * swing or an EPS/net-income sign mismatch). We surface the value with this badge rather than
 * hiding it: "every displayed number is reconciled or visibly flagged" (resilience principle #2).
 * Deliberately subtle; shown only when something is actually flagged.
 */
export default function UnverifiedBadge({ className = '' }: { className?: string }) {
  return (
    <span
      title="Some figures here are machine-extracted from XBRL and failed an automated sanity check (e.g. an unusual period-over-period swing). Treat them with caution and verify against the filing."
      className={`inline-flex items-center gap-1 rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-500/15 dark:text-amber-400 ${className}`}
    >
      <WarningIcon className="h-3 w-3" aria-hidden="true" />
      Unverified
    </span>
  )
}
