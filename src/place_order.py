import os, re, time, requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin
from selenium.webdriver.common.keys import Keys

# BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3005")
BACKEND_URL = os.getenv("BACKEND_URL", "http://31.97.78.137:3005")

# YOUR FIXED BILLING ADDRESS
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
                "qty": p.get("quantity") or 1,
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

                # confirm popup if appears
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

    # wait until cart empty message
    WebDriverWait(driver, 20).until(
        lambda d: "winkelwagen" in d.page_source.lower()
        and ("geen" in d.page_source.lower() or "empty" in d.page_source.lower())
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

    driver.execute_script(
        """
        arguments[0].scrollIntoView({block:'center'});
    """,
        btn,
    )

    time.sleep(1)

    driver.execute_script(
        """
        arguments[0].click();
    """,
        btn,
    )
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

    handle_save_address_popup(driver)
    wait_loader(driver)
    accept_terms(driver)

    # wait Magento state ready
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
        print("🛑 Duplicate submission blocked: place order already triggered")
        raise Exception("Order submission already triggered; refusing to click again")

    btn = driver.find_element(By.CSS_SELECTOR, "button.action.primary.checkout")

    print("🖱️ Clicking PLACE ORDER once")

    driver.execute_script(
        """
        arguments[0].scrollIntoView({block:'center'});
        arguments[0].click();
        arguments[0].disabled = true;
        arguments[0].style.pointerEvents = 'none';
    """,
        btn,
    )

    # 🔒 wait until redirect or disabled
    WebDriverWait(driver, 120).until(
        lambda d: "success" in d.current_url.lower()
        or d.execute_script(
            """
                const b=document.querySelector('button.action.primary.checkout');
                return b && b.disabled;
            """
        )
    )

    print("🎉 Order submitted")
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


def set_billing_address(driver):
    print("💼 Setting billing address to company address...")

    # Ensure billing is NOT same as shipping
    driver.execute_script(
        """
        const checkbox = document.querySelector('input[name="billing-address-same-as-shipping"]');
        if (checkbox && checkbox.checked) {
            checkbox.click();
        }
    """
    )

    time.sleep(2)
    wait_loader(driver)

    # Try to locate the billing form inside the active payment method
    container = WebDriverWait(driver, 30).until(
        lambda d: d.find_element(
            By.CSS_SELECTOR,
            ".payment-method._active .billing-address-form, "
            ".payment-method._active div[name='billingAddress'], "
            ".payment-method._active .payment-method-billing-address, "
            ".billing-address-form, div[name='billingAddress']",
        )
    )

    # If Magento shows a billing address dropdown, pick the company address
    try:
        select_el = container.find_element(
            By.CSS_SELECTOR, "select[name='billing_address_id']"
        )
        target_text = (
            f"{BILLING_ADDRESS['firstName']} {BILLING_ADDRESS['lastName']}, "
            f"{BILLING_ADDRESS['street']}, {BILLING_ADDRESS['city']}, "
            f"{BILLING_ADDRESS['zipcode']}"
        ).lower()
        matched = None
        for opt in select_el.find_elements(By.TAG_NAME, "option"):
            txt = (opt.text or "").lower()
            if target_text and target_text in txt:
                matched = opt.text
                break
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

    # If Magento shows address selector cards, choose the company billing address
    driver.execute_script(
        """
        const root = arguments[0];
        const showAll = root.querySelector('button, a');
        if (showAll && /show all|toon alle|alle adressen/i.test(showAll.innerText || '')) {
            showAll.click();
        }
    """,
        container,
    )
    time.sleep(1)

    driver.execute_script(
        """
        const root = arguments[0];
        const target = arguments[1].toLowerCase();
        const cards = Array.from(root.querySelectorAll('.address-item, .billing-address-details, .shipping-address-item, .address-card, li'));
        for (const c of cards) {
            const t = (c.innerText || '').toLowerCase();
            if (t.includes(target)) {
                c.click();
                return true;
            }
        }
        return false;
    """,
        container,
        f"{BILLING_ADDRESS['firstName']} {BILLING_ADDRESS['lastName']} {BILLING_ADDRESS['street']} {BILLING_ADDRESS['zipcode']} {BILLING_ADDRESS['city']}",
    )
    time.sleep(1)

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

    country_el = find_in_billing(
        ["select[name='country_id']", "select[name*='country_id']"]
    )
    if country_el:
        Select(country_el).select_by_value(BILLING_ADDRESS["country"])

    # Click "Bijwerken/Update" if Magento requires explicit save
    try:
        update_btn = container.find_element(
            By.XPATH,
            ".//following::div[contains(@class,'actions-toolbar')]//button[contains(@class,'action-update') or contains(.,'Bijwerken') or contains(.,'Update') or contains(.,'Opslaan')]",
        )
        if update_btn.is_displayed():
            driver.execute_script("arguments[0].click();", update_btn)
            time.sleep(2)
            wait_loader(driver)
    except:
        pass

    # Update quote model as extra safety
    driver.execute_script(
        """
        try {
            const quote = require('Magento_Checkout/js/model/quote');
            quote.billingAddress({
                firstname: arguments[0],
                lastname: arguments[1],
                company: arguments[2],
                street: [arguments[3]],
                postcode: arguments[4],
                city: arguments[5],
                country_id: arguments[6],
                telephone: arguments[7]
            });
            console.log('Billing address set');
        } catch(e) {
            console.log('Billing address error:', e);
        }
    """,
        BILLING_ADDRESS["firstName"],
        BILLING_ADDRESS["lastName"],
        BILLING_ADDRESS["company"],
        BILLING_ADDRESS["street"],
        BILLING_ADDRESS["zipcode"],
        BILLING_ADDRESS["city"],
        BILLING_ADDRESS["country"],
        BILLING_ADDRESS["phone"],
    )

    time.sleep(2)
    print("✅ Billing address set")


def wait_place_order_enabled(driver, timeout=60):
    print("⏳ Waiting for Place Order to enable...")
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script(
                """
                const btn = document.querySelector('button.action.primary.checkout');
                return btn && !btn.disabled;
            """
            )
        )
        print("✅ Place Order enabled")
        return True
    except:
        # Diagnostics
        state = driver.execute_script(
            """
            const btn = document.querySelector('button.action.primary.checkout');
            const agreements = Array.from(
              document.querySelectorAll('.checkout-agreement input[type=checkbox]')
            );
            let agreementsUnchecked = agreements.filter(cb => !cb.checked).length;
            let payment = null;
            let shipping = null;
            let totals = null;
            let billing = null;
            try {
              const q = require('Magento_Checkout/js/model/quote');
              payment = q.paymentMethod();
              shipping = q.shippingMethod();
              totals = q.totals();
              billing = q.billingAddress();
            } catch(e) {}
            return {
              btnDisabled: btn ? btn.disabled : null,
              agreementsUnchecked,
              payment,
              shipping,
              totals,
              billing
            };
            """
        )
        print("❌ Place Order still disabled. Debug state:", state)
        return False


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

        print("📍 After home redirect:", driver.current_url)

        # if already redirected somewhere else, don't wait for search box
        if (
            "catalogsearch" not in driver.current_url.lower()
            and "/product" not in driver.current_url.lower()
        ):

            close_popups(driver)

            WebDriverWait(driver, 40).until(
                lambda d: d.execute_script(
                    """
                    return document.querySelectorAll('input[name="q"]').length > 0;
                """
                )
            )
        # --------------------------------------------------
        # SEARCH PRODUCT
        # --------------------------------------------------
        for line in data["products"]:

            sku = line["sku"]
            qty = line["qty"]

            print("🔎 Searching SKU:", sku)

            inputs = driver.find_elements(By.NAME, "q")
            search = next(i for i in inputs if i.is_displayed())

            search.clear()
            for ch in sku:
                search.send_keys(ch)
                time.sleep(0.12)

            search.send_keys(Keys.ENTER)

            WebDriverWait(driver, 40).until(
                lambda d: d.execute_script(
                    """
                    return document.querySelectorAll('.product-item-link').length > 0
                        || window.location.href.includes('catalogsearch');
                    """
                )
            )

            add_btn = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button.amquote-addto-button, button.tocart")
                )
            )

            try:
                qty_input = add_btn.find_element(
                    By.XPATH,
                    "./ancestor::*[contains(@class,'product-item')]//input[contains(@class,'qty')]",
                )
                qty_input.clear()
                qty_input.send_keys(str(qty))
            except:
                pass

            js_click(driver, add_btn)
            wait_loader(driver)

        # wait minicart update
        WebDriverWait(driver, 40).until(
            lambda d: d.execute_script(
                """
                const c = document.querySelector('.counter-number');
                return c && parseInt(c.innerText || '0') > 0;
            """
            )
        )

        print("🛒 Cart updated")

        driver.get("https://www.cchobby.nl/checkout/")
        wait.until(EC.url_contains("/checkout"))
        wait_loader(driver)

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

        # handle_save_address_popup(driver)

        unlock_and_scroll_to_payment(driver)
        human_scroll_to_payment(driver)

        wait_payment_ready(driver)

        try:
            select_bank_transfer(driver)
            print("🛒 select_bank_transfer updated")
        except:
            force_banktransfer_js(driver)
            print("🛒 select_bank_transfer updated")

        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script(
                """
                try {
                    return require('Magento_Checkout/js/model/quote')
                        return window.checkoutConfig
                        && require('Magento_Checkout/js/model/quote').paymentMethod()
                        && require('Magento_Checkout/js/model/quote').paymentMethod().method === 'banktransfer';

                } catch(e) { return false; }
            """
            )
        )

        wait_payment_ready(driver)
        set_billing_address(driver)
        force_totals(driver)

        wait_loader(driver)
        accept_terms(driver)
        wait_place_order_enabled(driver)

        driver.execute_script(
            """
        try {
        const q=require('Magento_Checkout/js/model/quote');
        console.log("PAYMENT:", q.paymentMethod());
        console.log("SHIPPING:", q.shippingMethod());
        console.log("TOTALS:", q.totals());
        } catch(e){console.log(e);}
        """
        )

        click_place_order(driver)

        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".checkout-success-container")
            )
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

        print("📡 Syncing order to backend...")
        print("BACKEND_URL =", BACKEND_URL)
        print("ORDER ID =", order_id)
        print("ORDER NO =", order_no)

        try:
            res = requests.post(
                f"{BACKEND_URL}/v1/order-history/order-sync/{order_id}",
                json={"supplierOrderNumber": order_no, "status": "ORDERED_AT_SUPPLIER"},
                headers={
                    "Content-Type": "application/json",
                },
                timeout=15,
            )

            print("📡 SYNC STATUS:", res.status_code)
            print("📡 SYNC BODY:", res.text)

            res.raise_for_status()

        except Exception as e:
            print("❌ ORDER SYNC FAILED:", repr(e))

        print("🎉 ORDER COMPLETED + SYNCED")
        print("🏁 Finished placement attempts.")
        return order_no

    except Exception as e:
        import traceback

        print("MAIN ERROR:", repr(e))
        traceback.print_exc()
        raise
