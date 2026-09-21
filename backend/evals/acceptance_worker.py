"""One E7 invocation through the application's production summary pipeline.

This is a measurement adapter, not another generator. The caller freezes the manifest,
configuration, source archive, budget and slot identity before entering this module.
Each invocation must run in its own process: the app's settings, SQLite engine and
in-flight generation registry are process-global.
"""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from contextlib import ExitStack
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch


class InvalidMeasurement(RuntimeError):
    """A slot cannot be scored because its required evidence is incomplete."""


REQUIRED_FROZEN_SETTINGS = frozenset({
    "OPENAI_BASE_URL", "AI_DEFAULT_MODEL", "AI_FALLBACK_MODEL", "AI_FALLBACK_BASE_URL",
    "AI_FAST_MODEL", "AI_SECTION_RECOVERY_MODEL", "AI_SUMMARY_THINKING_EFFORT",
    "AI_SUMMARY_THINKING_MAX_TOKENS", "USE_STRUCTURED_OUTPUT", "USE_EDGARTOOLS_SECTIONS",
    "AI_QUALITY_GATE", "AI_FIGURE_TRACE_GATE", "AI_FORWARD_QUOTE_GATE",
    "AI_ATTRIBUTION_GATE", "AI_ATTRIBUTION_VERIFY", "AI_EVIDENCE_SNAP",
    "EVIDENCE_SNAP_MIN_SCORE", "ENABLE_FPI_FILINGS", "USE_STATEMENT_FINANCIALS",
    "RICHER_FINANCIALS_ENABLED", "STREAM_HEARTBEAT_INTERVAL", "STREAM_SECTION_REVEAL",
    "SEC_MAX_RETRIES", "SEC_RATE_LIMIT_PER_SECOND", "MAX_CONCURRENT_GENERATIONS",
})


def expected_database_url(invocation_dir: Path) -> str:
    """The only database URL permitted in an invocation child process."""
    return "sqlite:///" + str(Path(invocation_dir).resolve() / "invocation.sqlite3")


def _json_default(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"Cannot retain {type(value).__module__}.{type(value).__name__} as JSON")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")


def _append_jsonl(handle: Any, value: Any) -> None:
    handle.write(json.dumps(value, ensure_ascii=False, default=_json_default) + "\n")
    handle.flush()


def _digest_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def _preflight_sources(filing_spec: Mapping[str, Any], source_root: Path) -> dict[str, Any]:
    if not source_root.is_dir():
        raise InvalidMeasurement(f"Source archive absent: {source_root}")
    packets = filing_spec.get("source_packets")
    if not isinstance(packets, list) or not packets:
        raise InvalidMeasurement("Filing lacks source packets")
    root = source_root.resolve(strict=True)
    evidence: dict[str, Any] = {}
    for packet in packets:
        role = packet["role"]
        if role in evidence:
            raise InvalidMeasurement(f"Duplicate source role: {role}")
        relative = Path(packet["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise InvalidMeasurement(f"Unsafe source path: {relative}")
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise InvalidMeasurement(f"Source path escapes archive: {relative}")
        size, sha = _digest_file(path)
        if size != packet["bytes"] or sha != packet["sha256"]:
            raise InvalidMeasurement(f"Source packet hash/size mismatch: {relative}")
        provenance = packet.get("provenance") or {}
        if provenance.get("representation") != "httpx_decoded_response_text_utf8":
            raise InvalidMeasurement(f"Unknown source representation: {relative}")
        if provenance.get("sha256") != sha:
            raise InvalidMeasurement(f"Source provenance hash mismatch: {relative}")
        evidence[role] = {"path": str(path), "bytes": size, "sha256": sha,
                          "requested_url": provenance.get("requested_url")}
    primary = evidence.get("primary")
    if not primary or primary["sha256"] != filing_spec.get("source_sha256"):
        raise InvalidMeasurement("Primary packet does not match manifest source_sha256")
    if primary["requested_url"] != filing_spec.get("document_url"):
        raise InvalidMeasurement("Primary requested URL differs from manifest document URL")
    return evidence


def _check_configuration(invocation_dir: Path, config: Mapping[str, Any]) -> Any:
    # Import the app only after all source packets have been validated, and refuse a
    # parent process that already bootstrapped a production (or shared) DB engine.
    from app.config import settings

    expected = expected_database_url(invocation_dir)
    if settings.DATABASE_URL != expected or os.getenv("DATABASE_URL") != expected:
        raise InvalidMeasurement("Child DATABASE_URL is not the exact fresh invocation SQLite URL")
    if (invocation_dir / "invocation.sqlite3").exists():
        raise InvalidMeasurement("Invocation SQLite already exists")
    from app import database

    if str(database.engine.url) != expected:
        raise InvalidMeasurement("Imported app database engine is not the invocation SQLite engine")
    frozen = config.get("frozen_settings")
    if not isinstance(frozen, dict) or not frozen:
        raise InvalidMeasurement("Missing explicit frozen settings")
    if not REQUIRED_FROZEN_SETTINGS.issubset(frozen):
        raise InvalidMeasurement(
            f"Missing frozen settings: {sorted(REQUIRED_FROZEN_SETTINGS - frozen.keys())}"
        )
    for key, value in frozen.items():
        if key.endswith(("_KEY", "_SECRET", "_TOKEN", "_PASSWORD")):
            raise InvalidMeasurement(f"Credential field prohibited in frozen settings: {key}")
        if not hasattr(settings, key) or getattr(settings, key) != value:
            raise InvalidMeasurement(f"Frozen setting differs from effective setting: {key}")
    if settings.AI_FALLBACK_MODEL or settings.AI_FALLBACK_BASE_URL or settings.AI_FALLBACK_API_KEY:
        raise InvalidMeasurement("Acceptance child must have no fallback provider route")
    if settings.POSTHOG_API_KEY:
        raise InvalidMeasurement("Acceptance child must have no PostHog credential")
    if not config.get("allow_sec_network") or not config.get("allow_provider"):
        raise InvalidMeasurement("Execution must be explicitly armed by the parent")
    return database


def _validate_identity(filing_spec: Mapping[str, Any]) -> None:
    required = ("holdout_id", "ticker", "company_name", "cik", "filing_type",
                "accession_number", "filing_date", "period_of_report", "document_url",
                "index_url", "source_sha256")
    for key in required:
        if not filing_spec.get(key):
            raise InvalidMeasurement(f"Missing selected filing identity: {key}")
    if filing_spec["filing_type"] not in {"10-K", "10-Q", "20-F", "6-K"}:
        raise InvalidMeasurement("Unsupported selected filing type")
    if not str(filing_spec["document_url"]).startswith("https://www.sec.gov/Archives/"):
        raise InvalidMeasurement("Document URL is not an official SEC archive URL")


def _seed_filing(database: Any, filing_spec: Mapping[str, Any]) -> int:
    from app.models import Company, Filing

    with database.SessionLocal() as session:
        company = Company(cik=str(filing_spec["cik"]), ticker=filing_spec["ticker"],
                          name=filing_spec["company_name"])
        session.add(company)
        session.flush()
        filing = Filing(company_id=company.id,
                        accession_number=filing_spec["accession_number"],
                        filing_type=filing_spec["filing_type"],
                        filing_date=datetime.fromisoformat(filing_spec["filing_date"]),
                        period_end_date=datetime.fromisoformat(filing_spec["period_of_report"]),
                        document_url=filing_spec["document_url"],
                        sec_url=filing_spec["index_url"])
        session.add(filing)
        session.commit()
        return filing.id


async def run_invocation(
    filing_spec: Mapping[str, Any], invocation_dir: Path, config: Mapping[str, Any], budget_meter: Any
) -> dict[str, Any]:
    """Execute exactly one selected accession in a fresh child process.

    Preflight failures raise ``InvalidMeasurement`` before a database or provider
    artifact is created. Once execution starts, every event and error is durable in
    the invocation directory and the returned receipt is never a quality verdict.
    """
    invocation_dir = Path(invocation_dir).resolve()
    _validate_identity(filing_spec)
    evidence = _preflight_sources(filing_spec, Path(config["source_root"]))
    if filing_spec["filing_type"] == "6-K":
        raise InvalidMeasurement(
            "6-K exhibit text lacks a verifiable packet-to-production-extractor identity mapping; "
            "refusing provider admission"
        )
    database = _check_configuration(invocation_dir, config)
    if budget_meter is None or not callable(getattr(budget_meter, "snapshot", None)):
        raise InvalidMeasurement("A durable provider budget meter with snapshot() is required")
    if invocation_dir.exists() and any(invocation_dir.iterdir()):
        raise InvalidMeasurement("Invocation directory must be empty")

    from app.models import Base, Filing, Summary
    from app.services import summary_pipeline
    from app.services.ai import provider_requests
    from app.services.export_service import export_service
    from app.services.summary_sections import render_sections, render_sections_json, sections_to_markdown

    invocation_dir.mkdir(parents=True, exist_ok=True)
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "identity": {key: filing_spec[key] for key in ("holdout_id", "ticker", "cik", "filing_type", "accession_number")},
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "incomplete", "eligible_for_measurement": False,
        "source_packets": evidence, "source_identity": "unverified",
        "source_identity_scope": "Only the fetched primary HTTP-decoded text can be matched byte-for-byte; "
                                 "edgartools/XBRL results retain accession and CIK but lack packet replay proof.",
        "errors": [], "artifacts": {},
    }
    _write_json(invocation_dir / "frozen_settings.json", dict(config["frozen_settings"]))
    _write_json(invocation_dir / "source_evidence.json", evidence)
    events_path = invocation_dir / "events.jsonl"
    previews_path = invocation_dir / "raw_previews.jsonl"
    grounding_path = invocation_dir / "grounding.json"
    receipt["artifacts"].update(events=events_path.name, raw_previews=previews_path.name,
                                grounding=grounding_path.name)
    grounding: dict[str, Any] = {"production_pipeline": "app.services.summary_pipeline.stream_filing_summary",
                                 "source_calls": [], "summarizer_calls": [], "summarizer_returns": []}
    source_ok = False
    sixk_used = False
    summarizer_return_statuses: list[str] = []
    terminal_events: list[str] = []
    preview_errors: list[str] = []
    summaries: list[Any] = []
    try:
        Base.metadata.create_all(bind=database.engine)
        filing_id = _seed_filing(database, filing_spec)
        original_fetch = summary_pipeline.sec_edgar_service.get_filing_document
        original_sixk = summary_pipeline.get_sixk_text
        original_summarize = summary_pipeline.openai_service.summarize_filing
        original_xbrl = summary_pipeline.xbrl_service.get_xbrl_data
        original_sections = summary_pipeline.xbrl_service.get_filing_sections
        original_statement = summary_pipeline.acquire_statement_context
        original_excerpt = summary_pipeline.get_or_cache_excerpt

        async def measured_fetch(url: str, *args: Any, **kwargs: Any) -> Any:
            nonlocal source_ok
            if url != filing_spec["document_url"]:
                raise InvalidMeasurement(f"Unexpected primary document URL: {url}")
            content = await original_fetch(url, *args, **kwargs)
            encoded = content.encode("utf-8") if isinstance(content, str) else b""
            digest = hashlib.sha256(encoded).hexdigest()
            record = {"owner": "sec_edgar_service.get_filing_document", "url": url,
                      "bytes": len(encoded), "sha256": digest}
            grounding["source_calls"].append(record)
            source_ok = digest == evidence["primary"]["sha256"] and len(encoded) == evidence["primary"]["bytes"]
            if not source_ok:
                raise InvalidMeasurement("Production-fetched primary differs from retained source packet")
            return content

        async def measured_sixk(accession: str, cik: str) -> Any:
            nonlocal sixk_used
            if accession != filing_spec["accession_number"] or str(cik) != str(filing_spec["cik"]):
                raise InvalidMeasurement("6-K extractor requested a different accession/CIK")
            sixk_used = True
            content = await original_sixk(accession, cik)
            encoded = content.encode("utf-8") if isinstance(content, str) else b""
            grounding["source_calls"].append({"owner": "get_sixk_text", "accession": accession,
                                                "cik": str(cik), "bytes": len(encoded),
                                                "sha256": hashlib.sha256(encoded).hexdigest(),
                                                "source_packet_match": "unavailable"})
            return content

        async def measured_xbrl(accession: str, cik: str, *args: Any, **kwargs: Any) -> Any:
            if accession != filing_spec["accession_number"] or str(cik) != str(filing_spec["cik"]):
                raise InvalidMeasurement("XBRL requested a different accession/CIK")
            result = await original_xbrl(accession, cik, *args, **kwargs)
            grounding["source_calls"].append({"owner": "xbrl_service.get_xbrl_data", "result": result})
            return result

        async def measured_sections(accession: str, cik: str, *args: Any, **kwargs: Any) -> Any:
            if accession != filing_spec["accession_number"] or str(cik) != str(filing_spec["cik"]):
                raise InvalidMeasurement("Sections requested a different accession/CIK")
            result = await original_sections(accession, cik, *args, **kwargs)
            grounding["source_calls"].append({"owner": "xbrl_service.get_filing_sections", "result": result})
            return result

        def measured_statement(*args: Any, **kwargs: Any) -> Any:
            result = original_statement(*args, **kwargs)
            grounding["source_calls"].append({"owner": "acquire_statement_context",
                                                "args": args, "kwargs": kwargs, "result": result})
            return result

        def measured_excerpt(db: Any, filing: Any, filing_text: Any,
                             sections: Any = None) -> Any:
            result = original_excerpt(db, filing, filing_text, sections=sections)
            grounding["source_calls"].append({
                "owner": "get_or_cache_excerpt", "accession": filing.accession_number,
                "filing_text_sha256": hashlib.sha256((filing_text or "").encode("utf-8")).hexdigest(),
                "sections": sections, "excerpt": result,
            })
            return result

        with events_path.open("w", encoding="utf-8") as events, previews_path.open("w", encoding="utf-8") as previews:
            async def measured_summarize(*args: Any, **kwargs: Any) -> Any:
                callback = kwargs.get("stream_cb")
                grounding["summarizer_calls"].append({"args": args,
                                                       "kwargs": {k: v for k, v in kwargs.items() if k != "stream_cb"},
                                                       "stream_callback_present": callback is not None})

                async def raw_callback(markdown: str) -> None:
                    try:
                        _append_jsonl(previews, {"generation_ordinal": 0,
                                                  "provider_attempt": provider_requests.current_provider_attempt(),
                                                  "markdown": markdown})
                    except Exception as error:  # noqa: BLE001 - provider may swallow callback errors
                        preview_errors.append(f"{type(error).__name__}: {error}")
                        raise
                    if callback is not None:
                        await callback(markdown)

                # Preserve the frozen production stream setting: a disabled callback
                # must not turn a non-streaming provider request into a streaming one.
                kwargs["stream_cb"] = raw_callback if callback is not None else None
                result = await original_summarize(*args, **kwargs)
                grounding["summarizer_returns"].append(deepcopy(result))
                summarizer_return_statuses.append(result.get("status", "complete") if isinstance(result, dict) else "invalid")
                summaries.append(result)
                return result

            with ExitStack() as stack:
                stack.enter_context(patch.object(summary_pipeline.sec_edgar_service, "get_filing_document", measured_fetch))
                stack.enter_context(patch.object(summary_pipeline, "get_sixk_text", measured_sixk))
                stack.enter_context(patch.object(summary_pipeline.xbrl_service, "get_xbrl_data", measured_xbrl))
                stack.enter_context(patch.object(summary_pipeline.xbrl_service, "get_filing_sections", measured_sections))
                stack.enter_context(patch.object(summary_pipeline, "acquire_statement_context", measured_statement))
                stack.enter_context(patch.object(summary_pipeline, "get_or_cache_excerpt", measured_excerpt))
                stack.enter_context(patch.object(summary_pipeline.openai_service, "summarize_filing", measured_summarize))
                stack.enter_context(provider_requests.measure_provider_requests(budget_meter))
                async for event in summary_pipeline.stream_filing_summary(
                    filing_id=filing_id, current_user=None, user_id=None,
                    telemetry_distinct_id="e7-measurement", telemetry_entry_point=None,
                    telemetry_ctx={}, emit_funnel_telemetry=False, force_regenerate=True,
                ):
                    _append_jsonl(events, event)
                    if event.get("type") in {"error", "partial", "complete"}:
                        terminal_events.append(event["type"])

        with database.SessionLocal() as session:
            summary = session.query(Summary).filter(Summary.filing_id == filing_id).one_or_none()
            filing = session.query(Filing).filter(Filing.id == filing_id).one()
            if summary is not None:
                canonical = {column.name: getattr(summary, column.name) for column in Summary.__table__.columns}
                _write_json(invocation_dir / "canonical_summary.json", canonical)
                receipt["artifacts"]["canonical_summary"] = "canonical_summary.json"
                sections = render_sections(summary.raw_summary)
                (invocation_dir / "rendered_summary.md").write_text(
                    sections_to_markdown(sections), encoding="utf-8")
                _write_json(invocation_dir / "rendered_sections.json", render_sections_json(summary.raw_summary))
                (invocation_dir / "export.html").write_text(
                    export_service.generate_pdf_html(summary, filing), encoding="utf-8")
                receipt["artifacts"].update(rendered_summary="rendered_summary.md",
                                            rendered_sections="rendered_sections.json", export_html="export.html")
        receipt["source_identity"] = "primary_verified" if source_ok and not sixk_used else "incomplete"
        if not source_ok:
            receipt["errors"].append("Primary source was not fetched and hash-verified by production SEC service")
        if sixk_used:
            receipt["errors"].append("6-K exhibit grounding lacks a packet-to-extractor identity proof")
        if terminal_events != ["complete"]:
            receipt["errors"].append(f"Pipeline terminal events were {terminal_events!r}, not one complete")
        if preview_errors:
            receipt["errors"].append(f"Raw preview retention failed: {preview_errors!r}")
        if summarizer_return_statuses != ["complete"]:
            receipt["errors"].append(f"Summarizer statuses were {summarizer_return_statuses!r}")
        if summary is None:
            receipt["errors"].append("Pipeline did not persist a canonical Summary row")
        elif (summary.raw_summary or {}).get("status") != "complete":
            receipt["errors"].append("Persisted summary status was not complete")
    except BaseException as error:
        receipt["errors"].append(f"{type(error).__name__}: {error}")
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise
    finally:
        # Grounding and accounting survive failed/partial pipeline attempts. A missing
        # snapshot itself invalidates measurement; never impute zero provider usage.
        try:
            _write_json(grounding_path, grounding)
        except Exception as error:  # noqa: BLE001 - preserve an explicit evidence gap
            receipt["errors"].append(f"Grounding serialization failed: {type(error).__name__}: {error}")
        try:
            _write_json(invocation_dir / "provider_accounting.json", budget_meter.snapshot())
            receipt["artifacts"]["provider_accounting"] = "provider_accounting.json"
        except Exception as error:  # noqa: BLE001 - unknown charges remain incomplete
            receipt["errors"].append(f"Provider accounting unavailable: {type(error).__name__}: {error}")
        receipt["finished_at"] = datetime.now(timezone.utc).isoformat()
        receipt["eligible_for_measurement"] = not receipt["errors"]
        receipt["status"] = "complete" if receipt["eligible_for_measurement"] else "incomplete"
        _write_json(invocation_dir / "receipt.json", receipt)
        database.engine.dispose()
    return receipt
