# Collection readiness and adult eligibility

New registration, waitlist entries and general-contact submissions are closed by default.
Existing login, linked-account access, account management, billing portal access, data export
and deletion are independent of this hold. Public browsing still produces ordinary hosting and
security processing; a closed form is not a claim that the site processes no personal data.

## Operator notice and availability

`GET /api/legal/readiness` returns a non-cacheable availability response, agreement versions and
either an explicitly published operator notice or `operator: null`. The frontend reads it afresh
on mount and treats a failed read as unavailable. Backend routes and persistence/account services
check readiness independently; a stale open browser cannot bypass a closed backend.

The notice requires `LEGAL_OPERATOR_NAME`, `LEGAL_OPERATOR_POSTAL_ADDRESS`,
`LEGAL_OPERATOR_COUNTRY` and `LEGAL_OPERATOR_EMAIL`, plus explicit publication through
`LEGAL_OPERATOR_PUBLISHED=true`. Draft fields remain withheld while publication is false.
Completeness and email-format checks do not verify legal sufficiency or deliverability. Verify
the identity, appropriate public address and contact channel before authorizing publication.

`LEGAL_COLLECTION_ENABLED=true` is a separate opt-in, effective only with a complete published
notice. Neither switch enables new checkout or promotional mail. Those capabilities remain
unavailable until the offer/assent, checkout/deletion coordination, marketing permission,
unsubscribe and suppression work is implemented and verified. There is no temporary configuration
bypass for those missing controls. Requested account messages and existing billing management
continue to work. The waitlist's confirmation email contains only the requested confirmation; the
referral update a member would get when someone joins through their link is promotional mail, and
is not sent while promotional mail is held.

While collection is closed, the unavailable contact form directs readers to the existing support
and privacy contact channels. Keep those channels maintained for account assistance and rights
requests. Do not substitute an unmonitored address or ask people to wait for registration to reopen.

## New-account contract

Every new account requires the user's own affirmative statements that they are at least 18 and
legally an adult where they live, and that they accept the current Terms. These are separate,
unchecked controls. Password registration requires `adult_eligible: true`, `terms_accepted: true`,
`terms_version` and `eligibility_version`; the versions must match the readiness response.
Nonboolean, missing, false and stale inputs are rejected. No birth date or identity document is
collected by this self-attestation mechanism, and it is not identity or age verification.

The registration page also binds acceptance to policy versions bundled with its own text. If an
older page sees newer API versions, it closes registration and asks the reader to refresh; it
cannot relabel its existing checkboxes as acceptance of unseen new requirements.

OAuth signup sends the same fields in the POST start body, alongside any invite. The server binds
accepted versions and time to the short-lived, single-use state. Existing-user OAuth sign-in and
linking require no new agreement. A new identity arriving through a plain sign-in must return to
registration to accept the requirements. Every Google/Apple flow uses server state, and a restored
state cookie cannot replay a consumed state row.

Direct admin account creation is refused. Use the existing invitation flow so the recipient can
make their own statements; an administrator cannot attest for them. Manual invitation links can
be minted only when collection is ready and email delivery is not requested. While marketing is
closed, requested invitation emails and reissues of email-bound invitations return 503 before
creating a replacement or revoking an existing link. Unbound manual links may be reissued while
collection is ready; listing and revoking existing invitations remain available during the hold.
The email sender also independently refuses invitation delivery. Invitation wording, in the email
and in the default message an administrator copies for a manual link, promises account access only,
not Pro access or an available subscription offer; the registration page's lines promising an
invitee full Pro show only once checkout is available. Agreement evidence is stored
with account creation and invite redemption in the same transaction, exported with the account and
deleted with it. Existing accounts are not assigned fictional historical acceptance. A future
existing-user agreement transition must preserve login and privacy rights.

The registration test fixtures provide explicit synthetic assent and opt into a synthetic
published operator through the nonautomatic `collection_ready` fixture. The password, token,
invite, provider-identity and webhook security assertions remain in force. Direct admin
provisioning returns an authenticated 409 refusal, and a plain Google login stores one-use state
with no invite or agreement. Export includes agreement evidence, and a policy-version gate keeps
the Terms date aligned with the version accepted by the API.

## Rollout and remaining work

New collection is closed by default, invited registration included, and new checkout is closed in
code. Opening collection and publishing the operator notice are operator actions:
`LEGAL_COLLECTION_ENABLED` and `LEGAL_OPERATOR_PUBLISHED` default to false, and no deploy or
workflow turns either on.

Before enabling collection, verify the public legal notice, privacy processing inventory, current
agreement text, required regional disclosures, provider arrangements and maintained rights
channels. Test direct password/OAuth/API refusal, successful invited registration with evidence,
existing sign-in/linking, and the closed-form CAPTCHA behavior. Settings only express operator
configuration; they cannot certify legal compliance.

The legal pages currently refresh the published operator notice in the browser. Their static
support/privacy contact fallback remains visible without that request, but the operator details
are not in the initial server-rendered HTML. Verify accessibility and availability of the complete
notice before enabling collection; this implementation does not establish a no-JavaScript
operator-disclosure guarantee.

Remaining subscription work includes immutable account-bound offers, renewal assent and evidence,
published-price protection, acknowledgments and applicable withdrawal handling. The checkout and
account-deletion protocol must recover late Stripe results without holding database connections
across provider calls, and coordinate competing checkout intents for the same account. Remaining
marketing work includes separate permission, durable send-time suppression, unsubscribe and
authenticated bounce/complaint updates. Do not enable either capability by removing its hold alone.

Nothing here certifies the existing deletion endpoint's provider cleanup, changes retention
periods, registers a copyright agent, or resolves historical billing records. Those remain separate
implementation and operational obligations.
