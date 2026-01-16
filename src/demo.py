import os, re, time, requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3005")

# =====================================================
# STEP 0 – FETCH ORDER DATA
# =====================================================
def fetch_order_data(order_id):
    res = requests.get(f"{BACKEND_URL}/v1/order-history/internal/{order_id}", timeout=15)
    res.raise_for_status()

    order = res.json()
    raw = order.get("lightspeedRawOrder", {})

    street = " ".join(filter(None, [
        raw.get("addressShippingStreet"),
        raw.get("addressShippingNumber"),
        raw.get("addressShippingExtension"),
    ]))

    phone = re.sub(r"[^\d]", "", raw.get("phone") or "0600000000") or "0600000000"

    return {
        "sku": order.get("product", {}).get("articleNo", ""),
        "qty": order.get("quantity", 1),
        "firstName": raw.get("firstname", ""),
        "lastName": raw.get("lastname", ""),
        "company": raw.get("companyName", ""),
        "vat": raw.get("companyVatNumber", ""),
        "street": street,
        "zipcode": raw.get("addressShippingZipcode", ""),
        "city": raw.get("addressShippingCity", ""),
        "country": raw.get("addressShippingCountry", {}).get("code", "NL").upper(),
        "phone": phone,
        "is_company": bool(raw.get("companyName")),
    }

# =====================================================
# COMMON HELPERS
# =====================================================
def human_type(el, text, delay=0.12):
    el.click()
    el.clear()
    time.sleep(0.3)
    for ch in text:
        el.send_keys(ch)
        time.sleep(delay)

def js_click(driver, el):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.3)
    driver.execute_script("arguments[0].click();", el)

def wait_loader(driver, timeout=30):
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located(
                (By.CSS_SELECTOR, ".loading-mask, .loader")
            )
        )
    except:
        pass

def close_popups(driver):
    driver.execute_script("""
        ['.modal-popup','.newsletter-modal','.modals-overlay',
         '.action-close','#btn-cookie-allow']
        .forEach(s => document.querySelectorAll(s).forEach(e => e.remove()));
        document.body.style.overflow='auto';
    """)

# =====================================================
# ADDRESS MODAL
# =====================================================
def click_ship_here(driver):
    driver.execute_script("document.activeElement.blur();")
    time.sleep(0.3)

    btn = WebDriverWait(driver,30).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR,"button.action-save-address"))
    )
    driver.execute_script("arguments[0].click();", btn)
    time.sleep(1)

def add_new_address(driver, data):
    js_click(driver, WebDriverWait(driver,30).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Nieuw Adres')]"))
    ))

    modal = WebDriverWait(driver,30).until(
        EC.presence_of_element_located((By.ID, "co-shipping-form"))
    )

    human_type(modal.find_element(By.NAME, "firstname"), data["firstName"])
    human_type(modal.find_element(By.NAME, "lastname"), data["lastName"])

    if data["company"]:
        human_type(modal.find_element(By.NAME, "company"), data["company"])
    if data["vat"]:
        human_type(modal.find_element(By.NAME, "vat_id"), data["vat"])

    human_type(modal.find_element(By.NAME, "street[0]"), data["street"])
    human_type(modal.find_element(By.NAME, "postcode"), data["zipcode"], 0.18)
    human_type(modal.find_element(By.NAME, "city"), data["city"])

    Select(modal.find_element(By.NAME, "country_id")).select_by_value(data["country"])
    time.sleep(0.5)

    human_type(modal.find_element(By.NAME, "telephone"), data["phone"], 0.15)

    click_ship_here(driver)
    wait_loader(driver)

    # Handle "Save address?" popup if it appears
    try:
        no_thanks_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//button[contains(text(), 'No thanks') or contains(text(), 'Nee')]"
            ))
        )
        driver.execute_script("arguments[0].click();", no_thanks_btn)
        print("✅ Clicked 'No thanks' on save address popup")
        time.sleep(0.5)
    except:
        print("ℹ️ No 'Save address' popup appeared")
        pass

    # Scroll down after modal closes to ensure payment section is visible
      # ✅ WAIT until shipping methods exist (address fully applied)
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, ".table-checkout-shipping-method")
        )
    )

    # ✅ SCROLL SPECIFICALLY TO PAYMENT SECTION (not bottom)
    driver.execute_script("""
        const payment = document.querySelector('#checkout-payment-method-load');
        if (payment) {
            payment.scrollIntoView({ block: 'center', behavior: 'smooth' });
            window.scrollBy(0, -120);
        }
    """)
    time.sleep(2)

# =====================================================
# SHIPPING (FIXED)
# =====================================================

def select_shipping(driver, data):
    """
    STRICT shipping selection based on business rules:
    - NL  → DPD - Nederlands Zakelijke levering
    - BE private → GLS - Belgische Privé bezorging
    - BE business → GLS - Belgische Zakelijke bezorging
    """

    if data["country"] == "NL":
        carrier = "DPD"
        shipping_text = "Nederlands Zakelijke levering"

    elif data["country"] == "BE" and data["is_company"]:
        carrier = "GLS"
        shipping_text = "Belgische Zakelijke bezorging"

    elif data["country"] == "BE":
        carrier = "GLS"
        shipping_text = "Belgische Privé bezorging"

    else:
        raise Exception(f"❌ Unsupported country: {data['country']}")

    print(f"🚚 Selecting shipping: {carrier} - {shipping_text}")

    wait_loader(driver)
    time.sleep(1)

    # Scroll to shipping section
    driver.execute_script("""
        const el = document.querySelector('.table-checkout-shipping-method');
        if (el) el.scrollIntoView({block:'center'});
    """)
    time.sleep(1)

    # STRICT selector — no fallbacks
    radio = WebDriverWait(driver, 30).until(
        EC.element_to_be_clickable((
            By.XPATH,
            f"//tr[contains(., '{carrier}') and contains(., '{shipping_text}')]//input[@type='radio']"
        ))
    )

    # Click via JS (Magento-safe)
    driver.execute_script("""
        arguments[0].scrollIntoView({block:'center'});
        arguments[0].checked = true;
        arguments[0].dispatchEvent(new Event('click', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
    """, radio)

    # Wait until Magento confirms shipping is set
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script("""
            try {
                return require('Magento_Checkout/js/model/quote')
                    .shippingMethod() !== null;
            } catch(e) { return false; }
        """)
    )

    print(f"✅ Shipping locked: {carrier} - {shipping_text}")


# =====================================================
# PAYMENT – BANK TRANSFER (SIMPLIFIED & ROBUST)
# =====================================================

def scroll_to_payment(driver):
    print("📜 Scrolling to payment section...")

    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located(
            (By.ID, "checkout-payment-method-load")
        )
    )

    time.sleep(2)

    driver.execute_script("""
        const el = document.querySelector('#checkout-payment-method-load');
        if (el) {
            el.scrollIntoView({block: 'center', behavior: 'smooth'});
            window.scrollBy(0, -120);
        }
    """)

    time.sleep(1)
    print("✅ Payment section visible")

def activate_payment_step(driver):
    driver.execute_script("""
        const body = document.body;

        body.classList.remove('fc-step-shipping');
        body.classList.add('fc-step-payment');

        const payment = document.querySelector('#checkout-payment-method-load');
        if (payment) {
            payment.scrollIntoView({block:'center'});
        }
    """)
    time.sleep(1)

    # Wait for payment methods to load after step activation
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[value="banktransfer"]'))
    )
    time.sleep(1)
def select_bank_transfer(driver):
    print("💳 Selecting Bankoverschrijving as default")

    # Wait for payment methods to load and be clickable
    radio = WebDriverWait(driver, 30).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[value="banktransfer"]'))
    )

    # Scroll into view and click
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", radio)
    time.sleep(0.5)
    radio.click()
    time.sleep(1)

    # Dispatch change events to ensure Magento recognizes the selection
    driver.execute_script("""
        const radio = document.querySelector('input[value="banktransfer"]');
        if (radio) {
            radio.checked = true;
            radio.dispatchEvent(new Event('click', { bubbles: true }));
            radio.dispatchEvent(new Event('change', { bubbles: true }));
        }
    """)

    # Ensure it's active in UI
    driver.execute_script("""
        document.querySelectorAll('.payment-method').forEach(pm => pm.classList.remove('_active'));
        const radio = document.querySelector('input[value="banktransfer"]');
        if (radio) {
            const el = radio.closest('.payment-method');
            if (el) el.classList.add('_active');
        }
    """)

    # Verify selection
    WebDriverWait(driver, 10).until(
        lambda d: d.execute_script("""
            const radio = document.querySelector('.payment-method._active input[value="banktransfer"]');
            return radio && radio.checked;
        """)
    )

    print("✅ Bankoverschrijving ACTIVE (default selected)")


# =====================================================
# MAIN FLOW
# =====================================================
def place_order(driver, order_id):
    wait = WebDriverWait(driver, 60)
    data = fetch_order_data(order_id)

    driver.get("https://www.cchobby.nl/")
    time.sleep(3)
    close_popups(driver)

    search = driver.find_element(By.NAME, "q")
    search.send_keys(data["sku"])
    search.submit()
    time.sleep(3)

    js_click(driver, wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, ".product-item-link"))
    ))
    wait_loader(driver)

    try:
        qty = driver.find_element(By.NAME, "qty")
        qty.clear()
        qty.send_keys(str(data["qty"]))
    except:
        pass

    js_click(driver, wait.until(
        EC.element_to_be_clickable((By.ID, "product-addtocart-button"))
    ))
    time.sleep(2)

    driver.get("https://www.cchobby.nl/checkout/")
    wait.until(EC.url_contains("/checkout"))
    wait_loader(driver)

    add_new_address(driver, data)
    select_shipping(driver, data)
    scroll_to_payment(driver)
    activate_payment_step(driver)
    select_bank_transfer(driver)

    print("🛑 FINAL CHECK READY — ORDER NOT PLACED YET")
    print("👉 Review details manually, then click 'Plaats bestelling'")

    return True