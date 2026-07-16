import os
import shutil
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

root = Path(".").resolve()
app_dir = root / "app"
common_options = {
    "pathex": [str(root)],
    "datas": [],
    "hookspath": [],
    "runtime_hooks": [],
    "win_no_prefer_redirects": False,
    "win_private_assemblies": False,
    "cipher": block_cipher,
    "noarchive": False,
}

ffmpeg_binary = os.getenv("FFMPEG_BINARY") or shutil.which("ffmpeg")
if not ffmpeg_binary:
    local_ffmpeg = sorted(Path("F:/").glob("ffmpeg*/bin/ffmpeg.exe"))
    ffmpeg_binary = str(local_ffmpeg[0]) if local_ffmpeg else None
if not ffmpeg_binary or not Path(ffmpeg_binary).is_file():
    raise RuntimeError("FFmpeg не найден: сборка SmartHelper невозможна")

main_analysis = Analysis(
    [str(app_dir / "desktop.py")],
    binaries=[(ffmpeg_binary, ".")],
    hiddenimports=collect_submodules("PIL") + ["keyboard", "mss"],
    excludes=["telegram", "fastapi", "uvicorn", "pystray"],
    **common_options,
)
main_pyz = PYZ(
    main_analysis.pure,
    main_analysis.zipped_data,
    cipher=block_cipher,
)
main_exe = EXE(
    main_pyz,
    main_analysis.scripts,
    main_analysis.binaries,
    main_analysis.zipfiles,
    main_analysis.datas,
    [],
    name="SmartHelper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(root / "icon.ico"),
)

settings_analysis = Analysis(
    [str(app_dir / "settings_app.py")],
    binaries=[],
    hiddenimports=["keyboard"],
    excludes=["telegram", "fastapi", "uvicorn", "pystray", "PIL", "mss"],
    **common_options,
)
settings_pyz = PYZ(
    settings_analysis.pure,
    settings_analysis.zipped_data,
    cipher=block_cipher,
)
settings_exe = EXE(
    settings_pyz,
    settings_analysis.scripts,
    settings_analysis.binaries,
    settings_analysis.zipfiles,
    settings_analysis.datas,
    [],
    name="SmartHelperSettings",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(root / "icon.ico"),
)
