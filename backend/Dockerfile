# Dockerfile for EarningsNerd Backend - Cloud Run Deployment
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for:
# - psycopg2: libpq-dev
# - weasyprint: libpango, libcairo, libpangoft2 (FreeType text backend), fontconfig + a base
#   font (fonts-dejavu-core). Without fontconfig/fonts, WeasyPrint's write_pdf() dereferences a
#   NULL font in Pango and crashes — so PDF export 500s. These are required, not optional.
# - lxml: libxml2, libxslt
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fontconfig \
    fonts-dejavu-core \
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

# Start the server. Schema is created at startup via Base.metadata.create_all()
# in main.py's lifespan handler (this project has no Alembic config).
# Note: Cloud Run uses a single worker by default which is fine for scale-to-zero
#
# --proxy-headers + --forwarded-allow-ips="*": Cloud Run terminates TLS at its proxy and
# forwards to the container over plain HTTP. Without trusting the proxy's X-Forwarded-Proto
# header (uvicorn's forwarded-allow-ips defaults to 127.0.0.1, which never matches the
# Cloud Run front-end), Starlette builds redirect URLs (e.g. the trailing-slash 307) with
# scheme http://, which browsers refuse to follow from an https page (mixed content).
# Trusting "*" is safe here because only Google's front-end can reach the container.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips="*"
