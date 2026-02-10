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


def get_india_time():
    return datetime.now(INDIA_TZ)


def fetch_courses():
    headers = {"Authorization": config.CV_AUTH_PREF + config.CV_AUTH_TOKEN}
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
    status_text = "**PRESENT**" if status == "Present" else "**ABSENT**"

    msg = f"*{course}*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"Status: {status_text}\n"
    msg += f"Attendance: `{present}/{total}` lectures\n"
    msg += f"Percentage: *{percentage:.1f}%*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

    pct = config.MIN_ATTENDANCE_PCT / 100

    if percentage < config.MIN_ATTENDANCE_PCT:
        x = max(0, math.ceil((pct * total - present) / (1 - pct)))
        msg += "__CRITICAL ALERT__\n"
        msg += "Below minimum requirement\n"
        msg += f"*Action Required:* Attend next `{x}` lecture(s)\n"
        msg += "Missing classes could affect eligibility"
    else:
        y = max(0, math.floor(present / pct - total))
        msg += "__ATTENDANCE SECURE__\n"
        msg += f"Above {config.MIN_ATTENDANCE_PCT}% requirement\n"
        msg += f"*Flexibility:* Can skip up to `{y}` lecture(s)\n"
        msg += "Keep up the excellent work"

    return msg


def check_attendance():
    india_time = get_india_time()
    print(f"Checking attendance at {india_time.strftime('%Y-%m-%d %H:%M:%S IST')}...")

    courses = fetch_courses()

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
        if status == 401:
            print("ERROR: Token expired! Update CV_AUTH_TOKEN in GitHub Secrets.")
        print(f"Error: {e}")
        error_msg = (
            "**SYSTEM ERROR DETECTED**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Time: `{get_india_time().strftime('%d %B %Y, %I:%M %p IST')}`\n"
            f"Error Details:\n"
            f"```{str(e)}```\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "*Update CV_AUTH_TOKEN if token expired*"
        )
        try:
            send_telegram(error_msg)
        except Exception:
            pass
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        try:
            send_telegram(f"**ERROR:** `{e}`")
        except Exception:
            pass
        sys.exit(1)
