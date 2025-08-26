import requests
import json
import math
import os
import schedule
import time
from datetime import datetime
import pytz

LOGIN_URL = "https://kiet.cybervidya.net/api/auth/login"
COURSES_URL = "https://kiet.cybervidya.net/api/student/dashboard/registered-courses"

USERNAME = "your_username_here"
PASSWORD = "your_password_here"

BOT_TOKEN = "your_bot_token_here"
CHAT_ID = "your_chat_id_here"

STATE_FILE = "attendance_state.json"

INDIA_TZ = pytz.timezone('Asia/Kolkata')


def get_india_time():
    return datetime.now(INDIA_TZ)


def login():
    payload = {"userName": USERNAME, "password": PASSWORD}
    resp = requests.post(LOGIN_URL, json=payload)
    resp.raise_for_status()
    data = resp.json()["data"]
    return data["auth_pref"], data["token"]


def fetch_courses(auth_pref, token):
    headers = {"Authorization": auth_pref + token}
    resp = requests.get(COURSES_URL, headers=headers)
    resp.raise_for_status()
    return resp.json()["data"]


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    r = requests.post(url, json=payload)
    print("Telegram status:", r.json())


def calculate_attendance_message(course, present, total, status):
    percentage = (present / total * 100) if total > 0 else 0
    
    status_text = "**PRESENT**" if status == "Present" else "**ABSENT**"
    
    msg = f"*{course}*\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"Status: {status_text}\n"
    msg += f"Attendance: `{present}/{total}` lectures\n"
    msg += f"Percentage: *{percentage:.1f}%*\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

    if percentage < 75:
        x = math.ceil((0.75 * total - present) / 0.25)
        if x < 0: 
            x = 0
        msg += f"__CRITICAL ALERT__\n"
        msg += f"Below minimum requirement\n"
        msg += f"*Action Required:* Attend next `{x}` lecture(s)\n"
        msg += f"Missing classes could affect eligibility"
    else:
        y = math.floor(present / 0.75 - total)
        if y < 0: 
            y = 0
        msg += f"__ATTENDANCE SECURE__\n"
        msg += f"Above 75% requirement\n"
        msg += f"*Flexibility:* Can skip up to `{y}` lecture(s)\n"
        msg += f"Keep up the excellent work"
    
    return msg


def check_attendance():
    try:
        india_time = get_india_time()
        print(f"Checking attendance at {india_time.strftime('%Y-%m-%d %H:%M:%S IST')}...")
        
        auth_pref, token = login()

        courses = fetch_courses(auth_pref, token)

        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
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

        with open(STATE_FILE, "w") as f:
            json.dump(new_state, f)
        
        if not changes_found:
            print("No attendance changes detected.")
        else:
            print("Attendance changes found and notifications sent.")
            
    except Exception as e:
        print(f"Error checking attendance: {e}")
        error_msg = (
            "**SYSTEM ERROR DETECTED**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Time: `{get_india_time().strftime('%d %B %Y, %I:%M %p IST')}`\n"
            f"Error Details:\n"
            f"```{str(e)}```\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "*System will retry automatically*"
        )
        try:
            send_telegram(error_msg)
        except:
            pass


def run_scheduler():
    schedule.every(30).minutes.do(check_attendance)
    
    print("Attendance checker started!")
    print(f"Current Indian time: {get_india_time().strftime('%Y-%m-%d %H:%M:%S IST')}")
    print("Will check attendance every 30 minutes until 5:30 PM IST...")
    
    startup_msg = (
        "ATTENDANCE MONITOR ACTIVATED\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Started: `{get_india_time().strftime('%d %B %Y, %I:%M %p IST')}`\n"
        f"Check Interval: __Every 30 Minutes__\n"
        f"Auto Stop: *5:30 PM IST Daily*\n"
        f"Timezone: *Indian Standard Time*\n"
        f"Bot Status: **ONLINE**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "*Ready to track your academic progress*"
    )
    try:
        send_telegram(startup_msg)
    except Exception as e:
        print(f"Failed to send startup notification: {e}")
    
    check_attendance()
    
    while True:
        try:
            current_time = get_india_time()
            
            if current_time.hour >= 17 and current_time.minute >= 30:
                print(f"\n Reached 5:30 PM IST. Stopping attendance checker...")
                auto_shutdown_msg = (
                    "ATTENDANCE MONITOR AUTO-SHUTDOWN\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"Stopped: `{current_time.strftime('%d %B %Y, %I:%M %p IST')}`\n"
                    f"Status: __OFFLINE__\n"
                    f"Reason: *Scheduled Auto-Stop at 5:30 PM*\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "*Monitor will resume tomorrow*"
                )
                try:
                    send_telegram(auto_shutdown_msg)
                except:
                    pass
                break
            
            schedule.run_pending()
            time.sleep(60)
        except KeyboardInterrupt:
            print("\n Attendance checker stopped by user.")
            shutdown_msg = (
                "ATTENDANCE MONITOR DEACTIVATED\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Stopped: `{get_india_time().strftime('%d %B %Y, %I:%M %p IST')}`\n"
                f"Status: __OFFLINE__\n"
                f"Reason: *Manual Shutdown*\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "*Thanks for using Attendance Monitor*"
            )
            try:
                send_telegram(shutdown_msg)
            except:
                pass
            break
        except Exception as e:
            print(f"Scheduler error: {e}")
            time.sleep(300)


if __name__ == "__main__":
    run_scheduler()