"""Offline source adapter for E7; not an authorization to lift archive_binding_hold.

The caller supplies a hash-bound complete SEC submission, raw SEC submissions JSON,
and raw SEC companyfacts JSON. The application's section, instance-XBRL, and
companyfacts parsers still run unchanged. This module only substitutes their source
resolution and refuses uncatalogued source access. It is process-global patching and
must run in one isolated invocation child, never in the parent process.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.parse import urlparse
from unittest.mock import patch

from .acceptance_worker import InvalidMeasurement

_SEC_SCRIPT_RE = re.compile(rb'<script type="text/javascript"  src="/vkpr/[A-Za-z0-9/_-]+"></script>')
_SEC_SCRIPT_SHA256 = "6bf38ff34be5a73efcb89a8a31016c3e0d55d70b474969e903ea7e064a64acbf"


def _safe_source_file(root: Path, relative_value: Any, label: str) -> Path:
    """Resolve one regular, non-symlink archive file below an already frozen root."""
    if root.is_symlink():
        raise InvalidMeasurement("Source archive root contains a symlink")
    relative = Path(str(relative_value or ""))
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        raise InvalidMeasurement(f"Unsafe {label} source path")
    source_root = root.resolve(strict=True)
    candidate = source_root
    for part in relative.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise InvalidMeasurement(f"{label} source path contains a symlink")
    try:
        path = candidate.resolve(strict=True)
    except OSError as exc:
        raise InvalidMeasurement(f"Missing {label} source") from exc
    if not path.is_relative_to(source_root) or not path.is_file():
        raise InvalidMeasurement(f"{label} source escapes archive")
    return path


def _digest_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def _preflight_sources(filing_spec: Mapping[str, Any], source_root: Path) -> dict[str, dict[str, Any]]:
    """Verify every filing packet without importing the invocation worker's helper."""
    root = Path(source_root)
    if not root.is_dir():
        raise InvalidMeasurement(f"Source archive absent: {root}")
    packets = filing_spec.get("source_packets")
    if not isinstance(packets, list) or not packets:
        raise InvalidMeasurement("Filing lacks source packets")
    evidence: dict[str, dict[str, Any]] = {}
    for packet in packets:
        if not isinstance(packet, Mapping):
            raise InvalidMeasurement("Filing source packet is not an object")
        role = packet.get("role")
        if not isinstance(role, str) or not role or role in evidence:
            raise InvalidMeasurement(f"Invalid or duplicate source role: {role!r}")
        path = _safe_source_file(root, packet.get("path"), role)
        size, sha = _digest_file(path)
        if type(packet.get("bytes")) is not int or size != packet["bytes"] or packet.get("sha256") != sha:
            raise InvalidMeasurement(f"Source packet hash/size mismatch: {packet.get('path')}")
        provenance = packet.get("provenance")
        if not isinstance(provenance, Mapping):
            raise InvalidMeasurement(f"Missing source provenance: {packet.get('path')}")
        if provenance.get("representation") != "httpx_decoded_response_text_utf8":
            raise InvalidMeasurement(f"Unknown source representation: {packet.get('path')}")
        if provenance.get("sha256") != sha:
            raise InvalidMeasurement(f"Source provenance hash mismatch: {packet.get('path')}")
        evidence[role] = {
            "path": str(path), "bytes": size, "sha256": sha,
            "requested_url": provenance.get("requested_url"),
            "provenance": dict(provenance),
        }
    primary = evidence.get("primary")
    if primary is None or primary["sha256"] != filing_spec.get("source_sha256"):
        raise InvalidMeasurement("Primary packet does not match manifest source_sha256")
    if primary["requested_url"] != filing_spec.get("document_url"):
        raise InvalidMeasurement("Primary requested URL differs from manifest document URL")
    return evidence


def _span(kind: str, offset: int, content: bytes) -> dict[str, Any]:
    return {"kind": kind, "offset": offset, "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest()}


def audit_attachment_difference(embedded: bytes, packet: bytes, document: str) -> dict[str, Any]:
    """Prove exact body parity after *declared* SEC transport additions, without changing either source.

    Only the one observed SEC /vkpr script, one terminal LF, and (for a 6-K
    document response) its literal SGML DOCUMENT envelope are classified.
    Everything else fails closed. Spans refer to offsets in the original packet.
    """
    body = packet
    body_start = 0
    spans: list[dict[str, Any]] = []
    enveloped = packet.startswith(b"<DOCUMENT>\n")
    if enveloped:
        marker = packet.find(b"<TEXT>")
        close = packet.rfind(b"</TEXT>")
        if marker < 0 or close <= marker:
            raise InvalidMeasurement("SEC document envelope lacks a unique TEXT body")
        prefix = packet[:marker + len(b"<TEXT>")]
        suffix = packet[close:]
        if (prefix.count(b"<TEXT>") != 1 or
                b"\n<FILENAME>" + document.encode("utf-8") + b"\n" not in prefix or
                suffix != b"</TEXT>\n</DOCUMENT>\n"):
            raise InvalidMeasurement("SEC document envelope differs from selected attachment")
        body_start = len(prefix)
        body = packet[body_start:close]
        spans.append(_span("sec_document_prefix", 0, prefix))
        spans.append(_span("sec_document_suffix", close, suffix))
        if not body.startswith(b"\n") or not body.endswith(b"\n"):
            raise InvalidMeasurement("SEC document TEXT delimiters lack exact line breaks")
        spans.append(_span("sec_text_leading_lf", body_start, b"\n"))
        spans.append(_span("sec_text_trailing_lf", close - 1, b"\n"))
        body = body[1:-1]
        body_start += 1

    matches = list(_SEC_SCRIPT_RE.finditer(body))
    if len(matches) > 1:
        raise InvalidMeasurement("Multiple SEC-injected scripts in selected attachment")
    injected = bool(matches)
    if injected:
        match = matches[0]
        script = match.group()
        if (hashlib.sha256(script).hexdigest() != _SEC_SCRIPT_SHA256 or
                re.match(rb"</body>", body[match.end():], flags=re.IGNORECASE) is None):
            raise InvalidMeasurement("SEC-injected script is not the identified body-tail script")
        spans.append(_span("sec_injected_body_tail_script", body_start + match.start(), script))
        body = body[:match.start()] + body[match.end():]

    terminal_lf = False
    if not enveloped and body.endswith(b"\n") and body[:-1] == embedded:
        spans.append(_span("sec_terminal_lf", len(packet) - 1, b"\n"))
        body = body[:-1]
        terminal_lf = True

    if body != embedded:
        first = next((i for i in range(min(len(body), len(embedded))) if body[i] != embedded[i]),
                     min(len(body), len(embedded)))
        raise InvalidMeasurement(f"Unexplained direct-packet/SGML attachment difference at byte {first}")
    if enveloped:
        classification = "sec_document_envelope_and_injected_script" if injected else "sec_document_envelope"
    elif injected and terminal_lf:
        classification = "sec_injected_script_and_terminal_lf"
    elif not injected and not terminal_lf:
        classification = "byte_identical"
    else:
        raise InvalidMeasurement("Unrecognized direct-packet/SGML attachment byte relationship")
    return {"classification": classification, "embedded_sha256": hashlib.sha256(embedded).hexdigest(),
            "packet_sha256": hashlib.sha256(packet).hexdigest(),
            "edits": sorted(spans, key=lambda item: item["offset"])}


def _bound_json(root: Path, record: Mapping[str, Any], label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read an explicit SHA/byte-bound raw SEC JSON source inside the source root."""
    if not isinstance(record, Mapping) or not record.get("path"):
        raise InvalidMeasurement(f"Missing {label} source record")
    path = _safe_source_file(root, record.get("path"), label)
    size, sha = _digest_file(path)
    if (type(record.get("bytes")) is not int or size != record["bytes"] or
            not isinstance(record.get("sha256"), str) or sha != record["sha256"]):
        raise InvalidMeasurement(f"{label} source hash/size mismatch")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise InvalidMeasurement(f"{label} source is not JSON") from exc
    if not isinstance(data, dict):
        raise InvalidMeasurement(f"{label} source is not a JSON object")
    return data, {"path": str(path), "bytes": size, "sha256": sha}


def _embedded_bytes(attachment: Any) -> bytes:
    if getattr(attachment, "sgml_document", None) is None:
        raise InvalidMeasurement("Selected attachment lacks embedded SGML content")
    content = attachment.content
    if isinstance(content, str):
        return content.encode("utf-8")
    if isinstance(content, bytes):
        return content
    raise InvalidMeasurement("Embedded attachment has unsupported content type")


def _assert_attachment_contract(
    attachment: Any, packet: Mapping[str, Any], declared: Mapping[str, Any], label: str,
) -> dict[str, Any]:
    if not isinstance(declared, Mapping):
        raise InvalidMeasurement(f"Missing {label} embedded attachment contract")
    content = _embedded_bytes(attachment)
    embedded_sha = hashlib.sha256(content).hexdigest()
    packet_content = Path(packet["path"]).read_bytes()
    if len(packet_content) != packet["bytes"] or hashlib.sha256(packet_content).hexdigest() != packet["sha256"]:
        raise InvalidMeasurement(f"{label} direct packet changed after preflight")
    audit = audit_attachment_difference(content, packet_content, attachment.document)
    if (declared.get("document") != attachment.document or
            declared.get("embedded_bytes") != len(content) or
            declared.get("embedded_sha256") != embedded_sha or
            declared.get("packet_bytes") != packet["bytes"] or
            declared.get("packet_sha256") != packet["sha256"] or
            declared.get("difference_audit") != audit):
        raise InvalidMeasurement(f"{label} embedded/packet relationship differs from frozen contract")
    relationship = "byte_identical" if embedded_sha == packet["sha256"] and len(content) == packet["bytes"] else "distinct"
    if declared.get("relationship") != relationship:
        raise InvalidMeasurement(f"{label} byte relationship differs from frozen contract")
    return {"document": attachment.document, "embedded_bytes": len(content),
            "embedded_sha256": embedded_sha, "packet_bytes": packet["bytes"],
            "packet_sha256": packet["sha256"], "relationship": relationship,
            "difference_audit": audit}


@dataclass
class FrozenArchiveBinding:
    """One filing's verified sources plus a sticky runtime provenance trace."""

    spec: Mapping[str, Any]
    evidence: dict[str, Any]
    filing: Any
    company: Any
    companyfacts: dict[str, Any]
    trace: list[dict[str, Any]] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    _inside_patch: bool = False
    _grounding_complete: bool = False
    _allowed_text_sha256: set[str] = field(default_factory=set)
    _allowed_sections_sha256: set[str] = field(default_factory=set)

    def _event(self, path: str, outcome: str, **detail: Any) -> None:
        self.trace.append({"path": path, "outcome": outcome, **detail})

    def _violate(self, path: str, detail: str) -> None:
        message = f"{path}: {detail}"
        self.violations.append(message)
        self._event(path, "refused", detail=detail)
        raise InvalidMeasurement(message)

    def _selected(self, path: str, requested_cik: Any, requested_accession: Any) -> None:
        try:
            matches = (int(requested_cik) == int(self.spec["cik"]) and
                       requested_accession == self.spec["accession_number"])
        except (TypeError, ValueError):
            matches = False
        if not matches:
            self._violate(path, "different selected filing")

    def assert_ready_for_provider(self) -> None:
        """Reject sticky violations and source calls still unresolved at provider admission.

        This validates only channels production actually attempted. The pipeline owns
        which channels a form and frozen configuration require.
        """
        if not self._inside_patch:
            raise InvalidMeasurement("Archive source patch is not active")
        if self.violations:
            raise InvalidMeasurement("Archive source violation: " + "; ".join(self.violations))
        terminal = {
            "edgar.resolve_filing_by_accession": {"bound"},
            "edgar.Filing.sgml": {"bound"},
            "sec_edgar_service.get_filing_document": {"bound"},
            "edgar.companyfacts": {"bound"},
            "edgar.get_xbrl_data": {"returned"},
            "edgar.get_filing_sections": {"returned"},
            "edgar.get_sixk_text": {"bound", "returned_empty"},
            "statement_source": {"bound"},
            "filing_excerpt": {"returned"},
            "edgar.attachments.download_file": {"bound", "sgml_embedded_alias"},
            "edgar.FilingHomepage.load": {"bound"},
        }
        for path, outcomes in terminal.items():
            attempted = sum(row["path"] == path and row["outcome"] == "attempted" for row in self.trace)
            completed = sum(row["path"] == path and row["outcome"] in outcomes for row in self.trace)
            if completed < attempted:
                self._violate(path, "source attempt did not complete before provider admission")

    def assert_grounding_complete(self, *, sections_enabled: bool | None = None) -> None:
        """Require the production grounding channels for this form before summarization.

        The per-request provider guard only checks calls which have already started.
        This separate end-to-end assertion prevents a skipped production task from
        looking like a valid absence. It mirrors ``summary_pipeline``: 6-K uses its
        exhibit extractor, while 10-K/10-Q/20-F use XBRL and optionally sections.
        """
        self.assert_ready_for_provider()
        if sections_enabled is None:
            from app.services import summary_pipeline

            sections_enabled = bool(summary_pipeline.settings.USE_EDGARTOOLS_SECTIONS)

        def completed(path: str, outcomes: set[str]) -> bool:
            return any(row["path"] == path and row["outcome"] in outcomes for row in self.trace)

        form = str(self.spec["filing_type"]).upper().split("/")[0]
        required: list[tuple[str, set[str], str]] = [
            ("filing_excerpt", {"returned"}, "filing excerpt was not produced from frozen input"),
        ]
        if form == "6-K":
            required.append(("edgar.get_sixk_text", {"bound", "returned_empty"},
                             "6-K exhibit extraction was not completed"))
            if not (completed("edgar.get_sixk_text", {"bound"}) or
                    completed("sec_edgar_service.get_filing_document", {"bound"})):
                self._violate("archive.grounding", "6-K text was not bound to SGML or archived primary")
        else:
            required.extend([
                ("edgar.get_xbrl_data", {"returned"},
                 "XBRL extraction was not completed from a frozen source"),
                ("sec_edgar_service.get_filing_document", {"bound"},
                 "filing text was not bound to the archived primary"),
            ])
            if sections_enabled:
                required.append(("edgar.get_filing_sections", {"returned"},
                                 "configured section extraction was not completed"))

        text_bound = (completed("sec_edgar_service.get_filing_document", {"bound"}) or
                      completed("edgar.get_sixk_text", {"bound"}))
        if text_bound and self.spec.get("period_of_report"):
            required.append(("statement_source", {"bound"},
                             "statement context was not derived from the frozen filing text"))
        for path, outcomes, detail in required:
            if not completed(path, outcomes):
                self._violate("archive.grounding", detail)
        self._grounding_complete = True
        self._event("archive.grounding", "complete", form=form,
                    sections_enabled=bool(sections_enabled))

    def report(self) -> dict[str, Any]:
        return {"source_evidence": self.evidence, "source_calls": list(self.trace),
                "source_violations": list(self.violations),
                "grounding_complete": self._grounding_complete,
                "source_binding": "frozen_complete_submission_and_raw_sec_json"}

    @contextmanager
    def patch_production(self) -> Iterator["FrozenArchiveBinding"]:
        """Redirect source seams while retaining production parsing and extraction."""
        if self._inside_patch:
            raise InvalidMeasurement("Archive source patch cannot be nested")
        from edgar import Filing as EdgarFiling
        from edgar import _filings as edgar_filings
        from edgar import attachments as edgar_attachments
        from edgar import httprequests as edgar_http
        from edgar.attachments import Attachments, FilingHomepage, parse_homepage_html
        from edgar.entity import entity_facts as edgar_entity_facts
        from edgar.entity import submissions as edgar_submissions
        from edgar.sgml import sgml_common
        from app.services import summary_pipeline
        from app.services.edgar import sixk_extractor, xbrl_service

        accession = str(self.spec["accession_number"])
        original_sgml = EdgarFiling.sgml
        service = summary_pipeline.xbrl_service
        extractor = xbrl_service.edgar_xbrl_service
        original_xbrl = service.get_xbrl_data
        original_sections = service.get_filing_sections
        original_sixk = summary_pipeline.get_sixk_text
        original_statement = summary_pipeline.acquire_statement_context
        original_excerpt = summary_pipeline.get_or_cache_excerpt
        self._allowed_text_sha256 = {self.evidence["primary"]["sha256"]}
        self._allowed_sections_sha256 = set()

        def resolve_frozen(requested_cik: str, requested_accession: str) -> tuple[Any, list[Any]]:
            frame = sys._getframe(1)
            channel = "unknown"
            while frame is not None:
                if frame.f_code.co_name == "_extract_from_filing_instance_sync":
                    channel = "xbrl"
                    break
                if frame.f_code.co_name == "_extract_sections_sync":
                    channel = "sections"
                    break
                if frame.f_code.co_name == "_extract_sixk_text_sync":
                    channel = "sixk"
                    break
                frame = frame.f_back
            self._event("edgar.resolve_filing_by_accession", "attempted",
                        accession=str(requested_accession), cik=str(requested_cik), channel=channel)
            self._selected("edgar.resolve_filing_by_accession", requested_cik, requested_accession)
            self._event("edgar.resolve_filing_by_accession", "bound",
                        complete_submission_sha256=self.evidence["complete_submission"]["sha256"],
                        channel=channel)
            return self.company, [self.filing]

        def frozen_sgml(requested: Any, *args: Any, **kwargs: Any) -> Any:
            self._event("edgar.Filing.sgml", "attempted", accession=str(requested.accession_no))
            if requested is not self.filing:
                self._violate("edgar.Filing.sgml", "different filing object")
            result = original_sgml(requested, *args, **kwargs)
            self._event("edgar.Filing.sgml", "bound",
                        complete_submission_sha256=self.evidence["complete_submission"]["sha256"])
            return result

        async def frozen_primary(url: str, *_args: Any, **_kwargs: Any) -> str:
            self._event("sec_edgar_service.get_filing_document", "attempted", url=url)
            if url != self.spec["document_url"]:
                self._violate("sec_edgar_service.get_filing_document", "different selected URL")
            packet = self.evidence["primary"]
            content = Path(packet["path"]).read_bytes()
            if len(content) != packet["bytes"] or hashlib.sha256(content).hexdigest() != packet["sha256"]:
                self._violate("sec_edgar_service.get_filing_document", "source changed after preflight")
            try:
                decoded = content.decode("utf-8")
            except UnicodeError:
                self._violate("sec_edgar_service.get_filing_document", "invalid UTF-8 packet")
            self._event("sec_edgar_service.get_filing_document", "bound", sha256=packet["sha256"])
            return decoded

        async def frozen_primary_with_source(url: str, *args: Any, **kwargs: Any) -> tuple[str, dict[str, Any]]:
            content = await frozen_primary(url, *args, **kwargs)
            return content, dict(self.evidence["primary"]["provenance"])

        async def frozen_companyfacts(requested_cik: str, requested_accession: str) -> Any:
            self._event("edgar.companyfacts", "attempted", cik=str(requested_cik),
                        accession=str(requested_accession))
            self._selected("edgar.companyfacts", requested_cik, requested_accession)
            try:
                parsed = extractor._parse_company_facts(self.companyfacts, accession)
            except Exception as exc:
                self._violate("edgar.companyfacts", f"production parser failed: {type(exc).__name__}")
            self._event("edgar.companyfacts", "bound",
                        sha256=self.evidence["companyfacts"]["sha256"],
                        populated=any(bool(value) for value in parsed.values()))
            return parsed

        async def measured_xbrl(requested_accession: str, requested_cik: str) -> Any:
            self._event("edgar.get_xbrl_data", "attempted", accession=str(requested_accession),
                        cik=str(requested_cik))
            self._selected("edgar.get_xbrl_data", requested_cik, requested_accession)
            prior = len(self.trace)
            result = await original_xbrl(requested_accession, requested_cik)
            bound_source = any(
                row["outcome"] == "bound" and (
                    row["path"] == "edgar.companyfacts" or
                    (row["path"] == "edgar.resolve_filing_by_accession" and row.get("channel") == "xbrl")
                ) for row in self.trace[prior:]
            )
            if not bound_source:
                self._violate("edgar.get_xbrl_data", "returned without frozen filing or companyfacts source")
            populated = isinstance(result, dict) and any(bool(value) for value in result.values())
            self._event("edgar.get_xbrl_data", "returned", populated=populated,
                        genuine_source_absence=not populated)
            return result

        async def measured_sections(requested_accession: str, requested_cik: str, form: str) -> Any:
            self._event("edgar.get_filing_sections", "attempted", accession=str(requested_accession),
                        cik=str(requested_cik), form=str(form))
            self._selected("edgar.get_filing_sections", requested_cik, requested_accession)
            prior = len(self.trace)
            result = await original_sections(requested_accession, requested_cik, form)
            if result and not any(
                row["path"] == "edgar.resolve_filing_by_accession" and row["outcome"] == "bound"
                and row.get("channel") == "sections" for row in self.trace[prior:]
            ):
                self._violate("edgar.get_filing_sections", "nonempty sections without frozen filing resolution")
            if isinstance(result, dict):
                self._allowed_sections_sha256.add(hashlib.sha256(
                    json.dumps(result, sort_keys=True, ensure_ascii=False).encode("utf-8")
                ).hexdigest())
            self._event("edgar.get_filing_sections", "returned",
                        sections=sorted(result) if isinstance(result, dict) else [])
            return result

        async def measured_sixk(requested_accession: str, requested_cik: str, **kwargs: Any) -> Any:
            self._event("edgar.get_sixk_text", "attempted", accession=str(requested_accession),
                        cik=str(requested_cik))
            self._selected("edgar.get_sixk_text", requested_cik, requested_accession)
            prior = len(self.trace)
            result = await original_sixk(requested_accession, requested_cik, **kwargs)
            if result:
                if not isinstance(result, str) or not any(
                    row["path"] == "edgar.resolve_filing_by_accession" and row["outcome"] == "bound"
                    and row.get("channel") == "sixk"
                    for row in self.trace[prior:]
                ):
                    self._violate("edgar.get_sixk_text", "nonempty text without frozen SGML resolution")
                sha = hashlib.sha256(result.encode("utf-8")).hexdigest()
                self._allowed_text_sha256.add(sha)
                self._event("edgar.get_sixk_text", "bound", sha256=sha,
                            complete_submission_sha256=self.evidence["complete_submission"]["sha256"])
            else:
                self._event("edgar.get_sixk_text", "returned_empty")
            return result

        def measured_statement(source_html: str, *, accession: str, document_url: str,
                               form: str, report_period: str | None = None) -> Any:
            self._event("statement_source", "attempted", accession=accession, url=document_url)
            if accession != self.spec["accession_number"] or document_url != self.spec["document_url"] or form != self.spec["filing_type"]:
                self._violate("statement_source", "different selected filing")
            sha = hashlib.sha256(source_html.encode("utf-8")).hexdigest()
            if sha not in self._allowed_text_sha256:
                self._violate("statement_source", "input was not archived primary or frozen 6-K text")
            result = original_statement(source_html, accession=accession, document_url=document_url,
                                        form=form, report_period=report_period)
            self._event("statement_source", "bound", source_sha256=sha, populated=result is not None)
            return result

        def measured_excerpt(db: Any, filing: Any, filing_text: str | None,
                             sections: Any = None) -> Any:
            self._event("filing_excerpt", "attempted", accession=getattr(filing, "accession_number", None))
            if getattr(filing, "accession_number", None) != accession:
                self._violate("filing_excerpt", "different selected filing")
            if filing_text:
                sha = hashlib.sha256(filing_text.encode("utf-8")).hexdigest()
                if sha not in self._allowed_text_sha256:
                    self._violate("filing_excerpt", "input was not archived primary or frozen 6-K text")
            else:
                sha = None
            if sections:
                section_sha = hashlib.sha256(
                    json.dumps(sections, sort_keys=True, ensure_ascii=False).encode("utf-8")
                ).hexdigest()
                if section_sha not in self._allowed_sections_sha256:
                    self._violate("filing_excerpt", "sections were not returned by frozen Edgar parser")
            result = original_excerpt(db, filing, filing_text, sections=sections)
            self._event("filing_excerpt", "returned", input_sha256=sha,
                        populated=bool(result), section_keys=sorted(sections) if isinstance(sections, dict) else [])
            return result

        def frozen_download(url: str, as_text: bool | None = None, path: Any = None) -> Any:
            self._event("edgar.attachments.download_file", "attempted", url=url)
            if path is not None:
                self._violate("edgar.attachments.download_file", "SDK requested a file-writing download")
            for role in ("primary", "earnings_exhibit"):
                packet = self.evidence.get(role)
                if packet is not None and url == packet.get("requested_url"):
                    content = Path(packet["path"]).read_bytes()
                    if len(content) != packet["bytes"] or hashlib.sha256(content).hexdigest() != packet["sha256"]:
                        self._violate("edgar.attachments.download_file", "archived attachment changed")
                    self._event("edgar.attachments.download_file", "bound", role=role,
                                sha256=packet["sha256"])
                    # Edgar's download_file returns response.text for .htm/.html/.txt,
                    # including when as_text=False (its extension fallback).
                    return content.decode("utf-8")
            alias = self.evidence.get("homepage_primary_alias")
            if alias is not None and url == alias["requested_url"]:
                matched = [a for a in self.filing.sgml().attachments if a.document == alias["document"]]
                if len(matched) != 1:
                    self._violate("edgar.attachments.download_file", "SDK alias attachment is not unique in SGML")
                content = _embedded_bytes(matched[0])
                if hashlib.sha256(content).hexdigest() != alias["embedded_sha256"]:
                    self._violate("edgar.attachments.download_file", "SDK alias SGML bytes changed")
                self._event("edgar.attachments.download_file", "sgml_embedded_alias",
                            url=url, index_sha256=alias["index_sha256"],
                            embedded_sha256=alias["embedded_sha256"],
                            alias_http_byte_parity="unverified")
                return content.decode("utf-8")
            self._violate("edgar.attachments.download_file", "SDK requested unarchived attachment")

        def frozen_homepage(url: str) -> Any:
            self._event("edgar.FilingHomepage.load", "attempted", url=url)
            if url != self.filing.homepage_url:
                self._violate("edgar.FilingHomepage.load", "SDK requested another filing index")
            packet = self.evidence.get("index")
            if packet is None or packet.get("requested_url") != self.spec["index_url"]:
                self._violate("edgar.FilingHomepage.load", "selected filing index is not archived")
            content = Path(packet["path"]).read_bytes()
            if len(content) != packet["bytes"] or hashlib.sha256(content).hexdigest() != packet["sha256"]:
                self._violate("edgar.FilingHomepage.load", "archived filing index changed")
            try:
                root = parse_homepage_html(content)
                attachments = Attachments.load(root)
                homepage = FilingHomepage(self.spec["index_url"], root, attachments)
            except Exception as exc:
                self._violate("edgar.FilingHomepage.load", f"SDK index parser failed: {type(exc).__name__}")
            self._event("edgar.FilingHomepage.load", "bound", requested_url=url,
                        archived_url=self.spec["index_url"], sha256=packet["sha256"])
            return homepage

        def refuse_submissions(*_args: Any, **_kwargs: Any) -> Any:
            self._violate("edgar.entity.get_entity_submissions", "SDK requested live company metadata")

        def refuse_sdk_transport(*args: Any, **kwargs: Any) -> Any:
            requested = args[0] if args else kwargs.get("url", kwargs.get("data_url"))
            self._violate("edgar.httprequests", f"SDK requested live SEC transport: {requested!s}")

        async def no_redis(_self: Any, key: str) -> None:
            self._event("edgar.redis_xbrl", "bypassed", key=key)
            return None

        async def no_redis_write(_self: Any, key: str, _data: Any) -> bool:
            self._event("edgar.redis_xbrl_write", "bypassed", key=key)
            return False

        def no_persisted(_accession: str, _cik: str) -> None:
            self._event("edgar.persisted_xbrl", "bypassed")
            return None

        with ExitStack() as stack:
            stack.enter_context(patch.object(xbrl_service, "resolve_filing_by_accession", resolve_frozen))
            stack.enter_context(patch.object(sixk_extractor, "resolve_filing_by_accession", resolve_frozen))
            stack.enter_context(patch.object(EdgarFiling, "sgml", frozen_sgml))
            stack.enter_context(patch.object(edgar_attachments, "download_file", frozen_download))
            stack.enter_context(patch.object(edgar_attachments, "download_file_async", refuse_sdk_transport))
            stack.enter_context(patch.object(edgar_attachments, "get_with_retry", refuse_sdk_transport))
            stack.enter_context(patch.object(FilingHomepage, "load", frozen_homepage))
            stack.enter_context(patch.object(edgar_submissions, "get_entity_submissions", refuse_submissions))
            stack.enter_context(patch.object(edgar_submissions, "download_json", refuse_sdk_transport))
            stack.enter_context(patch.object(edgar_entity_facts, "download_json", refuse_sdk_transport))
            stack.enter_context(patch.object(edgar_filings, "download_file", refuse_sdk_transport))
            stack.enter_context(patch.object(edgar_filings, "download_text", refuse_sdk_transport))
            stack.enter_context(patch.object(edgar_filings, "download_text_between_tags", refuse_sdk_transport))
            stack.enter_context(patch.object(sgml_common, "stream_with_retry", refuse_sdk_transport))
            for name in (
                "get_with_retry", "get_with_retry_async", "stream_with_retry",
                "post_with_retry", "post_with_retry_async", "download_file",
                "download_file_async", "download_json", "download_json_async",
                "stream_file", "download_text", "download_text_between_tags",
                "download_bulk_data", "download_datafile",
            ):
                if hasattr(edgar_http, name):
                    stack.enter_context(patch.object(edgar_http, name, refuse_sdk_transport))
            stack.enter_context(patch.object(summary_pipeline.sec_edgar_service, "get_filing_document", frozen_primary))
            stack.enter_context(patch.object(summary_pipeline.sec_edgar_service, "get_filing_document_with_source",
                                             frozen_primary_with_source))
            stack.enter_context(patch.object(extractor, "_fallback_to_company_facts", frozen_companyfacts))
            stack.enter_context(patch.object(service, "get_xbrl_data", measured_xbrl))
            stack.enter_context(patch.object(service, "get_filing_sections", measured_sections))
            stack.enter_context(patch.object(summary_pipeline, "get_sixk_text", measured_sixk))
            stack.enter_context(patch.object(summary_pipeline, "acquire_statement_context", measured_statement))
            stack.enter_context(patch.object(summary_pipeline, "get_or_cache_excerpt", measured_excerpt))
            stack.enter_context(patch.object(xbrl_service.EdgarXBRLService, "_persisted_xbrl",
                                             staticmethod(no_persisted)))
            stack.enter_context(patch.object(xbrl_service.EdgarXBRLService, "_get_from_redis", no_redis))
            stack.enter_context(patch.object(xbrl_service.EdgarXBRLService, "_set_to_redis", no_redis_write))
            # One child owns this cache. Empty it before entry so no previous filing result can win.
            xbrl_service.clear_xbrl_cache()
            self._inside_patch = True
            try:
                yield self
                self.assert_ready_for_provider()
            finally:
                self._inside_patch = False


def prepare_archive_binding(
    filing_spec: Mapping[str, Any], source_root: Path,
    submissions_record: Mapping[str, Any], companyfacts_record: Mapping[str, Any],
    embedding_record: Mapping[str, Any],
) -> FrozenArchiveBinding:
    """Fail closed before provider admission unless all four source classes are bound.

    The two SEC API records point to raw JSON; ``embedding_record`` points to a
    separately frozen declaration of each packet/SGML attachment byte relationship.
    It may declare ``distinct`` direct-HTTP and embedded-SGML representations; neither
    byte stream is modified or silently treated as equal.
    """
    from edgar import Company, Filing
    from edgar import attachments as edgar_attachments
    from edgar.attachments import Attachments, FilingHomepage, parse_homepage_html
    from edgar.entity.data import parse_entity_submissions
    from edgar.entity import submissions as edgar_submissions

    root = Path(source_root)
    evidence = _preflight_sources(filing_spec, root)
    for packet in filing_spec["source_packets"]:
        if packet["role"] == "primary":
            evidence["primary"]["provenance"] = dict(packet["provenance"])
            break
    complete = evidence.get("complete_submission")
    if complete is None:
        raise InvalidMeasurement("Complete SGML submission packet is required")
    index = evidence.get("index")
    if index is None or index.get("requested_url") != filing_spec.get("index_url"):
        raise InvalidMeasurement("Selected filing index packet is required")
    submissions, submissions_source = _bound_json(root, submissions_record, "company submissions")
    companyfacts, companyfacts_source = _bound_json(root, companyfacts_record, "companyfacts")
    embedding, embedding_source = _bound_json(root, embedding_record, "embedding contract")
    if (embedding.get("schema_version") != 1 or
            embedding.get("holdout_id") != filing_spec["holdout_id"] or
            embedding.get("accession_number") != filing_spec["accession_number"] or
            str(embedding.get("cik")) != str(filing_spec["cik"]) or
            embedding.get("filing_type") != filing_spec["filing_type"] or
            embedding.get("selected_period_of_report") != filing_spec["period_of_report"] or
            embedding.get("complete_submission_sha256") != complete["sha256"] or
            not isinstance(embedding.get("attachments"), dict)):
        raise InvalidMeasurement("Embedding contract identity differs from selected filing")
    try:
        submissions_cik_matches = int(submissions.get("cik", -1)) == int(filing_spec["cik"])
        companyfacts_cik_matches = int(companyfacts.get("cik", -1)) == int(filing_spec["cik"])
    except (TypeError, ValueError):
        submissions_cik_matches = companyfacts_cik_matches = False
    if not submissions_cik_matches:
        raise InvalidMeasurement("Company submissions CIK differs from selected filing")
    if not companyfacts_cik_matches or not isinstance(companyfacts.get("facts"), dict):
        raise InvalidMeasurement("Companyfacts CIK or facts structure differs from selected filing")

    def refuse_preflight(*_args: Any, **_kwargs: Any) -> Any:
        raise InvalidMeasurement("SDK attempted a remote source during archive preparation")

    try:
        with patch.object(edgar_attachments, "download_file", refuse_preflight), \
                patch.object(FilingHomepage, "load", refuse_preflight), \
                patch.object(edgar_submissions, "get_entity_submissions", refuse_preflight):
            sgml_bytes = Path(complete["path"]).read_bytes()
            if len(sgml_bytes) != complete["bytes"] or hashlib.sha256(sgml_bytes).hexdigest() != complete["sha256"]:
                raise InvalidMeasurement("Complete submission changed after preflight")
            filing = Filing.from_sgml_text(sgml_bytes.decode("utf-8"))
            sgml_period = str(filing.period_of_report or "")
            if (filing.accession_no != filing_spec["accession_number"] or
                    int(filing.cik) != int(filing_spec["cik"]) or
                    filing.form != filing_spec["filing_type"] or
                    str(filing.filing_date) != str(filing_spec["filing_date"]) or
                    (filing.form != "6-K" and sgml_period != str(filing_spec["period_of_report"])) or
                    embedding.get("sgml_period_of_report") != sgml_period):
                raise InvalidMeasurement("Complete SGML identity differs from selected filing")

            primary_name = Path(urlparse(filing_spec["document_url"]).path).name
            primary = [a for a in filing.sgml().attachments if a.document == primary_name]
            if len(primary) != 1:
                raise InvalidMeasurement("Primary document is not uniquely embedded in SGML")
            evidence["embedded_primary"] = _assert_attachment_contract(
                primary[0], evidence["primary"], embedding["attachments"].get("primary"), "Primary"
            )
            index_bytes = Path(index["path"]).read_bytes()
            if len(index_bytes) != index["bytes"] or hashlib.sha256(index_bytes).hexdigest() != index["sha256"]:
                raise InvalidMeasurement("Selected index changed after preflight")
            parsed_index = parse_homepage_html(index_bytes)
            homepage = FilingHomepage(filing_spec["index_url"], parsed_index, Attachments.load(parsed_index))
            indexed_primary = homepage.primary_html_document
            if indexed_primary is not None and indexed_primary.url != filing_spec["document_url"]:
                declared_alias = embedding.get("homepage_primary_alias")
                alias_url = urlparse(indexed_primary.url)
                accession_path = filing_spec["accession_number"].replace("-", "")
                if (alias_url.scheme != "https" or alias_url.netloc != "www.sec.gov" or
                        not re.fullmatch(r"/Archives/edgar/data/\d+/" + re.escape(accession_path) +
                                         r"/" + re.escape(primary_name), alias_url.path)):
                    raise InvalidMeasurement("SDK homepage alias is outside selected SEC accession")
                expected_alias = {"requested_url": indexed_primary.url,
                                  "document": indexed_primary.document,
                                  "index_sha256": index["sha256"],
                                  "embedded_sha256": evidence["embedded_primary"]["embedded_sha256"],
                                  "alias_http_byte_parity": "unverified"}
                if declared_alias != expected_alias or indexed_primary.document != primary_name:
                    raise InvalidMeasurement("SDK homepage primary alias lacks frozen SGML identity declaration")
                evidence["homepage_primary_alias"] = expected_alias
            elif embedding.get("homepage_primary_alias") is not None:
                raise InvalidMeasurement("Unexpected SDK homepage alias declaration")

            if "earnings_exhibit" in evidence:
                selected_name = Path(evidence["earnings_exhibit"]["path"]).name
                if filing.form == "6-K":
                    sixk = filing.obj()
                    releases = sixk.press_releases
                    selected = list(releases.attachments) if releases is not None else [
                        a for a in sixk.exhibits if not a.is_binary()
                    ]
                    if any(a.sgml_document is None for a in selected):
                        raise InvalidMeasurement("6-K production-selected exhibit is not embedded in SGML")
                else:
                    selected = list(filing.sgml().attachments)
                matched = [a for a in selected if a.document == selected_name]
                if len(matched) != 1:
                    raise InvalidMeasurement("Retained earnings exhibit is not selected from SGML")
                evidence["embedded_earnings_exhibit"] = _assert_attachment_contract(
                    matched[0], evidence["earnings_exhibit"],
                    embedding["attachments"].get("earnings_exhibit"), "Earnings exhibit"
                )

            company = Company(int(filing_spec["cik"]))
            company._data = parse_entity_submissions(submissions)
            if int(company.cik) != int(company.data.cik):
                raise InvalidMeasurement("Parsed company metadata CIK differs from selected filing")
            # The SDK's own classification uses SIC, recent forms and entity type.
            # Force it now while only frozen submissions are available.
            _ = company.business_category
            _ = company.is_financial_institution()
    except InvalidMeasurement:
        raise
    except (OSError, UnicodeError, ValueError, TypeError, AttributeError, KeyError) as exc:
        raise InvalidMeasurement(f"Frozen SGML/metadata parse failed: {type(exc).__name__}") from exc

    evidence["company_submissions"] = submissions_source
    evidence["companyfacts"] = companyfacts_source
    evidence["embedding_contract"] = embedding_source
    evidence["sgml_period_of_report"] = sgml_period
    return FrozenArchiveBinding(filing_spec, evidence, filing, company, companyfacts)
