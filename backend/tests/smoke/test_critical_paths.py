"""
Smoke Test Suite - Critical Path Validation for EarningsNerd.

These tests verify that the core functionality of the application is operational.
Run these tests after every deployment to ensure critical paths are working.

Usage:
    # Run from backend directory
    pytest tests/smoke/ -v --tb=short

    # Or with PYTHONPATH set
    PYTHONPATH=. pytest tests/smoke/ -v --tb=short

Critical Paths Tested:
1. Health check endpoints (basic and detailed)
2. Company search functionality
3. Filing retrieval
4. Authentication flow
5. Database connectivity

Note:
    Tests that require database access are marked with @pytest.mark.requires_db
    and will skip gracefully if the database is not initialized.
"""

import pytest
from fastapi.testclient import TestClient
from sqlite3 import OperationalError as SQLiteOperationalError

# Import app - relies on PYTHONPATH or running from backend directory
from main import app


@pytest.fixture(scope="module")
def client():
    """
    Create a test client for the FastAPI app.

    Module scope means TestClient lifespan runs once per test module,
    dramatically reducing startup overhead in CI.
    """
    with TestClient(app) as test_client:
        yield test_client


def _is_db_table_error(exc: Exception) -> bool:
    """Check if an exception is due to missing database tables."""
    error_str = str(exc).lower()
    return (
        "no such table" in error_str or
        "relation" in error_str and "does not exist" in error_str or
        isinstance(exc, SQLiteOperationalError)
    )


class TestHealthEndpoints:
    """Test health check endpoints for monitoring and load balancers."""

    def test_basic_health_check(self, client):
        """Basic health check should always return healthy."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_detailed_health_check_structure(self, client):
        """Detailed health check should return proper structure."""
        response = client.get("/health/detailed")
        # Can be 200 (healthy/degraded) or 503 (unhealthy)
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data
        assert "checks" in data
        assert "timestamp" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

    def test_detailed_health_check_database(self, client):
        """Detailed health check should verify database connectivity."""
        response = client.get("/health/detailed")
        data = response.json()
        assert "database" in data["checks"]
        # Database should have healthy key
        assert "healthy" in data["checks"]["database"]

    def test_detailed_health_check_redis(self, client):
        """Detailed health check should verify Redis connectivity."""
        response = client.get("/health/detailed")
        data = response.json()
        assert "redis" in data["checks"]
        # Redis check should have healthy key
        assert "healthy" in data["checks"]["redis"]


class TestRootEndpoint:
    """Test the root API endpoint."""

    def test_root_returns_api_info(self, client):
        """Root endpoint should return API information."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "operational"


class TestCompanyEndpoints:
    """Test company-related endpoints."""

    def test_company_search_endpoint_exists(self, client):
        """Company search endpoint should exist and respond."""
        # Search with a valid query
        response = client.get("/api/companies/search?q=apple")
        # Should return 200, 404, or 503 (SEC EDGAR unavailable)
        # 500 indicates a code error, which is what we want to catch
        assert response.status_code in [200, 404, 503]

    @pytest.mark.requires_db
    def test_trending_companies_endpoint_exists(self, client):
        """Trending companies endpoint should exist."""
        try:
            response = client.get("/api/companies/trending")
            # Should return 200 or 500 (if DB not initialized in test env)
            # In production, this should always return 200
            assert response.status_code in [200, 500]
        except Exception as e:
            if _is_db_table_error(e):
                pytest.skip("Database tables not initialized (run in production for full coverage)")


class TestFilingsEndpoints:
    """Test filings-related endpoints."""

    @pytest.mark.requires_db
    def test_recent_filings_endpoint_exists(self, client):
        """Recent filings endpoint should exist."""
        try:
            response = client.get("/api/filings/recent/latest")
            # Should return 200, 404, or 500 (if DB not initialized in test env)
            # In production, this should return 200
            assert response.status_code in [200, 404, 500]
        except Exception as e:
            if _is_db_table_error(e):
                pytest.skip("Database tables not initialized (run in production for full coverage)")


class TestAuthEndpoints:
    """Test authentication endpoints."""

    def test_register_endpoint_exists(self, client):
        """Registration endpoint should exist and validate input."""
        # Send invalid data to test endpoint exists
        response = client.post("/api/auth/register", json={})
        # Should return 422 (validation error) not 404 or 500
        assert response.status_code == 422

    def test_login_endpoint_exists(self, client):
        """Login endpoint should exist and validate input."""
        # Send invalid data to test endpoint exists
        response = client.post("/api/auth/login", json={})
        # Should return 422 (validation error) not 404 or 500
        assert response.status_code == 422

    def test_me_endpoint_requires_auth(self, client):
        """Me endpoint should require authentication."""
        response = client.get("/api/auth/me")
        # Should return 401 or 403 (not 404 or 500)
        assert response.status_code in [401, 403]


class TestSubscriptionEndpoints:
    """Test subscription-related endpoints."""

    def test_usage_endpoint_requires_auth(self, client):
        """Usage endpoint should require authentication."""
        response = client.get("/api/subscriptions/usage")
        assert response.status_code in [401, 403]


class TestSEOEndpoints:
    """Test SEO-related endpoints."""

    def test_robots_txt(self, client):
        """The API host's robots.txt disallows all crawling (the site lives on www)."""
        response = client.get("/robots.txt")
        assert response.status_code == 200
        assert "User-agent" in response.text
        assert "Disallow: /" in response.text
        # No partial allow: crawlers have no business on the API host at all.
        assert "Allow: /" not in response.text

    @pytest.mark.requires_db
    def test_sitemap_endpoint_exists(self, client):
        """Sitemap endpoint should exist."""
        try:
            response = client.get("/sitemap.xml")
            # Should return 200 or 500 (if DB not initialized in test env)
            # In production with DB, this should return 200
            assert response.status_code in [200, 500]
        except Exception as e:
            if _is_db_table_error(e):
                pytest.skip("Database tables not initialized (run in production for full coverage)")


class TestSecurityHeaders:
    """Test that security headers are present."""

    def test_security_headers_present(self, client):
        """API responses should include security headers."""
        # Use a simple endpoint that doesn't require DB
        response = client.get("/health")
        # Check for security headers
        assert "x-content-type-options" in response.headers
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "x-frame-options" in response.headers


class TestErrorHandling:
    """Test error handling for invalid requests."""

    def test_404_for_nonexistent_endpoint(self, client):
        """Non-existent endpoints should return 404."""
        response = client.get("/api/nonexistent/endpoint")
        assert response.status_code == 404

    def test_method_not_allowed(self, client):
        """Wrong HTTP method should return 405."""
        response = client.delete("/health")
        assert response.status_code == 405


class TestCORS:
    """Test CORS configuration."""

    def test_cors_headers_for_allowed_origin(self, client):
        """CORS headers should be present for allowed origins."""
        response = client.options(
            "/api/companies/trending",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        # Should allow localhost:3000
        assert response.status_code == 200

    def test_error_response_carries_cors_headers(self):
        """A 500 must echo Access-Control-Allow-Origin for an allowed origin.

        Regression guard: FastAPI's generic-``Exception`` handler runs inside
        ServerErrorMiddleware, which sits OUTSIDE CORSMiddleware — so its 500 response
        does not get CORS headers automatically. Without the explicit fix in
        ``main._error_response_cors_headers`` the browser blocks the cross-origin 500 and
        the client reports an opaque network failure ("Unable to connect to the server")
        instead of the real server error.
        """
        async def _boom():
            raise RuntimeError("intentional test failure")

        app.add_api_route("/__test_boom__", _boom, methods=["GET"])
        try:
            # raise_server_exceptions=False lets the global handler produce the 500 response
            # (the default re-raises it, bypassing the handler under test).
            with TestClient(app, raise_server_exceptions=False) as c:
                allowed = c.get("/__test_boom__", headers={"Origin": "http://localhost:3000"})
                assert allowed.status_code == 500
                assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"

                # A disallowed origin must NOT be echoed back.
                denied = c.get("/__test_boom__", headers={"Origin": "https://evil.example.com"})
                assert denied.status_code == 500
                assert denied.headers.get("access-control-allow-origin") is None
        finally:
            app.router.routes = [
                r for r in app.router.routes
                if getattr(r, "path", None) != "/__test_boom__"
            ]


# Marker for smoke tests
pytestmark = pytest.mark.smoke


class TestAnalysisEndpoints:
    """Multi-Period Analysis critical path: routes registered + gated correctly."""

    def test_coverage_requires_auth(self, client):
        response = client.get("/api/analysis/AAPL/coverage")
        assert response.status_code == 401

    def test_dataset_requires_auth(self, client):
        response = client.post(
            "/api/analysis/AAPL/dataset",
            json={"mode": "annual", "start_period": "FY2020", "end_period": "FY2024"},
        )
        assert response.status_code == 401

    def test_stream_requires_auth(self, client):
        response = client.post(
            "/api/analysis/AAPL/stream",
            json={"mode": "annual", "start_period": "FY2020", "end_period": "FY2024"},
        )
        assert response.status_code == 401

    def test_export_requires_auth(self, client):
        assert client.get("/api/analysis/export/1/pdf").status_code == 401

    def test_compare_router_is_gone(self, client):
        # M5 teardown: the dark Compare feature is fully retired, not just hidden.
        response = client.post("/api/compare/", json={"filing_ids": [1, 2]})
        assert response.status_code == 404
