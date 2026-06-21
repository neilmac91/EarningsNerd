"""Data model for the "Ask this Filing" Copilot eval set (P8).

The summary harness scores one structured summary per filing. The Copilot is a per-question grounded
Q&A loop, so it needs its own golden shape: a list of question cases per filing, each marked
answerable or not (for refusal calibration) and optionally carrying the financial facts the answer
must contain. Scoring lives in ``copilot_scorers.py``; running the live model in ``copilot_runner.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from evals.schema import GroundTruthFact


@dataclass
class CopilotQACase:
    """One graded question about a filing."""

    question: str
    # True  → the filing discloses this; the Copilot must answer (and not refuse).
    # False → not disclosed; the Copilot must honestly refuse ("not disclosed"), proving refusal
    #         calibration rather than fabricating an answer.
    disclosed: bool = True
    # Financial facts the answer must contain (for targeted numeric questions on disclosed cases).
    expected_facts: List[GroundTruthFact] = field(default_factory=list)
    # Optional human hint for where the answer should come from (not hard-scored).
    expected_section: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CopilotQACase":
        return cls(
            question=d["question"],
            disclosed=bool(d.get("disclosed", True)),
            expected_facts=[GroundTruthFact(**f) for f in d.get("expected_facts", [])],
            expected_section=d.get("expected_section", ""),
            notes=d.get("notes", ""),
        )


@dataclass
class CopilotGoldenCase:
    """A filing plus the question cases graded against it."""

    ticker: str
    cik: str
    accession_number: str
    filing_type: str
    document_url: str
    company_name: str
    qa: List[CopilotQACase] = field(default_factory=list)
    # Operator must confirm the filing + each case's answerability against EDGAR before trusting scores.
    verified: bool = False
    notes: str = ""

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CopilotGoldenCase":
        return cls(
            ticker=d["ticker"],
            cik=str(d["cik"]),
            accession_number=d["accession_number"],
            filing_type=d["filing_type"],
            document_url=d["document_url"],
            company_name=d.get("company_name", d["ticker"]),
            qa=[CopilotQACase.from_dict(q) for q in d.get("qa", [])],
            verified=bool(d.get("verified", False)),
            notes=d.get("notes", ""),
        )


@dataclass
class CopilotAnswerScore:
    """Deterministic score for a single answered question."""

    question: str
    kind: str  # "answer" | "not_disclosed"
    refusal_correct: bool
    citation_faithfulness: float  # fraction of text citations that verify verbatim in the filing
    unverified_excerpts: List[str]
    numeric_recall: float  # fraction of expected_facts present in the answer (1.0 when none expected)
    missing_metrics: List[str]
    grounded: int
    gate_failures: List[str]  # hard vetoes: REFUSAL / CITATION / NUMERIC

    @property
    def passed(self) -> bool:
        return not self.gate_failures

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "kind": self.kind,
            "refusal_correct": self.refusal_correct,
            "citation_faithfulness": self.citation_faithfulness,
            "unverified_excerpts": self.unverified_excerpts,
            "numeric_recall": self.numeric_recall,
            "missing_metrics": self.missing_metrics,
            "grounded": self.grounded,
            "gate_failures": self.gate_failures,
            "passed": self.passed,
        }
