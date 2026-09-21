"""Durable, fail-closed USD 10 admission for the approved E7 acceptance programme.

The caller must reserve immediately before *every* provider attempt, including retries. A
reservation is never refunded: even missing usage or cancellation consumes its full worst-case
allowance. This is deliberately conservative, not a provider invoice. No network access occurs.

For plain text chat, UTF-8 bytes of the entire serialized request bound tokenized text bytes;
64 tokens per message and 256 per request cover chat framing. The bound is enforced before any
request, then priced at the supplied uncached input and maximum output rates. Any unrecognized
schema or provider behavior stops the durable ledger. The caller must separately freeze and review
the actual provider tokenizer/limits and fresh official prices before paid execution.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from urllib.parse import urlsplit

CAP = Decimal("10")
MAX_REQUESTS = 5082
ENVELOPES = {
    "summary_primary": (100_000, 12_000),
    "section_recovery": (20_000, 500),
    "attribution_verify": (20_000, 700),
}
REQUEST_FIELDS = {"model", "messages", "temperature", "max_tokens", "response_format",
                  "stream", "stream_options", "extra_body"}
ROUND = Decimal("0.000000001")
PER_REQUEST_PAD = Decimal("0.000001")


class BudgetStopped(RuntimeError):
    """No further provider request may be sent for this programme."""


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def _money(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid price") from exc
    if not result.is_finite() or result <= 0:
        raise ValueError("price must be positive and finite")
    return result


def _utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("pricing timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("pricing timestamp must carry a timezone")
    return parsed.astimezone(timezone.utc)


class BudgetLedger:
    """One persistent programme, bound to exact pricing and provider identity."""

    def __init__(self, path: str | Path, pricing: dict, programme_id: str):
        self.path = Path(path)
        if not programme_id or not isinstance(programme_id, str):
            raise ValueError("programme_id is required")
        if not isinstance(pricing, dict):
            raise ValueError("pricing evidence is required")
        required = {"model", "base_url", "official_source", "verified_at", "valid_until",
                    "uncached_input_per_million", "max_output_per_million"}
        if set(pricing) != required or not all(isinstance(pricing[k], str) and pricing[k]
                                                for k in ("model", "base_url", "official_source")):
            raise ValueError("complete exact pricing evidence is required")
        url = urlsplit(pricing["base_url"])
        if (url.scheme != "https" or url.hostname != "api.deepseek.com" or url.username
                or url.password or url.query or url.fragment or url.path.rstrip("/") != "/v1"):
            raise ValueError("exact DeepSeek API base URL required")
        source = urlsplit(pricing["official_source"])
        if (not pricing["model"].startswith("deepseek-") or source.scheme != "https"
                or source.hostname not in {"deepseek.com", "api-docs.deepseek.com"}
                or source.username or source.password or source.query or source.fragment):
            raise ValueError("exact DeepSeek model and official price source required")
        verified, expires = _utc(pricing["verified_at"]), _utc(pricing["valid_until"])
        now = datetime.now(timezone.utc)
        if verified > now or now - verified > timedelta(hours=24) or expires <= verified:
            raise ValueError("invalid pricing validity interval")
        self.pricing = pricing.copy()
        self.input_rate = _money(pricing["uncached_input_per_million"])
        self.output_rate = _money(pricing["max_output_per_million"])
        self.programme_id = programme_id
        self.pricing_hash = hashlib.sha256(_canonical(pricing).encode()).hexdigest()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS programme (
                id INTEGER PRIMARY KEY CHECK (id = 1), programme_id TEXT NOT NULL,
                pricing_hash TEXT NOT NULL, stop_reason TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY, slot_id TEXT NOT NULL, operation TEXT NOT NULL,
                request_hash TEXT NOT NULL, input_bound INTEGER NOT NULL, output_max INTEGER NOT NULL,
                reserved_usd TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
                usage_json TEXT, known_usage_upper_usd TEXT, actual_model TEXT, outcome TEXT)""")
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT programme_id, pricing_hash FROM programme WHERE id=1").fetchone()
            if row is None:
                db.execute("INSERT INTO programme VALUES (1, ?, ?, NULL)",
                           (programme_id, self.pricing_hash))
            elif row != (programme_id, self.pricing_hash):
                db.execute("UPDATE programme SET stop_reason=COALESCE(stop_reason, ?)",
                           ("programme or pricing identity changed",))
            db.commit()
        if row is not None and row != (programme_id, self.pricing_hash):
            raise BudgetStopped("programme or pricing identity changed")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    def _stop(db: sqlite3.Connection, reason: str) -> None:
        db.execute("UPDATE programme SET stop_reason=COALESCE(stop_reason, ?)", (reason,))
        db.commit()
        raise BudgetStopped(reason)

    def _check(self, db: sqlite3.Connection, *, admission: bool) -> None:
        row = db.execute("SELECT programme_id, pricing_hash, stop_reason FROM programme WHERE id=1").fetchone()
        if row is None or row[:2] != (self.programme_id, self.pricing_hash):
            self._stop(db, "programme or pricing identity changed")
        if row[2] and admission:
            raise BudgetStopped(row[2])
        now = datetime.now(timezone.utc)
        if admission and (now >= _utc(self.pricing["valid_until"])
                          or now - _utc(self.pricing["verified_at"]) > timedelta(hours=24)):
            self._stop(db, "pricing evidence expired")

    def _validate_request(self, request: dict, operation: str, base_url: str) -> tuple[int, int, str]:
        if operation not in ENVELOPES or not isinstance(request, dict):
            raise ValueError("unknown operation or request schema")
        if (base_url != self.pricing["base_url"] or request.get("model") != self.pricing["model"]
                or set(request) - REQUEST_FIELDS):
            raise ValueError("unpriced model, origin or request field")
        messages = request.get("messages")
        maximum = request.get("max_tokens")
        if (not isinstance(messages, list) or not messages or type(maximum) is not int
                or not 0 < maximum <= ENVELOPES[operation][1]):
            raise ValueError("invalid messages or output maximum")
        for message in messages:
            if (not isinstance(message, dict) or set(message) != {"role", "content"}
                    or message["role"] not in {"system", "user", "assistant"}
                    or not isinstance(message["content"], str)):
                raise ValueError("non-text or unknown chat message")
        if "temperature" in request:
            temperature = request["temperature"]
            if (type(temperature) not in (int, float) or not math.isfinite(temperature)
                    or not 0 <= temperature <= 2):
                raise ValueError("invalid temperature")
        if request.get("response_format", {"type": "json_object"}) != {"type": "json_object"}:
            raise ValueError("unsupported response format")
        if "stream" in request and type(request["stream"]) is not bool:
            raise ValueError("invalid stream setting")
        if "stream_options" in request and (request.get("stream") is not True
                                             or request["stream_options"] != {"include_usage": True}):
            raise ValueError("unknown stream options")
        if "extra_body" in request and request["extra_body"] != {"thinking": {"type": "disabled"}}:
            raise ValueError("thinking or unknown extra body is unsupported")
        raw = _canonical(request)
        bound = len(raw.encode("utf-8")) + 64 * len(messages) + 256
        if bound > ENVELOPES[operation][0]:
            raise ValueError("input token upper bound exceeds envelope")
        return bound, maximum, hashlib.sha256(raw.encode()).hexdigest()

    def reserve(self, slot_id: str, request: dict, operation: str, base_url: str) -> int:
        """Atomically charge the full worst case before the caller sends a request."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._check(db, admission=True)
            try:
                if not isinstance(slot_id, str) or not slot_id.strip():
                    raise ValueError("slot identity required")
                bound, maximum, digest = self._validate_request(request, operation, base_url)
            except (ValueError, TypeError, OverflowError) as exc:
                self._stop(db, str(exc))
            count = db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
            # Recompute from decimal strings: SQLite REAL is never the monetary authority.
            charged = sum((Decimal(row[0]) for row in db.execute("SELECT reserved_usd FROM reservations")),
                          Decimal(0))
            reserve = ((bound * self.input_rate + maximum * self.output_rate) / 1_000_000
                       + PER_REQUEST_PAD).quantize(ROUND, rounding=ROUND_CEILING)
            if count >= MAX_REQUESTS or charged + reserve > CAP:
                self._stop(db, "acceptance request or USD 10 ceiling exhausted")
            cursor = db.execute("""INSERT INTO reservations
                (slot_id, operation, request_hash, input_bound, output_max, reserved_usd)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (slot_id, operation, digest, bound, maximum, str(reserve)))
            db.commit()
            return int(cursor.lastrowid)

    def settle(self, reservation_id: int, usage: dict | None,
               actual_model: str | None, outcome: str) -> None:
        """Record observed usage without refunding the conservative reservation."""
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._check(db, admission=False)
            row = db.execute("SELECT input_bound, output_max, reserved_usd, status FROM reservations WHERE id=?",
                             (reservation_id,)).fetchone()
            if row is None or row[3] != "pending" or outcome not in {"success", "error", "cancelled"}:
                self._stop(db, "unknown or already settled reservation/outcome")
            if actual_model is not None and actual_model != self.pricing["model"]:
                self._stop(db, "unpriced actual model")
            if outcome == "success" and actual_model is None:
                self._stop(db, "successful response lacks actual model")
            known = None
            if usage is not None:
                if not isinstance(usage, dict) or set(usage) - {"prompt_tokens", "completion_tokens", "total_tokens"}:
                    self._stop(db, "unknown usage schema")
                inp, out = usage.get("prompt_tokens"), usage.get("completion_tokens")
                if (type(inp) is not int or type(out) is not int or inp < 0 or out < 0
                        or inp > row[0] or out > row[1]
                        or ("total_tokens" in usage and usage["total_tokens"] != inp + out)):
                    self._stop(db, "usage exceeds reservation or is incomplete")
                known = str(((inp * self.input_rate + out * self.output_rate) / 1_000_000)
                            .quantize(ROUND, rounding=ROUND_CEILING))
            db.execute("""UPDATE reservations SET status='settled', usage_json=?,
                known_usage_upper_usd=?, actual_model=?, outcome=? WHERE id=?""",
                (_canonical(usage) if usage is not None else None, known, actual_model,
                 outcome, reservation_id))
            db.commit()

    def snapshot(self) -> dict:
        """Read the durable ceiling, reservations and stop state without altering it."""
        with self._connect() as db:
            row = db.execute("SELECT programme_id, pricing_hash, stop_reason FROM programme WHERE id=1").fetchone()
            entries = db.execute("SELECT reserved_usd, known_usage_upper_usd, status FROM reservations").fetchall()
        return {"programme_id": row[0], "pricing_hash": row[1], "cap_usd": str(CAP),
                "max_requests": MAX_REQUESTS, "requests": len(entries),
                "reserved_usd": str(sum((Decimal(r[0]) for r in entries), Decimal(0))),
                "known_usage_upper_usd": str(sum((Decimal(r[1]) for r in entries if r[1]), Decimal(0))),
                "pending": sum(r[2] == "pending" for r in entries), "stop_reason": row[2]}
