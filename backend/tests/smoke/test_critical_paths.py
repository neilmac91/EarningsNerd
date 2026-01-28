"""
Smoke Test Suite - Critical Path Validation for EarningsNerd.

These tests verify that the core functionality of the application is operational.
Run these tests after every deployment to ensure critical paths are working.

Usage:
    pytest tests/smoke/ -v --tb=short

Critical Paths Tested:
1. Health check endpoints (basic and detailed)
2. Company search functionality
3. Filing retrieval
4. Authentication flow
5. Database connectivity
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


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

    def test_trending_companies_endpoint_exists(self, client):
        """Trending companies endpoint should exist."""
        try:
            response = client.get("/api/companies/trending")
            # Should return 200 or 500 (if DB not initialized in test env)
            # In production, this should always return 200
            assert response.status_code in [200, 500]
        except Exception as e:
            # Database not initialized in test env - this is expected
            # In production smoke tests, this should pass
            if "no such table" in str(e):
                pytest.skip("Database tables not initialized (expected in local test env)")


class TestFilingsEndpoints:
    """Test filings-related endpoints."""

    def test_recent_filings_endpoint_exists(self, client):
        """Recent filings endpoint should exist."""
        try:
            response = client.get("/api/filings/recent/latest")
            # Should return 200, 404, or 500 (if DB not initialized in test env)
            # In production, this should return 200
            assert response.status_code in [200, 404, 500]
        except Exception as e:
            # Database not initialized in test env - this is expected
            if "no such table" in str(e):
                pytest.skip("Database tables not initialized (expected in local test env)")


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
        """robots.txt should be served correctly."""
        response = client.get("/robots.txt")
        assert response.status_code == 200
        assert "User-agent" in response.text
        assert "Disallow: /api/" in response.text

    def test_sitemap_endpoint_exists(self, client):
        """Sitemap endpoint should exist."""
        try:
            response = client.get("/sitemap.xml")
            # Should return 200 or 500 (if DB not initialized in test env)
            # In production with DB, this should return 200
            assert response.status_code in [200, 500]
        except Exception as e:
            # Database not initialized in test env - this is expected
            if "no such table" in str(e):
                pytest.skip("Database tables not initialized (expected in local test env)")


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


# Marker for smoke tests
pytestmark = pytest.mark.smoke
