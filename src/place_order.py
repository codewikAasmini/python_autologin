import os
import time
import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3005")


def fetch_order_data(order_id):
    res = requests.get(
        f"{BACKEND_URL}/v1/order-history/internal/{order_id}",
        timeout=15,
    )
    res.raise_for_status()
    order = res.json()

    return {
        "sku": order["product"]["articleNo"],
        "qty": order.get("quantity", 1),
        "email": order["customer"]["email"],
        "firstName": order["customer"]["firstName"],
        "lastName": order["customer"]["lastName"],
        "street": order["shippingAddress"]["street"],
        "zipcode": order["shippingAddress"]["zipcode"],
        "city": order["shippingAddress"]["city"],
        "phone": order["customer"].get("phone", "0000000000"),
    }


def js_click(driver, el):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(1)
    driver.execute_script("arguments[0].click();", el)


def wait_for_loading(driver, timeout=30):
    """Wait for Magento loading masks to disappear."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, ".loading-mask, .loader"))
        )
    except:
        pass


def close_popups(driver):
    """Close known popups like newsletter or cookie banners."""
    selectors = [
        ".modal-popup .action-close",  # Magento newsletter/modal close
        ".newsletter-modal .action-close",
        ".am-close",                  # Common Magento popup close
        "button.action-close",
        ".privacy-policy-banner-close",
        "#btn-cookie-allow",
        ".close-button",
        "button[aria-label='Close']",
        ".amasty-hide",               # Sometimes used to hide popups
    ]
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                if el.is_displayed():
                    # Try both standard and JS click for closing popups
                    try:
                        el.click()
                    except:
                        driver.execute_script("arguments[0].click();", el)
                    time.sleep(0.5)
        except:
            pass
    
    # Special handling for that big newsletter modal if it persists
    try:
        driver.execute_script("""
            var modals = document.querySelectorAll('.modal-popup, .newsletter-modal');
            modals.forEach(function(m) { m.style.display = 'none'; });
            var overlays = document.querySelectorAll('.modals-overlay');
            overlays.forEach(function(o) { o.style.display = 'none'; });
            document.body.classList.remove('_has-modal');
        """)
    except:
        pass


def place_order(driver, order_id):
    wait = WebDriverWait(driver, 90)
    supplier_order_no = None

    data = fetch_order_data(order_id)
    print("Placing order:", order_id)

    # 1️⃣ Home
    driver.get("https://www.cchobby.nl/")
    wait.until(EC.presence_of_element_located((By.NAME, "q")))

    # 2️⃣ Search SKU
    search = driver.find_element(By.NAME, "q")
    search.clear()
    search.send_keys(data["sku"])
    search.submit()

    # Handle search results and popups
    time.sleep(3)
    close_popups(driver)

    # 3️⃣ Product page
    if "/checkout/cart" not in driver.current_url and "/catalog/product/view" not in driver.current_url:
        try:
            product_link_selectors = [
                ".product-item-link",
                "a.product.photo.product-item-photo",
                ".product-item-name a",
                f"a[href*='{data['sku']}']"
            ]
            
            product_link = None
            for selector in product_link_selectors:
                try:
                    product_link = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    if product_link:
                        break
                except:
                    continue
            
            if product_link:
                js_click(driver, product_link)
            else:
                driver.find_element(By.CSS_SELECTOR, ".product-item-info a").click()
        except Exception as e:
            print(f"Could not find product link: {e}")

    wait_for_loading(driver)
    time.sleep(2)
    close_popups(driver)

    # 4️⃣ Quantity
    try:
        qty = wait.until(EC.presence_of_element_located((By.NAME, "qty")))
        qty.clear()
        qty.send_keys(str(data["qty"]))
    except:
        pass

    # 5️⃣ Add to cart
    wait.until(EC.element_to_be_clickable(
        (By.ID, "product-addtocart-button")
    )).click()
    
    # 6️⃣ Go to checkout (Bekijk winkelwagen)
    time.sleep(2)
    close_popups(driver)
    
    try:
        # Strategy 1: Standard Wait and Click
        view_cart_xpath = "//a[contains(@class, 'viewcart')] | //a[.//span[contains(text(), 'Bekijk winkelwagen')]] | //button[contains(., 'Bekijk winkelwagen')]"
        view_cart_btn = wait.until(EC.presence_of_element_located((By.XPATH, view_cart_xpath)))
        
        # Strategy 2: Use JS to click the button by text if Strategy 1 element is blocked
        driver.execute_script("""
            var buttons = document.querySelectorAll('a, button');
            for (var i = 0; i < buttons.length; i++) {
                if (buttons[i].textContent.includes('Bekijk winkelwagen') && buttons[i].offsetWidth > 0) {
                    buttons[i].click();
                    return true;
                }
            }
            return false;
        """)
        time.sleep(2)
        
        # If we're still on the product page, try Strategy 1's element with js_click
        if "/checkout/cart" not in driver.current_url:
            js_click(driver, view_cart_btn)
            
    except Exception as e:
        print(f"Sidebar click failed, navigating directly: {e}")
        driver.get("https://www.cchobby.nl/checkout/cart/")

    # 7️⃣ Cart to Checkout
    wait.until(EC.url_contains("/cart"))
    wait_for_loading(driver)
    close_popups(driver)
    
    try:
        checkout_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.action.primary.checkout")))
        js_click(driver, checkout_btn)
    except:
        driver.get("https://www.cchobby.nl/checkout/")

    # 8️⃣ Checkout Form
    wait.until(EC.url_contains("/checkout"))
    wait_for_loading(driver)
    close_popups(driver)
    wait.until(EC.presence_of_element_located((By.NAME, "email")))

    email_field = driver.find_element(By.NAME, "email")
    email_field.clear()
    email_field.send_keys(data["email"])
    time.sleep(2)  

    wait_for_loading(driver)
    driver.find_element(By.NAME, "firstname").send_keys(data["firstName"])
    driver.find_element(By.NAME, "lastname").send_keys(data["lastName"])
    driver.find_element(By.NAME, "street[0]").send_keys(data["street"])
    driver.find_element(By.NAME, "postcode").send_keys(data["zipcode"])
    driver.find_element(By.NAME, "city").send_keys(data["city"])
    driver.find_element(By.NAME, "telephone").send_keys(data["phone"])

    wait_for_loading(driver)
    try:
        shipping_method = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input.radio")))
        if not shipping_method.is_selected():
            js_click(driver, shipping_method)
    except:
        pass

    wait_for_loading(driver)
    close_popups(driver)

    # 9️⃣ Final Place Order
    place_btn_xpath = "//button[contains(@class, 'checkout')]//span[contains(text(), 'Plaats bestelling')] | //button[@title='Plaats bestelling']"
    place_btn = wait.until(EC.element_to_be_clickable((By.XPATH, place_btn_xpath)))
    js_click(driver, place_btn)
    
    supplier_order_no = wait.until(EC.presence_of_element_located((
        By.XPATH,
        "//*[contains(text(),'Ordernummer') or contains(text(),'Order number')]"
    ))).text.strip()

    print("SUPPLIER ORDER:", supplier_order_no)
    return supplier_order_no
