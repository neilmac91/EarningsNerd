'use client'

import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  CircleNotchIcon,
  EnvelopeSimpleIcon,
  PaperPlaneTiltIcon,
  UserIcon,
} from '@/lib/icons'
import { Button } from '@/components/ui/Button'
import { Input, inputClasses } from '@/components/ui/Input'
import { EmptyState } from '@/components/ui/EmptyState'
import { ShimmeringLoader } from '@/components/ShimmeringLoader'
import SecondaryHeader from '@/components/SecondaryHeader'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import {
  createInvite,
  listInvites,
  type InviteRecord,
  type InviteStatus,
} from '@/features/admin/api/admin-api'
import EmailChipsInput, {
  type EmailChipsBreakdown,
} from '@/features/admin/components/EmailChipsInput'
import BulkResultSummary, {
  type BulkInviteOutcome,
} from '@/features/admin/components/BulkResultSummary'
import InviteRow from '@/features/admin/components/InviteRow'

const MAX_CONCURRENCY = 4
const LIST_LIMIT = 200
// Guard against a runaway paste firing thousands of mint requests (and emails). Closed-beta
// cohorts are dozens–low hundreds; anything past this is almost certainly a mistake.
const MAX_BATCH = 500

const EXPIRY_OPTIONS = [
  { label: '48 hours', value: 48 },
  { label: '72 hours', value: 72 },
  { label: '7 days', value: 168 },
] as const

const EMPTY_BREAKDOWN: EmailChipsBreakdown = { toInvite: [], invalid: [], alreadyInvited: [] }

/**
 * Run `task` over `items` with at most `limit` promises in flight at once. Resolves with the
 * results in input order. Each task is responsible for not throwing (returns a typed outcome),
 * so one failure never aborts the batch.
 */
async function runBounded<T, R>(
  items: T[],
  limit: number,
  task: (item: T) => Promise<R>,
): Promise<R[]> {
  const results = new Array<R>(items.length)
  let cursor = 0
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (cursor < items.length) {
      const index = cursor++
      results[index] = await task(items[index])
    }
  })
  await Promise.all(workers)
  return results
}

export default function AdminInvitesPage() {
  const queryClient = useQueryClient()

  // Zone A state
  const [breakdown, setBreakdown] = useState<EmailChipsBreakdown>(EMPTY_BREAKDOWN)
  const [cohort, setCohort] = useState('')
  const [expiryHours, setExpiryHours] = useState<number>(168)
  const [sendEmail, setSendEmail] = useState(true)
  const [sending, setSending] = useState(false)
  const [outcomes, setOutcomes] = useState<BulkInviteOutcome[]>([])
  const [skipped, setSkipped] = useState<string[]>([])

  // Zone B state
  const [statusFilter, setStatusFilter] = useState<'all' | InviteStatus>('all')
  const [cohortFilter, setCohortFilter] = useState<string>('all')
  const [emailSearch, setEmailSearch] = useState('')

  const {
    data: invites,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['admin-invites'],
    queryFn: listInvites,
    retry: false,
  })

  // Emails (lowercased) that already have a PENDING invite, so the chips input can flag them.
  const pendingEmails = useMemo(
    () =>
      (invites ?? [])
        .filter((i) => i.status === 'pending' && i.email)
        .map((i) => (i.email as string).toLowerCase()),
    [invites],
  )

  const cohorts = useMemo(() => {
    const set = new Set<string>()
    for (const i of invites ?? []) {
      if (i.cohort) set.add(i.cohort)
    }
    return Array.from(set).sort()
  }, [invites])

  const filteredInvites = useMemo(() => {
    const search = emailSearch.trim().toLowerCase()
    return (invites ?? []).filter((i) => {
      if (statusFilter !== 'all' && i.status !== statusFilter) return false
      if (cohortFilter !== 'all' && (i.cohort ?? '') !== cohortFilter) return false
      if (search && !(i.email ?? '').toLowerCase().includes(search)) return false
      return true
    })
  }, [invites, statusFilter, cohortFilter, emailSearch])

  const toInviteCount = breakdown.toInvite.length
  const overBatchLimit = toInviteCount > MAX_BATCH
  const canSend = toInviteCount > 0 && !overBatchLimit && !sending

  const handleSend = async () => {
    if (toInviteCount === 0 || sending) return
    if (overBatchLimit) {
      toast.error(`Too many at once — send at most ${MAX_BATCH} per batch (${toInviteCount} entered).`)
      return
    }
    setSending(true)
    setOutcomes([])
    setSkipped([...breakdown.invalid, ...breakdown.alreadyInvited])

    const cohortValue = cohort.trim() || undefined

    const results = await runBounded<string, BulkInviteOutcome>(
      breakdown.toInvite,
      MAX_CONCURRENCY,
      async (email) => {
        try {
          const result = await createInvite({
            email,
            cohort: cohortValue,
            expiresInHours: expiryHours,
            sendEmail,
          })
          return { email, ok: true, link: result.invite_link }
        } catch (err: unknown) {
          return {
            email,
            ok: false,
            error: isApiError(err) ? getErrorMessage(err) : 'Failed to create invite',
          }
        }
      },
    )

    setOutcomes(results)
    setSending(false)

    const failedCount = results.filter((r) => !r.ok).length
    const skippedCount = breakdown.invalid.length + breakdown.alreadyInvited.length
    if (failedCount === 0 && skippedCount === 0) {
      toast.success(
        `${results.length} invite${results.length === 1 ? '' : 's'} sent`,
      )
    } else if (failedCount > 0) {
      toast.error(`${failedCount} invite${failedCount === 1 ? '' : 's'} failed`)
    }

    queryClient.invalidateQueries({ queryKey: ['admin-invites'] })
  }

  return (
    <>
      <SecondaryHeader
        title="Invites"
        subtitle="Send and manage early-access invitations"
        backHref="/dashboard"
        backLabel="Back to dashboard"
      />

      <main className="mx-auto max-w-7xl space-y-8 px-4 py-10 sm:px-6 lg:px-8">
        {/* ── Zone A: Invite people ───────────────────────────────────────────── */}
        <section className="rounded-2xl border border-border-light bg-panel-light p-6 shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none">
          <div className="mb-4 flex items-center gap-3">
            <UserIcon className="h-5 w-5 text-brand-strong dark:text-brand-strong-dark" />
            <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
              Invite people
            </h2>
          </div>

          <EmailChipsInput
            alreadyInvited={pendingEmails}
            onChange={setBreakdown}
            disabled={sending}
          />

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label
                htmlFor="cohort"
                className="mb-2 block text-sm font-medium text-text-primary-light dark:text-text-primary-dark"
              >
                Cohort <span className="text-text-tertiary-light dark:text-text-secondary-dark">(optional)</span>
              </label>
              <Input
                id="cohort"
                value={cohort}
                onChange={(e) => setCohort(e.target.value)}
                disabled={sending}
                placeholder="e.g. beta-wave-2"
              />
            </div>

            <div>
              <label
                htmlFor="expiry"
                className="mb-2 block text-sm font-medium text-text-primary-light dark:text-text-primary-dark"
              >
                Link expires in
              </label>
              <select
                id="expiry"
                value={expiryHours}
                onChange={(e) => setExpiryHours(Number(e.target.value))}
                disabled={sending}
                className={inputClasses}
              >
                {EXPIRY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <label className="mt-4 inline-flex items-center gap-2.5 text-sm text-text-primary-light dark:text-text-primary-dark">
            <input
              type="checkbox"
              checked={sendEmail}
              onChange={(e) => setSendEmail(e.target.checked)}
              disabled={sending}
              className="h-4 w-4 rounded border-border-light text-brand-strong focus:shadow-ring-brand dark:border-white/10 dark:bg-slate-900/60"
            />
            <span className="inline-flex items-center gap-1.5">
              <EnvelopeSimpleIcon className="h-4 w-4 text-text-tertiary-light dark:text-text-secondary-dark" />
              Email invites
            </span>
          </label>

          <p
            aria-live="polite"
            className="mt-4 text-sm text-text-secondary-light dark:text-text-secondary-dark"
          >
            <span className="font-medium text-text-primary-light dark:text-text-primary-dark">
              {toInviteCount}
            </span>{' '}
            to invite
            {' · '}
            {breakdown.invalid.length} invalid
            {' · '}
            {breakdown.alreadyInvited.length} already invited
          </p>

          {overBatchLimit && (
            <p className="mt-3 text-sm text-error-light dark:text-error-dark">
              Too many addresses ({toInviteCount}). Send at most {MAX_BATCH} per batch.
            </p>
          )}

          <div className="mt-4">
            <Button onClick={handleSend} disabled={!canSend}>
              {sending ? (
                <CircleNotchIcon className="h-4 w-4 animate-spin" />
              ) : (
                <PaperPlaneTiltIcon className="h-4 w-4" />
              )}
              {sending ? 'Sending…' : 'Send invites'}
            </Button>
          </div>

          <BulkResultSummary outcomes={outcomes} skipped={skipped} />
        </section>

        {/* ── Zone B: Invites list ────────────────────────────────────────────── */}
        <section className="rounded-2xl border border-border-light bg-panel-light shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border-light px-6 py-4 dark:border-white/10">
            <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
              Invites
            </h2>
            <div className="flex flex-wrap items-center gap-2">
              <label htmlFor="filter-status" className="sr-only">
                Filter by status
              </label>
              <select
                id="filter-status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as 'all' | InviteStatus)}
                className={`${inputClasses} w-auto`}
              >
                <option value="all">All statuses</option>
                <option value="pending">Pending</option>
                <option value="used">Used</option>
                <option value="expired">Expired</option>
                <option value="revoked">Revoked</option>
              </select>

              <label htmlFor="filter-cohort" className="sr-only">
                Filter by cohort
              </label>
              <select
                id="filter-cohort"
                value={cohortFilter}
                onChange={(e) => setCohortFilter(e.target.value)}
                className={`${inputClasses} w-auto`}
              >
                <option value="all">All cohorts</option>
                {cohorts.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>

              <label htmlFor="filter-email" className="sr-only">
                Search by email
              </label>
              <Input
                id="filter-email"
                value={emailSearch}
                onChange={(e) => setEmailSearch(e.target.value)}
                placeholder="Search email…"
                className="w-auto"
              />
            </div>
          </div>

          {isLoading ? (
            <div className="space-y-3 p-6">
              {[0, 1, 2, 3, 4].map((i) => (
                <ShimmeringLoader key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : isError ? (
            <div className="p-6">
              <p className="text-sm text-error-light dark:text-error-dark">
                {isApiError(error) ? getErrorMessage(error) : 'Failed to load invites.'}
              </p>
            </div>
          ) : filteredInvites.length === 0 ? (
            <EmptyState
              label="Invites"
              message={
                (invites?.length ?? 0) === 0
                  ? 'No invites yet. Send your first one above.'
                  : 'No invites match these filters.'
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border-light dark:divide-white/10">
                <thead className="bg-background-light dark:bg-white/5">
                  <tr>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary-light dark:text-text-secondary-dark"
                    >
                      Email
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary-light dark:text-text-secondary-dark"
                    >
                      Cohort
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary-light dark:text-text-secondary-dark"
                    >
                      Status
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary-light dark:text-text-secondary-dark"
                    >
                      Created
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary-light dark:text-text-secondary-dark"
                    >
                      Expires
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-text-tertiary-light dark:text-text-secondary-dark"
                    >
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-light bg-panel-light dark:divide-white/10 dark:bg-panel-dark">
                  {filteredInvites.map((invite: InviteRecord) => (
                    <InviteRow key={invite.id} invite={invite} />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className="border-t border-border-light px-6 py-3 text-xs text-text-tertiary-light dark:border-white/10 dark:text-text-secondary-dark">
            Showing the most recent {LIST_LIMIT} invites.
          </p>
        </section>
      </main>
    </>
  )
}
