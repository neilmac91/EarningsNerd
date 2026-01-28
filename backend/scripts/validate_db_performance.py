#!/usr/bin/env python3
"""
Database Performance Validation Script for EarningsNerd.

Validates PostgreSQL Basic-1gb performance by running benchmark queries.
Run this script after database upgrades to ensure performance baselines.

Usage:
    python scripts/validate_db_performance.py

Environment:
    DATABASE_URL: PostgreSQL connection string

Expected Results (Basic-1gb instance):
    - Simple SELECT: < 5ms
    - Index scan: < 10ms
    - Connection establishment: < 100ms
    - Connection pool health: All connections valid
"""

import os
import sys
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()


def get_database_url():
    """Get database URL from environment."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    return url


def measure_operation(operation_func, description: str) -> tuple[float, any]:
    """
    Measure the execution time of an operation.

    Args:
        operation_func: Callable to execute and time
        description: Description for logging

    Returns:
        Tuple of (elapsed_ms, result)
    """
    start = time.perf_counter()
    try:
        result = operation_func()
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"  {description}: {elapsed_ms:.2f}ms")
        return elapsed_ms, result
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"  {description}: FAILED after {elapsed_ms:.2f}ms - {e}")
        raise


def run_validation():
    """Run database performance validation."""
    print("=" * 60)
    print("PostgreSQL Performance Validation")
    print("=" * 60)
    print()

    database_url = get_database_url()

    # Mask password in output
    masked_url = database_url
    if "@" in masked_url:
        parts = masked_url.split("@")
        if ":" in parts[0]:
            user_pass = parts[0].split(":")
            if len(user_pass) > 1:
                masked_url = f"{user_pass[0]}:****@{'@'.join(parts[1:])}"

    print(f"Database: {masked_url}")
    print()

    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.exc import SQLAlchemyError, OperationalError, InterfaceError
    except ImportError:
        print("ERROR: SQLAlchemy not installed. Run: pip install sqlalchemy")
        sys.exit(1)

    # Create engine with production-like settings
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=False
    )

    Session = sessionmaker(bind=engine)

    results = {
        "connection": None,
        "simple_select": None,
        "count_query": None,
        "pool_health": None,
    }

    print("1. Connection Establishment")
    print("-" * 40)
    try:
        start = time.perf_counter()
        conn = engine.connect()
        results["connection"] = (time.perf_counter() - start) * 1000
        print(f"  Connection established: {results['connection']:.2f}ms")

        if results["connection"] < 100:
            print("  ✅ PASS (< 100ms)")
        else:
            print("  ⚠️  SLOW (> 100ms)")
        conn.close()
    except OperationalError as e:
        print(f"  ❌ FAILED (connection error): {e}")
        sys.exit(1)
    except InterfaceError as e:
        print(f"  ❌ FAILED (interface error): {e}")
        sys.exit(1)
    except SQLAlchemyError as e:
        print(f"  ❌ FAILED (database error): {e}")
        sys.exit(1)

    print()
    print("2. Simple SELECT Query")
    print("-" * 40)
    try:
        session = Session()
        start = time.perf_counter()
        result = session.execute(text("SELECT 1"))
        result.fetchone()
        results["simple_select"] = (time.perf_counter() - start) * 1000
        print(f"  SELECT 1: {results['simple_select']:.2f}ms")

        if results["simple_select"] < 5:
            print("  ✅ PASS (< 5ms)")
        else:
            print("  ⚠️  SLOW (> 5ms)")
        session.close()
    except SQLAlchemyError as e:
        print(f"  ❌ FAILED (database error): {e}")

    print()
    print("3. Table Count Query")
    print("-" * 40)
    try:
        session = Session()

        # Check if tables exist
        tables_result = session.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        ))
        tables = [row[0] for row in tables_result.fetchall()]

        if not tables:
            print("  No tables found in database")
        else:
            print(f"  Found {len(tables)} tables: {', '.join(tables[:5])}...")

            # Try counting from a common table
            for table in ["companies", "filings", "users", "summaries"]:
                if table in tables:
                    start = time.perf_counter()
                    count_result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = count_result.fetchone()[0]
                    elapsed = (time.perf_counter() - start) * 1000
                    print(f"  COUNT({table}): {count} rows in {elapsed:.2f}ms")

                    if elapsed < 50:
                        print(f"  ✅ PASS (< 50ms)")
                    else:
                        print(f"  ⚠️  SLOW (> 50ms)")

                    results["count_query"] = elapsed
                    break

        session.close()
    except SQLAlchemyError as e:
        print(f"  ❌ FAILED (database error): {e}")

    print()
    print("4. Connection Pool Health")
    print("-" * 40)
    try:
        pool = engine.pool
        print(f"  Pool size: {pool.size()}")
        print(f"  Checked out: {pool.checkedout()}")
        print(f"  Overflow: {pool.overflow()}")
        print(f"  Checked in: {pool.checkedin()}")

        # Test multiple concurrent connections
        connections = []
        start = time.perf_counter()
        for i in range(5):
            conn = engine.connect()
            connections.append(conn)

        pool_time = (time.perf_counter() - start) * 1000
        print(f"  5 concurrent connections: {pool_time:.2f}ms")

        for conn in connections:
            conn.close()

        if pool_time < 500:
            print("  ✅ PASS (< 500ms)")
        else:
            print("  ⚠️  SLOW (> 500ms)")

        results["pool_health"] = pool_time
    except SQLAlchemyError as e:
        print(f"  ❌ FAILED (database error): {e}")

    print()
    print("5. Index Check")
    print("-" * 40)
    try:
        session = Session()
        index_result = session.execute(text(
            "SELECT indexname, tablename FROM pg_indexes "
            "WHERE schemaname = 'public' LIMIT 10"
        ))
        indexes = index_result.fetchall()

        if indexes:
            print(f"  Found {len(indexes)} indexes:")
            for idx in indexes[:5]:
                print(f"    - {idx[1]}.{idx[0]}")
        else:
            print("  No indexes found (consider adding indexes for better performance)")

        session.close()
    except SQLAlchemyError as e:
        print(f"  ❌ FAILED (database error): {e}")

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_pass = True
    if results["connection"] and results["connection"] < 100:
        print("✅ Connection: PASS")
    else:
        print("⚠️  Connection: NEEDS ATTENTION")
        all_pass = False

    if results["simple_select"] and results["simple_select"] < 5:
        print("✅ Simple SELECT: PASS")
    else:
        print("⚠️  Simple SELECT: NEEDS ATTENTION")
        all_pass = False

    if results["pool_health"] and results["pool_health"] < 500:
        print("✅ Connection Pool: PASS")
    else:
        print("⚠️  Connection Pool: NEEDS ATTENTION")
        all_pass = False

    print()
    if all_pass:
        print("🎉 All performance checks PASSED!")
        print("PostgreSQL Basic-1gb is performing within expected parameters.")
    else:
        print("⚠️  Some checks need attention.")
        print("Review the results above and consider database optimization.")

    return all_pass


if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1)
