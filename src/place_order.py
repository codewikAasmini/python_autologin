import os, re, time, requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import StaleElementReferenceException

BACKEND_URL = os.getenv("BACKEND_URL", "http://31.97.78.137:3005")
# BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3005")

BILLING_ADDRESS = {
    "firstName": "Mohamed",
    "lastName": "Guenoun",
    "company": "Crea Place",
    "street": "Postbus 3",
    "zipcode": "2840 AA",
    "city": "Moordrecht",
    "country": "NL",
    "phone": "0180-413131",
}


def fetch_order_data(order_id):
    res = requests.get(
        f"{BACKEND_URL}/v1/order-history/internal/{order_id}", timeout=15
    )
    res.raise_for_status()

    order = res.json()
    raw = order.get("lightspeedRawOrder", {})

    street = " ".join(
        filter(
            None,
            [
                raw.get("addressShippingStreet"),
                raw.get("addressShippingNumber"),
                raw.get("addressShippingExtension"),
            ],
        )
    ).strip()

    raw_phone = (raw.get("phone") or "").strip()
    digits = re.sub(r"[^\d]", "", raw_phone)
    phone = digits if digits else "0100000000"
    lines = order.get("products", [])

    return {
        "products": [
            {
                "sku": p.get("product", {}).get("articleNo", ""),
                "qty": max(int(p.get("quantity") or p.get("quantityOrdered") or 1), 1),
            }
            for p in lines
            if p.get("product")
        ],
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

def js_click_safe(driver, locator, timeout=30):
    for _ in range(3):
        try:
            el = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable(locator)
            )
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", el)
            return
        except StaleElementReferenceException:
            print("♻️ Retrying stale element...")
            time.sleep(1)
    raise Exception("❌ Failed to click element due to stale reference")


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
    driver.execute_script(
        """
        ['.modal-popup','.newsletter-modal','.modals-overlay',
         '.action-close','#btn-cookie-allow']
        .forEach(s => document.querySelectorAll(s).forEach(e => e.remove()));
        document.body.style.overflow='auto';
        """
    )


def clear_cart(driver):
    print("Checking and clearing old cart items")

    driver.get("https://www.cchobby.nl/checkout/cart/")
    time.sleep(3)

    while True:
        remove_buttons = driver.find_elements(
            By.CSS_SELECTOR, "a.action.action-delete, button.action-delete"
        )

        if not remove_buttons:
            print("Cart already empty")
            break

        print(f"Removing {len(remove_buttons)} item(s) from cart")

        for btn in remove_buttons:
            try:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", btn
                )
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(2)

                try:
                    confirm = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable(
                            (By.CSS_SELECTOR, "button.action-primary.action-accept")
                        )
                    )
                    confirm.click()
                except:
                    pass

                time.sleep(3)
            except:
                pass

        # Re-check after a pass
        time.sleep(2)

    # Wait until cart shows empty state (no item rows present)
    WebDriverWait(driver, 20).until(
        lambda d: len(d.find_elements(By.CSS_SELECTOR, "a.action.action-delete, button.action-delete")) == 0
    )

    print("Cart cleared successfully")


# =====================================================
# ADDRESS MODAL
# =====================================================

def real_mouse_scroll(driver, pixels=800):
    print("🖱️ Real mouse wheel scroll")
    origin = ScrollOrigin.from_viewport(0, 0)
    ActionChains(driver).scroll_from_origin(origin, 0, pixels).perform()
    time.sleep(1)


def unlock_body_and_force_scroll(driver):
    driver.execute_script(
        """
        document.querySelectorAll('.modals-overlay, .modal-popup, .loading-mask')
            .forEach(e => e.remove());
        document.body.classList.remove('modal-open', '_has-modal');
        document.body.style.overflow = 'auto';
        document.body.style.position = 'static';
        window.scrollTo(0, document.body.scrollHeight * 0.4);
        window.dispatchEvent(new Event('scroll'));
        """
    )
    time.sleep(1.5)


def click_ship_here(driver):
    print("📦 Clicking 'Hier naartoe verzenden'")

    btn = WebDriverWait(driver, 25).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.action-save-address"))
    )
    driver.execute_script("arguments[0].click();", btn)

    WebDriverWait(driver, 25).until(
        EC.invisibility_of_element_located((By.ID, "co-shipping-form"))
    )
    print("✅ Address saved & modal closed")


def _clear_magento_checkout_cache(driver):
    """Wipe all Magento checkout localStorage/sessionStorage keys."""
    driver.execute_script(
        """
        try {
            const storage = require('Magento_Customer/js/customer-data');
            storage.invalidate(['checkout-data', 'cart']);
        } catch(e) {}

        ['localStorage', 'sessionStorage'].forEach(storeName => {
            const store = window[storeName];
            if (!store) return;
            Object.keys(store).forEach(k => {
                if (k.includes('checkout') || k.includes('mage-cache') ||
                    k.includes('shipping') || k.includes('payment')) {
                    store.removeItem(k);
                }
            });
        });
        """
    )
    time.sleep(0.5)


def force_checkout_to_shipping_step(driver):
    """
    Magento caches shipping/payment state across sessions and can land
    directly on the payment step. Always verify we are on step 1 and
    reset if not.
    """
    print("🔄 Ensuring checkout is on shipping step...")

    state = driver.execute_script(
        """
        const payStep  = document.getElementById('checkout-step-payment');
        const shipStep = document.getElementById('checkout-step-shipping');
        const hasSpinner = !!document.querySelector('.loading-mask');

        const payVisible  = !!(payStep  && payStep.offsetParent  !== null);
        const shipVisible = !!(shipStep && shipStep.offsetParent !== null);

        return { payVisible, shipVisible, hasSpinner };
        """
    )
    print("🔍 Checkout state:", state)

    if state.get("shipVisible") and not state.get("payVisible"):
        print("✅ Already on shipping step")
        return

    # Any other case (payment visible, spinner, or neither) → reset
    print("⚠️  Not on shipping step — resetting checkout cache and reloading")
    _reset_to_shipping_step(driver)


def _reset_to_shipping_step(driver):
    """Hard-reset: clear cache then reload /checkout/ from scratch."""

    _clear_magento_checkout_cache(driver)
    time.sleep(1)

    driver.get("https://www.cchobby.nl/checkout/")
    time.sleep(4)
    wait_loader(driver)

    # Wait up to 30s for the shipping step to become visible
    try:
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script(
                """
                const s = document.getElementById('checkout-step-shipping');
                return s && s.offsetParent !== null;
                """
            )
        )
        print("✅ Checkout reset to shipping step")
    except Exception:
        # Last resort: try clicking the shipping step breadcrumb
        print("⚠️  Shipping step not visible after reload, trying breadcrumb click")
        try:
            crumb = driver.find_element(
                By.CSS_SELECTOR, "li[data-role='opc-nav-li'][data-name='shipping']"
            )
            driver.execute_script("arguments[0].click();", crumb)
            time.sleep(2)
        except Exception:
            pass
        WebDriverWait(driver, 20).until(
            lambda d: d.execute_script(
                """
                const s = document.getElementById('checkout-step-shipping');
                return s && s.offsetParent !== null;
                """
            )
        )


def ensure_address_modal_open(driver):
    print("🔍 Checking if address modal is open...")

    modals = driver.find_elements(By.ID, "co-shipping-form")
    if modals and modals[0].is_displayed():
        print("✅ Address modal already open")
        return

    print("📌 Clicking '+ Nieuw adres'")
    btn = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(.,'Nieuw adres') or contains(.,'Nieuw Adres')]")
        )
    )
    driver.execute_script("arguments[0].click();", btn)

    WebDriverWait(driver, 25).until(
        EC.visibility_of_element_located((By.ID, "co-shipping-form"))
    )
    print("✅ Address modal opened")


# =====================================================
# SHIPPING
# =====================================================

def select_shipping(driver, data):
    """Select shipping method based on country and customer type."""

    wait_loader(driver)
    time.sleep(2)

    driver.execute_script(
        """
        const el = document.querySelector('.table-checkout-shipping-method');
        if (el) el.scrollIntoView({block:'center'});
        """
    )
    time.sleep(1)

    rows_el = WebDriverWait(driver, 30).until(
        lambda d: d.find_elements(By.CSS_SELECTOR, ".table-checkout-shipping-method .row")
    )

    if not rows_el:
        raise Exception("❌ No shipping rows found on page")

    target = None

    if data["country"] == "NL":
        print("🚚 NL → Looking for DPD Nederlandse Zakelijke levering")
        for r in rows_el:
            title = (r.get_attribute("data-title") or "").lower()
            text = (r.text or "").lower()
            if "nederlandse" in title or "nederlandse" in text:
                target = r
                break
        if not target:
            # Fallback: first available row
            print("⚠️ NL specific row not found, using first available")
            target = rows_el[0]

    elif data["country"] == "BE":
        print("🇧🇪 BE → Selecting based on business type")
        for r in rows_el:
            title = (r.get_attribute("data-title") or "").lower()
            text = (r.text or "").lower()
            if data["is_company"]:
                if "zakelijke" in title or "zakelijke" in text:
                    target = r
                    break
            else:
                if "privé" in title or "prive" in title or "privé" in text:
                    target = r
                    break
        if not target:
            print("⚠️ BE specific row not found, using first available")
            target = rows_el[0]

    else:
        print(f"🌍 Country {data['country']} → using first available shipping")
        target = rows_el[0]

    if not target:
        raise Exception("❌ No shipping option matched")

    print("👉 Clicking shipping row:", target.get_attribute("data-title"))

    driver.execute_script(
        """
        arguments[0].scrollIntoView({block:'center'});
        arguments[0].click();
        """,
        target,
    )

    # Also click the radio inside the row directly
    try:
        radio = target.find_element(By.CSS_SELECTOR, "input[type='radio']")
        driver.execute_script("arguments[0].click();", radio)
    except:
        pass

    # Confirm Magento state
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script(
            """
            try {
                return require('Magento_Checkout/js/model/quote')
                    .shippingMethod() !== null;
            } catch(e) { return false; }
            """
        )
    )

    print("✅ Shipping selected correctly")


# =====================================================
# PAYMENT
# =====================================================

def wait_shipping_confirmed(driver):
    print("⏳ Waiting for shipping state")
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script(
            """
            try {
                return require('Magento_Checkout/js/model/quote')
                    .shippingMethod() !== null;
            } catch(e) { return false; }
            """
        )
    )
    print("✅ Shipping confirmed")


def handle_save_address_popup(driver):
    print("📦 Handling 'Save address' popup")
    driver.execute_script(
        """
        const buttons = Array.from(document.querySelectorAll('button, a, span'));
        const noThanks = buttons.find(b => {
            const t = (b.innerText || '').toLowerCase();
            return t.includes('no thanks') || t.includes('nee') || t.includes('no, thanks');
        });
        if (noThanks) { noThanks.click(); }

        document.body.classList.remove('modal-open', '_has-modal');
        document.body.style.overflow = 'auto';
        document.body.style.position = 'static';
        window.scrollBy(0, 1);
        window.dispatchEvent(new Event('scroll'));
        """
    )
    time.sleep(1)


def confirm_shipping_js(driver):
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script(
            """
            try {
                const quote = require('Magento_Checkout/js/model/quote');
                return quote.shippingMethod() && quote.shippingMethod().method_code;
            } catch(e) { return false; }
            """
        )
    )


def unlock_and_scroll_to_payment(driver):
    driver.execute_script(
        """
        document.querySelectorAll('.modals-overlay, .modal-popup, .loading-mask').forEach(e => e.remove());
        document.body.classList.remove('modal-open');
        document.body.style.overflow = 'auto';
        const payment = document.getElementById('checkout-payment-method-load');
        if (payment) {
            payment.scrollIntoView({ block: 'center' });
            window.scrollBy(0, -100);
        }
        """
    )
    time.sleep(1)


def human_scroll_to_payment(driver):
    driver.execute_script(
        """
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
        """
    )
    time.sleep(2)


def force_totals_recalculation(driver):
    print("🔄 Forcing totals recalculation")
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script(
            """
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
            """
        )
    )
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script(
            """
            try {
                return require('Magento_Checkout/js/model/quote').totals() !== null;
            } catch(e) { return false; }
            """
        )
    )
    print("✅ Totals ready")


def select_bank_transfer(driver):
    print("💳 Waiting for payment methods...")

    WebDriverWait(driver, 60).until(
        lambda d: d.execute_script(
            """
            const radios = document.querySelectorAll(
              '#checkout-payment-method-load input[type=radio]'
            );
            const loading = document.querySelector('.loading-mask');
            return radios.length > 0 && !loading;
            """
        )
    )

    print("💳 Selecting Bankoverschrijving...")

    radio = WebDriverWait(driver, 40).until(
        EC.presence_of_element_located((By.ID, "banktransfer"))
    )

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", radio)
    time.sleep(1)

    driver.execute_script(
        """
        arguments[0].dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));
        arguments[0].dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));
        arguments[0].click();
        """,
        radio,
    )

    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script(
            """
            try {
                const q = require('Magento_Checkout/js/model/quote');
                return q.paymentMethod() &&
                       q.paymentMethod().method === 'banktransfer';
            } catch(e) { return false; }
            """
        )
    )
    print("✅ Bankoverschrijving selected in Magento")


def wait_payment_ready(driver):
    print("⏳ Waiting for payment methods to render")
    WebDriverWait(driver, 60).until(
        lambda d: d.execute_script(
            """
            try {
                const step = document.getElementById('checkout-step-payment');
                const methods = document.querySelectorAll(
                    '#checkout-payment-method-load input[type=radio]'
                );
                const loading = document.querySelector('.loading-mask');
                return step && methods.length > 0 && !loading;
            } catch(e) { return false; }
            """
        )
    )
    print("✅ Payment methods rendered")


def force_banktransfer_js(driver):
    print("⚙️ Forcing Bankoverschrijving via Magento JS")
    driver.execute_script(
        """
        try {
            const service = require('Magento_Checkout/js/model/payment-service');
            const select = require('Magento_Checkout/js/action/select-payment-method');
            const methods = service.getAvailablePaymentMethods();
            methods.forEach(m => { if (m.method === 'banktransfer') { select(m); } });
        } catch(e) { console.log(e); }
        """
    )


def click_shipping_next(driver):
    print("➡️ Clicking shipping NEXT")

    WebDriverWait(driver, 60).until(
        lambda d: d.execute_script(
            """
            try {
                const q = require('Magento_Checkout/js/model/quote');
                return q.shippingMethod() && q.shippingMethod().carrier_code;
            } catch(e) { return false; }
            """
        )
    )

    WebDriverWait(driver, 60).until(
        EC.invisibility_of_element_located((By.CSS_SELECTOR, ".loading-mask, .loader"))
    )

    btn = WebDriverWait(driver, 60).until(
        lambda d: d.find_element(
            By.CSS_SELECTOR,
            "#shipping-method-buttons-container button.continue:not([disabled])",
        )
    )

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    time.sleep(1)
    driver.execute_script("arguments[0].click();", btn)

    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.ID, "checkout-step-payment"))
    )
    print("✅ Payment step opened")


def force_totals(driver):
    driver.execute_script(
        """
        try {
            const quote = require('Magento_Checkout/js/model/quote');
            const totalsProcessor =
                require('Magento_Checkout/js/model/cart/totals-processor/default');
            if (quote.shippingMethod()) { totalsProcessor.estimateTotals(); }
        } catch(e) {}
        """
    )


def accept_terms(driver):
    driver.execute_script(
        """
        document.querySelectorAll(
            '.checkout-agreement input[type="checkbox"]'
        ).forEach(cb => { if (!cb.checked) cb.click(); });
        """
    )


def set_field_js(driver, el, value):
    driver.execute_script(
        """
        arguments[0].focus();
        arguments[0].value = arguments[1];
        arguments[0].dispatchEvent(new Event('input', {bubbles:true}));
        arguments[0].dispatchEvent(new Event('change', {bubbles:true}));
        arguments[0].dispatchEvent(new Event('blur', {bubbles:true}));
        """,
        el,
        value,
    )


def clean_city(city):
    city = city.split(",")[0]
    city = re.sub(r"[^\w' -]", " ", city, flags=re.UNICODE)
    city = re.sub(r"\s+", " ", city).strip()
    return city


def fill_address_modal(driver, data):
    print("🏠 Filling address modal")

    modal = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.ID, "co-shipping-form"))
    )

    def by_name(name):
        return modal.find_element(By.NAME, name)

    set_field_js(driver, by_name("firstname"), data["firstName"])
    set_field_js(driver, by_name("lastname"), data["lastName"])

    if data["company"]:
        set_field_js(driver, by_name("company"), data["company"])

    if data["vat"]:
        set_field_js(driver, by_name("vat_id"), data["vat"])

    set_field_js(driver, by_name("street[0]"), data["street"])
    set_field_js(driver, by_name("postcode"), data["zipcode"])
    set_field_js(driver, by_name("city"), clean_city(data["city"]))
    set_field_js(driver, by_name("telephone"), data["phone"])

    Select(by_name("country_id")).select_by_value(data["country"])
    time.sleep(1)

    WebDriverWait(driver, 25).until(
        lambda d: d.execute_script(
            """
            const btn = document.querySelector('button.action-save-address');
            return btn && !btn.disabled;
            """
        )
    )
    print("✅ Address accepted by Magento")


def set_billing_address(driver):
    print("💼 Setting billing address to company address...")

    driver.execute_script(
        """
        const checkbox = document.querySelector('input[name="billing-address-same-as-shipping"]');
        if (checkbox && checkbox.checked) { checkbox.click(); }
        """
    )

    time.sleep(2)
    wait_loader(driver)

    container = WebDriverWait(driver, 30).until(
        lambda d: d.find_element(
            By.CSS_SELECTOR,
            ".payment-method._active .billing-address-form, "
            ".payment-method._active div[name='billingAddress'], "
            ".payment-method._active .payment-method-billing-address, "
            ".billing-address-form, div[name='billingAddress']",
        )
    )

    try:
        select_el = container.find_element(By.CSS_SELECTOR, "select[name='billing_address_id']")
        matched = None
        for opt in select_el.find_elements(By.TAG_NAME, "option"):
            txt = (opt.text or "").lower()
            if (
                BILLING_ADDRESS["lastName"].lower() in txt
                and BILLING_ADDRESS["city"].lower() in txt
            ):
                matched = opt.text
                break
        if matched:
            Select(select_el).select_by_visible_text(matched)
            driver.execute_script(
                "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                select_el,
            )
            time.sleep(1)
    except:
        pass

    def find_in_billing(selectors):
        for selector in selectors:
            try:
                el = container.find_element(By.CSS_SELECTOR, selector)
                if el.is_displayed():
                    return el
            except:
                pass
        return None

    print("📝 Filling billing address form fields...")

    fields = {
        "firstname": ["input[name='firstname']", "input[name*='firstname']"],
        "lastname": ["input[name='lastname']", "input[name*='lastname']"],
        "company": ["input[name='company']", "input[name*='company']"],
        "street": ["input[name='street[0]']", "input[name*='street[0]']"],
        "postcode": ["input[name='postcode']", "input[name*='postcode']"],
        "city": ["input[name='city']", "input[name*='city']"],
        "telephone": ["input[name='telephone']", "input[name*='telephone']"],
    }

    mapping = {
        "firstname": BILLING_ADDRESS["firstName"],
        "lastname": BILLING_ADDRESS["lastName"],
        "company": BILLING_ADDRESS["company"],
        "street": BILLING_ADDRESS["street"],
        "postcode": BILLING_ADDRESS["zipcode"],
        "city": BILLING_ADDRESS["city"],
        "telephone": BILLING_ADDRESS["phone"],
    }

    for key, selectors in fields.items():
        el = find_in_billing(selectors)
        if el:
            set_field_js(driver, el, mapping[key])

    country_el = find_in_billing(["select[name='country_id']", "select[name*='country_id']"])
    if country_el:
        Select(country_el).select_by_value(BILLING_ADDRESS["country"])

    try:
        update_btn = container.find_element(
            By.XPATH,
            ".//following::div[contains(@class,'actions-toolbar')]//button["
            "contains(@class,'action-update') or contains(.,'Bijwerken') "
            "or contains(.,'Update') or contains(.,'Opslaan')]",
        )
        if update_btn.is_displayed():
            driver.execute_script("arguments[0].click();", update_btn)
            time.sleep(2)
            wait_loader(driver)
    except:
        pass

    driver.execute_script(
        """
        try {
            const quote = require('Magento_Checkout/js/model/quote');
            quote.billingAddress({
                firstname: arguments[0], lastname: arguments[1],
                company: arguments[2], street: [arguments[3]],
                postcode: arguments[4], city: arguments[5],
                country_id: arguments[6], telephone: arguments[7]
            });
        } catch(e) { console.log('Billing address error:', e); }
        """,
        BILLING_ADDRESS["firstName"], BILLING_ADDRESS["lastName"],
        BILLING_ADDRESS["company"], BILLING_ADDRESS["street"],
        BILLING_ADDRESS["zipcode"], BILLING_ADDRESS["city"],
        BILLING_ADDRESS["country"], BILLING_ADDRESS["phone"],
    )

    time.sleep(2)
    print("✅ Billing address set")


def click_place_order(driver):
    print("🚀 Finalizing order placement")

    handle_save_address_popup(driver)
    wait_loader(driver)
    accept_terms(driver)

    WebDriverWait(driver, 40).until(
        lambda d: d.execute_script(
            """
            try {
                const q = require('Magento_Checkout/js/model/quote');
                return q.paymentMethod() &&
                       q.shippingMethod() &&
                       document.querySelector('button.action.primary.checkout') &&
                       !document.querySelector('button.action.primary.checkout').disabled;
            } catch(e) { return false; }
            """
        )
    )

    already_clicked = driver.execute_script(
        """
        if (window.__orderSubmitLock) { return true; }
        window.__orderSubmitLock = true;
        return false;
        """
    )
    if already_clicked:
        raise Exception("Order submission already triggered; refusing to click again")

    btn = driver.find_element(By.CSS_SELECTOR, "button.action.primary.checkout")
    driver.execute_script(
        """
        arguments[0].scrollIntoView({block:'center'});
        arguments[0].click();
        arguments[0].disabled = true;
        arguments[0].style.pointerEvents = 'none';
        """,
        btn,
    )

    WebDriverWait(driver, 120).until(
        lambda d: "success" in d.current_url.lower()
        or d.execute_script(
            """
            const b = document.querySelector('button.action.primary.checkout');
            return b && b.disabled;
            """
        )
    )
    print("🎉 Order submitted")
    return True


def add_product_to_cart(driver, sku, qty):
    """Search for a single SKU and add the given qty to cart."""
    print(f"🔍 Adding SKU={sku} qty={qty}")

    driver.get("https://www.cchobby.nl/")
    wait_loader(driver)

    search = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.NAME, "q"))
    )
    search.clear()
    search.send_keys(sku)
    time.sleep(1)
    search.send_keys(Keys.ENTER)

    wait_loader(driver)

    WebDriverWait(driver, 20).until(
        lambda d: d.find_elements(By.CSS_SELECTOR, ".product-item")
    )

    form = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "form[data-role='tocart-form']"))
    )

    # Set quantity via the + button if qty > 1
    if qty > 1:
        try:
            plus_btn = form.find_element(By.CSS_SELECTOR, ".qty-change.increase")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", plus_btn)
            time.sleep(0.5)
            for _ in range(qty - 1):
                driver.execute_script("arguments[0].click();", plus_btn)
                time.sleep(0.3)
            print(f"✅ Qty set via + button: {qty}")
        except Exception as e:
            print(f"❌ Failed to click + button: {e}")
            # Fallback: set qty input directly
            try:
                qty_input = form.find_element(By.CSS_SELECTOR, "input[name='qty']")
                set_field_js(driver, qty_input, str(qty))
            except:
                pass

    # Click Add to Cart
    add_btn = form.find_element(
        By.CSS_SELECTOR, "button.tocart, button.amquote-addto-button"
    )
    driver.execute_script("arguments[0].click();", add_btn)
    wait_loader(driver)

    # Wait for minicart counter to reflect the addition
    WebDriverWait(driver, 40).until(
        lambda d: d.execute_script(
            """
            const c = document.querySelector('.counter-number');
            return c && parseInt(c.innerText || '0') > 0;
            """
        )
    )
    print(f"🛒 SKU {sku} added to cart")


# =====================================================
# MAIN FLOW
# =====================================================

def place_order(driver, order_id):
    try:
        wait = WebDriverWait(driver, 60)
        data = fetch_order_data(order_id)
        print("📦 BACKEND PRODUCTS:", data["products"])

        driver.get("https://www.cchobby.nl/")
        time.sleep(3)
        close_popups(driver)

        clear_cart(driver)

        driver.get("https://www.cchobby.nl/")
        wait_loader(driver)
        close_popups(driver)

        # --------------------------------------------------
        # ADD ALL PRODUCTS TO CART (fixed loop)
        # --------------------------------------------------
        for line in data["products"]:
            sku = str(line["sku"]).strip()
            qty = int(line["qty"])
            add_product_to_cart(driver, sku, qty)

        # --------------------------------------------------
        # PROCEED TO CHECKOUT
        # --------------------------------------------------
        # ── Pre-clear Magento checkout cache BEFORE navigating to checkout ──
        print("🧹 Pre-clearing Magento checkout cache...")
        _clear_magento_checkout_cache(driver)

        driver.get("https://www.cchobby.nl/checkout/")
        wait.until(EC.url_contains("/checkout"))
        wait_loader(driver)

        # ── CRITICAL: force step 1 before doing anything else ──
        force_checkout_to_shipping_step(driver)

        ensure_address_modal_open(driver)
        fill_address_modal(driver, data)
        click_ship_here(driver)
        real_mouse_scroll(driver, 900)

        select_shipping(driver, data)
        click_shipping_next(driver)

        handle_save_address_popup(driver)
        force_totals_recalculation(driver)

        real_mouse_scroll(driver, 600)
        confirm_shipping_js(driver)

        unlock_and_scroll_to_payment(driver)
        human_scroll_to_payment(driver)

        wait_payment_ready(driver)

        try:
            select_bank_transfer(driver)
            print("🛒 select_bank_transfer done")
        except:
            force_banktransfer_js(driver)
            print("🛒 force_banktransfer_js done")

        # ✅ FIXED: single clean JS condition (no double return)
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script(
                """
                try {
                    const q = require('Magento_Checkout/js/model/quote');
                    return q.paymentMethod() &&
                           q.paymentMethod().method === 'banktransfer';
                } catch(e) { return false; }
                """
            )
        )

        wait_payment_ready(driver)
        force_totals(driver)
        wait_loader(driver)

        set_billing_address(driver)
        wait_loader(driver)

        WebDriverWait(driver, 20).until(
            lambda d: "Moordrecht" in d.page_source and "Postbus 3" in d.page_source
        )

        accept_terms(driver)

        driver.execute_script(
            """
            try {
                const q = require('Magento_Checkout/js/model/quote');
                console.log("PAYMENT:", JSON.stringify(q.paymentMethod()));
                console.log("SHIPPING:", JSON.stringify(q.shippingMethod()));
                console.log("TOTALS:", JSON.stringify(q.totals()));
            } catch(e) { console.log(e); }
            """
        )

        click_place_order(driver)

        WebDriverWait(driver, 120).until(
            lambda d: "success" in d.current_url.lower()
            or d.find_elements(By.CSS_SELECTOR, ".checkout-success-container")
            or d.find_elements(By.CSS_SELECTOR, ".checkout-onepage-success")
        )

        order_no = driver.execute_script(
            """
            const el = document.querySelector('.block.thank-you-note span');
            return el ? el.innerText.trim() : null;
            """
        )

        print("📡 Syncing order to backend...")
        print("BACKEND_URL =", BACKEND_URL)
        print("ORDER ID =", order_id)
        print("ORDER NO =", order_no)

        try:
            res = requests.post(
                f"{BACKEND_URL}/v1/order-history/order-sync/{order_id}",
                json={"supplierOrderNumber": order_no, "status": "ORDERED_AT_SUPPLIER"},
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            print("📡 SYNC STATUS:", res.status_code)
            print("📡 SYNC BODY:", res.text)
            res.raise_for_status()
        except Exception as e:
            print("❌ ORDER SYNC FAILED:", repr(e))

        print("🎉 ORDER COMPLETED + SYNCED")
        return order_no

    except Exception as e:
        import traceback
        print("MAIN ERROR:", repr(e))
        traceback.print_exc()
        raise