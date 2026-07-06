"""Shared citation-marker group knowledge (citation_markers.py): the trend resolver's group
classification and the copilot pre-pass that splits multi-reference groups."""
import re

from app.services import citation_markers as cm

# The copilot configuration: members may be "F1" (tool fact) or "1" (text excerpt); groups only
# expand when at least one F-ref is present (an all-plain group could be a bracketed thousands
# figure).
COPILOT_MEMBER_RE = re.compile(r"(F?\s*\d+)", re.IGNORECASE)


def copilot_expand(text: str) -> str:
    return cm.expand_citation_marker_groups(
        text,
        ref_re=COPILOT_MEMBER_RE,
        normalize=lambda ref: re.sub(r"\s+", "", ref).upper(),
        require_re=cm.MARKER_REF_RE,
    )


class TestIsCitationGroup:
    def test_lists_ranges_and_comparisons_are_citation_groups(self):
        for content in ("F1, F2", "F1..F10", "F1-F2", "F9 vs F10", "F1 and F2", "F1 through F3"):
            assert cm.is_citation_group(content) is True

    def test_prose_containing_an_f_token_is_not(self):
        assert cm.is_citation_group("see F1 in the appendix") is False


class TestExpandGroups:
    def test_comma_list_splits_into_single_brackets(self):
        assert cm.expand_citation_marker_groups("Margins fell [F58, F59].") == (
            "Margins fell [F58] [F59]."
        )

    def test_range_keeps_written_endpoints_only(self):
        # Expansion never invents members the model didn't write.
        assert cm.expand_citation_marker_groups("Steady growth [F1..F10].") == (
            "Steady growth [F1] [F10]."
        )

    def test_comparison_splits_both_sides(self):
        assert cm.expand_citation_marker_groups("[F9 vs F10]") == "[F9] [F10]"

    def test_duplicates_within_a_group_collapse(self):
        assert cm.expand_citation_marker_groups("[F1, F1, F2]") == "[F1] [F2]"

    def test_single_markers_and_prose_untouched(self):
        text = "Revenue [F3] grew (see [the 2024 notes]) [F4]."
        assert cm.expand_citation_marker_groups(text) == text

    def test_leading_zeros_canonicalize(self):
        assert cm.expand_citation_marker_groups("[F01, F2]") == "[F1] [F2]"


class TestCopilotConfiguration:
    def test_mixed_fact_and_text_group_expands(self):
        assert copilot_expand("Both sources agree [F1, 2].") == "Both sources agree [F1] [2]."

    def test_all_plain_group_never_expands(self):
        # Could be a bracketed thousands figure — and plain multi-refs staying literal is the
        # copilot resolver's pinned behavior.
        for text in ("Backlog of [1,234] units.", "See [1, 2]."):
            assert copilot_expand(text) == text

    def test_space_and_case_tolerant_members_normalize(self):
        assert copilot_expand("[f 1, F2]") == "[F1] [F2]"