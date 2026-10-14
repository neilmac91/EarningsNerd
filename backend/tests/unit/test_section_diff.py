"""section_diff: the deterministic Item 1A wording diff (pure; synthetic paragraphs only).

The gates the 2026-10 "what changed" plan set for the engine, each as a test: a deleted
paragraph is always reported; a known edit yields one modified item with word ops; typographic
and pagination differences yield nothing; near-edits pair at 80 % or better; items come back in
reading order with content-addressed ids. The fixtures pin each normalization and each re-flow
stop rule on its own, and the pairing threshold from both sides (a near-edit at 0.69 pairs, an
unrelated rewrite at 0.4 does not), so a loosened or tightened constant fails here.
"""
import json

import pytest

from app.services import section_diff as sd

P1 = "We depend on a small number of customers for a large share of our revenue."
P2 = "Our products may contain defects that could harm our reputation."
P3 = "We face intense competition, and competitors may have greater resources than we do."
P4 = "Changes in tax law could increase our effective tax rate."
P5 = 'The "Company" - as defined above - relies on third-party suppliers for key inputs.'


def _text(*paragraphs):
    return "\n\n".join(paragraphs)


def _texts(paragraphs):
    return [p.text for p in paragraphs]


def _kinds(result):
    return [item["kind"] for item in result["items"]]


def _reconstruct(ops, keep):
    return " ".join(segment for kind, segment in ops if kind in ("equal", keep))


class TestSplitParagraphs:
    def test_drops_page_furniture_and_counts_it_by_class(self):
        text = _text(
            "Item 1A. Risk Factors", P1, "7", "Example Corp | 2025 Form 10-K | 8",
            "Table of Contents", P2, "Part I", "iv", P3,
        )
        paragraphs, excluded = sd.split_paragraphs(text)
        assert _texts(paragraphs) == [P1, P2, P3]
        assert excluded == {"page_number": 2, "running_header": 3, "section_heading": 1}

    def test_section_heading_variants_are_excluded(self):
        for heading in ("ITEM 1A. RISK FACTORS", "Item\u00a01A\u2014Risk Factors", "Item 1A.\u00a0\u00a0\u00a0Risk Factors", "Item 1A - Risk Factors"):
            paragraphs, excluded = sd.split_paragraphs(_text(heading, P1))
            assert _texts(paragraphs) == [P1], heading
            assert excluded == {"section_heading": 1}, heading

    def test_repeated_company_banner_is_a_running_header(self):
        banner = "EXAMPLE HOLDINGS, INC. AND SUBSIDIARIES"
        paragraphs, excluded = sd.split_paragraphs(_text(banner, P1, banner, P2, banner, P3))
        assert _texts(paragraphs) == [P1, P2, P3]
        assert excluded == {"running_header": 3}

    def test_a_heading_seen_once_is_prose(self):
        paragraphs, excluded = sd.split_paragraphs(_text("Risks Related to Our Business", P1))
        assert _texts(paragraphs) == ["Risks Related to Our Business", P1]
        assert excluded == {}

    def test_reflows_line_wrapped_typesetting_across_a_page_break(self):
        wrapped = (
            "We depend on a small number of customers for a large \n\nshare of our revenue.\n\n"
            "12\n\nOur products may \n\ncontain defects that could harm our reputation.\n\n"
            "Our largest customers include \n\nApple and other companies of that size."
        )
        paragraphs, excluded = sd.split_paragraphs(wrapped)
        # A capitalized continuation joins too: only the trailing space says the line wrapped.
        assert _texts(paragraphs) == [P1, P2, "Our largest customers include Apple and other companies of that size."]
        assert excluded == {"page_number": 1}

    def test_reflow_stops_at_sentence_ends_colons_and_bullets(self):
        text = (
            "Product candidates may fail for many reasons, including: \n\n"
            "• pricing;\n\n• competition.\n\n"
            "Our products may contain defects. \n\nWe face intense competition."
        )
        paragraphs, _ = sd.split_paragraphs(text)
        assert _texts(paragraphs) == [
            "Product candidates may fail for many reasons, including:",
            "• pricing;",
            "• competition.",
            "Our products may contain defects.",
            "We face intense competition.",
        ]

    def test_each_reflow_stop_rule_holds_on_its_own(self):
        # A sentence end stops a lowercase continuation (an "iPhone"-style start is not a wrap).
        paragraphs, _ = sd.split_paragraphs(_text("We sell one product line.", "iPhone sales dominate it."))
        assert _texts(paragraphs) == ["We sell one product line.", "iPhone sales dominate it."]
        # A colon ends a wrapped line even though the line ends in a space.
        paragraphs, _ = sd.split_paragraphs("Risks include the following: \n\nPricing pressure may \n\nreduce margins.")
        assert _texts(paragraphs) == ["Risks include the following:", "Pricing pressure may reduce margins."]
        # A bullet never glues onto the wrapped line before it.
        paragraphs, _ = sd.split_paragraphs("Our risks include \n\n• pricing; \n\nand more.")
        assert _texts(paragraphs) == ["Our risks include", "• pricing;", "and more."]

    @pytest.mark.parametrize("glyph", ["•", "\uf0b7", "§", "–", "-", "o"])
    def test_every_bullet_glyph_stops_a_reflow(self, glyph):
        text = (
            f"Product candidates may fail for many reasons such as \n\n{glyph} pricing; \n\n"
            f"{glyph} competition. \n\nWe face intense competition."
        )
        paragraphs, _ = sd.split_paragraphs(text)
        assert _texts(paragraphs) == [
            "Product candidates may fail for many reasons such as",
            f"{glyph} pricing;",
            f"{glyph} competition.",
            "We face intense competition.",
        ]

    def test_lowercase_continuation_joins_even_without_a_trailing_space(self):
        paragraphs, _ = sd.split_paragraphs(
            "We depend on a small number of customers for a large\n\nshare of our revenue."
        )
        assert _texts(paragraphs) == [P1]

    def test_a_trailing_space_in_an_ordinary_document_merges_nothing(self):
        paragraphs, _ = sd.split_paragraphs(_text("Risks Related to Our Business ", P1, P2, P3))
        assert _texts(paragraphs) == ["Risks Related to Our Business", P1, P2, P3]

    def test_line_wrapped_documents_join_a_hyphenated_break_without_a_space(self):
        wrapped = "Our forward- \n\nlooking statements may \n\nprove wrong.\n\nWe face intense \n\ncompetition."
        paragraphs, _ = sd.split_paragraphs(wrapped)
        assert _texts(paragraphs) == ["Our forward-looking statements may prove wrong.", "We face intense competition."]

    def test_inner_newlines_nbsp_and_bullet_spacing_normalize(self):
        paragraphs, _ = sd.split_paragraphs(
            "We depend on a small\nnumber of customers for a large share of our revenue.\n\n•pricing;"
        )
        assert _texts(paragraphs) == [P1, "• pricing;"]


class TestExactPairing:
    def test_identical_sections_have_no_changes(self):
        result = sd.diff_sections(_text(P1, P2, P3), _text(P1, P2, P3))
        assert result["has_changes"] is False
        assert result["items"] == []
        assert result["counts"] == {"unchanged": 3, "modified": 0, "added": 0, "removed": 0, "moved": 0}

    def test_format_only_differences_are_not_changes(self):
        prior = _text(
            "ITEM 1A. RISK FACTORS", P1, "5", P5, "Example Corp | 2024 Form 10-K | 6", P3,
            "Page 7", "We don't control our suppliers' pricing.", "Example Corp 2024 Form 10-K 8",
            "• Our office leases expire in 2027.", "Our financial statements reflect these risks.",
        )
        later = _text(
            "Item 1A.  Risk Factors",
            "We depend on a small number of cus\u00adtomers for a large share of our revenue.",
            "6",
            "The \u201cCompany\u201d \u2014 as defined above \u2014 relies on third\u2011party suppliers for key inputs.",
            "Example Corp | 2025 Form 10-K | 7",
            "We face intense competition, and competitors may have greater\nresources than we do.",
            "Page 8",
            "We don\u2019t control our suppliers\u2019 pricing.",          # curly apostrophes
            "Example Corp 2025 Form 10-K 9",                               # running header without pipes
            "Our office leases expire in 2027.",                           # bullet glyph dropped
            "Our \ufb01nancial statements re\ufb02ect these risks.",         # fi / fl ligatures (NFKC)
        )
        result = sd.diff_sections(prior, later)
        assert result["has_changes"] is False, result["items"]
        assert result["counts"]["unchanged"] == 6
        assert result["words"]["changed_ratio"] == 0.0
        assert result["paragraphs"]["later_excluded"] == {"page_number": 2, "running_header": 2, "section_heading": 1}

    def test_zero_width_characters_inside_a_word_are_not_changes(self):
        later = P1.replace("customers", "cus\u200btomers")
        assert sd.diff_sections(_text(P1, P2), _text(later, P2))["has_changes"] is False

    def test_moved_paragraph_is_reported_once_as_moved(self):
        result = sd.diff_sections(_text(P1, P2, P3, P4), _text(P2, P3, P4, P1))
        assert _kinds(result) == ["moved"]
        assert result["items"][0]["after"] == P1
        assert result["counts"] == {"unchanged": 3, "modified": 0, "added": 0, "removed": 0, "moved": 1}

    def test_a_repeated_paragraph_pairs_in_order(self):
        result = sd.diff_sections(_text(P1, P2, P1), _text(P1, P2, P1))
        assert result["has_changes"] is False

    def test_a_dropped_repeat_is_removed_not_moved(self):
        result = sd.diff_sections(_text(P1, P2, P1), _text(P1, P1))
        assert _kinds(result) == ["removed"] and result["items"][0]["before"] == P2
        assert result["counts"]["unchanged"] == 2 and result["counts"]["moved"] == 0

    def test_a_summary_bullet_and_its_body_heading_pair_in_place(self):
        """A "Summary of Risk Factors" bullet repeats the body heading it points at (same key once
        the bullet glyph is dropped). An edit to the bullet must not be charged to the heading."""
        heading = "Risks Related to Our Industry"
        prior = _text(f"• {heading}", P1, heading, P2)
        # Bullet dropped: only the bullet is reported; the heading stays paired where it is.
        result = sd.diff_sections(prior, _text(P1, heading, P2))
        assert [(i["kind"], i["before"]) for i in result["items"]] == [("removed", f"• {heading}")]
        assert result["counts"] == {"unchanged": 3, "modified": 0, "added": 0, "removed": 1, "moved": 0}
        # Bullet reworded: one modified item in place, nothing moved.
        result = sd.diff_sections(prior, _text(f"• {heading} and Our Markets", P1, heading, P2))
        assert _kinds(result) == ["modified"] and result["items"][0]["moved"] is False
        assert result["items"][0]["prior_index"] == 0 and result["items"][0]["index"] == 0
        # Bullet added in front of an existing heading: one added item.
        result = sd.diff_sections(_text(P1, heading, P2), prior)
        assert [(i["kind"], i["after"]) for i in result["items"]] == [("added", f"• {heading}")]
        assert result["counts"]["moved"] == 0

    def test_exact_pairing_falls_back_to_first_occurrence_above_the_cell_cap(self, monkeypatch):
        monkeypatch.setattr(sd, "_LCS_CELL_CAP", 1)
        assert sd.diff_sections(_text(P1, P2, P3), _text(P1, P2, P3))["has_changes"] is False
        result = sd.diff_sections(_text(P1, P2, P3), _text(P1, P3))
        assert _kinds(result) == ["removed"] and result["counts"]["unchanged"] == 2


class TestFuzzyPairing:
    def test_small_edit_is_one_modified_item_with_word_ops(self):
        edited = P1.replace("a small number", "a limited number")
        result = sd.diff_sections(_text(P1, P2, P3), _text(P1.replace("a small number", "a limited number"), P2, P3))
        assert _kinds(result) == ["modified"]
        item = result["items"][0]
        assert item["similarity"] >= 0.9 and item["moved"] is False
        assert ["delete", "small"] in item["ops"] and ["insert", "limited"] in item["ops"]
        assert _reconstruct(item["ops"], "delete") == P1
        assert _reconstruct(item["ops"], "insert") == edited
        assert result["counts"]["modified"] == 1 and result["counts"]["unchanged"] == 2
        assert result["words"]["inserted"] == 1 and result["words"]["deleted"] == 1

    def test_deleted_paragraph_is_always_reported_where_it_sat(self):
        result = sd.diff_sections(_text(P1, P2, P3), _text(P1, P3))
        assert _kinds(result) == ["removed"]
        assert result["items"][0]["before"] == P2 and result["items"][0]["prior_index"] == 1
        assert result["counts"]["removed"] == 1
        assert result["has_changes"] is True  # a deletion alone is a change

    def test_added_paragraph_is_reported_in_reading_order(self):
        result = sd.diff_sections(_text(P1, P3), _text(P1, P4, P3))
        assert _kinds(result) == ["added"]
        assert result["items"][0]["after"] == P4 and result["items"][0]["index"] == 1

    def test_items_follow_the_later_section_order(self):
        result = sd.diff_sections(_text(P1, P2, P3, P4), _text(P4, P1.replace("small", "modest"), P3))
        # P4 moved to the front, P1 edited, P2 gone (anchored after P1's new position), P3 kept.
        assert [(i["kind"], i.get("index", i.get("prior_index"))) for i in result["items"]] == [
            ("moved", 0), ("modified", 1), ("removed", 1),
        ]

    def test_an_unrelated_rewrite_is_added_plus_removed_not_modified(self):
        result = sd.diff_sections(_text(P1, P2), _text(P1, P4))
        assert sorted(_kinds(result)) == ["added", "removed"]
        # Sharing a clause is not enough: "could harm our reputation" overlaps at a ratio of 0.4.
        overlapping = "Product recalls could harm our reputation and reduce our revenue."
        result = sd.diff_sections(_text(P1, P2), _text(P1, overlapping))
        assert sorted(_kinds(result)) == ["added", "removed"]

    def test_the_pairing_threshold_admits_clause_level_edits(self):
        """Edits well below the 80 % gate still pair (the threshold is 0.6): a five-word insertion
        near 0.9, three replaced words near 0.77, four near 0.69."""
        edits = [
            (P3.replace("greater resources", "greater resources and brand recognition"), 0.85, 0.91),
            ("We face intense competition, and rivals may have deeper pockets than we do.", 0.7, 0.8),
            ("We face intense competition, and rivals may enjoy deeper pockets than we do.", 0.6, 0.7),
        ]
        for edited, low, high in edits:
            result = sd.diff_sections(_text(P1, P3), _text(P1, edited))
            assert _kinds(result) == ["modified"], (edited, _kinds(result))
            assert low <= result["items"][0]["similarity"] < high, (edited, result["items"][0]["similarity"])

    def test_near_edits_pair_at_least_80_percent(self):
        base = [
            f"Risk {n}: our {noun} may be adversely affected by {cause}, which could reduce our revenue and harm our results."
            for n, (noun, cause) in enumerate([
                ("supply chain", "tariffs"), ("data centers", "power shortages"), ("employees", "wage inflation"),
                ("intellectual property", "litigation"), ("brand", "product recalls"), ("liquidity", "credit markets"),
                ("customers", "economic downturns"), ("operations", "natural disasters"), ("software", "security incidents"),
                ("pricing", "competition"), ("margins", "input costs"), ("growth", "regulation"),
                ("reputation", "misinformation"), ("facilities", "climate events"), ("capital", "interest rates"),
                ("systems", "outages"), ("partners", "contract disputes"), ("taxes", "new legislation"),
                ("insurance", "coverage limits"), ("forecasts", "demand volatility"),
            ])
        ]
        edits = []
        for n, paragraph in enumerate(base):
            words = paragraph.split()
            words[4] = "might"  # one word replaced (the fifth, whatever it is)
            if n % 2:
                words.insert(-2, "materially")
            edits.append(" ".join(words))
        result = sd.diff_sections(_text(*base), _text(*edits))
        assert result["counts"]["modified"] >= 16
        assert result["counts"]["added"] + result["counts"]["removed"] <= 4
        assert all(item["similarity"] >= sd.PAIR_THRESHOLD for item in result["items"] if item["kind"] == "modified")

    def test_global_best_first_pairs_the_closer_twin(self):
        close = P1.replace("small", "modest")
        far = P1.replace("small number of customers", "handful of distributors and resellers")
        result = sd.diff_sections(_text(far, close), _text(close.replace("revenue", "revenues")))
        modified = [i for i in result["items"] if i["kind"] == "modified"]
        assert len(modified) == 1 and modified[0]["prior_index"] == 1
        assert [i["before"] for i in result["items"] if i["kind"] == "removed"] == [far]


class TestOutput:
    def test_ids_are_stable_and_content_addressed(self):
        first = sd.diff_sections(_text(P1, P2), _text(P1.replace("small", "modest"), P2, P4))
        second = sd.diff_sections(_text(P1, P2), _text(P1.replace("small", "modest"), P2, P4))
        assert [i["id"] for i in first["items"]] == [i["id"] for i in second["items"]]
        other = sd.diff_sections(_text(P1, P2), _text(P1.replace("small", "tiny"), P2, P4))
        assert first["items"][0]["id"] != other["items"][0]["id"]
        assert first["items"][1]["id"] == other["items"][1]["id"]  # the unchanged addition keeps its id

    def test_repeated_content_gets_distinct_stable_ids(self):
        result = sd.diff_sections(_text(P1), _text(P1, P4, P4))
        ids = [i["id"] for i in result["items"]]
        assert _kinds(result) == ["added", "added"] and len(set(ids)) == 2
        assert ids == [i["id"] for i in sd.diff_sections(_text(P1), _text(P1, P4, P4))["items"]]
        heading = "Risks Related to Our Industry"
        removed = sd.diff_sections(_text(f"• {heading}", P1, heading), _text(P1))
        assert _kinds(removed) == ["removed", "removed"]
        assert len({i["id"] for i in removed["items"]}) == 2  # same key, told apart by occurrence

    def test_equal_segments_carry_the_later_typography(self):
        before = "We don\u2019t control pricing, and that could harm our margins."
        after = "We don't control pricing, and that could reduce our margins."
        item = sd.diff_sections(_text(before), _text(after))["items"][0]
        assert item["kind"] == "modified"
        assert _reconstruct(item["ops"], "insert") == after
        # The prior comes back in the later filing's typography (a straight apostrophe here).
        assert _reconstruct(item["ops"], "delete") == before.replace("\u2019", "'")

    def test_word_counts_and_changed_ratio(self):
        result = sd.diff_sections(_text(P1, P2), _text(P1, P4))
        later_total = len(P1.split()) + len(P4.split())
        assert result["words"] == {
            "later_total": later_total,
            "inserted": len(P4.split()),
            "deleted": len(P2.split()),
            "changed_ratio": round((len(P4.split()) + len(P2.split())) / later_total, 4),
        }
        assert result["paragraphs"]["prior"] == 2 and result["paragraphs"]["later"] == 2

    def test_output_is_json_serializable_and_versioned(self):
        result = sd.diff_sections(_text(P1, P2), _text(P2, P3))
        assert json.loads(json.dumps(result))["engine_version"] == sd.ENGINE_VERSION

    def test_empty_inputs(self):
        assert sd.diff_sections("", "")["has_changes"] is False
        result = sd.diff_sections("", P1)
        assert _kinds(result) == ["added"] and result["words"]["changed_ratio"] == 1.0
        assert _kinds(sd.diff_sections(P1, "")) == ["removed"]
