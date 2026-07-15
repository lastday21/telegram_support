from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

root = Path(".").resolve()
app_dir = root / "app"

hiddenimports = collect_submodules("PIL") + ["keyboard", "mss"]

a = Analysis(
    [str(app_dir / "desktop.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["telegram", "fastapi", "uvicorn"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="SmartHelper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(root / "icon.ico"),
)
