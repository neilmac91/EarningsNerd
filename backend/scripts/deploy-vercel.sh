#!/bin/bash

# Deployment script for EarningsNerd to Vercel
# Manual production deployment helper. Normal frontend deploys use Vercel Git integration.
# Usage from any directory: bash /path/to/repo/backend/scripts/deploy-vercel.sh

set -e  # Exit on error

echo "🚀 Starting Vercel deployment..."

# Check if Vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo "📦 Installing Vercel CLI..."
    npm install -g vercel
fi

# Resolve the repository from this script, independent of the caller's working directory.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../../frontend"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Set production API URL if not already set
if [ -z "$NEXT_PUBLIC_API_BASE_URL" ]; then
    echo "⚠️  NEXT_PUBLIC_API_BASE_URL not set."
    echo "   Please set it in Vercel dashboard after deployment, or export it now:"
    echo "   export NEXT_PUBLIC_API_BASE_URL=https://api.earningsnerd.io"
    read -p "   Enter your backend API URL (or press Enter to skip): " api_url
    if [ ! -z "$api_url" ]; then
        export NEXT_PUBLIC_API_BASE_URL="$api_url"
    fi
fi

echo "🔨 Building Next.js app..."
if [ ! -z "$NEXT_PUBLIC_API_BASE_URL" ]; then
    echo "   API URL: $NEXT_PUBLIC_API_BASE_URL"
    NEXT_PUBLIC_API_BASE_URL="$NEXT_PUBLIC_API_BASE_URL" npm run build
else
    npm run build
fi

echo "✅ Build successful!"

# Deploy to Vercel
echo "🚀 Deploying to Vercel..."
vercel --prod

echo "✅ Deployment complete!"
echo ""
echo "📝 Next steps:"
echo "1. Go to Vercel dashboard and add your custom domain: earningsnerd.io"
echo "2. Set NEXT_PUBLIC_API_BASE_URL environment variable in Vercel dashboard"
echo "3. Update DNS records in Cloudflare as instructed by Vercel"
echo "4. Your site should be live at: https://earningsnerd.io"

