"""The require_pro / require_entitlement FastAPI dependencies: 403 for free, pass-through for pro.

Called directly (bypassing Depends) with a stand-in user, so no auth/DB plumbing is needed.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.dependencies import require_entitlement, require_pro


def _user(is_pro=False, subscription=None):
    return SimpleNamespace(is_pro=is_pro, subscription=subscription)


def test_require_pro_blocks_free_user():
    with pytest.raises(HTTPException) as exc:
        require_pro(current_user=_user(is_pro=False))
    assert exc.value.status_code == 403


def test_require_pro_allows_pro_user():
    pro = _user(is_pro=True)
    assert require_pro(current_user=pro) is pro


def test_require_entitlement_blocks_free_user_for_export():
    dep = require_entitlement("can_export", "PDF export")
    with pytest.raises(HTTPException) as exc:
        dep(current_user=_user(is_pro=False))
    assert exc.value.status_code == 403
    assert "PDF export" in exc.value.detail


def test_require_entitlement_allows_pro_user_for_export():
    dep = require_entitlement("can_export", "PDF export")
    pro = _user(is_pro=True)
    assert dep(current_user=pro) is pro


def test_require_entitlement_allows_free_user_for_shared_capability():
    # can_compare_filings is True on both tiers — the gate must let a free user through.
    dep = require_entitlement("can_compare_filings", "Comparison")
    free = _user(is_pro=False)
    assert dep(current_user=free) is free
