"""Runtime settings, read from environment variables (or backend/.env)."""

import os
import secrets
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
SNAPSHOT_DIR = DATA_DIR / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'ppe.db').as_posix()}")


def _load_jwt_secret() -> str:
    """Use JWT_SECRET if set, otherwise generate one and persist it so logins survive restarts."""
    if os.getenv("JWT_SECRET"):
        return os.environ["JWT_SECRET"]
    secret_file = DATA_DIR / ".jwt_secret"
    if not secret_file.exists():
        secret_file.write_text(secrets.token_urlsafe(48))
    return secret_file.read_text().strip()


JWT_SECRET = _load_jwt_secret()
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "12"))

# Calendar days for date filters and reports, e.g. "Asia/Kolkata". Default: this machine's local time.
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "")
APP_TZ = ZoneInfo(APP_TIMEZONE) if APP_TIMEZONE else datetime.now().astimezone().tzinfo

# Comma-separated list of allowed frontend origins, or "*" for any (fine on a private LAN).
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# First admin account, created on startup only if the users table is empty.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# Detection models and thresholds
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PPE_MODEL_PATH = os.getenv("PPE_MODEL_PATH", str(BASE_DIR / "weights" / "ppe_yolov8n.pt"))
POSE_MODEL_PATH = os.getenv("POSE_MODEL_PATH", str(BASE_DIR / "weights" / "yolov8n-pose.pt"))
DEVICE = os.getenv("DEVICE", "")  # "" = auto (GPU if available), or "cpu", "0"
PPE_CONFIDENCE = float(os.getenv("PPE_CONFIDENCE", "0.35"))
PERSON_CONFIDENCE = float(os.getenv("PERSON_CONFIDENCE", "0.5"))
KEYPOINT_CONFIDENCE = float(os.getenv("KEYPOINT_CONFIDENCE", "0.1"))
# Number of recent frames the live result is smoothed over (majority vote per item).
SMOOTHING_FRAMES = int(os.getenv("SMOOTHING_FRAMES", "8"))
