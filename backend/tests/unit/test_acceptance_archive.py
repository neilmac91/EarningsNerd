"""Synthetic offline tests for E7's proposed archive source adapter."""

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from evals.acceptance_archive import audit_attachment_difference, prepare_archive_binding
from evals.acceptance_worker import InvalidMeasurement


def _record(root: Path, name: str, value: dict) -> dict:
    content = json.dumps(value, separators=(",", ":")).encode("utf-8")
    (root / name).write_bytes(content)
    return {"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}


def _fixture(
    tmp_path: Path, *, distinct_primary: bool = False,
    form: str = "10-K", with_release: bool = False,
):
    if form not in {"10-K", "10-Q", "20-F", "6-K"}:
        raise ValueError(f"Unsupported synthetic form: {form}")
    if with_release and form != "6-K":
        raise ValueError("Synthetic earnings release is only valid for 6-K")
    root = tmp_path / "sources"
    root.mkdir()
    primary = "<html><body>" + ("Archived filing text and financial context. " * 8) + "</body></html>"
    release = "<html><body>" + ("Archived earnings release facts and management context. " * 8) + "</body></html>"
    primary_url = "https://www.sec.gov/Archives/edgar/data/1/000000000100000001/filing.htm"
    index_url = primary_url.replace("filing.htm", "0000000001-00-000001-index.htm")
    sgml_period = "20260115" if form == "6-K" else "20251231"
    documents = [
        f"<DOCUMENT>\n<TYPE>{form}\n<SEQUENCE>1\n<FILENAME>filing.htm\n"
        f"<TEXT>{primary}</TEXT>\n</DOCUMENT>"
    ]
    if with_release:
        documents.append(
            "<DOCUMENT>\n<TYPE>EX-99.1\n<SEQUENCE>2\n<FILENAME>release.htm\n"
            f"<TEXT>{release}</TEXT>\n</DOCUMENT>"
        )
    sgml = ("<SUBMISSION>\n<ACCESSION-NUMBER>0000000001-00-000001\n"
            f"<TYPE>{form}\n<PUBLIC-DOCUMENT-COUNT>{len(documents)}\n"
            f"<PERIOD>{sgml_period}\n<FILING-DATE>20260115\n"
            "<FILER>\n<COMPANY-DATA>\n<CONFORMED-NAME>Test Company\n<CIK>0000000001\n"
            "</COMPANY-DATA>\n</FILER>\n" + "\n".join(documents) + "\n</SUBMISSION>")

    def packet(role: str, filename: str, content: str, url: str) -> dict:
        encoded = content.encode("utf-8")
        (root / filename).write_bytes(encoded)
        sha = hashlib.sha256(encoded).hexdigest()
        return {"role": role, "path": filename, "bytes": len(encoded), "sha256": sha,
                "provenance": {"representation": "httpx_decoded_response_text_utf8",
                               "sha256": sha, "requested_url": url}}

    sec_script = ('<script type="text/javascript"  '
                  'src="/vkpr/O2cG/-/aPR/OBK8BA/3puXNJkpchwLGDuzaY/JgJmeg/GF/ICYEkkESU"></script>')
    direct_primary = (primary.replace("</body>", sec_script + "</body>") + "\n"
                      if distinct_primary else primary)
    primary_packet = packet("primary", "filing.htm", direct_primary, primary_url)
    index_packet = packet("index", "index.htm", "<html><body>Filing index</body></html>", index_url)
    complete_packet = packet("complete_submission", "complete.txt", sgml,
                             "https://www.sec.gov/Archives/edgar/data/1/000000000100000001/complete.txt")
    spec = {"holdout_id": "synthetic", "ticker": "TEST", "company_name": "Test Company",
            "cik": "1", "filing_type": form, "accession_number": "0000000001-00-000001",
            "filing_date": "2026-01-15", "period_of_report": "2025-12-31",
            "document_url": primary_url, "index_url": index_url,
            "source_sha256": primary_packet["sha256"],
            "source_packets": [primary_packet, index_packet, complete_packet]}
    release_packet = None
    if with_release:
        release_packet = packet(
            "earnings_exhibit", "release.htm", release,
            "https://www.sec.gov/Archives/edgar/data/1/000000000100000001/release.htm",
        )
        spec["source_packets"].append(release_packet)
    address = {"street1": "1 Main St", "street2": None, "city": "Testville",
               "stateOrCountryDescription": "New York", "stateOrCountry": "NY", "zipCode": "10001"}
    submissions = {"cik": 1, "name": "Test Company", "tickers": ["TEST"], "exchanges": ["NYSE"],
                   "sic": "3571", "sicDescription": "Computer Hardware", "category": "",
                   "fiscalYearEnd": "1231", "entityType": "operating", "phone": "", "flags": "",
                   "addresses": {"mailing": address, "business": address},
                   "filings": {"recent": {"accessionNumber": []}, "files": []},
                   "insiderTransactionForOwnerExists": False,
                   "insiderTransactionForIssuerExists": False,
                   "ein": "000000001", "description": "", "website": "", "investorWebsite": "",
                   "stateOfIncorporation": "NY", "stateOfIncorporationDescription": "New York",
                   "formerNames": []}
    facts = {"cik": 1, "entityName": "Test Company", "facts": {"us-gaap": {}}}
    embedded = primary.encode("utf-8")
    embedding = {"schema_version": 1, "holdout_id": spec["holdout_id"],
                 "accession_number": spec["accession_number"], "cik": spec["cik"],
                 "filing_type": spec["filing_type"],
                 "selected_period_of_report": spec["period_of_report"],
                 "complete_submission_sha256": complete_packet["sha256"],
                 "sgml_period_of_report": "2026-01-15" if form == "6-K" else spec["period_of_report"],
                 "attachments": {"primary": {"document": "filing.htm", "embedded_bytes": len(embedded),
                                              "embedded_sha256": hashlib.sha256(embedded).hexdigest(),
                                              "packet_bytes": primary_packet["bytes"],
                                              "packet_sha256": primary_packet["sha256"],
                                              "relationship": "distinct" if distinct_primary else "byte_identical",
                                              "difference_audit": audit_attachment_difference(
                                                  embedded, direct_primary.encode("utf-8"), "filing.htm"
                                              )}}}
    if release_packet is not None:
        release_bytes = release.encode("utf-8")
        embedding["attachments"]["earnings_exhibit"] = {
            "document": "release.htm", "embedded_bytes": len(release_bytes),
            "embedded_sha256": hashlib.sha256(release_bytes).hexdigest(),
            "packet_bytes": release_packet["bytes"], "packet_sha256": release_packet["sha256"],
            "relationship": "byte_identical",
            "difference_audit": audit_attachment_difference(release_bytes, release_bytes, "release.htm"),
        }
    return (root, spec, direct_primary, _record(root, "submissions.json", submissions),
            _record(root, "facts.json", facts), _record(root, "embedding.json", embedding))


def test_frozen_sources_bind_sdk_company_and_primary(tmp_path):
    from app.services import summary_pipeline
    from app.services.edgar import sixk_extractor, xbrl_service

    root, spec, primary, submissions, facts, embedding = _fixture(tmp_path)
    binding = prepare_archive_binding(spec, root, submissions, facts, embedding)
    assert binding.company.__class__.__name__ == "Company"
    assert binding.company.sic == "3571"
    with binding.patch_production():
        content = asyncio.run(summary_pipeline.sec_edgar_service.get_filing_document(spec["document_url"]))
        company, filings = xbrl_service.resolve_filing_by_accession("0000000001", spec["accession_number"])
        assert content == primary
        assert company is binding.company and filings == [binding.filing]
        assert sixk_extractor.resolve_filing_by_accession("1", spec["accession_number"])[1] == [binding.filing]
        binding.assert_ready_for_provider()
    assert any(row["path"] == "edgar.resolve_filing_by_accession" and row["outcome"] == "bound"
               for row in binding.report()["source_calls"])


def test_wrong_identity_is_sticky_even_when_production_catches_exception(tmp_path):
    from app.services.edgar import xbrl_service

    root, spec, _, submissions, facts, embedding = _fixture(tmp_path)
    binding = prepare_archive_binding(spec, root, submissions, facts, embedding)
    with pytest.raises(InvalidMeasurement, match="Archive source violation"):
        with binding.patch_production():
            with pytest.raises(InvalidMeasurement, match="different selected filing"):
                xbrl_service.resolve_filing_by_accession("2", spec["accession_number"])
    assert any("different selected filing" in reason for reason in binding.violations)


def test_remote_sdk_attempt_is_sticky_after_caught_exception(tmp_path):
    from edgar import httprequests

    root, spec, _, submissions, facts, embedding = _fixture(tmp_path)
    binding = prepare_archive_binding(spec, root, submissions, facts, embedding)
    with pytest.raises(InvalidMeasurement, match="Archive source violation"):
        with binding.patch_production():
            with pytest.raises(InvalidMeasurement, match="live SEC transport"):
                httprequests.download_json("https://data.sec.gov/unbound.json")
    assert binding.report()["source_violations"]


def test_missing_or_changed_companyfacts_fails_before_patch(tmp_path):
    root, spec, _, submissions, facts, embedding = _fixture(tmp_path)
    with pytest.raises(InvalidMeasurement, match="Missing companyfacts source record"):
        prepare_archive_binding(spec, root, submissions, {}, embedding)
    (root / facts["path"]).write_text("{}", encoding="utf-8")
    with pytest.raises(InvalidMeasurement, match="companyfacts source hash/size mismatch"):
        prepare_archive_binding(spec, root, submissions, facts, embedding)


def test_genuine_empty_xbrl_is_traced_without_invented_facts(tmp_path, monkeypatch):
    from app.services import summary_pipeline
    from app.services.edgar.xbrl_service import edgar_xbrl_service

    root, spec, _, submissions, facts, embedding = _fixture(tmp_path)
    binding = prepare_archive_binding(spec, root, submissions, facts, embedding)
    service = summary_pipeline.xbrl_service

    async def no_instance(*_args):
        return None

    monkeypatch.setattr(edgar_xbrl_service, "_fetch_from_filing_instance", no_instance)
    with binding.patch_production():
        # A real frozen source may have no facts for this accession. Production
        # parser semantics must stand, while the attempted fallback is explicit.
        result = asyncio.run(service.get_xbrl_data(spec["accession_number"], spec["cik"]))
        assert result is None
        binding.assert_ready_for_provider()
    assert any(row["path"] == "edgar.companyfacts" and row["outcome"] == "bound"
               for row in binding.trace)
    assert any(row["path"] == "edgar.get_xbrl_data" and row.get("genuine_source_absence")
               for row in binding.trace)


def test_distinct_direct_http_and_embedded_sgml_are_explicitly_bound(tmp_path):
    root, spec, _, submissions, facts, embedding = _fixture(tmp_path, distinct_primary=True)
    binding = prepare_archive_binding(spec, root, submissions, facts, embedding)
    assert binding.evidence["embedded_primary"]["relationship"] == "distinct"
    assert binding.evidence["embedded_primary"]["embedded_sha256"] != spec["source_sha256"]
    assert binding.evidence["embedded_primary"]["difference_audit"]["classification"] == "sec_injected_script_and_terminal_lf"


def test_unbound_populated_sections_cannot_enter_provider(tmp_path, monkeypatch):
    from app.services import summary_pipeline

    root, spec, _, submissions, facts, embedding = _fixture(tmp_path)
    binding = prepare_archive_binding(spec, root, submissions, facts, embedding)

    async def unbound_sections(*_args):
        return {"mda": "Unbound text"}

    monkeypatch.setattr(summary_pipeline.xbrl_service, "get_filing_sections", unbound_sections)
    with pytest.raises(InvalidMeasurement, match="Archive source violation"):
        with binding.patch_production():
            with pytest.raises(InvalidMeasurement, match="nonempty sections without frozen"):
                asyncio.run(summary_pipeline.xbrl_service.get_filing_sections(
                    spec["accession_number"], spec["cik"], spec["filing_type"]
                ))


def test_grounding_complete_rejects_skipped_required_channel(tmp_path):
    root, spec, _, submissions, facts, embedding = _fixture(tmp_path)
    binding = prepare_archive_binding(spec, root, submissions, facts, embedding)
    with pytest.raises(InvalidMeasurement, match="XBRL extraction was not completed"):
        with binding.patch_production():
            binding.trace.extend([
                {"path": "sec_edgar_service.get_filing_document", "outcome": "bound"},
                {"path": "filing_excerpt", "outcome": "returned"},
                {"path": "statement_source", "outcome": "bound"},
            ])
            binding.assert_grounding_complete(sections_enabled=False)
