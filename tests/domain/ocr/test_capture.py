"""
Юнит-тесты для функции take_screenshot() из src.domain.ocr.capture.

     1  (region=None, monitor=1, PNG) –
   • вызывается sct.shot(); возвращаются байты «файла».

     2  (region=(x,y,w,h), JPG) –
   • вызывается sct.grab() → tools.to_png();
   • картинка конвертируется через Pillow;
   • функция возвращает байты «JPEG».

Все внешние зависимости мокаем:
  * mss.mss, mss.tools.to_png
  * PIL.Image
"""
from __future__ import annotations
import pathlib
import sys
import types
import importlib
import pytest



@pytest.fixture
def capture_module(monkeypatch):
    """
    Готовит фэйковые библиотеки и импортирует src.domain.ocr.capture заново,
    чтобы каждый тест работал с собственным словарём `calls`.
    """


    calls: dict[str, object] = {}


    def _fake_to_png(rgb, size):
        calls["to_png_called"] = True
        return b"PNG_BYTES"

    fake_tools = types.SimpleNamespace(to_png=_fake_to_png)


    class _FakeMSS:
        def __init__(self, *_, **__):
            self.monitors = [None, {"left": 0, "top": 0, "width": 1920, "height": 1080}]

        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): return False

        def shot(self, output: str, mon: int):
            calls["shot_called"] = True
            pathlib.Path(output).write_bytes(b"FILE_BYTES")

        def grab(self, region_dict):
            calls["grab_called"] = True

            class _Img:
                rgb = b"RGB"
                size = (region_dict["width"], region_dict["height"])

            return _Img()

    sys.modules["mss"] = types.SimpleNamespace(mss=_FakeMSS, tools=fake_tools)


    class _FakeImageObj:
        def save(self, buf, format): buf.write(b"JPEG_BYTES")
        def __enter__(self): return self
        def __exit__(self, exc_type, exc, tb): return False

    def _fake_image_open(buf):
        calls["image_open_called"] = True
        return _FakeImageObj()

    fake_pil_image = types.SimpleNamespace(open=_fake_image_open)
    fake_pil_mod = types.ModuleType("PIL")
    fake_pil_mod.Image = fake_pil_image
    sys.modules["PIL"] = fake_pil_mod
    sys.modules["PIL.Image"] = fake_pil_image


    sys.modules.pop("src.domain.ocr.capture", None)          # <-- ключевой сброс
    capture = importlib.import_module("src.domain.ocr.capture")

    return capture, calls



    sys.modules["mss"] = types.SimpleNamespace(mss=_FakeMSS, tools=fake_tools)


    class _FakeImageObj:
        def save(self, buf, format):

            buf.write(b"JPEG_BYTES")


        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_image_open(_bytes_io):
        calls["image_open_called"] = True
        return _FakeImageObj()

    fake_pil_image = types.SimpleNamespace(open=_fake_image_open)
    fake_pil_mod = types.ModuleType("PIL")
    fake_pil_mod.Image = fake_pil_image
    sys.modules["PIL"] = fake_pil_mod
    sys.modules["PIL.Image"] = fake_pil_image


    capture = importlib.import_module("src.domain.ocr.capture")

    return capture, calls


def test_full_monitor_png(capture_module):
    """
    region=None → используется sct.shot → возвращаются «FILE_BYTES».
    """
    capture, calls = capture_module

    out = capture.take_screenshot(output_format="png")

    assert out == b"FILE_BYTES"
    assert calls.get("shot_called") is True

    assert "grab_called" not in calls
    assert "to_png_called" not in calls


def test_region_jpg(capture_module):
    """
    region != None → grab() + to_png() + Pillow-конвертация → «JPEG_BYTES».
    """
    capture, calls = capture_module

    out = capture.take_screenshot(region=(0, 0, 100, 100), output_format="jpg")

    assert out == b"JPEG_BYTES"
    assert calls.get("grab_called") is True
    assert calls.get("to_png_called") is True
    assert calls.get("image_open_called") is True
