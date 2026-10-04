"""
Content-addressed document storage.

Files are stored as ``<data_dir>/documents/<sha256>.pdf``. The path is derived only
from a validated hex digest, so client-supplied names can never influence it
(no traversal, no collisions). Writes are atomic (temp file + rename).
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class FileStore:
    """Store and retrieve uploaded PDFs by SHA-256."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, sha256: str) -> Path:
        if not _HEX64.match(sha256):
            raise ValueError("invalid document digest")
        return self._root / f"{sha256}.pdf"

    def put(self, sha256: str, content: bytes) -> str:
        path = self._path(sha256)
        if not path.exists():
            fd, tmp = tempfile.mkstemp(dir=self._root, prefix=".upload-", suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(content)
                os.replace(tmp, path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
            os.chmod(path, 0o600)
        return path.name

    def get(self, sha256: str) -> bytes | None:
        path = self._path(sha256)
        return path.read_bytes() if path.exists() else None

    def exists(self, sha256: str) -> bool:
        return self._path(sha256).exists()

    def delete(self, sha256: str) -> bool:
        path = self._path(sha256)
        if path.exists():
            path.unlink()
            return True
        return False

    def cleanup_temp(self) -> int:
        """Remove stale temporary upload files (e.g. after a crash)."""
        removed = 0
        for tmp in self._root.glob(".upload-*.tmp"):
            tmp.unlink(missing_ok=True)
            removed += 1
        return removed
