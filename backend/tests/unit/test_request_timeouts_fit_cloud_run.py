"""Every request timeout main.py sets ends before Cloud Run ends the request (E213).

``request_timeout_middleware`` answers a request that outlives its path's timeout with a 504 carrying the CORS
and security headers (``_error_response_cors_headers``, ``_security_headers``), so a page on the site's origin
can read it. Cloud Run ends a request that outlives the API service's own request timeout (the deploy's
``--timeout``) with a response of its own, which carries neither. A timeout entry at or past the service's is
one the middleware never reaches. The stale-summary refresh holds its request through its batch's generations,
so its path keeps an entry of its own, inside the service's.
"""
import re
from pathlib import Path

import yaml

import main
from app.routers import admin
from app.services.summary_pipeline import PIPELINE_TIMEOUT_SECONDS

ROOT = Path(__file__).resolve().parents[3]


def _service_request_timeout() -> int:
    """The ``--timeout`` the deploy gives the API service, read from its executable lines."""
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    [step] = [step for step in workflow["jobs"]["deploy-backend"]["steps"]
              if step.get("name") == "Deploy Cloud Run service"]
    executable = "\n".join(line for line in step["run"].splitlines() if not line.lstrip().startswith("#"))
    [deploy] = re.findall(r"gcloud run deploy earningsnerd-backend\b.*?--quiet", executable, re.S)
    [seconds] = re.findall(r"--timeout=(\d+)\b", deploy)
    return int(seconds)


def test_every_request_timeout_ends_before_the_services():
    service = _service_request_timeout()
    timeouts = {**main.REQUEST_TIMEOUT_SECONDS, **main.REQUEST_TIMEOUT_SUFFIXES}
    assert {path: seconds for path, seconds in timeouts.items() if seconds >= service} == {}


def test_the_stale_refresh_takes_its_own_timeout_with_room_for_its_last_generation():
    # The middleware takes the first prefix that matches, so a broader entry above this one would shadow it.
    assert main.get_timeout_for_path("/api/admin/summaries/refresh-stale") == admin.REFRESH_STALE_TIMEOUT_SECONDS
    # A generation started at the start-by bound still has its whole allowance before the timeout, and the allowance
    # holds the pipeline's backstop.
    assert (admin._REFRESH_STALE_START_BY_SECONDS + admin._REFRESH_STALE_GENERATION_ALLOWANCE_SECONDS
            < admin.REFRESH_STALE_TIMEOUT_SECONDS)
    assert admin._REFRESH_STALE_GENERATION_ALLOWANCE_SECONDS > PIPELINE_TIMEOUT_SECONDS
