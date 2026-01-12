import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from dotenv import load_dotenv

load_dotenv()

LOGIN_URL = os.getenv("SUPPLIER_LOGIN_URL")


def login():
    # ---------- CHROME OPTIONS ----------
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 30)

    # ---------- OPEN LOGIN PAGE ----------
    driver.get(LOGIN_URL)

    # ---------- COOKIE POPUP ----------
    try:
        cookie_btn = wait.until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//button[contains(.,'OK') or contains(.,'Alleen')]"
            ))
        )
        driver.execute_script("arguments[0].click();", cookie_btn)
        time.sleep(1)
    except TimeoutException:
        print("ℹ️ Cookie popup not shown")

    # ---------- LOAD CREDENTIALS ----------
    email = os.getenv("SUPPLIER_EMAIL")
    password = os.getenv("SUPPLIER_PASSWORD")

    if not email or not password:
        raise Exception("❌ Missing SUPPLIER_EMAIL or SUPPLIER_PASSWORD in .env")

    # ---------- EMAIL ----------
    email_input = wait.until(
        EC.element_to_be_clickable((By.ID, "email"))
    )
    email_input.clear()
    email_input.send_keys(email)

    # ---------- PASSWORD (JS INJECTION – REQUIRED) ----------
    password_input = wait.until(
        EC.presence_of_element_located((By.ID, "pass"))
    )

    driver.execute_script(
        """
        arguments[0].value = arguments[1];
        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
        """,
        password_input,
        password
    )

    time.sleep(0.5)

    # ---------- CLICK LOGIN BUTTON (NO ENTER KEY) ----------
    login_btn = wait.until(
        EC.element_to_be_clickable((
            By.XPATH,
            "//button[@type='submit' or contains(.,'Inloggen')]"
        ))
    )

    driver.execute_script("arguments[0].click();", login_btn)

    # ---------- LOGIN SUCCESS CHECK ----------
    try:
        wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//a[contains(@href,'account')]")
            )
        )
        print("✅ LOGIN SUCCESS")
    except TimeoutException:
        driver.save_screenshot("login_failed.png")
        raise Exception("❌ LOGIN FAILED — screenshot saved")

    return driver
