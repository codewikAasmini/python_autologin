import os, re, time, requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3005")


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
        "qty": order.get("quantity"),
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

def unlock_body_and_force_scroll(driver):
    print("🔓 Unlocking body & forcing scroll after address modal")

    driver.execute_script("""
        // Remove any leftover overlays / locks
        document.querySelectorAll('.modals-overlay, .modal-popup, .loading-mask')
            .forEach(e => e.remove());

        document.body.classList.remove('modal-open', '_has-modal');
        document.body.style.overflow = 'auto';
        document.body.style.position = 'static';

        // Force real scroll event
        window.scrollTo(0, document.body.scrollHeight * 0.4);
        window.dispatchEvent(new Event('scroll'));
    """)
    time.sleep(1.5)
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

    try:
        no_thanks_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//button[contains(text(), 'No thanks') or contains(text(), 'Nee')]"
            ))
        )
        driver.execute_script("arguments[0].click();", no_thanks_btn)
        time.sleep(0.5)
    except:
        pass

    # ✅ THIS WAS MISSING
    unlock_body_and_force_scroll(driver)

# =====================================================
# SHIPPING (FIXED)
# =====================================================
def select_shipping(driver, data):
    """
    STABLE shipping selection:
    - NL → DPD (strict)
    - BE → GLS (carrier-based, safe)
    """

    wait_loader(driver)
    time.sleep(1)
    driver.execute_script("""
        const el = document.querySelector('.table-checkout-shipping-method');
        if (el) el.scrollIntoView({block:'center'});
    """)
    time.sleep(1)

    if data["country"] == "NL":
        print("🚚 Selecting NL shipping: DPD")

        radio = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//tr[contains(., 'DPD')]//input[@type='radio']"
            ))
        )

    elif data["country"] == "BE":
        print("🚚 Selecting BE shipping: GLS")
        radio = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//tr[contains(., 'GLS')]//input[@type='radio']"
            ))
        )

    else:
        raise Exception(f"❌ Unsupported country: {data['country']}")
    driver.execute_script("""
        arguments[0].scrollIntoView({block:'center'});
        arguments[0].checked = true;
        arguments[0].dispatchEvent(new Event('click', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
    """, radio)

    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script("""
            try {
                return require('Magento_Checkout/js/model/quote')
                    .shippingMethod() !== null;
            } catch(e) { return false; }
        """)
    )

    print("✅ Shipping selected & locked")



# =====================================================
# PAYMENT – BANK TRANSFER (SIMPLIFIED & ROBUST)
# =====================================================

def wait_shipping_confirmed(driver):
    print("⏳ Waiting for shipping to be confirmed by Magento")

    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script("""
            try {
                const q = require('Magento_Checkout/js/model/quote');
                return q.shippingMethod() !== null;
            } catch(e) { return false; }
        """)
    )

    print("✅ Shipping confirmed & stable")

def handle_save_address_popup(driver):
    print("📦 Checking for 'Save address' popup")
    try:
        no_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//button[contains(.,'No thanks') or contains(.,'Nee') or contains(.,'Niet opslaan')]"
            ))
        )
        driver.execute_script("arguments[0].click();", no_btn)
        print("✅ Clicked 'No thanks' on save-address popup")
    
        WebDriverWait(driver, 5).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, ".modals-overlay"))
        )
    except:
        print("ℹ️ No 'Save address' popup found or already closed")

def unlock_and_scroll_to_payment(driver):
    print("🔓 Force removing any blocking overlays & scrolling")

    driver.execute_script("""
        // Force remove any remaining modals or overlays that block clicks
        document.querySelectorAll('.modals-overlay, .modal-popup, .loading-mask').forEach(e => e.remove());
        document.body.classList.remove('modal-open');
        document.body.style.overflow = 'auto';

        const payment = document.getElementById('checkout-payment-method-load');
        if (payment) {
            payment.scrollIntoView({ block: 'center' });
            window.scrollBy(0, -100);
        }
    """)
    time.sleep(1)

def human_scroll_to_payment(driver):
    print("🖱️ Human-like scroll to payment section")

    driver.execute_script("""
        const target = document.getElementById('checkout-payment-method-load');
        if (!target) return;

        const rect = target.getBoundingClientRect();
        const targetY = rect.top + window.pageYOffset - 200;

        let currentY = window.pageYOffset;
        const step = 120;

        const interval = setInterval(() => {
            if (currentY >= targetY) {
                clearInterval(interval);
                target.scrollIntoView({ block: 'center' });
                window.dispatchEvent(new Event('scroll'));
            } else {
                window.scrollBy(0, step);
                currentY += step;
            }
        }, 60);
    """)
    time.sleep(2)
def force_payment_renderer(driver):
    print("⚙️ Forcing Magento payment renderer")

    driver.execute_script("""
        try {
            const service = require('Magento_Checkout/js/model/payment-service');
            const methods = service.getAvailablePaymentMethods();

            methods.forEach(m => {
                if (m.method === 'banktransfer') {
                    require('Magento_Checkout/js/action/select-payment-method')(m);
                }
            });
        } catch(e) {}
    """)
    time.sleep(1)

def select_bank_transfer(driver):
    print("💳 Selecting Bankoverschrijving (viewport + KO safe)")

    wait = WebDriverWait(driver, 30)

    # 🔥 REAL human scroll
    human_scroll_to_payment(driver)

    # 🔥 Force Magento payment JS
    force_payment_renderer(driver)

    # Wait until radio appears
    radio = wait.until(
        EC.presence_of_element_located((By.ID, "banktransfer"))
    )

    # Final KO-safe click
    driver.execute_script("""
        arguments[0].checked = true;
        arguments[0].dispatchEvent(new Event('click', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
    """, radio)

    # ✅ Confirm Magento state
    wait.until(lambda d: d.execute_script("""
        try {
            return require('Magento_Checkout/js/model/quote')
                .paymentMethod()?.method === 'banktransfer';
        } catch(e) { return false; }
    """))

    print("✅ Bankoverschrijving SELECTED & LOCKED")




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
    wait_shipping_confirmed(driver)
    handle_save_address_popup(driver)
    unlock_and_scroll_to_payment(driver)  
    select_bank_transfer(driver)

    print("🛑 FINAL CHECK READY — ORDER NOT PLACED YET")
    print("👉 Review details manually, then click 'Plaats bestelling'")

    return True