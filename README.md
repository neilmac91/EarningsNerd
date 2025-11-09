# EarningsNerd - AI-Powered SEC Filing Analysis

Transform dense SEC filings (10-Ks and 10-Qs) into clear, actionable insights using AI. Search any public company, access its filings, and instantly understand performance, risks, and trends.

## 🚀 Features

- **Company Search**: Search by name or ticker symbol
- **SEC Filing Retrieval**: Automatic access to 10-K and 10-Q filings from SEC EDGAR
- **AI Summarization**: GPT-4 powered summaries of business overview, financials, risks, and MD&A
- **Historical Access**: View and compare filings across multiple years/quarters
- **User Authentication**: Secure login and registration
- **Clean UI**: Modern, responsive interface built with Next.js and Tailwind CSS

## 📑 AI Summary JSON Contract

The analyst prompts that drive EarningsNerd now enforce a strict JSON contract:

- Every string must be substantive—blank strings and placeholder text are rejected.
- Each array must contain 1–4 evidence-backed bullets. When no validated bullet exists, the array must be `["Not disclosed—<concise reason>"]`.
- Risk factors, notable items, and other bullets must cite specific excerpts or XBRL anchors in their supporting evidence fields.

Update your integrations or downstream validators to respect these strengthened guarantees.

## 🛠️ Tech Stack

### Backend
- **FastAPI** - Python web framework
- **PostgreSQL** - Primary database
- **Redis** - Caching layer
- **OpenAI API** - AI summarization
- **SEC EDGAR API** - Filing data source

### Frontend
- **Next.js 14** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **React Query** - Data fetching and caching
- **Axios** - HTTP client

## 📋 Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 15+ (or use Docker)
- Redis (or use Docker)
- OpenAI API key
- (Optional) Stripe API keys for payments
- (Recommended) Finnhub API key for news sentiment enrichment

## 🚀 Quick Start

### 1. Clone and Setup

```bash
cd earningsnerd
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file from .env.example
cp .env.example .env

# Edit .env with your configuration:
# - DATABASE_URL (default: postgresql://user:password@localhost:5432/earningsnerd)
# - OPENAI_API_KEY (required)
# - SECRET_KEY (change in production)
```

### 3. Database Setup

#### Option A: Using Docker (Recommended)

```bash
# From project root
docker-compose up -d postgres redis
```

#### Option B: Local PostgreSQL

```bash
# Create database
createdb earningsnerd

# Or using psql
psql -U postgres
CREATE DATABASE earningsnerd;
```

### 4. Run Backend

```bash
cd backend

# Start FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`
API documentation: `http://localhost:8000/docs`

### 5. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env.local file
cp .env.local.example .env.local

# Edit .env.local if needed (default: NEXT_PUBLIC_API_URL=http://localhost:8000)

# Run development server
npm run dev
```

The frontend will be available at `http://localhost:3000`

## 📁 Project Structure

```
earningsnerd/
├── backend/
│   ├── app/
│   │   ├── routers/          # API routes
│   │   ├── services/         # Business logic (SEC, OpenAI)
│   │   ├── models.py         # Database models
│   │   ├── database.py       # DB connection
│   │   └── config.py         # Configuration
│   ├── main.py               # FastAPI app entry
│   └── requirements.txt      # Python dependencies
├── frontend/
│   ├── app/                  # Next.js app directory
│   │   ├── page.tsx          # Homepage
│   │   ├── company/          # Company pages
│   │   └── filing/           # Filing pages
│   ├── components/           # React components
│   ├── lib/                  # Utilities and API client
│   └── package.json          # Node dependencies
├── docker-compose.yml        # Docker services
└── README.md                 # This file
```

## 🔑 API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `GET /api/auth/me` - Get current user

### Companies
- `GET /api/companies/search?q={query}` - Search companies
- `GET /api/companies/{ticker}` - Get company by ticker

### Filings
- `GET /api/filings/company/{ticker}` - Get company filings
- `GET /api/filings/{id}` - Get specific filing

### Summaries
- `POST /api/summaries/filing/{id}/generate` - Generate AI summary
- `GET /api/summaries/filing/{id}` - Get summary

## 🔐 Environment Variables

### Backend (.env)

Copy `backend/.env.example` to `backend/.env` and fill in your values:

```env
# Required for AI summaries
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://openrouter.ai/api/v1

# Required for subscriptions (if using Stripe)
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key_here
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_signing_secret_here  # CRITICAL: Get from Stripe Dashboard > Webhooks

# Database (SQLite default, PostgreSQL optional)
DATABASE_URL=sqlite:///./earningsnerd.db

# Other settings
SECRET_KEY=your_secret_key_here
CORS_ORIGINS=http://localhost:3000
```

**Important Notes:**
- `STRIPE_WEBHOOK_SECRET` is **required** if you're using Stripe subscriptions. Without it, webhook signature verification will fail and subscription events won't be processed.
- Get your webhook secret from: Stripe Dashboard → Developers → Webhooks → [Your webhook endpoint] → Signing secret
- The application will warn you at startup if required configuration is missing

### Frontend (.env.local)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 🧪 Testing

### Backend

```bash
cd backend
# Run tests (when implemented)
pytest
```

### Frontend

```bash
cd frontend
# Run linter
npm run lint
```

## 📝 Usage Example

1. **Start the application** (backend and frontend)
2. **Search for a company** (e.g., "AAPL" or "Apple")
3. **Select a company** from search results
4. **View available filings** (10-K, 10-Q)
5. **Click "View Summary"** on a filing
6. **Generate AI summary** (if not already generated)
7. **Review summary** with business overview, financials, risks, and MD&A

## 🚧 Current Status

### ✅ Completed (MVP)
- Company search functionality
- SEC EDGAR API integration
- Filing retrieval
- AI summarization engine
- User authentication
- Summary display UI
- Responsive design

### 🚧 TODO (Future)
- Multi-year comparison (Pro feature)
- Export functionality (PDF/CSV)
- Historical filings access
- Payment integration (Stripe)
- Email alerts
- Mobile app

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For issues or questions:
- Check the [Development Plan](./EarningsNerd_Development_Plan.md)
- Review API documentation at `/docs` endpoint
- Open an issue on GitHub

## 🙏 Acknowledgments

- SEC EDGAR for public filing data
- OpenAI for AI summarization capabilities
- FastAPI and Next.js communities

---

**Built with ❤️ by the EarningsNerd team**

