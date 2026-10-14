import publicEmailAddresses from '../../backend/app/public_email_addresses.json'

/** Public email addresses are shared with the backend's sender and contact configuration. */
export const CONTACT_ADDRESSES = publicEmailAddresses

export type ContactRole = keyof typeof CONTACT_ADDRESSES

export function contactMailto(role: ContactRole): string {
  return `mailto:${CONTACT_ADDRESSES[role]}`
}
