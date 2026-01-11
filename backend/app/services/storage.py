from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile

ATTACHMENTS_DIR = Path("/data/attachments")
CHUNK_SIZE = 1024 * 1024


def _ensure_dir() -> None:
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_path(storage_key: str) -> Path:
    safe_key = storage_key.strip()
    path = (ATTACHMENTS_DIR / safe_key).resolve()
    base = ATTACHMENTS_DIR.resolve()
    if str(path) == str(base) or not str(path).startswith(f"{base}/"):
        raise ValueError("Invalid storage key")
    return path


def save_upload(upload_file: UploadFile, max_bytes: int) -> tuple[str, int]:
    _ensure_dir()
    storage_key = uuid.uuid4().hex
    path = _resolve_path(storage_key)
    total = 0
    try:
        with path.open("wb") as handle:
            while True:
                chunk = upload_file.file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("File exceeds max upload size")
                handle.write(chunk)
    except Exception:
        if path.exists():
            path.unlink()
        raise
    return storage_key, total


def open_file(storage_key: str):
    path = _resolve_path(storage_key)
    return path.open("rb")


def delete_file(storage_key: str) -> None:
    path = _resolve_path(storage_key)
    if path.exists():
        path.unlink()
