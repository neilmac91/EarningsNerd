"""Pins the app-loop registration in ``main.py``'s lifespan.

``facts_service._fetch_companyfacts_sync`` (the backfill cross-check, run in FastAPI's threadpool
from ``/internal/jobs/backfill-facts``) hands its coroutine to the loop registered by
``set_app_loop`` so the SEC limiter's ``asyncio.Lock`` is only ever awaited on the API's main loop
(see ``app/services/event_loop.py``). If the lifespan ever stops registering the loop, the bridge
would silently fall back to a private ``asyncio.run`` inside the API process — the exact cross-loop
hazard the registry exists to prevent — so this test drives the real lifespan and asserts the loop
is visible inside it and cleared after shutdown.
"""
import asyncio

from app.services.event_loop import get_app_loop


async def _drive_lifespan() -> tuple[bool, object]:
    from main import app, lifespan

    async with lifespan(app):
        registered_is_running_loop = get_app_loop() is asyncio.get_running_loop()
    return registered_is_running_loop, get_app_loop()


def test_lifespan_registers_the_running_loop_and_clears_it_on_shutdown():
    assert get_app_loop() is None  # nothing registered before startup
    inside, after = asyncio.run(_drive_lifespan())
    assert inside, "lifespan must register the running loop via set_app_loop()"
    assert after is None, "lifespan must clear the registered loop on shutdown"
