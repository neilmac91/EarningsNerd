"""section_diff: the deterministic Item 1A wording diff (pure; synthetic paragraphs only).

The gates the 2026-10 "what changed" plan set for the engine, each as a test: a deleted
paragraph is always reported; a known edit yields one modified item with word ops; typographic
and pagination differences yield nothing; near-edits pair at 80 % or better; items come back in
reading order with content-addressed ids.
"""
import json

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
            "12\n\nOur products may \n\ncontain defects that could harm our reputation."
        )
        paragraphs, excluded = sd.split_paragraphs(wrapped)
        assert _texts(paragraphs) == [P1, P2]
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

    def test_lowercase_continuation_joins_even_without_a_trailing_space(self):
        paragraphs, _ = sd.split_paragraphs(
            "We depend on a small number of customers for a large\n\nshare of our revenue."
        )
        assert _texts(paragraphs) == [P1]

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
        prior = _text("ITEM 1A. RISK FACTORS", P1, "5", P5, "Example Corp | 2024 Form 10-K | 6", P3)
        later = _text(
            "Item 1A.  Risk Factors",
            "We depend on a small number of cus­tomers for a large share of our revenue.",
            "6",
            "The “Company” — as defined above — relies on third‑party suppliers for key inputs.",
            "Example Corp | 2025 Form 10-K | 7",
            "We face intense competition, and competitors may have greater\nresources than we do.",
        )
        result = sd.diff_sections(prior, later)
        assert result["has_changes"] is False, result["items"]
        assert result["counts"]["unchanged"] == 3
        assert result["words"]["changed_ratio"] == 0.0

    def test_moved_paragraph_is_reported_once_as_moved(self):
        result = sd.diff_sections(_text(P1, P2, P3, P4), _text(P2, P3, P4, P1))
        assert _kinds(result) == ["moved"]
        assert result["items"][0]["after"] == P1
        assert result["counts"] == {"unchanged": 3, "modified": 0, "added": 0, "removed": 0, "moved": 1}

    def test_a_repeated_paragraph_pairs_in_order(self):
        result = sd.diff_sections(_text(P1, P2, P1), _text(P1, P2, P1))
        assert result["has_changes"] is False


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
            words[4] = "might"  # "may" -> "might"
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
