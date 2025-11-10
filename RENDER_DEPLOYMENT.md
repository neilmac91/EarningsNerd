# Render Deployment Guide for EarningsNerd Backend

## Issues Fixed

1. **Python Version Mismatch**: Render was using Python 3.13.4 (default) instead of Python 3.11.9
2. **Build Command Error**: Render was installing from root `requirements.txt` instead of `backend/requirements.txt`
3. **pydantic-core Build Failure**: Old pydantic versions don't have wheels for Python 3.13, causing Rust compilation errors

## Solution

### Files Created/Modified

1. **`runtime.txt`** (at repository root)
   - Specifies Python 3.11.9
   - Render automatically detects this file at the root

2. **`render.yaml`** (at repository root)
   - Configures Render service with correct settings
   - Sets `rootDir: backend` so all commands run from backend directory
   - Specifies build command with pip/setuptools/wheel upgrade
   - Configures start command to use PORT environment variable
   - Lists all required environment variables

3. **`backend/start_production.sh`** (optional)
   - Production start script (if not using render.yaml)

## Deployment Steps

### Option A: Using render.yaml (Recommended)

1. **Push changes to GitHub**:
   ```bash
   git add runtime.txt render.yaml backend/requirements.txt
   git commit -m "Fix Render deployment: Python 3.11.9, correct build commands"
   git push origin main
   ```

2. **In Render Dashboard**:
   - Go to your service settings
   - If using render.yaml, Render will automatically detect it
   - If not, manually configure:
     - **Root Directory**: `backend`
     - **Build Command**: `pip install --upgrade pip setuptools wheel && pip install -r requirements.txt`
     - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
     - **Python Version**: `3.11.9` (or use runtime.txt)

3. **Set Environment Variables**:
   - `DATABASE_URL` - PostgreSQL connection string (from Render PostgreSQL service)
   - `OPENAI_API_KEY` - Your OpenRouter API key
   - `OPENAI_BASE_URL` - `https://openrouter.ai/api/v1`
   - `SECRET_KEY` - Random secret key for JWT tokens
   - `STRIPE_SECRET_KEY` - Stripe secret key (if using subscriptions)
   - `STRIPE_PUBLISHABLE_KEY` - Stripe publishable key
   - `STRIPE_WEBHOOK_SECRET` - Stripe webhook secret
   - `REDIS_URL` - Redis connection string (if using Redis)
   - `FINNHUB_API_KEY` - Finnhub API key (if using)
   - `ENVIRONMENT` - `production`
   - `CORS_ORIGINS` - `https://earningsnerd.io,https://www.earningsnerd.io`

### Option B: Manual Configuration (Without render.yaml)

1. **In Render Dashboard**:
   - Create new Web Service
   - Connect your GitHub repository
   - Configure:
     - **Name**: `earningsnerd-backend`
     - **Environment**: `Python 3`
     - **Region**: `Oregon` (or your preference)
     - **Branch**: `main`
     - **Root Directory**: `backend`
     - **Build Command**: `pip install --upgrade pip setuptools wheel && pip install -r requirements.txt`
     - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
     - **Plan**: `Free` (or paid plan)

2. **Add Environment Variables** (same as Option A)

3. **Create PostgreSQL Database** (if not already created):
   - In Render Dashboard, create new PostgreSQL service
   - Copy the internal database URL
   - Set as `DATABASE_URL` in your web service environment variables

## Verification

After deployment, verify:

1. **Health Check**:
   ```bash
   curl https://your-service.onrender.com/health
   ```
   Should return: `{"status":"healthy"}`

2. **API Docs**:
   Visit: `https://your-service.onrender.com/docs`

3. **Check Logs**:
   - In Render Dashboard, check service logs
   - Look for startup messages:
     - `✓ OpenAI/OpenRouter configured`
     - `✓ Stripe configured` (if configured)
     - `INFO:     Uvicorn running on http://0.0.0.0:XXXX`

## Troubleshooting

### Build Fails with pydantic-core Error
- **Cause**: Python version mismatch or missing wheels
- **Solution**: Ensure `runtime.txt` exists at root with `python-3.11.9`

### Database Connection Error
- **Cause**: DATABASE_URL not set or incorrect
- **Solution**: Verify DATABASE_URL in environment variables, use internal database URL from Render PostgreSQL service

### Port Already in Use
- **Cause**: Start command not using $PORT variable
- **Solution**: Ensure start command uses `--port $PORT` (Render sets this automatically)

### Module Not Found Errors
- **Cause**: Dependencies not installed or wrong root directory
- **Solution**: Verify root directory is set to `backend` and build command runs from correct location

### CORS Errors
- **Cause**: CORS_ORIGINS not set correctly
- **Solution**: Set CORS_ORIGINS to your frontend domain(s)

## Notes

- Render free tier services spin down after 15 minutes of inactivity
- First request after spin-down may take 30-60 seconds (cold start)
- Consider upgrading to a paid plan for production use
- Database migrations (Alembic) should be run manually or via a script, not automatically on startup

## Next Steps

1. Set up PostgreSQL database on Render
2. Configure environment variables
3. Deploy and verify health check
4. Set up custom domain (if needed)
5. Configure SSL/TLS (automatic on Render)

