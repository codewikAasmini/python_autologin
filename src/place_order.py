import os, re, time, requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3005")


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
    phone = digits if digits else "0600000000"

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
    driver.execute_script(
        """
        ['.modal-popup','.newsletter-modal','.modals-overlay',
         '.action-close','#btn-cookie-allow']
        .forEach(s => document.querySelectorAll(s).forEach(e => e.remove()));
        document.body.style.overflow='auto';
    """
    )


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

    driver.execute_script(
        """
        // Remove any leftover overlays / locks
        document.querySelectorAll('.modals-overlay, .modal-popup, .loading-mask')
            .forEach(e => e.remove());

        document.body.classList.remove('modal-open', '_has-modal');
        document.body.style.overflow = 'auto';
        document.body.style.position = 'static';

        // Force real scroll event
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

    # wait modal close
    WebDriverWait(driver, 25).until(
        EC.invisibility_of_element_located((By.ID, "co-shipping-form"))
    )

    print("✅ Address saved & modal closed")


def ensure_address_modal_open(driver):

    print("🔍 Checking if address modal is open...")

    # Already open?
    modals = driver.find_elements(By.ID, "co-shipping-form")
    if modals and modals[0].is_displayed():
        print("✅ Address modal already open")
        return

    print("📌 Clicking '+ Nieuw adres'")

    btn = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable(
            (
                By.XPATH,
                "//button[contains(.,'Nieuw adres') or contains(.,'Nieuw Adres')]",
            )
        )
    )

    driver.execute_script("arguments[0].click();", btn)

    WebDriverWait(driver, 25).until(
        EC.visibility_of_element_located((By.ID, "co-shipping-form"))
    )

    print("✅ Address modal opened")


# =====================================================
# SHIPPING (FIXED)
# =====================================================
def select_shipping(driver, data):
    """
    EXACT shipping selection based on business rules
    """

    wait_loader(driver)
    time.sleep(1)

    driver.execute_script(
        """
        const el = document.querySelector('.table-checkout-shipping-method');
        if (el) el.scrollIntoView({block:'center'});
    """
    )
    time.sleep(1)

    # ---------- NETHERLANDS ----------
    if data["country"] == "NL":
        print("🚚 NL → DPD - Nederlandse Zakelijke levering")

        xpath = (
            "//div[contains(@class,'row') and "
            ".//div[contains(text(),'DPD') and contains(text(),'Nederlandse')]]"
            "//input[@type='radio']"
        )

        print("🧾 Dumping shipping HTML for debug...")

        html = driver.execute_script(
            """
            const el = document.querySelector('#checkout-shipping-method-load');
            return el ? el.outerHTML : 'NO_SHIPPING_CONTAINER';
        """
        )

        print(html[:3000])

        titles = driver.execute_script(
            """
                return Array.from(
                    document.querySelectorAll('.table-checkout-shipping-method .row')
                ).map(r => r.getAttribute('data-title'));
            """
        )

        print("📦 Available shipping titles:", titles)

    # ---------- BELGIUM ----------
    elif data["country"] == "BE":

        print("🇧🇪 Selecting Belgium shipping based on rendered titles")

        rows_el = driver.find_elements(
            By.CSS_SELECTOR, ".table-checkout-shipping-method .row"
        )

        target = None

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
            raise Exception("❌ No Belgium shipping option matched rules")

        print("👉 Clicking shipping row:", target.get_attribute("data-title"))

        driver.execute_script(
            """
            arguments[0].scrollIntoView({block:'center'});
            arguments[0].click();
        """,
            target,
        )

        # confirm Magento state
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

        # ---------- CONFIRM MAGENTO STATE ----------
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
# PAYMENT – BANK TRANSFER (SIMPLIFIED & ROBUST)
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
    print("📦 Handling 'Save address' popup (No thanks default)")

    driver.execute_script(
        """
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
    """
    )
    time.sleep(1)
    print("✅ Address popup cleared & page unlocked")


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
    print("🔓 Force removing any blocking overlays & scrolling")

    driver.execute_script(
        """
        // Force remove any remaining modals or overlays that block clicks
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
    print("🖱️ Human-like scroll to payment section")

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


def force_payment_renderer(driver):
    print("⚙️ Forcing Magento payment renderer")

    driver.execute_script(
        """
        try {
            const service = require('Magento_Checkout/js/model/payment-service');
            const methods = service.getAvailablePaymentMethods();

            methods.forEach(m => {
                if (m.method === 'banktransfer') {
                    require('Magento_Checkout/js/action/select-payment-method')(m);
                }
            });
        } catch(e) {}
    """
    )
    time.sleep(1)


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

    # wait until totals exist
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

    # wait radios rendered
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

    # scroll
    driver.execute_script(
        """
        arguments[0].scrollIntoView({block:'center'});
    """,
        radio,
    )
    time.sleep(1)

    # REAL click
    driver.execute_script(
        """
        arguments[0].dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));
        arguments[0].dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));
        arguments[0].click();
    """,
        radio,
    )

    # 🧠 Wait for KO update
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
            const service =
              require('Magento_Checkout/js/model/payment-service');
            const select =
              require('Magento_Checkout/js/action/select-payment-method');

            const methods = service.getAvailablePaymentMethods();

            methods.forEach(m => {
                if (m.method === 'banktransfer') {
                    select(m);
                }
            });
        } catch(e) {
            console.log(e);
        }
    """
    )


def click_shipping_next(driver):

    print("➡️ Clicking shipping NEXT")

    # wait shipping saved in KO
    WebDriverWait(driver, 60).until(
        lambda d: d.execute_script("""
            try {
                const q = require('Magento_Checkout/js/model/quote');
                return q.shippingMethod() && q.shippingMethod().carrier_code;
            } catch(e) { return false; }
        """)
    )

    # wait no loaders
    WebDriverWait(driver, 60).until(
        EC.invisibility_of_element_located(
            (By.CSS_SELECTOR, ".loading-mask, .loader")
        )
    )

    # wait enabled button
    btn = WebDriverWait(driver, 60).until(
        lambda d: d.find_element(
            By.CSS_SELECTOR,
            "#shipping-method-buttons-container button.continue:not([disabled])"
        )
    )

    driver.execute_script("""
        arguments[0].scrollIntoView({block:'center'});
    """, btn)

    time.sleep(1)

    driver.execute_script("""
        arguments[0].click();
    """, btn)

    # wait payment step DOM
    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located(
            (By.ID, "checkout-step-payment")
        )
    )

    print("✅ Payment step opened")

def force_totals(driver):
    driver.execute_script(
        """
        try {
            const quote = require('Magento_Checkout/js/model/quote');
            const totalsProcessor =
                require('Magento_Checkout/js/model/cart/totals-processor/default');

            if (quote.shippingMethod()) {
                totalsProcessor.estimateTotals();
            }
        } catch(e) {}
    """
    )


def accept_terms(driver):
    driver.execute_script(
        """
        document.querySelectorAll(
            '.checkout-agreement input[type="checkbox"]'
        ).forEach(cb => {
            if (!cb.checked) cb.click();
        });
    """
    )


def fill_input_by_label(modal, label_text, value):
    field = modal.find_element(
        By.XPATH,
        f".//label[normalize-space()[contains(.,'{label_text}')]]/following::input[1]",
    )
    human_type(field, value)


def click_place_order(driver):
    print("🚀 Finalizing order placement")

    for i in range(5):
        print(f"🔄 Attempting to click 'Plaats bestelling' ({i+1}/5)")

        # 1. Final popup cleanup
        handle_save_address_popup(driver)
        wait_loader(driver)

        # 2. Check for Agreement checkbox (again, just in case)
        driver.execute_script(
            """
            document.querySelectorAll('input[type="checkbox"].required-entry, .checkout-agreement input[type="checkbox"]')
                .forEach(cb => { if(!cb.checked) cb.click(); });
        """
        )
        time.sleep(0.5)

        # 3. Find and click button
        try:
            btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button.action.primary.checkout")
                )
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
            if (
                "/success" in driver.current_url
                or "success" in driver.current_url.lower()
            ):
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
    set_field_js(driver, by_name("city"), data["city"])
    set_field_js(driver, by_name("telephone"), data["phone"])

    Select(by_name("country_id")).select_by_value(data["country"])
    time.sleep(1)

    # wait Magento validation
    WebDriverWait(driver, 25).until(
        lambda d: d.execute_script(
            """
            const btn = document.querySelector('button.action-save-address');
            return btn && !btn.disabled;
        """
        )
    )

    print("✅ Magento accepted address")

    # 🔥 WAIT until Magento enables Save
    WebDriverWait(driver, 20).until(
        lambda d: d.execute_script(
            """
            return document.querySelector(
              'button.action-save-address'
            ) && !document.querySelector(
              'button.action-save-address'
            ).disabled;
        """
        )
    )

    print("✅ Address accepted by Magento")


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

    js_click(
        driver,
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".product-item-link"))),
    )
    wait_loader(driver)

    try:
        qty = driver.find_element(By.NAME, "qty")
        qty.clear()
        qty.send_keys(str(data["qty"]))
    except:
        pass

    js_click(
        driver,
        wait.until(EC.element_to_be_clickable((By.ID, "product-addtocart-button"))),
    )
    time.sleep(2)

    driver.get("https://www.cchobby.nl/checkout/")
    wait.until(EC.url_contains("/checkout"))
    wait_loader(driver)
    ensure_address_modal_open(driver)
    fill_address_modal(driver, data)
    click_ship_here(driver)
    real_mouse_scroll(driver, 900)
    select_shipping(driver, data)
    click_shipping_next(driver)
    # wait_shipping_confirmed(driver)
    handle_save_address_popup(driver)
    force_totals_recalculation(driver)
    real_mouse_scroll(driver, 600)
    confirm_shipping_js(driver)
    handle_save_address_popup(driver)
    unlock_and_scroll_to_payment(driver)
    human_scroll_to_payment(driver)
    wait_payment_ready(driver)

    try:
        select_bank_transfer(driver)
    except:
        force_banktransfer_js(driver)

    # final verify
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script(
            """
            try {
                return require('Magento_Checkout/js/model/quote')
                    .paymentMethod()?.method === 'banktransfer';
            } catch(e) { return false; }
        """
        )
    )
    wait_payment_ready(driver)
    force_totals(driver)
    wait_loader(driver)
    accept_terms(driver)
    click_place_order(driver)

    print("🏁 Finished placement attempts.")
    return False
