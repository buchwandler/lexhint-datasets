#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import sys
import tempfile
from pathlib import Path
from typing import TextIO

from scripts.config import SUPPORTED_BASE_LANGUAGES


class SplitError(RuntimeError):
    """The raw source could not be split into configured language inputs."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _open_source(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def _open_gzip_text(path: Path) -> tuple[gzip.GzipFile, io.TextIOWrapper]:
    raw = path.open("wb")
    compressed = gzip.GzipFile(
        filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0
    )
    return compressed, io.TextIOWrapper(compressed, encoding="utf-8", newline="")


def split_source(
    source: str | Path,
    output_dir: str | Path,
    languages: tuple[str, ...] | list[str],
    *,
    upstream_sha256: str | None = None,
    manifest_path: str | Path | None = None,
) -> dict[str, object]:
    """Split one source into physical base-language inputs.

    Regional English locale preferences stay in Lexhint and never create source
    splits or physical dataset artifacts here.
    """
    source_path = Path(source)
    if not source_path.is_file():
        raise SplitError(f"source file not found: {source_path}")
    selected = tuple(
        dict.fromkeys(language.strip() for language in languages if language.strip())
    )
    if not selected:
        raise SplitError("at least one target base language is required")
    unsupported = sorted(set(selected) - set(SUPPORTED_BASE_LANGUAGES))
    if unsupported:
        raise SplitError(f"regional or unsupported build language: {unsupported}")
    upstream_digest = sha256(source_path)
    if upstream_sha256 and upstream_digest != upstream_sha256.lower():
        raise SplitError(
            f"upstream SHA-256 mismatch: expected {upstream_sha256}, got {upstream_digest}"
        )

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    manifest_target = (
        Path(manifest_path) if manifest_path else destination / "source-splits-v1.json"
    )
    if not manifest_target.is_absolute():
        manifest_target = (
            destination / manifest_target
            if manifest_target.parent == Path(".")
            else manifest_target
        )

    with tempfile.TemporaryDirectory(
        prefix=".source-split-", dir=destination
    ) as temporary_name:
        temporary_dir = Path(temporary_name)
        writers: dict[str, tuple[gzip.GzipFile, io.TextIOWrapper]] = {}
        counts = {language: 0 for language in selected}
        try:
            for language in selected:
                writers[language] = _open_gzip_text(
                    temporary_dir / f"{language}.jsonl.gz"
                )
            with _open_source(source_path) as source_handle:
                for line_number, raw_line in enumerate(source_handle, 1):
                    if not raw_line.strip():
                        continue
                    try:
                        entry = json.loads(raw_line)
                    except json.JSONDecodeError as exc:
                        raise SplitError(
                            f"invalid JSON on source line {line_number}: {exc.msg}"
                        ) from exc
                    language = entry.get("lang_code")
                    writer = writers.get(language)
                    if writer is not None:
                        writer[1].write(raw_line)
                        counts[language] += 1
        finally:
            for compressed, text_writer in writers.values():
                text_writer.close()
                compressed.close()

        splits: dict[str, object] = {}
        for language in selected:
            temporary_file = temporary_dir / f"{language}.jsonl.gz"
            target = destination / temporary_file.name
            temporary_file.replace(target)
            splits[language] = {
                "path": str(target),
                "kind": "language-split",
                "upstream_sha256": upstream_digest,
                "sha256": sha256(target),
                "entries": counts[language],
            }
        manifest = {
            "manifest_version": 1,
            "upstream_sha256": upstream_digest,
            "source": str(source_path),
            "splits": splits,
        }
        manifest_target.parent.mkdir(parents=True, exist_ok=True)
        manifest_target.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Split raw Wiktextract JSONL by language."
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--languages", required=True)
    parser.add_argument("--upstream-sha256")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    try:
        manifest = split_source(
            args.source,
            args.output_dir,
            tuple(args.languages.split(",")),
            upstream_sha256=args.upstream_sha256,
            manifest_path=args.manifest,
        )
    except (SplitError, OSError) as exc:
        print(f"source split failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
