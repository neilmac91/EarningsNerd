"""Compatibility facade for financial fact normalization, persistence, jobs and reads."""
# ruff: noqa: F401 -- preserve the complete existing import surface.
from __future__ import annotations
import asyncio
import logging
import math
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Optional
from app.services.event_loop import get_app_loop
from app.services.fact_provenance import fact_operand, provenance_for_fact, published_value
from app.services.facts.calendar import _fiscal_year_windows, _label_quarters, fiscal_duration_values, fiscal_year_labels, reported_fiscal_year
from app.services.facts.lineage import annotate_filing_calculations, authoritative_reconciliation, local_reconciliation
from app.services.facts.quarterly import (
    FINAL_QUARTER_WINDOW, QUARTER_WINDOW, derive_cumulative_quarters, derive_quarter_sum_fallback,
    reported_fact, same_period_provenance, same_scope,
)
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from app.models import Company, Filing, FinancialFact, Watchlist
from app.services.facts.concepts import (
    AFFECTED_FINANCIAL_CONCEPTS, COMPANYFACTS_DURATION_TAGS, COMPANYFACTS_INFLIGHT_WAIT_SECONDS,
    COMPANYFACTS_INSTANT_TAGS, COMPANYFACTS_SYNC_TIMEOUT_SECONDS, CROSS_CHECK_TOLERANCE, HEADLINE_GAAP_TAGS,
    NON_NEGATIVE_CONCEPTS, _CF_ANNUAL_WINDOW, _CF_QUARTER_WINDOW, _CF_YTD6_WINDOW, _CF_YTD9_WINDOW,
    _CONCEPT_UNITS, _FI_SKIPPED_CONCEPTS, _INSTANT_HEADLINE, _MAGNITUDE_TOLERANCE, _QUARTER_PERIODS, _VALID_FP,
    _classify_duration, _duration_start, _fiscal_period, _is_financial_sic, _parse_date, _unit_for,
)
from app.services.facts.companyfacts import _collect_companyfacts_values, normalize_companyfacts
from app.services.facts.derive import derive_q4_facts, derive_same_period_metrics
from app.services.facts.reconcile import _prior_values, cross_check_facts, extract_authoritative_values, reconcile_facts
from app.services.facts.upsert import (
    _lock_fact_companies, normalize_standardized_to_facts, process_filing_facts, upsert_facts,
    upsert_facts_bulk,
)
from app.services.facts.transport import (
    _fetch_companyfacts_async, _fetch_companyfacts_sync, _running_loop_in_this_thread, logger,
)
from app.services.facts.jobs import backfill_facts, remediate_industry_facts, backfill_company_sic, sync_companyfacts_batch
from app.services.facts.fundamentals import _fundamentals_payload, get_filing_fundamentals
from app.services.facts.ingest import (
    _inflight_syncs, _companyfacts_fresh_result, _persist_companyfacts_payload,
    ingest_companyfacts, ingest_companyfacts_by_id,
)

__all__ = [
    'AFFECTED_FINANCIAL_CONCEPTS', 'COMPANYFACTS_DURATION_TAGS', 'COMPANYFACTS_INFLIGHT_WAIT_SECONDS',
    'COMPANYFACTS_INSTANT_TAGS', 'COMPANYFACTS_SYNC_TIMEOUT_SECONDS', 'CROSS_CHECK_TOLERANCE',
    'HEADLINE_GAAP_TAGS', 'NON_NEGATIVE_CONCEPTS', '_CF_ANNUAL_WINDOW', '_CF_QUARTER_WINDOW',
    '_CF_YTD6_WINDOW', '_CF_YTD9_WINDOW', '_CONCEPT_UNITS', '_FI_SKIPPED_CONCEPTS', '_INSTANT_HEADLINE',
    '_MAGNITUDE_TOLERANCE', '_QUARTER_PERIODS', '_VALID_FP', '_classify_duration',
    '_collect_companyfacts_values', '_companyfacts_fresh_result', '_duration_start',
    '_fetch_companyfacts_async', '_fetch_companyfacts_sync', '_fiscal_period', '_fiscal_year_windows',
    '_fundamentals_payload', '_inflight_syncs', '_is_financial_sic', '_label_quarters', '_lock_fact_companies',
    '_parse_date', '_persist_companyfacts_payload', '_prior_values', '_running_loop_in_this_thread',
    '_unit_for', 'backfill_company_sic', 'backfill_facts', 'cross_check_facts', 'derive_q4_facts',
    'derive_same_period_metrics', 'extract_authoritative_values', 'get_filing_fundamentals',
    'ingest_companyfacts', 'ingest_companyfacts_by_id', 'logger', 'normalize_companyfacts',
    'normalize_standardized_to_facts', 'process_filing_facts', 'reconcile_facts', 'remediate_industry_facts',
    'sync_companyfacts_batch', 'upsert_facts', 'upsert_facts_bulk',
]
