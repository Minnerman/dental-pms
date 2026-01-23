import re

__all__ = ["normalize_status"]

_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)


def normalize_status(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _WHITESPACE_RE.sub(" ", value.strip())
    if not cleaned:
        return None
    return cleaned.lower()
