"""Every request timeout main.py sets ends before Cloud Run ends the request (E213).

``request_timeout_middleware`` answers a request that outlives its path's timeout with a 504 carrying the CORS
and security headers (``_error_response_cors_headers``, ``_security_headers``), so a page on the site's origin
can read it. Cloud Run ends a request that outlives the API service's own request timeout (the deploy's
``--timeout``) with a response of its own, which carries neither. A timeout entry at or past the service's is
one the middleware never reaches, and one just short of it can lose the race to it, so each entry ends at least
``HEADROOM_SECONDS`` before. The stale-summary refresh holds its request through its batch's generations, so its
path keeps an entry of its own, inside the service's.
"""
import ast
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
    ``DB_POOL_TIMEOUT`` (``--update-env-vars``), else the image's (an ``ENV`` instruction in ``backend/Dockerfile``,
    which already sets four of its siblings), else ``database.py``'s default as written there, not as this process's
    environment (which ``load_dotenv`` may fill) sets it. Both files' shapes are checked whichever layer wins, and
    fail with a message: a Dockerfile instruction naming the value other than as an ``ENV`` this reads, a
    ``database.py`` that binds the name anywhere but its one default line (``_bindings`` names every kind of binding
    it finds), or a ``pool_timeout`` keyword other than the bare name. Code that
    sets the pool's timeout another way (keyword arguments spread from a mapping, a change at run time), and a value
    set on the service by hand (which outlives ``--update-env-vars``), are out of this reading's reach."""
    # The Dockerfile's instructions as Docker reads them: comment lines dropped (Docker never continues one), then
    # each line ending in a backslash, trailing spaces or tabs allowed, joined to the next.
    lines = [line for line in (ROOT / "backend/Dockerfile").read_text().splitlines() if not line.lstrip().startswith("#")]
    joined = re.sub(r"\\[ \t]*\n", " ", "\n".join(lines))
    named = [line.strip() for line in joined.splitlines() if "DB_POOL_TIMEOUT" in line]
    images = [re.fullmatch(r"(?i:ENV)\s+(?:\S+=\S+\s+)*DB_POOL_TIMEOUT[= ](\d+)(?:\s+\S+=\S+)*", line) for line in named]
    assert all(images), f"backend/Dockerfile names DB_POOL_TIMEOUT in a form this reading does not know: {named}"
    source = (ROOT / "backend/app/database.py").read_text()
    defaults = list(re.finditer(r'^DB_POOL_TIMEOUT = int\(os\.getenv\("DB_POOL_TIMEOUT", "(\d+)"\)\)$', source, re.M))
    module = ast.parse(source)
    bindings = _bindings(module, "DB_POOL_TIMEOUT")
    engine_arguments = [keyword.value for keyword in ast.walk(module)
                        if isinstance(keyword, ast.keyword) and keyword.arg == "pool_timeout"]
    assert len(defaults) == 1 and len(bindings) == 1 and engine_arguments and all(
        isinstance(value, ast.Name) and value.id == "DB_POOL_TIMEOUT" for value in engine_arguments), (
        "database.py sets its pool timeout in a form this reading does not know; teach it the new form")
    # The one binding is the default line itself, not a copy of it quoted in a string.
    assert bindings[0].lineno == source.count("\n", 0, defaults[0].start()) + 1, (
        "database.py binds DB_POOL_TIMEOUT on another line than its default; teach this reading the new form")
    [env] = re.findall(r"--update-env-vars=(\S+)", _service_deploy())
    pairs = dict(item.split("=", 1) for item in env.split(","))
    if "DB_POOL_TIMEOUT" in pairs:
        return float(pairs["DB_POOL_TIMEOUT"])
    if images:
        return float(images[-1].group(1))
    return float(defaults[0].group(1))


def _bindings(module: ast.Module, name: str) -> list[ast.AST]:
    """Every node of a parsed module that binds ``name``: an assignment target of any kind (plain, augmented,
    annotated, unpacked, chained, a ``for`` or ``with`` target, a walrus), an import, an ``except`` clause, a match
    capture, a ``def`` or a ``class``."""
    found: list[ast.AST] = []
    for node in ast.walk(module):
        if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Store):
            found.append(node)
        elif isinstance(node, ast.alias) and (node.asname or node.name.split(".")[0]) == name:
            found.append(node)
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name == name:
            found.append(node)
        elif isinstance(node, ast.MatchMapping) and node.rest == name:
            found.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            found.append(node)
    return found


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
