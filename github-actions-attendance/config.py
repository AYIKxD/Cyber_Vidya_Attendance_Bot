import os
import sys

# ──────────────────────────────────────────────
#  API Endpoints
# ──────────────────────────────────────────────
COURSES_URL = "https://kiet.cybervidya.net/api/student/dashboard/registered-courses"
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# ──────────────────────────────────────────────
#  Auth Token  (GitHub Secrets)
# ──────────────────────────────────────────────
CV_AUTH_TOKEN = os.environ.get("CV_AUTH_TOKEN", "")
CV_AUTH_PREF = os.environ.get("CV_AUTH_PREF", "")

# ──────────────────────────────────────────────
#  Telegram Bot  (GitHub Secrets)
# ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ──────────────────────────────────────────────
#  Settings
# ──────────────────────────────────────────────
TIMEZONE = "Asia/Kolkata"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "attendance_state.json")
MIN_ATTENDANCE_PCT = 75
REQUEST_TIMEOUT = 30


def validate():
    if not CV_AUTH_TOKEN:
        print("WARNING: CV_AUTH_TOKEN not set. Bot will check Telegram for /token command.")

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("WARNING: Telegram not configured. Notifications will only print to console.")
