# PR: Add Resend webhook support and troubleshooting documentation

## Summary
- Add Resend webhook endpoint for email event tracking
- Add comprehensive troubleshooting guides for contact form and deployment
- Configure webhook signing secret support

## Changes

### New Features
- **Webhook Endpoint** (`backend/app/routers/webhooks.py`):
  - POST /api/webhooks/resend endpoint with HMAC signature verification
  - Event handlers for: email.sent, email.delivered, email.bounced, email.complained, email.opened, email.clicked
  - Updates contact submission status based on email events
  - Logs delivery failures and bounce reasons

### Configuration
- **Backend Config** (`backend/app/config.py`):
  - Added RESEND_WEBHOOK_SECRET configuration parameter

- **Router Registration** (`backend/main.py`):
  - Registered webhook router in FastAPI app
  - Added webhooks to __init__.py exports

### Documentation
- **CONTACT_FORM_TROUBLESHOOTING.md**:
  - Step-by-step guide to diagnose and fix contact form email issues
  - Resend API key configuration instructions
  - Domain verification guide
  - Testing and verification steps

- **RESEND_WEBHOOKS_SETUP.md**:
  - Complete webhook setup guide
  - Resend dashboard configuration steps
  - Signature verification explanation
  - Testing procedures

- **CONTACT_FORM_DEPLOYMENT_FIX.md**:
  - Deployment verification checklist
  - Common deployment issues and solutions
  - Timeline expectations

## Why This PR?

This PR addresses the contact form email delivery issues by:
1. Adding webhook support to track email delivery status
2. Providing comprehensive troubleshooting documentation
3. Enabling automatic status updates for contact submissions

The webhook endpoint will resolve the 404 errors currently showing in the Resend dashboard.

## Files Changed
- ✅ `backend/app/routers/webhooks.py` (new)
- ✅ `backend/app/config.py` (modified)
- ✅ `backend/app/routers/__init__.py` (modified)
- ✅ `backend/main.py` (modified)
- ✅ `CONTACT_FORM_TROUBLESHOOTING.md` (new)
- ✅ `RESEND_WEBHOOKS_SETUP.md` (new)
- ✅ `CONTACT_FORM_DEPLOYMENT_FIX.md` (new)

## Testing Plan
- [ ] Verify webhook endpoint responds correctly to Resend events
- [ ] Test HMAC signature verification
- [ ] Confirm contact submission status updates on email events
- [ ] Validate all event types (sent, delivered, bounced, etc.)

## Deployment Notes

After merging, you'll need to:
1. Add `RESEND_WEBHOOK_SECRET` to Vercel environment variables
2. Configure webhook in Resend dashboard: `https://www.earningsnerd.io/api/webhooks/resend`
3. Test webhook with a contact form submission

See `RESEND_WEBHOOKS_SETUP.md` for detailed instructions.

## Related Issues
- Fixes contact form email delivery tracking
- Resolves Resend webhook 404 errors
- Related to PR #46 (contact form implementation)
