# Contact Form & Webhook Deployment Fix Plan

## Current Issue
The contact form at https://www.earningsnerd.io/contact is not sending emails because the backend API endpoints have not been deployed to production yet.

**Status**: Changes are on PR branch `claude/fix-footer-links-vwOPV` but NOT merged to `main`

## Root Cause
1. Contact form endpoint (`/api/contact/`) only exists on PR branch
2. Webhook endpoint (`/api/webhooks/resend`) only exists on PR branch
3. Production API returns 404 for these endpoints
4. Emails cannot be sent without the backend

## Step-by-Step Fix

### Step 1: Merge PR #46
1. Go to https://github.com/neilmac91/EarningsNerd/pull/46
2. Review the final changes (security fixes are already applied)
3. Click **"Merge pull request"**
4. Click **"Confirm merge"**
5. Optionally: Delete the branch `claude/fix-footer-links-vwOPV`

**Expected Result**: Changes merged to `main` branch

### Step 2: Verify Vercel Deployment
1. Go to your Vercel dashboard: https://vercel.com/dashboard
2. Wait for automatic deployment to complete (triggered by merge)
3. Check deployment status - should show "Ready" with green checkmark
4. Verify deployed URL: https://www.earningsnerd.io

**Expected Result**:
- Frontend deployment successful
- Backend deployment successful (if using Vercel for backend)

### Step 3: Add Environment Variables (CRITICAL)

#### If Backend is on Vercel:
1. Go to Vercel project settings
2. Navigate to **Settings** → **Environment Variables**
3. Add the following variable:
   - **Name**: `RESEND_WEBHOOK_SECRET`
   - **Value**: (Copy from Resend dashboard - the obscured value in your screenshot)
   - **Environment**: Production (and Preview if needed)
4. Click **Save**
5. **IMPORTANT**: Redeploy the application:
   - Go to **Deployments**
   - Click on latest deployment
   - Click **"Redeploy"**

#### If Backend is on another platform (Railway, Render, etc.):
1. Go to your backend hosting platform
2. Add environment variable: `RESEND_WEBHOOK_SECRET=whsec_...`
3. Redeploy the backend

**Expected Result**: Backend can verify webhook signatures

### Step 4: Verify Backend Endpoints

Test that endpoints are live:

```bash
# Test health endpoint
curl https://api.earningsnerd.io/health

# Should return: {"status":"healthy"}

# Test webhook endpoint (should return 400 without proper signature)
curl -X POST https://api.earningsnerd.io/api/webhooks/resend \
  -H "Content-Type: application/json" \
  -d '{}'

# Should return 400 (not 404!)
```

**Expected Result**:
- Health endpoint returns 200
- Webhook endpoint returns 400 (not 404)
- Contact endpoint accessible

### Step 5: Test Contact Form

1. Go to https://www.earningsnerd.io/contact
2. Fill out the form:
   - **Name**: Your name
   - **Email**: Your email address
   - **Subject**: Test submission
   - **Message**: Testing contact form after deployment
3. Click **"Send Message"**
4. Look for success message

**Expected Result**:
- Form submits successfully
- Success message appears
- You receive confirmation email within 1-2 minutes

### Step 6: Verify Webhook Events

1. Go to Resend dashboard: https://resend.com/webhooks
2. Click on your webhook
3. Check **"Recent Deliveries"** section
4. Look for new events (email.sent, email.delivered)
5. Verify HTTP status is **200 OK** (not 404)

**Expected Result**:
- Webhook events show 200 OK
- Events are being received successfully

### Step 7: Check Backend Logs

#### For Vercel:
1. Go to Vercel dashboard → Your project
2. Click **"Deployments"** → Latest deployment
3. Click **"Logs"** tab
4. Look for contact form submission logs
5. Should see:
   ```
   [INFO] Contact submission created: ID=1, email=your@email.com
   [INFO] Admin notification email sent for submission #1
   [INFO] User confirmation email sent to your@email.com
   ```

#### For other platforms:
Check your platform's logging dashboard

**Expected Result**: Logs show successful email sending

## Troubleshooting

### Issue: Still Getting 404
**Solution**:
- Verify merge completed
- Check deployment finished
- Clear browser cache
- Try incognito window

### Issue: Webhook Still Failing
**Solution**:
- Verify `RESEND_WEBHOOK_SECRET` is set in environment variables
- Ensure you redeployed after adding the variable
- Check webhook URL matches: `https://api.earningsnerd.io/api/webhooks/resend`

### Issue: Emails Not Sending
**Solution**:
- Check Resend API key is set: `RESEND_API_KEY`
- Verify `RESEND_FROM_EMAIL` is configured
- Check backend logs for errors
- Verify Resend dashboard shows sent emails

### Issue: Contact Form Shows Error
**Solution**:
- Open browser console (F12) and check for errors
- Check Network tab for failed API requests
- Verify frontend is calling correct API URL

## Verification Checklist

After completing all steps:

- [ ] PR #46 merged to main
- [ ] Vercel deployment shows "Ready"
- [ ] `RESEND_WEBHOOK_SECRET` added to environment variables
- [ ] Backend redeployed after adding env var
- [ ] Health endpoint returns 200 OK
- [ ] Webhook endpoint returns 400 (not 404)
- [ ] Contact form submits successfully
- [ ] Confirmation email received
- [ ] Webhook events show 200 OK in Resend
- [ ] Backend logs show successful email sending

## Expected Timeline

- **Merge to deployment**: 2-5 minutes (automatic)
- **Add env vars**: 2 minutes
- **Redeploy**: 2-5 minutes
- **Test form**: 1 minute
- **Receive email**: 1-2 minutes

**Total**: ~10-15 minutes

## Next Steps After Fix

Once everything is working:

1. **Monitor Resend Dashboard**: Check email delivery rates
2. **Review Contact Submissions**: Check database for stored messages
3. **Set Up Alerts**: Configure notifications for bounces/spam complaints
4. **Update Documentation**: Note the working contact process

## Support

If issues persist after following this plan:

1. **Check Resend Status**: https://status.resend.com
2. **Review Backend Logs**: Look for specific error messages
3. **Test Locally**: Run backend locally and test contact form
4. **Contact Resend Support**: support@resend.com (if email issues)

## Summary

The contact form will work once:
1. ✅ PR is merged
2. ✅ Changes deployed to production
3. ✅ Environment variables configured
4. ✅ Backend redeployed with new env vars

This is a **deployment issue**, not a code issue. All code is working correctly on the PR branch.
