#!/bin/bash

# Start script for EarningsNerd backend

echo "Starting EarningsNerd Backend..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your configuration!"
fi

# Start server
echo "Starting FastAPI server..."
uvicorn main:app --reload --host 0.0.0.0 --port 8000

