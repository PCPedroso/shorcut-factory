"""
Testes do cache local de thumbnails da Biblioteca de Vídeos (ensure_local_thumbnail).
Garante que thumbnails remotas (ex: pbs.twimg.com, que bloqueia hotlink com Referer localhost)
sejam baixadas pelo servidor e servidas localmente, com fallback para frame do vídeo.
"""
import os
from unittest import mock

import cv2
import numpy as np

import core.library_manager as lm

JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 4096


class _FakeResp:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _setup(tmp_path, monkeypatch, vid):
    monkeypatch.setattr(lm, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(lm, "_THUMB_FALLBACK_DIR", str(tmp_path / ".thumb_cache"))
    lm._THUMB_FAILED_IDS.clear()
    (tmp_path / vid).mkdir()


def test_local_file_returned_as_is(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, "v1")
    f = tmp_path / "v1" / "thumb.jpg"
    f.write_bytes(JPEG_BYTES)
    assert lm.ensure_local_thumbnail("v1", str(f)) == str(f)


def test_remote_url_downloaded_and_cached(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, "tw_1")
    with mock.patch("urllib.request.urlopen", return_value=_FakeResp(JPEG_BYTES)) as m:
        p1 = lm.ensure_local_thumbnail("tw_1", "https://pbs.twimg.com/media/x.jpg?name=orig")
        p2 = lm.ensure_local_thumbnail("tw_1", "https://pbs.twimg.com/media/x.jpg?name=orig")
    assert p1 == p2 and os.path.exists(p1)
    assert m.call_count == 1  # segunda chamada usa o cache
    sent_headers = {k.lower() for k in m.call_args[0][0].headers}
    assert "referer" not in sent_headers


def test_invalid_download_falls_back_to_video_frame(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, "tw_2")
    video = str(tmp_path / "tw_2" / "video_full.mp4")
    wr = cv2.VideoWriter(video, cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
    for _ in range(10):
        wr.write(np.full((240, 320, 3), 120, np.uint8))
    wr.release()
    with mock.patch("urllib.request.urlopen", return_value=_FakeResp(b"<html>Forbidden</html>")):
        p = lm.ensure_local_thumbnail("tw_2", "https://pbs.twimg.com/media/y.jpg")
    assert p and os.path.exists(p)


def test_no_source_returns_empty(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, "v3")
    assert lm.ensure_local_thumbnail("v3", None) == ""
