"""What a refused request's 422 may say about what was sent, and the text check a password takes first (E97).

FastAPI's default answer to a request that fails validation lists each error whole: the value it refused under
``input`` (for a missing field, the whole body, a password beside it) and the exception a validator raised under
``ctx``. So a 422 quoted a refused password back, and so did the error's own text
(``RequestValidationError.__str__`` prints every error, ``input`` included), which a log line or a Sentry event
carries whenever the answer fails to render. One such value always failed it: a lone surrogate (JSON's ``"\\ud800"``
escape decodes to one) encodes to no UTF-8 at all, so rendering the 422 raised and the request answered 500 with a
traceback that quoted the password; a password long enough to pass the length rule reached the breach check and
bcrypt instead, whose encode raised the same 500.

``public_validation_errors`` keeps what a client reads, each error's ``type``, ``loc`` and ``msg``
(``frontend/lib/api/client.ts::detailMessage`` shows the first ``msg``), drops everything else, and returns only
strings that encode to UTF-8; ``main.py`` answers ``RequestValidationError`` with it. ``is_valid_unicode`` is the
check ``password_utils.validate_password_strength`` runs before its length rule, so a password that cannot be
encoded is refused where it enters instead of where it is hashed.

Pure: no HTTP framework import (``tests/unit/test_services_http_free_allowlist.py``).
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def is_valid_unicode(text: str) -> bool:
    """Whether ``text`` encodes to UTF-8: false only for a lone surrogate, the one code point a Python ``str`` can
    hold that UTF-8 cannot carry (a JSON surrogate pair decodes to the character it encodes)."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def public_validation_errors(errors: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Each validation error as ``{"type", "loc", "msg"}`` only, every string in it encodable as UTF-8.

    Dropped: ``input`` (the refused value, or the whole body for a missing field), ``ctx`` (the validator's
    exception, or a decode error's own message) and ``url``, with any key a later pydantic adds. A ``loc`` part is
    a field name, a dict key or a list index; a key comes from the body, so it is made encodable like the rest.

    Total over any input, so it never raises: an exception here would chain the ``RequestValidationError``, whose
    text prints every ``input``, into the 500's log line and Sentry event. An error that is not a mapping, or a
    ``loc`` that is not a list or tuple, keeps only what can be read from it.
    """
    public = []
    for error in errors:
        error = error if isinstance(error, Mapping) else {}
        loc = error.get("loc")
        public.append({
            "type": _encodable(str(error.get("type", ""))),
            "loc": [part if type(part) is int else _encodable(str(part)) for part in loc]
            if isinstance(loc, (list, tuple)) else [],
            "msg": _encodable(str(error.get("msg", ""))),
        })
    return public


def _encodable(text: str) -> str:
    """``text`` with each code point UTF-8 cannot carry (a lone surrogate) replaced by ``?``."""
    return text.encode("utf-8", "replace").decode("utf-8")
