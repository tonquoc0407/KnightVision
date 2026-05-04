from __future__ import annotations

import sys
import types
from pathlib import Path

from ingestion.downloader import download_dump


def test_download_dump_uses_rated_standard_filename(tmp_path, monkeypatch):
    calls: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield b"abc"

    def fake_stream(method, url, *, follow_redirects, timeout):
        calls["method"] = method
        calls["url"] = url
        calls["follow_redirects"] = follow_redirects
        calls["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setitem(sys.modules, "httpx", types.SimpleNamespace(stream=fake_stream))

    path = download_dump("2026-04", tmp_path)

    assert path == Path(tmp_path) / "lichess_db_standard_rated_2026-04.pgn.zst"
    assert path.read_bytes() == b"abc"
    assert calls == {
        "method": "GET",
        "url": "https://database.lichess.org/standard/lichess_db_standard_rated_2026-04.pgn.zst",
        "follow_redirects": True,
        "timeout": None,
    }