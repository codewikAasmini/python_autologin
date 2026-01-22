import os, re, time, requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
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
        "qty": order.get("quantity") or 1,
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
def real_mouse_scroll(driver, pixels=800):
    print("🖱️ Real mouse wheel scroll")

    origin = ScrollOrigin.from_viewport(0, 0)
    ActionChains(driver).scroll_from_origin(origin, 0, pixels).perform()
    time.sleep(1)


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

    # Force unlock as some popups (Save address?) might appear here or later
    unlock_body_and_force_scroll(driver)

# =====================================================
# SHIPPING (FIXED)
# =====================================================
def select_shipping(driver, data):
    """
    EXACT shipping selection based on business rules
    """

    wait_loader(driver)
    time.sleep(1)

    driver.execute_script("""
        const el = document.querySelector('.table-checkout-shipping-method');
        if (el) el.scrollIntoView({block:'center'});
    """)
    time.sleep(1)

    # ---------- NETHERLANDS ----------
    if data["country"] == "NL":
        print("🚚 NL → DPD - Nederlands Zakelijke levering")

        xpath = (
            "//tr[.//text()[contains(.,'DPD') "
            "and contains(.,'Nederlands')]]//input[@type='radio']"
        )

    # ---------- BELGIUM ----------
    elif data["country"] == "BE":

        if data["is_company"]:
            print("🚚 BE Business → GLS - Belgische Zakelijke bezorging")

            xpath = (
                "//tr[.//text()[contains(.,'GLS') "
                "and contains(.,'Zakelijke')]]//input[@type='radio']"
            )

        else:
            print("🚚 BE Private → GLS - Belgische Privé bezorging")

            xpath = (
                "//tr[.//text()[contains(.,'GLS') "
                "and contains(.,'Privé')]]//input[@type='radio']"
            )

    else:
        raise Exception(f"❌ Unsupported country: {data['country']}")

    # ---------- CLICK RADIO ----------
    radio = WebDriverWait(driver, 30).until(
        EC.element_to_be_clickable((By.XPATH, xpath))
    )

    driver.execute_script("""
        arguments[0].scrollIntoView({block:'center'});
        arguments[0].checked = true;
        arguments[0].dispatchEvent(new Event('click', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
    """, radio)

    # ---------- CONFIRM MAGENTO STATE ----------
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script("""
            try {
                return require('Magento_Checkout/js/model/quote')
                    .shippingMethod() !== null;
            } catch(e) { return false; }
        """)
    )

    print("✅ Shipping selected correctly")
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
    print("📦 Handling 'Save address' popup (No thanks default)")

    driver.execute_script("""
        // 1️⃣ Try clicking "No thanks" button explicitly
        const buttons = Array.from(document.querySelectorAll('button, a, span'));
        const noThanks = buttons.find(b => {
            const t = (b.innerText || '').toLowerCase();
            return t.includes('no thanks') || t.includes('nee') || t.includes('no, thanks');
        });

        if (noThanks) {
            noThanks.click();
            console.log('Clicked NO THANKS');
        }

        // 2️⃣ Hard-remove popup if still present
        document.querySelectorAll(
            'aside, .modal-popup, .modals-overlay, .ui-widget-overlay'
        ).forEach(e => e.remove());

        // 3️⃣ Fully unlock page scroll
        document.body.classList.remove('modal-open', '_has-modal');
        document.body.style.overflow = 'auto';
        document.body.style.position = 'static';

        // 4️⃣ Force browser scroll event (VERY IMPORTANT)
        window.scrollBy(0, 1);
        window.dispatchEvent(new Event('scroll'));
    """)
    time.sleep(1)
    print("✅ Address popup cleared & page unlocked")


def confirm_shipping_js(driver):
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script("""
            try {
                const quote = require('Magento_Checkout/js/model/quote');
                return quote.shippingMethod() && quote.shippingMethod().method_code;
            } catch(e) { return false; }
        """)
    )

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
def force_totals_recalculation(driver):
    print("🔄 Forcing totals recalculation")

    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script("""
            try {
                const quote = require('Magento_Checkout/js/model/quote');
                const totalsProcessor =
                    require('Magento_Checkout/js/model/cart/totals-processor/default');

                if (quote.shippingMethod()) {
                    totalsProcessor.estimateTotals();
                    return true;
                }
                return false;
            } catch(e) { return false; }
        """)
    )

    # wait until totals exist
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script("""
            try {
                return require('Magento_Checkout/js/model/quote').totals() !== null;
            } catch(e) { return false; }
        """)
    )

    print("✅ Totals ready")
    
    
def select_bank_transfer(driver):
    print("💳 Selecting Bankoverschrijving (Bank Transfer)")

    # 1️⃣ Scroll payment section into view
    driver.execute_script("""
        const el = document.getElementById('checkout-payment-method-load');
        if (el) el.scrollIntoView({ block: 'center' });
    """)
    time.sleep(1)

    # 2️⃣ Click RADIO input (UI level)
    bank_radio_xpath = (
        "//label[.//text()[contains(.,'Bankoverschrijving')]]"
        "//input[@type='radio']"
    )

    radio = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, bank_radio_xpath))
    )

    driver.execute_script("""
        arguments[0].scrollIntoView({ block: 'center' });
        arguments[0].checked = true;
        arguments[0].dispatchEvent(new Event('click', { bubbles: true }));
        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
    """, radio)

    time.sleep(1)

    # 3️⃣ Force Magento KO payment state
    driver.execute_script("""
        try {
            const quote = require('Magento_Checkout/js/model/quote');
            const paymentService = require('Magento_Checkout/js/model/payment-service');
            const selectAction = require('Magento_Checkout/js/action/select-payment-method');

            const method = paymentService.getAvailablePaymentMethods()
                .find(m => m.method === 'banktransfer');

            if (method) {
                selectAction(method);
                quote.paymentMethod(method);
            }
        } catch(e) {
            console.error('Bank transfer JS select failed', e);
        }
    """)

    # 4️⃣ VERIFY it is selected
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script("""
            try {
                return require('Magento_Checkout/js/model/quote')
                    .paymentMethod()?.method === 'banktransfer';
            } catch(e) { return false; }
        """)
    )

    print("✅ Bankoverschrijving selected & locked")

def force_totals(driver):
    driver.execute_script("""
        try {
            const quote = require('Magento_Checkout/js/model/quote');
            const totalsProcessor =
                require('Magento_Checkout/js/model/cart/totals-processor/default');

            if (quote.shippingMethod()) {
                totalsProcessor.estimateTotals();
            }
        } catch(e) {}
    """)
def accept_terms(driver):
    driver.execute_script("""
        document.querySelectorAll(
            '.checkout-agreement input[type="checkbox"]'
        ).forEach(cb => {
            if (!cb.checked) cb.click();
        });
    """)
def click_place_order(driver):
    print("🚀 Finalizing order placement")
    
    for i in range(5):
        print(f"🔄 Attempting to click 'Plaats bestelling' ({i+1}/5)")
        
        # 1. Final popup cleanup
        handle_save_address_popup(driver)
        wait_loader(driver)
        
        # 2. Check for Agreement checkbox (again, just in case)
        driver.execute_script("""
            document.querySelectorAll('input[type="checkbox"].required-entry, .checkout-agreement input[type="checkbox"]')
                .forEach(cb => { if(!cb.checked) cb.click(); });
        """)
        time.sleep(0.5)

        # 3. Find and click button
        try:
            btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.action.primary.checkout"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", btn)
            print("✅ 'Plaats bestelling' clicked")
        except:
            print("⚠️ Button not clickable yet...")
            continue

        # 4. Verification loop
        print("⏳ Verification...")
        for _ in range(10):
            time.sleep(1)
            if "/success" in driver.current_url or "success" in driver.current_url.lower():
                print("🎉 SUCCESS! Order placed.")
                return True
            
            # Error check
            errs = driver.find_elements(By.CSS_SELECTOR, ".message-error")
            if errs and any(e.is_displayed() for e in errs):
                print(f"❌ Magento Error: {errs[0].text}")
                # If error is about payment, retry selection
                if "betaalmethode" in errs[0].text.lower():
                    select_bank_transfer(driver)
                break
                
    print("🏁 Finished placement attempts.")
    return True

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
    real_mouse_scroll(driver, 900)
    select_shipping(driver, data)
    wait_shipping_confirmed(driver)
    handle_save_address_popup(driver)
    force_totals_recalculation(driver)
    real_mouse_scroll(driver, 600)  
    confirm_shipping_js(driver)
    handle_save_address_popup(driver)
    unlock_and_scroll_to_payment(driver)
    human_scroll_to_payment(driver)
    select_bank_transfer(driver)
    force_totals(driver)
    wait_loader(driver)
    accept_terms(driver)
    click_place_order(driver)

    print("🏁 Finished placement attempts.")
    return False 