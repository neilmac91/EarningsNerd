'use client'

import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { format } from 'date-fns'
import { toast } from 'sonner'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import {
  mintInvite,
  listInvites,
  revokeInvite,
  MintedInvite,
  InviteListItem,
  InviteStatus,
} from '@/features/admin/api/invites-api'
import { clsx } from 'clsx'
import SecondaryHeader from '@/components/SecondaryHeader'
import StateCard from '@/components/StateCard'
import { Button, buttonVariants } from '@/components/ui/Button'
import { Input, inputClasses } from '@/components/ui/Input'
import {
  CircleNotchIcon,
  CopyIcon,
  CheckIcon,
  ProhibitIcon,
} from '@/lib/icons'

// Split a textarea of addresses on whitespace / comma / semicolon, dropping empties.
function parseEmails(raw: string): string[] {
  return raw
    .split(/[\s,;]+/)
    .map((e) => e.trim())
    .filter(Boolean)
}

const STATUS_CLASS: Record<InviteStatus, string> = {
  pending: 'bg-brand-weak text-brand-strong dark:bg-white/5 dark:text-brand-strong-dark',
  used: 'bg-gain-soft text-success-light dark:bg-gain-soft-dark dark:text-success-dark',
  revoked: 'bg-loss-soft text-error-light dark:bg-loss-soft-dark dark:text-error-dark',
  expired:
    'bg-warning-light/10 text-warning-light dark:bg-warning-dark/10 dark:text-warning-dark',
}

function formatDate(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return format(d, 'MMM dd, yyyy HH:mm')
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false)
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error('Could not copy — select the link and copy manually.')
    }
  }
  return (
    <Button variant="secondary" size="sm" onClick={onCopy} className="shrink-0">
      {copied ? <CheckIcon className="h-4 w-4" /> : <CopyIcon className="h-4 w-4" />}
      {copied ? 'Copied' : 'Copy'}
    </Button>
  )
}

export default function AdminInvitesPage() {
  const router = useRouter()
  const queryClient = useQueryClient()

  // Own query identity (the 'safe' fetch returns null on 401). Matches Header's convention of
  // pairing getCurrentUserSafe with ['current-user'] — never reuse ['user'], whose other callers
  // pair it with the throwing getCurrentUser, so the two would clobber each other's cached shape.
  const { data: user, isLoading: userLoading } = useQuery({
    queryKey: ['current-user'],
    queryFn: getCurrentUserSafe,
    retry: false,
  })
  const isAdmin = Boolean(user?.is_admin)

  // Send unauthenticated visitors to login. Authenticated non-admins see a forbidden card below
  // (the real gate is server-side: every /api/admin/invites call is 403'd for non-admins).
  useEffect(() => {
    if (!userLoading && user === null) {
      router.push('/login')
    }
  }, [router, userLoading, user])

  // Mint form state
  const [emailsRaw, setEmailsRaw] = useState('')
  const [expiresInHours, setExpiresInHours] = useState('')
  const [sendEmail, setSendEmail] = useState(false)
  const [minting, setMinting] = useState(false)
  const [minted, setMinted] = useState<MintedInvite[]>([])

  const invitesQuery = useQuery({
    queryKey: ['admin-invites'],
    queryFn: listInvites,
    enabled: isAdmin,
    retry: false,
  })

  const revokeMutation = useMutation({
    mutationFn: revokeInvite,
    onSuccess: () => {
      toast.success('Invite revoked')
      queryClient.invalidateQueries({ queryKey: ['admin-invites'] })
    },
    onError: () => toast.error('Could not revoke that invite. Please retry.'),
  })

  const handleMint = async () => {
    const emails = parseEmails(emailsRaw)
    // Cap a single batch so an accidental giant paste can't fan out into hundreds of concurrent
    // requests (browser/server overload, provider rate limits). 50 is ample for a closed beta.
    const MAX_BATCH = 50
    if (emails.length > MAX_BATCH) {
      toast.error(`Mint at most ${MAX_BATCH} invites at once (you entered ${emails.length}).`)
      return
    }
    const hours = expiresInHours.trim() ? Number(expiresInHours) : undefined
    // Backend expires_in_hours is an int — reject fractional/zero/negative here so a "1.5" doesn't
    // sail past and come back as an unexplained 422 ("N invites failed to mint").
    if (hours !== undefined && (!Number.isInteger(hours) || hours <= 0)) {
      toast.error('Expiry must be a whole number of hours greater than zero.')
      return
    }

    setMinting(true)
    setMinted([])
    try {
      // No email → one unbound, any-email invite. Otherwise one bound invite per address, in
      // parallel; allSettled so one failure doesn't drop the rest.
      const inputs =
        emails.length === 0
          ? [{ expiresInHours: hours, sendEmail: false }]
          : emails.map((email) => ({ email, expiresInHours: hours, sendEmail }))

      const results = await Promise.allSettled(inputs.map((input) => mintInvite(input)))
      const ok = results
        .filter((r): r is PromiseFulfilledResult<MintedInvite> => r.status === 'fulfilled')
        .map((r) => r.value)
      const failed = results.length - ok.length

      setMinted(ok)
      if (ok.length) {
        toast.success(`Minted ${ok.length} invite${ok.length === 1 ? '' : 's'}.`)
        setEmailsRaw('')
        queryClient.invalidateQueries({ queryKey: ['admin-invites'] })
      }
      if (failed) {
        toast.error(`${failed} invite${failed === 1 ? '' : 's'} failed to mint.`)
      }
    } finally {
      setMinting(false)
    }
  }

  if (userLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background-light dark:bg-background-dark">
        <CircleNotchIcon className="h-8 w-8 animate-spin text-brand-strong dark:text-brand-strong-dark" />
      </div>
    )
  }

  if (user === null) {
    return null // redirecting to /login
  }

  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-background-light dark:bg-background-dark">
        <SecondaryHeader
          title="Beta invites"
          subtitle="Admin only"
          backHref="/dashboard"
          backLabel="Back to dashboard"
        />
        <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <StateCard
            variant="error"
            title="Admin access required"
            message="Your account doesn't have admin privileges, so the invite console isn't available."
            action={
              <Link
                href="/dashboard"
                className={`${buttonVariants({ variant: 'primary' })} font-semibold`}
              >
                Back to dashboard
              </Link>
            }
          />
        </main>
      </div>
    )
  }

  const invites = invitesQuery.data ?? []

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      <SecondaryHeader
        title="Beta invites"
        subtitle="Mint single-use magic links for friends & family beta access."
        backHref="/dashboard"
        backLabel="Back to dashboard"
      />

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
        {/* Mint form */}
        <section className="bg-panel-light dark:bg-panel-dark border border-border-light dark:border-white/10 rounded-xl shadow-e2 dark:shadow-none p-6">
          <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark mb-1">
            Mint invites
          </h2>
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark mb-5">
            Leave the email box empty for one unbound link anyone can redeem once. Add one address
            per line (or comma-separated) to mint a bound invite for each — optionally emailing the
            link automatically.
          </p>

          <div className="space-y-4">
            <div>
              <label
                htmlFor="invite-emails"
                className="block text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark mb-2"
              >
                Emails <span className="font-normal text-text-tertiary-light dark:text-text-secondary-dark">(optional)</span>
              </label>
              <textarea
                id="invite-emails"
                value={emailsRaw}
                onChange={(e) => setEmailsRaw(e.target.value)}
                rows={4}
                placeholder={'friend@example.com\nfamily@example.com'}
                className={clsx(inputClasses, 'text-sm')}
              />
            </div>

            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div className="w-full sm:w-56">
                <label
                  htmlFor="invite-expiry"
                  className="block text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark mb-2"
                >
                  Expiry hours{' '}
                  <span className="font-normal text-text-tertiary-light dark:text-text-secondary-dark">
                    (default 168)
                  </span>
                </label>
                <Input
                  id="invite-expiry"
                  type="number"
                  min={1}
                  step={1}
                  value={expiresInHours}
                  onChange={(e) => setExpiresInHours(e.target.value)}
                  placeholder="168"
                />
              </div>

              <label className="flex items-center gap-2 text-sm text-text-secondary-light dark:text-text-secondary-dark select-none">
                <input
                  type="checkbox"
                  checked={sendEmail}
                  onChange={(e) => setSendEmail(e.target.checked)}
                  className="h-4 w-4 rounded border-border-light dark:border-white/20 text-brand-strong focus:ring-brand-light"
                />
                Email the link to each address
              </label>
            </div>

            <div>
              <Button onClick={handleMint} disabled={minting} className="font-semibold">
                {minting ? (
                  <>
                    <CircleNotchIcon className="h-4 w-4 animate-spin" />
                    Minting…
                  </>
                ) : (
                  'Mint invites'
                )}
              </Button>
            </div>
          </div>

          {/* Freshly minted links — shown once; the raw token is never retrievable again. */}
          {minted.length > 0 && (
            <div className="mt-6 border-t border-border-light dark:border-white/10 pt-5">
              <h3 className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark mb-1">
                New invite links
              </h3>
              <p className="text-xs text-text-tertiary-light dark:text-text-secondary-dark mb-3">
                Copy these now — for security the link is shown only once.
              </p>
              <ul className="space-y-2">
                {minted.map((m) => (
                  <li
                    key={m.id}
                    className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between rounded-lg border border-border-light dark:border-white/10 bg-background-light dark:bg-background-dark px-3 py-2"
                  >
                    <div className="min-w-0">
                      <div className="text-xs text-text-secondary-light dark:text-text-secondary-dark">
                        {m.email || 'Any email'}
                        {m.emailed && (
                          <span className="ml-2 text-success-light dark:text-success-dark">
                            · emailed
                          </span>
                        )}
                      </div>
                      <div className="font-mono text-xs text-text-primary-light dark:text-text-primary-dark truncate">
                        {m.invite_link}
                      </div>
                    </div>
                    <CopyButton value={m.invite_link} />
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>

        {/* Recent invites */}
        <section className="bg-panel-light dark:bg-panel-dark border border-border-light dark:border-white/10 rounded-xl shadow-e2 dark:shadow-none p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
              Recent invites
            </h2>
            <Button
              variant="tertiary"
              size="sm"
              onClick={() => invitesQuery.refetch()}
              disabled={invitesQuery.isFetching}
            >
              {invitesQuery.isFetching ? (
                <CircleNotchIcon className="h-4 w-4 animate-spin" />
              ) : (
                'Refresh'
              )}
            </Button>
          </div>

          {invitesQuery.isLoading ? (
            <div className="flex justify-center py-8">
              <CircleNotchIcon className="h-6 w-6 animate-spin text-brand-strong dark:text-brand-strong-dark" />
            </div>
          ) : invitesQuery.isError ? (
            <StateCard
              variant="error"
              title="Couldn't load invites"
              message="Please retry in a moment."
            />
          ) : invites.length === 0 ? (
            <StateCard
              title="No invites yet"
              message="Mint your first invite above to start onboarding beta testers."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-text-tertiary-light dark:text-text-secondary-dark border-b border-border-light dark:border-white/10">
                    <th className="py-2 pr-4 font-medium">Email</th>
                    <th className="py-2 pr-4 font-medium">Status</th>
                    <th className="py-2 pr-4 font-medium">Expires</th>
                    <th className="py-2 pr-4 font-medium">Used</th>
                    <th className="py-2 pr-0 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {invites.map((invite: InviteListItem) => (
                    <tr
                      key={invite.id}
                      className="border-b border-border-light/60 dark:border-white/5"
                    >
                      <td className="py-3 pr-4 text-text-primary-light dark:text-text-primary-dark">
                        {invite.email || (
                          <span className="text-text-tertiary-light dark:text-text-secondary-dark">
                            Any email
                          </span>
                        )}
                      </td>
                      <td className="py-3 pr-4">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize ${
                            STATUS_CLASS[invite.status]
                          }`}
                        >
                          {invite.status}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-text-secondary-light dark:text-text-secondary-dark whitespace-nowrap">
                        {formatDate(invite.expires_at)}
                      </td>
                      <td className="py-3 pr-4 text-text-secondary-light dark:text-text-secondary-dark whitespace-nowrap">
                        {formatDate(invite.used_at)}
                      </td>
                      <td className="py-3 pr-0 text-right">
                        {invite.status === 'pending' ? (
                          <Button
                            variant="tertiary"
                            size="sm"
                            onClick={() => revokeMutation.mutate(invite.id)}
                            disabled={
                              revokeMutation.isPending &&
                              revokeMutation.variables === invite.id
                            }
                            className="text-error-light dark:text-error-dark"
                          >
                            <ProhibitIcon className="h-4 w-4" />
                            Revoke
                          </Button>
                        ) : (
                          <span className="text-xs text-text-tertiary-light dark:text-text-secondary-dark">
                            —
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
