"""Exercise the installed dependency seam, including its reachable raw SGML fallback."""
import ast
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpxthrottlecache import HttpxThrottleCache
from httpxthrottlecache._compat import httpx

from app.services import sec_request_gate as gate
from app.services.edgar import sec_admission as integration


class LocalLimiter:
    def __init__(self, allowed=True):
        self.calls = 0
        self.allowed = allowed

    def try_acquire(self, name, timeout):
        self.calls += 1
        assert timeout > 0
        return self.allowed

    async def try_acquire_async(self, name, timeout):
        return self.try_acquire(name, timeout)


@pytest.fixture
def admissions(monkeypatch):
    calls = []
    monkeypatch.setattr(gate.settings, "SEC_DISTRIBUTED_LIMIT_ENABLED", True)
    monkeypatch.setattr(gate, "acquire_sync", lambda **kwargs: calls.append("sync"))

    async def acquire(**kwargs):
        calls.append("async")

    monkeypatch.setattr(gate, "acquire_async", acquire)
    return calls


@pytest.mark.parametrize("revalidate", [False, True])
def test_installed_sync_cache_hit_spends_no_permit_and_redirects_each_spend(admissions, monkeypatch, tmp_path, revalidate):
    sends = []

    def send(self, request):
        sends.append(request.url.path)
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"location": "/document"}, request=request)
        if "if-modified-since" in request.headers:
            return httpx.Response(304, request=request)
        return httpx.Response(200, stream=httpx.ByteStream(b"filing"), request=request, headers={
            "date": "Sat, 01 Jan 2000 00:00:00 GMT", "last-modified": "Fri, 31 Dec 1999 00:00:00 GMT",
        })

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", send)
    local = LocalLimiter()
    with HttpxThrottleCache(
        cache_mode="FileCache", cache_dir=tmp_path,
        cache_rules={r"^fixture\.invalid$": {"/document": 1 if revalidate else True}},
        rate_limiter=integration.FleetAdmissionLimiter(local),
    ) as manager:
        with manager.http_client() as client:
            assert client.get("https://fixture.invalid/redirect", follow_redirects=True).text == "filing"
            assert client.get("https://fixture.invalid/document").text == "filing"
    assert sends == ["/redirect", "/document"] + (["/document"] if revalidate else [])
    assert admissions == ["sync"] * len(sends)
    assert local.calls == len(sends)


@pytest.mark.asyncio
async def test_installed_async_redirect_retry_each_spend(admissions, monkeypatch):
    sends = []

    async def send(self, request):
        sends.append(request.url.path)
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"location": "/document"}, request=request)
        return httpx.Response(200, stream=httpx.ByteStream(b"filing"), request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", send)
    manager = HttpxThrottleCache(cache_mode="Disabled", rate_limiter=integration.FleetAdmissionLimiter(LocalLimiter()))
    async with manager.async_http_client() as client:
        await client.get("https://fixture.invalid/redirect", follow_redirects=True)
        await client.get("https://fixture.invalid/document")
    assert sends == ["/redirect", "/document", "/document"]
    assert admissions == ["async", "async", "async"]


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.asyncio
async def test_local_false_must_raise_because_transport_ignores_result(admissions, monkeypatch, asynchronous):
    def forbidden(*args, **kwargs):
        pytest.fail("denied permit reached network transport")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
    manager = HttpxThrottleCache(cache_mode="Disabled", rate_limiter=integration.FleetAdmissionLimiter(LocalLimiter(False)))
    with pytest.raises(gate.SECAdmissionUnavailable):
        if asynchronous:
            async with manager.async_http_client() as client:
                await client.get("https://fixture.invalid/document")
        else:
            with manager:
                with manager.http_client() as client:
                    client.get("https://fixture.invalid/document")
    assert admissions == []


def test_installed_short_sgml_fallback_uses_existing_limiter_and_identity(admissions, monkeypatch):
    from edgar import httpclient
    from edgar.sgml import sgml_common
    from edgar.sgml.sgml_header import FilingHeader

    local = LocalLimiter()
    manager = HttpxThrottleCache(cache_mode="Disabled", rate_limiter=local,
                                user_agent_factory=lambda: "Synthetic contact@example.invalid")
    monkeypatch.setattr(httpclient, "HTTP_MGR", manager)
    monkeypatch.setattr(sgml_common, "_fetch_url_directly", sgml_common._fetch_url_directly)
    integration.install_edgar_admission()
    integration.install_edgar_admission()  # No nested limiter or second permit.
    monkeypatch.setattr(sgml_common, "read_content_as_string", lambda source: "")
    bodies = []

    def parse(body):
        bodies.append(body)
        return FilingHeader(text="", filing_metadata={}), defaultdict(list)

    def send(self, request):
        assert request.headers["user-agent"] == "Synthetic contact@example.invalid"
        return httpx.Response(200, text="uncached SGML document", request=request)

    monkeypatch.setattr(sgml_common, "parse_submission_text", parse)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", send)
    sgml_common.FilingSGML.from_source("https://fixture.invalid/filing.txt")
    assert bodies == ["uncached SGML document"]
    assert admissions == ["sync"]
    assert local.calls == 1
    assert manager._client is None  # Fresh uncached client did not replace shared cache.


@pytest.mark.parametrize("problem", ["version", "signature", "opened", "disabled", "proxy", "mounts"])
def test_unsupported_setup_fails_closed(admissions, monkeypatch, problem):
    from edgar import httpclient
    from edgar.sgml import sgml_common

    manager = HttpxThrottleCache(cache_mode="Disabled", rate_limiter=LocalLimiter())
    monkeypatch.setattr(httpclient, "HTTP_MGR", manager)
    original = sgml_common._fetch_url_directly
    if problem == "version":
        monkeypatch.setattr(integration, "version", lambda package: "unsupported")
    if problem == "signature":
        monkeypatch.setattr(sgml_common, "_fetch_url_directly", lambda url, new_option: "")
    if problem == "opened":
        manager._client = SimpleNamespace()
    if problem == "disabled":
        manager.rate_limiter_enabled = False
    if problem in {"proxy", "mounts"}:
        manager.httpx_params[problem] = "unexpected"
    with pytest.raises(gate.SECAdmissionUnavailable, match="unsupported"):
        integration.install_edgar_admission()
    assert isinstance(manager.rate_limiter, LocalLimiter)
    if problem != "signature":
        assert sgml_common._fetch_url_directly is original


def test_existing_app_sec_client_sites_all_have_per_send_hook():
    app = Path(__file__).parents[2] / "app"
    expected = {
        "services/edgar/compat.py": 3,
        "services/edgar/xbrl_companyfacts.py": 1,
        "services/facts/transport.py": 1,
        "integrations/sec_api.py": 1,
    }
    # Read every EDGAR/facts source, not only a list that would miss a new raw
    # client home. Other integrations (Stripe/model/email) have their own owners.
    paths = {*app.joinpath("services/edgar").rglob("*.py"),
             *app.joinpath("services/facts").rglob("*.py"), app / "integrations/sec_api.py"}
    observed = {}
    for path in paths:
        owner = path.relative_to(app).as_posix()
        tree = ast.parse(path.read_text())
        raw_clients = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                       and node.func.value.id in {"httpx", "httpx2", "requests"}
                       and node.func.attr in {"Client", "AsyncClient", "get", "post", "request", "stream"}]
        if raw_clients:
            observed[owner] = len(raw_clients)
    assert observed == expected
    for owner, count in expected.items():
        tree = ast.parse((app / owner).read_text())
        clients = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Attribute) and node.func.attr == "AsyncClient"]
        assert len(clients) == count, owner
        configured_names = {node.targets[0].id for node in ast.walk(tree)
                            if isinstance(node, ast.Assign) and len(node.targets) == 1
                            and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Call)
                            and isinstance(node.value.func, ast.Name) and node.value.func.id == "sec_request_options"}
        assert all(any(keyword.arg is None and (
                       isinstance(keyword.value, ast.Call) and isinstance(keyword.value.func, ast.Name)
                       and keyword.value.func.id == "sec_request_options"
                       or isinstance(keyword.value, ast.Name) and keyword.value.id in configured_names)
                       for keyword in client.keywords)
                   for client in clients), owner


def test_other_dependency_raw_fetch_apis_are_not_supported_app_paths():
    from edgar.xmlfiling import XML_FILING_FORMS
    from app.services.edgar.config import FilingType

    assert not set(XML_FILING_FORMS).intersection(form.value for form in FilingType)
    app = Path(__file__).parents[2] / "app"
    for path in app.rglob("*.py"):
        if path.name == "sec_admission.py":
            continue
        tree = ast.parse(path.read_text())
        forbidden = [node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
                     and node.attr in {"parse_url", "update_rate_limiter", "_fetch_url_directly"}]
        assert not forbidden, (path, forbidden)


def test_edgar_feedback_is_below_cache_and_refusal_is_never_cached(admissions, monkeypatch, tmp_path):
    sends, feedback = [], []

    def send(self, request):
        sends.append(request.url.path)
        status = 429 if len(sends) == 1 else 200
        return httpx.Response(status, stream=httpx.ByteStream(b"body"), request=request, headers={
            "date": "Sat, 01 Jan 2000 00:00:00 GMT", **({"Retry-After": "60"} if status == 429 else {}),
        })

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", send)
    monkeypatch.setattr(gate, "record_response_sync", lambda status, hint: feedback.append((status, hint)))
    with integration.FeedbackManager(
        cache_mode="FileCache", cache_dir=tmp_path,
        cache_rules={r"^fixture\.invalid$": {"/document": True}},
        rate_limiter=integration.FleetAdmissionLimiter(LocalLimiter()),
    ) as manager:
        with manager.http_client() as client:
            assert client.get("https://fixture.invalid/document").status_code == 429
            assert client.get("https://fixture.invalid/document").status_code == 200
            assert client.get("https://fixture.invalid/document").status_code == 200
    assert sends == ["/document", "/document"]
    assert feedback == [(429, "60"), (200, None)]
    assert admissions == ["sync", "sync"]


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.asyncio
async def test_edgar_feedback_failure_closes_unowned_response(admissions, monkeypatch, asynchronous):
    class SyncBody(httpx.SyncByteStream):
        closed = False

        def __iter__(self):
            yield b"refused"

        def close(self):
            self.closed = True

    class AsyncBody(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            yield b"refused"

        async def aclose(self):
            self.closed = True

    body = AsyncBody() if asynchronous else SyncBody()

    def send(self, request):
        return httpx.Response(429, stream=body, request=request, headers={"Retry-After": "60"})

    async def async_send(self, request):
        return send(self, request)

    def fail(*args):
        raise gate.SECAdmissionUnavailable("SEC cooldown coordinator is unavailable")

    async def async_fail(*args):
        fail(*args)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", send)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", async_send)
    monkeypatch.setattr(gate, "record_response_sync", fail)
    monkeypatch.setattr(gate, "record_response_async", async_fail)
    manager = integration.FeedbackManager(cache_mode="Disabled", rate_limiter=integration.FleetAdmissionLimiter(LocalLimiter()))
    with pytest.raises(gate.SECAdmissionUnavailable):
        if asynchronous:
            async with manager.async_http_client() as client:
                await client.get("https://fixture.invalid/document")
        else:
            with manager:
                with manager.http_client() as client:
                    client.get("https://fixture.invalid/document")
    assert body.closed
