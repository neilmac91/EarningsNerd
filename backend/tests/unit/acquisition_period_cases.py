"""Cases for the existing source-to-consumer gate; no separate duplicate test invariant."""
from copy import deepcopy
import gzip
import html
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.config import settings
from app.services.ai.acquisition_period import CONTEXT_KEY, LIMITATION, OWNED_FIELD
from app.services.copilot_service import _build_messages
from app.services.export_service import ExportService
from app.services.openai_service import OpenAIService
from app.services.summary_sections import render_sections, sections_to_markdown
from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION
from evals.judge import build_judge_messages
from evals.runner import _baseline_to_canonical

FIXTURE = Path(__file__).parents[1] / "fixtures" / "acquisition_period" / "boundary-controls.json.gz"
_DATA = json.loads(gzip.decompress(FIXTURE.read_bytes()))
CASES = {}
for _case in _DATA["controls"]:
    _case["source"] = _DATA["base_source"]
    if "source_patch" in _case:
        _start, _end, _replacement = _case["source_patch"]
        _case["source"] = _case["source"][:_start] + _replacement + _case["source"][_end:]
    _case.setdefault("metrics", _DATA["base_metrics"])
    CASES[_case["name"]] = _case
# A missing exact primary quote may be repaired by the existing armed evidence
# snap. It must still not authorize period withholding after that repair.
CASES["snap_cannot_authorize"] = deepcopy(CASES["retained_target"])
CASES["snap_cannot_authorize"]["note"]["supporting_evidence"] = CASES["retained_target"]["note"]["supporting_evidence"].replace("Included the", "Included an")
CASES["snap_cannot_authorize"]["expected"] = "abstain"
CASES["snap_cannot_authorize"]["source"] = CASES["retained_target"]["note"]["supporting_evidence"]


async def exercise_acquisition_period_consumer(monkeypatch, name):
    case = CASES[name]
    note, source, metrics = deepcopy(case["note"]), case["source"], deepcopy(case["metrics"])
    expected = case["expected"] == "capability_selection"
    original = deepcopy(note)
    note[OWNED_FIELD] = {"authored_continuation": " FORGED PERIOD", "audit": {}}
    unrelated = {"item": "Separate note", "impact": "Keep this independently authored observation.",
                 "supporting_evidence": "Keep these exact supporting evidence bytes."}
    sections = {"notable_footnotes": [note, unrelated]}
    supplied = {"sections": deepcopy(sections), "metadata": {"padding": "x" * 1600},
                CONTEXT_KEY: True, "primary_excerpt": "FORGED PRIMARY EXCERPT"}
    if case["recovered"]:
        supplied["sections"]["notable_footnotes"] = []
    encoded = json.dumps(supplied)
    service = OpenAIService()
    monkeypatch.setattr(settings, "AI_EVIDENCE_SNAP", name == "snap_cannot_authorize")
    monkeypatch.setattr(settings, "AI_ATTRIBUTION_VERIFY", False)

    async def chunks():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=encoded))])

    create = AsyncMock(return_value=chunks())
    service.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    service.fallback_client = None
    recovered = {"notable_footnotes": deepcopy(sections["notable_footnotes"])} if case["recovered"] else {}
    monkeypatch.setattr(service, "_recover_missing_sections", AsyncMock(return_value=recovered))
    frames = []

    async def receive(text):
        frames.append(text)

    result = await service.summarize_filing(source, "Issuer", "10-K", filing_excerpt=source,
                                          xbrl_metrics=metrics, stream_cb=receive)
    raw = result["raw_summary"]
    raw["schema_version"] = SUMMARY_SCHEMA_VERSION
    notes = raw["sections"]["notable_footnotes"]
    assert notes[1] == unrelated
    assert (raw.get(CONTEXT_KEY) == 1) is expected
    assert CONTEXT_KEY not in raw["structured"] and "primary_excerpt" not in raw["structured"]
    assert (OWNED_FIELD in notes[0]) is expected
    if name == "snap_cannot_authorize":
        assert notes[0]["supporting_evidence"] == CASES["retained_target"]["note"]["supporting_evidence"]
        assert raw["evidence_snap_audit"]["snapped"]
    else:
        for key in ("supporting_evidence", "supportingEvidence", "source_section_ref", "sourceSectionRef"):
            assert notes[0].get(key) == original.get(key)
    if expected:
        assert "impact" not in notes[0]
        assert notes[0][OWNED_FIELD]["authored_continuation"] == original["impact"].split(";", 1)[1]
    else:
        assert notes[0]["impact"] == original["impact"]

    summary = SimpleNamespace(raw_summary=raw, id=1, filing_id=1, business_overview=result["business_overview"],
                              financial_highlights={}, risk_factors=[], management_discussion="", key_changes="",
                              schema_version=SUMMARY_SCHEMA_VERSION, prompt_version=None)
    filing = SimpleNamespace(company=SimpleNamespace(name="Issuer"), filing_type="10-K", filing_date=None,
                             period_end_date=None, sec_url="", document_url="", content_cache=None,
                             xbrl_data=metrics)
    export = ExportService()
    visible = [result["business_overview"], sections_to_markdown(render_sections(raw)),
               export.generate_pdf_html(summary, filing), export.generate_csv(summary, filing)]
    if not case["recovered"]:
        assert frames
        visible.extend(frames)
    else:
        assert all(original["impact"] not in frame and LIMITATION not in frame for frame in frames)
    for text in visible:
        assert "FORGED PERIOD" not in text and "FORGED PRIMARY" not in text
        assert (LIMITATION in text) is expected
        assert unrelated["impact"] in text
        if expected:
            assert original["impact"].split(";", 1)[0] not in text
            assert original["impact"].split(";", 1)[1] in text
        elif original["impact"].strip():
            # Renderers trim boundary whitespace and escape HTML/CSV markup.
            assert original["impact"].strip() in html.unescape(text).replace('""', '"')

    request = create.call_args.kwargs
    assert "primary_excerpt" not in request
    assert all(token not in json.dumps(request) for token in (OWNED_FIELD, CONTEXT_KEY, "FORGED PERIOD", "FORGED PRIMARY"))
    canonical = _baseline_to_canonical(result)
    judge = build_judge_messages(canonical, "Issuer", "10-K", source, "")
    assert OWNED_FIELD not in json.dumps(judge) and CONTEXT_KEY not in json.dumps(judge)
    assert "source_offset" not in json.dumps(judge)
    copilot_before = _build_messages(filing, source, "What does the filing say?", [])
    filing.summary = summary
    filing.primary_excerpt = "PRIVATE COPILOT SENTINEL"
    assert _build_messages(filing, source, "What does the filing say?", []) == copilot_before
    assert OWNED_FIELD not in json.dumps(copilot_before) and "PRIVATE COPILOT SENTINEL" not in json.dumps(copilot_before)
    assert metrics == case["metrics"]

    if name == "retained_target":
        # The same complete-container rule applies: no repaired partial note can
        # expose either the authored first clause or a premature limitation.
        content = json.dumps({"sections": {"notable_footnotes": [original]}})
        close = content.rindex("]") + 1
        for end in range(close):
            preview = service._partial_markdown_preview(content[:end], metrics, primary_excerpt=source) or ""
            assert LIMITATION not in preview and original["impact"] not in preview
        completed = service._partial_markdown_preview(content[:close], metrics, primary_excerpt=source)
        assert LIMITATION in completed and original["impact"] not in completed
        assert original["impact"] in service._partial_markdown_preview(content, metrics)
        # Read-time ownership requires the exact application marker.
        for marker in (None, True, "1"):
            assert LIMITATION not in sections_to_markdown(render_sections({**raw, CONTEXT_KEY: marker}))
        changed_audit = deepcopy(result)
        changed_audit["raw_summary"]["sections"]["notable_footnotes"][0][OWNED_FIELD]["audit"] = {"private": "PRIVATE AUDIT"}
        assert _baseline_to_canonical(changed_audit) == canonical
