# Deployment Issues and Solutions

## Current Issue: Next.js Static Export with Dynamic Routes

The Next.js app is configured for static export (`output: 'export'`), but there's an issue with dynamic routes (`[ticker]` and `[id]`) when using client components.

### Problem
Next.js static export requires `generateStaticParams()` for all dynamic routes, but when the page file imports a client component, Next.js isn't recognizing the export properly.

### Solutions to Try

#### Option 1: Use Next.js without Static Export (Recommended for now)
Remove `output: 'export'` from `next.config.js` and deploy using Firebase Functions or another hosting solution that supports Next.js SSR.

#### Option 2: Pre-generate Common Routes
Instead of returning an empty array, pre-generate routes for common companies:
```typescript
export async function generateStaticParams() {
  return [
    { ticker: 'AAPL' },
    { ticker: 'MSFT' },
    { ticker: 'GOOGL' },
    // Add more common tickers
  ]
}
```

#### Option 3: Use Query Parameters Instead of Dynamic Routes
Restructure to use query parameters (`/company?ticker=AAPL`) instead of dynamic routes (`/company/AAPL`).

#### Option 4: Use a Catch-All Route
Use `[...slug]` catch-all route that handles routing entirely client-side.

## Current Configuration

- ✅ Next.js configured for static export
- ✅ Firebase hosting configured to serve from `frontend/out`
- ✅ Home page converted to client-side rendering
- ⚠️ Dynamic route pages need `generateStaticParams` but Next.js isn't recognizing it

## Next Steps

1. Try Option 1 (remove static export) and deploy to Firebase Functions
2. Or try Option 2 (pre-generate routes) for a limited set of companies
3. Or restructure to use query parameters instead of dynamic routes

