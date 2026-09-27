"""Task-local durable provider-attempt meter for the fresh paired pilot."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

CAP = Decimal("0.950000")
MAX_CALLS = 20
INPUT_RATE = Decimal("0.150000")   # off-peak cache-miss USD / 1M tokens
OUTPUT_RATE = Decimal("0.600000")  # off-peak output USD / 1M tokens
ROUND = Decimal("0.000000001")


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


class PilotStopped(RuntimeError):
    pass


class PilotMeter:
    """Implements the existing measure_provider_requests meter interface.

    Reservations charge the full request-byte-as-token input bound and declared output
    ceiling. They are never refunded, including errors, cancellations or unknown usage.
    """

    def __init__(self, path: Path, slot_id: str, manifest_sha256: str):
        self.path, self.slot_id = path, slot_id
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("""CREATE TABLE IF NOT EXISTS programme (
                id INTEGER PRIMARY KEY CHECK(id=1), manifest_sha256 TEXT NOT NULL,
                stop_reason TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY, slot_id TEXT NOT NULL, operation TEXT NOT NULL,
                request_sha256 TEXT NOT NULL, input_bound INTEGER NOT NULL,
                output_max INTEGER NOT NULL, reserved_usd TEXT NOT NULL,
                status TEXT NOT NULL, outcome TEXT, usage_json TEXT, actual_model TEXT)""")
            row = db.execute("SELECT manifest_sha256, stop_reason FROM programme WHERE id=1").fetchone()
            if row is None:
                db.execute("INSERT INTO programme VALUES(1, ?, NULL)", (manifest_sha256,))
            elif row[0] != manifest_sha256:
                db.execute("UPDATE programme SET stop_reason=COALESCE(stop_reason, ?)",
                           ("manifest identity changed",))
                db.commit()
                raise PilotStopped("manifest identity changed")
            elif row[1]:
                raise PilotStopped(row[1])

    def _db(self):
        return sqlite3.connect(self.path, timeout=30)

    @staticmethod
    def _halt(db: sqlite3.Connection, reason: str):
        db.execute("UPDATE programme SET stop_reason=COALESCE(stop_reason, ?)", (reason,))
        db.commit()
        raise PilotStopped(reason)

    def reserve(self, request: dict, operation: str, base_url: str) -> int:
        allowed = {"model", "messages", "max_tokens", "response_format", "stream",
                   "stream_options", "extra_body", "reasoning_effort", "temperature"}
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            stop = db.execute("SELECT stop_reason FROM programme WHERE id=1").fetchone()[0]
            if stop:
                raise PilotStopped(stop)
            now = datetime.now(timezone.utc)
            if now.weekday() < 5 and (1 <= now.hour < 4 or 6 <= now.hour < 10):
                self._halt(db, "off-peak-only pilot reached an official peak pricing window")
            if base_url != "https://api.deepseek.com/v1" or set(request) - allowed:
                self._halt(db, "provider origin or request schema changed")
            messages, maximum = request.get("messages"), request.get("max_tokens")
            if request.get("model") != "deepseek-flash" or not isinstance(messages, list):
                self._halt(db, "model or messages changed")
            if request.get("response_format") != {"type": "json_object"}:
                self._halt(db, "response format changed")
            if operation == "summary_primary":
                candidate = self.slot_id.endswith("-thinking-low")
                expected_control_max = 12000 if "-10-K-" in self.slot_id else 8000
                if candidate:
                    valid = (maximum == 24000 and request.get("reasoning_effort") == "low"
                             and request.get("extra_body") == {"thinking": {"type": "enabled"}}
                             and "temperature" not in request)
                else:
                    valid = (self.slot_id.endswith("-control")
                             and maximum == expected_control_max
                             and request.get("extra_body") == {"thinking": {"type": "disabled"}}
                             and request.get("temperature") == 0.2
                             and "reasoning_effort" not in request)
                if not valid:
                    self._halt(db, "fresh-pair primary envelope changed")
            elif operation == "section_recovery":
                if (type(maximum) is not int or not 0 < maximum <= 500
                        or request.get("extra_body") != {"thinking": {"type": "disabled"}}
                        or "reasoning_effort" in request):
                    self._halt(db, "recovery envelope changed")
            else:
                self._halt(db, "unapproved operation")
            raw = canonical(request)
            bound = len(raw) + 64 * len(messages) + 256
            reserve = ((Decimal(bound) * INPUT_RATE + Decimal(maximum) * OUTPUT_RATE)
                       / Decimal(1_000_000)).quantize(ROUND, rounding=ROUND_CEILING)
            count = db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
            charged = sum((Decimal(row[0]) for row in
                           db.execute("SELECT reserved_usd FROM reservations")), Decimal(0))
            if count >= MAX_CALLS or charged + reserve > CAP:
                self._halt(db, "pilot physical-call or USD 0.95 ceiling exhausted")
            cur = db.execute("""INSERT INTO reservations
                (slot_id, operation, request_sha256, input_bound, output_max, reserved_usd, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
                (self.slot_id, operation, hashlib.sha256(raw).hexdigest(), bound, maximum,
                 str(reserve)))
            db.commit()
            return int(cur.lastrowid)

    def settle(self, reservation_id: int, usage, actual_model: str | None, outcome: str) -> None:
        normalized = None
        if usage is not None:
            normalized = {key: usage.get(key) for key in
                          ("prompt_tokens", "completion_tokens", "total_tokens")}
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status, input_bound, output_max FROM reservations WHERE id=?",
                             (reservation_id,)).fetchone()
            if row is None or row[0] != "pending":
                self._halt(db, "unknown or already-settled reservation")
            if actual_model is not None and actual_model != "deepseek-flash":
                self._halt(db, "actual model changed")
            if outcome == "success" and actual_model is None:
                self._halt(db, "successful response lacks an actual model")
            if normalized is not None:
                prompt, completion, total = (normalized[k] for k in
                                             ("prompt_tokens", "completion_tokens", "total_tokens"))
                if (type(prompt) is not int or type(completion) is not int
                        or prompt < 0 or completion < 0 or prompt > row[1]
                        or completion > row[2]
                        or (total is not None and total != prompt + completion)):
                    self._halt(db, "reported usage exceeds its conservative reservation")
            db.execute("""UPDATE reservations SET status='settled', outcome=?, usage_json=?,
                actual_model=? WHERE id=?""",
                (outcome, json.dumps(normalized, sort_keys=True) if normalized else None,
                 actual_model, reservation_id))
            db.commit()

    def slot_has_attempt(self, slot_id: str) -> bool:
        with self._db() as db:
            return db.execute("SELECT 1 FROM reservations WHERE slot_id=? LIMIT 1", (slot_id,)).fetchone() is not None

    def snapshot(self) -> dict:
        with self._db() as db:
            rows = db.execute("""SELECT id, slot_id, operation, request_sha256, input_bound,
                output_max, reserved_usd, status, outcome, usage_json, actual_model
                FROM reservations ORDER BY id""").fetchall()
            stop = db.execute("SELECT stop_reason FROM programme WHERE id=1").fetchone()[0]
        return {"hard_cap_usd": str(CAP), "max_physical_calls": MAX_CALLS,
                "reserved_usd": str(sum((Decimal(r[6]) for r in rows), Decimal(0))),
                "stop_reason": stop,
                "reservations": [dict(zip(("id", "slot_id", "operation", "request_sha256",
                    "input_bound", "output_max", "reserved_usd", "status", "outcome",
                    "usage_json", "actual_model"), row)) for row in rows]}
