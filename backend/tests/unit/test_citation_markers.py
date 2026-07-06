"""Shared citation-marker group knowledge (citation_markers.py): the trend resolver's group
classification and the copilot pre-pass that splits multi-reference groups."""
import time

from app.services import citation_markers as cm


def copilot_expand(text: str) -> str:
    """The exact configuration copilot_service uses (shared constants, not a copy)."""
    return cm.expand_citation_marker_groups(
        text,
        ref_re=cm.COPILOT_GROUP_MEMBER_RE,
        normalize=cm.copilot_normalize_ref,
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

    def test_thousands_figure_beside_a_fact_marker_never_splits(self):
        # Review finding: with the F-ref present, require_re passes — the 2-digit plain-member
        # cap must make the leftover digits fail the purity check so "1,234" is never mangled.
        text = "Backlog was [F1, 1,234] units."
        assert copilot_expand(text) == text

    def test_space_and_case_tolerant_members_normalize(self):
        assert copilot_expand("[f 1, F2]") == "[F1] [F2]"

    def test_linear_on_degenerate_whitespace_runs(self):
        # House rule: these patterns scan model output on the event loop — a quadratic member
        # regex (the original F?\s*\d+) measured seconds on inputs like this.
        text = "[" + " " * 20000 + "1]"
        started = time.perf_counter()
        copilot_expand(text)
        assert time.perf_counter() - started < 0.5