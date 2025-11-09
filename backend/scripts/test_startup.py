#!/usr/bin/env python3
"""
Test backend startup and validate configuration.
Simulates the startup process to catch configuration issues.
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_startup_validation():
    """Test startup validation logic"""
    print("Testing startup validation...")
    print("=" * 60)
    
    from app.config import settings
    
    # Test OpenAI validation
    print("\n1. OpenAI/OpenRouter Configuration:")
    is_valid, warnings = settings.validate_openai_config()
    if warnings:
        print("   ⚠️  Warnings:")
        for warning in warnings:
            print(f"      - {warning}")
    if is_valid:
        print(f"   ✓ OpenAI/OpenRouter configured: base_url={settings.OPENAI_BASE_URL}")
    else:
        print("   ✗ OpenAI/OpenRouter configuration is invalid. AI summaries may not work.")
    
    # Test Stripe validation
    print("\n2. Stripe Configuration:")
    stripe_valid, stripe_warnings = settings.validate_stripe_config()
    if stripe_warnings:
        print("   ⚠️  Warnings:")
        for warning in stripe_warnings:
            print(f"      - {warning}")
    if stripe_valid:
        print("   ✓ Stripe configured: API key present")
        if settings.STRIPE_WEBHOOK_SECRET:
            print("   ✓ Stripe webhook secret configured: subscription events will be processed")
        else:
            print("   ⚠️  Stripe webhook secret not configured: subscription events will fail")
    else:
        print("   ✗ Stripe configuration is invalid. Subscription features will be disabled.")
    
    # Test database initialization
    print("\n3. Database Initialization:")
    try:
        from app.database import engine, Base
        # This is what happens at startup
        Base.metadata.create_all(bind=engine)
        print("   ✓ Database tables initialized")
    except Exception as e:
        print(f"   ✗ Database initialization failed: {e}")
        return False
    
    # Test FastAPI app creation
    print("\n4. FastAPI Application:")
    try:
        from fastapi import FastAPI
        from app.routers import auth, companies, filings, summaries
        
        app = FastAPI(title="EarningsNerd API")
        print("   ✓ FastAPI app created")
        print("   ✓ Routers imported successfully")
    except Exception as e:
        print(f"   ✗ FastAPI app creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✅ Startup validation test completed")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = test_startup_validation()
    sys.exit(0 if success else 1)


