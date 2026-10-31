"""Validation helpers for short, user-supplied text fields (display names, free-text tags)."""
import unicodedata


def has_control_characters(value: str) -> bool:
    """True if ``value`` carries a control character (Unicode category Cc: the C0/C1 controls,
    including CR, LF, TAB and DEL). Such characters have no place in a name or a tag; letters,
    marks, spaces and punctuation in every script pass."""
    return any(unicodedata.category(ch) == "Cc" for ch in value)
