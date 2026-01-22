# EarningsNerd - AI-Powered SEC Filing Analysis

Transform dense SEC filings (10-Ks and 10-Qs) into clear, actionable insights using AI. Search any public company, access its filings, and instantly understand performance, risks, and trends.

## 🚀 Features

- **Company Search**: Search by name or ticker symbol
- **SEC Filing Retrieval**: Automatic access to 10-K and 10-Q filings from SEC EDGAR with robust XBRL parsing
- **AI Summarization**: GPT-4 powered summaries of business overview, financials, risks, and MD&A
- **Strict JSON Contracts**: Structured data output for reliable downstream integration
- **Side-by-Side Comparison**: Compare multiple filings (2-5) to analyze trends and changes (Pro feature)
- **Financial Visualization**: Interactive charts for revenue, earnings, and key metrics
- **Trending & Hot Filings**: Discover popular companies and recently released filings
- **User Dashboard**: Watchlist, saved summaries, and personalized insights
- **Subscriptions**: Tiered access (Free/Pro) managed via Stripe
- **Analytics**: User behavior tracking with PostHog
- **Email Notifications**: Transactional emails and alerts via Resend
- **Export Options**: Download summaries and reports
- **Clean UI**: Modern "Mint" theme interface built with Next.js, Tailwind CSS, and shadcn/ui

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
- **OpenAI API** - AI summarization (GPT-4)
- **SEC EDGAR Tools** - `sec-edgar-downloader`, `sec-parser`, `arelle`
- **Stripe** - Payments and subscriptions
- **Resend** - Email delivery
- **PostHog** - Product analytics
- **WeasyPrint** - PDF generation

### Frontend
- **Next.js 14** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **Recharts** - Financial charting
- **Lucide React** - Iconography
- **React Query** - Data fetching and caching
- **Axios** - HTTP client
- **PostHog JS** - Analytics integration

## 📋 Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 15+ (or use Docker)
- Redis (or use Docker)
- OpenAI API key
- Stripe API keys (for subscriptions)
- Resend API key (for emails)
- (Optional) Finnhub API key for news sentiment enrichment

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

# Create .env file
cp .env.example .env

# Edit .env with your configuration (see Environment Variables section)
```

### 3. Database Setup

#### Option A: Using Docker (Recommended)

```bash
# From project root
docker-compose up -d postgres redis
```

#### Option B: Local PostgreSQL

```bash
createdb earningsnerd
```

### 4. Run Backend

```bash
cd backend

# Verify configuration before start
python3 scripts/deploy_check.py

# Start FastAPI server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `https://api.earningsnerd.io` (or localhost:8000)
API documentation: `/docs`

### 5. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env.local file
cp .env.local.example .env.local

# Run development server
npm run dev
```

The frontend will be available at `http://localhost:3000`

## 📁 Project Structure

```
earningsnerd/
├── backend/
│   ├── app/
│   │   ├── routers/          # API routes (auth, companies, filings, subscriptions, contact, etc.)
│   │   ├── services/         # Business logic (SEC, OpenAI, Stripe, Resend, XBRL)
│   │   ├── models.py         # Database models
│   │   ├── database.py       # DB connection
│   │   └── config.py         # Configuration
│   ├── pipeline/             # Data processing pipeline (extract, validate, write)
│   ├── prompts/              # System prompts for AI agents
│   ├── scripts/              # Deployment and verification scripts
│   ├── main.py               # FastAPI app entry
│   └── requirements.txt      # Python dependencies
├── frontend/
│   ├── app/                  # Next.js app directory
│   │   ├── company/          # Company pages
│   │   ├── filing/           # Filing pages
│   │   ├── compare/          # Comparison tool
│   │   ├── dashboard/        # User dashboard
│   │   └── pricing/          # Pricing & Subscriptions
│   ├── components/           # React components
│   ├── features/             # Feature-specific components
│   ├── lib/                  # Utilities and API client
│   └── package.json          # Node dependencies
├── docker-compose.yml        # Docker services
└── README.md                 # This file
```

## 🔑 Key API Endpoints

### Authentication & Users
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `GET /api/auth/me` - Get current user

### Companies & Filings
- `GET /api/companies/search` - Search companies
- `GET /api/filings/company/{ticker}` - Get company filings
- `GET /api/trending_tickers` - Get trending companies
- `GET /api/hot-filings` - Get recently viewed filings

### AI Analysis
- `POST /api/summaries/filing/{id}/generate` - Generate AI summary
- `GET /api/summaries/filing/{id}` - Get summary
- `POST /api/compare` - Compare multiple filings (Pro)

### Subscriptions & Operations
- `POST /api/subscriptions/create-checkout-session` - Start subscription
- `POST /api/contact` - Submit contact form
- `POST /api/webhooks/stripe` - Stripe webhook handler

## 🔐 Environment Variables

### Backend (.env)

```env
# AI & LLM
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/ # or https://openrouter.ai/api/v1

# Database & Cache
DATABASE_URL=postgresql://user:pass@localhost:5432/earningsnerd
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your_secret_key_here
CORS_ORIGINS=http://localhost:3000

# Payments (Stripe) - Required for Pro features
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Email (Resend) - Required for notifications
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL=EarningsNerd <hello@yourdomain.com>

# Analytics
POSTHOG_API_KEY=ph_...
POSTHOG_HOST=https://app.posthog.com
```

### Frontend (.env.local)

```env
NEXT_PUBLIC_API_URL=https://api.earningsnerd.io
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...
NEXT_PUBLIC_POSTHOG_KEY=ph_...
NEXT_PUBLIC_POSTHOG_HOST=https://app.posthog.com
```

## 🚢 Deployment

Detailed deployment guides are available:
- [Production Deployment Guide](./PRODUCTION_DEPLOYMENT.md)
- [Deployment Checklist](./DEPLOYMENT_CHECKLIST.md)
- [Deployment Summary](./DEPLOYMENT_SUMMARY.md)

Run the deployment check script before shipping:
```bash
python3 backend/scripts/deploy_check.py
```

## 🚧 Current Status

### ✅ Completed
- [x] Company search & SEC EDGAR integration
- [x] AI summarization with strict JSON schemas
- [x] User authentication & Dashboard
- [x] Financial visualization & "Mint" theme UI
- [x] Multi-filing comparison (Pro)
- [x] Stripe subscription integration
- [x] Email notifications (Resend)
- [x] Contact form & Sitemap generation
- [x] Analytics (PostHog)
- [x] Production-ready deployment scripts

### 🚧 Roadmap
- [ ] Mobile app (React Native)
- [ ] Historical filings archive expansion
- [ ] Advanced portfolio alerts

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For issues or questions:
- Review [Deployment Docs](./PRODUCTION_DEPLOYMENT.md)
- Check API docs at `/docs`
- Open an issue on GitHub

---

**Built with ❤️ by the EarningsNerd team**
