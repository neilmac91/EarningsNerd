# Resend Webhooks Setup Guide

This guide will help you set up webhooks for Resend to track email delivery, opens, clicks, bounces, and spam complaints.

## What Are Webhooks?

Webhooks allow Resend to notify your application in real-time when email events occur (delivery, bounces, opens, clicks, etc.). This helps you:

- Track email delivery status
- Identify bounced or invalid email addresses
- Monitor spam complaints
- Measure engagement (opens and clicks)
- Debug email delivery issues

## Production activation checklist (F46)

Founder-run: engineering prepared these steps from the code and Resend's documentation (read
2026-10-28), and nothing here is done until the **Record** at the end is filled in. Never paste the
signing secret into the repository, a log, a chat or a pull request: every command below prints names
and metadata only. The backend side is in place: `POST /api/webhooks/resend` verifies Svix signatures
(`backend/app/routers/webhooks.py`, gated by `backend/tests/unit/test_resend_webhook_signature.py` and
`test_resend_webhook_handlers.py`). Only the API service receives these webhooks; the task worker
(`earningsnerd-task-worker`, F60) needs no binding.

1. **Read what the service binds, by name.** From a terminal signed in to `gcloud`:

   ```bash
   gcloud run services describe earningsnerd-backend --region=us-west1 --project=earnings-nerd \
     --format='value(spec.template.spec.containers[0].env[].name)'
   gcloud secrets versions list RESEND_WEBHOOK_SECRET --project=earnings-nerd --format='table(name,state,createTime)'
   ```

   The first lists environment names only, the second the secret's versions and their states only. If
   `RESEND_WEBHOOK_SECRET` is in the first list and has an enabled version, step 3 is a check that the
   stored value is this webhook's current secret (add a version if you are unsure); otherwise do step 3
   in full.
2. **Create or open the webhook in Resend.** On the Webhooks page (`https://resend.com/webhooks`), open
   the webhook for `https://api.earningsnerd.io/api/webhooks/resend` if one exists, or choose **Add
   Webhook** and enter that URL. Two webhooks for one URL deliver every event twice. Select the nine
   events the backend handles: `email.sent`, `email.delivered`, `email.delivery_delayed`,
   `email.bounced`, `email.complained`, `email.failed`, `email.suppressed`, `email.opened`,
   `email.clicked`. All but the last two also update the invitation delivery record and the
   suppression list once a delivery's signature verifies ([LEGAL_READINESS.md](../LEGAL_READINESS.md#invitation-email));
   a delivery whose write fails is answered 503, so Resend sends it again, and applying one twice
   changes nothing (retries keep their `svix-id`). Resend offers two more (`email.received`,
   `email.scheduled`); the backend answers them 200 and logs "Unhandled Resend webhook event type", so
   leave them off unless you want those log lines.
3. **Store and bind the signing secret.** Resend shows it on the webhook details page. Either paste it
   into a new secret or a new version in the Secret Manager console, or use a terminal command that
   neither echoes it nor writes it to your shell history:

   ```bash
   read -rs RESEND_SECRET   # paste the whole value, which starts with whsec_, then press Return
   printf '%s' "$RESEND_SECRET" | gcloud secrets create RESEND_WEBHOOK_SECRET --project=earnings-nerd --data-file=-
   # When the secret already exists, add a version instead:
   #   printf '%s' "$RESEND_SECRET" | gcloud secrets versions add RESEND_WEBHOOK_SECRET --project=earnings-nerd --data-file=-
   unset RESEND_SECRET
   gcloud run services update earningsnerd-backend --region=us-west1 --project=earnings-nerd \
     --update-secrets=RESEND_WEBHOOK_SECRET=RESEND_WEBHOOK_SECRET:latest
   ```

   The update makes a new revision of the API service. CI's deploys merge secrets
   (`--update-secrets`), so the binding survives later deploys. Run step 1 again: the name is listed.
4. **Prove one delivery.** Resend's documentation describes testing a webhook by performing an event it
   tracks, not by a test button. Send one email to an inbox you own, for example a password reset
   for your own account on the site. In Resend, open the webhook and that email's message: the
   delivery should show a 200 response (Resend retries a failure, and a message can be sent again with
   **Replay**). Then read the service log:

   ```bash
   gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="earningsnerd-backend" AND ("Resend webhook" OR "RESEND_WEBHOOK_SECRET" OR "Email sent" OR "Email delivered")' \
     --project=earnings-nerd --limit=20 --format='value(timestamp,textPayload,jsonPayload.message)'
   ```

   Expected: `Received Resend webhook: email.sent`, then `Email sent: re_… to f***@example.com - Subject: …`
   (the recipient masked), and likewise for `email.delivered`. A refusal logs one of
   `RESEND_WEBHOOK_SECRET is not set in production`, `RESEND_WEBHOOK_SECRET is not a Svix signing secret
   (whsec_ and base64)`, `Invalid Resend webhook signature` (a wrong secret, such as another webhook's)
   or `Resend webhook timestamp is more than five minutes from the server clock`, and Resend shows 401.
   An unsigned request is refused with 400 (`Missing webhook signature`); the unit tests above cover the
   unsigned, wrongly signed and stale cases, so no production probe is needed.
5. **Optional: click attribution (E11c).** Resend reports clicks only while tracking is on for the
   sending domain: **Domains**, the domain, **Configuration**, **Enable tracking metrics**, with click
   tracking enabled and its tracking subdomain verified (Resend's tracking page, read 2026-10-28). A click counts only on a filing alert sent to an account (one
   `earningsnerd_delivery_batches` row); transactional mail, such as the reset in step 4, resolves to
   nothing. With an alert delivered to an inbox you own, follow one of its links: PostHog records one
   `alert_email_clicked` event for your user id (`kind`, `batch_id`, `hours_to_first_click`,
   `link_path`). Follow a link again: no second event, because only a batch's first click is stamped
   (`docs/OPERATIONS.md`, "Alert-to-return measurement"). A 200 for a click event alone does not show
   attribution. If no alert reaches an inbox you own, record this step as Unverified.

**Record** (fill in when done; Unverified until then):

| Item | Value |
| --- | --- |
| Endpoint URL in Resend | Unverified |
| Events selected | Unverified |
| `RESEND_WEBHOOK_SECRET` version bound (its number, never its value) | Unverified |
| API service revision serving after the bind | Unverified |
| Step 4 delivery: event, response, time (UTC) | Unverified |
| Step 5 click attribution | Unverified |

## Backend Setup (Already Complete)

The following has been implemented in your backend:

✅ Webhook endpoint: `POST /api/webhooks/resend`
✅ Signature verification for security
✅ Handlers for the nine events listed in Step 2 of the activation checklist
✅ Delivery feedback recorded in the invitation ledger and suppression list
✅ Logging for monitoring
✅ Configuration for webhook secret

## Step 1: Get Your Webhook URL

Your webhook endpoint will be:

**Production**: `https://api.earningsnerd.io/api/webhooks/resend`
**Development**: `http://localhost:8000/api/webhooks/resend`

## Step 2: Configure Resend Dashboard

### 2.1 Log in to Resend

1. Go to [https://resend.com/login](https://resend.com/login)
2. Log in with your account

### 2.2 Navigate to Webhooks

1. In the left sidebar, click on **"Webhooks"**
2. Click **"Create Webhook"** or **"Add Webhook"**

### 2.3 Configure the Webhook

Fill in the following details:

**Endpoint URL**:
```
https://api.earningsnerd.io/api/webhooks/resend
```

**Events to Subscribe**: Select the events you want to track:

- ✅ `email.sent` - Email was accepted by Resend
- ✅ `email.delivered` - Email was delivered to the recipient's mail server
- ✅ `email.delivery_delayed` - Delivery was delayed
- ✅ `email.bounced` - Email bounced (`data.bounce.type`: Permanent or Temporary)
- ✅ `email.complained` - Recipient marked as spam
- ✅ `email.failed` - Resend failed the email after accepting it (`data.failed.reason`)
- ✅ `email.suppressed` - Resend suppressed the address and did not send
- ✅ `email.opened` - Recipient opened the email (requires tracking)
- ✅ `email.clicked` - Recipient clicked a link (requires tracking)

These are the nine events the backend handles, as Step 2 of the activation checklist above lists them;
it says why to leave Resend's other two (`email.received`, `email.scheduled`) off. The first seven also
move the invitation delivery record and can suppress the address once a delivery's signature verifies.

### 2.4 Save and Get Signing Secret

1. Save the webhook.
2. Resend shows its **signing secret** on the webhook details page: `whsec_` followed by base64 text.
   Copy it whole; never paste it anywhere but Secret Manager or your local `.env`.

## Step 3: Add Webhook Secret to Environment Variables

### For Production (Cloud Run)

The backend runs on Cloud Run and reads its secrets from Secret Manager (`docs/DEPLOYMENT.md` §4–§6).
The runtime service account already holds `secretmanager.secretAccessor`, and the CI deploy merges
secrets (`--update-secrets`), so a secret bound once survives later deploys:

Use the activation checklist's step 3 above: it reads the secret without echoing it or writing it to
your shell history, then binds it with `gcloud run services update ... --update-secrets=...`.

While the secret is unset, production refuses every webhook with 401 and logs
"RESEND_WEBHOOK_SECRET is not set in production".

### For Development (Local)

1. Open `backend/.env` in your checkout
2. Add the following line:
   ```bash
   RESEND_WEBHOOK_SECRET=whsec_your_actual_secret_here
   ```
3. Restart your backend server

### For Testing Locally (Optional)

If you want to test webhooks locally, you'll need to expose your local server:

**Option 1: Using ngrok**
```bash
# Install ngrok: https://ngrok.com/download
ngrok http 8000
```
Then use the ngrok URL (e.g., `https://abc123.ngrok.io/api/webhooks/resend`) in Resend dashboard.

**Option 2: Using Resend CLI (Recommended)**
```bash
# Install Resend CLI
npm install -g resend

# Forward webhooks to local server
resend webhooks forward http://localhost:8000/api/webhooks/resend
```

## Step 4: Test the Webhook

### Test Method 1: Send a Real Email

Resend's documentation tests a webhook by performing an event it tracks. Send one email to an inbox
you own through the running app (a password reset for your own account, for example); production uses
the activation checklist's step 4.

### Test Method 2: Replay From the Resend Dashboard

In Resend, open **Webhooks**, choose your webhook, open a message and choose **Replay**: Resend sends
that event again, failed or not.

### Verify Webhook Receipt

Check your backend logs for webhook events:

```text
# You should see logs like (the recipient is masked):
[INFO] Received Resend webhook: email.sent
[INFO] Email sent: re_abc123... to t***@example.com - Subject: We received your message
```

## Step 5: Monitor Webhooks

### View Webhook Logs in Resend

1. Go to **Webhooks** in Resend dashboard
2. Click on your webhook
3. View **Recent Deliveries** to see:
   - Request payload
   - Response status
   - Timestamp
   - Retry attempts (if any failed)

### View Logs in Your Application

Check your backend logs:

```bash
# Development: the terminal running `uvicorn`

# Production (Cloud Run)
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="earningsnerd-backend" AND ("Resend webhook" OR "RESEND_WEBHOOK_SECRET")' --limit=20
```

## Webhook Events Reference

### email.sent
Triggered when Resend accepts the email for delivery.

**Payload**:
```json
{
  "type": "email.sent",
  "data": {
    "email_id": "re_...",
    "to": "user@example.com",
    "from": "hello@inbound.earningsnerd.io",
    "subject": "We received your message",
    "created_at": "2024-01-21T10:00:00.000Z"
  }
}
```

### email.delivered
Triggered when the email is successfully delivered to the recipient's mail server.

**Payload**:
```json
{
  "type": "email.delivered",
  "data": {
    "email_id": "re_...",
    "to": "user@example.com"
  }
}
```

### email.bounced
Triggered when an email bounces.

**Payload**:
```json
{
  "type": "email.bounced",
  "data": {
    "email_id": "re_...",
    "to": ["user@example.com"],
    "bounce": {"type": "Permanent", "subType": "General", "message": "..."}
  }
}
```

**Bounce Types** (`data.bounce.type`; the handler reads this, never a top-level `bounce_type`):
- **Permanent**: the address cannot receive mail; it suppresses the address for invitation email
- **Temporary**: a transient failure (mailbox full, server down); it records the bounce and suppresses nothing

### email.complained
Triggered when a recipient marks your email as spam.

**Important**: Take action to prevent future complaints:
- Consider unsubscribing the user
- Review email content
- Verify sender domain reputation

## How Signature Verification Works

Resend uses the **Svix webhook standard** for signature verification. Understanding this helps with debugging and security.

### Svix Headers

Every webhook request includes three critical headers:

1. **`svix-id`**: Unique identifier for the webhook message
2. **`svix-timestamp`**: Unix timestamp of when the webhook was sent
3. **`svix-signature`**: HMAC signature(s) for verification

### Signature Construction

The signature is an HMAC-SHA256 over a concatenated string:

```
signed_content = svix-id + "." + svix-timestamp + "." + request_body
```

The HMAC key is not the secret's text: it is the base64-decoded part after the `whsec_` prefix. The
digest is sent base64-encoded, with its version: `v1,<base64 digest>`. The backend
(`verify_webhook_signature` in `backend/app/routers/webhooks.py`) follows Svix's manual verification
page (https://docs.svix.com/receiving/verifying-payloads/how-manual), and
`backend/tests/unit/test_resend_webhook_signature.py` checks it against that page's example. Resend's
own page (https://resend.com/docs/webhooks/verify-webhooks-requests) names the same three headers,
shows a signature in the same `v1,<base64>` form and points to Svix's libraries.

Example:
```
svix-id: msg_abc123
svix-timestamp: 1674321000
request body: {"type":"email.sent","data":{...}}

Signed content: "msg_abc123.1674321000.{"type":"email.sent","data":{...}}"
```

### Timestamp Window

A delivery whose `svix-timestamp` is more than five minutes from the server's clock is refused, as
Svix's own libraries refuse it, so a captured delivery cannot be replayed after that. Within the window
a repeat is accepted, as Svix's libraries accept it: the invitation delivery record moves only up its
evidence order and keeps the last event's `svix-id`, so a repeat changes nothing; a suppression is set once;
the other handlers only log, and the click handler stamps a batch's first click once. A retry carries
its own attempt's timestamp and a signature over it ("Every time an attempt is retried the timestamp
of the attempt is updated", in the Standard Webhooks specification Svix follows), so retries pass.

### Multiple Signatures

The `svix-signature` header can contain multiple signatures (for key rotation):

```
svix-signature: v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE= v1,bm9ldHUjKzFob2VudXRob2VodWUzMjRvdWVvdW9ldQo=
```

Format: `version,signature version,signature` (space-separated)

The verification function checks all signatures and succeeds if **any** match.

## Security Best Practices

### 1. Always Verify Signatures

The webhook endpoint automatically verifies signatures using `RESEND_WEBHOOK_SECRET` and the Svix standard. Never disable this in production.

### 2. Use HTTPS in Production

Webhooks should always use HTTPS (`https://api.earningsnerd.io`) to prevent man-in-the-middle attacks.

### 3. Validate Payload Data

The endpoint validates all incoming data before processing.

### 4. Rate Limiting

Consider implementing rate limiting on webhook endpoints to prevent abuse.

### 5. Idempotency

Handle duplicate webhook events gracefully (Resend may retry failed deliveries).

## Troubleshooting

### Webhook Not Receiving Events

1. **Check Webhook URL**: Ensure it matches exactly
2. **Check HTTPS**: Production must use HTTPS
3. **Check Firewall**: Ensure your server accepts requests from Resend IPs
4. **Check Logs**: Look for errors in backend logs

### Signature Verification Failing

1. **Check Secret**: Ensure `RESEND_WEBHOOK_SECRET` matches the signing secret on the webhook's page in the Resend dashboard
2. **Check Format**: The secret is `whsec_` followed by base64, pasted whole. If what follows the prefix is empty or not base64 (a doubled `whsec_whsec_` is one case), the log says "RESEND_WEBHOOK_SECRET is not a Svix signing secret". A well-formed but wrong key, such as another webhook's secret, logs only "Invalid Resend webhook signature" on each delivery
3. **Check the Clock**: A delivery more than five minutes from the server's clock logs "Resend webhook timestamp is more than five minutes from the server clock" and is refused
4. **Check the Binding**: After creating the secret, bind it to the service (`--update-secrets`, above); the new revision reads it

### Events Not Being Processed

1. **Check Event Type**: Ensure you subscribed to the event in Resend
2. **Check Handler**: Verify event handler function exists
3. **Check Logs**: Look for errors in event processing

## Next Steps

### Email Tracking (Optional)

To enable open and click tracking:

1. In Resend API calls, add tracking parameters:
```python
await send_email(
    to=[email],
    subject=subject,
    html=html,
    tags=[{"name": "category", "value": "contact"}],  # For filtering
)
```

2. Enable tracking in the Resend dashboard, per domain: **Domains**, the domain, **Configuration**,
   **Enable tracking metrics**; turn on open and click tracking and verify the tracking subdomain.

## Support

If you encounter issues:

1. Check Resend documentation: https://resend.com/docs/webhooks
2. Check backend logs for errors
3. Verify webhook signature and URL
4. Contact Resend support: support@resend.com

## Summary Checklist

Production activation is the founder-run checklist at the top of this guide, and its **Record** table
is the evidence: a webhook is not active until that table is filled in.
