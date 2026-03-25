"""Regex signature generation for Failure Insights."""

from __future__ import annotations

import re

_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_TIMESTAMP_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:\d{2})?)?"
)
_PATH_PATTERN = re.compile(r"(?:(?:[A-Za-z]:\\)|/)[^\s:]+")
_NUMBER_PATTERN = re.compile(r"\d+")

_PLACEHOLDERS = {
    "__TS__": _TIMESTAMP_PATTERN.pattern,
    "__NUM__": r"\d+",
    "__PATH__": _PATH_PATTERN.pattern,
    "__UUID__": _UUID_PATTERN.pattern,
}


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _insert_placeholders(text: str) -> str:
    text = _UUID_PATTERN.sub("__UUID__", text)
    text = _TIMESTAMP_PATTERN.sub("__TS__", text)
    text = _PATH_PATTERN.sub("__PATH__", text)

    def replace_number(match: re.Match[str]) -> str:
        value = match.group(0)
        if len(value) == 3:
            prefix = text[max(0, match.start() - 5) : match.start()]
            if re.search(r"(?i)http $", prefix):
                return value
        return "__NUM__"

    return _NUMBER_PATTERN.sub(replace_number, text)


def extract_signature(highlighted_text: str) -> str:
    """Return a regex signature for user-highlighted log text."""

    normalized = _normalize_whitespace(highlighted_text)
    if not normalized:
        return ""

    with_placeholders = _insert_placeholders(normalized)
    escaped = re.escape(with_placeholders)

    for placeholder, fragment in _PLACEHOLDERS.items():
        escaped = escaped.replace(re.escape(placeholder), fragment)

    return escaped


def build_signature_regex(highlighted_text: str) -> str:
    return extract_signature(highlighted_text)
