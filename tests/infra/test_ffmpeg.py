from app.infra import ffmpeg


def test_explicit_ffmpeg_path_is_used(monkeypatch, tmp_path):
    executable = tmp_path / "ffmpeg.exe"
    executable.write_bytes(b"binary")
    monkeypatch.setenv("FFMPEG_BINARY", str(executable))
    ffmpeg.ffmpeg_executable.cache_clear()

    result = ffmpeg.ffmpeg_executable()

    assert result == str(executable.resolve())
    ffmpeg.ffmpeg_executable.cache_clear()
