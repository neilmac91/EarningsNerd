"""Wave 0 anchors (C0) for the copilot_service refactor (tasks/refactor-plan-2026-10.md, M1).

Characterization pins at the seams that C1 (pure moves into ``app/services/copilot/``) and C2 (the
in-place decomposition of ``_answer_filing_question_attempt``) cut, where no existing test pins
today's behaviour:

* C0.1 ``_compact_xbrl_block`` cuts the model-facing XBRL rendering at exactly 8,000 chars.
* C0.2 ``_safe_activity_label`` falls back to fixed labels for unknown tools, concepts and kinds, and
  the attempt loop publishes every tool-activity signal through it.
* C0.3 the attempt loop's 3-second heartbeat: a ``reading`` progress event at 3 s or more since the
  last one, re-armed from the clock when it fires.
* C0.4 a failure before the first attempt starts is exactly one ``_STREAM_FAILURE`` error event.

Already pinned, so not repeated here: ``_register_fact`` dedupe (test_copilot_provenance.py) and
the ``_verify_citations`` matrix (test_copilot_quotation_retry.py).

Every boundary is faked in-process: the provider on the shared ``openai_service`` singleton's
``stream_chat_with_tools`` (through ``patch.object``, which leaves no instance attribute behind),
the filing as a duck-typed object. The one patch on
``copilot_service``'s own namespace is ``monotonic`` (C0.2 and C0.3). Its only readers are in the
attempt loop, which stays in this module, so the binding survives C1 and C2; do not re-point it.
"""
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services import copilot_service
from app.services.ai.copilot_chat import STREAM_ACTIVITY_SENTINEL

KNOWN = "Demand remained robust across cloud services."
SOURCE = "Item 2. Management's Discussion. " + KNOWN + " Capacity investment continued."
FOLLOWUPS = ["What supported cloud demand?", "What did capacity investment support?"]
READING = {"type": "progress", "stage": "reading"}


def _filing():
    return SimpleNamespace(
        company_id=1, accession_number="0000000001-26-000001", period_of_report="2026-06-30",
        filing_type="10-Q", filing_date=None, xbrl_data=None,
        document_url="https://www.sec.gov/Archives/edgar/data/1/000000000126000001/filing.htm",
        sec_url="https://www.sec.gov/Archives/edgar/data/1/000000000126000001/",
        company=SimpleNamespace(name="Test Company", ticker="TEST", cik="1"),
        content_cache=SimpleNamespace(critical_excerpt=SOURCE, markdown_content=None),
    )


class _ExpiredFiling:
    """Reading the cached text raises, as a lazy load on an expired ORM instance would."""

    @property
    def content_cache(self):
        raise RuntimeError("PRIVATE expired-instance detail")


async def _collect(filing, events):
    async for event in copilot_service.answer_filing_question(
        filing=filing, question="What did management say about demand?",
    ):
        events.append(event)
    return events


@pytest.mark.unit
@pytest.mark.parametrize("length", [7_999, 8_000, 8_001, 30_000])
def test_c0_1_compact_xbrl_block_caps_at_8000_chars(length):
    """C0.1 pins backend/app/services/copilot_service.py:289-309 (the cap is :309).

    A compact rendering of up to 8,000 chars comes back whole; a longer one is cut to its first
    8,000 chars: a bare prefix, neither "" (which the function's docstring promises for an
    oversized payload) nor a re-serialized smaller payload. ``_build_context_message`` hands the
    model exactly that block (copilot_service.py:322, :342-348). The payload has two keys in
    non-alphabetical order, so the pinned bytes also cover both compact separators (",", ":") and
    the insertion order (no sort_keys) at every length, the cut ones included.
    """
    head = '{"period":"FY2025","note":"'
    xbrl = {"period": "FY2025", "note": "x" * (length - len(head) - len('"}'))}
    rendering = head + xbrl["note"] + '"}'
    assert len(rendering) == length

    block = copilot_service._compact_xbrl_block(xbrl)

    assert block == rendering[:8_000]
    assert len(block) == min(length, 8_000)
    context = copilot_service._build_context_message(SimpleNamespace(xbrl_data=xbrl), "Excerpt.")
    assert context.endswith("\nSTRUCTURED FINANCIAL DATA (XBRL, for reference):\n" + rendering[:8_000])


@pytest.mark.unit
@pytest.mark.parametrize(("info", "label"), [
    # An unknown or missing tool name gets the generic label, whatever its args (:957-959).
    ({"name": "MODEL PRIVATE TOOL NAME", "args": {"concept": "revenue"}}, "Reading financial information"),
    ({"args": {"concept": "revenue"}}, "Reading financial information"),
    # A concept outside copilot_tools._CONCEPT_LABELS becomes concept=None (:964), so the tool's
    # generic wording replaces it. So does a concept that is not a string (an unhashable one would
    # raise without the isinstance check) and args that are not a dict (:961).
    ({"name": "get_financial_fact", "args": {"concept": "MODEL PRIVATE CONCEPT"}}, "Looking up a financial figure"),
    ({"name": "get_financial_fact", "args": {"concept": "operating_cash_flow"}}, "Looking up a financial figure"),
    ({"name": "get_financial_fact", "args": {"concept": ["revenue"]}}, "Looking up a financial figure"),
    ({"name": "get_financial_fact", "args": "revenue"}, "Looking up a financial figure"),
    ({"name": "compute_metric", "args": {"concept": "MODEL PRIVATE CONCEPT"}}, "Computing a metric"),
    ({"name": "compute_metric", "args": {"concept": "MODEL PRIVATE CONCEPT", "kind": "margin"}},
     "Computing a metric margin"),
    ({"name": "compute_metric", "args": {"concept": "MODEL PRIVATE CONCEPT", "kind": "yoy_growth"}},
     "Computing a metric YoY growth"),
    # Published labels only: describe_tool_call (copilot_tools.py:162-174) ignores these inputs
    # too, so the kind filter at :965 is not observable through the label.
    ({"name": "compute_metric", "args": {"concept": "revenue", "kind": "MODEL PRIVATE KIND"}}, "Computing revenue"),
    ({"name": "list_available_concepts", "args": {"concept": "MODEL PRIVATE CONCEPT"}},
     "Scanning available financials"),
    # Controls: labelled values pass through, so a label that always fell back would fail here.
    ({"name": "get_financial_fact", "args": {"concept": "revenue"}}, "Looking up revenue"),
    ({"name": "compute_metric", "args": {"concept": "gross_profit", "kind": "margin"}},
     "Computing gross profit margin"),
], ids=[
    "unknown_tool", "missing_tool", "unknown_concept", "unlabelled_concept", "unhashable_concept",
    "non_dict_args", "metric_unknown_concept", "margin_unknown_concept", "growth_unknown_concept",
    "unknown_kind", "list_ignores_args", "control_fact", "control_margin",
])
def test_c0_2_safe_activity_label_fallback_strings(info, label):
    """C0.2 pins the fallback strings of backend/app/services/copilot_service.py:955-967.

    test_copilot.py:591 keeps "MODEL PRIVATE" off the wire, but describe_tool_call lowercases a
    concept's label, so that check catches a leaked tool name and not a leaked concept; the
    unknown-concept rows here are what fail if a model-chosen concept is published.
    """
    assert copilot_service._safe_activity_label(info) == label



@pytest.mark.unit
@pytest.mark.asyncio
async def test_c0_2_the_attempt_loop_publishes_activity_only_through_the_safe_label(monkeypatch):
    """C0.2 pins the wiring at backend/app/services/copilot_service.py:1736-1747: every tool-activity
    signal on the provider stream becomes one ``activity`` event whose label is ``_safe_activity_label``'s,
    whose phase is "done" only when the signal says so, and whose ``ok`` defaults to true.

    A loop that labelled a known tool with ``describe_tool_call`` directly would publish the model's own
    concept, lowercased, which test_copilot.py:591's case-sensitive check cannot see.
    """
    private = {"name": "get_financial_fact", "args": {"concept": "MODEL PRIVATE CONCEPT"}}
    signals = [
        {**private, "phase": "start"},
        {**private, "phase": "done", "ok": False},
        {"name": "compute_metric", "args": {"concept": "gross_profit", "kind": "margin"}, "phase": "done"},
    ]
    chunks = [STREAM_ACTIVITY_SENTINEL + json.dumps(signal) for signal in signals]
    chunks += [STREAM_ACTIVITY_SENTINEL + "not json",
               "Management described demand as robust across its cloud services [1].",
               "\n===CITATIONS===\n" + json.dumps([{"n": 1, "excerpt": KNOWN, "section": "Item 2 — MD&A"}])
               + "\n===FOLLOWUPS===\n" + json.dumps(FOLLOWUPS)]

    async def provider(*_args, **_kwargs):
        for chunk in chunks:
            yield chunk

    events = []
    monkeypatch.setattr(copilot_service, "monotonic", lambda: 0.0)  # no heartbeat between the signals
    with patch.object(copilot_service.openai_service, "stream_chat_with_tools", provider):
        await _collect(_filing(), events)

    assert [event for event in events if event["type"] == "activity"] == [
        {"type": "activity", "label": "Looking up a financial figure", "phase": "start", "ok": True},
        {"type": "activity", "label": "Looking up a financial figure", "phase": "done", "ok": False},
        {"type": "activity", "label": "Computing gross profit margin", "phase": "done", "ok": True},
        {"type": "activity", "label": "Reading financial information", "phase": "start", "ok": True},
    ]
    assert events[-1]["type"] == "complete"
    assert "model private" not in json.dumps(events).lower()

@pytest.mark.unit
@pytest.mark.asyncio
async def test_c0_3_heartbeat_fires_at_3_seconds_and_re_arms_from_the_clock(monkeypatch):
    """C0.3 pins the heartbeat at backend/app/services/copilot_service.py:1751-1753.

    The clock reads 0 s when the loop arms it (copilot_service.py:1700), then 1, 2, 2.999, 3, 7.5 and
    10.499 s as the provider hands over each chunk:
    - 2.999 s is just under the threshold and adds nothing;
    - 3 s reaches it exactly and adds a ``reading`` progress, re-arming at 3 s;
    - 7.5 s is 4.5 s later, a late crossing, and adds one more, re-arming at 7.5 s;
    - 10.499 s is 2.999 s after that and adds nothing.
    A lower threshold, a strict ``>``, a missing re-arm, or a re-arm on the old schedule
    (``last_progress += 3``, which would sit at 6 s and fire again at 10.499 s) each change the
    events. test_copilot.py:519 patches the same clock, but no assertion there observes it.
    """
    now = [0.0]
    events, delivered_before_chunk = [], []
    chunks = [
        (1.0, "Management described demand "),
        (2.0, "as robust across its "),
        (2.999, "cloud "),
        (3.0, "services "),
        (7.5, "[1]."),
        (10.499, "\n===CITATIONS===\n" + json.dumps([{"n": 1, "excerpt": KNOWN, "section": "Item 2 — MD&A"}])
         + "\n===FOLLOWUPS===\n" + json.dumps(FOLLOWUPS)),
    ]

    async def provider(*_args, **_kwargs):
        for at, chunk in chunks:
            now[0] = at
            delivered_before_chunk.append(len(events))
            yield chunk

    monkeypatch.setattr(copilot_service, "monotonic", lambda: now[0])
    with patch.object(copilot_service.openai_service, "stream_chat_with_tools", provider):
        await _collect(_filing(), events)

    generating = {"type": "progress", "stage": copilot_service.PROVIDER_STARTED_STAGE}
    assert events[:4] == [READING, generating, READING, READING]
    assert [event["type"] for event in events[4:]] == ["complete"]
    assert events[4]["answer"] == "Management described demand as robust across its cloud services [1]."
    assert (events[4]["kind"], events[4]["grounded"]) == ("answer", 1)
    # Each heartbeat was published after its chunk arrived and before the next was requested.
    assert delivered_before_chunk == [1, 2, 2, 2, 3, 4]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_c0_4_failure_before_the_attempt_yields_one_stream_failure():
    """C0.4 pins backend/app/services/copilot_service.py:1633-1635 for a failure in :1603-1606.

    ``_select_source_text`` raising before the first attempt starts reaches the question owner's
    handler: exactly one ``_STREAM_FAILURE`` error, no progress, the provider never streamed and
    the exception text never published. test_copilot.py:1262-1281 fails inside the attempt, which
    answers itself with the same message (the error sentinel at copilot_service.py:1726-1728, the
    raised exception at :1929-1931), so it never reaches this handler.
    """
    streamed = []

    async def provider(*_args, **_kwargs):
        streamed.append(True)
        yield "unreachable"

    with patch.object(copilot_service.openai_service, "stream_chat_with_tools", provider):
        events = await _collect(_ExpiredFiling(), [])

    assert events == [{"type": "error", "message": copilot_service._STREAM_FAILURE}]
    assert streamed == []
