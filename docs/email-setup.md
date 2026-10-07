# EarningsNerd email setup

Status reviewed on **8 October 2026**. EarningsNerd is operated by Neil as an individual. This document does not establish a company, registered office, or data protection officer.

## Current status

| Work | Status |
| --- | --- |
| Gmail settings inventory | Read-only baseline recorded: primary Send mail as identity is `neil@earningsnerd.io`; existing labels and filters are preserved. |
| Workspace directory inventory | Neil's super admin access verified. Existing users/aliases/Groups inspected; the pre-existing second licensed user and existing aliases are preserved. No Groups existed at audit. Default routing is empty; the sole existing Gmail routing rule targets archived accounts with delegates only, with active users/Groups unchecked; preserved without saving changes. |
| Public and DMARC aliases | Created on Neil's existing user and saved; **external delivery is not verified yet**. |
| Reserved operational Groups | Created; Neil is sole owner/member, external posting allowed, conversations and members hidden from outsiders. **Each Email verified for both**; external delivery still needs testing. Both Groups have ordinary-message moderation None, email posting on, conversation history off, author-address default and automatic replies off, verified without changing these defaults. |
| Gmail role identities and recipient filters | All 11 new recipient filters imported and saved; “Apply to existing conversations” off; original five filters preserved. Four public Send mail as identities and explicit own-role Reply-To values verified. Reply-from-same-address selected; Neil remains the default. Google verification messages received with all four public labels. Founder signature and all four role new-message/reply defaults saved and verified after reload; Neil retains No signature. Templates enabled and three task-created templates saved/verified in the menu. |
| Gmail label hierarchy | Genuine nested navigation verified after reload: four public labels under EarningsNerd, three operations labels under EarningsNerd/Operations, and private account labels under their separate parent. |
| Workspace signing/routing | Google DKIM shows Authenticating email; default routing empty and the existing archived-account delegation rule preserved. Received headers still need testing. |
| Resend sender domain | Root earningsnerd.io added and fully verified for sending only, receiving disabled, tracking off, EU West. DKIM/send MX/TXT and approved rsend CNAME all verified. Existing inbound domain preserved; received-message test pending. |
| Product changes | Committed on the email-setup branch and opened as [draft PR #1121](https://github.com/neilmac91/EarningsNerd/pull/1121); production is unchanged. Local code gates and mutation proofs pass. The preview rendered 13 light/13 dark visitor/auth pages; 55 recorded mailto targets and security.txt browser content are verified. See [preview verification](#preview-verification) for limits. |
| DNS | Neil-approved DMARC replacement **applied**. Authoritative readback returns exactly one `p=none` policy reporting to dmarc. The separately approved rsend CNAME is also applied; no other DNS changed and MX is untouched. |
| External inbound, reply identity and authentication tests | Pending Neil's final test step. Internal self-sends are insufficient evidence. |

The private operations guide is stored outside this public repository. Internal coding account addresses are intentionally absent from repository files, application code and public pages.

## Addresses and routing

The primary mailbox remains `neil@earningsnerd.io`. Aliases, operational Groups, recipient filters/labels, public reply identities, founder signature defaults and three Gmail templates are configured and saved. Both Group Each Email subscriptions and advanced defaults are verified. The label hierarchy is verified after reload. Visitor/auth preview renders, public mailto targets and security.txt browser content are verified. Real outside-account tests remain pending; the preview limits are recorded below. Product changes are committed in the draft PR and undeployed.

| Address | Purpose | Intended publication | Configured routing | Reply from role? |
| --- | --- | --- | --- | --- |
| `support@earningsnerd.io` | General questions, product help, feedback and terms/licensing enquiries | Footer, contact page, error and form fallbacks, onboarding/transactional reply contacts, terms, README and structured data | Alias to Neil; `EarningsNerd/Support`; retain Inbox | Yes; external reply test pending |
| `billing@earningsnerd.io` | Subscriptions, invoices, cancellations and payment questions | Contact page, pricing, relevant account/billing flows and structured data | Alias to Neil; `EarningsNerd/Billing`; retain Inbox | Yes; external reply test pending |
| `privacy@earningsnerd.io` | Data rights, deletion/export issues and privacy questions | Contact page, privacy policy, account deletion/export fallbacks, cookie information and structured data | Alias to Neil; `EarningsNerd/Privacy`; retain Inbox | Yes; external reply test pending |
| `security@earningsnerd.io` | Vulnerability and security reports | Contact/security pages, `/.well-known/security.txt` and structured data | Alias to Neil; `EarningsNerd/Security`; retain Inbox | Yes; external reply test pending |
| `postmaster@earningsnerd.io` | Mail delivery problems | Conventional operational contact; no extra promotional placement | Reserved Group; Neil sole owner/member; Each Email verified; `EarningsNerd/Operations/Postmaster`; retain Inbox | No additional Gmail identity planned |
| `abuse@earningsnerd.io` | Spam and abuse reports | Conventional operational contact; no extra promotional placement | Reserved Group; Neil sole owner/member; Each Email verified; `EarningsNerd/Operations/Abuse`; retain Inbox | No additional Gmail identity planned |
| `dmarc@earningsnerd.io` | Machine-generated aggregate authentication reports | Applied DMARC DNS policy | Alias to Neil; `EarningsNerd/Operations/DMARC`; skip Inbox and mark read | No |
| `hello@inbound.earningsnerd.io` | Existing Resend transactional sender | From header of product emails | Existing Resend sending/inbound domain; preserve transport. Proposed Reply-To is `support@earningsnerd.io` | Customers reply to support |

Support combines general enquiries and feedback so a solo founder does not maintain extra hello, legal, press, partners or feedback mailboxes. Billing is useful for payment-related triage; privacy and security provide discoverable, distinct reporting channels. Customers hear from Neil personally, signed as founder.

Aliases deliver directly to the existing mailbox and need less setup than a distribution Group for one person. Google supports up to 30 aliases per user without extra cost. A public alias can later become a Group with the same address when a teammate needs delivery. No paid Workspace users are required for this setup. See [Google aliases](https://support.google.com/a/answer/33327) and [RFC 2142 role mailboxes](https://www.rfc-editor.org/info/rfc2142/).

## Workspace configuration procedure — partly complete

1. Neil's super admin access and directory inventory are confirmed. Default routing is empty. The sole existing Gmail routing rule rejects archived accounts with delegates only; active users and Groups are unchecked. It was inspected and cancelled without changes. If an intended address belongs to something else, flag the conflict; do not remove or alter it.
2. The four public aliases and DMARC alias have been saved on Neil's existing user without conflicts. No paid users, catch-all routing, or additional Google login identities were created; the pre-existing second licensed user remains untouched.
3. `postmaster` and `abuse` Groups have been created in **Admin console**. These reserved names cannot be individual user aliases. Google documents that creation can display an error while still creating the Group; check the directory before retrying.
4. Neil is the sole owner/member of both Groups. External email posting is enabled; outsiders cannot view conversations or members. Neil's **Each Email** subscription has been verified for both in the Neil account's My Groups view. Both Groups' advanced defaults are verified: ordinary-message moderation **None**, email posting **on**, conversation history **off**, author-address default and automatic replies **off**. A public contact Group needs external posting, not external membership or public archives. Preserve unrelated organisational policies and Groups.
5. Record every newly created alias, Group and setting, plus the original values of any changed settings, in the private change log.

Google continues receiving mail submitted to the abuse Group. Use security, rather than abuse, for confidential vulnerabilities. See [reserved Groups](https://knowledge.workspace.google.com/admin/support/troubleshooting/handling-reports-of-abuse-and-technical-issues), [Group settings](https://support.google.com/groups/answer/2464926) and [private Groups accepting external email](https://knowledge.workspace.google.com/admin/groups/set-organization-wide-policies-for-using-groups).

## Gmail configuration — settings and signatures saved; external tests pending

`neil@earningsnerd.io` remains the default sender for new personal messages. The four public roles are saved and verified under Settings → Accounts → **Send mail as**, with display name **Neil · EarningsNerd**. Each role's own address is explicitly saved in its Reply-To field and verified in Accounts readback. **Reply from the same address the message was sent to** is selected. The prior setting was **Always reply from default address (currently neil@earningsnerd.io)**. Only new Google verification emails were opened for ownership verification; all four arrived with their public labels. Ordinary replies addressed to a single public role should use that role automatically; Bcc, forwarding and multi-role recipients still require checking the From field. The real outside-account and mobile reply tests remain pending.

All 11 task-created filters and their labels have been imported and saved, using recipient criteria without changing existing sender filters. The alias filters use this Gmail search pattern, replacing the address:

```text
{to:support@earningsnerd.io deliveredto:support@earningsnerd.io}
```

The braces mean OR. Normal To/Cc recipients and original delivery headers can differ, especially with Bcc or forwarding, so confirm against external test mail. The reserved Group filters match their recipient addresses; adjust only task-created filters if real test headers show another criterion is needed. Do not guess a List-ID before a test message exists. Public and operations filters leave mail unread in Inbox. The DMARC filter applies `EarningsNerd/Operations/DMARC`, skips Inbox and marks read. **Apply to existing conversations was off**; these filters were not applied retrospectively.

The observed pre-existing labels are `Action Required`, `Billing/Payments`, `DevOps/Alerts`, `Google Cloud`, `Newsletters`, `Security`, and `Tools/Services`. Five existing sender filters route Sentry/Vercel/Render mail to `DevOps/Alerts` and skip Inbox, Stripe mail to `Billing/Payments`, and PostHog mail to `Security`. Leave these filters and labels unchanged. New `EarningsNerd/…` labels make this task's additions easy to identify and undo. Genuine nesting was verified after reload: Support, Billing, Privacy and Security under EarningsNerd; Postmaster, Abuse and DMARC under EarningsNerd/Operations; private account labels under their separate parent. Opening a parent label does not necessarily aggregate messages carrying only its children; use the specific label view.

Use label views on both web and mobile. Multiple Inboxes would change the current desktop layout and does not provide the same mobile workflow, so it is optional rather than part of the default setup. Gmail templates are available on computer only. See [Send mail as](https://support.google.com/mail/answer/22370), [Multiple Inboxes](https://support.google.com/mail/answer/9694882) and [templates](https://support.google.com/mail/answer/14864208).

The saved baseline was **No signatures**, with Neil's personal address set to **No signature**. The signature **Neil — EarningsNerd** is now saved with the content below. Billing, privacy, security and support each use it for both new messages and replies; persistence and all eight role defaults were read back after reload. Neil's personal new-message/reply defaults remain **No signature**:

```text
Neil
Founder, EarningsNerd
https://earningsnerd.io
```

Gmail supports signatures per send-as address. On mobile, leave the mobile signature unset if using the computer signature, or use the same plain founder signature. Check mobile replies during verification; Google documents computer-signature fallback for new messages, which alone does not prove every mobile reply behaves identically. See [web signatures](https://support.google.com/mail/answer/8395), [iOS](https://support.google.com/mail/answer/8395?co=GENIE.Platform%3DiOS) and [Android](https://support.google.com/mail/answer/8395?co=GENIE.Platform%3DAndroid).

No automatic support acknowledgement is planned. At beta volume it adds mail and settings without reducing the need for a personal reply; Gmail also warns automated filter responses can expose the primary identity. No external auto-replies are enabled by this task. Templates are enabled and these three task-created templates are saved and verified in Gmail's menu:

- **EarningsNerd — Support details:** Neil introduces himself as founder, asks for the relevant URL and steps, tells the sender to omit passwords/login codes/payment details, and aims to reply within two business days.
- **EarningsNerd — Billing details:** Requests the account email and invoice/receipt reference, and asks the sender to omit card details.
- **EarningsNerd — Investigating:** Acknowledges the supplied detail, identifies the issue being investigated, and says Neil will follow up when he has an update.

Each template already includes Neil's founder sign-off. When inserting one, remove a duplicate automatically appended signature if necessary. Templates are inserted manually and never sent automatically. Only a task-created working draft was discarded after saving; the Drafts count returned to its prior baseline of two. Any future time commitment must be no faster than two business days; privacy requests also remain subject to applicable statutory deadlines.

## Product and runtime configuration

The PR centralises public contact roles in [the canonical public address JSON](../backend/app/public_email_addresses.json), consumed by [the frontend contact module](../frontend/lib/contactAddresses.ts) and [the backend loader](../backend/app/public_email_addresses.py). Product surfaces must use these shared values rather than introducing new address literals. The backend retains the existing Resend From identity, introduces a reply-able support default, and uses explicit contact/feedback notification destinations instead of deriving an inbox from the From address. These changes are **not deployed**.

| Runtime setting | Proposed value/action | Status |
| --- | --- | --- |
| `RESEND_FROM_EMAIL` | Current code default preserved: `EarningsNerd <hello@inbound.earningsnerd.io>`. Root domain now fully verified; proposed later runtime value: `Neil · EarningsNerd <support@earningsnerd.io>` | Review the actual production env/secret and apply only in a later authorised release; unchanged here |
| `RESEND_REPLY_TO_EMAIL` | `support@earningsnerd.io` | New code default; review any production override before later release |
| `CONTACT_NOTIFICATION_EMAIL` | `support@earningsnerd.io` | New explicit code default; review any production override before later release |
| `FEEDBACK_NOTIFICATION_EMAIL` | `support@earningsnerd.io` | New explicit code default; review any production override before later release |
| `SEC_USER_AGENT` | Reachable support contact, e.g. `EarningsNerd/1.0 (support@earningsnerd.io)` | List Cloud Run/job override changes for Neil; do not assume values |
| `EDGAR_IDENTITY` | Same reachable support contact, where an explicit override exists | Review Cloud Run/jobs/scripts separately |
| `DATA_QUALITY_REPORT_EMAIL` | Preserve `neil@earningsnerd.io` | No change |
| Resend API key, webhook secret and base URL | Preserve | No secret changes |
| Vercel | Public constants are built into the frontend; no new email-specific env var planned | Hosted build and visitor/auth preview verified; see [preview verification](#preview-verification) for the authenticated-settings, cookie-dialog and deployed-header limits |

Contact/feedback notifications use the submitter's email as Reply-To; customer confirmations and other transactional mail use support. Do not change Stripe receipt/sender configuration during this task: billing settings are founder-held. The existing verified Resend domain is `inbound.earningsnerd.io`; its sending/receiving configuration is preserved. The added root domain `earningsnerd.io` is fully verified for sending only, with receiving disabled and the approved CNAME applied. Resend has no individual sender address to create: From/friendly name and Reply-To come from each API payload. No Resend Inboxes or stored Resend templates exist. Keep all public-role inbound mail in Workspace. Domain verification alone does not prove received-message authentication. See [Resend sender addresses](https://resend.com/docs/knowledge-base/how-do-I-create-an-email-address-or-sender-in-resend) and [email API](https://resend.com/docs/api-reference/emails/send-email).

The proposed security.txt publishes the security mailto, canonical URL, English preference and Expires `2027-09-30T00:00:00Z`, less than one year after setup. It must be served over HTTPS as `text/plain; charset=utf-8`. Renew before that date. The main-domain file does not automatically cover `api.earningsnerd.io`; the backend PR adds a redirect to the canonical file. Verify both frontend and API discovery routes after any later approved release before claiming live coverage. See [RFC 9116](https://www.rfc-editor.org/info/rfc9116/).

## DNS: preserved records and applied approved changes

Cloudflare nameservers are `lou.ns.cloudflare.com` and `sky.ns.cloudflare.com`. **Only the exact Neil-approved DMARC replacement and separately approved rsend CNAME addition have been applied. No other DNS changed; all MX records remain untouched.**

| Name | Type | Observed value | Action |
| --- | --- | --- | --- |
| `@` | MX | Priority 1 `aspmx.l.google.com`; priority 5 `alt1.aspmx.l.google.com` and `alt2.aspmx.l.google.com`; priority 10 `alt3.aspmx.l.google.com` and `alt4.aspmx.l.google.com` | Preserve |
| `@` | TXT | `v=spf1 include:_spf.google.com ~all` | Preserve; only one root SPF policy |
| `google._domainkey` | TXT | Published Google RSA DKIM public key | Preserve exact key; Workspace shows Authenticating email, received headers still need verification |
| `resend._domainkey` | TXT | Existing Resend root-domain public DKIM key | Preserved; vendor verification passed |
| `send` | TXT | `v=spf1 include:amazonses.com ~all` | Preserved; vendor verification passed |
| `send` | MX | Priority 10 `feedback-smtp.eu-west-1.amazonses.com` | Preserved; vendor verification passed |
| `rsend` | CNAME | `send.forge.rmta.net` | Exact addition approved and applied; TTL Auto, DNS-only; authoritative CNAME readback matches |
| `resend._domainkey.inbound` | TXT | Published Resend DKIM public key | Preserve exact key |
| `send.inbound` | TXT | `v=spf1 include:amazonses.com ~all` | Preserve |
| `send.inbound` | MX | Priority 10 `feedback-smtp.eu-west-1.amazonses.com` | Preserve |
| `inbound` | MX | Priority 10 `inbound-smtp.eu-west-1.amazonaws.com` | Preserve |
| `_dmarc` | TXT | `v=DMARC1; p=none; rua=mailto:dmarc@earningsnerd.io` | Applied; exactly one policy confirmed by authoritative readback |

The DKIM table names the existing keys instead of repeating their long public-key values. Export/read back the exact existing Cloudflare records before any edit. Other existing DNS records remain untouched. The three pre-existing root-domain Resend records match the new vendor configuration exactly and have verified without any DNS edit.

The prior duplicate policies were `v=DMARC1; p=none; rua=mailto:neil@earningsnerd.io` and the same value with `; fo=1`. Two policy records prevent valid DMARC discovery. Neil approved and the task applied their replacement with exactly one record:

```text
Type: TXT
Name: _dmarc
Value: v=DMARC1; p=none; rua=mailto:dmarc@earningsnerd.io
TTL: Auto
```

This exact replacement, including removal of the duplicate entries, was **approved and applied on 8 October 2026**. An authoritative query, `dig @sky.ns.cloudflare.com _dmarc.earningsnerd.io TXT`, returned exactly the single policy above. This proves publication, not a received message's authentication result. No separate DMARC policy was observed for the Resend sending subdomain; it inherits the now-valid root policy. Do not add an unnecessary Resend include to root SPF: Resend uses its own envelope domain, while aligned DKIM can satisfy DMARC for its visible From domain. Confirm actual SPF/DKIM identities and alignment in a received message.

### Resend root sender: CNAME applied and domain fully verified

The root sending-only domain was added reversibly within the existing Free plan (two of three domain slots). It is now **Verified**, including the existing `resend._domainkey` TXT and `send` MX/TXT plus the added CNAME. Resend's dashboard places the CNAME under sending SPF, with receiving off. Neil approved and the task applied this exact addition; authoritative sky.ns.cloudflare.com readback returns one matching CNAME. All four vendor-generated authentication records now read Verified:

```text
Type: CNAME
Name: rsend
Target: send.forge.rmta.net
TTL: Auto
Proxy: DNS-only (off)
```

Before the addition, no existing `rsend` CNAME was found in authoritative DNS. Do not replace root Google MX/SPF or existing DKIM records, add receiving MX, enable Resend receiving on the root domain, or use automatic Cloudflare DNS setup. The approved record is applied and the fresh verification check completed: root status and all four records read Verified, sending enabled, receiving disabled and tracking off. A message to Neil with From and Reply-To support remains part of the gated final authentication test. Only a later authorised release may change the actual production From environment value. The application's present From default is unchanged.

Keep `p=none` until Google Workspace and every product sender are identified and their test headers pass. Review aggregate reports over at least a full sending cycle that includes infrequent jobs; correct legitimate failures first. Then request separate approval for a gradual `p=quarantine` rollout, monitor delivery/reporting, and request approval for `p=reject` only when legitimate senders consistently align. Preserve the last approved policy for rollback. Do not tighten automatically. See [Google sender requirements](https://support.google.com/mail/answer/81126) and [Yahoo sender requirements](https://senders.yahooinc.com/best-practices/).

## Privacy identity and Workspace tier

Privacy is a reachable role contact, not a claim that Neil has appointed a DPO. GDPR Articles 13–14 and Swiss FADP Article 19 require controller identity and contact information where applicable. The live privacy/terms pages and working legal templates need Neil's legal-identity and correspondence-address review; never invent an entity, registered address, home address or phone number. This PR removes a pre-existing home-address disclosure from the EULA working document; it does not erase earlier Git history. A dedicated role email alone does not settle every legal-page obligation. See [GDPR](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng/) and [Swiss FDPIC information guidance](https://www.edoeb.admin.ch/dam/en/sd-web/brLL9rM3ny9d/Leitfaden%20des%20ED%C3%96B%20betreffend%20Datenbearbeitungen%20mittels%20Cookies%20und%20%C3%A4hnlichen%20Technologien%20V.%201.1%20vom%2006.10.2025_EN.pdf).

This email design requires no Business Plus-exclusive feature. Business Starter includes aliases, Groups, filtering and routing; it has 30 GB pooled storage per user. Plus includes features such as Vault and larger storage. Before any future downgrade Neil should review storage usage, Vault retention/holds and other independently used features. **No Workspace plan or billing change is part of this task.** See [Gmail edition comparison](https://knowledge.workspace.google.com/admin/gmail/compare-gmail-features-across-google-workspace-editions) and [Business editions](https://knowledge.workspace.google.com/admin/getting-started/editions/compare-business-editions).

## Ten-minute daily routine

1. Spend two minutes on new security/privacy mail and time-sensitive account/payment issues.
2. Spend six minutes on support/billing: respond personally, use a saved template when useful, and star or apply the existing `Action Required` label to work needing a follow-up. Archive only after it is handled, as part of Neil's own daily routine.
3. Spend two minutes on pending follow-ups and operational delivery alerts. Open private account labels when requesting a sign-in link/code. Review DMARC reports periodically or when a sending change occurs; raw XML reports are not a daily support queue.

During setup the assistant must not open, archive, delete or reply to existing messages. The routine above describes Neil's future use, not an action authorised on historical mail.

## Verification and completion record

The code is reviewable in [draft PR #1121](https://github.com/neilmac91/EarningsNerd/pull/1121). Local frontend lint and CI type-check pass. The full frontend suite passed 147 files/1,131 tests before the final waitlist/Turbopack changes; subsequent affected checks passed 8 tests and staged-source checks passed 9 tests. The final production build compiled and generated 28/28 static pages. Backend checks on Python 3.11.17 passed Ruff, Bandit and the full pytest gate: 5,762 passed, 39 skipped and 2 deselected, with 40 warnings. All seven committed-state mutation guards failed on their intended temporary faults and passed after restoration. Detailed commands, exact tails and limitations are in the PR.

### Preview verification

The [Vercel preview](https://earnings-nerd-git-codex-wave3-998a23-neil-mac-aogains-projects.vercel.app) is Ready for tested feature revision `cd8fd049395660ebab584bcb1874cd72e177b899`. The existing authorised browser session completed **13 light and 13 dark render checks** at `/`, `/contact`, `/pricing`, `/privacy`, `/terms`, `/security`, `/delete-account`, `/login`, `/register`, `/forgot-password`, `/check-email`, `/reset-password` and `/verify-email`. Saved URL/headings records cover 13 light pages and 12 dark pages; the separate dark contact screenshot completes the dark-theme evidence.

All **55 recorded mailto labels and targets** (30 light, 25 dark) match the canonical address map and the expected roles on each page. The contact page displays all four roles in both themes. The static privacy policy cookie paragraph also has the correct privacy link. No mail was sent to test these links. Before/after contact screenshots and the security.txt screenshot are saved in private task outputs; browser chrome/bookmarks in those captures are kept private.

The browser displays security.txt with `Contact: mailto:security@earningsnerd.io`, `Expires: 2027-09-30T00:00:00Z`, `Canonical: https://www.earningsnerd.io/.well-known/security.txt`, `Preferred-Languages: en` and the security policy URL. Actual deployed HTTP status/MIME headers were not inspected: unauthenticated CLI requests reach Vercel SSO, and the existing CLI has no credentials. Local route gates separately verify HTTP 200 and `text/plain; charset=utf-8`.

Authenticated `/dashboard/settings` and its billing/data-request states still require an existing product login; no product account was created. Conditional error views are covered by the local suite and code review. Existing consent meant the cookie-preferences dialog was not shown, so its modal rendering remains unverified. The preview uses the production API and does not verify the undeployed backend changes.

Successful local/hosted builds and actual browser contacts establish that this revision includes the shared JSON outside the frontend root. The Vercel source-inclusion checkbox still lacks direct readback because project API inspection returned 403. Record that setting when access is available.

### Received-mail verification — pending


Before declaring completion, record the real outside-account test results. Resend domain/record verification is complete; received-message authentication remains pending. Group settings, administrative routing and Workspace DKIM activation have been inspected; message headers remain the decisive authentication test. The private guide contains the full external test script including internal-only account addresses.

For public mail, Neil sends a separate message from an outside account to each role. Confirm receipt, expected label, retained Inbox, correct reply From and role Reply-To. Neil sends the replies to his outside account himself; inspect only these test messages. Check the received replies' original headers for SPF, DKIM and DMARC pass and alignment. An incoming outside-account message verifies the outside sender's authentication, not EarningsNerd's outgoing authentication. A Gmail Sent copy also does not establish the destination server's authentication result. Obtain the received reply headers from the outside account.

Separately test a permitted Resend message to Neil and inspect its received original headers; Workspace reply headers do not prove Resend authentication. Any new product Reply-To/notification code remains unverified in production until Neil later approves its release. Never merge or deploy as part of this setup task.

## Adding a teammate and undoing changes

For a future public-role teammate, first give the person their own approved mailbox/account. Export the current alias and Gmail setup. In a planned window, remove only the selected role alias from Neil and create a private Group with the identical address; add Neil and the teammate as recipients with each-email delivery. Enable external posting, keep membership/history private, configure each person's verified send-as identity and role Reply-To, and retest from outside. This migration preserves the published address; creation failure can be reversed by restoring the alias. Do not provision a paid user without a separate founder instruction.

| Task-created change | Undo procedure |
| --- | --- |
| Public/DMARC aliases | Remove only aliases created by this task after replacing public routing or reverting the public references. Alias removal stops delivery but does not erase Neil's existing mail. |
| Reserved Groups | If this task created a Group, remove Neil's newly added membership to stop forwarding first. Keep the Group and its mail until Neil explicitly approves any irreversible deletion. If it existed beforehand, restore only task-added memberships/settings; do not delete it. |
| New recipient filters | Delete only the filters recorded as created by this task. This stops future actions; it does not move, unlabel or mark historical mail. |
| `EarningsNerd/…` labels | Leave labels and mail intact by default. Remove only empty task-created labels; get explicit approval before removing a label from stored messages or deleting related history. |
| Send-as identities | Remove only identities created for this task; restore **Always reply from default address (currently neil@earningsnerd.io)**. Keep Neil's original default identity, signature and existing identities. |
| Founder signature/templates | Restore **No signature** for the role new-message/reply defaults; keep Neil's personal **No signature** baseline. Leave the task-created signature available unless its removal is approved. Preserve existing templates. Template deletion is irreversible in Gmail, so obtain Neil's approval before deleting any saved template. If reverting the task-enabled Templates feature, first retain the three template texts and restore its recorded prior disabled setting. |
| DMARC replacement | Requires fresh DNS approval. Restore the previous approved valid policy if available. The two observed duplicate records are a broken baseline; do not silently recreate them as rollback. |
| Added Resend root domain / approved CNAME | The current application From default is unchanged, so retain the existing inbound sender for rollback. Revert any later runtime From override to its recorded previous value before disabling the new root sending domain. Remove the task-created Resend domain only with explicit approval if deletion is irreversible; preserve the older domain and all existing DNS. Removing an applied rsend CNAME requires fresh DNS approval. |
| Cloud Run/job env overrides | With Neil's release approval, restore each recorded previous value or remove only newly introduced overrides. Do not guess previous values or expose secrets. |
| Product code and security.txt | Close the unmerged PR or revert its branch changes. If released later, use a reviewed revert PR; do not merge/deploy it automatically. Renew security.txt expiry if retaining the feature. |
| Alias-to-Group teammate migration | Restore the recorded alias and send-as configuration if needed; do not delete a Group archive without approval. Retest externally after changing routing. |

The draft PR remains unmerged and product production is unchanged. Neil's super admin access, aliases/Groups, all 11 recipient filters, four public send-as identities, founder signature/all role defaults, three templates and the approved DMARC replacement are confirmed. Group advanced settings, routing and Workspace DKIM activation are also inspected and preserved. The added Resend root domain and all four authentication records are fully verified, with its exact CNAME approved and applied. The visitor/auth preview is verified in light/dark themes, with 55 recorded mailto targets and security.txt browser content checked. Authenticated settings, the cookie dialog, deployed response headers and Neil's real outside-account authentication tests retain the limits recorded above.
