import sys
import json
import time
from playwright.sync_api import sync_playwright
import config


def browser_login():
    """Open real browser, login through reCAPTCHA, extract token."""
    print("Launching browser for login...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )
        page = context.new_page()

        # Navigate to login page
        print(f"Opening {config.LOGIN_PAGE}...")
        page.goto(config.LOGIN_PAGE, wait_until="networkidle", timeout=60000)
        time.sleep(3)

        # Fill in credentials
        print("Filling credentials...")
        username_field = page.locator('input[type="text"], input[name="userName"], input[placeholder*="user" i], input[placeholder*="roll" i], input[placeholder*="id" i]').first
        password_field = page.locator('input[type="password"]').first

        username_field.click()
        time.sleep(0.5)
        username_field.fill(config.CV_USERNAME)
        time.sleep(0.8)

        password_field.click()
        time.sleep(0.5)
        password_field.fill(config.CV_PASSWORD)
        time.sleep(1)

        # Wait for reCAPTCHA v3 to load and score
        print("Waiting for reCAPTCHA...")
        time.sleep(3)

        # Click login button
        print("Clicking login...")
        login_btn = page.locator('button[type="submit"], button:has-text("Login"), button:has-text("Sign In"), button:has-text("LOG IN")').first
        login_btn.click()

        # Wait for login to complete and redirect
        print("Waiting for login response...")
        try:
            page.wait_for_url("**/home**", timeout=30000)
        except Exception:
            # Maybe it doesn't redirect to /home, wait for network idle instead
            time.sleep(5)

        # Extract token from localStorage
        token = page.evaluate("() => localStorage.getItem('authenticationtoken')")
        if token:
            # Strip quotes if present
            token = token.strip('"')
            print("Token obtained successfully!")
        else:
            # Try alternative storage keys
            all_storage = page.evaluate("""() => {
                let result = {};
                for (let i = 0; i < localStorage.length; i++) {
                    let key = localStorage.key(i);
                    if (key.toLowerCase().includes('token') || key.toLowerCase().includes('auth')) {
                        result[key] = localStorage.getItem(key);
                    }
                }
                return result;
            }""")
            print(f"Available auth keys in localStorage: {json.dumps(all_storage, indent=2)}")

            if all_storage:
                # Use the first token-like value found
                for key, val in all_storage.items():
                    if val and len(val) > 20:
                        token = val.strip('"')
                        print(f"Using token from key: {key}")
                        break

        # Try to get auth_pref too
        auth_pref = page.evaluate("() => localStorage.getItem('auth_pref')") or ""
        if auth_pref:
            auth_pref = auth_pref.strip('"')

        browser.close()

        if not token:
            print("ERROR: Could not extract token after login.")
            print("Login may have failed — check credentials or CAPTCHA.")
            sys.exit(1)

        return auth_pref, token


if __name__ == "__main__":
    if not config.CV_USERNAME or not config.CV_PASSWORD:
        print("ERROR: CV_USERNAME and CV_PASSWORD required for browser login.")
        sys.exit(1)

    auth_pref, token = browser_login()

    # Write token to file so attendance.py can pick it up
    token_data = {"auth_pref": auth_pref, "token": token}
    token_file = config.STATE_FILE.replace("attendance_state.json", "token.json")
    with open(token_file, "w") as f:
        json.dump(token_data, f)

    print(f"Token saved to {token_file}")
