# CyberVidya Attendance Bot

Automated attendance tracker for CyberVidya. Runs every 6 minutes via GitHub Actions, checks for attendance changes, and sends Telegram notifications.

## Setup

### 1. Get Your Auth Token

1. Login to [kiet.cybervidya.net](https://kiet.cybervidya.net/login) in your browser
2. Open DevTools (`F12`) → **Application** → **Local Storage** → `https://kiet.cybervidya.net`
3. Copy the values of `authenticationtoken` and `auth_prefix`

### 2. Set GitHub Secrets

Go to **repo → Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `CV_AUTH_TOKEN` | Your `authenticationtoken` from localStorage |
| `CV_AUTH_PREF` | Your `auth_prefix` from localStorage |
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID from [@userinfobot](https://t.me/userinfobot) |

### 3. Enable Actions

Go to **repo → Actions** and enable the workflow. It runs every 6 minutes automatically.

## How It Works

- Fetches your registered courses from the CyberVidya API
- Compares with previous state to detect changes
- Sends a Telegram notification with attendance status, percentage, and skip/attend calculations
- Alerts if you're below 75% attendance

## Token Expired?

If you get a 401 error, your token has expired. Repeat step 1 to get a fresh token and update the `CV_AUTH_TOKEN` secret.
