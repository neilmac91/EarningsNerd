"""An OAuth sign-in's session handoff as the tests drive it (E29 (5)).

A start that asks for the handoff (``HANDOFF_QUERY`` on a GET start, ``HANDOFF_BODY`` in a POST start's JSON, as a
frontend with the landing page sends them) leads to a callback that does not set the session cookies on its redirect,
a navigation no Web Lock can hold: it redirects to the frontend's landing page with a one-time code in the URL fragment
and sets the cookie that binds that code to the browser it answers. The landing page posts the code to
``/api/auth/oauth/complete``, and that answer sets the session cookies. A start without the ask takes main's path: the
callback sets the session cookies on its redirect home. ``handoff_code`` reads the code off a callback's answer,
holding the redirect to that shape (the landing page, the code in the fragment alone, nothing in the query);
``complete_sign_in`` makes the landing page's post from the same client, whose cookie jar carries the binding cookie
the callback set.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from app.config import settings

LANDING = "/auth/complete"
HANDOFF_COOKIE = "en_oauth_handoff"
COMPLETE_PATH = "/api/auth/oauth/complete"
# The start's ask for the handoff: the GET starts' query parameter (the string "1" alone) and the POST starts' key.
HANDOFF_QUERY = {"handoff": "1"}
HANDOFF_BODY = {"handoff": True}


def handoff_code(response) -> str:
    """The one-time code a successful callback's redirect carries, in its fragment and nowhere else."""
    assert response.status_code == 302, response.text
    location = response.headers["location"]
    parts = urlsplit(location)
    assert location.startswith(f"{settings.FRONTEND_URL}{LANDING}#"), location
    assert parts.path == LANDING and parts.query == "" and "?" not in location, location
    name, _, code = parts.fragment.partition("=")
    assert name == "code" and code and code.isascii() and "&" not in code, location
    return code


def complete_sign_in(client, response):
    """The landing page's exchange of the code ``response`` (a callback's answer to ``client``) carries."""
    return client.post(COMPLETE_PATH, json={"code": handoff_code(response)})
