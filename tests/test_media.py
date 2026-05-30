from __future__ import annotations

from pathlib import Path

from PIL import Image

from kol_monitor.media import detect_ext, media_path, validate_image


def test_detect_ext_prefers_content_type():
    assert detect_ext("https://example.com/image?id=1", "image/webp") == "webp"
    assert detect_ext("https://example.com/image", "image/jpeg") == "jpg"


def test_detect_ext_uses_url_suffix():
    assert detect_ext("https://example.com/a/photo.png?format=png", None) == "png"
    assert detect_ext("https://example.com/a/video.mp4", None) == "mp4"


def test_media_path_uses_date_handle_and_index(tmp_path):
    path = media_path("2026-05-29", "qinbafrank", "1800", 2, "jpg", root=tmp_path)

    assert path == tmp_path / "2026-05-29" / "qinbafrank" / "1800_2.jpg"


def test_validate_image_accepts_real_image(tmp_path):
    path = tmp_path / "image.jpg"
    Image.new("RGB", (8, 8), "white").save(path)

    assert validate_image(path) is True
    assert validate_image(Path("/no/such/file.jpg")) is False
