# Dockerfile for EarningsNerd Backend - Cloud Run Deployment
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for:
# - psycopg2: libpq-dev
# - weasyprint: libpango, libcairo, etc.
# - lxml: libxml2, libxslt
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Cloud Run sets PORT env var (default 8080)
ENV PORT=8080

# Cloud Run optimized settings:
# - Smaller connection pool for serverless (instances scale up/down)
# - Reduced max overflow to prevent connection exhaustion
ENV DB_POOL_SIZE=5
ENV DB_MAX_OVERFLOW=5
ENV DB_POOL_RECYCLE=1800
ENV DB_CONNECT_TIMEOUT=10

# Run database migrations and start the server
# Note: Cloud Run uses a single worker by default which is fine for scale-to-zero
CMD alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port ${PORT}
