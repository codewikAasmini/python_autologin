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
    options = webdriver.ChromeOptions()

    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 30)

    driver.get(LOGIN_URL)
    try:

        cookie = wait.until(EC.element_to_be_clickable((
            By.XPATH, "//button[contains(.,'OK') or contains(.,'Alleen') or contains(@class, 'coi-banner__accept')]"
        )))
        driver.execute_script("arguments[0].click();", cookie)
        time.sleep(1)
    
        popups = driver.find_elements(By.XPATH, "//button[contains(@class, 'klaviyo-close-form')]")
        for p in popups:
            if p.is_displayed():
                driver.execute_script("arguments[0].click();", p)
    except Exception:
        pass

    email_val = os.getenv("SUPPLIER_EMAIL")
    password_val = os.getenv("SUPPLIER_PASSWORD")

    if not email_val or not password_val:
        raise Exception("SUPPLIER_EMAIL / SUPPLIER_PASSWORD missing")
    print("Waiting for email field...")
    def find_visible_element(xpath):
        elements = driver.find_elements(By.XPATH, xpath)
        for el in elements:
            if el.is_displayed():
                return el
        return None

    wait.until(lambda d: find_visible_element("//input[@id='email' or @id='customer-email']") is not None)
    email_el = find_visible_element("//input[@id='email' or @id='customer-email']")
    
    print("Email field found.")
    driver.execute_script("arguments[0].scrollIntoView(true);", email_el)
    time.sleep(1)
    email_el.clear()
    email_el.send_keys(email_val)
    print("Waiting for password field...")
    wait.until(lambda d: find_visible_element("//input[@id='password' or @id='pass']") is not None)
    pwd = find_visible_element("//input[@id='password' or @id='pass']")
    print("Password field found.")
    driver.execute_script("""
        arguments[0].focus();
        arguments[0].value = arguments[1];
        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
    """, pwd, password_val)

    time.sleep(1)
    print("Waiting for login button...")
    wait.until(lambda d: find_visible_element("//button[@id='send2' and contains(@class, 'primary')]") is not None)
    login_btn = find_visible_element("//button[@id='send2' and contains(@class, 'primary')]")
    print("Login button found.")
    driver.execute_script("arguments[0].click();", login_btn)
    try:
        wait.until(lambda d: d.current_url != LOGIN_URL)
        print("LOGIN SUCCESS")
    except TimeoutException:
        print("LOGIN TIMEOUT - might have failed or stayed on the same page")
        if "login" in driver.current_url:
     
             try:
                 error = driver.find_element(By.XPATH, "//div[@data-bind='html: $parent.prepareMessageForHtml(message.text)']")
                 print(f"Login error: {error.text}")
             except:
                 pass
    
    return driver
