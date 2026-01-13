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
    ]
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                if el.is_displayed():
                    el.click()
                    time.sleep(0.5)
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
    # Sometimes search redirects directly to product page, check for that
    if "/checkout/cart" not in driver.current_url and "/catalog/product/view" not in driver.current_url:
        try:
            # Try finding the product link in search results
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
                # Last resort: click anything that looks like a product link
                driver.find_element(By.CSS_SELECTOR, ".product-item-info a").click()
        except Exception as e:
            print(f"Could not find product link: {e}")
            # If we are already on a product page, this will just fail and continue

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
    time.sleep(2)
    close_popups(driver)

    # 6️⃣ Go to checkout
    try:
        # Check for sidebar checkout button first
        checkout_btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button.checkout.viewcart, .action.primary.checkout")
        ))
        checkout_btn.click()
    except:
        driver.get("https://www.cchobby.nl/checkout/cart/")
        wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button.action.primary.checkout")
        )).click()

    # 7️⃣ Wait checkout form
    wait.until(EC.url_contains("/checkout"))
    wait_for_loading(driver)
    close_popups(driver)
    wait.until(EC.presence_of_element_located((By.NAME, "email")))

    # 8️⃣ Fill billing details
    email_field = driver.find_element(By.NAME, "email")
    email_field.clear()
    email_field.send_keys(data["email"])
    time.sleep(2)  # Wait for email validation/account check

    wait_for_loading(driver)
    driver.find_element(By.NAME, "firstname").send_keys(data["firstName"])
    driver.find_element(By.NAME, "lastname").send_keys(data["lastName"])
    driver.find_element(By.NAME, "street[0]").send_keys(data["street"])
    driver.find_element(By.NAME, "postcode").send_keys(data["zipcode"])
    driver.find_element(By.NAME, "city").send_keys(data["city"])
    driver.find_element(By.NAME, "telephone").send_keys(data["phone"])

    # Wait for shipping methods to load and select first one if not selected
    wait_for_loading(driver)
    try:
        shipping_method = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input.radio")))
        if not shipping_method.is_selected():
            js_click(driver, shipping_method)
    except:
        pass

    wait_for_loading(driver)
    close_popups(driver)

    # 9️⃣ Place order
    # The button text is "Plaats bestelling"
    place_btn_xpath = "//button[contains(@class, 'checkout')]//span[contains(text(), 'Plaats bestelling')] | //button[@title='Plaats bestelling']"
    place_btn = wait.until(EC.element_to_be_clickable((By.XPATH, place_btn_xpath)))

    # Ensure it's scrolled into view and clickable
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", place_btn)
    time.sleep(2)
    js_click(driver, place_btn)

    # 🔟 Wait for success and get order number
    supplier_order_no = wait.until(EC.presence_of_element_located((
        By.XPATH,
        "//*[contains(text(),'Ordernummer') or contains(text(),'Order number')]"
    ))).text.strip()

    print("SUPPLIER ORDER:", supplier_order_no)
    return supplier_order_no
