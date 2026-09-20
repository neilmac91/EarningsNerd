"""Attribution verification (the #805 path, step 5): one bounded model verdict decides which flagged
clauses are removed. The prompt carries only the gate's passages, a "stated" verdict must quote a
passage it was actually given, and every failure mode leaves the summary untouched."""
import copy
import json

import pytest

from app.config import settings
from app.services.ai import attribution_verify as verify
from app.services.ai.attribution_gate import MAX_VERIFIABLE_CLAUSES, apply_attributions, find_attributions

FILING = (
    "Item 7. MD&A. DCAI revenue increased $926 million from Q1 2025, primarily driven by $696 million of "
    "higher server revenue due to a 27% increase in server ASPs.\n"
    "Diluted weighted average shares outstanding declined to 24,391 million from 24,611 million.\n"
    "During the year we repurchased 220 million shares."
)
SECTIONS = {
    "the_print": {"headline": "", "key_takeaways": [
        "Diluted weighted average shares declined to 24,391 million from 24,611 million, reflecting share repurchases."],
        "what_changed": ""},
    "segments": [{"segment": "Data Center and AI", "commentary":
                  "Segment performance improved, driven by $696 million of higher server revenue due to a "
                  "27% increase in server ASPs."}],
}


def _candidates(sections=None, filing=FILING):
    return find_attributions(sections if sections is not None else copy.deepcopy(SECTIONS), filing)


def test_default_flag_is_off():
    assert settings.AI_ATTRIBUTION_VERIFY is False


def test_the_prompt_carries_every_flagged_clause_with_its_passages_and_nothing_else():
    _checked, candidates = _candidates()
    judged = verify.verifiable(candidates)
    prompt = verify.build_prompt(judged)
    assert len(judged) == len(candidates) >= 2
    for i, candidate in enumerate(judged):
        assert f"CLAIM {i + 1}" in prompt
        assert candidate.clause[:60] in prompt
        assert candidate.slot in prompt
        for passage in candidate.evidence:
            assert passage[:60] in prompt
    assert "27% increase in server ASPs" in prompt  # the passage the lexical anchor could not reach
    assert "two numbers moving together is not a stated cause" in prompt
    assert '"claims"' in prompt


def test_a_stated_verdict_must_quote_a_passage_it_was_given():
    _checked, candidates = _candidates()
    judged = verify.verifiable(candidates)
    real = judged[0].evidence[0][:80]
    raw = json.dumps({"claims": [
        {"claim": 1, "verdict": "stated", "quote": real},
        {"claim": 2, "verdict": "stated", "quote": "The filing plainly attributes this to strong demand."},
    ]})
    verdicts = verify.parse_verdicts(raw, judged)
    assert verdicts[0] == "stated"
    assert verdicts[1] == "unknown", "an unquotable 'stated' cannot save a clause"


def test_a_too_short_quote_cannot_prove_a_stated_verdict():
    _checked, candidates = _candidates()
    judged = verify.verifiable(candidates)
    raw = json.dumps({"claims": [{"claim": 1, "verdict": "stated", "quote": "revenue"}]})
    assert verify.parse_verdicts(raw, judged) == {0: "unknown"}


@pytest.mark.parametrize("raw", ["", None, "not json at all", '{"claims": "nope"}', '{"other": []}',
                                 '{"claims": [{"claim": 99, "verdict": "not_stated"}]}',
                                 '{"claims": [{"claim": "one", "verdict": "not_stated"}]}',
                                 '{"claims": [{"claim": true, "verdict": "not_stated"}]}'])
def test_unusable_responses_yield_no_verdicts(raw):
    _checked, candidates = _candidates()
    assert verify.parse_verdicts(raw, verify.verifiable(candidates)) == {}


def test_fenced_and_damaged_json_is_still_read():
    _checked, candidates = _candidates()
    judged = verify.verifiable(candidates)
    raw = '```json\n{"claims": [{"claim": 1, "verdict": "not_stated", "quote": "",},]}\n```'
    assert verify.parse_verdicts(raw, judged).get(0) == "not_stated"


def test_a_repeated_claim_number_cannot_overwrite_the_first_verdict():
    _checked, candidates = _candidates()
    judged = verify.verifiable(candidates)
    raw = json.dumps({"claims": [{"claim": 1, "verdict": "unknown"},
                                 {"claim": 1, "verdict": "not_stated"}]})
    assert verify.parse_verdicts(raw, judged) == {0: "unknown"}


def test_only_clauses_with_passages_are_sent_and_the_batch_is_bounded():
    takeaways = [f"Metric {i} rose 5%, driven by an unrelated invented cause number {i}." for i in range(30)]
    sections = {"the_print": {"headline": "", "key_takeaways": takeaways, "what_changed": ""}}
    _checked, candidates = find_attributions(sections, FILING)
    judged = verify.verifiable(candidates)
    assert len(candidates) > MAX_VERIFIABLE_CLAUSES
    assert len(judged) <= MAX_VERIFIABLE_CLAUSES
    assert all(c.evidence for c in judged)


def test_the_audit_note_reports_what_was_sent_decided_and_why_not():
    _checked, candidates = _candidates()
    judged = verify.verifiable(candidates)
    note = verify.audit_note(candidates, judged, {0: "not_stated", 1: "stated"}, None)
    assert note == {"flagged": len(candidates), "sent": len(judged), "decided": 2,
                    "counts": {"not_stated": 1, "stated": 1}, "error": None}
    assert verify.audit_note(candidates, [], {}, "TimeoutError")["error"] == "TimeoutError"


def test_a_verdict_removes_only_its_own_clause_end_to_end():
    sections = copy.deepcopy(SECTIONS)
    checked, candidates = find_attributions(sections, FILING)
    judged = verify.verifiable(candidates)
    by_slot = {c.slot: i for i, c in enumerate(candidates)}
    raw = json.dumps({"claims": [
        {"claim": i + 1,
         "verdict": "not_stated" if c.slot.startswith("the_print") else "stated",
         "quote": "" if c.slot.startswith("the_print") else c.evidence[0][:90]}
        for i, c in enumerate(judged)]})
    verdicts = verify.parse_verdicts(raw, judged)
    audit = apply_attributions(checked, candidates, verdicts, armed=True)
    assert sections["the_print"]["key_takeaways"][0] == "Diluted weighted average shares declined to 24,391 million from 24,611 million."
    assert "27% increase in server ASPs" in sections["segments"][0]["commentary"]
    assert [d["slot"] for d in audit["dropped"]] == ["the_print.key_takeaways[0]"]
    assert audit["verdicts"][candidates[by_slot["segments[0].commentary"]].slot] == "stated"


# --- service wiring: the real transport, one bounded call, and failure that changes nothing ---

import asyncio  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

import httpx2  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402

from app.services.openai_service import OpenAIService  # noqa: E402


@asynccontextmanager
async def _service(handler):
    service = object.__new__(OpenAIService)
    service.model = 'deepseek-v4-pro'
    service.fallback_client = None
    service._task_models = {}
    service._model_overrides = {}
    service._recovery_semaphore = asyncio.Semaphore(1)
    async with AsyncOpenAI(api_key='offline', base_url='https://api.deepseek.com/v1', max_retries=0,
                           http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler))) as client:
        service.client = client
        yield service


def _completion(content):
    return httpx2.Response(200, json={'id': 'offline', 'object': 'chat.completion', 'created': 1,
        'model': 'deepseek-chat', 'choices': [{'index': 0, 'finish_reason': 'stop',
        'message': {'role': 'assistant', 'content': content}}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 2, 'total_tokens': 12}})


@pytest.mark.asyncio
async def test_verification_is_one_call_only_when_armed_and_something_was_flagged(monkeypatch):
    monkeypatch.setattr(settings, 'AI_ATTRIBUTION_VERIFY', True)
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return _completion(json.dumps({"claims": [{"claim": 1, "verdict": "not_stated", "quote": ""},
                                                  {"claim": 2, "verdict": "stated", "quote": ""}]}))

    _checked, candidates = _candidates()
    async with _service(handler) as service:
        verdicts, note = await service._verify_attributions(candidates, '10-K')
        empty = await service._verify_attributions([], '10-K')
    assert len(requests) == 1, 'one bounded call per generation, never one per clause'
    assert requests[0]['temperature'] == 0.0 and requests[0]['max_tokens'] == 700
    assert verify.VERIFY_SYSTEM_MESSAGE == requests[0]['messages'][0]['content']
    assert verdicts[0] == 'not_stated'
    assert verdicts.get(1) == 'unknown'  # "stated" without a quote never survives
    assert note['sent'] == len(candidates) and note['error'] is None
    assert empty == (None, None), 'nothing flagged → no call and no verdicts'


@pytest.mark.asyncio
async def test_verification_off_makes_no_call_and_returns_no_verdicts(monkeypatch):
    monkeypatch.setattr(settings, 'AI_ATTRIBUTION_VERIFY', False)

    def handler(request):  # pragma: no cover - must never run
        raise AssertionError('no provider call may be made while verification is off')

    _checked, candidates = _candidates()
    async with _service(handler) as service:
        assert await service._verify_attributions(candidates, '10-K') == (None, None)


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["provider_error", "garbage"])
async def test_a_failed_verification_drops_nothing_and_records_why(monkeypatch, outcome):
    monkeypatch.setattr(settings, 'AI_ATTRIBUTION_VERIFY', True)

    def handler(request):
        if outcome == "provider_error":
            return httpx2.Response(500, json={'error': 'upstream'})
        return _completion('I could not determine this.')

    sections = copy.deepcopy(SECTIONS)
    before = copy.deepcopy(sections)
    checked, candidates = find_attributions(sections, FILING)
    async with _service(handler) as service:
        verdicts, note = await service._verify_attributions(candidates, '10-K')
    audit = apply_attributions(checked, candidates, verdicts, armed=True)
    assert verdicts is None and note['error']
    assert sections == before, 'a failed verification never changes the summary'
    assert audit['dropped'] == [] and audit['decider'] == 'none'


@pytest.mark.asyncio
async def test_claim_identity_reaches_the_verifier_from_filing_slots(monkeypatch):
    # PFE run0, eval_20260917T221422Z: retain the source's real line/bullet breaks. The lexical
    # gate flags this SIA clause even though the excerpt carries its lead-in and spending bullets.
    filing = (
        "Selling, Informational and Administrative Expenses\n"
        "Selling, informational and administrative\n"
        " expenses decreased $70\xa0million in the first quarter of 2026, primarily reflecting:\n"
        "•\na decrease of $100 million in marketing and promotional spend on various products "
        "from more targeted investments and ongoing productivity improvements; and\n"
        "•\nlower spending of $60 million in corporate enabling function"
    )
    metric = "Selling, informational and administrative expenses"
    driver = ("a decrease of $100 million in marketing and promotional spend on various products "
              "from more targeted investments and ongoing productivity improvements and lower "
              "spending of $60 million in corporate enabling function")
    commentary = f"{metric} decreased $70M, primarily reflecting {driver}."
    long_subject = "Operating expenses in Q1 2026 " + "management discussion " * 60 + "versus Q1 2025,"
    long_anchor = "Corporate operations " + "regional reporting " * 30 + "prior period Q1 2025"
    sections = {
        "results_that_matter": {"table": [
            {"metric": metric, "commentary": commentary},
            {"metric": "Cost of sales", "commentary": commentary.replace(metric, "Cost of sales")},
            {"metric": long_anchor, "commentary": long_subject + " primarily reflecting " + driver + "."},
        ]},
        "segments": [{"segment": "Oncology", "commentary": commentary}],
    }
    before = copy.deepcopy(sections)
    checked, candidates = find_attributions(sections, filing)
    assert checked == len(candidates) == 4
    assert sections == before  # discovery still only measures
    monkeypatch.setattr(settings, 'AI_ATTRIBUTION_VERIFY', True)
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return _completion(json.dumps({"claims": [
            {"claim": i + 1, "verdict": "unknown", "quote": ""} for i in range(len(candidates))
        ]}))

    async with _service(handler) as service:
        verdicts, _note = await service._verify_attributions(candidates, '10-Q')
    assert len(requests) == 1
    message = requests[0]['messages'][1]['content']
    contexts = [json.loads(line.removeprefix("  Summary context: "))
                for line in message.splitlines() if line.startswith("  Summary context: ")]
    assert len(contexts) == len(candidates)
    by_slot = {candidate.slot: context for candidate, context in zip(candidates, contexts)}
    assert by_slot['results_that_matter.table[0].commentary'] == {
        'subject_before_cause': metric + ' decreased $70M,', 'metric_or_segment': metric,
    }
    assert by_slot['results_that_matter.table[1].commentary'] == {
        'subject_before_cause': 'Cost of sales decreased $70M,', 'metric_or_segment': 'Cost of sales',
    }
    assert by_slot['segments[0].commentary'] == {
        'subject_before_cause': metric + ' decreased $70M,', 'metric_or_segment': 'Oncology',
    }
    bounded = by_slot['results_that_matter.table[2].commentary']
    assert len(bounded['subject_before_cause']) <= 600
    assert bounded['subject_before_cause'].startswith('Operating expenses in Q1 2026 ')
    assert bounded['subject_before_cause'].endswith('versus Q1 2025,')
    assert len(bounded['metric_or_segment']) <= 240
    assert bounded['metric_or_segment'].startswith('Corporate operations ')
    assert bounded['metric_or_segment'].endswith('prior period Q1 2025')
    assert all('[context clipped]' in text for text in bounded.values())
    pfe = next(c for c in candidates if c.slot == 'results_that_matter.table[0].commentary')
    # Current windowing supplies detached bullets, not the causal lead-in. Preserve that evidence
    # limitation rather than fabricating a complete passage in this prompt-context gate.
    assert any('a decrease of $100 million' in passage for passage in pfe.evidence)
    assert all(passage in message for passage in pfe.evidence)
    # Transport's unknown verdict cannot delete the clause, even with the drop flag armed.
    audit = apply_attributions(checked, candidates, verdicts, armed=True)
    assert audit['dropped'] == [] and sections == before
