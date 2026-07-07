"""P0-3 guardrail (data-quality plan): the ASU 2016-18 restricted-cash tag in all three
cash registries, appended LAST.

`CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents` is the tag JPM (FY2019+) and
every large-bank ASU 2016-18 adopter migrated to; its absence truncated every big bank's cash
series at the migration year. LAST position is load-bearing: per-period first-tag-wins
(companyfacts) / first-candidate-wins (extractors) must keep pre-migration years on the legacy
unrestricted tags — zero churn — while post-migration years fill from the new tag. The three
lists deliberately differ in their OTHER members (IFRS names etc.), so this pins membership +
last position, not list equality.
"""
from app.services import facts_service
from app.services.edgar import instance_extractor, xbrl_service

RESTRICTED_CASH_TAG = "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"


def test_companyfacts_registry_has_tag_last():
    tags = facts_service.COMPANYFACTS_INSTANT_TAGS["cash_and_equivalents"]
    assert RESTRICTED_CASH_TAG in tags
    assert tags[-1] == RESTRICTED_CASH_TAG


def test_instance_extractor_registry_has_tag_last():
    tags = instance_extractor.INSTANT_CONCEPTS["cash_and_equivalents"]
    assert RESTRICTED_CASH_TAG in tags
    assert tags[-1] == RESTRICTED_CASH_TAG


def test_xbrl_service_statement_candidates_have_tag_last():
    tags = xbrl_service.CASH_TAG_CANDIDATES
    assert RESTRICTED_CASH_TAG in tags
    assert tags[-1] == RESTRICTED_CASH_TAG


def test_legacy_tags_precede_the_restricted_total_everywhere():
    for tags in (
        facts_service.COMPANYFACTS_INSTANT_TAGS["cash_and_equivalents"],
        instance_extractor.INSTANT_CONCEPTS["cash_and_equivalents"],
        xbrl_service.CASH_TAG_CANDIDATES,
    ):
        tag_list = list(tags)
        restricted_idx = tag_list.index(RESTRICTED_CASH_TAG)
        # EVERY other (legacy/unrestricted) tag must precede the restricted total, so
        # first-tag-wins never lets the restricted total shadow an unrestricted value.
        for i, tag in enumerate(tag_list):
            if tag != RESTRICTED_CASH_TAG:
                assert i < restricted_idx, tag
