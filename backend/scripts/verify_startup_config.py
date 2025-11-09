#!/usr/bin/env python3
"""
Verification script for startup configuration validation.
Tests that configuration validation works correctly.
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import Settings


def test_stripe_validation():
    """Test Stripe configuration validation"""
    print("Testing Stripe configuration validation...\n")
    
    # Test 1: No Stripe key
    settings1 = Settings(STRIPE_SECRET_KEY="")
    valid1, warnings1 = settings1.validate_stripe_config()
    print(f"Test 1 - No Stripe key:")
    print(f"  Valid: {valid1}")
    print(f"  Warnings: {warnings1}")
    assert not valid1, "Should be invalid without Stripe key"
    assert any("STRIPE_SECRET_KEY is not set" in w for w in warnings1)
    print("  ✓ Passed\n")
    
    # Test 2: Stripe key but no webhook secret
    settings2 = Settings(STRIPE_SECRET_KEY="sk_test_12345678901234567890")
    valid2, warnings2 = settings2.validate_stripe_config()
    print(f"Test 2 - Stripe key but no webhook secret:")
    print(f"  Valid: {valid2}")
    print(f"  Warnings: {warnings2}")
    assert valid2, "Should be valid with Stripe key"
    assert any("STRIPE_WEBHOOK_SECRET is not set" in w for w in warnings2)
    print("  ✓ Passed\n")
    
    # Test 3: Both configured
    settings3 = Settings(
        STRIPE_SECRET_KEY="sk_test_12345678901234567890",
        STRIPE_WEBHOOK_SECRET="whsec_12345678901234567890"
    )
    valid3, warnings3 = settings3.validate_stripe_config()
    print(f"Test 3 - Both Stripe key and webhook secret:")
    print(f"  Valid: {valid3}")
    print(f"  Warnings: {warnings3}")
    assert valid3, "Should be valid with both configured"
    assert len(warnings3) == 0, "Should have no warnings when both are set"
    print("  ✓ Passed\n")
    
    # Test 4: Short Stripe key
    settings4 = Settings(STRIPE_SECRET_KEY="sk_test_short")
    valid4, warnings4 = settings4.validate_stripe_config()
    print(f"Test 4 - Short Stripe key:")
    print(f"  Valid: {valid4}")
    print(f"  Warnings: {warnings4}")
    assert not valid4, "Should be invalid with short key"
    assert any("appears too short" in w for w in warnings4)
    print("  ✓ Passed\n")
    
    print("✅ All Stripe validation tests passed!")
    return True


def test_openai_validation():
    """Test OpenAI configuration validation"""
    print("\nTesting OpenAI configuration validation...\n")
    
    # Test 1: No API key
    settings1 = Settings(OPENAI_API_KEY="", OPENAI_BASE_URL="https://openrouter.ai/api/v1")
    valid1, warnings1 = settings1.validate_openai_config()
    print(f"Test 1 - No OpenAI key:")
    print(f"  Valid: {valid1}")
    print(f"  Warnings: {warnings1}")
    assert not valid1
    assert any("OPENAI_API_KEY is not set" in w for w in warnings1)
    print("  ✓ Passed\n")
    
    # Test 2: Valid configuration
    settings2 = Settings(
        OPENAI_API_KEY="sk-123456789012345678901234567890",
        OPENAI_BASE_URL="https://openrouter.ai/api/v1"
    )
    valid2, warnings2 = settings2.validate_openai_config()
    print(f"Test 2 - Valid OpenAI config:")
    print(f"  Valid: {valid2}")
    print(f"  Warnings: {warnings2}")
    assert valid2
    assert len(warnings2) == 0
    print("  ✓ Passed\n")
    
    print("✅ All OpenAI validation tests passed!")
    return True


if __name__ == "__main__":
    try:
        test_stripe_validation()
        test_openai_validation()
        print("\n🎉 All configuration validation tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

