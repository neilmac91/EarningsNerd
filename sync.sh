#!/bin/bash
# sync.sh — keeps local and remote GitHub versions aligned

echo "🔄 Pulling latest changes from GitHub..."
git pull origin main || { echo "❌ Pull failed. Resolve conflicts first."; exit 1; }

echo "✅ Repo is up to date with GitHub."
echo "🛠️ Make your changes in Cursor now."

read -p "Press ENTER when done editing to push changes..."

echo "📦 Adding and committing your changes..."
git add .
git commit -m "Sync from Cursor $(date '+%Y-%m-%d %H:%M:%S')" || echo "⚠️ Nothing to commit."

echo "⬆️ Pushing changes to GitHub..."
git push origin main

echo "🎉 Done! Local and GitHub repo are now in sync."

