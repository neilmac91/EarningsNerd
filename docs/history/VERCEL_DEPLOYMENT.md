# Vercel Deployment Guide for EarningsNerd

## ✅ Pre-Deployment Setup Complete

The following has been configured:
- ✅ Vercel CLI installed locally
- ✅ `vercel.json` configuration file created
- ✅ Backend API URL set to `https://api.earningsnerd.io`
- ✅ Build script verified and working
- ✅ Next.js configured for SSR

## 🚀 Deployment Steps

### Step 1: Login to Vercel

Run this command from the `frontend` directory:

```bash
cd frontend
npx vercel login
```

This will open a browser window for you to authenticate with Vercel.

### Step 2: Deploy to Vercel

Once logged in, deploy your application:

```bash
npx vercel --prod
```

Or use the npm script:
```bash
npm run deploy
```

**During deployment, Vercel will ask:**
1. **Set up and deploy?** → Yes
2. **Which scope?** → Select your account
3. **Link to existing project?** → No (first time)
4. **Project name?** → `earningsnerd` (or press Enter for default)
5. **Directory?** → `./` (press Enter)
6. **Override settings?** → No (press Enter)

### Step 3: Set Environment Variables

After the first deployment, set the environment variable in Vercel dashboard:

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Select your project (`earningsnerd`)
3. Go to **Settings** → **Environment Variables**
4. Add:
   - **Name**: `NEXT_PUBLIC_API_BASE_URL`
   - **Value**: `https://api.earningsnerd.io`
   - **Environment**: Production, Preview, Development (select all)
   - **Name**: `NEXT_PUBLIC_SENTRY_DSN`
   - **Value**: _(your Sentry DSN — copy from Sentry → Project Settings → Client Keys (DSN); not stored in this repo)_
   - **Environment**: Production, Preview, Development (select all)
   - **Name**: `SENTRY_DSN`
   - **Value**: _(your Sentry DSN — copy from Sentry → Project Settings → Client Keys (DSN); not stored in this repo)_
   - **Environment**: Production, Preview, Development (select all)
5. Click **Save**

### Step 4: Configure Sentry Log Drain

Add the Vercel Log Drain endpoint so deployment logs land in Sentry:

1. Go to **Vercel Dashboard** → your project → **Settings** → **Log Drains**
2. Click **Add Log Drain**
3. Paste the endpoint:
   `https://o4510744719851520.ingest.de.sentry.io/api/4510744722276432/integration/vercel/logs`
4. Save and wait for the connection to validate

### Step 5: Connect Custom Domain

1. In Vercel dashboard, go to your project → **Settings** → **Domains**
2. Click **Add Domain**
3. Enter: `earningsnerd.io`
4. Click **Add**

Vercel will provide DNS records to add to Cloudflare.

### Step 6: Update Cloudflare DNS

Vercel will show you DNS records like:

```
Type: CNAME
Name: @
Value: cname.vercel-dns.com
```

**In Cloudflare:**
1. Go to your domain's DNS settings
2. Add a **CNAME** record:
   - **Name**: `@` (or root domain)
   - **Target**: `cname.vercel-dns.com` (or the value Vercel provides)
   - **Proxy status**: DNS only (gray cloud) initially
3. Wait for DNS propagation (usually 5-15 minutes)

**Note**: If Cloudflare doesn't support CNAME at root, Vercel will provide A records instead.

### Step 7: Enable HTTPS

Vercel automatically provisions SSL certificates. Once DNS propagates:
- SSL will be automatically configured
- Your site will be available at `https://earningsnerd.io`

### Step 8: Redeploy (if needed)

If you added environment variables after deployment, trigger a new deployment:

```bash
npx vercel --prod
```

Or go to Vercel dashboard → **Deployments** → Click **Redeploy** on the latest deployment.

## 🔍 Verify Deployment

After deployment completes:

1. **Check deployment URL**: Vercel provides a URL like `https://earningsnerd-xxx.vercel.app`
2. **Test the site**: Visit the URL and verify it loads
3. **Check API connection**: Try searching for a company to verify backend connectivity
4. **Check custom domain**: Once DNS propagates, visit `https://earningsnerd.io`

## 📝 Important Notes

### Backend API URL
- The backend API URL is set to: `https://api.earningsnerd.io`
- Make sure your backend is deployed and accessible at this URL
- Update CORS settings in your backend to allow requests from `https://earningsnerd.io`

### Environment Variables
- `NEXT_PUBLIC_API_BASE_URL` is set in `vercel.json` and should also be set in Vercel dashboard
- `NEXT_PUBLIC_SENTRY_DSN` and `SENTRY_DSN` should also be set in Vercel dashboard
- Any changes to environment variables require a redeploy

### Automatic Deployments
- Connect your Git repository to Vercel for automatic deployments on push
- Go to **Settings** → **Git** to connect your repository

## 🆘 Troubleshooting

### Deployment Fails
- Check build logs in Vercel dashboard
- Ensure all dependencies are in `package.json`
- Verify `next.config.js` is correct

### Domain Not Working
- Wait 15-30 minutes for DNS propagation
- Verify DNS records in Cloudflare match Vercel's instructions
- Check SSL certificate status in Vercel dashboard

### API Connection Issues
- Verify `NEXT_PUBLIC_API_URL` is set correctly in Vercel
- Check backend CORS settings allow `https://earningsnerd.io`
- Test backend API directly: `curl https://api.earningsnerd.io/health`

## 🎉 Success!

Once deployed, your site will be live at:
- **Vercel URL**: `https://earningsnerd-xxx.vercel.app`
- **Custom Domain**: `https://earningsnerd.io` (after DNS setup)

