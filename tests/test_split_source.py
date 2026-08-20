from pathlib import Path
import pytest
import gzip
import json

from scripts.split_source import SplitError, split_source


def test_split_source_preserves_selected_lines_and_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    lines = [
        '{"word":"house","lang_code":"en"}\n',
        '{"word":"Haus","lang_code":"de"}\n',
        '{"word":"ignored","lang_code":"fr"}\n',
    ]
    source.write_text("".join(lines), encoding="utf-8")

    manifest = split_source(source, tmp_path / "split", ("en", "de"))
    assert manifest["upstream_sha256"]
    assert manifest["splits"]["en"]["entries"] == 1
    assert manifest["splits"]["de"]["entries"] == 1
    assert json.loads(
        gzip.open(manifest["splits"]["en"]["path"], "rt", encoding="utf-8").read()
    ) == {"word": "house", "lang_code": "en"}

    split_source(source, tmp_path / "split-second", ("en", "de"))
    assert (tmp_path / "split" / "en.jsonl.gz").read_bytes() == (
        tmp_path / "split-second" / "en.jsonl.gz"
    ).read_bytes()


def test_split_source_rejects_bad_json_without_replacing_existing_outputs(
    tmp_path: Path,
) -> None:
    source = tmp_path / "bad.jsonl"
    source.write_text('{"word":"ok","lang_code":"en"}\nnot-json\n', encoding="utf-8")
    output = tmp_path / "split"
    output.mkdir()
    existing = output / "en.jsonl.gz"
    existing.write_bytes(b"existing")

    with pytest.raises(SplitError, match="line 2"):
        split_source(source, output, ("en",))
    assert existing.read_bytes() == b"existing"
