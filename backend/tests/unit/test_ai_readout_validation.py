"""External weekly handoff rejects malformed counts, identity, links and oversized content."""

import base64
import json

import pytest

from app.services.ai_readout import DIMENSIONS, decode_readout, unavailable_readout


@pytest.mark.parametrize(
    "defect",
    [
        "schema",
        "version",
        "boolean-count",
        "denominator",
        "completion",
        "weak-judge",
        "source",
        "link",
        "model",
        "dimension",
        "empty-dimension",
        "oversize",
        "base64",
    ],
)
def test_external_readout_rejects_invalid_measurement(defect):
    value = unavailable_readout()
    value.update(
        status="complete",
        source_sha="a" * 40,
        cohort_sha256="b" * 64,
        golden_set_sha256="c" * 64,
        generator_model="deepseek-v4-pro",
        completed=24,
        scored=24,
        missing=0,
        dimensions=dict.fromkeys(DIMENSIONS, 4),
    )
    if defect == "schema":
        value["unknown"] = "not allowed"
    elif defect == "version":
        value["version"] = True
    elif defect == "boolean-count":
        value["errors"] = False
    elif defect == "denominator":
        value["errors"] = 1
    elif defect == "completion":
        value.update(scored=23, errors=1)
    elif defect == "weak-judge":
        value["judge_model"] = "cheap-judge"
    elif defect == "source":
        value["source_sha"] = "unknown"
    elif defect == "link":
        value["run_url"] = "https://github.com.evil.example/claim"
    elif defect == "model":
        value["generator_model"] = "<script>"
    elif defect == "dimension":
        value["dimensions"]["faithfulness"] = float("nan")
    elif defect == "empty-dimension":
        value["dimensions"]["clarity"] = None
    encoded = base64.b64encode(json.dumps(value).encode()).decode()
    if defect == "oversize":
        encoded = "a" * 8193
    elif defect == "base64":
        encoded = "!not base64"
    result = decode_readout(encoded)
    assert result["status"] == "unavailable" and result["scored"] == 0
    assert result["reason"] == "Weekly judged readout handoff invalid"
