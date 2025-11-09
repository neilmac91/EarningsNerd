# Deployment Checklist

This checklist covers critical configuration and verification steps after the code review fixes.

## ✅ Code Review Fixes Applied

### 1. XBRL Fallback Parser Fix
- **Status**: ✅ Fixed
- **Changes**: Fixed bug where all GAAP tags were incorrectly mapped to revenue bucket
- **Impact**: Net income, liabilities, cash, and other metrics now correctly extracted from XBRL XML fallback
- **Verification**: Run `backend/scripts/verify_xbrl_fallback.py` (if needed, adjust for your test environment)

### 2. Stripe Webhook Security Fix
- **Status**: ✅ Fixed
- **Changes**: Removed dangerous fallback that used API key as webhook secret
- **Impact**: Webhooks now require explicit `STRIPE_WEBHOOK_SECRET` configuration
- **Verification**: Run `backend/scripts/verify_startup_config.py` ✅ Verified

### 3. Summary Generation Authentication
- **Status**: ✅ Fixed
- **Changes**: Both `/generate` and `/generate-stream` endpoints now require authentication
- **Impact**: Prevents unauthenticated API abuse and enforces usage limits
- **Verification**: Test endpoints require valid JWT token

## 🔧 Pre-Deployment Configuration

### Required Environment Variables

#### Backend (.env)
```bash
# Required for AI summaries
OPENAI_API_KEY=your_key_here
OPENAI_BASE_URL=https://openrouter.ai/api/v1

# Required for Stripe subscriptions
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...  # ⚠️ CRITICAL: Must be set!

# Database
DATABASE_URL=postgresql://user:password@host:5432/earningsnerd

# Security
SECRET_KEY=generate-a-random-secret-key-here
```

### Stripe Webhook Setup

1. **Create Webhook Endpoint** in Stripe Dashboard:
   - Go to: Developers → Webhooks → Add endpoint
   - URL: `https://your-domain.com/api/subscriptions/webhook`
   - Events to listen for:
     - `checkout.session.completed`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`

2. **Copy Signing Secret**:
   - After creating webhook, click on it
   - Copy the "Signing secret" (starts with `whsec_`)
   - Set as `STRIPE_WEBHOOK_SECRET` in your environment

3. **Verify Configuration**:
   ```bash
   cd backend
   python3 scripts/verify_startup_config.py
   ```

## 🚀 Deployment Steps

### 1. Pre-Deployment Verification

- [ ] Run configuration validation: `python3 backend/scripts/verify_startup_config.py`
- [ ] Verify all environment variables are set (especially `STRIPE_WEBHOOK_SECRET`)
- [ ] Check that database migrations are up to date
- [ ] Review startup logs for configuration warnings

### 2. Deploy Backend

- [ ] Deploy backend code
- [ ] Set environment variables in production
- [ ] Start application and check startup logs:
  ```
  ✓ OpenAI/OpenRouter configured
  ✓ Stripe configured: API key present
  ✓ Stripe webhook secret configured: subscription events will be processed
  ```
- [ ] Verify health endpoint: `GET /health`
- [ ] Test authentication endpoints

### 3. Deploy Frontend

- [ ] Deploy frontend code
- [ ] Set `NEXT_PUBLIC_API_URL` to production backend URL
- [ ] Verify API connectivity
- [ ] Test summary generation flow

### 4. Post-Deployment Verification

- [ ] Test company search
- [ ] Test filing retrieval
- [ ] Test summary generation (requires auth)
- [ ] Test Stripe checkout flow (if enabled)
- [ ] Verify webhook endpoint receives events:
  - Trigger a test checkout
  - Check Stripe Dashboard → Webhooks → [Your endpoint] → Recent events
  - Verify events are received (not "Failed")

### 5. Monitor Startup Logs

Watch for these startup messages:

**Good:**
```
✓ OpenAI/OpenRouter configured: base_url=https://openrouter.ai/api/v1
✓ Stripe configured: API key present
✓ Stripe webhook secret configured: subscription events will be processed
```

**Warnings (fix before production):**
```
⚠️  STRIPE_WEBHOOK_SECRET is not set. Webhook endpoints will fail signature verification.
```

**Errors (must fix):**
```
✗ OpenAI/OpenRouter configuration is invalid. AI summaries may not work.
✗ Stripe configuration is invalid. Subscription features will be disabled.
```

## 🧪 Testing

### Run Test Suite
```bash
cd backend
venv/bin/pytest tests/ -v
```

### Manual Verification Scripts
```bash
# Configuration validation
python3 backend/scripts/verify_startup_config.py

# XBRL parser (if needed)
python3 backend/scripts/verify_xbrl_fallback.py
```

## 📝 Important Notes

1. **Stripe Webhook Secret**: This is now REQUIRED. Without it, subscription events will fail silently. Always verify webhook events are being received in Stripe Dashboard.

2. **Summary Generation**: Now requires authentication. Ensure your frontend handles auth tokens correctly.

3. **XBRL Fallback**: The parser now correctly extracts all metrics. If you see missing net income data, check that XBRL fallback is working (check logs for "Error fetching XBRL data" messages).

4. **Startup Validation**: The application will warn you at startup about missing configuration. Review these warnings before going live.

## 🆘 Troubleshooting

### Webhook Events Not Processing
- Check `STRIPE_WEBHOOK_SECRET` is set correctly
- Verify webhook URL matches your deployed endpoint
- Check Stripe Dashboard → Webhooks → Recent events for error messages
- Review backend logs for signature verification errors

### Summary Generation Failing
- Verify `OPENAI_API_KEY` is set and valid
- Check usage limits (free tier: 5/month)
- Review authentication token is being sent
- Check backend logs for OpenAI API errors

### XBRL Data Missing
- Check if SEC companyfacts API is accessible
- Verify fallback XML parsing is working (check logs)
- Review `backend/app/services/xbrl_service.py` for parsing errors

