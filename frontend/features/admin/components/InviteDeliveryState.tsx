import type { EmailSuppression, InviteDelivery } from '@/features/admin/api/admin-api'
import { deliveryState, permissionLine, suppressionNote } from '@/features/admin/lib/inviteDelivery'

interface InviteDeliveryStateProps {
  delivery: InviteDelivery | null | undefined
  suppression: EmailSuppression | null | undefined
}

/**
 * An invite row's "Invitation email" cell: the email's state in words that claim no more than the evidence (the
 * provider's acceptance is never delivery, a delivery is only the recipient's mail server taking it), the request it
 * was sent under, and, apart from them, whether the address takes no invitation email at all. Words, not a chip: a
 * state like "Accepted by the email provider" needs its hint beside it, and the row's one status chip stays the
 * invite's own (statusChipContrast.spec.ts reads every layer between a chip and its row).
 */
export default function InviteDeliveryState({ delivery, suppression }: InviteDeliveryStateProps) {
  const state = deliveryState(delivery)
  const note = suppressionNote(suppression, delivery)
  return (
    <div className="min-w-48 max-w-64 space-y-0.5">
      <p
        className={
          delivery
            ? 'text-sm text-text-primary-light dark:text-text-primary-dark'
            : 'text-sm text-text-secondary-light dark:text-text-secondary-dark'
        }
      >
        {state.label}
      </p>
      {state.hint && <p className="text-xs text-text-secondary-light dark:text-text-secondary-dark">{state.hint}</p>}
      {delivery && <p className="text-xs text-text-tertiary-light dark:text-text-tertiary-dark">{permissionLine(delivery)}</p>}
      {note && (
        <p className="pt-1 text-xs text-text-secondary-light dark:text-text-secondary-dark">
          <span className="font-medium text-text-primary-light dark:text-text-primary-dark">{note}.</span> Resend makes a
          new link without emailing it.
        </p>
      )}
    </div>
  )
}
