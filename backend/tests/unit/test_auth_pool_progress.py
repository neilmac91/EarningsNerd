"""A waiting auth lookup must let another request release its database slot."""

import asyncio
from itertools import count

import httpx
import pytest
from fastapi import Depends, FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app import database
from app.models import User
from app.routers import auth


@pytest.mark.asyncio
@pytest.mark.parametrize("dependency", [auth.get_current_user, auth.get_current_user_optional])
async def test_waiting_auth_lookup_allows_request_cleanup(monkeypatch, tmp_path, dependency):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'auth-pool.db'}",
        connect_args={"check_same_thread": False},
        poolclass=QueuePool,
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.25,
    )
    User.__table__.create(engine)
    with sessionmaker(bind=engine)() as db:
        db.add(User(email="auth-pool@example.test", is_active=True))
        db.commit()

    loop = asyncio.get_running_loop()
    holder_entered = asyncio.Event()
    release_holder = asyncio.Event()
    lookups = count()

    class ObservedSession(Session):
        def query(self, *args, **kwargs):
            if next(lookups) == 1:
                # The second lookup is about to wait on the only connection. Its first
                # owner can finish as soon as the event loop is free to run this callback.
                loop.call_soon_threadsafe(release_holder.set)
            return super().query(*args, **kwargs)

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, class_=ObservedSession))
    monkeypatch.setattr(auth, "sentry_sdk", None)
    app = FastAPI()
    requests_entered = count()

    @app.get("/protected")
    async def protected(user=Depends(dependency)):
        if next(requests_entered) == 0:
            holder_entered.set()
            await asyncio.wait_for(release_holder.wait(), timeout=2)
        return {"authenticated": user is not None}

    token = auth.create_access_token({"sub": "auth-pool@example.test"})
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            first = asyncio.create_task(client.get("/protected"))
            await asyncio.wait_for(holder_entered.wait(), timeout=2)
            second = asyncio.create_task(client.get("/protected"))
            responses = await asyncio.wait_for(asyncio.gather(first, second), timeout=3)
        assert [r.status_code for r in responses] == [200, 200]
        assert [r.json() for r in responses] == [{"authenticated": True}] * 2
        assert engine.pool.checkedout() == 0
    finally:
        release_holder.set()
        engine.dispose()
