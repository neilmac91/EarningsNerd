# EarningsNerd email setup

Reviewed **12 October 2026**. Public mail uses Google Workspace and routes to the existing primary mailbox. The proposed product changes are unmerged and undeployed. Account-specific addresses, mailbox details and verification records are maintained separately.

## Addresses and routing

| Address | Purpose and publication | Routing and label | Reply from this address? |
| --- | --- | --- | --- |
| `support@earningsnerd.io` | Product help, feedback and general/terms questions; footer, contact page, error/form/auth fallbacks, terms, README and transactional Reply-To | Workspace alias; `EarningsNerd/Support`; keep Inbox and unread | Yes |
| `billing@earningsnerd.io` | Subscriptions, payments and invoices; contact, pricing, billing flows and terms | Workspace alias; `EarningsNerd/Billing`; keep Inbox and unread | Yes |
| `privacy@earningsnerd.io` | Privacy and data-rights requests; contact/privacy pages, export/deletion fallbacks and cookie information | Workspace alias; `EarningsNerd/Privacy`; keep Inbox and unread | Yes |
| `security@earningsnerd.io` | Private security reports; contact/security pages and security.txt | Workspace alias; `EarningsNerd/Security`; keep Inbox and unread | Yes |
| `postmaster@earningsnerd.io` | Mail delivery problems | Reserved Workspace Group; primary mailbox receives Each Email; `EarningsNerd/Operations/Postmaster`; keep Inbox and unread | No separate identity |
| `abuse@earningsnerd.io` | Spam and abuse reports | Reserved Workspace Group; primary mailbox receives Each Email; `EarningsNerd/Operations/Abuse`; keep Inbox and unread | No separate identity |
| `dmarc@earningsnerd.io` | Aggregate authentication reports; published in DMARC DNS | Workspace alias; `EarningsNerd/Operations/DMARC`; skip Inbox and mark read | No |
| `hello@inbound.earningsnerd.io` | Existing transactional From identity | Existing Resend sender; proposed product Reply-To is support | Replies go to support after release |

Support combines general enquiries and feedback to avoid unnecessary mailboxes. Billing, privacy and security earn separate addresses because they need distinct triage and discoverable contact routes. Operational Groups accept outside-domain email, have private membership/conversations, and forward Each Email. Google reserves postmaster/abuse for Groups; use security for confidential vulnerability reports. See [Google reserved-address guidance](https://knowledge.workspace.google.com/admin/support/troubleshooting/handling-reports-of-abuse-and-technical-issues) and [RFC 2142](https://www.rfc-editor.org/info/rfc2142/).

## Gmail replies and daily use

Keep the primary identity as the default for ordinary new messages. Configure the four public roles under **Settings → Accounts → Send mail as**, with each role's own Reply-To, and select **Reply from the same address the message was sent to**. Use **EarningsNerd** as the public display name and sign-off. Account-specific saved identity/signature values must be reviewed separately before changing them.

Recipient filters apply the labels above. For an alias, use the following OR search, substituting the role:

```text
{to:support@earningsnerd.io deliveredto:support@earningsnerd.io}
```

Do not apply new filters to existing conversations. Preserve unrelated aliases, Groups, labels and filters. Check From before sending when a message was forwarded, Bcc'd or addressed to several roles. Web reply identities and received authentication have been verified; mobile reply behaviour still needs a real-device check. Use the same label views on web and mobile; Multiple Inboxes is optional.

Saved reply templates can request reproduction details, direct billing questions or acknowledge a privacy request. Templates are inserted manually. Use a neutral product sign-off, avoid duplicate signatures and do not promise a reply faster than **2 business days**. Formal privacy requests follow applicable statutory deadlines. No automatic support acknowledgement is configured beyond the contact-form confirmation.

A ten-minute routine: prioritise security/privacy and urgent account/payment issues for two minutes, handle support/billing for six, then review follow-ups and delivery alerts for two. Aggregate DMARC reports need periodic review rather than daily inbox triage.

This design requires no Business Plus-exclusive feature or additional paid user. Review storage and other plan dependencies separately before any downgrade; no plan or billing change is part of this setup. See [Google email aliases](https://support.google.com/a/answer/33327) and [Workspace Business editions](https://knowledge.workspace.google.com/admin/getting-started/editions/compare-business-editions).

## Product and runtime configuration

The [canonical address JSON](../backend/app/public_email_addresses.json) is consumed by the [frontend module](../frontend/lib/contactAddresses.ts) and [typed backend loader](../backend/app/public_email_addresses.py). Shipped product code imports those values. Documentation and environment examples describe explicit configuration values; internal account addresses must never enter the public map.

| Setting | Source default or later release action |
| --- | --- |
| `RESEND_FROM_EMAIL` | Existing default: `EarningsNerd <hello@inbound.earningsnerd.io>`. The verified root domain can support `EarningsNerd <support@earningsnerd.io>` during a later approved release. |
| `RESEND_REPLY_TO_EMAIL` | New code default: `support@earningsnerd.io` |
| `CONTACT_NOTIFICATION_EMAIL` | New code default: `support@earningsnerd.io`, independent of From |
| `FEEDBACK_NOTIFICATION_EMAIL` | New code default: `support@earningsnerd.io`, independent of From |
| `SEC_USER_AGENT` | New code default: `EarningsNerd/1.0 (support@earningsnerd.io)` |
| `EDGAR_IDENTITY` | Same reachable support contact for the bootstrap default or an explicitly reviewed override |

Live environment values have not changed. Before release, review each service/job's existing overrides and record previous values privately; a source default does not replace an override. Preserve unrelated recipients, credentials, webhook settings and billing configuration. No new frontend email environment variable is required.

Contact and feedback notifications use the submitter's email as Reply-To; confirmations and other transactional mail use support. Keep inbound public mail in Workspace. Resend's root domain is verified for sending only, with receiving disabled and tracking off; preserve the existing inbound subdomain. See [Resend sender configuration](https://resend.com/docs/knowledge-base/how-do-I-create-an-email-address-or-sender-in-resend).

The frontend [security.txt route](../frontend/app/.well-known/security.txt/route.ts) serves HTTPS plain text with the security contact and expiry **2027-09-30T00:00:00Z**; renew before that date. The [API route](../backend/app/routers/security_contact.py) redirects to the canonical website file. Verify both after release. See [RFC 9116](https://www.rfc-editor.org/info/rfc9116/).

## DNS

Cloudflare nameservers are `lou.ns.cloudflare.com` and `sky.ns.cloudflare.com`. The approved DMARC replacement and `rsend` CNAME were applied; all other records, including MX, were preserved. Every future DNS edit requires review and approval of its exact records.

| Name | Type | Value or preservation instruction |
| --- | --- | --- |
| `@` | MX | Priority 1 `aspmx.l.google.com`; priority 5 `alt1.aspmx.l.google.com`, `alt2.aspmx.l.google.com`; priority 10 `alt3.aspmx.l.google.com`, `alt4.aspmx.l.google.com` |
| `@` | TXT | `v=spf1 include:_spf.google.com ~all` |
| `google._domainkey` | TXT | Preserve the exact published Workspace DKIM key |
| `resend._domainkey` | TXT | Preserve the exact published root-domain Resend DKIM key |
| `send` | TXT | `v=spf1 include:amazonses.com ~all` |
| `send` | MX | Priority 10 `feedback-smtp.eu-west-1.amazonses.com` |
| `rsend` | CNAME | `send.forge.rmta.net`; TTL Auto; DNS-only |
| `resend._domainkey.inbound` | TXT | Preserve the exact published subdomain Resend DKIM key |
| `send.inbound` | TXT | `v=spf1 include:amazonses.com ~all` |
| `send.inbound` | MX | Priority 10 `feedback-smtp.eu-west-1.amazonses.com` |
| `inbound` | MX | Priority 10 `inbound-smtp.eu-west-1.amazonaws.com` |
| `_dmarc` | TXT | `v=DMARC1; p=none; rua=mailto:dmarc@earningsnerd.io`; TTL Auto; exactly one policy |

Read back/export existing DKIM keys before any edit. Resend uses its own envelope domain; do not add an unnecessary Resend include to root SPF. Received headers, rather than domain verification alone, establish SPF/DKIM/DMARC results.

Keep DMARC at `p=none` while reviewing aggregate reports across a full sending cycle, including infrequent jobs. Fix legitimate alignment failures first. A gradual `p=quarantine` rollout and later `p=reject` each need separate exact-record approval, monitoring and an approved rollback policy. See [Google](https://support.google.com/mail/answer/81126) and [Yahoo](https://senders.yahooinc.com/best-practices/) sender requirements.

## Verify after routing or release changes

Use an outside account to send a distinct test to each public role and operational address. Confirm the correct label, Inbox/unread state and prompt delivery. For public roles, check the reply's selected From and sign-off before sending; verify the received From/Reply-To plus SPF, DKIM and DMARC headers. Sending from the primary mailbox to its own aliases does not reproduce normal inbound delivery. Repeat a public-role reply on mobile. Test account-specific addresses only against the separate private inventory.

Check changed pages, mailto targets and both security.txt URLs on the preview and after an approved release. A frontend preview using the production API cannot establish that undeployed backend defaults work in production.

## Add a teammate and undo changes

For a shared role, arrange an approved mailbox for the teammate, record the current alias/send-as setup, then migrate that role alias to a private Group with the same address during a planned window. Add the primary mailbox and teammate with Each Email, allow external posting, configure each person's verified send-as/Reply-To, and retest externally. Restore the alias if creation fails. A new paid user needs separate approval.

| Change | Undo |
| --- | --- |
| Task-created aliases | Replace public routing/references first, then remove only the recorded new aliases; existing mail remains intact. |
| Operational Groups | Remove task-added forwarding memberships to stop delivery; obtain approval before irreversible Group deletion. Preserve pre-existing Groups/settings. |
| Recipient filters and labels | Remove only recorded task-created filters. Leave historical mail/labels untouched; remove only empty new labels without affecting stored messages. |
| Send-as/reply preference | Remove only new role identities and restore the recorded previous reply preference; preserve the primary identity. |
| Signatures and templates | Restore recorded role defaults and signature-placement/template settings. Preserve existing templates and retain texts before disabling the feature; deleting a saved template needs approval. |
| DMARC/CNAME | Obtain fresh DNS approval and restore an approved valid policy/record state. Do not recreate the former duplicate DMARC policies. |
| Resend root sender | Restore a recorded prior runtime From before disabling a later sender. Preserve the existing subdomain; irreversible domain deletion needs approval. |
| Runtime overrides | Restore each recorded prior value or remove only new overrides through an approved release; do not expose credentials. |
| Product code/security.txt | Close the unmerged PR or use a reviewed revert PR after a release. Do not merge/deploy automatically. |
| Alias-to-Group migration | Restore the recorded alias/send-as configuration and retest. Preserve any Group history unless its deletion is approved. |
