#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen


class SourceError(RuntimeError):
    """The upstream source could not be acquired or verified."""


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_sha256(path: str | Path, expected: str) -> str:
    actual = sha256(path)
    if actual != expected.lower():
        raise SourceError(f"source SHA-256 mismatch: expected {expected}, got {actual}")
    return actual


def _copy_url(url: str, target: Path) -> None:
    parsed = urlparse(url)
    if parsed.scheme in {"", "file"}:
        source = Path(parsed.path if parsed.scheme == "file" else url)
        if not source.is_file():
            raise SourceError(f"source file not found: {source}")
        with source.open("rb") as src, target.open("wb") as dst:
            shutil.copyfileobj(src, dst, length=1024 * 1024)
        return
    try:
        with urlopen(url) as response, target.open("wb") as dst:
            shutil.copyfileobj(response, dst, length=1024 * 1024)
    except OSError as exc:
        raise SourceError(f"source download failed: {url}: {exc}") from exc


def download_source(
    url: str,
    output: str | Path,
    *,
    expected_sha256: str | None = None,
    require_sha256: bool = False,
) -> Path:
    if require_sha256 and not expected_sha256:
        raise SourceError("source SHA-256 is required")
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        _copy_url(url, temporary)
        if expected_sha256:
            verify_sha256(temporary, expected_sha256)
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download and verify a Lexhint source snapshot."
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sha256")
    parser.add_argument("--require-sha256", action="store_true")
    args = parser.parse_args()
    try:
        path = download_source(
            args.url,
            args.output,
            expected_sha256=args.sha256,
            require_sha256=args.require_sha256,
        )
    except (SourceError, OSError) as exc:
        print(f"source download failed: {exc}", file=sys.stderr)
        return 1
    print(f"{sha256(path)}  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
