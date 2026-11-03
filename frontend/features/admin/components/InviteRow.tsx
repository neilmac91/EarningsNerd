'use client'

import { queryKeys } from '@/lib/queryKeys'
import { useEffect, useId, useState } from 'react'
import { format } from 'date-fns'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { CircleNotchIcon, PaperPlaneTiltIcon, ProhibitIcon } from '@/lib/icons'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import { resendInvite, revokeInvite, type InviteRecord, type ResendResult } from '@/features/admin/api/admin-api'
import InviteStatusBadge from '@/features/admin/components/InviteStatusBadge'
import InviteDeliveryState from '@/features/admin/components/InviteDeliveryState'
import { resendEmails } from '@/features/admin/lib/inviteDelivery'
import RevokeConfirmModal from '@/features/admin/components/RevokeConfirmModal'
import { MissingValue } from '@/components/ui/MissingValue'
import ResendShareModal from '@/features/admin/components/ResendShareModal'
import AddressText from '@/features/auth/components/AddressText'

const RESEND_COOLDOWN_SECONDS = 30

/** A stored instant as its day, or null when there is none or it does not parse: the cell then shows MissingValue
 *  ("unavailable"), never a bare token. */
function fmtDate(value: string | null): string | null {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return null
  return format(d, 'MMM d, yyyy')
}

interface InviteRowProps {
  invite: InviteRecord
  /** Why no new invite link can be made now (registration is on hold, or its check has not answered), or null when
   *  one can: Resend stays focusable but inert, and says why. Revoke never waits on it. */
  linkHold: string | null
  /** Requested invitation email is available (the readiness read answered so). */
  invitationEmailAvailable: boolean
}

export default function InviteRow({ invite, linkHold, invitationEmailAvailable }: InviteRowProps) {
  const queryClient = useQueryClient()
  const holdId = useId()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [cooldown, setCooldown] = useState(0)
  // Holds the freshly-minted link after a resend so we can offer it for sharing.
  const [resendShare, setResendShare] = useState<{
    link: string
    email: string | null
    emailed: boolean
    deliveryStatus: ResendResult['delivery_status']
  } | null>(null)

  // Client-side cooldown countdown after a resend, so an admin can't hammer the endpoint and
  // mint a pile of fresh links in a few seconds.
  useEffect(() => {
    if (cooldown <= 0) return
    const t = setInterval(() => setCooldown((c) => Math.max(0, c - 1)), 1000)
    return () => clearInterval(t)
  }, [cooldown])

  const resendMutation = useMutation({
    // send_email is always explicit (resendEmails): left out, the backend would email any bound invite's replacement.
    mutationFn: () => resendInvite(invite.id, { sendEmail: resendEmails(invite, invitationEmailAvailable) }),
    onSuccess: (result) => {
      setCooldown(RESEND_COOLDOWN_SECONDS)
      // `emailed` is the provider's acceptance, never delivery: the dialog and the row say what is known.
      toast.success(result.emailed ? 'New invite link ready · accepted by the email provider' : 'New invite link ready')
      // Surface the fresh link in a dialog so the admin can copy/share it right away.
      setResendShare({
        link: result.invite_link,
        email: result.email,
        emailed: result.emailed,
        deliveryStatus: result.delivery_status ?? null,
      })
      queryClient.invalidateQueries({ queryKey: queryKeys.adminInvites() })
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
      queryClient.invalidateQueries({ queryKey: queryKeys.adminInvites() })
    },
    onError: (err: unknown) => {
      toast.error(isApiError(err) ? getErrorMessage(err) : 'Could not revoke that invite.')
    },
  })

  const isUsed = invite.status === 'used'
  const isRevoked = invite.status === 'revoked'
  // A link-only invite has no address to name, so its actions say what it is.
  const resendLabel = invite.email ? `Resend invite to ${invite.email}` : 'Resend this link-only invite'
  const revokeLabel = invite.email ? `Revoke invite to ${invite.email}` : 'Revoke this link-only invite'
  const resendDisabled = resendMutation.isPending || cooldown > 0 || linkHold !== null

  return (
    <tr className="hover:bg-background-light dark:hover:bg-white/5">
      {/* The address breaks after its @ (AddressText), never nowrap: one 51-character address took the table to 1295px
          in its 1214px box from 1280px to 1920px, Revoke past its right edge (chief design on #1965). A short address
          still keeps its line. */}
      <td className="px-4 py-3 text-sm text-text-primary-light dark:text-text-primary-dark">
        {invite.email ? (
          <AddressText address={invite.email} />
        ) : (
          <span className="text-text-tertiary-light dark:text-text-tertiary-dark">Link only</span>
        )}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        {/* An invite minted without a cohort has none: "no cohort", never "unavailable". */}
        {invite.cohort ?? <MissingValue label="no cohort" />}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-sm">
        <InviteStatusBadge status={invite.status} />
      </td>
      <td className="px-4 py-3 text-sm">
        <InviteDeliveryState delivery={invite.delivery} suppression={invite.email_suppression} />
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        {fmtDate(invite.created_at) ?? <MissingValue />}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        {fmtDate(invite.expires_at) ?? <MissingValue />}
      </td>
      <td className="whitespace-nowrap px-4 py-3 text-sm">
        <div className="flex items-center gap-2">
          {/* Resend is hidden once an invite is used — re-minting a redeemed invite is a 409. */}
          {!isUsed && (
            // aria-disabled + an early return, not native `disabled` (the DS Button's `loading`
            // pattern): ResendShareModal returns focus here on close, and a disabled button can't
            // take it (Chrome even blurs it mid-request), so focus would land on <body>. Unavailable
            // fades the label and hairline, not the element, so the focus indicator keeps its strength
            // (dark's hairline is white/10, so its half is white/5).
            <button
              type="button"
              onClick={() => {
                if (resendDisabled) return
                resendMutation.mutate()
              }}
              aria-disabled={resendDisabled || undefined}
              aria-busy={resendMutation.isPending || undefined}
              aria-label={resendLabel}
              aria-describedby={linkHold !== null ? holdId : undefined}
              className="focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark inline-flex items-center gap-1.5 rounded-lg border border-border-light bg-panel-light px-2.5 py-1.5 text-xs font-medium text-text-primary-light shadow-e1 transition hover:bg-brand-weak hover:shadow-e2 aria-disabled:cursor-not-allowed aria-disabled:border-border-light/50 aria-disabled:text-text-primary-light/50 dark:border-white/10 dark:bg-panel-dark dark:text-text-primary-dark dark:shadow-none dark:hover:bg-white/5 dark:aria-disabled:border-white/5 dark:aria-disabled:text-text-primary-dark/50"
            >
              {resendMutation.isPending ? (
                <CircleNotchIcon aria-hidden="true" className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" />
              ) : (
                <PaperPlaneTiltIcon className="h-3.5 w-3.5" />
              )}
              {cooldown > 0 ? `Resend (${cooldown}s)` : 'Resend'}
            </button>
          )}
          {!isUsed && linkHold !== null && (
            <span id={holdId} className="sr-only">
              {linkHold}
            </span>
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
              aria-label={revokeLabel}
              className="focus-visible:outline-none focus-visible:shadow-ring-error dark:focus-visible:shadow-ring-error-dark inline-flex items-center gap-1.5 rounded-lg border border-transparent px-2.5 py-1.5 text-xs font-medium text-error-light transition-colors hover:bg-error-light/10 dark:text-error-dark dark:hover:border-error-dark/40 dark:hover:bg-transparent"
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
          emailed={resendShare.emailed}
          deliveryStatus={resendShare.deliveryStatus}
          onClose={() => setResendShare(null)}
        />
      )}
    </tr>
  )
}
