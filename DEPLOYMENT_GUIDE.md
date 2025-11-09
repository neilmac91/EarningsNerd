# Deployment Guide for EarningsNerd

## Option A: Deploy to Vercel (Recommended - Easiest)

Vercel has native Next.js support and is the simplest deployment option.

### Steps:

1. **Install Vercel CLI** (if not already installed):
   ```bash
   npm install -g vercel
   ```

2. **Deploy from frontend directory**:
   ```bash
   cd frontend
   vercel
   ```

3. **Set environment variables** in Vercel dashboard:
   - `NEXT_PUBLIC_API_URL` = Your backend API URL (e.g., `https://api.earningsnerd.io`)

4. **Connect custom domain**:
   - In Vercel dashboard, go to your project → Settings → Domains
   - Add `earningsnerd.io`
   - Update DNS records in Cloudflare as instructed by Vercel

### Advantages:
- ✅ Native Next.js support (SSR, ISR, etc.)
- ✅ Automatic deployments on git push
- ✅ Built-in CDN and edge functions
- ✅ Free tier available

---

## Option B: Deploy to Firebase Functions + Hosting

Firebase Functions can host Next.js with SSR, but requires more setup.

### Steps:

1. **Install Firebase Functions dependencies**:
   ```bash
   cd frontend
   npm install firebase-functions@latest firebase-admin@latest
   ```

2. **Create Firebase Function wrapper** (create `functions/index.js`):
   ```javascript
   const { next } = require('next/dist/server/next');
   const functions = require('firebase-functions');

   const nextjsServer = next({
     dev: false,
     conf: { distDir: '.next' },
   });

   const nextjsHandle = nextjsServer.getRequestHandler();

   exports.nextjs = functions.https.onRequest((req, res) => {
     return nextjsServer.prepare().then(() => {
       return nextjsHandle(req, res);
     });
   });
   ```

3. **Update firebase.json**:
   ```json
   {
     "hosting": {
       "rewrites": [
         {
           "source": "**",
           "function": "nextjs"
         }
       ]
     },
     "functions": {
       "source": "frontend",
       "runtime": "nodejs18"
     }
   }
   ```

4. **Build and deploy**:
   ```bash
   cd frontend
   npm run build
   firebase deploy --only functions,hosting
   ```

### Note:
This approach is more complex and may have limitations. Vercel is recommended for Next.js apps.

---

## Option C: Static Export (Current Firebase Hosting)

If you want to stick with Firebase Hosting only (no SSR), you can use static export:

1. **Revert to static export**:
   - Change `output: 'standalone'` back to `output: 'export'` in `next.config.js`
   - Pre-generate common routes in `generateStaticParams()`

2. **Build and deploy**:
   ```bash
   cd frontend
   npm run build
   firebase deploy --only hosting
   ```

---

## Environment Variables

Make sure to set these in your deployment platform:

- `NEXT_PUBLIC_API_URL` - Your backend API URL (e.g., `https://api.earningsnerd.io`)

---

## Recommended: Vercel Deployment

For the best Next.js experience with minimal configuration, **Vercel is recommended**.

After deploying to Vercel:
1. Connect your `earningsnerd.io` domain
2. Update Cloudflare DNS records as instructed by Vercel
3. Set environment variables in Vercel dashboard

