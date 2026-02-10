# Attendance Checker — GitHub Actions

Automated attendance tracker for CyberVidya (KIET) that runs 24/7 via GitHub Actions and sends Telegram notifications when your attendance changes.

## Project Structure

```
github-actions-attendance/
├── config.py            # All URLs, secrets, settings in one place
├── attendance.py        # Main attendance checking logic
├── requirements.txt     # Python dependencies
└── README.md            # You are here

.github/workflows/
└── attendance-checker.yml   # Runs every 6 minutes
```

## Setup

### 1. Push this repo to GitHub (public)

```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 2. Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret | Required | Description |
|--------|----------|-------------|
| `CV_USERNAME` | Mode 1 | Your CyberVidya username |
| `CV_PASSWORD` | Mode 1 | Your CyberVidya password |
| `CV_AUTH_TOKEN` | Mode 2 | Auth token from the Chrome extension |
| `CV_AUTH_PREF` | Optional | Auth prefix (defaults to `Bearer `) |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Yes | Your chat ID from [@userinfobot](https://t.me/userinfobot) |

**Mode 1** — Direct API login with username/password. Works if the API doesn't require CAPTCHA.

**Mode 2** — Use a pre-authenticated token obtained via the Kiet Auth Bridge Chrome extension. Use this if the API login is blocked by CAPTCHA.

### 3. Enable Actions

Go to the **Actions** tab in your repo. If prompted, enable workflows. The cron job will start automatically.

You can also trigger a run manually: **Actions → Attendance Checker → Run workflow**.

## How It Works

1. GitHub Actions triggers every **6 minutes**, 24/7
2. Script authenticates with CyberVidya (token or username/password)
3. Fetches all registered courses and current attendance
4. Compares with the previous cached state
5. If attendance changed → sends a Telegram notification with:
   - Present/Absent status
   - Current attendance percentage
   - How many lectures you can skip (or need to attend)
6. If nothing changed → silently exits

## Telegram Notifications

**When marked present:**
```
Computer Networks
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Status: PRESENT
Attendance: 18/24 lectures
Percentage: 75.0%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ATTENDANCE SECURE
Above 75% requirement
Flexibility: Can skip up to 2 lecture(s)
```

**When marked absent:**
```
Data Structures
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Status: ABSENT
Attendance: 10/16 lectures
Percentage: 62.5%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL ALERT
Below minimum requirement
Action Required: Attend next 2 lecture(s)
```

## Configuration

All settings live in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `TIMEZONE` | `Asia/Kolkata` | Timezone for timestamps |
| `MIN_ATTENDANCE_PCT` | `75` | Minimum attendance percentage |
| `REQUEST_TIMEOUT` | `30` | API request timeout in seconds |

## Troubleshooting

**Actions not running?**
- Make sure the repo is public and Actions are enabled
- Check the Actions tab for error logs

**Getting auth errors?**
- If using Mode 1: the API may now require CAPTCHA — switch to Mode 2
- If using Mode 2: tokens expire — get a fresh one from the Chrome extension and update the `CV_AUTH_TOKEN` secret

**No Telegram messages?**
- Verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are correct
- Make sure you've started a chat with your bot first (send it `/start`)

## Chrome Extension (for getting tokens)

The included Chrome extension (`content.js` + `manifest.json` in the root folder) extracts your auth token after you log in manually on `kiet.cybervidya.net`. Use this to get the `CV_AUTH_TOKEN` value if the API blocks direct login.

## License

[MIT](../LICENSE)
