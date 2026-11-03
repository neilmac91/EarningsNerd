import type { InviteReadiness } from '@/features/admin/api/admin-api'

/**
 * What the admin invites page may offer, from the readiness read (GET /api/admin/invites/readiness). It fails
 * closed: with no answer (the read is loading or failed) every capability is off, and invitation email is never
 * on while links are off. The server checks again on every invite route, so this only turns controls off.
 */
export interface InviteAvailability {
  /** New invite links can be created: minting and Resend. */
  links: boolean
  /** A new invite link can be emailed. */
  email: boolean
  /** Links are open only through the invited-cohort exception: the server takes a link bound to an address and in
   *  the configured cohort, exactly, and refuses any other (collection is held). */
  cohortOnly: boolean
}

export function inviteAvailability(readiness: InviteReadiness | undefined): InviteAvailability {
  const collection = readiness?.collection.available === true
  const cohortOnly = !collection && readiness?.invited_cohort.available === true
  const links = collection || cohortOnly
  return { links, email: links && readiness?.invitation_email.available === true, cohortOnly }
}

/**
 * Each reason code as a sentence naming what holds the capability and who or what clears it. The codes are
 * conditions, never values, so a setting's name is the most a sentence says (it is not secret).
 */
export const COLLECTION_REASONS: Record<string, string> = {
  collection_disabled:
    'New registrations are switched off (LEGAL_COLLECTION_ENABLED is off). The operator turns it on in the server settings.',
  operator_unpublished:
    "The operator details aren't published (LEGAL_OPERATOR_PUBLISHED is off). The operator publishes them once they're final.",
  operator_incomplete:
    'A published operator detail is missing or invalid. The operator completes the LEGAL_OPERATOR settings: name, postal address, country and email.',
}

/** The reason that says the operator left the exception switched off: the banner says nothing more about it then. */
export const INVITED_COHORT_SWITCHED_OFF = 'invited_cohort_disabled'

export const INVITED_COHORT_REASONS: Record<string, string> = {
  registration_not_invite_only: 'Registration is not invite-only (REGISTRATION_MODE is public).',
  invited_cohort_disabled: 'The exception is switched off (LEGAL_INVITED_COHORT_ENABLED is off).',
  invited_cohort_unset:
    "No cohort an invite can carry is set (LEGAL_INVITED_COHORT is empty, or has a space at either end, a control character or more than 64 characters). The operator sets it in the server settings.",
}

export const INVITATION_EMAIL_REASONS: Record<string, string> = {
  collection_unavailable: 'It waits for registration to open.',
  invitation_email_disabled:
    'Invitation email is switched off (LEGAL_INVITATION_EMAIL_ENABLED is off). It goes on once the founder approves the permission policy and a test send.',
  provider_unconfigured:
    'No email provider is set up (RESEND_API_KEY is empty). The operator adds the key in the server settings.',
  provider_feedback_unverified:
    "Bounces and spam reports can't be recorded (RESEND_WEBHOOK_SECRET is missing or invalid). The operator sets the email provider's webhook signing secret.",
}

/** A code this page does not know, or a hold that names none: said once, whatever the count. */
export const UNKNOWN_REASON = "Something this page doesn't recognize holds it. The server settings say what."
/** The same, after the reasons this page knows. */
export const UNKNOWN_REASON_TOO = "Something this page doesn't recognize holds it too. The server settings say what."

/** The sentences for a capability's reason codes, in the server's order, an unknown code (or none) read once. */
export function reasonSentences(reasons: readonly string[], known: Record<string, string>): string[] {
  const sentences: string[] = []
  let unknown = reasons.length === 0
  for (const code of new Set(reasons)) {
    if (Object.prototype.hasOwnProperty.call(known, code)) sentences.push(known[code])
    else unknown = true
  }
  if (unknown) sentences.push(sentences.length ? UNKNOWN_REASON_TOO : UNKNOWN_REASON)
  return sentences
}

export interface HeldCapability {
  key: 'collection' | 'invitation_email'
  title: string
  description: string
}

/**
 * The capabilities a readiness answer holds, each as the banner's notice: registration (collection) held, which also
 * holds new links and Resend unless the invited-cohort exception opens them for its cohort, apart from invitation email
 * held, which leaves links to share by hand. An exception the operator switched on but something else holds is named
 * under registration held, so a misset cohort is not silent.
 */
export function heldCapabilities(readiness: InviteReadiness): HeldCapability[] {
  const held: HeldCapability[] = []
  const { links, email, cohortOnly } = inviteAvailability(readiness)
  const cohortReasons = readiness.invited_cohort.reasons
  const cohortSwitchedOn = !readiness.invited_cohort.available && cohortReasons.length > 0 &&
    !cohortReasons.includes(INVITED_COHORT_SWITCHED_OFF)
  if (cohortOnly) {
    held.push({
      key: 'collection',
      title: 'Registration is open to the invited cohort only',
      description: [
        ...reasonSentences(readiness.collection.reasons, COLLECTION_REASONS),
        "Until registration opens, a new invite link needs its recipient's address and exactly the cohort set in LEGAL_INVITED_COHORT, and only such a link can be resent. The list and Revoke still work.",
      ].join(' '),
    })
  } else if (!links) {
    held.push({
      key: 'collection',
      title: 'Registration is on hold',
      description: [
        ...reasonSentences(readiness.collection.reasons, COLLECTION_REASONS),
        ...(cohortSwitchedOn
          ? ['The invited-cohort exception is switched on but held:', ...reasonSentences(cohortReasons, INVITED_COHORT_REASONS)]
          : []),
        "Until registration opens, you can't create invite links or resend one. The list and Revoke still work.",
      ].join(' '),
    })
  }
  if (!email) {
    // Links held hold invitation email too, whatever its own reasons say.
    const reasons = links ? readiness.invitation_email.reasons : ['collection_unavailable', ...readiness.invitation_email.reasons]
    held.push({
      key: 'invitation_email',
      title: 'Invitation email is on hold',
      description: [
        ...reasonSentences(reasons, INVITATION_EMAIL_REASONS),
        ...(links ? ['You can still create invite links with Email invites off and share them yourself.'] : []),
      ].join(' '),
    })
  }
  return held
}
