import os
import sys

# ──────────────────────────────────────────────
#  API Endpoints
# ──────────────────────────────────────────────
LOGIN_URL = "https://kiet.cybervidya.net/api/auth/login"
COURSES_URL = "https://kiet.cybervidya.net/api/student/dashboard/registered-courses"
TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# ──────────────────────────────────────────────
#  CyberVidya Credentials  (GitHub Secrets)
# ──────────────────────────────────────────────
CV_USERNAME = os.environ.get("CV_USERNAME", "")
CV_PASSWORD = os.environ.get("CV_PASSWORD", "")
CV_AUTH_TOKEN = os.environ.get("CV_AUTH_TOKEN", "")
CV_AUTH_PREF = os.environ.get("CV_AUTH_PREF", "Bearer ")

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
    """Check that minimum required secrets are set."""
    has_token = bool(CV_AUTH_TOKEN)
    has_creds = bool(CV_USERNAME and CV_PASSWORD)
    has_telegram = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

    if not has_token and not has_creds:
        print("ERROR: No credentials provided.")
        print("Set either CV_AUTH_TOKEN or both CV_USERNAME + CV_PASSWORD as GitHub Secrets.")
        sys.exit(1)

    if not has_telegram:
        print("WARNING: Telegram not configured. Notifications will only print to console.")
