'use client'

import type { RefObject } from 'react'
import { fieldUnavailableClass, inputClasses } from '@/components/ui'
import { PERMISSION_VIA, type PermissionVia } from '@/features/admin/api/admin-api'
import { PERMISSION_VIA_LABELS } from '@/features/admin/lib/inviteDelivery'
import type { PermissionErrors } from '@/features/admin/lib/invitePermission'

const HINT_ID = 'invite-permission-hint'

interface InvitePermissionFieldsProps {
  requestedVia: PermissionVia | ''
  requestedOn: string
  onRequestedViaChange: (via: PermissionVia | '') => void
  onRequestedOnChange: (day: string) => void
  /** The days the date field accepts (invitePermission.permissionDayRange). */
  range: { min: string; max: string }
  errors: PermissionErrors
  /** A send is in flight: the fields keep focus but take no change (aria-disabled and a guarded handler). */
  unavailable: boolean
  viaRef: RefObject<HTMLSelectElement>
  onRef: RefObject<HTMLInputElement>
}

/**
 * The request an emailed invite records, shown only while "Email invites" is on: how and when the recipient asked
 * for an invitation, both required and covering every address in the send. There is no consent box to tick: an
 * admin's checkbox is not the recipient's request (backend InvitePermission).
 */
export default function InvitePermissionFields({
  requestedVia,
  requestedOn,
  onRequestedViaChange,
  onRequestedOnChange,
  range,
  errors,
  unavailable,
  viaRef,
  onRef,
}: InvitePermissionFieldsProps) {
  // A field's error first, then the explanation the two fields share.
  const describedBy = (error: string | undefined, id: string) => (error ? `${id}-error ${HINT_ID}` : HINT_ID)
  return (
    <fieldset className="mt-4 min-w-0">
      <legend className="text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
        Their request for an invitation
      </legend>
      <p id={HINT_ID} className="mt-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Only email people who asked you for an invitation. Record how and when they asked: it covers every address in
        this send.
      </p>
      <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label
            htmlFor="permission-via"
            className="mb-2 block text-sm font-medium text-text-primary-light dark:text-text-primary-dark"
          >
            How they asked
          </label>
          <select
            id="permission-via"
            ref={viaRef}
            value={requestedVia}
            required
            aria-invalid={errors.via ? true : undefined}
            aria-describedby={describedBy(errors.via, 'permission-via')}
            aria-disabled={unavailable || undefined}
            onChange={(e) => {
              if (unavailable) return
              onRequestedViaChange(e.target.value as PermissionVia | '')
            }}
            className={`${inputClasses({ select: true, invalid: Boolean(errors.via) })} ${fieldUnavailableClass}`}
          >
            <option value="" disabled>
              Choose one
            </option>
            {PERMISSION_VIA.map((via) => (
              <option key={via} value={via}>
                {PERMISSION_VIA_LABELS[via]}
              </option>
            ))}
          </select>
          {errors.via && (
            <p id="permission-via-error" role="alert" className="mt-1.5 text-xs font-medium text-error-light dark:text-error-dark">
              {errors.via}
            </p>
          )}
        </div>

        <div>
          <label
            htmlFor="permission-on"
            className="mb-2 block text-sm font-medium text-text-primary-light dark:text-text-primary-dark"
          >
            When they asked
          </label>
          <input
            id="permission-on"
            ref={onRef}
            type="date"
            value={requestedOn}
            min={range.min}
            max={range.max}
            required
            aria-invalid={errors.on ? true : undefined}
            aria-describedby={describedBy(errors.on, 'permission-on')}
            aria-disabled={unavailable || undefined}
            onChange={(e) => {
              if (unavailable) return
              onRequestedOnChange(e.target.value)
            }}
            className={`${inputClasses({ invalid: Boolean(errors.on) })} ${fieldUnavailableClass}`}
          />
          {errors.on && (
            <p id="permission-on-error" role="alert" className="mt-1.5 text-xs font-medium text-error-light dark:text-error-dark">
              {errors.on}
            </p>
          )}
        </div>
      </div>
    </fieldset>
  )
}
