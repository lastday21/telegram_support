from __future__ import annotations

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER_TOKEN_PATH = ROOT / ".env.access"


def _read_existing_token() -> str | None:
    if not SERVER_TOKEN_PATH.exists():
        return None
    for line in SERVER_TOKEN_PATH.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip() == "APP_ACCESS_TOKEN" and value.strip():
            return value.strip()
    return None


def _read_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip():
            values[name.strip()] = value.strip()
    return values


def main() -> None:
    token = _read_existing_token() or secrets.token_urlsafe(48)
    SERVER_TOKEN_PATH.write_text(
        f"APP_ACCESS_TOKEN={token}\n",
        encoding="utf-8",
    )

    app_data = Path(os.getenv("APPDATA") or Path.home())
    client_dir = app_data / "SmartHelper"
    client_dir.mkdir(parents=True, exist_ok=True)
    client_path = client_dir / ".env"
    client_values = _read_values(client_path)
    client_path.write_text(
        "\n".join(
            (
                "SERVER_URL="
                + client_values.get("SERVER_URL", "http://127.0.0.1:8000"),
                f"APP_ACCESS_TOKEN={token}",
                "TG_CHAT_ID=" + client_values.get("TG_CHAT_ID", ""),
                "MIC_DEVICE=" + client_values.get("MIC_DEVICE", ""),
                "MIX_DEVICE=" + client_values.get("MIX_DEVICE", ""),
                "",
            )
        ),
        encoding="utf-8",
    )

    print(f"Настройки Docker: {SERVER_TOKEN_PATH}")
    print(f"Настройки Windows: {client_path}")
    print("Ключ доступа создан, его значение не выводилось.")


if __name__ == "__main__":
    main()
