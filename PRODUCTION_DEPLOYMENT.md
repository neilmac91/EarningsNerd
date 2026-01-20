# Production Deployment Guide

This guide walks through deploying EarningsNerd to production following the deployment checklist.

## ✅ Pre-Deployment Verification Complete

All code review fixes have been applied and verified:
- ✅ XBRL fallback parser fixed
- ✅ Stripe webhook security fixed  
- ✅ Summary generation authentication enforced
- ✅ Configuration validation added
- ✅ Test coverage enhanced

## 📋 Pre-Deployment Checklist

Run the deployment check script:
```bash
cd backend
python3 scripts/deploy_check.py
```

**Expected Output for Production:**
- ✓ All environment variables set
- ✓ Configuration validation passed
- ✓ Database connection successful
- ✓ All dependencies installed

## 🚀 Step-by-Step Deployment

### Step 1: Environment Setup

#### Backend Environment Variables

Create `backend/.env` with the following (or set in your deployment platform):

```bash
# Required for AI summaries (Google AI Studio recommended)
OPENAI_API_KEY=your_google_ai_studio_api_key_here
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/

# Required for Stripe subscriptions (if using)
STRIPE_SECRET_KEY=sk_live_your_live_key_here
STRIPE_PUBLISHABLE_KEY=pk_live_your_live_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here  # CRITICAL!

# Database (PostgreSQL recommended for production)
DATABASE_URL=postgresql://user:password@host:5432/earningsnerd

# Security (MUST change from default!)
SECRET_KEY=generate-a-strong-random-secret-key-here-min-32-chars

# Application Settings
ENVIRONMENT=production
CORS_ORIGINS=https://your-frontend-domain.com
```

#### Frontend Environment Variables

Create `frontend/.env.local`:
```bash
NEXT_PUBLIC_API_URL=https://your-backend-api-domain.com
```

### Step 2: Database Setup

#### Option A: PostgreSQL (Recommended)

```bash
# Create database
createdb earningsnerd

# Or using psql
psql -U postgres
CREATE DATABASE earningsnerd;
```

The application will automatically create tables on first startup via `Base.metadata.create_all()`.

#### Option B: SQLite (Development Only)

SQLite is configured by default but NOT recommended for production.

### Step 3: Install Dependencies

#### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### Frontend
```bash
cd frontend
npm install
```

### Step 4: Verify Configuration

```bash
# Run deployment check
cd backend
python3 scripts/deploy_check.py

# Run startup test
python3 scripts/test_startup.py

# Run configuration validation
python3 scripts/verify_startup_config.py
```

All should pass before proceeding.

### Step 5: Stripe Webhook Setup

1. **Create Webhook Endpoint** in Stripe Dashboard:
   - Navigate to: Developers → Webhooks → Add endpoint
   - Endpoint URL: `https://your-backend-domain.com/api/subscriptions/webhook`
   - Select events:
     - `checkout.session.completed`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`

2. **Copy Signing Secret**:
   - Click on the created webhook
   - Reveal and copy the "Signing secret" (starts with `whsec_`)
   - Add to `STRIPE_WEBHOOK_SECRET` in your environment

3. **Test Webhook**:
   - Use Stripe CLI: `stripe listen --forward-to localhost:8000/api/subscriptions/webhook`
   - Or trigger a test checkout and verify events appear in Stripe Dashboard

### Step 6: Deploy Backend

#### Using uvicorn directly:
```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

#### Using systemd (Linux):
Create `/etc/systemd/system/earningsnerd.service`:
```ini
[Unit]
Description=EarningsNerd API
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/earningsnerd/backend
Environment="PATH=/path/to/earningsnerd/backend/venv/bin"
ExecStart=/path/to/earningsnerd/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable earningsnerd
sudo systemctl start earningsnerd
sudo systemctl status earningsnerd
```

#### Using Docker:
```bash
# Build and run
docker-compose up -d
```

### Step 7: Verify Backend Deployment

1. **Health Check**:
   ```bash
   curl https://your-backend-domain.com/health
   # Should return: {"status":"healthy"}
   ```

2. **Check Startup Logs**:
   Look for these messages:
   ```
   ✓ OpenAI-compatible provider configured: base_url=https://generativelanguage.googleapis.com/v1beta/openai/
   ✓ Stripe configured: API key present
   ✓ Stripe webhook secret configured: subscription events will be processed
   ```

3. **Test Authentication**:
   ```bash
   curl -X POST https://your-backend-domain.com/api/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"testpass123"}'
   ```

### Step 8: Deploy Frontend

#### Build for Production:
```bash
cd frontend
npm run build
```

#### Using Next.js Standalone:
```bash
npm run build
# Output in .next/standalone
```

#### Using Vercel/Netlify:
- Connect your repository
- Set `NEXT_PUBLIC_API_URL` environment variable
- Deploy

#### Using Docker:
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

### Step 9: Post-Deployment Verification

Run through these tests:

1. **Company Search**:
   ```bash
   curl "https://your-backend-domain.com/api/companies/search?q=AAPL"
   ```

2. **Filing Retrieval**:
   ```bash
   curl "https://your-backend-domain.com/api/filings/company/AAPL"
   ```

3. **Summary Generation** (requires auth):
   ```bash
   # First login to get token
   TOKEN=$(curl -X POST https://your-backend-domain.com/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"testpass123"}' \
     | jq -r '.access_token')
   
   # Generate summary
   curl -X POST "https://your-backend-domain.com/api/summaries/filing/1/generate" \
     -H "Authorization: Bearer $TOKEN"
   ```

4. **Stripe Webhook**:
   - Trigger a test checkout
   - Check Stripe Dashboard → Webhooks → Recent events
   - Verify events show "Succeeded" not "Failed"

### Step 10: Monitor Startup Logs

Watch for these startup messages:

**✅ Good (Production Ready):**
```
✓ OpenAI-compatible provider configured: base_url=https://generativelanguage.googleapis.com/v1beta/openai/
✓ Stripe configured: API key present
✓ Stripe webhook secret configured: subscription events will be processed
```

**⚠️ Warnings (Fix Before Production):**
```
⚠️  STRIPE_WEBHOOK_SECRET is not set. Webhook endpoints will fail signature verification.
⚠️  OPENAI_API_KEY is not set
```

**❌ Errors (Must Fix):**
```
✗ OpenAI-compatible configuration is invalid. AI summaries may not work.
✗ Stripe configuration is invalid. Subscription features will be disabled.
```

## 🔒 Security Checklist

- [ ] `SECRET_KEY` changed from default value
- [ ] `STRIPE_WEBHOOK_SECRET` set and verified
- [ ] Database credentials are secure
- [ ] CORS origins restricted to your frontend domain
- [ ] Environment variables not committed to git
- [ ] HTTPS enabled for all endpoints
- [ ] Rate limiting configured (if applicable)

## 📊 Monitoring

### Key Metrics to Monitor

1. **API Health**: `/health` endpoint
2. **Summary Generation**: Success rate, average time
3. **Stripe Webhooks**: Event processing success rate
4. **Database**: Connection pool usage
5. **OpenAI API**: Rate limits, errors

### Log Locations

- Application logs: Check your process manager (systemd, PM2, etc.)
- Error logs: Check for exceptions in startup logs
- Stripe webhook logs: Stripe Dashboard → Webhooks → [Endpoint] → Recent events

## 🆘 Troubleshooting

### Backend Won't Start
1. Check environment variables are set
2. Verify database connection
3. Check port 8000 is available
4. Review startup logs for errors

### Webhooks Not Working
1. Verify `STRIPE_WEBHOOK_SECRET` is set correctly
2. Check webhook URL matches your endpoint
3. Review Stripe Dashboard for event failures
4. Check backend logs for signature verification errors

### Summary Generation Failing
1. Verify `OPENAI_API_KEY` is valid
2. Check usage limits (free tier: 5/month)
3. Verify authentication token is sent
4. Review OpenAI API errors in logs

## 📝 Deployment Summary

After successful deployment, you should have:

- ✅ Backend API running and accessible
- ✅ Frontend deployed and connected to backend
- ✅ Database initialized with all tables
- ✅ Stripe webhooks configured and working
- ✅ Authentication working
- ✅ Summary generation functional
- ✅ All configuration validated

## 🔄 Rollback Plan

If deployment fails:

1. **Backend Rollback**:
   ```bash
   # Stop current version
   sudo systemctl stop earningsnerd
   
   # Restore previous version
   git checkout <previous-commit>
   
   # Restart
   sudo systemctl start earningsnerd
   ```

2. **Database Rollback**:
   - Restore from backup if needed
   - Or revert migrations (if using Alembic)

3. **Frontend Rollback**:
   - Revert to previous deployment
   - Or update `NEXT_PUBLIC_API_URL` to point to previous backend

## 📞 Support

For issues during deployment:
1. Check `DEPLOYMENT_CHECKLIST.md` for detailed troubleshooting
2. Review application logs
3. Verify all environment variables are set correctly
4. Test endpoints individually to isolate issues


