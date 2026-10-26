"""Every request timeout main.py sets ends before Cloud Run ends the request (E213).

``request_timeout_middleware`` answers a request that outlives its path's timeout with a 504 carrying the CORS
and security headers (``_error_response_cors_headers``, ``_security_headers``), so a page on the site's origin
can read it. Cloud Run ends a request that outlives the API service's own request timeout (the deploy's
``--timeout``) with a response of its own, which carries neither. A timeout entry at or past the service's is
one the middleware never reaches, and one just short of it can lose the race to it, so each entry ends at least
``HEADROOM_SECONDS`` before. The stale-summary refresh holds its request through its batch's generations, so its
path keeps an entry of its own, inside the service's.
"""
import re
from pathlib import Path

import yaml

import main
from app.routers import admin
from app.services.summary_pipeline import PIPELINE_TIMEOUT_SECONDS

ROOT = Path(__file__).resolve().parents[3]
# Each timeout ends at least this long before the service's: the middleware's 504 has to go out before Cloud Run's
# deadline, on an event loop that can run its timer late.
HEADROOM_SECONDS = 30.0


def _service_deploy() -> str:
    """The API service's ``gcloud run deploy`` command, read from the deploy step's executable lines."""
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    [step] = [step for step in workflow["jobs"]["deploy-backend"]["steps"]
              if step.get("name") == "Deploy Cloud Run service"]
    executable = "\n".join(line for line in step["run"].splitlines() if not line.lstrip().startswith("#"))
    [deploy] = re.findall(r"gcloud run deploy earningsnerd-backend\b.*?--quiet", executable, re.S)
    return deploy


def _service_request_timeout() -> int:
    """The ``--timeout`` the deploy gives the API service."""
    [seconds] = re.findall(r"--timeout=(\d+)\b", _service_deploy())
    return int(seconds)


def _service_pool_timeout() -> float:
    """The pool timeout the API service is deployed with, in the order the service resolves it: the deploy's
    ``DB_POOL_TIMEOUT`` (``--update-env-vars``), else the image's (an ``ENV`` line in ``backend/Dockerfile``, which
    already sets four of its siblings), else ``database.py``'s default as written there, not as this process's
    environment (which ``load_dotenv`` may fill) sets it. A value set on the service by hand outlives
    ``--update-env-vars`` and is out of this reading's reach."""
    [env] = re.findall(r"--update-env-vars=(\S+)", _service_deploy())
    pairs = dict(item.split("=", 1) for item in env.split(","))
    if "DB_POOL_TIMEOUT" in pairs:
        return float(pairs["DB_POOL_TIMEOUT"])
    image = [line for line in (ROOT / "backend/Dockerfile").read_text().splitlines()
             if line.lstrip().upper().startswith("ENV") and "DB_POOL_TIMEOUT" in line]
    if image:
        values = [re.search(r"\bDB_POOL_TIMEOUT[= ]+(\d+)\b", line) for line in image]
        assert all(values), f"backend/Dockerfile sets DB_POOL_TIMEOUT in a form this reading does not know: {image}"
        return float(values[-1].group(1))
    defaults = re.findall(r'^DB_POOL_TIMEOUT = int\(os\.getenv\("DB_POOL_TIMEOUT", "(\d+)"\)\)$',
                          (ROOT / "backend/app/database.py").read_text(), re.M)
    assert len(defaults) == 1, "database.py's DB_POOL_TIMEOUT assignment changed shape; teach this reading its form"
    return float(defaults[0])


def test_every_request_timeout_ends_before_the_services():
    service = _service_request_timeout()
    timeouts = {**main.REQUEST_TIMEOUT_SECONDS, **main.REQUEST_TIMEOUT_SUFFIXES}
    assert {path: seconds for path, seconds in timeouts.items() if seconds > service - HEADROOM_SECONDS} == {}


def test_the_stale_refresh_takes_its_own_timeout_with_room_for_its_last_generation():
    # The middleware takes the first prefix that matches, so a broader entry above this one would shadow it.
    assert main.get_timeout_for_path("/api/admin/summaries/refresh-stale") == admin.REFRESH_STALE_TIMEOUT_SECONDS
    # A generation started at the start-by bound still has its whole allowance, which holds the pipeline's backstop
    # (the minute beyond it is an estimate, review-checked). What the timeout leaves after it holds more than the three
    # pool waits outside it at the deployed pool timeout: the auth lookup before the route, and the last stamp re-read
    # and the audit row after the batch. The rest of that margin, for their queries and any reconnect, is an estimate,
    # review-checked too.
    assert admin._REFRESH_STALE_GENERATION_ALLOWANCE_SECONDS > PIPELINE_TIMEOUT_SECONDS
    left = (admin.REFRESH_STALE_TIMEOUT_SECONDS - admin._REFRESH_STALE_START_BY_SECONDS
            - admin._REFRESH_STALE_GENERATION_ALLOWANCE_SECONDS)
    assert left > 3 * _service_pool_timeout()
