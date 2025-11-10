# Quick Start Guide

Get EarningsNerd up and running in 5 minutes!

## Prerequisites

- Python 3.10+
- Node.js 18+
- Docker and Docker Compose (optional, for database)

## Step 1: Start Database (Docker)

```bash
docker-compose up -d postgres redis
```

Or use local PostgreSQL/Redis if you have them installed.

## Step 2: Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env and add your OPENAI_API_KEY
# DATABASE_URL=postgresql://user:password@localhost:5432/earningsnerd
# OPENAI_API_KEY=your_key_here

# Start backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: `https://api.earningsnerd.io`
API docs at: `https://api.earningsnerd.io/docs`

## Step 3: Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env.local (optional, defaults work)
cp .env.local.example .env.local

# Start frontend
npm run dev
```

Frontend will be available at: `http://localhost:3000`

## Step 4: Test It!

1. Open `http://localhost:3000`
2. Search for "AAPL" or "Apple"
3. Click on the company
4. View available filings
5. Click "View Summary" on a filing
6. Click "Generate Summary" to create AI summary

## Troubleshooting

### Database Connection Error
- Make sure PostgreSQL is running
- Check DATABASE_URL in backend/.env
- Run: `docker-compose ps` to check containers

### OpenAI API Error
- Make sure you've added OPENAI_API_KEY to backend/.env
- Verify your API key is valid and has credits

### Frontend Can't Connect to Backend
- Check NEXT_PUBLIC_API_URL in frontend/.env.local
- Make sure backend is running on port 8000
- Check CORS settings in backend/app/config.py

## Need Help?

Check the full [README.md](./README.md) for detailed documentation.

