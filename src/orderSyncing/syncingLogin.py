import os
import time
import traceback
from datetime import datetime

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException

load_dotenv()

LOGIN_URL = os.getenv("SUPPLIER_LOGIN_URL")

def save_debug(driver, name):
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

```
screenshot_path = f"/tmp/{name}_{timestamp}.png"
html_path = f"/tmp/{name}_{timestamp}.html"

print("\n========== DEBUG INFO ==========")

try:
    print("DEBUG URL:", driver.current_url)
    print("DEBUG TITLE:", driver.title)
except Exception as e:
    print("Unable to get URL/title:", repr(e))

try:
    driver.save_screenshot(screenshot_path)
    print(f"DEBUG SCREENSHOT SAVED: {screenshot_path}")
except Exception as e:
    print("Screenshot error:", repr(e))

try:
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"DEBUG PAGE SOURCE SAVED: {html_path}")
except Exception as e:
    print("Page source save error:", repr(e))

try:
    logs = driver.get_log("browser")
    print("\n========== BROWSER LOGS ==========")
    for log in logs:
        print(log)
except Exception as e:
    print("Could not get browser logs:", repr(e))

print("\n========== END DEBUG ==========\n")
```

def find_visible_element(driver, xpath):
elements = driver.find_elements(By.XPATH, xpath)

```
for element in elements:
    try:
        if element.is_displayed():
            return element
    except Exception:
        continue

return None
```

def login():
driver = None

```
try:
    print("========== STARTING SELENIUM ==========")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")

    print("Connecting to Selenium server...")

    driver = webdriver.Remote(
        command_executor="http://localhost:4444/wd/hub",
        options=options,
    )

    print("Selenium session created successfully.")
    print("Session ID:", driver.session_id)

    driver.set_page_load_timeout(60)
    wait = WebDriverWait(driver, 30)

    print("Opening login URL:", LOGIN_URL)
    driver.get(LOGIN_URL)

    print("Page opened successfully.")
    print("Current URL:", driver.current_url)
    print("Page title:", driver.title)

    if "noroute" in driver.current_url:
        raise Exception(
            f"Invalid login URL or redirect: {driver.current_url}"
        )

    # ========================================
    # COOKIE POPUP
    # ========================================
    try:
        print("Checking cookie popup...")

        cookie = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//button[contains(.,'OK') "
                    "or contains(.,'Alleen') "
                    "or contains(@class, 'coi-banner__accept')]",
                )
            )
        )

        print("Cookie popup found.")
        driver.execute_script("arguments[0].click();", cookie)
        print("Cookie popup accepted.")
        time.sleep(1)

    except TimeoutException:
        print("No cookie popup found.")

    except Exception as e:
        print("Cookie popup error:", repr(e))

    # ========================================
    # KLAVIYO POPUP
    # ========================================
    try:
        popups = driver.find_elements(
            By.XPATH,
            "//button[contains(@class, 'klaviyo-close-form')]"
        )

        for popup in popups:
            try:
                if popup.is_displayed():
                    print("Closing Klaviyo popup...")
                    driver.execute_script(
                        "arguments[0].click();",
                        popup
                    )
                    time.sleep(1)

            except Exception as e:
                print("Popup close error:", repr(e))

    except Exception as e:
        print("Popup search error:", repr(e))

    # ========================================
    # ENV VARIABLES
    # ========================================
    email_val = os.getenv("SUPPLIER_EMAIL")
    password_val = os.getenv("SUPPLIER_PASSWORD")

    if not email_val:
        raise Exception("SUPPLIER_EMAIL missing")

    if not password_val:
        raise Exception("SUPPLIER_PASSWORD missing")

    print("Supplier credentials found.")

    # ========================================
    # EMAIL FIELD
    # ========================================
    email_xpath = (
        "//input[@id='email' or @id='customer-email']"
    )

    print("Waiting for email field...")

    wait.until(
        lambda d: find_visible_element(
            driver, email_xpath
        ) is not None
    )

    email_el = find_visible_element(driver, email_xpath)

    if email_el is None:
        raise Exception("Email field not found")

    print("Email field found.")

    driver.execute_script(
        """
        arguments[0].scrollIntoView({
            block: 'center'
        });
        """,
        email_el
    )

    email_el.clear()
    email_el.send_keys(email_val)

    print("Email entered successfully.")

    # ========================================
    # PASSWORD FIELD
    # ========================================
    password_xpath = (
        "//input[@id='password' or @id='pass']"
    )

    print("Waiting for password field...")

    wait.until(
        lambda d: find_visible_element(
            driver, password_xpath
        ) is not None
    )

    pwd = find_visible_element(driver, password_xpath)

    if pwd is None:
        raise Exception("Password field not found")

    print("Password field found.")

    # Normal send_keys is safer than directly
    # changing the JavaScript value.
    pwd.clear()
    pwd.send_keys(password_val)

    print("Password entered successfully.")

    time.sleep(1)

    # ========================================
    # LOGIN BUTTON
    # ========================================
    login_button_xpath = (
        "//button[@id='send2' and contains(@class, 'primary')]"
    )

    print("Waiting for login button...")

    wait.until(
        lambda d: find_visible_element(
            driver, login_button_xpath
        ) is not None
    )

    login_btn = find_visible_element(
        driver,
        login_button_xpath
    )

    if login_btn is None:
        raise Exception("Login button not found")

    print("Login button found.")

    driver.execute_script(
        """
        arguments[0].scrollIntoView({
            block: 'center'
        });
        """,
        login_btn
    )

    time.sleep(1)

    print("Button displayed:", login_btn.is_displayed())
    print("Button enabled:", login_btn.is_enabled())

    print("Clicking login button...")

    driver.execute_script(
        "arguments[0].click();",
        login_btn
    )

    print("Login button clicked.")

    # ========================================
    # WAIT FOR ACTUAL LOGIN SUCCESS
    # ========================================
    print("Waiting for login success...")

    expected_url = "https://www.cchobby.nl/customer/account/"

    try:
        WebDriverWait(driver, 30).until(
            lambda d: (
                d.current_url.rstrip("/")
                == expected_url.rstrip("/")
            )
        )

        print("========== LOGIN SUCCESS ==========")
        print("Current URL:", driver.current_url)

        return driver

    except TimeoutException:
        print("========== LOGIN TIMEOUT ==========")
        print("Current URL:", driver.current_url)

        save_debug(driver, "login_timeout")

        try:
            errors = driver.find_elements(
                By.XPATH,
                "//div[contains(@class,'message-error') "
                "or @role='alert']"
            )

            for error in errors:
                if error.is_displayed() and error.text.strip():
                    print("LOGIN ERROR:", error.text)

        except Exception as e:
            print(
                "Could not read login error:",
                repr(e)
            )

        raise Exception(
            f"Login failed. Current URL: {driver.current_url}"
        )

except Exception as e:
    print("\n========== LOGIN FAILED ==========")
    print("Exception type:", type(e).__name__)
    print("Exception:", repr(e))
    print("\n========== FULL TRACEBACK ==========")

    traceback.print_exc()

    if driver is not None:
        save_debug(driver, "login_failed")

    raise
```
