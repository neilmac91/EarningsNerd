"""Unit tests for the Filing Pulse composition (calm, sourced sentiment view)."""

from app.services import pulse_service as pulse


class TestPulseTier:
    def test_tiers_by_score(self):
        assert pulse.pulse_tier(0.0) == "Quiet"
        assert pulse.pulse_tier(2.9) == "Quiet"
        assert pulse.pulse_tier(3.0) == "On the radar"
        assert pulse.pulse_tier(7.0) == "Active"
        assert pulse.pulse_tier(12.0) == "Elevated"
        assert pulse.pulse_tier(99.0) == "Elevated"


class TestComposePulse:
    COMPONENTS = {
        "recency": 5.0,
        "search_activity": 0.0,      # inactive -> excluded
        "filing_velocity": 1.5,
        "news_buzz": 3.5,
        "news_sentiment": 0.0,       # inactive -> excluded
    }

    def test_active_components_only_with_labels_and_sources(self):
        out = pulse.compose_pulse(self.COMPONENTS, 10.0)
        keys = [c["key"] for c in out["components"]]
        assert keys == ["recency", "news_buzz", "filing_velocity"]  # sorted by value desc
        first = out["components"][0]
        assert first["label"] == "Recently filed"
        assert first["source"] == "EDGAR"
        assert "description" in first
        # inactive/zero components are dropped
        assert "search_activity" not in keys and "news_sentiment" not in keys

    def test_shares_sum_to_about_100(self):
        out = pulse.compose_pulse(self.COMPONENTS, 10.0)
        total_share = sum(c["share"] for c in out["components"])
        assert 99 <= total_share <= 101  # rounding tolerance

    def test_tier_and_score(self):
        out = pulse.compose_pulse(self.COMPONENTS, 10.0)
        assert out["tier"] == "Active"
        assert out["score"] == 10.0
        assert out["has_signal"] is True

    def test_no_signal_when_all_zero(self):
        out = pulse.compose_pulse(
            {"recency": 0.0, "news_buzz": 0.0}, 0.0
        )
        assert out["has_signal"] is False
        assert out["components"] == []
        assert out["tier"] == "Quiet"

    def test_tolerates_missing_and_malformed_input(self):
        assert pulse.compose_pulse(None, None)["has_signal"] is False
        assert pulse.compose_pulse({}, 0.0)["components"] == []
        # non-numeric component values are ignored, not crashed on
        out = pulse.compose_pulse({"recency": "oops", "news_buzz": 2.0}, 2.0)
        assert [c["key"] for c in out["components"]] == ["news_buzz"]

    def test_unknown_component_keys_ignored(self):
        out = pulse.compose_pulse({"some_future_signal": 9.0, "recency": 1.0}, 1.0)
        assert [c["key"] for c in out["components"]] == ["recency"]
