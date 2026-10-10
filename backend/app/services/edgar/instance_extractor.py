"""Accession-aware XBRL instance extraction helpers (issue #240).

These helpers operate on an edgartools XBRL instance (``filing.xbrl()``) and
select facts for the filing's OWN reporting period: undimensioned
(consolidated) facts ending on the filing's period_of_report, with durations
matching the form's standard slice (12-month for a 10-K, 3-month for a 10-Q).

They generalize the single-fact selection in ``backend/evals/build_golden_set.py``
(the eval golden-set builder) into the series shape the product's XBRL service
returns, so the product and the eval harness ground on the same period and
duration semantics.

Kept dependency-light on purpose (no app config or edgartools imports): the
eval builder imports from here before app settings are loaded, and unit tests
exercise these functions with fake fact-query objects.
"""

from .debt_concepts import DEBT_COMPONENT_CONCEPTS as DEBT_COMPONENT_CONCEPTS
from .debt_concepts import classify_debt_concept as classify_debt_concept
from .instance.concepts import DIVIDEND_COMPONENT_CONCEPTS as DIVIDEND_COMPONENT_CONCEPTS
from .instance.concepts import DURATION_CONCEPTS as DURATION_CONCEPTS
from .instance.concepts import INSTANT_CONCEPTS as INSTANT_CONCEPTS
from .instance.concepts import RICHER_DURATION_CONCEPTS as RICHER_DURATION_CONCEPTS
from .instance.concepts import RICHER_INSTANT_CONCEPTS as RICHER_INSTANT_CONCEPTS
from .instance.core import _CONCEPT_NAMESPACES as _CONCEPT_NAMESPACES
from .instance.core import DURATION_WINDOWS as DURATION_WINDOWS
from .instance.core import _currency as _currency
from .instance.core import _fact_records_with_concept as _fact_records_with_concept
from .instance.core import _iso_date as _iso_date
from .instance.core import _numeric as _numeric
from .instance.core import _parse_decimals as _parse_decimals
from .instance.core import _reporting_currency as _reporting_currency
from .instance.core import _resolve_period_value as _resolve_period_value
from .instance.core import _series_from_values as _series_from_values
from .instance.core import _text_or_none as _text_or_none
from .instance.core import _unanimous_start as _unanimous_start
from .instance.core import duration_in_window as duration_in_window
from .instance.core import logger as logger
from .instance.core import normalize_form as normalize_form
from .instance.debt import _one_undimensioned_instant_fact as _one_undimensioned_instant_fact
from .instance.debt import debt_component_observations as debt_component_observations
from .instance.financial_profiles import FINANCIAL_PROFILES as FINANCIAL_PROFILES
from .instance.financial_profiles import FINANCIAL_SIC_HIGH as FINANCIAL_SIC_HIGH
from .instance.financial_profiles import FINANCIAL_SIC_LOW as FINANCIAL_SIC_LOW
from .instance.financial_profiles import cash_financial_classification as cash_financial_classification
from .instance.financial_profiles import is_financial_institution as is_financial_institution
from .instance.segments import _SEGMENT_MEMBER_SKIP as _SEGMENT_MEMBER_SKIP
from .instance.segments import SEGMENT_AXIS as SEGMENT_AXIS
from .instance.segments import _is_reportable_segment as _is_reportable_segment
from .instance.segments import _passes_consolidation_axis as _passes_consolidation_axis
from .instance.segments import _segment_fact_records as _segment_fact_records
from .instance.segments import _segment_member_label as _segment_member_label
from .instance.segments import segment_series_by_member as segment_series_by_member
from .instance.series import dividend_component_sum_series as dividend_component_sum_series
from .instance.series import duration_series as duration_series
from .instance.series import duration_series_currency_concept as duration_series_currency_concept
from .instance.series import duration_series_with_currency as duration_series_with_currency
from .instance.series import duration_series_with_starts as duration_series_with_starts
from .instance.series import instant_series as instant_series
from .instance.series import instant_series_currency_concept as instant_series_currency_concept
from .instance.series import instant_series_with_currency as instant_series_with_currency
from .instance.statements import _concept_local as _concept_local
from .instance.statements import _period_marker as _period_marker
from .instance.statements import _profile_required as _profile_required
from .instance.statements import _row_is_face_value as _row_is_face_value
from .instance.statements import _select_statement_series as _select_statement_series
from .instance.statements import _statement_period_columns as _statement_period_columns
from .instance.statements import _truthy_flag as _truthy_flag
from .instance.statements import extract_financial_statement_metrics as extract_financial_statement_metrics
from .instance.statements import income_statement_dataframe as income_statement_dataframe
from .instance.statements import match_financial_profile as match_financial_profile
