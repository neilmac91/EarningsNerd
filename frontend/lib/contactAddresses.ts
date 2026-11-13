import publicEmailAddresses from './publicEmailAddresses.json'

/**
 * Public email addresses, shared with the backend's sender and contact configuration. The build reads nothing outside
 * frontend/, so publicEmailAddresses.json is a copy of backend/app/public_email_addresses.json, and
 * tests/unit/publicEmailConfiguration.spec.ts holds the two to the same bytes.
 */
export const CONTACT_ADDRESSES = publicEmailAddresses

export type ContactRole = keyof typeof CONTACT_ADDRESSES

export function contactMailto(role: ContactRole): string {
  return `mailto:${CONTACT_ADDRESSES[role]}`
}
