"""A5 progressive section reveal: streaming helpers on openai_service.

No network — provider streams are mocked; the completion invariant uses the real renderer.
Covers: the partial-preview render
is best-effort (never raises), and _stream_collect accumulates the complete content while emitting
throttled preview frames via the callback.
"""
import json

import pytest

from app.services.openai_service import openai_service


@pytest.mark.parametrize(
    "partial",
    ["", "{", "not json at all", '{"sections":', '{"metadata":{},"sections":{"x":"y"}}', '{"sections":[]}'],
)
def test_partial_markdown_preview_never_raises(partial):
    # Best-effort: returns a string or None for any (often malformed) partial JSON, never raises.
    out = openai_service._partial_markdown_preview(partial, None)
    assert out is None or isinstance(out, str)


class _Delta:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.delta = _Delta(content)


class _Chunk:
    def __init__(self, content):
        self.choices = [_Choice(content)]


@pytest.mark.asyncio
async def test_stream_collect_accumulates_and_emits(monkeypatch):
    pieces = ["a" * 800, "b" * 800, "c" * 200]  # total 1800 chars → crosses the ~1500 emit threshold

    async def fake_create(**kwargs):
        async def gen():
            for p in pieces:
                yield _Chunk(p)
        return gen()

    monkeypatch.setattr(openai_service.client.chat.completions, "create", fake_create)
    # Decouple from the real markdown builder — preview rendering is exercised separately above.
    monkeypatch.setattr(openai_service, "_partial_markdown_preview", lambda content, xbrl: "PREVIEW")

    emitted = []

    async def cb(md):
        emitted.append(md)

    content = await openai_service._stream_collect({}, cb, "10-K", None)

    assert content == "".join(pieces)          # complete content returned for assembly
    assert emitted and emitted[0] == "PREVIEW"  # at least one throttled preview frame fired


@pytest.mark.asyncio
async def test_stream_collect_consumer_error_does_not_abort(monkeypatch):
    async def fake_create(**kwargs):
        async def gen():
            yield _Chunk("z" * 2000)
        return gen()

    monkeypatch.setattr(openai_service.client.chat.completions, "create", fake_create)
    monkeypatch.setattr(openai_service, "_partial_markdown_preview", lambda content, xbrl: "PREVIEW")

    async def bad_cb(_md):
        raise RuntimeError("consumer blew up")

    # A consumer error must never abort generation — content still returns intact.
    content = await openai_service._stream_collect({}, bad_cb, "10-K", None)
    assert content == "z" * 2000


@pytest.mark.asyncio
async def test_previews_render_only_originally_complete_current_sections(monkeypatch):
    """A preview is the shared projection of complete containers, never repaired claims."""
    from app.services.summary_sections import render_sections, sections_to_markdown
    from app.services.summary_versioning import SUMMARY_SCHEMA_VERSION

    sections = {
        "the_print": {"headline": 'Revenue rose; management said "growth {continues}".',
                      "key_takeaways": ["Disclosed demand. " * 100]},
        "results_that_matter": {"table": [
            {"metric": "Revenue", "current_period": "$1,000M", "prior_period": "$800M",
             "change": "+25%", "commentary": "Volume", "source_value": 1.25e3},
        ]},
        "risks": [{"summary": "Concentration risk", "supporting_evidence": "A \\ B",
                   "materiality": "high"}],
        "forward_signals": {"guidance": "Sales guidance is $1,100M to $1,200M."},
    }
    prefix = '{"metadata":{"company_name":"Example"},"sections":{'
    content = prefix
    boundaries = []
    for key, value in sections.items():
        content += ("," if boundaries else "") + json.dumps(key) + ":" + json.dumps(value)
        boundaries.append(len(content))
    content += "}}"

    def expected(count):
        selected = dict(list(sections.items())[:count])
        return sections_to_markdown(render_sections({
            "schema_version": SUMMARY_SCHEMA_VERSION, "sections": selected,
        })) or None

    # Every byte boundary includes unfinished strings, escapes, numbers and nested arrays.
    # Closing only the first section must make progress before the root closes.
    for end in range(len(content) + 1):
        complete = sum(boundary <= end for boundary in boundaries)
        assert openai_service._partial_markdown_preview(content[:end], None) == expected(complete), end
    assert expected(1) and "Revenue rose" in expected(1)
    assert "$1,000M" in expected(2) and "Concentration risk" in expected(3)
    assert "Sales guidance" in expected(4)
    assert openai_service._partial_markdown_preview("```json\n" + content + "\n```", None) == expected(4)

    for malformed in (
        content + "garbage", content.replace('"sections":{', '"sections":['),
        content[:boundaries[0]] + 'x', content[:boundaries[0]] + ',}}',
        '{"sections":{"the_print":{"headline":"one","headline":"two"}}}',
        '{"sections":{"the_print":{"headline":"one"},"the_print":{}}}',
        '{"sections":{"the_print":{"headline":"one","bad":NaN}}}',
        '{"sections":{"the_print":"scalar"}}',
        '{"nested":{"sections":{"the_print":{"headline":"not root"}}}}',
        '{"sections":{"executive_snapshot":{"headline":"legacy"}}}',
        " " * 256_001 + content,
    ):
        assert openai_service._partial_markdown_preview(malformed, None) is None

    # Exercise the actual callback owner too: first frame precedes the completed root,
    # and optional preview rendering cannot change the assembled provider content.
    split = boundaries[0]
    pieces = [content[:split], content[split:]]
    seen = []

    async def fake_create(**kwargs):
        async def gen():
            yield _Chunk(pieces[0])
            assert seen == [expected(1)]
            yield _Chunk(pieces[1])
        return gen()

    async def cb(markdown):
        seen.append(markdown)

    monkeypatch.setattr(openai_service.client.chat.completions, "create", fake_create)
    assert await openai_service._stream_collect({}, cb, "10-K", None) == content
    assert seen[0] == expected(1)
