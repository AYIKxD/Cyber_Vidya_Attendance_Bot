#  Cyber Vidya Attendance Monitor

An automated attendance tracking system for Cyber Vidya students that monitors your attendance every 30 minutes and sends real-time updates via Telegram.

##  Features

- **Automated Monitoring**: Checks attendance every 30 minutes
- **Smart Scheduling**: Automatically stops at 5:30 PM IST daily
- **Telegram Notifications**: Instant updates when attendance changes
- **Attendance Analytics**: Shows required classes to maintain 75% attendance
- **Professional Reporting**: Clean, emoji-free status messages
- **Error Handling**: Robust error management with automatic retries

##  Prerequisites

- Python 3.6 or higher
- Cyber Vidya student portal credentials
- Telegram bot token and chat ID

##  Installation

### Windows

1. **Install Python** (if not already installed):
   - Download from [python.org](https://www.python.org/downloads/)
   - Make sure to check "Add Python to PATH" during installation

2. **Open Command Prompt** and install required packages:
   ```cmd
   pip install requests schedule pytz
   ```

3. **Verify installation**:
   ```cmd
   python --version
   pip list
   ```

### Linux (Ubuntu/Debian)

1. **Update package list**:
   ```bash
   sudo apt update
   ```

2. **Install Python and pip** (if not already installed):
   ```bash
   sudo apt install python3 python3-pip
   ```

3. **Install required packages**:
   ```bash
   pip3 install requests schedule pytz
   ```

   **Alternative method using apt**:
   ```bash
   sudo apt install python3-requests python3-tz
   pip3 install schedule
   ```

4. **For externally managed environment error**:
   ```bash
   python3 -m venv attendance_env
   source attendance_env/bin/activate
   pip install requests schedule pytz
   ```

### Other Linux Distributions

**CentOS/RHEL/Fedora**:
```bash
sudo yum install python3 python3-pip  # CentOS/RHEL
sudo dnf install python3 python3-pip  # Fedora
pip3 install requests schedule pytz
```

**Arch Linux**:
```bash
sudo pacman -S python python-pip
pip install requests schedule pytz
```

##  Configuration

1. **Clone or download** this repository
2. **Open the script** in your favorite text editor
3. **Replace the placeholder values** with your actual credentials:

```python
# Hard-coded credentials - Replace with your actual values
USERNAME = "your_cybervidya_username"
PASSWORD = "your_cybervidya_password"

# Telegram bot details - Replace with your actual values
BOT_TOKEN = "your_bot_token_from_botfather"
CHAT_ID = "your_telegram_chat_id"
```

### Getting Telegram Bot Token and Chat ID

1. **Create a bot**:
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Send `/newbot` and follow instructions
   - Copy the bot token

2. **Get your Chat ID**:
   - Message [@userinfobot](https://t.me/userinfobot)
   - It will reply with your Chat ID

##  Usage

### Windows
```cmd
python attendance_checker.py
```

### Linux
```bash
python3 attendance_checker.py
```

### Running in Background (Linux)
```bash
# Using nohup
nohup python3 attendance_checker.py &

# Using screen
screen -S attendance
python3 attendance_checker.py
# Press Ctrl+A then D to detach
```

##  Schedule

- **Check Interval**: Every 30 minutes
- **Auto-Stop Time**: 5:30 PM IST daily
- **Timezone**: Indian Standard Time (UTC+5:30)

##  Message Examples

### Startup Notification
```
ATTENDANCE MONITOR ACTIVATED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Started: 25 August 2025, 02:00 PM IST
Check Interval: Every 30 Minutes
Auto Stop: 5:30 PM IST Daily
Timezone: Indian Standard Time
Bot Status: ONLINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ready to track your academic progress
```

### Attendance Update
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
Keep up the excellent work
```

## 🔧 Troubleshooting

### Common Issues

1. **Module not found error**:
   ```bash
   pip install --user requests schedule pytz
   ```

2. **Permission denied (Linux)**:
   ```bash
   pip3 install --user requests schedule pytz
   ```

3. **Python command not recognized (Windows)**:
   - Add Python to system PATH
   - Use `py` instead of `python`

4. **SSL Certificate errors**:
   ```bash
   pip install --trusted-host pypi.org --trusted-host pypi.python.org requests schedule pytz
   ```

### Dependencies

| Package | Purpose |
|---------|---------|
| `requests` | HTTP requests to KIET API and Telegram |
| `schedule` | Task scheduling for 30-minute intervals |
| `pytz` | Indian timezone support |

##  Contributing

Feel free to open issues or submit pull requests to improve this project!

##  License

This project is open source and available under the [MIT License](LICENSE).

##  Credits

Special thanks to [Harshit](https://github.com/Harshit-Patel01) for inspiration and contributions to this project.

##  Disclaimer

- This tool is for educational purposes only
- Use responsibly and in accordance with Cyber Vidya's terms of service
- Keep your credentials secure and never share them publicly
- The developers are not responsible for any misuse of this tool

---

**Made with ❤️ for AYIKxD**
