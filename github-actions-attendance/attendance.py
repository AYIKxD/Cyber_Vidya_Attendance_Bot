import requests
import json
import math
import os
import sys
from datetime import datetime
import pytz
import config

config.validate()

INDIA_TZ = pytz.timezone(config.TIMEZONE)
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.json")


def get_india_time():
    return datetime.now(INDIA_TZ)


# ── Token management ──

def load_token():
    """Load token: check Telegram for updates first, then cached file, then env."""
    # Check if user sent a new token via Telegram
    tg_token, tg_pref = check_telegram_for_token()
    if tg_token:
        save_token(tg_token, tg_pref)
        print("Token updated from Telegram!")
        return tg_token, tg_pref

    # Try cached file
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
        if data.get("token"):
            print("Using cached token.")
            return data["token"], data.get("auth_pref", "")

    # Fall back to env/secret
    if config.CV_AUTH_TOKEN:
        print("Using token from secret.")
        return config.CV_AUTH_TOKEN, config.CV_AUTH_PREF

    print("ERROR: No token available.")
    send_telegram("🔑 No token found. Send your token:\n\n`/token YOUR_TOKEN`\n`/authpref YOUR_PREFIX`")
    sys.exit(1)


def save_token(token, auth_pref=""):
    with open(TOKEN_FILE, "w") as f:
        json.dump({"token": token, "auth_pref": auth_pref}, f)


def check_telegram_for_token():
    """Check recent Telegram messages for /token and /authpref commands."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return None, None

    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates"
        resp = requests.get(url, params={"limit": 20, "timeout": 0}, timeout=10)
        data = resp.json()

        if not data.get("ok"):
            return None, None

        token = None
        auth_pref = ""

        for update in data.get("result", []):
            msg = update.get("message", {})
            chat_id = str(msg.get("chat", {}).get("id", ""))
            text = (msg.get("text") or "").strip()

            # Only accept commands from the configured chat
            if chat_id != config.TELEGRAM_CHAT_ID:
                continue

            if text.startswith("/token "):
                token = text[7:].strip()
            elif text.startswith("/authpref "):
                auth_pref = text[10:].strip()

        if token:
            # Clear processed updates
            if data.get("result"):
                last_id = data["result"][-1]["update_id"]
                requests.get(url, params={"offset": last_id + 1, "timeout": 0}, timeout=10)
            print(f"Found /token command in Telegram (token: {token[:15]}...)")
            return token, auth_pref

    except Exception as e:
        print(f"Telegram check failed (non-fatal): {e}")

    return None, None


# ── Core functions ──

def fetch_courses(token, auth_pref):
    headers = {"Authorization": auth_pref + token}
    resp = requests.get(config.COURSES_URL, headers=headers, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()["data"]


def send_telegram(msg):
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("Telegram not configured, skipping.")
        print("Message:", msg)
        return
    url = config.TELEGRAM_API.format(token=config.TELEGRAM_BOT_TOKEN)
    payload = {"chat_id": config.TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    r = requests.post(url, json=payload, timeout=15)
    print("Telegram status:", r.json().get("ok", False))


def calculate_attendance_message(course, present, total, status):
    percentage = (present / total * 100) if total > 0 else 0
    pct = config.MIN_ATTENDANCE_PCT / 100

    icon = "✅" if status == "Present" else "❌" if status == "Absent" else "📝"

    msg = f"{icon} *{course}*\n\n"
    msg += f"    `{present}/{total}` — *{percentage:.1f}%*\n\n"

    if percentage < config.MIN_ATTENDANCE_PCT:
        x = max(0, math.ceil((pct * total - present) / (1 - pct)))
        msg += f"⚠️ Below {config.MIN_ATTENDANCE_PCT}%. Attend next *{x}* to recover."
    else:
        y = max(0, math.floor(present / pct - total))
        msg += f"You can skip *{y}* more class(es) safely."

    return msg


def check_attendance():
    india_time = get_india_time()
    print(f"Checking attendance at {india_time.strftime('%Y-%m-%d %H:%M:%S IST')}...")

    token, auth_pref = load_token()
    courses = fetch_courses(token, auth_pref)

    # Token worked — cache it
    save_token(token, auth_pref)

    if os.path.exists(config.STATE_FILE):
        with open(config.STATE_FILE, "r") as f:
            prev_state = json.load(f)
    else:
        prev_state = {}

    new_state = {}
    changes_found = False

    for c in courses:
        code = c["courseCode"]
        comp = c["studentCourseCompDetails"][0]
        present = comp["presentLecture"]
        total = comp["totalLecture"]

        new_state[code] = {"present": present, "total": total}

        old = prev_state.get(code, {})
        if old.get("present") != present or old.get("total") != total:
            changes_found = True
            status = "Unknown"
            old_present = old.get("present", 0)
            old_total = old.get("total", 0)
            if present > old_present and total > old_total:
                status = "Present"
            elif present == old_present and total > old_total:
                status = "Absent"

            msg = calculate_attendance_message(c["courseName"], present, total, status)
            send_telegram(msg)

    with open(config.STATE_FILE, "w") as f:
        json.dump(new_state, f)

    if not changes_found:
        print("No attendance changes detected.")
    else:
        print("Attendance changes found and notifications sent.")


if __name__ == "__main__":
    try:
        check_attendance()
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        print(f"Error: {e}")

        if status == 401:
            # Delete cached token so next run picks up new one
            if os.path.exists(TOKEN_FILE):
                os.remove(TOKEN_FILE)

            send_telegram(
                "🔑 *Token expired*\n\n"
                "Send a new token:\n"
                "`/token YOUR_TOKEN`\n"
                "`/authpref YOUR_PREFIX`"
            )
        else:
            send_telegram(f"🚨 *Error {status}*\n\n```\n{e}\n```")

        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        try:
            send_telegram(f"🚨 *Error*\n\n```\n{e}\n```")
        except Exception:
            pass
        sys.exit(1)
