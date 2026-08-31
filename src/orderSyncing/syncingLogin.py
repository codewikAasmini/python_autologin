import json
import os
import time
import traceback
from datetime import datetime

from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


load_dotenv()

LOGIN_URL = os.getenv("SUPPLIER_LOGIN_URL")
SELENIUM_REMOTE_URL = os.getenv(
    "SELENIUM_REMOTE_URL", "http://localhost:4444/wd/hub"
)
EXPECTED_LOGIN_URL = "https://www.cchobby.nl/customer/account/"


def save_debug(driver, name):
    """Save browser state without printing page contents or credentials."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = f"/tmp/{name}_{timestamp}"
    screenshot_path = f"{prefix}.png"
    html_path = f"{prefix}.html"
    info_path = f"{prefix}.txt"
    logs_path = f"{prefix}_browser_logs.json"

    print("\n========== DEBUG INFO ==========")

    try:
        current_url = driver.current_url
        page_title = driver.title
        with open(info_path, "w", encoding="utf-8") as info_file:
            info_file.write(f"Current URL: {current_url}\n")
            info_file.write(f"Page title: {page_title}\n")
        print("DEBUG URL:", current_url)
        print("DEBUG TITLE:", page_title)
        print(f"DEBUG INFO SAVED: {info_path}")
    except Exception as e:
        print("Unable to save URL/title:", repr(e))

    try:
        driver.save_screenshot(screenshot_path)
        print(f"DEBUG SCREENSHOT SAVED: {screenshot_path}")
    except Exception as e:
        print("Screenshot error:", repr(e))

    try:
        with open(html_path, "w", encoding="utf-8") as html_file:
            html_file.write(driver.page_source)
        print(f"DEBUG PAGE SOURCE SAVED: {html_path}")
    except Exception as e:
        print("Page source save error:", repr(e))

    try:
        logs = driver.get_log("browser")
        with open(logs_path, "w", encoding="utf-8") as logs_file:
            json.dump(logs, logs_file, indent=2)
        print(f"DEBUG BROWSER LOGS SAVED: {logs_path}")
    except Exception as e:
        print("Could not get browser logs:", repr(e))

    print("========== END DEBUG ==========\n")


def find_visible_element(driver, xpath):
    for element in driver.find_elements(By.XPATH, xpath):
        try:
            if element.is_displayed():
                return element
        except Exception:
            continue

    return None


def login():
    driver = None

    try:
        if not LOGIN_URL:
            raise RuntimeError("SUPPLIER_LOGIN_URL missing")

        email_val = os.getenv("SUPPLIER_EMAIL")
        password_val = os.getenv("SUPPLIER_PASSWORD")
        if not email_val:
            raise RuntimeError("SUPPLIER_EMAIL missing")
        if not password_val:
            raise RuntimeError("SUPPLIER_PASSWORD missing")

        print("========== STARTING SELENIUM ==========")
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.set_capability("goog:loggingPrefs", {"browser": "ALL"})

        print("Connecting to Selenium server:", SELENIUM_REMOTE_URL)
        driver = webdriver.Remote(
            command_executor=SELENIUM_REMOTE_URL,
            options=options,
        )

        print("Selenium session created successfully.")
        driver.set_page_load_timeout(60)
        wait = WebDriverWait(driver, 30)

        print("Opening supplier login page.")
        driver.get(LOGIN_URL)
        print("Current URL:", driver.current_url)
        print("Page title:", driver.title)

        if "noroute" in driver.current_url.lower():
            raise RuntimeError(f"Invalid login URL or redirect: {driver.current_url}")

        try:
            cookie = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//button[contains(.,'OK') "
                        "or contains(.,'Alleen') "
                        "or contains(@class,'coi-banner__accept')]",
                    )
                )
            )
            driver.execute_script("arguments[0].click();", cookie)
            time.sleep(1)
        except TimeoutException:
            print("No cookie popup found.")
        except Exception as e:
            print("Cookie popup error:", repr(e))

        try:
            popup_xpath = (
                "//button[contains(@class,'klaviyo-close-form') "
                "or contains(@aria-label,'Close') "
                "or contains(@aria-label,'close')]"
            )
            for popup in driver.find_elements(By.XPATH, popup_xpath):
                try:
                    if popup.is_displayed():
                        driver.execute_script("arguments[0].click();", popup)
                        time.sleep(1)
                except Exception as e:
                    print("Popup close error:", repr(e))
        except Exception as e:
            print("Popup search error:", repr(e))

        email_xpath = (
            "//input[@id='email' or @id='customer-email' "
            "or @name='login[username]' or @type='email']"
        )
        wait.until(lambda d: find_visible_element(d, email_xpath) is not None)
        email_el = find_visible_element(driver, email_xpath)
        if email_el is None:
            raise RuntimeError("Email field not found")
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", email_el
        )
        email_el.clear()
        email_el.send_keys(email_val)
        print("Email entered successfully.")

        password_xpath = (
            "//input[@id='password' or @id='pass' "
            "or @name='login[password]' or @type='password']"
        )
        wait.until(lambda d: find_visible_element(d, password_xpath) is not None)
        password_el = find_visible_element(driver, password_xpath)
        if password_el is None:
            raise RuntimeError("Password field not found")
        password_el.clear()
        password_el.send_keys(password_val)
        print("Password entered successfully.")

        login_button_xpath = (
            "//button[@id='send2' or @name='send' or @type='submit']"
        )
        wait.until(
            lambda d: find_visible_element(d, login_button_xpath) is not None
        )
        login_button = find_visible_element(driver, login_button_xpath)
        if login_button is None:
            raise RuntimeError("Login button not found")
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", login_button
        )
        driver.execute_script("arguments[0].click();", login_button)
        print("Login button clicked; waiting for account page.")

        WebDriverWait(driver, 30).until(
            lambda d: d.current_url.rstrip("/")
            == EXPECTED_LOGIN_URL.rstrip("/")
        )
        print("========== LOGIN SUCCESS ==========")
        print("Current URL:", driver.current_url)
        return driver

    except Exception as e:
        print("\n========== LOGIN FAILED ==========")
        print("Exception type:", type(e).__name__)
        print(repr(e))
        traceback.print_exc()

        if driver is not None:
            save_debug(driver, "login_failed")
            try:
                driver.quit()
            except Exception as quit_error:
                print("Driver cleanup error:", repr(quit_error))

        raise RuntimeError(
            f"Supplier login failed: {type(e).__name__}: {e}"
        ) from e
