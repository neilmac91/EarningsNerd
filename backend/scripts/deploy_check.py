#!/usr/bin/env python3
"""
Pre-deployment verification script.
Checks all prerequisites before deploying to production.
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings


def check_environment_variables():
    """Check critical environment variables"""
    print("=" * 60)
    print("ENVIRONMENT VARIABLES CHECK")
    print("=" * 60)
    
    checks = {
        "OPENAI_API_KEY": {
            "required": True,
            "set": bool(settings.OPENAI_API_KEY),
            "valid": len(settings.OPENAI_API_KEY) >= 20 if settings.OPENAI_API_KEY else False,
            "message": "Required for AI summary generation"
        },
        "OPENAI_BASE_URL": {
            "required": True,
            "set": bool(settings.OPENAI_BASE_URL),
            "valid": any(
                provider in settings.OPENAI_BASE_URL.lower()
                for provider in ("generativelanguage.googleapis.com", "openrouter.ai")
            ) if settings.OPENAI_BASE_URL else False,
            "message": "Should point to Google AI Studio (recommended) or OpenRouter"
        },
        "STRIPE_SECRET_KEY": {
            "required": False,  # Optional if not using Stripe
            "set": bool(settings.STRIPE_SECRET_KEY),
            "valid": len(settings.STRIPE_SECRET_KEY) >= 20 if settings.STRIPE_SECRET_KEY else False,
            "message": "Required for subscription features"
        },
        "STRIPE_WEBHOOK_SECRET": {
            "required": bool(settings.STRIPE_SECRET_KEY),  # Required if Stripe is enabled
            "set": bool(settings.STRIPE_WEBHOOK_SECRET),
            "valid": bool(settings.STRIPE_WEBHOOK_SECRET),
            "message": "CRITICAL: Required if using Stripe webhooks"
        },
        "SECRET_KEY": {
            "required": True,
            "set": bool(settings.SECRET_KEY),
            "valid": settings.SECRET_KEY != "change-this-secret-key-in-production",
            "message": "Must be changed from default in production"
        },
        "DATABASE_URL": {
            "required": True,
            "set": bool(settings.DATABASE_URL),
            "valid": True,
            "message": "Database connection string"
        }
    }
    
    all_passed = True
    critical_failures = []
    warnings = []
    
    for var_name, check in checks.items():
        status = "✓" if check["set"] and check["valid"] else ("⚠️" if check["set"] else "✗")
        required_marker = "[REQUIRED]" if check["required"] else "[OPTIONAL]"
        
        print(f"\n{status} {var_name} {required_marker}")
        print(f"   {check['message']}")
        
        if check["required"] and not check["set"]:
            print(f"   ❌ FAILED: {var_name} is required but not set")
            critical_failures.append(var_name)
            all_passed = False
        elif check["set"] and not check["valid"]:
            if check["required"]:
                print(f"   ❌ FAILED: {var_name} is set but invalid")
                critical_failures.append(var_name)
                all_passed = False
            else:
                print(f"   ⚠️  WARNING: {var_name} is set but may be invalid")
                warnings.append(var_name)
        elif check["set"]:
            value_preview = str(getattr(settings, var_name))[:30] + "..." if len(str(getattr(settings, var_name))) > 30 else str(getattr(settings, var_name))
            print(f"   ✓ Set: {value_preview}")
    
    # Special check for Stripe webhook secret
    if settings.STRIPE_SECRET_KEY and not settings.STRIPE_WEBHOOK_SECRET:
        print(f"\n⚠️  CRITICAL WARNING: STRIPE_SECRET_KEY is set but STRIPE_WEBHOOK_SECRET is missing!")
        print(f"   Webhook endpoints will fail signature verification.")
        print(f"   Subscription events will NOT be processed.")
        warnings.append("STRIPE_WEBHOOK_SECRET_MISSING")
    
    return all_passed, critical_failures, warnings


def check_configuration_validation():
    """Run configuration validation"""
    print("\n" + "=" * 60)
    print("CONFIGURATION VALIDATION")
    print("=" * 60)
    
    # OpenAI validation
    openai_valid, openai_warnings = settings.validate_openai_config()
    print(f"\nOpenAI-compatible Configuration (Google AI Studio recommended):")
    print(f"  Status: {'✓ Valid' if openai_valid else '✗ Invalid'}")
    if openai_warnings:
        for warning in openai_warnings:
            print(f"  ⚠️  {warning}")
    
    # Stripe validation
    stripe_valid, stripe_warnings = settings.validate_stripe_config()
    print(f"\nStripe Configuration:")
    print(f"  Status: {'✓ Valid' if stripe_valid else '✗ Invalid'}")
    if stripe_warnings:
        for warning in stripe_warnings:
            print(f"  ⚠️  {warning}")
    
    return openai_valid and stripe_valid, openai_warnings + stripe_warnings


def check_database():
    """Check database connectivity"""
    print("\n" + "=" * 60)
    print("DATABASE CHECK")
    print("=" * 60)
    
    try:
        from app.database import engine, Base
        from sqlalchemy import inspect
        
        # Try to connect
        with engine.connect() as conn:
            print("✓ Database connection successful")
            
            # Check if tables exist
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            expected_tables = [
                "users", "companies", "filings", "summaries",
                "user_searches", "saved_summaries", "user_usage",
                "watchlist", "summary_generation_progress", "filing_content_cache"
            ]
            
            print(f"\nFound {len(tables)} tables in database")
            missing_tables = [t for t in expected_tables if t not in tables]
            
            if missing_tables:
                print(f"⚠️  Missing tables: {', '.join(missing_tables)}")
                print("   Tables will be created automatically on startup")
            else:
                print("✓ All expected tables present")
            
            return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False


def check_dependencies():
    """Check Python dependencies"""
    print("\n" + "=" * 60)
    print("DEPENDENCIES CHECK")
    print("=" * 60)
    
    required_packages = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("sqlalchemy", "sqlalchemy"),
        ("httpx", "httpx"),
        ("openai", "openai"),
        ("beautifulsoup4", "bs4"),
        ("pydantic", "pydantic"),
        ("pydantic_settings", "pydantic_settings"),
        ("python-jose", "jose"),
        ("passlib", "passlib"),
        ("stripe", "stripe")
    ]
    
    missing = []
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
            print(f"✓ {package_name}")
        except ImportError:
            print(f"✗ {package_name} - MISSING")
            missing.append(package_name)
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("   Install with: pip install -r requirements.txt")
        return False
    
    return True


def main():
    """Run all pre-deployment checks"""
    print("\n" + "=" * 60)
    print("PRE-DEPLOYMENT VERIFICATION")
    print("=" * 60)
    print()
    
    results = {
        "env_vars": False,
        "config": False,
        "database": False,
        "dependencies": False
    }
    
    # Check environment variables
    env_passed, critical_failures, warnings = check_environment_variables()
    results["env_vars"] = env_passed
    
    # Check configuration validation
    config_passed, config_warnings = check_configuration_validation()
    results["config"] = config_passed
    
    # Check database
    db_passed = check_database()
    results["database"] = db_passed
    
    # Check dependencies
    deps_passed = check_dependencies()
    results["dependencies"] = deps_passed
    
    # Summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT READINESS SUMMARY")
    print("=" * 60)
    
    all_passed = all(results.values())
    
    for check_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {check_name.replace('_', ' ').title()}")
    
    if critical_failures:
        print(f"\n❌ CRITICAL FAILURES:")
        for failure in critical_failures:
            print(f"   - {failure} must be configured")
    
    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for warning in warnings[:5]:  # Show first 5
            print(f"   - {warning}")
        if len(warnings) > 5:
            print(f"   ... and {len(warnings) - 5} more")
    
    if all_passed and not critical_failures:
        print("\n✅ All checks passed! Ready for deployment.")
        print("\nNext steps:")
        print("1. Start backend: uvicorn main:app --host 0.0.0.0 --port 8000")
        print("2. Verify health endpoint: curl https://api.earningsnerd.io/health")
        print("3. Check startup logs for configuration warnings")
        return 0
    else:
        print("\n❌ Deployment checks failed. Fix issues above before deploying.")
        if critical_failures:
            print("\nCRITICAL: Fix these issues first:")
            for failure in critical_failures:
                print(f"  - {failure}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

