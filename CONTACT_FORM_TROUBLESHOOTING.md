# Contact Form Email Troubleshooting Guide

## Issue
Contact form submissions succeed but emails are not being sent.

## Root Cause
The Resend email service is not properly configured in the production environment (Vercel).

## Required Configuration

### 1. RESEND_API_KEY (CRITICAL)
**Status**: ❌ Likely missing or invalid

**How to get it:**
1. Log in to https://resend.com/
2. Go to **API Keys** in the dashboard
3. Copy your API key (starts with `re_`)

**How to add to Vercel:**
```bash
# Via Vercel CLI (if installed)
vercel env add RESEND_API_KEY

# Or via Vercel Dashboard:
# 1. Go to https://vercel.com/dashboard
# 2. Select your project
# 3. Go to Settings > Environment Variables
# 4. Add: RESEND_API_KEY = re_xxxxxxxxxxxxx
# 5. Select: Production, Preview, Development
# 6. Click Save
# 7. IMPORTANT: Redeploy for changes to take effect
```

### 2. RESEND_FROM_EMAIL (CRITICAL)
**Current default**: `EarningsNerd <onboarding@resend.dev>` ❌ Won't work

**Issue**: You cannot send from `onboarding@resend.dev` without domain verification.

**Solution - Option A: Use Resend's Testing Domain (Quick)**
```bash
RESEND_FROM_EMAIL="EarningsNerd <onboarding@resend.dev>"
```
This works for testing but emails may go to spam and have Resend branding.

**Solution - Option B: Verify Your Domain (Recommended)**
1. In Resend dashboard, go to **Domains**
2. Click **Add Domain**
3. Enter your domain: `earningsnerd.io`
4. Add the DNS records shown (DKIM, SPF, DMARC)
5. Wait for verification (usually 5-15 minutes)
6. Once verified, update in Vercel:
```bash
RESEND_FROM_EMAIL="EarningsNerd <hello@earningsnerd.io>"
```

### 3. RESEND_BASE_URL (Should be set)
**Default**: `https://api.resend.com`
**Action**: No change needed unless using a different endpoint

### 4. FRONTEND_URL (Should be set)
**Expected**: `https://www.earningsnerd.io` or `https://earningsnerd.io`
**Purpose**: Used in email templates for links

## Verification Steps

### Step 1: Check Current Vercel Environment Variables
1. Go to https://vercel.com/dashboard
2. Select your EarningsNerd project
3. Go to **Settings** > **Environment Variables**
4. Verify these exist:
   - ✅ RESEND_API_KEY (should start with `re_`)
   - ✅ RESEND_FROM_EMAIL (should use verified domain)
   - ✅ FRONTEND_URL (should be your production URL)

### Step 2: Check Backend Logs
1. Go to your Vercel project
2. Click on **Deployments**
3. Click on the latest production deployment
4. Click **View Function Logs** or **Runtime Logs**
5. Look for errors containing:
   - `"Resend is not configured"`
   - `"ResendError"`
   - `"Failed to send contact notification emails"`

### Step 3: Test the API Endpoint Directly
```bash
# Test the contact endpoint
curl -X POST https://www.earningsnerd.io/api/contact/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "email": "your-email@example.com",
    "subject": "Test",
    "message": "Testing contact form"
  }'
```

Expected response if working:
```json
{
  "id": 1,
  "name": "Test User",
  "email": "your-email@example.com",
  "subject": "Test",
  "message": "Testing contact form",
  "status": "new",
  "created_at": "2026-01-21T..."
}
```

### Step 4: Check Resend Dashboard
1. Log in to https://resend.com/
2. Go to **Logs** or **Emails**
3. Check if any email attempts appear
4. Look for errors or delivery status

## Quick Fix Checklist

- [ ] Add RESEND_API_KEY to Vercel environment variables
- [ ] Update RESEND_FROM_EMAIL to use verified domain (or use onboarding@resend.dev for testing)
- [ ] Verify FRONTEND_URL is set correctly
- [ ] Redeploy the application in Vercel
- [ ] Test contact form submission
- [ ] Check Resend logs for email delivery
- [ ] Check your inbox for test email

## After Configuration

Once you've updated the environment variables:

1. **Trigger a new deployment:**
   - Go to Vercel dashboard
   - Click **Deployments**
   - Click the three dots on the latest deployment
   - Click **Redeploy**
   - Wait for deployment to complete

2. **Test the contact form:**
   - Go to https://www.earningsnerd.io/contact
   - Fill out the form with your email
   - Submit
   - Check your email inbox (and spam folder)

## Expected Behavior After Fix

When someone submits the contact form:
1. ✅ Form submission saved to database
2. ✅ Admin receives email notification at configured RESEND_FROM_EMAIL address
3. ✅ User receives confirmation email
4. ✅ Both emails appear in Resend dashboard logs

## Additional: Webhook Setup (Optional)

The webhook endpoint is NOT yet merged to main (it's only on the branch). To enable email event tracking:

1. Merge the webhook implementation (webhooks.py)
2. Add RESEND_WEBHOOK_SECRET to Vercel
3. Configure webhook in Resend dashboard: `https://www.earningsnerd.io/api/webhooks/resend`

See RESEND_WEBHOOKS_SETUP.md for detailed webhook configuration instructions.

## Need Help?

If emails still aren't working after following these steps:
1. Share the Vercel runtime logs
2. Share the Resend dashboard screenshot showing any errors
3. Confirm which environment variables are set in Vercel
