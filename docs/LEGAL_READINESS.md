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
notice. Neither switch enables new checkout or promotional mail. New checkout stays closed in code
until the offer/assent and checkout/deletion coordination work is implemented and verified, and so
does general promotional mail, which has no permission record of its own. Requested beta-invitation
email is a capability of its own, behind its own switch: its permission record, send-time
suppression, unsubscribe and authenticated bounce/complaint updates are implemented
([Invitation email](#invitation-email)). Invited-cohort registration is an admission exception of
its own, behind its own switch, for invitations alone; it opens no collection
([Invited-cohort registration](#invited-cohort-registration)). There is no temporary configuration
bypass for a missing control. Requested account messages and existing billing management continue to work. The waitlist's confirmation email contains only the requested confirmation; the
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
be minted only when collection is ready. While invitation email is unavailable, a requested
invitation email, and a re-send that would email (one that asks to, or one of an email-bound
invitation that names no choice), return 503 before creating a replacement or revoking an
existing link. A re-send that asks for a manual link (`send_email: false`) works for bound and
unbound invitations while collection is ready; listing and revoking existing invitations remain
available during the hold. The email sender also independently refuses invitation delivery. Invitation wording, in the email
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
workflow turns either on. So does the invited-cohort exception's switch,
`LEGAL_INVITED_COHORT_ENABLED`.

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
across provider calls, and coordinate competing checkout intents for the same account. For
requested beta invitations the marketing controls now exist ([Invitation email](#invitation-email));
general promotional mail stays closed, and would need a permission record and wording of its own
on the same suppression list. Do not enable a capability by removing its hold alone.

## Invitation email

A requested beta invitation can be emailed only while every condition holds
(`legal_readiness_service.invitation_email_readiness`; the admin page's banner names each one that
does not):

- collection is available (above), or the invited-cohort exception is and the link is in its cohort
  ([Invited-cohort registration](#invited-cohort-registration)), since the link must be redeemable;
- `LEGAL_INVITATION_EMAIL_ENABLED` is true: the operator's switch, set only after the founder
  approves the permission policy below and an approved test send has passed;
- `RESEND_API_KEY` is set; and
- `RESEND_WEBHOOK_SECRET` holds a usable Svix secret, without which bounces and complaints cannot be
  authenticated, so they could not suppress later sends.

The admin route and the sender each check again; neither trusts the browser's copy. General
promotional mail (the waitlist's referral update, any campaign) stays closed in code whatever the
switch says.

**Permission.** An invitation is emailed only to someone who asked for one. With each emailed
invitation the admin records how the recipient asked (email, message, call, in person or other) and
on which day, within the last year; the record is stored with the send. Knowing the person, an
admin's checkbox or an account's acceptance of the Terms is not this permission. It covers the
invitation email for that link and its re-sends, nothing else, and an unsubscribe ends it. Whether a
recorded request is a sufficient basis for this mail wherever a tester lives is the founder's
decision, made before the switch is turned on.

**One link per person.** An emailed invitation is refused while another live invitation is bound to
the address, and a re-send of a bound invitation is refused while a different live one exists, so a
repeated submit, a retry or a second tab cannot mail two different links. A re-send revokes the old
link in the same transaction that creates its replacement.

**Suppression.** An unsubscribe, a permanent bounce, a complaint or the provider's own suppression
list suppresses the address for invitation and any future promotional mail, and a suppressed address
is refused before anything is written. Requested account mail (verification, password reset, the
sign-in notices) never reads the list. The list keeps a pseudonymous SHA-256 of the normalized
address under a fixed prefix, with the suppression's reason and source. It holds a row for each
address an invitation was emailed to (the lock that address's sends and its opt-out take, unsuppressed
until something suppresses it) and for each address that unsubscribed, bounced permanently, complained
or was suppressed by the provider on any mail EarningsNerd sends, which starts once
`RESEND_WEBHOOK_SECRET` is bound (F46). A manual re-issue, which sends nothing, adds no row. It is not peppered with
`SECRET_KEY`, because rotating that key would silently forget every opt-out; the cost is that the
hash of a known address can be recomputed. It survives account deletion, since honouring an opt-out
means recognizing the address again. Its retention, and its mention in the privacy notice, are the
founder's decision.

**Unsubscribe.** Each invitation's footer links `/email/unsubscribe#token=…`. The token rides in the
fragment, which no request carries, so no server or proxy log records it, and the page posts it only
when its reader presses the button, so a link scanner's fetch changes nothing. A send and an opt-out
take the address's row lock in turn: a send authorised before an opt-out committed may still go out,
and none authorised after it does (proven on PostgreSQL in
`backend/tests/integration/test_admin_invite_transactions.py`).

**Delivery record.** Each emailed link has one delivery row with a server-made reference, sent as the
provider's idempotency key (`en-invite-<ref>`) and as the tag `en_invite_delivery`, which the
provider's events carry back. Its state says only what the evidence supports: `sending` (committed
before the call), `accepted` (the provider took it: not delivered, not read), `delayed`, `delivered`
(the recipient's mail server accepted it: not proof it reached the inbox), `bounced`, `complained`,
`suppressed` (by the provider), `failed` (nothing was sent) or `unknown` (the provider may have
accepted it and the answer was lost; a row still `sending` five minutes after its commit reads
unknown). Signed events move a row up that order and never down, so a duplicate, a retry or a late
event changes nothing; an unsigned delivery records nothing, and a failed write answers 503 so the
provider sends it again. Neither the link's token nor the unsubscribe token is stored. An unknown
outcome is never retried blind: the admin's re-send, which revokes the link and mails a new one, is
its recovery.

### Enabling invitation email

Operator steps, in order, each after the one before has passed. No deploy or workflow does any of
them.

1. Founder: approve the permission policy above, and the suppression list's retention and notice.
2. Confirm collection is ready (`GET /api/legal/readiness`), or, for the invited cohort alone, that
   the admin banner reads "Registration is open to the invited cohort only", and that
   `REGISTRATION_MODE` is the intended mode (`invite_only` for the beta).
3. Resend: subscribe the webhook to `email.sent`, `email.delivered`, `email.delivery_delayed`,
   `email.bounced`, `email.complained`, `email.failed` and `email.suppressed`, and bind
   `RESEND_WEBHOOK_SECRET` ([resend-webhooks.md](integrations/resend-webhooks.md)); the admin banner
   then no longer names `provider_feedback_unverified`.
4. Set `LEGAL_INVITATION_EMAIL_ENABLED=true` on `earningsnerd-backend`.
5. Canary, with destinations the founder approves: email one invitation to an inbox the founder holds;
   confirm its receipt, its From/Reply-To and SPF/DKIM/DMARC headers, that its link opens
   `https://www.earningsnerd.io/register?invite=…`, registration with the tester's own agreement,
   verification, login and a password reset. Then unsubscribe from that email and confirm that a
   second emailed invitation to the address is refused.
6. Rollback: set `LEGAL_INVITATION_EMAIL_ENABLED=false`. Sends stop at once (the route and the sender
   both check); links already issued stay valid until they expire or are revoked; the delivery record
   and the suppression list stay.

## Invited-cohort registration

An admission exception that lets a known group of invited testers open accounts while collection
stays held. It opens no collection: `GET /api/legal/readiness` still reports collection, checkout
and promotion unavailable and returns no operator notice, and general registration, the waitlist
and the contact form stay closed.

It is in effect only while every condition holds
(`legal_readiness_service.invited_cohort_readiness`; the admin page's banner names each one that
does not):

- `REGISTRATION_MODE` is `invite_only`;
- `LEGAL_INVITED_COHORT_ENABLED` is true (the default is false); and
- `LEGAL_INVITED_COHORT` holds an opaque cohort label that an invitation can carry: not empty, no
  space at either end, no control character, at most 64 characters (a synthetic example:
  `cohort-synthetic-7f3a9c`). The label is an identifier, not a secret: no public response carries
  it, but the admin page lists each invitation's cohort, the audit log records it, and the server's
  private logs and error reports can carry it, as they can an account's address. Choose one that
  names no one and says nothing about the notice.

While it is in effect and collection is held, an invitation admits an account only when it is bound
to its recipient's address and its stored cohort equals the configured label exactly. Each path
checks this itself, when it acts, and trusts no earlier answer:

- minting an invitation (`POST /api/admin/invites`) and re-issuing one
  (`POST /api/admin/invites/{id}/resend`), before anything is written or revoked: 422 for an
  invitation outside the cohort or bound to no address, and 503, as before, while neither collection
  nor the exception is open;
- emailing an invitation: the admin route and the sender (`email_service.send_invite_email`) each
  check its cohort again, and the permission, one-link and suppression rules above still apply;
- password registration (`POST /api/auth/register`): the request's invitation must validate (its
  bound address, unexpired, unrevoked, unused) and be in the cohort, and the account service
  (`auth_account_service.create_password_account`) decides admission again. Its redemption is one
  guarded update that requires the invitation's row to be unused, unrevoked, unexpired, in the
  cohort and bound to the new account's address, so neither the copy of the invitation the route
  read earlier nor the browser decides it;
- Google and Apple sign-up: the start (`POST /api/auth/{google,apple}/start`) refuses a sign-up whose
  invitation is not live and in the cohort, and the callback decides again on the address the
  provider verified, with the same guarded redemption, so an exception closed during a sign-in
  admits nothing.

A sign-up without an invitation meets the closure it always met (503), and an invitation the
exception refuses gets the answer any invalid invitation gets (403 at `/api/auth/register`,
`invite_required` after a social sign-in). A password registration whose admitted invitation is
bound to the address of an existing account creates nothing and spends no invitation; as with open
registration, it answers as a new account does, and the account's owner gets the account-exists
notice. Existing sign-in, linking, sessions and account rights are unchanged, and a new account
still needs both of its holder's own statements.

`GET /api/auth/registration` carries `invited_cohort_available`, a boolean and never the label, with
`Cache-Control: no-store`. The register page reads it afresh for a visitor holding an invitation
while collection is held, opens the form only on an exact `true`, treats a failed or malformed read
as closed, and reads it again before each sign-up. It decides only what the page offers.

**What the code does not establish.** The exception is for a cohort that receives the operator's
notice privately before any public notice is published. The code enforces cohort eligibility only;
it cannot see whether, when or how that notice reached anyone. The notice's version and its
delivery to each invitee are the operator's own record, kept outside this repository, linked by
cohort label and invitation ID, and made before addresses are imported or any invitation is
emailed. Whether a privately delivered notice is a sufficient basis for this collection wherever a
tester lives is the founder's decision; nothing here claims it is.

**Operating it.** Operator steps; no deploy or workflow does any of them.

1. Founder: decide the cohort, its private notice and that notice's delivery record (above).
2. On `earningsnerd-backend`, with `REGISTRATION_MODE=invite_only`, set `LEGAL_INVITED_COHORT` to
   the cohort's label and `LEGAL_INVITED_COHORT_ENABLED=true`. The admin banner then reads
   "Registration is open to the invited cohort only".
3. Mint each invitation bound to its recipient's address, with that label in its Cohort field.
4. To close it, set `LEGAL_INVITED_COHORT_ENABLED=false`. Every mint, re-send, send, registration
   and sign-up checks it at once. While it is off and collection is held, links already issued
   admit no account, and they work again if it reopens before they expire. Accounts it admitted
   keep their access.

The cases are in `backend/tests/unit/test_invited_cohort_registration.py` and, for the register
page, `frontend/tests/unit/registerInvitedCohort.spec.tsx`.

Nothing here certifies the existing deletion endpoint's provider cleanup, changes retention
periods, registers a copyright agent, or resolves historical billing records. Those remain separate
implementation and operational obligations.
