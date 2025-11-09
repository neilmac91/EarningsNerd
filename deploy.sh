#!/bin/bash

# Deployment script for EarningsNerd to Firebase Hosting
# This script builds the Next.js app and deploys it to Firebase

set -e  # Exit on error

echo "🚀 Starting deployment process..."

# Check if Firebase CLI is installed
if ! command -v firebase &> /dev/null; then
    echo "❌ Firebase CLI is not installed. Please install it with:"
    echo "   npm install -g firebase-tools"
    exit 1
fi

# Check if we're logged in to Firebase
if ! firebase projects:list &> /dev/null; then
    echo "❌ Not logged in to Firebase. Please run:"
    echo "   firebase login"
    exit 1
fi

# Navigate to frontend directory
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Set production API URL if not already set
if [ -z "$NEXT_PUBLIC_API_URL" ]; then
    echo "⚠️  NEXT_PUBLIC_API_URL not set. Using default: https://api.earningsnerd.io"
    export NEXT_PUBLIC_API_URL="https://api.earningsnerd.io"
fi

echo "🔨 Building Next.js app..."
echo "   API URL: $NEXT_PUBLIC_API_URL"
npm run build

# Check if build was successful
if [ ! -d "out" ]; then
    echo "❌ Build failed - 'out' directory not found"
    exit 1
fi

echo "✅ Build successful!"

# Go back to project root
cd ..

# Deploy to Firebase
echo "🔥 Deploying to Firebase..."
firebase deploy --only hosting

echo "✅ Deployment complete!"
echo "🌐 Your site should be live at: https://earningsnerd.io"

