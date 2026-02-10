import sys
import json
import time
import random
import requests
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

        # Approach 1: Target by name/formcontrolname with real keystrokes
        # From debug output: name="username" formControl=username, name="password" formControl=password
        print("Approach 1: Targeting inputs by name attribute with keyboard typing...")
        username_selectors = [
            'input[name="username"]:visible',
            'input[formcontrolname="username"]:visible',
            'input[formcontrolname="userName"]:visible',
            'input[name="userName"]:visible',
            'input[formcontrolname="rollNo"]:visible',
        ]
        password_selectors = [
            'input[name="password"]:visible',
            'input[formcontrolname="password"]:visible',
            'input[type="password"]:visible',
        ]

        for selector in username_selectors:
            el = page.locator(selector)
            if el.count() > 0:
                try:
                    el.first.click(timeout=3000)
                    time.sleep(0.2)
                    # Triple-click to select all, then clear
                    el.first.press("Control+a")
                    el.first.press("Backspace")
                    time.sleep(0.1)
                    # Type character by character — triggers Angular input events properly
                    el.first.press_sequentially(config.CV_USERNAME, delay=50)
                    time.sleep(0.3)
                    # Tab out to trigger blur/validation
                    el.first.press("Tab")
                    username_filled = True
                    print(f"  Username typed via: {selector}")
                    break
                except Exception as e:
                    print(f"  Failed with {selector}: {e}")

        for selector in password_selectors:
            el = page.locator(selector)
            if el.count() > 0:
                try:
                    el.first.click(timeout=3000)
                    time.sleep(0.2)
                    el.first.press("Control+a")
                    el.first.press("Backspace")
                    time.sleep(0.1)
                    el.first.press_sequentially(config.CV_PASSWORD, delay=50)
                    time.sleep(0.3)
                    el.first.press("Tab")
                    password_filled = True
                    print(f"  Password typed via: {selector}")
                    break
                except Exception as e:
                    print(f"  Failed with {selector}: {e}")

        # Approach 2: If Approach 1 failed, use JS to set values AND patch Angular form control
        if not username_filled or not password_filled:
            print("Approach 2: Direct Angular form control patching via JS...")
            result = page.evaluate("""(creds) => {
                let filled = {username: false, password: false};

                // Find the Angular form component and patch its reactive form
                const appLogin = document.querySelector('app-login');
                if (appLogin) {
                    // Try Angular's internal API to get the component instance
                    const ngContext = appLogin.__ngContext__;
                    // Also try ng.getComponent
                    if (typeof ng !== 'undefined' && ng.getComponent) {
                        try {
                            const comp = ng.getComponent(appLogin);
                            if (comp && comp.loginForm) {
                                comp.loginForm.patchValue({
                                    username: creds.username,
                                    password: creds.password
                                });
                                comp.loginForm.markAsDirty();
                                comp.loginForm.markAsTouched();
                                comp.loginForm.updateValueAndValidity();
                                filled.username = true;
                                filled.password = true;
                                return filled;
                            }
                        } catch(e) { console.log('ng.getComponent failed:', e); }
                    }
                }

                // Fallback: set values with proper event dispatching
                const inputs = document.querySelectorAll('input');
                for (const input of inputs) {
                    const name = (input.name || '').toLowerCase();
                    const fc = (input.getAttribute('formcontrolname') || '').toLowerCase();

                    if ((name === 'username' || fc === 'username') && !filled.username) {
                        const setter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value').set;
                        setter.call(input, creds.username);
                        input.dispatchEvent(new Event('input', {bubbles: true}));
                        input.dispatchEvent(new Event('change', {bubbles: true}));
                        input.dispatchEvent(new Event('blur', {bubbles: true}));
                        filled.username = true;
                    }
                    if ((name === 'password' || fc === 'password' || input.type === 'password') && !filled.password) {
                        const setter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value').set;
                        setter.call(input, creds.password);
                        input.dispatchEvent(new Event('input', {bubbles: true}));
                        input.dispatchEvent(new Event('change', {bubbles: true}));
                        input.dispatchEvent(new Event('blur', {bubbles: true}));
                        filled.password = true;
                    }
                }
                return filled;
            }""", {"username": config.CV_USERNAME, "password": config.CV_PASSWORD})
            username_filled = result.get("username", False)
            password_filled = result.get("password", False)
            print(f"  JS patching result: username={username_filled}, password={password_filled}")

        # Verify Angular form state after filling
        form_state = page.evaluate("""() => {
            const inputs = document.querySelectorAll('input[formcontrolname]');
            const states = [];
            for (const inp of inputs) {
                states.push({
                    name: inp.getAttribute('formcontrolname'),
                    value: inp.value ? '(has value)' : '(empty)',
                    classes: inp.className,
                    valid: inp.classList.contains('ng-valid'),
                    dirty: inp.classList.contains('ng-dirty'),
                });
            }
            // Also check if submit button is disabled
            const btn = document.querySelector('button[type="submit"]');
            return {
                inputs: states,
                submitDisabled: btn ? btn.disabled : 'no button found',
            };
        }""")
        print(f"Form state after filling: {json.dumps(form_state, indent=2)}")

        if not username_filled or not password_filled:
            print(f"ERROR: Could not fill credentials (username={username_filled}, password={password_filled})")
            _dump_page_debug(page)
            browser.close()
            sys.exit(1)

        # ── Simulate human behavior to boost reCAPTCHA v3 score ──
        print("Simulating human behavior for reCAPTCHA...")
        _simulate_human_behavior(page)

        # ── Wait for reCAPTCHA v3 to load ──
        print("Waiting for reCAPTCHA to initialize...")
        try:
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

        # ── Extract token from localStorage ──
        _try_extract_token(page, auth_result)

        # ── RETRY: If button-click login failed, try direct API call ──
        if not auth_result["token"]:
            print("Button-click login failed. Trying direct API call with fresh reCAPTCHA token...")
            _simulate_human_behavior(page)  # more human behavior before retry
            try:
                # Execute reCAPTCHA to get a fresh token
                captcha_token = page.evaluate("""() => {
                    return new Promise((resolve, reject) => {
                        if (typeof grecaptcha === 'undefined') {
                            reject('grecaptcha not found');
                            return;
                        }
                        // Find the site key from the script tag or existing config
                        const scripts = document.querySelectorAll('script[src*="recaptcha"]');
                        let siteKey = '';
                        for (const s of scripts) {
                            const match = s.src.match(/render=([\w-]+)/);
                            if (match) { siteKey = match[1]; break; }
                        }
                        if (!siteKey) {
                            // Try to get it from grecaptcha enterprise or container
                            const iframe = document.querySelector('iframe[src*="recaptcha"]');
                            if (iframe) {
                                const m = iframe.src.match(/k=([\w-]+)/);
                                if (m) siteKey = m[1];
                            }
                        }
                        if (!siteKey) { reject('No site key found'); return; }

                        grecaptcha.ready(() => {
                            grecaptcha.execute(siteKey, {action: 'login'})
                                .then(token => resolve(token))
                                .catch(err => reject(err));
                        });
                    });
                }""")
                print(f"  Got reCAPTCHA token: {captcha_token[:30]}...")

                # Read the current form values
                form_values = page.evaluate("""() => {
                    const u = document.querySelector('input[name="username"]');
                    const p = document.querySelector('input[name="password"]');
                    return {
                        username: u ? u.value : '',
                        password: p ? p.value : '',
                    };
                }""")

                # Make direct API call
                api_payload = {
                    "userName": form_values.get("username", config.CV_USERNAME),
                    "password": form_values.get("password", config.CV_PASSWORD),
                    "recaptchaToken": captcha_token,
                }
                print(f"  Calling {config.LOGIN_API} directly...")
                resp = requests.post(
                    config.LOGIN_API,
                    json=api_payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Origin": "https://kiet.cybervidya.net",
                        "Referer": "https://kiet.cybervidya.net/login",
                    },
                    timeout=30
                )
                print(f"  API response: {resp.status_code}")
                if resp.status_code == 200:
                    body = resp.json()
                    if body.get("data", {}).get("token"):
                        auth_result["token"] = body["data"]["token"]
                        auth_result["auth_pref"] = body["data"].get("auth_pref", "")
                        print("  Token captured from direct API call!")
                else:
                    print(f"  Direct API call failed: {resp.text}")
            except Exception as e:
                print(f"  Direct API call attempt failed: {e}")

        # ── Final localStorage check ──
        _try_extract_token(page, auth_result)

        # Dump debug info if login failed
        if not auth_result["token"]:
            _dump_page_debug(page)

        browser.close()

        if not auth_result["token"]:
            print("ERROR: Could not extract token after login.")
            print("Login may have failed — reCAPTCHA is scoring the bot too low.")
            print("TIP: Set CV_AUTH_TOKEN as a GitHub secret (from browser localStorage 'authenticationtoken').")
            sys.exit(1)

        return auth_result["auth_pref"], auth_result["token"]


def _simulate_human_behavior(page):
    """Simulate human-like behavior to improve reCAPTCHA v3 score."""
    try:
        vw = 1920
        vh = 1080

        # Random mouse movements across the page
        for _ in range(random.randint(3, 6)):
            x = random.randint(100, vw - 100)
            y = random.randint(100, vh - 100)
            page.mouse.move(x, y, steps=random.randint(5, 15))
            time.sleep(random.uniform(0.1, 0.3))

        # Scroll down and up
        page.mouse.wheel(0, random.randint(100, 300))
        time.sleep(random.uniform(0.3, 0.7))
        page.mouse.wheel(0, -random.randint(50, 150))
        time.sleep(random.uniform(0.2, 0.5))

        # Click on a non-interactive area (body)
        page.mouse.click(random.randint(500, 800), random.randint(200, 400))
        time.sleep(random.uniform(0.2, 0.4))

        # Move mouse to login button area and hover
        btn = page.locator('button[type="submit"]:visible')
        if btn.count() > 0:
            box = btn.first.bounding_box()
            if box:
                page.mouse.move(
                    box["x"] + box["width"] / 2,
                    box["y"] + box["height"] / 2,
                    steps=random.randint(8, 20)
                )
                time.sleep(random.uniform(0.3, 0.6))

        # Brief pause to let reCAPTCHA observe
        time.sleep(random.uniform(1.0, 2.0))
        print("  Human behavior simulation complete.")
    except Exception as e:
        print(f"  Human behavior simulation error (non-fatal): {e}")


def _try_extract_token(page, auth_result):
    """Try to extract auth token from page localStorage."""
    if auth_result["token"]:
        return
    try:
        token = page.evaluate("() => localStorage.getItem('authenticationtoken')")
        if token:
            auth_result["token"] = token.strip('"')
            print("Token found in localStorage!")

        auth_pref = page.evaluate("() => localStorage.getItem('auth_pref')")
        if auth_pref:
            auth_result["auth_pref"] = auth_pref.strip('"')

        # Try other common storage keys
        if not auth_result["token"]:
            for key in ["token", "jwt", "access_token", "auth_token"]:
                val = page.evaluate(f"() => localStorage.getItem('{key}')")
                if val:
                    auth_result["token"] = val.strip('"')
                    print(f"Token found in localStorage key '{key}'!")
                    break
    except Exception:
        pass


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
