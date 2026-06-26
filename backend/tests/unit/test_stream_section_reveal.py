"""A5 progressive section reveal: streaming helpers on openai_service.

No network — the LLM stream and the markdown builder are mocked. Covers: the partial-preview render
is best-effort (never raises), and _stream_collect accumulates the complete content while emitting
throttled preview frames via the callback.
"""
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
