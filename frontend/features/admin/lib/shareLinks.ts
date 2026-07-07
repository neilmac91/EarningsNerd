/**
 * Pure helpers for building invite share copy + deep links. No DOM, no React — kept
 * separate from the ShareInvite component so the substitution and URL-encoding logic can
 * be unit-tested in isolation (see tests/unit/shareInvite.test.ts).
 *
 * Privacy note: nothing here logs or transmits the link/token. The single-use invite link
 * only ever travels into the share targets the admin explicitly picks.
 */

/** The professional default invite message. `{invite_link}` (and optional `{name}`) are placeholders. */
export const DEFAULT_INVITE_MESSAGE =
  "You're invited to the EarningsNerd private beta. Full Pro access, on us. " +
  'Every number traced to the SEC source. ' +
  "Single-use link, please don't forward: {invite_link}"

export interface BuildMessageInput {
  /** Template with `{invite_link}` and optional `{name}` placeholders. */
  template: string
  /** The invite link substituted into `{invite_link}`. */
  link: string
  /** Optional recipient name substituted into `{name}` (blank → placeholder removed cleanly). */
  name?: string | null
}

/**
 * Substitute `{invite_link}` and `{name}` into a template. `{invite_link}` is replaced with
 * the raw link; `{name}` with the trimmed name (or removed, collapsing surrounding space, when
 * absent) so the copy never shows a dangling "{name}" or double space.
 */
export function buildInviteMessage({ template, link, name }: BuildMessageInput): string {
  const trimmedName = (name ?? '').trim()
  let out = template.replaceAll('{invite_link}', link)
  if (trimmedName) {
    out = out.replaceAll('{name}', trimmedName)
  } else {
    // Surgically drop "{name}" and exactly one adjacent space (trailing first, else leading) so
    // "Hi {name}," → "Hi," and "Hi {name} there" → "Hi there", without rewriting the rest of the
    // copy (preserves "…", links, etc.).
    out = out.replace(/\{name\} /g, '').replace(/ \{name\}/g, '').replaceAll('{name}', '')
  }
  return out
}

const INVITE_SHARE_SUBJECT = 'Your EarningsNerd beta invite'

/**
 * Strip the raw invite link out of a message body so it isn't duplicated when a share target
 * (e.g. the Web Share API) also receives the link via a dedicated `url` field.
 */
export function messageWithoutLink(message: string, link: string): string {
  return message.replaceAll(link, '').replace(/\s{2,}/g, ' ').trim()
}

export interface ShareDeepLinks {
  whatsapp: string
  sms: string
  mailto: string
  subject: string
}

/**
 * Build the fallback deep links from a fully-substituted message (which already contains the
 * link). Every piece of free text is URL-encoded.
 */
export function buildShareDeepLinks(message: string): ShareDeepLinks {
  const encodedMessage = encodeURIComponent(message)
  return {
    whatsapp: `https://wa.me/?text=${encodedMessage}`,
    sms: `sms:?&body=${encodedMessage}`,
    mailto: `mailto:?subject=${encodeURIComponent(INVITE_SHARE_SUBJECT)}&body=${encodedMessage}`,
    subject: INVITE_SHARE_SUBJECT,
  }
}

/**
 * A link with no bound email is redeemable by anyone who receives it — surface that caution.
 * Returns `true` when the invite is link-only (no email), so the UI can render a warning.
 */
export function isUnboundInvite(email?: string | null): boolean {
  return !((email ?? '').trim())
}

export { INVITE_SHARE_SUBJECT }
