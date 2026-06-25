"""Phase 2: 20-F (foreign private issuer) annual-summary wiring.

Guards that a 20-F is summarized with the 20-F prompt + 20-F section layout/budget — not silently
with 10-K assumptions — and that the explicit prompt fallback covers forms without a prompt yet
(e.g. 6-K before Phase 4). See tasks/fpi-support-roadmap.md.
"""

from app.services import prompt_loader
from app.services.openai_service import openai_service


class TestPromptSelection:
    def test_20f_analyst_prompt_selected(self):
        p = prompt_loader.get_prompt("20-F")
        assert p is prompt_loader._PROMPTS["20-F"]
        assert p is not prompt_loader._PROMPTS["10-K"]
        # It really is the 20-F prompt (references the foreign annual form).
        assert "20-F" in p.raw

    def test_20f_hyphenless_normalizes(self):
        assert prompt_loader._normalize_filing_type("20F") == "20-F"
        assert prompt_loader.get_prompt("20f") is prompt_loader._PROMPTS["20-F"]

    def test_20f_structured_prompt_selected(self):
        s = prompt_loader.get_structured_prompt("20-F")
        assert s == prompt_loader._STRUCTURED_PROMPTS["20-F"]
        # The structured prompt enforces the native-currency rule.
        assert "USD" in s

    def test_unknown_form_falls_back_to_10k(self):
        # 6-K has no dedicated prompt yet (Phase 4) → explicit, logged 10-K fallback (not silent).
        assert prompt_loader.get_prompt("6-K") is prompt_loader._PROMPTS["10-K"]


class TestSectionConfig:
    def test_section_layout_has_20f(self):
        layout = openai_service._SECTION_LAYOUT["20-F"]
        canon = [c for c, _, _ in layout]
        assert canon == ["financials", "mda", "risk"]
        labels = " ".join(label for _, label, _ in layout)
        # 20-F item numbers, not 10-K's (Item 8/7/1A).
        assert "ITEM 18" in labels and "ITEM 5" in labels and "ITEM 3" in labels

    def test_type_config_20f_budget(self):
        cfg = openai_service._get_type_config("20-F")
        # 20-F gets the generous 10-K-sized budget, not the smaller base/10-Q one.
        assert cfg["max_tokens"] == 12000
        assert cfg["ai_timeout"] == 150.0
        assert cfg["sample_length"] == 100000

    def test_assemble_excerpt_uses_20f_labels(self):
        sections = {
            "financials": "F" * 600,
            "mda": "M" * 600,
            "risk": "R" * 600,
        }
        excerpt = openai_service.assemble_excerpt_from_sections(sections, "20-F")
        assert "ITEM 18 - FINANCIAL STATEMENTS" in excerpt
        assert "ITEM 5 - OPERATING AND FINANCIAL REVIEW" in excerpt
        assert "ITEM 3.D - RISK FACTORS" in excerpt
        # Must NOT mislabel with 10-K item numbers.
        assert "ITEM 8 - FINANCIAL STATEMENTS AND SUPPLEMENTARY DATA" not in excerpt
