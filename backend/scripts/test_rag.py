#!/usr/bin/env python3
"""
Test script for the RAG pipeline.
Run from the backend directory: python -m scripts.test_rag

Prerequisites:
1. Set SUPABASE_URL and SUPABASE_SERVICE_KEY in your .env
2. Set OPENAI_API_KEY (for embeddings)
3. Run the schema.sql in your Supabase project
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.rag import RAGService
from app.config import settings

SAMPLE_FILING_TEXT = """
ITEM 1A. RISK FACTORS

Investing in our securities involves a high degree of risk. You should carefully consider the risks and uncertainties described below, together with all of the other information in this Annual Report on Form 10-K, including the section titled "Management's Discussion and Analysis of Financial Condition and Results of Operations" and our consolidated financial statements and related notes, before making a decision to invest in our securities.

RISKS RELATED TO OUR BUSINESS AND INDUSTRY

We have a history of net losses, we anticipate increasing expenses in the future, and we may not be able to achieve or maintain profitability.

We have incurred significant losses since our inception. We incurred net losses of $5.6 billion, $4.6 billion, and $3.0 billion in fiscal years 2024, 2023, and 2022, respectively. As of January 28, 2024, we had an accumulated deficit of $18.8 billion. We expect to continue to incur losses for the foreseeable future, and these losses may increase as we continue to invest in research and development, sales and marketing, and general and administrative functions.

Our business is subject to the risks of earthquakes, fire, floods, and other natural catastrophic events, and to interruption by man-made problems such as terrorism.

Our corporate headquarters are located in the San Francisco Bay Area, a region known for seismic activity. A significant natural disaster, such as an earthquake, fire, or flood, could have a material adverse impact on our business, results of operations, and financial condition.

ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS

Revenue for fiscal year 2024 was $60.9 billion, an increase of 126% compared to fiscal year 2023. The increase was primarily driven by strong demand for our Data Center products, particularly our AI-focused GPUs and systems.

Gross profit margin improved to 72.7% in fiscal year 2024 compared to 56.9% in fiscal year 2023, primarily due to a favorable product mix shift towards higher-margin Data Center products.

Operating expenses increased by 23% year-over-year, driven by increased investments in research and development to support our AI initiatives.
"""


async def main():
    print("=" * 60)
    print("EarningsNerd RAG Pipeline Test")
    print("=" * 60)
    
    # Validate configuration
    is_valid, warnings = settings.validate_supabase_config()
    if warnings:
        print("\n⚠️  Configuration Warnings:")
        for w in warnings:
            print(f"   - {w}")
    
    if not is_valid:
        print("\n❌ Supabase configuration is invalid. Cannot proceed.")
        print("   Please set SUPABASE_URL and SUPABASE_SERVICE_KEY in your .env file.")
        return
    
    print(f"\n✓ Supabase URL: {settings.SUPABASE_URL[:30]}...")
    print(f"✓ Service Key: {settings.SUPABASE_SERVICE_KEY[:10]}...")
    
    # Initialize RAG Service
    print("\n📦 Initializing RAG Service...")
    rag = RAGService()
    
    if not rag.supabase:
        print("❌ Failed to initialize Supabase client.")
        return
    
    print("✓ Supabase client initialized.")
    
    # Test 1: Process a sample filing
    print("\n" + "=" * 60)
    print("TEST 1: Processing Sample Filing")
    print("=" * 60)
    
    # Use a fake filing ID for testing
    test_filing_id = 99999
    
    print(f"Processing {len(SAMPLE_FILING_TEXT)} characters of sample text...")
    success = await rag.process_filing(test_filing_id, SAMPLE_FILING_TEXT)
    
    if success:
        print("✓ Filing processed and chunks stored.")
    else:
        print("❌ Failed to process filing.")
        return
    
    # Test 2: Query the filing
    print("\n" + "=" * 60)
    print("TEST 2: Querying Filing")
    print("=" * 60)
    
    test_queries = [
        "What are the main risk factors?",
        "What was the revenue growth?",
        "What is the gross profit margin?",
    ]
    
    for query in test_queries:
        print(f"\n🔍 Query: \"{query}\"")
        answer = await rag.query_filing(test_filing_id, query)
        print(f"📝 Answer: {answer[:500]}...")
    
    # Cleanup: Delete test chunks
    print("\n" + "=" * 60)
    print("CLEANUP: Removing test data")
    print("=" * 60)
    
    try:
        rag.supabase.table("filing_chunks").delete().eq("filing_id", test_filing_id).execute()
        print(f"✓ Deleted test chunks for filing_id={test_filing_id}")
    except Exception as e:
        print(f"⚠️ Could not delete test data: {e}")
    
    print("\n" + "=" * 60)
    print("✅ RAG Pipeline Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

