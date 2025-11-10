#!/bin/bash

# Production start script for EarningsNerd backend on Render
# This script is optimized for Render's deployment environment

echo "Starting EarningsNerd Backend (Production)..."

# Render sets the PORT environment variable
# Default to 8000 if not set (for local testing)
PORT=${PORT:-8000}

# Start server without reload (reload is for development only)
echo "Starting FastAPI server on port $PORT..."
uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1

