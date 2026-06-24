'use client'

import { useEffect, useState } from 'react'
import { format } from 'date-fns'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { CircleNotchIcon, PaperPlaneTiltIcon, ProhibitIcon } from '@/lib/icons'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import { resendInvite, revokeInvite, type InviteRecord } from '@/features/admin/api/admin-api'
import InviteStatusBadge from '@/features/admin/components/InviteStatusBadge'
import RevokeConfirmModal from '@/features/admin/components/RevokeConfirmModal'
import ResendShareModal from '@/features/admin/components/ResendShareModal'

const RESEND_COOLDOWN_SECONDS = 30

function fmtDate(value: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return format(d, 'MMM d, yyyy')
}

interface InviteRowProps {
  invite: InviteRecord
}

export default function InviteRow({ invite }: InviteRowProps) {
  const queryClient = useQueryClient()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [cooldown, setCooldown] = useState(0)
  // Holds the freshly-minted link after a resend so we can offer it for sharing.
  const [resendShare, setResendShare] = useState<{ link: string; email: string | null } | null>(
    null,
  )

  // Client-side cooldown countdown after a resend, so an admin can't hammer the endpoint and
  // mint a pile of fresh links in a few seconds.
  useEffect(() => {
    if (cooldown <= 0) return
    const t = setInterval(() => setCooldown((c) => Math.max(0, c - 1)), 1000)
    return () => clearInterval(t)
  }, [cooldown])

  const resendMutation = useMutation({
    mutationFn: () => resendInvite(invite.id),
    onSuccess: (result) => {
      setCooldown(RESEND_COOLDOWN_SECONDS)
      toast.success(result.emailed ? `Invite re-sent to ${result.email}` : 'Fresh invite link minted')
      // Surface the fresh link in a dialog so the admin can copy/share it right away.
      setResendShare({ link: result.invite_link, email: result.email })
      queryClient.invalidateQueries({ queryKey: ['admin-invites'] })
    },
    onError: (err: unknown) => {
      toast.error(isApiError(err) ? getErrorMessage(err) : 'Could not resend that invite.')
    },
  })

  const revokeMutation = useMutation({
    mutationFn: () => revokeInvite(invite.id),
    onSuccess: () => {
      setConfirmOpen(false)
      toast.success('Invite revoked')
      queryClient.invalidateQueries({ queryKey: ['admin-invites'] })
    },
    onError: (err: unknown) => {
      toast.error(isApiError(err) ? getErrorMessage(err) : 'Could not revoke that invite.')
    },
  })

  const isUsed = invite.status === 'used'
  const isRevoked = invite.status === 'revoked'
  const emailLabel = invite.email ?? 'this invite'
  const resendDisabled = resendMutation.isPending || cooldown > 0

  return (
    <tr className="hover:bg-background-light dark:hover:bg-white/5">
      <td className="whitespace-nowrap px-4 py-3 text-sm text-text-primary-light dark:text-text-primary-dark">
        {invite.email ?? (
          <span className="text-text-tertiary-light dark:text-text-secondary-dark">Link only</span>
        )}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        {invite.cohort ?? '—'}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-sm">
        <InviteStatusBadge status={invite.status} />
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        {fmtDate(invite.created_at)}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        {fmtDate(invite.expires_at)}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-sm">
        <div className="flex items-center gap-2">
          {/* Resend is hidden once an invite is used — re-minting a redeemed invite is a 409. */}
          {!isUsed && (
            <button
              type="button"
              onClick={() => resendMutation.mutate()}
              disabled={resendDisabled}
              aria-label={`Resend invite to ${emailLabel}`}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border-light bg-panel-light px-2.5 py-1.5 text-xs font-medium text-text-primary-light shadow-e1 transition-all hover:bg-brand-weak hover:shadow-e2 disabled:opacity-50 disabled:cursor-not-allowed dark:border-white/10 dark:bg-panel-dark dark:text-text-primary-dark dark:shadow-none dark:hover:bg-white/5"
            >
              {resendMutation.isPending ? (
                <CircleNotchIcon className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <PaperPlaneTiltIcon className="h-3.5 w-3.5" />
              )}
              {cooldown > 0 ? `Resend (${cooldown}s)` : 'Resend'}
            </button>
          )}

          {/* Visual separator between the constructive and destructive actions. */}
          {!isUsed && !isRevoked && (
            <span className="h-4 w-px bg-border-light dark:bg-white/10" aria-hidden="true" />
          )}

          {/* Revoke is hidden once used or already revoked. */}
          {!isUsed && !isRevoked && (
            <button
              type="button"
              onClick={() => setConfirmOpen(true)}
              aria-label={`Revoke invite to ${emailLabel}`}
              className="inline-flex items-center gap-1.5 rounded-lg border border-transparent px-2.5 py-1.5 text-xs font-medium text-error-light transition-colors hover:bg-error-light/10 dark:text-error-dark dark:hover:bg-error-dark/15"
            >
              <ProhibitIcon className="h-3.5 w-3.5" />
              Revoke
            </button>
          )}
        </div>
      </td>

      {confirmOpen && (
        <RevokeConfirmModal
          email={invite.email}
          isPending={revokeMutation.isPending}
          onConfirm={() => revokeMutation.mutate()}
          onClose={() => setConfirmOpen(false)}
        />
      )}

      {resendShare && (
        <ResendShareModal
          link={resendShare.link}
          email={resendShare.email}
          onClose={() => setResendShare(null)}
        />
      )}
    </tr>
  )
}
