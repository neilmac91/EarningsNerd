"""The waitlist referral link lands where a referral is counted (audit pub/F02, EM-05).

``build_referral_link`` once returned ``FRONTEND_URL?ref=CODE``: the homepage, where nothing reads
``ref``, so a shared link credited nobody while the success card and the welcome mail promised a
jump of REFERRAL_BONUS spots per referral. The link now names ``/waitlist``, the page whose form
submits ``ref`` as the referral code. These tests hold the link and its reader together: the path and
query key the backend writes are the ones the frontend reads, and the frontend's edge guard lets the
page through while WAITLIST_MODE is on (with it off, every path passes). The position arithmetic the
referral sentence quotes is pinned here too; ``test_waitlist_join_route.py`` pins the referrer's bump.
"""
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from app.services import waitlist_service
from app.services.waitlist_service import REFERRAL_BONUS, build_referral_link, calculate_waitlist_position

FRONTEND = Path(__file__).resolve().parents[3] / "frontend"


@pytest.mark.parametrize("frontend_url", ["https://earningsnerd.test", "https://earningsnerd.test/"])
def test_referral_link_lands_on_the_waitlist_page(monkeypatch, frontend_url):
    monkeypatch.setattr(waitlist_service.settings, "FRONTEND_URL", frontend_url)
    link = build_referral_link("abc12345")
    assert link == "https://earningsnerd.test/waitlist?ref=abc12345", f"{link} must land on /waitlist?ref=, where the form reads it"


def test_the_waitlist_page_reads_the_link_the_backend_writes(monkeypatch):
    monkeypatch.setattr(waitlist_service.settings, "FRONTEND_URL", "https://earningsnerd.test")
    link = urlsplit(build_referral_link("abc12345"))
    path = link.path or "/"
    (query_key,) = parse_qs(link.query)

    page = (FRONTEND / "app" / path.strip("/") / "page.tsx").read_text(encoding="utf8")
    assert re.search(r"<WaitlistForm\b", page), f"the referral link lands on {path}, which renders no WaitlistForm to read ?{query_key}="

    form = (FRONTEND / "features" / "waitlist" / "components" / "WaitlistForm.tsx").read_text(encoding="utf8")
    readers = re.findall(r"searchParams\.get\(\s*['\"]([^'\"]+)['\"]\s*\)", form)
    assert readers == [query_key], f"WaitlistForm reads {readers}, the link carries ?{query_key}="

    middleware = (FRONTEND / "middleware.ts").read_text(encoding="utf8")
    allowed = re.search(r"ALLOWED_PATHS = new Set\(\[(.*?)\]\)", middleware, re.S)
    assert allowed, "middleware.ts: ALLOWED_PATHS is unreadable"
    assert f"'{path}'" in allowed.group(1), f"{path} must stay reachable while WAITLIST_MODE is on"


def test_each_referral_moves_the_referrer_up_referral_bonus_spots():
    assert calculate_waitlist_position(40, 0) == 40
    assert calculate_waitlist_position(40, 1) == 40 - REFERRAL_BONUS
    assert calculate_waitlist_position(40, 3) == 40 - 3 * REFERRAL_BONUS
    assert calculate_waitlist_position(3, 2) == 1  # never above the front of the list
