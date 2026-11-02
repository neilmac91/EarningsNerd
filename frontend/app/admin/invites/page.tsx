'use client'

import { queryKeys } from '@/lib/queryKeys'
import { useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  EnvelopeSimpleIcon,
  PaperPlaneTiltIcon,
} from '@/lib/icons'
import { Button, primaryUnavailableClass } from '@/components/ui/Button'
import { Input, inputClasses } from '@/components/ui/Input'
import { Checkbox, Notice, Skeleton } from '@/components/ui'
import SecondaryHeader from '@/components/SecondaryHeader'
import { RetryButton, useRetainedFailure } from '@/hooks/useRetainedFailure'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import {
  createInvite,
  getInviteReadiness,
  listInvites,
  type InvitePermission,
  type InviteRecord,
  type InviteStatus,
  type PermissionVia,
} from '@/features/admin/api/admin-api'
import EmailChipsInput, {
  type EmailChipsBreakdown,
} from '@/features/admin/components/EmailChipsInput'
import BulkResultSummary, {
  type BulkInviteOutcome,
} from '@/features/admin/components/BulkResultSummary'
import InviteRow from '@/features/admin/components/InviteRow'
import InviteReadinessBanner from '@/features/admin/components/InviteReadinessBanner'
import InvitePermissionFields from '@/features/admin/components/InvitePermissionFields'
import TableScroll from '@/features/admin/components/TableScroll'
import { inviteAvailability } from '@/features/admin/lib/inviteReadiness'
import {
  localDay,
  permissionDayRange,
  permissionErrors,
  permissionOf,
  type PermissionErrors,
} from '@/features/admin/lib/invitePermission'

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

/** Why new invite links are off, for Send's and each Resend's description, by what the readiness read says. */
const LINKS_HELD = {
  checking: 'New invite links wait for the availability check above.',
  failed: 'New invite links are off until the availability check above answers.',
  held: 'New invite links are off while registration is on hold (see above).',
} as const
/** Why "Email invites" is off, the same way; held, it says whether links can still go out by hand. */
const EMAIL_HELD = {
  checking: 'Invitation email waits for the availability check above.',
  failed: 'Invitation email is off until the availability check above answers.',
  held: 'Invitation email is on hold (see above), so these invites are links you share yourself.',
  heldWithRegistration: 'Invitation email is on hold while registration is (see above).',
} as const

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
  // Off by default: an invitation is emailed only on purpose, under the recipient's recorded request.
  const [sendEmail, setSendEmail] = useState(false)
  // The recipient's request (InvitePermissionFields), one record for every address in a send.
  const [requestedVia, setRequestedVia] = useState<PermissionVia | ''>('')
  const [requestedOn, setRequestedOn] = useState(() => localDay())
  const [permissionProblems, setPermissionProblems] = useState<PermissionErrors>({})
  const viaRef = useRef<HTMLSelectElement>(null)
  const onRef = useRef<HTMLInputElement>(null)
  const [sending, setSending] = useState(false)
  const [outcomes, setOutcomes] = useState<BulkInviteOutcome[]>([])
  // Whether "Email invites" was on for the run the summary shows (the box can change after it).
  const [emailRequested, setEmailRequested] = useState(false)
  const [skipped, setSkipped] = useState<string[]>([])

  // Zone B state
  const [statusFilter, setStatusFilter] = useState<'all' | InviteStatus>('all')
  const [cohortFilter, setCohortFilter] = useState<string>('all')
  const [emailSearch, setEmailSearch] = useState('')

  const invitesQuery = useQuery({
    queryKey: queryKeys.adminInvites(),
    queryFn: listInvites,
    retry: false,
  })
  const { data: invites } = invitesQuery
  // Holds the error card, and its focused Retry, through the refetch a Retry starts.
  const invitesFailure = useRetainedFailure(invitesQuery, queryKeys.adminInvites())
  const invitesHeadingRef = useRef<HTMLHeadingElement>(null)

  // What holds new links and invitation email. Read fresh on each visit (staleTime 0), and again with the list after
  // every invite action (its key shares the list's prefix). Loading or failed, both stay off (fail closed); the list
  // and Revoke never wait on it.
  const readinessQuery = useQuery({
    queryKey: queryKeys.adminInviteReadiness(),
    queryFn: ({ signal }) => getInviteReadiness(signal),
    retry: false,
    staleTime: 0,
  })
  const readinessFailure = useRetainedFailure(readinessQuery, queryKeys.adminInviteReadiness())
  const readiness = readinessQuery.status === 'success' ? readinessQuery.data : undefined
  const available = inviteAvailability(readiness)
  const holdState = readinessFailure.failed ? 'failed' : readiness ? 'held' : 'checking'
  const linkHold = available.links ? null : LINKS_HELD[holdState]
  const emailHold = available.email
    ? null
    : EMAIL_HELD[holdState === 'held' && !available.links ? 'heldWithRegistration' : holdState]
  // The box shows what a send would do: never on while invitation email is held. A hold that starts after the box was
  // ticked clears it (a render-time update of state), so a later answer never ticks it again unseen.
  if (sendEmail && !available.email) setSendEmail(false)
  const emailOn = sendEmail && available.email
  const inviteHeadingRef = useRef<HTMLHeadingElement>(null)

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
  const nothingToSend = toInviteCount === 0

  const handleSend = async () => {
    if (nothingToSend || sending || linkHold !== null) return
    if (overBatchLimit) {
      toast.error(`Too many at once. Send at most ${MAX_BATCH} per batch (${toInviteCount} entered).`)
      return
    }
    // An emailed invite carries the recipient's request: every field of it, or no request is sent at all.
    const emailing = emailOn
    let permission: InvitePermission | undefined
    if (emailing) {
      const problems = permissionErrors(requestedVia, requestedOn, permissionDayRange())
      setPermissionProblems(problems)
      if (problems.via || problems.on) {
        const firstInvalid = problems.via ? viaRef.current : onRef.current
        firstInvalid?.focus()
        return
      }
      permission = permissionOf(requestedVia as PermissionVia, requestedOn)
    }
    setSending(true)
    setOutcomes([])
    setEmailRequested(emailing)
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
            sendEmail: emailing,
            permission,
          })
          return {
            email,
            ok: true,
            link: result.invite_link,
            emailed: result.emailed,
            deliveryStatus: result.delivery_status ?? null,
          }
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
    // Send keeps focus, so it stays busy until the refetched list marks these addresses invited:
    // re-enabled any sooner, a second Enter would mint (and email) every invite in the batch again.
    await queryClient.invalidateQueries({ queryKey: queryKeys.adminInvites() })
    setSending(false)

    // Say what happened: an invite is created, and its email accepted by the provider only when the box was on and
    // the provider took it (the API's `emailed`). An acceptance is never a delivery, so no line says "sent" or
    // "delivered": the list shows each email's state as it is learned.
    const created = results.filter((r) => r.ok)
    const acceptedCount = created.filter((r) => r.emailed).length
    const failedCount = results.length - created.length
    const skippedCount = breakdown.invalid.length + breakdown.alreadyInvited.length
    const createdLabel = `${created.length} invite${created.length === 1 ? '' : 's'} created`
    if (failedCount > 0) {
      toast.error(`${failedCount} invite${failedCount === 1 ? '' : 's'} failed`)
    } else if (emailing && acceptedCount < created.length) {
      toast.warning(`${createdLabel} · ${acceptedCount} accepted by the email provider. Copy the rest from the list below.`)
    } else if (skippedCount === 0) {
      toast.success(
        emailing
          ? `${createdLabel} · ${acceptedCount} accepted by the email provider`
          : `${created.length} invite link${created.length === 1 ? '' : 's'} created`,
      )
    }
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
        {/* What holds new links and invitation email, before anything that acts on them. */}
        <InviteReadinessBanner
          readiness={readiness}
          checking={readinessQuery.isPending}
          failure={readinessFailure}
          focusTarget={inviteHeadingRef}
        />

        {/* ── Zone A: Invite people ───────────────────────────────────────────── */}
        <section className="rounded-2xl border border-border-light bg-panel-light p-cap-6 shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none">
          {/* tabIndex -1: where focus goes if the availability check's Try again unmounts while it holds focus. */}
          <h2
            ref={inviteHeadingRef}
            tabIndex={-1}
            className="mb-4 text-xl font-semibold text-text-primary-light outline-none dark:text-text-primary-dark"
          >
            Invite people
          </h2>

          {/* Zone A fields stay natively disabled while sending: only Send's click starts a send
              (no form, so no Enter-submit), so focus is on Send, never on a field, when it flips. */}
          <EmailChipsInput
            alreadyInvited={pendingEmails}
            onChange={setBreakdown}
            disabled={sending}
          />

          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label
                htmlFor="cohort"
                className="mb-2 block text-sm font-medium text-text-primary-light dark:text-text-primary-dark"
              >
                Cohort <span className="text-text-tertiary-light dark:text-text-tertiary-dark">(optional)</span>
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
                className={inputClasses({ select: true })}
              >
                {EXPIRY_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Unavailable while invitation email is held: aria-disabled with an early return (focus stays, the box
              stays unchecked) and the reason beside it, never native `disabled`, which stays for a send in flight
              (the pinned 'sending' site). */}
          <label
            className={
              emailHold === null
                ? 'mt-4 inline-flex items-center gap-2.5 text-sm text-text-primary-light dark:text-text-primary-dark'
                : 'mt-4 inline-flex cursor-not-allowed items-center gap-2.5 text-sm text-text-secondary-light dark:text-text-secondary-dark'
            }
          >
            <Checkbox
              size="sm"
              checked={emailOn}
              onChange={(e) => {
                if (emailHold !== null) return
                setSendEmail(e.target.checked)
                setPermissionProblems({})
              }}
              disabled={sending}
              aria-disabled={emailHold !== null || undefined}
              aria-describedby={emailHold !== null ? 'email-invites-hold' : undefined}
            />
            <span className="inline-flex items-center gap-1.5">
              <EnvelopeSimpleIcon className="h-4 w-4 text-text-tertiary-light dark:text-text-tertiary-dark" />
              Email invites
            </span>
          </label>
          {emailHold !== null && (
            <p id="email-invites-hold" className="mt-1 text-xs text-text-secondary-light dark:text-text-secondary-dark">
              {emailHold}
            </p>
          )}

          {emailOn && (
            <InvitePermissionFields
              requestedVia={requestedVia}
              requestedOn={requestedOn}
              onRequestedViaChange={(via) => {
                setRequestedVia(via)
                setPermissionProblems((problems) => ({ ...problems, via: undefined }))
              }}
              onRequestedOnChange={(day) => {
                setRequestedOn(day)
                setPermissionProblems((problems) => ({ ...problems, on: undefined }))
              }}
              range={permissionDayRange()}
              errors={permissionProblems}
              unavailable={sending}
              viaRef={viaRef}
              onRef={onRef}
            />
          )}

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
            {/* Busy and nothing-to-send are aria-disabled (handleSend returns early), not native
                `disabled`: Chromium blurs a focused button that turns disabled, and an all-success
                send refetches the list, turning the sent chips "already invited" (nothing to send)
                while Send still holds focus. A hold on new links (registration on hold, or its check not
                answered) is aria-disabled too, its reason under the button: a check that answers while Send
                holds focus must not blur it. Over the batch cap is set only by the chips field, never by Send
                itself, so it stays natively disabled. */}
            <Button
              onClick={handleSend}
              loading={sending}
              loadingText="Sending…"
              leftIcon={<PaperPlaneTiltIcon className="h-4 w-4" />}
              disabled={overBatchLimit}
              aria-disabled={sending || nothingToSend || linkHold !== null || undefined}
              aria-describedby={linkHold !== null ? 'send-invites-hold' : undefined}
              className={(nothingToSend || linkHold !== null) && !sending ? primaryUnavailableClass : undefined}
            >
              Send invites
            </Button>
            {linkHold !== null && (
              <p id="send-invites-hold" className="mt-2 text-xs text-text-secondary-light dark:text-text-secondary-dark">
                {linkHold}
              </p>
            )}
          </div>

          <BulkResultSummary outcomes={outcomes} skipped={skipped} emailRequested={emailRequested} />
        </section>

        {/* ── Zone B: Invites list ────────────────────────────────────────────── */}
        <section className="rounded-2xl border border-border-light bg-panel-light shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border-light px-cap-6 py-4 dark:border-white/10">
            {/* tabIndex -1: where focus goes if the Retry unmounts while it holds focus. */}
            <h2
              ref={invitesHeadingRef}
              tabIndex={-1}
              className="text-xl font-semibold text-text-primary-light outline-none dark:text-text-primary-dark"
            >
              Invites
            </h2>
            {/* min-w-0: the cohort filter is as wide as its longest cohort name, which is data; as a
                flex item this row would otherwise grow to that width and push the card past a phone. */}
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <label htmlFor="filter-status" className="sr-only">
                Filter by status
              </label>
              <select
                id="filter-status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as 'all' | InviteStatus)}
                className={inputClasses({ select: true, autoWidth: true })}
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
                className={inputClasses({ select: true, autoWidth: true })}
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

          {invitesQuery.isLoading && !invitesFailure.failed ? (
            <div role="status" aria-label="Loading invites" className="space-y-3 p-cap-6">
              {[0, 1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
              <span className="sr-only">Loading invites…</span>
            </div>
          ) : invitesFailure.failed ? (
            <div className="p-cap-6">
              <Notice
                variant="error"
                title="Could not load the invites."
                description={isApiError(invitesFailure.error) ? getErrorMessage(invitesFailure.error) : undefined}
                action={
                  <RetryButton size="sm" failures={[invitesFailure]} focusTarget={invitesHeadingRef} />
                }
              />
            </div>
          ) : filteredInvites.length === 0 ? (
            <p
              role="status"
              className="px-cap-6 py-cap-10 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark"
            >
              {(invites?.length ?? 0) === 0 ? 'No invites yet. Send your first one above.' : 'No invites match these filters.'}
            </p>
          ) : (
            <TableScroll label="Invites">
              <table className="min-w-full divide-y divide-border-light dark:divide-white/10">
                <thead className="bg-background-light dark:bg-white/5">
                  <tr>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-tertiary-dark"
                    >
                      Email
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-tertiary-dark"
                    >
                      Cohort
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-tertiary-dark"
                    >
                      Status
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-tertiary-dark"
                    >
                      Invitation email
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-tertiary-dark"
                    >
                      Created
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-tertiary-dark"
                    >
                      Expires
                    </th>
                    <th
                      scope="col"
                      className="px-4 py-3 text-left text-xs font-medium uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-tertiary-dark"
                    >
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-light bg-panel-light dark:divide-white/10 dark:bg-panel-dark">
                  {filteredInvites.map((invite: InviteRecord) => (
                    <InviteRow
                      key={invite.id}
                      invite={invite}
                      linkHold={linkHold}
                      invitationEmailAvailable={available.email}
                    />
                  ))}
                </tbody>
              </table>
            </TableScroll>
          )}

          <p className="border-t border-border-light px-cap-6 py-3 text-xs text-text-tertiary-light dark:border-white/10 dark:text-text-tertiary-dark">
            Showing the most recent {LIST_LIMIT} invites.
          </p>
        </section>
      </main>
    </>
  )
}
