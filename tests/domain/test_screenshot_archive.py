import os

from app.domain.screenshot_archive import save_screenshot, screenshot_directory


def test_screenshot_is_saved_outside_project_directory(tmp_path):
    saved = save_screenshot(b"PNG_BYTES", base_dir=tmp_path)

    assert saved is not None
    assert saved.parent == tmp_path / "SmartHelper" / "screenshots"
    assert saved.read_bytes() == b"PNG_BYTES"
    assert screenshot_directory(tmp_path) == saved.parent


def test_default_directory_uses_local_app_data(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert screenshot_directory() == tmp_path / "SmartHelper" / "screenshots"


def test_only_latest_hundred_screenshots_are_kept(tmp_path):
    directory = screenshot_directory(tmp_path)
    directory.mkdir(parents=True)
    old_files = []
    for index in range(100):
        path = directory / f"screenshot_20260723_120000_{index:06d}.png"
        path.write_bytes(str(index).encode())
        os.utime(path, (index + 1, index + 1))
        old_files.append(path)

    saved = save_screenshot(b"NEW", base_dir=tmp_path)

    screenshots = list(directory.glob("screenshot_*.png"))
    assert saved is not None
    assert len(screenshots) == 100
    assert not old_files[0].exists()
    assert saved.exists()
