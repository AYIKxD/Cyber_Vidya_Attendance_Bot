import sys
import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
import config


def browser_login():
    """Open real browser, login through the Angular form, extract token."""
    print("Launching browser for login...")

    auth_result = {"auth_pref": "", "token": ""}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--window-size=1920,1080",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
        )

        # ── Stealth: inject anti-detection scripts before any page loads ──
        context.add_init_script("""
            // Remove webdriver flag
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

            // Override plugins to look like a real browser
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });

            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });

            // Override chrome object
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {},
            };

            // Override permissions query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters);

            // Remove automation-related properties
            delete navigator.__proto__.webdriver;
        """)

        page = context.new_page()

        # ── Intercept the login API response to grab the token directly ──
        def handle_response(response):
            if "auth" in response.url and "login" in response.url:
                try:
                    body = response.json()
                    if response.status == 200:
                        if body.get("data", {}).get("token"):
                            auth_result["token"] = body["data"]["token"]
                            auth_result["auth_pref"] = body["data"].get("auth_pref", "")
                            print("Token captured from API response!")
                    else:
                        print(f"Login API responded {response.status}: {json.dumps(body)}")
                except Exception as e:
                    print(f"Login API responded {response.status} (non-JSON): {e}")

        page.on("response", handle_response)

        # ── Navigate to login page ──
        print(f"Opening {config.LOGIN_PAGE}...")
        page.goto(config.LOGIN_PAGE, wait_until="networkidle", timeout=60000)

        # Wait for Angular to fully bootstrap and render
        print("Waiting for Angular app to load...")
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        # Wait for the app-login component or the loginPage-section to appear
        try:
            page.wait_for_selector("app-login, .loginPage-section, section#loading",
                                   state="attached", timeout=15000)
            print("Angular login component detected.")
        except PwTimeout:
            print("Warning: Angular login component not found within 15s, proceeding anyway...")

        time.sleep(2)  # extra buffer for Angular rendering

        # ── Debug: dump all inputs on page ──
        inputs_info = page.evaluate("""() => {
            const inputs = document.querySelectorAll('input');
            return Array.from(inputs).map((el, i) => ({
                index: i,
                type: el.type,
                name: el.name,
                placeholder: el.placeholder,
                id: el.id,
                classes: el.className,
                visible: el.offsetParent !== null && !el.classList.contains('hide-option'),
                tag: el.tagName,
                formControl: el.getAttribute('formcontrolname') || '',
                rect: el.getBoundingClientRect(),
            }));
        }""")
        print("Found inputs on page:")
        for inp in inputs_info:
            print(f"  [{inp['index']}] type={inp['type']} name={inp['name']} "
                  f"placeholder='{inp['placeholder']}' visible={inp['visible']} "
                  f"class={inp['classes']} formControl={inp['formControl']}")

        # ── Dismiss any blocking modals (OTP modal, etc.) ──
        _dismiss_modals(page)

        # ── Fill credentials ──
        username_filled = False
        password_filled = False

        # Approach 1: Use :visible pseudo-selector (Playwright-specific)
        print("Approach 1: Looking for visible inputs...")
        try:
            visible_text = page.locator(
                'input[type="text"]:visible, input[type="email"]:visible, '
                'input[type="tel"]:visible, input[type="number"]:visible'
            )
            visible_pass = page.locator('input[type="password"]:visible')

            text_count = visible_text.count()
            pass_count = visible_pass.count()
            print(f"  Visible text inputs: {text_count}, password inputs: {pass_count}")

            if text_count > 0 and pass_count > 0:
                visible_text.first.click(timeout=5000)
                time.sleep(0.3)
                visible_text.first.fill(config.CV_USERNAME)
                username_filled = True
                print("  Username filled via visible text input.")

                time.sleep(0.5)
                visible_pass.first.click(timeout=5000)
                time.sleep(0.3)
                visible_pass.first.fill(config.CV_PASSWORD)
                password_filled = True
                print("  Password filled via visible password input.")
        except Exception as e:
            print(f"  Approach 1 failed: {e}")

        # Approach 2: Target Angular formcontrolname attributes directly
        if not username_filled or not password_filled:
            print("Approach 2: Trying formcontrolname selectors...")
            if not username_filled:
                for selector in [
                    'input[formcontrolname="userName"]',
                    'input[formcontrolname="username"]',
                    'input[formcontrolname="rollNo"]',
                    'input[formcontrolname="userId"]',
                    'input[formcontrolname="email"]',
                ]:
                    el = page.locator(selector)
                    if el.count() > 0:
                        # Remove hide-option class and force-fill
                        el.first.evaluate("el => { el.classList.remove('hide-option'); el.style.display = 'block'; el.style.visibility = 'visible'; }")
                        time.sleep(0.2)
                        el.first.fill(config.CV_USERNAME, force=True)
                        username_filled = True
                        print(f"  Username filled via {selector}")
                        break

            if not password_filled:
                for selector in [
                    'input[formcontrolname="password"]',
                    'input[formcontrolname="pwd"]',
                ]:
                    el = page.locator(selector)
                    if el.count() > 0:
                        el.first.evaluate("el => { el.classList.remove('hide-option'); el.style.display = 'block'; el.style.visibility = 'visible'; }")
                        time.sleep(0.2)
                        el.first.fill(config.CV_PASSWORD, force=True)
                        password_filled = True
                        print(f"  Password filled via {selector}")
                        break

        # Approach 3: JavaScript injection into Angular reactive form
        if not username_filled or not password_filled:
            print("Approach 3: JavaScript injection into Angular form...")
            result = page.evaluate("""(creds) => {
                let filled = {username: false, password: false};
                const inputs = document.querySelectorAll('input');
                inputs.forEach(input => {
                    const fc = (input.getAttribute('formcontrolname') || '').toLowerCase();
                    const type = input.type;
                    const name = (input.name || '').toLowerCase();

                    const isUsername = (
                        fc.includes('user') || fc.includes('roll') || fc.includes('email') ||
                        name.includes('user') || name.includes('roll') ||
                        (type === 'text' && !fc.includes('password'))
                    );
                    const isPassword = (
                        type === 'password' || fc.includes('password') || fc.includes('pwd')
                    );

                    if (isUsername && !filled.username) {
                        // Use Angular's NgZone to properly update
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        ).set;
                        nativeInputValueSetter.call(input, creds.username);
                        input.dispatchEvent(new Event('input', {bubbles: true}));
                        input.dispatchEvent(new Event('change', {bubbles: true}));
                        input.dispatchEvent(new Event('blur', {bubbles: true}));
                        filled.username = true;
                    }
                    if (isPassword && !filled.password) {
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        ).set;
                        nativeInputValueSetter.call(input, creds.password);
                        input.dispatchEvent(new Event('input', {bubbles: true}));
                        input.dispatchEvent(new Event('change', {bubbles: true}));
                        input.dispatchEvent(new Event('blur', {bubbles: true}));
                        filled.password = true;
                    }
                });
                return filled;
            }""", {"username": config.CV_USERNAME, "password": config.CV_PASSWORD})
            username_filled = result.get("username", False)
            password_filled = result.get("password", False)
            print(f"  JS injection result: username={username_filled}, password={password_filled}")

        if not username_filled or not password_filled:
            print(f"ERROR: Could not fill credentials (username={username_filled}, password={password_filled})")
            _dump_page_debug(page)
            browser.close()
            sys.exit(1)

        time.sleep(1)

        # ── Wait for reCAPTCHA v3 to load ──
        print("Waiting for reCAPTCHA to initialize...")
        try:
            # reCAPTCHA v3 loads via an iframe from google.com/recaptcha
            page.wait_for_selector('iframe[src*="recaptcha"]', state="attached", timeout=10000)
            print("  reCAPTCHA iframe detected, waiting for it to settle...")
            time.sleep(3)
        except PwTimeout:
            print("  No reCAPTCHA iframe found (may not be on this page), proceeding...")
            time.sleep(2)

        # ── Click login button ──
        print("Clicking login...")
        login_clicked = False

        # Try visible submit/login buttons
        for btn_selector in [
            'button[type="submit"]:visible',
            'button:visible:has-text("Login")',
            'button:visible:has-text("Sign In")',
            'button:visible:has-text("LOG IN")',
            'button:visible:has-text("Submit")',
        ]:
            btn = page.locator(btn_selector)
            if btn.count() > 0:
                try:
                    btn.first.click(timeout=5000)
                    login_clicked = True
                    print(f"  Login button clicked via: {btn_selector}")
                    break
                except Exception as e:
                    print(f"  Button click failed for {btn_selector}: {e}")

        # Fallback: JS click on any login/submit button
        if not login_clicked:
            print("  Fallback: JS clicking login button...")
            page.evaluate("""() => {
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    const text = btn.textContent.toLowerCase();
                    if (text.includes('login') || text.includes('sign in') || text.includes('submit')) {
                        btn.click();
                        return true;
                    }
                }
                // Also try submitting the form directly
                const form = document.querySelector('form');
                if (form) { form.submit(); return true; }
                return false;
            }""")

        # ── Wait for login API response or navigation ──
        print("Waiting for login response...")
        # Poll for token or URL change (max 15 seconds)
        for attempt in range(15):
            time.sleep(1)
            if auth_result["token"]:
                print(f"  Token received after {attempt + 1}s!")
                break
            current_url = page.url
            if "/login" not in current_url:
                print(f"  Navigated away from login to: {current_url}")
                time.sleep(2)  # let localStorage populate
                break
        else:
            print("  No token or navigation after 15s.")

        # ── Extract token ──
        if not auth_result["token"]:
            # Check localStorage for token
            token = page.evaluate("() => localStorage.getItem('authenticationtoken')")
            if token:
                auth_result["token"] = token.strip('"')
                print("Token found in localStorage!")

            auth_pref = page.evaluate("() => localStorage.getItem('auth_pref')")
            if auth_pref:
                auth_result["auth_pref"] = auth_pref.strip('"')

        # Still no token? Try other common storage keys
        if not auth_result["token"]:
            for key in ["token", "jwt", "access_token", "auth_token"]:
                val = page.evaluate(f"() => localStorage.getItem('{key}')")
                if val:
                    auth_result["token"] = val.strip('"')
                    print(f"Token found in localStorage key '{key}'!")
                    break

        # Dump debug info if login failed
        if not auth_result["token"]:
            _dump_page_debug(page)

        browser.close()

        if not auth_result["token"]:
            print("ERROR: Could not extract token after login.")
            print("Login may have failed — check credentials or CAPTCHA blocking.")
            sys.exit(1)

        return auth_result["auth_pref"], auth_result["token"]


def _dismiss_modals(page):
    """Dismiss any modal dialogs that might block the login form."""
    try:
        result = page.evaluate("""() => {
            let dismissed = [];
            // Hide any Bootstrap modals
            const modals = document.querySelectorAll('.modal, .modal-backdrop');
            modals.forEach(m => {
                m.style.display = 'none';
                m.classList.remove('show');
                dismissed.push(m.id || m.className);
            });
            // Remove modal-open from body
            document.body.classList.remove('modal-open');
            document.body.style.overflow = 'auto';

            // Specifically handle the OTP modal
            const otpModal = document.getElementById('generate-otp');
            if (otpModal) {
                otpModal.style.display = 'none';
                otpModal.setAttribute('aria-hidden', 'true');
                dismissed.push('generate-otp');
            }

            // Also unhide any hidden inputs in the login form
            const hiddenInputs = document.querySelectorAll('input.hide-option');
            hiddenInputs.forEach(inp => {
                inp.classList.remove('hide-option');
                inp.style.display = '';
                inp.style.visibility = 'visible';
                dismissed.push('unhid: ' + (inp.getAttribute('formcontrolname') || inp.type));
            });

            return dismissed;
        }""")
        if result:
            print(f"Dismissed modals/unhid inputs: {result}")
    except Exception as e:
        print(f"Modal dismissal had an issue (non-fatal): {e}")


def _dump_page_debug(page):
    """Dump page state for debugging failed login."""
    try:
        current_url = page.url
        print(f"Current URL after login attempt: {current_url}")

        all_storage = page.evaluate("""() => {
            let result = {};
            for (let i = 0; i < localStorage.length; i++) {
                let key = localStorage.key(i);
                result[key] = localStorage.getItem(key);
            }
            return result;
        }""")
        print(f"localStorage contents: {json.dumps(all_storage, indent=2)}")
    except Exception as e:
        print(f"Debug dump failed: {e}")


if __name__ == "__main__":
    if not config.CV_USERNAME or not config.CV_PASSWORD:
        print("ERROR: CV_USERNAME and CV_PASSWORD required.")
        sys.exit(1)

    auth_pref, token = browser_login()
    print(f"Auth prefix: '{auth_pref}'")
    print(f"Token: {token[:20]}...")
