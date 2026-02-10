import requests
import json
import math
import os
import sys
from datetime import datetime
import pytz
import config
from browser_login import browser_login

config.validate()

INDIA_TZ = pytz.timezone(config.TIMEZONE)
TOKEN_FILE = config.STATE_FILE.replace("attendance_state.json", "token.json")


def get_india_time():
    return datetime.now(INDIA_TZ)


def load_cached_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
        if data.get("token"):
            return data.get("auth_pref", ""), data["token"]
    return None, None


def save_token(auth_pref, token):
    with open(TOKEN_FILE, "w") as f:
        json.dump({"auth_pref": auth_pref, "token": token}, f)


def fetch_courses(auth_pref, token):
    headers = {"Authorization": auth_pref + token}
    resp = requests.get(config.COURSES_URL, headers=headers, timeout=config.REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()["data"]


def get_courses_with_auto_login():
    """Try CV_AUTH_TOKEN secret first, then cached token, then browser login."""

    # Priority 1: Direct token from GitHub Secret (most reliable — bypasses CAPTCHA)
    if config.CV_AUTH_TOKEN:
        try:
            print("Trying CV_AUTH_TOKEN from secret...")
            courses = fetch_courses(config.CV_AUTH_PREF, config.CV_AUTH_TOKEN)
            print("CV_AUTH_TOKEN is valid!")
            # Cache it for future use
            save_token(config.CV_AUTH_PREF, config.CV_AUTH_TOKEN)
            return courses
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            print(f"CV_AUTH_TOKEN failed (HTTP {status}). Token may have expired.")
        except Exception as e:
            print(f"CV_AUTH_TOKEN failed: {e}")

    # Priority 2: Cached token from previous login
    auth_pref, token = load_cached_token()

    if token:
        try:
            print("Trying cached token...")
            courses = fetch_courses(auth_pref, token)
            print("Cached token is valid.")
            return courses
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            print(f"Cached token failed (HTTP {status}). Refreshing via browser...")
        except Exception as e:
            print(f"Cached token failed: {e}. Refreshing via browser...")
    else:
        print("No cached token found. Logging in via browser...")

    # Priority 3: Browser login for fresh token
    auth_pref, token = browser_login()
    save_token(auth_pref, token)
    print("New token saved.")

    courses = fetch_courses(auth_pref, token)
    return courses


def send_telegram(msg):
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("Telegram not configured, skipping notification.")
        print("Message:", msg)
        return
    url = config.TELEGRAM_API.format(token=config.TELEGRAM_BOT_TOKEN)
    payload = {"chat_id": config.TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    r = requests.post(url, json=payload, timeout=15)
    print("Telegram status:", r.json().get("ok", False))


def calculate_attendance_message(course, present, total, status):
    percentage = (present / total * 100) if total > 0 else 0

    status_text = "**PRESENT**" if status == "Present" else "**ABSENT**"

    msg = f"*{course}*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"Status: {status_text}\n"
    msg += f"Attendance: `{present}/{total}` lectures\n"
    msg += f"Percentage: *{percentage:.1f}%*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

    pct = config.MIN_ATTENDANCE_PCT / 100

    if percentage < config.MIN_ATTENDANCE_PCT:
        x = math.ceil((pct * total - present) / (1 - pct))
        if x < 0:
            x = 0
        msg += "__CRITICAL ALERT__\n"
        msg += "Below minimum requirement\n"
        msg += f"*Action Required:* Attend next `{x}` lecture(s)\n"
        msg += "Missing classes could affect eligibility"
    else:
        y = math.floor(present / pct - total)
        if y < 0:
            y = 0
        msg += "__ATTENDANCE SECURE__\n"
        msg += f"Above {config.MIN_ATTENDANCE_PCT}% requirement\n"
        msg += f"*Flexibility:* Can skip up to `{y}` lecture(s)\n"
        msg += "Keep up the excellent work"

    return msg


def check_attendance():
    india_time = get_india_time()
    print(f"Checking attendance at {india_time.strftime('%Y-%m-%d %H:%M:%S IST')}...")

    courses = get_courses_with_auto_login()

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
    except Exception as e:
        print(f"Error: {e}")
        error_msg = (
            "**SYSTEM ERROR DETECTED**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Time: `{get_india_time().strftime('%d %B %Y, %I:%M %p IST')}`\n"
            f"Error Details:\n"
            f"```{str(e)}```\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "*System will retry in 6 minutes*"
        )
        try:
            send_telegram(error_msg)
        except Exception:
            pass
        sys.exit(1)
