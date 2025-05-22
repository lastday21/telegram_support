import os, sys, pathlib
from dotenv import load_dotenv


ROOT = pathlib.Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"

if not ENV_PATH.exists():
    sys.exit(f"[config] .env not found → {ENV_PATH}")

load_dotenv(ENV_PATH, override=True)   # <-- ключевой фикс

# ─── ключи ────────────────────────────────────────────────
YC_API_KEY   = os.getenv("YC_API_KEY")
YC_FOLDER_ID = os.getenv("YC_FOLDER_ID")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID   = os.getenv("TG_CHAT_ID")
os.environ["YC_FOLDER_ID"] = YC_FOLDER_ID

for var in ("YC_API_KEY", "YC_FOLDER_ID", "TG_BOT_TOKEN", "TG_CHAT_ID"):
    if not globals()[var]:
        sys.exit(f"[config] {var} не найден в .env")