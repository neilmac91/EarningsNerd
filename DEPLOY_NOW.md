# 🚀 Deploy EarningsNerd to Vercel - Quick Start

## Ready to Deploy!

Everything is configured and ready. Follow these steps to deploy:

### Step 1: Login to Vercel (if not already logged in)

```bash
cd frontend
npx vercel login
```

This will open your browser for authentication.

### Step 2: Deploy to Production

```bash
npx vercel --prod --yes
```

Or use the npm script:
```bash
npm run deploy
```

**What happens:**
- Vercel will build your Next.js app
- Deploy it to a production URL (e.g., `https://earningsnerd-xxx.vercel.app`)
- The backend API URL is already configured as `https://api.earningsnerd.io`

### Step 3: Set Environment Variable in Vercel Dashboard

1. Go to https://vercel.com/dashboard
2. Click on your project (`earningsnerd`)
3. Go to **Settings** → **Environment Variables**
4. Add:
   - **Key**: `NEXT_PUBLIC_API_URL`
   - **Value**: `https://api.earningsnerd.io`
   - **Environments**: Select all (Production, Preview, Development)
5. Click **Save**
6. **Redeploy** your project (Deployments → Latest → Redeploy)

### Step 4: Connect Your Domain

1. In Vercel dashboard → **Settings** → **Domains**
2. Click **Add Domain**
3. Enter: `earningsnerd.io`
4. Click **Add**

Vercel will show you DNS records to add to Cloudflare.

### Step 5: Update Cloudflare DNS

Vercel will provide DNS records. Typically:

**Option A: CNAME (if supported)**
```
Type: CNAME
Name: @
Target: cname.vercel-dns.com
Proxy: DNS only (gray cloud)
```

**Option B: A Records (if CNAME not supported at root)**
Vercel will provide IP addresses to use as A records.

**In Cloudflare:**
1. Go to DNS settings for `earningsnerd.io`
2. Add the records Vercel provides
3. Set proxy to **DNS only** (gray cloud) initially
4. Wait 5-15 minutes for DNS propagation

### Step 6: Verify SSL

Vercel automatically provisions SSL certificates. Once DNS propagates:
- Your site will be available at `https://earningsnerd.io`
- SSL will be automatically configured

## ✅ Verification Checklist

After deployment:
- [ ] Site loads at Vercel URL
- [ ] Environment variable `NEXT_PUBLIC_API_URL` is set
- [ ] Domain added in Vercel dashboard
- [ ] DNS records added in Cloudflare
- [ ] Site accessible at `https://earningsnerd.io`
- [ ] SSL certificate active (green lock icon)
- [ ] Backend API connectivity working (test search functionality)

## 📝 Important Notes

1. **Backend API**: Make sure your backend is deployed and accessible at `https://api.earningsnerd.io`
2. **CORS**: Update your backend CORS settings to allow `https://earningsnerd.io`
3. **Environment Variables**: Any changes require a redeploy

## 🆘 Need Help?

See `VERCEL_DEPLOYMENT.md` for detailed troubleshooting guide.

## 🎉 Success!

Once complete, your site will be live at:
- **Vercel URL**: `https://earningsnerd-xxx.vercel.app`
- **Custom Domain**: `https://earningsnerd.io`

