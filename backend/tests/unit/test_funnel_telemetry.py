"""Unit tests for activation-funnel telemetry (SB1).

capture_funnel_event must (a) include only provided properties, (b) accept the
funnel property contract (duration_ms, result_type, quality_verdict, entry_point),
and (c) never raise — telemetry must not break summary generation.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services import posthog_client as ph


@pytest.mark.unit
class TestCaptureFunnelEvent:
    def test_passes_full_property_contract(self):
        fake_client = MagicMock()
        with patch.object(ph, "get_posthog_client", return_value=fake_client):
            ph.capture_funnel_event(
                "user-1",
                ph.EVENT_GENERATION_SUCCEEDED,
                duration_ms=42_000,
                result_type="complete",
                quality_verdict="full",
                entry_point="homepage",
                filing_id=7,
            )

        fake_client.capture.assert_called_once()
        distinct_id, event, properties = fake_client.capture.call_args[0]
        assert distinct_id == "user-1"
        assert event == "generation_succeeded"
        assert properties == {
            "duration_ms": 42_000,
            "result_type": "complete",
            "quality_verdict": "full",
            "entry_point": "homepage",
            "filing_id": 7,
        }

    def test_drops_none_properties(self):
        fake_client = MagicMock()
        with patch.object(ph, "get_posthog_client", return_value=fake_client):
            ph.capture_funnel_event("guest:1.2.3.4", ph.EVENT_GENERATION_STARTED, entry_point=None)

        _, _, properties = fake_client.capture.call_args[0]
        assert properties == {}

    def test_never_raises_when_capture_fails(self):
        fake_client = MagicMock()
        fake_client.capture.side_effect = RuntimeError("posthog down")
        with patch.object(ph, "get_posthog_client", return_value=fake_client):
            ph.capture_funnel_event("user-1", ph.EVENT_GENERATION_TIMED_OUT, result_type="timeout")

    def test_noop_without_client(self):
        with patch.object(ph, "get_posthog_client", return_value=None):
            ph.capture_funnel_event("user-1", ph.EVENT_GENERATION_FAILED, result_type="error")
