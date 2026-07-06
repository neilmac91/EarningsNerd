"""Transport-agnostic streaming chat wrappers for the copilot path (roadmap S2 façade split).

``_CopilotChatMixin`` holds the provider-generic streaming wrappers used by "Ask this Filing":
``stream_chat`` (plain streamed completion) and ``stream_chat_with_tools`` (tool-use round-trips
with live activity signals). Both yield sentinel-prefixed chunks on error/tool-activity instead of
raising, so the SSE contract stays intact. Mixed into ``OpenAIService``; methods resolve through
``self``. Extracted verbatim; the two public sentinels are re-exported by ``openai_service``.
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.config import settings
from app.services.ai.model_flags import _thinking_disabled_model

logger = logging.getLogger(__name__)


# Distinct failure signal for the transport-agnostic streaming wrappers (``stream_chat`` /
# ``stream_chat_with_tools``). On an upstream/model error they yield a single chunk prefixed with
# this sentinel instead of raising, so the SSE contract stays intact. The null-byte delimiters can
# never appear in normal model output, so a consumer can unambiguously distinguish a real failure
# from answer prose (a plain ``[Error: ...]`` string is indistinguishable from a model that happens
# to quote one, and would otherwise be streamed to the user as the answer body).
STREAM_ERROR_SENTINEL = "\x00\x00__OPENAI_STREAM_ERROR__\x00\x00"

# Tool-activity signal for ``stream_chat_with_tools``. Before and after running each tool call the
# wrapper yields a single chunk prefixed with this sentinel whose remainder is a JSON object
# ``{"name","args","phase":"start"|"done","ok"?}``. A consumer can surface a live "show the work"
# ticker ("Looking up revenue… ✓") while keeping the wrapper provider-generic — it emits the raw
# tool name/args and leaves human labelling to the caller. Null-byte delimiters can't appear in
# model output, so this is unambiguous vs. answer prose.
STREAM_ACTIVITY_SENTINEL = "\x00\x00__OPENAI_STREAM_ACTIVITY__\x00\x00"

# Hold back this many chars of a tool round's prose before deciding it is a real answer —
# inter-tool narration is short ("Let me compute the margins…"); real answers blow past it.
_TOOL_ROUND_HOLDBACK_CHARS = 240


class _CopilotChatMixin:
    """Streaming chat + tool-use wrappers for the copilot path, mixed into OpenAIService."""

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        max_tokens: int = 1200,
        temperature: float = 0.2,
        usage_sink: Optional[Dict[str, int]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream raw assistant delta content for an arbitrary chat completion.

        A thin, transport-agnostic wrapper used by the "Ask this Filing" Copilot (A2) and the
        Multi-Period Analysis narrative. It does not own any prompt/JSON contract — callers pass
        the full ``messages`` and parse the streamed text themselves. Yields only ``delta.content``
        strings in order.

        ``model`` defaults to ``self.model``. DeepSeek's reasoning ("thinking") mode is disabled so
        the stream is the answer text, not chain-of-thought. Pass ``usage_sink`` to receive the
        provider's token usage (same accumulation contract as ``stream_chat_with_tools``). Tolerant
        try/except mirrors the existing streaming method: on failure it yields a single chunk
        prefixed with ``STREAM_ERROR_SENTINEL`` (so a consumer can surface a real error rather than
        stream it as the answer) rather than raising, so the generator never breaks the SSE contract.
        """
        model_name = model or self.model
        try:
            create_kwargs: Dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
            if _thinking_disabled_model(model_name, getattr(settings, "OPENAI_BASE_URL", None)):
                create_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
            if usage_sink is not None:
                create_kwargs["stream_options"] = {"include_usage": True}
            stream = await self.client.chat.completions.create(**create_kwargs)
            async for chunk in stream:
                if not chunk.choices:
                    # The include_usage final chunk: empty choices + a `usage` payload (dict on some
                    # OpenAI-compatible gateways, object on others) — same handling as the tools
                    # variant so both meters price identically.
                    if usage_sink is not None:
                        u = getattr(chunk, "usage", None)
                        if u is not None:
                            is_dict = isinstance(u, dict)
                            for sink_key, provider_key in (
                                ("prompt_tokens", "prompt_tokens"),
                                ("completion_tokens", "completion_tokens"),
                                ("total_tokens", "total_tokens"),
                                ("cache_hit_tokens", "prompt_cache_hit_tokens"),
                                ("cache_miss_tokens", "prompt_cache_miss_tokens"),
                            ):
                                tok = (u.get(provider_key) if is_dict else getattr(u, provider_key, 0)) or 0
                                usage_sink[sink_key] = usage_sink.get(sink_key, 0) + tok
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
        except Exception as e:  # noqa: BLE001 — tolerant: never raise out of the stream
            error_msg = str(e)
            logger.warning(f"stream_chat failed for {model_name}: {error_msg[:200]}")
            yield f"{STREAM_ERROR_SENTINEL}{error_msg[:200]}"

    async def stream_chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        run_tool: Any,
        *,
        model: Optional[str] = None,
        max_tokens: int = 1200,
        temperature: float = 0.2,
        max_rounds: int = 4,
        usage_sink: Optional[Dict[str, int]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a chat completion that may call tools, executing them server-side between rounds.

        A function-calling sibling of :meth:`stream_chat` used by the "Ask this Filing" Copilot's
        numeric path (P5). The model is offered ``tools`` with ``tool_choice="auto"``; when it asks
        for one, this method runs it via ``run_tool(name, args)`` and feeds the result back, then lets
        the model continue. Plain answer text is yielded live (token-by-token) exactly like
        ``stream_chat``, so the caller's sentinel-split prose handling is unchanged.

        The tricky part is **stream-assembling tool calls**: a single tool call's
        ``function.arguments`` arrives as a sequence of string fragments across many chunks, keyed by
        ``tc.index``. We accumulate ``id``/``name`` and concatenate the argument fragments per index,
        then at the round's end append the assistant ``tool_calls`` message + one ``tool`` result
        message per call and loop again (the next round streams the answer). Rounds that only call
        tools normally carry empty ``content``, so yielding their content live is harmless.

        Args:
            messages: The conversation so far (mutated in place across rounds with tool turns).
            tools: OpenAI-format tool schemas to offer the model.
            run_tool: ``Callable[[str, dict], dict]`` executing a tool by name + decoded args.
            model: Model id (defaults to ``self.model``).
            max_tokens: Max completion tokens per round.
            temperature: Sampling temperature.
            max_rounds: Hard cap on tool-call rounds to bound latency/loops.

        Yields:
            Assistant answer ``delta.content`` strings in order. On any failure yields a single chunk
            prefixed with ``STREAM_ERROR_SENTINEL`` (so the consumer can surface a real error instead
            of streaming it as the answer) rather than raising, so the SSE contract is never broken.
        """
        model_name = model or self.model
        disable_thinking = _thinking_disabled_model(model_name, getattr(settings, "OPENAI_BASE_URL", None))
        try:
            for _ in range(max_rounds):
                create_kwargs: Dict[str, Any] = {
                    "model": model_name,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True,
                }
                if disable_thinking:
                    create_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
                # Ask for token usage on the final (choices-empty) chunk when the caller wants to
                # meter cost. Opt-in, so the default streaming contract is otherwise unchanged.
                if usage_sink is not None:
                    create_kwargs["stream_options"] = {"include_usage": True}

                stream = await self.client.chat.completions.create(**create_kwargs)

                # Assemble tool calls across chunks, keyed by their delta index. Each entry holds the
                # call id, function name, and the concatenated arguments-string fragments. Whether any
                # tool calls were assembled (not finish_reason) drives the round's branch below.
                tool_calls: Dict[int, Dict[str, str]] = {}
                content_parts: List[str] = []
                # Models narrate between tool rounds ("Let me gather the figures…") — chatter the
                # user must never see (field report: it streamed as the answer's opening lines).
                # A round's content is HELD BACK until the round's nature is known: the first
                # tool-call delta marks a tool round and its held content is dropped from the
                # stream (it still rides the assistant message below, so the model keeps its own
                # context); content that outgrows the hold-back cap is a real answer — flush and
                # stream live from there. A short final answer that never hits the cap flushes
                # when the round ends without tool calls.
                held: List[str] = []
                held_len = 0
                streaming_live = False

                async for chunk in stream:
                    if not chunk.choices:
                        # The include_usage final chunk has empty choices + a `usage` payload;
                        # accumulate it across tool rounds (best-effort, only when requested). Some
                        # OpenAI-compatible gateways return usage as a dict rather than an object, so
                        # handle both — getattr on a dict would silently zero the token counts.
                        if usage_sink is not None:
                            u = getattr(chunk, "usage", None)
                            if u is not None:
                                is_dict = isinstance(u, dict)
                                p_tok = (u.get("prompt_tokens") if is_dict else getattr(u, "prompt_tokens", 0)) or 0
                                c_tok = (u.get("completion_tokens") if is_dict else getattr(u, "completion_tokens", 0)) or 0
                                t_tok = (u.get("total_tokens") if is_dict else getattr(u, "total_tokens", 0)) or 0
                                # DeepSeek-specific: input tokens served from the context cache (HIT)
                                # vs not (MISS), priced ~120x apart. Absent on providers that don't
                                # cache → 0, and the cost estimate then treats all input as a miss.
                                hit_tok = (u.get("prompt_cache_hit_tokens") if is_dict else getattr(u, "prompt_cache_hit_tokens", 0)) or 0
                                miss_tok = (u.get("prompt_cache_miss_tokens") if is_dict else getattr(u, "prompt_cache_miss_tokens", 0)) or 0
                                usage_sink["prompt_tokens"] = usage_sink.get("prompt_tokens", 0) + p_tok
                                usage_sink["completion_tokens"] = usage_sink.get("completion_tokens", 0) + c_tok
                                usage_sink["total_tokens"] = usage_sink.get("total_tokens", 0) + t_tok
                                usage_sink["cache_hit_tokens"] = usage_sink.get("cache_hit_tokens", 0) + hit_tok
                                usage_sink["cache_miss_tokens"] = usage_sink.get("cache_miss_tokens", 0) + miss_tok
                        continue
                    choice = chunk.choices[0]
                    delta = choice.delta
                    if delta is None:
                        continue
                    if delta.content:
                        content_parts.append(delta.content)
                        if streaming_live:
                            yield delta.content
                        elif not tool_calls:
                            held.append(delta.content)
                            held_len += len(delta.content)
                            if held_len >= _TOOL_ROUND_HOLDBACK_CHARS:
                                streaming_live = True
                                yield "".join(held)
                                held = []
                        # else: a tool round's narration — dropped from the stream.
                    for tc in (delta.tool_calls or []):
                        slot = tool_calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                slot["name"] = tc.function.name
                            if tc.function.arguments:
                                slot["arguments"] += tc.function.arguments

                # No tool calls → this round's content was the final answer; flush anything the
                # hold-back was still sitting on (a short answer that never crossed the cap).
                if not tool_calls:
                    if held:
                        yield "".join(held)
                    return

                # Append the assistant tool-call turn, then run each call and append its result, so
                # the next round can stream the grounded answer.
                assembled = [tool_calls[idx] for idx in sorted(tool_calls)]
                messages.append({
                    "role": "assistant",
                    "content": "".join(content_parts),
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {"name": call["name"], "arguments": call["arguments"]},
                        }
                        for call in assembled
                    ],
                })
                for call in assembled:
                    try:
                        parsed_args = json.loads(call["arguments"] or "{}")
                    except (ValueError, TypeError):
                        parsed_args = {}
                    # Live "show the work" signal: announce the tool call, run it, then report the
                    # outcome. Labelling is left to the (copilot-specific) consumer.
                    yield STREAM_ACTIVITY_SENTINEL + json.dumps(
                        {"name": call["name"], "args": parsed_args, "phase": "start"}
                    )
                    result = run_tool(call["name"], parsed_args)
                    ok = not (isinstance(result, dict) and "error" in result)
                    yield STREAM_ACTIVITY_SENTINEL + json.dumps(
                        {"name": call["name"], "args": parsed_args, "phase": "done", "ok": ok}
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(result, default=str),
                    })
                # Loop continues for the next round (which should stream the answer).
        except Exception as e:  # noqa: BLE001 — tolerant: never raise out of the stream
            error_msg = str(e)
            logger.warning(f"stream_chat_with_tools failed for {model_name}: {error_msg[:200]}")
            yield f"{STREAM_ERROR_SENTINEL}{error_msg[:200]}"

