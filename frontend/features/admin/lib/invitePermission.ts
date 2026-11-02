import { format, subDays } from 'date-fns'
import { PERMISSION_VIA, type InvitePermission, type PermissionVia } from '@/features/admin/api/admin-api'

/**
 * The request an emailed invite is sent under (EN-BETA PB-01): the recipient asked for an invitation, and the admin
 * records how and on which day. It is the recipient's own request, never the admin's say-so, so there is no box to
 * tick: each field is required, and one record covers every address in that send.
 */

/** The admin's own calendar day, YYYY-MM-DD: the date field's latest day (the field starts empty). */
export function localDay(at: Date = new Date()): string {
  return format(at, 'yyyy-MM-dd')
}

/**
 * The days the form accepts: from 364 days before today to today, in the admin's calendar. The server allows a year
 * back and a day ahead of its UTC day, so every day offered here passes it whatever the admin's zone.
 */
export function permissionDayRange(at: Date = new Date()): { min: string; max: string } {
  return { min: format(subDays(at, 364), 'yyyy-MM-dd'), max: localDay(at) }
}

export interface PermissionErrors {
  via?: string
  on?: string
}

const DAY = /^\d{4}-\d{2}-\d{2}$/

/** What is missing from the request, field by field; an empty object when it can be sent. */
export function permissionErrors(
  via: PermissionVia | '',
  on: string,
  range: { min: string; max: string },
): PermissionErrors {
  const errors: PermissionErrors = {}
  if (!(PERMISSION_VIA as readonly string[]).includes(via)) errors.via = 'Choose how they asked for an invitation.'
  // ISO days compare as text.
  if (!DAY.test(on) || on < range.min || on > range.max) errors.on = 'Enter the day they asked, within the last year.'
  return errors
}

/** The request as the API takes it, once permissionErrors finds nothing missing. */
export function permissionOf(via: PermissionVia, on: string): InvitePermission {
  return { requested_via: via, requested_on: on }
}
