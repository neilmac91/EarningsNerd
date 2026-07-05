"""Reusable FastAPI dependencies for entitlement gating.

Centralises paid-feature gating so routers stop hand-rolling ``if not current_user.is_pro``.
``require_pro`` guards a whole-plan check; ``require_entitlement("flag")`` guards a single
capability flag from :class:`~app.services.entitlements.Entitlements` — making per-feature gates
auditable and tier-ready.

These build on the (required-auth) ``get_current_user`` dependency. To avoid an import cycle
(``app.routers`` package init imports the routers, some of which import *this* module), the auth
dependency is resolved **lazily at request time** via ``_resolve_current_user`` rather than imported
at module load. So importing ``app.dependencies`` touches only services/models, never routers.
"""
from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.entitlements import can_use_copilot, get_entitlements, is_pro_user

_UPGRADE_HINT = "Upgrade to Pro to access this feature."
# Mirrors the bearer scheme in app.routers.auth (auto_error=False → get_current_user decides 401).
_security = HTTPBearer(auto_error=False)


async def _resolve_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
    db: Session = Depends(get_db),
) -> User:
    """Delegate to the canonical ``get_current_user`` (imported lazily to dodge the import cycle)."""
    from app.routers.auth import get_current_user

    return await get_current_user(request, credentials, db)


def require_pro(current_user: User = Depends(_resolve_current_user)) -> User:
    """Allow only Pro (or trialing) users through; 403 otherwise."""
    if not is_pro_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This is a Pro feature. {_UPGRADE_HINT}",
        )
    return current_user


def require_copilot_or_taste(current_user: User = Depends(_resolve_current_user)) -> User:
    """Allow the Copilot Q&A endpoint for Pro users (full entitlement) OR a Free user who still has
    lifetime free-taste questions left (roadmap 2.2); 403 → upsell once the taste is spent.

    Unlike ``require_entitlement("copilot")`` (a hard Pro gate), this lets Free users sample the
    feature a few times. The lifetime counter is metered on the endpoint after a successful answer.
    """
    if can_use_copilot(current_user):
        return current_user
    allowance = get_entitlements(current_user).copilot_free_taste
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"You've used your {allowance} free Copilot questions. {_UPGRADE_HINT}"
            if allowance
            else f"Ask this Filing is a Pro feature. {_UPGRADE_HINT}"
        ),
    )


def require_entitlement(flag: str, feature_label: str | None = None) -> Callable[..., User]:
    """Build a dependency that requires a specific boolean entitlement flag.

    Example::

        @router.post("/", dependencies=[Depends(require_entitlement("can_analyze_trends"))])

    or capture the user::

        user: User = Depends(require_entitlement("can_export", "PDF export"))
    """

    def _dependency(current_user: User = Depends(_resolve_current_user)) -> User:
        allowed = bool(getattr(get_entitlements(current_user), flag, False))
        if not allowed:
            label = feature_label or "This feature"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{label} is a Pro feature. {_UPGRADE_HINT}",
            )
        return current_user

    return _dependency
