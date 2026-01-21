# Resend Webhooks Setup Guide

This guide will help you set up webhooks for Resend to track email delivery, opens, clicks, bounces, and spam complaints.

## What Are Webhooks?

Webhooks allow Resend to notify your application in real-time when email events occur (delivery, bounces, opens, clicks, etc.). This helps you:

- Track email delivery status
- Identify bounced or invalid email addresses
- Monitor spam complaints
- Measure engagement (opens and clicks)
- Debug email delivery issues

## Backend Setup (Already Complete)

The following has been implemented in your backend:

✅ Webhook endpoint: `POST /api/webhooks/resend`
✅ Signature verification for security
✅ Event handlers for all Resend events
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
- ✅ `email.delivered` - Email was delivered to recipient
- ✅ `email.delivery_delayed` - Delivery was delayed
- ✅ `email.bounced` - Email bounced (hard or soft)
- ✅ `email.complained` - Recipient marked as spam
- ✅ `email.opened` - Recipient opened the email (requires tracking)
- ✅ `email.clicked` - Recipient clicked a link (requires tracking)

**Recommended**: Select all events for comprehensive tracking.

### 2.4 Save and Get Signing Secret

1. Click **"Create"** or **"Save"**
2. Resend will show you a **Signing Secret** (starts with `whsec_`)
3. **IMPORTANT**: Copy this secret immediately - you won't be able to see it again!

Example signing secret format:
```
whsec_1234567890abcdefghijklmnopqrstuvwxyz
```

## Step 3: Add Webhook Secret to Environment Variables

### For Production (Vercel)

1. Go to your Vercel project dashboard
2. Navigate to **Settings** → **Environment Variables**
3. Add a new variable:
   - **Name**: `RESEND_WEBHOOK_SECRET`
   - **Value**: Your webhook signing secret (e.g., `whsec_...`)
   - **Environment**: Select "Production" (and "Preview" if needed)
4. Click **"Save"**
5. **Redeploy** your application for the changes to take effect

### For Development (Local)

1. Open `/home/user/EarningsNerd/backend/.env`
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

### Test Method 1: Send a Test Email

Trigger a contact form submission or send a test email:

```bash
# From your backend directory
curl -X POST http://localhost:8000/api/contact/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "test@example.com",
    "message": "Testing webhooks"
  }'
```

### Test Method 2: Use Resend Dashboard

1. In Resend dashboard, go to **Webhooks**
2. Click on your webhook
3. Click **"Send test event"**
4. Select an event type (e.g., `email.delivered`)
5. Click **"Send"**

### Verify Webhook Receipt

Check your backend logs for webhook events:

```bash
# You should see logs like:
[INFO] Received Resend webhook: email.sent
[INFO] Email sent: re_abc123... to test@example.com
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
# Development
tail -f /var/log/your-app.log

# Production (Vercel)
# View logs in Vercel dashboard under "Deployments" → [Your deployment] → "Logs"
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
    "from": "hello@earningsnerd.com",
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
    "to": "user@example.com",
    "bounce_type": "hard"  // or "soft"
  }
}
```

**Bounce Types**:
- **Hard Bounce**: Permanent failure (invalid email address)
- **Soft Bounce**: Temporary failure (mailbox full, server down)

### email.complained
Triggered when a recipient marks your email as spam.

**Important**: Take action to prevent future complaints:
- Consider unsubscribing the user
- Review email content
- Verify sender domain reputation

## Security Best Practices

### 1. Always Verify Signatures

The webhook endpoint automatically verifies signatures using `RESEND_WEBHOOK_SECRET`. Never disable this in production.

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

1. **Check Secret**: Ensure `RESEND_WEBHOOK_SECRET` matches Resend dashboard
2. **Check Format**: Secret should start with `whsec_`
3. **Redeploy**: After adding secret to Vercel, redeploy the app

### Events Not Being Processed

1. **Check Event Type**: Ensure you subscribed to the event in Resend
2. **Check Handler**: Verify event handler function exists
3. **Check Logs**: Look for errors in event processing

## Next Steps

### Database Integration (Optional)

To track email events in your database:

1. **Create Email Events Table**:
```sql
CREATE TABLE email_events (
    id SERIAL PRIMARY KEY,
    email_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    recipient VARCHAR(255) NOT NULL,
    data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

2. **Update Event Handlers** in `/backend/app/routers/webhooks.py`:
```python
async def handle_email_bounced(data: Dict[str, Any]):
    email_id = data.get("email_id")
    to = data.get("to")
    bounce_type = data.get("bounce_type")

    # Store in database
    db_event = EmailEvent(
        email_id=email_id,
        event_type="bounced",
        recipient=to,
        data=data
    )
    # db.add(db_event)
    # db.commit()

    # Mark contact submission as bounced
    # submission = db.query(ContactSubmission).filter_by(email=to).first()
    # if submission:
    #     submission.status = "bounced"
    #     db.commit()
```

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

2. Enable tracking in Resend dashboard:
   - Go to **Settings** → **Email Tracking**
   - Enable **Open Tracking**
   - Enable **Click Tracking**

## Support

If you encounter issues:

1. Check Resend documentation: https://resend.com/docs/webhooks
2. Check backend logs for errors
3. Verify webhook signature and URL
4. Contact Resend support: support@resend.com

## Summary Checklist

- [ ] Webhook endpoint deployed at `https://api.earningsnerd.io/api/webhooks/resend`
- [ ] Webhook created in Resend dashboard
- [ ] All desired events subscribed
- [ ] Webhook signing secret copied
- [ ] `RESEND_WEBHOOK_SECRET` added to Vercel environment variables
- [ ] Application redeployed
- [ ] Test webhook sent and received
- [ ] Webhook logs showing successful events
- [ ] Email events being processed correctly

Once completed, your Resend webhooks will be fully operational! 🎉
